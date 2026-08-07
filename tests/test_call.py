"""Offline coverage for `pdk call`'s argument classification and coercion,
plus `pdk assets`' amount parsing.

These are the parts that decide what actually gets SCALE-encoded and
signed, so they are worth pinning without a node: a misclassification
here means signing something other than what the user typed.
"""

from __future__ import annotations

import pytest
import typer
from scalecodec.base import RuntimeConfigurationObject
from scalecodec.type_registry import load_type_registry_preset

from pdk.commands.assets import _parse_amount
from pdk.commands.call import classify_type, coerce_arg, unwrap_compact

ALICE = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
BOB = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"


@pytest.fixture(scope="module")
def runtime() -> RuntimeConfigurationObject:
    """Bundled presets only. `legacy` carries the V13-era aliases this
    runtime declares its call arguments with."""
    config = RuntimeConfigurationObject(ss58_format=42)
    config.update_type_registry(load_type_registry_preset("core"))
    config.update_type_registry(load_type_registry_preset("legacy"))
    return config


class TestUnwrapCompact:
    def test_peels_a_single_layer(self) -> None:
        assert unwrap_compact("Compact<Balance>") == "Balance"

    def test_peels_nested_layers(self) -> None:
        assert unwrap_compact("Compact<Compact<u32>>") == "u32"

    def test_leaves_a_bare_type_alone(self) -> None:
        assert unwrap_compact("AccountId") == "AccountId"

    def test_does_not_peel_a_lookalike(self) -> None:
        # Vec<u8> is a byte string, not a compact-wrapped u8.
        assert unwrap_compact("Vec<u8>") == "Vec<u8>"


class TestClassifyType:
    @pytest.mark.parametrize("declared", ["AccountId", "LookupSource", "MultiAddress", "Address", "accountid"])
    def test_account_shapes(self, runtime, declared: str) -> None:
        assert classify_type(runtime, declared) == "accountId"

    @pytest.mark.parametrize("declared", ["u8", "u32", "u128", "Compact<Balance>", "Compact<AssetId>"])
    def test_plain_and_compact_numbers(self, runtime, declared: str) -> None:
        assert classify_type(runtime, declared) == "integer"

    @pytest.mark.parametrize("declared", ["BalanceOf", "BlockNumber", "EraIndex", "Perbill", "Weight"])
    def test_numeric_aliases_resolve_through_the_registry(self, runtime, declared: str) -> None:
        # The point of asking the registry instead of keeping a name list:
        # every one of these is declared on portaldot-1002 and none of them
        # look like a number by name.
        assert classify_type(runtime, declared) == "integer"

    def test_bool(self, runtime) -> None:
        assert classify_type(runtime, "bool") == "bool"

    @pytest.mark.parametrize("declared", ["Bytes", "Vec<u8>"])
    def test_byte_strings(self, runtime, declared: str) -> None:
        assert classify_type(runtime, declared) == "bytes"

    @pytest.mark.parametrize("declared", ["Call", "Vec<AccountId>", "Option<u32>", "[u8; 32]"])
    def test_composites_are_unsupported(self, runtime, declared: str) -> None:
        assert classify_type(runtime, declared) == "unsupported"

    def test_an_unknown_name_is_unsupported_not_a_crash(self, runtime) -> None:
        assert classify_type(runtime, "NoSuchTypeXyz") == "unsupported"

    def test_account_id_is_never_read_as_a_number(self, runtime) -> None:
        # Guard against re-introducing an "ends with Id" heuristic:
        # AccountId is a 32-byte hash, and coercing it as an integer would
        # silently mis-encode a recipient.
        assert classify_type(runtime, "AccountId") != "integer"


class TestCoerceArg:
    def test_account_uri_derives_an_address(self) -> None:
        assert coerce_arg("accountId", "//Alice", "dest") == ALICE

    def test_shell_mangled_uri_is_repaired(self) -> None:
        # Git Bash rewrites `//Bob` to `/Bob`, which derives a DIFFERENT
        # valid keypair — the whole reason resolve_account exists.
        assert coerce_arg("accountId", "/Bob", "dest") == BOB
        assert coerce_arg("accountId", "Bob", "dest") == BOB

    def test_ss58_passes_through(self) -> None:
        assert coerce_arg("accountId", ALICE, "dest") == ALICE

    def test_integer(self) -> None:
        assert coerce_arg("integer", " 1000 ", "value") == 1000

    @pytest.mark.parametrize("bad", ["0x10", "-1", "", "1.5", "1e3"])
    def test_integer_refuses_anything_it_would_have_to_guess_at(self, bad: str) -> None:
        # int()/BigInt() would take "0x10" as 16 — silently signing an
        # amount the user never typed.
        with pytest.raises(typer.BadParameter):
            coerce_arg("integer", bad, "value")

    def test_bool_both_ways_case_insensitively(self) -> None:
        assert coerce_arg("bool", "TRUE", "keep_alive") is True
        assert coerce_arg("bool", "false", "keep_alive") is False

    def test_bool_refuses_truthy_lookalikes(self) -> None:
        for bad in ("1", "yes", "on"):
            with pytest.raises(typer.BadParameter):
                coerce_arg("bool", bad, "keep_alive")

    def test_bytes_requires_0x_hex(self) -> None:
        assert coerce_arg("bytes", "0xdeadBEEF", "remark") == "0xdeadBEEF"
        for bad in ("deadbeef", "0xzz", "hello"):
            with pytest.raises(typer.BadParameter):
                coerce_arg("bytes", bad, "remark")

    def test_unsupported_is_a_named_error(self) -> None:
        with pytest.raises(typer.BadParameter, match="unsupported argument type"):
            coerce_arg("unsupported", "anything", "call (Call)")


class TestAssetsParseAmount:
    def test_accepts_whole_numbers(self) -> None:
        assert _parse_amount("1000", "--amount") == 1000
        assert _parse_amount(" 7 ", "--amount") == 7

    @pytest.mark.parametrize("bad", ["0x10", "-1", "1.5", "", "1_000"])
    def test_refuses_everything_else(self, bad: str) -> None:
        with pytest.raises(typer.BadParameter):
            _parse_amount(bad, "--amount")
