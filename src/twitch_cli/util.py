import collections
import datetime
import logging
import math
import os
import random
import string
import subprocess
import sys
import tempfile

from . import package_name, whoami

import logging
logger = logging.getLogger(__name__)

def setup_logger(level, logger=None, name=None):
    level = level.upper()
    if logger is None:
        logger = logging.getLogger(name=name or package_name)
    logger.setLevel(level)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    logger.addHandler(handler)

    fmt = logging.Formatter(fmt="%(asctime)s:%(name)s:%(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z")
    handler.setFormatter(fmt)

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def fresh_salt(n=5):
    alphabeth = string.ascii_letters + string.digits
    return ''.join(random.choices(alphabeth, k=n))

def interact(cwd=None, check=True):
    shell = os.environ.get("SHELL", "/bin/sh")
    tty = "/dev/tty"
    cmdline = f"{shell} -i <{tty} >{tty} 2>&1"
    subprocess.run(cmdline, shell=True, check=check, cwd=cwd)

def temporary_directory():
    return tempfile.TemporaryDirectory(prefix=f"{whoami}-")

def now():
    return datetime.datetime.now().astimezone()

def wait_indefinitely():
    import threading
    forever = threading.Event()
    forever.wait()

def pickle_cache(thing, f, force=False, cache_dir=None):
    import pickle

    path = os.path.join(cache_dir or ".", f".{thing}.pickle")
    if os.path.exists(path) and not force:
        logger.debug("reading %s from: %s", thing, path)
        with open(path, "rb") as f:
            return pickle.load(f)

    x = f()
    with open(path, "wb") as f:
        pickle.dump(x, f)

    return x

def load_module_from_path(path):
    if not os.path.isabs(path):
        hd, tl = os.path.split(path)
        path = os.path.join(hd or ".", tl)
    logger.debug("loading module from path: %s", path)

    import importlib.util
    spec = importlib.util.spec_from_file_location(path, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    return module

def render_duration(secs: float | int | datetime.timedelta, short=False) -> str:
    if isinstance(secs, datetime.timedelta):
        secs = math.floor(secs.total_seconds())

    if short is True:
        short = 2
    else:
        short = short or 5

    s = ""
    if secs >= 31536000:
        s += f"{secs // 31536000}y"
        secs %= 31536000
        short -= 1
    if short == 0:
        return s

    if secs >= 86400:
        s += f"{secs // 86400}d"
        secs %= 86400
        short -= 1
    if short == 0:
        return s

    if secs >= 3600:
        s += f"{secs // 3600}h"
        secs %= 3600
        short -= 1
    if short == 0:
        return s

    if secs >= 60:
        s += f"{secs // 60}m"
        secs %= 60
        short -= 1
    if short == 0:
        return s

    if secs > 0:
        s += f"{secs}s"
    return s

def parse_duration(string) -> None | datetime.timedelta:
    import re
    secs = None
    for m in re.compile("([0-9]+)([dDhHmMsSwW])").finditer(string):
        n = int(m.group(1))
        t = m.group(2)
        if secs is None:
            secs = 0
        if t == "s" or t == "S":
            secs += n
        elif t == "m" or t == "M":
            secs += n * 60
        elif t == "h" or t == "H":
            secs += n * 60 * 60
        elif t == "d" or t == "D":
            secs += n * 60 * 60 * 24
        elif t == "w" or t == "W":
            secs += n * 60 * 60 * 24 * 7
    if secs is None:
        raise ValueError("unable to parse duration: %s", string)
    return datetime.timedelta(seconds=secs)

# https://docs.python.org/3.13/library/collections.html#ordereddict-examples-and-recipes
class LastUpdatedOrderedDict(collections.OrderedDict):
    "Store items in the order the keys were last added"
    def __setitem__(self, key, value):
       super().__setitem__(key, value)
       self.move_to_end(key)
