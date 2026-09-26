# Verification

## Full implementation results — 2026-09-25 UTC

- 73 deterministic/UI/concurrency tests passed, 0 failed (1.16 s).
- Actual Vosk small English model on locally generated Windows speech: clean
  fixture 0 detections, single profanity fixture 1, repeated fixture 2. Offline
  censored WAVs and live-algorithm replay WAVs were generated locally.
- Stream-relative first-hypothesis latency on the tiny corpus: approximately
  670–1395 ms. This is not a statistically valid general p99 or human-voice accuracy
  measurement. Model SHA256: `30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498`.
- At 3000 ms, replay preserved 100% of active clean-fixture samples. Other fixture
  changes include both expected censor spans and protective muting. The repeated
  fixture exposed the cost of late endpoint finalization; do not interpret every
  changed sample as successfully precise censorship.
- 30-second actual Anker C300 → Bose run with the local ASR worker: no controller
  fault or dropped blocks; processing p50 0.372 ms, p95 4.910 ms, p99 20.727 ms per
  20 ms block. No blocked words were spoken/detected in that smoke run, so its
  detection-latency distribution is unavailable. Final queue depth was 0.
- At 3000 ms the hardware run muted 12.84 s and released 14.16 s after initial
  delay. This includes ambient/silent audio and demonstrates finalization-related
  muting; it is not a claim that 12.84 s of human speech was lost. Callback load was
  ~0.32% of its budget. Full-process CPU/memory and acoustic latency are unmeasured.
- Accelerated 600-second whole release-pipeline test with a test-only immediate
  detector: zero faults and zero muted samples after startup, bounded pending
  state (max 8 blocks), 129 output slots and 64,000 bytes of capture storage.
  Wall time 1.80 s. This is not a 10-minute real-device soak or ASR benchmark.
- UI was rendered and visually checked; asynchronous start/stop and saved settings
  were tested. Windows portable packaging was built; final executable smoke results
  are recorded in the milestone log.
- Packaged executable smoke test passed after removing an incompatible collected
  ICU DLL: Qt window initialization and actual bundled Vosk PCM inference succeeded.
- Real VB-CABLE → OBS recording, listening, accents/noise, long-run drift and
  production protection acceptance remain open. Official signed driver and
  isolated portable OBS downloads are prepared locally; no public broadcast ran.

### Reproduce
`python -m pytest`, then `tools/generate_speech.ps1`, `tools/verify_speech.py`,
`tools/replay_live.py`, and `tools/stress_pipeline.py`. Hardware scripts require
deliberate device selection and access outside a sandbox that blocks audio APIs.
Do not conflate ASR processing percentiles, first-detection latency, finalization
age, configured buffer delay and acoustic output latency.

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
