from dataclasses import dataclass
import math
import numpy as np
from .timeline import Timeline


@dataclass(frozen=True)
class CensorSettings:
    mode: str = 'beep'
    frequency: float = 1000
    volume: float = .2
    before_ms: float = 150
    after_ms: float = 150
    fade_ms: float = 5

    def __post_init__(self):
        if self.mode not in ('beep', 'silence'):
            raise ValueError('mode must be beep or silence')
        if not all(math.isfinite(v) for v in (self.frequency, self.volume, self.before_ms,
                                             self.after_ms, self.fade_ms)):
            raise ValueError('censor values must be finite')
        if not 100 <= self.frequency <= 4000 or not 0 <= self.volume <= 1:
            raise ValueError('frequency must be 100–4000 Hz and volume 0–1')
        if not 0 <= self.before_ms <= 500 or not 0 <= self.after_ms <= 500:
            raise ValueError('padding must be 0–500 ms')
        if not 0 <= self.fade_ms <= 20:
            raise ValueError('fade must be 0–20 ms')


@dataclass(frozen=True)
class CensorSpan:
    start: int
    end: int
    term: str = ''
    confidence: float = 1.0


def word_span(word, sample_rate, settings):
    if not math.isfinite(word.confidence) or not 0 <= word.confidence <= 1:
        raise ValueError('invalid confidence')
    start, end = Timeline(sample_rate).interval(word.start, word.end,
                                               settings.before_ms / 1000,
                                               settings.after_ms / 1000)
    return CensorSpan(start, end, word.text, word.confidence)


def merged_spans(spans):
    result = []
    for span in sorted(spans, key=lambda s: s.start):
        if span.start < 0 or span.end < span.start:
            raise ValueError('invalid censor span')
        if result and span.start <= result[-1].end:
            previous = result[-1]
            result[-1] = CensorSpan(previous.start, max(span.end, previous.end))
        else:
            result.append(span)
    return result


def censor_into(audio, sample_start, spans, sample_rate, settings):
    """Replace all original samples in spans; fades never reveal the word.

    Global sample phase and span-relative envelope make chunking invariant.
    Original speech tapers OUTSIDE padded spans to avoid a hard discontinuity.
    """
    if settings.frequency >= sample_rate / 2:
        raise ValueError('tone must be below Nyquist')
    end = sample_start + len(audio)
    fade = Timeline(sample_rate).samples(settings.fade_ms / 1000)
    for span in merged_spans(spans):
        a, b = max(sample_start, span.start), min(end, span.end)
        if fade:
            for left, right, rising in ((span.start-fade, span.start, False),
                                        (span.end, span.end+fade, True)):
                lo, hi = max(sample_start, left, 0), min(end, right)
                if lo < hi:
                    ramp = (np.arange(lo, hi) - left) / fade
                    gain = ramp if rising else 1 - ramp
                    audio[lo-sample_start:hi-sample_start] *= gain[:, None]
        if a >= b:
            continue
        target = audio[a-sample_start:b-sample_start]
        target.fill(0)
        if settings.mode == 'beep':
            indices = np.arange(a, b)
            tone = settings.volume * np.sin(2 * np.pi * settings.frequency * indices / sample_rate)
            if fade:
                envelope = np.minimum(1, np.minimum((indices-span.start)/fade,
                                                     (span.end-1-indices)/fade))
                tone *= np.maximum(envelope, 0)
            target[:] = tone[:, None]
