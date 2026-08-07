#!/usr/bin/env node
/**
 * Runs `pdk-ts report --json` (or Python `pdk report --json`), decodes each
 * distinct failure with FailLens (`explain --name`/`explain <name>`, an
 * offline KB lookup — no extra node round trips), and publishes the result
 * as a $GITHUB_STEP_SUMMARY (plus, optionally, a PR comment).
 *
 * JSON shapes this depends on (verified against both CLIs' source and real
 * output — see pdk-ts/src/commands/report.ts + explain.ts and
 * pdk/commands/report.py + explain.py):
 *   report --json  -> {blocks_scanned, total_failures, by_error:[{error,count}], blocks_undecodable?}
 *                      or {error: string, ...} on failure (non-zero exit)
 *   explain --json -> {palletName, errorName, key, summary, steps, kbEntry, source}
 *                      or {error: string, ...} on a KB miss (non-zero exit)
 * Python's `report`/`explain` --json shapes are intentionally ported to
 * match pdk-ts exactly, so this script treats both CLIs identically once
 * invoked — only the argv shape (--name vs positional, --timeout support)
 * differs, handled in explainArgs()/reportArgs() below.
 */
import {execFileSync} from 'node:child_process';
import {appendFileSync, readFileSync} from 'node:fs';

const cli = process.env.PDK_CLI === 'pdk' ? 'pdk' : 'pdk-ts';
const node = process.env.PDK_NODE;
const blocks = process.env.PDK_BLOCKS || '20';
const timeout = process.env.PDK_TIMEOUT || '30';
const maxExplain = Number(process.env.PDK_MAX_EXPLAIN || '10');
const failOnFailures = process.env.FAIL_ON_FAILURES === 'true';
const postComment = process.env.POST_COMMENT === 'true';
const token = process.env.GITHUB_TOKEN;

if (!node) {
  console.error('report-annotate: `node` input is required (WS endpoint of the chain to scan).');
  process.exit(1);
}

/** Run `<cli> <args>`, return parsed JSON stdout. Both CLIs print valid JSON
 * on --json even on their non-zero-exit error paths, so a thrown exec error
 * with parseable stdout is not itself fatal — only unparseable stdout is. */
function runCli(args) {
  try {
    const out = execFileSync(cli, args, {encoding: 'utf8', maxBuffer: 10 * 1024 * 1024});
    return JSON.parse(out);
  } catch (err) {
    const stdout = err.stdout?.toString?.() ?? '';
    if (stdout.trim()) {
      try {
        return JSON.parse(stdout);
      } catch {
        /* fall through to throw below */
      }
    }
    throw new Error(`${cli} ${args.join(' ')} failed: ${err.stderr?.toString?.() || err.message}`);
  }
}

function reportArgs() {
  const args = ['report', '--node', node, '--blocks', blocks, '--json'];
  // Python `pdk report` has no --timeout flag — only pdk-ts supports it.
  if (cli === 'pdk-ts') args.push('--timeout', timeout);
  return args;
}

function explainArgs(errorName) {
  // pdk-ts: `explain --name <key>`.  pdk (Python): `explain <key>` (positional).
  return cli === 'pdk-ts' ? ['explain', '--name', errorName, '--json'] : ['explain', errorName, '--json'];
}

let report;
try {
  report = runCli(reportArgs());
} catch (err) {
  console.error(`report-annotate: ${err.message}`);
  process.exit(1);
}

if (report.error) {
  console.error(`report-annotate: ${cli} report failed — ${report.error}`);
  process.exit(1);
}

const byError = Array.isArray(report.by_error) ? report.by_error : [];
const explained = byError.slice(0, maxExplain).map(({error, count}) => {
  let ex = {};
  try {
    ex = runCli(explainArgs(error));
  } catch {
    /* no KB entry / lookup failed — fall back to the raw name below */
  }
  return {
    error,
    count,
    summary: ex.summary ?? null,
    steps: Array.isArray(ex.steps) ? ex.steps : [],
    kbEntry: Boolean(ex.kbEntry),
  };
});

// error labels are decoded from on-chain data (a malicious/fake node could
// forge them, same reasoning pdk's own CLIs apply when escaping these for
// Rich console rendering) — strip markdown-active characters before they're
// embedded in the summary/comment so a crafted name can't break out of a
// code span or fake bold/heading formatting. Curated KB text (summary/steps)
// is maintainer-authored, not chain data, so it's left as-is.
const mdSafe = (s) => String(s).replace(/[`*_[\]]/g, '');

// --- build the markdown summary ---
const lines = [`## FailLens report (\`${cli} report\`)`, '', `Scanned **${report.blocks_scanned}** block(s) against \`${node}\`.`, ''];

if (report.total_failures === 0) {
  lines.push('No failed extrinsics in range.');
} else {
  lines.push(`**${report.total_failures}** failed extrinsic(s) across **${byError.length}** error type(s):`, '');
  for (const e of explained) {
    const label = mdSafe(e.error);
    lines.push(`### \`${label}\` (${e.count}×)`, '');
    if (e.summary) {
      lines.push(e.summary, '');
      if (e.steps.length > 0) {
        lines.push('**How to fix:**');
        e.steps.forEach((step, i) => lines.push(`${i + 1}. ${step}`));
        lines.push('');
      }
    } else {
      lines.push(`_No curated FailLens entry yet — run \`${cli} explain ${cli === 'pdk-ts' ? '--name ' : ''}${label}\` for details._`, '');
    }
  }
  if (byError.length > explained.length) {
    lines.push(`_...and ${byError.length - explained.length} more error type(s) — see the full \`report --json\` output._`, '');
  }
  if (report.blocks_undecodable) {
    lines.push(`> ${report.blocks_undecodable} block(s) could not be decoded — counts are partial.`, '');
  }
}
const markdown = lines.join('\n');

if (process.env.GITHUB_STEP_SUMMARY) {
  appendFileSync(process.env.GITHUB_STEP_SUMMARY, `${markdown}\n`);
}

if (process.env.GITHUB_OUTPUT) {
  appendFileSync(
    process.env.GITHUB_OUTPUT,
    `blocks-scanned=${report.blocks_scanned}\ntotal-failures=${report.total_failures}\nhas-failures=${report.total_failures > 0}\n`,
  );
}

if (postComment) {
  await upsertPrComment(markdown);
}

console.log(`report-annotate: ${report.total_failures} failed extrinsic(s) in the last ${report.blocks_scanned} block(s).`);

if (failOnFailures && report.total_failures > 0) {
  console.error('report-annotate: failing per fail-on-failures: true');
  process.exit(1);
}

/** Upsert (find-and-edit, else create) a single marked PR comment — reruns
 * update the same comment instead of piling up duplicates. */
async function upsertPrComment(body) {
  const repo = process.env.GITHUB_REPOSITORY;
  const eventPath = process.env.GITHUB_EVENT_PATH;
  if (!repo || !eventPath || !token) {
    console.warn('report-annotate: post-comment requested but missing repo/event/token context — skipping.');
    return;
  }
  const event = JSON.parse(readFileSync(eventPath, 'utf8'));
  const prNumber = event.pull_request?.number;
  if (!prNumber) {
    console.warn('report-annotate: post-comment requested but this run is not a pull_request event — skipping.');
    return;
  }

  const marker = '<!-- pdk-report-annotate -->';
  const fullBody = `${marker}\n${body}`;
  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'pdk-report-annotate-action',
  };
  const commentsUrl = `https://api.github.com/repos/${repo}/issues/${prNumber}/comments`;

  const listRes = await fetch(commentsUrl, {headers});
  if (!listRes.ok) {
    console.warn(`report-annotate: could not list PR comments (HTTP ${listRes.status}) — skipping comment.`);
    return;
  }
  const comments = await listRes.json();
  const prior = comments.find((c) => c.body?.startsWith(marker));

  const res = prior
    ? await fetch(`https://api.github.com/repos/${repo}/issues/comments/${prior.id}`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify({body: fullBody}),
      })
    : await fetch(commentsUrl, {method: 'POST', headers, body: JSON.stringify({body: fullBody})});

  if (!res.ok) {
    console.warn(`report-annotate: failed to ${prior ? 'update' : 'create'} PR comment (HTTP ${res.status}).`);
  }
}
