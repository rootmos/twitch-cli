import http.server
import json
import os
import shutil
import string
import subprocess
import sys
import urllib.parse

from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any

import xdg_base_dirs

from .. import package_data, whoami

import logging
logger = logging.getLogger(__name__)

class UnauthorizedException(Exception):
    pass

@dataclass
class Token:
    value: str
    expires: datetime
    created: datetime | None = None
    meta: Any | None = None

    def to_dict(self):
        d = {
            "value": self.value,
            "expires": self.expires.isoformat(timespec="seconds"),
        }

        if self.created is not None:
            d["created"] = self.created.isoformat(timespec="seconds")

        if self.meta is not None:
            d["meta"] = self.meta

        return d

    @staticmethod
    def from_dict(d):
        created = None
        if "created" in d:
            created = datetime.fromisoformat(d["created"])

        return Token(
            value = d["value"],
            expires = datetime.fromisoformat(d["expires"]),
            created = created,
            meta = d.get("meta"),
        )

class OAuth:
    def __init__(self, xdg_open=None, fetch_new_tokens=None):
        self.redirect_host = "localhost"
        self.redirect_port = 37876
        self.redirect_path = "/redirect"
        self.redirect_token_path = "/token"

        self.use_xdg_open = True if xdg_open is None else xdg_open

        self.fetch_new_tokens = fetch_new_tokens

    def url(self) -> str:
        raise NotImplementedError()

    @property
    def redirect_url(self) -> str:
        return f"http://{self.redirect_host}:{self.redirect_port}{self.redirect_path}"

    def mappings(self):
        return {
            "title": f"{whoami} - OAuth",
            "initial_status_text": "Saving token...",
            "ok_status_text": "Saving token... OK",
            "error_status_text": "Saving token... Oops!",
            "token_path": self.redirect_token_path,
        }

    def present_url(self, url):
        (self.use_xdg_open and self.xdg_open(url)) or print(url)

    def xdg_open(self, url):
        exe = shutil.which("xdg-open")
        if exe is None:
            return False
        subprocess.Popen([exe, url], stdout=sys.stderr)
        return True

    def new_token(self) -> Token:
        result : dict | BaseException | None = None

        this = self
        class RequestHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                logger.debug("GET %s", self.path)
                p = urllib.parse.urlparse(self.path)
                if p.path != this.redirect_path:
                    self.send_response(404)
                    self.send_header("Content-Length", str(0))
                    self.end_headers()
                    return

                with open(package_data("oauth", "redirect.html"), "r") as f:
                    raw = f.read()

                body = string.Template(raw).substitute(this.mappings()).encode("UTF-8")

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                p = urllib.parse.urlparse(self.path)
                if p.path != this.redirect_token_path:
                    logger.warning("POST %s unexpected", self.path)
                    self.send_response(404)
                    self.send_header("Content-Length", str(0))
                    self.end_headers()
                    return

                l = int(self.headers["Content-Length"])
                j = json.loads(self.rfile.read(l))

                logger.debug("POST %s %s", self.path, json.dumps(j))

                nonlocal result

                error = j.get("error")
                if error:
                    result = { "error": error }
                else:
                    result = { "token": this.validate_token(j) }

                self.send_response(204)
                self.send_header("Content-Length", str(0))
                self.end_headers()

        class Server(http.server.HTTPServer):
            def __init__(self):
                super().__init__((this.redirect_host, this.redirect_port), RequestHandler)

            def handle_error(self, request, client_address):
                nonlocal result
                result = sys.exception()

        self.present_url(self.url())

        logger.info("OAuth redirect listener: %s:%s", self.redirect_host, self.redirect_port)
        with Server() as srv:
            while result is None:
                try:
                    srv.handle_request()
                except KeyboardInterrupt:
                    logger.info("OAuth redirect listener: interrupted")
                    raise

        if isinstance(result, BaseException):
            raise result

        if "error" in result:
            raise RuntimeError("unable to fetch token", result["error"])

        return result["token"]

    def validate_token(self, result: dict):
        raise NotImplementedError()

    def token_path(self):
        st = os.path.join(xdg_base_dirs.xdg_state_home(), whoami)
        return os.path.join(st, "token.json")

    def get_token(self) -> Token:
        p = self.token_path()

        if os.path.exists(p):
            with open(p) as f:
                t = Token.from_dict(json.load(f))

            now = datetime.now(UTC)
            if now < t.expires:
                logger.debug("token (%s): %s", t.meta, p)
                return t
            logger.debug("token expired (%s): %s", t.expires, p)
        else:
            logger.debug("token not found: %s", p)

        if not self.fetch_new_tokens:
            raise UnauthorizedException()
        else:
            logger.info("token is unauthorized; attempting to fetch a new one: %s", p)

        t = self.new_token()
        logger.debug("fetched new token (%s): %s", t.meta, p)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            json.dump(t.to_dict(), f)
        return t
