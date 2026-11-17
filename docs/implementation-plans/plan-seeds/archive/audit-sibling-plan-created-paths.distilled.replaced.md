> **Replaced**: this file has been superseded by `docs/implementation-plans/2-audit-sibling-plan-created-paths.md`.
> Preserved here for history; do not edit.

## Overview

A roadmap-derived plan's conceptual completeness audit receives the list of repo-relative paths that the other plans in the same roadmap declare in `creates:`. The audit is told to treat those paths as planned work, not as missing files. The list comes from the existing sibling selection in `plan_tool/review.py`, minus the audited plan's own `creates:`. It is captured in the `AuditInputSnapshot` and covered by its fingerprint. A plan with no roadmap identity, or with uncertain identity, gets an explicit statement that no sibling paths apply. Audit blocking, severity, convergence policy and exit codes stay as they are.

## Problem statement

In a multi-plan roadmap batch, the model-driven conceptual audit reports a path as missing when a sibling plan in the same roadmap will create it. The same false finding comes back every round. Today `integrations/shared/DIRECTIVES.md` § "T — tool artifacts" has to tell triagers to ignore it.

The deterministic missing-file check already merges sibling `creates:` paths (archived plan `2-sibling-planned-input-paths`), using `_sibling_roadmap_identity` and `_eligible_planned_paths` in `plan_tool/review.py`. The conceptual audit prompt, `plan_tool/prompts/plan-audit.md`, rendered by `render_plan_audit_prompt`, is never given those paths. So the model has no way to know the path is planned work.

Source: `BUG_BACKLOG.md` → BUG → "The audit reports a path a sibling plan in the same roadmap creates as missing" (Route: plan). It has no Jira ticket yet.

## Architecture

**Settled: deliver, don't verify.** The audit receives the sibling paths as facts. The only checked claim is binary: the rendered prompt contains the sibling paths for a roadmap-derived plan, and states that none apply for any other plan. No test asserts whether a real model then holds back the finding. Findings are deliberately not filtered or post-processed. Matching finding prose against paths is the vocabulary-matching shape that `CLAUDE.md` § "Validating a semantic property you cannot observe" refuses.

**Settled: one selection rule.** The same-roadmap set is the existing `_eligible_planned_paths` result minus the audited plan's own `creates:`. It is used only when `_sibling_roadmap_identity` returns an identity. In two cases the block states that no sibling paths apply:
- identity is absent;
- identity evidence is uncertain: the function raises `ValueError`, which `_eligible_planned_paths` already treats as "own paths only".

This way the prompt never carries a set the deterministic check would not use. No second selection rule is written. The all-registered-plans set that `_eligible_planned_paths` uses for a plan with no roadmap identity is deliberately not delivered to the prompt.

**New prompt input block.** `plan_tool/prompts/plan-audit.md` gains one input block. It lists the sibling `creates:` paths, one per line, with an instruction that a listed path is a sibling plan's planned work and is not reported as missing. `render_plan_audit_prompt` in `plan_tool/review.py` supplies the block. The block is explicit when empty: to a model, an absent block and an empty one look the same, so the rendered text says plainly that no sibling plan paths apply.

**Settled: the sibling set is an audit input.** It is captured once in `plan_tool/review_persistence.py:AuditInputSnapshot`, alongside the other inputs, and folded into the snapshot fingerprint. The snapshot is the exact input the model was shown, and its fingerprint controls whether a conceptual call is reused and whether the report is fresh. A change to a sibling's `creates:` therefore makes a prior conceptual result stale instead of letting it be reused. The prompt is rendered from the captured set, not re-read.

**Guarantee:** "a path a same-roadmap sibling plan declares in `creates:` is given to the auditor as planned work." Mechanism: the rendered prompt block. Owner: the prompt renderer in `plan_tool/review.py`.

**Docs and bookkeeping.** `integrations/shared/DIRECTIVES.md` § "T — tool artifacts" describes the sibling-path case as handled by the audit, while the stale roadmap or seed path case stays a T label. The final step removes the originating `BUG_BACKLOG.md` entry, but only after full shipment.

## Out of scope

- Filtering or post-processing the model's findings. Matching finding prose
  against paths is the vocabulary-matching shape `CLAUDE.md` § "Validating a
  semantic property you cannot observe" refuses; the fix delivers the facts
  to the auditor and checks only that they were delivered.
- Paths created by plans outside the audited plan's roadmap, including the
  all-registered-plans set `_eligible_planned_paths` uses for a plan with no
  roadmap identity. That deterministic behavior is unchanged.
- Any other T class, including stale roadmap or seed paths.
- The deterministic missing-file check, which already merges sibling
  `creates:` (archived plan `2-sibling-planned-input-paths`).
- How a plan may depend on an unbuilt sibling plan (the separate
  `BUG_BACKLOG.md` entry on `create`'s "record unbuilt upstreams and stop"
  step).
- Audit blocking predicates, convergence policy, severity, or exit codes.

## Risks

- A long sibling list adds prompt size on large roadmaps. The block lists
  paths only, one per line, and the plan states the expected size on the
  largest real roadmap (Loom's `loom-aidlc-mvp`, nine plan rows).
- The model may still raise the finding despite the block. That is not
  tested by the suite; the plan records it as a limit rather than adding a
  finding filter.
- Changing a prompt contract can leave its descriptions disagreeing. Sweep by
  vocabulary, not only by identifier: `plan-audit.md`, the renderer's
  docstring, `DIRECTIVES.md` § T, and the `BUG_BACKLOG.md` entry.

## Testing

- A two-plan roadmap fixture where plan 2 cites a file plan 1 declares in
  `creates:`: the rendered audit prompt for plan 2 lists that path in the
  sibling block, and does not list plan 2's own `creates:`.
- A plan with no roadmap identity renders the explicit empty statement, even
  when other registered plans declare `creates:`.
- A plan from a different roadmap's `creates:` does not appear in the block.
- Uncertain identity evidence renders the empty statement, not a partial set.
- Changing a sibling plan's `creates:` changes the audit input fingerprint, so
  a prior conceptual result is not reused; an unchanged sibling set leaves the
  fingerprint unchanged.
- Every `${...}` placeholder in `plan-audit.md` is supplied by the renderer.
- `uv run pytest tests/ -q -n auto` is green.

## Acceptance criteria

- For a roadmap-derived plan, the rendered conceptual audit prompt lists each
  same-roadmap sibling's `creates:` path and tells the auditor not to report
  those as missing; for any other plan it states that none apply.
- The block's set equals the deterministic check's eligible set minus the
  plan's own paths for a plan with a roadmap identity, and is empty otherwise.
- The sibling set is part of the audit input fingerprint.
- `DIRECTIVES.md` § "T — tool artifacts" no longer lists the sibling-path case
  as a false positive to ignore.
- Backlog reconciliation: the final step removes the originating
  `BUG_BACKLOG.md` entry only after full shipment. Authoring this plan does not
  remove it.

## Input

- The block's contents come from the existing selection in
  `plan_tool/review.py`: the same-roadmap identity
  (`_sibling_roadmap_identity`) and the eligible sibling promises
  (`_eligible_planned_paths`), minus the audited plan's own `creates:`. No
  second selection rule is written.

## Scope guardrails

- No filtering of model findings, and no new selection rule for siblings.
- No change to the deterministic missing-file check or its selection.

## Audit guardrails

- Plans outside the audited plan's roadmap and other T classes are out of
  scope.
- Stop and surface to the user if sibling footprints are not reliable at
  audit time (for example the roadmap identity is ambiguous), rather than
  widening the selection.

## Expected placement

None.

## References

- `BUG_BACKLOG.md` — the source entry named above.
- `plan_tool/review.py` — `_eligible_planned_paths`, `_sibling_roadmap_identity`,
  `_planned_paths`, and the `plan-audit.md` renderer.
- `plan_tool/prompts/plan-audit.md` — the conceptual audit prompt.
- `plan_tool/review_persistence.py:AuditInputSnapshot` — the captured audit
  inputs and their fingerprint.
- `integrations/shared/DIRECTIVES.md` § "T — tool artifacts".
- `docs/implementation-plans/archive/2-sibling-planned-input-paths.md` — the
  deterministic half, already shipped.
