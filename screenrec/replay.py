import argparse
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

try:
    import keyboard  # type: ignore[import]
except Exception:  # pragma: no cover - import-time only
    keyboard = None  # type: ignore[assignment]

try:
    import mouse  # type: ignore[import]
except Exception:  # pragma: no cover - import-time only
    mouse = None  # type: ignore[assignment]


@dataclass
class ScreenMeta:
    left: int
    top: int
    width: int
    height: int


def _load_events(path: str) -> tuple[ScreenMeta, int, List[Dict[str, Any]]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("meta", {}) or {}
    screen = meta.get("screen", {}) or {}
    fps = int(meta.get("fps", 25))
    geom = ScreenMeta(
        left=int(screen.get("left", 0)),
        top=int(screen.get("top", 0)),
        width=int(screen.get("width", 1920)),
        height=int(screen.get("height", 1080)),
    )
    events = list(data.get("events", []) or [])
    events.sort(key=lambda e: float(e.get("t_rel", 0.0)))
    return geom, fps, events


def _normalize_key_name(name: str) -> str:
    # New recordings already use keyboard's key names; older JSON may contain
    # strings like "Key.space" / "Key.ctrl_l".
    if name.startswith("Key."):
        core = name.split(".", 1)[1]
        mapping = {
            "ctrl_l": "ctrl",
            "ctrl_r": "ctrl",
            "shift_l": "shift",
            "shift_r": "shift",
            "alt_l": "alt",
            "alt_r": "alt",
        }
        return mapping.get(core, core)
    return name


def _normalize_button_name(button: str) -> str:
    # Support legacy values like "Button.left"
    if button.startswith("Button."):
        return button.split(".", 1)[1]
    return button or "left"


def _install_double_esc_hotkey(stop_event: threading.Event) -> Optional[Any]:
    """Register a global "Esc, Esc" hotkey to set stop_event.

    Returns a handle that can be passed to ``keyboard.remove_hotkey``.
    """

    if keyboard is None:
        return None
    try:
        handle = keyboard.add_hotkey("esc, esc", lambda: stop_event.set())
        return handle
    except Exception:
        return None


def _dispatch_event(event: Dict[str, Any], geom: ScreenMeta, dry_run: bool) -> None:
    etype = event.get("type")
    if etype in {"key_press", "key_release"}:
        if keyboard is None:
            return
        name = _normalize_key_name(str(event.get("key", "")))
        if dry_run:
            print(f"[KEY {etype}] {name}")
            return
        if etype == "key_press":
            keyboard.press(name)
        else:
            keyboard.release(name)
    elif etype in {"mouse_move", "mouse_click", "mouse_scroll"}:
        if mouse is None:
            return
        xn = float(event.get("pos_x_norm", 0.0))
        yn = float(event.get("pos_y_norm", 0.0))
        x = int(geom.left + xn * geom.width)
        y = int(geom.top + yn * geom.height)

        if etype == "mouse_move":
            if dry_run:
                print(f"[MOUSE MOVE] ({x}, {y})")
                return
            mouse.move(x, y, absolute=True, duration=0)
        elif etype == "mouse_click":
            button = _normalize_button_name(str(event.get("button", "left")))
            pressed = event.get("event", "press") == "press"
            if dry_run:
                print(f"[MOUSE CLICK] {button} {'DOWN' if pressed else 'UP'} at ({x}, {y})")
                return
            if pressed:
                mouse.press(button=button)
            else:
                mouse.release(button=button)
        elif etype == "mouse_scroll":
            dy = int(event.get("scroll_dy", 0))
            if dry_run:
                print(f"[MOUSE SCROLL] dy={dy} at ({x}, {y})")
                return
            mouse.wheel(dy)


def replay(
    json_path: str,
    speed: float = 1.0,
    dry_run: bool = False,
    start_delay: float = 0.0,
    allow_esc_stop: bool = False,
) -> None:
    if keyboard is None or mouse is None:
        raise SystemExit(
            "keyboard/mouse packages are required for replay. Please install 'keyboard' and 'mouse'."
        )
    if speed <= 0:
        speed = 1.0

    geom, fps, events = _load_events(json_path)
    if not events:
        print("No events to replay.")
        return

    print(
        f"Loaded {len(events)} events from {json_path} (fps={fps}, "
        f"speed={speed}x, delay={start_delay}s)"
    )

    stop_event: Optional[threading.Event] = None
    hotkey_handle: Optional[Any] = None
    if allow_esc_stop:
        stop_event = threading.Event()
        hotkey_handle = _install_double_esc_hotkey(stop_event)

    try:
        if start_delay > 0:
            print(f"Waiting {start_delay} seconds before replay...")
            # 简单延迟，不检查停止标志；如需立即中断可按两次 Esc 后等待开始时刻
            time.sleep(start_delay)

        start = time.perf_counter()
        for ev in events:
            if stop_event is not None and stop_event.is_set():
                print("Replay stopped by ESC ESC.")
                break
            t_rel = float(ev.get("t_rel", 0.0)) / speed
            now = time.perf_counter() - start
            delay = t_rel - now
            if delay > 0:
                # 在 delay 期间也周期性检查是否需要停止
                end = time.perf_counter() + delay
                while time.perf_counter() < end:
                    if stop_event is not None and stop_event.is_set():
                        break
                    time.sleep(0.01)
                if stop_event is not None and stop_event.is_set():
                    print("Replay stopped by ESC ESC.")
                    break
            _dispatch_event(ev, geom, dry_run=dry_run)
    finally:
        if hotkey_handle is not None and keyboard is not None:
            try:
                keyboard.remove_hotkey(hotkey_handle)
            except Exception:
                pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="screenrec-replay",
        description="Replay keyboard/mouse events from a ScreenRec JSON file.",
    )
    parser.add_argument("json_path", type=str, help="Path to the JSON events file to replay.")
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback speed multiplier (>1.0 = faster, <1.0 = slower).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print events instead of sending real keyboard/mouse input.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Delay (seconds) before starting replay.",
    )
    parser.add_argument(
        "--esc-stop",
        action="store_true",
        help="Allow stopping replay by pressing ESC twice quickly.",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        replay(
            args.json_path,
            speed=args.speed,
            dry_run=args.dry_run,
            start_delay=args.delay,
            allow_esc_stop=args.esc_stop,
        )
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
