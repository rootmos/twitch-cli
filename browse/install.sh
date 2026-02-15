#!/bin/bash

set -o nounset -o pipefail -o errexit

XDG_DATA_HOME=${XDG_DATA_HOME-$HOME/.local/share}
XDG_CONFIG_HOME=${XDG_CONFIG_HOME-$HOME/.config}

APP=${APP-"browse-twitch"}
TITLE_WIDTH=${TITLE_WIDTH-80}
DATA_DIR=${DATA_DIR-$XDG_DATA_HOME/$APP}
BIN_DIR=${BIN_DIR-$HOME/.local/bin}
UNITS_DIR=${UNITS_DIR-$XDG_CONFIG_HOME/systemd/user}

TMP=$(mktemp -d)
trap 'rm -rf $TMP' EXIT

fix() {
    if [ -f "$1" ]; then
        sed -i 's/%APP%/'"$APP"'/' "$1"
        sed -i 's,%SERVICE_PY%,'"$DATA_DIR/service.py"',' "$1"
        sed -i 's,%TITLE_WIDTH%,'"$TITLE_WIDTH"',' "$1"
    fi
}

SCRIPT_DIR=$(readlink -f "$0" | xargs dirname)
cd "$SCRIPT_DIR"

ROOT=$TMP/root
mkdir -p "$ROOT" "$ROOT/$DATA_DIR" "$ROOT/$BIN_DIR" "$ROOT/$UNITS_DIR"
cp -v service.py main.lua "$ROOT/$DATA_DIR"
cp -v browse.sh "$ROOT/$BIN_DIR/$APP"
cp -v service.unit "$ROOT/$UNITS_DIR/$APP.service"

find "$ROOT" -type f -print0 | while IFS= read -r -d '' f; do
    fix "$f"
done

TARBALL="$TMP/$APP.tar.gz"
tar czvf "$TARBALL" -C "$ROOT" .
if [ -z "${DRY_RUN-}" ]; then
    tar xvf "$TARBALL" -C / || true
    systemctl --user daemon-reload
    systemctl --user restart "$APP"
    systemctl --user status "$APP"
    journalctl --user -fu "$APP"
fi
