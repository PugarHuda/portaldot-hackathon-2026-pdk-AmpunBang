"""pdk — Portaldot Dev Kit CLI entry point.

Registers the toolkit's commands and wires the `--version` flag. Each command's
logic lives in `pdk/commands/<name>.py` (a thin `run()`), with chain work in
`pdk/core/`. The hero command is `pdk debug` (FailLens), which decodes a failed
transaction into a clear, actionable diagnosis.
"""

import sys

# Rich prints ✗, box-drawing, and em-dashes. On Windows a non-UTF-8 console — or
# any redirected pipe — defaults to cp1252, and Rich then crashes with
# UnicodeEncodeError. Force UTF-8 before any Rich Console is constructed (the
# command imports below each create one at import time).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # e.g. test runners that wrap stdout
        pass

import typer  # noqa: E402 — must follow the stdout reconfigure above

from pdk import __version__  # noqa: E402
from pdk.commands import (  # noqa: E402
    accounts, ai_setup, assets, call, debug, doctor, explain, fund, kb, keys, pallets, report, seed, send, simulate, storage, up, watch,
)

app = typer.Typer(
    name="pdk",
    help="Portaldot Dev Kit — a developer toolkit for the Portaldot blockchain.",
    no_args_is_help=True,
    add_completion=False,
)

app.command("up", help="Start a local Portaldot node and verify it with a transaction.")(up.run)
app.command("accounts", help="Show pre-funded dev accounts and their POT balances.")(accounts.run)
app.command("debug", help="Decode a failed transaction into a human-readable diagnosis.")(debug.run)
app.command("explain", help="Explain an error by name, or decode a raw code (--module/--error).")(explain.run)
app.command("doctor", help="Check node version and environment health.")(doctor.run)
app.command("simulate", help="Preview a transfer's fee and feasibility, without sending.")(simulate.run)
app.command("seed", help="Fund dev accounts on a local node from YAML fixtures.")(seed.run)
app.command("pallets", help="Discover the runtime's pallets, calls, and errors.")(pallets.run)
app.command("send", help="Send POT from a dev account — a real on-chain transfer.")(send.run)
app.command("fund", help="Top up an account with POT from //Alice (answers 'how do I get POT?').")(fund.run)
app.command("storage", help="Read any value from the chain's storage.")(storage.run)
app.command("watch", help="Stream all chain events live (optionally filtered by pallet).")(watch.run)
app.command("report", help="Scan recent blocks and summarise decoded failures by type.")(report.run)
app.command("keys", help="Generate or inspect a keypair (SS58 format 42).")(keys.run)
app.command("ai-setup", help="Set up (or verify) the optional AI diagnosis layer.")(ai_setup.run)
app.command("kb", help="Knowledge-base introspection — coverage, missing entries, or full list.")(kb.run)
app.add_typer(assets.app, name="assets", help="Create, mint, and transfer custom assets.")
app.command("call", help="Compose, sign, and submit any pallet call the runtime exposes.")(call.run)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pdk {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the pdk version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Portaldot Dev Kit — developer toolkit for the Portaldot blockchain."""


def main() -> None:
    """Console-script entry point."""
    from pdk.core.knowledge import KbPathError

    try:
        app()
    except KbPathError as exc:
        # A typo'd PDK_KB_PATH / PDK_INDEX_PATH is user error, not a pdk
        # bug — show the one-line message, not a Rich traceback.
        import sys

        from rich.console import Console

        Console(stderr=True).print(f"[red]{exc}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
