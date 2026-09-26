# Stream-safe audio architecture

Physical mic → capture mailbox → detector worker + pending PCM → sample
replacement → immutable sanitized blocks → delayed output → virtual cable → OBS.
Direct hardware monitoring stays outside the audience path.

## Ownership and scheduling

The PortAudio callback owns capture indices. It copies input to a preallocated
single-producer/consumer mailbox, then requests sanitized audio at
`captured_index - delay_samples`. Non-block-aligned delays split reads across
two output blocks. It performs no ASR, logging, file access, locks or queue waits.

The worker copies a capture slot before releasing it and owns mutable pending
audio, detector state, spans and deduplication. Sanitized arrays are published as
immutable `(absolute_sample_index, array)` tuples in bounded slots. The callback
retains a tuple reference while copying; slot replacement cannot mutate its array.
Ordinary GIL CPython 3.11+ is required; free-threaded builds are rejected. Python
and NumPy still have scheduling/allocation overhead: this is not hard real-time.

The GUI polls published dictionaries; model loading/stopping run on background
threads. Logs rotate, UI history is capped at 100 and metric windows at 2000.
Capture capacity is about one second. Output/pending memory scales with delay.
Event overflow faults rather than allowing unbounded memory growth.

## Timeline and detector contract

Timeline centralizes seconds/sample conversion, outward rounding and padding.
Ranges are half-open absolute sample intervals from session start. Restart
constructs fresh buffers and detector. Invalid MME ADC times do not influence
sample ordering; device timing is separate from the configured sample delay.

SpeechDetector provides start/process_audio/finish/stop. Detection contains
Word(text,start,end,confidence) and monotonic `finalized_through` sample coverage.
A backend must never revise finalized audio. Vosk partials add conservative spans
but cannot authorize release; endpoint-final results can. Span revisions are
unioned. Repeated words with separate raw intervals remain separate events even
when their padding overlaps.

The worker retains pre-padding plus fade lookahead before authorizing output.
Beep/silence fully replaces original PCM within padded spans. Tone phase and
envelope use absolute indices for chunk invariance. Tone fades never contain
original speech; surrounding speech tapers outside the padded interval.

## Deadlines and failures

Missing sanitized output is silence. Raw microphone audio is never a fallback.
Expired pending blocks are discarded; late results cannot restore played audio.
Queue overflow, device errors, exceptions or invalid coverage latch a fault until
restart. Stop aborts playback and signals the worker. Stuck workers are reported
and not reused.

This protects against pipeline failure, not ASR false negatives: a model can
finalize an incorrect transcript. Continuous speech may not finalize within the
selected delay, causing substantial muting. UI state and muted-duration counters
expose this tradeoff.

Deterministic tests prove sample/release invariants. Actual Vosk TTS replay tests
a tiny controlled corpus. Device smoke tests verify callback health. Neither
replaces listening, diverse voices/noise or physical OBS acceptance.

References: [sounddevice callback contract](https://python-sounddevice.readthedocs.io/en/latest/api/streams.html),
[Vosk Python implementation](https://github.com/alphacep/vosk-api/blob/master/python/vosk/__init__.py).
