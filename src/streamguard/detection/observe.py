"""Live detector-only milestone: capture and report, never output raw audio."""
import json
import time
import sounddevice as sd
from ..audio.mailbox import AudioMailbox
from .profanity import ProfanityDictionary


def observe(detector, input_device, rate=48000, seconds=15):
    block = rate // 50
    mailbox = AudioMailbox(50, block)
    failed = [False]
    position = [0]
    dictionary = ProfanityDictionary()
    seen = set()
    def capture(data, frames, times, status):
        if status or frames != block:
            failed[0] = True
        if not failed[0]:
            failed[0] = not mailbox.push(data, position[0])
            position[0] += frames
    detector.start(rate)
    try:
        with sd.InputStream(device=input_device, samplerate=rate, channels=1,
                            dtype='float32', blocksize=block, callback=capture):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                if failed[0]: raise RuntimeError('capture overrun/discontinuity')
                item = mailbox.pop()
                if item is None:
                    time.sleep(.002)
                    continue
                audio, start_sample = item
                result = detector.process_audio(audio)
                for word in result.words:
                    key = (word.text, round(word.start, 2))
                    if dictionary.matches(word.text) and key not in seen:
                        seen.add(key)
                        print(json.dumps({'word':word.text, 'start':word.start, 'end':word.end,
                                          'confidence':word.confidence,
                                          'latency_ms':(position[0]/rate-word.end)*1000}), flush=True)
    finally:
        detector.stop()
