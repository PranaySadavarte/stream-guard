"""The sole conversion boundary between time and absolute sample positions."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class FrameStamp:
    sample_index: int
    capture_time: float
    relative_time: float


@dataclass(frozen=True)
class Timeline:
    sample_rate: int

    def __post_init__(self):
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")

    def seconds(self, samples: int) -> float:
        return samples / self.sample_rate

    def samples(self, seconds: float) -> int:
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("time must be finite and nonnegative")
        return round(seconds * self.sample_rate)

    def interval(self, start: float, end: float, before: float = 0,
                 after: float = 0) -> tuple[int, int]:
        """Outward rounding retains boundary syllables; ranges are half-open."""
        if any(not math.isfinite(x) or x < 0 for x in (start, end, before, after)):
            raise ValueError("times and padding must be finite and nonnegative")
        if end < start:
            raise ValueError("end precedes start")
        return (math.floor(max(0, start - before) * self.sample_rate),
                math.ceil((end + after) * self.sample_rate))

    def stamp(self, sample_index: int, capture_time: float) -> FrameStamp:
        return FrameStamp(sample_index, capture_time, self.seconds(sample_index))
