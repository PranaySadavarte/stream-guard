import argparse
import json
import sys
import time
from .config import AudioSettings
from .audio.duplex import AudioDiagnostic


def main(argv=None):
    parser = argparse.ArgumentParser(description="StreamGuard audio-plumbing diagnostic (NO CENSORSHIP)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("devices", help="list input/output device IDs")
    live = commands.add_parser('live', help='delayed, fail-closed local profanity filter')
    live.add_argument('--input', type=int, required=True)
    live.add_argument('--output', type=int, required=True)
    live.add_argument('--model', required=True)
    live.add_argument('--delay-ms', type=float, default=1500)
    live.add_argument('--sample-rate', type=int, default=48000)
    live.add_argument('--output-channels', type=int, choices=[1,2], default=2)
    live.add_argument('--mode', choices=['beep','silence'], default='beep')
    live.add_argument('--terms')
    live.add_argument('--seconds', type=int, default=60)
    observe = commands.add_parser('detect', help='live local recognition; no audio output')
    observe.add_argument('--input', type=int, required=True)
    observe.add_argument('--model', required=True)
    observe.add_argument('--seconds', type=int, default=15)
    offline = commands.add_parser('censor-file', help='replace prohibited word samples in a PCM16 WAV')
    offline.add_argument('source')
    offline.add_argument('destination')
    evidence = offline.add_mutually_exclusive_group(required=True)
    evidence.add_argument('--words-json', help='annotated Word records (text/start/end/confidence)')
    evidence.add_argument('--model', help='local Vosk model directory')
    offline.add_argument('--mode', choices=['beep', 'silence'], default='beep')
    offline.add_argument('--terms', help='UTF-8 file, one word per line')
    run = commands.add_parser("diagnose", help="unprotected delayed monitoring; keep OBS closed")
    run.add_argument("--input", type=int, required=True)
    run.add_argument("--output", type=int, required=True)
    run.add_argument("--delay-ms", type=float, default=1500)
    run.add_argument("--sample-rate", type=int, default=48000)
    run.add_argument("--block-ms", type=int, default=20)
    run.add_argument("--output-channels", type=int, choices=(1, 2), default=1)
    run.add_argument("--seconds", type=int, default=30)
    run.add_argument("--monitor-gain", type=float, default=0.1,
                     help="diagnostic output gain 0–1 (default 0.1)")
    run.add_argument("--allow-unprotected-monitor", action="store_true",
                     help="acknowledge that diagnostic audio is uncensored")
    args = parser.parse_args(argv)
    if args.command == 'live':
        from pathlib import Path
        from .pipeline.controller import LiveController
        from .audio.censor import CensorSettings
        from .detection.profanity import ProfanityDictionary
        from .detection.vosk_backend import VoskDetector
        if args.seconds <= 0: parser.error('seconds must be positive')
        dictionary = ProfanityDictionary(Path(args.terms).read_text(encoding='utf-8').splitlines()) if args.terms else ProfanityDictionary()
        settings = AudioSettings(args.input,args.output, sample_rate=args.sample_rate,
                                 delay_ms=args.delay_ms,output_channels=args.output_channels)
        controller = LiveController(settings,VoskDetector(args.model),dictionary,CensorSettings(mode=args.mode))
        try:
            controller.start()
            deadline = time.monotonic()+args.seconds
            while time.monotonic() < deadline:
                time.sleep(.25)
                status = controller.snapshot()
                print(json.dumps(status), flush=True)
                if status['error']: return 1
            return 0
        except KeyboardInterrupt:
            return 130
        finally:
            controller.close()
    if args.command == 'detect':
        from .detection.observe import observe
        from .detection.vosk_backend import VoskDetector
        if args.seconds <= 0: parser.error('seconds must be positive')
        observe(VoskDetector(args.model), args.input, seconds=args.seconds)
        return 0
    if args.command == 'censor-file':
        from pathlib import Path
        from .offline import censor_file, load_words
        from .audio.censor import CensorSettings
        from .detection.profanity import ProfanityDictionary
        try:
            detector = None
            if args.model:
                from .detection.vosk_backend import VoskDetector
                detector = VoskDetector(args.model)
            terms = ProfanityDictionary(Path(args.terms).read_text(encoding='utf-8').splitlines()) if args.terms else None
            spans = censor_file(args.source, args.destination, terms, CensorSettings(mode=args.mode),
                                load_words(args.words_json) if args.words_json else None, detector)
            print(json.dumps({'output': args.destination, 'detections': len(spans)}))
            return 0
        except (ValueError, OSError, RuntimeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
    import sounddevice as sd
    if args.command == "devices":
        print(sd.query_devices())
        return 0
    if not args.allow_unprotected_monitor:
        parser.error("diagnostic requires --allow-unprotected-monitor; keep OBS closed and use headphones")
    if args.seconds <= 0:
        parser.error("--seconds must be positive")
    diagnostic = None
    try:
        settings = AudioSettings(args.input, args.output, args.sample_rate,
                                 args.block_ms, args.delay_ms, args.output_channels)
        output = sd.query_devices(args.output)
        # Milestone 1 must not be used as an uncensored OBS feed.
        if any(token in output["name"].casefold() for token in ("cable", "virtual", "voicemeeter")):
            raise ValueError("virtual outputs are disabled in the unprotected diagnostic")
        print("PROTECTION OFF. Uncensored diagnostic audio. Keep OBS closed.", file=sys.stderr)
        diagnostic = AudioDiagnostic(settings, args.monitor_gain)
        diagnostic.start()
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            time.sleep(min(0.25, max(0, deadline - time.monotonic())))
            print(json.dumps(diagnostic.snapshot()), flush=True)
            if diagnostic.failed or not diagnostic.stream.active:
                raise RuntimeError("audio discontinuity/device failure; output muted; restart diagnostic")
        return 0
    except KeyboardInterrupt:
        return 130
    except (ValueError, RuntimeError, sd.PortAudioError) as exc:
        print(f"StreamGuard stopped: {exc}", file=sys.stderr)
        return 1
    finally:
        if diagnostic is not None:
            diagnostic.close()


if __name__ == "__main__":
    raise SystemExit(main())
