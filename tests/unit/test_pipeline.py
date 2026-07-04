import pytest
from liquidetl.pipeline import (
    PipelineConfig,
    build_backfill_argv,
    build_stream_argv,
    run,
    wait_for_rpc,
    wait_for_sync,
)

BASE_ENV = {
    "LIQUID_PROVIDER_URI": "http://u:p@elements:7041",
    "LIQUID_DSN": "postgresql://x@postgres:5432/db",
}


def _cfg(**over):
    env = dict(BASE_ENV)
    env.update(over)
    return PipelineConfig.from_env(env)


# ---- config parsing ----


def test_from_env_requires_uri_and_dsn():
    with pytest.raises(ValueError):
        PipelineConfig.from_env({"LIQUID_DSN": "x"})
    with pytest.raises(ValueError):
        PipelineConfig.from_env({"LIQUID_PROVIDER_URI": "x"})


def test_from_env_defaults_and_overrides():
    cfg = _cfg()
    assert cfg.mode == "backfill_then_stream"
    assert cfg.conflict_strategy == "ignore"
    assert cfg.fast_local is True
    cfg2 = _cfg(
        LIQUID_PIPELINE_MODE="stream",
        LIQUID_WAIT_FOR_SYNC="1",
        LIQUID_START_BLOCK="100",
        LIQUID_END_BLOCK="200",
        LIQUID_PREFETCH="4",
        LIQUID_FAST_LOCAL="0",
        LIQUID_ENRICH="true",
    )
    assert cfg2.mode == "stream"
    assert cfg2.wait_for_sync is True
    assert (cfg2.start_block, cfg2.end_block) == (100, 200)
    assert cfg2.prefetch == 4
    assert cfg2.fast_local is False
    assert cfg2.enrich is True


def test_from_env_rejects_bad_mode():
    with pytest.raises(ValueError):
        PipelineConfig.from_env({**BASE_ENV, "LIQUID_PIPELINE_MODE": "nope"})


# ---- argv builders ----


def test_build_backfill_argv():
    cfg = _cfg(LIQUID_DATADIR="/data", LIQUID_FAST_RPC_DECODE="0")
    argv = build_backfill_argv(cfg, 0, 999)
    assert argv[0] == "ingest_range_to_postgres"
    assert "-s" in argv and argv[argv.index("-s") + 1] == "0"
    assert argv[argv.index("-e") + 1] == "999"
    assert argv[argv.index("--conflict-strategy") + 1] == "ignore"
    assert "--fast-local" in argv
    assert "--no-fast-rpc-decode" in argv
    assert argv[argv.index("--datadir") + 1] == "/data"


def test_build_stream_argv_uses_dsn_output_and_no_start_block():
    cfg = _cfg(LIQUID_DEAD_LETTER="/tmp/dl.ndjson")
    argv = build_stream_argv(cfg)
    assert argv[0] == "stream"
    assert argv[argv.index("--output") + 1] == cfg.dsn
    # stream resumes from DB max for a postgres output; no --start-block forced
    assert "--start-block" not in argv
    assert argv[argv.index("--dead-letter") + 1] == "/tmp/dl.ndjson"


# ---- wait helpers ----


class _Rpc:
    def __init__(self, fail_times=0, tip=42, ibd_rounds=0):
        self.fail_times = fail_times
        self.calls = 0
        self.tip = tip
        self.ibd_rounds = ibd_rounds
        self.info_calls = 0

    def getblockcount(self):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ConnectionError("node not up")
        return self.tip

    def getblockchaininfo(self):
        self.info_calls += 1
        ibd = self.info_calls <= self.ibd_rounds
        return {"initialblockdownload": ibd, "blocks": 10, "headers": 10}


def test_wait_for_rpc_retries_then_returns_height():
    rpc = _Rpc(fail_times=2, tip=7)
    height = wait_for_rpc(
        rpc,
        timeout=100,
        interval=0,
        sleep=lambda *_: None,
        monotonic=lambda: 0.0,
        log=lambda *_: None,
    )
    assert height == 7
    assert rpc.calls == 3


def test_wait_for_rpc_times_out():
    rpc = _Rpc(fail_times=999)
    ticks = iter([0.0, 0.0, 5.0, 200.0])
    with pytest.raises(TimeoutError):
        wait_for_rpc(
            rpc,
            timeout=100,
            interval=0,
            sleep=lambda *_: None,
            monotonic=lambda: next(ticks),
            log=lambda *_: None,
        )


def test_wait_for_sync_blocks_until_not_ibd():
    rpc = _Rpc(ibd_rounds=3)
    wait_for_sync(rpc, interval=0, sleep=lambda *_: None, log=lambda *_: None)
    assert rpc.info_calls == 4  # 3 in-IBD rounds, then one clear


# ---- orchestration ----


def _deps(rpc, db_max, recorder, rc=0):
    return dict(
        make_rpc=lambda uri, dd: rpc,
        db_max_height=lambda dsn: db_max,
        cli_main=lambda argv: recorder.append(list(argv)) or rc,
        sleep=lambda *_: None,
        monotonic=lambda: 0.0,
        log=lambda *_: None,
    )


def test_backfill_then_stream_runs_both_in_order():
    calls = []
    rc = run(_cfg(), **_deps(_Rpc(tip=500), db_max=None, recorder=calls))
    assert rc == 0
    assert [c[0] for c in calls] == ["ingest_range_to_postgres", "stream"]
    backfill = calls[0]
    assert backfill[backfill.index("-s") + 1] == "0"
    assert backfill[backfill.index("-e") + 1] == "500"


def test_backfill_resumes_from_db_max():
    calls = []
    run(_cfg(), **_deps(_Rpc(tip=500), db_max=300, recorder=calls))
    backfill = calls[0]
    assert backfill[backfill.index("-s") + 1] == "301"  # db_max + 1


def test_backfill_skipped_when_up_to_date():
    calls = []
    run(
        _cfg(LIQUID_PIPELINE_MODE="backfill_then_stream"),
        **_deps(_Rpc(tip=100), db_max=100, recorder=calls),
    )
    # start (101) > tip (100): only stream runs
    assert [c[0] for c in calls] == ["stream"]


def test_stream_not_started_if_backfill_fails():
    calls = []
    rc = run(_cfg(), **_deps(_Rpc(tip=500), db_max=None, recorder=calls, rc=2))
    assert rc == 2
    assert [c[0] for c in calls] == ["ingest_range_to_postgres"]  # stream never reached


def test_stream_only_mode_skips_backfill():
    calls = []
    run(_cfg(LIQUID_PIPELINE_MODE="stream"), **_deps(_Rpc(tip=500), db_max=None, recorder=calls))
    assert [c[0] for c in calls] == ["stream"]


def test_backfill_only_mode_skips_stream():
    calls = []
    run(_cfg(LIQUID_PIPELINE_MODE="backfill"), **_deps(_Rpc(tip=9), db_max=None, recorder=calls))
    assert [c[0] for c in calls] == ["ingest_range_to_postgres"]
