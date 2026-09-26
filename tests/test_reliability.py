from types import SimpleNamespace
import threading
import time
import numpy as np
import pytest
from streamguard.audio.censor import CensorSettings
from streamguard.audio.mailbox import AudioMailbox
from streamguard.config import AudioSettings
from streamguard.detection.base import Word, Detection
from streamguard.detection.profanity import ProfanityDictionary
from streamguard.pipeline.controller import LiveController
from streamguard.pipeline.engine import CensorEngine


def test_concurrent_mailbox_order_under_load():
    mailbox=AudioMailbox(4,320)
    count=5000
    def produce():
        for index in range(count):
            block=np.full(320,index,dtype=np.float32)
            while not mailbox.push(block,index):time.sleep(0)
    thread=threading.Thread(target=produce);thread.start()
    for expected in range(count):
        deadline=time.monotonic()+5
        item=mailbox.pop()
        while item is None:
            assert time.monotonic()<deadline
            time.sleep(0);item=mailbox.pop()
        assert item[1]==expected
        np.testing.assert_array_equal(item[0],expected)
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_detector_failure_latches_output_mute():
    class Broken:
        stopped=False
        def process_audio(self,a):raise RuntimeError('injected')
        def stop(self):self.stopped=True
    detector=Broken()
    controller=LiveController(AudioSettings(0,1),detector,ProfanityDictionary(),CensorSettings())
    controller.mailbox.push(np.ones(960,dtype=np.float32),0)
    controller._work()
    assert detector.stopped and 'injected' in controller.fault
    output=np.ones((960,2),dtype=np.float32)
    controller.callback(np.ones((960,1),dtype=np.float32),output,960,None,False)
    assert not np.any(output)


def test_repeated_nearby_words_count_separately():
    class Repeated:
        def process_audio(self,a):return Detection((Word('shit',.1,.2),Word('shit',.21,.3)),16000)
    engine=CensorEngine(16000,16000,48000,Repeated(),ProfanityDictionary(),CensorSettings())
    engine.process(0,np.zeros(16000),0,16000)
    assert engine.detected==2


def test_detector_revising_finalized_audio_faults():
    class Invalid:
        def process_audio(self,a):return Detection((Word('shit',.01,.1),),16000)
    engine=CensorEngine(16000,16000,48000,Invalid(),ProfanityDictionary(),CensorSettings())
    engine.finalized=8000
    with pytest.raises(RuntimeError,match='revised'):
        engine.process(0,np.zeros(16000),0,16000)


def test_coverage_cannot_advance_past_processed_audio():
    class Invalid:
        def process_audio(self,a):return Detection((),999999)
    engine=CensorEngine(16000,320,48000,Invalid(),ProfanityDictionary(),CensorSettings())
    with pytest.raises(RuntimeError,match='coverage'):
        engine.process(0,np.zeros(320),0,320)


def test_stop_prevents_cached_audio_release():
    controller=LiveController(AudioSettings(0,1),None,ProfanityDictionary(),CensorSettings())
    controller.stop_event.set()
    output=np.ones((960,2),dtype=np.float32)
    controller.callback(np.ones((960,1),dtype=np.float32),output,960,None,False)
    assert not np.any(output)


def test_fully_expired_first_detection_is_counted_as_late_once():
    class Late:
        def process_audio(self,a):return Detection((Word('shit',.1,.2),),0)
    engine=CensorEngine(16000,320,8000,Late(),ProfanityDictionary(),CensorSettings())
    engine.process(0,np.zeros(320),8000,16000)
    engine.process(320,np.zeros(320),8320,16320)
    assert engine.detected==1 and engine.late==1
    assert engine.events[0]['late']
