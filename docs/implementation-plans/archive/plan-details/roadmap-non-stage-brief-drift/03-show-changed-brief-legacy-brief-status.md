> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Show changed-brief and legacy-brief status in the log-free impact-analysis view

## Summary

Extend impact-analysis inspection so a stored analysis reports `changed-brief` or `legacy-brief` when its current recorded brief no longer has an accepted baseline. Update `plan_tool/roadmap_impact_run.py`’s inspection classifier and make `plan_tool/cli/roadmap_cmd.py` render both as redacted no-route statuses. Keep immutable analysis bytes, evidence storage, telemetry, and source-baseline state unchanged. On green, the view exits successfully while clearly withholding routes and workflows for both statuses.

## Table of Contents

- [Summary](#summary) — States the completed inspection behavior.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Explains why generic unavailable or stale output is not enough.
- [Input](#input) — Defines the upstream baseline classification and existing inspection contract.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the scoped edits.
- [Implementation](#implementation) — Describes status classification, rendering, and immutability boundaries.
- [Tests](#tests) — Names focused unit, CLI, and documentation coverage.
- [Acceptance criteria](#acceptance-criteria) — Lists observable completion conditions.
- [References](#references) — Links to the governing route and source contracts.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s authority and disclosure limits.
- [Deferred](#deferred) — Records work owned by other route steps.

## Why

`plan_tool/roadmap_impact_run.py:current_impact_analysis` currently turns a failed snapshot capture into `unavailable`, while a changed brief can otherwise look like generic stale evidence. Operators need to know that an existing immutable analysis is not current because its brief baseline changed or is unknown, without treating the view as authority to repair that baseline or alter the evidence.

## Input

- **Step 1 baseline result:** Step 1 provides the changed-versus-legacy snapshot classification consumed by `plan_tool/roadmap_impact_run.py:current_impact_analysis`. This step uses that result only to classify inspection output.

- **Stored-analysis contract:** `plan_tool/roadmap_impact_run.py:current_impact_analysis` continues to parse and bind each immutable `ImpactAnalysis` record before it evaluates current state.

- **View contract:** `plan_tool/cli/roadmap_cmd.py:_render_impact_analyses` shares a successfully captured `RoadmapImpactSnapshot` across records in one guarded view call, but `current_impact_analysis` rechecks it before each reuse. A failed capture or cached recheck removes its entry before the record is classified, so later records may capture again.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/roadmap_impact_run.py` — extend `ImpactAnalysisCurrentStatus` and map step 1’s changed and legacy snapshot results in `current_impact_analysis`.
  - `plan_tool/cli/roadmap_cmd.py` — keep `_render_impact_analyses` and `_render_current_impact_analysis` aligned with the closed inspection-status vocabulary and redacted no-route output, and make `--view` help own the changed-brief and legacy-brief policy.
  - `tests/test_roadmap_impact_run.py` — make ordinary roadmap fixtures use a matching accepted digest and cover changed, legacy, stale, and cache-recovery classification.
  - `tests/cli/test_roadmap_cmd.py` — cover rendered changed and legacy rows, successful view exit status, withheld route fields, and log-free redaction.
  - `ROADMAP_FORMAT.md` — document changed and legacy as distinct no-current-route inspection states without changing the immutable analysis schema.
  - `docs/cli/roadmap.md` — regenerate the `--view impact-analyses` behavior for changed and legacy brief baselines from parser help.
  - `tests/test_roadmap_format.py` — bind the documented vocabulary and log-free inspection boundary to `ImpactAnalysisCurrentStatus`.
  - `tests/cli/test_cli_reference.py` — retain the generated CLI-reference drift guard after the `--view` help and reference regeneration.

## Implementation

- **Return closed brief-baseline statuses.** Extend `plan_tool/roadmap_impact_run.py:ImpactAnalysisCurrentStatus` so `current_impact_analysis` returns `changed-brief` for a changed accepted baseline and `legacy-brief` for an absent accepted digest supplied by step 1. Both results must return no `ImpactAnalysis` payload.

- **Keep existing precedence.** `current_impact_analysis` must continue to validate the stored final and load its named receipt before it captures a current roadmap snapshot. Malformed stored data remains `invalid`, unavailable receipt or ordinary snapshot failures remain `unavailable`, and an otherwise valid record whose recomputed candidate differs remains `stale`.

- **Recheck every cached success and evict on failure.** Before a later record uses a cached snapshot, call `recheck_roadmap_impact_snapshot` on that binding. On any recheck failure, remove that slug’s cached snapshot before classifying the current record. A changed or legacy baseline after cache fill must return its matching no-route status, never `current`; an unchanged recheck may reuse the original snapshot. Other recheck failures retain the existing unavailable path, but a later recovered record must perform a fresh capture.

- **Do not cache a refusal.** The `snapshot_cache` contract caches only a successfully captured and successfully rechecked snapshot, not a failed capture or recheck. Changed and legacy baseline results must remain retryable per record so restoring a matching source record during the same view can produce a fresh current result.

- **Render both statuses as no-route evidence.** Have `plan_tool/cli/roadmap_cmd.py:_render_current_impact_analysis` emit the existing redacted non-current shape for `changed-brief` and `legacy-brief`: the status plus the opaque evidence location. It must not emit analysis identity, route, workflow, publication state, brief text, source path, or stored evidence body.

- **Keep inspection read-only.** `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_impact_analyses_view` must preserve its guarded rescan and reader coordination. The new statuses must not publish or rewrite immutable finals, append run-log events, change `source.json`, rebind a baseline, or change the version-2 analysis fields rendered by `plan_tool/roadmap_impact_analysis.py:render_impact_analysis`.

- **Document the distinction at the inspection boundary.** Update `ROADMAP_FORMAT.md:Impact-routing analyses` and the `--view` parser help in `plan_tool/cli/roadmap_cmd.py:register` to identify `changed-brief` and `legacy-brief` as redacted no-current-route outcomes. Regenerate `docs/cli/roadmap.md` with `uv run python -m plan_tool.cli_reference --write`; do not hand-edit the generated reference. Keep the existing successful inspection exit status for all no-route states.

## Tests

- `test_current_analysis_inspection_requires_exact_recomputed_candidate` — update the changed-brief case to assert `changed-brief` and no analysis payload for an otherwise valid stored final.

- `test_current_analysis_classifies_legacy_brief_without_mutating_evidence` — remove the accepted digest after creating a valid final and assert `legacy-brief`, no analysis payload, and unchanged immutable record bytes.

- `test_current_analysis_distinguishes_brief_baseline_status_from_stale_evidence` — assert changed and legacy baseline states do not collapse into `stale`, while unrelated candidate drift retains `stale`.

- `test_current_analysis_never_caches_a_failed_capture` — extend cache-recovery coverage so changed and legacy classifications are not retained after the source returns to a matching baseline.

- `test_current_analysis_rechecks_cached_batch_baseline` — proves a reader-guarded view rechecks every record against its first accepted snapshot.

- `test_current_analysis_evicts_failed_cached_recheck_before_later_recovery` — warm a shared cache, cause a changed, legacy, or ordinary recheck failure, then restore a matching source for a third record; assert the failed recheck removed the entry and the recovered record performs a fresh current capture.

- `test_impact_analysis_accepts_crlf_brief_digest_written_by_stage_admission` — asserts a matching CRLF baseline emitted by stage admission remains acceptable for analysis creation.

- `test_impact_analysis_view_withholds_workflow_for_no_current_route` — include `changed-brief` and `legacy-brief` in the no-route status set and assert neither exposes route, workflow, or publication fields.

- `test_impact_analysis_view_renders_changed_and_legacy_brief_status_without_evidence_disclosure` — assert each status prints the redacted row shape, returns `0`, remains log-free, and does not expose fixture evidence text.

- `test_impact_analysis_documentation_names_the_permitted_writes_and_log_free_view` — update the closed `ImpactAnalysisCurrentStatus` expectation and require the documented no-write boundary to cover both new statuses.

- `TestCliReferenceDrift.test_every_generated_file_matches_disk` — assert the regenerated Roadmap CLI reference matches the landed `--view` help.

### Tests for this step

Every listed test must be green before this step is complete. Run `uv run pytest tests/test_roadmap_impact_run.py tests/cli/test_roadmap_cmd.py tests/cli/test_cli_reference.py tests/test_roadmap_format.py -q`, then run the plan’s full `uv run pytest tests/ -q -n auto` command.

## Acceptance criteria

- A valid stored analysis with a matching accepted brief baseline remains `current` and renders its existing route fields.

- A valid stored analysis with changed current brief text returns `changed-brief` with no analysis payload.

- A valid stored analysis whose present `source.json` lacks `brief_digest` returns `legacy-brief` with no analysis payload.

- `--view impact-analyses` renders both new statuses with only the existing redacted no-route fields, exits `0`, and does not render a route, workflow, publication state, brief text, absolute path, or evidence body.

- Changed and legacy snapshot failures do not enter `current_impact_analysis`’s shared snapshot cache.

- A cached successful snapshot is rechecked before every later record; a changed or legacy baseline after cache fill never renders as `current`.

- Every failed cached recheck removes its shared entry before classification, so a later recovered record does not inherit an earlier `unavailable` result.

- Inspection does not change immutable analysis finals, create evidence, append telemetry, or alter the recorded source baseline.

- `ROADMAP_FORMAT.md`, `docs/cli/roadmap.md`, and `ImpactAnalysisCurrentStatus` use the same changed-brief and legacy-brief vocabulary.

## References

- [BACKLOG.md](BACKLOG.md) — Read the closed route-local brief-drift record for the authority and redaction scope.

- [plan_tool/roadmap_impact_snapshot.py](plan_tool/roadmap_impact_snapshot.py) — Read the snapshot capture and recheck boundary supplied by step 1.

- [plan_tool/roadmap_impact_run.py](plan_tool/roadmap_impact_run.py) — Read `current_impact_analysis` and its successful-snapshot cache contract.

- [ROADMAP_FORMAT.md](ROADMAP_FORMAT.md) — Read the concept-brief lifecycle and impact-analysis inspection contracts.

## Applicable guardrails

- **The plan’s “## Step intent.”** This step may label stale inspection evidence more precisely, but it must not make an unaccepted brief appear current.

- **The plan’s “## Out of scope.”** This step must not add source admission, baseline rebind, new stages, prompts, or broader writer authority.

- **The plan’s “### Contracts and constraints,” digest meaning.** Classify only the decoded-text baseline result supplied by step 1; do not treat source-record or stored-byte digests as interchangeable.

- **The plan’s “### Contracts and constraints,” disclosure boundary.** Preserve the existing redacted inspection output and omit all newly available baseline details.

## Deferred

- Impact-analysis creation refusals and lifecycle telemetry — Step 2 owns pre-publication outcomes; this step only classifies existing immutable finals for inspection.

- Structural-rewrite and root-enrollment brief policies — Steps 4 and 5 own their distinct authority and result contracts.

- Baseline acceptance or same-path rebind — the plan’s out-of-scope boundary and BACKLOG.md #367 retain that operator-intent decision.
