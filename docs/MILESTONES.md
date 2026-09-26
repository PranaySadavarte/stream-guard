# Implementation record

## M2 — Offline waveform censorship
Added dictionary/custom terms, normalized whole-word matching, typed word events,
timestamp padding, deterministic chunk-invariant tone/silence replacement and
PCM16 WAV import/export. CLI: `streamguard censor-file input.wav output.wav
--words-json words.json`. Word records have text/start/end/confidence fields.
Annotated timestamps test the DSP independently from ASR; they are not automatic
recognition. M3 adds the actual detector.

53 automated tests passed, including real WAV round-trip, overlapping/repeated
spans, chunk-crossing words and proof that censored samples are independent of
the original PCM. Original samples are fully replaced, not mixed beneath tones.

## M3 — Local streaming detection
Vosk adapter supports partial words/timestamps and monotonic endpoint-finalized
coverage. `streamguard detect --input ID --model PATH` prints detections without
playing microphone audio. A bounded single-producer/consumer mailbox isolates
inference from capture. Model download is explicit from alphacephei.com.

54 tests passed. Windows-generated clean/profanity/repeated WAVs were processed
through the actual small English Vosk model: zero blocked terms in clean speech;
`fucking` recognized in the single-word fixture; `shit` and `fucking` recognized
in the repeated fixture. First-hypothesis stream-relative delays ranged from
744 to 1395 ms in this tiny corpus. These are not sufficient p99 population
measurements and do not establish accuracy for accents, noise or live speech.

## M4 — Live waveform censorship
The detector worker publishes sanitized immutable blocks. The output callback
has no access to the raw pending buffer and emits silence whenever a matching
sanitized block misses its release deadline. Detector queue overflow, errors,
invalid coverage and audio discontinuity cannot enable raw pass-through.

64 tests passed. Actual Vosk fixture replay through the live release algorithm
found 0/1/2 terms for clean/single/repeated fixtures, no controller errors at
3000 ms. Finalization delays also caused protective muting; this is visible in
telemetry rather than disguised as full uninterrupted protection. Long sentences
may lose substantial speech; the small Vosk backend is an MVP baseline.

## M5 — OBS route support
Added explicit virtual playback/capture readiness report and the exact OBS setup
and recording checklist. The current machine has no VB-CABLE endpoints; actual
OBS acceptance remains open. Official signed driver installer prepared locally;
installation/restart is not silently performed.

## M6 — Desktop UI
Implemented model/device selection, start/stop, delay, beep/silence, tone controls,
padding, custom terms, session metrics, masked event history, rotating event logs
and atomic settings persistence. Model startup and stopping run off the GUI
thread. Settings are locked during a session. Window close stops audio first.
66 tests passed, including UI validation/persistence; the stopped UI was rendered
and visually inspected. No microphone capture is performed by UI screenshot tests.

## M7 — Reliability, performance and packaging
73 tests passed. Added concurrent mailbox load, detector crashes, finalized
coverage violations, repeated nearby detections, stop muting and asynchronous GUI
start/stop tests. A ten-minute accelerated sample workload completed with bounded
state and no muted samples after startup using a test-only immediate detector.
Actual 30-second ASR/device smoke completed without dropped blocks or fault;
Vosk finalization caused visible protective silence. Full details are in TESTING.
Windows executable packaging and a no-capture packaged Qt/Vosk smoke test are
provided. Physical OBS and long-run/listening acceptance remain unchecked.

Packaged executable smoke test passed: Qt loaded, the window initialized, and
bundled Vosk processed PCM using the downloaded model. Fixed a packaging-specific
ICU DLL conflict: Qt uses the supported Windows 10/11 system ICU API; an unrelated
Python-runtime ICU with renamed exports must not shadow it in the app folder.
