#!/bin/sh
script_directory=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
exec /bin/sh "$script_directory/Start_TX_linux.sh"
