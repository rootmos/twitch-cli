import os
import re

from abc import ABC, abstractmethod
from typing import Any, Iterable

import xdg_base_dirs
import yaml

from .model import *
from . import whoami

import logging
logger = logging.getLogger(__name__)

class Configurable(ABC):
    def __init__(self, path=None, thing=None, filename=None):
        thing = thing or self.__class__.__name__.lower()
        filename = filename or f"{thing}.yaml"
        self.path = path or os.path.join(xdg_base_dirs.xdg_config_home(), whoami, filename)

        logger.debug("attempting to load %s from: %s", thing, self.path)
        try:
            with open(self.path, "r") as f:
                self._raw = yaml.load(f, Loader=yaml.Loader)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("loaded %s from; %s: %s", thing, self.path, self._raw)
            else:
                logger.info("loaded %s from: %s", thing, self.path)
        except FileNotFoundError:
            logger.info("populating an empty %s at: %s", thing, self.path)
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "x") as f:
                yaml.dump(self.empty(), f, Dumper=yaml.Dumper)
            with open(self.path, "r") as f:
                self._raw = yaml.load(f, Loader=yaml.Loader)

    @classmethod
    @abstractmethod
    def empty(cls) -> Any:
        ...

class Filter(Configurable):
    @classmethod
    def empty(cls):
        return {
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
        super().__init__(path=path)

    @classmethod
    def default_path(cls):
        return os.path.join(xdg_base_dirs.xdg_config_home(), whoami, "filter.yaml")

    def stream(self, s: Stream) -> bool:
        for b in [self._user(s.user), self._game(s.game), self._title(s.title)]:
            if b is not None:
                return b
        return True

    def video(self, v: Video) -> bool:
        for b in [self._user(v.user), self._title(v.title)]:
            if b is not None:
                return b
        return True

    def user(self, u: User) -> bool:
        b = self._user(u)
        return b if b is not None else True

    def _user(self, u: User) -> bool | None:
        for x in self._raw.get("include", {}).get("user", []):
            if x == u.id or self._match(x, u.login) or self._match(x, u.name):
                return True
        for x in self._raw.get("exclude", {}).get("user", []):
            if x == u.id or self._match(x, u.login) or self._match(x, u.name):
                return False

    def _game(self, g: Game) -> bool | None:
        for x in self._raw.get("include", {}).get("game", []):
            if x == g.id or self._match(x, g.name):
                return True
        for x in self._raw.get("exclude", {}).get("game", []):
            if x == g.id or self._match(x, g.name):
                return False

    def _title(self, t: str) -> bool | None:
        for p in self._raw.get("include", {}).get("title", []):
            if self._match(p, t):
                return True
        for p in self._raw.get("exclude", {}).get("title", []):
            if self._match(p, t):
                return False

    @staticmethod
    def _match(test: int | str | None, subject: str | None) -> bool | None:
        if subject == None:
            return None
        match test:
            case None:
                return None
            case int():
                try:
                    return test == int(subject)
                except ValueError:
                    return False
            case str():
                if test.startswith("/"):
                    return bool(re.search(test[1:], subject))
                return test == subject

class Lists(Configurable):
    def __init__(self, path=None):
        super().__init__(path=path)

    @classmethod
    def empty(cls):
        return {}

    def __getitem__(self, k: str) -> set[str]:
        return set(self._raw[k])

    def keys(self) -> Iterable[str]:
        return self._raw.keys()

    def __contains__(self, k: str) -> bool:
        return k in self._raw

    def __len__(self) -> int:
        return len(self._raw)
