> **Replaced**: this file has been superseded by `docs/implementation-plans/2-accumulate-audit-finding-knowledge.md`.
> Preserved here for history; do not edit.

## Overview

Backlog item **#76**. This plan widens the audit-iteration finding carry-forward so later passes and the execution/apply path can reason about what the `--iterate` loop already surfaced and tried. Today `audit_plan_until_stable` carries prior findings forward only as `(anchor, title)` pairs into the next *audit* prompt, purely for id-stability/dedup. This generalizes the existing `known_anchors` mechanism along two axes: a **richer payload** (anchor, title, a bounded body excerpt, severity, and resolution = applied/blocked/skipped + reason) and a **second consumer** (thread the accumulated, resolved-finding context into `apply_finding`, not only the next audit prompt). It does **not** change *what* the audit finds, how it samples, or the convergence stop logic — only the context fed into subsequent passes. The existing narrow `(anchor, title)` → next-audit-prompt dedup path stays correct and is the foundation this generalizes.

## Problem statement

The iterate loop accumulates findings but shares almost none of that knowledge forward, and what it does share goes to only one consumer:

- **Carry-forward is identity-only.** `audit_plan_until_stable` (`review.py:4611`) accumulates findings in `by_id` and, on each pass after the first, passes `known_anchors=[(r.anchor, r.title) for r in by_id.values()]` into `check_plan_audit` → `render_plan_audit_prompt` → `_format_known_findings_block` (`review.py:4170`). That block lists slug + title only, and exists purely so Claude re-uses the established slug and the union-by-id merge collapses rephrasings. A later pass cannot see a finding's body, its severity, or whether it was already applied/blocked — so it can't reason "this was tried and blocked" or "this region was patched and re-surfaced" (the spin signature).
- **Execution has no loop memory.** `apply_finding` (`launcher.py:2434`) operates on plan + the single finding being applied, with no view of the other findings the loop has surfaced or resolved this run. The convergence loop (`completeness_cmd._run_iterate_convergence_loop`, `_sample_conceptual_audit` in `completeness_phases.py:265`) drives audit → apply but never hands apply the accumulated context.
- **Net effect:** redundant re-flagging across passes, apply re-attempting remedies a prior finding already established won't work, and the "what the loop learned" context living only in the operator's head.

## Architecture

This plan consumes existing structures — pin them at HEAD before decomposing:

- **`review._format_known_findings_block(known_anchors: Sequence[tuple[str, str]]) -> str`** (`review.py:4170`) — the current slug-reuse renderer; the widened payload extends or replaces it.
- **`review.render_plan_audit_prompt(..., known_anchors=()) -> Optional[str]`** (`review.py:4201`) and `check_plan_audit(..., known_anchors=())` (`review.py:4353`) — the prompt seam threading `known_anchors`; the `prompts/plan-audit.md` template's `known_findings_block` substitution.
- **`review.audit_plan_until_stable(...)`** (`review.py:4611`) — owns the `by_id: dict[str, Recommendation]` accumulator and builds `known_anchors` from it (`review.py:4731`); where the widened payload is assembled.
- **`Recommendation`** carries `id`, `anchor`, `title`, `severity`, and body; **`Annotation`** carries `status` (`applied`/`skip`/`open`) and `halt_reason` (the apply verdict / resolution). Both are persisted-schema dataclasses documented in `DATA_CONTRACT.md` (drift-guarded) — confirm field names/shapes at HEAD before reading them into the carry-forward record.
- **`apply_finding(...)`** (`launcher.py:2434`) — the execution seam; widening its input is gated by its deliberately-narrow scope guard.

Three-phase design:

**Phase 1 — widen the carry-forward payload (`review.py`).** Define a small, ordered, deterministic carry-forward record (e.g. `CarriedFinding`: anchor, title, severity, a length-capped body excerpt, and resolution = applied/blocked/skipped + reason). Assemble it in `audit_plan_until_stable` from the `by_id` accumulator plus the saved `Annotation` status/`halt_reason` for each finding's resolution. Keep ordering stable (sort by a fixed key, e.g. severity then anchor) so the loop never reorders findings non-deterministically.

**Phase 2 — render the richer payload into later audit prompts (`review.py` + `prompts/plan-audit.md`).** Extend `_format_known_findings_block` (or add a sibling renderer) to emit the widened record — slug + title as today, plus severity, the body excerpt, and the resolution — so a later pass can say "already surfaced as HIGH, applied; if it recurs that's a spin signal". Update `prompts/plan-audit.md` to consume the richer block. Preserve the existing slug-reuse contract verbatim (dedup must not regress). Cap the rendered size so the prompt doesn't balloon (truncate/summarize the carried set; prefer highest-severity / unresolved findings if capped).

**Phase 3 — thread accumulated context into execution/apply (`launcher.py` + the loop sites).** Give `apply_finding` an optional, bounded view of the resolved-finding history (e.g. a `carried_findings=()` kwarg, defaulting empty so every existing caller is unchanged), rendered into the apply prompt so apply can avoid re-attempting an already-blocked remedy. Wire it from the convergence loop (`_run_iterate_convergence_loop` / the `_dispatch_apply_finding` path) which owns the accumulated set. This crosses `apply_finding`'s narrow scope guard — make the context strictly *advisory* in the prompt (it informs, it does not expand what apply is allowed to edit), and keep the scope-guard's in-scope path set unchanged.

Keep Phase 2 (audit-prompt rendering) and Phase 3 (apply-prompt threading) as separate concerns — distinct consumers, distinct prompt files, distinct scope-guard exposure.

## Out of scope

- Changing *what* the audit finds, how it samples, the convergence stop logic, or what gets auto-applied — this is carry-forward *context* only.
- Widening `apply_finding`'s **in-scope edit set** — the carried context is advisory; it never expands what apply is permitted to write. (The apply-context-widening *policy* decision is shared with #41 — coordinate, don't conflate the seed payload with the findings payload.)
- A persisted cross-run finding-history store — this is *within-run* loop memory (cross-run history already lives in saved reports / `convergence` / #72).
- Auto-tuning thresholds from the carried data — that consumer is #72 telemetry.

## Risks

- **`apply_finding` scope-guard regression.** Severity: high. Mitigation: the carried context is advisory prompt text only; assert the scope-guard's in-scope path set is unchanged with vs. without `carried_findings`. Same policy seam #41 faces — keep them consistent.
- **Prompt-cache / token cost growth.** Severity: medium. The carried payload grows with the finding count. Mitigation: cap and summarize the rendered set (length-bounded body excerpts; prefer unresolved / highest-severity when capped); verify against the run-log `cache_read_tokens`.
- **Non-deterministic reordering.** Severity: medium. Mitigation: sort the carried set by a fixed key; pin the order in tests.
- **Dedup contract regression.** Severity: medium. The slug-reuse behavior is load-bearing for union dedup. Mitigation: keep the existing slug + title lines intact; add a test that rephrased duplicates still collapse after the payload widens.

## Testing

Default to unit tests exercising one function in isolation, per the project's unit-first convention; reserve `@pytest.mark.integration` for the cross-module loop wiring. Cross-cutting coverage this plan requires:

- Unit-test the `CarriedFinding` assembly + ordering in `audit_plan_until_stable` from `by_id` plus the saved `Annotation` resolution — pin the deterministic order by the fixed sort key.
- Regression-test that the widened `_format_known_findings_block` / `prompts/plan-audit.md` rendering preserves the slug-reuse dedup (rephrased duplicates still collapse) and that the new severity/body-excerpt/resolution fields render, respecting the size cap.
- Test the new `apply_finding` caller path with `carried_findings` threaded from the convergence loop, and assert the scope-guard invariant: the in-scope edit set is identical with and without `carried_findings`.
- With `carried_findings` empty, confirm every existing `apply_finding` caller and test is unchanged.
- When touching the convergence-loop wiring (`completeness_cmd._run_iterate_convergence_loop`, `_dispatch_apply_finding`), run the relevant integration tests that drive audit → apply end-to-end.

## Acceptance criteria

- `audit_plan_until_stable` assembles a deterministic, stably-ordered carry-forward record per accumulated finding, including severity, a length-capped body excerpt, and the resolution (applied/blocked/skipped + reason) read from the saved `Annotation`.
- Later audit passes render the widened record into `prompts/plan-audit.md`; the existing slug-reuse dedup still collapses rephrased duplicates (regression test passes), and the rendered block respects the size cap.
- `apply_finding` accepts an optional, default-empty advisory `carried_findings` view threaded from the convergence loop; with it empty, every existing caller and test is unchanged.
- The scope guard's in-scope edit set is identical with and without `carried_findings` (test-asserted) — the context never widens what apply may write.
- The carried set is deterministically ordered (test-pinned); the rendered audit + apply prompts do not reorder findings across runs.

## Deferred

- A persisted, cross-run finding-knowledge store (within-run only here).
- Telemetry/tuning consumption of the carried data (#72).
- Folding #41's seed payload and #76's findings payload into one shared apply-context mechanism (decide the shared scope-guard policy first).
- A machine-readable `--json` surface for the carried context.
