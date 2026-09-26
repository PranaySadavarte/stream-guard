from dataclasses import dataclass
from typing import Protocol
import numpy as np


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    confidence: float = 1.0


@dataclass(frozen=True)
class Detection:
    words: tuple[Word, ...] = ()
    # Only finalized coverage may authorize output. Partials never advance this.
    finalized_through: int = 0


class SpeechDetector(Protocol):
    def start(self, sample_rate: int) -> None: ...
    def process_audio(self, audio: np.ndarray) -> Detection: ...
    def finish(self) -> Detection: ...
    def stop(self) -> None: ...
