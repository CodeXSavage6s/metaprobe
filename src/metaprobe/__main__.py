"""Command line interface: ``python -m metaprobe URL`` or ``metaprobe URL``.

Prints the extracted metadata as JSON on stdout. Diagnostics (e.g. why a fetch
failed) go to stderr, so stdout is always valid JSON. Exit status is 0 on
success, 1 if the page could not be fetched, 2 on a usage error.
"""

import argparse
import asyncio
import json
import sys

from . import __version__
from .extractor import MetadataExtractor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="metaprobe",
        description="Extract title, Open Graph, Twitter Card and <meta> data "
        "from a web page and print it as JSON.",
    )
    parser.add_argument("url", help="page to inspect, e.g. https://example.com")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = asyncio.run(MetadataExtractor().get_metadata(args.url))
    except KeyboardInterrupt:
        return 130

    # ensure_ascii (the default) keeps output safe on consoles that cannot
    # encode arbitrary Unicode.
    print(json.dumps(result, indent=2))

    # A successful result always has a "title" key; a failure is just {"error"}.
    # (Checking for "error" alone would misfire on a page with <meta name="error">.)
    return 0 if "title" in result else 1


if __name__ == "__main__":
    sys.exit(main())
