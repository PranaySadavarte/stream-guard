"""WAV waveform censorship using detector output or explicit annotated words."""
import json
from pathlib import Path
import wave
import numpy as np
from .audio.censor import CensorSettings, censor_into, word_span
from .detection.base import Word
from .detection.profanity import ProfanityDictionary


def read_wav(path):
    with wave.open(str(path), 'rb') as source:
        if source.getsampwidth() != 2 or source.getcomptype() != 'NONE':
            raise ValueError('input must be uncompressed 16-bit PCM WAV')
        rate, channels = source.getframerate(), source.getnchannels()
        audio = np.frombuffer(source.readframes(source.getnframes()), dtype='<i2')
    return audio.astype(np.float32).reshape(-1, channels) / 32768, rate


def write_wav(path, audio, rate):
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(audio.shape[1])
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(np.rint(np.clip(audio, -1, 32767/32768)*32768).astype('<i2').tobytes())


def censor_file(source, destination, dictionary=None, settings=None, words=None, detector=None):
    if Path(source).resolve() == Path(destination).resolve():
        raise ValueError('choose a different output file to preserve the original')
    audio, rate = read_wav(source)
    settings = settings or CensorSettings()
    dictionary = dictionary or ProfanityDictionary()
    if words is None:
        if detector is None:
            raise ValueError('provide a speech detector or annotated words')
        words = []
        detector.start(rate)
        try:
            for offset in range(0, len(audio), rate // 50):
                result = detector.process_audio(audio[offset:offset+rate//50].mean(axis=1))
                words.extend(result.words)
            words.extend(detector.finish().words)
        finally:
            detector.stop()
    spans = [word_span(w, rate, settings) for w in words if dictionary.matches(w.text)]
    result = audio.copy()
    censor_into(result, 0, spans, rate, settings)
    write_wav(destination, result, rate)
    return spans


def load_words(path):
    return [Word(**record) for record in json.loads(Path(path).read_text(encoding='utf-8'))]
