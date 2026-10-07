# StreamGuard 0.3 RC1 - reliability release

Validated 2026-10-07. English-only, as requested. This is a tested release candidate;
recognition accuracy and end-to-end broadcast acceptance are not a guarantee.

## Fixed workflows

- Live -> record -> live selects compatible recognizers and remembers model paths.
- Playback results remain associated with their own mode.
- Every session uses fresh capture, recognition and recording state.
- Word-list Save validates fast-live vocabulary asynchronously, then writes settings
  atomically. Unsupported words produce an actionable list and an explicit remove
  button. No term is silently omitted and invalid saves retain the last valid file.
- Failed starts/saves/filtering unlock controls. Prior recordings and a captured
  original remain available where applicable.
- Stop during startup requests cancellation and closes the subsequently created
  resources. Close waits for cleanup. Empty recordings have an explicit error.
- Live cleanup joins the recognition worker and closes the recorder even when
  audio abort/close throws. Repeated close is supported.
- Device refresh preserves surviving selections. Corrupt settings fall back to
  editable defaults with an error message.
- One app instance per user; repeated launcher calls reveal the existing window.
- The regular launcher now opens the current release package. Earlier temporary
  live-test preferences migrate once, preserving a backup of regular settings.

## Completed validation

| Check | Result |
|---|---|
| Automated tests | 106 passed; no physical audio devices used |
| Session regression | 15 consecutive live/record/live sessions with saves and word edits |
| Failure regression | Unsupported vocabulary, startup failure, cancellation, disk/save failure, transcription failure, corrupt settings, resource-close failure |
| Real-model integration | Vosk -> Whisper -> Vosk, generated WAV input; supported word added and saved before final session |
| Recorded result | 39,040 original and filtered samples at 16 kHz; 10,391 samples changed by filtering |
| Resource balance | Three simulated streams opened and three closed in real-model integration |
| Duplicate launch | Two offscreen processes created one window; second launch revealed the first |
| Windows package | EXE loaded Qt/playback, bounded Vosk, edited keywords and local Whisper; mode-switch smoke test passed |
| Tutorial | 1920x1080, 24 fps, 178.67 seconds, narrated and captioned; audio/video duration difference under 1 ms; six decoded frames visually reviewed |

`tools/verify_session_switching.py` uses real installed models with fake devices
fed from generated speech. `tools/verify_single_instance.py` tests the real local
socket/lock protocol. Neither script opens the physical microphone or speakers.

Earlier fast-live latency evidence remains in [LIVE_WINDOWS.md](LIVE_WINDOWS.md):
750 ms recognition windows, 250 ms hops, 1250 ms audience buffer. The recognition
algorithm and its lookahead are unchanged by this reliability release.

## Release boundary

The user reported the previous live version working in their own test. This release
has not repeated physical-microphone tests or OBS/game-load tests. Before external
shipment or a sponsored stream, verify real accents/noise, the complete blocked list,
false positives/negatives, long sessions, device reconnects, encoder contention,
virtual-cable routing, and measured video synchronization. The portable package is
not code-signed and does not include an installer or automatically download models.

Phone/watch notifications, Hindi/Hinglish, phrases and semantic brand policy checks
remain future work. English live vocabulary is finite. An unsupported transliterated
word cannot be made recognizable merely by adding it to a text list.

## Reproduce

```powershell
python -m pytest -q
python tools/verify_session_switching.py
python tools/verify_single_instance.py
powershell -File tools/build_windows.ps1 -Python .venv/Scripts/python.exe
```

Tutorial generation uses `tools/make_tutorial.py --assets`, the local Windows voice
through `tools/narrate_tutorial.ps1`, then `tools/make_tutorial.py --render`. It renders
offscreen demo views and diagrams; it never captures the desktop or records speech.
