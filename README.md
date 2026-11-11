# Camera-ready RIS/OFDM demo

The package contains three independent components:

- `Ris` — RIS control via a serial port, patterns, and polar plots.
- `Rx` — a Python OFDM receiver with a constellation display.
- `Tx` — a minimal OFDM transmitter for MATLAB and USRP.

This directory is intended to serve as the root directory of a standalone
repository. It does not require any files from the parent repository.

## Python environment

Create a virtual environment in the package's root directory:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

On Linux or macOS, use `.venv/bin/python`. Tkinter is not installed via pip;
on Windows, it is usually included with Python, while on Linux it may require
a system package such as `python3-tk`. The receiver also requires a working UHD
driver and compatible Python bindings for the installed UHD version.

## RIS

The port configuration and default values are defined in `Ris/ris_config.py`.
The application does not connect to the RIS at startup; the port is opened only
when a pattern is sent.

- Windows: run `Ris/Start_RIS_windows.vbs`.
- Linux: run `sh Ris/Start_RIS_linux.sh`.
- macOS: run `Ris/Start_RIS_macos.command`.

## RX receiver

The radio and OFDM parameters are defined in `Rx/rx_config.py`.

- Windows: run `Rx/Start_RX_windows.vbs`.
- Linux: run `sh Rx/Start_RX_linux.sh`.
- macOS: run `Rx/Start_RX_macos.command`.

## TX transmitter

The transmitter requires MATLAB, Communications Toolbox, and Communications
Toolbox Support Package for USRP Radio. These components are not installed via
pip.

In MATLAB, navigate to the `Tx` directory, adjust the radio settings in
`defaultConfig.m`, and then run:

```matlab
runTransmitter
```

The script uses only the files located in `Tx` and the `Tx/+ofdm` package.
