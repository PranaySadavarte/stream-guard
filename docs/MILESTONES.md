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
