"""Exact sample delay with startup silence and no unbounded queues."""

import numpy as np
from .ring_buffer import RingBuffer


class DelayLine:
    def __init__(self, delay_samples: int, max_block: int, channels: int = 1):
        if delay_samples < 0 or max_block <= 0:
            raise ValueError("invalid delay or block size")
        self.max_block = max_block
        self.ring = RingBuffer(delay_samples + max_block, channels)
        self.ring.write(np.zeros((delay_samples, channels), dtype=np.float32))
        self.captured_samples = 0

    def process_into(self, incoming, outgoing):
        if incoming.shape != outgoing.shape or len(incoming) > self.max_block:
            raise ValueError("mismatched buffers or oversized callback")
        # Validate both before mutating state.
        self.ring._validate(incoming)
        self.ring._validate(outgoing)
        self.ring.write(incoming)
        self.ring.read_into(outgoing)
        self.captured_samples += len(incoming)
