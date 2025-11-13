import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

try:
    from pynput import keyboard, mouse
except Exception as e:  # pragma: no cover - import-time only
    keyboard = None  # type: ignore
    mouse = None  # type: ignore


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

        self._kb_listener = None
        self._ms_listener = None

    def start(self) -> None:
        if keyboard is None or mouse is None:
            raise RuntimeError("pynput is not available. Please install pynput.")
        self._start_epoch = time.time()
        self._start_mono = time.perf_counter()

        self._kb_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._kb_listener.start()

        self._ms_listener = mouse.Listener(
            on_move=self._on_mouse_move,
            on_click=self._on_mouse_click,
            on_scroll=self._on_mouse_scroll,
        )
        self._ms_listener.start()

    def stop(self) -> None:
        if self._kb_listener:
            self._kb_listener.stop()
        if self._ms_listener:
            self._ms_listener.stop()

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
    def _on_key_press(self, key) -> None:
        epoch, t_rel = self._now()
        try:
            key_name = key.char  # type: ignore[attr-defined]
        except Exception:
            key_name = str(key)
        self._append(
            {
                "timestamp": epoch,
                "t_rel": t_rel,
                "type": "key_press",
                "key": key_name,
            }
        )

    def _on_key_release(self, key) -> None:
        epoch, t_rel = self._now()
        try:
            key_name = key.char  # type: ignore[attr-defined]
        except Exception:
            key_name = str(key)
        self._append(
            {
                "timestamp": epoch,
                "t_rel": t_rel,
                "type": "key_release",
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

    def _on_mouse_move(self, x: int, y: int) -> None:
        epoch, t_rel = self._now()
        xn, yn = self._normalize(x, y)
        # To avoid flooding, sample moves at ~20Hz using time-based throttle
        # Basic approach: keep only every 50 ms move
        # We'll implement a simple last time check
        now_ms = int(t_rel * 1000)
        # Use integer modulus: record around every 50ms window boundary
        if now_ms % 50 < 5:
            self._append(
                {
                    "timestamp": epoch,
                    "t_rel": t_rel,
                    "type": "mouse_move",
                    "pos_x_norm": xn,
                    "pos_y_norm": yn,
                }
            )

    def _on_mouse_click(self, x: int, y: int, button, pressed: bool) -> None:
        epoch, t_rel = self._now()
        xn, yn = self._normalize(x, y)
        self._append(
            {
                "timestamp": epoch,
                "t_rel": t_rel,
                "type": "mouse_click",
                "event": "press" if pressed else "release",
                "pos_x_norm": xn,
                "pos_y_norm": yn,
                "button": str(button),
            }
        )

    def _on_mouse_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        epoch, t_rel = self._now()
        xn, yn = self._normalize(x, y)
        self._append(
            {
                "timestamp": epoch,
                "t_rel": t_rel,
                "type": "mouse_scroll",
                "pos_x_norm": xn,
                "pos_y_norm": yn,
                "scroll_dx": dx,
                "scroll_dy": dy,
            }
        )

    def snapshot(self) -> List[dict]:
        with self._lock:
            return list(self._events)

