import datetime
import logging
import os
import random
import string
import subprocess
import sys
import tempfile
import threading

from . import whoami

import logging
logger = logging.getLogger(__name__)

def setup_logger(level, logger=None, name=None):
    level = level.upper()
    if logger is None:
        logger = logging.getLogger(name=name or whoami)
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
