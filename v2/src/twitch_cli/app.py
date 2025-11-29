import logging
logger = logging.getLogger(__name__)

from .helix import Helix

def oauth(args):
    helix = Helix(fetch_new_tokens=not args.dont_fetch_new_token).authenticate()
    logger.debug("token: %s", helix._token)
    print(helix._token.value)

def sandbox(args):
    logger.info("hello")
    helix = Helix().authenticate()
    print(helix._token.meta["login"])
