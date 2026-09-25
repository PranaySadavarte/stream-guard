# MVP roadmap

- [x] Inspect workspace: empty project mirror; no Git repository or source files.
- [x] Establish architecture and milestone sequence.
- [x] M1 implementation: sample timeline, bounded ring, delayed duplex diagnostic.
- [ ] M1 automated tests and measured simulation results.
- [ ] M1 physical microphone/headphone stability validation.
- [ ] M1 push to confirmed GitHub repository.
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
simulation. GitHub URL is pending; local roadmap serves as issue tracking until
the target repository is confirmed.
