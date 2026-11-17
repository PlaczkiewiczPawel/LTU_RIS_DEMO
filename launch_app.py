"""Prepare the shared venv, then start one demo component."""

from pathlib import Path
import argparse
import os
import subprocess
import sys
import traceback

import setup_venv


ROOT = Path(__file__).resolve().parent
APPLICATIONS = {
    "ris": ("Ris", "launch_ris.py"),
    "rx": ("Rx", "launch_rx.py"),
    "tx": ("Tx", "launch_tx.py"),
}


def launch(component: str) -> None:
    if not setup_venv.check_environment(component):
        # pythonw has no console; use its console sibling for the installer.
        installer_python = Path(sys.executable)
        if sys.platform == "win32":
            installer_python = installer_python.with_name("python.exe")
        command = [str(installer_python), str(ROOT / "setup_venv.py"), component]
        options = {}
        if sys.platform == "win32":
            command.append("--pause-on-error")
            options["creationflags"] = subprocess.CREATE_NEW_CONSOLE
        subprocess.run(command, cwd=ROOT, check=True, **options)
        if not setup_venv.check_environment(component):
            raise RuntimeError("The environment is still incomplete. Run setup_venv.py again.")

    folder, script = APPLICATIONS[component]
    python = setup_venv.environment_python()
    if sys.platform == "win32":
        options = {}
        if component == "tx":
            options["creationflags"] = subprocess.CREATE_NEW_CONSOLE
        else:
            python = python.with_name("pythonw.exe")
        subprocess.Popen([str(python), str(ROOT / folder / script)], cwd=ROOT / folder, **options)
    else:
        os.chdir(ROOT / folder)
        os.execv(str(python), [str(python), str(ROOT / folder / script)])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component", choices=APPLICATIONS)
    args = parser.parse_args()
    try:
        launch(args.component)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        log_directory = ROOT / ".logs"
        message = f"{args.component.upper()} startup failed: {exc}"
        try:
            log_directory.mkdir(exist_ok=True)
            log_path = log_directory / "launcher.log"
            with log_path.open("a", encoding="utf-8") as log:
                traceback.print_exc(file=log)
            message += f"\n\nDetails: {log_path}"
        except OSError:
            pass
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, "Demo startup error", 0x10)
        else:
            print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
