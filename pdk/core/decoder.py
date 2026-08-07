"""Decode a failed Portaldot transaction into a structured, named error.

A failed extrinsic emits a ``System.ExtrinsicFailed`` event carrying a
``DispatchError``. substrate-interface already resolves that DispatchError
against chain metadata and exposes it via ``ExtrinsicReceipt.error_message``
(error name + doc comment). FailLens builds on that: it wraps the receipt's
error into a :class:`DecodedError` and, for a bare tx hash, locates the
receipt by scanning recent blocks.

Verified against a live `portaldot-1002` node as part of the 84
integration & stress cases referenced in the project README.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from substrateinterface import ExtrinsicReceipt, SubstrateInterface

from pdk.config import RECENT_BLOCKS_SCAN
from pdk.core.events import decode_block_events, receipt_succeeded

# Strips ASCII control characters (0x00-0x1F, 0x7F) except \t and \n.
# Doc comments are free-form Rust text with no syntax restriction, so a
# malicious/compromised chain could embed a raw terminal escape sequence
# (ESC 0x1B) — e.g. an OSC 8 hyperlink escape — that a real terminal
# renders as a clickable link, completely bypassing Rich's own
# markup.escape() (which only handles Rich's `[tag]` bracket syntax,
# not raw control bytes). This is the source-level sanitizer; render
# sites additionally call rich.markup.escape() for Rich's own syntax —
# two different mechanisms, both needed.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def strip_control_chars(text: str) -> str:
    """Remove ASCII control characters (keeps \\t and \\n) from untrusted
    chain-sourced free text before it ever reaches a render call."""
    return _CONTROL_CHARS.sub("", text)


@dataclass
class DecodedError:
    """A fully decoded, human-readable extrinsic error."""

    pallet: str  # e.g. "Balances" — "Unknown" if the error carries no type
    name: str  # e.g. "InsufficientBalance"
    docs: str  # doc comment from chain metadata, via the receipt
    extrinsic_call: str  # e.g. "Balances.transfer_keep_alive" (best-effort)

    @property
    def key(self) -> str:
        """Knowledge-base lookup key, e.g. 'balances.InsufficientBalance'."""
        return f"{self.pallet.lower()}.{self.name}"


def decode_receipt(receipt: ExtrinsicReceipt, substrate: SubstrateInterface | None = None) -> DecodedError | None:
    """Wrap a failed :class:`ExtrinsicReceipt` into a :class:`DecodedError`.

    Returns ``None`` if the extrinsic actually succeeded — there is nothing
    to debug in that case.

    Pass ``substrate`` so the success check goes through
    :func:`receipt_succeeded`, which survives Assets blocks that
    ``receipt.is_success`` cannot decode. Omitting it keeps the plain
    substrate-interface check, which is only safe when the caller already
    knows the block holds no Assets amount events.
    """
    if receipt_succeeded(substrate, receipt) if substrate is not None else receipt.is_success:
        return None

    # substrate-interface exposes the decoded error in the shape
    #   {'type': 'Balances', 'name': 'InsufficientBalance', 'docs': 'Balance too low'}
    # 'type' is the pallet name; there are no separate module/error indices.
    err = receipt.error_message or {}
    name = err.get("name") or "UnknownError"
    pallet = err.get("type") or "Unknown"

    docs_value = err.get("docs", "")
    docs = strip_control_chars(" ".join(docs_value) if isinstance(docs_value, list) else str(docs_value))

    extrinsic_call = ""
    call = getattr(receipt, "extrinsic", None)
    if call is not None:
        module = getattr(call, "call_module", None)
        function = getattr(call, "call_function", None)
        # call_module/call_function may be objects — coerce to their names.
        mod_name = getattr(module, "name", module)
        fn_name = getattr(function, "name", function)
        if mod_name and fn_name:
            extrinsic_call = f"{mod_name}.{fn_name}"

    return DecodedError(
        pallet=str(pallet),
        name=str(name),
        docs=docs,
        extrinsic_call=extrinsic_call,
    )


def failed_receipts_in_block(
    substrate: SubstrateInterface,
    block_hash: str,
) -> list[ExtrinsicReceipt]:
    """Return an :class:`ExtrinsicReceipt` for each failed extrinsic in a block.

    Scans the block's events for ``System.ExtrinsicFailed``; for each, maps the
    event's ``extrinsic_idx`` back to the extrinsic and builds a receipt. Used by
    ``pdk debug --watch`` to surface failures as blocks are produced.

    Reads events through :func:`pdk.core.events.decode_block_events` rather
    than ``substrate.get_events``: the latter cannot decode any block
    containing an Assets amount event on Portaldot's V13 metadata, so
    ``watch``/``report`` would crash on the whole block — including the
    unrelated failures in it — instead of reporting them.
    """
    receipts: list[ExtrinsicReceipt] = []
    block = None
    for event in decode_block_events(substrate, block_hash):
        if event.pallet == "System" and event.name == "ExtrinsicFailed":
            idx = event.extrinsic_idx
            if idx is None:
                continue
            if block is None:
                block = substrate.get_block(block_hash=block_hash)
            extrinsic = block["extrinsics"][idx]
            ext_hash = getattr(extrinsic, "extrinsic_hash", None)
            if ext_hash is None:
                continue
            receipts.append(
                ExtrinsicReceipt(
                    substrate=substrate,
                    extrinsic_hash="0x" + ext_hash.hex(),
                    block_hash=block_hash,
                )
            )
    return receipts


def find_receipt(
    substrate: SubstrateInterface,
    tx_hash: str,
    scan_blocks: int = RECENT_BLOCKS_SCAN,
) -> ExtrinsicReceipt | None:
    """Locate the :class:`ExtrinsicReceipt` for a bare tx hash.

    Substrate does not index tx hash -> block, so this walks back from the
    chain head up to ``scan_blocks`` blocks looking for a matching extrinsic.
    Fine for a local dev node; returns ``None`` if not found in range.
    """
    target = tx_hash.lower().removeprefix("0x")
    block_hash = substrate.get_chain_head()

    for _ in range(scan_blocks):
        block = substrate.get_block(block_hash=block_hash)
        if block is None:
            # Walked past the start of the chain (genesis' parent is the zero
            # hash, which has no block). On a short chain this is the normal
            # "not found" terminus — stop instead of crashing.
            break
        for extrinsic in block["extrinsics"]:
            ext_hash = getattr(extrinsic, "extrinsic_hash", None)
            if ext_hash and ext_hash.hex().lower() == target:
                return ExtrinsicReceipt(
                    substrate=substrate,
                    extrinsic_hash=f"0x{target}",
                    block_hash=block_hash,
                )
        parent = block["header"]["parentHash"]
        if not parent or parent == block_hash:
            break
        block_hash = parent

    return None
