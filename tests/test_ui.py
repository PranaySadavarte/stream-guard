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
    assert 'Choose both' in window.message.text()
    window.restore({'delay':3000,'mode':'Silence','words':'test\nshit'})
    window.save()
    assert load_settings(tmp_path/'settings.json')['delay']==3000
    assert window.count.text()=='2 blocked terms'
    window.close()


def test_ui_background_start_and_stop(tmp_path, monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr('streamguard.ui.main_window.devices',lambda:[
        {'id':1,'name':'Mic','host':'Test','input_channels':1,'output_channels':0},
        {'id':2,'name':'Output','host':'Test','input_channels':0,'output_channels':2}])
    class Controller:
        def __init__(self,*args):self.closed=False
        def start(self):pass
        def close(self):self.closed=True
        def snapshot(self):return {'state':'FILTERING','error':None,'detected':0,
            'muted_ms':0,'queue_depth':0,'headroom_ms':1200,'detection_latency_ms':None,'events':[]}
    monkeypatch.setattr('streamguard.ui.main_window.LiveController',Controller)
    model=tmp_path/'model'/'am';model.mkdir(parents=True);(model/'final.mdl').touch()
    window=MainWindow(tmp_path/'state');window.input.setCurrentIndex(1);window.output.setCurrentIndex(1)
    window.model.setText(str(model.parent));window.start()
    deadline=time.monotonic()+2
    while window.task and time.monotonic()<deadline:window.poll();time.sleep(.001)
    assert window.controller is not None and not window.routing.isEnabled()
    controller=window.controller;window.stop()
    while window.task and time.monotonic()<deadline:window.poll();time.sleep(.001)
    assert controller.closed and window.controller is None and window.routing.isEnabled()
    window.close()
