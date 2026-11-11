"""Simple GUI for selecting predefined 5 GHz RIS patterns."""

from __future__ import annotations

import json
import math
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

try:
    import serial
except ImportError:
    serial = None


RIS_PORT = "COM4"
RIS_ID = 1
BAUD_RATE = 115200
SERIAL_TIMEOUT_S = 2.0
PATTERN_SETTLE_TIME_S = 0.1
SWIPE_PATTERN_FILE = Path(__file__).with_name(
    "ris_patterns_16x16_5.24GHz_angles.json"
)
POLAR_PLOT_DIRECTORY = Path(__file__).with_name("plots_polar")

DEFAULT_MODE_ANGLES = {
    "LEFT": -20.0,
    "BOTH": 55.0,
    "RIGHT": -29.5,
}


def load_swipe_patterns(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    patterns = []
    for entry in payload["PATTERNS"]:
        angle = float(str(entry["DESC"]).replace("deg", "").strip())
        hex_pattern = str(entry["HEX"])
        if len(hex_pattern) != 66:
            raise ValueError(f"Invalid 256-bit pattern for angle {angle:g}")
        patterns.append(
            {
                "id": str(entry["ID"]),
                "angle": angle,
                "hex": hex_pattern,
            }
        )
    return sorted(patterns, key=lambda pattern: pattern["angle"])


class RisController:
    def __init__(self) -> None:
        self._port = None
        self._lock = threading.Lock()

    def set_pattern(self, pattern: str) -> str:
        with self._lock:
            port = self._get_port()
            port.write(f"!{pattern}\n".encode("utf-8"))
            time.sleep(PATTERN_SETTLE_TIME_S)
            return port.readline().decode("utf-8", errors="replace").rstrip()

    def close(self) -> None:
        with self._lock:
            if self._port is not None and self._port.is_open:
                self._port.close()

    def _get_port(self):
        if serial is None:
            raise RuntimeError("PySerial is not installed. Run: pip install pyserial")
        if self._port is None or not self._port.is_open:
            self._port = serial.Serial(
                RIS_PORT,
                BAUD_RATE,
                timeout=SERIAL_TIMEOUT_S,
            )
        return self._port


class RisControlApp:
    POLL_INTERVAL_MS = 50

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.controller = RisController()
        self.task_queue: queue.Queue = queue.Queue()
        self.result_queue: queue.Queue = queue.Queue()
        self.generation = 0
        self.periodic_enabled = False
        self.swipe_enabled = False
        self.automatic_after_id = None
        self.next_periodic_mode = "LEFT"
        self.swipe_index = 0
        self.current_plot_angle = 0.0
        self.plot_visible = False
        self.plot_panel = None
        self.plot_label = None
        self.plot_image = None

        try:
            self.swipe_patterns = load_swipe_patterns(SWIPE_PATTERN_FILE)
            self.swipe_load_error = None
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self.swipe_patterns = []
            self.swipe_load_error = str(exc)

        self.status = tk.StringVar(value=f"Ready - {RIS_PORT}, ID {RIS_ID}")
        self.interval = tk.IntVar(value=1)
        self.custom_angle = tk.StringVar(value="0")
        self.mode_angles = {
            mode: tk.StringVar(value=f"{angle:g}")
            for mode, angle in DEFAULT_MODE_ANGLES.items()
        }

        self._build_gui()
        self.worker = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker.start()
        self.root.after(self.POLL_INTERVAL_MS, self._process_results)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build_gui(self) -> None:
        self.root.title("RIS 5 GHz control")
        self.root.resizable(False, False)

        frame = ttk.Frame(self.root, padding=18)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text="Select RIS mode", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=3, pady=(0, 14)
        )

        for column, mode in enumerate(("LEFT", "BOTH", "RIGHT")):
            ttk.Entry(
                frame,
                textvariable=self.mode_angles[mode],
                width=16,
                justify="center",
            ).grid(row=1, column=column, padx=5, pady=(0, 3))
            ttk.Button(
                frame,
                text=mode,
                command=lambda selected_mode=mode: self._select_manual_mode(
                    selected_mode
                ),
                width=16,
            ).grid(row=2, column=column, padx=5, pady=(3, 5))

        self.periodic_button = ttk.Button(
            frame,
            text="START PERIODIC",
            command=self._toggle_periodic,
        )
        self.periodic_button.grid(
            row=3, column=0, columnspan=3, sticky="ew", padx=5, pady=(14, 5)
        )

        self.swipe_button = ttk.Button(
            frame,
            text="START SWIPE (-90 to +90 deg)",
            command=self._toggle_swipe,
        )
        self.swipe_button.grid(
            row=4, column=0, columnspan=3, sticky="ew", padx=5, pady=5
        )

        self.plot_button = ttk.Button(
            frame,
            text="SHOW POLAR PLOT",
            command=self._toggle_plot_panel,
        )
        self.plot_button.grid(
            row=5, column=0, columnspan=3, sticky="ew", padx=5, pady=5
        )

        angle_frame = ttk.Frame(frame)
        angle_frame.grid(row=6, column=0, columnspan=3, pady=(10, 5))
        ttk.Label(angle_frame, text="Reflection angle [deg]").grid(
            row=0, column=0, columnspan=4, pady=(0, 4)
        )
        ttk.Button(
            angle_frame,
            text="−",
            command=lambda: self._step_custom_angle(-1),
            width=4,
        ).grid(row=1, column=0, padx=(0, 5))
        angle_entry = ttk.Entry(
            angle_frame,
            textvariable=self.custom_angle,
            width=10,
            justify="center",
        )
        angle_entry.grid(row=1, column=1, padx=5)
        angle_entry.bind("<Return>", lambda _event: self._set_custom_angle())
        ttk.Button(
            angle_frame,
            text="+",
            command=lambda: self._step_custom_angle(1),
            width=4,
        ).grid(row=1, column=2, padx=5)
        ttk.Button(
            angle_frame,
            text="SET ANGLE",
            command=self._set_custom_angle,
        ).grid(row=1, column=3, padx=(5, 0))

        ttk.Label(frame, text="Automatic interval [s]").grid(
            row=7, column=0, columnspan=3, pady=(10, 0)
        )
        tk.Scale(
            frame,
            from_=1,
            to=5,
            orient="horizontal",
            resolution=1,
            variable=self.interval,
            showvalue=True,
            length=360,
        ).grid(row=8, column=0, columnspan=3, pady=(0, 10))

        ttk.Separator(frame).grid(
            row=9, column=0, columnspan=3, sticky="ew", pady=(2, 10)
        )
        ttk.Label(frame, textvariable=self.status, anchor="center").grid(
            row=10, column=0, columnspan=3, sticky="ew"
        )

        self.plot_panel = ttk.Frame(self.root, padding=(0, 18, 18, 18))
        self.plot_label = ttk.Label(
            self.plot_panel,
            text="Apply a RIS pattern to display its polar plot.",
            anchor="center",
            padding=12,
        )
        self.plot_label.grid(row=0, column=0)

    def _select_manual_mode(self, mode: str) -> None:
        pattern = self._get_mode_pattern(mode)
        if pattern is None:
            return
        self._stop_periodic()
        self._stop_swipe()
        self.generation += 1
        self._queue_pattern(mode, self.generation, pattern)

    def _toggle_periodic(self) -> None:
        if self.periodic_enabled:
            self._stop_periodic()
            self.generation += 1
            self.status.set("Periodic mode stopped")
            return

        self._stop_swipe()
        left_pattern = self._get_mode_pattern("LEFT")
        right_pattern = self._get_mode_pattern("RIGHT")
        if left_pattern is None or right_pattern is None:
            return
        self.generation += 1
        self.periodic_enabled = True
        self.next_periodic_mode = "LEFT"
        self.periodic_button.configure(text="STOP PERIODIC")
        self._queue_pattern(self.next_periodic_mode, self.generation, left_pattern)

    def _get_mode_pattern(self, mode: str) -> dict | None:
        if self.swipe_load_error:
            self.status.set(f"Pattern file error: {self.swipe_load_error}")
            return None
        if not self.swipe_patterns:
            self.status.set("Pattern file contains no patterns")
            return None

        value = self.mode_angles[mode].get().strip().replace(",", ".")
        try:
            requested_angle = float(value)
        except ValueError:
            self.status.set(f"Enter a valid angle for {mode}")
            return None
        if not math.isfinite(requested_angle):
            self.status.set(f"Angle for {mode} must be a finite number")
            return None

        return min(
            self.swipe_patterns,
            key=lambda item: abs(item["angle"] - requested_angle),
        )

    def _queue_periodic_pattern(self) -> None:
        if not self.periodic_enabled:
            return
        pattern = self._get_mode_pattern(self.next_periodic_mode)
        if pattern is None:
            self._stop_periodic()
            return
        self._queue_pattern(self.next_periodic_mode, self.generation, pattern)

    def _toggle_swipe(self) -> None:
        if self.swipe_enabled:
            self._stop_swipe()
            self.generation += 1
            self.status.set("Swipe stopped")
            return

        if self.swipe_load_error:
            self.status.set(f"Swipe file error: {self.swipe_load_error}")
            return
        if not self.swipe_patterns:
            self.status.set("Swipe file contains no patterns")
            return

        self._stop_periodic()
        self.generation += 1
        self.swipe_enabled = True
        self.swipe_index = 0
        self.swipe_button.configure(text="STOP SWIPE")
        self._queue_swipe_pattern(self.generation)

    def _set_custom_angle(self) -> None:
        if self.swipe_load_error:
            self.status.set(f"Pattern file error: {self.swipe_load_error}")
            return
        if not self.swipe_patterns:
            self.status.set("Pattern file contains no patterns")
            return

        try:
            requested_angle = float(self.custom_angle.get().strip().replace(",", "."))
        except ValueError:
            self.status.set("Enter a valid angle, for example -45 or 12.5")
            return
        if not math.isfinite(requested_angle):
            self.status.set("Angle must be a finite number")
            return

        pattern = min(
            self.swipe_patterns,
            key=lambda item: abs(item["angle"] - requested_angle),
        )
        selected_angle = pattern["angle"]
        self._stop_periodic()
        self._stop_swipe()
        self.generation += 1
        mode = f"ANGLE {requested_angle:+g} -> {selected_angle:+g} deg"
        self._queue_pattern(mode, self.generation, pattern)

    def _step_custom_angle(self, direction: int) -> None:
        if self.swipe_load_error:
            self.status.set(f"Pattern file error: {self.swipe_load_error}")
            return
        if not self.swipe_patterns:
            self.status.set("Pattern file contains no patterns")
            return

        try:
            current_angle = float(self.custom_angle.get().strip().replace(",", "."))
        except ValueError:
            self.status.set("Enter a valid angle before using + or −")
            return
        if not math.isfinite(current_angle):
            self.status.set("Angle must be a finite number")
            return

        current_index = min(
            range(len(self.swipe_patterns)),
            key=lambda index: abs(
                self.swipe_patterns[index]["angle"] - current_angle
            ),
        )
        next_index = max(
            0,
            min(len(self.swipe_patterns) - 1, current_index + direction),
        )
        self.custom_angle.set(f"{self.swipe_patterns[next_index]['angle']:g}")
        self._set_custom_angle()

    def _queue_pattern(
        self,
        mode: str,
        generation: int,
        pattern: dict,
    ) -> None:
        angle = pattern["angle"]
        self.status.set(f"Setting {mode}: {angle:+g} deg...")
        self.task_queue.put((generation, mode, angle, pattern["hex"]))

    def _queue_swipe_pattern(self, generation: int) -> None:
        pattern = self.swipe_patterns[self.swipe_index]
        progress = f"{self.swipe_index + 1}/{len(self.swipe_patterns)}"
        self._queue_pattern(f"SWIPE {progress}", generation, pattern)

    def _worker_loop(self) -> None:
        while True:
            task = self.task_queue.get()
            if task is None:
                return

            generation, mode, angle, hex_pattern = task
            if generation != self.generation:
                continue

            try:
                response = self.controller.set_pattern(hex_pattern)
                self.result_queue.put((generation, mode, angle, response, None))
            except Exception as exc:
                self.result_queue.put((generation, mode, angle, "", str(exc)))

    def _process_results(self) -> None:
        while True:
            try:
                generation, mode, angle, response, error = (
                    self.result_queue.get_nowait()
                )
            except queue.Empty:
                break

            if generation != self.generation:
                continue
            if error:
                self.status.set(f"Error: {error}")
                self._stop_periodic()
                self._stop_swipe()
                continue

            response_text = f" - {response}" if response else ""
            self.status.set(f"Active: {mode} ({angle:+g} deg){response_text}")
            self._update_plot_panel(angle)
            if self.periodic_enabled:
                self.next_periodic_mode = "RIGHT" if mode == "LEFT" else "LEFT"
                delay_ms = self.interval.get() * 1000
                self.automatic_after_id = self.root.after(
                    delay_ms,
                    self._queue_periodic_pattern,
                )
            elif self.swipe_enabled:
                self.swipe_index += 1
                if self.swipe_index >= len(self.swipe_patterns):
                    count = len(self.swipe_patterns)
                    self._stop_swipe()
                    self.status.set(f"Swipe complete: {count} patterns, last {angle:+g} deg")
                else:
                    delay_ms = self.interval.get() * 1000
                    self.automatic_after_id = self.root.after(
                        delay_ms,
                        lambda: self._queue_swipe_pattern(self.generation),
                    )

        self.root.after(self.POLL_INTERVAL_MS, self._process_results)

    def _toggle_plot_panel(self) -> None:
        self.plot_visible = not self.plot_visible
        if self.plot_visible:
            self.plot_panel.grid(row=0, column=1, sticky="nsew")
            self.plot_button.configure(text="HIDE POLAR PLOT")
            self._update_plot_panel()
        else:
            self.plot_panel.grid_remove()
            self.plot_button.configure(text="SHOW POLAR PLOT")
        self._resize_root_to_content()

    def _update_plot_panel(self, angle: float | None = None) -> None:
        if angle is not None:
            self.current_plot_angle = angle
        if not self.plot_visible:
            return
        if self.current_plot_angle is None:
            return

        pattern = min(
            self.swipe_patterns,
            key=lambda item: abs(item["angle"] - self.current_plot_angle),
        )
        angle_token = f"{abs(pattern['angle']):.1f}".replace(".", "_")
        angle_prefix = "p" if pattern["angle"] >= 0.0 else "m"
        filename = (
            f"pattern_{int(pattern['id']):03d}_target_"
            f"{angle_prefix}{angle_token}deg.png"
        )
        plot_path = POLAR_PLOT_DIRECTORY / filename
        if not plot_path.exists():
            self.plot_image = None
            self.plot_label.configure(
                image="",
                text=f"Polar plot not found:\n{plot_path}",
            )
            return

        try:
            self.plot_image = tk.PhotoImage(file=str(plot_path))
        except tk.TclError as exc:
            self.plot_image = None
            self.plot_label.configure(image="", text=f"Cannot open plot:\n{exc}")
            return

        self.plot_label.configure(image=self.plot_image, text="")
        self._resize_root_to_content()

    def _resize_root_to_content(self) -> None:
        self.root.update_idletasks()
        width = self.root.winfo_reqwidth()
        height = self.root.winfo_reqheight()
        self.root.geometry(f"{width}x{height}")

    def _stop_periodic(self) -> None:
        self.periodic_enabled = False
        self.periodic_button.configure(text="START PERIODIC")
        self._cancel_automatic_action()

    def _stop_swipe(self) -> None:
        self.swipe_enabled = False
        self.swipe_button.configure(text="START SWIPE (-90 to +90 deg)")
        self._cancel_automatic_action()

    def _cancel_automatic_action(self) -> None:
        if self.automatic_after_id is not None:
            self.root.after_cancel(self.automatic_after_id)
            self.automatic_after_id = None

    def _close(self) -> None:
        self.generation += 1
        self._stop_periodic()
        self._stop_swipe()
        self.task_queue.put(None)
        self.controller.close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    RisControlApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
