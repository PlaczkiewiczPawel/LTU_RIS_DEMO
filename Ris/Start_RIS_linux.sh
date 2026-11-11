#!/bin/sh
set -eu

script_directory=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repository=$(CDPATH='' cd -- "$script_directory/.." && pwd)
python="$repository/.venv/bin/python"

if [ ! -x "$python" ]; then
    printf '%s\n' "Python environment not found: $python" \
        "Prepare the repository .venv with Tk and PySerial first." >&2
    exit 1
fi

cd -- "$script_directory"
exec "$python" "$script_directory/launch_ris.py"
