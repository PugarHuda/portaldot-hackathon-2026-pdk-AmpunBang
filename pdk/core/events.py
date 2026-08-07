"""Decode a block's events when substrate-interface can't.

This is the event-side twin of ``chain._fix_assets_balance_width``. Same
root cause, other side of the wire: Portaldot's V13 metadata declares the
Assets pallet's amount fields as the bare type name ``Balance``, and
substrate-interface resolves that name globally as u128 (the chain's
native POT width) because scalecodec's type registry has no pallet-scoped
override. Inside pallet-assets, ``Balance`` is actually u64.

On the *call* side that produced a bad signature. On the *event* side it
is worse: events are a single SCALE-encoded ``Vec<EventRecord>`` decoded
front to back, so reading 16 bytes where the chain wrote 8 desynchronises
every event after it. The decode doesn't return a wrong value, it walks
off the end of the buffer and raises — which is why ``receipt.is_success``
*throws* rather than lying, for any block containing ``Assets.Issued``,
``Assets.Transferred``, ``Assets.Burned``, ``ApprovedTransfer`` or
``TransferredApproved``. Verified live against portaldot-1002:
``Assets.mint`` and ``Assets.transfer`` both raise
``RemainingScaleBytesNotEmptyException``; ``Assets.create`` doesn't,
because ``Assets.Created`` carries no ``Balance`` field.

A global registry override can't fix this: a single ``Assets.mint`` block
contains both an ``Assets.Issued`` (u64) and a ``Treasury.Deposit``
(u128), both declared ``Balance``. Correcting one by name corrupts the
other. So this walks the vec itself and substitutes u64 for ``Balance``
only within Assets events.

ponytail: only the Assets pallet is corrected, because it's the only one
verified mis-declared on this runtime. If another pallet turns up with
the same bare-``Balance``-as-u64 pattern, add it to ``_NARROW_BALANCE_
PALLETS`` rather than generalising to a heuristic — guessing widths is
how you silently mis-read money.
"""

from __future__ import annotations

from dataclasses import dataclass

from scalecodec.base import ScaleBytes

# Pallets whose bare `Balance` is narrower than the chain's native width.
_NARROW_BALANCE_PALLETS = {"Assets": "u64"}


@dataclass
class BlockEvent:
    """One decoded event, with the extrinsic it belongs to."""

    pallet: str
    name: str
    args: list
    extrinsic_idx: int | None  # None for Initialization/Finalization phases

    @property
    def key(self) -> str:
        return f"{self.pallet}.{self.name}"


def _event_types(substrate) -> dict[int, tuple[str, dict[int, tuple[str, list[str]]]]]:
    """Map pallet index → (pallet name, {event index: (event name, arg types)}).

    V13 metadata declares event args as plain type-name strings, which is
    exactly the ambiguity this module exists to work around.
    """
    mapping: dict[int, tuple[str, dict[int, tuple[str, list[str]]]]] = {}
    for position, pallet in enumerate(substrate.get_metadata().pallets):
        events = pallet.value.get("events") or []
        if not events:
            continue
        index = pallet.value.get("index")
        name = pallet.value.get("name")
        mapping[position if index is None else index] = (
            name,
            {i: (e.get("name"), list(e.get("args") or [])) for i, e in enumerate(events)},
        )
    return mapping


def decode_block_events(substrate, block_hash: str) -> list[BlockEvent]:
    """Decode every event in ``block_hash``, correcting Assets amount widths.

    Raises whatever scalecodec raises if the vec still doesn't decode — a
    loud failure beats a half-read event list that looks complete.
    """
    # Derived, not hardcoded: the literal twox128("System")++twox128("Events")
    # hex is high-entropy enough that secret scanners flag it as a credential.
    events_key = substrate.create_storage_key("System", "Events").to_hex()
    raw = substrate.rpc_request("state_getStorage", [events_key, block_hash])["result"]
    if not raw:
        return []

    runtime = substrate.runtime_config
    pallets = _event_types(substrate)
    data = ScaleBytes(raw)

    def take(type_name: str):
        return runtime.create_scale_object(type_name, data=data).decode(check_remaining=False)

    events: list[BlockEvent] = []
    for _ in range(take("Compact<u32>")):
        phase = take("Phase")
        pallet_index = take("u8")
        event_index = take("u8")

        pallet_name, known = pallets.get(pallet_index, (f"Pallet{pallet_index}", {}))
        event_name, arg_types = known.get(event_index, (f"Event{event_index}", []))

        narrow = _NARROW_BALANCE_PALLETS.get(pallet_name)
        args = [take(narrow if (narrow and t == "Balance") else t) for t in arg_types]
        take("Vec<Hash>")  # topics — decoded to advance the cursor, never used

        events.append(BlockEvent(pallet_name, event_name, args, _applied_to(phase)))

    return events


def _applied_to(phase) -> int | None:
    """Extrinsic index from a decoded ``Phase``, or None for block-level phases.

    scalecodec renders the enum as ``{'ApplyExtrinsic': 3}`` or the bare
    string ``'Finalization'`` depending on version, so handle both.
    """
    if isinstance(phase, dict):
        value = phase.get("ApplyExtrinsic")
        return int(value) if value is not None else None
    return None


def receipt_succeeded(substrate, receipt) -> bool:
    """Did this extrinsic succeed?

    Confirmed only by a positive ``System.ExtrinsicSuccess`` for this
    extrinsic — never by the absence of an error, which is the project's
    hard invariant on the money path.

    This always decodes the block itself rather than trying
    ``receipt.is_success`` first and falling back. Falling back looks
    cheaper and is a trap: substrate-interface caches partial state inside
    the receipt, so a ``is_success`` that raised once returns a plain
    ``False`` on the next read instead of raising again. Any caller that
    had already touched ``is_success`` — a log line, a debugger, an
    earlier guard — would then push this function down a path that reports
    a successful mint as failed. Measured live, that is exactly what
    happened. One decode path is worth an extra ``state_getStorage`` per
    confirmation.
    """
    index = getattr(receipt, "extrinsic_idx", None)
    if index is None or not receipt.block_hash:
        raise RuntimeError(
            "receipt carries no extrinsic index or block hash — cannot confirm the outcome."
        )
    for event in decode_block_events(substrate, receipt.block_hash):
        if event.extrinsic_idx == index and event.pallet == "System":
            if event.name == "ExtrinsicSuccess":
                return True
            if event.name == "ExtrinsicFailed":
                return False
    # Neither outcome event present: the extrinsic isn't in this block, or
    # the vec decoded into something we don't recognise. Say so instead of
    # defaulting either way.
    raise RuntimeError(
        f"no System.ExtrinsicSuccess/Failed found for extrinsic {index} "
        f"in block {receipt.block_hash} — cannot confirm the outcome."
    )
