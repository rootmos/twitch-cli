import logging
import os
import re
import string
import sys
from datetime import UTC, datetime, timedelta
from typing import Iterable

from prettytable import PrettyTable

from . import util
from .config import Filter, Lists
from .helix import Helix
from .model import *

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

    def videos_by_vid(self, *vid: str) -> list[Video]:
        logger.debug("fetching videos by id: %s", vid)

        if len(vid) == 0:
            return []

        if len(vid) > 100:
            raise NotImplementedError()

        params = [ ("id", i) for i in set(vid) ]
        vs = {}
        for j in self.helix.paginate("/videos", params=params, page_size=100):
            v = Video.from_twitch_json(j)
            vs[v.id] = v

        return [ vs[i] for i in vid ]

    def videos_by_user(self, user: User, since: datetime | None = None) -> set[Video]:
        logger.debug("listing videos by user (%s) since: %s", user, since)
        params = {"user_id": user.id, "sort": "time"}
        vs = set()
        for j in self.helix.paginate("/videos", params=params, page_size=10):
            published_at = datetime.fromisoformat(j["published_at"])
            if since and published_at < since:
                break
            vs.add(Video.from_twitch_json(j))
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
        return s.replace(f"www.{CNAME}", CNAME)
    return "".join(filter(lambda x: x in string.printable, s))

def do_following(args):
    app = App()
    for u in app.following(app.me):
        print(u)

def resolve_channels(app: App, args, f=None) -> Iterable[User]:
    us = set()
    if args.list:
        ls = Lists(path=args.lists)
        for l in args.list:
            us |= ls[l]
    for c in args.channel:
        us.add(c)

    if us:
        us = app.users(logins=us)
    else:
        us = app.following(app.me)

        if not args.no_filter:
            f = f or Filter(path=args.filter)
            us = filter(f.user, us)

    return us

def do_live(args):
    app = App()
    f = Filter(args.filter)

    us = resolve_channels(app, args, f=f)
    ss = app.streams(us)

    if not args.no_filter:
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

def render_table_of_videos(vs, width=None, now=None) -> PrettyTable:
    now = now or datetime.now().astimezone()

    table = PrettyTable()
    table.field_names = ["When", "User", "Title", "Duration", "URL"]
    table.align = "l"
    for v in vs:
        if v.duration < timedelta(minutes=10):
            continue
        age = util.render_duration(now - v.published_at)
        title = clean(v.title)
        if width:
            title = title[:width]
        table.add_row([
            age,
            v.user.name,
            title,
            util.render_duration(v.duration),
            clean(v.url),
        ])

    return table

def do_videos(args):
    app = App()
    f = Filter(args.filter)

    now = datetime.now(UTC)
    since = now - args.since

    vs = set()
    for u in resolve_channels(app, args, f=f):
        logger.info("fetching videos from: %s", u)
        ws = app.videos_by_user(u, since=since)
        if args.no_filter:
            vs |= set(ws)
        else:
            vs |= set(filter(f.video, ws))

    vs = sorted(vs, key=lambda v: v.published_at, reverse=True)

    def render(o):
        o.write(render_table_of_videos(vs, width=args.title_width).get_string())
        o.write("\n")

    if args.output:
        with open(args.output, "w") as o:
            render(o)

    if args.edit:
        def do_edit(path):
            util.run_with_tty(util.find_editor(), path)

        if args.output:
            do_edit(args.output)
        else:
            with util.temporary_directory() as tmp:
                path = os.path.join(tmp, "videos.twitch")
                with open(path, "w") as o:
                    render(o)
                do_edit(path)
    elif not args.output:
        render(sys.stdout)

def do_videos_file(args):
    app = App()

    if args.file is None or args.file == "-":
        ls = sys.stdin.readlines()
    else:
        with open(args.file) as f:
            ls = f.readlines()

    vs = []
    pat = re.compile(rf'{CNAME}/videos/(?P<vid>\w+)')
    for l in ls:
        m = pat.search(l)
        if m:
            vs.append(m.group("vid"))
    vs = app.videos_by_vid(*vs)
    s = render_table_of_videos(vs, width=args.title_width).get_string()

    if args.file is None or args.file == "-" or not args.in_place:
        o = sys.stdout
    else:
        assert args.file is not None and args.file != "-" and args.in_place
        o = open(args.file, "w")

    with o:
        o.write(s)
        o.write('\n')

def do_channels(args):
    app = App()
    for u in resolve_channels(app, args):
        print(u)

def do_sandbox(args):
    logger.info("hello")
