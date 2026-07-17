/**
 * `call`'s node-touching path (metadata lookup, tx build, submit) was
 * verified end-to-end against a live node across three pallets it has no
 * hardcoded knowledge of — Balances.transferKeepAlive, Assets.create +
 * Assets.mint (parity with the hardcoded `assets` command), and
 * System.remark — including the false-success guard correctly reporting
 * `unconfirmed` on a genuine dispatch failure (duplicate asset id) and a
 * hard error on an RPC-level reject (insufficient balance for fee).
 *
 * Here we lock the pure decisions that run before any node call: which
 * metadata type strings map to which coercion, and that coercion accepts
 * good input / rejects bad input with a clear error rather than a silent
 * mis-encode.
 */

import {describe, it, expect} from 'vitest';
import {Keyring} from '@polkadot/api';
import {classifyType, coerceArg} from '../src/commands/call.js';

describe('classifyType', () => {
  it('recognises account-like types, incl. Portaldot legacy LookupSource', () => {
    for (const t of ['AccountId', 'AccountId32', 'MultiAddress', 'Address', 'LookupSource']) {
      expect(classifyType(t)).toBe('accountId');
    }
  });

  it('recognises raw unsigned integer primitives', () => {
    for (const t of ['u8', 'u16', 'u32', 'u64', 'u128', 'u256']) {
      expect(classifyType(t)).toBe('integer');
    }
  });

  it('recognises known numeric aliases (Balance, AssetId, AssetBalance)', () => {
    for (const t of ['Balance', 'AssetId', 'AssetBalance', 'TAssetBalance']) {
      expect(classifyType(t)).toBe('integer');
    }
  });

  it('unwraps Compact<...> — including nested — down to the base type', () => {
    expect(classifyType('Compact<u128>')).toBe('integer');
    expect(classifyType('Compact<Balance>')).toBe('integer');
    expect(classifyType('Compact<AssetId>')).toBe('integer');
    expect(classifyType('Compact<Compact<u32>>')).toBe('integer');
  });

  it('recognises bool', () => {
    expect(classifyType('bool')).toBe('bool');
  });

  it('recognises Bytes / Vec<u8>', () => {
    expect(classifyType('Bytes')).toBe('bytes');
    expect(classifyType('Vec<u8>')).toBe('bytes');
  });

  it('refuses everything else instead of guessing', () => {
    for (const t of ['Vec<AccountId32>', 'Option<u32>', '(u32,u32)', 'AssetDestroyWitness', 'Perbill', 'i32', 'H256']) {
      expect(classifyType(t)).toBe('unsupported');
    }
  });
});

describe('coerceArg', () => {
  const keyring = new Keyring({type: 'sr25519', ss58Format: 42});

  it('accountId: derives a //URI and passes a valid SS58 address through', () => {
    const bob = keyring.addFromUri('//Bob').address;
    expect(coerceArg('accountId', '//Bob', 'dest', keyring)).toBe(bob);
    expect(coerceArg('accountId', bob, 'dest', keyring)).toBe(bob);
  });

  it('accountId: rejects a bare typo word (money-command-strict, same rule as send.ts)', () => {
    expect(() => coerceArg('accountId', 'NOTANADDRESS', 'dest', keyring)).toThrow(/not a valid SS58 address/);
  });

  it('integer: accepts a plain non-negative integer string, returns it as a decimal string', () => {
    expect(coerceArg('integer', '1000000000000', 'value', keyring)).toBe('1000000000000');
    expect(coerceArg('integer', '0', 'value', keyring)).toBe('0');
  });

  it('integer: rejects negative, decimal, hex, and empty input', () => {
    for (const bad of ['-5', '1.5', '0x10', '', '1e3', 'abc']) {
      expect(() => coerceArg('integer', bad, 'value', keyring)).toThrow(/expected a non-negative integer/);
    }
  });

  it('bool: accepts "true"/"false" case-insensitively', () => {
    expect(coerceArg('bool', 'true', 'keepAlive', keyring)).toBe(true);
    expect(coerceArg('bool', 'FALSE', 'keepAlive', keyring)).toBe(false);
  });

  it('bool: rejects anything else', () => {
    expect(() => coerceArg('bool', 'maybe', 'keepAlive', keyring)).toThrow(/expected "true" or "false"/);
  });

  it('bytes: accepts 0x-prefixed hex, passes it through unchanged', () => {
    expect(coerceArg('bytes', '0x70646b2d7473', 'remark', keyring)).toBe('0x70646b2d7473');
  });

  it('bytes: rejects input without a 0x prefix or with non-hex characters', () => {
    expect(() => coerceArg('bytes', 'pdk-ts', 'remark', keyring)).toThrow(/expected 0x-prefixed hex/);
    expect(() => coerceArg('bytes', '0xzz', 'remark', keyring)).toThrow(/expected 0x-prefixed hex/);
  });

  it('unsupported: always throws, naming the arg', () => {
    expect(() => coerceArg('unsupported', 'whatever', 'witness (AssetDestroyWitness)', keyring)).toThrow(
      /witness \(AssetDestroyWitness\): unsupported argument type/,
    );
  });
});
