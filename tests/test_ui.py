import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
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
