# StreamGuard 0.3 RC1 quick start

English-only. Open **Launch StreamGuard.cmd** in the project folder. The current
package is in `release/StreamGuard`; keep its `_internal` folder with the EXE.
The narrated, captioned walkthrough is in `artifacts/tutorial/StreamGuard-Tutorial.mp4`.

## Record a whole session

1. Choose **Record full session, filter after Stop**. The app selects the saved
   recording detector, defaulting to local Whisper when that model is installed.
2. Choose your microphone. Output and audience delay do not apply in this mode.
3. Click **Start recording**, speak normally, then **Stop**.
4. Wait for **PROCESSING FULL RECORDING** to finish. Controls remain locked while
   the complete recording is processed.
5. Compare **Play original** and **Play filtered**. **Open recordings** shows files.

Original microphone audio is saved locally. If filtering fails, the original is
retained and playback stays available when a readable recording exists.

## Test live filtering

1. Select **Live protection (experimental)**. The app selects the compatible live
   detector and restores its model path. Default: **Vosk - fast live**.
2. Select your microphone and output. For local listening, use headphones to avoid
   feedback. For OBS, use **CABLE Input** and capture **CABLE Output** in OBS.
3. Use at least **1.25 seconds** of audience delay. Choose devices using the same
   Windows audio API and a supported sample rate/channel configuration.
4. Click **Start protection**. Wait for **FILTERING**, then speak. Blocked words
   produce an on-screen notice and event entry. Phone/watch alerts are future work.
5. If saving live output, pause for at least the audience delay before **Stop** so
   the end of the sentence reaches output. Stop immediately discards delayed audio.
6. **Play recording** replays the actual output, including startup or fault silence.

## Change words or switch modes

**Stop -> wait -> edit -> Save settings -> wait for validation -> Start.**

One English word per line. Fast-live vocabulary is finite. Unsupported words are
listed explicitly. Edit them, or click **Remove unsupported words**, then Save.
Unsupported words are never silently dropped, and a failed save does not replace
valid settings. Hindi/Hinglish, phrases and semantic brand rules are not supported.

Changing Test mode automatically restores the corresponding detector and model
folder. Each mode remembers its most recent playback result for this app session.
Refreshing devices keeps selections that are still present. If a device disappears,
choose its replacement before starting again.

A failed start unlocks controls and preserves prior recordings. Correct the visible
error and retry. Stop during model loading requests cancellation; wait for cleanup
before starting again. Closing during processing waits for the operation to finish.

## One launcher, one app

Opening the launcher again reveals the running instance instead of opening a
second microphone session. Older already-running development builds do not have
this protection; close those normally once before opening this release.

Settings and normal recordings live in `%LOCALAPPDATA%/StreamGuard`. On first launch,
newer settings from the temporary live-test launcher are imported once, and the old
normal settings are backed up as `settings-before-unification.json`. No recordings
are moved or deleted. Recordings made by that earlier launcher remain under the
project's `recordings/live-test-state/recordings` folder.

Recognition can miss words. Before a public stream, check your real voice, noisy
conditions, the full blocked list, game/encoder load, OBS routing and audio/video
synchronization in a local recording.
