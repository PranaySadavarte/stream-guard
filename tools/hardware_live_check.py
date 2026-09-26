"""Explicit 30-second live worker/device smoke test; no microphone recordings."""
import json
from pathlib import Path
import time
import numpy as np
from streamguard.config import AudioSettings
from streamguard.audio.censor import CensorSettings
from streamguard.detection.vosk_backend import VoskDetector
from streamguard.detection.profanity import ProfanityDictionary
from streamguard.pipeline.controller import LiveController

root=Path(__file__).resolve().parents[1]
controller=LiveController(AudioSettings(1,5,delay_ms=3000,output_channels=2),
    VoskDetector(root/'models/vosk-model-small-en-us-0.15'),ProfanityDictionary(),CensorSettings(volume=.1))
normal_callback=controller.callback
def quiet_monitor(indata,outdata,frames,times,status):
    normal_callback(indata,outdata,frames,times,status)
    np.multiply(outdata,.03,out=outdata)
controller.callback=quiet_monitor
reports=[]
try:
    controller.start()
    for _ in range(60):
        time.sleep(.5)
        status=controller.snapshot()
        reports.append({k:v for k,v in status.items() if k!='events'})
        if status['error']:break
finally:controller.close()
(root/'recordings/live-hardware.json').write_text(json.dumps(reports,indent=2))
print(json.dumps(reports[-1],indent=2))
if reports[-1]['error']:raise SystemExit(1)
