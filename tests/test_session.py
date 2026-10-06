from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from streamguard.config import AudioSettings
from streamguard.audio.censor import CensorSettings
from streamguard.detection.base import Detection,Word
from streamguard.detection.profanity import ProfanityDictionary
from streamguard.pipeline.session import RecordedSession
from streamguard.offline import read_wav,censor_file,write_wav
from streamguard.detection.whisper_backend import WhisperFileDetector


class LateDetector:
    def start(self,rate):self.processed=0
    def process_audio(self,audio):self.processed+=len(audio);return Detection()
    def finish(self):return Detection((Word('banana',3,3.3),),self.processed)
    def stop(self):pass


def test_continuous_28_second_session_preserves_beginning_end_and_duration(tmp_path):
    session=RecordedSession(AudioSettings(0,1,sample_rate=16000),LateDetector(),
                            ProfanityDictionary(['banana']),CensorSettings(mode='silence'),tmp_path/'session.wav')
    session.recorder.start()
    for n in range(1400):
        session.callback(np.full((320,1),.5,dtype=np.float32),320,None,False)
        # Drain normally without allowing this accelerated test to simulate an overrun.
        while session.recorder.mailbox.depth>50:session.recorder.finished.wait(.001)
    session.close();result=session.filter()
    original,rate=read_wav(result['original']);filtered,_=read_wav(result['path'])
    assert len(original)==len(filtered)==28*rate
    np.testing.assert_array_equal(original[:rate],filtered[:rate])
    np.testing.assert_array_equal(original[-rate:],filtered[-rate:])
    assert original[3*rate:int(3.3*rate)].any() and not filtered[3*rate:int(3.3*rate)].any()
    assert result['detections']==1


def test_incomplete_capture_is_not_published_as_filtered(tmp_path):
    session=RecordedSession(AudioSettings(0,1),LateDetector(),ProfanityDictionary(),CensorSettings(),tmp_path/'s.wav')
    session.recorder.start();session.callback(np.ones((960,1)),960,None,True);session.close()
    with pytest.raises(RuntimeError,match='incomplete'):session.filter()
    assert not session.filtered_path.exists()


def test_whisper_file_path_preserves_audio_outside_detected_intervals(tmp_path):
    source=tmp_path/'original.wav';output=tmp_path/'filtered.wav'
    write_wav(source,np.full((16000,1),.5,dtype=np.float32),16000)
    detector=SimpleNamespace(transcribe_file=lambda path:[Word('banana',.4,.5)])
    spans=censor_file(source,output,ProfanityDictionary(['banana']),CensorSettings(mode='silence',before_ms=0,after_ms=0),detector=detector)
    filtered,rate=read_wav(output);original,_=read_wav(source)
    assert len(spans)==1 and len(filtered)==len(original)
    np.testing.assert_array_equal(filtered[:6240],original[:6240])
    np.testing.assert_array_equal(filtered[8160:],original[8160:])


def test_whisper_uses_local_cpu_model_and_word_timestamps(tmp_path,monkeypatch):
    import sys
    (tmp_path/'model.bin').touch();calls={}
    class Model:
        def __init__(self,path,**kwargs):calls.update(kwargs)
        def transcribe(self,path,**kwargs):
            calls.update(kwargs)
            return iter([SimpleNamespace(words=[SimpleNamespace(word=' banana',start=.1,end=.3,probability=.8)])]),None
    monkeypatch.setitem(sys.modules,'faster_whisper',SimpleNamespace(WhisperModel=Model))
    assert WhisperFileDetector(tmp_path).transcribe_file('test.wav')==[Word('banana',.1,.3,.8)]
    assert calls['local_files_only'] and calls['word_timestamps'] and calls['device']=='cpu'
