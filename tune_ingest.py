from __future__ import annotations

import argparse
import csv
import os
import time
import uuid
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit


def _parse_int_list(s: str) -> List[int]:
    out: List[int] = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    if not out:
        raise ValueError("empty list")
    return out


def _parse_bool_list(s: str) -> List[bool]:
    out: List[bool] = []
    for part in (s or "").split(","):
        part = part.strip().lower()
        if not part:
            continue
        if part in {"1", "true", "t", "yes", "y"}:
            out.append(True)
        elif part in {"0", "false", "f", "no", "n"}:
            out.append(False)
        else:
            raise ValueError(f"invalid boolean: {part}")
    if not out:
        raise ValueError("empty list")
    return out


def _dsn_with_search_path(dsn: str, schema: str) -> str:
    parts = urlsplit(dsn)
    if not parts.scheme or not parts.netloc:
        raise ValueError("DSN must be a postgresql:// URL")
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    opt = f"-csearch_path={schema}"
    if "options" in q and q["options"]:
        q["options"] = f"{q['options']} {opt}"
    else:
        q["options"] = opt
    query = urlencode(q, quote_via=quote)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def _mask_dsn(dsn: str) -> str:
    parts = urlsplit(dsn)
    if not parts.scheme or not parts.netloc:
        return dsn
    netloc = parts.netloc
    if "@" in netloc and ":" in netloc.split("@", 1)[0]:
        creds, host = netloc.split("@", 1)
        user = creds.split(":", 1)[0]
        netloc = f"{user}:***@{host}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _create_schema(dsn: str, schema: str) -> None:
    try:
        import psycopg
    except Exception as e:
        raise RuntimeError("psycopg not installed; install with pip install -e .[postgres]") from e
    conn = psycopg.connect(dsn, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA "{schema}"')
    finally:
        conn.close()


def _drop_schema(dsn: str, schema: str) -> None:
    try:
        import psycopg
    except Exception as e:
        raise RuntimeError("psycopg not installed; install with pip install -e .[postgres]") from e
    conn = psycopg.connect(dsn, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    finally:
        conn.close()


@dataclass(frozen=True)
class Trial:
    rpc_batch_size: int
    chunk_size: int
    prefetch: int
    fast_rpc_decode: bool


@dataclass(frozen=True)
class TrialResult:
    trial: Trial
    seconds: float
    blocks_per_second: float
    rc: int


def _run_ingest_trial(
    *,
    provider_uri: str,
    datadir: Optional[str],
    dsn: str,
    start_block: int,
    end_block: int,
    trial: Trial,
) -> TrialResult:
    import liquidetl.cli as cli_mod

    argv: List[str] = [
        "ingest_range_to_postgres",
        "-p",
        provider_uri,
        "-s",
        str(start_block),
        "-e",
        str(end_block),
        "--dsn",
        dsn,
        "--fast-local",
        "--conflict-strategy",
        "ignore",
        "--rpc-batch-size",
        str(trial.rpc_batch_size),
        "--chunk-size",
        str(trial.chunk_size),
        "--prefetch",
        str(trial.prefetch),
        "--no-progress",
    ]
    if datadir:
        argv.extend(["--datadir", datadir])
    if trial.fast_rpc_decode:
        argv.append("--fast-rpc-decode")

    t0 = time.monotonic()
    rc = int(cli_mod.main(argv))
    elapsed = max(0.0001, time.monotonic() - t0)
    blocks = int(end_block) - int(start_block) + 1
    return TrialResult(
        trial=trial,
        seconds=elapsed,
        blocks_per_second=float(blocks) / elapsed,
        rc=rc,
    )


def _coordinate_search(
    *,
    provider_uri: str,
    datadir: Optional[str],
    base_dsn: str,
    start_block: int,
    blocks: int,
    rpc_batch_sizes: Sequence[int],
    chunk_sizes: Sequence[int],
    prefetch_values: Sequence[int],
    fast_rpc_decode_values: Sequence[bool],
    rounds: int,
    out_csv_path: Optional[str],
) -> List[TrialResult]:
    results: List[TrialResult] = []
    best = Trial(
        rpc_batch_size=rpc_batch_sizes[0],
        chunk_size=chunk_sizes[0],
        prefetch=prefetch_values[0],
        fast_rpc_decode=fast_rpc_decode_values[0],
    )

    def run_one(t: Trial) -> TrialResult:
        schema = f"bench_{uuid.uuid4().hex[:10]}"
        dsn = _dsn_with_search_path(base_dsn, schema)
        _create_schema(base_dsn, schema)
        try:
            res = _run_ingest_trial(
                provider_uri=provider_uri,
                datadir=datadir,
                dsn=dsn,
                start_block=start_block,
                end_block=start_block + blocks - 1,
                trial=t,
            )
            return res
        finally:
            _drop_schema(base_dsn, schema)

    def record(res: TrialResult) -> None:
        results.append(res)
        dsn_masked = _mask_dsn(base_dsn)
        print(
            f"{dsn_masked} rpc={res.trial.rpc_batch_size} chunk={res.trial.chunk_size} "
            f"prefetch={res.trial.prefetch} fast_decode={int(res.trial.fast_rpc_decode)} "
            f"-> {res.blocks_per_second:.2f} blk/s ({res.seconds:.2f}s) rc={res.rc}"
        )
        if out_csv_path:
            write_header = not os.path.exists(out_csv_path)
            with open(out_csv_path, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if write_header:
                    w.writerow(
                        [
                            "rpc_batch_size",
                            "chunk_size",
                            "prefetch",
                            "fast_rpc_decode",
                            "seconds",
                            "blocks_per_second",
                            "rc",
                        ]
                    )
                w.writerow(
                    [
                        res.trial.rpc_batch_size,
                        res.trial.chunk_size,
                        res.trial.prefetch,
                        int(res.trial.fast_rpc_decode),
                        f"{res.seconds:.6f}",
                        f"{res.blocks_per_second:.6f}",
                        res.rc,
                    ]
                )

    best_res = run_one(best)
    record(best_res)

    for _round in range(rounds):
        improved = False

        for v in rpc_batch_sizes:
            t = Trial(v, best.chunk_size, best.prefetch, best.fast_rpc_decode)
            res = run_one(t)
            record(res)
            if res.rc == 0 and res.blocks_per_second > best_res.blocks_per_second:
                best, best_res, improved = t, res, True

        for v in chunk_sizes:
            t = Trial(best.rpc_batch_size, v, best.prefetch, best.fast_rpc_decode)
            res = run_one(t)
            record(res)
            if res.rc == 0 and res.blocks_per_second > best_res.blocks_per_second:
                best, best_res, improved = t, res, True

        for v in prefetch_values:
            t = Trial(best.rpc_batch_size, best.chunk_size, v, best.fast_rpc_decode)
            res = run_one(t)
            record(res)
            if res.rc == 0 and res.blocks_per_second > best_res.blocks_per_second:
                best, best_res, improved = t, res, True

        for v in fast_rpc_decode_values:
            t = Trial(best.rpc_batch_size, best.chunk_size, best.prefetch, v)
            res = run_one(t)
            record(res)
            if res.rc == 0 and res.blocks_per_second > best_res.blocks_per_second:
                best, best_res, improved = t, res, True

        if not improved:
            break

    results_sorted = sorted(
        [r for r in results if r.rc == 0], key=lambda r: r.blocks_per_second, reverse=True
    )
    if results_sorted:
        top = results_sorted[0]
        print(
            f"BEST rpc={top.trial.rpc_batch_size} chunk={top.trial.chunk_size} prefetch={top.trial.prefetch} "
            f"fast_decode={int(top.trial.fast_rpc_decode)} -> {top.blocks_per_second:.2f} blk/s"
        )
    return results_sorted


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="tune_ingest.py")
    p.add_argument("--provider-uri", "-p", required=True)
    p.add_argument("--datadir", default=None)
    p.add_argument("--dsn", required=True, help="postgresql://... (base DSN, schema is created/dropped per run)")
    p.add_argument("--start-block", type=int, default=1)
    p.add_argument("--blocks", type=int, default=30000)
    p.add_argument("--rounds", type=int, default=2)
    p.add_argument("--rpc-batch-sizes", default="200,300,400")
    p.add_argument("--chunk-sizes", default="500,1000,1500")
    p.add_argument("--prefetch-values", default="0,2,4,8")
    p.add_argument("--fast-rpc-decode-values", default="1")
    p.add_argument("--out-csv", default=None)
    args = p.parse_args(argv)

    rpc_batch_sizes = _parse_int_list(args.rpc_batch_sizes)
    chunk_sizes = _parse_int_list(args.chunk_sizes)
    prefetch_values = _parse_int_list(args.prefetch_values)
    fast_rpc_decode_values = _parse_bool_list(args.fast_rpc_decode_values)

    _coordinate_search(
        provider_uri=str(args.provider_uri),
        datadir=str(args.datadir) if args.datadir else None,
        base_dsn=str(args.dsn),
        start_block=int(args.start_block),
        blocks=int(args.blocks),
        rpc_batch_sizes=rpc_batch_sizes,
        chunk_sizes=chunk_sizes,
        prefetch_values=prefetch_values,
        fast_rpc_decode_values=fast_rpc_decode_values,
        rounds=max(1, int(args.rounds)),
        out_csv_path=str(args.out_csv) if args.out_csv else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

