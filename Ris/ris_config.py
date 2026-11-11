"""Editable RIS settings. Restart the application after changing this file."""

from pathlib import Path


RIS_DIRECTORY = Path(__file__).resolve().parent

# Serial connection
RIS_PORT = "COM4"
RIS_ID = 1
BAUD_RATE = 115200
SERIAL_TIMEOUT_SECONDS = 2.0
PATTERN_SETTLE_TIME_SECONDS = 0.1

# Pattern and polar plot files
SWIPE_PATTERN_FILE = RIS_DIRECTORY / "ris_patterns_16x16_5.24GHz_angles.json"
POLAR_PLOT_DIRECTORY = RIS_DIRECTORY / "plots_polar"

# Default reflection angles [deg]
DEFAULT_MODE_ANGLES = {
    "LEFT": -20.0,
    "BOTH": 55.0,
    "RIGHT": -29.5,
}

# Automatic mode and GUI refresh intervals
DEFAULT_AUTOMATIC_INTERVAL_SECONDS = 1
MINIMUM_AUTOMATIC_INTERVAL_SECONDS = 1
MAXIMUM_AUTOMATIC_INTERVAL_SECONDS = 5
GUI_POLL_INTERVAL_MILLISECONDS = 50

# Main window size (without the optional polar plot panel)
GUI_WINDOW_WIDTH = 760
GUI_WINDOW_HEIGHT = 540
GUI_STATUS_WRAP_LENGTH = 700
