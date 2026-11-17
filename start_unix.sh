#!/bin/sh
set -eu

repository=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
component=${1:?Specify ris, rx or tx}
case "$component" in ris|rx|tx) ;; *) exit 1 ;; esac

for python in "$repository/.venv/bin/python" python3.13 python3.12 python3.11 python3.10 python3 python; do
    if "$python" -c 'import sys; sys.exit(not ((3, 10) <= sys.version_info[:2] < (3, 14)))' 2>/dev/null; then
        exec "$python" "$repository/launch_app.py" "$component"
    fi
done

printf '%s\n' 'Python 3.10-3.13 was not found. Install Python with venv and Tk support, then retry.' >&2
exit 1
