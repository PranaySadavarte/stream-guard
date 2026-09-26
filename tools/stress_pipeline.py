"""Accelerated ten-minute pipeline soak using an immediate test-only detector."""
import json
from types import SimpleNamespace
import time
import numpy as np
from streamguard.audio.censor import CensorSettings
from streamguard.config import AudioSettings
from streamguard.detection.base import Detection
from streamguard.detection.profanity import ProfanityDictionary
from streamguard.pipeline.controller import LiveController


class Immediate:
    def __init__(self):self.samples=0
    def process_audio(self,a):self.samples+=len(a);return Detection((),self.samples)
    def stop(self):pass


settings=AudioSettings(0,1,sample_rate=16000,delay_ms=1500)
live=LiveController(settings,Immediate(),ProfanityDictionary(),CensorSettings())
incoming=np.full((320,1),.123,dtype=np.float32);output=np.empty_like(incoming)
start=time.perf_counter();max_pending=0;max_queue=0
for index in range(30000):
    live.callback(incoming,output,320,SimpleNamespace(inputBufferAdcTime=index*.02,currentTime=index*.02),False)
    if index>=75:np.testing.assert_array_equal(output,incoming)
    audio,position=live.mailbox.pop()
    for pos,sanitized in live.engine.process(position,audio,live.playback_sample,live.captured):
        live.ready[(pos//320)%live.capacity]=(pos,sanitized)
    max_pending=max(max_pending,len(live.engine.pending));max_queue=max(max_queue,live.mailbox.depth)
assert not live.fault and live.muted_samples==0
print(json.dumps({'simulated_seconds':600,'wall_seconds':time.perf_counter()-start,
    'max_pending_blocks':max_pending,'output_slots':len(live.ready),
    'capture_storage_bytes':live.mailbox.storage.nbytes,'fault':live.fault,
    'muted_samples':live.muted_samples,'note':'Synthetic immediate detector; not an ASR or hardware soak.'},indent=2))
