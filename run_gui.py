import os

# Avoid Qt picking up OpenCV's bundled plugin path
os.environ.pop("QT_PLUGIN_PATH", None)
os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)

from gui.app import run

if __name__ == "__main__":
    raise SystemExit(run())
