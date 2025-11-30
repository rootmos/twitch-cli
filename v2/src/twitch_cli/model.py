from dataclasses import dataclass, field
from datetime import datetime, timedelta

HUMAN_URL = "https://twitch.tv"

@dataclass(unsafe_hash=True)
class User:
    id: str
    login: str | None = field(compare=False, default=None)
    name: str | None = field(compare=False, default=None)

    def __str__(self):
        return self.name or self.login or repr(self)

@dataclass
class Video:
    id: str
    title: str
    user: User
    url: str
    duration: timedelta
    created_at: datetime
    published_at: datetime

@dataclass(unsafe_hash=True)
class Game:
    id: str
    name: str | None = field(compare=False, default=None)

    def __str__(self):
        return self.name or repr(self)

@dataclass(unsafe_hash=True)
class Stream:
    id: str
    title: str = field(compare=False)
    user: User = field(compare=False)
    started_at: datetime = field(compare=False)
    game: Game = field(compare=False)

    @property
    def url(self) -> str:
        assert self.user.login is not None
        return f"{HUMAN_URL}/{self.user.login}"

