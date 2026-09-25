# Verification

## Automated
Run `python -m pytest` after installing `.[dev]`. No hardware, model, network,
microphone access, or speech recordings are needed for the unit/simulation suite.
Synthetic PCM is generated deterministically in tests; no third-party dataset.

Coverage: wraparound, overflow/underflow integrity, startup silence, delay shorter
than a callback, nonintegral block delays, varying block sizes, mono/stereo output,
fault muting, callback exceptions, configuration and timestamp boundary rounding.

## Recorded results — 2026-09-25 UTC

- Windows, Python 3.12.14, NumPy 2.3.5, sounddevice 0.5.6, pytest 9.1.1.
- 39 automated tests passed, 0 failed (0.60 s).
- Installation and installed command help verified.
- Synthetic 600-second audio workload (30,000 × 20 ms blocks), 1500 ms delay:
  delay-only processing p50 0.0050 ms / p95 0.0054 ms / p99 0.0101 ms /
  maximum 0.0263 ms. Ring storage 291,840 bytes. This runs faster than real time
  and is not a 10-minute hardware soak or ASR benchmark.
- Physical Anker PowerConf C300 input ID 1 → Bose USB Audio output ID 5,
  MME, 48 kHz, mono capture / stereo output, 20 ms blocks, 1500 ms sample delay,
  diagnostic gain 0.03. Five-second initial and 15-second post-fix runs exited
  successfully. The final run processed 748 callbacks with zero reported status
  events, input overflows or output underflows. Final callback CPU-load ratio
  0.00454 (~0.45% of callback budget, **not whole-process CPU utilization**).
- Driver-reported input/output latency was 40/200 ms; acoustic latency was not
  measured. MME returned invalid constant ADC times. The code now labels the
  capture-time fallback as estimated and reports measured device-path latency
  as unavailable rather than fabricating a measurement.
- Device opening failed inside the restricted sandbox (MME/DirectSound host
  errors), then succeeded outside it. This is an environment limitation.
- No speech/audio recordings were retained. Sound quality, feedback, actual
  speech intelligibility, acoustic delay, long-run drift and disconnect behavior
  still require manual/long-run validation. ASR is not implemented or measured.

## Physical M1 acceptance (long-run/manual checks pending)
1. Keep OBS closed. Enumerate audio devices and choose mic/headphones explicitly.
2. Run the 30-second diagnostic with 1500 ms delay; check understandable delayed
   speech, silence at startup, no crackle or feedback, and clean stop.
3. Run for 10 minutes while under typical streaming CPU load. Save JSON status.
4. Repeat delays 500/750/1000/1250/1500/2000/2500/3000 ms.
5. Record device names, host API, sample rate, actual measured end-to-end latency,
   CPU load and status/overflow counters. Device disconnect must stop/mute.

Do not mark this acceptance complete from a simulated stream. True acoustic
latency requires loopback/recording measurement. ASR latency and leak checks are
not applicable until later milestones. No microphone recording is created here.

## Future censorship/OBS acceptance
Create consented or synthetic spoken fixtures with annotated word boundaries.
Test clean speech, repeated/overlapping events, chunk-spanning profanity,
late partial revisions, overload, disconnect/reconnect, and backend crashes.
Verify PCM replacement plus listen to the exported result. Use a local OBS
recording; disable every raw mic route. Record ASR p50/p95/p99, late events,
headroom, CPU, actual delay and boundary leakage separately.
