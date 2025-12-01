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

    def videos(self, user: User, since: datetime | None = None) -> set[Video]:
        params = {"user_id": user.id, "sort": "time"}
        vs = set()
        for j in self.helix.paginate("/videos", params=params, page_size=10):
            published_at = datetime.fromisoformat(j["published_at"])
            if since and published_at < since:
                break
            vs.add(Video(
                id = j["id"],
                title = j["title"],
                user = User(
                    id = j["user_id"],
                    login = j["user_login"],
                    name = j["user_name"],
                ),
                url = j["url"],
                duration = util.parse_duration(j["duration"]),
                created_at = datetime.fromisoformat(j["created_at"]),
                published_at = published_at,
            ))
        return vs

    def users(self, logins: Iterable[str] = [], ids: Iterable[str] = []) -> set[User]:
        us = set()
        ps = [ ("login", l) for l in logins ] + [ ("id", i) for i in ids ]
        PS = 100
        while len(ps) > 0:
            for j in self.helix.paginate("/users", params=ps[:PS], page_size=PS):
                us.add(User(
                    id = j["id"],
                    login = j["login"],
                    name = j["display_name"],
                ))
            ps = ps[PS:]
        return us

def clean(s: str) -> str:
    s = s.strip()
    if s.startswith("http"):
        return s.replace("www.twitch.tv", "twitch.tv")
    return "".join(filter(lambda x: x in string.printable, s))

def do_following(args):
    app = App()
    for u in app.following(app.me):
        print(u)

def do_live(args):
    app = App()
    f = Filter()

    if args.channel is None:
        us = app.following(app.me)
        us = filter(f.user, us)
    else:
        us = app.users(logins=args.channel)

    ss = app.streams(us)

    ss = filter(f.stream, ss)
    ss = sorted(ss, key=lambda s: s.started_at, reverse=True)

    now = datetime.now(UTC)

    table = PrettyTable()
    table.field_names = ["Channel", "Title", "Game", "Since", "URL"]
    table.align = "l"
    for s in ss:
        title = clean(s.title)
        if args.title_width:
            title = title[:args.title_width]

        table.add_row([
            str(s.user),
            title,
            str(s.game),
            util.render_duration(now - s.started_at),
            clean(s.url),
        ])
    print(table.get_string())

def do_videos(args):
    app = App()
    f = Filter()

    if args.channel is None:
        us = app.following(app.me)
        us = filter(f.user, us)
    else:
        us = app.users(logins=args.channel)

    now = datetime.now(UTC)
    since = now - timedelta(days=1)

    vs = set()
    for u in us:
        logger.info("fetching videos from: %s", u)
        vs |= set(filter(f.video, app.videos(u, since=since)))
    vs = sorted(vs, key=lambda v: v.published_at, reverse=True)

    table = PrettyTable()
    table.field_names = ["When", "User", "Title", "Duration", "URL"]
    table.align = "l"
    for v in vs:
        if v.duration < timedelta(minutes=10):
            continue
        age = util.render_duration(now - v.published_at)
        title = clean(v.title)
        if args.title_width:
            title = title[:args.title_width]
        table.add_row([
            age,
            v.user.name,
            title,
            util.render_duration(v.duration),
            clean(v.url),
        ])
    print(table.get_string())

def do_sandbox(args):
    logger.info("hello")
