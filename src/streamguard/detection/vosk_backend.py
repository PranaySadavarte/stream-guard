"""Local streaming Vosk adapter. Only endpoint-finalized audio authorizes release."""
import json
from pathlib import Path
import numpy as np
from .base import Detection, Word


class VoskDetector:
    def __init__(self, model_path):
        self.model_path = str(model_path)
        self.recognizer = None
        self.model = None
        self.processed = 0
        self.finalized = 0

    def start(self, sample_rate):
        from vosk import Model, KaldiRecognizer, SetLogLevel
        if not Path(self.model_path).is_dir():
            raise ValueError('select an extracted Vosk model directory')
        SetLogLevel(-1)
        self.model = Model(self.model_path)
        self.recognizer = KaldiRecognizer(self.model, sample_rate)
        self.recognizer.SetWords(True)
        self.recognizer.SetPartialWords(True)
        self.processed = self.finalized = 0

    @staticmethod
    def words(payload, key):
        return tuple(Word(row['word'], float(row['start']), float(row['end']),
                          float(row.get('conf', 1))) for row in payload.get(key, []))

    def process_audio(self, audio):
        if self.recognizer is None:
            raise RuntimeError('detector is not started')
        pcm = np.rint(np.clip(np.asarray(audio).reshape(-1), -1, 32767/32768)*32768).astype('<i2')
        final = self.recognizer.AcceptWaveform(pcm.tobytes())
        self.processed += len(pcm)
        if final:
            payload = json.loads(self.recognizer.Result())
            self.finalized = self.processed
            return Detection(self.words(payload, 'result'), self.finalized)
        payload = json.loads(self.recognizer.PartialResult())
        return Detection(self.words(payload, 'partial_result'), self.finalized)

    def finish(self):
        if self.recognizer is None:
            raise RuntimeError('detector is not started')
        payload = json.loads(self.recognizer.FinalResult())
        self.finalized = self.processed
        return Detection(self.words(payload, 'result'), self.finalized)

    def stop(self):
        self.recognizer = self.model = None
