"""Repeatable synthetic throughput measurement, not acoustic/device latency."""
import json
import time
import numpy as np
from streamguard.audio.delay import DelayLine


def main():
    sample_rate, block, delay, iterations = 48000, 960, 72000, 30000
    line = DelayLine(delay, block)
    incoming = np.random.default_rng(0).uniform(-.5, .5, (block, 1)).astype(np.float32)
    output = np.empty_like(incoming)
    timings = np.empty(iterations)
    for index in range(iterations):
        start = time.perf_counter_ns()
        line.process_into(incoming, output)
        timings[index] = (time.perf_counter_ns() - start) / 1e6
    print(json.dumps({
        'kind': 'synthetic delay-only benchmark; no ASR or hardware',
        'simulated_audio_seconds': iterations * block / sample_rate,
        'configured_delay_ms': delay / sample_rate * 1000,
        'ring_bytes': line.ring.data.nbytes,
        'block_ms': block / sample_rate * 1000,
        'processing_ms': dict(zip(('p50', 'p95', 'p99', 'max'),
                                  [*np.percentile(timings, [50, 95, 99]), timings.max()])),
    }, indent=2))


if __name__ == '__main__':
    main()
