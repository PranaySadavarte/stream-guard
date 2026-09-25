# OBS routing and local acceptance

## Install and select the route

1. Download [VB-CABLE from VB-Audio](https://vb-audio.com/Cable/) and
   [OBS from its official site](https://obsproject.com/download). Extract the cable
   package and run the matching installer as administrator. Restart Windows if
   the installer requires it. StreamGuard never installs a kernel driver silently.
2. Run `streamguard routing-check`. It must list both **CABLE Input** playback
   and **CABLE Output** capture. If absent, installation/restart is not complete.
3. Start StreamGuard, choose the physical microphone, **CABLE Input** output,
   and the local Vosk model directory. Begin with a 3000 ms delay for this backend.
   Default remains 1500 ms; final-result delays may cause protective silence.
4. In OBS Settings → Audio, disable global Mic/Aux inputs. Also remove/disable
   raw microphone sources from every scene and nested scene that will be used.
5. Add Audio Input Capture named StreamGuard and choose **CABLE Output**.
   In Advanced Audio Properties, leave audio monitoring **Off**. Monitor your
   microphone directly through hardware if desired, outside this delayed path.
6. Do not capture StreamGuard's playback twice through desktop audio or another
   scene. Check the OBS mixer with the physical mic source disabled.
7. Record locally before going live. Never start a broadcast from this test.

See [VB-Audio's reference manual](https://vb-audio.com/Cable/VBCABLE_ReferenceManual.pdf)
for driver requirements. Device IDs can change after restart; reselect by name.
Use 48 kHz throughout if supported. The streamer's video must be delayed to match
the audio using an appropriate OBS video delay/filter; measure the offset with a
clap recording rather than relying solely on the configured buffer value.

## Acceptance checklist

- Speak a clean phrase and a phrase containing each configured test word.
- Stop and inspect the local recording: understandable surrounding speech,
  beep/silence instead of the prohibited word, no first/last syllable leakage.
- Repeat near chunk boundaries, rapidly repeated words, noise and longer sentences.
- Simulate overload/device loss: the UI must warn and the output must be silent.
- Measure audiovisual offset, audible crackle, callback CPU load and muted time.
- Retain only consented recordings; StreamGuard itself does not save microphone
  audio by default. JSON event logs mask terms and contain timing/confidence.

## Current machine status

At implementation time, no VB-CABLE endpoints were enumerated and no OBS install
was found at the standard Windows installation path. A real local OBS recording
cannot be honestly certified until those external components are installed and
the recording is listened to. The app supports selecting their ordinary audio
device endpoints; a software replay is not a replacement for this acceptance.
