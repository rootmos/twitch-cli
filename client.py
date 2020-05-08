#!/usr/bin/env python3

import os
import uuid
import json
import requests
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

client_id = "dqfe0to2kp1pj0yvs3rpvuupdn1u6d"
redirect_host = "localhost"
redirect_port = 37876
redirect_path = "/redirect"
redirect_uri = f"http://{redirect_host}:{redirect_port}{redirect_path}"

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

    print(url)
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

    def user(self):
        h = { "Authorization": f"OAuth {self.token}" }
        j = requests.get("https://id.twitch.tv/oauth2/validate", headers=h).json()
        return {
            "user_name": j["login"],
            "user_id": j["user_id"],
        }

if __name__ == "__main__":
    c = Client(scope="")
    print(c.user())
