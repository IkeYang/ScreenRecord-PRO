import argparse
import json
import os
from dataclasses import asdict
from datetime import datetime
from typing import Dict

from .events import EventRecorder, MonitorGeom
from .video import ScreenCapture


def _ensure_dir(path: str) -> None:
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def _timestamp_name() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def list_screens() -> None:
    from .video import ScreenCapture

    monitors = ScreenCapture.list_monitors()
    if not monitors:
        print("No monitors detected.")
        return
    for idx, mon in enumerate(monitors, start=1):
        print(
            f"{idx}: {mon['width']}x{mon['height']}  left={mon['left']} top={mon['top']}"
        )


def run_record(
    screen_index: int,
    outdir: str,
    duration: float | None,
    fps: int = 25,
) -> tuple[str, str]:
    # Prepare paths
    _ensure_dir(outdir)
    base = _timestamp_name()
    video_path = os.path.join(outdir, f"{base}.avi")
    json_path = os.path.join(outdir, f"{base}.json")

    # Resolve monitor
    monitors = ScreenCapture.list_monitors()
    if screen_index < 1 or screen_index > len(monitors):
        raise SystemExit(f"Invalid screen index: {screen_index}. Use --list to view.")
    mon: Dict[str, int] = monitors[screen_index - 1]
    geom = MonitorGeom(
        left=int(mon["left"]),
        top=int(mon["top"]),
        width=int(mon["width"]),
        height=int(mon["height"]),
    )

    # Start recorders
    cap = ScreenCapture(mon, video_path, fps=fps)
    ev = EventRecorder(geom)

    cap.start()
    ev.start()

    print("Recording... Press Ctrl+C to stop.")
    print(f"Video: {video_path}")
    print(f"Events: {json_path}")

    try:
        if duration is not None and duration > 0:
            import time

            time.sleep(duration)
        else:
            # wait forever until interrupted
            import signal
            import threading

            stop = threading.Event()

            def _handler(signum, frame):  # type: ignore[no-redef]
                stop.set()

            signal.signal(signal.SIGINT, _handler)
            signal.signal(signal.SIGTERM, _handler)
            stop.wait()
    finally:
        cap.stop()
        ev.stop()

    # Save events JSON with meta
    data = {
        "meta": {
            "screen": asdict(geom),
            "fps": fps,
            "started_at": base,
        },
        "events": ev.snapshot(),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Saved.")
    return video_path, json_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="screenrec",
        description="Record a single monitor's screen to AVI and keyboard/mouse events to JSON.",
    )
    p.add_argument("--list", action="store_true", help="List available screens and exit.")
    p.add_argument("--screen", type=int, default=1, help="Screen index to record (1-based)")
    p.add_argument("--outdir", type=str, default="output", help="Directory to save files")
    p.add_argument("--duration", type=float, default=None, help="Seconds to record (optional)")
    p.add_argument("--fps", type=int, default=25, help="Frames per second for video")

    args = p.parse_args(argv)
    if args.list:
        list_screens()
        return 0

    try:
        run_record(args.screen, args.outdir, args.duration, fps=args.fps)
    except KeyboardInterrupt:
        # Graceful exit already handled in run_record
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
