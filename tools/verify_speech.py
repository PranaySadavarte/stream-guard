"""Real-model fixture report. Misses are reported, never silently accepted."""
import json
from pathlib import Path
import time
import numpy as np
from streamguard.detection.vosk_backend import VoskDetector
from streamguard.detection.profanity import ProfanityDictionary
from streamguard.offline import read_wav, censor_file


def main():
    root = Path(__file__).resolve().parents[1]
    model = root/'models/vosk-model-small-en-us-0.15'
    report = []
    for path in sorted((root/'recordings/fixtures').glob('*.wav')):
        if path.stem.endswith('-censored'): continue
        audio, rate = read_wav(path)
        detector = VoskDetector(model)
        detector.start(rate)
        processing, words, latencies, seen = [], [], [], set()
        padded = np.concatenate([audio.mean(axis=1), np.zeros(rate*2, dtype=np.float32)])
        for offset in range(0, len(padded), rate//50):
            chunk = padded[offset:offset+rate//50]
            start = time.perf_counter()
            result = detector.process_audio(chunk)
            elapsed = time.perf_counter()-start
            processing.append(elapsed*1000)
            for word in result.words:
                key = (word.text, round(word.start, 2))
                if key not in seen:
                    seen.add(key)
                    words.append(word)
                    if ProfanityDictionary().matches(word.text):
                        latencies.append(((offset+len(chunk))/rate - word.end + elapsed)*1000)
        words.extend(detector.finish().words)
        detector.stop()
        spans = censor_file(path, path.with_stem(path.stem+'-censored'), words=words)
        report.append({'fixture':path.name, 'recognized_words':[w.text for w in words],
            'detected_terms':[s.term for s in spans],
            'detection_latency_ms':latencies,
            'processing_ms':dict(zip(['p50','p95','p99'], np.percentile(processing,[50,95,99]))),
            'note':'Latency is stream-relative first hypothesis plus current processing; not a live scheduling benchmark.'})
    target = root/'recordings/asr-report.json'
    target.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(target.read_text())


if __name__ == '__main__': main()
