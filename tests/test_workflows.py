"""Real session controllers and WAV writers; fake devices never access hardware."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import threading
import time
from types import SimpleNamespace
import numpy as np
import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication
from streamguard.ui.main_window import MainWindow
from streamguard.ui.settings import load_settings
from streamguard.detection.base import Detection,Word
from streamguard.detection.vocabulary import UnsupportedWordsError
from streamguard.offline import read_wav


def settle(window):
    deadline=time.monotonic()+5
    while window.task and time.monotonic()<deadline:
        window.poll();time.sleep(.001)
    assert window.task is None


@pytest.fixture
def rig(tmp_path,monkeypatch):
    import sounddevice as sd
    import streamguard.ui.main_window as ui
    app=QApplication.instance() or QApplication([])
    state=SimpleNamespace(opened=0,closed=0,starts=[],fail_filter=False,gate=None,entered=threading.Event())
    model=tmp_path/'vosk'/'am';model.mkdir(parents=True);(model/'final.mdl').touch()
    whisper=tmp_path/'whisper';whisper.mkdir();(whisper/'model.bin').touch()
    class Detector:
        def __init__(self,path,*args):self.path=path;self.terms=args[-1] if args else ();self.position=0
        def start(self,rate):
            state.starts.append(tuple(sorted(self.terms)))
            state.entered.set()
            if state.gate:state.gate.wait(3)
            if 'unsupported' in self.terms:raise UnsupportedWordsError(['unsupported'])
        def process_audio(self,audio):
            self.position+=len(audio)
            return Detection((),self.position)
        def finish(self):return Detection((Word('banana',.1,.2),),self.position)
        def stop(self):pass
        def transcribe_file(self,path):
            if state.fail_filter:raise RuntimeError('injected transcription failure')
            return [Word('banana',.1,.2)]
    class Stream:
        def __init__(self,**kwargs):
            self.options=kwargs;self.active=False;self.cpu_load=0;self.closed=False;state.opened+=1
        def start(self):
            self.active=True
            block=self.options['blocksize'];audio=np.full((block,1),.25,dtype=np.float32)
            for n in range(15):
                if isinstance(self.options['channels'],tuple):
                    out=np.empty((block,self.options['channels'][1]),dtype=np.float32)
                    self.options['callback'](audio,out,block,SimpleNamespace(inputBufferAdcTime=0,currentTime=0),False)
                else:self.options['callback'](audio,block,None,False)
        def stop(self):self.active=False
        abort=stop
        def close(self):
            if not self.closed:state.closed+=1;self.closed=True
            self.active=False
    monkeypatch.setattr(sd,'check_input_settings',lambda **kw:None)
    monkeypatch.setattr(sd,'check_output_settings',lambda **kw:None)
    monkeypatch.setattr(sd,'Stream',Stream);monkeypatch.setattr(sd,'InputStream',Stream)
    for name in ['VoskDetector','BoundedVoskDetector','WhisperFileDetector']:monkeypatch.setattr(ui,name,Detector)
    def validate(path,terms):
        if 'unsupported' in terms:raise UnsupportedWordsError(['unsupported'])
    monkeypatch.setattr(ui,'check_live_words',validate)
    monkeypatch.setattr(ui,'devices',lambda:[
        {'id':1,'name':'Mic','host':'Test','input_channels':1,'output_channels':0},
        {'id':2,'name':'Output','host':'Test','input_channels':0,'output_channels':2}])
    window=MainWindow(tmp_path/'state')
    window.restore({'session_mode':1,'backend':2,'model':str(model.parent),
        'models':{'vosk':str(model.parent),'whisper':str(whisper)},'mode_backends':{'0':1,'1':2},
        'input':'Mic \u00b7 Test','output':'Output \u00b7 Test','words':'banana','delay':1250})
    yield window,state
    if state.gate:state.gate.set()
    settle(window)
    if window.controller:window.stop();settle(window)
    window.close()
    assert state.opened==state.closed


def test_repeated_live_record_live_and_saved_word_changes(rig):
    window,state=rig
    for cycle in range(5):
        for mode in (1,0,1):
            window.session_mode.setCurrentIndex(mode)
            assert window.backend.currentIndex()==(2 if mode else 1)
            assert window.model.text().endswith('vosk' if mode else 'whisper')
            window.words.setPlainText('banana\ncat' if cycle%2 else 'banana')
            window.save();settle(window)
            assert 'validated and saved' in window.message.text()
            window.start();window.start();settle(window)
            assert window.controller is not None
            assert not window.start_button.isEnabled()
            window.stop();settle(window)
            assert window.controller is None and window.start_button.isEnabled()
            assert not window.stop_button.isEnabled()
            assert window.last_recording.exists()
            audio,rate=read_wav(window.last_recording)
            assert len(audio)==15*960
            if mode==0:
                original,_=read_wav(window.original_recording)
                assert original.shape==audio.shape
                assert not np.array_equal(original,audio)
    assert state.opened==15 and state.closed==15
    assert ('banana','cat') in state.starts


def test_unsupported_save_preserves_valid_settings_and_recovers(rig):
    window,state=rig
    window.save();settle(window)
    original=load_settings(window.root/'settings.json')
    window.words.setPlainText('banana\nunsupported');window.save();settle(window)
    assert load_settings(window.root/'settings.json')==original
    assert 'does not support: unsupported' in window.message.text()
    assert window.start_button.isEnabled() and not window.remove_words.isHidden()
    window.remove_unsupported_words();window.save();settle(window)
    window.start();settle(window)
    assert window.controller is not None


def test_failed_start_retains_playback_and_next_start_works(rig):
    window,state=rig
    window.start();settle(window);window.stop();settle(window)
    previous=window.last_recording
    window.words.setPlainText('unsupported');window.start();settle(window)
    assert window.controller is None and window.last_recording==previous
    assert window.replay_button.isEnabled() and not window.stop_button.isEnabled()
    window.words.setPlainText('banana');window.start();settle(window)
    assert window.controller is not None


def test_cancel_while_model_loads_releases_device_and_allows_restart(rig):
    window,state=rig
    state.gate=threading.Event()
    window.start();assert state.entered.wait(2)
    window.stop();assert window.cancel_start
    state.gate.set();settle(window)
    assert window.controller is None and state.opened==state.closed
    assert window.start_button.isEnabled()
    state.gate=None;window.start();settle(window)
    assert window.controller is not None


def test_filter_failure_keeps_original_and_allows_live_restart(rig):
    window,state=rig
    state.fail_filter=True;window.session_mode.setCurrentIndex(0)
    window.start();settle(window);window.stop();settle(window)
    assert window.original_recording.exists() and window.original_button.isEnabled()
    assert window.start_button.isEnabled() and 'injected' in window.message.text()
    window.session_mode.setCurrentIndex(1);window.start();settle(window)
    assert window.controller is not None


def test_refresh_preserves_devices_and_profile_roundtrip(rig):
    window,state=rig
    before=window.values();window.refresh_devices()
    assert window.input.currentText()==before['input'] and window.output.currentText()==before['output']
    window.session_mode.setCurrentIndex(0);window.save();settle(window)
    saved=load_settings(window.root/'settings.json')
    window.session_mode.setCurrentIndex(1);window.restore(saved)
    assert window.backend.currentIndex()==1 and window.model.text().endswith('whisper')
    window.session_mode.setCurrentIndex(1)
    assert window.backend.currentIndex()==2 and window.model.text().endswith('vosk')


def test_failed_save_unlocks_controls_without_losing_last_settings(rig,monkeypatch):
    window,state=rig
    window.save();settle(window)
    previous=load_settings(window.root/'settings.json')
    def broken(*args):raise OSError('disk full')
    monkeypatch.setattr('streamguard.ui.main_window.save_settings',broken)
    window.words.setPlainText('banana\ncat');window.save();settle(window)
    assert 'disk full' in window.message.text() and window.start_button.isEnabled()
    assert load_settings(window.root/'settings.json')==previous


def test_close_during_start_cancels_and_releases_device(rig):
    window,state=rig
    state.gate=threading.Event();window.start();assert state.entered.wait(2)
    window.close();assert window.closing and window.cancel_start
    state.gate.set();settle(window)
    assert window.controller is None and state.closed==state.opened


def test_settings_migration_keeps_latest_live_preferences_and_backup(tmp_path):
    from streamguard.ui.settings import save_settings,migrate_live_test_settings
    root=tmp_path/'app';root.mkdir()
    legacy=tmp_path/'live.json'
    save_settings(root/'settings.json',{'words':'old','session_mode':0})
    save_settings(legacy,{'words':'banana','session_mode':1,'backend':2})
    os.utime(legacy,(time.time()+10,time.time()+10))
    migrate_live_test_settings(root,legacy)
    assert load_settings(root/'settings.json')['words']=='banana'
    assert load_settings(root/'settings-before-unification.json')['words']=='old'
    save_settings(legacy,{'words':'later'})
    migrate_live_test_settings(root,legacy)
    assert load_settings(root/'settings.json')['words']=='banana'


def test_empty_list_does_not_replace_last_saved_settings(rig):
    window,state=rig
    window.save();settle(window)
    previous=load_settings(window.root/'settings.json')
    window.words.setPlainText('   ');window.save()
    assert window.task is None and window.start_button.isEnabled()
    assert load_settings(window.root/'settings.json')==previous


def test_mode_switch_restores_only_its_own_recording(rig):
    window,state=rig
    window.start();settle(window);window.stop();settle(window)
    live_path=window.last_recording
    window.session_mode.setCurrentIndex(0)
    assert window.last_recording is None and not window.replay_button.isEnabled()
    window.start();settle(window);window.stop();settle(window)
    record_path=window.last_recording
    window.session_mode.setCurrentIndex(1)
    assert window.last_recording==live_path and window.original_recording is None
    window.session_mode.setCurrentIndex(0)
    assert window.last_recording==record_path and window.original_recording.exists()


def test_live_cleanup_joins_worker_even_when_audio_close_fails():
    from streamguard.pipeline.controller import LiveController
    from streamguard.config import AudioSettings
    from streamguard.audio.censor import CensorSettings
    from streamguard.detection.profanity import ProfanityDictionary
    calls=[]
    detector=SimpleNamespace(stop=lambda:calls.append('detector'))
    controller=LiveController(AudioSettings(0,1),detector,ProfanityDictionary(),CensorSettings())
    def broken():raise RuntimeError('device disconnected')
    controller.stream=SimpleNamespace(abort=broken,close=broken)
    controller.worker=SimpleNamespace(join=lambda timeout:calls.append('joined'),is_alive=lambda:False)
    controller.recorder=SimpleNamespace(close=lambda:calls.append('recorder'))
    with pytest.raises(RuntimeError,match='disconnected'):controller.close()
    assert calls==['joined','recorder'] and controller.stream is None
    controller.close()


def test_bad_settings_file_recovers_to_editable_defaults(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr('streamguard.ui.main_window.devices',lambda:[])
    (tmp_path/'settings.json').write_text('{bad json',encoding='utf-8')
    window=MainWindow(tmp_path)
    assert 'defaults restored' in window.message.text() and window.start_button.isEnabled()
    assert window.model.text()
    window.close()
