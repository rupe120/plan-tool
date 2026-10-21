> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Accumulate Audit Finding Knowledge
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Define CarriedFinding record + deterministic assembly in audit_plan_until_stable
  files:
  - plan_tool/review.py
  - plan_tool/review_persistence.py
  - tests/test_review.py
  - tests/test_review_persistence.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/accumulate-audit-finding-knowledge/01-define-carriedfinding-record.md
  status: done
- id: 2
  title: Render the widened CarriedFinding payload into later audit prompts (sibling
    renderer + plan-audit.md), preserving slug-reuse dedup and a size cap
  files:
  - plan_tool/review.py
  - plan_tool/prompts/plan-audit.md
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/accumulate-audit-finding-knowledge/02-render-widened-carriedfinding-payload.md
  status: done
- id: 3
  title: Add optional advisory carried_findings kwarg to apply_finding + render it
    into apply-finding.md without widening the scope-guard edit set
  files:
  - plan_tool/launcher.py
  - plan_tool/prompts/apply-finding.md
  - tests/test_launcher.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/accumulate-audit-finding-knowledge/03-optional-advisory-carried-findings.md
  status: done
- id: 4
  title: Wire the accumulated carried_findings set from the convergence loop into
    both apply_finding call sites
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/review_actions.py
  - tests/cli/test_completeness_cmd.py
  - tests/cli/test_review_actions.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 3
  detail: docs/implementation-plans/plan-details/accumulate-audit-finding-knowledge/04-wire-accumulated-carried-findings-set.md
  status: done
---
# Accumulate Audit Finding Knowledge

## Overview

Backlog item **#76**. This plan widens the audit-iteration finding carry-forward so later passes and the execution/apply path can reason about what the `--iterate` loop already surfaced and tried. Today `audit_plan_until_stable` carries prior findings forward only as `(anchor, title)` pairs into the next *audit* prompt, purely for id-stability/dedup. This generalizes the existing `known_anchors` mechanism along two axes: a **richer payload** (anchor, title, a bounded body excerpt, severity, and resolution = applied/blocked/skipped + reason) and a **second consumer** (thread the accumulated, resolved-finding context into `apply_finding`, not only the next audit prompt). The widened *audit* prompt gains severity + body excerpt only; the **resolution** is populated by the live apply path and rendered solely to the apply consumer (Phase 3), since apply has not run during the audit-only loop. It does **not** change *what* the audit finds, how it samples, or the convergence stop logic — only the context fed into subsequent passes. The existing narrow `(anchor, title)` → next-audit-prompt dedup path stays correct and is the foundation this generalizes.

## Problem statement

The iterate loop accumulates findings but shares almost none of that knowledge forward, and what it does share goes to only one consumer:

- **Carry-forward is identity-only.** `audit_plan_until_stable` (`review.py:4611`) accumulates findings in `by_id` and, on each pass after the first, passes `known_anchors=[(r.anchor, r.title) for r in by_id.values()]` into `check_plan_audit` → `render_plan_audit_prompt` → `_format_known_findings_block` (`review.py:4170`). That block lists slug + title only, and exists purely so Claude re-uses the established slug and the union-by-id merge collapses rephrasings. A later **audit** pass cannot see a finding's body or its severity — so it can't recognize the form a recurring finding takes when it widens its sampling. (Whether a finding was already applied/blocked — the "this was tried and blocked" / "this region was patched and re-surfaced" spin-signature reasoning — is an *apply*-side benefit: apply has not run during the audit-only loop, so the carried resolution is `open` for every finding the audit prompt sees and travels instead to `apply_finding` in Phase 3.)
- **Execution has no loop memory.** `apply_finding` (`launcher.py:2434`) operates on plan + the single finding being applied, with no view of the other findings the loop has surfaced or resolved this run. The convergence loop (`completeness_cmd._run_iterate_convergence_loop`, `_sample_conceptual_audit` in `completeness_phases.py:265`) drives audit → apply but never hands apply the accumulated context.
- **Net effect:** redundant re-flagging across passes and apply re-attempting remedies a prior finding already established won't work because the prompt consumers do not receive the loop's carried context; operator-facing visibility remains deferred to the `--json` surface.

## Architecture

This plan consumes existing structures — pin them at HEAD before decomposing:

- **`review._format_known_findings_block(known_anchors: Sequence[tuple[str, str]]) -> str`** (`review.py:4170`) — the current slug-reuse renderer; the widened payload extends or replaces it.
- **`review.render_plan_audit_prompt(..., known_anchors=()) -> Optional[str]`** (`review.py:4201`) and `check_plan_audit(..., known_anchors=())` (`review.py:4353`) — the prompt seam threading `known_anchors`; the `prompts/plan-audit.md` template's `known_findings_block` substitution.
- **`review.audit_plan_until_stable(...)`** (`review.py:4611`) — owns the `by_id: dict[str, Recommendation]` accumulator and builds `known_anchors` from it (`review.py:4731`); where the widened payload is assembled.
- **`Recommendation`** carries `id`, `anchor`, `title`, `severity`, and body; **`Annotation`** carries `status` (`applied`/`skip`/`open`) and `halt_reason` (the apply verdict / resolution). Both are persisted-schema dataclasses documented in `DATA_CONTRACT.md` (drift-guarded) — confirm field names/shapes at HEAD before reading them into the carry-forward record.
- **`apply_finding(...)`** (`launcher.py:2434`) — the execution seam; widening its input is gated by its deliberately-narrow scope guard.

Three-phase design:

**Phase 1 — widen the carry-forward payload (`review.py`).** Define a small, ordered, deterministic carry-forward record (e.g. `CarriedFinding`: anchor, title, severity, a length-capped body excerpt, and resolution = applied/blocked/skipped + reason). Assemble it in `audit_plan_until_stable` from the `by_id` accumulator plus the saved `Annotation` status/`halt_reason` for each finding's resolution. Keep ordering stable (sort by a fixed key, e.g. severity then anchor) so the loop never reorders findings non-deterministically.

**Phase 2 — render the richer payload into later audit prompts (`review.py` + `prompts/plan-audit.md`).** Extend `_format_known_findings_block` (or add a sibling renderer) to emit the widened record — slug + title as today, plus severity and the body excerpt — so a later pass can say "already surfaced as HIGH; here is its substance" and re-use the established slug when it recurs. (The resolution field is **not** rendered here: during the audit-only loop every carried finding is `open`, so the applied/blocked/spin-signal benefit lands on the apply consumer in Phase 3, not the audit prompt.) Update `prompts/plan-audit.md` to consume the richer block. Preserve the existing slug-reuse contract verbatim (dedup must not regress). Cap the rendered size so the prompt doesn't balloon (truncate/summarize the carried set; prefer highest-severity findings if capped).

**Phase 3 — thread accumulated context into execution/apply (`launcher.py` + the loop sites).** Give `apply_finding` an optional, bounded view of the resolved-finding history (e.g. a `carried_findings=()` kwarg, defaulting empty so every existing caller is unchanged), rendered into the apply prompt so apply can avoid re-attempting an already-blocked remedy. This is the **only** consumer that sees the applied/blocked resolution — so the "already tried and blocked" and patched-and-re-surfaced spin reasoning lives here, not in the audit prompt. Wire it from the convergence loop (`_run_iterate_convergence_loop` / the `_dispatch_apply_finding` path) which owns the accumulated set. This crosses `apply_finding`'s narrow scope guard — make the context strictly *advisory* in the prompt (it informs, it does not expand what apply is allowed to edit), and keep the scope-guard's in-scope path set unchanged.

Keep Phase 2 (audit-prompt rendering) and Phase 3 (apply-prompt threading) as separate concerns — distinct consumers, distinct prompt files, distinct scope-guard exposure.

## References

- [Prompt caching - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) — Official guidance on prompt-cache breakpoints and the cache_creation/cache_read_input_tokens usage fields, needed to verify the carried-payload growth doesn't blow the cache (the plan's medium token-cost risk).
- [Token counting - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/token-counting) — The /v1/messages/count_tokens endpoint reference for measuring prompt size, used to size-cap the widened known-findings and apply-context blocks before they balloon the audit/apply prompts.
- [dataclasses — Data Classes — Python 3 documentation](https://docs.python.org/3/library/dataclasses.html) — Authoritative reference for @dataclass field(), frozen, and order semantics, consulted when defining the new deterministic CarriedFinding carry-forward record alongside the existing Recommendation/Annotation dataclasses.
- [Sorting Techniques — Python 3 documentation](https://docs.python.org/3/howto/sorting.html) — Covers sorted()/list.sort() stability and key functions, the basis for pinning the carried-finding set to a fixed (severity, anchor) sort key so the loop never reorders findings non-deterministically.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changing *what* the audit finds, how it samples, the convergence stop logic, or what gets auto-applied — this is carry-forward *context* only.
- Widening `apply_finding`'s **in-scope edit set** — the carried context is advisory; it never expands what apply is permitted to write. (The apply-context-widening *policy* decision is shared with #41 — coordinate, don't conflate the seed payload with the findings payload.)
- A persisted cross-run finding-history store — this is *within-run* loop memory (cross-run history already lives in saved reports / `convergence` / #72).
- Auto-tuning thresholds from the carried data — that consumer is #72 telemetry.

## Risks

- **`apply_finding` scope-guard regression.** Severity: high. Mitigation: the carried context is advisory prompt text only; it never enters the tracked/snapshot surface or `compute_in_scope_paths`, which takes no `carried_findings` input and is computed before per-finding apply dispatch. Same policy seam #41 faces — keep them consistent.
- **Prompt-cache / token cost growth.** Severity: medium. The carried payload grows with the finding count. Mitigation: cap and summarize the rendered set (length-bounded body excerpts; prefer unresolved / highest-severity when capped); verify against the run-log `cache_read_tokens`.
- **Non-deterministic reordering.** Severity: medium. Mitigation: sort the carried set by a fixed key; pin the order in tests.
- **Dedup contract regression.** Severity: medium. The slug-reuse behavior is load-bearing for union dedup. Mitigation: keep the existing slug + title lines intact for the rendered <=30 anchored findings and test that rephrased duplicates collapse within that cap. Above the cap, lower-severity slug lines may be dropped, so a rephrased re-find can get a new body-derived id and remain duplicated; step 2 accepts that bounded residual regression.

## Testing

Default to unit tests exercising one function in isolation, per the project's unit-first convention; reserve `@pytest.mark.integration` for the cross-module loop wiring. Cross-cutting coverage this plan requires:

- Unit-test the `CarriedFinding` assembly + ordering in `audit_plan_until_stable` from `by_id` plus the saved `Annotation` resolution — pin the deterministic order by the fixed sort key.
- Regression-test that the widened `_format_known_findings_block` / `prompts/plan-audit.md` rendering preserves the slug-reuse dedup (rephrased duplicates still collapse) and that the new severity/body-excerpt/resolution fields render, respecting the size cap.
- Test the new `apply_finding` caller path with `carried_findings` threaded from the convergence loop, and assert the structural scope-guard invariant: carried context remains prompt-only and never enters the tracked/snapshot or scope-guard inputs.
- With `carried_findings` empty, confirm every existing `apply_finding` caller and test is unchanged.
- When touching the convergence-loop wiring (`completeness_cmd._run_iterate_convergence_loop`, `_dispatch_apply_finding`), run the relevant integration tests that drive audit → apply end-to-end.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.

## Acceptance criteria

- `audit_plan_until_stable` assembles a deterministic, stably-ordered carry-forward record per accumulated finding, including severity, a length-capped body excerpt, and the resolution (applied/blocked/skipped + reason) read from the saved `Annotation`.
- Later audit passes render the widened record into `prompts/plan-audit.md`; for the <=30 anchored findings kept in the carried block, the existing slug-reuse dedup still collapses rephrased duplicates (regression test passes). Above that cap, dropped lower-severity slug lines carry the documented bounded residual duplicate risk, and the rendered block respects the size cap.
- The audit and apply carried-findings blocks have fixed prompt placement after cacheable static prompt content, respect the documented per-set caps, and keep per-pass growth isolated to the dynamic suffix.
- `apply_finding` accepts an optional, default-empty advisory `carried_findings` view threaded from the convergence loop; with it empty, every existing caller and test is unchanged.
- The scope guard is structurally independent of `carried_findings`: carried context is prompt-only and never enters the tracked/snapshot surface or the `compute_in_scope_paths` inputs.
- The carried set is deterministically ordered (test-pinned); the rendered audit + apply prompts do not reorder findings across runs.

## Deferred

- A persisted, cross-run finding-knowledge store (within-run only here).
- Telemetry/tuning consumption of the carried data (#72).
- Folding #41's seed payload and #76's findings payload into one shared apply-context mechanism (decide the shared scope-guard policy first).
- A machine-readable `--json` surface for the carried context.
