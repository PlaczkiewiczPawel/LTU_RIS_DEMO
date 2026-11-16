"""Continuously transmit the MATLAB-compatible OFDM waveform through UHD."""

from __future__ import annotations

import signal
import threading

import numpy as np

import tx_config as cfg


CONSTELLATION = np.array([1 + 1j, 1 - 1j, -1 + 1j, -1 - 1j]) / np.sqrt(2)


def validate_config() -> None:
    for name in ("FFT_LENGTH", "CYCLIC_PREFIX_LENGTH", "NUM_USED_SUBCARRIERS",
                 "NUM_SYMBOLS", "NUM_FRAMES", "FRAMES_PER_SEND", "CONNECTION_ATTEMPTS"):
        value = getattr(cfg, name)
        if not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if cfg.FFT_LENGTH % 2 or cfg.NUM_USED_SUBCARRIERS % 2:
        raise ValueError("FFT_LENGTH and NUM_USED_SUBCARRIERS must be even")
    if not cfg.NUM_USED_SUBCARRIERS < cfg.FFT_LENGTH:
        raise ValueError("Occupied carriers must leave room for DC")
    if not cfg.CYCLIC_PREFIX_LENGTH < cfg.FFT_LENGTH:
        raise ValueError("The cyclic prefix must be shorter than the FFT")
    positions = cfg.PILOT_POSITIONS + cfg.FRAME_POSITIONS + cfg.SYMBOL_POSITIONS
    if (any(not isinstance(p, int) or not 1 <= p <= cfg.NUM_USED_SUBCARRIERS
            for p in positions) or len(set(positions)) != len(positions)):
        raise ValueError("Carrier positions must be valid, disjoint one-based indices")
    if cfg.NUM_FRAMES > 4 ** len(cfg.FRAME_POSITIONS):
        raise ValueError("Frame numbers do not fit in FRAME_POSITIONS")
    if cfg.NUM_SYMBOLS >= 4 ** len(cfg.SYMBOL_POSITIONS):
        raise ValueError("One-based symbol numbers do not fit in SYMBOL_POSITIONS")
    if not np.isfinite(cfg.PILOT_SYMBOL) or cfg.PILOT_SYMBOL == 0:
        raise ValueError("PILOT_SYMBOL must be finite and nonzero")
    if not 0 < cfg.AMPLITUDE_SCALE <= 1:
        raise ValueError("AMPLITUDE_SCALE must be in (0, 1]")
    for value in (cfg.SAMPLE_RATE, cfg.MASTER_CLOCK_RATE, cfg.SEND_TIMEOUT_SECONDS):
        if not np.isfinite(value) or value <= 0:
            raise ValueError("Clock rate, sample rate and send timeout must be positive")
    factor = cfg.MASTER_CLOCK_RATE / cfg.SAMPLE_RATE
    if factor < 1 or not factor.is_integer():
        raise ValueError("MASTER_CLOCK_RATE / SAMPLE_RATE must be a positive integer")
    if cfg.CLOCK_SOURCE not in ("external", "internal"):
        raise ValueError("CLOCK_SOURCE must be external or internal")


def encode_numbers(numbers, width: int) -> np.ndarray:
    """Return base-four digits, most significant first (MATLAB de2bi left-msb)."""
    numbers = np.asarray(numbers, dtype=np.int64).reshape(1, -1)
    divisors = 4 ** np.arange(width - 1, -1, -1, dtype=np.int64)
    return (numbers // divisors[:, None]) % 4


def build_transmit_frame(frame_number: int, rng=None) -> np.ndarray:
    """Build one unscaled frame; serialize each OFDM symbol column first."""
    if not isinstance(frame_number, (int, np.integer)) or not 0 <= frame_number < cfg.NUM_FRAMES:
        raise ValueError("frame_number must be an integer in [0, NUM_FRAMES)")
    if rng is None:
        rng = np.random.default_rng()
    data = CONSTELLATION[rng.integers(0, 4, (cfg.NUM_USED_SUBCARRIERS, cfg.NUM_SYMBOLS))]
    data[np.asarray(cfg.PILOT_POSITIONS, dtype=int) - 1] = cfg.PILOT_SYMBOL
    data[np.asarray(cfg.FRAME_POSITIONS, dtype=int) - 1] = CONSTELLATION[
        encode_numbers([frame_number], len(cfg.FRAME_POSITIONS))]
    data[np.asarray(cfg.SYMBOL_POSITIONS, dtype=int) - 1] = CONSTELLATION[
        encode_numbers(np.arange(1, cfg.NUM_SYMBOLS + 1), len(cfg.SYMBOL_POSITIONS))]
    grid = np.zeros((cfg.FFT_LENGTH, cfg.NUM_SYMBOLS), dtype=np.complex128)
    half = cfg.NUM_USED_SUBCARRIERS // 2
    grid[1:half + 1] = data[half:]
    grid[-half:] = data[:half]
    useful = np.fft.ifft(grid, axis=0) * np.sqrt(cfg.NUM_USED_SUBCARRIERS)
    return np.concatenate((useful[-cfg.CYCLIC_PREFIX_LENGTH:], useful)).ravel(order="F")


def configure_transmitter(uhd, stop_event):
    for attempt in range(1, cfg.CONNECTION_ATTEMPTS + 1):
        try:
            usrp = uhd.usrp.MultiUSRP(f"addr={cfg.TX_IP}")
            break
        except RuntimeError:
            if attempt == cfg.CONNECTION_ATTEMPTS:
                raise
            print(f"USRP {cfg.TX_IP} unavailable ({attempt}/{cfg.CONNECTION_ATTEMPTS}); retrying.")
            if stop_event.wait(cfg.CONNECTION_RETRY_INTERVAL_SECONDS):
                raise KeyboardInterrupt
    usrp.set_clock_source(cfg.CLOCK_SOURCE)
    # N200/N210 has a fixed 100 MHz master clock; set_tx_rate selects interpolation.
    if not np.isclose(usrp.get_master_clock_rate(), cfg.MASTER_CLOCK_RATE):
        raise RuntimeError("USRP master clock does not match MASTER_CLOCK_RATE")
    usrp.set_tx_rate(cfg.SAMPLE_RATE, 0)
    if not np.isclose(usrp.get_tx_rate(0), cfg.SAMPLE_RATE):
        raise RuntimeError("USRP cannot provide the configured SAMPLE_RATE")
    usrp.set_tx_freq(uhd.types.TuneRequest(cfg.CENTER_FREQUENCY), 0)
    usrp.set_tx_gain(cfg.TX_GAIN, 0)
    args = uhd.usrp.StreamArgs("fc32", "sc16")
    args.channels = [0]
    return usrp, usrp.get_tx_stream(args)


def send_samples(streamer, samples, metadata, stop_event) -> None:
    offset = 0
    while offset < samples.size and not stop_event.is_set():
        count = streamer.send(samples[None, offset:], metadata, cfg.SEND_TIMEOUT_SECONDS)
        if count <= 0:
            raise RuntimeError("TX send timed out without sending samples")
        offset += count
        metadata.start_of_burst = False


def main() -> None:
    validate_config()
    try:
        import uhd
    except ImportError as exc:
        raise SystemExit("Python UHD bindings are required to transmit.") from exc

    stop_event = threading.Event()
    previous_handlers = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[sig] = signal.signal(sig, lambda *_: stop_event.set())
    usrp = streamer = None
    try:
        usrp, streamer = configure_transmitter(uhd, stop_event)
        metadata = uhd.types.TXMetadata()
        metadata.start_of_burst = True
        metadata.end_of_burst = False
        metadata.has_time_spec = False
        async_metadata = uhd.types.TXAsyncMetadata()
        rng = np.random.default_rng()
        frame_count = 0
        print(f"Transmitting continuously at {cfg.CENTER_FREQUENCY / 1e9:.3f} GHz. "
              "Press Ctrl+C to stop.", flush=True)
        while not stop_event.is_set():
            samples = np.concatenate([
                build_transmit_frame((frame_count + i) % cfg.NUM_FRAMES, rng)
                for i in range(cfg.FRAMES_PER_SEND)
            ])
            samples = np.asarray(cfg.AMPLITUDE_SCALE * samples, dtype=np.complex64)
            send_samples(streamer, samples, metadata, stop_event)
            frame_count += cfg.FRAMES_PER_SEND
            while streamer.recv_async_msg(async_metadata, 0.0):
                if cfg.REPORT_UNDERRUNS:
                    print(f"TX event near frame {frame_count}: {async_metadata.event_code}")
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if streamer is not None:
                end = uhd.types.TXMetadata()
                end.end_of_burst = True
                streamer.send(np.zeros((1, 0), dtype=np.complex64), end,
                              cfg.SEND_TIMEOUT_SECONDS)
        finally:
            streamer = None
            usrp = None
            for sig, handler in previous_handlers.items():
                signal.signal(sig, handler)


if __name__ == "__main__":
    main()
