# Full-session proof of concept

Choose **Record full session, filter after Stop** as Test mode. This is now the
default mode. It records the microphone directly to a local original WAV, with
no live playback or recognition deadline. Stop closes the microphone, transcribes
the entire recording, and replaces only recognized blocked word intervals in a
separate filtered WAV. Both files have the same duration. The end of speech is
included; no delay or special pause before Stop is required.

1. Choose the Anker microphone and **Whisper · local English, offline**.
2. Select `models/faster-whisper-small.en`. Choose 48 kHz; the recording is mono.
3. Configure the blocked words, beep/silence and padding.
4. Click **Start recording**, speak normally, then **Stop**.
5. Wait for **PROCESSING FULL RECORDING** to finish. CPU processing takes time.
6. Use **Play recording** for the filtered version and **Play original** for the
   uncensored comparison. Playback uses the Windows default audio output.
7. **Open recordings** opens `%LOCALAPPDATA%/StreamGuard/recordings`. Paired files
   end with `-original.wav` and `-filtered.wav`; JSON includes duration and count.

Original audio contains everything captured, including blocked terms. Both WAVs
stay locally until deleted. No audio is uploaded. Capture or disk errors mark the
session incomplete and prevent publishing a misleading filtered result. If
transcription fails, the original remains available. Keep uncensored comparisons
out of OBS and public broadcasts.

Whisper is a local model here, using faster-whisper on CPU with int8 computation
and word timestamps. The separate download tool fetches model files; inference
loads only those local files. Speech recognition can still miss words or place
boundaries inaccurately. Listen to actual speech, including the first and final
sentences and every configured test word; fixture tests cannot guarantee accuracy.

Vosk also supports this recording mode as a smaller fallback. Whisper is a
candidate for better offline recognition, not a guarantee that it will recognize
your voice better. It is not currently supported in the experimental live mode.

**Live protection (experimental)** remains available separately. It still uses
the previous Vosk recognition deadlines and can mute continuous speech. The
full-session fix demonstrates capture, recognition, censorship and playback; it
does not resolve live streaming latency or OBS/video synchronization.

Developer setup:

```powershell
python -m pip install -e ".[app,whisper]"
python tools/download_whisper_model.py
python tools/verify_recorded_session.py
```

The small English model is about 484 MB. Deterministic tests include a 28-second
continuous session whose detector produces its first final result at Stop;
beginning/end audio and duration are preserved, and the blocked interval is replaced.
