"""`pdk seed` — populate a local dev node with funded accounts from a YAML file.

Reads a YAML fixtures file (a bundled example by default) and submits the real
extrinsics to fund accounts with POT, so you start testing from realistic
multi-account state instead of just Alice.
"""

from __future__ import annotations

from pathlib import Path

import typer
import yaml
from rich.console import Console
from substrateinterface import Keypair

from pdk.config import DEFAULT_NODE_URL
from pdk.core.chain import connect, pot_to_plancks, submit_call
from pdk.core.events import receipt_succeeded

console = Console()
_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "seed.example.yaml"


def run(
    file: Path = typer.Option(None, "--file", help="YAML fixtures file (default: bundled example)."),
    node: str = typer.Option(DEFAULT_NODE_URL, "--node", help="Portaldot node WS endpoint."),
) -> None:
    """Apply fixtures to a local dev node so you start from realistic state, not zero."""
    path = Path(file) if file else _DEFAULT
    try:
        fixtures = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("fixtures", [])
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Cannot read fixtures from {path}: {exc}[/red]")
        raise typer.Exit(code=1)

    try:
        substrate = connect(node)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Cannot reach a Portaldot node at {node}[/red]")
        console.print(f"[dim]{exc}[/dim]")
        console.print("Start a node with [bold]pdk up[/bold] (run the node in WSL on Windows; pdk itself runs natively).")
        raise typer.Exit(code=1)

    alice = Keypair.create_from_uri("//Alice")
    console.print(f"[bold]Seeding from {path.name} — {len(fixtures)} fixtures[/bold]")
    applied = 0
    for fx in fixtures:
        kind = fx.get("type")
        if kind != "fund":
            console.print(f"  [yellow]• skipped unsupported fixture type: {kind}[/yellow]")
            continue
        try:
            dest = Keypair.create_from_uri(fx["to"]).ss58_address
            receipt = submit_call(
                substrate, alice, "Balances", "transfer",
                {"dest": dest, "value": pot_to_plancks(fx["pot"])},
            )
            succeeded = receipt_succeeded(substrate, receipt)
            mark = "[green]✓[/green]" if succeeded else "[red]✗[/red]"
            console.print(f"  {mark} funded {fx['to']} with {fx['pot']:,} POT")
            applied += 1 if succeeded else 0
        except Exception as exc:  # noqa: BLE001
            console.print(f"  [red]✗ fund {fx.get('to')} failed: {str(exc)[:90]}[/red]")
    console.print(f"[green]seed complete[/green] — {applied}/{len(fixtures)} accounts funded.")
