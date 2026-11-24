"""Check pattern display data without a GUI or serial connection."""

from pathlib import Path
import queue
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Ris"))
from ris_control_gui import RisControlApp, decode_pattern, load_swipe_patterns
import ris_config as cfg


class PatternDataTests(unittest.TestCase):
    def test_leading_zeros_and_bit_order_are_preserved(self):
        self.assertEqual(decode_pattern("0x80" + "00" * 31), "1" + "0" * 255)
        self.assertEqual(decode_pattern("0x" + "00" * 31 + "01"), "0" * 255 + "1")
        self.assertEqual(decode_pattern("0x" + "FF" * 32), "1" * 256)

    def test_malformed_payloads_are_rejected(self):
        for payload in ("0x00", "00" * 33, "0x" + "00" * 31 + "G0"):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                decode_pattern(payload)

    def test_repository_patterns_all_have_256_bits(self):
        patterns = load_swipe_patterns(cfg.SWIPE_PATTERN_FILE)
        self.assertTrue(patterns)
        for pattern in patterns:
            self.assertEqual(len(decode_pattern(pattern["hex"])), 256)


class ActivePatternTests(unittest.TestCase):
    def make_app(self):
        app = RisControlApp.__new__(RisControlApp)
        app.generation = 2
        app.current_pattern_bits = "0" * 256
        app.current_pattern_angle = 0.0
        app.result_queue = queue.Queue()
        app.task_queue = queue.Queue()
        app.controller = MagicMock()
        app.controller.set_pattern.return_value = "OK"
        app.status = MagicMock()
        app.root = MagicMock()
        app._update_plot_panel = MagicMock()
        app._stop_periodic = MagicMock()
        app._stop_swipe = MagicMock()
        app.periodic_enabled = app.swipe_enabled = False
        return app

    def test_worker_keeps_the_exact_sent_payload_for_the_preview(self):
        app = self.make_app()
        payload = "0x80" + "00" * 31
        app.task_queue.put((2, "LEFT", -20.0, payload))
        app.task_queue.put(None)
        app._worker_loop()
        app.controller.set_pattern.assert_called_once_with(payload)
        app._process_results()
        self.assertEqual(app.current_pattern_bits, "1" + "0" * 255)
        self.assertEqual(app.current_pattern_angle, -20.0)
        app._update_plot_panel.assert_called_once_with(-20.0)

    def test_failed_send_preserves_the_last_displayed_pattern(self):
        app = self.make_app()
        app.controller.set_pattern.side_effect = RuntimeError("serial unavailable")
        app.task_queue.put((2, "RIGHT", 30.0, "0x" + "FF" * 32))
        app.task_queue.put(None)
        app._worker_loop()
        app._process_results()
        self.assertEqual(app.current_pattern_bits, "0" * 256)
        self.assertEqual(app.current_pattern_angle, 0.0)
        app._update_plot_panel.assert_not_called()

    def test_obsolete_result_does_not_replace_the_active_pattern(self):
        app = self.make_app()
        app.result_queue.put((1, "LEFT", -20.0, "0x" + "FF" * 32, "OK", None))
        app._process_results()
        self.assertEqual(app.current_pattern_bits, "0" * 256)
        app._update_plot_panel.assert_not_called()


if __name__ == "__main__":
    unittest.main()
