"""Bounded, asynchronous recording of the actual protected output buffer."""
from pathlib import Path
import threading
import wave
import numpy as np
from .mailbox import AudioMailbox


class OutputRecorder:
    def __init__(self, path, rate, channels, block, capacity=100):
        self.path = Path(path)
        self.rate, self.channels = rate, channels
        self.mailbox = AudioMailbox(capacity, block*channels)
        self.error = None
        self.complete = False
        self.finished = threading.Event()
        self.worker = None

    def start(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open('xb')
        try:
            self.wav = wave.open(self.file, 'wb')
            self.wav.setnchannels(self.channels)
            self.wav.setsampwidth(2)
            self.wav.setframerate(self.rate)
            self.worker = threading.Thread(target=self._write, daemon=True, name='StreamGuard-recording')
            self.worker.start()
        except BaseException:
            self.file.close()
            raise

    def push(self, output):
        if self.error or self.finished.is_set(): return
        try:
            if not self.mailbox.push(output, None):
                self.error = 'Recording queue full; saved recording is incomplete.'
        except Exception as exc:
            self.error = f'Recording failed; saved recording is incomplete: {exc}'

    def _write(self):
        frames = 0
        try:
            while not self.finished.is_set() or self.mailbox.depth:
                item = self.mailbox.pop()
                if item is None:
                    self.finished.wait(.002)
                    continue
                pcm = (np.clip(item[0], -1, 1)*32767).astype('<i2')
                if (frames*self.channels*2 + pcm.nbytes) > 0xFFFFFFFF-36:
                    raise RuntimeError('WAV size limit reached')
                self.wav.writeframesraw(pcm.tobytes())
                frames += len(pcm)//self.channels
        except Exception as exc:
            self.error = f'Recording failed; saved recording is incomplete: {exc}'
        finally:
            try:
                self.wav.close()
            except Exception as exc:
                self.error = f'Could not finish recording: {exc}'
            finally:self.file.close()
            self.complete = self.error is None

    def close(self):
        self.finished.set()
        if self.worker:
            self.worker.join(timeout=5)
            if self.worker.is_alive():
                self.error = 'Recording is still finishing; playback is unavailable.'
