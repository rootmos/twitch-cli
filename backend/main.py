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
import enum
from datetime import datetime, timezone, timedelta

PORT = os.getenv("PORT", default=8000)
WSPORT = os.getenv("WSPORT", default=8001)
host = os.getenv("HOST", default=None)

def base_url():
    return f"http://{host}:{PORT}"

app = Sanic("twitch webhook to websocket adapter (http)")
wsapp = Sanic("twitch webhook to websocket adapter (websocket)")

class Subscription:
    class State(enum.Enum):
        UNVERIFIED = 1
        VERIFIED = 2
        DENIED = 3

    def __init__(self, subscription_id, session, topic, secret):
        self.subscription_id = subscription_id
        self.session = session
        self.topic = topic
        self.expires_at = None
        self.lease_seconds = None
        self.created_at = datetime.now(timezone.utc)
        self.verified_at = None
        self.secret = secret
        self.state = Subscription.State.UNVERIFIED
        self.callback_url = session.base_url + f"/subscriptions/{self.subscription_id}"

        self.lock = asyncio.Lock()
        # TODO: self.state_timeout

    @staticmethod
    async def new(session, topic):
        sub = Subscription(
            subscription_id = str(b64Ue(secrets.token_bytes(6)), "UTF-8"),
            session = session,
            secret = str(b64e(secrets.token_bytes(36)), "UTF-8"),
            topic = topic,
        )

        await session.events.put({"subscription": sub.to_dict()})

        return sub

    async def verify(self, lease_seconds, topic):
        async with self.lock:
            if self.state != Subscription.State.UNVERIFIED:
                raise RuntimeError(f"verifying in unexpected state: {self.state}")

            self.lease_seconds = lease_seconds
            self.verified_at = datetime.now(timezone.utc)
            self.expires_at = self.verified_at + timedelta(seconds=lease_seconds)
            self.topic = topic
            self.state = Subscription.State.VERIFIED

            await self.session.events.put({"subscription": self.to_dict()})

    async def denied(self, reason):
        async with self.lock:
            if self.state != Subscription.State.UNVERIFIED:
                raise RuntimeError(f"subscription denied while in unexpected state: {self.state}")

            self.state = Subscription.State.DENIED

            await self.session.events.put({"subscription": { **self.to_dict(), "reason": reason }})

    async def event(self, payload, metadata):
        await self.session.events.put({
            "event": {
                "payload": payload,
                "session_id": self.session.session_id,
                "subscription_id": self.subscription_id,
                "topic": self.topic,
                "metadata": metadata
            }
        })

    def to_dict(self):
        return {
            "subscription_id": self.subscription_id,
            "session_id": self.session.session_id,
            "secret": self.secret,
            "callback_url": self.callback_url,
            "state": self.state.name,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "topic": self.topic,
        }

class Session:
    def __init__(self, session_id, token):
        self.events = asyncio.Queue()
        self.session_id = session_id
        self.token = token
        self.base_url = base_url() + f"/sessions/{self.session_id}"
        self.subscriptions = {}
        self.created_at = datetime.now(timezone.utc)
        self.lock = asyncio.Lock()

    @staticmethod
    def new():
        return Session(
            session_id = str(b64Ue(secrets.token_bytes(12)), "UTF-8"),
            token = str(b64e(secrets.token_bytes(36)), "UTF-8"),
        )

    async def add_subscription(self, topic):
        s = await Subscription.new(self, topic)
        async with self.lock:
            self.subscriptions[s.subscription_id] = s
        return s

    async def get_subsciption(self, sid):
        async with self.lock:
            return self.subscriptions.get(sid)

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "token": self.token,
            "created_at": self.created_at.isoformat(),
            "subscriptions": self.subscriptions,
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
async def run_session(req, ws):
    s = Session.new()
    logger.info(f"new session: session_id={s.session_id}")
    await sessions.put(s)
    await ws.send(json.dumps({"session": s.to_dict()}))

    async def do_propagate_events():
        while True:
            e = await s.events.get()
            logger.debug(f"propagating event: session_id={s.session_id} event={e}")
            await ws.send(json.dumps(e))

    async def do_read_reqs():
        while True:
            e = json.loads(await ws.recv())
            if "subscription" in e:
                topic = e["subscription"]["topic"]
                logger.debug(f"allocating subscription: topic={topic} session_id={s.session_id}")
                await s.add_subscription(topic)
            else:
                logger.warn(f"unknown request: {e}")
                await ws.send(json.dumps({
                    "error": "unknown request",
                    "request": e
                }))

    await asyncio.gather(do_propagate_events(), do_read_reqs())

@app.route("/sessions/<session_id>/subscriptions/<subscription_id>", methods=["POST", "GET"])
async def handle_subscriptions(req, session_id, subscription_id):
    s = await sessions.get(session_id)
    if s is None:
        logger.warning(f"request for unknown session: session_id={session_id} subscription_id={subscription_id}")
        return response.empty(status=202)
    sub = await s.get_subsciption(subscription_id)
    if sub is None:
        logger.warning(f"request for unknown subscription: session_id={session_id} subscription_id={subscription_id}")
        return response.empty(status=202)

    if req.method == "GET":
        mode = req.args["hub.mode"][0]
        topic = req.args["hub.topic"][0]
        if mode == "subscribe":
            logger.debug(f"verifying session: session_id={session_id} subscription_id={subscription_id} topic={topic}")
            await sub.verify(
                lease_seconds=int(req.args["hub.lease_seconds"][0]),
                topic=topic,
            )

            return response.text(req.args["hub.challenge"][0])
        elif mode == "unsubscribe":
            logger.warning(f"unhandled unsubscribe requeuest: session_id={session_id} subscription_id={subscription_id} topic={topic}")
            return response.empty(status=202)
        elif mode == "denied":
            reason = req.args["hub.reason"][0]
            logger.warning(f"denied subscription: session_id={session_id} subscription_id={subscription_id} topic={topic} reason={reason}")
            await sub.denied(reason=reason)
            return response.empty(status=202)
        else:
            logger.error(f"unexpected mode: mode={mode} session_id={session_id} subscription_id={subscription_id} topic={topic}")
            return response.empty(status=202)
    elif req.method == "POST":
        nid = req.headers["twitch-notification-id"]

        if s is None:
            logger.warning(f"received notification for unknown session: session_id={session_id} twitch-notification-id={nid}")
            return response.empty(status=202)

        sig0 = bytes.fromhex(req.headers["x-hub-signature"].split("=")[1])
        sig1 = hmac.new(bytes(sub.secret, "UTF-8"), req.body, digestmod=hashlib.sha256).digest()
        if sig0 != sig1:
            logger.error(f"incorrect webhook signature: session_id={session_id} twitch-notification-id={nid}")
            return response.empty(status=202)

        d = req.json["data"]
        if len(d) != 1:
            logger.error(f"unexpected amount of notification data: twitch-notification-id={nid}")
            return response.empty(status=202)
        else:
            d = d[0]

        await sub.event(payload=d, metadata={
            "twitch-notification-id": nid,
            "twitch-notification-timestamp": req.headers["twitch-notification-timestamp"],
        })

        return response.empty(status=204)


if __name__ == "__main__":
    if host is None:
        r = httpx.get("http://169.254.169.254/latest/meta-data/public-hostname")
        r.raise_for_status()
        host = r.text

    loop = asyncio.get_event_loop()
    loop.create_task(app.create_server(host="0.0.0.0", port=PORT, return_asyncio_server=True))
    loop.create_task(wsapp.create_server(host="0.0.0.0", port=WSPORT, return_asyncio_server=True))
    loop.run_forever()
