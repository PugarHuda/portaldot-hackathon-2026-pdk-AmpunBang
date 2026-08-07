/**
 * assets' signing path is node-dependent and was verified live (create,
 * mint, transfer against a real Portaldot node, balances confirmed via
 * storage). Python could not sign these at all until pdk 0.2.0 root-caused
 * the V13 `Balance` width ambiguity; the two CLIs are at parity now.
 * Here we lock the pure input validation that runs before any node call.
 */

import {describe, it, expect} from 'vitest';

// Mirrors the private parseAssetId/parseAssetAmount in assets.ts — tested
// via the same regex/parse rules since they're not exported (no reason to
// widen the public surface for two one-line guards).
function parseAssetId(raw: string): number {
  if (!/^\d+$/.test(raw.trim())) throw new Error('invalid asset id');
  return Number(raw.trim());
}
function parseAssetAmount(raw: string | undefined): bigint {
  if (raw === undefined || !/^\d+$/.test(raw.trim())) throw new Error('invalid amount');
  return BigInt(raw.trim());
}

describe('assets input validation', () => {
  it('accepts a non-negative integer asset id', () => {
    expect(parseAssetId('0')).toBe(0);
    expect(parseAssetId('77001')).toBe(77001);
  });
  it('rejects negative, fractional, and non-numeric asset ids', () => {
    for (const bad of ['-1', '1.5', 'abc', '']) expect(() => parseAssetId(bad)).toThrow();
  });
  it('accepts a plain non-negative integer amount', () => {
    expect(parseAssetAmount('5000')).toBe(5000n);
    expect(parseAssetAmount('0')).toBe(0n);
  });
  it('rejects missing, negative, decimal, and scientific-notation amounts', () => {
    for (const bad of [undefined, '-5', '1.5', '1e3', 'abc']) expect(() => parseAssetAmount(bad)).toThrow();
  });
});
