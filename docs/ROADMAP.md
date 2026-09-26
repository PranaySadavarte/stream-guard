# MVP roadmap and acceptance

Implementation and external acceptance are separate. Checked code milestones do
not imply a verified broadcast or guaranteed ASR accuracy.

- [x] M1: capture, bounded ring, sample timeline, delayed diagnostic output.
- [x] M2: offline WAV replacement, dictionary, custom terms, padding and fades.
- [x] M3: actual local Vosk adapter, timestamps, generated speech validation.
- [x] M4: live censorship, worker isolation, finalized release, fail-closed mute.
- [x] M5 code: virtual-device selection, readiness check and OBS setup guide.
- [ ] M5 acceptance: install VB-CABLE/restart, record actual output in OBS,
      inspect syllable leakage, crackle, intelligibility and audiovisual sync.
- [x] M6: desktop controls, settings, event history and rotating logs.
- [x] M7 code: overload/crash/concurrency tests, percentiles and Windows build.
- [ ] M7 acceptance: hardware soak, larger voice/noise corpus, useful population
      p99, latency tuning and false-negative assessment.

The conservative Vosk backend can pass short clean speech intact at 3 seconds,
but longer utterances may be muted at the start. Reliable low-delay continuous
speech needs a faster finalization backend or separately validated overlapping
recognition. Do not hide this tradeoff by releasing unfinalized raw audio.

Repository: PranaySadavarte/stream-guard. Epic #1 tracks full acceptance. Focused
commits are pushed at each implementation milestone. Enclosing project sources
remain untouched.
