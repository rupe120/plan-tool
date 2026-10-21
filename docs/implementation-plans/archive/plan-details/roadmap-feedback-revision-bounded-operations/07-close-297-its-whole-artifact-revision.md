# Step 7 — Close #297, retire its bug record, and re-scope source-identity work

## Summary

Update `BACKLOG.md`, `BUG_BACKLOG.md`, and `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` so #297 is recorded as shipped rather than active. Remove the duplicate whole-artifact failure record from `BUG_BACKLOG.md` while retaining the independent hand-authored YAML defect and the remaining evidence-reader risk. Rework `docs/implementation-plans/2-roadmap-canonical-source-identity.md` into a smaller future plan for receipt and evidence freshness that consumes step 5’s baseline contract. Green means the tracking documents agree on what shipped, what remains paused, and what needs a later plan.

## Table of Contents

- [Summary](#summary) — The close-out outcome and affected tracking records.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the active records must match the shipped route.
- [Input](#input) — The shipped behavior and tracking contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The four documentation artifacts this step changes.
- [Implementation](#implementation) — Status transition, bug retirement, and remaining source-identity scope.
- [Tests](#tests) — Existing regression coverage and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Reviewable conditions for accurate close-out records.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries preserved by this documentation-only step.
- [Deferred](#deferred) — Work that remains outside this close-out.

## Why

`BACKLOG.md:#297 — Stage-level roadmap feedback revision regenerates the whole artifact; bound it to typed operations and a deterministic merge instead`, `BUG_BACKLOG.md:### Stage-level roadmap feedback revision fails on real-sized artifacts`, and `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md:## Ordered route` still describe the same failure as active. Leaving those records active after steps 5 and 6 deliver and document the bounded route would misdirect the next roadmap effort, while leaving the broad `docs/implementation-plans/2-roadmap-canonical-source-identity.md:steps:` graph intact would schedule baseline work that this plan now owns.

## Input

- **Shipped route evidence:** Read step 5’s landed result and step 6’s aligned public contract before changing any status. The close-out must rest on the bounded feedback route and its real-size regression coverage, not on this documentation step alone.

- **Backlog relationships:** Treat `BACKLOG.md:#297`, `BACKLOG.md:#298`, the #242 entry under `BACKLOG.md:### A. New capability, well-scoped`, and `BACKLOG.md:### Now / Next / Blocked / Parked (working set)` as one status surface. A change to one status must not leave a conflicting dependency or working-set label elsewhere.

- **Bug ownership:** Treat `BUG_BACKLOG.md:### Stage-level roadmap feedback revision fails on real-sized artifacts` as the duplicate #297 failure record. Keep `BUG_BACKLOG.md:### Hand-typed reviewer feedback in a raw YAML scalar can corrupt the canonical roadmap artifact` independent, and retain the remaining source-identity risk under `BUG_BACKLOG.md:### Every roadmap revision route rejects a render-canonical mismatch outright`.

- **Remaining reader scope:** Use `plan_tool/roadmap_escalation_selection.py:canonical_artifact_snapshot`, `plan_tool/roadmap_escalation_run.py:current_escalation_receipt`, `plan_tool/roadmap_impact_snapshot.py:_capture_artifact`, and `plan_tool/roadmap_impact_analysis.py:build_impact_analysis` as the real reader surfaces that the re-scoped plan must still address. Step 5 supplies baseline publication and ordinary/local admission; this step does not claim those readers already use it.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `BACKLOG.md` — Mark #297 completed, remove it from the active working set, and update #242 and #298 references so they state only their live conditions.
  - `BUG_BACKLOG.md` — Remove the whole-artifact revision bug record, repair the adjacent hand-authored YAML record’s cross-reference, and narrow the render-canonicality risk to the reader surfaces that remain unaddressed.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` — Mark the #297 gate in `## Ordered route` shipped and give the arc a current continuation through the re-scoped source-identity work.
  - `docs/implementation-plans/2-roadmap-canonical-source-identity.md` — Replace the superseded baseline-authoring plan shape with the remaining receipt, impact, escalation, and structural-evidence freshness work.

## Implementation

- **Close #297 without erasing its delivery record.** Update `BACKLOG.md:#297 — Stage-level roadmap feedback revision regenerates the whole artifact; bound it to typed operations and a deterministic merge instead` to a completed status with the actual closure evidence. Preserve the record as the durable decision and evidence trail, but remove every active-work instruction that belongs only before steps 5 and 6 complete.

- **Sweep every active-status reference.** Update the working-set rows in `BACKLOG.md:### Now / Next / Blocked / Parked (working set)` and the #242/#298 records. #298 still needs real usage evidence, but #297 shipping is no longer a pending dependency. #242 remains paused until the remaining source-identity work is re-scoped and audited; shipping #297 does not authorize its retention work.

- **Remove only the duplicate bug record.** Delete the complete `BUG_BACKLOG.md:### Stage-level roadmap feedback revision fails on real-sized artifacts (`invoke`/`parse`/`gates`)` entry. Update the adjacent hand-authored YAML entry so it stands on its own and does not refer to a removed entry as “above”; it remains open because this plan does not mediate reviewer edits to raw YAML.

- **Narrow the remaining risk instead of declaring source identity complete.** Rewrite the `BUG_BACKLOG.md:### Every roadmap revision route rejects a render-canonical mismatch outright` heading and body so it no longer claims that ordinary or local revision lacks presentation tolerance. It should identify the remaining receipt, impact, escalation, and structural-evidence readers, their raw-provenance versus canonical-freshness boundary, and the need for a later plan to adopt the shared baseline safely.

- **Mark the arc gate shipped.** Replace the #297 gate state in `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md:## Ordered route` with a dated shipped record that names the bounded feedback outcome and its evidence. Keep the arc’s continuation explicit: re-scope source identity first, then reconsider #242 against the landed merge layer. Do not make either follow-up appear ready merely because the gate ships.

- **Re-scope the source-identity plan as a future evidence-reader plan.** Rework `docs/implementation-plans/2-roadmap-canonical-source-identity.md:steps:`, `## Architecture`, `## Testing`, `## Acceptance criteria`, and `## Deferred` together. Remove baseline initialization, writer publication, enrollment, and ordinary/local revision admission as future deliverables; step 5 supplies those capabilities. The replacement plan should begin from the existing writer-owned baseline and cover only the versioned receipt, impact, escalation, and structural-evidence readers that need canonical freshness while retaining raw immutable provenance.

- **Keep immutable version boundaries explicit.** The re-scoped plan must retain version-1 raw-evidence compatibility and forbid a reader from silently repairing or initializing source state. A later implementation may add versioned evidence fields and reader admission, but this documentation step must not widen writer authority or turn a semantic hand edit into an accepted source.

- **Prefer a smaller ordered plan over a caveat-heavy old plan.** One workable shape is a contract decision for evidence identity/versioning, reader updates that consume the baseline, and output/reference retirement. Adapt the exact step split to the remaining reader dependencies, but ensure its frontmatter file lists and acceptance criteria cover only that smaller surface.

## Tests

- `tests/test_roadmap_format.py:test_local_feedback_route_reference_marks_broad_reentry_boundaries` — Remains green, confirming the step 6 documentation prerequisite still names the bounded route and its broad-reentry boundary.
- `tests/test_roadmap_format.py:test_every_artifact_example_parses` — Remains green, confirming this close-out does not disturb the roadmap format examples.
- `tests/test_parser.py:TestIntent.test_plan_intent_parses_when_present` — Remains green as a regression check for plan frontmatter parsing; load the re-scoped source-identity plan with `plan_tool/parser.py:parse_plan` as part of verification.

### Verification (non-code step)

1. Parse `docs/implementation-plans/2-roadmap-canonical-source-identity.md` after changing its frontmatter step graph and confirm its declared files match the remaining work.
2. Run `uv run pytest tests/test_roadmap_format.py -q` to confirm the shipped documentation contract that supports this closure remains valid.
3. Search all four declared files for `#297`, `whole-artifact`, `in progress`, `in flight`, `paused`, and `roadmap-canonical-source-identity`; classify every surviving match as completed history or live remaining work.
4. Confirm the independent YAML-scalar bug still has its own heading and does not depend on text removed with the whole-artifact bug record.
5. Check Markdown links and `git diff --check` so the tracking cleanup leaves no broken route or formatting error.

## Acceptance criteria

- `BACKLOG.md` records #297 as completed and no working-set row presents it as in flight, blocked, or a prerequisite that has not shipped.
- `BACKLOG.md` preserves #298’s real-usage evidence requirement and #242’s pause without treating either as automatically ready.
- `BUG_BACKLOG.md` no longer contains `### Stage-level roadmap feedback revision fails on real-sized artifacts (`invoke`/`parse`/`gates`)`.
- `BUG_BACKLOG.md` retains the independent hand-authored YAML defect and a source-identity risk that names only still-uncovered evidence-reader behavior.
- `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md:## Ordered route` marks the #297 gate shipped and names re-scoped source identity as the next prerequisite for reconsidering #242.
- `docs/implementation-plans/2-roadmap-canonical-source-identity.md` contains no future step that reimplements baseline enrollment, writer publication, or ordinary/local revision admission delivered by step 5.
- `docs/implementation-plans/2-roadmap-canonical-source-identity.md` preserves raw immutable provenance, version-1 compatibility, and side-effect-free evidence-reader boundaries as requirements for its remaining scope.
- `plan_tool/parser.py:parse_plan` loads `docs/implementation-plans/2-roadmap-canonical-source-identity.md`, and `uv run pytest tests/test_roadmap_format.py -q` passes.

## Applicable guardrails

- **Bounded stage-revision intent:** The plan’s `## Plan intent` requires this step to report the deterministic bounded route as shipped; it must not reopen whole-artifact generation or describe a new revision mechanism.

- **Evidence-reader handoff:** The plan’s `## Out of scope`, baseline use by evidence readers, requires this step to preserve that work as a separate re-scoped plan rather than implementing or closing it.

- **Independent YAML defect:** The plan’s `## Out of scope`, reviewer-authored YAML corruption, allows a wording repair in `BUG_BACKLOG.md` but does not allow this step to resolve, retire, or absorb that defect.

- **Retention and recovery follow-ups:** The plan’s `## Out of scope`, #242 and broad recovery, requires the tracking updates to retain their decision boundaries and avoid claiming that #297 completion delivers either capability.

## Deferred

- #298 hand-edit-to-feedback review bridge — Remains deferred until real hand-edit evidence defines its review contract.
- #242 roadmap revision retention — Remains paused until the re-scoped source-identity plan is audited and the landed merge layer informs its redesign.
- Receipt, impact, escalation, and structural-evidence freshness implementation — Remains the re-scoped work in `docs/implementation-plans/2-roadmap-canonical-source-identity.md`; this step only defines its tracking boundary.
- Hand-authored YAML feedback safety — Remains the independent `BUG_BACKLOG.md` defect.
