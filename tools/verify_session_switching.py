"""Use real local models and generated WAV input; never opens audio hardware."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ.setdefault('OMP_NUM_THREADS','2')
import json,time,threading
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import sounddevice as sd
from PySide6.QtWidgets import QApplication
import streamguard.ui.main_window as ui
from streamguard.offline import read_wav

root=Path(__file__).resolve().parents[1]
source,rate=read_wav(root/'recordings/fixtures/profanity.wav')
counts={'opened':0,'closed':0}
class FixtureStream:
    def __init__(self,**options):
        self.options=options;self.active=False;self.cpu_load=0;self.done=threading.Event();self.worker=None
        counts['opened']+=1
    def start(self):
        self.active=True
        def feed():
            block=self.options['blocksize']
            # Time callbacks as a device would, but use a generated file only.
            for offset in range(0,len(source),block):
                if self.done.is_set():break
                audio=np.zeros((block,1),dtype=np.float32)
                part=source[offset:offset+block];audio[:len(part)]=part
                if isinstance(self.options['channels'],tuple):
                    output=np.zeros((block,self.options['channels'][1]),dtype=np.float32)
                    self.options['callback'](audio,output,block,SimpleNamespace(inputBufferAdcTime=0,currentTime=0),False)
                else:self.options['callback'](audio,block,None,False)
                self.done.wait(block/rate)
        self.worker=threading.Thread(target=feed,daemon=True);self.worker.start()
    def stop(self):
        self.done.set()
        if self.worker:self.worker.join()
        self.active=False
    abort=stop
    def close(self):self.stop();counts['closed']+=1
sd.Stream=sd.InputStream=FixtureStream
sd.check_input_settings=sd.check_output_settings=lambda **kw:None
ui.devices=lambda:[{'id':1,'name':'Fixture mic','host':'Replay','input_channels':1,'output_channels':0},
                   {'id':2,'name':'Discarded output','host':'Replay','input_channels':0,'output_channels':1}]
app=QApplication([])
window=ui.MainWindow(root/'recordings/switching-verification')
window.restore({'session_mode':1,'backend':2,'model':str(root/'models/vosk-model-small-en-us-0.15'),
    'input':'Fixture mic \u00b7 Replay','output':'Discarded output \u00b7 Replay','rate':rate,'channels':1,
    'models':{'whisper':str(root/'models/faster-whisper-small.en')},'mode_backends':{'0':1,'1':2},
    'words':'fucking\nbanana','delay':1250})
def settle():
    deadline=time.monotonic()+90
    while window.task and time.monotonic()<deadline:window.poll();time.sleep(.01)
    assert window.task is None,window.message.text()
report=[]
for index,mode in enumerate((1,0,1)):
    window.session_mode.setCurrentIndex(mode)
    if index==2:window.words.appendPlainText('cat')
    window.save();settle();assert 'validated and saved' in window.message.text(),window.message.text()
    window.start();settle();assert window.controller,window.message.text()
    current=window.controller
    current.stream.worker.join(timeout=20)
    window.poll();window.stop();settle()
    assert window.last_recording and window.last_recording.exists(),window.message.text()
    audio,audio_rate=read_wav(window.last_recording)
    row={'mode':'live' if mode else 'record','backend':window.backend.currentText(),
         'saved_words':window.words.toPlainText().splitlines(),'output_frames':len(audio),'rate':audio_rate}
    if mode==0:
        original,_=read_wav(window.original_recording)
        row['same_duration']=len(original)==len(audio)
        row['changed_samples']=int(np.sum(original!=audio))
        assert row['same_duration'] and row['changed_samples']>0
    report.append(row)
assert counts['opened']==counts['closed']==3
window.close()
result={'sessions':report,'resources':counts,'devices':'simulated; generated speech only'}
(root/'recordings/session-switching-report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
