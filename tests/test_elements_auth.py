from pathlib import Path

from liquidetl.utils.elements_auth import resolve_rpc_auth


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_resolve_rpc_auth_prefers_chain_cookie(tmp_path):
    dd = tmp_path / "elements"
    _write(dd / "elements.conf", "chain=liquidv1\n")
    _write(dd / "liquidv1" / ".cookie", "u1:p1\n")
    _write(dd / ".cookie", "u2:p2\n")
    assert resolve_rpc_auth(str(dd)) == ("u1", "p1")


def test_resolve_rpc_auth_falls_back_to_root_cookie(tmp_path):
    dd = tmp_path / "elements"
    _write(dd / "elements.conf", "chain=liquidv1\n")
    _write(dd / ".cookie", "u2:p2\n")
    assert resolve_rpc_auth(str(dd)) == ("u2", "p2")


def test_resolve_rpc_auth_falls_back_to_conf_user_pass(tmp_path):
    dd = tmp_path / "elements"
    _write(dd / "elements.conf", "rpcuser=alice\nrpcpassword=secret\n")
    assert resolve_rpc_auth(str(dd)) == ("alice", "secret")


def test_resolve_rpc_auth_ignores_invalid_cookie(tmp_path):
    dd = tmp_path / "elements"
    _write(dd / ".cookie", "missing_colon\n")
    assert resolve_rpc_auth(str(dd)) is None

