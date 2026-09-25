# StreamGuard

Windows-first real-time livestream profanity censor, under development.

**Current stage: Milestone 1 audio plumbing. Protection is OFF. There is no
speech recognition or censorship yet. Do not route this diagnostic into OBS.**

The intended product captures a microphone, delays only the audience path,
detects prohibited words with timestamps, replaces their PCM samples, and sends
sanitized audio to a virtual device. The streamer's normal monitoring remains
direct through their audio hardware, outside this path.

## Install (Windows, Python 3.11+)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\streamguard.exe devices
```

Choose explicit microphone and **headphone** output IDs. Keep OBS closed.
The following IDs are examples; substitute your listed devices:

```powershell
.\.venv\Scripts\streamguard.exe diagnose --input 1 --output 4 --delay-ms 1500 --seconds 30 --allow-unprotected-monitor
```

The delayed headphone output is for verifying this milestone only. Never use it
as the streamer's normal monitoring path. Use headphones to prevent feedback.
Recognizable virtual audio outputs are rejected in this diagnostic; name-based
filtering is a convenience, not a security guarantee.

Options: `--delay-ms` 500–3000 (default 1500), `--block-ms` 10/20/30,
`--monitor-gain` 0–1 (default 0.1, deliberately quiet for diagnostic playback),
`--sample-rate` 16000/32000/44100/48000, `--output-channels` 1 or 2. Audio is
mono internally; stereo output duplicates mono. Both devices must support the
selected rate and a compatible PortAudio host API. Try another pair of listed
device IDs if the host rejects a duplex stream. No automatic resampling yet.

Output starts with silence for the configured number of samples. Device latency
is additional. A callback status error latches silence and terminates the run;
Ctrl+C aborts without draining queued speech. JSON status goes to stdout (redirect
it to a `.log` file if desired). Microphone audio is never saved by this command.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Tests simulate audio hardware and prove sample delay, bounded memory, wraparound,
timestamp mapping, and fault muting. They do not prove real microphone/device
stability. See [testing](docs/TESTING.md) for validation status and procedure.

## Planned OBS setup (not available in this milestone)

Once live censorship passes testing: install VB-CABLE separately, select CABLE
Input as StreamGuard's playback output, and select CABLE Output as OBS's audio
capture source. Disable raw mic sources in OBS and avoid duplicate routes.
Record locally before broadcasting. Video will need matching synchronization.
StreamGuard does not install drivers or change OBS settings.

ASR adapters, profanity configuration, beep/silence, GUI, and actual safe virtual
output are still pending. ASR can miss words; never claim absolute protection
based only on detector uptime. No API credentials or backend is required yet.

See [roadmap](docs/ROADMAP.md), [architecture](docs/ARCHITECTURE.md), and
[decisions](docs/DECISIONS.md).
