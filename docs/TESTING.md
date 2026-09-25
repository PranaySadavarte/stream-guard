# Verification

## Automated
Run `python -m pytest` after installing `.[dev]`. No hardware, model, network,
microphone access, or speech recordings are needed for the unit/simulation suite.
Synthetic PCM is generated deterministically in tests; no third-party dataset.

Coverage: wraparound, overflow/underflow integrity, startup silence, delay shorter
than a callback, nonintegral block delays, varying block sizes, mono/stereo output,
fault muting, callback exceptions, configuration and timestamp boundary rounding.

## Physical M1 acceptance (pending)
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
