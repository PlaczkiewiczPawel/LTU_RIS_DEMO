"""Editable TX settings. Restart the transmitter after changing this file."""

# Radio (same defaults as defaultConfig.m)
TX_IP = "192.168.10.2"
MASTER_CLOCK_RATE = 100e6
CENTER_FREQUENCY = 5.53e9
SAMPLE_RATE = 1e6
TX_GAIN = 2.0
CLOCK_SOURCE = "internal"  # Requires a connected 10 MHz reference.
CONNECTION_ATTEMPTS = 10
CONNECTION_RETRY_INTERVAL_SECONDS = 1.0
SEND_TIMEOUT_SECONDS = 1.0

# OFDM: carrier positions use MATLAB's one-based numbering.
FFT_LENGTH = 128
CYCLIC_PREFIX_LENGTH = 32
NUM_USED_SUBCARRIERS = 50
NUM_SYMBOLS = 20
NUM_FRAMES = 20000
PILOT_POSITIONS = [1, 6, 11, 16, 21, 30, 35, 40, 45, 50]
FRAME_POSITIONS = [2, 5, 10, 15, 20, 31, 36, 41, 46, 49]
SYMBOL_POSITIONS = [7, 12, 17, 22, 29, 34, 39, 44]
PILOT_SYMBOL = 1.0 + 1.0j

# Transmission
AMPLITUDE_SCALE = 0.25
REPORT_UNDERRUNS = True
FRAMES_PER_SEND = 32  # Batch consecutive frames to reduce Python/UHD overhead.
