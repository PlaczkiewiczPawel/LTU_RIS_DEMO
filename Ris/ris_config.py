"""Editable RIS settings. Restart the application after changing this file."""

from pathlib import Path

RIS_DIRECTORY = Path(__file__).resolve().parent

# Serial connection
RIS_PORT = "COM3"
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

# Dark GUI theme (hex RGB colors). Restart the application after editing.
GUI_COLORS = {
    "background": "#0B1120",
    "surface": "#111C2F",
    "button": "#1B2B43",
    "button_hover": "#293F5D",
    "field": "#0D1728",
    "border": "#30415B",
    "text": "#E6EDF7",
    "muted_text": "#9AAEC7",
    "disabled_text": "#65758B",
    "accent": "#36CDBB",
    "accent_hover": "#56E1D0",
    "accent_pressed": "#24AF9E",
    "accent_text": "#06201E",
    "slider": "#36CDBB",
    "slider_hover": "#70F0DC",
    "slider_track": "#415B78",
    "pattern_zero": "#FFFFFF",
    "pattern_one": "#22C55E",
}
