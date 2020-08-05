# [Twitch](https://twitch.tv) command line interface

## Features
* manage followed channels
* list videos and active streams of channels
* [dmenu](https://tools.suckless.org/dmenu/) integration to select channels,
  videos or streams
* manage stream metadata: title, category
* lurk in chat or interact using per channel unix sockets:
  - `twitch-cli --chat rootmos2` in one terminal and
    `socat readline unix:~/.twitch-cli/channel/rootmos2` in another
    ([tmux](https://tmux.github.io/) sounds perfect for this, no?)
* follow channels activity: follows and stream up/down events

## Example
The menu option makes for a simple Twitch GUI when paired
with a media player that support Twitch URLs
(I recommend [mpv](https://mpv.io/) and [youtube-dl](https://youtube-dl.org/)).
```shell
twitch-cli list --menu | xargs mpv
```

For a more sophisticated/klickety-klick GUI check out:
[streamlink-twitch-gui](https://streamlink.github.io/streamlink-twitch-gui/),
however it doesn't list videos (at the time of writing).

## Usage
```
usage: twitch-cli [-h] [--log LOG] [--config-path CONFIG_PATH]
                  [--token-path TOKEN_PATH]
                  {activity,follow,unfollow,following,list,live,chat,stream}
                  ...

Twitch command line interface

positional arguments:
  {activity,follow,unfollow,following,list,live,chat,stream}
                        sub-commands
    activity            activity feed
    follow              follow channel(s)
    unfollow            unfollow user(s)
    following           list followed users
    list (live)         list live streams and videos (default)
    chat                interact with chat
    stream              manage stream

optional arguments:
  -h, --help            show this help message and exit
  --log LOG             set log level
  --config-path CONFIG_PATH
                        configuration base path (default: ~/.twitch-cli)
  --token-path TOKEN_PATH
                        token path (default: CONFIG_PATH/tokens.json)
```

### list
```
usage: twitch-cli list [-h] [--live] [--since SINCE] [--exclude PATH]
                       [--title-max-length TITLE_MAX_LENGTH] [--json] [--menu]
                       [--menu-lines MENU_LINES]
                       [CHANNEL [CHANNEL ...]]

positional arguments:
  CHANNEL               list streams and videos of CHANNEL (defaults to
                        followed channels)

optional arguments:
  -h, --help            show this help message and exit
  --live                list only live streams (synonym for --since=0)
  --since SINCE         days to list videos
  --exclude PATH        exclude channel if it appears in the specified file
                        (default: CONFIG_PATH/exclude)
  --title-max-length TITLE_MAX_LENGTH
                        maximum length of printed titles
  --json                output json
  --menu                run dmenu
  --menu-lines MENU_LINES
                        number of maximum lines in the menu
```

### chat
```
usage: twitch-cli chat [-h] [--input-path PATH] [--read-only] [--join-parts]
                       [CHANNEL [CHANNEL ...]]

positional arguments:
  CHANNEL            join CHANNEL's chat

optional arguments:
  -h, --help         show this help message and exit
  --input-path PATH  create chat input channel at PATH/CHANNEL (default:
                     CONFIG_PATH/channel)
  --read-only        lurker mode
  --join-parts       display who joins and leaves the chat
```

### activity
```
usage: twitch-cli activity [-h] [--event [EVENT [EVENT ...]]]
                           [--notify-live [COMMAND]]
                           [--notify-follow [COMMAND]]
                           CHANNEL [CHANNEL ...]

positional arguments:
  CHANNEL               follow activity feed of CHANNEL

optional arguments:
  -h, --help            show this help message and exit
  --event [EVENT [EVENT ...]]
                        event types: live,follow
  --notify-live [COMMAND]
                        command to run when channel goes live (%c replaced
                        with channel name, %t with the stream title)
  --notify-follow [COMMAND]
                        command to run when channel goes live (%c is replaced
                        with channel name, %u with user name)
```

### stream
```
usage: twitch-cli stream [-h]
                         {title,set-title,edit-title,category,set-category,edit-category,status}
                         ...

positional arguments:
  {title,set-title,edit-title,category,set-category,edit-category,status}
                        management actions
    title               print stream title
    set-title           set stream title
    edit-title          edit stream title using $EDITOR
    category            print stream category
    set-category        set stream category
    edit-category       edit stream category using $EDITOR
    status              print stream status

optional arguments:
  -h, --help            show this help message and exit
```
