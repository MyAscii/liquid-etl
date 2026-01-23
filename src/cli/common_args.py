from __future__ import annotations

import argparse


def add_common_provider(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-p",
        "--provider-uri",
        required=True,
        help="JSON-RPC URI, e.g. http://user:pass@localhost:7041",
    )
    parser.add_argument(
        "--datadir",
        help="Elements/Liquid datadir (optional). Used to read .cookie or elements.conf when provider-uri has no creds.",
    )

