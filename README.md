# StreamGuard

Windows desktop prototype that delays the audience microphone path, recognizes
speech locally, and replaces configured word intervals with a beep or silence.

**0.3 RC1: English desktop release candidate.** Recording and live mode now
select compatible detectors automatically. Session switching, word-list saving,
startup cancellation and failure recovery have automated regression coverage.
Recognition accuracy and final OBS acceptance still depend on your own setup.

## Launch

Double-click **Launch StreamGuard.cmd**. It opens the current package at
`release/StreamGuard/StreamGuard.exe`, or the source environment when no current
package exists. Reopening the launcher reveals the existing app.

- **Record full session:** choose a microphone, Start recording, speak, Stop,
  wait for filtering, then compare **Play original** and **Play filtered**.
- **Live protection:** select the microphone/output, use **Vosk - fast live**
  and at least **1.25 seconds** of audience delay, then Start protection.
- **Change words:** Stop, wait, edit one word per line, Save settings, wait for
  validation, then Start. Unsupported English-model words are named explicitly;
  edit them or use **Remove unsupported words**. Invalid saves retain the last
  valid settings. Hindi/Hinglish and phrases are not supported in this release.
- **Switch modes:** Stop and wait for processing, then change Test mode. The app
  restores the matching model and that mode's latest playback results.

See the [current quick start](docs/QUICK_START.md),
[release validation](docs/RELEASE_READINESS.md) and [user guide](docs/USER_GUIDE.md).
The generated narrated video is `artifacts/tutorial/StreamGuard-Tutorial.mp4`.

For OBS, StreamGuard sends to **CABLE Input**; OBS captures **CABLE Output**.
Disable raw microphone sources. Match video delay to measured audio delay and
verify a local OBS recording before broadcasting. Use direct hardware monitoring
for the streamer. Speakers can feed back into the microphone.

## Source installation (Windows, Python 3.11+)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,app]"
.\.venv\Scripts\python.exe tools\download_model.py
.\.venv\Scripts\streamguard.exe gui
```

The explicit downloader fetches the ~40 MB small English model from
[Vosk's official host](https://alphacephei.com/vosk/models). Inference then runs
locally with no API key or audio upload. Model memory is additional to bounded
PCM storage. Other languages/models have not been validated here.

## Implemented

- Mono capture with optional stereo duplication; bounded sample-index buffers.
- Local streaming Vosk backend behind an independent detector protocol.
- Default dictionary, custom single words, normalization and timestamp padding.
- Full PCM beep/silence replacement with fades; no original word mixed underneath.
- Fail-closed output: only finalized, sanitized blocks reach playback.
- Desktop controls, visible late/muted/fault state, metrics and masked event logs.
- Offline PCM16 WAV censorship, generated speech fixtures and replay tools.
- OBS readiness check, Windows package build and CI tests.

Beep volume/frequency and padding are configurable. Low confidence does not cause
a recognized blocked word to be ignored. Attenuation is omitted because it leaves
the original word audible. Custom phrases/contextual rules are future work.

## Commands

```powershell
streamguard devices
streamguard routing-check
streamguard live --input 1 --output 5 --model models\vosk-model-small-en-us-0.15 --detector bounded --delay-ms 1250
streamguard detect --input 1 --model models\vosk-model-small-en-us-0.15
streamguard censor-file input.wav censored.wav --model models\vosk-model-small-en-us-0.15
streamguard censor-file input.wav censored.wav --words-json words.json --mode silence
```

IDs above are examples: enumerate and select current devices. Both must support
the chosen sample rate and duplex host API. `live` defaults to 48 kHz, stereo
output and a 60-second run. `detect` emits events without playback. `diagnose` is
the old **uncensored** plumbing test and must not feed OBS.

Offline input must be PCM16 WAV. Annotation JSON is a list of
`{"text":"word","start":0.5,"end":0.9,"confidence":1.0}` records in seconds.
Annotations test DSP independently; `--model` performs ASR. `--terms` accepts a
UTF-8 file with one word per line. Output must differ from the source path.

## Status and privacy

The UI distinguishes stopped, loading, warming up, filtering, at-risk/muted and
faults. Queue overflow, invalid coverage, device errors and detector crashes
cannot enable raw pass-through. Stop aborts queued playback. Full-session mode records raw microphone audio locally and produces a separate
filtered file. Live mode optionally saves the protected output, including startup
and protective silence, and can replay it after stopping. Recordings
are local under `%LOCALAPPDATA%/StreamGuard/recordings` and remain until deleted.

Settings and rotating JSON logs are under `%LOCALAPPDATA%/StreamGuard`. Terms are
masked in GUI logs; CLI debugging can show the full detected word. Percentiles
describe recent samples, not guaranteed accuracy. Callback CPU load is a budget
ratio, not whole-process CPU utilization. Invalid MME clocks do not affect the
sample-relative timeline.

## Test and build

```powershell
python -m pytest
powershell -File tools\generate_speech.ps1
python tools\verify_speech.py
python tools\replay_live.py
python tools\benchmark_delay.py
python -m pip install -e ".[build]"
powershell -File tools\build_windows.ps1 -Python .venv\Scripts\python.exe
```

Deterministic tests need no model or hardware. UI tests require the `app` extra.
Speech verification needs the downloaded model and Windows-generated TTS.
Fixtures, models and recordings are ignored by Git. Hardware scripts are explicit
and must use the correct IDs. See [results](docs/TESTING.md),
[architecture](docs/ARCHITECTURE.md), [OBS setup](docs/OBS_SETUP.md),
[milestones](docs/MILESTONES.md), [roadmap](docs/ROADMAP.md), and
[decisions](docs/DECISIONS.md).
