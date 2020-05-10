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
import argparse

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
oauth2_url = "https://id.twitch.tv/oauth2"

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def new_token(scope):
    state = str(uuid.uuid4())
    q = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "token",
        "scope": scope,
        "state": state,
    }

    url = "{oauth2_url}/authorize?" + urlencode(q)

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

class Client:
    def __init__(self, token=None, scope=None):
        if token is not None:
            self.token = token
        elif scope is not None:
            self.token = get_token(scope)
        else:
            raise ValueError("specify either token or scope")

    def me(self):
        h = { "Authorization": f"OAuth {self.token}" }
        r = requests.get(f"{oauth2_url}/validate", headers=h)
        r.raise_for_status()
        j = r.json()
        return User(self, user_name=j["login"], user_id=j["user_id"])

    def get(self, url, params=None):
        h = { "Authorization": f"Bearer {self.token}", "Client-ID": client_id }
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
                j = self.get(f"{helix_url}/streams", params=p)
                for i in j["data"]:
                    ss.append(Stream.from_json(self, i))
                if "cursor" not in j["pagination"]: break
                p["after"] = j["pagination"]["cursor"]
            users = users[100:]

        return ss

    def user(self, name):
        try:
            names = list(name)
        except TypeError:
            names = [name]

        us = []
        while len(names) > 0:
            p = { "login": names[:100] }
            j = self.get(f"{helix_url}/users", params=p)
            for i in j["data"]:
                us.append(User.from_json(self, i))
            names = names[100:]

        return us

class User:
    def __init__(self, client, user_id, user_name):
        self.client = client
        self.user_id = user_id
        self.user_name = user_name

    def __str__(self):
        return self.user_name

    def __repr__(self):
        return f"{self.user_name} ({self.user_id})"

    def from_json(client, j):
        if "login" in j:
            return User(client, user_id=j["id"], user_name=j["login"])
        else:
            return User(client, user_id=j["user_id"], user_name=j["user_name"])

    def following(self):
        p = { "from_id": self.user_id, "first": 100 }
        us = []
        while True:
            j = self.client.get(f"{helix_url}/users/follows", params=p)
            for i in j["data"]:
                us.append(User(self.client, user_id=i["to_id"], user_name=i["to_name"]))

            if len(us) == j["total"]: break

            p["after"] = j["pagination"]["cursor"]

        return us

    def videos(self, since=None):
        p = { "user_id": self.user_id, "first": 10, "sort": "time" }
        vs = []
        while True:
            j = self.client.get(f"{helix_url}/videos", params=p)
            for i in j["data"]:
                v = Video.from_json(self, i)
                if since is not None and v.created_at < since:
                    return vs
                vs.append(v)

            if "cursor" not in j["pagination"]: break
            p["after"] = j["pagination"]["cursor"]

        return vs

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

    def from_json(client, j):
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
            user=User.from_json(client, j),
            created_at=created_at,
            published_at=published_at,
            duration=j["duration"],
            typ=j["type"],
        )

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

    def from_json(client, j):
        return Stream(client,
            title=j["title"],
            user=User.from_json(client, j),
        )

def tabularize(rows, pad=" ", sep=" "):
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
        for c in choices:
            d[c[0]] = c[1]
        stdin = '\n'.join(tabularize([l for (l, v) in choices]))
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

def parse_args():
    parser = argparse.ArgumentParser(description='Twitch command line interface')
    parser.add_argument("--following", help="print channels you're following", action="store_true")
    parser.add_argument("--menu", help="run dmenu", action="store_true")
    parser.add_argument("--menu-lines", type=int, default=20, help="number of maximum lines in the menu")
    parser.add_argument("--title-max-length", type=int, default=80, help="maximum length of printed titles")
    parser.add_argument('channels', metavar='CHANNEL', nargs='*',
                        help='channel to act on (defaults to followed channels)')
    parser.add_argument('--since', type=int, default=3, help='days to list videos')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    c = Client(scope="")

    if args.following:
        fs = c.me().following()
        if args.menu:
            for c in dmenu([f.user_name for f in fs], lines=args.menu_lines): print(c)
        else:
            for f in fs: print(f.user_name)
        sys.exit(0)

    if len(args.channels) > 0:
        fs = c.user(args.channels)
    else:
        fs = c.me().following()

    since = datetime.now(timezone.utc) - timedelta(days=args.since)

    vs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        for f in [ ex.submit(lambda f: f.videos(since=since), f) for f in fs ]:
            vs += f.result()
    vs = sorted(vs, key=lambda v: v.created_at, reverse=True)

    def clean_title(t):
        t = t.replace('\n', ' ')
        t = t.encode("ascii", "ignore")
        return str(t[:args.title_max_length], "ascii")

    choices = []
    for s in c.streams(fs):
        choices.append(((s.user.user_name, "", "", clean_title(s.title)), s.url))
    for v in vs:
        choices.append(((v.user.user_name, v.duration, v.typ[0], clean_title(v.title)), v.url))

    if args.menu:
        for c in dmenu(choices, lines=args.menu_lines): print(c)
    else:
        for l in tabularize([r + (u,) for (r, u) in choices]): print(l)
