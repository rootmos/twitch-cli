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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

client_id = "dqfe0to2kp1pj0yvs3rpvuupdn1u6d"
redirect_host = "localhost"
redirect_port = 37876
redirect_path = "/redirect"
redirect_uri = f"http://{redirect_host}:{redirect_port}{redirect_path}"

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

    url = "https://id.twitch.tv/oauth2/authorize?" + urlencode(q)

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
        r = requests.get("https://id.twitch.tv/oauth2/validate", headers=h)
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
                j = self.get("https://api.twitch.tv/helix/streams", params=p)
                for i in j["data"]:
                    ss.append(Stream.from_json(self, i))
                if "cursor" not in j["pagination"]: break
                p["after"] = j["pagination"]["cursor"]
            users = users[100:]

        return ss

class User:
    def __init__(self, client, user_id, user_name):
        self.client = client
        self.user_id = user_id
        self.user_name = user_name

    def __str__(self):
        return self.user_name

    def __repr__(self):
        return f"{self.user_name} ({self.user_id})"

    def following(self):
        p = { "from_id": self.user_id, "first": 100 }
        us = []
        while True:
            j = self.client.get("https://api.twitch.tv/helix/users/follows", params=p)
            for i in j["data"]:
                us.append(User(self.client, user_id=i["to_id"], user_name=i["to_name"]))

            if len(us) == j["total"]: break

            p["after"] = j["pagination"]["cursor"]

        return us

    def videos(self, since=None):
        p = { "user_id": self.user_id, "first": 10, "sort": "time" }
        vs = []
        while True:
            j = self.client.get("https://api.twitch.tv/helix/videos", params=p)
            for i in j["data"]:
                v = Video.from_json(self, i)
                if since is not None and v.created_at < since:
                    return vs
                vs.append(v)

            if "cursor" not in j["pagination"]: break
            p["after"] = j["pagination"]["cursor"]

        return vs

class Video:
    def __init__(self, client, video_id, title, user, url, created_at, published_at, duration):
        self.client = client
        self.video_id = video_id
        self.title = title
        self.user = user
        self.url = url
        self.created_at = created_at
        self.published_at = published_at
        self.duration = duration

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
            user=User(client, user_id=j["user_id"], user_name=j["user_name"]),
            created_at=created_at,
            published_at=published_at,
            duration=j["duration"],
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
            user=User(client, user_id=j["user_id"], user_name=j["user_name"]),
        )

if __name__ == "__main__":
    c = Client(scope="")

    since = datetime.now(timezone.utc) - timedelta(days=1)

    fs = c.me().following()

    vs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        for f in [ ex.submit(lambda f: f.videos(since=since), f) for f in fs ]:
            vs += f.result()
    vs = sorted(vs, key=lambda v: v.created_at, reverse=True)

    ss = c.streams(fs)

    max_user_name_length = max([len(v.user.user_name) for v in vs] + [len(s.user.user_name) for s in ss])
    max_duration_length = max([len(v.duration) for v in vs])

    urls = {}
    stdin = ""
    for s in ss:
        l = f"{s.user.user_name.ljust(max_user_name_length)} {' ' * max_duration_length} {s.title}"
        urls[l] = s.url
        stdin += l + "\n"

    for v in vs:
        l = f"{v.user.user_name.ljust(max_user_name_length)} {v.duration.ljust(max_duration_length)} {v.title}"
        urls[l] = v.url
        stdin += l + "\n"

    p = subprocess.Popen("dmenu -l 20", shell=True, text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    (selection, _) = p.communicate(input=stdin)
    for l in selection.splitlines():
        print(urls[l])
