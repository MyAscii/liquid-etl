"""Supervised backfill-then-stream pipeline for containerized runs.

Waits for the node RPC (and, optionally, initial sync) to be ready, batch-ingests
history up to the chain tip, then follows the head continuously. Everything is
driven by env vars so the container entrypoint is just `python -m liquidetl.pipeline`.

The orchestration composes the existing `ingest_range_to_postgres` and `stream`
CLI commands rather than reimplementing them, so it inherits their fixes/tuning.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, List, Mapping, Optional, Sequence

logger = logging.getLogger("liquidetl.pipeline")

MODES = ("backfill_then_stream", "backfill", "stream")


def _as_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _as_int(value: Optional[str], default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _as_opt_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class PipelineConfig:
    provider_uri: str
    dsn: str
    datadir: Optional[str] = None
    mode: str = "backfill_then_stream"
    start_block: int = 0
    end_block: Optional[int] = None
    wait_for_sync: bool = False
    rpc_ready_timeout: float = 900.0
    rpc_ready_interval: float = 3.0
    sync_poll_interval: float = 15.0
    # backfill tuning
    rpc_batch_size: int = 200
    chunk_size: int = 500
    prefetch: int = 8
    conflict_strategy: str = "ignore"
    fast_local: bool = True
    fast_rpc_decode: bool = True
    # stream tuning
    stream_batch_size: int = 100
    poll_interval: float = 2.0
    lag: int = 0
    enrich: bool = False
    dead_letter: Optional[str] = None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "PipelineConfig":
        provider_uri = env.get("LIQUID_PROVIDER_URI") or env.get("LIQUID_RPC_URI") or ""
        dsn = env.get("LIQUID_DSN", "")
        if not provider_uri:
            raise ValueError("LIQUID_PROVIDER_URI is required")
        if not dsn:
            raise ValueError("LIQUID_DSN is required")
        mode = env.get("LIQUID_PIPELINE_MODE", "backfill_then_stream").strip()
        if mode not in MODES:
            raise ValueError(f"LIQUID_PIPELINE_MODE must be one of {MODES}, got {mode!r}")
        return cls(
            provider_uri=provider_uri,
            dsn=dsn,
            datadir=env.get("LIQUID_DATADIR") or None,
            mode=mode,
            start_block=_as_int(env.get("LIQUID_START_BLOCK"), 0),
            end_block=_as_opt_int(env.get("LIQUID_END_BLOCK")),
            wait_for_sync=_as_bool(env.get("LIQUID_WAIT_FOR_SYNC"), False),
            rpc_ready_timeout=float(_as_int(env.get("LIQUID_RPC_READY_TIMEOUT"), 900)),
            rpc_ready_interval=float(_as_int(env.get("LIQUID_RPC_READY_INTERVAL"), 3)),
            sync_poll_interval=float(_as_int(env.get("LIQUID_SYNC_POLL_INTERVAL"), 15)),
            rpc_batch_size=_as_int(env.get("LIQUID_RPC_BATCH_SIZE"), 200),
            chunk_size=_as_int(env.get("LIQUID_CHUNK_SIZE"), 500),
            prefetch=_as_int(env.get("LIQUID_PREFETCH"), 8),
            conflict_strategy=env.get("LIQUID_CONFLICT_STRATEGY", "ignore").strip() or "ignore",
            fast_local=_as_bool(env.get("LIQUID_FAST_LOCAL"), True),
            fast_rpc_decode=_as_bool(env.get("LIQUID_FAST_RPC_DECODE"), True),
            stream_batch_size=_as_int(env.get("LIQUID_STREAM_BATCH_SIZE"), 100),
            poll_interval=float(_as_int(env.get("LIQUID_POLL_INTERVAL"), 2)),
            lag=_as_int(env.get("LIQUID_LAG"), 0),
            enrich=_as_bool(env.get("LIQUID_ENRICH"), False),
            dead_letter=env.get("LIQUID_DEAD_LETTER") or None,
        )


def build_backfill_argv(cfg: PipelineConfig, start: int, end: int) -> List[str]:
    argv: List[str] = [
        "ingest_range_to_postgres",
        "-p",
        cfg.provider_uri,
        "-s",
        str(start),
        "-e",
        str(end),
        "--dsn",
        cfg.dsn,
        "--rpc-batch-size",
        str(cfg.rpc_batch_size),
        "--chunk-size",
        str(cfg.chunk_size),
        "--prefetch",
        str(cfg.prefetch),
        "--conflict-strategy",
        cfg.conflict_strategy,
        "--no-progress",
    ]
    if cfg.datadir:
        argv += ["--datadir", cfg.datadir]
    if cfg.fast_local:
        argv.append("--fast-local")
    argv.append("--fast-rpc-decode" if cfg.fast_rpc_decode else "--no-fast-rpc-decode")
    return argv


def build_stream_argv(cfg: PipelineConfig) -> List[str]:
    argv: List[str] = [
        "stream",
        "-p",
        cfg.provider_uri,
        "--output",
        cfg.dsn,
        "--batch-size",
        str(cfg.stream_batch_size),
        "--poll-interval",
        str(cfg.poll_interval),
        "--lag",
        str(cfg.lag),
    ]
    if cfg.datadir:
        argv += ["--datadir", cfg.datadir]
    if cfg.enrich:
        argv.append("--enrich")
    if cfg.dead_letter:
        argv += ["--dead-letter", cfg.dead_letter]
    return argv


def wait_for_rpc(
    rpc: Any,
    *,
    timeout: float,
    interval: float,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    log: Callable[[str], None] = logger.info,
) -> int:
    """Block until the node answers getblockcount, or raise TimeoutError."""
    deadline = monotonic() + timeout
    attempt = 0
    while True:
        attempt += 1
        try:
            height = int(rpc.getblockcount())
            log(f"node ready at height {height}")
            return height
        except Exception as e:  # noqa: BLE001 - node not up yet is expected
            if monotonic() >= deadline:
                raise TimeoutError(f"node RPC not ready after {timeout}s: {e}") from e
            log(f"waiting for node RPC (attempt {attempt}): {e}")
            sleep(interval)


def wait_for_sync(
    rpc: Any,
    *,
    interval: float,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = logger.info,
) -> None:
    """Block until the node reports it is no longer in initial block download."""
    while True:
        info = rpc.getblockchaininfo()
        ibd = bool(info.get("initialblockdownload", False))
        blocks = info.get("blocks")
        headers = info.get("headers")
        progress = info.get("verificationprogress")
        if not ibd:
            log(f"node synced (blocks={blocks}, headers={headers})")
            return
        log(f"syncing: blocks={blocks} headers={headers} progress={progress}")
        sleep(interval)


def run(
    cfg: PipelineConfig,
    *,
    make_rpc: Callable[[str, Optional[str]], Any],
    db_max_height: Callable[[str], Optional[int]],
    cli_main: Callable[[Sequence[str]], int],
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    log: Callable[[str], None] = logger.info,
) -> int:
    rpc = make_rpc(cfg.provider_uri, cfg.datadir)
    wait_for_rpc(
        rpc,
        timeout=cfg.rpc_ready_timeout,
        interval=cfg.rpc_ready_interval,
        sleep=sleep,
        monotonic=monotonic,
        log=log,
    )
    if cfg.wait_for_sync:
        wait_for_sync(rpc, interval=cfg.sync_poll_interval, sleep=sleep, log=log)

    if cfg.mode in ("backfill", "backfill_then_stream"):
        end = cfg.end_block if cfg.end_block is not None else int(rpc.getblockcount())
        start = cfg.start_block
        existing = db_max_height(cfg.dsn)
        if existing is not None:
            start = max(start, existing + 1)
        if start > end:
            log(f"backfill: up to date (start {start} > tip {end}); skipping")
        else:
            log(f"backfill: ingesting {start}..{end}")
            rc = cli_main(build_backfill_argv(cfg, start, end))
            if rc != 0:
                log(f"backfill failed with rc={rc}; not starting stream")
                return rc
            log("backfill complete")

    if cfg.mode in ("stream", "backfill_then_stream"):
        log("stream: following chain head (Ctrl-C to stop)")
        return cli_main(build_stream_argv(cfg))

    return 0


def _real_make_rpc(provider_uri: str, datadir: Optional[str]) -> Any:
    from .rpc import LiquidRpc

    return LiquidRpc(provider_uri, datadir=datadir)


def _real_db_max_height(dsn: str) -> Optional[int]:
    from .utils.postgres_writer import PostgresWriter

    writer = PostgresWriter(dsn)
    try:
        return writer.get_max_block_height()
    finally:
        writer.close()


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    from .cli import main as cli_main

    cfg = PipelineConfig.from_env(os.environ)
    logger.info(
        "pipeline start: mode=%s provider=%s wait_for_sync=%s",
        cfg.mode,
        _redact(cfg.provider_uri),
        cfg.wait_for_sync,
    )
    return run(
        cfg,
        make_rpc=_real_make_rpc,
        db_max_height=_real_db_max_height,
        cli_main=cli_main,
    )


def _redact(uri: str) -> str:
    # Hide credentials in provider URIs when logging.
    if "@" in uri and "//" in uri:
        scheme, rest = uri.split("//", 1)
        if "@" in rest:
            return f"{scheme}//***@{rest.split('@', 1)[1]}"
    return uri


if __name__ == "__main__":
    raise SystemExit(main())
