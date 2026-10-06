# StreamGuard user guide

StreamGuard is a Windows prototype for filtering the microphone audio heard by
your audience. It recognizes speech locally, looks for your blocked single words,
and replaces their audio with a beep or silence. Your audience audio is delayed
to give recognition time to work. Phone and watch notifications are future work.

## 1. Open the app

Double-click **Launch StreamGuard.cmd** in the project folder. Keep the packaged
`dist/StreamGuard` folder and its `_internal` folder together. Nothing is routed
until you click **Start protection**.

## 2. Configure a local speaker test

For this computer, choose **Anker PowerConf C300 · MME** as Microphone and
**Speakers (Bose USB Audio) · MME** as Output to OBS. The latter field also accepts
ordinary speakers for a local test. Keep the speaker volume low: delayed speaker
audio can be picked up by the microphone and cause feedback. Headphones are a
better choice for longer testing.

Browse to the extracted `models/vosk-model-small-en-us-0.15` folder in the project.
Choose the folder itself, which contains `am/final.mdl`.

Start with **3 seconds**, **48000 Hz**, **Stereo**, **Beep**, **1000 Hz**, **20%**,
and **150 ms** of padding before and after. The beep volume controls only the
replacement tone, not the overall microphone or speaker volume.

## 3. Set your blocked words

The default list is already populated. Add one single word per line. For a harmless
demonstration, append `banana`, keeping the default list. Matching ignores case
and punctuation. Multiword phrases, contextual brand rules and arbitrary word
variations are not supported. **Save settings** remembers your choices; settings
are locked during protection, so click Stop before changing them.

## 4. Try protection

1. Click **Start protection** and wait for the local model to load and the buffer
   to warm up.
2. Say a short clean sentence, then pause for a few seconds. Listen to the delayed
   output.
3. Say “I said banana today,” then pause. Check the event table and output.
4. A yellow notice appears for ten seconds when a blocked word is recognized.
   It masks the word and reminds you to avoid repeating it. The event remains
   in the table after the notice disappears.
5. Click **Stop**, change Replacement to **Silence**, then repeat the test.
6. Remove `banana` after testing and save your normal word list.

### Replay the whole session

**Record protected output from Start to Stop** is enabled initially. After Stop,
click **Play recording** to hear the complete saved session through your Windows
default audio output. Click **Stop replay** to stop playback. **Open recordings**
opens the folder so you can choose older sessions or play a WAV in another player.
Recording preference is included in Save settings.

The WAV contains the audio StreamGuard sent to the output: clean speech, replacement
beeps, startup silence and protective muting. It begins when the audio device starts,
after model loading, and ends when you stop. Stop discards queued delayed audio;
pause for at least the selected delay before stopping to hear the end of your sentence.
This checks StreamGuard's output, not the later OBS recording or physical speaker sound.
Recording errors are reported as incomplete and do not interrupt live filtering.
Playback is disabled while protection runs so it cannot feed back into the microphone.
Recordings stay locally under `%LOCALAPPDATA%/StreamGuard/recordings` until you delete
them; they are not uploaded or automatically deleted. Disable the checkbox if you
do not want to save a session. Earlier unrecorded sessions cannot be recovered.

The notice reports detection and scheduled censorship, not independently verified
playback. Late recognition reports protective muting. The notice is inside the
StreamGuard window; it does not notify a phone/watch or overlay other applications.
Keep the app visible on a second monitor if you need to see it while streaming.

## 5. Understand every control

| Control | Purpose |
| --- | --- |
| Microphone | Physical audio source to filter. |
| Output to OBS | Delayed destination; speakers for testing, CABLE Input for OBS. |
| Refresh devices | Re-enumerate endpoints after plugging in hardware. Reselect devices. |
| Local model / Browse | Extracted offline English recognition model folder. |
| Detector | Current implementation uses Vosk locally. |
| Audience delay | 0.5–3 seconds; longer gives recognition more time. |
| Sample rate | Must be supported by both selected devices; begin at 48 kHz. |
| Output channels | Mono or stereo duplication of the microphone. |
| Replacement | Beep tone or silence over detected word intervals. |
| Beep frequency / volume | Tone pitch and level. |
| Padding before / after | Extra coverage around word timestamps; more can remove nearby speech. |
| Blocked words | Single words, one per line. |
| Start protection / Stop | Open or close the audio path. Stop aborts queued playback. |
| Save settings | Persist devices, model and censorship options. |

## 6. Read status, metrics and events

- **STOPPED / NOT STARTED:** no protection is running; read the bottom message.
- **LOADING / WARMING:** model or delay buffer is preparing.
- **FILTERING:** pipeline is active; this does not guarantee recognition accuracy.
- **AT RISK / MUTED:** recognition has not safely covered audio before its deadline.
  That audio is silenced. Long sentences can lose surrounding clean speech too.
- **ERROR / fault:** output stops or mutes; read the error, correct the cause, then restart.

Detected counts recognized violations. Muted seconds include protective silence,
so they are not a count of profane speech. Queue describes pending work. Headroom
and detection p99 help spot recognition delays; they are not accuracy scores.
The event table shows time, masked term, confidence and timing. Recognized blocked
words are censored even at low confidence. Only the most recent 100 rows are shown.

## 7. Connect OBS

VB-CABLE endpoints are currently absent on this computer. OBS use requires its
driver installation and possibly a Windows restart. The prepared installer is in
`setup/VB-CABLE`; installation is an explicit administrator action.

After installation:

1. In StreamGuard, choose the Anker microphone and **CABLE Input** playback.
2. In OBS Settings → Audio, disable raw global Mic/Aux inputs. Remove or disable
   raw mic sources in every scene, including nested scenes.
3. Add an **Audio Input Capture** source and select **CABLE Output**.
4. Leave OBS monitoring for that source **Off**. Avoid capturing the same audio
   again through desktop audio. Use direct hardware monitoring for your own voice.
5. Start protection and make a **local recording**. Play it back and check clean
   speech, blocked words, rapid repetitions and noisy speech.
6. Match video delay to the audio using an OBS video delay/filter, then verify
   synchronization with a clap recording. Buffer settings alone are not a measurement.

See [OBS setup](OBS_SETUP.md) for the acceptance checklist. Do not rely on this
prototype for a sponsored live broadcast until the complete recording path is tested.

## 8. Troubleshoot

If Start fails, select both devices, verify the model folder, and read the bottom
message. If a device is unplugged, Stop, reconnect, Refresh devices, reselect and
restart. If speech disappears, try 3 seconds and short sentences with pauses:
Vosk final recognition can still arrive too late. Reducing delay can increase
protective muting. If a word is missed, verify the list and test your voice;
recognition mistakes remain possible. If feedback occurs, Stop and use headphones
or lower the physical speaker volume.

## 9. Privacy and additional tools

Inference runs locally without an API key or audio upload. With the recording checkbox
enabled, the protected output is saved locally. Raw microphone input is not recorded.
Settings and rotating event logs live under
`%LOCALAPPDATA%/StreamGuard`; event terms are masked. Explicit testing tools can
create recordings, and command-line detection can print full terms.

Developer commands also enumerate devices, check OBS routing, detect without
playback, and censor PCM16 WAV files offline. See [README](../README.md#commands)
for syntax. The old `diagnose` command is uncensored and should never feed OBS.

This MVP supports word filtering and local on-screen notices. It does not yet
support phone/watch push alerts, brand context, custom phrases or guaranteed
prevention of every violation. [Testing results](TESTING.md) describe what has
actually been verified.
