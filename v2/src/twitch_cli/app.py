from datetime import datetime, timedelta, UTC

from . import util
from .helix import Helix

import logging
logger = logging.getLogger(__name__)

def oauth(args):
    helix = Helix().authenticate(
        fetch_new_tokens = not args.dont_fetch_new_token,
        force = args.force_fetch_new_token,
    )

    logger.debug("token: %s", helix._token)
    print(helix._token.value)

def sandbox(args):
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

    after = datetime.now(UTC) - timedelta(days=3)

    def fetch_videos():
        vs = []
        for f in following:
            for j in helix.paginate("/videos", params={"user_id": f, "sort": "time"}, page_size=10):
                when = datetime.fromisoformat(j["published_at"])
                if when < after:
                    break
                vs.append(j)
        return vs

    vs = util.pickle_cache("videos", fetch_videos)

    for v in vs:
        print(v)
