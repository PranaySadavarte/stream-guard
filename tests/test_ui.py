import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
import time
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication
from streamguard.ui.main_window import MainWindow
from streamguard.ui.settings import load_settings, save_settings


def test_settings_roundtrip(tmp_path):
    path=tmp_path/'settings.json'
    save_settings(path,{'model':'C:/models/test','words':'custom\nshit'})
    assert load_settings(path)['words']=='custom\nshit'


def test_ui_validates_before_start_and_restores_settings(tmp_path, monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr('streamguard.ui.main_window.devices',lambda:[])
    window=MainWindow(tmp_path)
    window.start()
    assert window.controller is None
    assert 'Choose a microphone' in window.message.text()
    window.restore({'delay':3000,'mode':'Silence','words':'test\nshit'})
    window.save()
    assert load_settings(tmp_path/'settings.json')['delay']==3000
    assert window.count.text()=='2 blocked terms'
    window.close()


def test_violation_notice_masks_terms_and_deduplicates(tmp_path, monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr('streamguard.ui.main_window.devices',lambda:[])
    event={'id':1,'timestamp':time.time(),'term':'shit','confidence':.9,
           'late':False,'latency_ms':500,'start':0,'end':1}
    class Controller:
        def snapshot(self):return {'state':'FILTERING','error':None,'detected':1,
            'muted_ms':0,'queue_depth':0,'headroom_ms':1200,'detection_latency_ms':None,'events':[event]}
    window=MainWindow(tmp_path);window.controller=Controller()
    window.poll()
    assert 's***' in window.violation.text() and 'shit' not in window.violation.text()
    assert 'scheduled' in window.violation.text() and not window.violation.isHidden()
    window.violation.hide();window.poll()
    assert window.violation.isHidden() and window.events.rowCount()==1
    event.update(id=2,late=True);window.poll()
    assert 'late' in window.violation.text() and not window.violation.isHidden()
    window.controller=None;window.close()


def test_ui_background_start_and_stop(tmp_path, monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr('streamguard.ui.main_window.devices',lambda:[
        {'id':1,'name':'Mic','host':'Test','input_channels':1,'output_channels':0},
        {'id':2,'name':'Output','host':'Test','input_channels':0,'output_channels':2}])
    class Controller:
        def __init__(self,*args,**kwargs):self.closed=False
        def start(self):pass
        def close(self):self.closed=True
        def snapshot(self):return {'state':'FILTERING','error':None,'detected':0,
            'muted_ms':0,'queue_depth':0,'headroom_ms':1200,'detection_latency_ms':None,'events':[]}
    monkeypatch.setattr('streamguard.ui.main_window.LiveController',Controller)
    model=tmp_path/'model'/'am';model.mkdir(parents=True);(model/'final.mdl').touch()
    window=MainWindow(tmp_path/'state');window.input.setCurrentIndex(1);window.output.setCurrentIndex(1)
    window.session_mode.setCurrentIndex(1)
    window.model.setText(str(model.parent));window.start()
    deadline=time.monotonic()+2
    while window.task and time.monotonic()<deadline:window.poll();time.sleep(.001)
    assert window.controller is not None and not window.routing.isEnabled()
    assert not window.record_output.isEnabled() and not window.replay_button.isEnabled()
    controller=window.controller;window.stop()
    while window.task and time.monotonic()<deadline:window.poll();time.sleep(.001)
    assert controller.closed and window.controller is None and window.routing.isEnabled()
    assert window.record_output.isEnabled()
    window.close()


def test_finished_recording_enables_replay_and_incomplete_recording_does_not(tmp_path, monkeypatch):
    import threading
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr('streamguard.ui.main_window.devices',lambda:[])
    window=MainWindow(tmp_path)
    path=tmp_path/'test.wav'
    window.task=threading.Thread(target=lambda:None);window.task.start();window.task.join()
    window.task_result=('stopped',{'path':path,'error':None});window.poll()
    assert window.last_recording==path and window.replay_button.isEnabled()
    window.task=threading.Thread(target=lambda:None);window.task.start();window.task.join()
    window.task_result=('stopped',{'path':None,'error':'Recording is incomplete'});window.poll()
    assert not window.replay_button.isEnabled() and 'incomplete' in window.recording_status.text()
    window.close()


def test_full_session_ui_records_without_output_and_filters_after_stop(tmp_path,monkeypatch):
    from streamguard.detection.base import Detection,Word
    from streamguard.offline import read_wav
    import sounddevice
    import numpy as np
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr('streamguard.ui.main_window.devices',lambda:[
        {'id':1,'name':'Mic','host':'Test','input_channels':1,'output_channels':0}])
    class Detector:
        def start(self,rate):pass
        def process_audio(self,audio):return Detection()
        def finish(self):return Detection((Word('banana',.1,.2),))
        def stop(self):pass
    class Stream:
        def __init__(self,**kwargs):self.options=kwargs;self.active=False
        def start(self):
            self.active=True
            for n in range(20):self.options['callback'](np.full((960,1),.5,dtype=np.float32),960,None,False)
        def stop(self):self.active=False
        def close(self):pass
    monkeypatch.setattr(sounddevice,'check_input_settings',lambda **kwargs:None)
    monkeypatch.setattr(sounddevice,'InputStream',Stream)
    monkeypatch.setattr('streamguard.ui.main_window.VoskDetector',lambda model:Detector())
    model=tmp_path/'model'/'am';model.mkdir(parents=True);(model/'final.mdl').touch()
    window=MainWindow(tmp_path/'state');window.input.setCurrentIndex(1);window.model.setText(str(model.parent))
    window.words.setPlainText('banana');window.start()
    deadline=time.monotonic()+3
    while window.task and time.monotonic()<deadline:window.poll();time.sleep(.001)
    assert window.controller is not None and window.status.text()=='RECORDING FULL SESSION'
    window.stop()
    while window.task and time.monotonic()<deadline:window.poll();time.sleep(.001)
    assert window.last_recording and window.original_recording
    assert window.replay_button.isEnabled() and window.original_button.isEnabled()
    original,rate=read_wav(window.original_recording);filtered,_=read_wav(window.last_recording)
    assert len(original)==len(filtered)==19200 and original.any()
    assert 'No deadline muting' in window.metrics.text()
    window.close()


def test_fast_live_rejects_batch_and_insufficient_delay_without_devices(tmp_path,monkeypatch):
    monkeypatch.setattr('streamguard.ui.main_window.RecordedSession',lambda *a,**k:pytest.fail('must not open devices'))
    monkeypatch.setattr('streamguard.ui.main_window.LiveController',lambda *a,**k:pytest.fail('must not open devices'))
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr('streamguard.ui.main_window.devices',lambda:[
        {'id':1,'name':'Mic','host':'Test','input_channels':1,'output_channels':0},
        {'id':2,'name':'Output','host':'Test','input_channels':0,'output_channels':2}])
    window=MainWindow(tmp_path);window.input.setCurrentIndex(1);window.output.setCurrentIndex(1)
    window.backend.setCurrentIndex(2);window.start()
    assert 'requires Live protection' in window.message.text() and window.task is None
    window.session_mode.setCurrentIndex(1)
    window.delay.setCurrentIndex(window.delay.findData(1000));window.start()
    assert 'at least 1.25' in window.message.text() and window.task is None
    window.close()
