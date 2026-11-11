# Camera-ready RIS/OFDM demo

Pakiet zawiera trzy niezależne komponenty:

- `Ris` - sterowanie RIS przez port szeregowy, wzorce i wykresy biegunowe.
- `Rx` - odbiornik OFDM w Pythonie z podglądem konstelacji.
- `Tx` - minimalny nadajnik OFDM dla MATLAB-a i USRP.

Katalog jest przygotowany jako katalog główny osobnego repozytorium. Nie wymaga
plików z nadrzędnego repozytorium.

## Środowisko Python

Utwórz środowisko w katalogu głównym pakietu:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Na Linuxie lub macOS użyj `.venv/bin/python`. Tkinter nie jest instalowany przez
pip; na Windowsie jest zwykle częścią Pythona, a na Linuxie może wymagać pakietu
systemowego, np. `python3-tk`. Odbiornik wymaga także działającego sterownika UHD
i zgodnych Python bindings dla używanej wersji UHD.

## RIS

Konfiguracja portu i wartości domyślne znajdują się na początku
`Ris/ris_control_gui.py`. Program nie łączy się z RIS-em podczas uruchamiania;
port jest otwierany dopiero przy wysłaniu wzorca.

- Windows: uruchom `Ris/Start_RIS_windows.vbs`.
- Linux: uruchom `sh Ris/Start_RIS_linux.sh`.
- macOS: uruchom `Ris/Start_RIS_macos.command`.

## Odbiornik RX

Parametry radia i OFDM znajdują się w `Rx/rx_config.py`.

- Windows: uruchom `Rx/Start_RX_windows.vbs`.
- Linux: uruchom `sh Rx/Start_RX_linux.sh`.
- macOS: uruchom `Rx/Start_RX_macos.command`.

## Nadajnik TX

Nadajnik wymaga MATLAB-a, Communications Toolbox oraz Communications Toolbox
Support Package for USRP Radio. Te składniki nie są instalowane przez pip.

W MATLAB-ie przejdź do katalogu `Tx`, dostosuj ustawienia radia w
`defaultConfig.m`, a następnie uruchom:

```matlab
runTransmitter
```

Skrypt korzysta wyłącznie z plików znajdujących się w `Tx` i pakiecie
`Tx/+ofdm`.
