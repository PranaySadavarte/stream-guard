"""No-device replay benchmark. Uses only generated speech, never microphone audio."""
import json
import argparse
import os

# Yield CPU priority to foreground apps; this affects only this replay process.
if os.name == "nt":
    import ctypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    if not kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000):
        raise ctypes.WinError(ctypes.get_last_error())
from pathlib import Path
import time
from types import SimpleNamespace
import numpy as np
from streamguard.config import AudioSettings
from streamguard.audio.censor import CensorSettings
from streamguard.detection.profanity import ProfanityDictionary
from streamguard.detection.vosk_backend import VoskDetector
from streamguard.detection.bounded_vosk import BoundedVoskDetector
from streamguard.detection.base import Word
from streamguard.offline import read_wav
from streamguard.offline import _stream_words
from streamguard.telemetry import masked_event
from streamguard.pipeline.controller import LiveController

parser=argparse.ArgumentParser()
parser.add_argument('--keywords',action='store_true')
parser.add_argument('--scheduled',action='store_true',help='simulate callbacks arriving during measured inference work')
parser.add_argument('--window-ms',type=int)
parser.add_argument('--hop-ms',type=int)
parser.add_argument('--delay-ms',type=int)
parser.add_argument('--phase-sweep',action='store_true')
args=parser.parse_args()

root=Path(__file__).resolve().parents[1]
model=root/'models/vosk-model-small-en-us-0.15'
fixtures=[]
for name,count in [('clean',0),('profanity',1),('repeated',2)]:
    source,rate=read_wav(root/f'recordings/fixtures/{name}.wav')
    fixtures.append((name,source,rate,count))
speech=[]
for name,source,rate,count in fixtures:
    active=np.flatnonzero(np.abs(source[:,0])>.005)
    speech.append(source[max(0,active[0]-160):min(len(source),active[-1]+160)])
continuous=np.concatenate(speech*4)
fixtures.append(('continuous',continuous,rate,12))
references={}
for name,source,rate,expected in fixtures:
    words=_stream_words(source,rate,VoskDetector(model))
    references[name]=[w for w in words if ProfanityDictionary().matches(w.text)]
if args.phase_sweep:
    for name,source,rate,expected in list(fixtures):
        if name=='continuous':continue
        for ms in (100,200,300,400):
            key=f'{name}-offset-{ms}'
            fixtures.append((key,np.concatenate([np.zeros((round(ms*rate/1000),1),dtype=np.float32),source]),rate,expected))
            references[key]=[Word(w.text,w.start+ms/1000,w.end+ms/1000,w.confidence) for w in references[name]]
report=[]
if any(value is not None for value in (args.window_ms,args.hop_ms,args.delay_ms)):
    if any(value is None for value in (args.window_ms,args.hop_ms,args.delay_ms)):parser.error('provide window, hop and delay together')
    configurations=[(args.window_ms,args.hop_ms,args.delay_ms)]
else:configurations=[(1000,250,1500),(1500,500,2000)] if args.keywords else [(None,None,3000),(1000,250,1500),(1500,500,2000)]
for window,hop,delay in configurations:
    for name,source,rate,expected in fixtures:
        detector=VoskDetector(model) if window is None else BoundedVoskDetector(model,window,hop,
            terms=ProfanityDictionary().terms if args.keywords else None)
        settings=AudioSettings(0,1,sample_rate=rate,delay_ms=delay)
        live=LiveController(settings,detector,ProfanityDictionary(),CensorSettings())
        detector.start(rate);block=live.block
        padded=np.zeros(((len(source)+rate*5+block-1)//block*block,1),dtype=np.float32);padded[:len(source)]=source
        output=np.zeros_like(padded);durations=[];began=time.perf_counter()
        try:
            if args.scheduled:
                # Infer synchronously but postpone publication until measured work
                # completes. During that interval virtual device callbacks continue.
                clock=[0.0,0];base_process=detector.process_audio
                def pump(until):
                    while clock[1]*block<len(padded) and clock[1]*block/rate<=until:
                        start=clock[1]*block
                        live.callback(padded[start:start+block],output[start:start+block],block,
                            SimpleNamespace(inputBufferAdcTime=start/rate,currentTime=start/rate),False)
                        clock[1]+=1
                    clock[0]=until
                def timed_process(audio):
                    t=time.perf_counter();result=base_process(audio)
                    pump(clock[0]+time.perf_counter()-t)
                    return result
                detector.process_audio=timed_process
                while (clock[1]*block<len(padded) or live.mailbox.depth) and not live.fault:
                    item=live.mailbox.pop()
                    if item is None:pump(clock[1]*block/rate);continue
                    audio,position=item;t=time.perf_counter()
                    for sample,sanitized in live.engine.process(position,audio,live.playback_sample,lambda:live.captured):
                        live.ready[(sample//block)%live.capacity]=(sample,sanitized)
                    durations.append((time.perf_counter()-t)*1000)
            else:
              for start in range(0,len(padded),block):
                live.callback(padded[start:start+block],output[start:start+block],block,
                    SimpleNamespace(inputBufferAdcTime=start/rate,currentTime=start/rate),False)
                item=live.mailbox.pop()
                if item:
                    audio,position=item;t=time.perf_counter()
                    for sample,sanitized in live.engine.process(position,audio,live.playback_sample,live.captured):
                        live.ready[(sample//block)%live.capacity]=(sample,sanitized)
                    durations.append((time.perf_counter()-t)*1000)
            elapsed=time.perf_counter()-began
            aligned=output[settings.delay_samples:settings.delay_samples+len(source)]
            active=np.abs(source[:,0])>.01
            lost=int(np.sum(active & (np.abs(aligned[:,0])<1e-7)))
            status=live.engine.snapshot()
            reference=references[name];coverage=[];outside=np.ones(len(source),dtype=bool)
            for word in reference:
                lo=max(0,round(word.start*rate));hi=min(len(source),round(word.end*rate))
                speech=active[lo:hi]
                replaced=np.abs(aligned[lo:hi,0]-source[lo:hi,0])>=1/32768
                coverage.append(float(np.mean(replaced[speech])) if np.any(speech) else 1.0)
                outside[max(0,lo-round(.155*rate)):min(len(source),hi+round(.155*rate))]=False
            clean=outside & active
            result={'backend':'sentence' if window is None else f'window-{window}-hop-{hop}'+('-keywords' if args.keywords else ''),
                    'scheduled_replay':args.scheduled,
                    'fixture':name,'seconds':round(len(source)/rate,2),'delay_ms':delay,
                    'reference_terms':len(reference),'reference_word_replaced_percent':[round(c*100,2) for c in coverage],
                    'clean_outside_reference_unchanged_percent':round(100*float(np.mean(
                        (np.abs(aligned[:,0]-source[:,0])<1/32768)[clean])),2) if np.any(clean) else 100,
                    'events':[masked_event(e) for e in status['events']],
                    'detected':status['detected'],'expected':expected,'error':live.fault,
                    'active_speech_zeroed_percent':round(100*lost/max(1,np.sum(active)),2),
                    'realtime_factor':round(elapsed/(len(padded)/rate),3),
                    'processing_ms':dict(zip(['p50','p95','p99','max'],
                        [round(float(x),2) for x in [*np.percentile(durations,[50,95,99]),max(durations)]])),
                    'release_age_ms':status['release_age_ms'],'detection_latency_ms':status['detection_latency_ms']}
            report.append(result)
            suffix=('-keywords' if args.keywords else '')+('-scheduled' if args.scheduled else '')
            if args.window_ms:suffix+=f'-{args.window_ms}-{args.hop_ms}-{args.delay_ms}'
            if args.phase_sweep:suffix+='-phases'
            (root/f'recordings/live-windows{suffix}-report.json').write_text(json.dumps(report,indent=2))
            print(json.dumps(result),flush=True)
        finally:detector.stop()
