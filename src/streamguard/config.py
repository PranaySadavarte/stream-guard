from dataclasses import dataclass
import math
from .audio.timeline import Timeline


@dataclass(frozen=True)
class AudioSettings:
    input_device: int
    output_device: int
    sample_rate: int = 48000
    block_ms: int = 20
    delay_ms: float = 1500
    output_channels: int = 1

    def __post_init__(self):
        if self.sample_rate not in (16000, 32000, 44100, 48000):
            raise ValueError("unsupported sample rate")
        if self.block_ms not in (10, 20, 30):
            raise ValueError("block_ms must be 10, 20, or 30")
        if not math.isfinite(self.delay_ms) or not 500 <= self.delay_ms <= 3000:
            raise ValueError("delay_ms must be 500–3000")
        if self.output_channels not in (1, 2):
            raise ValueError("output_channels must be 1 or 2")
        if self.input_device < 0 or self.output_device < 0:
            raise ValueError("select explicit nonnegative device IDs")

    @property
    def block_samples(self):
        return Timeline(self.sample_rate).samples(self.block_ms / 1000)

    @property
    def delay_samples(self):
        return Timeline(self.sample_rate).samples(self.delay_ms / 1000)
