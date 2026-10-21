> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Document source admission and lifecycle, then retire the drift risk

## Summary

Align the roadmap documentation with the source-admission and explicit same-path acceptance behavior delivered by steps 2 and 3. Update the roadmap contract, operator guides, architecture reference, and backlog arcs; remove the resolved risk from `BUG_BACKLOG.md`. Extend `tests/test_roadmap_format.py` with a documentation sweep that keeps the public guidance consistent. On green, readers can tell that changed or legacy brief content fails closed until explicitly accepted as a new baseline, without implying artifact regeneration.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the documentation sweep.
- [Table of Contents](#table-of-contents) — Section map for this detail.
- [Why](#why) — The documentation drift this step removes.
- [Input](#input) — Source-admission and acceptance contracts from earlier steps.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation and test files changed by this step.
- [Implementation](#implementation) — Required source lifecycle guidance and backlog retirement.
- [Tests](#tests) — Drift-guard coverage and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation outcomes.
- [References](#references) — Relevant roadmap source contracts.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries for the documentation sweep.
- [Deferred](#deferred) — Related work outside this documentation step.

## Why

The current guides describe a path-only one-time brief binding, while steps 2 and 3 add a decoded-text baseline, fail-closed admission, lifecycle evidence, and deliberate same-path rebinding. Leaving the old wording in place would tell operators that a changed file at the recorded path is safely reused, recreating the confusion the source-admission work removes.

## Input

- **Step 2 admission outcome:** Treat `plan_tool/roadmap.py:_run_roadmap`, `plan_tool/roadmap_source.py:RecordedBriefSource`, and step 2's landed event contract in `plan_tool/run_log.py` as the authority for initial, matched, and pre-artifact-refusal dispositions. Verify the event's actual class and field names after step 2 ships. `RoadmapSourceResolved` remains the narrower source-selection and read fact.

- **Step 3 acceptance outcome:** Treat the explicit same-path `--from-existing` behavior as a baseline-only acceptance. Read the landed CLI wording and lifecycle result rather than copying proposed names from sibling detail files.

- **Current documentation guard:** `tests/test_roadmap_format.py:_DOC`, `_ROADMAP_ARC`, and `_INTEGRATION_MVP_ARC` already bind roadmap documentation claims to checked-in contracts.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — define the source-record digest, admission states, refusal boundary, and narrow explicit acceptance meaning.
  - `docs/ARCHITECTURE.md` — update **Brief-source persistence** and the roadmap module description to assign source admission and lifecycle ownership accurately.
  - `README.md` — correct the roadmap command overview and lifecycle explanation for changed or legacy source content.
  - `RUNBOOK.md` — update the roadmap operating guidance and lifecycle-event description with the refusal and explicit acceptance route.
  - `USE_CASES.md` — update the roadmap use case so re-entry guidance distinguishes matching, refused, and explicitly accepted content.
  - `docs/how-to/roadmap.md` — explain the operator-visible source lifecycle around first run, failed re-entry, and same-path acceptance.
  - `BUG_BACKLOG.md` — remove the resolved changed-concept-brief risk entry and sweep nearby references that frame it as open.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` — replace the open-risk framing with the shipped source-admission boundary.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-integration-mvp.md` — remove or correct stale operating guidance that assumes the former path-only behavior.
  - `tests/test_roadmap_format.py` — add focused assertions covering the required public-guide source-admission statements.

## Implementation

The foundational logic is: **a recorded brief is admitted only when its decoded text matches the accepted baseline, unless the operator explicitly accepts the current text at the same recorded path.**

- **Describe the source record as content-bound.** Update `ROADMAP_FORMAT.md` so its source and re-entry guidance identifies the recorded brief path and accepted decoded-text digest as separate facts. State that a missing digest on a readable record is a legacy/unknown baseline, not evidence of a match.

- **Make the admission ordering clear.** Document that `plan_tool/roadmap.py:_run_roadmap` completes source admission before artifact loading, stage selection, backend invocation, artifact publication, or seed-state effects. A refused source must leave the existing roadmap artifacts and seed state unchanged.

- **Document eligible initial binding.** State in `ROADMAP_FORMAT.md` that a genuinely absent source-record target can be bound after the first successful artifact, while an existing directory at `source.json` is malformed and refuses before artifact publication rather than being treated as absence.

- **Preserve the one-shot binding boundary.** State in `ROADMAP_FORMAT.md`, `docs/ARCHITECTURE.md`, and the operator guides that a changed brief does not re-ground, regenerate, reconcile, or rewrite an existing roadmap. Explicit acceptance changes only the decoded-text source baseline; semantic changes belong in reviewer feedback on the owning artifact or a successor roadmap lineage.

- **Document the narrow acceptance gesture.** Describe the existing same-path `--from-existing` route from step 3 as an intentional operator choice. The baseline-replacement operation must retain path identity, replace only `source.json`, and cause no artifact, feedback, or seed-state effect itself. It must not imply semantic confirmation of the existing roadmap; any subsequent stage work keeps its ordinary behavior.

- **Keep lifecycle evidence factual and redacted.** Update the lifecycle descriptions in `RUNBOOK.md` and `docs/ARCHITECTURE.md` to include the step-2 admission result and the step-3 accepted-rebind result. Follow `plan_tool/run_log.py:RoadmapSourceAdmission` for dispositions, `RoadmapSourceResolved` for source-selection and read facts, and `RoadmapSourceRecorded` for persistence facts. Guide text may name references, digests, and dispositions, but must not claim that brief text is logged.

- **Match each guide’s role.** Keep `ROADMAP_FORMAT.md` as the normative source and re-entry contract; use `docs/ARCHITECTURE.md` for ownership and ordering; use `README.md`, `RUNBOOK.md`, `USE_CASES.md`, and `docs/how-to/roadmap.md` for concise operator-facing guidance. Do not duplicate a detailed schema across every guide.

- **Retire the risk without erasing the boundary.** Remove the resolved entry headed “A changed concept brief is silently ignored on every stage run after the first” from `BUG_BACKLOG.md`. Update `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` and `docs/implementation-plans/backlog-arcs/backlog-arc-integration-mvp.md` so they describe the current refusal-and-acceptance behavior rather than leaving the risk open.

- **Guard the public claims together.** Add a focused documentation-sweep test in `tests/test_roadmap_format.py`. One approach is to define the exact public guide set near `_STAGE_FEEDBACK_GUIDES`, then assert each required guide distinguishes content drift from path changes and names the explicit acceptance boundary. Keep assertions specific enough to catch a return to path-only wording without forcing identical prose in every document.

## Tests

- `test_source_admission_guidance_sweep_matches_landed_contract` — asserts each selected public guide describes baseline comparison, fail-closed refusal, and explicit same-path acceptance without claiming regeneration, and directs semantic changes to owning-artifact feedback or a successor roadmap lineage.

- `test_source_admission_guidance_keeps_artifact_and_seed_isolation` — asserts the normative contract states that acceptance changes only the source baseline and that refusal does not publish artifacts or alter seed state.

- `test_source_admission_guidance_rejects_non_replaceable_record_target` — asserts the normative contract distinguishes an eligible absent target from an existing `source.json` directory that refuses before artifact publication.

- `test_source_admission_backlog_retirement_is_complete` — asserts `BUG_BACKLOG.md` no longer presents the resolved changed-brief risk as open and roadmap arc guidance reflects the current boundary.

### Verification (non-code step)

1. Run `uv run pytest tests/test_roadmap_format.py -q`.

2. Search the declared documentation files for `source.json`, `changed brief`, `legacy`, `baseline`, and `--from-existing`; confirm every remaining statement matches the landed step-2 and step-3 behavior.

3. Check that references to the retired risk in `BUG_BACKLOG.md`, `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md`, and `docs/implementation-plans/backlog-arcs/backlog-arc-integration-mvp.md` no longer describe it as unresolved.

4. Verify links and heading anchors changed in the documentation remain valid.

## Acceptance criteria

- `ROADMAP_FORMAT.md` states that the recorded source baseline includes a decoded-text digest and that a missing digest is legacy/unknown rather than a match.

- `ROADMAP_FORMAT.md` states that an existing directory at `source.json` is malformed source state and refuses before artifact publication rather than entering initial binding.

- The roadmap guides state that changed or legacy source content is refused before roadmap work begins until an operator deliberately accepts the current text through the documented same-path route.

- The guides state that the explicit baseline-replacement operation updates only the recorded source baseline and causes no artifact, feedback, or seed-state effect itself, while any subsequent stage work keeps its ordinary behavior.

- Operator guidance directs semantic changes to reviewer feedback on the owning artifact or a successor roadmap lineage.

- `docs/ARCHITECTURE.md` identifies `plan_tool/roadmap.py:_run_roadmap` as the source-admission owner and keeps lifecycle facts redacted.

- Public lifecycle guidance assigns admission dispositions to `RoadmapSourceAdmission`, source-selection and read facts to `RoadmapSourceResolved`, and persistence facts to `RoadmapSourceRecorded`.

- `BUG_BACKLOG.md` no longer contains the resolved changed-concept-brief risk as an active item.

- `uv run pytest tests/test_roadmap_format.py -q` passes.

## References

- [BUG_BACKLOG.md — Read the originating changed-concept-brief risk and remove its resolved framing.

- [ROADMAP_FORMAT.md — Keep the normative source, re-entry, and feedback boundaries aligned.

- [docs/ARCHITECTURE.md — Update roadmap ownership and lifecycle descriptions.

- [plan_tool/roadmap.py — Verify `_resolve_brief_path`, `_run_roadmap`, and `_write_brief_source` behavior before documenting it.

- [plan_tool/roadmap_source.py — Verify `RecordedBriefSource`, `read_recorded_brief_source`, and `digest_decoded_text` contracts.

- [tests/test_roadmap_format.py — Extend the existing documentation drift guard.

## Applicable guardrails

- **The plan’s “## Plan intent”, source baseline boundary** — document fail-closed admission and explicit acceptance without suggesting that existing artifacts were regenerated.

- **The plan’s “## Step intent”, documentation alignment** — limit work to keeping source-persistence descriptions and risk tracking accurate.

- **The plan’s “## Out of scope”, roadmap mutation boundaries** — do not introduce a new acceptance surface, change stage behavior, or expand the source model while documenting this work.

- **The plan’s “## Out of scope”, candidate and feedback boundaries** — do not change candidate lineage checks, feedback semantics, artifact gates, retries, or path-identity rules.

## Deferred

- Multi-source and role-tagged upstream inputs — remain with the AI-DLC intake evolution work because this step documents the current single-source boundary only.

- Artifact regeneration after a brief change — remains outside the plan because baseline acceptance does not establish semantic agreement between existing artifacts and revised brief text.
