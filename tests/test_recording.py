from types import SimpleNamespace
import wave
import numpy as np
import pytest
from streamguard.audio.recording import OutputRecorder
from streamguard.audio.censor import CensorSettings
from streamguard.config import AudioSettings
from streamguard.detection.base import Detection, Word
from streamguard.detection.profanity import ProfanityDictionary
from streamguard.pipeline.controller import LiveController


class Detector:
    def __init__(self):self.position=0
    def process_audio(self,audio):
        self.position+=len(audio)
        return Detection((Word('banana',.1,.2),),self.position)
    def stop(self):pass


def test_saved_session_equals_actual_output_and_includes_fault_silence(tmp_path):
    path=tmp_path/'protected.wav'
    live=LiveController(AudioSettings(0,1,sample_rate=16000,delay_ms=500,output_channels=2),
                        Detector(),ProfanityDictionary(['banana']),
                        CensorSettings(mode='silence',before_ms=0,after_ms=0),recording_path=path)
    live.recorder.start();expected=[]
    for n in range(60):
        output=np.ones((live.block,2),dtype=np.float32)
        live.callback(np.full((live.block,1),.6,dtype=np.float32),output,live.block,
                      SimpleNamespace(inputBufferAdcTime=0,currentTime=0),n==59)
        expected.append(output.copy())
        item=live.mailbox.pop()
        if item:
            audio,start=item
            for position,block in live.engine.process(start,audio,live.playback_sample,live.captured):
                live.ready[(position//live.block)%live.capacity]=(position,block)
    live.close()
    assert live.recorder.complete
    with wave.open(str(path),'rb') as wav:
        assert wav.getnchannels()==2 and wav.getframerate()==16000
        recorded=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').reshape(-1,2)
    expected=np.concatenate(expected)
    np.testing.assert_array_equal(recorded,(expected*32767).astype('<i2'))
    assert np.any(recorded)
    assert not recorded[:8000].any()  # Startup delay is part of the session.
    assert not recorded[9600:11200].any()  # The blocked word never reaches the recording.
    assert not recorded[-live.block:].any()  # Device fault records silence, not microphone input.


def test_recording_overflow_reports_incomplete_without_blocking(tmp_path):
    recorder=OutputRecorder(tmp_path/'partial.wav',16000,1,320,capacity=1)
    recorder.push(np.ones((320,1),dtype=np.float32))
    recorder.push(np.ones((320,1),dtype=np.float32))
    assert 'incomplete' in recorder.error and recorder.mailbox.depth==1
    recorder.start();recorder.close()
    assert not recorder.complete


def test_existing_recording_is_never_overwritten(tmp_path):
    path=tmp_path/'existing.wav';path.write_bytes(b'keep')
    recorder=OutputRecorder(path,16000,1,320)
    with pytest.raises(FileExistsError):recorder.start()
    recorder.close()
    assert path.read_bytes()==b'keep'
