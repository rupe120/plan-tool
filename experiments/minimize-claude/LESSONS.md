# Lessons learned — minimize-Claude experiment (create)

A living methodology log from the `create` experiment, written so the
**`detail` pass can repeat the process faster**. Pair with the seeds
`plan-seeds/minimize-claude-in-create.md` and
`plan-seeds/minimize-claude-in-detail.md`, and the analyzer
`scripts/analyze_run_log.py`.

## Methodology lessons (apply these to `detail`)

1. **Instrument the target metric BEFORE measuring.** The run log did not
   capture the thing we set out to measure: `create.py:5355` called
   `apply_finding(...)` without `run_logger=`, so the body-placeholder
   fills (Opp 1+2) emitted nothing. First action for `detail`: confirm
   its run log captures every authoring / quality-loop / apply call with
   the finding `source` + section, and patch the gaps before any run.

2. **`claude_call_end` is the authoritative cost record — not
   `phase_end`.** Iteration re-proposals/applies emit
   `claude_call_start/end` but are NOT all wrapped in a `phase_end`, so a
   phase-based analysis silently undercounts (we first saw `propose_steps
   n=1` when it actually ran twice). `scripts/analyze_run_log.py` already
   buckets from `claude_call_end`; reuse it as-is for `detail`.

3. **Establish the noise floor before attributing impact.** `create` is
   highly non-deterministic: the same seed varied run-to-run (e.g.
   `propose_steps` 152s vs 354s; one seed iterated, another with the same
   logic iterated 0 times). Run N≥2 of the *current* logic per input and
   measure variance FIRST; an optimization's claimed win only counts if
   it clears that variance band. (This is the A/B re-run in progress.)

4. **Measure quality, not just speed.** Quality inspection overturned a
   speed assumption: `## Deferred` looked like cheap boilerplate to
   default to a sentinel, but Claude actually produced substantive,
   plan-specific content (300–590 chars across 3 plans). Removing that
   Claude call would have been a quality regression. For `detail`:
   inspect the seven-section output of a sample before declaring any
   section deterministic-fillable.

5. **Let data re-rank priorities — the biggest prize was unexpected.** We
   started on the placeholder fill (~6% of wall-clock) but the dominant
   cost was per-iteration re-proposal of steps+references (~40%). Measure
   ALL call sites; don't trust the a-priori ranking in the seed.

## Mechanics / gotchas (save time next round)

6. **`create --from-existing` archives the seed on consumption.** It moves
   the seed to `plan-seeds/archive/` as `<name>.replaced.md` (raw, as
   consumed) and `<name>.distilled.replaced.md` (post-distill). To re-run
   the *same* input, feed the raw `.replaced.md`. Edits to a seed made
   after create consumed it do NOT affect the archived copy.

7. **Isolate experiment output.** Use `--output-dir <scratch>` +
   `PLAN_TOOL_PLANS_DIR=<scratch-manifest>` to keep re-runs out of the
   real plans dir and manifest. Run logs still land in
   `.plan-tool/runs/<slug>/` regardless, keyed by slug — prefix
   experiment slugs (e.g. `instr-…-a` / `-b`) so they're filterable.

8. **Run re-creations sequentially.** Concurrent `create` runs race the
   shared `.plan-tool/plans.json` manifest. Chain them; don't parallelize.

9. **Instrumentation must be behavior-preserving** to keep the A/B honest,
   and de-risked with the unit suite (`pytest -m "not integration"`)
   before relying on it. Our create instrumentation added only
   `phase_start/phase_end` extras (`source`, `finding_label`, `verdict`)
   around the existing apply call — no logic change. (A `mechanism` field
   was added then removed once Opp 1/2b were rejected — see below.)

10. **Editing source while a run is in flight:** safe for the *running*
    process (Python won't reload loaded modules), but the next fresh
    `uv run` picks up the edits. Sequence edits relative to when new
    processes launch.

## Variance results (2026-06-17, n=2 per seed: baseline vs instr-a)

Note: the intended 2-fresh-runs-per-seed (`-a`/`-b`) degraded to n=2
(baseline + one instrumented run) because feeding an archived seed via
`--from-existing` RE-archives it on success, so the `-b` replicate failed
with `existing plan path is not a file`. **Fix next time: copy each seed
to a stable scratch path and run every replicate from its own copy.**

| seed | total Δ% | propose_steps Δ% | re-proposal cost (base→instr) | apply fills |
| --- | --- | --- | --- | --- |
| merge | 7% | 12% | 188s → 224s (18%) | 1× body-completeness, 44s |
| escalate | 7% | 13% | 200s → 275s (31%) | 2× body-completeness, 64s |
| advisor | 10% | 10% | **0s → 304s** | 1× body-completeness, 35s |

Findings:

11. **The dominant variance is BIMODAL, not Gaussian — does the iteration
    loop fire at all?** Total wall-clock is fairly stable (7–10%) and most
    phases sit in a 5–30% band, BUT the `advisor` seed ran **0 iterations
    in baseline and 1 in instr-a** — a ±300s (~60%) swing that is a
    structural fork, not noise. **Consequence: at small N, a wall-clock
    A/B cannot detect an optimization through this fork.** Measure the
    *mechanism* directly (e.g. "re-proposal Claude calls eliminated for a
    fixed applied-finding set"), which is deterministic; reserve
    wall-clock comparison for N≥5 to average the fork out.

12. **The placeholder fill is the TRIGGER for the expensive re-proposal —
    they compound.** In all three instrumented runs, EVERY apply was a
    `body-completeness` placeholder fill (n=1–2, ~35–64s each) — there
    were no correctness/completeness applies. So the iteration loop ran
    *solely* to fill body placeholders, and each iteration then spent
    188–304s re-proposing steps+references. The cheap fill (~50s) drags
    the expensive re-proposal (~200–300s) behind it.
    - **Opp 3 (skip re-propose after a prose-only apply)** captures the
      ~200–300s AND preserves `## Deferred` quality (Claude still writes
      it; we just don't re-propose steps afterward). **The prize.**
    - **Opp 1 (deterministic placeholder fill)** could stop the iteration
      from firing at all (saving fill + re-proposal), but risks Deferred
      quality — so restrict it to genuinely source-less sections.

13. **Significance threshold for the optimization tests:** within-mode
    wall-clock noise ≈ **10%**; cross-mode (iteration fires vs not) ≈
    **60%**. Judge Opp 3 by re-proposal calls eliminated (deterministic),
    not by total-time delta at small N.

## Clean-room protocol (use verbatim for the `detail` pass)

To keep re-runs full, independent, and comparable — verified valid for the
`create` variance runs:

1. **Fresh unique slug per replicate** (e.g. `instr-<name>-a`, `-b`). A
   reused slug risks resume-from-checkpoint / "plan already exists" skips.
   Checkpoints are keyed by slug; a new slug guarantees a cold start.
2. **Copy each seed to a stable scratch path first**, and run every
   replicate from its own copy — never feed an archived seed directly.
   `create --from-existing` RE-archives the seed on success, so a second
   run from the same path fails `existing plan path is not a file`.
3. **Isolate output + manifest:** `--output-dir <scratch>` +
   `PLAN_TOOL_PLANS_DIR=<scratch-manifest>` so re-runs never touch real
   plans or the real manifest. Run logs still land in
   `.plan-tool/runs/<slug>/`, keyed by slug — filter on the prefix.
4. **Run sequentially** (manifest race) and **`--yes`** (unattended).
5. **Verify the run was full, not resumed:** the run log should show the
   complete phase sequence (distill → steps → references → body → …) and
   `checkpoint_discard` on clean completion, with NO resume/restore event.
6. **Always capture ≥2 replicates per input to get the noise floor BEFORE
   attributing any optimization impact.** Variance was decisive for create
   (it exposed the bimodal "does it iterate" fork; lessons 11/13). For
   `detail`/`completeness`, which MUTATE the plan in place (no fresh-slug
   trick), get replicates by: run → revert tracked mutations (run logs are
   gitignored, so they survive) → run again on the clean state with
   identical flags. Each run appends a timestamped JSONL under
   `.plan-tool/runs/<slug>/`, so replicates coexist and are diffable.

## Opp 3 prototype (landed 2026-06-17, opt-in, default OFF)

Gated behind `PLAN_TOOL_SKIP_REPROPOSE_PROSE_ONLY=1`. When every finding
applied in an iteration round is a prose/body-section source
(`_PROSE_ONLY_APPLY_SOURCES = {body-completeness, detail-body}`), the loop
skips the steps + references re-proposal (2 Claude calls) and converges on
the deterministic re-derive instead. Rationale: those re-proposals take
`title + description` as input, which `apply_finding` never edits — so the
re-proposal is byte-identical-input churn.

- Predicate extracted as `create._reproposal_is_skippable(applied_sources)`
  (unit-tested in `TestReproposalSkippable`). Default OFF keeps behavior
  byte-identical (638 unit tests green).
- **How to A/B (mechanism, not wall-clock — see lesson 11/13):** clean-room
  re-run the same seed twice, once with the env var set. Then
  `scripts/analyze_run_log.py` on each: the win is the eliminated
  `propose_steps` / `propose_references` re-proposal calls (a `phase_end`
  with `skip_reason=opp3_prose_only_apply` marks the skip). Expect ~2 calls
  / ~200–300s removed per prose-only iteration; total wall-clock will still
  be dominated by the bimodal "did it iterate" fork.

## Scoping the `detail` pass (per-step, NOT whole-plan)

`detail` authors a seven-section file per step and runs its quality loop
per step, so cost scales with step count. Do NOT detail every step of
every plan up front — that multiplies Claude spend without adding
methodological signal (the call *pattern* repeats per step).

- **Target a few representative steps**, not the whole plan: e.g. one
  `feature` step, one `refactor` step, and one likely to trip the purity /
  quality loop (a larger or mixed step). Use `detail <plan> --step N` to
  scope to a single step.
- Characterize the per-step call pattern (authoring + quality-loop applies
  + any re-author churn) on those few, find the deterministic-fillable vs
  judgment-required split, THEN generalize — only broaden to more steps if
  a step type behaves differently.
- Reuse the analyzer + clean-room protocol unchanged; the unit of
  measurement is now per-step rather than per-plan, so capture which step
  (id + change_type) each run targeted.

## Opp 3 A/B results (2026-06-17) — VALIDATED, strong KEEP

9 runs, clean-room protocol: 3 seeds × {1 control (skip OFF), 2 treatment
(skip ON)}. All rc=0.

| seed | calls OFF→ON | Claude wall-clock OFF→ON | re-proposal calls OFF→ON | skip fired |
| --- | --- | --- | --- | --- |
| merge | 6 → 4 | 475s → 256/262s (~-45%) | 2 → 0 | 2/2 |
| escalate | 6 → 4 | 619s → 387/202s (~-52%) | 2 → 0 | 2/2 |
| advisor | 7 → 4–5 | 698s → 284/399s (~-51%) | 2 → 0–1 | 2/2 |

- **Mechanism confirmed:** the skip fired in **6/6** treatment runs;
  re-proposal calls dropped 2→0 (one advisor run kept 1 — see below).
  ~2 Claude calls eliminated per run; **total Claude wall-clock roughly
  halved (~45–52%).**
- **Quality parity — no regression:** every run (both arms) ended with
  **0 `_(TODO)_` placeholders** and all **10 body sections present**;
  `## Deferred` and `## Acceptance criteria` were substantive in treatment
  runs (Deferred 377–637 ch vs control 185–569 ch). Skipping the
  re-proposal did NOT leave the plan incomplete.
- **Step-count delta is re-roll noise, not lost refinement.** Control
  plans had ±1 more steps in some cases. But propose_steps' input is
  `title + description`, unchanged by the prose apply — so control's
  re-proposal re-draws steps from the SAME input: a different random
  sample, not a better-informed one. That variance IS the waste Opp 3
  removes.
- **Conservative gate behaves correctly:** `ab-advisor-trt2` iterated
  twice — it skipped the prose-only round but still re-proposed the round
  that applied a non-prose finding (reprop 1, skip 1). The gate skips only
  prose-only rounds, exactly as designed.

**Verdict: Opp 3 is the validated primary win — keep it.** Next: promote
from the experimental env flag to a real `create` flag/default + a
loop-level regression test (the predicate is already unit-tested).

## Detail pass — audit + instrumentation (2026-06-17)

Phase-A audit findings:

- **No re-proposal churn → Opp 3 does NOT transfer.** `detail`'s loop is
  `apply_finding` → `collect_detail_quality_findings` (re-reads the file
  from disk and re-audits; does NOT re-author the body) → converge. The
  ~40% create prize has no analogue here; `detail`'s per-iteration cost is
  the re-audit + the applies, not authoring churn.
- **Same two blind spots create had** (lesson #1 again): `apply_finding`
  was called without `run_logger=` (`detail.py:~2297`), and the
  quality-audit (`collect_detail_quality_findings`) shelled to Claude with
  no `claude_call_start/end`. A baseline run would have been blind to both.

Instrumentation landed (observability-only, 3239 unit tests green):

- Wrapped the loop's `apply_finding` in an `apply_finding_dispatch` phase
  (`source` + `finding_label` + `verdict`) and passed `run_logger`.
- `collect_detail_quality_findings` now emits `claude_call_start` +
  `bind_shell_sink` under phase `detail_quality_audit`, wired from both the
  initial scan and the in-loop re-scan — so the analyzer can price every
  iteration's audit. (No `mechanism` field — that idea was rejected; see
  Opp 2b.)

### Detail baseline results (n=2 per step, 2026-06-17)

Phase breakdown (Claude seconds), rep1 / rep2:

| step | authoring | quality re-audits (n) | applies (n) | total |
| --- | --- | --- | --- | --- |
| merge s1 (feature) | 329 / 231 | 132(1) / 351(3) | 0(0) / 43(2) | 461 / 624 |
| advisor s2 (refactor) | 315 / 203 | **859(4) / 811(4)** | 258(8) / 168(5) | 1432 / 1181 |
| escalate s3 (mixed) | 299 / 183 | **672(4) / 567(4)** | 117(4) / 98(4) | 1088 / 848 |

- **The per-iteration Claude quality re-audit dominates** on steps that
  iterate (≈60–70% of Claude time). Authoring is a fixed one call (~200–
  330s). Cost scales with iteration count.
- **Variance:** total wall-clock ±19–30% (noisier than create's ~10%).
  Audit *count* is STABLE at 4 for the saturating steps (advisor/escalate,
  both reps) but swings for the fast-converging feature step (1↔3). So,
  like create, judge any optimization by **mechanism (audit calls
  eliminated)**, not wall-clock — and a saturating step gives a
  deterministic 3-of-4 elimination signal.

### Detail "audit-once" optimization — PROTOTYPED, A/B'd, DISCARDED

Hypothesis: mirror `completeness` (audit once + deterministic re-derive),
skipping detail's per-iteration Claude re-audit. Prototyped behind
`PLAN_TOOL_DETAIL_AUDIT_ONCE=1`, A/B'd vs the n=2 OFF baseline:

| step | audits OFF→ON | total Claude OFF→ON | applies OFF→ON |
| --- | --- | --- | --- |
| advisor s2 | 4/4 → **1** | 1432/1181 → **578** (~-55%) | 8/5 → **2** |
| escalate s3 | 4/4 → **1** | 1088/848 → **319** (~-67%) | 4/4 → **1** |
| merge s1 | 1/3 → 1 | 461/624 → 399 | 0/2 → 3 |

**Mechanism win was real (~half the Claude cost) — but it's a QUALITY
REGRESSION, so discarded.** The apply finding-labels showed the OFF
re-audits surfaced 5–8 DISTINCT, genuine issues (mis-cited tests,
import-contract tensions, DETAIL_FLOW.md inaccuracies, cross-plan gaps —
not rephrasings). Audit-once applied only 1–2 (the single initial scan)
then "converged" on an incompletely-reviewed file, leaving 3–6 real issues
unfixed.

**Key lesson — the inverse of create's Opp 3.** Create's re-proposal
re-rolled *identical* input (title+description) → pure churn → free to
skip. Detail's re-audit re-reads the *edited* file → genuinely finds new
issues each round → **load-bearing, not churn.** The "same loop shape"
(audit→apply→re-derive) does NOT imply the same optimization; what the
re-derive consumes (unchanged vs edited input) decides whether it's waste.

### Sampled initial scan — PROTOTYPED, A/B'd, DISCARDED

Follow-up idea: detail's initial scan is a SINGLE audit; completeness
SAMPLES its one-time audit (N unioned). Hypothesis: a sampled initial scan
front-loads findings → fewer re-audit rounds, at no quality risk (re-audit
loop left intact). Prototyped behind `PLAN_TOOL_DETAIL_INITIAL_SAMPLES=3`,
A/B'd vs the N=1 baseline:

| step | audits N=1 → N=3 | total Claude N=1 → N=3 |
| --- | --- | --- |
| merge s1 | 1–3 → 4 | 461–624 → 823 |
| advisor s2 | 4 → **6** | 1181–1432 → **1777** |
| escalate s3 | 4 → 4 | 848–1088 → 1031 (neutral) |

**LOSS — discarded.** Front-loading did NOT collapse the re-audits:
advisor still ran ~3 re-audits ON TOP of the 3 initial samples (6 total vs
4). This RESOLVES the open (a)/(b) question: detail's re-audit findings are
predominantly **edit-introduced** (only exist after the applies edit the
file), NOT pre-existing-missed — so initial sampling can't pre-empt them.

**Conditional front-loading is therefore moot.** It only helps if some
steps benefit; front-loading helped NONE (iterating steps got worse), so a
condition gating "sample more where it helps" resolves to "never."

**Quality angle also tested → no win either.** Separately checked whether
N=3 yields a BETTER final file (ignoring cost): ran advisor s2 at N=1 vs
N=3 and compared the converged detail files. They're COMPARABLE — both
have all 9 sections, comparable section sizes, and substantively
equivalent, equally-grounded Implementation prose (N1 marginally fuller in
Implementation/Acceptance, N3 in a few others = run-to-run noise). Both
arms run the full re-audit loop, so both converge to the same quality;
N=3 just front-loads discovery and pays ~2.2× wall-clock to reach it.
**Sampled-initial fully discarded: no cost win AND no quality win.**

**Combined detail verdict:** both levers fail for the same root cause —
detail's per-round re-audit is load-bearing and irreducible because each
round's edits create genuinely new issues. Detail's loop is already
correctly shaped; no loop-level Claude-reduction win exists.

## Completeness pass — audit (prep, 2026-06-17)

**Not a separate subprocess — a SHARED tail.** `detail` and `split` run
the conceptual completeness audit by calling `app.cmd_completeness(...)`
directly (`authoring.py:1353`, the `_run_completeness_tail`), i.e. the
exact same code as the standalone `completeness` command. Don't confuse it
with detail's OWN per-step `detail-quality` loop
(`collect_detail_quality_findings`) — that's file-quality, a different
audit. Consequences:

- **One instrumentation fix in `completeness_cmd.py`** covers the
  standalone command + detail's tail + split's tail at once.
- **No separate experimental track / dual-baseline campaign** — it's
  per-plan, deterministic re-derive (no churn), shared. Measure it ONCE
  (standalone, or as a full detail run with the tail on). The detail
  baseline deliberately used `--no-completeness` to isolate detail-quality
  from this shared tail.

Phase-A audit findings:

- **Already the leanest loop — no Opp-3 analogue.** The conceptual audit
  (`check_plan_audit`, ≤`--audit-samples` = 3) runs ONCE up-front
  (`completeness_cmd.py:940`), never per-iteration (re-phrasing a
  subjective audit would defeat convergence detection). Per-iteration
  re-derivation is deterministic-only — no Claude (`:962`). Nothing to
  skip.
- **Same apply-logging gap (3rd command):** the `--iterate` loop calls
  `apply_finding` without `run_logger=` and without the
  `apply_finding_dispatch` wrap (`completeness_cmd.py:1182`) — applies are
  visible (internal `claude_call_end`) but unattributed.
- **Up-front audit is fully unlogged** (`audit_plan_until_stable` /
  `_sample_conceptual_audit`) — no `claude_call_start/end`, only stderr
  heartbeats. That's completeness's single biggest Claude cost (the
  samples) and the analyzer can't see it.
- The separate `completeness-apply` replay verb IS already instrumented
  (routes through `review_actions.py`'s wrapped apply); only the
  `--iterate` audit loop needs wrapping.
- Likely conclusion: no reduction win in the loop; the only tunable cost
  is `--audit-samples` (a stability-vs-cost lever, not waste). Instrument
  to confirm, don't pre-optimize.

Instrumentation landed (3239 unit tests green):

- Wrapped the `--iterate` loop's `apply_finding` in `apply_finding_dispatch`
  (source/finding_label/verdict) + passed a logger.
- `audit_plan_until_stable` now binds the shell sink per sample under phase
  `plan_audit`, so the up-front audit's samples emit `claude_call_end` and
  the analyzer can finally price them.
- The audit loop had no logger at all, so the caller now opens a
  `command="completeness"` run log and brackets the loop with `run_end`.

**Gotcha (reusable): instrumenting a SHARED command that's also invoked as
a tail double-logs.** `detail`/`split` call `cmd_completeness` as a tail; a
new run log there created a 2nd JSONL under the same slug and broke the
"exactly one JSONL per run" contract. Fix: the tail passes
`_suppress_run_log=True`; nested invocations skip opening their own log
(the parent owns it) and run with `run_logger=None`. Watch for this whenever
instrumenting a command that another command invokes in-process.

## Merge-calls survey (2026-06-17) — no viable candidates

Surveyed whether distinct Claude round-trips could be BATCHED into one
(orthogonal to the skip-redundant lever). None viable:

- **create distill→steps→references→body**: a true pipeline — each call
  consumes the prior's output; not independent, can't batch.
- **apply_finding auto-fix follow-up**: conditional (fires only on
  regressions) and the regressions are detected by EXTERNAL deterministic
  checks post-edit, not by Claude — a self-verify merge would be weaker.
- **detail authoring + initial quality scan**: intentionally split (purity
  self-check was moved OUT of authoring); the audit-once A/B already proved
  folding review into authoring regresses quality.
- **detail lessons extraction**: different prompt + output (lessons store
  vs findings), post-loop; merging would destabilize it.
- **completeness correctness + completeness**: ALREADY one call (two
  finding layers tagged by source).

Takeaway: the Claude calls are already well-factored (focused, dependent
stages). The skip-redundant lever found one real win (create Opp 3); the
merge lever finds none. Don't re-investigate without a new angle.

## Still open

- Confirm whether `## Out of scope` ever reaches a placeholder in practice
  (seed-derived in all samples so far) and whether the Testing per-step
  block is fully deterministic end-to-end.
- Run the Opp 3 A/B (clean-room protocol) to confirm calls-eliminated and
  check convergence/quality parity vs the baseline plans.
