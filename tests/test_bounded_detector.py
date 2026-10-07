import json
from types import SimpleNamespace
import sys
import numpy as np
import pytest
from streamguard.detection.bounded_vosk import BoundedVoskDetector


@pytest.fixture
def fake_vosk(monkeypatch):
    class Recognizer:
        def __init__(self,model,rate):self.samples=0;self.rate=rate
        def SetWords(self,value):pass
        def AcceptWaveform(self,audio):self.samples+=len(audio)//2;return False
        def FinalResult(self):return json.dumps({'result':[{'word':'banana','start':.2,'end':.4,'conf':.9}]})
    monkeypatch.setitem(sys.modules,'vosk',SimpleNamespace(Model=lambda path:object(),
        KaldiRecognizer=Recognizer,SetLogLevel=lambda level:None))


def test_closed_windows_advance_without_silence_and_keep_bounded_decoders(tmp_path,fake_vosk):
    detector=BoundedVoskDetector(tmp_path,window_ms=1500,hop_ms=500);detector.start(16000)
    coverage=[];words=[]
    for n in range(250):
        result=detector.process_audio(np.ones(320,dtype=np.float32));coverage.append(result.finalized_through)
        words.extend(result.words)
        assert len(detector.active)<=3
    assert coverage[:74]==[0]*74 and coverage[-1]==64000
    assert all(a<=b for a,b in zip(coverage,coverage[1:]))
    assert words[0].start==.2 and words[1].start==.7
    assert detector.finish().finalized_through==80000
    detector.stop()


def test_window_boundaries_inside_input_block_do_not_lose_samples(tmp_path,fake_vosk):
    detector=BoundedVoskDetector(tmp_path,window_ms=1000,hop_ms=250);detector.start(16000)
    for n in range(100):detector.process_audio(np.ones(333,dtype=np.float32))
    assert detector.processed==33300 and detector.finalized==20000
    assert all(w['recognizer'].samples==33300-w['start'] for w in detector.active)


def test_partial_audio_does_not_advance_coverage(tmp_path,fake_vosk):
    detector=BoundedVoskDetector(tmp_path);detector.start(16000)
    result=detector.process_audio(np.ones(16000,dtype=np.float32))
    assert result.finalized_through==0 and not result.words


def test_invalid_window_configuration_rejected():
    with pytest.raises(ValueError):BoundedVoskDetector('model',window_ms=1000,hop_ms=400)


def test_alternative_blocked_labels_count_one_utterance_but_adjacent_words_remain_separate():
    from streamguard.pipeline.engine import CensorEngine
    from streamguard.detection.base import Detection,Word
    from streamguard.audio.censor import CensorSettings
    from streamguard.detection.profanity import ProfanityDictionary
    results=iter([Detection((Word('fuck',.1,.25),)),
                  Detection((Word('fucking',.11,.3),)),
                  Detection((Word('shit',.31,.45),))])
    detector=SimpleNamespace(process_audio=lambda audio:next(results))
    engine=CensorEngine(16000,320,24000,detector,ProfanityDictionary(),CensorSettings())
    for n in range(3):engine.process(n*320,np.zeros(320),-24000,960)
    assert engine.detected==2 and len(engine.spans)==3


def test_missing_keyword_fails_before_decoding(tmp_path,monkeypatch):
    model=SimpleNamespace(vosk_model_find_word=lambda word:-1)
    monkeypatch.setitem(sys.modules,'vosk',SimpleNamespace(Model=lambda path:model,
        KaldiRecognizer=lambda *args:pytest.fail('must not create a decoder'),SetLogLevel=lambda level:None))
    detector=BoundedVoskDetector(tmp_path,750,250,terms=['custom'])
    with pytest.raises(ValueError,match='does not support: custom'):detector.start(16000)


def test_keyword_decoder_receives_context_and_unknown_token(tmp_path,monkeypatch):
    grammars=[]
    class Recognizer:
        def __init__(self,model,rate,grammar):grammars.append(json.loads(grammar))
        def SetWords(self,value):pass
        def AcceptWaveform(self,audio):return False
    model=SimpleNamespace(vosk_model_find_word=lambda word:0 if word in ['shit','hello','the'] else -1)
    monkeypatch.setitem(sys.modules,'vosk',SimpleNamespace(Model=lambda path:model,
        KaldiRecognizer=Recognizer,SetLogLevel=lambda level:None))
    detector=BoundedVoskDetector(tmp_path,750,250,terms=['shit']);detector.start(16000)
    detector.process_audio(np.zeros(320))
    assert grammars==[['shit','the','[unk]']]
