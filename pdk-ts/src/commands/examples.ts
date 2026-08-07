/**
 * `pdk-ts examples` — print a curated list of example invocations
 * grouped by task. Complements `--help` for discovery.
 */

import pc from 'picocolors';

interface Group {
  title: string;
  items: Array<{cmd: string; note: string}>;
}

const GROUPS: Group[] = [
  {
    title: 'Health / setup',
    items: [
      {cmd: 'pdk-ts doctor --node ws://127.0.0.1:9944', note: 'confirm a local Portaldot node is reachable + healthy'},
      {cmd: 'pdk-ts diagnose --skip-connect', note: 'inspect the tool itself: version, KB, index'},
      {cmd: 'pdk-ts version --json', note: 'machine-readable version for scripting'},
    ],
  },
  {
    title: 'Dev accounts + POT',
    items: [
      {cmd: 'pdk-ts accounts', note: 'list Alice/Bob/Charlie balances on a local dev node'},
      {cmd: 'pdk-ts keys //Alice', note: 'inspect the well-known Alice keypair (SS58 format 42)'},
      {cmd: 'pdk-ts keys', note: 'generate a fresh 12-word keypair for local dev'},
    ],
  },
  {
    title: 'Explore the runtime',
    items: [
      {cmd: 'pdk-ts pallets', note: 'list every pallet with call / event / error counts'},
      {cmd: 'pdk-ts pallets Balances', note: 'detail one pallet — its calls + error names'},
      {cmd: 'pdk-ts storage System Number', note: 'read the current block number'},
      {cmd: 'pdk-ts storage System Account //Alice', note: 'read a map storage — one account'},
    ],
  },
  {
    title: 'FailLens — the hero',
    items: [
      {cmd: 'pdk-ts explain --module 6 --error 2', note: 'offline fast-path: decode Portaldot-1002 raw code'},
      {cmd: 'pdk-ts explain --name balances.InsufficientBalance', note: 'KB-only lookup — no node needed'},
      {cmd: 'pdk-ts explain --module 6 --error 2 --live', note: 'force metadata walk against any Substrate chain'},
    ],
  },
  {
    title: 'Signing (moves real POT — run against a --dev node)',
    items: [
      {cmd: 'pdk-ts send //Bob --amount 5 --dry-run', note: 'preview the fee + feasibility, submits nothing'},
      {cmd: 'pdk-ts fund //Bob', note: 'top up an account with POT from //Alice (default 100)'},
      {cmd: 'pdk-ts seed', note: 'fund accounts from a YAML fixtures file'},
      {cmd: 'pdk-ts assets create 9001', note: 'create a custom asset class, admin defaults to the signer'},
      {cmd: 'pdk-ts report --exit-code', note: 'exit 2 if any failure is found — CI gate'},
      {cmd: 'pdk-ts watch --pallet Balances', note: 'live-stream chain events, filtered to one pallet'},
    ],
  },
  {
    title: 'Scripting',
    items: [
      {cmd: 'pdk-ts pallets --json | jq \'map(.name)\'', note: 'pipe machine-readable output to jq'},
      {cmd: 'PDK_TS_NODE=ws://127.0.0.1:9944 pdk-ts doctor', note: 'set default node via env var'},
      {cmd: 'DEBUG_POLKADOT_API=1 pdk-ts doctor', note: 'restore verbose @polkadot/api logs for debugging'},
    ],
  },
  {
    title: 'Programmatic (as a library)',
    items: [
      {
        cmd: "import { resolveByName } from 'portaldot-pdk-ts'",
        note: 'offline FailLens lookup — no node, no @polkadot/api pulled',
      },
      {
        cmd: "import { collectReport } from 'portaldot-pdk-ts'",
        note: 'health check inside a backend endpoint or CI script',
      },
      {
        cmd: "import { indexLookup, indexDrift } from 'portaldot-pdk-ts'",
        note: 'raw-code decode + fingerprint drift detection',
      },
    ],
  },
];

export function run(): void {
  console.log();
  console.log(pc.bold('  pdk-ts examples'));
  console.log(pc.dim('  Everything except the "Signing" group is read-only and safe to run anywhere.'));
  console.log();
  for (const g of GROUPS) {
    console.log(`  ${pc.bold(g.title)}`);
    for (const {cmd, note} of g.items) {
      console.log(`    ${pc.green('$')} ${cmd}`);
      console.log(`      ${pc.dim(note)}`);
    }
    console.log();
  }
  console.log(pc.dim('  See `pdk-ts <command> --help` for full options on any of the above.'));
  console.log();
}
