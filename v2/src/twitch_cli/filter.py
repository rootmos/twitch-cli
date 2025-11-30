import os
import re

import xdg_base_dirs
import yaml

from .model import *
from . import whoami

import logging
logger = logging.getLogger(__name__)

class Filter:
    EMPTY = {
        "include": {
            "user": [],
            "game": [],
            "title": [],
        },
        "exclude": {
            "user": [],
            "game": [],
            "title": [],
        },
    }

    def __init__(self, path=None):
        self.path = path or self.default_path()

        logger.debug("loading filter configuration from: %s", self.path)
        try:
            with open(self.path, "r") as f:
                self._raw = yaml.load(f, Loader=yaml.Loader)
        except FileNotFoundError:
            logger.debug("populating an empty filter at: %s", self.path)
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "x") as f:
                yaml.dump(self.EMPTY, f, Dumper=yaml.Dumper)
            with open(self.path, "r") as f:
                self._raw = yaml.load(f, Loader=yaml.Loader)

    @classmethod
    def default_path(cls):
        return os.path.join(xdg_base_dirs.xdg_config_home(), whoami, "filter.yaml")

    def stream(self, s: Stream) -> bool:
        for b in [self.user(s.user), self.game(s.game), self.title(s.title)]:
            if b is not None:
                return b
        return True

    def user(self, u: User) -> bool | None:
        for x in self._raw.get("include", {}).get("user", []):
            if x == u.id or (u.login and x == u.login) or (u.name and x == u.name):
                return True
        for x in self._raw.get("exclude", {}).get("user", []):
            if x == u.id or (u.login and x == u.login) or (u.name and x == u.name):
                return False

    def game(self, g: Game) -> bool | None:
        for x in self._raw.get("include", {}).get("game", []):
            if x == g.id or (g.name and x == g.name):
                return True
        for x in self._raw.get("exclude", {}).get("game", []):
            if x == g.id or (g.name and x == g.name):
                return False

    def title(self, t: str) -> bool | None:
        for p in self._raw.get("include", {}).get("title", []):
            if re.search(p, t):
                return True
        for p in self._raw.get("exclude", {}).get("title", []):
            if re.search(p, t):
                return False
