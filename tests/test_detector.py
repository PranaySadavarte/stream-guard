import json
import numpy as np
from streamguard.detection.vosk_backend import VoskDetector


class Recognizer:
    def __init__(self): self.calls = 0
    def AcceptWaveform(self, data):
        assert len(data) == 640
        self.calls += 1
        return self.calls == 2
    def PartialResult(self):
        return json.dumps({'partial_result':[{'word':'shit','start':.01,'end':.02,'conf':.8}]})
    def Result(self):
        return json.dumps({'result':[{'word':'shit','start':.01,'end':.03,'conf':.9}]})
    def FinalResult(self): return '{}'


def test_partial_does_not_authorize_audio_release():
    detector = VoskDetector('unused')
    detector.recognizer = Recognizer()
    partial = detector.process_audio(np.zeros(320, dtype=np.float32))
    assert partial.finalized_through == 0
    assert partial.words[0].text == 'shit'
    final = detector.process_audio(np.zeros(320, dtype=np.float32))
    assert final.finalized_through == 640
    assert final.words[0].end == .03
    assert detector.finish().finalized_through == 640
    detector.stop()
    assert detector.recognizer is None
