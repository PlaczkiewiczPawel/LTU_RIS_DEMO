"""Start the RX window and report errors when no terminal is visible."""

from pathlib import Path
import runpy
import sys
import traceback
from datetime import datetime


def main() -> int:
    directory = Path(__file__).resolve().parent
    sys.path.insert(0, str(directory))
    log_directory = directory / ".logs"
    try:
        log_directory.mkdir(exist_ok=True)
        log_path = log_directory / "rx.log"
        with log_path.open("a", encoding="utf-8", buffering=1) as log:
            original_stdout, original_stderr = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = log
            try:
                print(f"\n--- RX started {datetime.now().isoformat(timespec='seconds')} ---")
                runpy.run_path(str(directory / "run_receiver.py"), run_name="__main__")
                return 0
            except KeyboardInterrupt:
                return 0
            except SystemExit as exc:
                if exc.code in (None, 0):
                    return 0
                traceback.print_exc()
                error = str(exc)
            except Exception as exc:
                traceback.print_exc()
                error = str(exc)
            finally:
                sys.stdout, sys.stderr = original_stdout, original_stderr
        message = f"{error}\n\nDetails: {log_path}"
    except OSError as exc:
        message = f"Cannot write the RX log:\n{exc}"

    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("RX startup error", message, parent=root)
        root.destroy()
    except Exception:
        if sys.stderr is not None:
            print(message, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
