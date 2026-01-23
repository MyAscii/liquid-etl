from __future__ import annotations

from typing import Any, Optional

from ..config import Config


def apply_config_defaults(args: Any, cfg: Config) -> Any:
    _set_if_missing(args, "provider_uri", cfg.rpc.provider_uri)
    _set_if_missing(args, "datadir", cfg.rpc.datadir)
    _set_if_missing(args, "dsn", cfg.postgres.dsn)
    _set_if_missing(args, "db", cfg.sqlite.path)

    _set_if_missing(args, "output", cfg.streaming.output)
    _set_if_missing(args, "batch_size", cfg.streaming.batch_size)
    _set_if_missing(args, "poll_interval", cfg.streaming.poll_interval)
    _set_if_missing(args, "rpc_batch_size", cfg.streaming.rpc_batch_size)
    _set_if_missing(args, "lag", cfg.streaming.lag)

    return args


def validate_required_args(args: Any) -> None:
    cmd = getattr(args, "command", None)
    if not cmd:
        return

    if cmd in {
        "export_blocks_and_transactions",
        "enrich_transactions",
        "get_block_range_for_date",
        "export_all",
        "stream",
        "ingest_range_to_postgres",
        "audit_rpc_schema",
    }:
        _require(
            args, "provider_uri", "RPC provider URI (--provider-uri or config.rpc.provider_uri)"
        )

    if cmd in {"load_ndjson_to_postgres", "ingest_range_to_postgres"}:
        _require(args, "dsn", "Postgres DSN (--dsn or config.postgres.dsn)")

    if cmd == "repair_postgres":
        _require(args, "dsn", "Postgres DSN (--dsn or config.postgres.dsn)")
        needs_rpc = not getattr(args, "dry_run", False) and not getattr(args, "no_fill_gaps", False)
        if needs_rpc:
            _require(
                args, "provider_uri", "RPC provider URI (--provider-uri or config.rpc.provider_uri)"
            )

    if cmd == "load_ndjson_to_sqlite":
        _require(args, "db", "SQLite DB path (--db or config.sqlite.path)")


def _set_if_missing(args: Any, field: str, value: Optional[Any]) -> None:
    if value is None:
        return
    if not hasattr(args, field):
        return
    current = getattr(args, field)
    if current is None:
        setattr(args, field, value)
        return
    if isinstance(current, str) and not current.strip():
        setattr(args, field, value)


def _require(args: Any, field: str, label: str) -> None:
    if not hasattr(args, field):
        raise ValueError(f"Missing required setting: {label}")
    v = getattr(args, field)
    if v is None:
        raise ValueError(f"Missing required setting: {label}")
    if isinstance(v, str) and not v.strip():
        raise ValueError(f"Missing required setting: {label}")
