"""`pdk send` — submit a real POT transfer from a dev account (pays POT as gas)."""

from __future__ import annotations

import typer
from rich.console import Console
from substrateinterface import Keypair

from pdk.config import DEFAULT_NODE_URL
from pdk.core.chain import POT_DECIMALS, connect, free_balance, normalise_account_uri, pot_to_plancks, submit_call
from pdk.core.decoder import decode_receipt
from pdk.core.events import receipt_succeeded
from pdk.commands.simulate import predict_outcome

console = Console()


def run(
    to: str = typer.Argument(..., help="Recipient: a //URI (//Bob) or an SS58 address."),
    amount: float = typer.Option(..., "--amount", help="POT to send."),
    sender: str = typer.Option("//Alice", "--from", help="Sender dev account URI."),
    node: str = typer.Option(DEFAULT_NODE_URL, "--node", help="Portaldot node WS endpoint."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the fee + feasibility for this exact transfer, submit nothing."),
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON (dry-run only)."),
) -> None:
    """Send POT from a dev account — a real on-chain transaction, POT paid as gas."""
    if amount <= 0:
        console.print("[red]Amount must be positive.[/red]")
        raise typer.Exit(code=1)
    try:
        substrate = connect(node)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Cannot reach a Portaldot node at {node}[/red]")
        console.print(f"[dim]{exc}[/dim]")
        console.print("Start a node with [bold]pdk up[/bold] (run the node in WSL on Windows; pdk itself runs natively).")
        raise typer.Exit(code=1)

    keypair = Keypair.create_from_uri(normalise_account_uri(sender))
    # Normalise the recipient too: a git-bash-mangled `//Bob` → `/Bob`
    # would otherwise derive a DIFFERENT address and send real POT to
    # the wrong account with no warning.
    to_norm = normalise_account_uri(to)
    dest = Keypair.create_from_uri(to_norm).ss58_address if (to_norm.startswith("//") or "/" in to_norm) else to_norm

    if dry_run:
        _dry_run(substrate, keypair, dest, sender, to, amount, json_out)
        return

    try:
        receipt = submit_call(substrate, keypair, "Balances", "transfer",
                              {"dest": dest, "value": pot_to_plancks(amount)})
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Send failed: {exc}[/red]")
        raise typer.Exit(code=1)

    if receipt_succeeded(substrate, receipt):
        console.print(f"[green]✓ sent {amount:,} POT[/green]  {sender} → {to}")
        console.print(f"[dim]tx: {receipt.extrinsic_hash}[/dim]")
    else:
        decoded = decode_receipt(receipt, substrate)
        console.print(f"[red]✗ transfer failed: {decoded.name if decoded else 'unknown'}[/red]")
        console.print(f"[dim]Diagnose it: pdk debug {receipt.extrinsic_hash}[/dim]")
        raise typer.Exit(code=1)


def _dry_run(substrate, keypair, dest: str, sender_label: str, to_label: str,
             amount: float, json_out: bool) -> None:
    """Preview the fee + feasibility for THIS exact sender/recipient/amount,
    reusing simulate's predict_outcome — nothing is submitted."""
    import json as jsonlib

    try:
        call = substrate.compose_call(
            call_module="Balances", call_function="transfer_keep_alive",
            call_params={"dest": dest, "value": pot_to_plancks(amount)},
        )
        info = substrate.get_payment_info(call=call, keypair=keypair)
        fee = info["partialFee"] / 10**POT_DECIMALS
        balance = free_balance(substrate, keypair.ss58_address)
        ed_raw = substrate.get_constant("Balances", "ExistentialDeposit")
        existential_deposit = int(ed_raw.value) / 10**POT_DECIMALS if ed_raw is not None else 0.0
    except Exception as exc:  # noqa: BLE001
        msg = f"Could not estimate the transfer: {exc}"
        if json_out:
            console.print(jsonlib.dumps({"error": msg}))
        else:
            console.print(f"[red]{msg}[/red]")
        raise typer.Exit(code=1)

    feasible, likely_error = predict_outcome(amount, fee, balance, existential_deposit)

    if json_out:
        console.print(jsonlib.dumps({
            "dryRun": True,
            "from": sender_label,
            "to": to_label,
            "amount": amount,
            "fee": fee,
            "senderBalance": balance,
            "existentialDeposit": existential_deposit,
            "feasible": feasible,
            "likelyError": likely_error,
        }))
    else:
        console.print(f"[bold]pdk send --dry-run[/bold]  {sender_label} → {to_label}  [dim](not submitted)[/dim]")
        console.print(f"  Amount               {amount:,.4f} POT")
        console.print(f"  Estimated fee        {fee:.6f} POT")
        console.print(f"  Sender balance       {balance:,.4f} POT")
        console.print(f"  Existential deposit  {existential_deposit:.6f} POT")
        if feasible:
            console.print("  Prediction           [green]likely SUCCEED[/green]")
        else:
            console.print(f"  Prediction           [red]would FAIL — {likely_error}[/red]")
    if not feasible:
        raise typer.Exit(code=1)
