from __future__ import annotations

import json
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from .utils.elements_auth import resolve_rpc_auth


class RpcError(RuntimeError):
    pass


# HTTP statuses worth retrying when the body is not a decodable JSON-RPC payload.
# A JSON-RPC error body (elementsd often returns it with HTTP 500) is handled before
# this and surfaces as RpcError instead of being retried.
_TRANSIENT_STATUSES = frozenset({429, 500, 502, 503, 504})
_UNSET = object()


class LiquidRpc:
    """Minimal JSON-RPC client for Elements/Liquid nodes.

    - Supports batch calls.
    - Decodes JSON with Decimal to avoid precision loss.
    - Accepts URIs like http://user:pass@host:7041.
    """

    def __init__(
        self,
        provider_uri: str,
        timeout: float = 30.0,
        datadir: Optional[str] = None,
        use_decimal: bool = True,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        max_backoff: float = 30.0,
    ):
        self._provider_uri = provider_uri
        self._timeout = timeout
        self._session = requests.Session()
        self._use_decimal = bool(use_decimal)
        self._max_retries = max(0, int(max_retries))
        self._backoff_base = float(backoff_base)
        self._max_backoff = float(max_backoff)

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
        if self._use_decimal:
            return json.loads(text, parse_float=Decimal)
        return json.loads(text)

    def _sleep_backoff(self, attempt: int) -> None:
        delay = min(self._max_backoff, self._backoff_base * (2**attempt))
        if delay > 0:
            time.sleep(delay)

    def _post(self, body: str) -> Any:
        """POST with bounded retry on transient failures; return the decoded JSON body.

        The body is decoded before any HTTP status check so a JSON-RPC error returned
        with HTTP 500 surfaces as RpcError (via the caller) rather than a generic
        HTTPError. Connection errors, timeouts and transient statuses with no JSON body
        are retried with exponential backoff.
        """
        last: Any = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._session.post(
                    self._url, headers=self._headers, data=body, timeout=self._timeout
                )
            except (requests.ConnectionError, requests.Timeout) as e:
                last = e
            else:
                decoded = _UNSET
                try:
                    decoded = self._decode(resp.text)
                except ValueError:
                    decoded = _UNSET
                if decoded is not _UNSET:
                    return decoded
                status = getattr(resp, "status_code", None)
                if status not in _TRANSIENT_STATUSES:
                    resp.raise_for_status()
                    raise RpcError(f"non-JSON response from node (HTTP {status})")
                last = RpcError(f"HTTP {status} from node")

            if attempt < self._max_retries:
                self._sleep_backoff(attempt)
                continue
            raise RpcError(f"RPC request failed after {attempt + 1} attempt(s): {last}")

    def call(self, method: str, params: Optional[List[Any]] = None) -> Any:
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or [],
        }
        data = self._post(json.dumps(payload))
        if not isinstance(data, dict):
            raise RpcError(f"unexpected RPC response for {method}: {data!r}")
        if data.get("error"):
            raise RpcError(str(data["error"]))
        return data.get("result")

    def batch_call(self, calls: List[Tuple[str, List[Any]]]) -> List[Any]:
        batch = []
        for method, params in calls:
            self._request_id += 1
            batch.append(
                {"jsonrpc": "2.0", "id": self._request_id, "method": method, "params": params or []}
            )
        results = self._post(json.dumps(batch))
        if not isinstance(results, list):
            raise RpcError(f"expected a batch array response, got {type(results).__name__}")
        # Map by id so ordering is independent of the node's response order.
        id_to_result: Dict[int, Any] = {}
        for item in results:
            if not isinstance(item, dict):
                raise RpcError(f"malformed batch response item: {item!r}")
            if item.get("error"):
                raise RpcError(str(item["error"]))
            if "id" not in item:
                raise RpcError("batch response item missing 'id'")
            id_to_result[item["id"]] = item.get("result")
        missing = [req["id"] for req in batch if req["id"] not in id_to_result]
        if missing:
            raise RpcError(f"batch response missing ids: {missing}")
        return [id_to_result[req["id"]] for req in batch]

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:
            pass

    def __enter__(self) -> "LiquidRpc":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

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
