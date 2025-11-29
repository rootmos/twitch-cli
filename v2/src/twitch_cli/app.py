import logging
logger = logging.getLogger(__name__)

from .helix import Helix

def sandbox(args):
    logger.info("hello")
    helix = Helix(fetch_new_tokens=True).authenticate()
    logger.debug("token: %s", helix._token)
