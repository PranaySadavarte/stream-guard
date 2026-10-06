"""Record full microphone input, then censor the whole file after Stop."""
import json
import time
from ..audio.recording import OutputRecorder
from ..offline import censor_file


class RecordedSession:
    def __init__(self, audio, detector, dictionary, censor, recording_path):
        self.audio,self.detector,self.dictionary,self.censor=audio,detector,dictionary,censor
        self.raw_path=recording_path.with_name(recording_path.stem+'-original.wav')
        self.filtered_path=recording_path.with_name(recording_path.stem+'-filtered.wav')
        self.recorder=OutputRecorder(self.raw_path,audio.sample_rate,1,audio.block_samples)
        self.stream=None;self.frames=0;self.fault=None;self.stopped=False;self.last_callback=None

    def callback(self,incoming,frames,times,status):
        self.last_callback=time.monotonic()
        if self.stopped:return
        if status or frames!=self.audio.block_samples:
            self.fault='Microphone discontinuity; recording is incomplete.'
            return
        self.recorder.push(incoming);self.frames+=frames
        if self.recorder.error:self.fault=self.recorder.error

    def start(self):
        import sounddevice as sd
        try:
            sd.check_input_settings(device=self.audio.input_device,channels=1,
                                   samplerate=self.audio.sample_rate,dtype='float32')
            self.recorder.start()
            self.stream=sd.InputStream(device=self.audio.input_device,channels=1,
                samplerate=self.audio.sample_rate,blocksize=self.audio.block_samples,
                dtype='float32',callback=self.callback,latency='high')
            self.stream.start()
        except BaseException:
            self.close();raise

    def snapshot(self):
        if self.stream and not self.stopped:
            if not self.stream.active:self.fault=self.fault or 'Microphone stopped; recording is incomplete.'
            elif self.last_callback and time.monotonic()-self.last_callback>2:
                self.fault=self.fault or 'Microphone stalled; recording is incomplete.'
        return {'state':'RECORDING ERROR' if self.fault else 'RECORDING FULL SESSION',
                'error':self.fault,'recorded_seconds':self.frames/self.audio.sample_rate,'events':[]}

    def close(self):
        self.stopped=True
        try:
            if self.stream:
                try:self.stream.stop()
                finally:self.stream.close();self.stream=None
        finally:self.recorder.close()

    def filter(self):
        if self.fault or not self.recorder.complete:
            raise RuntimeError(self.fault or self.recorder.error or 'Recording is incomplete; original retained.')
        spans=censor_file(self.raw_path,self.filtered_path,self.dictionary,self.censor,detector=self.detector)
        self.filtered_path.with_suffix('.json').write_text(json.dumps({
            'original':str(self.raw_path),'filtered':str(self.filtered_path),
            'seconds':self.frames/self.audio.sample_rate,'detections':len(spans),
            'note':'Only detected blocked intervals are replaced. Recognition can miss words.'}),encoding='utf-8')
        return {'path':self.filtered_path,'original':self.raw_path,'error':None,'detections':len(spans)}
