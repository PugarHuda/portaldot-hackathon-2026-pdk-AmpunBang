#!/usr/bin/env node
/**
 * pdk-ts — TypeScript companion CLI for the Portaldot Dev Kit.
 *
 * Wires each `commands/<name>.ts` module into a commander program so
 * `pdk-ts <name>` runs the corresponding handler. Chain-touching commands
 * take a `--node <ws-url>` flag; JSON output via `--json` for scripting.
 *
 * v0.2.0-alpha.1 scope: doctor, accounts, version.
 * Next alphas (in order):
 *   .2  pallets · storage · keys
 *   .3  simulate · send · seed
 *   .4  debug · explain · report · watch · ai-setup
 *   .5  PAPI migration spike + benchmark vs @polkadot/api
 */

import {Command} from 'commander';
import {VERSION} from './core/config.js';
import {installConsoleFilter} from './core/chain.js';

// CLI-only side effect: silence @polkadot/api's verbose stdout so that
// `--json` output stays pure JSON. Library consumers of `portaldot-pdk-ts`
// never load this file — their console stays untouched.
installConsoleFilter();
import * as doctor from './commands/doctor.js';
import * as accounts from './commands/accounts.js';
import * as version from './commands/version.js';
import * as pallets from './commands/pallets.js';
import * as storage from './commands/storage.js';
import * as keys from './commands/keys.js';
import * as explain from './commands/explain.js';
import * as diagnose from './commands/diagnose.js';
import * as examples from './commands/examples.js';
import * as kb from './commands/kb.js';
import * as report from './commands/report.js';
import * as simulate from './commands/simulate.js';
import * as send from './commands/send.js';
import * as fund from './commands/fund.js';
import * as assets from './commands/assets.js';
import * as call from './commands/call.js';
import * as seed from './commands/seed.js';
import * as watch from './commands/watch.js';
import * as debug from './commands/debug.js';

const program = new Command();

// Commander's default on an unknown command is a bare "error: unknown
// command 'X'". Add a hint pointing at the built-in help.
program.showSuggestionAfterError(true);
program.showHelpAfterError('(run `pdk-ts --help` for the full command list)');

program
  .name('pdk-ts')
  .description('TypeScript companion CLI for pdk (Portaldot Dev Kit)')
  .version(VERSION, '-v, --version', 'print version + build status (same as `pdk-ts version`)')
  .addHelpText(
    'after',
    `
Examples:
  $ pdk-ts doctor --node ws://127.0.0.1:9944
  $ pdk-ts accounts --json
  $ pdk-ts pallets Balances
  $ pdk-ts storage System Number
  $ pdk-ts keys //Alice
  $ pdk-ts explain --module 6 --error 2       (offline fast path)
  $ pdk-ts explain --name balances.InsufficientBalance
  $ pdk-ts explain --module 6 --error 2 --live  (force metadata walk)
  $ pdk-ts call Balances                        (list a pallet's calls)
  $ pdk-ts call Balances transferKeepAlive      (show one call's args)
  $ pdk-ts call Balances transferKeepAlive //Bob 1000000000000

Environment:
  PDK_TS_NODE            override the default ws://127.0.0.1:9944
  PDK_KB_PATH            custom path to error_fixes.yaml (shared with pdk)
  PDK_INDEX_PATH         custom path to error_index.json
  DEBUG_POLKADOT_API=1   restore @polkadot/api verbose logs
`,
  );

program
  .command('doctor')
  .description('Health probe against a Portaldot node')
  .option('--node <url>', 'WebSocket endpoint (overrides PDK_TS_NODE)')
  .option('--timeout <seconds>', 'connect timeout in seconds (default 15)')
  .option('--liveness', 'check the chain is producing blocks, ~7s (default: on)', true)
  .option('--no-liveness', 'skip the block-production check')
  .option('--json', 'emit machine-readable JSON')
  .action((opts) => doctor.run(opts));

program
  .command('accounts')
  .description('List pre-funded dev accounts and their POT balance')
  .option('--node <url>', 'WebSocket endpoint (overrides PDK_TS_NODE)')
  .option('--all', 'include //Dave, //Eve, //Ferdie (default: Alice/Bob/Charlie)')
  .option('--json', 'emit machine-readable JSON')
  .action((opts) => accounts.run(opts));

program
  .command('pallets [name]')
  .description('Browse runtime pallets — list all, or detail one')
  .option('--node <url>', 'WebSocket endpoint (overrides PDK_TS_NODE)')
  .option('--timeout <seconds>', 'connect timeout in seconds (default 15)')
  .option('--json', 'emit machine-readable JSON')
  .action((name, opts) => pallets.run(name, opts));

program
  .command('storage <pallet> <item> [keys...]')
  .description('Read a value from runtime storage (raw, in the storage item\'s native unit — Balance-type values are plancks, not POT/DOT)')
  .option('--node <url>', 'WebSocket endpoint (overrides PDK_TS_NODE)')
  .option('--timeout <seconds>', 'connect timeout in seconds (default 15)')
  .option('--json', 'emit machine-readable JSON')
  .action((pallet, item, k, opts) => storage.run(pallet, item, k ?? [], opts));

program
  .command('keys [source]')
  .description('Inspect or generate a keypair (SS58 format 42)')
  .option('--words <n>', 'mnemonic word count when generating (12/15/18/21/24)', '12')
  .option('--json', 'emit machine-readable JSON')
  .action((source, opts) => keys.run(source, opts));

program
  .command('explain')
  .description('Decode a raw Module/error code into a named error + fix steps')
  .option('--module <n>', 'pallet index (from the DispatchError code)')
  .option('--error <n>', 'error index within the pallet')
  .option('--name <pallet.error>', 'skip metadata walk, look up by name directly')
  .option('--live', 'skip the offline index, always walk live runtime metadata')
  .option('--node <url>', 'WebSocket endpoint (overrides PDK_TS_NODE)')
  .option('--timeout <seconds>', 'connect timeout in seconds (default 15)')
  .option('--json', 'emit machine-readable JSON')
  .action((opts) => explain.run(opts));

program
  .command('diagnose')
  .description('Report tool version + KB + index + connectivity status')
  .option('--node <url>', 'WebSocket endpoint (overrides PDK_TS_NODE)')
  .option('--timeout <seconds>', 'connect timeout in seconds (default 8)')
  .option('--skip-connect', 'skip the network probe, report tool + KB only')
  .option('--json', 'emit machine-readable JSON')
  .action((opts) => diagnose.run(opts));

program
  .command('examples')
  .description('Print a curated list of example invocations, grouped by task')
  .action(() => examples.run());

program
  .command('send <to>')
  .description('Submit a REAL POT transfer (transferKeepAlive) — <to> is a //URI or SS58 address')
  .option('--amount <pot>', 'POT to send (required)')
  .option('--from <uri>', 'sender dev account URI (default //Alice)')
  .option('--dry-run', 'preview the fee + feasibility for this exact transfer, submit nothing')
  .option('--node <url>', 'WebSocket endpoint (overrides PDK_TS_NODE)')
  .option('--timeout <seconds>', 'connect timeout in seconds')
  .option('--json', 'emit machine-readable JSON')
  .action((to, opts) => send.run(to, opts));

program
  .command('fund <to>')
  .description('Top up an account with POT from //Alice (default 100 POT)')
  .option('--amount <pot>', 'POT to fund with (default 100)')
  .option('--dry-run', 'preview the fee + feasibility, submit nothing')
  .option('--node <url>', 'WebSocket endpoint (overrides PDK_TS_NODE)')
  .option('--timeout <seconds>', 'connect timeout in seconds')
  .option('--json', 'emit machine-readable JSON')
  .action((to, opts) => fund.run(to, opts));

const assetsCmd = program
  .command('assets')
  .description('Sign Assets pallet operations — the surface Python substrate-interface cannot sign on Portaldot V13 metadata');

assetsCmd
  .command('create <id>')
  .description('Create a new asset class (id must be unused)')
  .option('--admin <uri>', "admin account for the asset (default: --from's account)")
  .option('--min-balance <n>', 'minimum balance for an account to hold this asset (default 1)')
  .option('--from <uri>', 'signing account URI (default //Alice)')
  .option('--node <url>', 'WebSocket endpoint (overrides PDK_TS_NODE)')
  .option('--timeout <seconds>', 'connect timeout in seconds')
  .option('--json', 'emit machine-readable JSON')
  .action((id, opts) => assets.runCreate(id, opts));

assetsCmd
  .command('mint <id> <to>')
  .description('Mint units of an asset to an account (signer must be the asset admin)')
  .option('--amount <n>', 'amount to mint (required, integer)')
  .option('--from <uri>', 'signing account URI (default //Alice)')
  .option('--node <url>', 'WebSocket endpoint (overrides PDK_TS_NODE)')
  .option('--timeout <seconds>', 'connect timeout in seconds')
  .option('--json', 'emit machine-readable JSON')
  .action((id, to, opts) => assets.runMint(id, to, opts));

assetsCmd
  .command('transfer <id> <to>')
  .description('Transfer units of an asset to another account')
  .option('--amount <n>', 'amount to transfer (required, integer)')
  .option('--from <uri>', 'signing account URI (default //Alice)')
  .option('--node <url>', 'WebSocket endpoint (overrides PDK_TS_NODE)')
  .option('--timeout <seconds>', 'connect timeout in seconds')
  .option('--json', 'emit machine-readable JSON')
  .action((id, to, opts) => assets.runTransfer(id, to, opts));

program
  .command('call <pallet> [call] [args...]')
  .description('Generic extrinsic composer — sign & submit ANY pallet.call from live metadata, not just the hardcoded commands')
  .option('--from <uri>', 'signing account URI (default //Alice)')
  .option('--dry-run', 'validate the call + estimate the fee, submit nothing')
  .option('--node <url>', 'WebSocket endpoint (overrides PDK_TS_NODE)')
  .option('--timeout <seconds>', 'connect timeout in seconds')
  .option('--json', 'emit machine-readable JSON')
  .action((pallet, callName, args, opts) => call.run(pallet, callName, args ?? [], opts));

program
  .command('seed')
  .description('Fund accounts from a YAML fixtures file (real transfers from //Alice)')
  .option('--file <path>', 'YAML fixtures file (default: bundled seed.example.yaml)')
  .option('--node <url>', 'WebSocket endpoint (overrides PDK_TS_NODE)')
  .option('--timeout <seconds>', 'connect timeout in seconds')
  .option('--json', 'emit machine-readable JSON')
  .action((opts) => seed.run(opts));

program
  .command('simulate')
  .description('Preview a transfer\'s POT fee + feasibility without sending (Alice → Bob)')
  .option('--amount <pot>', 'POT to simulate transferring (default 1)')
  .option('--node <url>', 'WebSocket endpoint (overrides PDK_TS_NODE)')
  .option('--timeout <seconds>', 'connect timeout in seconds')
  .option('--json', 'emit machine-readable JSON')
  .action((opts) => simulate.run(opts));

program
  .command('debug [txhash]')
  .description('FailLens: diagnose a failed transaction into a named error + fix steps')
  .option('--demo', 'submit a failing transfer, then diagnose it')
  .option('--node <url>', 'WebSocket endpoint (overrides PDK_TS_NODE)')
  .option('--timeout <seconds>', 'connect timeout in seconds')
  .option('--exit-code', 'exit 2 when a failure is decoded (for CI gating)')
  .option('--json', 'emit machine-readable JSON')
  .action((txhash, opts) => debug.run(txhash, opts));

program
  .command('report')
  .description('Scan recent blocks and group every decoded failure by error type')
  .option('--node <url>', 'WebSocket endpoint (overrides PDK_TS_NODE)')
  .option('--blocks <n>', 'how many recent blocks to scan (default 20)')
  .option('--timeout <seconds>', 'connect timeout in seconds')
  .option('--exit-code', 'exit 2 when any failure is found in range (for CI gating)')
  .option('--json', 'emit machine-readable JSON')
  .action((opts) => report.run(opts));

program
  .command('watch')
  .description('Live-stream chain events as blocks are produced (Ctrl+C to stop)')
  .option('--pallet <name>', 'only show events from this pallet (e.g. Balances)')
  .option('--node <url>', 'WebSocket endpoint (overrides PDK_TS_NODE)')
  .option('--timeout <seconds>', 'connect timeout in seconds')
  .option('--json', 'emit one JSON object per event (NDJSON)')
  .action((opts) => watch.run(opts));

program
  .command('kb')
  .description('Knowledge-base introspection — coverage, missing entries, list, or live index verification')
  .option('--missing', 'list index entries without a curated KB fix')
  .option('--list', 'list every curated KB entry')
  .option('--verify', 'check the offline index against a live node (needs --node)')
  .option('--node <url>', 'WebSocket endpoint (for --verify)')
  .option('--timeout <seconds>', 'connect timeout in seconds (for --verify)')
  .option('--json', 'emit machine-readable JSON')
  .action((opts) => kb.run(opts));

program
  .command('version')
  .description('Print pdk-ts version and status')
  .option('--json', 'emit machine-readable JSON')
  .action((opts) => version.run(opts));

// Default help when no command given. Include a first-run tip so
// users immediately know where to find worked example invocations.
if (process.argv.length <= 2) {
  program.outputHelp();
  console.log('\nTip: run `pdk-ts examples` for a curated list of ready-to-copy invocations.\n');
  process.exit(0);
}

/**
 * Guard against async errors that leak past command handlers.
 * `@polkadot/api` can raise on the WebSocket AFTER a command has
 * returned — without these handlers the user sees a bare Node stack
 * trace and the process exits without closing the socket.
 */
import {readableError} from './core/errors.js';

process.on('unhandledRejection', (reason) => {
  process.stderr.write(`pdk-ts: unhandled rejection: ${readableError(reason)}\n`);
  process.exit(1);
});

process.on('uncaughtException', (err) => {
  process.stderr.write(`pdk-ts: uncaught exception: ${readableError(err)}\n`);
  process.exit(1);
});

program.parseAsync(process.argv).catch((err) => {
  console.error(readableError(err));
  process.exit(1);
});
