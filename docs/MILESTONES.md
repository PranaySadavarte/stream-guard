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

## M3 — Local streaming detection
Vosk adapter supports partial words/timestamps and monotonic endpoint-finalized
coverage. `streamguard detect --input ID --model PATH` prints detections without
playing microphone audio. A bounded single-producer/consumer mailbox isolates
inference from capture. Model download is explicit from alphacephei.com.

54 tests passed. Windows-generated clean/profanity/repeated WAVs were processed
through the actual small English Vosk model: zero blocked terms in clean speech;
`fucking` recognized in the single-word fixture; `shit` and `fucking` recognized
in the repeated fixture. First-hypothesis stream-relative delays ranged from
744 to 1395 ms in this tiny corpus. These are not sufficient p99 population
measurements and do not establish accuracy for accents, noise or live speech.
