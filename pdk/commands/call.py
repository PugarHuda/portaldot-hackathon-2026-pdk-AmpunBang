"""`pdk call <pallet> <call> [args...]` — generic extrinsic composer.

Every other signing command hardcodes one pallet call. This one doesn't:
it looks up any pallet/call pair in the live runtime's metadata, validates
and coerces the CLI strings against that call's real argument types, and
submits through the same ``submit_call`` / ``receipt_succeeded`` path as
the rest of the toolkit. That inheritance is the point — it picks up the
Assets encoding fix and the event-decode fix rather than inventing a
second signing path that could get either wrong again.

Discovery is built in, because a generic composer is useless if you must
already know the signature to try it::

    pdk call <pallet>          list the pallet's calls and their arg types
    pdk call <pallet> <call>   show that call's expected arguments

Coercion covers a deliberately narrow slice of primitive shapes:
account-like (SS58 or ``//URI``), unsigned integers including
``Compact<...>`` wrapping, bool, and ``Bytes``/``Vec<u8>`` as 0x-hex.
Everything else — structs, enums, ``Option<T>``, tuples, ``Vec<T>`` of
non-bytes, signed integers — is a named, hard error. Never a silent
mis-encode: guessing at an encoding on a signing path is how you sign
something the user didn't ask for.
"""

from __future__ import annotations

import json as jsonlib
import re

import typer
from scalecodec import types
from rich.console import Console
from rich.markup import escape
from rich.table import Table
from substrateinterface import Keypair

from pdk.config import DEFAULT_NODE_URL
from pdk.core.chain import (
    POT_DECIMALS, connect, free_balance, normalise_account_uri, resolve_account, submit_call,
)
from pdk.core.decoder import decode_receipt
from pdk.core.events import receipt_succeeded

console = Console()

_COMPACT = re.compile(r"^Compact<(.+)>$")
# Account-like and byte-string types are matched by name, because what pdk
# has to do with them (SS58/`//URI` resolution, hex validation) doesn't
# follow from their SCALE shape — an AccountId is 32 bytes just like a hash.
_ACCOUNT_TYPES = re.compile(r"^(AccountId32|AccountId|MultiAddress|Address|LookupSource)$", re.IGNORECASE)
_BYTES_TYPES = re.compile(r"^(Bytes|Vec<u8>)$", re.IGNORECASE)
_INT_SCALE_TYPES = (types.U8, types.U16, types.U32, types.U64, types.U128, types.U256)


def unwrap_compact(raw_type: str) -> str:
    """Peel any number of ``Compact<...>`` layers down to the inner type."""
    current = raw_type.strip()
    while True:
        match = _COMPACT.match(current)
        if not match:
            return current
        current = match.group(1).strip()


def classify_type(runtime, raw_type: str) -> str:
    """Classify a metadata type string into a shape we know how to coerce.

    Numbers and bools are identified by asking the chain's own type
    registry what the name resolves to, rather than matching a hand-kept
    list of aliases. This runtime alone declares call arguments as
    `BalanceOf`, `BlockNumber`, `EraIndex`, `Perbill`, `Weight`,
    `AccountIndex`, `BountyIndex`, `RegistrarIndex` and more — all plain
    unsigned integers underneath. A name list would have to guess at each
    one and would silently rot as the runtime adds aliases; the registry
    already knows. Anything that doesn't resolve, or resolves to a
    composite (`Call`, `Vec<T>`, `Option<T>`, structs), stays
    'unsupported' and is refused loudly.
    """
    inner = unwrap_compact(raw_type)
    if _ACCOUNT_TYPES.match(inner):
        return "accountId"
    if _BYTES_TYPES.match(inner):
        return "bytes"
    try:
        resolved = runtime.create_scale_object(inner)
    except Exception:  # noqa: BLE001 — an unknown type name is simply unsupported
        return "unsupported"
    if isinstance(resolved, types.Bool):
        return "bool"
    if isinstance(resolved, _INT_SCALE_TYPES):
        return "integer"
    return "unsupported"


def coerce_arg(kind: str, raw: str, label: str):
    """Coerce one CLI string into what ``compose_call`` expects for ``kind``.

    Raises ``typer.BadParameter`` with the argument's name and declared
    type on bad input, rather than letting a malformed value reach SCALE
    encoding and fail opaquely — or encode something unintended.
    """
    text = raw.strip()
    if kind == "accountId":
        return resolve_account(text)
    if kind == "integer":
        if not text.isdigit():
            raise typer.BadParameter(f"{label}: expected a non-negative integer, got {raw!r}.")
        return int(text)
    if kind == "bool":
        if text.lower() not in ("true", "false"):
            raise typer.BadParameter(f'{label}: expected "true" or "false", got {raw!r}.')
        return text.lower() == "true"
    if kind == "bytes":
        if not re.fullmatch(r"0x[0-9a-fA-F]*", text):
            raise typer.BadParameter(f"{label}: expected 0x-prefixed hex, got {raw!r}.")
        return text
    raise typer.BadParameter(f"{label}: unsupported argument type — pdk call can't encode this yet.")


def _find(names, wanted: str) -> str | None:
    """Case-insensitive name match, mirroring how `pallets`/`storage` resolve."""
    target = wanted.lower()
    return next((n for n in names if n.lower() == target), None)


def _pallet(substrate, name: str):
    return next((p for p in substrate.metadata.pallets if str(p.name) == name), None)


def _call_args(substrate, pallet: str, call: str) -> list[tuple[str, str]]:
    """(name, declared type) for one call, straight off runtime metadata.

    Read from `substrate.metadata`, NOT `get_metadata_call_function`: the
    two disagree. The latter returns the runtime's raw Rust type strings
    (`<T::Lookup as StaticLookup>::Source`, `Compact<T::Balance>`), which
    resolve against nothing; `metadata.pallets` gives the registry-facing
    names (`LookupSource`, `Compact<Balance>`) that classification and
    encoding both need.
    """
    entry = _pallet(substrate, pallet)
    found = next((c for c in (entry.calls or []) if str(c.name) == call), None) if entry else None
    return [(str(a.name), str(a.type)) for a in (getattr(found, "args", None) or [])]


def run(
    pallet: str = typer.Argument(..., help="Pallet name, e.g. Balances."),
    call: str = typer.Argument(None, help="Call name. Omit to list the pallet's calls."),
    args: list[str] = typer.Argument(None, help="Call arguments, in metadata order."),
    sender: str = typer.Option("//Alice", "--from", help="Signing account URI."),
    node: str = typer.Option(DEFAULT_NODE_URL, "--node", help="Portaldot node WS endpoint."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the composed call and its fee, submit nothing."),
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Compose, sign, and submit any pallet call the runtime exposes."""
    try:
        substrate = connect(node)
        substrate.init_runtime()
    except Exception as exc:  # noqa: BLE001
        _die(json_out, f"Cannot reach a Portaldot node at {node}", str(exc),
             "Start a node with pdk up (run the node in WSL on Windows; pdk itself runs natively).")

    pallet_names = [str(p.name) for p in substrate.metadata.pallets]
    resolved_pallet = _find(pallet_names, pallet)
    if resolved_pallet is None:
        _die(json_out, f'Pallet "{pallet}" not found — run pdk pallets to list them.')

    call_names = [str(c.name) for c in (_pallet(substrate, resolved_pallet).calls or [])]

    # Discovery: no call named — list what this pallet offers.
    if not call:
        _render_calls(substrate, resolved_pallet, call_names, json_out)
        return

    resolved_call = _find(call_names, call)
    if resolved_call is None:
        _die(json_out, f'Call "{call}" not found on pallet "{resolved_pallet}" — '
                       f"run pdk call {resolved_pallet} to list its calls.")

    signature = _call_args(substrate, resolved_pallet, resolved_call)
    supplied = list(args or [])

    # Discovery: call named but no args given, and it needs some — show the
    # signature instead of failing on an arg-count error the user can't yet read.
    if not supplied and signature:
        _render_signature(substrate.runtime_config, resolved_pallet, resolved_call, signature, json_out)
        return

    if len(supplied) != len(signature):
        detail = ", ".join(f"{n}: {t}" for n, t in signature) or "no arguments"
        _die(json_out, f"{resolved_pallet}.{resolved_call} expects {len(signature)} argument(s) "
                       f"({detail}), got {len(supplied)}.")

    params = {
        name: coerce_arg(classify_type(substrate.runtime_config, declared), value, f"{name} ({declared})")
        for (name, declared), value in zip(signature, supplied)
    }

    keypair = Keypair.create_from_uri(normalise_account_uri(sender))
    if dry_run:
        _dry_run(substrate, keypair, resolved_pallet, resolved_call, params, json_out)
        return

    try:
        receipt = submit_call(substrate, keypair, resolved_pallet, resolved_call, params)
    except Exception as exc:  # noqa: BLE001
        _die(json_out, f"{resolved_pallet}.{resolved_call} failed: {exc}")

    tx = str(receipt.extrinsic_hash)
    if receipt_succeeded(substrate, receipt):
        if json_out:
            typer.echo(jsonlib.dumps({"success": True, "pallet": resolved_pallet, "call": resolved_call,
                                      "tx": tx, "block": receipt.block_hash}))
        else:
            console.print(f"[green]✓ {escape(resolved_pallet)}.{escape(resolved_call)}[/green]")
            console.print(f"[dim]tx: {tx}[/dim]")
        return

    decoded = decode_receipt(receipt, substrate)
    name = decoded.name if decoded else "unknown"
    if json_out:
        typer.echo(jsonlib.dumps({"success": False, "pallet": resolved_pallet, "call": resolved_call,
                                  "tx": tx, "error": name}))
    else:
        console.print(f"[red]✗ {escape(resolved_pallet)}.{escape(resolved_call)} failed: {escape(name)}[/red]")
        console.print(f"[dim]Diagnose it: pdk debug {tx}[/dim]")
    raise typer.Exit(code=1)


def _dry_run(substrate, keypair, pallet: str, call: str, params: dict, json_out: bool) -> None:
    """Fee-payability preview only. pdk cannot predict arbitrary pallet
    dispatch logic, so this deliberately claims nothing about whether the
    call itself would succeed — only whether the signer can pay for it."""
    try:
        composed = substrate.compose_call(call_module=pallet, call_function=call, call_params=params)
        fee = substrate.get_payment_info(call=composed, keypair=keypair)["partialFee"] / 10**POT_DECIMALS
        balance = free_balance(substrate, keypair.ss58_address)
    except Exception as exc:  # noqa: BLE001
        _die(json_out, f"Could not estimate {pallet}.{call}: {exc}")

    payable = balance >= fee
    if json_out:
        typer.echo(jsonlib.dumps({"dryRun": True, "pallet": pallet, "call": call,
                                  "args": {k: str(v) for k, v in params.items()},
                                  "fee": fee, "senderBalance": balance, "feasible": payable}))
    else:
        console.print(f"[bold]pdk call {escape(pallet)} {escape(call)} --dry-run[/bold]  [dim](not submitted)[/dim]")
        for key, value in params.items():
            console.print(f"  {key:<20} {escape(str(value))}")
        console.print(f"  {'Estimated fee':<20} {fee:.6f} POT")
        console.print(f"  {'Sender balance':<20} {balance:,.4f} POT")
        console.print(f"  {'Prediction':<20} " + ("[green]fee payable[/green]" if payable
                                                  else "[red]would FAIL — cannot cover the fee[/red]"))
        console.print("[dim](fee-payability only — pdk can't predict arbitrary pallet dispatch logic)[/dim]")
    if not payable:
        raise typer.Exit(code=1)


def _render_calls(substrate, pallet: str, call_names: list[str], json_out: bool) -> None:
    rows = [(name, _call_args(substrate, pallet, name)) for name in sorted(call_names)]
    if json_out:
        typer.echo(jsonlib.dumps({"pallet": pallet, "calls": [
            {"name": name, "args": [{"name": n, "type": t} for n, t in sig]} for name, sig in rows
        ]}))
        return
    table = Table(title=f"{pallet} — {len(rows)} calls")
    table.add_column("call", style="green")
    table.add_column("arguments")
    for name, sig in rows:
        table.add_row(escape(name), escape(", ".join(f"{n}: {t}" for n, t in sig)))
    console.print(table)
    console.print(f"[dim]Run one: pdk call {pallet} <call> <args...>[/dim]")


def _render_signature(runtime, pallet: str, call: str, signature: list[tuple[str, str]], json_out: bool) -> None:
    if json_out:
        typer.echo(jsonlib.dumps({"pallet": pallet, "call": call,
                                  "args": [{"name": n, "type": t, "kind": classify_type(runtime, t)} for n, t in signature]}))
        return
    table = Table(title=f"{pallet}.{call}")
    table.add_column("argument", style="cyan")
    table.add_column("type")
    table.add_column("accepts")
    accepts = {
        "accountId": "//URI or SS58 address",
        "integer": "non-negative integer",
        "bool": "true / false",
        "bytes": "0x-prefixed hex",
        "unsupported": "[red]unsupported by pdk call[/red]",
    }
    for name, declared in signature:
        table.add_row(escape(name), escape(declared), accepts[classify_type(runtime, declared)])
    console.print(table)


def _die(json_out: bool, message: str, detail: str = "", hint: str = "") -> None:
    """Emit an error and exit 1 — as JSON under --json so every exit path
    stays parseable, as Rich text otherwise. Always raises."""
    if json_out:
        payload = {"error": message}
        if detail:
            payload["detail"] = detail
        typer.echo(jsonlib.dumps(payload))
    else:
        console.print(f"[red]{escape(message)}[/red]")
        if detail:
            console.print(f"[dim]{escape(detail)}[/dim]")
        if hint:
            console.print(hint)
    raise typer.Exit(code=1)
