"""CLI entry point: ``python -m fidx <directory> <command>``."""

import argparse
import os
import sys

import fidx

EXIT_OK = 0
EXIT_NO_MATCH = 1
EXIT_USAGE = 2


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m fidx")
    parser.add_argument("directory", help="folder to index or search")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("index", help="refresh the content-addressed index")

    search_parser = subparsers.add_parser("search", help="search the index for a term")
    search_parser.add_argument("term", help="term to search for")

    return parser


def run_index(directory):
    stats = fidx.index_directory(directory)
    print(
        f"seen={stats['seen']} reprocessed={stats['reprocessed']} "
        f"removed={stats['removed']}"
    )
    return EXIT_OK


def run_search(directory, term):
    try:
        matches = fidx.search(directory, term)
    except (fidx.IndexNotFoundError, ValueError) as exc:
        print(f"fidx: {exc}", file=sys.stderr)
        return EXIT_USAGE

    for path in matches:
        print(path)
    return EXIT_OK if matches else EXIT_NO_MATCH


def main(argv=None):
    args = build_parser().parse_args(argv)

    if not os.path.isdir(args.directory):
        print(f"fidx: {args.directory!r} is not a directory", file=sys.stderr)
        return EXIT_USAGE

    if args.command == "index":
        return run_index(args.directory)
    return run_search(args.directory, args.term)


if __name__ == "__main__":
    sys.exit(main())
