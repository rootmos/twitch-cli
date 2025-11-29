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

    # print(list(helix.paginate("/users", params=[("login", "AdmiralBahroo")])))

    user_id = helix._token.meta["user_id"]
    params = { "user_id": user_id }
    for x in helix.paginate("/channels/followed", params=params, page_size=100):
        print(x)
