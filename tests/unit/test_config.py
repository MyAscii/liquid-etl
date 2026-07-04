from __future__ import annotations

import json
from argparse import Namespace

from liquidetl.cli.config_apply import apply_config_defaults
from liquidetl.config import load_effective_config


def test_load_effective_config_default_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = load_effective_config()
    assert cfg.rpc.provider_uri is None
    assert cfg.postgres.dsn is None
    assert cfg.sqlite.path is None


def test_load_effective_config_profile_merge(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            {
                "rpc": {"provider_uri": "http://base"},
                "streaming": {"batch_size": 100},
                "profiles": {
                    "prod": {
                        "rpc": {"provider_uri": "http://prod"},
                        "postgres": {"dsn": "postgresql://prod"},
                        "streaming": {"batch_size": 500},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    cfg = load_effective_config(cli_path=str(p), cli_profile="prod")
    assert cfg.rpc.provider_uri == "http://prod"
    assert cfg.postgres.dsn == "postgresql://prod"
    assert cfg.streaming.batch_size == 500


def test_apply_config_defaults_only_fills_missing():
    cfg = load_effective_config(cli_path=None, cli_profile=None)
    args = Namespace(provider_uri="http://cli", datadir=None, dsn=None, db=None)
    cfg2 = cfg.__class__(
        rpc=cfg.rpc.__class__(provider_uri="http://cfg", datadir="X"),
        postgres=cfg.postgres.__class__(dsn="postgresql://cfg"),
        sqlite=cfg.sqlite.__class__(path="db.sqlite"),
        streaming=cfg.streaming,
    )
    apply_config_defaults(args, cfg2)
    assert args.provider_uri == "http://cli"
    assert args.datadir == "X"
    assert args.dsn == "postgresql://cfg"
    assert args.db == "db.sqlite"
