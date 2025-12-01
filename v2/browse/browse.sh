#!/bin/bash

set -o nounset -o pipefail -o errexit

XDG_DATA_HOME=${XDG_DATA_HOME-$HOME/.local/share}
XDG_STATE_HOME=${XDG_STATE_HOME-$HOME/.local/state}

DATA_DIR=${DATA_DIR-$XDG_DATA_HOME/%APP%}
STATE_DIR=${STATE_DIR-$XDG_STATE_HOME/%APP%}

exec nvim -R "$STATE_DIR/${1-live}" -S "$DATA_DIR/main.lua"
