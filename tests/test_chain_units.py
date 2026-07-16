"""Unit tests for the pure (no-node) helpers in pdk.core.chain.

Covers the money-conversion and account-URI-normalization logic that
`send`, `simulate`, `seed`, and `keys` all route through. These are the
correctness-critical paths: `pot_to_plancks` feeds a REAL on-chain
transfer amount, and `normalise_account_uri` picks the recipient.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from scalecodec.base import RuntimeConfigurationObject, ScaleBytes
from scalecodec.type_registry import load_type_registry_preset

from pdk.core.chain import (
    POT_DECIMALS,
    _ASSETS_BALANCE_ARG,
    _fix_assets_balance_width,
    detect_git_bash_mangling,
    normalise_account_uri,
    pot_to_plancks,
)


class TestPotToPlancks:
    def test_whole_number(self) -> None:
        assert pot_to_plancks(1) == 10**POT_DECIMALS
        assert pot_to_plancks(100) == 100 * 10**POT_DECIMALS

    def test_precision_cases_that_float_gets_wrong(self) -> None:
        # These are the exact values where `int(amount * 10**14)` loses a
        # planck to float64 rounding. The whole point of the helper.
        assert pot_to_plancks(2.3) == 230000000000000
        assert pot_to_plancks(0.7) == 70000000000000

    def test_matches_decimal_reference_across_a_range(self) -> None:
        for amt in [0.1, 0.7, 1.1, 2.3, 3.3, 100.7, 1234.5678, 9999.99, 0.00000000000001]:
            assert pot_to_plancks(amt) == int(Decimal(str(amt)) * 10**POT_DECIMALS), f"{amt} mismatch"

    def test_accepts_string_input(self) -> None:
        assert pot_to_plancks("2.3") == 230000000000000

    def test_zero_is_allowed(self) -> None:
        assert pot_to_plancks(0) == 0

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            pot_to_plancks(-1.0)

    def test_non_numeric_raises(self) -> None:
        with pytest.raises(ValueError, match="not a valid POT amount"):
            pot_to_plancks("not a number")

    def test_truncates_sub_planck_toward_zero(self) -> None:
        # A plancks is indivisible; sub-planck remainders truncate down.
        # 1e-15 POT is 0.1 plancks -> 0.
        assert pot_to_plancks("0.000000000000001") == 0


class TestNormaliseAccountUri:
    def test_double_slash_passes_through(self) -> None:
        assert normalise_account_uri("//Alice") == "//Alice"

    def test_single_slash_git_bash_mangling_recovered(self) -> None:
        # Git Bash strips one leading slash: //Bob -> /Bob. Must recover.
        assert normalise_account_uri("/Bob") == "//Bob"

    def test_bare_name_becomes_uri(self) -> None:
        assert normalise_account_uri("Charlie") == "//Charlie"

    def test_ss58_address_passes_through(self) -> None:
        addr = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
        assert normalise_account_uri(addr) == addr

    def test_mnemonic_phrase_passes_through(self) -> None:
        phrase = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
        assert normalise_account_uri(phrase) == phrase


class TestDetectGitBashMangling:
    def test_recognises_full_path_rewrite(self) -> None:
        hint = detect_git_bash_mangling("C:/Program Files/Git/Alice")
        assert hint is not None
        assert "//Alice" in hint

    def test_clean_uri_returns_none(self) -> None:
        assert detect_git_bash_mangling("//Alice") is None
        assert detect_git_bash_mangling("5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty") is None


def _offline_runtime_config() -> RuntimeConfigurationObject:
    """A scalecodec runtime config built from bundled presets only — no node
    needed. Enough to exercise `_fix_assets_balance_width`'s pure byte
    surgery in isolation."""
    rc = RuntimeConfigurationObject()
    rc.update_type_registry(load_type_registry_preset("core"))
    return rc


class _FakeSubstrate:
    """Stand-in for SubstrateInterface: `_fix_assets_balance_width` only
    touches `.runtime_config`."""

    def __init__(self) -> None:
        self.runtime_config = _offline_runtime_config()


class _FakeCall:
    """Stand-in for GenericCall: `_fix_assets_balance_width` only reads/
    reassigns `.data`."""

    def __init__(self, data: ScaleBytes) -> None:
        self.data = data


class TestFixAssetsBalanceWidth:
    """Regression coverage for the `Assets.create` "bad signature" bug:
    substrate-interface encodes `min_balance` (metadata type `T::Balance`,
    stripped to the ambiguous bare name `Balance`) as u128 (16 bytes)
    instead of the runtime's actual u64 (8 bytes) — verified byte-for-byte
    against @polkadot/api and against a live Portaldot dev node, where the
    unpatched call is rejected at the RPC layer with "Invalid Transaction:
    bad signature" (1010) before it ever reaches dispatch."""

    def test_corrects_u128_tail_to_u64(self) -> None:
        substrate = _FakeSubstrate()
        prefix = b"\x1a\x00\x96\xfe\x3c\x00\x00"  # arbitrary call_index + id bytes
        wrong_tail = bytes(substrate.runtime_config.create_scale_object("u128").encode(1).data)
        call = _FakeCall(ScaleBytes(prefix + wrong_tail))

        fixed = _fix_assets_balance_width(substrate, call, 1)

        correct_tail = bytes(substrate.runtime_config.create_scale_object("u64").encode(1).data)
        assert bytes(fixed.data.data) == prefix + correct_tail
        assert len(fixed.data.data) == len(prefix) + 8  # 8 bytes shorter than the broken 16-byte tail

    def test_preserves_the_signed_value(self) -> None:
        substrate = _FakeSubstrate()
        value = 999_888_777
        wrong_tail = bytes(substrate.runtime_config.create_scale_object("u128").encode(value).data)
        call = _FakeCall(ScaleBytes(b"" + wrong_tail))

        fixed = _fix_assets_balance_width(substrate, call, value)

        assert int.from_bytes(bytes(fixed.data.data), "little") == value

    def test_refuses_to_patch_an_unrecognised_shape(self) -> None:
        # Guards against silently mis-signing if a future metadata/runtime
        # change makes this assumption stale — better a loud error than a
        # quietly wrong signature.
        substrate = _FakeSubstrate()
        call = _FakeCall(ScaleBytes(b"\x00\x01\x02"))

        with pytest.raises(RuntimeError, match="no longer matches"):
            _fix_assets_balance_width(substrate, call, 1)

    def test_only_create_is_patched(self) -> None:
        # mint/transfer's `amount` is `Compact<Balance>`: compact encoding
        # is width-agnostic for any value fitting in a u64, so the same
        # u128-vs-u64 ambiguity produces identical bytes either way and
        # doesn't need (or want) this patch — verified live against mint
        # and transfer, which sign and dispatch correctly unpatched.
        assert _ASSETS_BALANCE_ARG == {"create": "min_balance"}
