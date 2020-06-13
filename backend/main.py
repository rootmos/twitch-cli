import secrets
from base64 import b64encode as b64e, urlsafe_b64encode as b64Ue
from sanic import Sanic, response
import httpx
from uuid import uuid4
import os
import asyncio
import json

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
            secret = secrets.token_bytes(36),
        )

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "secret_base64": str(b64e(self.secret), "UTF-8"),
            "callback_urls": {
                "/users/follows": self.base_callback_url + "/users/follows",
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
        await ws.send(json.dumps({"event": e}))

@app.route("/sessions/<session_id>/users/follows", methods=["POST", "GET"])
async def webhook_users_follows(req, session_id):
    if req.method == "GET":
        s = await sessions.get(session_id)
        if s is not None:
            await s.events.put({"state": "verified"})
            return response.text(req.args["hub.challenge"])
        else:
            return response.empty(status=404)
    elif req.method == "POST":
        s = await sessions.get(session_id)
        await s.events.put({"event": req.json})
        return response.empty()


if __name__ == "__main__":
    if HOST is None:
        r = httpx.get("http://169.254.169.254/latest/meta-data/public-hostname")
        r.raise_for_status()
        HOST = r.text

    loop = asyncio.get_event_loop()
    loop.create_task(app.create_server(host="0.0.0.0", port=PORT, debug=True, return_asyncio_server=True))
    loop.create_task(wsapp.create_server(host="0.0.0.0", port=WSPORT, debug=True, return_asyncio_server=True))
    loop.run_forever()
