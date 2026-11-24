"""Create or complete the shared environment without starting radio hardware."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import venv


ROOT = Path(__file__).resolve().parent
ENVIRONMENT = ROOT / ".venv"
DEPENDENCIES = {
    "ris": {"serial": "pyserial", "PIL": "pillow"},
    "rx": {"numpy": "numpy", "matplotlib": "matplotlib", "uhd": "uhd"},
    "tx": {"numpy": "numpy", "uhd": "uhd"},
}


def environment_python() -> Path:
    return ENVIRONMENT / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def dependencies(component: str) -> dict[str, str]:
    if component == "all":
        return {module: package for group in DEPENDENCIES.values() for module, package in group.items()}
    return DEPENDENCIES[component]


def check_environment(component: str) -> bool:
    python = environment_python()
    if not python.is_file():
        return False
    modules = list(dependencies(component))
    if component != "tx":
        modules.append("tkinter")
    code = (
        "import sys; assert (3, 10) <= sys.version_info[:2] < (3, 14); "
        "assert sys.prefix != sys.base_prefix; "
        + "; ".join(f"import {module}" for module in modules)
    )
    try:
        return subprocess.run([str(python), "-c", code], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0
    except OSError:
        return False


def install_environment(component: str) -> None:
    if not (3, 10) <= sys.version_info[:2] < (3, 14):
        raise RuntimeError("Run setup with Python 3.10-3.13.")
    python = environment_python()
    if not python.is_file():
        print(f"Creating {ENVIRONMENT}", flush=True)
        # Native UHD bindings supplied by the OS/driver can be reused.
        venv.EnvBuilder(with_pip=True, system_site_packages=True).create(ENVIRONMENT)
    subprocess.run([str(python), "-c", "import sys; "
                    "assert sys.prefix != sys.base_prefix, 'Existing .venv is not a virtual environment'; "
                    "assert (3, 10) <= sys.version_info[:2] < (3, 14), "
                    "'Existing .venv requires Python 3.10-3.13; rename it and retry'"], check=True)
    if subprocess.run([str(python), "-m", "pip", "--version"],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        subprocess.run([str(python), "-m", "ensurepip", "--upgrade"], check=True)
    for module, package in dependencies(component).items():
        if subprocess.run([str(python), "-c", f"import {module}"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
            subprocess.run([str(python), "-m", "pip", "install", package], check=True)
    # Keep import errors visible, including missing Tk or UHD runtime libraries.
    modules = list(dependencies(component))
    if component != "tx":
        modules.append("tkinter")
    subprocess.run([str(python), "-c", "; ".join(f"import {module}" for module in modules)], check=True)
    print(f"Environment ready for {component.upper()}.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component", choices=[*DEPENDENCIES, "all"], nargs="?", default="all")
    parser.add_argument("--check", action="store_true", help="Check only; never install packages")
    parser.add_argument("--pause-on-error", action="store_true")
    args = parser.parse_args()
    if args.check:
        return 0 if check_environment(args.component) else 1
    try:
        install_environment(args.component)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"\nEnvironment setup failed: {exc}", file=sys.stderr, flush=True)
        print("Install Python with Tk support. RX/TX also require a working UHD runtime "
              "and matching Python bindings. Retry the launcher after fixing the error.",
              file=sys.stderr, flush=True)
        if args.pause_on_error:
            input("Press Enter to close setup...")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
