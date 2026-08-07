/**
 * `pdk-ts debug` — FailLens: turn a cryptic failed transaction into a
 * clear diagnosis + fix steps.
 *
 * Two modes: a tx hash, or `--demo` (submits its own failing transfer,
 * paying POT gas, then diagnoses it). Reuses the pieces already built:
 * report's `labelFor` (DispatchError → Pallet.Error) and explain's
 * `resolveByName` (Pallet.Error → curated KB fix).
 *
 * Honest about the decode wall: @polkadot/api can't always decode
 * Portaldot's events in a failed block. When it can't, debug says so and
 * points at Python `pdk debug <hash>` (substrate-interface decodes it
 * reliably) instead of guessing. Same graceful degradation as `report`.
 */

import pc from 'picocolors';
import {getApi, closeApi} from '../core/chain.js';
import {resolveNode} from '../core/config.js';
import {humanizeChainError, stripControlChars} from '../core/errors.js';
import {labelFor} from './report.js';
import {resolveByName} from './explain.js';
import {potToPlancks, submitTransfer} from './send.js';
import {Keyring} from '@polkadot/api';
import {normaliseUri} from './keys.js';

export interface DebugOptions {
  node?: string;
  demo?: boolean;
  timeout?: string;
  json?: boolean;
  exitCode?: boolean;
}

const DEFAULT_SCAN = 30;

// The demo deliberately drains Alice over her balance — a Portaldot failure
// @polkadot/api can't decode live (verified via Python: it decodes to
// Balances.InsufficientBalance). So when the demo hits the decode wall we
// still show FailLens's diagnosis for the failure the demo is KNOWN to
// trigger, clearly labelled — never a fabricated decode of an unknown tx.
export const DEMO_EXPECTED_ERROR = 'Balances.InsufficientBalance';

export type DebugFinding =
  | {status: 'not-found'}
  | {status: 'succeeded'; block: string}
  | {status: 'undecodable'; block: string}
  | {status: 'failed'; block: string; label: string};

/**
 * Scan back `maxBlocks` from the head for the extrinsic `txHash`, and
 * report its outcome. A block whose events @polkadot/api can't decode on
 * Portaldot yields `undecodable` (not a crash) — the same wall `report`
 * hits, surfaced honestly rather than guessed past.
 */
export async function diagnoseTx(
  // biome-ignore lint/suspicious/noExplicitAny: ApiPromise surface is broad.
  api: any,
  txHash: string,
  maxBlocks = DEFAULT_SCAN,
): Promise<DebugFinding> {
  let hash = (await api.rpc.chain.getHeader()).hash;
  for (let i = 0; i < maxBlocks; i++) {
    const signedBlock = await api.rpc.chain.getBlock(hash);
    // biome-ignore lint/suspicious/noExplicitAny: extrinsic codec.
    const exts = signedBlock.block.extrinsics as any[];
    const idx = exts.findIndex((ex) => ex.hash.toHex() === txHash);
    if (idx >= 0) {
      const blockHex: string = hash.toHex();
      try {
        const apiAt = await api.at(hash);
        const events = (await apiAt.query.system.events()) as unknown as Array<{
          // biome-ignore lint/suspicious/noExplicitAny: phase/event codec.
          phase: any;
          event: {data: unknown[]};
        }>;
        const mine = events.filter((e) => e.phase.isApplyExtrinsic && e.phase.asApplyExtrinsic.eqn(idx));
        const failed = mine.find((e) => api.events.system.ExtrinsicFailed.is(e.event as never));
        if (failed) {
          const [dispatchError] = (failed.event as {data: unknown[]}).data;
          return {status: 'failed', block: blockHex, label: labelFor(api, dispatchError)};
        }
        if (mine.some((e) => api.events.system.ExtrinsicSuccess.is(e.event as never))) {
          return {status: 'succeeded', block: blockHex};
        }
        return {status: 'undecodable', block: blockHex};
      } catch {
        return {status: 'undecodable', block: blockHex};
      }
    }
    const header = await api.rpc.chain.getHeader(hash);
    const parent = header.parentHash;
    if (parent.isEmpty || parent.eq(hash)) break;
    hash = parent;
  }
  return {status: 'not-found'};
}

/** Submit a deliberately failing transfer (amount well over Alice's balance). */
// biome-ignore lint/suspicious/noExplicitAny: ApiPromise surface.
async function triggerDemoFailure(api: any): Promise<string> {
  const keyring = new Keyring({type: 'sr25519', ss58Format: 42});
  const alice = keyring.addFromUri(normaliseUri('//Alice'));
  const bob = keyring.addFromUri(normaliseUri('//Bob')).address;
  const outcome = await submitTransfer(api, alice, bob, potToPlancks('1000000000'));
  return outcome.txHash;
}

function emitDiagnosis(txHash: string, label: string, json: boolean): boolean {
  const report = resolveByName(label);
  const known = Boolean(report?.kbEntry);
  if (json) {
    // Match Python `pdk debug --json` exactly: `pallet` is its own field and
    // `error` is the BARE error name (not `Pallet.Error`), so a script keying
    // on either field consumes both CLIs interchangeably. Split the label
    // (properly cased `Balances.InsufficientBalance`), not resolveByName's
    // fields (lowercased from the KB key) — Python emits Title-case.
    const dot = label.indexOf('.');
    const pallet = dot > 0 ? label.slice(0, dot) : '';
    const errorName = dot > 0 ? label.slice(dot + 1) : label;
    console.log(JSON.stringify({
      tx: txHash,
      pallet,
      error: errorName,
      known,
      summary: report?.summary ?? null,
      fix: report?.steps ?? [],
    }));
    return known;
  }
  const border = known ? pc.red : pc.yellow;
  console.log();
  console.log(border(`  ┌─ FailLens — ${txHash.slice(0, 18)}…`));
  console.log(border('  │'));
  console.log(`  ${border('│')}  ${pc.bold(pc.red(`✗ ${label}`))}`);
  if (report?.summary) {
    console.log(border('  │'));
    console.log(`  ${border('│')}  ${pc.bold('What happened')}${known ? '' : pc.yellow('  (no curated entry)')}`);
    console.log(`  ${border('│')}  ${report.summary}`);
  }
  if (report?.steps.length) {
    console.log(border('  │'));
    console.log(`  ${border('│')}  ${pc.bold('How to fix')}`);
    report.steps.forEach((step, i) => {
      console.log(`  ${border('│')}  ${i + 1}. ${step}`);
    });
  }
  console.log(border('  └─'));
  console.log();
  return known;
}

export async function run(txHash: string | undefined, opts: DebugOptions): Promise<void> {
  const node = resolveNode(opts.node);
  const timeoutMs = opts.timeout ? Math.round(Number(opts.timeout) * 1000) : undefined;

  if (!opts.demo && !txHash) {
    const msg = 'Provide a transaction hash, or use --demo.';
    if (opts.json) console.log(JSON.stringify({error: msg}));
    else console.error(pc.red(`\n  ✗ ${msg}\n`));
    process.exit(1);
    return;
  }

  try {
    const api = await getApi(node, timeoutMs);
    let hash = txHash;
    if (opts.demo) {
      hash = await triggerDemoFailure(api);
      if (!opts.json) console.log(pc.dim(`  demo: submitted failing tx ${hash}`));
    }

    const finding = await diagnoseTx(api, hash as string);
    await closeApi();

    if (finding.status === 'not-found') {
      const msg = `No transaction ${hash} found in the last ${DEFAULT_SCAN} blocks.`;
      if (opts.json) console.log(JSON.stringify({error: msg, tx: hash}));
      else console.error(pc.yellow(`\n  ⚠ ${msg}\n  FailLens scans only recent blocks — an older tx is out of range.\n`));
      process.exit(1);
      return;
    }
    if (finding.status === 'succeeded') {
      if (opts.json) console.log(JSON.stringify({tx: hash, success: true}));
      else console.log(pc.green('\n  ✓ that transaction succeeded — nothing to debug.\n'));
      return;
    }
    if (finding.status === 'undecodable') {
      // Demo knows exactly which failure it triggered — diagnose that from
      // the offline KB even though the live event didn't decode.
      if (opts.demo) {
        if (!opts.json) console.log(pc.dim("  (live event undecodable on Portaldot — showing the demo's known failure; Python decodes real ones)"));
        emitDiagnosis(hash as string, DEMO_EXPECTED_ERROR, Boolean(opts.json));
        if (opts.exitCode) process.exit(2);
        return;
      }
      const msg = `found tx ${hash} but @polkadot/api couldn't decode its outcome on Portaldot.`;
      if (opts.json) console.log(JSON.stringify({error: msg, tx: hash, block: finding.block, undecodable: true}));
      else {
        console.error(pc.yellow(`\n  ⚠ ${msg}`));
        console.error(pc.dim(`  This is the known metadata limit. Decode it reliably with Python:\n    pdk debug ${hash}\n`));
      }
      process.exit(1);
      return;
    }

    // finding.status === 'failed'
    emitDiagnosis(hash as string, finding.label, Boolean(opts.json));
    if (opts.exitCode) process.exit(2); // a failure was decoded — CI gate signal
  } catch (err) {
    const msg = humanizeChainError(err, node);
    if (opts.json) console.log(JSON.stringify({error: stripControlChars(msg), endpoint: node}));
    else console.error(pc.red(`\n  ✗ debug failed — ${msg}\n`));
    await closeApi();
    process.exit(1);
  }
}
