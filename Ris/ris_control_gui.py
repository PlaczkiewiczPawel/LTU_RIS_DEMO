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

from PIL import Image, ImageTk

import ris_config as cfg

try:
    import serial
except ImportError:
    serial = None


def decode_pattern(hex_pattern: str) -> str:
    """Return 256 display bits, MSB first, left to right and row by row."""
    if (len(hex_pattern) != 66 or hex_pattern[:2].lower() != "0x"
            or any(character not in "0123456789abcdefABCDEF" for character in hex_pattern[2:])):
        raise ValueError("A RIS pattern must contain 0x followed by 64 hexadecimal digits")
    return f"{int(hex_pattern[2:], 16):0256b}"


def load_swipe_patterns(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    patterns = []
    for entry in payload["PATTERNS"]:
        angle = float(str(entry["DESC"]).replace("deg", "").strip())
        hex_pattern = str(entry["HEX"])
        decode_pattern(hex_pattern)
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
            time.sleep(cfg.PATTERN_SETTLE_TIME_SECONDS)
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
                cfg.RIS_PORT,
                cfg.BAUD_RATE,
                timeout=cfg.SERIAL_TIMEOUT_SECONDS,
            )
        return self._port


class RisControlApp:
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
        self.current_pattern_bits = None
        self.current_pattern_angle = None
        self.plot_visible = False
        self.plot_panel = None
        self.plot_label = None
        self.plot_image = None
        self.plot_source = None
        self.plot_render_size = None
        self.plot_resize_after_id = None
        self.plot_opened = False

        try:
            self.swipe_patterns = load_swipe_patterns(cfg.SWIPE_PATTERN_FILE)
            self.swipe_load_error = None
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self.swipe_patterns = []
            self.swipe_load_error = str(exc)

        self.status = tk.StringVar(
            value=f"Ready - {cfg.RIS_PORT}, ID {cfg.RIS_ID}"
        )
        self.interval = tk.IntVar(value=cfg.DEFAULT_AUTOMATIC_INTERVAL_SECONDS)
        self.custom_angle = tk.StringVar(value="0")
        self.plot_type = tk.StringVar(value="both")
        self.mode_angles = {
            mode: tk.StringVar(value=f"{angle:g}")
            for mode, angle in cfg.DEFAULT_MODE_ANGLES.items()
        }

        self._build_gui()
        self.worker = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker.start()
        self.root.after(
            cfg.GUI_POLL_INTERVAL_MILLISECONDS,
            self._process_results,
        )
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _apply_theme(self) -> None:
        colors = cfg.GUI_COLORS
        self.root.configure(background=colors["background"])
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")
        self.style.configure(
            ".", background=colors["background"], foreground=colors["text"],
            bordercolor=colors["border"], lightcolor=colors["border"],
            darkcolor=colors["border"], focuscolor=colors["accent"],
        )
        self.style.configure("TFrame", background=colors["background"])
        self.style.configure("TLabel", background=colors["background"], foreground=colors["text"])
        self.style.configure("Muted.TLabel", foreground=colors["muted_text"])
        self.style.configure("Plot.TFrame", background=colors["surface"])
        self.style.configure("Plot.TLabel", background=colors["surface"], foreground=colors["muted_text"])
        self.style.configure("TSeparator", background=colors["border"])
        self.style.configure(
            "TButton", background=colors["button"], foreground=colors["text"],
            padding=(12, 7), borderwidth=1, relief="flat", anchor="center",
        )
        self.style.map(
            "TButton",
            background=[("disabled", colors["surface"]), ("pressed", colors["field"]),
                        ("active", colors["button_hover"])],
            foreground=[("disabled", colors["disabled_text"])],
            bordercolor=[("focus", colors["accent"])],
        )
        self.style.configure(
            "Accent.TButton", background=colors["accent"], foreground=colors["accent_text"],
        )
        self.style.map(
            "Accent.TButton",
            background=[("disabled", colors["surface"]), ("pressed", colors["accent_pressed"]),
                        ("active", colors["accent_hover"])],
            foreground=[("disabled", colors["disabled_text"]), ("!disabled", colors["accent_text"])],
        )
        self.style.configure(
            "TEntry", fieldbackground=colors["field"], foreground=colors["text"],
            insertcolor=colors["text"], padding=(8, 6),
            selectbackground=colors["accent"], selectforeground=colors["accent_text"],
        )
        self.style.map(
            "TEntry", bordercolor=[("focus", colors["accent"])],
            fieldbackground=[("disabled", colors["surface"])],
            foreground=[("disabled", colors["disabled_text"])],
        )
        self.style.configure(
            "TRadiobutton", background=colors["background"], foreground=colors["muted_text"],
            padding=(4, 4), indicatorbackground=colors["field"],
            indicatorforeground=colors["accent_text"],
        )
        self.style.map(
            "TRadiobutton",
            background=[("active", colors["surface"])],
            foreground=[("disabled", colors["disabled_text"]), ("selected", colors["text"])],
            indicatorbackground=[("selected", colors["accent"]), ("active", colors["button_hover"])],
        )
        self.style.configure(
            "Horizontal.TScale", background=colors["slider"],
            troughcolor=colors["slider_track"], bordercolor=colors["slider_track"],
            lightcolor=colors["slider"], darkcolor=colors["slider"],
            arrowsize=24, gripcount=0,
        )
        self.style.map(
            "Horizontal.TScale",
            background=[("pressed", colors["slider_hover"]), ("active", colors["slider_hover"])],
        )
        self.style.configure(
            "Value.TLabel", background=colors["surface"], foreground=colors["accent"],
            padding=(8, 4),
        )

    def _build_gui(self) -> None:
        self._apply_theme()
        self.root.title("RIS 5 GHz control")
        self.root.resizable(True, True)
        self.root.geometry(f"{cfg.GUI_WINDOW_WIDTH}x{cfg.GUI_WINDOW_HEIGHT}")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        frame = ttk.Frame(
            self.root,
            width=cfg.GUI_WINDOW_WIDTH,
            height=cfg.GUI_WINDOW_HEIGHT,
            padding=18,
        )
        frame.grid(row=0, column=0, sticky="nsew")
        for column in range(3):
            frame.columnconfigure(column, weight=1, uniform="mode")
        frame.rowconfigure(10, weight=1)

        ttk.Label(frame, text="Select RIS mode", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=3, pady=(0, 14)
        )

        for column, mode in enumerate(("LEFT", "BOTH", "RIGHT")):
            ttk.Entry(
                frame,
                textvariable=self.mode_angles[mode],
                width=16,
                justify="center",
            ).grid(row=1, column=column, sticky="ew", padx=5, pady=(0, 3))
            ttk.Button(
                frame,
                text=mode,
                command=lambda selected_mode=mode: self._select_manual_mode(
                    selected_mode
                ),
                width=16,
                style="Accent.TButton",
            ).grid(row=2, column=column, sticky="ew", padx=5, pady=(3, 5))

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
            text="SHOW PLOT / PATTERN",
            command=self._toggle_plot_panel,
        )
        self.plot_button.grid(
            row=9, column=0, columnspan=3, sticky="ew", padx=5, pady=(0, 10)
        )

        angle_frame = ttk.Frame(frame)
        angle_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(10, 5))
        angle_frame.columnconfigure(1, weight=1)
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
        angle_entry.grid(row=1, column=1, sticky="ew", padx=5)
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
            style="Accent.TButton",
            command=self._set_custom_angle,
        ).grid(row=1, column=3, padx=(5, 0))

        ttk.Label(frame, text="Automatic interval [s]").grid(
            row=7, column=0, columnspan=3, pady=(10, 0)
        )
        interval_frame = ttk.Frame(frame)
        interval_frame.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        interval_frame.columnconfigure(0, weight=1)
        self.interval_slider = ttk.Scale(
            interval_frame,
            from_=cfg.MINIMUM_AUTOMATIC_INTERVAL_SECONDS,
            to=cfg.MAXIMUM_AUTOMATIC_INTERVAL_SECONDS,
            orient="horizontal",
            variable=self.interval,
            command=lambda value: self.interval.set(round(float(value))),
            length=360,
        )
        self.interval_slider.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            interval_frame, textvariable=self.interval, style="Value.TLabel",
            width=3, anchor="center",
        ).grid(row=0, column=1, padx=(10, 0))

        ttk.Separator(frame).grid(
            row=11, column=0, columnspan=3, sticky="sew", pady=(2, 10)
        )
        self.status_label = ttk.Label(
            frame,
            style="Muted.TLabel",
            textvariable=self.status,
            anchor="center",
            justify="center",
            wraplength=cfg.GUI_STATUS_WRAP_LENGTH,
        )
        self.status_label.grid(
            row=12,
            column=0,
            columnspan=3,
            sticky="ew",
        )

        self.plot_panel = ttk.Frame(frame, padding=(0, 0, 0, 8))
        self.plot_panel.columnconfigure(0, weight=1)
        self.plot_panel.rowconfigure(1, weight=1)
        plot_options = ttk.Frame(self.plot_panel)
        plot_options.grid(row=0, column=0, pady=(0, 8))
        ttk.Label(plot_options, text="View:").grid(row=0, column=0, padx=(0, 8))
        for column, (text, value) in enumerate(
            (("Continuous phase", "continuous_phase"),
             ("Quantized", "quantized_1bit"),
             ("Both", "both"),
             ("Pattern", "pattern")),
            start=1,
        ):
            ttk.Radiobutton(
                plot_options,
                text=text,
                variable=self.plot_type,
                value=value,
                command=self._update_plot_panel,
            ).grid(row=0, column=column, padx=5)
        self.plot_viewport = ttk.Frame(self.plot_panel, width=1, height=1, style="Plot.TFrame")
        self.plot_viewport.grid(row=1, column=0, sticky="nsew")
        self.plot_viewport.grid_propagate(False)
        self.plot_viewport.bind("<Configure>", self._queue_plot_resize)
        self.plot_label = ttk.Label(
            self.plot_viewport,
            style="Plot.TLabel",
            text="Apply a RIS pattern to display its polar plot.",
            anchor="center",
        )
        self.plot_label.place(relx=0.5, rely=0.5, anchor="center")
        self.pattern_canvas = tk.Canvas(
            self.plot_viewport, background=cfg.GUI_COLORS["surface"],
            highlightthickness=0, borderwidth=0,
        )
        self.root.update_idletasks()
        self.controls_height = frame.winfo_reqheight()
        self.minimum_width = max(520, frame.winfo_reqwidth(), plot_options.winfo_reqwidth() + 36)
        self.plot_options_height = plot_options.winfo_reqheight() + 16
        self.root.minsize(self.minimum_width, self.controls_height)
        frame.bind("<Configure>", self._resize_status_wrap)

    def _resize_status_wrap(self, event) -> None:
        self.status_label.configure(wraplength=max(1, event.width - 36))

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
                self.result_queue.put((generation, mode, angle, hex_pattern, response, None))
            except Exception as exc:
                self.result_queue.put((generation, mode, angle, hex_pattern, "", str(exc)))

    def _process_results(self) -> None:
        while True:
            try:
                generation, mode, angle, hex_pattern, response, error = (
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
            self.current_pattern_bits = decode_pattern(hex_pattern)
            self.current_pattern_angle = angle
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

        self.root.after(
            cfg.GUI_POLL_INTERVAL_MILLISECONDS,
            self._process_results,
        )

    def _toggle_plot_panel(self) -> None:
        self.plot_visible = not self.plot_visible
        if self.plot_visible:
            self.plot_panel.grid(row=10, column=0, columnspan=3, sticky="nsew")
            self.root.minsize(
                self.minimum_width, self.controls_height + self.plot_options_height + 120
            )
            if not self.plot_opened:
                if (self.root.winfo_width(), self.root.winfo_height()) == (
                    cfg.GUI_WINDOW_WIDTH, cfg.GUI_WINDOW_HEIGHT
                ) and self.root.state() == "normal":
                    height = min(
                        self.root.winfo_screenheight() - 100,
                        self.controls_height + self.plot_options_height + int((cfg.GUI_WINDOW_WIDTH - 36) * 9 / 16),
                    )
                    self.root.geometry(f"{cfg.GUI_WINDOW_WIDTH}x{height}")
                self.plot_opened = True
            self.plot_button.configure(text="HIDE PLOT / PATTERN")
            self._update_plot_panel()
        else:
            self.plot_panel.grid_remove()
            self.root.minsize(self.minimum_width, self.controls_height)
            self.plot_button.configure(text="SHOW PLOT / PATTERN")

    def _update_plot_panel(self, angle: float | None = None) -> None:
        if angle is not None:
            self.current_plot_angle = angle
        if not self.plot_visible:
            return
        if self.plot_type.get() == "pattern":
            self.plot_label.place_forget()
            self.pattern_canvas.place(x=0, y=0, relwidth=1, relheight=1)
            self._queue_plot_resize()
            return
        self.pattern_canvas.place_forget()
        self.plot_label.place(relx=0.5, rely=0.5, anchor="center")
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
        plot_directory = cfg.POLAR_PLOT_DIRECTORY
        if self.plot_type.get() != "both":
            plot_directory = plot_directory / self.plot_type.get()
        plot_path = plot_directory / filename
        if not plot_path.exists():
            self.plot_source = None
            self.plot_image = None
            self.plot_label.configure(
                image="",
                text=f"Polar plot not found:\n{plot_path}",
            )
            return

        try:
            with Image.open(plot_path) as image:
                self.plot_source = image.copy()
            self.plot_render_size = None
        except (OSError, ValueError) as exc:
            self.plot_source = None
            self.plot_image = None
            self.plot_label.configure(image="", text=f"Cannot open plot:\n{exc}")
            return

        self._queue_plot_resize()

    def _queue_plot_resize(self, _event=None) -> None:
        if self.plot_resize_after_id is not None:
            self.root.after_cancel(self.plot_resize_after_id)
        self.plot_resize_after_id = self.root.after(60, self._resize_plot_image)

    def _resize_plot_image(self) -> None:
        self.plot_resize_after_id = None
        if self.plot_visible and self.plot_type.get() == "pattern":
            self._draw_pattern()
            return
        width = max(1, self.plot_viewport.winfo_width() - 4)
        height = max(1, self.plot_viewport.winfo_height() - 4)
        self.plot_label.configure(wraplength=width)
        if not self.plot_visible or self.plot_source is None:
            return
        scale = min(width / self.plot_source.width, height / self.plot_source.height)
        size = (max(1, int(self.plot_source.width * scale)),
                max(1, int(self.plot_source.height * scale)))
        if size == self.plot_render_size:
            return
        image = self.plot_source.resize(size, Image.Resampling.LANCZOS)
        self.plot_image = ImageTk.PhotoImage(image, master=self.root)
        self.plot_render_size = size
        self.plot_label.configure(image=self.plot_image, text="")

    def _draw_pattern(self) -> None:
        canvas = self.pattern_canvas
        canvas.delete("all")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        colors = cfg.GUI_COLORS
        if self.current_pattern_bits is None:
            canvas.create_text(
                width / 2, height / 2, text="Apply a RIS pattern to display its elements.",
                fill=colors["muted_text"], width=max(1, width - 24), justify="center",
            )
            return
        canvas.create_text(
            width / 2, 16, text=f"Current pattern | {self.current_pattern_angle:+g} deg",
            fill=colors["text"],
        )
        for offset, bit, color in ((-54, "0", colors["pattern_zero"]),
                                   (22, "1", colors["pattern_one"])):
            x = width / 2 + offset
            canvas.create_rectangle(x, 34, x + 14, 44, fill=color, outline=colors["border"])
            canvas.create_text(x + 26, 39, text=bit, fill=colors["text"])
        # Sixteen rows/columns; both the full panel and each element are 2:1 rectangles.
        cell_height = max(0, min((width - 16) / 32, (height - 64) / 16))
        if cell_height <= 0:
            return
        cell_width = 2 * cell_height
        left = (width - 16 * cell_width) / 2
        top = 56 + (height - 64 - 16 * cell_height) / 2
        for index, bit in enumerate(self.current_pattern_bits):
            row, column = divmod(index, 16)
            x = left + (15 - column) * cell_width
            y = top + row * cell_height
            canvas.create_rectangle(
                x, y, x + cell_width, y + cell_height,
                fill=colors["pattern_one"] if bit == "1" else colors["pattern_zero"],
                outline=colors["border"], width=1, tags="pattern_cell",
            )

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
        if self.plot_resize_after_id is not None:
            self.root.after_cancel(self.plot_resize_after_id)
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
