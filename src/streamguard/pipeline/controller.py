"""Fail-closed delayed output: only immutable, worker-sanitized blocks can play."""
import math
import sys
import threading
import time
import numpy as np
from ..audio.mailbox import AudioMailbox
from .engine import CensorEngine


class LiveController:
    def __init__(self, audio, detector, dictionary, censor):
        if hasattr(sys, '_is_gil_enabled') and not sys._is_gil_enabled():
            raise RuntimeError('free-threaded Python is not supported')
        self.audio, self.detector = audio, detector
        self.block = audio.block_samples
        self.delay = audio.delay_samples
        self.mailbox = AudioMailbox(max(10, math.ceil(audio.sample_rate/self.block)), self.block)
        self.engine = CensorEngine(audio.sample_rate, self.block, self.delay, detector, dictionary, censor)
        self.capacity = math.ceil(self.delay/self.block) + self.mailbox.capacity + 4
        self.ready = [None] * self.capacity
        self.captured = 0
        self.playback_sample = -self.delay
        self.muted_samples = self.released_samples = self.dropped_blocks = 0
        self.muted_now = False
        self.fault = None
        self.stream = None
        self.worker = None
        self.stop_event = threading.Event()
        self.stats = self.engine.snapshot()
        self.input_adc_time = 0.0
        self.host_time = 0.0
        self.last_callback = None
        self.started = False

    def callback(self, incoming, output, frames, times, status):
        output.fill(0)
        self.last_callback = time.monotonic()
        if self.stop_event.is_set() or self.fault: return
        if status or frames != self.block:
            self.fault = 'Audio discontinuity — output muted; restart required'
            self.dropped_blocks += 1
            return
        try:
            if not self.mailbox.push(incoming, self.captured):
                self.dropped_blocks += 1
                self.fault = 'Detector queue full — output muted; restart required'
                return
            self.input_adc_time = times.inputBufferAdcTime
            self.host_time = times.currentTime
            source = self.captured - self.delay
            self.muted_now = False
            offset = 0
            while offset < frames:
                position = source + offset
                if position < 0:
                    offset += min(frames-offset, -position)
                    continue
                block_start = position // self.block * self.block
                within = position - block_start
                length = min(frames-offset, self.block-within)
                item = self.ready[(block_start//self.block) % self.capacity]
                if item is not None and item[0] == block_start:
                    output[offset:offset+length] = item[1][within:within+length]
                    self.released_samples += length
                else:
                    self.muted_samples += length
                    self.muted_now = True
                offset += length
            self.captured += frames
            self.playback_sample = source + frames
        except Exception:
            output.fill(0)
            self.fault = 'Audio callback failed — output muted; restart required'

    def _work(self):
        try:
            while not self.stop_event.is_set() and not self.fault:
                item = self.mailbox.pop()
                if item is None:
                    self.stop_event.wait(.002)
                    continue
                audio, start = item
                for position, sanitized in self.engine.process(start, audio,
                        self.playback_sample, lambda:self.captured):
                    # Immutable publication: callback holds its own tuple reference.
                    self.ready[(position//self.block) % self.capacity] = (position, sanitized)
                self.stats = self.engine.snapshot()
        except Exception as exc:
            self.fault = f'Detector failed: {exc}'
        finally:
            self.detector.stop()

    def start(self):
        import sounddevice as sd
        if self.started: raise RuntimeError('create a new controller for each session')
        self.started = True
        s = self.audio
        try:
            self.detector.start(s.sample_rate)
            sd.check_input_settings(device=s.input_device, channels=1, samplerate=s.sample_rate, dtype='float32')
            sd.check_output_settings(device=s.output_device, channels=s.output_channels,
                                     samplerate=s.sample_rate, dtype='float32')
            self.stream = sd.Stream(device=(s.input_device,s.output_device), channels=(1,s.output_channels),
                                    samplerate=s.sample_rate, blocksize=self.block, dtype='float32',
                                    callback=self.callback, latency='high')
            self.worker = threading.Thread(target=self._work, daemon=True, name='StreamGuard-ASR')
            self.worker.start()
            self.stream.start()
        except BaseException:
            self.close()
            raise

    def snapshot(self):
        if self.stream is not None and not self.stop_event.is_set():
            if not self.stream.active:
                self.fault = self.fault or 'Audio device stopped'
            elif self.last_callback is not None and time.monotonic()-self.last_callback > 2:
                self.fault = self.fault or 'Audio callback stalled'
        state = ('FAULT — MUTED' if self.fault else
                 'STOPPED' if self.stop_event.is_set() else
                 'WARMING UP' if self.captured < self.delay else
                 'PROTECTION AT RISK — MUTED' if self.muted_now else 'FILTERING')
        return {**self.stats, 'state':state, 'error':self.fault,
                'delay_ms':self.delay/self.audio.sample_rate*1000,
                'queue_depth':self.mailbox.depth, 'dropped_blocks':self.dropped_blocks,
                'muted_ms':self.muted_samples/self.audio.sample_rate*1000,
                'released_ms':self.released_samples/self.audio.sample_rate*1000,
                'headroom_ms':(self.stats['finalized_sample']-max(0,self.playback_sample))/self.audio.sample_rate*1000,
                'cpu_load':self.stream.cpu_load if self.stream else None,
                'capture_adc_time':self.input_adc_time, 'host_time':self.host_time,
                'stream_relative_time':self.captured/self.audio.sample_rate}

    def close(self):
        self.stop_event.set()
        if self.stream:
            try: self.stream.abort()
            finally:
                self.stream.close()
                self.stream = None
        if self.worker:
            self.worker.join(timeout=3)
            if self.worker.is_alive():
                self.fault = 'Detector did not stop within 3 seconds; audio is stopped'
        else:
            self.detector.stop()
