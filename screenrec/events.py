import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

try:
    import keyboard  # type: ignore[import]
except Exception:  # pragma: no cover - import-time only
    keyboard = None  # type: ignore[assignment]

try:
    import mouse  # type: ignore[import]
except Exception:  # pragma: no cover - import-time only
    mouse = None  # type: ignore[assignment]


@dataclass
class MonitorGeom:
    left: int
    top: int
    width: int
    height: int


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


class EventRecorder:
    """
    Record keyboard and mouse events with high-precision timestamps.
    Mouse positions are normalized relative to the selected monitor geometry.
    """

    def __init__(self, monitor: MonitorGeom) -> None:
        self.monitor = monitor
        self._lock = threading.Lock()
        self._events: List[dict] = []
        self._start_epoch: Optional[float] = None
        self._start_mono: Optional[float] = None

        self._kb_hook = None
        self._ms_hook = None
        self._last_move_sample_ms: Optional[int] = None

    def start(self) -> None:
        if keyboard is None or mouse is None:
            raise RuntimeError(
                "keyboard/mouse packages are not available. Please install 'keyboard' and 'mouse'."
            )
        self._start_epoch = time.time()
        self._start_mono = time.perf_counter()

        # Global hooks provided by keyboard/mouse
        self._kb_hook = self._on_keyboard_event
        keyboard.hook(self._kb_hook)

        self._ms_hook = self._on_mouse_event
        mouse.hook(self._ms_hook)

    def stop(self) -> None:
        # Unhook global listeners
        if self._kb_hook is not None and keyboard is not None:
            try:
                keyboard.unhook(self._kb_hook)
            except Exception:
                pass
            self._kb_hook = None
        if self._ms_hook is not None and mouse is not None:
            try:
                mouse.unhook(self._ms_hook)
            except Exception:
                pass
            self._ms_hook = None

    # Event helpers
    def _now(self) -> tuple[float, float]:
        assert self._start_epoch is not None
        assert self._start_mono is not None
        epoch = time.time()
        t_rel = time.perf_counter() - self._start_mono
        return epoch, t_rel

    def _append(self, obj: dict) -> None:
        with self._lock:
            self._events.append(obj)

    # Keyboard
    def _on_keyboard_event(self, event) -> None:
        # keyboard library sends "down" / "up" events with .name
        if self._start_mono is None:
            return
        epoch, t_rel = self._now()
        event_type = getattr(event, "event_type", "")
        if event_type == "down":
            type_name = "key_press"
        elif event_type == "up":
            type_name = "key_release"
        else:
            return
        key_name = getattr(event, "name", None) or str(event)
        self._append(
            {
                "timestamp": epoch,
                "t_rel": t_rel,
                "type": type_name,
                "key": key_name,
            }
        )

    # Mouse helpers
    def _normalize(self, x_abs: int, y_abs: int) -> tuple[float, float]:
        # Translate global coords to monitor-local then normalize
        mx = x_abs - self.monitor.left
        my = y_abs - self.monitor.top
        if self.monitor.width <= 0 or self.monitor.height <= 0:
            return 0.0, 0.0
        xn = _clamp01(mx / float(self.monitor.width))
        yn = _clamp01(my / float(self.monitor.height))
        return xn, yn

    def _on_mouse_event(self, event) -> None:
        # mouse library sends MoveEvent / ButtonEvent / WheelEvent
        if self._start_mono is None or mouse is None:
            return
        epoch, t_rel = self._now()

        # Import types from the mouse module for isinstance checks
        MoveEvent = getattr(mouse, "MoveEvent", None)
        ButtonEvent = getattr(mouse, "ButtonEvent", None)
        WheelEvent = getattr(mouse, "WheelEvent", None)

        if MoveEvent is not None and isinstance(event, MoveEvent):
            x = int(getattr(event, "x", 0))
            y = int(getattr(event, "y", 0))
            xn, yn = self._normalize(x, y)
            now_ms = int(t_rel * 1000)
            # Sample moves at ~20Hz to avoid flooding
            if self._last_move_sample_ms is None or now_ms - self._last_move_sample_ms >= 50:
                self._last_move_sample_ms = now_ms
                self._append(
                    {
                        "timestamp": epoch,
                        "t_rel": t_rel,
                        "type": "mouse_move",
                        "pos_x_norm": xn,
                        "pos_y_norm": yn,
                    }
                )
        elif ButtonEvent is not None and isinstance(event, ButtonEvent):
            x = int(getattr(event, "x", 0))
            y = int(getattr(event, "y", 0))
            xn, yn = self._normalize(x, y)
            button = str(getattr(event, "button", ""))
            ev_type = getattr(event, "event_type", "")
            pressed = ev_type == "down"
            self._append(
                {
                    "timestamp": epoch,
                    "t_rel": t_rel,
                    "type": "mouse_click",
                    "event": "press" if pressed else "release",
                    "pos_x_norm": xn,
                    "pos_y_norm": yn,
                    "button": button,
                }
            )
        elif WheelEvent is not None and isinstance(event, WheelEvent):
            x = int(getattr(event, "x", 0))
            y = int(getattr(event, "y", 0))
            xn, yn = self._normalize(x, y)
            dy = int(getattr(event, "delta", 0))
            self._append(
                {
                    "timestamp": epoch,
                    "t_rel": t_rel,
                    "type": "mouse_scroll",
                    "pos_x_norm": xn,
                    "pos_y_norm": yn,
                    "scroll_dx": 0,
                    "scroll_dy": dy,
                }
            )

    def snapshot(self) -> List[dict]:
        with self._lock:
            return list(self._events)
