import argparse
import os
import sys
from typing import Callable

from . import util, app
from . import env, package_version

import argcomplete

import logging
logger = logging.getLogger(__name__)

def parse_args(build: Callable[[], argparse.ArgumentParser]) -> argparse.Namespace:
    early = argparse.ArgumentParser(add_help=False)
    main_parser = build()

    for p in [ early, main_parser ]:
        p.add_argument("-v", "--version", action="store_true", help="print program version, then exit")
        p.add_argument("--completion-script", action="store_true", help="print script that when sourced configures shell completion, then exit")
        p.add_argument("--log", default=env("LOG_LEVEL", "INFO"), help="set log level")

    args, _ = early.parse_known_args()

    util.setup_logger(args.log)
    logger.debug("early args: %s", args)

    if args.version:
        prog = os.path.basename(sys.argv[0])
        print(f"{prog} {package_version}")
        sys.exit(0)

    if args.completion_script:
        prog = os.path.basename(sys.argv[0])
        sys.stdout.write(argcomplete.shellcode([ prog ]))
        sys.exit(0)

    argcomplete.autocomplete(main_parser)
    return main_parser.parse_args()

def main_parser():
    parser = argparse.ArgumentParser(
        # description="TODO",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="cmd", required=True)
    def add_subcommand(cmd):
        return subparsers.add_parser(cmd, formatter_class=parser.formatter_class)

    oauth_cmd = add_subcommand("oauth")
    oauth_cmd.add_argument("-n", "--dont-fetch-new-token", action="store_true")
    oauth_cmd.add_argument("-f", "--force-fetch-new-token", action="store_true")

    sandbox_cmd = add_subcommand("sandbox")

    following_cmd = add_subcommand("following")

    def add_title_width_argmunent(p):
        p.add_argument("-w", "--title-width", metavar="WIDTH", type=int, default=60, help="truncate titles to WIDTH")

    live_cmd = add_subcommand("live")
    add_title_width_argmunent(live_cmd)

    videos_cmd = add_subcommand("videos")
    add_title_width_argmunent(videos_cmd)
    videos_cmd.add_argument("channel", metavar="CHANNEL", nargs="*", help="list videos from CHANNEL (if not present: all followed channels)")

    return parser

def main():
    args = parse_args(main_parser)
    logger.debug("args: %s", args)

    match args.cmd:
        case "oauth":
            app.do_oauth(args)
        case "sandbox":
            app.do_sandbox(args)
        case "following":
            app.do_following(args)
        case "live":
            app.do_live(args)
        case "videos":
            app.do_videos(args)
        case cmd:
            raise NotImplementedError(cmd)
