from __future__ import annotations

import argparse

from ...utils.filters import filter_items as _filter_items


def filter_items(args: argparse.Namespace) -> int:
    _filter_items(
        input_path=args.input,
        output_path=args.output,
        predicate=args.predicate,
        input_format=args.format,
    )
    return 0

