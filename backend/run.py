#!/usr/bin/env python3

import os
import sys
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Twitch webhook to websocket adapter")
    parser.add_argument("--daemon", help="daemonize", action="store_true")
    parser.add_argument("--pid-file", default=None, help="daemonize")
    parser.add_argument("--log", metavar="FILE", default=None, help="redirect stdout and stderr (unless --log-stderr is set) to FILE")
    parser.add_argument("--log-stderr", metavar="FILE", default=None, help="redirect stderr to FILE")
    parser.add_argument("file", metavar="FILE", nargs=1, help="run FILE")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    if args.daemon:
        p = os.fork()
        if p != 0:
            if args.pid_file is not None:
                with open(args.pid_file, "w") as f:
                    f.write(str(p))
            sys.exit(0)

    if args.log_stderr is not None:
        sys.stderr = open(args.log_stderr, "a")

    if args.log is not None:
        sys.stdout = open(args.log, "a")
        if args.log_stderr is None:
            sys.stderr = sys.stdout

    import importlib.util
    spec = importlib.util.spec_from_file_location("m", args.file[0])
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.run()
