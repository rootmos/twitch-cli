import logging
logger = logging.getLogger(__name__)

from .helix import Helix

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

    # rsp = helix.req("GET", "/users", params = [ ("login", "AdmiralBahroo") ])
    # print(rsp)

    user_id = helix._token.meta["user_id"]
    params = { "user_id": user_id, "first": 100 }
    rsp = helix.req("GET", "/channels/followed", params=params)
    print(rsp)
