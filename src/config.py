from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RpcConfig:
    provider_uri: Optional[str] = None
    datadir: Optional[str] = None


@dataclass(frozen=True)
class PostgresConfig:
    dsn: Optional[str] = None


@dataclass(frozen=True)
class SqliteConfig:
    path: Optional[str] = None


@dataclass(frozen=True)
class StreamingConfig:
    output: Optional[str] = None
    batch_size: Optional[int] = None
    poll_interval: Optional[float] = None
    rpc_batch_size: Optional[int] = None
    lag: Optional[int] = None


@dataclass(frozen=True)
class Config:
    rpc: RpcConfig = RpcConfig()
    postgres: PostgresConfig = PostgresConfig()
    sqlite: SqliteConfig = SqliteConfig()
    streaming: StreamingConfig = StreamingConfig()


def load_effective_config(
    *,
    cli_path: Optional[str] = None,
    cli_profile: Optional[str] = None,
) -> Config:
    path = resolve_config_path(cli_path)
    profile = resolve_profile(cli_profile)
    if path is None:
        return Config()
    raw = _read_json(path)
    merged = _select_profile(raw, profile)
    return _to_config(merged)


def resolve_config_path(cli_path: Optional[str]) -> Optional[Path]:
    if cli_path:
        return Path(cli_path).expanduser().resolve()
    env_path = os.environ.get("LIQUID_ETL_CONFIG")
    if env_path:
        return Path(env_path).expanduser().resolve()
    for candidate in (
        Path.cwd() / "liquidetl.config.json",
        Path.cwd() / "config.json",
        Path.home() / ".config" / "liquidetl" / "config.json",
    ):
        if candidate.exists():
            return candidate
    return None


def resolve_profile(cli_profile: Optional[str]) -> Optional[str]:
    if cli_profile:
        return cli_profile
    return os.environ.get("LIQUID_ETL_PROFILE")


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config file must be a JSON object: {path}")
    return data


def _select_profile(raw: Dict[str, Any], profile: Optional[str]) -> Dict[str, Any]:
    if not profile:
        return raw
    profiles = raw.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError("Config has no 'profiles' object")
    prof = profiles.get(profile)
    if not isinstance(prof, dict):
        raise ValueError(f"Unknown profile '{profile}'")
    base = dict(raw)
    base.pop("profiles", None)
    return _deep_merge(base, prof)


def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _to_config(d: Dict[str, Any]) -> Config:
    rpc = d.get("rpc") if isinstance(d.get("rpc"), dict) else {}
    postgres = d.get("postgres") if isinstance(d.get("postgres"), dict) else {}
    sqlite = d.get("sqlite") if isinstance(d.get("sqlite"), dict) else {}
    streaming = d.get("streaming") if isinstance(d.get("streaming"), dict) else {}

    return Config(
        rpc=RpcConfig(
            provider_uri=_as_str(rpc.get("provider_uri")),
            datadir=_as_str(rpc.get("datadir")),
        ),
        postgres=PostgresConfig(dsn=_as_str(postgres.get("dsn"))),
        sqlite=SqliteConfig(path=_as_str(sqlite.get("path"))),
        streaming=StreamingConfig(
            output=_as_str(streaming.get("output")),
            batch_size=_as_int(streaming.get("batch_size")),
            poll_interval=_as_float(streaming.get("poll_interval")),
            rpc_batch_size=_as_int(streaming.get("rpc_batch_size")),
            lag=_as_int(streaming.get("lag")),
        ),
    )


def _as_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return str(v)


def _as_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    try:
        return int(v)
    except Exception:
        return None


def _as_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, float):
        return v
    if isinstance(v, int):
        return float(v)
    try:
        return float(v)
    except Exception:
        return None
