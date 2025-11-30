#!/bin/bash

set -o nounset -o pipefail -o errexit

INTERVAL=${INTERVAL-%INTERVAL%}

XDG_STATE_HOME=${XDG_STATE_HOME-$HOME/.local/state}

STATE_DIR=${STATE_DIR-$XDG_STATE_HOME/%APP%}
TARGET=${TARGET-$STATE_DIR/vods}

mkdir -p "$STATE_DIR"

export TWITCH_CLI_LOG_LEVEL=DEBUG

while true; do
    twitch videos >"$TARGET.new"
    mv "$TARGET.new" "$TARGET"

    echo 1>&2 "sleeping for ${INTERVAL}s..."
    sleep "$INTERVAL"
done
