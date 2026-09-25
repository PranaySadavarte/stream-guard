"""Single producer/consumer bounded PCM mailbox for ordinary GIL CPython.

Producer publishes its index after copying; consumer releases after copying.
No lock, queue wait or speech inference executes in the audio callback.
Not supported on free-threaded Python or multiple producers/consumers.
"""
import numpy as np


class AudioMailbox:
    def __init__(self, capacity, block):
        self.storage = np.empty((capacity, block), dtype=np.float32)
        self.metadata = [None] * capacity
        self.capacity = capacity
        self.written = self.read = 0

    def push(self, audio, stamp):
        if self.written - self.read >= self.capacity:
            return False
        slot = self.written % self.capacity
        self.storage[slot] = audio.reshape(-1)
        self.metadata[slot] = stamp
        self.written += 1
        return True

    def pop(self):
        if self.read == self.written:
            return None
        slot = self.read % self.capacity
        result = (self.storage[slot].copy(), self.metadata[slot])
        self.read += 1
        return result

    @property
    def depth(self):
        return self.written - self.read
