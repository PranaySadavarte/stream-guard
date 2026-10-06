"""Whole-file local Whisper transcription; never downloads during inference."""
from pathlib import Path
from .base import Word


class WhisperFileDetector:
    def __init__(self, model_path):self.model_path=str(model_path)

    def transcribe_file(self, path):
        from faster_whisper import WhisperModel
        if not (Path(self.model_path)/'model.bin').is_file():
            raise ValueError('Choose a downloaded faster-whisper model folder containing model.bin.')
        model=WhisperModel(self.model_path,device='cpu',compute_type='int8',local_files_only=True)
        segments,_=model.transcribe(str(path),language='en',beam_size=5,word_timestamps=True,
                                   condition_on_previous_text=False,vad_filter=False)
        return [Word(word.word.strip(),word.start,word.end,word.probability)
                for segment in segments for word in (segment.words or [])]
