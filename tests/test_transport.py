from types import SimpleNamespace
import numpy as np
import pytest
import sounddevice
from streamguard.cli import main
from streamguard.audio.duplex import AudioDiagnostic
from streamguard.config import AudioSettings


def test_cli_requires_unprotected_acknowledgement():
    with pytest.raises(SystemExit) as exc:
        main(['diagnose', '--input', '0', '--output', '1'])
    assert exc.value.code == 2


def test_cli_blocks_virtual_output(monkeypatch):
    monkeypatch.setattr(sounddevice, 'query_devices', lambda device: {'name': 'CABLE Input'})
    assert main(['diagnose', '--input', '0', '--output', '1',
                 '--allow-unprotected-monitor']) == 1


def test_stream_open_failure_closes_resources(monkeypatch):
    closed = []
    class BrokenStream:
        latency = (.02, .02)
        def __init__(self, **kwargs): pass
        def start(self): raise RuntimeError('device lost')
        def close(self): closed.append(True)
    monkeypatch.setattr(sounddevice, 'check_input_settings', lambda **kw: None)
    monkeypatch.setattr(sounddevice, 'check_output_settings', lambda **kw: None)
    monkeypatch.setattr(sounddevice, 'Stream', BrokenStream)
    diagnostic = AudioDiagnostic(AudioSettings(0, 1))
    with pytest.raises(RuntimeError): diagnostic.start()
    assert closed == [True]
    assert diagnostic.stream is None


def test_stop_aborts_without_drain_even_if_abort_fails():
    closed = []
    class Stream:
        def abort(self): raise RuntimeError('disconnected')
        def close(self): closed.append(True)
    diagnostic = AudioDiagnostic(AudioSettings(0, 1))
    diagnostic.stream = Stream()
    with pytest.raises(RuntimeError): diagnostic.close()
    assert closed == [True]
    assert diagnostic.stream is None
