# Results — typesafe-system-one

Results log for [DESIGN.md](DESIGN.md). The final claims table (C1–C10 ×
tasks) is written at the end of Part 2; until then it is *(not yet written)*.

## Part 1 — mechanism characterization (2026-09-28)

**Run.** 60 conceptual findings from 11 plans (`build_corpus.py`, seed
`20260928`), 1,860 serial calls to `jev-1.13.0` (every response echoed
`jev-1.13.0`), SDK `typesafe-sdk==0.7.2`, SDK retries disabled. Questions are
the **draft v0** wording in `questions.draft.json`, not yet frozen. The state
was the finding plus the cited step (frontmatter entry and up to 6k chars of
detail file) plus `prior_edit`, the plan/detail diff since the previous audit;
46 of 60 items had a non-empty `prior_edit`. Metrics:
[`part1.metrics.json`](part1.metrics.json); raw responses are cached under
`.tmp/typesafe-system-one/`.

**Gate G1: pass.** Schema validity was 100% and the mean P1b flip rate was
4.4%, under the 5% bar.

| Probe | Result |
|---|---|
| P1a schema (C1) | 2,160 of 2,160 answers valid; 0 call errors |
| P1b repeat stability (C2), 5 identical calls | flip rate: domain **8.3%**, self-seeded **3.3%**, materiality **1.7%**; mean sd(p) 0.009–0.020, max 0.045; byte-identical answers across all 5 repeats on only 7–25% of items |
| P1c batch vs singles (C3), 6 questions | argmax agreement 97.5% (93–100% per question), mean \|Δp\| ≤ 0.023; singles cost **5.1x** the input tokens and **6.0x** the wall-clock of one batch |
| P1d paraphrase, 3 wordings | flip rate 6.7–8.3% per question |
| P1e state size | finding-only vs finding + step: self-seeded shifts on 23% of items (the edit diff is absent), domain on 12%; adding the whole plan (~10k tokens) shifts ≤ 7%, self-seeded 0% |
| P1f latency and cost (C4, C5) | p50 **159 ms**, p95 221 ms, max 749 ms; 6.46M input tokens for **$0.27** in total, **$0.00015** per single-question decision |

**How to read these.**

- **Answers are not deterministic.** Identical requests usually return
  slightly different probabilities. The spread is small (sd ≤ 0.045), so
  argmax flips happen only on items near a decision boundary, but they do
  happen.
- **The per-task stability bar (≤ 2%, decision rule condition 2) fails for
  two of three draft questions.** Domain (8.3%) and self-seeded (3.3%) fail;
  materiality (1.7%) passes. Unless dev-split tuning brings the frozen T1
  and T2 questions under 2%, both tasks will be **not supported** on stability
  alone, whatever their quality. The rule is left as pre-registered.
- **C3 holds in direction but not magnitude.** Batching is 5–6x cheaper and
  faster on these inputs, not the 12.2x / 10.0x the cookbook reports, and it
  changes 2.5% of argmax answers rather than none. That shift is inside the
  repeat-noise band (P1b), so this run cannot separate a batching effect from
  ordinary run-to-run variation.
- **C4 and C5 are supported.** Latency sits at the claimed ~150 ms at p50. The
  whole Part 1 run cost less than one plan-tool `plan_audit` call's median
  ($2.63).
- **State slicing matters where the question depends on it.** Removing
  `prior_edit` moves the self-seeded answer on a quarter of items, as it
  should. Adding the whole plan changes little, at about 3x the tokens.

## Part 2 — corpus and dev-split state (2026-09-28)

**Owner decisions.** Claude baseline spend cap **$25**; **T4 skipped** (no
labeling cost taken on).

**T2 corpus.** Rounds are consecutive completeness reports whose plan commits
differ: **61 edited pairs**, fewer than the design's 99, because `git blame`
can only attribute edits committed between two audits. Those pairs hold 190
new findings; **173 are labeled mechanically (69 positive, 40%)**, split 52 dev
/ 121 test, and **17 have no verbatim quote** (the residue, all sent for owner
labeling). 16 rounds have ≥ 4 new findings for the round-rate check. A spot
check shows the longest quote is sometimes a secondary citation (for example a
test name) rather than the defective text; the 50-item owner noise audit
measures how often that mislabels. On mechanically labeled items B-code *is*
the label, so the model's T2 value can only show on the residue (n = 17).

**T2 dev (n = 52, 22 positive; `t2.dev.metrics.json`).** Single-question AUROC
0.69 at wording w0 (0.63–0.65 at w1/w2); decomposed, leave-one-out 0.67.
The best atom alone ("the edit adds the cited text") reaches 0.73. ECE 0.16–0.20, over
the 0.10 routing bar. **Frozen choices:** single arm w0; decomposed weights as
fit on all 52 dev items.

**T3 corpus.** The replay re-run covers **70 conclusive refactor steps**
(32 fail, 29 uncollectable, 9 pass; 87% would fire, against 89% of 28 on
2026-07-30). **68 items** carry detail `## Tests`, **9 positive**, so T3 reports
descriptively only. The detail format has no `## Changes` section; T3 state is
`## Files (creates vs edits)`, `## Implementation`, and `## Tests` at the step's
parent commit.

**Waiting on.** Owner labels for T1 (150), the T2 noise audit (50), and the T2
residue (17). The question freeze, and every test-split call, follows the T1
dev tuning.
