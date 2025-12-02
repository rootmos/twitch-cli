#!/usr/bin/env python3

import os
import shutil
import subprocess
import tempfile
import time
import sys

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

EXE = shutil.which("twitch")
LOG_LEVEL = "DEBUG"

XDG_STATE_HOME = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
STATE_DIR = os.environ.get("STATE_DIR", os.path.join(XDG_STATE_HOME, os.environ["APP"]))

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def env():
    return {
        "TWITCH_CLI_LOG_LEVEL": LOG_LEVEL,
        **os.environ
    }

def run_and_copy_stdout(cmdline, target, env=None):
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "out")
        with open(out, "x") as f:
            subprocess.check_call(cmdline, env=env, stdout=f)
        shutil.copyfile(out, target)

def live():
    target = os.path.join(STATE_DIR, "live")
    cmdline = [EXE, "live", "--title-width=80"]
    run_and_copy_stdout(cmdline, target, env=env())

def videos():
    target = os.path.join(STATE_DIR, "videos")
    cmdline = [EXE, "videos", "--title-width=80"]
    run_and_copy_stdout(cmdline, target, env=env())

@dataclass
class Task:
    name: str
    period: timedelta
    callback: Callable[[], None]

def poor_mans_scheduler(*tasks: Task):

    @dataclass
    class Scheduled:
        task: Task
        at: datetime

    now = datetime.now()
    schedule = [ Scheduled(task=t, at=now) for t in tasks ]

    while True:
        for s in schedule:
            now = datetime.now()
            if s.at <= now:
                eprint(f"task start: {s.task.name}")
                s.task.callback()
                eprint(f"task done: {s.task.name}")
                s.at = now + s.task.period

        now = datetime.now()
        s = (min([s.at for s in schedule]) - now).total_seconds()
        if s > 0:
            eprint(f"seeping for {s}s...")
            time.sleep(s)
        else:
            eprint(f"too late: {s}s")

def main():
    os.makedirs(STATE_DIR, exist_ok=True)
    a = Task("live", timedelta(minutes=5), live)
    b = Task("videos", timedelta(minutes=15), videos)
    poor_mans_scheduler(a, b)

if __name__ == "__main__":
    main()
