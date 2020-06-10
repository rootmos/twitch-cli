#!/usr/bin/env python3

import os
import uuid
import json
import requests
import dateutil.parser
import time
import concurrent.futures
import subprocess
import sys
import re
import argparse
import tempfile
import socket
import ssl
import select
import errno
import asyncio

from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

client_id = "dqfe0to2kp1pj0yvs3rpvuupdn1u6d"
redirect_host = "localhost"
redirect_port = 37876
redirect_path = "/redirect"
redirect_uri = f"http://{redirect_host}:{redirect_port}{redirect_path}"

helix_url = "https://api.twitch.tv/helix"
kraken_url = "https://api.twitch.tv/kraken"
oauth2_url = "https://id.twitch.tv/oauth2"
irc_addr = ("irc.chat.twitch.tv", 6697)

# utils

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def parse_duration(string):
    p = re.compile("([0-9]+)([dDhHmMsS])")
    secs = 0
    for m in p.finditer(string):
        n = int(m.group(1))
        t = m.group(2)
        if t == "s" or t == "S":
            secs += n
        elif t == "m" or t == "M":
            secs += n * 60
        elif t == "h" or t == "H":
            secs += n * 60 * 60
        elif t == "d" or t == "D":
            secs += n * 60 * 60 * 24
    return secs

def render_duration(secs):
    s = ""

    if secs >= 60 * 60 * 24:
        s += f"{secs // (60 * 60 * 24)}d"
        secs %= 60 * 60 * 24

    if secs >= 60 * 60:
        s += f"{secs // (60 * 60)}h"
        secs %= 60 * 60

    if secs >= 60:
        s += f"{secs // 60}m"
        secs %= 60

    if secs > 0:
        s += f"{secs}s"

    return s

# auth

def new_token(scope):
    state = str(uuid.uuid4())
    q = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "token",
        "scope": scope,
        "state": state,
    }

    url = f"{oauth2_url}/authorize?{urlencode(q)}"

    eprint(url)
    os.system(f"xdg-open '{url}'")

    token = None

    class RequestHandler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def do_GET(self):
            p = urlparse(self.path)

            if p.path != redirect_path:
                self.send_response(404)
                self.send_header("Content-Length", 0)
                self.end_headers()
                return

            body = '<html>' \
                   '<body>' \
                   '<script>' \
                   'var xhr = new XMLHttpRequest();' \
                   'xhr.open("POST", "/token", true);' \
                   'xhr.setRequestHeader("Content-Type", "application/json");' \
                   'xhr.onreadystatechange = function () {' \
                       'if (xhr.readyState === 4 && xhr.status === 204) {' \
                            'document.write("ok");' \
                       '}' \
                   '};' \
                   'p = new URLSearchParams(document.location.hash.substring(1));' \
                   'xhr.send(JSON.stringify({"token": p.get("access_token"), "state": p.get("state")}));' \
                   '</script>' \
                   '</body>' \
                   '</html>'

            body = body.encode("UTF-8")

            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            p = urlparse(self.path)
            if p.path != "/token":
                self.send_response(404)
                self.send_header("Content-Length", 0)
                self.end_headers()
                return

            l = int(self.headers["Content-Length"])
            r = json.loads(self.rfile.read(l))

            if r["state"] != state:
                self.send_response(400)
                self.send_header("Content-Length", 0)
                self.end_headers()
                return

            nonlocal token
            token = r["token"]
            self.send_response(204)
            self.send_header("Content-Length", 0)
            self.end_headers()

    with ThreadingHTTPServer((redirect_host, redirect_port), RequestHandler) as s:
        s.timeout = 0.2
        while token is None:
            s.handle_request()

    if token is None:
        raise RuntimeError("unable to obtain token")

    return token

def get_token(scope):
    p = Path("~/.twitch-cli.json").expanduser()
    if p.exists():
        with p.open() as f: s = json.loads(f.read())
    else:
        s = {}

    if "tokens" not in s: s["tokens"] = {}

    if scope not in s["tokens"]:
        s["tokens"][scope] = new_token(scope)
        with p.open("w") as f: f.write(json.dumps(s))

    return s["tokens"][scope]

# the client

class Client:
    def __init__(self, token=None, scope=None):
        self._me = None
        if token is not None:
            self.token = token
        elif scope is not None:
            self.token = get_token(scope)
        else:
            raise ValueError("specify either token or scope")

    @property
    def me(self):
        if self._me is None:
            h = { "Authorization": f"OAuth {self.token}" }
            r = requests.get(f"{oauth2_url}/validate", headers=h)
            r.raise_for_status()
            j = r.json()
            self._me = User(self, user_name=j["login"], user_id=j["user_id"])
        return self._me

    def put(self, url, body, kraken=False):
        if kraken:
            url = kraken_url + url
            h = {
                "Authorization": f"OAuth {self.token}",
                "Client-ID": client_id,
                "Accept": "application/vnd.twitchtv.v5+json",
            }
        else:
            url = helix_url + url
            h = {
                "Authorization": f"Bearer {self.token}",
                "Client-ID": client_id,
            }

        r = requests.put(url, json=body, headers=h)
        r.raise_for_status()

    def get(self, url, params=None, kraken=False):
        if kraken:
            url = kraken_url + url
            h = {
                "Authorization": f"OAuth {self.token}",
                "Client-ID": client_id,
                "Accept": "application/vnd.twitchtv.v5+json",
            }
        else:
            url = helix_url + url
            h = {
                "Authorization": f"Bearer {self.token}",
                "Client-ID": client_id,
            }

        while True:
            r = requests.get(url, params=params, headers=h)
            if r.status_code == 429:
                l = r.headers["Ratelimit-Limit"]
                t = int(r.headers["Ratelimit-Reset"])
                w = (t - time.time()) / 10
                eprint(f"calm down! limit={l} reset={t} wait={w}")
                time.sleep(w)
                continue

            r.raise_for_status()
            return r.json()

    def streams(self, user):
        try:
            users = list(user)
        except TypeError:
            users = [user]

        ss = []
        while len(users) > 0:
            p = { "user_id": [u.user_id for u in users[:100]] }
            while True:
                j = self.get("/streams", params=p)
                for i in j["data"]:
                    ss.append(Stream.from_twitch_json(self, i))
                if "cursor" not in j["pagination"]: break
                p["after"] = j["pagination"]["cursor"]
            users = users[100:]

        return ss

    def user(self, *names):
        us = []
        while len(names) > 0:
            p = { "login": names[:100] }
            j = self.get("/users", params=p)
            for i in j["data"]:
                us.append(User.from_twitch_json(self, i))
            names = names[100:]

        return us

    def channel(self, id):
        return Channel.from_twitch_json(self, self.get(f"/channels/{id}", kraken=True))

class User:
    def __init__(self, client, user_id, user_name, title=None):
        self.client = client
        self.user_id = user_id
        self.user_name = user_name
        self._channel = None

    def __str__(self):
        return self.user_name

    def __repr__(self):
        return f"{self.user_name} ({self.user_id})"

    @staticmethod
    def from_twitch_json(client, j):
        if "login" in j:
            return User(client, user_id=j["id"], user_name=j["login"])
        else:
            return User(client, user_id=j["user_id"], user_name=j["user_name"])

    @property
    def channel(self):
        if self._channel is None:
            self._channel = self.client.channel(self.user_id)

        return self._channel

    def following(self):
        p = { "from_id": self.user_id, "first": 100 }
        us = []
        while True:
            j = self.client.get("/users/follows", params=p)
            for i in j["data"]:
                us.append(User(self.client, user_id=i["to_id"], user_name=i["to_name"]))

            if len(us) == j["total"]: break

            p["after"] = j["pagination"]["cursor"]

        return us

    def videos(self, since=None):
        p = { "user_id": self.user_id, "first": 10, "sort": "time" }
        vs = []
        while True:
            j = self.client.get("/videos", params=p)
            for i in j["data"]:
                v = Video.from_twitch_json(self, i)
                if since is not None and v.created_at < since:
                    return vs
                vs.append(v)

            if "cursor" not in j["pagination"]: break
            p["after"] = j["pagination"]["cursor"]

        return vs

class Channel:
    def __init__(self, client, channel_id, status, game, followers, views):
        self.client = client
        self.channel_id = channel_id
        self._status = status
        self._game = game
        self.followers = followers
        self.views = views

    def _setter(self, k, v):
        self.client.put(
            f"/channels/{self.channel_id}",
            body={f"channel[{k}]": v},
            kraken=True,
        )
        return v

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, v):
        self._status = self._setter("status", v)

    @property
    def game(self):
        return self._game

    @game.setter
    def game(self, v):
        self._game = self._setter("game", v)

    @staticmethod
    def from_twitch_json(client, j):
        return Channel(client,
            channel_id = j["_id"],
            status = j["status"],
            game = j["game"],
            followers = j["followers"],
            views = j["views"],
        )

    def to_dict(self):
        return {
            "channel_id": self.channel_id,
            "title": self.status,
            "category": self.game,
            "followers": self.followers,
            "views": self.views,
        }

class Video:
    def __init__(self, client, video_id, title, user, url, created_at, published_at, duration, typ):
        self.client = client
        self.video_id = video_id
        self.title = title
        self.user = user
        self.url = url
        self.created_at = created_at
        self.published_at = published_at
        self.duration = duration
        self.typ = typ

    def __str__(self):
        return self.title

    def __repr__(self):
        return f"{self.user.user_name}: {self.title} ({self.video_id})"

    def from_twitch_json(client, j):
        if "created_at" in j and j["created_at"] is not None:
            created_at = dateutil.parser.isoparse(j["created_at"])
        else:
            created_at = None

        if "published_at" in j and j["published_at"] is not None:
            published_at = dateutil.parser.isoparse(j["published_at"])
        else:
            published_at = None

        return Video(client,
            video_id=j["id"],
            title=j["title"],
            url=j["url"],
            user=User.from_twitch_json(client, j),
            created_at=created_at,
            published_at=published_at,
            duration=parse_duration(j["duration"]),
            typ=j["type"],
        )

    def to_dict(self):
        return {
            "video_id": self.video_id,
            "user_id": self.user.user_id,
            "user_name": self.user.user_name,
            "created_at": self.created_at.isoformat(),
            "published_at": self.published_at.isoformat(),
            "title": self.title,
            "url": self.url,
            "type": self.typ,
            "duration": self.duration,
            "duration_human": render_duration(self.duration),
        }

class Stream:
    def __init__(self, client, user, title):
        self.client = client
        self.user = user
        self.title = title

    def __str__(self):
        return self.title

    def __repr__(self):
        return f"{self.user.user_name}: {self.title}"

    @property
    def url(self):
        return f"https://twitch.tv/{self.user.user_name}"

    def from_twitch_json(client, j):
        return Stream(client,
            title=j["title"],
            user=User.from_twitch_json(client, j),
        )

def tabularize(rows, pad=" ", sep=" "):
    if len(rows) == 0:
        return []

    s = [0] * max([len(r) for r in rows])
    for r in rows:
        for i, c in enumerate(r):
            s[i] = max(s[i], len(c))

    ls = []
    for r in rows:
        l = ""
        for i, c in enumerate(r):
            if i + 1 < len(r):
                l += c.ljust(s[i], pad[0]) + sep
            else:
                l += c
        ls.append(l)
    return ls

def dmenu(choices, lines=20):
    d = {}
    if all([isinstance(c, tuple) for c in choices]):
        cs = tabularize([l for (l, v) in choices])
        for i, c in enumerate(cs):
            d[c] = choices[i][1]
        stdin = '\n'.join(cs)
    else:
        for c in choices:
            d[c] = c
        stdin = '\n'.join(choices)

    p = subprocess.Popen(f"dmenu -l {lines}", shell=True, text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    (selection, _) = p.communicate(input=stdin)
    vs = []
    for l in selection.splitlines():
        vs.append(d[l])
    return vs

def parse_args(args):
    parser = argparse.ArgumentParser(description='Twitch command line interface')
    parser.add_argument("--following", help="print channels you're following", action="store_true")
    parser.add_argument("--menu", help="run dmenu", action="store_true")
    parser.add_argument("--json", help="output json", action="store_true")
    parser.add_argument("--menu-lines", type=int, default=20, help="number of maximum lines in the menu")
    parser.add_argument("--chat", action="store_true", help="interact with chat")
    parser.add_argument("--title-max-length", type=int, default=80, help="maximum length of printed titles")
    parser.add_argument('channels', metavar='CHANNEL', nargs='*',
                        help='channel to act on (defaults to followed channels)')
    parser.add_argument('--since', type=int, default=3, help='days to list videos')
    return parser.parse_args(args)

def parse_manager_args(args):
    parser = argparse.ArgumentParser(sys.argv[0] + " --manage", description='Twitch stream manager command line interface')
    parser.add_argument("--title", action="store_true", help="print stream title")
    parser.add_argument("--set-title", metavar="TITLE", help="set stream title")
    parser.add_argument("--edit-title", action="store_true", help="edit stream title using $EDITOR")
    parser.add_argument("--category", action="store_true", help="print stream category")
    parser.add_argument("--set-category", metavar="CATEGORY", help="set stream category")
    parser.add_argument("--json", help="output json", action="store_true")
    return parser.parse_args(args)

def edit(v):
    with tempfile.NamedTemporaryFile() as f:
        f.write(bytes(v, "UTF-8"))
        f.flush()

        e = os.getenv("EDITOR", "vi")
        if e == "vi" or e == "vim":
            os.system(f"{e} -b {f.name}")
        else:
            os.system(f"$EDITOR -b {f.name}")

        f.seek(0)
        return str(f.read(), "UTF-8")


def run_manager(args):
    c = None
    run_default_action = True

    if args.edit_title:
        c = c or Client(scope="channel_editor")
        c.me.channel.status = edit(c.me.channel.status)
        run_default_action = False

    if args.set_title is not None:
        c = c or Client(scope="channel_editor")
        c.me.channel.status = args.set_title
        run_default_action = False

    if args.set_category is not None:
        c = c or Client(scope="channel_editor")
        c.me.channel.game = args.set_category
        run_default_action = False

    c = c or Client(scope="")
    if args.title or args.category:
        if args.title:
            s = c.me.channel.status
            print(json.dumps(s) if args.json else s)
        if args.category:
            s = c.me.channel.game
            print(json.dumps(s) if args.json else s)
    elif run_default_action:
        d = c.me.channel.to_dict()
        if args.json:
            print(json.dumps(d))
        else:
            for k, v in d.items():
                print(f"{k}: {v}")

class IRCMessage:
    def __init__(self, bs):
        self.raw = bs
        s = str(bs, "UTF-8")
        self.tags, s = IRCMessage.__parse_tags(s)
        self.prefix, s = IRCMessage.__parse_prefix(s)
        self.command, s = IRCMessage.__parse_command(s)
        self.params, self.trailing = IRCMessage.__parse_params(s, [])

    def __repr__(self):
        props = []
        if self.prefix is not None: props.append(f"prefix={self.prefix}")
        if self.tags is not None: props.append(f"tags={self.tags}")
        if self.command is not None: props.append(f"command={self.command}")
        if len(self.params) > 0: props.append(f"params={self.params}")
        if self.trailing is not None: props.append(f"trailing={self.trailing}")
        return f"IRCMessage({','.join(props)})"

    def __parse_prefix(s):
        if s[0] == ':':
            i = s.index(' ')
            return s[1:i], s[i:]
        else:
            return s

    def __parse_command(s):
        m = re.match("([ ]+)(\w+)|(\d\d\d) ", s)
        cmd = m.group(2)
        return cmd, s[len(m.group(1)) + len(cmd):]

    def __parse_params(s, acc):
        if re.fullmatch("[ ]*", s):
            return acc, None

        m = re.fullmatch("[ ]*:(.*)", s)
        if m:
            return acc, m.group(1)
        else:
            m = re.match("[ ]*([^ :][^ ]*)(.*)", s)
            if m is None:
                raise ValueError(f"<params> don't match: {s}")
            middle = m.group(1)
            acc.append(middle)
            return IRCMessage.__parse_params(m.group(2), acc)

    def __parse_tags(s):
        if s[0] != '@':
            return {}, s
        else:
            return IRCMessage.__parse_tag(s[1:], {})

    def __parse_tag(s, acc):
        p = re.compile("(\\+?([a-zA-Z0-9\\-]+/)?[a-zA-Z0-9\\-]+)(=([^ ;]*))?[ ;]")
        m = p.match(s)
        if m is None: return acc, s
        acc[m.group(1)] = m.group(4)
        return IRCMessage.__parse_tag(s[m.end(0):], acc)

class Chat:
    def __init__(self, *channels):
        self.client = Client(scope="chat:read")

        if len(channels) == 0:
            self.channels = [self.client.me.user_name]
        else:
            self.channels = [ u.user_name for u in self.client.user(*channels) ]

    async def run(self, callback):
        q = asyncio.Queue()

        async def send_line(line):
            q.put_nowait(bytes(line + "\r\n", "UTF-8"))

        await send_line(f"PASS oauth:{self.client.token}")
        await send_line(f"NICK {self.client.me.user_name}")
        await send_line("CAP REQ :twitch.tv/membership")
        await send_line("CAP REQ :twitch.tv/commands")
        await send_line("CAP REQ :twitch.tv/tags")

        for c in self.channels:
            await send_line(f"JOIN #{c}")

        r, w = await asyncio.open_connection(
            host = irc_addr[0], port = irc_addr[1],
            family = socket.AF_INET,
            ssl = True
        )

        async def do_read():
            bs = await r.readuntil(separator=b'\r\n')
            await callback(self, IRCMessage(bs), send_line)
            await do_read()

        async def do_write():
            w.write(await q.get())
            q.task_done()
            await do_write()

        await asyncio.gather(do_read(), do_write())

async def handle_twitch_chat_message(chat, msg, send_line):
    if msg.command == "PING":
        chat.send_line(f"PONG {msg.trailing}")
        return

    if msg.command != "PRIVMSG":
        return

    d = datetime.fromtimestamp(int(msg.tags["tmi-sent-ts"])/1000)
    d = d.isoformat(timespec='seconds')
    u = msg.tags["display-name"]

    if len(chat.channels) > 1:
        print(f"{d} {msg.params[0]} {u}: {msg.trailing}")
    else:
        print(f"{d} {u}: {msg.trailing}")

if __name__ == "__main__":
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--manage", action="store_true")
    (a, args) = p.parse_known_args()

    if a.manage:
        run_manager(parse_manager_args(args))
        sys.exit(0)
    else:
        args = parse_args(args)

    if args.chat:
        asyncio.run(Chat(*args.channels).run(handle_twitch_chat_message))
        sys.exit(0)

    c = Client(scope="")

    if args.following:
        fs = c.me.following()
        if args.menu:
            for c in dmenu([f.user_name for f in fs], lines=args.menu_lines): print(c)
        else:
            if args.json:
                for f in fs: print('"' + f.user_name + '"')
            else:
                for f in fs: print(f.user_name)
        sys.exit(0)

    if len(args.channels) > 0:
        fs = c.user(args.channels)
    else:
        fs = c.me.following()

    since = datetime.now(timezone.utc) - timedelta(days=args.since)

    vs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        for f in [ ex.submit(lambda f: f.videos(since=since), f) for f in fs ]:
            vs += f.result()
    vs = sorted(vs, key=lambda v: v.created_at, reverse=True)

    if args.json:
        for v in vs: print(json.dumps(v.to_dict()))
        sys.exit(0)

    def clean_title(t):
        t = t.replace('\n', ' ')
        t = t.encode("ascii", "ignore")
        return str(t[:args.title_max_length], "ascii")

    choices = []
    for s in c.streams(fs):
        choices.append(((s.user.user_name, "", "", clean_title(s.title)), s.url))
    for v in vs:
        choices.append(((v.user.user_name, render_duration(v.duration), v.typ[0], clean_title(v.title)), v.url))

    if args.menu:
        for c in dmenu(choices, lines=args.menu_lines): print(c)
    else:
        for l in tabularize([r + (u,) for (r, u) in choices]): print(l)
