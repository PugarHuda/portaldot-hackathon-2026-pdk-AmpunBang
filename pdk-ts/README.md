# pdk-ts — TypeScript companion for pdk

[![npm version](https://img.shields.io/npm/v/portaldot-pdk-ts?label=npm%20%40alpha&color=orange)](https://www.npmjs.com/package/portaldot-pdk-ts)
[![CI](https://github.com/PugarHuda/portaldot-dev-kit/actions/workflows/pdk-ts.yml/badge.svg)](https://github.com/PugarHuda/portaldot-dev-kit/actions/workflows/pdk-ts.yml)
[![Docker](https://github.com/PugarHuda/portaldot-dev-kit/actions/workflows/docker.yml/badge.svg)](https://github.com/PugarHuda/portaldot-dev-kit/actions/workflows/docker.yml)

Status: **v0.2.0-alpha.7** — 17 commands, covering every chain / FailLens / signing command Python pdk has (`doctor`, `accounts`, `pallets`, `storage`, `keys`, `explain`, `debug`, `report`, `simulate`, `send`, `fund`, `seed`, `watch`, `diagnose`, `examples`, `kb`, `version`), plus `assets` (create/mint/transfer) and the metadata-driven `call` composer. (Python-only `up` (node lifecycle) and `ai-setup` are out of scope for the companion.)

pdk-ts is the TypeScript companion CLI to the Python
[`portaldot-pdk`](https://pypi.org/project/portaldot-pdk/). Same commands,
same terminal UX, Node-backed — so a JS/TS project can use the toolkit
without a Python runtime, and import it as a library
(`import { resolveByName, collectReport } from 'portaldot-pdk-ts'`).

pdk-ts led on Assets pallet signing: `@polkadot/api` signed those calls
correctly while Python `substrate-interface` could not sign them at all on
Portaldot's V13 metadata, failing at the RPC layer with `Invalid
Transaction: bad signature` before dispatch. That is no longer a
difference — pdk 0.2.0 root-caused the underlying `Balance` width
ambiguity and shipped `pdk assets`, so the two are at parity. Pick the one
matching the runtime your project already has.

17 commands covering Python pdk's full chain/FailLens/signing surface — Node-backed, same terminal UX, importable as a library.

## In a hurry

CLI:
```bash
npx portaldot-pdk-ts@alpha explain --name balances.InsufficientBalance
```

Library:
```ts
import { resolveByName } from 'portaldot-pdk-ts';

const fix = resolveByName('balances.InsufficientBalance');
console.log(fix?.summary);
for (const step of fix?.steps ?? []) console.log('→', step);
```

Cold import ~430 ms · offline lookup ~40 ms · no `@polkadot/api` until you actually connect.

## Architecture

```
                   pdk/data/error_fixes.yaml
                    (shared KB — one PR = both CLIs)
                              │
                ┌─────────────┴─────────────┐
                │                           │
        ┌───────▼───────┐          ┌────────▼────────┐
        │  pdk (Python) │          │  pdk-ts (TS)    │
        │  v0.1.7 · PyPI│          │ v0.2 alpha.7·npm α│
        │               │          │                 │
        │ substrate-    │          │ @polkadot/api   │
        │ interface     │          │ (PAPI deferred) │
        └───────┬───────┘          └────────┬────────┘
                │                           │
                └───────────┬───────────────┘
                            ▼
                    Portaldot node
                (WebSocket · runtime metadata)
```

Both CLIs speak the chain via WebSocket + read the chain's runtime
metadata at every invocation — no hardcoded pallet or error tables on
either side. The shared YAML KB adds human-authored fix steps on top.

## Why v0.2 while Python pdk is still v0.1?

Version numbers here are **per-package**, not a global release. Python
pdk shipped stable at 0.1.6 during the hackathon. pdk-ts starts fresh
at 0.2 to signal that this whole track is the *v0.2 initiative*, and the
first `.0` release lands only when it reaches feature parity. Alpha.1–4
built the read-only surface; alpha.5 lit up signing and the full command
surface; alpha.6 was a post-publish QA + packaging-fix pass; alpha.7
shipped Assets pallet signing — which Python could not do at the time,
and matched in pdk 0.2.0.

## Support

- Bugs & feature requests → [issues](https://github.com/PugarHuda/portaldot-dev-kit/issues)
- Security disclosures → [SECURITY.md](https://github.com/PugarHuda/portaldot-dev-kit/blob/master/SECURITY.md)
- Support policy → [SUPPORT.md](https://github.com/PugarHuda/portaldot-dev-kit/blob/master/SUPPORT.md)
- Contribution guide → [CONTRIBUTING.md](https://github.com/PugarHuda/portaldot-dev-kit/blob/master/CONTRIBUTING.md)
- Release notes → [GitHub Releases](https://github.com/PugarHuda/portaldot-dev-kit/releases) (per-version detail also in [`docs/releases/`](docs/releases/))

## Roadmap

| Alpha | Scope | Status |
|---|---|---|
| alpha.1 | `doctor` · `accounts` · `version` — real chain queries | ✅ |
| alpha.2 | `pallets` · `storage` · `keys` — read-only surface | ✅ |
| alpha.3 | `explain` — hero raw-code decoder (skipped ahead of signing) | ✅ |
| alpha.4 | Library entry (`import { resolve, collectReport } from 'portaldot-pdk-ts'`), `diagnose`, `examples`, `kb` introspection, hardening pass | ✅ |
| alpha.5 | Signing tier (`simulate` · `send` · `seed`) + `report` · `watch` + hero `debug` (FailLens) — full command surface, verified live | ✅ |
| alpha.6 | Post-publish QA: ship the KB in the tarball, submission-timeout on `send`/`seed`, `--json` parity with Python, deterministic `watch` exit, doc fixes | ✅ |
| **alpha.7** (current) | `assets` (create/mint/transfer) signing — the surface Python can't sign at all; `send --dry-run`; `fund`; `report --exit-code`; +9 curated KB entries | ✅ |
| alpha.8 | PAPI migration spike: hard blocker found — PAPI only supports metadata V14/V15, Portaldot serves V13, can't connect at all. Deferred until either side moves. Bundle-size pass still open | ✅ (deferred) |
| beta.1  | Hardening + docs pass on the full surface | ◻️ |
| 0.2.0   | Ship as `portaldot-pdk-ts` on npm (`latest` dist-tag) | ◻️ |

## Install (local dev)

```bash
cd pdk-ts
npm install
npm run build
node dist/index.js doctor --node ws://127.0.0.1:9944
```

Or without building, in dev mode:

```bash
npm run dev -- doctor --node ws://127.0.0.1:9944
```

## Commands available today

```
pdk-ts doctor              Health probe against a Portaldot node
pdk-ts accounts            List pre-funded dev accounts + POT balance
pdk-ts pallets [name]      Browse runtime pallets (all, or detail one)
pdk-ts storage <p> <i> [k] Read any storage value from the runtime
pdk-ts keys [source]       Inspect (//Alice, mnemonic) or generate a keypair
pdk-ts explain --module N --error M   Decode a raw code → named error + fix
pdk-ts explain --name <pallet.error>  KB-only lookup (no node required)
pdk-ts debug [txhash]      FailLens — diagnose a failed tx (--demo to trigger one)
pdk-ts report              Scan recent blocks, group failures by error type
pdk-ts watch [--pallet N]  Live-stream chain events as blocks are produced
pdk-ts simulate --amount N Preview a transfer's fee + feasibility (no send)
pdk-ts send <to> --amount N  Submit a REAL POT transfer (transferKeepAlive)
pdk-ts send <to> --amount N --dry-run  Preview the fee + feasibility, submit nothing
pdk-ts fund <to> [--amount N]  Top up an account with POT from //Alice (default 100)
pdk-ts assets create <id>          Create an asset class (admin defaults to the signer)
pdk-ts assets mint <id> <to> --amount N      Mint asset units to an account
pdk-ts assets transfer <id> <to> --amount N  Transfer asset units
pdk-ts call <pallet>                    List a pallet's calls + arg types (metadata-driven)
pdk-ts call <pallet> <call>             Show one call's expected argument types
pdk-ts call <pallet> <call> [args...]   Sign & submit ANY pallet.call, not just the commands above
pdk-ts call <pallet> <call> [args...] --dry-run  Validate + estimate fee, submit nothing
pdk-ts seed [--file f]     Fund accounts from a YAML fixtures file
pdk-ts diagnose            Tool + KB + index + connectivity status
pdk-ts examples            Curated ready-to-copy invocations
pdk-ts kb [--missing]      Knowledge-base introspection
pdk-ts version [--json]    Print CLI version
```

### Windows / git-bash note

Git Bash on Windows converts a single leading `/` in an argument to
a full Windows path (`/Alice` → `C:/Program Files/Git/Alice`). Two
workarounds:

- Use `//Alice` (double slash preserved) or bare `Alice` (pdk-ts
  auto-prepends `//`).
- Or set `MSYS_NO_PATHCONV=1` for the invocation.

PowerShell and Unix shells are unaffected.

Every chain-touching command accepts:

- `--node <ws-url>` — override the default `ws://127.0.0.1:9944`
- `--json` — emit machine-readable output for scripting

`PDK_TS_NODE` environment variable also works as a fallback.

## API — using pdk-ts as a library

Every command exports a `run()` entry plus a pure helper that returns
a structured report. Use the helpers to embed FailLens in your own
tools:

```ts
// All public symbols come from the package root — deep imports into
// dist/* are blocked by the package's `exports` map on purpose.
import {resolveByName, resolve, collectReport, loadKb, lookup, indexLookup} from 'portaldot-pdk-ts';

// Offline KB lookup — no node needed
const named = resolveByName('balances.InsufficientBalance');
console.log(named?.summary, named?.steps);

// Offline index lookup — no node, no @polkadot/api load
const raw = indexLookup(6, 2);   // 'Balances.InsufficientBalance'

// Metadata walk — chain-agnostic, requires a live node
const live = await resolve('ws://127.0.0.1:9944', 6, 2);

// Health probe
const health = await collectReport('wss://rpc.polkadot.io');
```

A worked example lives at
[`examples/basic-consumer/`](../examples/basic-consumer/).

## Troubleshooting

**`pdk-ts doctor` hangs, then errors "could not connect within Xms"**
→ Node URL wrong, or the node is not accepting WebSocket. Verify with
`curl -i http://127.0.0.1:9944` — a WebSocket-only endpoint returns
400 for plain HTTP. Fix the URL scheme (`ws://` for local, `wss://`
for public), or increase `--timeout`.

**`pdk-ts keys /Alice` fails on git-bash (Windows)**
→ MSYS converts single-slash paths to Windows paths (`/Alice` →
`C:/Program Files/Git/Alice`). Use `//Alice` (double slash, preserved
by MSYS), bare `Alice` (pdk-ts auto-prepends `//`), or set
`MSYS_NO_PATHCONV=1` for the invocation.

**`pdk-ts` output shows verbose `@polkadot/api` log lines**
→ Filtering is on by default. If you set `DEBUG_POLKADOT_API=1`, the
logs come back. Unset the env var (`unset DEBUG_POLKADOT_API` in
bash) to re-silence.

**`pdk-ts explain --module N --error M` returns the wrong name**
→ Fast-path resolves against the Portaldot-1002 offline index. If
your node is a different chain (Kusama, Rococo, etc), pass `--live`
to walk metadata instead. When both `--node` and offline-index resolve
succeed, pdk-ts emits a warning field in the JSON output.

**"KB missing or empty" in `pdk-ts diagnose`**
→ pdk-ts couldn't find `pdk/data/error_fixes.yaml`. Ensure you're
running from a clone with the `pdk/` directory intact, or set
`PDK_KB_PATH` to your custom location.

## FAQ

**Q: Can I use pdk-ts against Polkadot / Kusama / any Substrate chain?**
A: Yes — pass `--node wss://<endpoint> --live` for full metadata
resolution. Only the offline fast path is Portaldot-specific.

**Q: When will pdk-ts publish to npm?**
A: Prereleases already ship to the `alpha` dist-tag (`npm install
portaldot-pdk-ts@alpha`). The `0.2.0` stable `latest` release lands after
a beta.1 hardening pass — alpha.8's PAPI migration is deferred (see
Bundle size below), so it's no longer a blocker.

**Q: How is pdk-ts different from `@polkadot/api` or PAPI?**
A: pdk-ts is a **CLI** built on top of those libraries. See the
comparison table at the root README. Short version: PAPI/api are
libraries, pdk-ts is the 17-command dev-loop toolkit.

**Q: What about ink! contracts?**
A: Scoped and dropped. Portaldot's `Contracts` pallet does exist, but
it's an old, pre-2021 rent-model build (`u64` gas, no
`storageDepositLimit`, rent/tombstone errors still present) —
incompatible with modern ink!/`cargo-contract` tooling. This confirms
why pdk-ts uses native pallets (Balances, Assets) instead of deployed
contracts. Not planned.

## Bundle size

Installed `pdk-ts` (node_modules included) is roughly **190 MB** —
mostly `@polkadot/api` and its transitive dependencies for chain
encoding, metadata handling, and crypto. The compiled distributable
(`dist/`) is under **200 KB**; the size lives in the runtime
dependencies, not our code.

The α.8 spike measured PAPI (`polkadot-api@2.1.8`) as a replacement:
its own runtime graph is lighter (~20-23 MB excluding the codegen CLI
it hard-depends on, which pulls in TypeScript/esbuild/rollup and
brings installed size back up to ~88 MB — not the clean win the
headline package size suggests). Moot either way: PAPI's metadata
layer only decodes **V14/V15** metadata, Portaldot's runtime serves
**V13**, and PAPI has no legacy `state_getMetadata` fallback — verified
live, it can't connect to a Portaldot node at all. No bundle-size
optimisation is planned until that's resolved on one side or the
other.

## Design bets

**Metadata-driven, not hardcoded.** Same architecture as Python pdk:
we read the chain's own runtime metadata at every invocation, so error
names, pallet lists, and dispatch types never rot across runtime
upgrades.

**Composable core.** `src/core/chain.ts` is a single lazy `ApiPromise`
factory — commands request the API from it and never construct their
own connection. Same pattern the Python core uses.

**Signing is explicit and opt-in.** Only `send` and `seed` move POT, and
only when you invoke them — every other command is read-only. `npm test`
never touches a live chain (node-dependent paths are verified separately
against a `--dev` node), so contributors can trust the suite won't move POT.

## Contributing

pdk-ts is developed alongside Python pdk in the same repo. If you have a
new Portaldot error to decode, PR it to `pdk/data/error_fixes.yaml` —
both CLIs read from the same knowledge base.

## License

MIT. Same as the parent repo.
