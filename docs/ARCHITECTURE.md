# Architecture

Target path: physical microphone → timestamped PCM → bounded delay ring →
censored sample release → virtual playback device → OBS capture. Optional local
monitoring stays on the hardware's direct path and is not delayed.

## Implemented in M1

Float32 mono PCM at a configurable device-supported sample rate. A full-duplex
PortAudio callback owns a preallocated ring and scratch block. It writes captured
audio and reads equally sized delayed blocks into the supplied output array.
The ring starts with exactly `delay_samples` zeros. Its capacity is delay plus
one maximum callback block; no session-length storage grows. Callback-sized
NumPy views and Python counters still incur interpreter overhead; this is a
prototype, not a hard real-time guarantee.

All seconds/sample conversion belongs to Timeline. Absolute sample positions
start at zero; frame metadata uses PortAudio input ADC time, not wall-clock time.
Only the latest frame stamp is retained in this diagnostic. Future detector queue
entries must carry their own stamp, including session identity after restart.
End-exclusive word intervals round outward and apply padding centrally.

The main thread handles control and JSON telemetry. The callback does no logging,
ASR, file I/O, blocking queue operations or lock acquisition. Status/discontinuity
errors latch mute; main-thread polling stops the stream. Counts reflect reported
overflow/underflow events, not an invented number of lost samples. Stopping aborts
pending playback. Snapshots are best-effort observations, not atomic transactions.

Reference: [sounddevice stream callback contract](https://python-sounddevice.readthedocs.io/en/latest/api/streams.html).

## Planned worker boundaries

Capture publishes copies into a bounded detector input queue without waiting.
The detector worker owns the ASR instance and produces typed word events with
session-relative sample spans and confidence. ASR adapters share start/process/
poll/stop behavior, with explicit timestamp origin and finalized coverage.
Detector partials may arrive early but must not certify an entire region safe.

Playback owns censorship intervals and reads only audio eligible for release.
Beep or silence replaces original PCM completely, including fade boundaries;
it never mixes original speech beneath the tone. Event overlap/revision handling
must be deterministic. Late detection cannot repair already-played audio.

Future live release must fail closed when detector coverage misses the release
deadline, queues drop audio, or a backend fails. Display PROTECTION AT RISK with
headroom, latency, late-event and overflow counts. Even timely ASR may miss words;
successful inference is not proof of clean speech.

GUI polls immutable/bounded status snapshots on its own event loop. It never
invokes inference from the audio callback. Hardware clock drift and duplex host
compatibility require real-device measurement before OBS routing is accepted.
