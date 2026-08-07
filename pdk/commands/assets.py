"""`pdk assets` — create, mint, and transfer custom assets.

Three lifecycle operations, the minimum to create an asset, fund it, and
move it: ``create``, ``mint``, ``transfer``. Mirrors ``pdk-ts assets``
argument-for-argument, closing the last command-surface gap between the
two CLIs.

Signing these on Portaldot needed two separate fixes, both of which live
in ``pdk/core`` rather than here:

* ``chain._fix_assets_balance_width`` — ``Assets.create``'s ``min_balance``
  is declared ``T::Balance`` in V13 metadata, which substrate-interface
  resolves as u128 while pallet-assets uses u64. The extra 8 bytes get
  signed but not verified, so the node rejects the extrinsic with
  "bad signature" before dispatch.
* ``events.receipt_succeeded`` — the same ambiguity on the event side
  makes ``receipt.is_success`` raise for ``mint``/``transfer``, because a
  block's events decode as one vec and an over-wide read desynchronises
  the rest of it.

So this module submits through ``submit_call`` and confirms through
``receipt_succeeded``, and inherits both. Success is confirmed only by a
positive ``System.ExtrinsicSuccess`` for this extrinsic — never by the
absence of an error.
"""

from __future__ import annotations

import json as jsonlib

import typer
from rich.console import Console
from rich.markup import escape
from substrateinterface import Keypair

from pdk.config import DEFAULT_NODE_URL
from pdk.core.chain import connect, normalise_account_uri, resolve_account, submit_call
from pdk.core.decoder import decode_receipt
from pdk.core.events import receipt_succeeded

console = Console()

app = typer.Typer(
    name="assets",
    help="Create, mint, and transfer custom assets (Assets pallet).",
    no_args_is_help=True,
    add_completion=False,
)

_NODE = typer.Option(DEFAULT_NODE_URL, "--node", help="Portaldot node WS endpoint.")
_FROM = typer.Option("//Alice", "--from", help="Signing account URI.")
_JSON = typer.Option(False, "--json", help="Emit machine-readable JSON.")


def _parse_amount(raw: str, label: str) -> int:
    """Whole non-negative integer only.

    Assets pallet units have no decimals convention like POT, so there is
    nothing to scale. int() alone would accept "0x10" (→16) and a bare
    "-1", either of which silently encodes something other than what was
    typed — refuse instead.
    """
    text = str(raw).strip()
    if not text.isdigit():
        raise typer.BadParameter(f"{label} must be a non-negative whole number, got {raw!r}.")
    return int(text)


def _connect(node: str, json_out: bool):
    try:
        return connect(node)
    except Exception as exc:  # noqa: BLE001
        if json_out:
            typer.echo(jsonlib.dumps({"error": f"Cannot reach a Portaldot node at {node}", "detail": str(exc)}))
        else:
            console.print(f"[red]Cannot reach a Portaldot node at {node}[/red]")
            console.print(f"[dim]{exc}[/dim]")
            console.print("Start a node with [bold]pdk up[/bold] (run the node in WSL on Windows; pdk itself runs natively).")
        raise typer.Exit(code=1)


def _submit(substrate, sender: str, call: str, params: dict, action: str,
            extra: dict, json_out: bool) -> None:
    """Sign, submit, confirm, and report one Assets call."""
    keypair = Keypair.create_from_uri(normalise_account_uri(sender))
    try:
        receipt = submit_call(substrate, keypair, "Assets", call, params)
    except Exception as exc:  # noqa: BLE001
        if json_out:
            typer.echo(jsonlib.dumps({"success": False, "error": str(exc), **extra}))
        else:
            console.print(f"[red]✗ assets {call} failed: {escape(str(exc))}[/red]")
        raise typer.Exit(code=1)

    tx = str(receipt.extrinsic_hash)
    if receipt_succeeded(substrate, receipt):
        if json_out:
            typer.echo(jsonlib.dumps({"success": True, "tx": tx, "block": receipt.block_hash, **extra}))
        else:
            console.print(f"[green]✓ {action}[/green]")
            console.print(f"[dim]tx: {tx}[/dim]")
        return

    decoded = decode_receipt(receipt, substrate)
    name = decoded.name if decoded else "unknown"
    if json_out:
        typer.echo(jsonlib.dumps({"success": False, "tx": tx, "error": name, **extra}))
    else:
        console.print(f"[red]✗ assets {call} failed: {escape(name)}[/red]")
        console.print(f"[dim]Diagnose it: pdk debug {tx}[/dim]")
    raise typer.Exit(code=1)


@app.command("create")
def create(
    asset_id: str = typer.Argument(..., help="Numeric id for the new asset."),
    min_balance: str = typer.Option("1", "--min-balance", help="Smallest holdable amount; accounts below it are dusted."),
    admin: str = typer.Option(None, "--admin", help="Admin account (//URI or SS58). Defaults to the signer."),
    sender: str = _FROM,
    node: str = _NODE,
    json_out: bool = _JSON,
) -> None:
    """Create a new asset, owned and administered by --admin (default: the signer)."""
    ident = _parse_amount(asset_id, "asset id")
    minimum = _parse_amount(min_balance, "--min-balance")
    substrate = _connect(node, json_out)
    admin_address = resolve_account(admin) if admin else Keypair.create_from_uri(normalise_account_uri(sender)).ss58_address
    _submit(
        substrate, sender, "create",
        {"id": ident, "admin": admin_address, "min_balance": minimum},
        f"created asset #{ident}", {"id": ident, "admin": admin_address}, json_out,
    )


@app.command("mint")
def mint(
    asset_id: str = typer.Argument(..., help="Asset id to mint."),
    to: str = typer.Argument(..., help="Beneficiary (//URI or SS58)."),
    amount: str = typer.Option(..., "--amount", help="How much to mint."),
    sender: str = _FROM,
    node: str = _NODE,
    json_out: bool = _JSON,
) -> None:
    """Mint new units of an asset to an account. Only the asset's issuer may do this."""
    ident = _parse_amount(asset_id, "asset id")
    units = _parse_amount(amount, "--amount")
    substrate = _connect(node, json_out)
    dest = resolve_account(to)
    _submit(
        substrate, sender, "mint",
        {"id": ident, "beneficiary": dest, "amount": units},
        f"minted {units:,} of asset #{ident} to {to}",
        {"id": ident, "to": dest, "amount": units}, json_out,
    )


@app.command("transfer")
def transfer(
    asset_id: str = typer.Argument(..., help="Asset id to transfer."),
    to: str = typer.Argument(..., help="Recipient (//URI or SS58)."),
    amount: str = typer.Option(..., "--amount", help="How much to transfer."),
    sender: str = _FROM,
    node: str = _NODE,
    json_out: bool = _JSON,
) -> None:
    """Transfer units of an asset from the signer to another account."""
    ident = _parse_amount(asset_id, "asset id")
    units = _parse_amount(amount, "--amount")
    substrate = _connect(node, json_out)
    dest = resolve_account(to)
    _submit(
        substrate, sender, "transfer",
        {"id": ident, "target": dest, "amount": units},
        f"transferred {units:,} of asset #{ident} to {to}",
        {"id": ident, "to": dest, "amount": units}, json_out,
    )
