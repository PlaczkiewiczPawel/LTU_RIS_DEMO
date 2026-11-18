"""RX connection retry checks without a UHD installation or radio hardware."""

from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, call, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Rx"))
with patch.dict(sys.modules, {"uhd": MagicMock()}):
    import run_receiver as rx


class ReceiverConnectionTests(unittest.TestCase):
    def setUp(self):
        self.uhd = MagicMock()
        self.radio = MagicMock()
        self.uhd.usrp.MultiUSRP.return_value = self.radio
        for context in (
            patch.object(rx, "uhd", self.uhd),
            patch.object(rx.cfg, "CONNECTION_ATTEMPTS", 3),
            patch.object(rx.cfg, "CONNECTION_RETRY_INTERVAL_SECONDS", 0.25),
            patch.object(rx.time, "sleep"),
            patch("builtins.print"),
        ):
            context.start()
            self.addCleanup(context.stop)

    def test_success_on_first_attempt_does_not_wait(self):
        radio, streamer = rx.configure_receiver()
        self.assertIs(radio, self.radio)
        self.assertIs(streamer, self.radio.get_rx_stream.return_value)
        self.uhd.usrp.MultiUSRP.assert_called_once_with(f"addr={rx.cfg.RX_IP}")
        rx.time.sleep.assert_not_called()

    def test_transient_failures_continue_to_configure_radio(self):
        self.uhd.usrp.MultiUSRP.side_effect = [RuntimeError("timeout"), RuntimeError("busy"), self.radio]
        radio, _ = rx.configure_receiver()
        self.assertIs(radio, self.radio)
        self.assertEqual(self.uhd.usrp.MultiUSRP.call_args_list, [call(f"addr={rx.cfg.RX_IP}")] * 3)
        self.assertEqual(rx.time.sleep.call_args_list, [call(0.25), call(0.25)])
        self.radio.set_rx_antenna.assert_called_once_with(rx.cfg.RX_ANTENNA, 0)
        self.radio.get_rx_stream.assert_called_once()

    def test_exhaustion_reports_ip_and_last_error_without_extra_wait(self):
        error = RuntimeError("device unavailable")
        self.uhd.usrp.MultiUSRP.side_effect = error
        with self.assertRaises(RuntimeError) as caught:
            rx.configure_receiver()
        self.assertIn(rx.cfg.RX_IP, str(caught.exception))
        self.assertIn("after 3 attempts", str(caught.exception))
        self.assertIn("device unavailable", str(caught.exception))
        self.assertIs(caught.exception.__cause__, error)
        self.assertEqual(self.uhd.usrp.MultiUSRP.call_count, 3)
        self.assertEqual(rx.time.sleep.call_count, 2)
        self.radio.set_clock_source.assert_not_called()

    def test_configuration_errors_are_not_retried(self):
        self.radio.set_clock_source.side_effect = RuntimeError("invalid clock source")
        with self.assertRaisesRegex(RuntimeError, "invalid clock source"):
            rx.configure_receiver()
        self.uhd.usrp.MultiUSRP.assert_called_once()
        rx.time.sleep.assert_not_called()

    def test_keyboard_interrupt_stops_retries(self):
        self.uhd.usrp.MultiUSRP.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            rx.configure_receiver()
        self.uhd.usrp.MultiUSRP.assert_called_once()
        rx.time.sleep.assert_not_called()

    def test_invalid_retry_settings_fail_before_connecting(self):
        for attempts in (0, -1, 1.5, True):
            with self.subTest(attempts=attempts), patch.object(rx.cfg, "CONNECTION_ATTEMPTS", attempts):
                with self.assertRaisesRegex(ValueError, "CONNECTION_ATTEMPTS"):
                    rx.configure_receiver()
        for delay in (-1, float("nan"), float("inf")):
            with self.subTest(delay=delay), patch.object(rx.cfg, "CONNECTION_RETRY_INTERVAL_SECONDS", delay):
                with self.assertRaisesRegex(ValueError, "CONNECTION_RETRY_INTERVAL_SECONDS"):
                    rx.configure_receiver()
        self.uhd.usrp.MultiUSRP.assert_not_called()


if __name__ == "__main__":
    unittest.main()
