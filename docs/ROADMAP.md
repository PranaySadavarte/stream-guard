# MVP roadmap

- [x] Inspect workspace: empty project mirror; no Git repository or source files.
- [x] Establish architecture and milestone sequence.
- [x] M1 implementation: sample timeline, bounded ring, delayed duplex diagnostic.
- [x] M1 automated tests and measured simulation results: 39 passed.
- [x] M1 Anker C300 → Bose short hardware smoke test (15 seconds, no reported faults).
- [ ] M1 physical microphone/headphone stability validation.
- [ ] M1 implementation push to confirmed GitHub repository.
- [ ] M2 offline censorship: dictionary/custom words, timestamp events, padding,
      beep/silence replacement, synthetic WAV fixtures and boundary tests.
- [ ] M3 detector interface and streaming backend; confidence, timestamp extraction,
      partial/final revision handling; measure detection p50/p95/p99.
- [ ] M4 live censorship: bounded detector queue, immutable sample spans, censored
      release, fail-closed output when detection coverage misses release deadline.
- [ ] M5 virtual audio routing, OBS setup, local recording and leak inspection.
- [ ] M6 desktop UI: devices, modes, terms, padding, event history, health.
- [ ] M7 load/reliability tests, latency-based delay tuning and release packaging.

Every milestone requires relevant tests, a focused commit, and a push before
the next major milestone. Hardware success must be recorded separately from
simulation. Repository: PranaySadavarte/stream-guard; tracking epic: GitHub issue #1.
This roadmap tracks detailed acceptance alongside the epic. Physical long-run
stability and listening acceptance remain pending despite the successful smoke test.
