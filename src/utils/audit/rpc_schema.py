from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class RpcSchemaAudit:
    sampled_blocks: int
    sampled_transactions: int
    sampled_vins: int
    sampled_vouts: int
    block_key_hits: Dict[str, int]
    vin_key_hits: Dict[str, int]
    vout_key_hits: Dict[str, int]
    issuance_key_hits: Dict[str, int]
    prevout_key_hits: Dict[str, int]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "sampled_blocks": self.sampled_blocks,
            "sampled_transactions": self.sampled_transactions,
            "sampled_vins": self.sampled_vins,
            "sampled_vouts": self.sampled_vouts,
            "block_key_hits": dict(self.block_key_hits),
            "vin_key_hits": dict(self.vin_key_hits),
            "vout_key_hits": dict(self.vout_key_hits),
            "issuance_key_hits": dict(self.issuance_key_hits),
            "prevout_key_hits": dict(self.prevout_key_hits),
        }

