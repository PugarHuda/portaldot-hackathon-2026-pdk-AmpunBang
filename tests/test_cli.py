"""CLI smoke tests — exercise the typer app wiring without a node."""

from __future__ import annotations

import json as _json
import os
import re
import subprocess
import sys

from typer.testing import CliRunner

from pdk import __version__
from pdk.cli import app

runner = CliRunner()

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Rich's ReprHighlighter auto-styles numbers it finds in printed text,
    splitting a plain substring like "at least 1" across two ANSI-colored
    spans. Strip escape codes before asserting on substrings that include
    a number, rather than asserting against raw styled output."""
    return _ANSI_RE.sub("", text)


def test_help_lists_all_commands(monkeypatch) -> None:
    monkeypatch.setenv("COLUMNS", "200")
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("up", "accounts", "debug", "explain", "doctor", "simulate", "seed",
                    "pallets", "send", "fund", "storage", "watch", "keys", "report", "ai-setup"):
        assert command in result.output


def test_version_flag_reports_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_version_matches_pyproject() -> None:
    # Regression guard: pdk/__init__.py's __version__ drifted from
    # pyproject.toml's version for a full release (0.1.6 vs 0.1.7 on PyPI)
    # because the only prior test compared __version__ against itself, not
    # against the source of truth. Cross-check both against pyproject.toml
    # directly so a bump to one without the other fails CI.
    import tomllib
    from pathlib import Path

    pyproject = tomllib.loads((Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == pyproject["project"]["version"]


def test_debug_without_hash_or_demo_errors() -> None:
    # No node is contacted: the missing-argument check runs first.
    result = runner.invoke(app, ["debug"])
    assert result.exit_code != 0


def test_debug_json_error_path_emits_valid_json() -> None:
    # CI-citizen contract: `pdk debug --json` must ALWAYS emit parseable
    # JSON, even on the bad-input path — a consumer piping to jq must not
    # hit human-readable Rich text. (Regression: these paths used to print
    # console text and break the pipe.)
    result = runner.invoke(app, ["debug", "--json"])
    assert result.exit_code != 0
    payload = _json.loads(result.output)
    assert "error" in payload
    # no Rich markup leaked into the machine-readable field
    assert "[red]" not in payload["error"]


def test_debug_json_unreachable_node_emits_valid_json() -> None:
    # The connection-failure path must also be JSON under --json.
    result = runner.invoke(
        app, ["debug", "0xdeadbeef", "--json", "--node", "ws://127.0.0.1:19999"]
    )
    assert result.exit_code != 0
    payload = _json.loads(result.output)
    assert "error" in payload
    assert "detail" in payload


def test_doctor_json_unreachable_emits_valid_json() -> None:
    # doctor --json must emit JSON (not Rich text) on the connection-fail
    # path — a CI health-check consumer pipes it to jq.
    result = runner.invoke(app, ["doctor", "--json", "--node", "ws://127.0.0.1:19999"])
    assert result.exit_code != 0
    payload = _json.loads(result.output)
    assert "error" in payload and "detail" in payload


def test_accounts_json_unreachable_emits_valid_json() -> None:
    result = runner.invoke(app, ["accounts", "--json", "--node", "ws://127.0.0.1:19999"])
    assert result.exit_code != 0
    payload = _json.loads(result.output)
    assert "error" in payload


def test_pallets_json_unreachable_emits_valid_json() -> None:
    result = runner.invoke(app, ["pallets", "--json", "--node", "ws://127.0.0.1:19999"])
    assert result.exit_code != 0
    payload = _json.loads(result.output)
    assert "error" in payload and "detail" in payload


def test_report_rejects_non_positive_blocks() -> None:
    # The guard runs before any node connection — a negative/zero scan is
    # a mistake, not a silent "no failures in the last -5 blocks" no-op.
    for bad in ("-5", "0"):
        result = runner.invoke(app, ["report", "--blocks", bad])
        assert result.exit_code == 1
        assert "at least 1" in _strip_ansi(result.output)


def test_report_non_positive_blocks_json_is_valid() -> None:
    result = runner.invoke(app, ["report", "--blocks", "-1", "--json"])
    assert result.exit_code == 1
    assert "error" in _json.loads(result.output)


def test_simulate_rejects_negative_amount() -> None:
    # The amount guard runs before any node connection.
    result = runner.invoke(app, ["simulate", "--amount", "-5"])
    assert result.exit_code == 1
    assert "non-negative" in result.output.lower()


def test_debug_help_documents_auto_ai_and_no_ai(monkeypatch) -> None:
    # The auto-on AI UX is a deliberate design choice — make sure both
    # opt-out (--no-ai) and the force-attempt flag (--ai) stay discoverable
    # from the command's --help so reviewers can find them without docs.
    monkeypatch.setenv("COLUMNS", "200")
    result = runner.invoke(app, ["debug", "--help"])
    assert result.exit_code == 0
    output = " ".join(result.output.split())
    # Both flags should be mentioned by their distinguishing description text.
    assert "Skip the AI diagnosis" in output, "--no-ai opt-out is missing from help"
    assert "Force the AI diagnosis" in output, "--ai force flag is missing from help"


def test_debug_help_advertises_ci_gating(monkeypatch) -> None:
    # The CI-gating contract must be discoverable from --help (no node needed).
    # We can't substring-check the flag name itself: typer/Rich on a no-TTY
    # GitHub Actions runner inserts soft-wrap markers that break `--exit-code`
    # apart even at COLUMNS=200. Check the description text instead — it
    # word-wraps cleanly and is unique to this option.
    monkeypatch.setenv("COLUMNS", "200")
    result = runner.invoke(app, ["debug", "--help"])
    assert result.exit_code == 0
    # The phrase "CI pipeline gating" appears only in the --exit-code option's
    # description; finding it proves the flag is wired and documented.
    output_normalised = " ".join(result.output.split())
    assert "CI pipeline gating" in output_normalised


def test_explain_lists_all_when_no_argument() -> None:
    # Listing the knowledge base needs no node.
    result = runner.invoke(app, ["explain"])
    assert result.exit_code == 0
    assert "InsufficientBalance" in result.output


def test_explain_unknown_error_exits_nonzero_gracefully() -> None:
    # An unknown error is a clean "not found" (scriptable), not a crash.
    result = runner.invoke(app, ["explain", "ZzzNotARealError"])
    assert result.exit_code == 1
    assert "No curated entry" in result.output


def test_no_ai_flag_suppresses_ai_when_key_is_set(monkeypatch) -> None:
    # Regression guard for the new auto-on AI UX: setting --no-ai must skip
    # the AI call even when a key is configured. We assert via the helper that
    # decides whether to run AI (avoids network), since `pdk explain <known>`
    # would otherwise contact OpenRouter when a key is in env.
    monkeypatch.setenv("PDK_AI_KEY", "test-key-not-used-because-we-skip")
    from pdk.commands.explain import _should_run_ai
    assert _should_run_ai(ai_flag=False, no_ai_flag=True) is False
    # And the default (no flag, key set) DOES auto-run.
    assert _should_run_ai(ai_flag=False, no_ai_flag=False) is True
    # --ai forces even when no_ai also passed? --no-ai wins (explicit opt-out).
    assert _should_run_ai(ai_flag=True, no_ai_flag=True) is False


def test_ai_setup_test_only_with_no_key_exits_nonzero(monkeypatch) -> None:
    # Calling --test without a key should fail loudly (so scripts can branch
    # on the exit code) rather than silently asking the user to set one up.
    monkeypatch.delenv("PDK_AI_KEY", raising=False)
    result = runner.invoke(app, ["ai-setup", "--test"])
    assert result.exit_code != 0
    assert "No key set" in result.output


def test_simulate_and_report_share_the_ai_gate(monkeypatch) -> None:
    # simulate and report each carry their own _should_run_ai (copied so the
    # gate stays local to the command module). Both must obey --no-ai and
    # auto-on with a key, exactly like debug/explain.
    monkeypatch.setenv("PDK_AI_KEY", "test-key")
    from pdk.commands.simulate import _should_run_ai as sim_gate
    from pdk.commands.report import _should_run_ai as rep_gate
    assert sim_gate(ai_flag=False, no_ai_flag=True) is False
    assert sim_gate(ai_flag=False, no_ai_flag=False) is True
    assert rep_gate(ai_flag=False, no_ai_flag=True) is False
    assert rep_gate(ai_flag=False, no_ai_flag=False) is True
    monkeypatch.delenv("PDK_AI_KEY", raising=False)
    assert sim_gate(ai_flag=False, no_ai_flag=False) is False
    assert rep_gate(ai_flag=False, no_ai_flag=False) is False


def test_force_ai_flag_runs_even_without_key(monkeypatch) -> None:
    # --ai is the explicit-opt-in path — it should attempt the AI call even
    # when PDK_AI_KEY is missing, so the user sees the setup hint instead of
    # silently getting nothing.
    monkeypatch.delenv("PDK_AI_KEY", raising=False)
    from pdk.commands.explain import _should_run_ai
    assert _should_run_ai(ai_flag=True, no_ai_flag=False) is True
    # And without the flag + no key, auto-mode stays silent.
    assert _should_run_ai(ai_flag=False, no_ai_flag=False) is False


def test_unicode_output_on_non_utf8_pipe_does_not_crash() -> None:
    # Regression: on a non-UTF-8 stdout (Windows cp1252 / a redirected pipe),
    # Rich output (box-drawing, em-dashes, ✗) crashed with UnicodeEncodeError.
    # pdk.cli forces UTF-8 at startup. `explain` renders a Rich panel, no node.
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    result = subprocess.run(
        [sys.executable, "-m", "pdk.cli", "explain", "InsufficientBalance"],
        capture_output=True, env=env,
    )
    assert result.returncode == 0
    assert b"Traceback" not in result.stderr


def test_explain_decodes_raw_module_error_code() -> None:
    # The hero case: decode `Module: { index: 6, error: 2 }` with no node.
    result = runner.invoke(app, ["explain", "--module", "6", "--error", "2"])
    assert result.exit_code == 0
    assert "Balances.InsufficientBalance" in result.output


def test_explain_raw_code_requires_both_indices() -> None:
    result = runner.invoke(app, ["explain", "--module", "6"])
    assert result.exit_code == 1


def test_explain_unknown_raw_code_is_graceful() -> None:
    result = runner.invoke(app, ["explain", "-m", "99", "-e", "99"])
    assert result.exit_code == 1
    assert "No error at module" in result.output


def test_explain_json_raw_code_matches_pdk_ts_shape() -> None:
    # `explain --json` (raw-code path) — offline, no node. Shape must
    # match pdk-ts so a script consumes either CLI. Canonical index
    # casing (Balances, not balances).
    result = runner.invoke(app, ["explain", "--module", "6", "--error", "2", "--json"])
    assert result.exit_code == 0
    d = _json.loads(result.output)
    assert d["palletName"] == "Balances"
    assert d["errorName"] == "InsufficientBalance"
    assert d["source"] == "index"
    assert d["kbEntry"] is True
    assert d["indexFingerprint"] == {"specName": "portaldot", "specVersion": 1002}
    assert set(d) >= {"palletIndex", "errorIndex", "palletName", "errorName", "key", "summary", "steps", "kbEntry", "source"}


def test_explain_json_name_lookup_source() -> None:
    result = runner.invoke(app, ["explain", "balances.InsufficientBalance", "--json"])
    assert result.exit_code == 0
    d = _json.loads(result.output)
    assert d["source"] == "kb-name-only"
    assert d["kbEntry"] is True


def test_explain_json_error_paths_emit_json() -> None:
    # missing --error, and a not-found name, both emit parseable JSON.
    r1 = runner.invoke(app, ["explain", "--module", "6", "--json"])
    assert r1.exit_code == 1
    assert "error" in _json.loads(r1.output)
    r2 = runner.invoke(app, ["explain", "TotallyFakeError", "--json"])
    assert r2.exit_code == 1
    assert "error" in _json.loads(r2.output)


def test_explain_raw_code_without_kb_entry_returns_decoded_name() -> None:
    # A raw code IN the index but WITHOUT a curated KB entry
    # (Contracts.InvalidContractOrigin at 13.5 — the one error-gap-closing
    # pass deliberately skipped: its doc comment, "An origin TrieId written
    # in the current block", is too terse to write a confident fix for)
    # must return the decoded name with kbEntry=false — NOT error. Mirrors
    # pdk-ts (summary=null, steps=[]). Offline, no node.
    result = runner.invoke(app, ["explain", "--module", "13", "--error", "5", "--json"])
    assert result.exit_code == 0
    d = _json.loads(result.output)
    assert d["errorName"] == "InvalidContractOrigin"
    assert d["kbEntry"] is False
    assert d["summary"] is None
    assert d["steps"] == []
    assert d["source"] == "index"


def test_explain_code_not_in_index_without_node_hints_live() -> None:
    # A code outside the offline index and no --node → error that points at
    # --live, rather than pretending the code doesn't exist anywhere.
    result = runner.invoke(app, ["explain", "--module", "250", "--error", "0"])
    assert result.exit_code == 1
    assert "--live" in result.output


def test_explain_live_unreachable_node_emits_json_error() -> None:
    result = runner.invoke(
        app, ["explain", "--module", "6", "--error", "2", "--live",
              "--node", "ws://127.0.0.1:19999", "--json"]
    )
    assert result.exit_code == 1
    assert "error" in _json.loads(result.output)


def test_resolve_code_maps_verified_index() -> None:
    from pdk.core.knowledge import resolve_code

    assert resolve_code(6, 2) == "Balances.InsufficientBalance"
    assert resolve_code(99, 99) is None


def test_keys_inspect_uri() -> None:
    # Keypair derivation needs no node.
    result = runner.invoke(app, ["keys", "//Alice"])
    assert result.exit_code == 0
    assert "SS58 address" in result.output


def test_keys_generate() -> None:
    result = runner.invoke(app, ["keys"])
    assert result.exit_code == 0
    assert "Mnemonic" in result.output


def test_keys_alice_matches_canonical_dev_address() -> None:
    # Locks the actual VALUE, not just "some address appeared" — this is
    # the address every //Alice-derived dev fixture in the ecosystem
    # expects. A regression here would silently sign with the wrong key.
    result = runner.invoke(app, ["keys", "//Alice"])
    assert result.exit_code == 0
    assert "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY" in result.output


def test_keys_bob_matches_canonical_dev_address() -> None:
    result = runner.invoke(app, ["keys", "//Bob"])
    assert result.exit_code == 0
    assert "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty" in result.output


def test_keys_normalises_git_bash_single_slash_mangling() -> None:
    # Git Bash strips one leading slash from `//Alice`, so pdk sees
    # `/Alice`. Without _normalise_uri this silently derives a
    # DIFFERENT keypair with no error — a wrong-answer bug, not a
    # crash. Locks that `/Alice` resolves to the same canonical
    # address as `//Alice`.
    # Helpers moved to pdk.core.chain so `send`/`simulate` share them
    # (see test_chain_units.py for the full matrix); the `///` edge case
    # lives here.
    from pdk.core.chain import normalise_account_uri

    assert normalise_account_uri("/Alice") == "//Alice"
    assert normalise_account_uri("//Alice") == "//Alice"
    assert normalise_account_uri("Alice") == "//Alice"
    assert normalise_account_uri("///") == "///"  # not a bare identifier — passes through
    # A real mnemonic phrase must never be treated as a URI.
    mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
    assert normalise_account_uri(mnemonic) == mnemonic


def test_keys_detects_git_bash_full_path_mangling() -> None:
    from pdk.core.chain import detect_git_bash_mangling

    hint = detect_git_bash_mangling("C:/Program Files/Git/Alice")
    assert hint is not None
    assert "//Alice" in hint
    assert detect_git_bash_mangling("//Alice") is None


def test_keys_malformed_uri_gives_readable_error_not_internal_leak() -> None:
    # `//`, `/`, `//Alice/` all previously surfaced substrate-interface's
    # raw `'NoneType' object has no attribute 'groupdict'` — a Python
    # implementation detail meaningless to a CLI user.
    result = runner.invoke(app, ["keys", "//"])
    assert result.exit_code != 0
    assert "groupdict" not in result.output
    assert "NoneType" not in result.output


def test_keys_json_matches_canonical_address() -> None:
    # pdk-ts's `keys --json` has existed since its first alpha; Python's
    # `pdk keys` had no --json at all until this test was written.
    # Scripts (seed fixtures, CI) need this to grab an address without
    # scraping a Rich table.
    result = runner.invoke(app, ["keys", "//Alice", "--json"])
    assert result.exit_code == 0
    payload = _json.loads(result.output)
    assert payload["ss58_address"] == "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
    assert payload["public_key"].startswith("0x")
    assert payload["type"] == "sr25519"


def test_keys_json_generate_includes_mnemonic() -> None:
    result = runner.invoke(app, ["keys", "--json"])
    assert result.exit_code == 0
    payload = _json.loads(result.output)
    assert "mnemonic" in payload
    assert "ss58_address" in payload


def test_keys_json_error_path_is_valid_json() -> None:
    result = runner.invoke(app, ["keys", "//", "--json"])
    assert result.exit_code != 0
    payload = _json.loads(result.output)
    assert "error" in payload
    assert "groupdict" not in payload["error"]
