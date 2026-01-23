from __future__ import annotations

import sys
from typing import Optional, Sequence

from ..config import load_effective_config
from .config_apply import apply_config_defaults, validate_required_args
from .parser import build_parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        cfg = load_effective_config(cli_path=getattr(args, "config", None), cli_profile=getattr(args, "profile", None))
        apply_config_defaults(args, cfg)
        validate_required_args(args)
        return int(args.func(args))
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


__all__ = ["build_parser", "main"]
