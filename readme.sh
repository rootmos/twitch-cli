#!/bin/bash

set -o nounset -o pipefail -o errexit

OUT=README.md

cat <<EOF > "$OUT"
# [Twitch](https://twitch.tv) command line interface

## Features
* list followed channels
* list videos and active streams of channels
* [dmenu](https://tools.suckless.org/dmenu/) integration to select channels,
  videos or streams

## Example
The menu option makes for a simple Twitch GUI when paired
with a media player that support Twitch URLs
(I recommend [mpv](https://mpv.io/) and [youtube-dl](https://youtube-dl.org/)).
\`\`\`shell
./cli.py --menu | xargs mpv
\`\`\`

For a more sophisticated/klickety-klick GUI check out:
[streamlink-twitch-gui](https://streamlink.github.io/streamlink-twitch-gui/),
however it doesn't list videos (at the time of writing).

## Usage
\`\`\`
EOF
./cli.py -h >> "$OUT" 2>&1

cat <<EOF >> "$OUT"
\`\`\`
EOF
