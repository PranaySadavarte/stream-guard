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
