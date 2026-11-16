"""Hardware-free checks: run python -m unittest discover -s Tx."""

import threading
import types
import unittest

import numpy as np

import run_transmitter as tx
import tx_config as cfg


class TransmitterTests(unittest.TestCase):
    def test_frame_can_be_decoded(self):
        tx.validate_config()
        # Independently recover carriers and decode metadata at frame boundaries.
        for number in (0, 1, cfg.NUM_FRAMES - 1):
            frame = tx.build_transmit_frame(number, np.random.default_rng(7))
            symbols = frame.reshape(cfg.NUM_SYMBOLS, -1)
            cp = cfg.CYCLIC_PREFIX_LENGTH
            np.testing.assert_array_equal(symbols[:, :cp], symbols[:, -cp:])
            spectrum = np.fft.fft(symbols[:, cp:], axis=1) / np.sqrt(cfg.NUM_USED_SUBCARRIERS)
            half = cfg.NUM_USED_SUBCARRIERS // 2
            carriers = np.concatenate((spectrum[:, -half:], spectrum[:, 1:half + 1]), axis=1)
            np.testing.assert_allclose(carriers[:, np.array(cfg.PILOT_POSITIONS) - 1], cfg.PILOT_SYMBOL)
            np.testing.assert_allclose(spectrum[:, 0], 0, atol=1e-14)
            np.testing.assert_allclose(spectrum[:, half + 1:-half], 0, atol=1e-14)
            digits = np.argmin(abs(carriers[:, :, None] - tx.CONSTELLATION) ** 2, axis=2)
            def decode(positions):
                return digits[:, np.array(positions) - 1] @ (4 ** np.arange(len(positions) - 1, -1, -1))
            np.testing.assert_array_equal(decode(cfg.FRAME_POSITIONS), np.full(cfg.NUM_SYMBOLS, number))
            np.testing.assert_array_equal(decode(cfg.SYMBOL_POSITIONS), np.arange(1, cfg.NUM_SYMBOLS + 1))

    def test_ifft_scaling_against_direct_sum(self):
        frame = tx.build_transmit_frame(13, np.random.default_rng(3))
        useful = frame.reshape(cfg.NUM_SYMBOLS, -1)[0, cfg.CYCLIC_PREFIX_LENGTH:]
        spectrum = np.fft.fft(useful) / np.sqrt(cfg.NUM_USED_SUBCARRIERS)
        indices = np.arange(cfg.FFT_LENGTH)
        direct = np.exp(2j * np.pi * np.outer(indices, indices) / cfg.FFT_LENGTH) @ spectrum
        direct *= np.sqrt(cfg.NUM_USED_SUBCARRIERS) / cfg.FFT_LENGTH
        np.testing.assert_allclose(useful, direct, atol=1e-13)

    def test_partial_send_preserves_samples_and_burst(self):
        received, flags = [], []
        def send(samples, metadata, timeout):
            count = min(3, samples.size)
            received.extend(samples[0, :count])
            flags.append(metadata.start_of_burst)
            return count
        samples = np.arange(11, dtype=np.complex64)
        tx.send_samples(types.SimpleNamespace(send=send), samples,
                        types.SimpleNamespace(start_of_burst=True), threading.Event())
        np.testing.assert_array_equal(received, samples)
        self.assertEqual(flags, [True, False, False, False])


if __name__ == "__main__":
    unittest.main()
