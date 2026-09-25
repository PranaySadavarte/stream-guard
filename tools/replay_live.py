"""Actual Vosk through the live release algorithm, using generated speech."""
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from streamguard.config import AudioSettings
from streamguard.audio.censor import CensorSettings
from streamguard.detection.vosk_backend import VoskDetector
from streamguard.detection.profanity import ProfanityDictionary
from streamguard.offline import read_wav, write_wav
from streamguard.pipeline.controller import LiveController


def main():
    root = Path(__file__).resolve().parents[1]
    results = []
    for name in ('clean','profanity','repeated'):
        source,rate = read_wav(root/f'recordings/fixtures/{name}.wav')
        settings = AudioSettings(0,1,sample_rate=rate,delay_ms=3000)
        detector = VoskDetector(root/'models/vosk-model-small-en-us-0.15')
        live = LiveController(settings,detector,ProfanityDictionary(),CensorSettings())
        detector.start(rate)
        block=live.block
        padded = np.zeros(((len(source)+rate*6+block-1)//block*block,1),dtype=np.float32)
        padded[:len(source)] = source
        output=np.zeros_like(padded)
        try:
            for start in range(0,len(padded),block):
                live.callback(padded[start:start+block],output[start:start+block],block,
                              SimpleNamespace(inputBufferAdcTime=start/rate,currentTime=start/rate),False)
                item=live.mailbox.pop()
                if item:
                    audio, position=item
                    for sample,sanitized in live.engine.process(position,audio,live.playback_sample,live.captured):
                        live.ready[(sample//block)%live.capacity]=(sample,sanitized)
            status=live.engine.snapshot()
            aligned=output[settings.delay_samples:settings.delay_samples+len(source)]
            active=np.abs(source[:,0])>.01
            preserved=np.abs(aligned[:,0]-source[:,0])<1/32768
            write_wav(root/f'recordings/{name}-live.wav',output,rate)
            results.append({'fixture':name, 'detected':status['detected'],
                            'events':status['events'], 'muted_ms':live.muted_samples/rate*1000,
                            'released_ms':live.released_samples/rate*1000,
                            'error':live.fault, 'delay_ms':3000,
                            'active_samples_unchanged_percent':float(100*np.mean(preserved[active])) if np.any(active) else 100})
        finally: detector.stop()
    (root/'recordings/live-replay-report.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
