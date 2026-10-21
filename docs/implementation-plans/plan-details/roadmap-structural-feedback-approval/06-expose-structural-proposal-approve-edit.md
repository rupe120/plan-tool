# Step 6 — Expose the structural proposal and approve, edit, or reject choices through the ordinary roadmap feedback command

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Extend `plan_tool/cli/roadmap_cmd.py` so the existing ordinary roadmap feedback route presents the structural proposal and its explicit approve, edit, and reject choices. Reuse the candidate lifecycle dispatch, result renderers, and exit-status mapping rather than adding another command family or lifecycle. The CLI must expose only persisted proposal and decision facts, while step 5 remains the only accepted-head writer. On green, `tests/cli/test_roadmap_cmd.py` proves invalid, stale, rejected, failed, edited, and promoted outcomes reach distinct operator-visible results without changing canonical state on non-promotion paths.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the CLI decision surface.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why the current lifecycle flags do not yet expose structural approval clearly.
- [Input](#input) — Stored proposal, decision, and promotion contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two existing files changed by this step.
- [Implementation](#implementation) — Command routing, rendering, and safety boundaries.
- [Tests](#tests) — Focused CLI coverage for proposal and decision outcomes.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Contracts and operator guidance for the lifecycle.
- [Applicable guardrails](#applicable-guardrails) — Plan fences that limit this command surface.
- [Deferred](#deferred) — Documentation and broader lifecycle work owned elsewhere.

## Why

`plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_candidate_lifecycle` already routes ordinary `--revise-feedback` and candidate lifecycle actions, but its current proposal, question, answer, release, and promotion surfaces do not present step 3’s structural decision as one clear approve/edit/reject choice. The CLI needs to make the stored structural proposal understandable and let a user select one exact outcome without asking them to classify feedback, infer candidate state, or mistake a review answer for approval.

## Input

- **Step 3 structural decision:** Consume the persisted structural proposal and exact approve, edit, and reject outcomes supplied by step 3. The CLI must treat those records as authoritative and must not derive a structural route from feedback wording, a live ledger read, or a new diff.

- **Stored disclosure:** Use the active candidate's persisted normalized operations, route, `predecessor_diff`, batch receipt, and immutable source and candidate identities. The same facts are required for an edited replacement; do not reuse the initial candidate's disclosure after edit.

- **Step 5 promotion result:** Consume step 5’s approved-promotion entry point and terminal result. Promotion remains backend-free at this layer and remains responsible for all accepted-head, active-pointer, and seed-state effects.

- **Existing lifecycle dispatch:** Retain `plan_tool/cli/roadmap_cmd.py:_has_candidate_lifecycle_action`, `_candidate_lifecycle_has_conflict`, `_cmd_roadmap_candidate_lifecycle`, and `_option_occurrences` as the parser-history and one-action boundary.

- **Existing proposal route:** Keep `plan_tool/cli/roadmap_cmd.py:_selector_free_revise_feedback_selected` and `_cmd_roadmap_propose_candidate` as the ordinary feedback intake. `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal` remains the candidate producer.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Extend the ordinary feedback lifecycle flags, preflight, dispatch, result rendering, help text, and exit-status handling for structural proposal decisions.
  - `tests/cli/test_roadmap_cmd.py` — Add focused parser, dispatch, rendering, exclusivity, and no-side-effect coverage for the structural decision surface.

## Implementation

- **Keep one intake.** Continue to accept ordinary feedback through selector-free `--revise-feedback`, routed through `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_propose_candidate`. Users must not supply a structural flag, operation kind, or route selector. A valid typed operation set reaches the route chosen by steps 1 and 2.

- **Expose one decision surface for structural proposals.** Extend the candidate lifecycle parser registration in `plan_tool/cli/roadmap_cmd.py:register` and the dispatch in `_cmd_roadmap_candidate_lifecycle` so an operator can inspect the stored structural proposal and choose exactly one approve, edit, or reject outcome. Reuse the final public entry points from steps 3 and 5; do not create a second candidate review or promotion command family.

- **Make approval exact and separate from review answers.** The approve action must directly seal the displayed active structural candidate, including an initial proposal, without requiring a question or replacement. A stored answer or edited replacement is not approval. Route the resulting exact seal through step 5’s promotion entry point, preserving the writer-guard and error boundary.

- **Treat edit as replacement, not mutation.** Pass the user’s correction to step 3 as the only edit input. It records an active, unsealed replacement for a fresh decision; the CLI must not request an additional user answer, edit stored candidate bytes, rewrite an accepted artifact, or silently promote the replacement.

- **Treat reject as release only.** Route rejection through the step 3 release behavior, following the existing shape of `_cmd_roadmap_candidate_resolution`. It must identify the exact active proposal, retain immutable history, and leave the accepted head unchanged.

- **Render the exact decision disclosure.** Adapt the existing result renderers to show the active candidate and source identities; selected feedback and typed operations; every changed artifact and row (including downstream rows); relation additions/removals and ordering-row changes; and the before/after values needed to see material consequences. Distinguish the selected feedback's already-recorded candidate state from approval's effects: accepted-head advance, active-pointer release, and enrolled seed-state invalidation. State the non-goals: no change to unlisted artifact bytes, unrelated feedback, or seed bodies. Label empty categories explicitly. Derive this display only from the active candidate's stored evidence and immutable bytes, not a fresh model reply, mutable ledger, or reconstructed diff. Do not allow a decision until this disclosure is available.

- **Keep results distinct.** Preserve `_candidate_model_result_status` as the common outcome-to-exit boundary, extending it only as needed for step 3 and step 5 result vocabulary. Invalid or stale proposals, failed model work, rejected proposals, edited replacements, and successful promotions must have unambiguous output and appropriate non-success or success statuses. Use the existing refusal path for invalid input and stale bindings.

- **Reject ambiguous command combinations before work.** Extend `_candidate_lifecycle_has_conflict` and every relevant exclusive-mode predicate so proposal, decision, promotion, broad modes, views, and unrelated lifecycle actions remain mutually exclusive. The preflight must run before path resolution, run-log creation, model invocation, candidate writes, or promotion.

- **Preserve bounded-route behavior.** Presentation-only candidates retain the current lifecycle behavior and must not be forced through the structural approval gate. The CLI selects the current active candidate's persisted route, including after edit, but does not repeat step 1’s classification or inherit the initial candidate's route.

- **Reuse unchanged shared owners.** Leave `plan_tool/roadmap_candidate_run.py`, `plan_tool/roadmap_candidate_review.py`, and `plan_tool/roadmap_version_promotion.py` outside this step’s footprint. Steps 3 and 5 own decision and promotion semantics; this step only passes their exact inputs and presents their closed results.

## Tests

### Tests for this step

- `test_revise_feedback_dispatches_to_the_selector_free_proposal_runner` — asserts ordinary feedback forwards no user-selected structural selector and preserves the invoker seam.

- `test_structural_proposal_rendering_discloses_the_full_stored_effect` — asserts initial and edited proposals each show their own source/candidate identities, selected feedback and operations, affected artifacts and rows, relation and ordering effects, before/after consequences, promotion effects, and explicit non-goals; empty categories are labeled, and no fresh ledger or diff read is needed.

- `test_structural_approve_seals_the_initial_proposal_without_a_question` — asserts approval forwards the exact displayed candidate to step 3 and its seal to step 5 without invoking question/answer commands.

- `test_one_edit_correction_creates_an_unapproved_replacement_without_promoting` — asserts edit needs one user correction, creates the fresh-decision route, and never calls the accepted-head writer.

- `test_structural_reject_releases_only_the_named_active_proposal` — asserts rejection routes to the step 3 release operation and leaves the accepted head unchanged.

- `test_structural_decision_outcomes_have_distinct_terminal_rendering_and_statuses` — asserts invalid, stale, failed, rejected, edited, and promoted outcomes remain distinguishable to the operator.

- `test_structural_lifecycle_actions_reject_companions_before_side_effects` — asserts conflicting actions, views, broad modes, and confirmation shortcuts stop before runner, writer-guard, or backend calls.

- `test_presentation_route_does_not_require_structural_approval` — asserts a persisted bounded route retains its existing candidate behavior.

- `test_promoted_structural_revision_becomes_the_next_ordinary_feedback_predecessor` — promotes one approved structural candidate, submits subsequent ordinary feedback, and asserts the next candidate's accepted root names the promoted version rather than the former head.

- Every test in `tests/cli/test_roadmap_cmd.py` must be green before this step is complete.

## Acceptance criteria

- Ordinary `--revise-feedback` remains the only user-facing feedback intake and accepts no structural route selector.

- A stored structural proposal exposes one explicit approve, edit, or reject decision surface through `plan_tool/cli/roadmap_cmd.py`.

- The decision surface discloses the active candidate's complete stored effect and explicit non-goals before accepting a choice.

- Approval forwards only the exact reviewed structural identity to step 5’s promotion path.

- Edit produces a replacement that requires a fresh decision and does not promote it.

- Rejection releases only the named active proposal and does not change `AcceptedRoadmapHead`.

- Invalid, stale, failed, rejected, edited, and promoted outcomes produce distinct CLI results.

- Conflicting lifecycle options fail before any backend call, candidate write, accepted-head write, or seed change.

- A bounded presentation-only proposal does not require structural approval.

- `uv run pytest tests/cli/test_roadmap_cmd.py -q` passes.

## References

- [Roadmap Structural Feedback Approval plan](../../2-roadmap-structural-feedback-approval.md) — Read step 6’s intent, dependencies, and acceptance criteria.

- [ROADMAP_FEEDBACK_FORMAT.md](../../../ROADMAP_FEEDBACK_FORMAT.md) — Read the ordinary feedback, candidate review, release, and promotion lifecycle.

- [DATA_CONTRACT.md](../../../DATA_CONTRACT.md) — Read persisted candidate, review, and terminal-result boundaries.

- [docs/how-to/roadmap.md](../../how-to/roadmap.md) — Read the current operator-facing candidate review and promotion flow.

- [handoffs/2026-09-22-roadmap-feedback-revision-approval.md](../../../handoffs/2026-09-22-roadmap-feedback-revision-approval.md) — Read the approved reuse boundary and prerequisite limits.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, one intake and one decision surface** — Keep all structural choices within the ordinary roadmap feedback command and do not add a user-selected structural route.

- **The plan’s “## Scope guardrails”, accepted-head authority** — Do not add a CLI write path that bypasses step 5’s promotion owner or treats proposal, review, edit, or rejection as canonical publication.

- **The plan’s “## Scope guardrails”, non-promotion preservation** — Ensure CLI routing and error handling leave canonical artifacts and seeds untouched on invalid, stale, failed, rejected, edited, or interrupted outcomes.

- **The plan’s “## Out of scope”, no new lifecycle subsystem** — Reuse the current candidate lifecycle dispatch and stored-record owners instead of adding a parallel candidate store, checkpoint, or transaction path.

- **The plan’s “## Out of scope”, stage authority remains fixed** — Do not make the CLI accept structural work that the existing candidate and full-roadmap gates cannot validate.

## Deferred

- **Operator documentation for the final command forms and outcome wording** — Step 7 owns `ROADMAP_FEEDBACK_FORMAT.md`, `docs/how-to/roadmap.md`, CLI reference updates, and lifecycle documentation.

- **Read-only stale-status advice and richer model protocol diagnostics** — The plan’s “## Deferred” keeps these outside the approval command surface.
