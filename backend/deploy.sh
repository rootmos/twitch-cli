#!/bin/bash

set -o nounset -o pipefail -o errexit

. ./.env

TMP=$(mktemp -d)
trap 'rm -rf $TMP' EXIT

NAME=twitch-cli-backend

upload() {
    scp -i "$KEYFILE" "$1" "$2"
}

SALT=$(date +%FT%H%M%S%z).$(uuidgen)

remote() {
    SCRIPT=$NAME.$SALT.sh
    echo "#!/bin/sh -x" > "$TMP/$SCRIPT"
    cat >> "$TMP/$SCRIPT"
    chmod +x "$TMP/$SCRIPT"

    upload "$TMP/$SCRIPT" "$TARGET:$SCRIPT"
    ssh -t -t -i "$KEYFILE" "$TARGET" "./$SCRIPT"
}

ACTION=${1-}

if [ "$ACTION" = "prepare" ]; then
    remote <<EOF
sudo apt-get update
sudo apt-get install --yes build-essential python3-venv python3-dev
EOF
    exit 0
elif [ "$ACTION" = "ssh" ]; then
    ssh -i "$KEYFILE" "$TARGET"
    exit 0
elif [ "$ACTION" = "stop" ]; then
    remote <<< "pkill python"
    exit 0
fi

TARBALL=bundle.$SALT.tar.gz
git ls . | tar -c -f "$TMP/$TARBALL" -T-
upload "$TMP/$TARBALL" "$TARGET:$TARBALL"
remote <<EOF
mkdir -p "$NAME"
tar -xf "$TARBALL" -C "$NAME"
make -C "$NAME" $@
EOF
