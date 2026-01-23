from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from .utils.elements_auth import resolve_rpc_auth


class RpcError(RuntimeError):
    pass


class LiquidRpc:
    """Minimal JSON-RPC client for Elements/Liquid nodes.

    - Supports batch calls.
    - Decodes JSON with Decimal to avoid precision loss.
    - Accepts URIs like http://user:pass@host:7041.
    """

    def __init__(self, provider_uri: str, timeout: float = 30.0, datadir: Optional[str] = None):
        self._provider_uri = provider_uri
        self._timeout = timeout
        self._session = requests.Session()

        parsed = urlparse(provider_uri)
        self._url = f"{parsed.scheme}://{parsed.hostname}:{parsed.port or 7041}"
        if parsed.username or parsed.password:
            self._session.auth = (parsed.username or "", parsed.password or "")
        elif datadir:
            auth = resolve_rpc_auth(datadir)
            if auth:
                self._session.auth = auth

        # Elements/Bitcoin JSON-RPC typically requires 'application/json'
        self._headers = {"Content-Type": "application/json"}
        self._request_id = 0

    def _decode(self, text: str) -> Any:
        return json.loads(text, parse_float=Decimal)

    def call(self, method: str, params: Optional[List[Any]] = None) -> Any:
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or [],
        }
        resp = self._session.post(
            self._url, headers=self._headers, data=json.dumps(payload), timeout=self._timeout
        )
        resp.raise_for_status()
        data = self._decode(resp.text)
        if "error" in data and data["error"]:
            raise RpcError(str(data["error"]))
        return data.get("result")

    def batch_call(self, calls: List[Tuple[str, List[Any]]]) -> List[Any]:
        batch = []
        for method, params in calls:
            self._request_id += 1
            batch.append(
                {"jsonrpc": "2.0", "id": self._request_id, "method": method, "params": params or []}
            )
        resp = self._session.post(
            self._url, headers=self._headers, data=json.dumps(batch), timeout=self._timeout
        )
        resp.raise_for_status()
        results = self._decode(resp.text)
        # Map by id to keep ordering consistent
        id_to_result: Dict[int, Any] = {}
        for item in results:
            if item.get("error"):
                raise RpcError(str(item["error"]))
            id_to_result[item["id"]] = item.get("result")
        ordered = [id_to_result[req["id"]] for req in batch]
        return ordered

    # Convenience wrappers
    def getblockhash(self, height: int) -> str:
        return self.call("getblockhash", [height])

    def getblock(self, block_hash: str, verbosity: int = 2) -> Dict[str, Any]:
        return self.call("getblock", [block_hash, verbosity])

    def getrawtransaction(self, txid: str, verbose: bool = True) -> Dict[str, Any]:
        return self.call("getrawtransaction", [txid, int(verbose)])

    def getblockcount(self) -> int:
        return int(self.call("getblockcount", []))

    def getblockchaininfo(self) -> Dict[str, Any]:
        return self.call("getblockchaininfo", [])

    def decodescript(self, script_hex: str) -> Dict[str, Any]:
        return self.call("decodescript", [script_hex])
