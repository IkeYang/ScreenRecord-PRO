import threading
import time
from typing import Dict, Optional

import cv2
import numpy as np

try:
    import mss
except Exception as e:  # pragma: no cover - import-time only
    mss = None  # type: ignore


class ScreenCapture:
    """
    Capture a selected monitor region using mss and encode video via OpenCV.

    - monitor: a dict from mss with keys left, top, width, height
    - fps: target frames per second
    - fourcc: codec for OpenCV writer (default mp4v)
    """

    def __init__(
        self,
        monitor: Dict[str, int],
        output_path: str,
        fps: int = 10,
        fourcc: str = "XVID",
    ) -> None:
        self.monitor = monitor
        self.output_path = output_path
        self.fps = fps
        self.fourcc = fourcc

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._writer: Optional[cv2.VideoWriter] = None

    def start(self) -> None:
        if mss is None:
            raise RuntimeError("mss is not available. Please install mss.")

        width = int(self.monitor["width"])  # type: ignore[index]
        height = int(self.monitor["height"])  # type: ignore[index]

        fourcc = cv2.VideoWriter_fourcc(*self.fourcc)
        self._writer = cv2.VideoWriter(self.output_path, fourcc, self.fps, (width, height))
        if not self._writer.isOpened():
            # Try a fallback codec for AVI if initial fourcc failed
            fallback = cv2.VideoWriter_fourcc(*"MJPG")
            self._writer = cv2.VideoWriter(self.output_path, fallback, self.fps, (width, height))
            if not self._writer.isOpened():
                raise RuntimeError(f"Failed to open VideoWriter for {self.output_path}")

        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="ScreenCaptureThread", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        if self._writer is not None:
            self._writer.release()

    def _run(self) -> None:
        assert self._writer is not None
        frame_period = 1.0 / float(self.fps)
        with mss.mss() as sct:  # type: ignore[attr-defined]
            # mss expects a dict with keys: left, top, width, height
            region = {
                "left": int(self.monitor["left"]),
                "top": int(self.monitor["top"]),
                "width": int(self.monitor["width"]),
                "height": int(self.monitor["height"]),
            }
            next_time = time.perf_counter()
            while not self._stop.is_set():
                frame = np.array(sct.grab(region))  # BGRA
                # Convert BGRA -> BGR for OpenCV
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                self._writer.write(frame_bgr)

                next_time += frame_period
                delay = next_time - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)

    @staticmethod
    def list_monitors() -> "list[Dict[str, int]]":
        """Return list of monitor dicts (left, top, width, height). Index 1..N like mss."""
        if mss is None:
            raise RuntimeError("mss is not available. Please install mss.")
        with mss.mss() as sct:  # type: ignore[attr-defined]
            # sct.monitors[0] is the virtual screen (all monitors). We only return 1..N
            return [m for i, m in enumerate(sct.monitors) if i != 0]
