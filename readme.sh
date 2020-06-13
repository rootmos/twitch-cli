#!/bin/bash

set -o nounset -o pipefail -o errexit

OUT=README.md
TARGET=twitch-cli
PATH=.:$PATH

cat <<EOF | tee "$OUT"
# [Twitch](https://twitch.tv) command line interface

## Features
* manage followed channels
* list videos and active streams of channels
* [dmenu](https://tools.suckless.org/dmenu/) integration to select channels,
  videos or streams
* manage stream metadata: title, category
* read chat

## Example
The menu option makes for a simple Twitch GUI when paired
with a media player that support Twitch URLs
(I recommend [mpv](https://mpv.io/) and [youtube-dl](https://youtube-dl.org/)).
\`\`\`shell
$TARGET --menu | xargs mpv
\`\`\`

For a more sophisticated/klickety-klick GUI check out:
[streamlink-twitch-gui](https://streamlink.github.io/streamlink-twitch-gui/),
however it doesn't list videos (at the time of writing).

## Usage
\`\`\`
EOF
$TARGET -h 2>&1 | tee -a "$OUT"

cat <<EOF | tee -a "$OUT"
\`\`\`
### Stream manager
\`\`\`
EOF
$TARGET --manage -h 2>&1 | tee -a "$OUT"

cat <<EOF | tee -a "$OUT"
\`\`\`
EOF
