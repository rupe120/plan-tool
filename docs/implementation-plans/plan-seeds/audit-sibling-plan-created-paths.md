# Plan seed: the conceptual audit knows the paths sibling roadmap plans create

This file is a `plan-tool create` input. Use it via:

```
plan-tool create audit-sibling-plan-created-paths --from-existing docs/implementation-plans/plan-seeds/audit-sibling-plan-created-paths.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per
step.

Source: `BUG_BACKLOG.md` → BUG → "The audit reports a path a sibling plan in
the same roadmap creates as missing" (Route: plan). It has no Jira ticket yet.
This seed carries that entry's scope contract.

## Outcome

A roadmap-derived plan's completeness audit is told which paths the other
plans in the same roadmap will create, so the model-driven audit stops
reporting those paths as missing. A multi-plan roadmap batch no longer
re-raises the same false finding every round, and `integrations/shared/DIRECTIVES.md`
§ "T — tool artifacts" no longer needs to tell triagers to ignore it.

## In scope

- The conceptual audit prompt, `plan_tool/prompts/plan-audit.md`, gains one
  input block: the repo-relative paths that same-roadmap sibling plans declare
  in `creates:`, with an instruction that a path in that list is planned
  work by a sibling plan and is not reported as missing.
- The block's contents come from the existing selection in
  `plan_tool/review.py`: the same-roadmap identity
  (`_sibling_roadmap_identity`) and the eligible sibling promises
  (`_eligible_planned_paths`), minus the audited plan's own `creates:`. No
  second selection rule is written.
- The rendering in `plan_tool/review.py` (`render_plan_audit_prompt`)
  supplies the block for a plan with a roadmap identity and renders an
  explicit empty statement otherwise.
- The audit input snapshot (`plan_tool/review_persistence.py:AuditInputSnapshot`)
  captures the sibling path set with the other inputs, and its fingerprint
  covers it, because the snapshot is the exact input the model was shown and
  its fingerprint gates conceptual-call reuse and the report's freshness.
- `integrations/shared/DIRECTIVES.md` § "T — tool artifacts": the sibling-path
  case is described as handled by the audit, while the stale roadmap or seed
  path case stays a T label.
- Backlog reconciliation: the final step removes the originating
  `BUG_BACKLOG.md` entry only after full shipment. Authoring this plan does
  not remove it.

## Out of scope / Non-goals

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

## Allowed behavior changes

Only these:

- The rendered conceptual audit prompt for a roadmap-derived plan includes
  the sibling `creates:` paths and the instruction not to report them
  missing; for any other plan it states that no sibling paths apply.
- The `DIRECTIVES.md` T paragraph changes as described above.

No other audit, `create`, `detail`, or roadmap behavior changes.

## Allowed reorganization

None.

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

## Architecture

- **Settled: deliver, don't verify.** The audit receives the sibling paths as
  facts. The only checked claim is the binary one: the rendered prompt
  contains the sibling paths for a roadmap-derived plan, and states none for
  any other plan. Whether a real model then refrains from the finding is not
  asserted by a test.
- **Settled: one selection rule.** The same-roadmap set is the existing
  `_eligible_planned_paths` result minus the audited plan's own `creates:`,
  used only when `_sibling_roadmap_identity` returns an identity. When identity
  is absent, or identity evidence is uncertain (the function raises
  `ValueError`, which `_eligible_planned_paths` already treats as "own paths
  only"), the block states that no sibling paths apply, so the prompt never
  carries a set the deterministic check would not use.
- **Settled: the sibling set is an audit input.** It is captured once in the
  `AuditInputSnapshot` and folded into its fingerprint, so a change to a
  sibling's `creates:` makes a prior conceptual result stale instead of being
  reused, and the prompt is rendered from the captured set, not re-read.
- **The block is explicit when empty.** An absent block and an empty one read
  the same to a model; the rendered text says plainly that no sibling plan
  paths apply.
- **Guarantee: "a path a same-roadmap sibling plan declares in `creates:` is
  given to the auditor as planned work."** Mechanism: the rendered prompt
  block. Owner: the prompt renderer in `plan_tool/review.py`.

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

## Stop / defer

Stop and surface to the user if sibling footprints are not reliable at audit
time, or if delivering them would need a new selection rule, a new persisted
record, or a change to the deterministic check. File any adjacent finding in
`BUG_BACKLOG.md` or `BACKLOG.md`; do not absorb it here.

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
