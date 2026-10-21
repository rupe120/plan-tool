> **Replaced**: this file has been superseded by `docs/implementation-plans/2-escalate-structural-findings-to-split.md`.
> Preserved here for history; do not edit.

# Plan seed: escalate structural findings to the split engine (re-decomposed)

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/escalate-structural-findings-to-split-redecomposed.md --iterate
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Why this seed exists.** The predecessor plan
> (`docs/implementation-plans/2-escalate-structural-findings-to-split.md`) would
> not converge under the completeness audit: eight audit/apply cycles kept
> surfacing fresh HIGH/MEDIUM correctness findings, all clustered on one
> over-packed step that wired a *structure-mutating* split through the
> *prose-mutating* convergence loops. The fix is not more prose patches — it is a
> different **decomposition**. This seed re-states the same feature with the
> step breakdown that confines the hard part. Read `## Step decomposition` first;
> it is the whole point of re-seeding.

---

## Overview

Build a bridge that routes an already-classified **structural finding** — one
whose only correct fix is to split a step into two — to the **already-existing
split engine**, under the same safety gates `detail --split` Phase B uses today.
This is routing and plumbing: **no new split algorithm**. The split engine
(`create._propose_step_split` / `create._apply_step_split`), the safety gate
(`detail._split_is_safe`), the operator confirm (`detail._confirm_split`), and
downstream-detail migration (`detail._migrate_downstream_details_after_split`)
are reused verbatim — they are already wired to this exact trigger in
`detail --split` Phase B, just nowhere else.

Two paired invariants govern the bridge:

1. **Always validate the more-correct plan.** For a recognized structural
   finding with a concrete target step, the bridge always detects, proposes, and
   (on any non-applying path with a usable proposal) records a split
   *recommendation* — never silently skipped. Recommendation emission is
   unconditional; the only no-recommendation paths are the cases that fall
   outside "recognized structural finding with a concrete target."
2. **Never mutate structure unattended.** An in-place split happens only
   interactively, behind an explicit opt-in flag, with a genuine operator
   confirm. Every unattended path (CI / `--yes` / `yes_to_all` / non-TTY)
   recommends only. `--yes`/`yes_to_all` is an *unattended* path — it must not
   satisfy the interactive-confirm gate.

## Problem statement

A finding whose only correct fix is "split this step into two" is recognized but
dead-ended. The `detail` purity self-check tags a step that mixes refactor +
feature as `detail-purity`, excludes it from `APPLY_ELIGIBLE_SOURCES`, and the
convergence loop skips it. Separately, when Claude determines mid-apply that the
only correct fix is a split, `apply_finding` returns a bare `BLOCKED` and the
caller reverts and reports. Either way `apply_finding`/convergence cannot finish
what they start.

## The two triggers (they are not symmetric — keep them in separate steps)

1. **Pre-classified `detail-purity` (trigger 1).** Lives in `detail`'s Phase B,
   **outside** the per-step convergence apply loop. The split runs after the
   `for step in target_steps` loop closes, so it never renumbers ids out from
   under an in-flight iteration. This trigger is clean and self-contained.
   `detail`'s self-check is the *only* producer of `detail-purity`.
2. **Discovered mid-apply `BLOCKED-STRUCTURAL` (trigger 2).** A new verdict
   bucket on `apply_finding`, inspected **inside** the convergence apply loop.
   When Claude mid-apply decides the only correct fix is a split, it emits
   `## Verdict: BLOCKED-STRUCTURAL` instead of a bare `BLOCKED`. This is the hard
   trigger: applying a split renumbers step ids in the middle of a loop that
   iterates *by* step id, which breaks every assumption the loop makes (stale
   captured ids, re-collection re-deriving the same finding, the per-step
   summary having already emitted, partial prose edits needing revert-first).

The predecessor plan's recurring findings were *all* symptoms of trigger 2 being
forced through the loops, stated twice (create's outer `while`, detail's nested
`for step` → `for rec`) with different mechanics. Separating the triggers, and
isolating the loop-renumbering contract into its own step, is the core of this
re-decomposition.

## Open question to settle FIRST — is create-side trigger 2 even reachable?

`create` dispatches to `apply_finding` only prose-fill sources
(`APPLY_ELIGIBLE_SOURCES = {body-completeness, detail-body, plan-correctness,
reconcile, …}` in `review.py`). For create's trigger 2 to ever fire, Claude
would have to be mid-apply on a "fill in this prose" finding and decide the only
correct fix is a *step split*. The predecessor plan asserted this is create's
"live structural trigger" but never named a concrete scenario where it happens.

**Resolve this before decomposing the create side.** If no concrete scenario
exists, the entire create-side trigger-2 wiring is forward-only dead code — and
roughly half the predecessor plan's complexity and audit findings lived there.
Default: **defer create-side trigger-2** to `## Deferred` as forward-only wiring
unless a real scenario is named. `create`'s `detail-purity` route is already
inert (create never emits `detail-purity`), so with trigger 2 deferred the
create side carries no live structural trigger and needs no in-loop split
handling at all.

## Step decomposition (the reason for this seed)

Propose **small, single-concern steps**. Each step is one `change_type` and one
coherent surface. Suggested shape:

- **Refactor step — single-source the structural predicate.** Add
  `review.is_structural(rec)` (seeded with `detail-purity`) and route the
  existing `triage_reason` guard through it. Pure refactor, behavior-preserving,
  no output change. Keep `detail-purity` excluded from `APPLY_ELIGIBLE_SOURCES`.
- **Feature step — render structural recommendations in the triage summary.**
  The new `structural-split` `triage_reason` branch (points the operator at
  `plan-tool split`, not `plan-tool detail`) and `emit_triage_summary` rendering
  of `rec.body`/`rec.suggested_action`. This is the new *output* behavior the
  predecessor plan illegally bundled into the refactor step (the audit BLOCKED it
  for exactly this refactor+feature impurity — do not repeat it).
- **Feature step — `BLOCKED-STRUCTURAL` verdict bucket.** Extend
  `parse_apply_verdict` / `ApplyFindingResult`, and teach the shared
  `apply-finding` prompt to emit `## Verdict: BLOCKED-STRUCTURAL`.
- **Feature step — the `escalate_to_split` bridge seam itself.** Safe-gate →
  single-proposal recover (titles **and** rationale from one `invoker` call —
  never a second proposal) → interactive-opt-in apply vs. unattended recommend.
  Enumerate **all** outcomes including the `_apply_step_split` `CreateError`
  failure path (catch, mutate nothing, recommend) and `proposal-unusable` /
  `step-missing` (`recommendation=None`). Reuse the Phase-B lazy `create` imports.
- **Refactor step — re-point `detail --split` Phase B at the bridge.**
  Behavior-preserving; existing `detail --split` tests stay green; add a
  delegation test. This is trigger 1, the clean path.
- **Feature step — trigger 1 unattended recommendation surface in `detail`.**
  Drop the Phase-B `allow_split and isatty()` warning-only guard and add the
  **post-Phase-B emission surface** (Phase B runs after the per-step loop, so the
  in-loop `emit_detail_findings_summary` calls cannot carry its recommendation).
- **Feature step — the loop-renumbering contract (trigger 2 in `detail`).**
  Isolate everything that makes an in-loop split safe as its own step: break out
  of the inner `for rec in open_apply`, re-parse, re-collect `target_steps` from
  the renumbered plan, break the enclosing `for step in target_steps`, revert
  partial prose edits via `_restore_text_files` before escalating, and a per-run
  seen-set so a recommend-only trigger-2 finding is not re-dispatched (and
  re-proposed) every unattended iteration. This contract is what the predecessor
  plan scattered across five plan-body sentences — that scattering *was* the bug.
- **Feature step — handle `BLOCKED-STRUCTURAL` in `cli/review_actions.py`.** The
  apply-walk verdict branch (escalate when interactive + opt-in, else surface
  recommendation), treating `yes_to_all` as unattended (recommend-only).

Create-side trigger 2 gets a step **only if** the open question above names a
real scenario; otherwise it is Deferred, not a step.

## Architecture notes the bridge must honor

- **Single proposal, never two.** `_propose_step_split` does one internal
  `invoker(prompt)` call and returns only `Optional[list[Step]]` (titles);
  rationale is captured into a discarded local. `escalate_to_split` must recover
  titles **and** rationale from *one* response — either run the proposal itself
  and parse via `_parse_steps_json(..., rationales_out=...)`, or extend
  `_propose_step_split` to surface its `rationales_out`/raw. Never a second
  `invoker` call (a divergent proposal could describe a different split than the
  titles already chosen).
- **Safe-gate always first.** Re-parse the plan and run
  `_split_is_safe(plan, step_id)`; if a downstream step has run/started, do not
  split — recommend a re-plan instead.
- **Apply-failure degrades, never crashes.** Mirror Phase B's
  `try/except CreateError` log-and-continue: catch a mid-apply `CreateError`,
  mutate nothing, surface a re-plan recommendation.
- **Design the seam to be caller-agnostic (forward-design for BACKLOG #57).**
  `escalate_to_split` ships wired to three callers (create loop, detail loop,
  review walk), but a fourth — the completeness *authoring* audit — is the
  planned successor (BACKLOG #57: a decomposition convergence loop, with this
  bridge as its *localized executor*). Keep the seam's signature free of
  create/detail-specific coupling: take `plan_path` / `step_id` / `repo_root` /
  `invoker` / the opt-in + TTY flags as plain parameters, return a structured
  `EscalateResult` the caller interprets, and do **not** reach into create's or
  detail's loop state. This costs nothing now and lets #57 reuse the executor
  without a refactor. Do **not** build the authoring-audit wiring here — that is
  #57's scope (see Out of scope / Deferred); only avoid foreclosing it.

## Out of scope

- New split *algorithm* or any change to renumbering / dependency rewiring —
  reuse `_apply_step_split` as-is.
- Auto-splitting in unattended mode.
- Restructuring beyond a single-step split (merge steps, N-way re-plan).
- **Wiring the bridge into the completeness *authoring* audit / `completeness-apply`
  walk.** This bridge serves the create/detail content-generation loops and the
  apply/review execution walk. Letting the authoring audit escalate a
  mis-decomposed plan to a re-plan (rather than only patching prose) is the
  generalized follow-up — see BACKLOG.

## Risks

- **Unattended structural mutation.** Severity: high. Mitigation: callers gate on
  TTY + the opt-in flag and treat `--yes`/`yes_to_all` as unattended.
- **Splitting a step whose downstream work already started.** Mitigation:
  `_split_is_safe` before any split; recommend re-plan on failure.
- **Invoker seam not neutralized in tests.** Mitigation: override the invoker
  seams per `TESTING.md`; the autouse gate raises on a real `claude` spawn.
- **Unattended propose cost.** Dropping the Phase-B `isatty()` guard means one
  `_propose_step_split` Claude call per flagged mixed step even on the default
  non-`--split` path; the seen-set bounds the trigger-2 path to one propose per
  finding per run. Severity: low; accepted as the cost of invariant (1).

## Acceptance criteria

- `review.is_structural(rec)` is the single source for the `detail-purity` guard;
  the refactor step changes no output, the feature step adds the
  `structural-split` rendering.
- `apply_finding` emits `## Verdict: BLOCKED-STRUCTURAL`, parsed into
  `ApplyFindingResult`.
- `escalate_to_split` runs `_split_is_safe` first; recovers titles+rationale from
  one proposal; enumerates `applied` / `recommended` / `unsafe` /
  `proposal-unusable` / `step-missing` / `split-failed (CreateError)`.
- Interactive + opt-in runs `_confirm_split` → `_apply_step_split` →
  `_migrate_downstream_details_after_split` and converges in one pass; unattended
  recommends only and never mutates structure.
- An in-loop (trigger 2) applied split in `detail` breaks both loop levels,
  re-parses, re-collects `target_steps`, and processes no stale pre-split `Step`.
- A recommend-only trigger-2 finding is remembered in a per-run seen-set and not
  re-proposed on later unattended iterations.
- A surfaced split recommendation keeps rc 0 unless `--fail-on-findings`.
- Create-side trigger 2 is either backed by a named scenario *or* Deferred — not
  shipped as live-but-inert wiring.

## Deferred

- **Create-side trigger 2** unless the open question names a real scenario.
- Pairing with the granularity advisor (`step-granularity-advisor.md`) that
  *produces* `granularity-split` findings.
- Renaming `detail-purity` → `granularity-split` across the classifier.
- Persisting the create `structural-split` recommendation as a saved finding.
- Wiring the bridge into the completeness authoring audit (the generalized
  "escalate to re-plan instead of patching prose" capability).
