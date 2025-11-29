import email.utils
import urllib.parse
import uuid

from datetime import datetime, timedelta, UTC

import requests

from . import oauth
from . import package_version, whoami

import logging
logger = logging.getLogger(__name__)

class Helix:
    base_url = "https://api.twitch.tv/helix"
    client_id = "dqfe0to2kp1pj0yvs3rpvuupdn1u6d"
    authorize_url = "https://id.twitch.tv/oauth2/authorize"
    validate_url = "https://id.twitch.tv/oauth2/validate"

    def __init__(self, token=None):
        self._token = token
        self.session = requests.Session()

        self.scopes = [ "user:read:follows" ]

    @classmethod
    def build_headers(cls, token):
        return {
            "User-Agent": f"{whoami}-{package_version}",
            "Client-ID": cls.client_id,
            "Authorization": f"Bearer {token}",
        }

    def authenticate(self, fetch_new_tokens=None, force=None):
        if self._token is not None:
            return self

        now = datetime.now(UTC)
        state = str(uuid.uuid4())

        this = self
        class OAuth(oauth.OAuth):
            def __init__(self):
                super().__init__(fetch_new_tokens=fetch_new_tokens)

            def url(self) -> str:
                return this.authorize_url + "?" + urllib.parse.urlencode({
                    "client_id": this.client_id,
                    "redirect_uri": self.redirect_url,
                    "response_type": "token",
                    "scope": ",".join(this.scopes),
                    "state": state,
                })

            def validate_token(self, result):
                logger.debug("validating: %s", result)
                token = result["access_token"]
                assert result["state"] == state
                assert result["token_type"] == "bearer"
                assert "scope" in result

                hdr = this.build_headers(token=token)
                hdr["Accept"] = "application/json"

                req = requests.Request("GET", this.validate_url, headers=hdr)
                preq = this.session.prepare_request(req)
                rsp = this.session.send(preq)
                if rsp.status_code == requests.codes.unauthorized:
                    return False
                rsp.raise_for_status()

                offset = email.utils.parsedate_to_datetime(rsp.headers["Date"])
                assert now < offset

                j = rsp.json()
                return oauth.Token(
                    value = token,
                    created = now,
                    expires = offset + timedelta(seconds=j["expires_in"]),
                    meta = {
                        "login": j["login"],
                        "user_id": j["user_id"],
                        "scopes": j["scopes"],
                    },
                )

        self._token = OAuth().get_token(force=force)
        self.session.headers.update(self.build_headers(token=self._token.value))
        return self

    def log_request(self, req):
        logger.debug("request: %s %s %s", req.method, req.url, req.params)

    def req(self, method, path, params=None, body=None):
        hdr = {
            "Accept": "application/json",
        }
        req = requests.Request(method, self.base_url + path, headers=hdr, params=params, json=body)
        self.log_request(req)

        preq = self.session.prepare_request(req)
        rsp = self.session.send(preq)
        if rsp.status_code == 429:
            raise NotImplementedError(rsp)
        rsp.raise_for_status()
        return rsp.json()

    def paginate(self, path, params, page_size=None):
        hdr = {
            "Accept": "application/json",
        }

        def build(after):
            qs = params.copy()
            if isinstance(params, list):
                if page_size is not None:
                    qs += [ ("first", str(page_size)) ]
                if after is not None:
                    qs += [ ("after", after) ]
            elif isinstance(params, dict):
                if page_size is not None:
                    qs["first"] = str(page_size)
                if after is not None:
                    qs["after"] = after
            else:
                raise ValueError(f"unable to paginate params: {params}")

            return requests.Request("GET", self.base_url + path, headers=hdr, params=qs)

        after = None
        while True:
            req = build(after)
            self.log_request(req)
            preq = self.session.prepare_request(req)
            rsp = self.session.send(preq)
            rsp.raise_for_status()
            j = rsp.json()

            for d in j["data"]:
                yield d

            p = j.get("pagination")
            if p is None:
                break
            after = p.get("cursor")
            if after is None:
                break
