#!/bin/sh
script_directory=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
exec /bin/sh "$script_directory/../start_unix.sh" tx
