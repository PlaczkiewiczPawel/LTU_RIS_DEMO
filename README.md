# Camera-ready RIS/OFDM demo

The package contains three independent components:

- `Ris` — RIS control via a serial port, patterns, and polar plots.
- `Rx` — a Python OFDM receiver with a constellation display.
- `Tx` — a minimal OFDM transmitter for Python or MATLAB and USRP.

This directory is intended to serve as the root directory of a standalone
repository. It does not require any files from the parent repository.

## Python dependencies

Python `>=3.10, <3.14 (3.13 recommended)` is required because the receiver depends on the UHD
Python bindings, which are not compatible with Python 3.14 or newer.

The RIS, RX and Python TX launchers use the shared `.venv` in the repository
root. If it is missing, they automatically run `setup_venv.py`, install the
dependencies for the selected component and then start it. An existing
environment with missing dependencies is completed in the same way. Internet
access is needed when packages must be downloaded. Later launches reuse the
environment without reinstalling working packages.

On Windows, install Python with the Python launcher (`py`/`pyw`) or add it to
`PATH`. No user-specific Python path needs to be edited. Setup opens in a
visible console; RIS and RX then open without a console. TX keeps its console
open so that Ctrl+C can stop transmission. On Linux/macOS, setup runs in the
launcher's terminal; install the OS Python venv package if it is not included.

To prepare all three components manually, run from the repository root:

```powershell
py -3.12 setup_venv.py all
```

On Linux or macOS, use a compatible Python 3:

```sh
python3 setup_venv.py all
```

Replace `all` with `ris`, `rx` or `tx` to prepare only one component. The same
command can be rerun after a failed installation. Setup preserves an existing
environment and does not delete it. If an old `.venv` uses an incompatible
Python, rename it and run a launcher to create a new one.

The environment enables system site packages so it can reuse native UHD
bindings installed for the base Python. Missing Python packages are installed
inside `.venv`. UHD drivers/runtime must still be installed separately and
match the Python UHD bindings; pip cannot install the hardware driver.

For a fully manual installation on Windows:

```powershell
py -3.12 -m venv --system-site-packages .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

On Linux or macOS, run:

```sh
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
```

Tkinter is not installed via pip. On Windows, it is usually included with
Python. On Debian or Ubuntu, install it with:

```sh
sudo apt update
sudo apt install python3-tk
```

On Fedora or RHEL-based distributions, use:

```sh
sudo dnf install python3-tkinter
```

On macOS, the Python.org installer includes Tkinter. When using Python from
Homebrew, install the matching package separately, for example:

```sh
brew install python-tk@3.13
```

Replace `3.13` with the installed Python minor version if necessary. The
receiver also requires a working UHD driver and compatible Python bindings for
the installed UHD version. Download the latest UHD driver release from
[Ettus Research](https://files.ettus.com/#/binaries/uhd/latest_release).

## RIS

The port configuration and default values are defined in `Ris/ris_config.py`.
Before starting the application, set `RIS_PORT` in that file to the serial port
used by the RIS device, for example `COM4` on Windows, `/dev/ttyUSB0` on Linux,
or `/dev/cu.usbserial-...` on macOS. If the serial port is not detected, install
the [FTDI Virtual COM Port drivers](https://ftdichip.com/drivers/vcp-drivers/).
The application does not connect to the RIS at startup; the port is opened only
when a pattern is sent.

- Windows: run `Ris/Start_RIS_windows.vbs`.
- Linux: run `sh Ris/Start_RIS_linux.sh`.
- macOS: run `Ris/Start_RIS_macos.command`.

## RX receiver

The radio and OFDM parameters are defined in `Rx/rx_config.py`. Before starting
the receiver, set `RX_IP` in that file to the IP address of the receiving USRP.

- Windows: run `Rx/Start_RX_windows.vbs`.
- Linux: run `sh Rx/Start_RX_linux.sh`.
- macOS: run `Rx/Start_RX_macos.command`.

## TX transmitter

### Python

Set the radio and OFDM parameters in `Tx/tx_config.py`, including `TX_IP` and
the clock source, then start:

- Windows: run `Tx/Start_TX_windows.vbs`.
- Linux: run `sh Tx/Start_TX_linux.sh`.
- macOS: run `Tx/Start_TX_macos.command`.

The launcher prepares `.venv` if needed, then starts continuous transmission
in a console. Press Ctrl+C to stop. Startup errors remain visible until Enter
is pressed.

### MATLAB

The MATLAB transmitter requires MATLAB, Communications Toolbox, and
Communications Toolbox Support Package for USRP Radio. These components are
not installed via pip and are independent of `.venv`.

In MATLAB, navigate to the `Tx` directory and set `cfg.radio.txIPAddress` in
`defaultConfig.m` to the IP address of the transmitting USRP. Adjust any other
radio settings as required, and then run:

```matlab
runTransmitter
```

The script uses only the files located in `Tx` and the `Tx/+ofdm` package.
