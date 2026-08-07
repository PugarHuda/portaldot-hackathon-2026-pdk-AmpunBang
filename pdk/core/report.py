"""Failure analytics: scan recent blocks and summarise every failed extrinsic.

This turns FailLens from a one-shot decoder into a triage tool — "what's been
failing on this chain, and why?" — useful for a dev chasing a flaky integration
or an operator watching a node. 100% metadata-driven, no mocks.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from pdk.config import RECENT_BLOCKS_SCAN
from pdk.core.decoder import DecodedError, decode_receipt, failed_receipts_in_block


@dataclass
class FailureHit:
    """One decoded failure, with the block it landed in."""

    block: int
    decoded: DecodedError


def scan_failures(substrate, blocks: int = RECENT_BLOCKS_SCAN) -> list[FailureHit]:
    """Walk back ``blocks`` from the chain head, decoding every failed extrinsic.

    Stops cleanly at the start of the chain (a short dev chain has fewer than
    ``blocks`` blocks; ``get_block`` then returns ``None``).
    """
    block_hash = substrate.get_chain_head()
    hits: list[FailureHit] = []
    for _ in range(blocks):
        block = substrate.get_block(block_hash=block_hash)
        if block is None:
            break
        number = int(block["header"]["number"])
        for receipt in failed_receipts_in_block(substrate, block_hash):
            decoded = decode_receipt(receipt, substrate)
            if decoded is not None:
                hits.append(FailureHit(block=number, decoded=decoded))
        parent = block["header"]["parentHash"]
        if not parent or parent == block_hash:
            break
        block_hash = parent
    return hits


def label(decoded: DecodedError, matched_key: str | None = None) -> str:
    """Best display label for grouping — prefer the KB-matched ``Pallet.Error``,
    fall back to the decoded name (the pallet is often a generic ``Module``)."""
    if matched_key:
        pallet, _, name = matched_key.partition(".")
        return f"{pallet.title()}.{name}"
    if decoded.pallet and decoded.pallet not in ("Module", "Unknown"):
        return f"{decoded.pallet}.{decoded.name}"
    return decoded.name


def summarize(labels: list[str]) -> list[tuple[str, int]]:
    """Count occurrences per label, most frequent first (ties: alphabetical)."""
    counts = Counter(labels)
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
