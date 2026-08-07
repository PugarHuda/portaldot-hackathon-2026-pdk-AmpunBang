# Changelog

All notable changes to **pdk — Portaldot Dev Kit**. Published to PyPI:
`pip install portaldot-pdk`. Format follows [Keep a Changelog](https://keepachangelog.com).

TypeScript companion (`pdk-ts`) tracks its own changelog at
[`pdk-ts/CHANGELOG.md`](pdk-ts/CHANGELOG.md). Milestones cross-referenced
here for repo-level chronology.

## [Cross-repo milestones]
- **2026-07-12** — pdk-ts **0.2.0-alpha.7** ships `assets` (create/mint/
  transfer) — signs Assets pallet calls Python `substrate-interface`
  cannot sign on Portaldot V13 metadata at all, verified live
  (`Assets.create` fails at the RPC layer with "bad signature" from
  Python, succeeds via `@polkadot/api`). Also: `send --dry-run`, `fund`,
  `report --exit-code`. First npm publish of the fix landed here after
  alpha.5's tarball shipped with zero KB data (see alpha.6). Published to
  npm `alpha` + `latest` dist-tags.
- **2026-07-12** — pdk-ts **0.2.0-alpha.6** — post-publish QA pass.
  alpha.5 was pdk-ts's first-ever npm publish, and installing it
  surfaced a critical bug: the shared knowledge base never shipped in
  the tarball, so `explain`/`debug`/`kb` returned "KB size: 0" for every
  installer. Fixed with a build-time copy step; also fixed a hang on
  `send`/`seed` when a tx never reached a block, `--json` parity with
  Python, and a nondeterministic `watch` exit code. alpha.5 deprecated
  on npm; `latest` moved to alpha.6.
- **2026-07-12** — pdk-ts **0.2.0-alpha.5** — the signing tier + hero
  `debug` (FailLens) land, reaching full command-surface coverage
  (16 commands) with Python. `send`/`seed` confirm success only via a
  positive `system.ExtrinsicSuccess` event, never absence-of-error — a
  verified false-success bug on the money path was caught and fixed
  before shipping. `report`/`watch` degrade honestly on Portaldot's
  known @polkadot/api event-decode limit rather than guessing.
- **2026-07-09** — pdk-ts **0.2.0-alpha.4** ships the library entry.
  `import { resolveByName, collectReport } from 'portaldot-pdk-ts'`
  cold-imports in ~430 ms (down from 2792 ms) because `@polkadot/api`
  now loads lazily inside `getApi()`. 10/14 commands covered on the TS
  side. Also: `alpha` npm dist-tag (never accidentally ships prerelease
  as `latest`), non-root Docker image, `.gitattributes` kills the CRLF
  warnings, sourcemaps out of the npm tarball (64 → 36 files, 42 → 35 KB),
  URL scheme validation, humanized WebSocket errors across every
  chain-touching command. Full detail: `pdk-ts/CHANGELOG.md` rounds 7-12.
- **2026-07-09** — pdk-ts **0.2.0-alpha.3** ships `explain` (raw-code
  decoder — the unique feature). 7/14 commands now covered on the TS
  side. Verbose polkadot.js logs silenced from stdout so `--json`
  pipes cleanly. See `pdk-ts/CHANGELOG.md` for details.
- **2026-07-09** — pdk-ts **0.2.0-alpha.2** ships `pallets` · `storage`
  · `keys`. Read-only tier complete. Verified live against Polkadot
  RPC (61 pallets listed, block 32M returned).
- **2026-07-08** — pdk-ts **0.2.0-alpha.1** scaffold pushed. Real
  `@polkadot/api` chain queries, shared KB parser reads Python's
  `error_fixes.yaml`. `doctor` verified against `wss://rpc.polkadot.io`.

## [0.2.0] — 2026-08-07

Closes the command-surface gap with `pdk-ts`, and with it the claim that
Python "cannot sign Assets calls on Portaldot" — which this release makes
false, deliberately. Two new commands (16 → 18) and the two encoding fixes
that had to land first.

### Added
- **`pdk assets`** — `create` · `mint` · `transfer`. Mirrors `pdk-ts
  assets` argument-for-argument. Verified live against a
  `portaldot-1002` node, including a genuine `Assets.BalanceLow`
  dispatch failure reporting as a failure (exit 1) rather than a crash
  or a false success.
- **`pdk call <pallet> <call> [args...]`** — generic extrinsic composer
  over any pallet/call in live metadata, with discovery built in
  (`pdk call <pallet>` lists calls and arg types; `pdk call <pallet>
  <call>` shows one signature) and a `--dry-run` fee preview. Verified
  live on `Balances.transfer`, `Assets.mint`, and `System.remark`.

  Argument types are classified by asking the chain's own type registry
  what each name resolves to, rather than matching a hand-kept list of
  aliases. This runtime declares call arguments as `BalanceOf`,
  `BlockNumber`, `EraIndex`, `Perbill`, `Weight`, `AccountIndex` and
  more — all plain unsigned integers underneath, none of which look
  numeric by name. Composites (`Call`, `Vec<T>`, `Option<T>`, structs)
  are refused with a named error; a signing path never guesses an
  encoding.

### Fixed
- **Assets amount events broke every block they appeared in.** V13
  metadata declares the Assets pallet's amount fields as the bare name
  `Balance`, which resolves globally to u128 while pallet-assets uses
  u64. A block's events are one SCALE-encoded `Vec<EventRecord>` read
  front to back, so the over-wide read desynchronised everything after
  it and the decoder ran off the end of the buffer. `receipt.is_success`
  and `substrate.get_events` both raised for any block containing an
  `Assets.Issued`/`Transferred`/`Burned` event.

  Blast radius went well past the Assets commands: `report` and `debug
  --watch` read events for the whole block, so they crashed on *every*
  failure in a block where any extrinsic happened to move an asset.
  Fixed once at the shared read path (`pdk/core/events.py`), which walks
  the vec and narrows only inside Assets events — a global override is
  impossible, since one `Assets.mint` block carries both an
  `Assets.Issued` (u64) and a `Treasury.Deposit` (u128), both declared
  `Balance`.

  `receipt_succeeded` never reads `receipt.is_success`, not even as a
  fast path: substrate-interface caches partial state, so a property
  that raised once returns a bare `False` on the next read. A
  native-first design reported a successful mint as *failed*, caught
  during live verification.
- **Recipient resolution is now one helper** (`chain.resolve_account`)
  shared by `send`, `assets`, and `call`. Git Bash rewrites `//Bob` to
  `/Bob`, which derives a different valid keypair — applying the repair
  on one path and forgetting it on another sends real value to an
  address nobody controls.

### Changed
- README and `pdk-ts` docs no longer claim Assets signing as the reason
  `pdk-ts` exists; that gap is closed. `pdk-ts`'s standing reason is now
  stated plainly — a Node-native CLI and importable library for projects
  that would rather not add a Python runtime.
- Test suite 126 → 184 cases.

## [0.1.8] — 2026-07-12

A hardening + correctness pass across the CLI surface, plus two new
commands: `fund` (top up an account with POT from `//Alice` — the
literal answer to "how do I get POT?") and `send --dry-run` (preview
the fee + feasibility for the exact transfer before submitting, reusing
`simulate`'s predictor). 16th command overall.

### Security
- **Rich-markup injection blocked.** Chain-sourced doc comments, error
  labels, storage values, and AI-response text are now `escape()`d
  before rendering. A malicious/compromised chain's error doc comment
  could otherwise embed Rich markup — including a real clickable
  `[link=...]` — that rendered inside pdk's own trusted-looking output.
- **Terminal-escape injection blocked** (`decoder.strip_control_chars`).
  `escape()` only neutralizes Rich's `[tag]` syntax, not raw ANSI/OSC
  control bytes; a raw OSC 8 hyperlink escape rendered as a native
  clickable link in many terminals. Stripped at the source
  (`decode_receipt`) plus every direct render site.
- **Prompt-injection defense in depth** for the AI layer: the untrusted
  metadata doc is fenced (`<<<DOC ... DOC>>>`, breakout markers
  neutralized) and the system prompt marks it UNTRUSTED reference data,
  never instructions.

### Fixed
- **`simulate` mispredicted SUCCEED** for a transfer that would drain
  the sender below the existential deposit — `transfer_keep_alive`
  actually fails there. Now models the ED and reports the right error
  (`Balances.KeepAlive` vs `Balances.InsufficientBalance`).
- **Exact planck math.** `pot_to_plancks` uses `Decimal` — the old
  `int(amount * 10**14)` lost a planck to float64 for values like 2.3 /
  0.7 POT, so `pdk send` transferred a hair less than typed.
- **`keys` git-bash mangling.** `pdk keys //Alice` from Git Bash
  silently derived a *different* keypair (MSYS strips a leading slash);
  now normalized, with a hint on the heavier full-path rewrite.
- **`debug --json` / `report --json` now emit JSON on every exit path**
  (bad input, unreachable node, tx-not-found) — the documented CI-citizen
  contract was broken on exactly the error branches automation hits.
- **`PDK_KB_PATH` / `PDK_INDEX_PATH` env overrides honored** (Python
  ignored them, though pdk-ts documented them as "shared with pdk");
  a typo'd path fails fast instead of silently using the bundled default.
- `load_knowledge` degrades gracefully if the KB file is missing/corrupt
  instead of crashing the hero command with a raw traceback.

### Added
- **`pdk explain --live` / `--node`** — the raw-code decoder can now walk
  a live node's runtime metadata, not just the shipped offline index.
  `--live` forces the metadata walk; otherwise a `--node` makes it a
  fallback that kicks in only when the offline index misses — so a code
  from a *newer* runtime (a pallet/error added after the bundled index was
  extracted) still decodes. `source` in `--json` is now `index` |
  `metadata` | `kb-name-only`, matching pdk-ts.
- **`explain` raw-code now returns the decoded name even without a curated
  KB entry** (e.g. `Assets.BalanceZero`) instead of erroring — `kbEntry:
  false`, `summary: null`, `steps: []`, mirroring pdk-ts. Previously a
  raw code outside the ~29 curated errors exited non-zero.
- **`--json` on every scriptable command** (debug, report, kb, keys,
  explain, doctor, accounts, pallets), shapes byte-identical to pdk-ts so
  a script consumes either CLI interchangeably.
- **`pdk kb --verify --node`** — diff the offline index against a live
  node's metadata (mismatch / missing / stale), `--json` for CI.
- **`pdk kb`** — knowledge-base introspection (coverage, `--missing`
  shortlist, `--list`), matching `pdk-ts kb`. 15th command.
- **`pdk kb --verify --node <url>`** — walks a live node's runtime
  metadata and diffs it against the shipped offline `error_index.json`,
  reporting mismatches (a code whose name changed — the fast path would
  return the wrong error), missing, and stale entries. The offline
  fast-path (`explain --module N --error M`) is only as correct as the
  bundled index; after a runtime upgrade this confirms it still matches
  (or flags exactly what drifted). `--json` for CI; exit 1 on any drift.
  Verified live against `portaldot-1002`: 202/202 exact match.
- **`keys --json`** for scripting/seed-fixture consumers.
- **`pdk fund <account> [--amount]`** — top up an account with POT from
  `//Alice` (default 100 POT). Thin wrapper over `send`; answers the #1
  hackathon Q&A question ("how do I get POT?") with a command instead of
  prose. 16th command.
- **`send --dry-run`** — preview the fee + feasibility for the *exact*
  sender/recipient/amount before submitting, reusing `simulate`'s
  `predict_outcome`. `simulate` only ever previewed Alice → Bob; this
  previews the real call.
- **`report --exit-code`** — exit 2 when any failure is found in range,
  mirroring `debug --exit-code`, for CI gating on `pdk report`.
- Shared knowledge base grew **29 → 38 curated entries** (sudo, staking,
  assets, balances dev-loop errors) — see `pdk-ts/CHANGELOG.md` alpha.7
  for the full list; both CLIs load the same YAML.
- Confirmed directly against a live node — the reason `pdk-ts` exists as
  more than a companion: `substrate-interface` cannot sign Assets pallet
  calls on Portaldot's V13 metadata at all (`Assets.create` fails at the
  RPC layer with "Invalid Transaction: bad signature" before reaching a
  dispatch error). `pdk-ts assets` (create/mint/transfer) signs it via
  `@polkadot/api` — the pallet Python is structurally unable to touch.
- Test suite grew to **102 pytest cases** (from 40), now **122**.

## [0.1.7] — 2026-07-09
### Description
- `pyproject.toml` description regenerated to mention the TS companion
  (`pdk-ts`). PyPI project page reflects reality on next tag push.

### Documented troubleshooting
- README now has a **Troubleshooting** section covering every real-world
  problem encountered while building / installing pdk this hackathon:
  Microsoft-Store-Python PATH (`'pdk' is not recognized`), pip cache
  serving v0.1.0, WSL2 localhost edge cases, stalled dev chain
  (BABE epoch error), AI key not picked up, fee-estimator quirk that
  rejects sends after Alice has paid demo fees, Rich Unicode crash on
  Windows cp1252 stdout, release.yml after repo rename, Vercel canonical
  domain 404 after rename. Each entry has the exact command to fix it.


### Changed
- **Release pipeline now uses an API token, not OIDC.** PyPI Trusted Publisher
  records pin to a specific owner+repo pair, and the mid-hackathon repo
  rename broke them. `release.yml` now reads `PYPI_API_TOKEN` from GitHub
  Secrets, so renames no longer require a manual reconfig on pypi.org.
  Added `workflow_dispatch` so a maintainer can re-trigger publish without
  pushing a new tag, and `skip-existing: true` so re-runs are idempotent.
  Verified by manually dispatching the workflow against v0.1.6 — green run.
- Re-linked the Vercel project to the renamed GitHub repo via
  `vercel git connect`. Future master pushes auto-deploy again.
- Web pages (`/`, `/demo`, `/dashboard`, `/errors`, `/slide`) all sync to
  v0.1.6 numbers; `/demo` page hosts an interactive asciinema replay of all
  14 commands plus an embedded 90 s narrated pitch video.
### Added
- README documents the Windows-Store-Python PATH caveat so first-time users
  don't hit "'pdk' is not recognized" after `pip install`.
- Comprehensive QA harness (gitignored, developer-local): 30 CLI smoke
  cases, 30 live-node integration cases, 24 stress + edge cases. Total
  ground-truth coverage = 40 pytest + 84 QA-harness = 124 deterministic
  checks across the 14 commands.

## [0.1.6] — 2026-05-29
### Added
- **`pdk ai-setup`** (new command — total now 14) — first-run wizard that
  prints OpenRouter sign-up steps tailored to the user's shell, tests the
  current key with a small chat-completion round-trip, and explains the
  optional `PDK_AI_MODEL` / `PDK_AI_BASE_URL` overrides. Replaces the
  "where do I even put the key" friction.
- **`pdk simulate --ai`** — adds an AI-suggested fee breakdown panel
  (base / length / weight / tip components) next to the verified fee table.
  Auto-on when `PDK_AI_KEY` is set; opt out with `--no-ai`.
- **`pdk report --ai`** — adds an AI-suggested pattern summary across the
  failure counts (clustered root causes, configuration smells). Same auto-on
  + `--no-ai` semantics.
- **`pdk doctor`** now shows an "AI (optional)" row with the configured key
  preview + model name (or a clear hint to run `pdk ai-setup`).
- 2 more unit tests covering the shared `_should_run_ai` gate on simulate
  and report, plus the `ai-setup --test` exit-code contract. Total: 40.
### Changed
- **AI is now auto-on whenever `PDK_AI_KEY` is set** — no `--ai` flag needed.
  `pdk debug` / `pdk explain` / `pdk simulate` / `pdk report` automatically
  attach the "AI-suggested — UNVERIFIED" panel next to the verified entry.
  The `--ai` flag is still accepted as a force-attempt that surfaces the
  setup hint when no key is configured; new `--no-ai` opts out per-command.
- Pitch video re-rendered as a hybrid: slide intro + **live asciinema
  recording** of the full demo flow (with AI auto-on visible) + uniqueness
  slide + outro. Slide images regenerated with the correct repo URL and the
  current test count; reveal-style navigation footer removed via a new
  `?clean=1` screenshot mode on slide.html.
- Web pitch deck (`/slide`) synced — was claiming "twelve commands · 29 tests";
  now matches the canonical fourteen-commands / 40-tests numbers.
### Fixed
- `test_debug_help_advertises_ci_gating` asserts on the option's description
  text (CI pipeline gating) instead of the flag name; Rich was wrapping
  `--exit-code` on CI's narrow no-TTY terminal which made the literal
  substring check brittle. First green CI in nine commits.

## [0.1.5] — 2026-05-27
### Fixed
- `--ai` hint now references OpenRouter (matches the default provider).
### Changed
- Docs synced to **13 commands** across README, submission, dashboard, and slides.

## [0.1.4] — 2026-05-27
### Added
- `pdk debug --ai` — AI diagnosis on a real failed transaction, grounded in its
  runtime metadata doc.
### Changed
- AI now defaults to OpenRouter's free OpenAI-compatible endpoint
  (`openai/gpt-oss-120b:free`); set `PDK_AI_KEY` and it works out of the box.
  Override with `PDK_AI_BASE_URL` / `PDK_AI_MODEL` for any provider.
### Fixed
- AI was unreachable: an em-dash in the `X-Title` HTTP header broke urllib's
  latin-1 header encoding (`UnicodeEncodeError`). Header values are now ASCII.

## [0.1.3] — 2026-05-26
### Added
- `pdk report` — scan recent blocks, decode and group **every** failed extrinsic
  by error type (table + `--json`). Failure analytics for triage.
- `pdk debug --demo --fix` — diagnose, then submit the corrected transaction and
  show it succeed (diagnose → fix → success).
- `--ai` (opt-in) — metadata-grounded AI diagnosis for the long tail, clearly
  labelled "AI-suggested"; the verified knowledge base stays the source of truth.

## [0.1.2] — 2026-05-26
### Added
- `pdk explain --module 6 --error 2` — decode the raw `DispatchError { Module }`
  code a node prints, with no hash and no name, via a verified 202-entry runtime
  index (`pdk/data/error_index.json`). Nothing else in the ecosystem decodes it.

## [0.1.1] — 2026-05-26
### Fixed
- `pdk debug <unknown-hash>` no longer crashes on a short chain — it walks past
  genesis cleanly and reports "not found".
- Force UTF-8 stdout at startup so Rich output never crashes with
  `UnicodeEncodeError` on a non-UTF-8 Windows console or a redirected pipe.

## [0.1.0] — 2026-05
### Added
- Initial release. **FailLens** (`pdk debug`) plus a 12-command CLI for the
  Portaldot local dev loop — native pallets + metadata-driven decoding, a verified
  29-entry fix knowledge base, real on-chain transactions paying POT as gas, and
  no mocks. Runs on Linux, macOS, and Windows.
