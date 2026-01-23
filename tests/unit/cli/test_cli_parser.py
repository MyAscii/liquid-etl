import pytest
from liquidetl.cli import build_parser


def test_parser_ingest_range_requires_args():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["ingest_range_to_postgres"])


def test_parser_ingest_range_defaults_and_progress_mutex():
    parser = build_parser()
    args = parser.parse_args(
        [
            "ingest_range_to_postgres",
            "-p",
            "http://127.0.0.1:7041",
            "-s",
            "1",
            "-e",
            "2",
            "--dsn",
            "postgresql://u:p@localhost:5432/db",
        ]
    )
    assert args.rpc_batch_size == 25
    assert hasattr(args, "func")

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "ingest_range_to_postgres",
                "-p",
                "http://127.0.0.1:7041",
                "-s",
                "1",
                "-e",
                "2",
                "--dsn",
                "postgresql://u:p@localhost:5432/db",
                "--progress",
                "--no-progress",
            ]
        )
