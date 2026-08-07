"""Offline coverage for pdk.core.events.

The bug these guard: Portaldot V13 metadata declares the Assets pallet's
amount fields as the bare name `Balance`, which resolves globally to u128
while pallet-assets actually uses u64. Because a block's events are one
SCALE-encoded `Vec<EventRecord>` read front to back, an over-wide read
desynchronises every event after it — verified live, `receipt.is_success`
raises for any block containing `Assets.Issued`/`Transferred`.

These tests build such a vec byte-for-byte and assert the decoder reads it
whole, with a `Treasury.Deposit` (a genuine u128 `Balance`) sitting in the
same vec so a naive global override can't pass.
"""

from __future__ import annotations

import pytest
from scalecodec.base import RuntimeConfigurationObject, ScaleBytes
from scalecodec.type_registry import load_type_registry_preset

from pdk.core.events import BlockEvent, decode_block_events, receipt_succeeded

ALICE = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"


def _runtime() -> RuntimeConfigurationObject:
    """Bundled presets only — the `legacy` preset carries the V13-era types
    (Phase, DispatchInfo, AssetId) this decoder walks."""
    # ss58_format matters: without it AccountId decodes to raw hex rather
    # than the SS58 text a live node's config yields, and the assertions
    # below would be testing the fixture instead of the decoder.
    runtime = RuntimeConfigurationObject(ss58_format=42)
    runtime.update_type_registry(load_type_registry_preset("core"))
    runtime.update_type_registry(load_type_registry_preset("legacy"))
    return runtime


# Pallet indices are arbitrary here — the decoder reads them from metadata.
_PALLETS = [
    {"name": "System", "index": 0, "events": [{"name": "ExtrinsicSuccess", "args": ["DispatchInfo"]},
                                              {"name": "ExtrinsicFailed", "args": ["DispatchError", "DispatchInfo"]}]},
    {"name": "Treasury", "index": 3, "events": [{"name": "Deposit", "args": ["Balance"]}]},
    {"name": "Assets", "index": 8, "events": [{"name": "Created", "args": ["AssetId", "AccountId", "AccountId"]},
                                              {"name": "Issued", "args": ["AssetId", "AccountId", "Balance"]}]},
]

_DISPATCH_INFO = {"weight": 295983000, "class": "Normal", "pays_fee": "Yes"}


class _Value:
    def __init__(self, value: dict) -> None:
        self.value = value


class _Metadata:
    def __init__(self) -> None:
        self.pallets = [_Value(p) for p in _PALLETS]


class _FakeSubstrate:
    """Only what pdk.core.events touches: a runtime config, metadata, and
    the one storage read that returns the raw event vec."""

    def __init__(self, raw_events: str) -> None:
        self.runtime_config = _runtime()
        self._raw = raw_events

    def get_metadata(self) -> _Metadata:
        return _Metadata()

    def create_storage_key(self, pallet: str, storage_function: str):
        assert (pallet, storage_function) == ("System", "Events")
        return _StorageKey()

    def rpc_request(self, method: str, params: list) -> dict:
        assert method == "state_getStorage"
        assert params[0].startswith("0x")
        return {"result": self._raw}


class _StorageKey:
    def to_hex(self) -> str:
        return "0x26aa394eea5630e07c48ae0c9558cef78"


def _encode_events(runtime: RuntimeConfigurationObject, records: list[tuple]) -> str:
    """Build a `Vec<EventRecord>` exactly as a node would: count, then per
    record phase / pallet index / event index / args / topics."""
    out = ScaleBytes(bytearray())
    out += runtime.create_scale_object("Compact<u32>").encode(len(records))
    for extrinsic_idx, pallet_index, event_index, arg_types_values in records:
        phase = {"ApplyExtrinsic": extrinsic_idx} if extrinsic_idx is not None else "Finalization"
        out += runtime.create_scale_object("Phase").encode(phase)
        out += runtime.create_scale_object("u8").encode(pallet_index)
        out += runtime.create_scale_object("u8").encode(event_index)
        for type_name, value in arg_types_values:
            out += runtime.create_scale_object(type_name).encode(value)
        out += runtime.create_scale_object("Vec<Hash>").encode([])
    return str(out)


def _mint_block() -> _FakeSubstrate:
    """The shape that broke substrate-interface live: an Assets.Issued whose
    amount the chain wrote as u64, followed by a Treasury.Deposit whose
    Balance genuinely is u128, then the extrinsic's success marker."""
    runtime = _runtime()
    raw = _encode_events(runtime, [
        (0, 0, 0, [("DispatchInfo", _DISPATCH_INFO)]),
        (1, 8, 1, [("AssetId", 93), ("AccountId", ALICE), ("u64", 1000)]),
        (1, 3, 0, [("Balance", 1_144_336_747_933)]),
        (1, 0, 0, [("DispatchInfo", _DISPATCH_INFO)]),
    ])
    return _FakeSubstrate(raw)


class _FakeReceipt:
    def __init__(self, extrinsic_idx: int | None = 1, block_hash: str | None = "0xblock") -> None:
        self.extrinsic_idx = extrinsic_idx
        self.block_hash = block_hash


class TestDecodeBlockEvents:
    def test_reads_an_assets_block_whole(self) -> None:
        events = decode_block_events(_mint_block(), "0xblock")

        assert [e.key for e in events] == [
            "System.ExtrinsicSuccess", "Assets.Issued",
            "Treasury.Deposit", "System.ExtrinsicSuccess",
        ]

    def test_narrows_balance_only_inside_assets(self) -> None:
        # The whole point: same declared type name, two different widths in
        # one vec. If Assets weren't narrowed the vec would not decode at
        # all; if Treasury were narrowed its value would come out wrong.
        events = decode_block_events(_mint_block(), "0xblock")

        assert events[1].args == [93, ALICE, 1000]
        assert events[2].args == [1_144_336_747_933]

    def test_attributes_events_to_their_extrinsic(self) -> None:
        events = decode_block_events(_mint_block(), "0xblock")

        assert events[0].extrinsic_idx == 0  # the timestamp inherent
        assert [e.extrinsic_idx for e in events[1:]] == [1, 1, 1]

    def test_block_level_phases_have_no_extrinsic(self) -> None:
        runtime = _runtime()
        raw = _encode_events(runtime, [(None, 3, 0, [("Balance", 7)])])

        assert decode_block_events(_FakeSubstrate(raw), "0xblock")[0].extrinsic_idx is None

    def test_empty_storage_is_no_events(self) -> None:
        assert decode_block_events(_FakeSubstrate(None), "0xblock") == []


class TestReceiptSucceeded:
    def test_confirms_success_from_the_extrinsics_own_event(self) -> None:
        assert receipt_succeeded(_mint_block(), _FakeReceipt(extrinsic_idx=1)) is True

    def test_ignores_another_extrinsics_success(self) -> None:
        # Extrinsic 2 isn't in this block at all. The inherent at index 0
        # succeeded, but that says nothing about ours — refuse to answer
        # rather than borrow someone else's outcome.
        with pytest.raises(RuntimeError, match="no System.ExtrinsicSuccess"):
            receipt_succeeded(_mint_block(), _FakeReceipt(extrinsic_idx=2))

    def test_reports_a_dispatch_failure_as_false(self) -> None:
        runtime = _runtime()
        raw = _encode_events(runtime, [
            (1, 3, 0, [("Balance", 12)]),
            (1, 0, 1, [("DispatchError", {"Module": {"index": 8, "error": 3}}),
                       ("DispatchInfo", _DISPATCH_INFO)]),
        ])

        assert receipt_succeeded(_FakeSubstrate(raw), _FakeReceipt(extrinsic_idx=1)) is False

    def test_refuses_a_receipt_with_no_block(self) -> None:
        # Never guess an outcome for an extrinsic we can't locate.
        with pytest.raises(RuntimeError, match="no extrinsic index or block hash"):
            receipt_succeeded(_mint_block(), _FakeReceipt(block_hash=None))

    def test_never_reads_is_success(self) -> None:
        # Regression guard for a measured trap: substrate-interface caches
        # partial state, so an `is_success` that raised once returns a bare
        # False on the next read. Touching it at all would turn a successful
        # mint into a reported failure.
        class _Exploding(_FakeReceipt):
            @property
            def is_success(self):  # pragma: no cover - must never be reached
                raise AssertionError("receipt_succeeded must not read is_success")

        assert receipt_succeeded(_mint_block(), _Exploding(extrinsic_idx=1)) is True


class TestBlockEvent:
    def test_key_joins_pallet_and_name(self) -> None:
        assert BlockEvent("Assets", "Issued", [], 1).key == "Assets.Issued"
