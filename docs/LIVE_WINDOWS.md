# Experimental fast live detection

The full-session recording workflow remains the default. This change adds an opt-in live detector; it does not replace the running packaged app.

## Why change live recognition?

Sentence endpoint recognition can withhold finalized coverage throughout continuous speech. The audio callback then correctly emits protective silence when the delayed output deadline arrives. Short overlapping recognizers remove the dependency on pauses.

The candidate starts one recognizer every 250 ms, closes each after 750 ms, and commits only its first 250 ms of coverage. The remaining 500 ms provides right context. Only genuine final results authorize release; partial guesses never do. Future word timestamps may schedule censorship ahead of committed coverage. Previously released samples are immutable. All overlapping censor spans are retained, while alternative labels for the same utterance count as one notice.

Full-vocabulary windows were slower than real time on this PC. The candidate therefore uses the configured blocked words, vocabulary-supported conversational context, and Vosk's unknown token. Startup rejects any configured word absent from the model vocabulary. This speeds decoding but can change recognition accuracy and cause false positives or misses. It supports individual English words, not semantic brand violations or phrases.

## Replay evidence

Measured 2026-10-05 with the local Vosk small English model on this PC. No microphone, speaker playback, desktop controls, or OBS were used for the benchmark. Three generated-speech fixtures plus a 26.73-second continuous concatenation were replayed through the actual callback, engine, and output slots. Each short fixture was also shifted by 100, 200, 300 and 400 ms to exercise window boundaries.

The scheduled replay continues virtual 20 ms callbacks during measured inference work, exposing output deadlines and queue buildup. It is a model of scheduling, not a hardware capture or OS contention test. Five seconds of trailing silence drains the replay.

- All 16 cases matched expected event counts (including 12 violations in continuous speech), with no simulated faults.
- Audience delay: **1250 ms**. Prepared audio age: median 800 ms, 99th percentile 920 ms.
- Worst per-case processing 99th percentile: **23.88 ms**; largest observed step: **33.93 ms**. Most blocks do little work; expensive window closures can exceed one callback interval, using buffer headroom.
- Replay processing time / padded audio duration: **0.109-0.166**. This is not CPU utilization and includes the trailing silence.
- Clean-only fixtures remained unchanged. Continuous speech preserved 98.11% of active clean samples outside reference censor padding. Some nearby clean speech is censored too.
- At least 99.95% of active samples inside offline-reference blocked-word intervals changed. The reference is another Vosk pass, not human annotation; these figures do not prove no audible leakage, general recall, or performance on accents/noise/custom terms.

[Compact measured results](LIVE_WINDOW_RESULTS.json) contain generated-fixture metrics only. Original microphone recordings are neither committed nor uploaded.

## Try when ready

The source GUI offers `Live protection (experimental)` plus `Vosk - fast live (experimental)`. Choose the extracted Vosk model and at least 1.25 seconds of audience delay. Existing full-session recording and offline Whisper remain available. This source update has not been packaged into the app currently open on the PC.

The command-line equivalent is:

```powershell
streamguard live --input <mic-id> --output <output-id> --model models/vosk-model-small-en-us-0.15 --detector bounded --window-ms 750 --hop-ms 250 --delay-ms 1250
```

The CLI retains endpoint detection by default. Bounded CLI mode requires at least window duration + 500 ms of delay. This is a conservative experimental floor, not a guarantee. Under sustained overload, device faults or missing finalized coverage, output remains muted.

To reproduce the no-device benchmark, first generate the saved fixtures with `tools/generate_speech.ps1`, then run:

```powershell
python tools/benchmark_live_windows.py --keywords --scheduled --window-ms 750 --hop-ms 250 --delay-ms 1250 --phase-sweep
python -m pytest -q
```

The replay process lowers its own Windows CPU priority so foreground work takes priority.

## Remaining validation

Before broadcasting: annotate real-voice recordings; test accents, noise, fast speech, every configured term and false positives; replay under game/encoding load; verify microphone, cable and OBS routing; measure actual end-to-end audio delay and match video delay. A fast decoder cannot remove the lookahead needed to recognize and censor a word before viewers hear it. Phone/watch alerts remain future work; the existing on-screen notice is retained.
