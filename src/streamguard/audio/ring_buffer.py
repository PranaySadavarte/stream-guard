"""Bounded PCM storage. One owner thread; callers supply all output storage."""

import numpy as np


class RingBuffer:
    def __init__(self, capacity: int, channels: int = 1):
        if capacity <= 0 or channels <= 0:
            raise ValueError("capacity and channels must be positive")
        self.data = np.zeros((capacity, channels), dtype=np.float32)
        self.capacity = capacity
        self.channels = channels
        self.read_position = 0
        self.write_position = 0
        self.available = 0

    def _validate(self, block):
        if block.ndim != 2 or block.shape[1] != self.channels or block.dtype != np.float32:
            raise ValueError("expected float32 array with shape (frames, channels)")

    def write(self, block):
        self._validate(block)
        n = len(block)
        if n > self.capacity - self.available:
            raise BufferError("ring overflow; unread audio would be overwritten")
        first = min(n, self.capacity - self.write_position)
        self.data[self.write_position:self.write_position + first] = block[:first]
        self.data[:n - first] = block[first:]
        self.write_position = (self.write_position + n) % self.capacity
        self.available += n

    def read_into(self, output):
        self._validate(output)
        n = len(output)
        if n > self.available:
            raise BufferError("ring underflow")
        first = min(n, self.capacity - self.read_position)
        output[:first] = self.data[self.read_position:self.read_position + first]
        output[first:] = self.data[:n - first]
        self.read_position = (self.read_position + n) % self.capacity
        self.available -= n
