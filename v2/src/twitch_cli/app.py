import string

from datetime import datetime, timedelta, UTC
from typing import Iterable

from prettytable import PrettyTable

from . import util
from .filter import Filter
from .helix import Helix
from .model import *

import logging
logger = logging.getLogger(__name__)

def do_oauth(args):
    helix = Helix().authenticate(
        fetch_new_tokens = not args.dont_fetch_new_token,
        force = args.force_fetch_new_token,
    )

    logger.debug("token: %s", helix.token)
    print(helix.token.value)

class App:
    def __init__(self):
        self.helix = Helix().authenticate()
        meta = self.helix.token.meta
        assert meta is not None
        self.me = User(
            id = meta["user_id"],
            login = meta["login"],
        )

    # which users is user following
    def following(self, user: User) -> set[User]:
        user = user or self.me

        us = set()
        params = { "user_id": user.id }
        for j in self.helix.paginate("/channels/followed", params=params, page_size=100):
            us.add(User(
                id = j["broadcaster_id"],
                name = j["broadcaster_name"],
                login = j["broadcaster_login"],
            ))

        return us

    def streams(self, users: Iterable[User]) -> set[Stream]:
        us = [ ("user_id", u.id) for u in users ]
        ss = set()
        PS = 100
        while len(us) > 0:
            for j in self.helix.paginate("/streams", params=us[:PS], page_size=PS):
                ss.add(Stream(
                    id = j["id"],
                    title = j["title"],
                    user = User(
                        id = j["user_id"],
                        login = j["user_login"],
                        name = j["user_name"],
                    ),
                    started_at = datetime.fromisoformat(j["started_at"]),
                    game = Game(
                        id = j["game_id"],
                        name = j["game_name"],
                    ),
                ))
            us = us[PS:]
        return ss

def do_following(args):
    app = App()
    for u in app.following(app.me):
        print(u)

def clean(s: str) -> str:
    return "".join(filter(lambda x: x in string.printable, s))

def do_sandbox(args):
    app = App()

    fs = util.pickle_cache("following", lambda: app.following(app.me))
    ss = util.pickle_cache("streams", lambda: app.streams(fs))

    f = Filter()
    ss = filter(f.stream, ss)
    ss = sorted(ss, key=lambda s: s.started_at)

    now = datetime.now(UTC)

    table = PrettyTable()
    table.field_names = ["Channel", "Title", "Game", "Since", "URL"]
    table.align = "l"
    for s in ss:
        table.add_row([
            str(s.user),
            clean(s.title)[:60],
            str(s.game),
            util.render_duration(now - s.started_at),
            s.url,
        ])
    print(table.get_string())

def do_sandbox0(args):
    logger.info("hello")
    helix = Helix().authenticate()

    # print(list(helix.paginate("/users", params=[("login", "AdmiralBahroo")])))

    def fetch_following():
        bids = set()
        user_id = helix._token.meta["user_id"]
        params = { "user_id": user_id }
        for j in helix.paginate("/channels/followed", params=params, page_size=100):
            name = j["broadcaster_name"]
            bid = j["broadcaster_id"]
            logger.debug("following: %s (%s)", name, bid)
            bids.add(bid)
        return bids

    following = list(util.pickle_cache("following", fetch_following))
    # following = ["40972890"]

    now = datetime.now(UTC)
    after = now - timedelta(days=3)

    def fetch_videos():
        vs = []
        for f in following:
            for j in helix.paginate("/videos", params={"user_id": f, "sort": "time"}, page_size=10):
                when = datetime.fromisoformat(j["published_at"])
                if when < after:
                    break
                vs.append(j)
        return vs

    ws = util.pickle_cache("videos", fetch_videos)

    vs = []
    for j in ws:
        vs.append(Video(
            id = j["id"],
            title = j["title"],
            user = User(
                id = j["user_id"],
                name = j["user_name"],
            ),
            url = j["url"],
            duration = util.parse_duration(j["duration"]),
            created_at = datetime.fromisoformat(j["created_at"]),
            published_at = datetime.fromisoformat(j["published_at"]),
        ))
    vs.sort(key=lambda v: v.published_at)

    table = PrettyTable()
    table.field_names = ["When", "User", "Title", "Duration", "URL"]
    table.align = "l"
    for v in vs:
        if v.duration < timedelta(minutes=10):
            continue
        age = util.render_duration(now - v.published_at)
        title = clean(v.title)[:60]
        url = v.url.replace("www.twitch.tv", "twitch.tv")
        table.add_row([
            age,
            v.user.name,
            title,
            util.render_duration(v.duration),
            url,
        ])
    print(table.get_string())
