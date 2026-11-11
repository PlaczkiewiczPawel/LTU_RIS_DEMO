"""Continuously receive and display the MATLAB OFDM transmitter constellation."""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np

import rx_config as cfg

try:
    import uhd
except ImportError as exc:
    raise SystemExit(
        "Python UHD bindings are required. Install UHD with Python support first."
    ) from exc


PILOT_POSITIONS = np.asarray(cfg.PILOT_POSITIONS) - 1
FRAME_POSITIONS = np.asarray(cfg.FRAME_POSITIONS) - 1
SYMBOL_POSITIONS = np.asarray(cfg.SYMBOL_POSITIONS) - 1

SYMBOL_LENGTH = cfg.FFT_LENGTH + cfg.CYCLIC_PREFIX_LENGTH
USED_BINS = np.concatenate(
    (
        np.arange(cfg.FFT_LENGTH - cfg.NUM_USED_SUBCARRIERS // 2, cfg.FFT_LENGTH),
        np.arange(1, cfg.NUM_USED_SUBCARRIERS // 2 + 1),
    )
)
FREQUENCY_SHIFTS = np.arange(-cfg.INTEGER_OFFSET_RANGE, cfg.INTEGER_OFFSET_RANGE + 1)
CANDIDATE_BINS = (
    USED_BINS[:, np.newaxis] - FREQUENCY_SHIFTS[np.newaxis, :]
) % cfg.FFT_LENGTH
RESERVED_POSITIONS = np.concatenate(
    (PILOT_POSITIONS, FRAME_POSITIONS, SYMBOL_POSITIONS)
)
DATA_POSITIONS = np.setdiff1d(np.arange(cfg.NUM_USED_SUBCARRIERS), RESERVED_POSITIONS)
QPSK_CONSTELLATION = np.array([1 + 1j, 1 - 1j, -1 + 1j, -1 - 1j]) / np.sqrt(2)


@dataclass(frozen=True)
class ProcessingResult:
    symbols: np.ndarray
    evm: float
    fractional_cfo_hz: float
    integer_offset: int
    synchronized: bool


@dataclass
class ReceiverState:
    channel: np.ndarray | None = None
    fractional_offset: float = 0.0
    integer_offset: int = 0


def channel_interpolation_matrix() -> np.ndarray:
    """Return the same linear interpolation weights as MATLAB interp1."""
    rows = np.arange(cfg.NUM_USED_SUBCARRIERS)
    basis = np.eye(PILOT_POSITIONS.size)
    return np.column_stack(
        [np.interp(rows, PILOT_POSITIONS, basis[:, column]) for column in range(basis.shape[1])]
    )


INTERPOLATION_MATRIX = channel_interpolation_matrix()


def noise_result(samples: np.ndarray, state: ReceiverState) -> ProcessingResult:
    """Display current samples through the last reliable channel estimate."""
    count = samples.size // SYMBOL_LENGTH
    windows = samples[:count * SYMBOL_LENGTH].reshape(count, SYMBOL_LENGTH)
    useful = windows[:, cfg.CYCLIC_PREFIX_LENGTH:].T
    useful = useful * np.exp(
        -1j * state.fractional_offset * np.arange(cfg.FFT_LENGTH)[:, None] / cfg.FFT_LENGTH
    )
    spectrum = np.fft.fft(useful, axis=0) / np.sqrt(cfg.NUM_USED_SUBCARRIERS)
    received = np.roll(spectrum, state.integer_offset, axis=0)[USED_BINS]
    if state.channel is not None:
        received = received / state.channel[:, None]
    return ProcessingResult(
        symbols=received[DATA_POSITIONS],
        evm=float("nan"),
        fractional_cfo_hz=float("nan"),
        integer_offset=state.integer_offset,
        synchronized=False,
    )


def process_received_buffer(
    samples: np.ndarray, state: ReceiverState | None = None
) -> ProcessingResult | None:
    """Synchronize and equalize one independent UHD receive buffer."""
    samples = np.asarray(samples, dtype=np.complex128).reshape(-1)
    if state is None:
        state = ReceiverState()
    if samples.size < 2 * SYMBOL_LENGTH or not np.all(np.isfinite(samples)):
        return None

    correlation = np.zeros(SYMBOL_LENGTH, dtype=np.complex128)
    cp_energy = np.zeros(SYMBOL_LENGTH)
    repeated_energy = np.zeros(SYMBOL_LENGTH)

    for offset in range(SYMBOL_LENGTH):
        starts = np.arange(offset, samples.size - SYMBOL_LENGTH + 1, SYMBOL_LENGTH)
        indices = starts[:, np.newaxis] + np.arange(cfg.CYCLIC_PREFIX_LENGTH)
        prefix = samples[indices]
        repeated = samples[indices + cfg.FFT_LENGTH]
        correlation[offset] = np.sum(np.conj(prefix) * repeated)
        cp_energy[offset] = np.sum(np.abs(prefix) ** 2)
        repeated_energy[offset] = np.sum(np.abs(repeated) ** 2)

    metric = np.abs(correlation) ** 2 / (
        cp_energy * repeated_energy + np.finfo(float).eps
    )
    first_start = int(np.argmax(metric))
    if metric[first_start] < cfg.MINIMUM_TIMING_METRIC:
        return noise_result(samples, state)

    symbol_starts = np.arange(
        first_start, samples.size - SYMBOL_LENGTH + 1, SYMBOL_LENGTH
    )
    sample_indices = np.arange(cfg.FFT_LENGTH)
    useful_indices = (
        symbol_starts[np.newaxis, :]
        + cfg.CYCLIC_PREFIX_LENGTH
        + sample_indices[:, np.newaxis]
    )
    useful = samples[useful_indices]

    fractional_offset = np.angle(correlation[first_start])
    correction = np.exp(-1j * fractional_offset * sample_indices / cfg.FFT_LENGTH)
    useful *= correction[:, np.newaxis]
    fft_output = np.fft.fft(useful, axis=0) / np.sqrt(cfg.NUM_USED_SUBCARRIERS)

    # Occupied-band energy alone can prefer a one-bin error with this waveform.
    # Rank shifts by equalization error on all non-pilot QPSK carriers.
    candidates = fft_output[CANDIDATE_BINS.T, :]
    candidate_pilots = candidates[:, PILOT_POSITIONS, :] / cfg.PILOT_SYMBOL
    candidate_channel = np.einsum(
        "rp,kps->krs", INTERPOLATION_MATRIX, candidate_pilots
    )
    candidate_channel = np.where(
        np.abs(candidate_channel) < cfg.MINIMUM_CHANNEL_MAGNITUDE,
        cfg.MINIMUM_CHANNEL_MAGNITUDE,
        candidate_channel,
    )
    non_pilot_rows = np.setdiff1d(np.arange(cfg.NUM_USED_SUBCARRIERS), PILOT_POSITIONS)
    candidate_data = (candidates / candidate_channel)[:, non_pilot_rows, :]
    candidate_error = np.min(
        np.abs(candidate_data[:, :, :, np.newaxis] - QPSK_CONSTELLATION) ** 2,
        axis=3,
    )
    shift_error = np.mean(candidate_error, axis=(1, 2))
    integer_offset = int(FREQUENCY_SHIFTS[np.argmin(shift_error)])
    corrected_fft = np.roll(fft_output, integer_offset, axis=0)
    received_symbols = corrected_fft[USED_BINS, :]

    pilot_channel = received_symbols[PILOT_POSITIONS, :] / cfg.PILOT_SYMBOL

    # Align the symbol-to-symbol common phase before averaging the channel.
    # This lowers pilot noise while retaining the residual CFO phase per symbol.
    reference = pilot_channel[:, 0]
    common_phase = np.angle(
        np.sum(np.conj(reference[:, np.newaxis]) * pilot_channel, axis=0)
    )
    aligned_pilots = pilot_channel * np.exp(-1j * common_phase[np.newaxis, :])
    mean_pilot_channel = np.mean(aligned_pilots, axis=1)
    common_phase = np.angle(
        np.sum(
            np.conj(mean_pilot_channel[:, np.newaxis]) * pilot_channel,
            axis=0,
        )
    )
    channel_estimate = (INTERPOLATION_MATRIX @ mean_pilot_channel[:, np.newaxis]) * np.exp(
        1j * common_phase[np.newaxis, :]
    )
    weak_channel = np.abs(channel_estimate) < cfg.MINIMUM_CHANNEL_MAGNITUDE
    channel_estimate[weak_channel] = cfg.MINIMUM_CHANNEL_MAGNITUDE * np.exp(
        1j * np.angle(channel_estimate[weak_channel])
    )
    equalized = received_symbols / channel_estimate

    data_symbols = equalized[DATA_POSITIONS, :]
    decision_error = np.min(
        np.abs(data_symbols[:, :, np.newaxis] - QPSK_CONSTELLATION), axis=2
    )
    symbol_evm = np.sqrt(np.mean(decision_error**2, axis=0))
    evm = float(np.sqrt(np.mean(symbol_evm**2)))
    synchronized = np.isfinite(evm) and evm <= cfg.MAXIMUM_TRACKING_EVM
    if synchronized:
        state.channel = channel_estimate[:, -1].copy()
        state.fractional_offset = fractional_offset
        state.integer_offset = integer_offset
    elif state.channel is not None:
        return noise_result(samples, state)

    return ProcessingResult(
        symbols=data_symbols,
        evm=evm,
        fractional_cfo_hz=float(
            fractional_offset * cfg.SAMPLE_RATE / (2 * np.pi * cfg.FFT_LENGTH)
        ),
        integer_offset=integer_offset,
        synchronized=bool(synchronized),
    )


def configure_receiver() -> tuple[uhd.usrp.MultiUSRP, uhd.usrp.RXStreamer]:
    """Connect to the USRP and configure the MATLAB-compatible RX stream."""
    usrp = uhd.usrp.MultiUSRP(f"addr={cfg.RX_IP}")
    usrp.set_clock_source(cfg.CLOCK_SOURCE)
    usrp.set_rx_rate(cfg.SAMPLE_RATE, 0)
    usrp.set_rx_freq(uhd.types.TuneRequest(cfg.CENTER_FREQUENCY), 0)
    usrp.set_rx_gain(cfg.RX_GAIN, 0)
    usrp.set_rx_antenna(cfg.RX_ANTENNA, 0)

    stream_args = uhd.usrp.StreamArgs("fc32", "sc16")
    stream_args.channels = [0]
    return usrp, usrp.get_rx_stream(stream_args)


def start_stream(streamer: uhd.usrp.RXStreamer) -> None:
    command = uhd.types.StreamCMD(uhd.types.StreamMode.start_cont)
    command.stream_now = True
    streamer.issue_stream_cmd(command)


def stop_stream(streamer: uhd.usrp.RXStreamer) -> None:
    command = uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont)
    command.stream_now = True
    streamer.issue_stream_cmd(command)


class LatestReceiver:
    """Drain UHD continuously; overwrite old samples instead of queuing them."""

    def __init__(self, streamer: uhd.usrp.RXStreamer):
        self.streamer = streamer
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.latest: tuple[np.ndarray, float, int] | None = None
        self.error: Exception | None = None
        self.sample_count = 0
        self.overruns = 0
        self.thread = threading.Thread(target=self.receive, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=2.0)

    def snapshot(self) -> tuple[np.ndarray, float, int] | None:
        with self.lock:
            return self.latest

    def receive(self) -> None:
        metadata = uhd.types.RXMetadata()
        buffer = np.zeros((1, cfg.SAMPLES_PER_READ), dtype=np.complex64)
        sequence = 0
        try:
            start_stream(self.streamer)
            while not self.stop_event.is_set():
                count = self.streamer.recv(buffer, metadata, 0.1)
                if metadata.error_code == uhd.types.RXMetadataErrorCode.timeout:
                    continue
                if metadata.error_code == uhd.types.RXMetadataErrorCode.overflow:
                    self.overruns += 1
                    with self.lock:
                        self.latest = None
                    continue
                if metadata.error_code != uhd.types.RXMetadataErrorCode.none:
                    raise RuntimeError(f"RX streamer error: {metadata.strerror()}")
                if count < 2 * SYMBOL_LENGTH:
                    continue
                sequence += 1
                self.sample_count += count
                latest = (buffer[0, :count].copy(), time.monotonic(), sequence)
                with self.lock:
                    self.latest = latest
        except Exception as exc:
            self.error = exc
        finally:
            try:
                stop_stream(self.streamer)
            except Exception as exc:
                self.error = self.error or exc


def create_constellation_plot():
    plt.style.use("dark_background")
    plt.rcParams.update({
        "font.size": cfg.FONT_SIZE,
        "axes.titlesize": cfg.TITLE_FONT_SIZE,
        "axes.labelsize": cfg.LABEL_FONT_SIZE,
        "xtick.labelsize": cfg.TICK_FONT_SIZE,
        "ytick.labelsize": cfg.TICK_FONT_SIZE,
        "text.color": cfg.TEXT_COLOR,
        "axes.labelcolor": cfg.TEXT_COLOR,
        "xtick.color": cfg.TEXT_COLOR,
        "ytick.color": cfg.TEXT_COLOR,
    })
    figure, axes = plt.subplots(num="OFDM constellation", figsize=cfg.FIGURE_SIZE)
    figure.set_facecolor(cfg.FIGURE_BACKGROUND)
    axes.set_facecolor(cfg.PLOT_BACKGROUND)
    constellation_plot, = axes.plot(
        [], [], "o", color=cfg.POINT_COLOR, markersize=cfg.POINT_SIZE, markeredgewidth=0,
        linestyle="none"
    )
    axes.set_title("Equalized constellation\n ", pad=16)
    axes.set_xlabel("In-phase", labelpad=12)
    axes.set_ylabel("Quadrature", labelpad=12)
    axes.set_xlim(-cfg.AXIS_LIMIT, cfg.AXIS_LIMIT)
    axes.set_ylim(-cfg.AXIS_LIMIT, cfg.AXIS_LIMIT)
    axes.set_aspect("equal", adjustable="box")
    axes.grid(True, color=cfg.GRID_COLOR, linewidth=0.8)
    figure.tight_layout()
    return figure, axes, constellation_plot


def main() -> None:
    usrp, streamer = configure_receiver()
    receiver = LatestReceiver(streamer)
    state = ReceiverState()

    plt.ion()
    figure, axes, constellation_plot = create_constellation_plot()
    figure.show()
    if cfg.FULLSCREEN:
        figure.canvas.manager.full_screen_toggle()

    print(
        f"Receiving continuously from USRP {cfg.RX_IP} with {cfg.CLOCK_SOURCE} clock. "
        "Close the plot or press Ctrl+C to stop."
    )
    last_sequence = -1
    receiver.start()
    try:
        while plt.fignum_exists(figure.number):
            update_start = time.monotonic()
            if receiver.error is not None:
                raise receiver.error
            latest = receiver.snapshot()
            if latest is None or update_start - latest[1] > cfg.MAXIMUM_BUFFER_AGE_SECONDS:
                constellation_plot.set_data([], [])
                axes.set_title("No fresh RX samples")
            elif latest[2] != last_sequence:
                samples, received_at, last_sequence = latest
                result = process_received_buffer(samples, state)
                power_dbfs = 10 * np.log10(max(float(np.mean(np.abs(samples)**2)), 1e-30))
                if result is not None:
                    constellation_plot.set_data(
                        result.symbols.real.ravel(), result.symbols.imag.ravel()
                    )
                    if result.synchronized:
                        cfo_khz = (
                            result.fractional_cfo_hz
                            - result.integer_offset * cfg.SAMPLE_RATE / cfg.FFT_LENGTH
                        ) / 1e3
                        status = f"OFDM | CFO {cfo_khz:+.1f} kHz | EVM {100*result.evm:.1f}%"
                    else:
                        status = "No OFDM sync | noise / interference"
                    age_ms = 1000 * (time.monotonic() - received_at)
                    axes.set_title(f"{status}\n{power_dbfs:.1f} dBFS | buffer age {age_ms:.0f} ms")
                else:
                    constellation_plot.set_data([], [])
                    axes.set_title("Invalid RX samples")
            figure.canvas.draw_idle()
            elapsed = time.monotonic() - update_start
            plt.pause(max(0.001, cfg.PLOT_UPDATE_INTERVAL_SECONDS - elapsed))
    except KeyboardInterrupt:
        pass
    finally:
        receiver.close()
        plt.close(figure)


if __name__ == "__main__":
    main()
