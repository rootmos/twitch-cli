import secrets
from base64 import b64encode as b64e, urlsafe_b64encode as b64Ue
from sanic import Sanic, response
from sanic.log import logger
import httpx
from uuid import uuid4
import os
import asyncio
import json
import hashlib
import hmac

PORT = os.getenv("PORT", default=8000)
WSPORT = os.getenv("WSPORT", default=8001)
HOST = os.getenv("HOST", default=None)

app = Sanic("twitch webhook to websocket adapter (http)")
wsapp = Sanic("twitch webhook to websocket adapter (websocket)")

class Session:
    def __init__(self, session_id, secret):
        self.events = asyncio.Queue()
        self.session_id = session_id
        self.secret = secret
        self.base_callback_url = f"http://{HOST}:{PORT}/sessions/{self.session_id}"

    @staticmethod
    def new():
        sid = str(b64Ue(secrets.token_bytes(12)), "UTF-8")
        return Session(
            session_id = sid,
            secret = str(b64e(secrets.token_bytes(36)), "UTF-8"),
        )

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "secret": self.secret,
            "callback_urls": {
                "/users/follows": self.base_callback_url + "/users/follows",
                "/streams": self.base_callback_url + "/streams",
            }
        }

class SessionStore:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.sessions = {}

    async def get(self, sid):
        async with self.lock:
            return self.sessions.get(sid)

    async def put(self, s):
        async with self.lock:
            self.sessions[s.session_id] = s

    async def exists(self, sid):
        async with self.lock:
            return sid in self.sessions

sessions = SessionStore()

@wsapp.websocket("/sessions")
async def new_session(req, ws):
    s = Session.new()
    await sessions.put(s)
    await ws.send(json.dumps({"session": s.to_dict()}))

    while True:
        e = await s.events.get()
        await ws.send(json.dumps(e))

@app.route("/sessions/<session_id>/users/follows", methods=["POST", "GET"])
async def webhook_users_follows(req, session_id):
    return await handle_webhook(req, session_id, "/users/follows")

@app.route("/sessions/<session_id>/streams", methods=["POST", "GET"])
async def webhook_streams(req, session_id):
    return await handle_webhook(req, session_id, "/streams")

async def handle_webhook(req, session_id, path):
    s = await sessions.get(session_id)

    if req.method == "GET":
        if s is not None:
            if req.args["hub.mode"][0] == "subscribe":
                logger.debug(f"verifying session: session_id={session_id}")
                await s.events.put({
                    "state": "verified",
                    "topic": req.args["hub.topic"][0],
                    })
                return response.text(req.args["hub.challenge"][0])
            else:
                logger.warning(f"request to verify unknown session: session_id={session_id}")
                return response.empty(status=202)
        else:
            return response.empty(status=404)
    elif req.method == "POST":
        nid = req.headers["twitch-notification-id"]

        if s is None:
            logger.warning(f"received notification for unknown session: session_id={session_id} twitch-notification-id={nid}")
            return response.empty(status=202)

        sig0 = bytes.fromhex(req.headers["x-hub-signature"].split("=")[1])
        sig1 = hmac.new(bytes(s.secret, "UTF-8"), req.body, digestmod=hashlib.sha256).digest()
        if sig0 != sig1:
            logger.error(f"incorrect webhook signature: session_id={session_id} twitch-notification-id={nid}")
            return response.empty(status=202)

        d = req.json["data"]
        if len(d) != 1:
            logger.error(f"unexpected amount of notification data: twitch-notification-id={nid}")
            return response.empty(status=202)
        else:
            d = d[0]

        await s.events.put({
            "event": d,
            "topic": path,
            "twitch-notification-id": nid,
            "twitch-notification-timestamp": req.headers["twitch-notification-timestamp"],
        })
        return response.empty(status=204)


if __name__ == "__main__":
    if HOST is None:
        r = httpx.get("http://169.254.169.254/latest/meta-data/public-hostname")
        r.raise_for_status()
        HOST = r.text

    loop = asyncio.get_event_loop()
    loop.create_task(app.create_server(host="0.0.0.0", port=PORT, return_asyncio_server=True))
    loop.create_task(wsapp.create_server(host="0.0.0.0", port=WSPORT, return_asyncio_server=True))
    loop.run_forever()
