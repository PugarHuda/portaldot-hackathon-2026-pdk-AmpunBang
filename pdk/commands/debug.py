"""`pdk debug` — FailLens: turn a cryptic failed transaction into a clear diagnosis."""

from __future__ import annotations

import json as jsonlib
import time

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel

from pdk.config import DEFAULT_NODE_URL
from pdk.core.chain import connect, submit_valid_demo_transfer, trigger_demo_failure
from pdk.core.decoder import (
    DecodedError,
    decode_receipt,
    failed_receipts_in_block,
    find_receipt,
    strip_control_chars,
)
from pdk.core.events import receipt_succeeded
from pdk.core.knowledge import FixSuggestion, load_knowledge, lookup_fix

console = Console()


def run(
    tx_hash: str = typer.Argument(None, help="Hash of the failed transaction to diagnose."),
    node: str = typer.Option(DEFAULT_NODE_URL, "--node", help="Portaldot node WS endpoint."),
    demo: bool = typer.Option(False, "--demo", help="Trigger a failing transaction, then diagnose it."),
    watch: bool = typer.Option(False, "--watch", help="Live mode: decode every failed transaction as it lands."),
    json_out: bool = typer.Option(False, "--json", help="Emit the diagnosis as JSON (for scripts/CI)."),
    exit_code: bool = typer.Option(False, "--exit-code", help="Exit non-zero (2) when a failure is decoded — for CI pipeline gating."),
    fix: bool = typer.Option(False, "--fix", help="After diagnosing, apply a remediation (with --demo) or suggest one."),
    ai: bool = typer.Option(False, "--ai", help="Force the AI diagnosis even if key auto-detection fails (mostly: print the 'set PDK_AI_KEY' hint when missing)."),
    no_ai: bool = typer.Option(False, "--no-ai", help="Skip the AI diagnosis even if PDK_AI_KEY is set."),
) -> None:
    """Diagnose a failed Portaldot transaction.

    Three modes: a single tx hash, `--demo` (submits its own failing tx, paying
    POT gas), or `--watch` (a live monitor that decodes failures as they happen).

    With `--json --exit-code`, pdk becomes a CI citizen: pipe a tx hash in, gate
    the build on the result.
    """
    if not (demo or watch) and not tx_hash:
        raise _fail(json_out, "Provide a transaction hash, or use --demo / --watch.")

    try:
        substrate = connect(node)
    except Exception as exc:  # noqa: BLE001 — surface any connection failure plainly
        raise _fail(
            json_out,
            f"Cannot reach a Portaldot node at {node}",
            detail=str(exc),
            hint="Start a node with pdk up (run the node in WSL on Windows; pdk itself runs natively).",
        )

    if watch:
        _watch(substrate, json_out)
        return

    if demo:
        receipt = trigger_demo_failure(substrate)
        tx_hash = receipt.extrinsic_hash
        if not json_out:
            console.print(f"[dim]demo: submitted failing tx {tx_hash}[/dim]")
    else:
        receipt = find_receipt(substrate, tx_hash)
        if receipt is None:
            raise _fail(
                json_out,
                f"No transaction {tx_hash} found in recent blocks.",
                detail="FailLens scans only recent blocks — an older tx may be out of range.",
                tx=str(tx_hash),
                severity="yellow",
            )

    decoded = decode_receipt(receipt, substrate)
    if decoded is None:
        if json_out:
            typer.echo(jsonlib.dumps({"tx": str(tx_hash), "success": True}))
        else:
            console.print("[green]That transaction succeeded — nothing to debug.[/green]")
        return

    suggestion = lookup_fix(decoded, load_knowledge())
    _emit(str(tx_hash), decoded, suggestion, json_out)
    if _should_run_ai(ai, no_ai, json_out):
        _ai_section(_resolve_pallet(decoded, suggestion), decoded.name, decoded.docs,
                    explicit=ai)
    if fix:
        _remediate(substrate, demo, decoded, json_out)
    if exit_code:
        # A failure was decoded — signal it so CI pipelines can gate on the result.
        raise typer.Exit(code=2)


def _fail(json_out: bool, message: str, *, detail: str = "", hint: str = "",
          tx: str | None = None, severity: str = "red") -> "typer.Exit":
    """Emit an error and exit 1 — as a JSON object under --json, as Rich text
    otherwise. Keeps `pdk debug --json` a real CI citizen: EVERY exit path
    yields parseable JSON, so a consumer can `jq .error` without hitting
    human-readable text on the not-found / bad-input / unreachable branches.
    Raises typer.Exit; the return annotation is only to satisfy callers that
    write `raise _fail(...)` for clarity (it always raises)."""
    if json_out:
        payload: dict = {"error": message}
        if detail:
            payload["detail"] = detail
        if tx is not None:
            payload["tx"] = tx
        typer.echo(jsonlib.dumps(payload))
    else:
        console.print(f"[{severity}]{message}[/{severity}]")
        if detail:
            console.print(f"[dim]{detail}[/dim]")
        if hint:
            console.print(hint)
    raise typer.Exit(code=1)


def _should_run_ai(ai_flag: bool, no_ai_flag: bool, json_out: bool) -> bool:
    """AI auto-runs whenever a key is set. `--no-ai` is the off-switch;
    `--ai` is still accepted as an explicit opt-in (which surfaces the setup
    hint when no key is configured). JSON output never includes the AI panel."""
    if json_out or no_ai_flag:
        return False
    if ai_flag:
        return True
    from pdk.core.ai import ai_available
    return ai_available()


def _ai_section(pallet: str, name: str, docs: str, *, explicit: bool = False) -> bool:
    """Print an AI-suggested diagnosis (clearly labelled unverified). Never raises;
    returns False on missing key / failed call. ``explicit`` means the user passed
    --ai so the missing-key hint is shown; otherwise we stay silent (auto-mode)."""
    from pdk.core.ai import ai_available, ai_diagnose

    if not ai_available():
        if explicit:
            console.print("[dim]--ai needs PDK_AI_KEY (e.g. a free OpenRouter key) to enable AI diagnosis.[/dim]")
        return False
    console.print("[dim]asking AI (grounded in chain metadata) …[/dim]")
    result = ai_diagnose(pallet, name, docs)
    if not result:
        console.print("[yellow]AI diagnosis unavailable right now.[/yellow]")
        return False
    # `result` is LLM output generated FROM `docs` (chain-sourced free
    # text, no syntax constraint) — a prompt-injected or simply
    # context-echoing model could reproduce embedded markup/escape
    # sequences verbatim in its own response. Same treatment as every
    # other render site this sweep covered.
    console.print(Panel(escape(strip_control_chars(result)), title="AI-suggested — UNVERIFIED (not a curated KB entry)",
                        border_style="yellow"))
    return True


def _remediate(substrate, demo: bool, decoded: DecodedError, json_out: bool) -> None:
    """`--fix`: for the demo, submit the corrected transaction and show it succeed;
    otherwise print a concrete, runnable remediation for the decoded error."""
    if json_out:
        return
    console.print()
    if demo:
        console.print("[bold]Applying fix[/bold] — the demo transfer exceeded the balance; "
                      "retrying with a valid amount …")
        try:
            receipt = submit_valid_demo_transfer(substrate)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Fix attempt failed: {str(exc)[:90]}[/red]")
            return
        if receipt_succeeded(substrate, receipt):
            console.print(f"[green]✓ Fixed[/green] — the corrected transfer succeeded. "
                          f"tx: {receipt.extrinsic_hash}")
        else:
            console.print("[yellow]The corrected transfer still failed — run pdk debug on its hash.[/yellow]")
        return
    # Real tx: suggest, don't auto-execute (we can't know the user's intent).
    if decoded.name == "InsufficientBalance":
        console.print("[bold]Suggested fix[/bold] — lower the amount, or fund the sender:")
        console.print("  [dim]pdk send <dest> --amount <smaller>[/dim]   ·   fund: "
                      "[dim]pdk send //Alice --amount <n>[/dim]")
    else:
        console.print(f"[dim]No automated remediation for {decoded.name} — follow the fix steps above.[/dim]")


def _watch(substrate, json_out: bool) -> None:
    """Poll for new blocks and diagnose every failed extrinsic as it appears."""
    kb = load_knowledge()
    last = substrate.get_block_number(substrate.get_chain_head())
    if not json_out:
        console.print(f"[dim]FailLens watching from block #{last} — Ctrl+C to stop.[/dim]")
    try:
        while True:
            head_num = substrate.get_block_number(substrate.get_chain_head())
            for number in range(last + 1, head_num + 1):
                block_hash = substrate.get_block_hash(number)
                for receipt in failed_receipts_in_block(substrate, block_hash):
                    decoded = decode_receipt(receipt, substrate)
                    if decoded is None:
                        continue
                    fix = lookup_fix(decoded, kb)
                    _emit(str(receipt.extrinsic_hash), decoded, fix, json_out)
            last = head_num
            time.sleep(2)
    except KeyboardInterrupt:
        if not json_out:
            console.print("\n[dim]stopped.[/dim]")


def _resolve_pallet(decoded: DecodedError, fix: FixSuggestion) -> str:
    """Recover the real pallet name.

    error_message reports a generic "Module" type for pallet errors, so prefer
    the pallet from the matched knowledge-base key when one is available.
    """
    return fix.matched_key.split(".")[0].title() if fix.matched_key else decoded.pallet


def _emit(tx_hash: str, decoded: DecodedError, fix: FixSuggestion, json_out: bool) -> None:
    """Render the diagnosis as a Rich panel, or as one JSON line when --json."""
    if json_out:
        typer.echo(
            jsonlib.dumps(
                {
                    "tx": tx_hash,
                    "pallet": _resolve_pallet(decoded, fix),
                    "error": decoded.name,
                    "known": fix.known,
                    "summary": fix.summary,
                    "fix": fix.steps,
                }
            )
        )
        return
    _render(tx_hash, decoded, fix)


def _render(tx_hash: str, decoded: DecodedError, fix: FixSuggestion) -> None:
    """Print the diagnosis: error -> explanation -> fix steps."""
    called = f"  [dim]· {escape(decoded.extrinsic_call)}[/dim]" if decoded.extrinsic_call else ""
    confidence = "" if fix.known else "  [yellow](no curated entry — metadata fallback)[/yellow]"
    pallet = _resolve_pallet(decoded, fix)
    error_label = (
        f"{pallet}.{decoded.name}"
        if pallet and pallet not in ("Module", "Unknown")
        else decoded.name
    )

    # `fix.summary` can be the raw runtime doc comment (knowledge.py's
    # tier-3 metadata fallback, which fires for any error outside the
    # curated KB). Doc comments are free-form text with no syntax
    # restriction — a malicious/compromised chain could embed Rich
    # markup (including a real clickable `[link=...]`) that would
    # otherwise render inside pdk's own trusted-looking Panel. escape()
    # neutralizes untrusted chain text while leaving pdk's own styling
    # tags (written directly in this f-string) intact.
    body = (
        f"[bold red]✗ {escape(error_label)}[/bold red]{called}\n\n"
        f"[bold]What happened[/bold]{confidence}\n{escape(fix.summary)}\n\n"
        f"[bold]How to fix[/bold]\n"
        + "\n".join(f"  {i}. {escape(step)}" for i, step in enumerate(fix.steps, 1))
    )
    console.print(
        Panel(
            body,
            title=f"FailLens — {tx_hash[:18]}…",
            border_style="red" if fix.known else "yellow",
        )
    )
