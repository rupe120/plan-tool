# Token-optimization experiments: retro and next experiments

Written 2026-10-16. Covers the instruction-loading experiment (2026-10-13 to
10-14) and the June experiments it builds on (`minimize-claude`,
`lessons-utility`). It reports what the records support and where they stop; it does not change policy.

## Summary

| Experiment | Tested | Result | Strength |
| --- | --- | --- | --- |
| `harness-instruction-loading` | Full CLAUDE.md (A) vs compact entry point plus on-demand reference (B), 6 tasks x 3 reps x 2 conditions | B passed 13/18 checks vs A 18/18, and used more tokens (median +21.6% non-cached, +48.6% input+output) and time (+38.9%). Misses the DESIGN bar (20% tokens or 15% time). | 18 pairs; two graders relaxed after outputs were seen; owner scope grading not done |
| `minimize-claude` (June) | Where `create`/`detail`/`completeness` spend Claude calls | One validated win (skip step re-proposal after prose-only fixes, about 50% of `create` Claude time, now on by default). Two `detail` levers discarded for quality or cost. | Mechanism-level, n=2 to 3 per cell |
| `lessons-utility` (June) | Whether injected lessons earn their tokens | Store is 88.5% dead weight at the prompt, and the salience signal does not exist. Utility runs (C0 vs C1) never ran. | Volume only; no utility result |

Net: no experiment has yet shown a safe reduction in instruction text, and the
only validated token win came from removing redundant model calls, not from
shrinking prompts.

## 1. Instruction-loading (CLAUDE.md routing)

**Question.** Does a compact, task-routed CLAUDE.md reduce the cost of
developing plan-tool without losing required behavior?

**What was measured.** 36 scored trials (18 adjacent A/B pairs, seed 20261013,
9 A-first) on `gpt-6.1-sol`, in offline containers. Totals: 3,896,340
non-cached tokens, no nonzero exit or limit breach.

**Results** (from `harness-instruction-loading/RESULTS.md`):
A passed 18/18 external checks, B 13/18. B's failures were T6 reps 1-3 (Stack
not recognized as a guardrail heading in the fence) and T2 reps 1-2 (Stack row
labels lacking the `stack` prefix). Median paired cost of B relative to A:
+48.6% input+output, +21.6% non-cached, +38.9% elapsed.

**What the record supports.**
- On these tasks the routed layout did not save tokens or time. It cost more.
- Both quality failures concern the Stack guardrail. That points at what the
  compact entry point retained, not at routing in general. The coverage table
  (rule-to-destination) is where such a gap should have been caught.
- B read `docs/` reference files on demand and in one T1 trial spawned a
  `collab_tool_call` (first pair: A 80,961 vs B 97,661 non-cached tokens). So
  retrieval work appears to cost more than the startup text it replaced. This
  is an observation from one pair, not a measured mechanism.
- Startup guidance is a small share of session tokens. The two T1 calibration
  probes used 1.3M and 1.6M input+output tokens, about 1.5M of it cached, and
  non-cached was roughly 90k. Cached prefix reads dominate; shrinking the
  prefix attacks the cheap part.

**What the record does not support.**
- That routing is worse in general: one task set, one routed layout, one model.
- Why B was costlier: no per-call attribution exists, and reviewer-session
  usage is not observable.
- Anything about owner scope/rule grading: not done.

**Threats to validity, as recorded.**
- Three grader relaxations happened after outputs were seen (T1 twice, T3
  once). They apply to A and B equally, but they were made post hoc, and the
  second one was made after a scored B output. The pass counts are therefore
  conditional on graders that were not fully frozen.
- Evidence was lost once: the raw directory sat in `/private/tmp` and a reboot
  cleared it. Inputs were rebuilt and re-verified (hashes match), but sandbox
  probes and the controller suite were not repeated. Evidence now lives in the
  repo's gitignored `.tmp/`.
- Calibration used only condition A probes to set the limits.

## 2. Chat-session skill screen (not kept)

A screen of a candidate chat skill against the tracked router (8 scenarios, one
evaluator per condition) did not discriminate: both followed the directives on
every scenario, because each evaluator read the whole shared directives file.
It measured no tokens or time and is not evidence for or against the
candidate. Its records are deliberately not kept; the section number stays so
the `§ 5` citations elsewhere remain valid.

## 3. June experiments still relevant to token cost

**`minimize-claude`** (2026-06-17), mechanism-level:
- **Kept.** After a prose-only fix round, `create` re-proposed steps and
  references from unchanged input, which is pure re-roll. Skipping it removed 2
  calls per run and about 45-52% of Claude time with quality parity (3 seeds, n=3
  each). The behavior is now on by default (`--no-skip-prose-reproposal` opts
  out).
- **Discarded: `detail` audit-once.** About half the cost saved, but it left 3-6
  real issues unfixed. `detail`'s re-audits read the edited file and find new
  issues, so they are load-bearing, not churn.
- **Discarded: sampled initial scan.** It cost 1.0-2.2x more and gave no
  quality gain, because re-audit findings are introduced by edits.
- **Left alone: `completeness`.** Already audits once up front; the only lever
  is `--audit-samples`, a stability-versus-cost trade.

**`lessons-utility`** (2026-06-18), volume only:
- 305 bullets, about 405 KB on disk; blind recency truncation injects 35
  (11.5%). The largest surface (`domain-shape`, 204 bullets) is injected by no
  prompt.
- Citations record creation, not reuse (exactly 1 per bullet), so a salience
  ranking has no signal. Conditions C0/C1 (lessons off vs on) never ran, so
  whether lessons earn their tokens is unanswered.

## 4. Lessons about how we run these

1. **Remove redundant calls before shrinking prompts.** The one validated win
   came from identical-input re-rolls; the instruction-text experiment lost.
2. **Same loop shape does not imply the same waste.** Whether a re-derive is
   churn depends on whether its input changed (`create` re-proposal: no;
   `detail` re-audit: yes).
3. **Judge by mechanism, not wall-clock, at small n.** Wall-clock noise is about
   10% (`create`), 19-30% (`detail`), and a bimodal "did the loop fire" fork
   swings 60%.
4. **Instrument before measuring.** Every June track found unlogged call sites
   (`apply_finding` without a logger, unlogged audit samples). Count cached and
   non-cached separately: the headline measure and the budget used different
   definitions, and the difference is about 15x here.
5. **Freeze graders before sampling.** Post-hoc relaxation is disclosed but
   still weakens the pass/fail comparison.
6. **Keep evidence in the repo's `.tmp/`, never `/tmp`.**
7. **Quality parity is part of the result.** Mechanism wins were discarded twice
   for quality, and the CLAUDE.md experiment's cost increase came with fewer
   passes.

## 5. Suggested experiments for general token optimization

Ordered by cost and information value. Items 1-4 are read-only analysis of
existing logs and files, with no new model spend.

1. **Per-command token ledger.** Replay `.plan-tool/runs/**` JSONL through
   `scripts/analyze_run_log.py` (extended to split cached and non-cached input
   plus output) to rank call sites by non-cached tokens for `create`, `detail`,
   `completeness-audit`, `run`, and the reconcile verbs. Check first that every
   call site logs `claude_call_end`; the June instrumentation gaps may have
   re-opened as code changed. *Decision it drives:* which of the following
   deserves effort at all.
2. **Identical-input call detector.** Hash each call's full prompt inputs per
   run and count repeats. The June win was exactly this pattern (same input,
   re-rolled output). Any repeat group that ends in the same applied outcome is
   a candidate skip. *Output:* a ranked list of repeat groups, each with an
   input-changed-or-not verdict before anyone proposes a skip.
3. **Audit sample yield.** From saved completeness reports, measure how many
   material findings samples 2 and 3 add over sample 1, per plan. If the
   marginal yield of the third sample is near zero, `--audit-samples` can drop
   with a quality check; if not, the default stays. Needs the stable-identity
   matching that `convergence` already uses.
4. **Prompt composition audit.** For each prompt template, measure static text
   versus injected blocks (plan body, detail files, code excerpts, lessons,
   directives) in tokens per call. *Output:* the top injected blocks by size,
   so ablations target the largest first.
5. **Lessons utility, two arms before any selection work.** (a) Surface
   filtering only: stop injecting surfaces no prompt uses, and measure the
   freed budget. (b) C0 vs C1 (lessons off vs on) with the June rubric and a
   noise floor from N>=2. Do not build salience selection until a reuse event
   exists (June seed `lessons-reuse-instrumentation`).
6. **Prefix stability and cache hits.** Order each prompt stable-first (rules,
   plan) and variable-last (findings, diffs), then compare non-cached input
   before and after on the same replayed inputs. Since non-cached input was
   about 6% of total in the T1 probes, this is only worthwhile if item 1 shows
   large non-cached input on repeated calls with a shared prefix.
7. **Context ablation per prompt.** For the top blocks from item 4, drop or
   trim one block at a time on a fixed set of replayed inputs and compare
   outputs on the deterministic checks plus a frozen rubric. This is the
   defensible form of "smaller instructions": per block, with a quality check,
   not a wholesale reorganization.
8. **Model-tier downshift for mechanical calls.** Test prose-only applies and
   deterministic-verdict calls on a cheaper tier with a quality rubric. The
   directives already put everything except `create` and `roadmap` on the
   working tier, so only calls below that line are open.
9. **Instruction-loading, second attempt (only if wanted).** Change what was
   wrong, not the idea: the fixed coverage table must include the Stack
   guardrail vocabulary; freeze all graders and the schedule before sampling;
   report non-cached tokens as the headline; add per-call attribution so a
   cost difference can be explained; consider trimming duplicated rules across
   CLAUDE.md and DIRECTIVES.md instead of routing. This is the most expensive
   item and the one with a negative first result, so it goes last.

**Standing protocol for all of them:** state the mechanism observable (calls
eliminated, tokens by call site) before running; take a noise floor first; run
a quality parity check; keep graders frozen; commit evidence in the repo;
get a concrete resource envelope approved before any spend.

## Update, 2026-10-16: token ledger

`experiments/token-ledger/REPORT.md` measured the tool's own runs (1,480 logged
calls). It changes three statements above:

- Cached input is 89% of all input across the log, which supports the claim that
  startup guidance is the cheap part; the "about 6%" non-cached share came from
  the two T1 probes only.
- `domain-shape` lessons are injected by `detail` (`plan_tool/detail.py:225`);
  the June finding that no prompt injects them is superseded.
- Completeness `plan_audit` is 47% of non-cached input plus output tokens (193M
  of 406.8M), so experiment 7 should start there, and lessons filtering (5a) is
  rescoped to the lessons block in `detail` and `create`.

Experiments 2 and 3 were blocked on logging; that shipped in pull requests 101
and 102. Current status: `BACKLOG.md` #495 (the `--audit-samples` decision and its resume trigger).
Experiment 9 has no support in this data.
