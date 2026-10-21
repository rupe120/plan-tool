# Experiment design — typesafe-system-one

**Question.** Does TypeSafe's System One model (`jev-1.13.0`) deliver the value
it claims — calibrated, stable, cheap, fast typed decisions — on decisions
plan-tool actually makes, compared with what plan-tool uses for those decisions
today (a deterministic heuristic, a Claude call, or session judgment)?

**What this experiment changes in plan-tool: nothing.** It runs entirely under
`experiments/typesafe-system-one/`. No file under `plan_tool/`, `tests/`,
`pyproject.toml`, `uv.lock`, or CI is touched. The SDK is resolved per script
through PEP 723 inline metadata (`uv run --script`), so it never enters the
project's dependency set. Any later integration is a separate, opt-in, scoped
`BACKLOG.md` entry, and it is proposed only for a task this experiment marks
**supported**.

**Prior withdrawn mechanisms are not grounds for excluding a task.** System One
is a different mechanism from the phrase matchers plan-tool withdrew: a trained
model returns probabilities over typed options, where a phrase matcher only
checks vocabulary. The withdrawn cases are used here in two ways only: as
known-hard test inputs (T3) and as the reason for the fail-open error metric
(T1). A task is left out only when no ground truth exists for it (see
§ "Deliberately not tested").

## Vendor claims under test

Each claim is tested where plan-tool would rely on it. Sources are the
docs.typesafe.ai pages fetched on 2026-09-28.

| # | Claim | Source | Tested in | Metric |
|---|---|---|---|---|
| C1 | Answers always conform to the requested type | `api`, `coding-agents` | Part 1 | schema-valid rate |
| C2 | Stable answers across repeated evaluations | `how-to-build-with-system-one` | Part 1 | argmax flip rate, sd(p) |
| C3 | Batching questions into one call is cheaper and faster, with no change in answers | `cookbooks/parallel_questions` (12.2x cheaper, 10.0x faster) | Part 1 | agreement, token and latency ratio |
| C4 | Fast (~100–150 ms) | `how-to-build…`, `use-case-map` | Part 1 | p50/p95 latency |
| C5 | Cheap ($0.042 / M input tokens, output free) | `models` | Part 1, 2 | $ per decision from `usage` |
| C6 | Probabilities are calibrated (RLCD-trained) | `system-one`, `models` | Part 2 | Brier, ECE, reliability diagram |
| C7 | Confidence can route: automate the confident, escalate the rest | `confidence`, `patterns/confidence-routing` | Part 2 | risk–coverage curve |
| C8 | Decomposed atomic questions combined in code beat one broad question | `how-to-build…`, `patterns/composite-scoring` | Part 2 (T2) | AUROC, decomposed vs single |
| C9 | Verification quality comparable to an LLM at a fraction of the cost | `use-case-map` (Universal Verification, Guardrails) | Part 2 | quality vs Claude, cost ratio |
| C10 | Replaces fragile "return JSON" prompts | `coding-agents` | Part 2 | parse-failure rate vs Claude |

**The C10 baseline is already low.** plan-tool's measured Claude parse-failure
rate is 1 in 228 calls (`plan-tool-2` run logs), so C10 can at most show a
marginal gain here.

No vendor page publishes a calibration figure, accuracy figure, or seed or
determinism option (`confidence`, `api`), so C2 and C6 are measured here, not
assumed.

## Corpus sources

Three sources feed the corpus. Reports from the two clones are unioned and
deduplicated by (`plan_slug`, `created_at`, recommendation `id`).

| Source | What it holds | Used for |
|---|---|---|
| `plan-tool-1` tracked reports (`docs/implementation-plans/plan-details/*/reports/*.json`) | 353 reports, 729 recommendations (623 conceptual), 99 edited consecutive completeness pairs | T1, T2, Part 1 items |
| `plan-tool-2` reports | 8 further report JSONs, not present in `plan-tool-1` | same |
| `plan-tool-2` untracked `.plan-tool/runs/*` run logs | 228 `claude_call_end` events with `cost_usd`, `duration_ms`, and tokens; 72 `plan_audit` calls (median $2.63 and 88 s per call; p95 698 s; $37.26 total) | the cost of today's decisions (C5, C9, C7 value framing) |
| `plan-tool-2` `.plan-tool/parse-failures/` | 1 parse failure in 228 Claude calls | the C10 baseline |

Two parts of `plan-tool-2` are deliberately not used:

- **The run logs' `claude_stream_event` records.** They carry tool-use
  summaries only, with no finding text, so they add nothing to labels.
- **`telemetry/decisions.jsonl`.** Its 219 prompt-budget and 101 granularity
  records have no outcome labels.

**How the cost baseline frames C7 value.** System One would not replace an
audit call. Its value case is avoiding or narrowing one: for example, a
high-confidence T2 "self-seeded" majority signals exit 2 without another
$2–3, ~90 s audit round. Part 2 reports routing results in those units: audit
rounds and dollars avoided at the measured precision.

## Design constraints taken from the vendor's own failure list

`model-jaggedness/jev-1.13` names nine failure modes. The design applies each
one that bears on these tasks:

- **Arithmetic stays in code.** A round's self-seeded *rate* (T2) is computed
  from per-finding probabilities in code. The model is never asked to count.
- **State is sliced.** Each item sends only what its question needs: the
  finding, the cited step section, and for T2 the preceding edit's diff hunk.
  Part 1 (P1e) measures what unsliced state costs.
- **Literal reading.** Question instructions state the exact condition and its
  boundary cases, including repo-specific policy (for example, a step detail
  `.md` file is plan content, not documentation). Part 1 (P1d) measures
  sensitivity to paraphrase.
- **Adversarial content.** Findings in this repo quote prompts and instructions
  verbatim. State is passed as structured JSON fields, never concatenated into
  `instructions`.

## Part 1 — mechanism characterization (no labels needed)

This part tests C1–C5 on plan-tool-shaped inputs. **Inputs:** 60 conceptual
findings drawn with a fixed seed from the union corpus (§ "Corpus sources"),
each with its cited step section. **Questions:** the frozen T1 Choice, the T2 Noul,
and one Score (finding materiality, three levels), so all three primitives are
exercised.

| Probe | Procedure | Output |
|---|---|---|
| P1a schema | every response below | valid-type rate (expect 100%) |
| P1b repeat stability | each (state, question) × 5 identical calls | argmax flip rate, sd(p) |
| P1c batch equivalence | the 3 questions + 3 T2 decomposition Nouls, sent once as a batch and once as 6 single calls | argmax agreement, \|Δp\|, token ratio, wall-clock ratio |
| P1d paraphrase | 3 equivalent wordings per question | argmax flip rate across wordings |
| P1e state size | finding only / + step section / + whole plan (capped at 32k) | answer shift, latency, tokens |
| P1f cost and latency | all calls above | p50/p95 latency, $ per decision |

**Gate G1 (verdict only; the downstream design does not change):** proceed to
Part 2 when schema validity is 100% and the P1b flip rate is ≤ 5%. Otherwise
stop and record the result, because unstable answers would make every Part 2
metric noise.

## Part 2 — decision tasks with ground truth

Each task names the plan-tool decision it would feed, the current way plan-tool
makes that decision, and where its labels come from.

### T1 — finding domain (Choice; classification)

- **Plan-tool decision.** `review.py:classify_finding_domain` →
  `convergence.is_blocking_finding`. A `"docs"` label demotes a medium
  conceptual finding from blocking.
- **Options.** `code-logic`, `unit-test`, `docs`, `unknown`. Each option's
  description is taken from the policy in `docs/how-to/pipeline/audit.md`,
  including the step-detail-file rule from commit `0ebbb0f5`.
- **Labels.** The owner labels, blind, 150 medium conceptual findings,
  stratified by the current matcher's label. The 2026-09-28 tally gives the
  targets: all 32 `docs`, all 3 `unit-test`, 40 `code-logic`, and 75
  `unknown`. `build_corpus.py` recomputes the strata over the union corpus and
  keeps the 150 total. Split: 50 dev, 100 test.
- **Primary endpoints.** Macro-F1, plus the **false-`docs` rate** (a true
  non-docs finding labeled `docs`). A false `docs` label is the fail-open
  error, because it demotes a blocking finding.

### T2 — self-seeded finding (Noul; detection, single vs decomposed)

- **Plan-tool decision.** The `self-seeded-finding` audit shape, currently
  `judgment_only`, which the operating rules use as exit 2 of the convergence
  loop ("the loop is auditing your own edits").
- **Item.** A finding that is new in audit round N, together with the plan diff
  between rounds N−1 and N, sliced to the hunks touching the cited step.
- **Label source.** 491 of the 623 conceptual findings quote plan text
  verbatim, so the label can be derived mechanically. **Positive:** `git blame`
  on the plan file at round N attributes the quoted span to a commit between
  the two audits. **Negative:** the span predates round N−1. The owner audits
  50 mechanical labels, blind, to measure label noise. Findings with no
  verbatim quote form a residue; the owner labels a 50-item sample of it.
- **Arms.**
  - **Single:** one Noul — "does this finding describe text that the edit
    introduced?"
  - **Decomposed:** 3–4 atomic Nouls (the edit adds the cited text; the finding
    names a contract the edit created; the finding would be false before the
    edit) combined with weights set on the dev split.
- **Round-level check.** For each round with ≥ 4 new findings, compare the
  mean of p against the labeled self-seeded rate.
- **Primary endpoint.** AUROC on the test split (70% of the mechanically
  labeled items), plus round-rate error.
- **Code baseline.** The `git blame` rule is itself a deterministic detector
  that needs no model. The model's value is therefore judged in two places: on
  the full set, where the model sees no git history, and on the residue that
  `blame` cannot reach.

### T3 — refactor preserves the test-visible interface (Noul; judge-free prediction)

- **Plan-tool decision.** Whether a `refactor` step can be held to "tests pass
  before and after". This is the withdrawn per-`change_type` contract, which
  failed because most refactors cannot satisfy it and a vocabulary check
  cannot tell which ones can.
- **Item.** The step's detail file (`## Changes` and `## Tests` sections).
- **Labels.** Judge-free, from
  `experiments/refactor-characterization-replay/replay.py`. **Positive:** the
  step's post-change tests collect and pass at the parent commit. The existing
  `results.json` holds 28 conclusive replays, only 3 of them positive. Before
  scoring, `replay.py` is re-run over the refactor steps landed since then to
  grow n.
- **No dev split.** The question is worded from the contract definition before
  any call and never tuned, because n is too small to hold out.
- **Reporting rule.** With fewer than 10 positives, T3 reports AUROC with its
  exact confidence interval as **descriptive only**, and its verdict is at most
  "consistent" or "inconsistent" with the claim.

### T4 (optional) — history written in the present tense (Noul; semantic lint)

- **Plan-tool decision.** The "Documentation is forward-looking" sweep, which
  is done by hand today.
- **Item.** One paragraph from a tracked doc or plan.
- **Labels.** Candidates are mined from paragraphs removed or rewritten by
  forward-looking and sweep commits (for example `0e45ad41`, `bbe28e8a`), at
  each commit's parent. Negatives are paragraphs in the same files that
  survived. The owner labels 150 of them, blind, with a 50 / 100 split.
- **Status.** T4 runs only if the owner opts into its labeling cost.

## Baselines

Every task is scored against the same set of baselines on the same items:

- **B-code:** the existing plan-tool heuristic (T1: the phrase matcher; T2: the
  `git blame` rule) plus the majority class.
- **B-haiku / B-sonnet:** `claude -p --output-format json` with `--model`
  `claude-haiku-4-5-20251001` or `claude-sonnet-5`. Each receives the identical
  state and question wording, rendered as a prompt that asks for
  `{"answer": …, "probability": …}`. Cost is read from the CLI's reported usage,
  never from a price table. Each model runs once over each test split, plus
  3 repeats on a 30-item subset for a stability comparison.
- **Jev:** `jev-1.13.0`, pinned. The `model` echoed in each response is
  recorded, and a mismatch invalidates the run.

## Integrity rules (pre-registration)

1. **Freeze before the test split.** The labels, the frozen question file
   (recorded by SHA-256), the combination weights, and the decision thresholds
   below are committed before any model call on a test split. Dev-split calls
   may tune wording; test-split calls may not.
2. **Blind labeling.** Labelers never see any model's output. Opus may act as a
   second rater, but only to estimate inter-rater agreement (Cohen's κ) as the
   labels' quality ceiling. Opus labels are never used as truth.
3. **Report everything.** Every task, arm, and metric is reported, including
   failures and inconclusive results.
4. **Paired comparisons.** All systems see the same items. Uncertainty comes
   from a paired bootstrap (10,000 resamples, seed recorded); McNemar's test
   compares argmax accuracy.

## Decision rule, per task (fixed before the test split)

A task's verdict is **supported** when all three conditions hold:

1. **Quality**, by either route:
   - **(a)** Strictly better than B-code: the primary endpoint's 95% CI
     excludes 0, and for T1 the false-`docs` rate is no higher than B-code's.
   - **(b)** Non-inferior to the better Claude baseline, within 0.03 AUROC or
     macro-F1, at ≥ 10x lower cost per decision.
2. **Stability:** P1b flip rate ≤ 2% on the task's question.
3. **Calibration**, required only where routing is proposed: ECE ≤ 0.10 and a
   Brier score no worse than the Claude baselines' verbalized probabilities.

Otherwise the verdict is **not supported**, or **inconclusive** when the CIs
cannot separate the systems.

The C7 routing claim is **supported** for a task when some confidence threshold
fixed on dev yields ≥ 95% precision at ≥ 40% coverage on test.

The final report is one table of claims C1–C10 against tasks, each cell marked
supported, not supported, inconclusive, or not tested.

## Deliberately not tested

Each exclusion is for lack of data, not for doctrine:

- **Model routing** (for example, choosing Opus or Sonnet per subcommand). No
  outcome labels exist for which model would have been right.
- **Lessons re-ranking.** This is a real match for the vendor's Search &
  Retrieval use case, but its value depends on `experiments/lessons-utility`
  H1 (whether lessons help at all), which is still open.
- **`remedy-proportionality`, `check-saturation`,
  `premise-conditioned-design`, `measurement-instrument-adequacy`.** Each has
  only 1–2 recorded instances (in `CLAUDE.md` prose) and no labeled corpus.
  This can be revisited once T2 shows whether a shape-level Noul works at all.
- **Text generation of any kind.** The vendor states the model does not
  generate text (`coding-agents`, jaggedness item 9).

## Data handling, cost, and execution

- **Content sent.** Only this repository's own plans, reports, and docs. No
  report derived from a client repository is sent. Before sending, a
  secret-pattern scan (API keys, tokens) runs over every item, and any hit is
  dropped. The vendor's zero-retention option is enterprise-only (`models`),
  so sent content falls under the vendor's standard retention policy.
- **Credential.** `TYPESAFE_API_KEY` is read from the environment at run time
  and never written to disk or logs.
- **Budget.**
  - **Jev:** roughly 1,500 items × ≤ 8 call variants × ~3k tokens ≈ 36M input
    tokens, which is about $1.50 at the published rate.
  - **Claude baselines:** the owner sets a spend cap before the first call
    (proposed: $25), and `run_claude.py` stops when the cumulative reported
    cost reaches it.
- **Serial calls.** Calls run serially. At the claimed ~150 ms per call, the
  Jev workload finishes in minutes, and serial execution avoids
  client-side concurrency (the Architecture rule in `CLAUDE.md`). The
  vendor's own server-side batching is measured in P1c.
- **Caching.** Raw responses are cached under `.tmp/typesafe-system-one/`
  (gitignored), keyed by the hash of (model, state, questions), so the analysis
  re-runs without new calls. Durable results — labels, the frozen question
  file, and computed metrics — are committed under this directory.
- **Long runs.** Each long run runs in the background and tees to
  `.tmp/typesafe-system-one.<verb>.log`.

## Artifacts

| File | Role |
|---|---|
| `build_corpus.py` | stdlib; reads reports and git; writes items JSONL with fixed seeds |
| `label.py` | exports blind labeling CSVs; imports and validates labels |
| `run_jev.py` | PEP 723 (`typesafe-sdk`); Part 1 probes and Part 2 scoring; caches responses |
| `run_claude.py` | `claude -p` baselines under the spend cap |
| `analyze.py` | metrics, bootstrap CIs, reliability and risk–coverage plots |
| `questions.frozen.json` | the frozen question set; its SHA-256 is recorded in `LESSONS.md` |
| `labels/` | committed ground truth |
| `LESSONS.md` | results log and the final claims table |
| `CLEANUP.md`, `cleanup.sh` | cleanup, per the sibling experiments' convention |

## Order of work

1. **Part 1.** Needs no labels; about an hour; under $1. Ends at gate G1.
2. **Labeling.** In parallel with Part 1: the T1 set, the T2 noise audit and
   residue sample, and T4 if chosen. About 250 items, or about 400 with T4.
3. **Re-run the T3 replay** to grow its n.
4. **Tuning on dev and freezing.** Tune question wording and T2 weights on dev
   splits, then commit the freeze.
5. **Scoring.** Score the test splits for Jev and the baselines.
6. **Report.** Write `LESSONS.md` and the claims table. For each task marked
   **supported**, file an opt-in `BACKLOG.md` entry carrying a full scope
   contract.
