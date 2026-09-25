from types import SimpleNamespace
import numpy as np
import pytest
from streamguard.audio.ring_buffer import RingBuffer
from streamguard.audio.delay import DelayLine
from streamguard.audio.timeline import Timeline
from streamguard.audio.duplex import AudioDiagnostic
from streamguard.config import AudioSettings


def pcm(values):
    return np.asarray(values, dtype=np.float32).reshape(-1, 1)


def test_ring_wraparound():
    ring = RingBuffer(5)
    ring.write(pcm([1, 2, 3, 4]))
    out = pcm([0, 0, 0])
    ring.read_into(out)
    np.testing.assert_array_equal(out, pcm([1, 2, 3]))
    ring.write(pcm([5, 6, 7, 8]))
    out = pcm([0] * 5)
    ring.read_into(out)
    np.testing.assert_array_equal(out, pcm([4, 5, 6, 7, 8]))
    assert ring.available == 0


def test_ring_errors_do_not_corrupt_unread_audio():
    ring = RingBuffer(3)
    ring.write(pcm([1, 2]))
    with pytest.raises(BufferError):
        ring.write(pcm([3, 4]))
    with pytest.raises(BufferError):
        ring.read_into(pcm([0, 0, 0]))
    with pytest.raises(ValueError):
        ring.read_into(np.zeros((1, 1), dtype=np.float64))
    out = pcm([0, 0])
    ring.read_into(out)
    np.testing.assert_array_equal(out, pcm([1, 2]))


@pytest.mark.parametrize("delay", [0, 1, 3, 7, 20, 57])
def test_delay_across_varying_blocks(delay):
    source = pcm(np.arange(300))
    result = np.zeros_like(source)
    line = DelayLine(delay, 11)
    position = 0
    rng = np.random.default_rng(4)
    while position < len(source):
        n = min(int(rng.integers(1, 12)), len(source) - position)
        line.process_into(source[position:position+n], result[position:position+n])
        position += n
        assert line.ring.available == delay
    expected = np.concatenate([pcm([0] * delay), source])[:len(source)]
    np.testing.assert_array_equal(result, expected)
    assert line.captured_samples == 300


@pytest.mark.parametrize("delay_ms", [500, 750, 1000, 1250, 1500, 2000, 2500, 3000])
def test_supported_delays_at_real_sample_rate(delay_ms):
    settings = AudioSettings(0, 1, delay_ms=delay_ms)
    n = settings.block_samples
    delay = settings.delay_samples
    length = ((delay * 2 + n - 1) // n) * n
    source = np.random.default_rng(9).uniform(-1, 1, (length, 1)).astype(np.float32)
    output = np.zeros_like(source)
    line = DelayLine(delay, n)
    for offset in range(0, length, n):
        line.process_into(source[offset:offset+n], output[offset:offset+n])
    np.testing.assert_array_equal(output[:delay], 0)
    np.testing.assert_array_equal(output[delay:], source[:-delay])


def test_delay_storage_remains_bounded():
    line = DelayLine(100, 20)
    storage = line.ring.data
    incoming = np.ones((20, 1), dtype=np.float32)
    output = np.empty_like(incoming)
    for _ in range(10000):
        line.process_into(incoming, output)
    assert line.ring.data is storage
    assert storage.nbytes == 120 * 4
    assert line.ring.available == 100


def test_invalid_delay_block_preserves_state():
    line = DelayLine(3, 2)
    with pytest.raises(ValueError):
        line.process_into(pcm([1, 2, 3]), pcm([0, 0, 0]))
    with pytest.raises(ValueError):
        line.process_into(pcm([1]), np.zeros((1, 1), dtype=np.float64))
    assert line.captured_samples == 0
    assert line.ring.available == 3


def test_timeline_padding_rounds_outward():
    timeline = Timeline(1000)
    assert timeline.interval(0.2001, 0.4001, .1, .15) == (100, 551)
    assert timeline.interval(.05, .1, .15, .1) == (0, 200)
    assert timeline.samples(1.5) == 1500
    assert timeline.seconds(1500) == 1.5
    assert timeline.stamp(1500, 77.3).relative_time == 1.5


@pytest.mark.parametrize("values", [(2, 1), (-1, 1), (0, float('nan')), (0, 1, -1)])
def test_invalid_timeline_intervals(values):
    with pytest.raises(ValueError):
        Timeline(48000).interval(*values)


@pytest.mark.parametrize("kwargs", [dict(delay_ms=float('nan')), dict(delay_ms=499),
    dict(delay_ms=3001), dict(sample_rate=0), dict(block_ms=40), dict(output_channels=6)])
def test_invalid_settings(kwargs):
    with pytest.raises(ValueError):
        AudioSettings(0, 1, **kwargs)


def times(offset=0):
    return SimpleNamespace(inputBufferAdcTime=10+offset, outputBufferDacTime=10.02+offset,
                           currentTime=10.01+offset)


def test_callback_stereo_and_exact_delay():
    diagnostic = AudioDiagnostic(AudioSettings(0, 1, sample_rate=16000,
                                              delay_ms=500, output_channels=2))
    n = diagnostic.settings.block_samples
    out = np.ones((n, 2), dtype=np.float32)
    source = np.full((n, 1), .25, dtype=np.float32)
    for index in range(25):
        diagnostic.callback(source, out, n, times(index*.02), False)
        np.testing.assert_array_equal(out, 0)
    diagnostic.callback(source, out, n, times(.5), False)
    np.testing.assert_array_equal(out, .25)
    assert not diagnostic.failed
    assert diagnostic.snapshot()['stream_relative_seconds'] == .5
    assert diagnostic.snapshot()['device_path_ms'] == pytest.approx(20)


def test_callback_fault_latches_silence():
    diagnostic = AudioDiagnostic(AudioSettings(0, 1))
    n = diagnostic.settings.block_samples
    source = np.ones((n, 1), dtype=np.float32)
    out = source.copy()
    status = SimpleNamespace(input_overflow=True, output_underflow=False)
    diagnostic.callback(source, out, n, times(), status)
    assert diagnostic.failed
    assert diagnostic.input_overflows == 1
    np.testing.assert_array_equal(out, 0)
    out.fill(1)
    diagnostic.callback(source, out, n, times(), False)
    np.testing.assert_array_equal(out, 0)
    assert diagnostic.snapshot()['state'] == 'MUTED_FAULT'


def test_callback_exception_and_oversize_mute(monkeypatch):
    for oversize in (False, True):
        diagnostic = AudioDiagnostic(AudioSettings(0, 1))
        n = diagnostic.settings.block_samples + int(oversize)
        def broken(*args):
            raise RuntimeError('injected failure')
        monkeypatch.setattr(diagnostic.delay, 'process_into', broken)
        output = np.ones((n, 1), dtype=np.float32)
        diagnostic.callback(output.copy(), output, n, times(), False)
        assert diagnostic.failed
        np.testing.assert_array_equal(output, 0)


def test_monitor_gain_and_validation():
    for gain in (-1, 2, float('nan')):
        with pytest.raises(ValueError):
            AudioDiagnostic(AudioSettings(0, 1), gain)
    diagnostic = AudioDiagnostic(AudioSettings(0, 1, sample_rate=16000, delay_ms=500), .1)
    source = np.ones((320, 1), dtype=np.float32)
    output = np.empty_like(source)
    for _ in range(26):
        diagnostic.callback(source, output, 320, times(), False)
    np.testing.assert_allclose(output, .1)


def test_bad_host_adc_timestamp_not_reported_as_measured_latency():
    diagnostic = AudioDiagnostic(AudioSettings(0, 1))
    source = np.ones((960, 1), dtype=np.float32)
    output = np.empty_like(source)
    bad = SimpleNamespace(inputBufferAdcTime=.02, currentTime=12345,
                          outputBufferDacTime=12345.02)
    diagnostic.callback(source, output, 960, bad, False)
    assert diagnostic.snapshot()['device_path_ms'] is None
    assert diagnostic.snapshot()['capture_timestamp_source'] == 'host_time_minus_reported_latency'
    assert not diagnostic.failed


def test_repeated_host_adc_timestamp_uses_estimate():
    diagnostic = AudioDiagnostic(AudioSettings(0, 1))
    source = np.zeros((960, 1), dtype=np.float32)
    output = np.empty_like(source)
    diagnostic.callback(source, output, 960, times(), False)
    diagnostic.callback(source, output, 960, times(), False)
    assert diagnostic.snapshot()['device_path_ms'] is None
