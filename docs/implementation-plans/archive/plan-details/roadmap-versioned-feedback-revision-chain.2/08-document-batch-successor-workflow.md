> **Withdrawn 2026-09-22** — Superseded 2026-09-22: feedback moves to a roadmap-scoped mutable ledger; artifact versions retain no embedded mutable feedback.
> Preserved here for history; do not edit.

# Step 8 — Document the batch-to-successor workflow and reconcile obsolete selector and live-writer records

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update the roadmap reference and operator documentation to describe one accepted-head feedback batch becoming one inert successor, review lineage, and exact-seal promotion. Remove public guidance that treats `--revise-feedback` or selector-bearing `--propose-candidate` as ordinary feedback writers. Reconcile stale telemetry, capability, architecture, backlog, and test records with the lifecycle implemented by steps 1–7. On green, every scoped guide directs operators to the same selector-free batch workflow and names `AcceptedRoadmapHead` as the only canonical-content selector.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the documentation sweep.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why stale selector and live-writer guidance is unsafe.
- [Input](#input) — Landed lifecycle contracts this documentation reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation and drift-guard changes.
- [Implementation](#implementation) — Batch workflow, authority model, and obsolete-record cleanup.
- [Tests](#tests) — Documentation contract and generated-reference coverage.
- [Verification (non-code step)](#verification-non-code-step) — Checks for this non-code step.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Lifecycle contracts to consult.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for the documentation change.
- [Deferred](#deferred) — Work outside the documentation sweep.

## Why

The current public docs describe two incompatible ordinary-feedback models: `ROADMAP_FORMAT.md` and several guides still advertise one selected live-artifact revision, while steps 1–7 establish an accepted-head batch candidate that stays inert until exact review-seal promotion. Leaving both models visible could send an operator toward a route that bypasses the intended successor lifecycle or misstates which data is canonical.

## Input

- **Steps 1–6 lifecycle:** Read the landed batch, successor, review, and promotion names from `plan_tool/roadmap_candidate_context.py:build_candidate_context()`, `plan_tool/roadmap_candidate.py:materialize_candidate()`, `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal()`, `plan_tool/roadmap_candidate_review.py:generate_candidate_question()`, and `plan_tool/roadmap_version_promotion.py:promote_review_seal()`. The code and its tests win over earlier detail wording.

- **Step 7 command boundary:** Read `plan_tool/cli/roadmap_cmd.py:register()` and `_cmd_roadmap_candidate_lifecycle()` to document the selector-free public flags and their exclusive action rules.

- **Canonical authority:** Preserve `plan_tool/roadmap_versions.py:AcceptedRoadmapHead` and `load_accepted_version()` as the reader boundary. A candidate, question, answer, replacement, or seal is not canonical content.

- **Generated CLI reference:** Treat `docs/cli/roadmap.md` as output of `plan_tool/cli_reference.py:render_reference()`. Update the parser help first if needed, then regenerate the reference rather than hand-editing generated text.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — Replace the local feedback-revision contract and immutable-authority narrative with the batch-to-successor lifecycle and its canonical-content boundary.
  - `DATA_CONTRACT.md` — Remove or reconcile `RoadmapLocalRevisionPreflight` and `RoadmapLocalRevisionAttempt` records that no longer describe a supported ordinary-feedback route; document the landed batch lifecycle records only where durable telemetry owns them.
  - `README.md` — Update the roadmap command cheat sheet and workflow guidance to start selector-free batch proposal and explain promotion.
  - `CAPABILITIES.md` — Replace selector-bound and live-writer capability claims with the implemented batch lifecycle.
  - `RUNBOOK.md` — Replace routine local-revision recovery and workflow guidance with enrollment, batch proposal, review, and promotion guidance.
  - `TESTING.md` — Remove the obsolete local-revision seam entry and describe the selector-free candidate-proposal seam.
  - `docs/ARCHITECTURE.md` — Describe candidate modules as the ordinary feedback path and retain structural and stage-feedback boundaries without claiming a parallel live writer.
  - `docs/cli/roadmap.md` — Regenerate the CLI reference after selector-free help text lands.
  - `docs/how-to/common-workflows.md` — Update the feedback-row workflow to use the accepted-head batch lifecycle.
  - `docs/how-to/roadmap.md` — Replace the selected-row revision walkthrough and command sequence with an end-to-end batch-to-successor walkthrough.
  - `docs/reference/commands.md` — Update the roadmap cheat sheet and flag notes for selector-free proposal and promotion.
  - `BACKLOG.md` — Reconcile active entries that describe the removed ordinary live-writer route; retain independent follow-up work without presenting it as a current public workflow.
  - `BUG_BACKLOG.md` — Reconcile local-revision-specific defects and provenance so remaining records describe a still-supported surface or are clearly retired.
  - `tests/test_roadmap_format.py` — Replace local-revision reference assertions with batch lifecycle, canonical-authority, and obsolete-guidance sweep checks.
  - `tests/cli/test_cli_reference.py` — Keep generated-reference drift coverage and add focused assertions for selector-free feedback flags where useful.

## Implementation

- **Document one ordinary feedback workflow.** Make `ROADMAP_FORMAT.md` the detailed contract: enroll a complete roadmap, derive one ordered batch from the current accepted head, store one inert successor, complete review, then move only `AcceptedRoadmapHead` through `promote_review_seal()`. State that a later proposal starts from the promoted successor.

- **Keep feedback ownership clear.** Explain that batch admission may move eligible `open` rows to `awaiting-review` in the successor, while reviewer closure, deferral, and reopening retain their existing ownership. The dedicated `--reopen-feedback` route remains separate from model proposal.

- **Keep canonicality narrow.** Across `README.md`, `RUNBOOK.md`, `CAPABILITIES.md`, `docs/ARCHITECTURE.md`, `docs/how-to/common-workflows.md`, and `docs/how-to/roadmap.md`, state that stored candidate artifacts and review records are not canonical. Readers use the accepted head; promotion changes the selector without rewriting live top-level roadmap artifacts.

- **Remove obsolete public route claims.** Sweep the declared documentation files for selector-bearing `--revise-feedback`, selector-bearing `--propose-candidate`, `run_local_feedback_revision`, and wording that says ordinary feedback writes live artifacts. Replace each current-workflow claim with the batch lifecycle, or remove it when no replacement belongs at that location.

- **Preserve unrelated route boundaries.** Keep stage feedback, structural escalation, exact-pair structural rewrite, seed operations, decision settlement, and confirmed reopen distinct. Do not describe a structural route as a batch candidate path or grant it accepted-head authority.

- **Reconcile durable records carefully.** In `DATA_CONTRACT.md`, `BACKLOG.md`, and `BUG_BACKLOG.md`, remove obsolete records only when they exist solely for the retired ordinary route. Preserve an independent telemetry or recovery concern, but rewrite it so it does not name a removed public command as current behavior.

- **Use generated CLI output.** Update `plan_tool/cli/roadmap_cmd.py:register()` help only if the landed step 7 behavior needs wording correction, then use `plan_tool/cli_reference.py:render_reference()` to refresh `docs/cli/roadmap.md`. Do not manually maintain a conflicting flag signature.

- **Keep drift checks focused.** Adapt `tests/test_roadmap_format.py:test_immutable_candidate_version_reference_matches_landed_authority_contract()` and related route-sweep tests to require batch language and reject stale ordinary-route claims within the scoped documentation set. Keep `tests/cli/test_cli_reference.py:TestCliReferenceDrift` as the generated-file authority check.

## Tests

- `test_immutable_candidate_version_reference_matches_landed_authority_contract` — asserts the format reference names the landed batch lifecycle owners and keeps `AcceptedRoadmapHead` as the sole canonical selector.

- `test_batch_feedback_guidance_has_no_selector_or_live_writer_route` — asserts scoped current-workflow guides do not advertise selector-bearing ordinary feedback or live-artifact replacement.

- `test_batch_feedback_guidance_preserves_reopen_and_structural_boundaries` — asserts confirmed reopen, stage feedback, and structural routes remain distinct from batch proposal.

- `test_backlog_and_bug_backlog_do_not_present_retired_local_revision_as_current` — asserts active tracking records do not route new work through the obsolete ordinary writer.

- `test_roadmap_reference_documents_selector_free_batch_proposal` — renders `plan_tool/cli_reference.py:render_reference()` and asserts the proposal flags match the parser’s selector-free lifecycle.

- `tests/cli/test_cli_reference.py::TestCliReferenceDrift.test_every_generated_file_matches_disk` — confirms regenerated CLI reference files match the live parser.

## Verification (non-code step)

1. Run `uv run pytest tests/test_roadmap_format.py tests/cli/test_cli_reference.py -q`.

2. Run `python -m plan_tool.cli_reference --write` only after the CLI help is final, then confirm `docs/cli/roadmap.md` has no hand-maintained drift.

3. Search the declared documentation and tracking files for `--revise-feedback`, selector-valued `--propose-candidate`, `run_local_feedback_revision`, and “local feedback revision”; inspect each remaining hit and retain only a clearly marked historical or independent record.

4. Confirm each command shown in `README.md`, `RUNBOOK.md`, `docs/how-to/common-workflows.md`, `docs/how-to/roadmap.md`, and `docs/reference/commands.md` matches `plan_tool/cli/roadmap_cmd.py:register()`.

5. Confirm markdown links and table-of-contents anchors still resolve after heading changes.

## Acceptance criteria

- `ROADMAP_FORMAT.md` describes one complete accepted-head feedback batch, inert successor, review, and exact-seal promotion workflow.

- The scoped operator guides use selector-free ordinary-feedback commands and do not instruct users to revise one selected live artifact.

- Documentation states that only `AcceptedRoadmapHead` selects canonical enrolled-roadmap content.

- `DATA_CONTRACT.md` contains no durable local-revision event contract for a retired ordinary-feedback writer.

- `BACKLOG.md` and `BUG_BACKLOG.md` retain only tracking that remains relevant after the ordinary live-writer route is removed.

- `docs/cli/roadmap.md` is generated from the current parser and passes `tests/cli/test_cli_reference.py`.

- `uv run pytest tests/test_roadmap_format.py tests/cli/test_cli_reference.py -q` passes.

## References

- [ROADMAP_FORMAT.md — Read the feedback lifecycle and immutable accepted-head authority contract.](../../../ROADMAP_FORMAT.md)

- [DATA_CONTRACT.md — Read durable roadmap event and record ownership before retiring stale entries.](../../../DATA_CONTRACT.md)

- [docs/how-to/roadmap.md — Keep the operator walkthrough aligned with the implemented lifecycle.](../../how-to/roadmap.md)

- [plan_tool/roadmap_candidate_run.py — Read `run_initial_candidate_proposal()` for the landed batch proposal boundary.](../../../plan_tool/roadmap_candidate_run.py)

- [plan_tool/roadmap_version_promotion.py — Read `promote_review_seal()` for the only ordinary feedback promotion boundary.](../../../plan_tool/roadmap_version_promotion.py)

## Applicable guardrails

- **The plan’s “## Plan intent”, accepted-head authority:** Document the batch workflow without creating another canonical selector or writer.

- **The plan’s “## Scope guardrails”, exact batch identity:** Preserve the requirement that one candidate has one accepted predecessor and one exact batch identity.

- **The plan’s “## Scope guardrails”, inert candidate state:** Do not describe candidate storage, review, or seals as implicit enrollment or promotion.

- **The plan’s “## Out of scope”, feedback lifecycle changes:** Do not add new feedback states or redefine reviewer-owned transitions while correcting documentation.

- **The plan’s “## Out of scope”, parallel infrastructure:** Do not introduce a new version, candidate, review, recovery, or transaction design through documentation changes.

## Deferred

- Legacy module deletion or consolidation — Keep code removal and any shared lifecycle refactor outside this documentation-only step unless a declared earlier step lands it.

- Broader historical cleanup — Retain dated evidence that remains necessary to interpret an active bug or backlog item; this step only removes records that falsely describe the current ordinary workflow.
