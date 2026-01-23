from __future__ import annotations

from typing import Any, Dict, Protocol


class DbWriter(Protocol):
    def write_block(self, block: Dict[str, Any]) -> None: ...

    def write_transaction(self, tx: Dict[str, Any]) -> None: ...

    def close(self) -> None: ...
