/**
 * `pdk-ts call <pallet> <call> [args...]` — generic extrinsic composer.
 *
 * Every other signing command (`send`, `assets`) hardcodes one specific
 * pallet call. This one doesn't: it looks up ANY pallet.call pair in
 * live metadata via `api.tx[pallet][call].meta.args` — the same kind of
 * runtime introspection `pallets.ts`/`storage.ts`/`explain.ts` already
 * do against `api.runtimeMetadata`/`api.registry.lookup` — validates and
 * coerces the CLI args against that call's real argument types, builds
 * `api.tx[pallet][call](...args)`, signs with the same `--from` URI
 * pattern as every other signing command, and submits through send.ts's
 * `submitExtrinsic`. That's the whole point: it inherits the project's
 * hard invariant (success confirmed ONLY by a positive
 * `system.ExtrinsicSuccess` event, never by the absence of a
 * dispatchError) for free, instead of a new success-detection path that
 * could get the false-success bug wrong again.
 *
 * Discovery is built in, not an afterthought — a generic composer is
 * useless if you have to already know the signature to try it:
 *   `pdk-ts call <pallet>`         → list the pallet's calls + arg types
 *   `pdk-ts call <pallet> <call>`  → show that call's expected args
 *
 * Coercion deliberately covers a narrow, common slice of primitive
 * shapes — AccountId-like (SS58/`//URI`), unsigned integers including
 * `Compact<...>` wrapping (covers Balance/AssetId/etc, which are type
 * aliases over u32/u64/u128 with no distinct runtime shape), bool, and
 * `Bytes`/`Vec<u8>` as 0x-hex. Anything else (structs, enums, Vec<T> of
 * non-bytes, Option<T>, tuples, signed integers) is a hard, named error
 * — never a silent mis-encode.
 */

import pc from 'picocolors';
import {Keyring} from '@polkadot/api';
import type {ApiPromise} from '@polkadot/api';
import {getApi, closeApi} from '../core/chain.js';
import {resolveNode} from '../core/config.js';
import {humanizeChainError} from '../core/errors.js';
import {normaliseUri} from './keys.js';
import {resolveRecipient, submitExtrinsic, type TransferOutcome} from './send.js';

const POT_DECIMALS = 14; // matches send.ts/simulate.ts/accounts.ts — fees are always paid in the native token regardless of which pallet/call is invoked.

export interface CallOptions {
  from?: string;
  node?: string;
  timeout?: string;
  json?: boolean;
  dryRun?: boolean;
}

export interface CallArgMeta {
  name: string;
  type: string;
}

// ---------------------------------------------------------------------
// Argument type classification
// ---------------------------------------------------------------------

export type ArgKind = 'accountId' | 'integer' | 'bool' | 'bytes' | 'unsupported';

/** Peel N layers of `Compact<...>` down to the inner type name. */
function unwrapCompact(rawType: string): string {
  let t = rawType.trim();
  for (;;) {
    const m = /^Compact<(.+)>$/.exec(t);
    if (!m) return t;
    t = m[1].trim();
  }
}

const ACCOUNT_TYPES = /^(AccountId32|AccountId|MultiAddress|Address|LookupSource)$/i;
// Raw primitives, plus the handful of near-universal Substrate numeric
// *aliases* verified live against Portaldot-1002 metadata — `Balance` is
// always a u128 alias, and pallet-assets always aliases its id/amount as
// `AssetId`/`AssetBalance`/`TAssetBalance`. Deliberately NOT a generic
// "ends with Balance/Id" heuristic: e.g. AccountId also ends with "Id" but
// is a 32-byte hash, not a number — matching that broadly would silently
// mis-encode. Anything not on this exact list falls through to 'unsupported'.
const INT_TYPES = /^(u8|u16|u32|u64|u128|u256|Balance|AssetId|AssetBalance|TAssetBalance)$/i;
const BYTES_TYPES = /^(Bytes|Vec<u8>)$/i;

/** Classify a metadata-reported arg type string into a shape we know how to coerce. */
export function classifyType(rawType: string): ArgKind {
  const t = unwrapCompact(rawType);
  if (ACCOUNT_TYPES.test(t)) return 'accountId';
  if (INT_TYPES.test(t)) return 'integer';
  if (/^bool$/i.test(t)) return 'bool';
  if (BYTES_TYPES.test(t)) return 'bytes';
  return 'unsupported';
}

/**
 * Coerce one raw CLI string into what @polkadot/api's tx builder expects
 * for `kind`. Throws a clear, arg-labelled error on bad input rather
 * than letting a malformed value reach SCALE encoding and either fail
 * opaquely or — worse — encode something the user didn't mean.
 */
export function coerceArg(kind: ArgKind, raw: string, label: string, keyring: Keyring): string | boolean {
  switch (kind) {
    case 'accountId':
      // Same SS58-or-`//URI` rule as every other signing command's
      // recipient argument (send.ts's resolveRecipient) — a bare typo'd
      // word is refused rather than silently derived into a black hole.
      return resolveRecipient(keyring, raw);
    case 'integer':
      // Plain non-negative integer only — same strict guard as assets.ts's
      // parseAssetAmount. BigInt() alone accepts "" (→0n) and "0x10" hex,
      // which would silently corrupt whatever the user typed.
      if (!/^\d+$/.test(raw.trim())) throw new Error(`${label}: expected a non-negative integer, got "${raw}"`);
      return BigInt(raw.trim()).toString();
    case 'bool':
      if (!/^(true|false)$/i.test(raw.trim())) throw new Error(`${label}: expected "true" or "false", got "${raw}"`);
      return /^true$/i.test(raw.trim());
    case 'bytes':
      if (!/^0x[0-9a-fA-F]*$/.test(raw.trim())) throw new Error(`${label}: expected 0x-prefixed hex, got "${raw}"`);
      return raw.trim();
    case 'unsupported':
      throw new Error(`${label}: unsupported argument type — pdk-ts call doesn't know how to encode this yet`);
  }
}

// ---------------------------------------------------------------------
// Metadata lookups
// ---------------------------------------------------------------------

// Case-insensitive key match — mirrors storage.ts's findKey so
// `pdk-ts call balances transferKeepAlive` and `Balances transferKeepAlive`
// both resolve the same way storage/pallets commands already do.
function findKey(obj: Record<string, unknown> | undefined, name: string): string | undefined {
  if (!obj) return undefined;
  const target = name.toLowerCase();
  return Object.keys(obj).find((k) => k.toLowerCase() === target);
}

interface BuiltExtrinsic {
  // biome-ignore lint/suspicious/noExplicitAny: sender is a KeyringPair; paymentInfo's return shape varies by chain, we only touch partialFee.
  paymentInfo: (sender: any) => Promise<{partialFee: {toString(): string}}>;
}

interface TxFn {
  meta: {args: Array<{name: {toString(): string}; type: {toString(): string}}>};
  (...args: unknown[]): BuiltExtrinsic;
}

function txPallets(api: ApiPromise): Record<string, Record<string, TxFn>> {
  // api.tx's shape is generated per-chain at connect time; pallet/call
  // names are resolved dynamically at runtime, same as pallets.ts/storage.ts.
  // biome-ignore lint/suspicious/noExplicitAny: see above.
  return api.tx as any;
}

function argMeta(fn: TxFn): CallArgMeta[] {
  return fn.meta.args.map((a) => ({name: a.name.toString(), type: a.type.toString()}));
}

// ---------------------------------------------------------------------
// Command
// ---------------------------------------------------------------------

export async function run(pallet: string, call: string | undefined, args: string[], opts: CallOptions): Promise<void> {
  const node = resolveNode(opts.node);
  try {
    const api = await getApi(node, opts.timeout ? Math.round(Number(opts.timeout) * 1000) : undefined);
    const tx = txPallets(api);
    const palletKey = findKey(tx, pallet);
    if (!palletKey) {
      const msg = `pallet "${pallet}" not found — try \`pdk-ts pallets\` to list`;
      if (opts.json) console.log(JSON.stringify({error: msg}));
      else console.error(pc.red(`\n  ✗ ${msg}\n`));
      await closeApi();
      process.exit(1);
    }

    // Discovery: no call given — list this pallet's calls + arg signatures.
    if (!call) {
      const calls = Object.keys(tx[palletKey])
        .sort()
        .map((c) => ({name: c, args: argMeta(tx[palletKey][c])}));
      if (opts.json) console.log(JSON.stringify({pallet: palletKey, calls}, null, 2));
      else renderCallList(palletKey, calls);
      await closeApi();
      return;
    }

    const callKey = findKey(tx[palletKey], call);
    if (!callKey) {
      const msg = `call "${call}" not found on pallet "${palletKey}" — run \`pdk-ts call ${palletKey}\` to list its calls`;
      if (opts.json) console.log(JSON.stringify({error: msg}));
      else console.error(pc.red(`\n  ✗ ${msg}\n`));
      await closeApi();
      process.exit(1);
    }

    const fn = tx[palletKey][callKey];
    const meta = argMeta(fn);

    // Discovery: call given, no args, and the call actually needs some —
    // show the signature instead of failing blind on an arg-count error.
    if (args.length === 0 && meta.length > 0) {
      if (opts.json) console.log(JSON.stringify({pallet: palletKey, call: callKey, args: meta}, null, 2));
      else renderCallSignature(palletKey, callKey, meta);
      await closeApi();
      return;
    }

    if (args.length !== meta.length) {
      const sig = meta.length ? ` — ${meta.map((m) => `${m.name}: ${m.type}`).join(', ')}` : '';
      throw new Error(`${palletKey}.${callKey} expects ${meta.length} argument(s)${sig}, got ${args.length}`);
    }

    const keyring = new Keyring({type: 'sr25519', ss58Format: 42});
    const coerced = meta.map((m, i) => coerceArg(classifyType(m.type), args[i], `${m.name} (${m.type})`, keyring));

    const extrinsic = fn(...coerced);
    const sender = keyring.addFromUri(normaliseUri(opts.from ?? '//Alice'));

    if (opts.dryRun) {
      await dryRun(api, extrinsic, sender, palletKey, callKey, meta, coerced, Boolean(opts.json));
      await closeApi();
      return;
    }

    const outcome = await submitExtrinsic(api, extrinsic, sender);
    const ok = emitOutcome(palletKey, callKey, outcome, Boolean(opts.json));
    await closeApi();
    if (!ok) process.exit(1);
  } catch (err) {
    const msg = humanizeChainError(err, node);
    if (opts.json) console.log(JSON.stringify({error: msg, endpoint: node}));
    else console.error(pc.red(`\n  ✗ call failed — ${msg}\n`));
    await closeApi();
    process.exit(1);
  }
}

async function dryRun(
  api: ApiPromise,
  extrinsic: BuiltExtrinsic,
  // biome-ignore lint/suspicious/noExplicitAny: KeyringPair.
  sender: any,
  pallet: string,
  call: string,
  meta: CallArgMeta[],
  coerced: Array<string | boolean>,
  json: boolean,
): Promise<void> {
  const info = await extrinsic.paymentInfo(sender);
  const feeRaw = BigInt(info.partialFee.toString());
  const fee = Number(feeRaw) / 10 ** POT_DECIMALS;
  // biome-ignore lint/suspicious/noExplicitAny: system.account is a well-known storage item present on every Substrate chain; shape is stable.
  const accountInfo = await (api.query.system as any).account(sender.address);
  const balanceRaw = BigInt(accountInfo.data.free.toString());
  const balance = Number(balanceRaw) / 10 ** POT_DECIMALS;
  const feasible = balance >= fee;
  const argsOut = meta.map((m, i) => ({name: m.name, type: m.type, value: coerced[i]}));

  if (json) {
    console.log(
      JSON.stringify({dryRun: true, pallet, call, args: argsOut, fee, senderBalance: balance, feasible}),
    );
  } else {
    console.log(`\n  ${pc.bold(`pdk-ts call ${pallet} ${call} --dry-run`)}  ${pc.dim('(not submitted)')}`);
    for (const a of argsOut) console.log(`  ${pc.dim(a.name.padEnd(20))}${String(a.value)}`);
    console.log(`  ${pc.dim('Estimated fee'.padEnd(20))}${fee.toFixed(6)} POT`);
    console.log(`  ${pc.dim('Sender balance'.padEnd(20))}${balance.toLocaleString('en-US')} POT`);
    console.log(
      `  ${pc.dim('Prediction'.padEnd(20))}${feasible ? pc.green('fee payable') : pc.red('would FAIL — insufficient balance for fee')}`,
    );
    console.log(pc.dim('  (fee-payability only — pdk-ts call cannot predict arbitrary pallet dispatch logic)\n'));
  }
  if (!feasible) process.exitCode = 1;
}

function emitOutcome(pallet: string, call: string, outcome: TransferOutcome, json: boolean): boolean {
  const ok = outcome.status === 'success';
  const action = `${pallet}.${call}`;
  if (json) {
    console.log(JSON.stringify({success: ok, status: outcome.status, tx: outcome.txHash, block: outcome.block, error: outcome.error, pallet, call}));
    return ok;
  }
  if (outcome.status === 'success') {
    console.log(pc.green(`\n  ✓ ${action}`));
    console.log(pc.dim(`  tx: ${outcome.txHash}\n`));
  } else if (outcome.status === 'unconfirmed') {
    console.error(pc.yellow(`\n  ⚠ submitted but the outcome couldn't be confirmed — @polkadot/api can't decode Portaldot's result events.`));
    console.error(pc.dim(outcome.txHash ? `  Confirm with Python: pdk debug ${outcome.txHash}\n` : '  No block inclusion within the timeout — check node connectivity and retry.\n'));
  } else {
    console.error(pc.red(`\n  ✗ ${action} failed${outcome.error ? ` — ${outcome.error}` : ''}`));
    console.error(pc.dim(`  tx: ${outcome.txHash}\n`));
  }
  return ok;
}

// ---------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------

function renderCallList(pallet: string, calls: Array<{name: string; args: CallArgMeta[]}>): void {
  console.log();
  console.log(pc.bold(`  ${pallet}`) + pc.dim(`  (${calls.length} calls)`));
  console.log();
  for (const c of calls) {
    const sig = c.args.map((a) => `${a.name}: ${a.type}`).join(', ');
    console.log(`  ${pc.green(c.name)}${pc.dim(`(${sig})`)}`);
  }
  console.log();
  console.log(pc.dim(`  pdk-ts call ${pallet} <call>  — show one call's argument types`));
  console.log();
}

function renderCallSignature(pallet: string, call: string, args: CallArgMeta[]): void {
  console.log();
  console.log(pc.bold(`  ${pallet}.${call}`));
  console.log();
  if (args.length === 0) {
    console.log(pc.dim('  (no arguments)'));
  } else {
    const nameW = Math.max(...args.map((a) => a.name.length));
    for (const a of args) {
      const kind = classifyType(a.type);
      const support = kind === 'unsupported' ? pc.yellow(' — not supported by pdk-ts call yet') : '';
      console.log(`  ${pc.cyan(a.name.padEnd(nameW))}  ${a.type}${support}`);
    }
  }
  console.log();
  console.log(pc.dim(`  pdk-ts call ${pallet} ${call} ${args.map((a) => `<${a.name}>`).join(' ')}`));
  console.log();
}
