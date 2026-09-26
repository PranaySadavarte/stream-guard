from types import SimpleNamespace
import numpy as np
import pytest
from streamguard.audio.censor import CensorSettings, censor_into, word_span
from streamguard.audio.mailbox import AudioMailbox
from streamguard.config import AudioSettings
from streamguard.detection.base import Detection, Word
from streamguard.detection.profanity import ProfanityDictionary
from streamguard.pipeline.controller import LiveController


class ScriptedDetector:
    def __init__(self, words=(), final=True): self.position=0; self.words=words; self.final=final
    def process_audio(self, audio):
        self.position += len(audio)
        coverage = self.position
        for word in self.words:
            if word.start*16000 < self.position < word.end*16000:
                coverage = min(coverage, int(word.start*16000))
        return Detection(tuple(w for w in self.words if w.end*16000 <= self.position),
                         coverage if self.final else 0)
    def stop(self): pass


def simulate(controller, source, process=True):
    block = controller.block
    result = []
    for position in range(0, len(source), block):
        output = np.full((block,1), 99, dtype=np.float32)
        controller.callback(source[position:position+block], output, block,
                            SimpleNamespace(inputBufferAdcTime=position/16000,
                                            currentTime=position/16000), False)
        result.append(output.copy())
        if process:
            item = controller.mailbox.pop()
            if item:
                data, start = item
                for sample, sanitized in controller.engine.process(start, data,
                        controller.playback_sample, controller.captured):
                    controller.ready[(sample//block)%controller.capacity]=(sample,sanitized)
    return np.concatenate(result)


@pytest.mark.parametrize('delay_ms',[500,750,1500])
@pytest.mark.parametrize('mode',['beep','silence'])
def test_live_delayed_waveform_matches_offline(delay_ms, mode):
    settings = AudioSettings(0,1,sample_rate=16000,delay_ms=delay_ms)
    words = (Word('fucking', .30, .42), Word('shit', .70, .83))
    censor = CensorSettings(mode=mode, before_ms=100, after_ms=100)
    live = LiveController(settings, ScriptedDetector(words), ProfanityDictionary(), censor)
    source = np.full((16000*4,1), .7, dtype=np.float32)
    output = simulate(live, source)
    expected=source.copy()
    censor_into(expected,0,[word_span(w,16000,censor) for w in words],16000,censor)
    delay=settings.delay_samples
    np.testing.assert_array_equal(output[:delay],0)
    np.testing.assert_allclose(output[delay:],expected[:-delay],atol=1e-6)


def test_unfinalized_audio_never_escapes():
    live=LiveController(AudioSettings(0,1,sample_rate=16000,delay_ms=500),
                        ScriptedDetector(final=False),ProfanityDictionary(),CensorSettings())
    output=simulate(live,np.ones((32000,1),dtype=np.float32))
    assert not np.any(output)
    assert live.muted_samples > 0
    assert len(live.engine.pending) <= 26


def test_queue_overrun_latches_mute():
    live=LiveController(AudioSettings(0,1,sample_rate=16000,delay_ms=500),
                        ScriptedDetector(),ProfanityDictionary(),CensorSettings())
    output=simulate(live,np.ones((32000,1),dtype=np.float32),process=False)
    assert not np.any(output)
    assert 'queue full' in live.fault


def test_mailbox_does_not_overwrite_unread_block():
    box=AudioMailbox(2,4)
    assert box.push(np.ones(4),0)
    assert box.push(np.ones(4)*2,4)
    assert not box.push(np.ones(4)*3,8)
    data,stamp=box.pop()
    np.testing.assert_array_equal(data,1)
    assert stamp==0
    assert box.push(np.ones(4)*3,8)
    assert box.pop()[1]==4
    assert box.pop()[1]==8
    assert box.pop() is None


def test_noncontiguous_detector_input_fails():
    live=LiveController(AudioSettings(0,1),ScriptedDetector(),ProfanityDictionary(),CensorSettings())
    with pytest.raises(RuntimeError): live.engine.process(1,np.zeros(960),0,960)
