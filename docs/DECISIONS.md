# Engineering decisions

## ADR 006 — Conservative local Vosk MVP
Vosk provides CPU-friendly streaming word timestamps without audio upload. Only
endpoint-finalized coverage authorizes clean release. Partials can add censor
spans but cannot prove a region clean. Deadline misses emit silence, never raw
pass-through. This sacrifices uninterrupted speech when finalization is late.
Known ASR false negatives remain a product limitation; no absolute protection
claim is made. A faster adapter may be added behind the same finalized-coverage
contract after independent validation.

## ADR 007 — PySide6 and portable Windows packaging
PySide6 keeps the desktop interface native and separates controls from audio and
inference workers. Portable packaging avoids requiring Python at runtime. Models
are user-selected external assets. Driver installation and restart remain explicit
operating-system setup steps, outside app start/stop.

## ADR 001 — Python prototype
Python/NumPy/PortAudio reduce iteration time and keep PCM manipulation testable.
Callback work is bounded; ASR will be separated. Native processing remains an
option if measurements show Python cannot meet deadlines.

## ADR 002 — Sample timeline and bounded ring
Sample indices avoid cumulative timing drift from wall-clock arithmetic. Fixed
storage and explicit over/underflow preserve ordering. Restart after audio loss
rather than pretending timestamps remain trustworthy.

## ADR 003 — Provisional 1500 ms audience delay
The requested default is implemented, not validated as enough time for ASR.
Measure end-of-word to censorship-event p99 plus padding/output scheduling
headroom before tuning. Device latency is additional to the sample delay.

## ADR 004 — VB-CABLE and interchangeable ASR planned
An external cable avoids writing a kernel audio driver. Model-specific timestamp
and revision behavior belongs behind detector adapters. No backend is selected
until latency and word-boundary behavior are measured on this machine.

## ADR 005 — Stage unprotected plumbing explicitly
M1 is a manual headphone diagnostic with an explicit unprotected flag. Virtual
outputs with common names are blocked. It must not be described as Sponsor Safe
Mode or used for OBS. Production output will remain muted on detector failure.
