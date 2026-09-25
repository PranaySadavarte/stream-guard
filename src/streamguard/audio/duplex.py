"""PortAudio diagnostic transport; never advertises censorship protection."""

import numpy as np
import math
from .delay import DelayLine
from .timeline import Timeline


class AudioDiagnostic:
    def __init__(self, settings, monitor_gain=1.0):
        if not math.isfinite(monitor_gain) or not 0 <= monitor_gain <= 1:
            raise ValueError("monitor gain must be between 0 and 1")
        self.monitor_gain = monitor_gain
        self.settings = settings
        self.timeline = Timeline(settings.sample_rate)
        self.delay = DelayLine(settings.delay_samples, settings.block_samples)
        self.scratch = np.zeros((settings.block_samples, 1), dtype=np.float32)
        self.callbacks = 0
        self.status_events = 0
        self.input_overflows = 0
        self.output_underflows = 0
        self.failed = False
        self.last_sample_index = 0
        self.last_capture_time = 0.0
        self.last_output_time = 0.0
        self.adc_timestamp_valid = False
        self.input_latency = 0.0
        self.output_latency = 0.0
        self.last_raw_adc_time = None
        self.stream = None

    def callback(self, indata, outdata, frames, time_info, status):
        # No ASR, I/O, logging, locks, or waiting in the audio callback.
        outdata.fill(0)
        if self.failed:
            return
        if status:
            self.status_events += 1
            self.input_overflows += int(bool(status.input_overflow))
            self.output_underflows += int(bool(status.output_underflow))
            # A dropped sample makes timestamps unreliable. Latch mute until restart.
            self.failed = True
            return
        if frames > self.settings.block_samples or frames != len(indata) or frames != len(outdata):
            self.failed = True
            return
        try:
            self.last_sample_index = self.delay.captured_samples
            adc_time = time_info.inputBufferAdcTime
            current_time = time_info.currentTime
            # Some MME drivers return a constant/non-clock ADC value. Do not
            # report a huge subtraction as measured device latency.
            self.adc_timestamp_valid = (
                math.isfinite(adc_time) and math.isfinite(current_time)
                and 0 <= current_time - adc_time <= max(1.0, self.input_latency * 4)
                and (self.last_raw_adc_time is None or adc_time > self.last_raw_adc_time)
            )
            self.last_raw_adc_time = adc_time
            self.last_capture_time = (adc_time if self.adc_timestamp_valid
                                      else current_time - self.input_latency)
            self.last_output_time = time_info.outputBufferDacTime
            target = self.scratch[:frames]
            self.delay.process_into(indata, target)
            np.multiply(target, self.monitor_gain, out=target)
            outdata[:] = target  # Explicit mono duplication for stereo-only outputs.
            self.callbacks += 1
        except Exception:
            outdata.fill(0)
            self.failed = True

    def start(self):
        import sounddevice as sd
        s = self.settings
        sd.check_input_settings(device=s.input_device, channels=1,
                                dtype="float32", samplerate=s.sample_rate)
        sd.check_output_settings(device=s.output_device, channels=s.output_channels,
                                 dtype="float32", samplerate=s.sample_rate)
        self.stream = sd.Stream(device=(s.input_device, s.output_device),
                                channels=(1, s.output_channels), dtype="float32",
                                samplerate=s.sample_rate, blocksize=s.block_samples,
                                callback=self.callback, latency="high")
        try:
            self.input_latency, self.output_latency = self.stream.latency
            self.stream.start()
        except BaseException:
            self.stream.close()
            self.stream = None
            raise

    def snapshot(self):
        stamp = self.timeline.stamp(self.last_sample_index, self.last_capture_time)
        return {
            "protection": "OFF — audio plumbing diagnostic",
            "state": "MUTED_FAULT" if self.failed else "RUNNING_UNPROTECTED",
            "sample_index": stamp.sample_index,
            "capture_timestamp": stamp.capture_time,
            "capture_timestamp_source": "adc" if self.adc_timestamp_valid else "host_time_minus_reported_latency",
            "stream_relative_seconds": stamp.relative_time,
            "buffer_delay_ms": self.timeline.seconds(self.settings.delay_samples) * 1000,
            "device_path_ms": ((self.last_output_time - self.last_capture_time) * 1000
                               if self.adc_timestamp_valid else None),
            "reported_input_latency_ms": self.input_latency * 1000,
            "reported_output_latency_ms": self.output_latency * 1000,
            "callbacks": self.callbacks,
            "status_events": self.status_events,
            "input_overflows": self.input_overflows,
            "output_underflows": self.output_underflows,
            "cpu_load": self.stream.cpu_load if self.stream else None,
            "asr_latency_ms": None,
        }

    def close(self):
        if self.stream is not None:
            try:
                self.stream.abort()  # Do not drain delayed speech on stop.
            finally:
                self.stream.close()
                self.stream = None
