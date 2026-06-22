#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

EXE = shutil.which("twitch")
assert EXE is not None
LOG_LEVEL = "INFO"

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
        subprocess.check_call(["install", "--mode=0444", out, target])

def live():
    target = os.path.join(STATE_DIR, "live.twitch")
    cmdline = [EXE, "live"]
    run_and_copy_stdout(cmdline, target, env=env())

def videos():
    target = os.path.join(STATE_DIR, "videos.twitch")
    cmdline = [EXE, "videos"]
    run_and_copy_stdout(cmdline, target, env=env())

def _run_with_timeout_harness(q, f):
    try:
        q.put(f())
    except Exception as e:
        q.put(e)

def run_with_timeout[A](f: Callable[[], A], timeout: float, what: str | None = None) -> A | Exception:
    import multiprocessing

    q = multiprocessing.Queue()
    p = multiprocessing.Process(target=_run_with_timeout_harness, args=(q,f), daemon=True, name=what)
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.kill()
        raise TimeoutError(f"timeout ({what}): {timeout}s")
    return q.get()

@dataclass
class Task:
    name: str
    period: timedelta
    callback: Callable[[], None]
    timeout: float | None = None

    def run(self) -> None | Exception:
        return run_with_timeout(
            self.callback,
            timeout = self.timeout or self.period.total_seconds(),
            what = self.name,
        )

def poor_mans_scheduler(*tasks: Task, on_exc: Callable[[Exception]] | None = None):
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
                x = s.task.run()
                if x is not None:
                    eprint(f"task failed: {s.task.name}")
                    if on_exc is None:
                        raise x
                    else:
                        on_exc(x)
                else:
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
    poor_mans_scheduler(a, b, on_exc=traceback.print_exception)

if __name__ == "__main__":
    main()
