> **Replaced**: this file has been superseded by `docs/implementation-plans/2-accumulate-audit-finding-knowledge.md`.
> Preserved here for history; do not edit.

# Plan seed: accumulate audit-iteration finding knowledge as carry-forward context (audit + execution)

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/accumulate-audit-finding-knowledge.md --iterate
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Scope: widen the finding carry-forward across an `--iterate` run.** Today the
> audit loop carries prior findings forward as `(anchor, title)` pairs into the
> next *audit* prompt, solely for id-stability/dedup. This plan widens that
> carry-forward payload (body + severity + apply-resolution) and extends it to a
> second consumer — the *execution/apply* path — so later passes and
> `apply_finding` can reason about what the loop already surfaced and tried. It
> does **not** change *what* the audit finds or the convergence stop logic — only
> the context fed into subsequent passes.

---

## Overview

Backlog item **#76**. Across a `completeness` / reconcile `--iterate` run, the
loop already re-derives context it has seen before, and the execution side has no
memory of the loop's history. Generalize the existing `known_anchors` mechanism
along two axes:

1. **Richer payload** — carry forward each accumulated finding's *knowledge*
   (anchor slug, title, a bounded body excerpt, severity, and its
   resolution: applied / blocked / skipped + reason), not just `(anchor, title)`.
2. **Second consumer** — thread the accumulated, resolved-finding context into
   the **execution/apply** path (`apply_finding`), not only the next audit
   prompt, so apply can avoid re-attempting a blocked remedy and execution gets
   the "here's what the loop learned" context.

The narrow `(anchor, title)` → next-audit-prompt path stays correct and is the
foundation this generalizes; nothing here removes the existing dedup behavior.

## Problem statement

The iterate loop accumulates findings but shares almost none of that knowledge
forward, and what it does share goes to only one consumer:

- **Carry-forward is identity-only.** `audit_plan_until_stable`
  (`review.py:4611`) accumulates findings in `by_id` and, on each pass after the
  first, passes `known_anchors=[(r.anchor, r.title) for r in by_id.values()]`
  into `check_plan_audit` → `render_plan_audit_prompt` →
  `_format_known_findings_block` (`review.py:4170`). That block lists slug +
  title only, and exists *purely* so Claude re-uses the established slug and the
  union-by-id merge collapses rephrasings. A later pass cannot see a finding's
  body, its severity, or whether it was already applied/blocked — so it can't
  reason "this was tried and blocked" or "this region was patched and
  re-surfaced" (the spin signature).
- **Execution has no loop memory.** `apply_finding` (`launcher.py:2434`)
  operates on plan + the single finding being applied, with no view of the other
  findings the loop has surfaced or resolved this run. The convergence loop
  (`completeness_cmd._run_iterate_convergence_loop`, `_sample_conceptual_audit`
  in `completeness_phases.py:265`) drives audit → apply but never hands apply the
  accumulated context.
- **Net effect:** redundant re-flagging across passes, apply re-attempting
  remedies a prior finding already established won't work, and the
  "what the loop learned" context living only in the operator's head.

## Input contract (verified against code at HEAD)

This plan consumes existing structures — pin them before decomposing:

- **`review._format_known_findings_block(known_anchors: Sequence[tuple[str, str]]) -> str`**
  (`review.py:4170`) — the current slug-reuse renderer; the widened payload
  extends or replaces this.
- **`review.render_plan_audit_prompt(..., known_anchors=()) -> Optional[str]`**
  (`review.py:4201`) and `check_plan_audit(..., known_anchors=())`
  (`review.py:4353`) — the prompt seam threading `known_anchors`; the
  `prompts/plan-audit.md` template's `known_findings_block` substitution.
- **`review.audit_plan_until_stable(...)`** (`review.py:4611`) — owns the
  `by_id: dict[str, Recommendation]` accumulator and builds `known_anchors` from
  it (`review.py:4731`). This is where the widened payload is assembled.
- **`Recommendation`** — carries `id`, `anchor`, `title`, `severity`, and body;
  **`Annotation`** — carries `status` (`applied`/`skip`/`open`) and
  `halt_reason` (the apply verdict / resolution). Both are persisted-schema
  dataclasses documented in `DATA_CONTRACT.md` (drift-guarded) — confirm field
  names/shapes at HEAD before reading them into the carry-forward record.
- **`apply_finding(...)`** (`launcher.py:2434`) — the execution seam; widening
  its input is gated by its deliberately-narrow scope guard (see Risks).

## Design

### Phase 1 — widen the carry-forward payload (`review.py`)

Define a small, ordered, deterministic carry-forward record (e.g.
`CarriedFinding`: anchor, title, severity, a length-capped body excerpt, and
resolution = applied/blocked/skipped + reason). Assemble it in
`audit_plan_until_stable` from the `by_id` accumulator plus the saved
`Annotation` status/`halt_reason` for each finding's resolution. Keep ordering
stable (sort by a fixed key, e.g. severity then anchor) so the loop never
reorders findings non-deterministically.

### Phase 2 — render the richer payload into later audit prompts (`review.py` + `prompts/plan-audit.md`)

Extend `_format_known_findings_block` (or add a sibling renderer) to emit the
widened record — slug + title as today, plus severity, the body excerpt, and the
resolution — so a later pass can say "already surfaced as HIGH, applied; if it
recurs that's a spin signal" rather than re-deriving it. Update
`prompts/plan-audit.md` to consume the richer block. Preserve the existing
slug-reuse contract verbatim (the dedup behavior must not regress). Cap the
rendered size so the prompt doesn't balloon (truncate/summarize the carried set;
prefer the highest-severity / unresolved findings if capped).

### Phase 3 — thread accumulated context into execution/apply (`launcher.py` + the loop sites)

The harder half. Give `apply_finding` an optional, bounded view of the
resolved-finding history (e.g. a `carried_findings=()` kwarg, defaulting empty so
every existing caller is unchanged), rendered into the apply prompt so apply can
avoid re-attempting an already-blocked remedy. Wire it from the convergence loop
(`_run_iterate_convergence_loop` / the `_dispatch_apply_finding` path) which owns
the accumulated set. This crosses `apply_finding`'s narrow scope guard — make the
context strictly *advisory* in the prompt (it informs, it does not expand what
apply is allowed to edit), and keep the scope-guard's in-scope path set
unchanged.

## Step decomposition (apply the single-concern rule)

Propose **pure, single-concern steps**:

- **Phase-1 step** — the `CarriedFinding` record + deterministic assembly in
  `audit_plan_until_stable` from `by_id` + saved `Annotation` resolution. No
  prompt change yet; unit-test the assembly + ordering.
- **Phase-2 step** — render the widened block (`review.py` +
  `prompts/plan-audit.md`); preserve the slug-reuse dedup contract; add the
  size cap. Test that dedup still collapses rephrasings and the new fields
  render.
- **Phase-3 step (feature)** — `apply_finding` gains the optional advisory
  `carried_findings` view + the loop wiring; default-empty keeps all existing
  callers byte-for-byte. Test the new caller path and the scope-guard
  invariant (advisory context does not widen the in-scope edit set).

Keep Phase 2 (audit-prompt rendering) and Phase 3 (apply-prompt threading) as
**separate** steps — distinct consumers, distinct prompt files, distinct
scope-guard exposure.

## Out of scope

- Changing *what* the audit finds, how it samples, the convergence stop logic,
  or what gets auto-applied — this is carry-forward *context* only.
- Widening `apply_finding`'s **in-scope edit set** — the carried context is
  advisory; it never expands what apply is permitted to write. (The
  apply-context-widening *policy* decision is shared with #41 — coordinate, don't
  conflate the seed payload with the findings payload.)
- A persisted cross-run finding-history store — this is *within-run* loop memory
  (cross-run history already lives in saved reports / `convergence` / #72).
- Auto-tuning thresholds from the carried data — that consumer is #72 telemetry.

## Risks

- **`apply_finding` scope-guard regression.** Severity: high. Mitigation: the
  carried context is advisory prompt text only; assert the scope-guard's
  in-scope path set is unchanged with vs. without `carried_findings`. Same
  policy seam #41 faces — keep them consistent.
- **Prompt-cache / token cost growth.** Severity: medium. The carried payload
  grows with the finding count. Mitigation: cap and summarize the rendered set
  (length-bounded body excerpts; prefer unresolved / highest-severity when
  capped); verify against the run-log `cache_read_tokens`.
- **Non-deterministic reordering.** Severity: medium. Mitigation: sort the
  carried set by a fixed key; pin the order in tests.
- **Dedup contract regression.** Severity: medium. The slug-reuse behavior is
  load-bearing for union dedup. Mitigation: keep the existing slug + title lines
  intact; add a test that rephrased duplicates still collapse after the
  payload widens.

## Acceptance criteria

- `audit_plan_until_stable` assembles a deterministic, stably-ordered
  carry-forward record per accumulated finding, including severity, a
  length-capped body excerpt, and the resolution (applied/blocked/skipped +
  reason) read from the saved `Annotation`.
- Later audit passes render the widened record into `prompts/plan-audit.md`; the
  existing slug-reuse dedup still collapses rephrased duplicates (regression
  test passes), and the rendered block respects the size cap.
- `apply_finding` accepts an optional, default-empty advisory `carried_findings`
  view threaded from the convergence loop; with it empty, every existing caller
  and test is unchanged.
- The scope guard's in-scope edit set is identical with and without
  `carried_findings` (test-asserted) — the context never widens what apply may
  write.
- The carried set is deterministically ordered (test-pinned); the rendered
  audit + apply prompts do not reorder findings across runs.

## Deferred

- A persisted, cross-run finding-knowledge store (within-run only here).
- Telemetry/tuning consumption of the carried data (#72).
- Folding #41's seed payload and #76's findings payload into one shared
  apply-context mechanism (decide the shared scope-guard policy first).
- A machine-readable `--json` surface for the carried context.
