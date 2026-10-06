"""Real offline Whisper fixture checks, preserving all audio outside censor spans."""
import json
from pathlib import Path
import time
import numpy as np
from streamguard.audio.censor import CensorSettings
from streamguard.detection.whisper_backend import WhisperFileDetector
from streamguard.offline import censor_file,read_wav

root=Path(__file__).resolve().parents[1]
report=[]
for name,expected in [('clean',0),('profanity',1),('repeated',2)]:
    source=root/'recordings/fixtures'/f'{name}.wav'
    destination=root/'recordings'/f'{name}-whisper-filtered.wav'
    start=time.perf_counter()
    spans=censor_file(source,destination,detector=WhisperFileDetector(root/'models/faster-whisper-small.en'))
    original,rate=read_wav(source);filtered,_=read_wav(destination)
    outside=np.ones(len(original),dtype=bool)
    for span in spans:outside[max(0,span.start-rate//200):min(len(outside),span.end+rate//200)]=False
    unchanged=bool(np.array_equal(original[outside],filtered[outside]))
    report.append({'fixture':name,'seconds':len(original)/rate,'processing_seconds':round(time.perf_counter()-start,2),
                   'detected':len(spans),'expected':expected,'same_duration':len(original)==len(filtered),
                   'outside_censor_unchanged':unchanged})
target=root/'recordings/whole-session-report.json';target.write_text(json.dumps(report,indent=2))
print(target.read_text())
assert all(r['detected']==r['expected'] and r['same_duration'] and r['outside_censor_unchanged'] for r in report)
