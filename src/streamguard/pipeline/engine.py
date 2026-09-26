"""Worker-owned censorship state, independent of devices and wall-clock pacing."""
from collections import deque
import time
import numpy as np
from ..audio.censor import censor_into, word_span
from ..audio.timeline import Timeline


class CensorEngine:
    def __init__(self, rate, block, delay, detector, dictionary, censor):
        self.rate, self.block, self.delay = rate, block, delay
        self.detector, self.dictionary, self.censor = detector, dictionary, censor
        self.pending = {}
        self.spans = []
        self.events = deque(maxlen=100)
        self.event_sequence = 0
        self.detected = 0
        self.late = 0
        self.processed = self.finalized = 0
        self.processing_ms = deque(maxlen=2000)
        self.detection_ms = deque(maxlen=2000)
        self.release_age_ms = deque(maxlen=2000)
        self._seen = {}

    def process(self, start, audio, playback_sample, captured_sample):
        if start != self.processed:
            raise RuntimeError('noncontiguous detector input')
        self.pending[start] = audio
        began = time.perf_counter()
        result = self.detector.process_audio(audio)
        self.processing_ms.append((time.perf_counter()-began)*1000)
        self.processed += len(audio)
        if not self.finalized <= result.finalized_through <= self.processed:
            raise RuntimeError('invalid detector coverage')
        previous_finalized = self.finalized
        self.finalized = result.finalized_through
        for word in result.words:
            if not self.dictionary.matches(word.text): continue
            span = word_span(word, self.rate, self.censor)
            if span.end <= playback_sample: continue
            # Union revisions, including earlier/later boundaries, until expired.
            key = next((key for key, old in self._seen.items()
                        if old.text == word.text and old.start < word.end and word.start < old.end), None)
            if key is None:
                if word.start*self.rate < previous_finalized - 1:
                    raise RuntimeError('detector revised previously finalized audio')
                self.event_sequence += 1
                key = self.event_sequence
                self.detected += 1
                is_late = span.start < playback_sample
                self.late += int(is_late)
                capture_now = captured_sample() if callable(captured_sample) else captured_sample
                latency = max(0, capture_now/self.rate-word.end)*1000
                self.detection_ms.append(latency)
                self.events.append({'id':key, 'term':word.text, 'start':word.start, 'end':word.end,
                                    'confidence':word.confidence, 'late':is_late,
                                    'latency_ms':latency, 'timestamp':time.time()})
            self._seen[key] = word
            self.spans.append(span)
        self._seen = {k:v for k,v in self._seen.items()
                      if (v.end+self.censor.after_ms/1000)*self.rate > playback_sample}
        # A repeated ASR partial does not need another identical interval.
        self.spans = list({(s.start,s.end):s for s in self.spans if s.end + self.rate//50 > playback_sample}.values())
        guard = Timeline(self.rate).samples((self.censor.before_ms+self.censor.fade_ms)/1000)
        ready = []
        capture_now = captured_sample() if callable(captured_sample) else captured_sample
        for position in list(self.pending):
            if position + self.block <= playback_sample:
                del self.pending[position]  # Expired audio was muted by the callback.
            elif position + self.block <= self.finalized - guard:
                block = self.pending.pop(position).reshape(-1, 1).copy()
                censor_into(block, position, self.spans, self.rate, self.censor)
                self.release_age_ms.append(max(0,capture_now-position)/self.rate*1000)
                ready.append((position, block))
        # Malfunctioning adapters cannot grow session-length data indefinitely.
        if len(self.pending) > (self.delay // self.block + 100):
            raise RuntimeError('pending audio capacity exceeded')
        if len(self.spans) > 4096 or len(self._seen) > 4096:
            raise RuntimeError('detector event capacity exceeded')
        return ready

    def snapshot(self):
        def percentiles(values):
            return dict(zip(('p50','p95','p99'), np.percentile(list(values), [50,95,99]).tolist())) if values else None
        return {'detected':self.detected, 'late_detections':self.late,
                'finalized_sample':self.finalized, 'processed_sample':self.processed,
                'processing_ms':percentiles(self.processing_ms),
                'detection_latency_ms':percentiles(self.detection_ms),
                'release_age_ms':percentiles(self.release_age_ms),
                'observed_delay_hint_ms':(float(np.percentile(list(self.release_age_ms),99))*1.25+100
                                           if self.release_age_ms else None),
                'events':list(self.events)}
