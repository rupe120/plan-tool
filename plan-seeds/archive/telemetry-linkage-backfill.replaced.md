> **Replaced**: this file has been superseded by `docs/implementation-plans/2-telemetry-linkage-backfill.md`.
> Preserved here for history; do not edit.

# Plan seed: decision→outcome join-key backfill + new decision sites (BACKLOG #72, phase 2)

The **backfill** slice of #72 (decision/outcome telemetry). Phase 1 shipped the
schema — the base `DecisionEvent` now *carries* the join keys `decision_id` /
`run_id` / `plan_fingerprint` / `code_fingerprint` / `anchor`
(`docs/implementation-plans/2-telemetry-linkage-schema.md`) — but almost every
producer still leaves them empty, and several high-value heuristic decisions have
no recorder at all. Phase 2 **fills the producers**: it makes new events actually
carry the keys a phase-3 resolver will join on. It ships **no new consumer** — the
read-only `plan-tool telemetry` resolver/analysis surface and outcome-verdict
derivation are still phase 3.

> **Source.** Distilled from **BACKLOG #72** ("Decision/outcome telemetry →
> understand heuristics across scenarios over time, recommend tuning"), the
> backfill/new-sites work its status block names as "Remaining (phase 2–3):
> … backfilling the join keys across the decision sites the schema slice did not
> wire (create-side granularity, `--refresh`/reconcile drift-gate, `apply_finding`
> verdicts, escalate-to-split)", via the schema spike at
> **`.tmp/72-telemetry-linkage.spike.md`** (§5, §8 "Backfill the good keys"). The
> resulting plan **must update BACKLOG #72** when it ships (see the docs/status
> step in Scope + the final AC): mark the phase-2 backfill done and leave phase 3
> (resolver + `plan-tool telemetry` surface + outcome-verdict derivation) as the
> remaining scope. This backlog reconciliation is a plan requirement, not an
> operator afterthought.

## Why this slice

The spike's empirical finding (347 real events): "the recorders that carry the
good join keys (fingerprints, outcome actions) are exactly the ones that haven't
fired, and 81% of events are ownerless prompt-budget checks. … no amount of
post-hoc join logic recovers linkage the events don't carry." Phase 1 gave the
event a *place* to carry `plan_fingerprint`/`code_fingerprint`/`anchor`; every
authoring-time recorder call site verified at HEAD still passes **nothing** for
them (relies on the `""`/`{}` defaults), so new events remain unjoinable on the
renumber-proof fingerprint anchor. And three of the highest-leverage heuristic
decisions the backlog names — the reconcile/`--refresh` drift-gate, per-finding
`apply_finding` verdicts, and escalate-to-split outcomes — emit **no decision
event at all**. Until the producers carry the keys, phase 3's resolver has nothing
to correlate and its smoke test (spike §7) cannot run.

## What phase 2 delivers

Two coordinated parts, both purely additive and best-effort (telemetry is
observational — it must never change a command's control flow, exit code, or
output):

**Part A — backfill the join keys onto the existing recorders' call sites.** The
recorders already *accept* `plan_fingerprint`/`code_fingerprint` (defaulted);
their callers just don't pass them. Thread the caller-computed digests
(`review_persistence.compute_plan_fingerprint`,
`fingerprint.compute_code_fingerprint`) into each site that has a plan in hand:

- `plan_tool/create.py` — `record_create_granularity_assessment` (~3504) and the
  `record_create_step_outcome` wrapper `_record_step_outcome` (~3539).
- `plan_tool/review.py` — `record_code_reveals_split` (~3457, reconcile lane).
- `plan_tool/cli/completeness_phases.py` — `record_granularity` (~664) and
  `record_audit_coverage` (~816). (Both modules already import
  `compute_plan_fingerprint`/`compute_code_fingerprint`.)
- `plan_tool/cli/convergence_cmd.py` — `record_convergence` (~119).

`record_prompt_budget` stays fingerprint-less by design — it's the ownerless
pre-send backstop with no plan context (spike §3). `run_id` needs no backfill
here: it auto-flows from the `telemetry`-owned `_active_run_id` ContextVar, which
phase 1 binds at the two `run` entrypoints only; these are authoring-time commands
(`create`/`completeness`/`convergence`), not runs, so `run_id=""` is the correct
value (a decision made outside a run has no run to join to). Carry `anchor` only
where a decision is about one specific finding — none of the Part-A sites are
(they're plan-wide/step-wide), so Part A adds fingerprints, not anchors.

**Part B — add recorders + call sites for the three un-wired decision families.**
New per-kind convenience recorders in `telemetry.py` (each a thin wrapper over
`record_decision`, taking primitives so the module stays a stdlib-only leaf), each
with a new `kind`/`decision` literal exported as a module constant (the contract
downstream aggregation keys on), plus one call site each:

1. **reconcile / `--refresh` drift-gate** (`plan_tool/refresh.py:refresh_plan`).
   Record the gate verdict per refresh: `no-baseline` (first stamp) /
   `no-drift` (fast no-op) / `drifted` (reconcile ran), the drifted-file count,
   and the findings count. `refresh_plan` already computes
   `current_code_fp = compute_code_fingerprint(...)` and imports
   `compute_plan_fingerprint`, so both fingerprints are in hand — this is the
   decision whose whole point is code-vs-plan drift, so it carries
   `code_fingerprint`.
2. **`apply_finding` verdicts** (`plan_tool/launcher.py`, where
   `parse_apply_verdict`'s result is consumed). Record the per-finding verdict:
   `APPLIED` / `NOT-APPLICABLE` / `BLOCKED` / `BLOCKED-STRUCTURAL` (the tokens
   `parse_apply_verdict` already yields), with the finding `anchor` slug + its
   `step_id` (folded into `decision_id` so per-step verdicts sharing a
   second-precision `ts` don't collide) + `plan_fingerprint`.
3. **escalate-to-split outcomes** (`plan_tool/launcher.py:escalate_to_split`, or
   its three callers on the frozen `EscalateResult`). Record
   `EscalateResult.outcome` — `applied` / `recommended` / `unsafe` /
   `proposal-unusable` / `step-missing` (only `applied` mutated) — with the
   target `step_id` + `plan_fingerprint`.

## Resolved design decisions (ground the build on these)

1. **`telemetry.py` stays a stdlib-only leaf.** The new Part-B recorders take
   primitives (verdict strings, ids, counts, and *already-computed* fingerprint
   strings/dicts) exactly as the existing wrappers do. Callers import and run
   `compute_plan_fingerprint`/`compute_code_fingerprint`; the leaf never imports
   `review_persistence`/`fingerprint`. The stdlib-only import test stays green.
2. **Best-effort, control-flow-neutral, everywhere.** `record_decision` already
   swallows all errors; each new call site additionally must not perturb the host
   flow — wrap the fingerprint-compute + record in a local `try/except` that
   returns/continues on failure (mirror the existing sites, e.g. create.py's
   `_record_*` helpers), so a fingerprint error never fails an apply/refresh/
   escalate. No new non-zero exit path; no new stdout the operator sees.
3. **`plan_fingerprint` on every backfilled/new site; `code_fingerprint` only
   where it earns its bytes.** `plan_fingerprint` is a short digest and the
   renumber-proof anchor — carry it everywhere a plan is in hand. The full
   `code_fingerprint` path→hash map is large (phase 1's `_MAX_LINE_BYTES` lesson:
   a big map single-homed still fits, but dozens of per-finding lines each
   carrying a ~45 KB map is wasteful volume). So carry `code_fingerprint` where
   the decision is *about* code state — the **drift-gate** (its whole purpose) and
   the **Part-A recorders that already have it cheaply** — but on the per-finding
   `apply_finding` verdict site prefer `plan_fingerprint` only (the verdict joins
   on plan-state + anchor, not the code map). Make this per-site choice explicit
   in the plan and note the line-volume rationale.
4. **Hoist fingerprint computation above per-item loops.** `apply_finding`
   verdicts fire once per finding and escalate can fire per structural finding;
   `compute_plan_fingerprint` reads the plan file and `compute_code_fingerprint`
   hashes the footprint. Compute the plan-state fingerprint **once** per
   apply/reconcile pass and reuse it across the per-finding records — do not
   recompute inside the loop. Flag the hot sites in the plan.

## Seams to reuse / verify at HEAD during detail

- `plan_tool/telemetry.py` — `record_decision`, the existing per-kind wrappers
  (the pattern the 3 new recorders copy), the `kind`/`decision` constant block,
  `TELEMETRY_SCHEMA_VERSION` (**no bump** — phase 2 adds no base field; it fills
  existing ones and adds new `kind` families, which the tolerant reader already
  handles). Confirm leaf purity: `grep -E '^(from|import) plan_tool' plan_tool/telemetry.py` stays empty.
- `plan_tool/review_persistence.py:compute_plan_fingerprint` /
  `plan_tool/fingerprint.py:compute_code_fingerprint` — the caller-side digest
  producers (telemetry never imports them).
- `plan_tool/refresh.py:refresh_plan` + `RefreshResult` — the drift-gate verdict
  source (already holds both fingerprints + drifted-file list).
- `plan_tool/launcher.py:parse_apply_verdict` (the verdict tokens) and
  `escalate_to_split` + the frozen `EscalateResult` (`outcome` ∈ applied /
  recommended / unsafe / proposal-unusable / step-missing) — the two Part-B
  launcher sites.
- `plan_tool/review.py:Recommendation.anchor` / `.step_id` — the finding-scoped
  join keys the apply-verdict recorder carries.
- `DATA_CONTRACT.md` + `tests/test_data_contract.py` (drift guard) — document the
  three new `kind` families' context shapes and note that the previously-empty
  base fields are now populated at the backfilled sites.

## Scope of work (indicative — let `create` decompose)

1. **Part A backfill** — thread `plan_fingerprint`(+`code_fingerprint` where
   already in hand) into the 6 existing call sites (create ×2, review, completeness
   ×2, convergence); each wrapped best-effort. Tests assert the fingerprints now
   land on recorded events at those sites.
2. **Part B recorder: drift-gate** — new `record_*` wrapper + `kind`/`decision`
   constants in `telemetry.py`; call it from `refresh_plan` with verdict +
   fingerprints + drifted-file/findings counts. Tests: each of no-baseline /
   no-drift / drifted records the right verdict + keys.
3. **Part B recorder: apply-verdict** — new wrapper + constants; call from the
   `apply_finding` verdict-consumption site with verdict + anchor + step_id +
   plan_fingerprint (hoisted). Tests over the four verdict tokens.
4. **Part B recorder: escalate-to-split** — new wrapper + constants; call on
   `EscalateResult` with outcome + step_id + plan_fingerprint. Tests over the five
   outcomes.
5. **DATA_CONTRACT.md** — document the three new `kind` families + note the newly
   populated base fields; drift guard green.
6. **Docs/status step** — update **BACKLOG #72**: mark phase-2 backfill + new
   sites shipped; leave phase 3 (resolver + `plan-tool telemetry` + outcome-verdict
   derivation) as remaining; keep the spike reference.

## Non-goals / out of scope (these are phase 3)

- **The resolver / `plan-tool telemetry` analysis-and-recommend surface** — no
  consumer of the keys ships here; nothing *reads* the backfilled fingerprints.
- **Deriving outcome verdicts** (`acted-on` / `no-op` / `reverted` / `still-open`)
  — phase 3 correlates decision→outcome; phase 2 only makes the keys exist.
- **Backfilling historical events** — the existing events stay as-is; only new
  events carry the enriched producers. No migration of old data.
- **A `TELEMETRY_SCHEMA_VERSION` bump** — phase 2 adds no base field; the tolerant
  reader already accepts new `kind` values. Do not bump.
- **Binding `run_id` at non-run commands** — `run_id` means "the run this happened
  in"; create/detail/completeness/convergence are not runs. Leaving `run_id=""`
  there is correct, not a gap.
- **Changing `telemetry.py`'s leaf status** — it stays stdlib-only.

## Risks

- **Leaf-purity regression** — the seductive wrong move is importing a fingerprint
  producer into `telemetry.py`. Guard: fingerprints are caller-supplied; keep the
  stdlib-only import test green.
- **Control-flow / exit-code perturbation** — a recorder or fingerprint-compute
  throwing at the apply/refresh/escalate site must not fail that operation. Guard:
  best-effort try/except at every new site + the existing swallow in
  `record_decision`; a test that a raising `compute_*`/record leaves the host
  command's rc and output unchanged.
- **Line-volume / cost at hot sites** — per-finding apply verdicts × a big
  `code_fingerprint` map would bloat the log and re-hash the footprint each
  finding. Guard: `plan_fingerprint`-only on the per-finding site + hoist the
  compute above the loop (decisions 3–4).
- **Silent schema drift** — DATA_CONTRACT + drift guard must move with the new
  `kind` families' context shapes.
- **`decision_id` collision on per-step verdicts** — many `apply_finding` verdicts
  can share a second-precision `ts`; fold `step_id` into the hash (as
  `create-step-outcome` already does) so distinct per-step verdicts stay
  distinguishable.

## Acceptance criteria (plan-level)

- A newly recorded event at each of the six backfilled call sites (create ×2,
  code-reveals-split, granularity[completeness], audit-coverage, convergence)
  carries a non-empty `plan_fingerprint` (and `code_fingerprint` where the site
  already had it); `record_prompt_budget` stays fingerprint-less.
- Three new decision families record: a drift-gate verdict
  (`no-baseline`/`no-drift`/`drifted`) with both fingerprints + counts; a
  per-finding apply verdict (`APPLIED`/`NOT-APPLICABLE`/`BLOCKED`/
  `BLOCKED-STRUCTURAL`) with anchor + step_id + `plan_fingerprint`; and an
  escalate-to-split outcome (applied/recommended/unsafe/proposal-unusable/
  step-missing) with step_id + `plan_fingerprint`.
- Every new/changed call site is best-effort: a forced failure in
  `compute_*`/`record_*` leaves the host command's exit code and stdout unchanged
  (test-proven for at least the apply and refresh sites).
- `telemetry.py` imports nothing first-party (leaf test green); no
  `TELEMETRY_SCHEMA_VERSION` bump; per-finding apply site carries no full
  `code_fingerprint` map; fingerprint compute is hoisted above per-finding loops.
- `DATA_CONTRACT.md` documents the three new `kind` families with the drift guard
  green; the change ships **no** resolver/analysis/read surface.
- **BACKLOG #72 is updated** in the plan's final step: phase-2 backfill + new sites
  marked shipped, phase 3 (resolver + verdict derivation) left as remaining scope,
  spike reference retained.
