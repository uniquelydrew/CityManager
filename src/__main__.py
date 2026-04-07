"""Module entry point for running the town recovery GUI."""

import os
import sys


if __package__ in (None, ""):
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.ui.main_window import launch_gui
else:
    from .ui.main_window import launch_gui


if __name__ == "__main__":
    raise SystemExit(launch_gui())
