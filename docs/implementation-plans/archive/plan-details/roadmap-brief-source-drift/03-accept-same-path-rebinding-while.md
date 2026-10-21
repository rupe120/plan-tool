> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Accept same-path rebinding while isolating the baseline operation from artifact and seed effects

## Summary

Extend `--from-existing` so an explicit path that resolves to the already-recorded brief can accept a legacy or changed decoded-text baseline. Update `plan_tool/roadmap.py` to replace only `source.json` atomically, report the `accepted-rebind` source-admission result, and return a fact the CLI can render alongside the ordinary stage result. Update `plan_tool/run_log.py`, `plan_tool/cli/roadmap_cmd.py`, `plan_tool/cli/__init__.py`, `docs/cli/roadmap.md`, and the top-level help snapshot to describe this narrow operation accurately. On green, the baseline replacement itself rewrites no roadmap artifact and alters no draft or promoted seed state; after it completes, the same invocation continues through the existing stage routes.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the baseline-only acceptance change.
- [Table of Contents](#table-of-contents) — Section map for this detail.
- [Why](#why) — Why fail-closed brief admission needs an explicit recovery action.
- [Input](#input) — Step 2 source-admission contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — In-scope source, test, and documentation changes.
- [Implementation](#implementation) — Required same-path rebinding behavior and boundaries.
- [Tests](#tests) — Focused regression coverage for acceptance, isolation, and reporting.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant roadmap source and lifecycle contracts.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this recovery path.
- [Deferred](#deferred) — Related work outside this implementation.

## Why

Step 2 blocks a roadmap when its recorded brief is legacy or its decoded text no longer matches the accepted digest. An operator needs one explicit way to accept the text now present at that same path, but that acceptance cannot make existing artifacts appear regenerated or make dependent seeds appear current.

## Input

- **Step 2 admission contract:** Use step 2’s landed `plan_tool/roadmap_source.py:RecordedBriefSource` and `plan_tool/roadmap.py:_run_roadmap` admission result as the authority for recorded-path identity, legacy baseline absence, and digest mismatch. Read the landed names and fields rather than duplicating source-record parsing in this step.

- **Step 2 lifecycle contract:** Extend step 2's landed source-admission event and writer surface in `plan_tool/run_log.py` with the accepted-rebind disposition. Verify their actual names and fields after step 2 ships. Preserve the redaction boundary: lifecycle records contain safe references and digest facts, never brief text.

- **Existing writer boundary:** `plan_tool/roadmap.py:_write_brief_source` and `plan_tool/fileio.py:atomic_write_text` already define durable source-record publication. Rebinding must use the same atomic replacement boundary.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — identify the explicit same-path rebind route, replace the source baseline atomically, return a baseline-only result, and emit its admission fact.
  - `plan_tool/run_log.py` — admit `accepted-rebind` in the existing source-admission event and writer surface.
  - `plan_tool/cli/__init__.py` — describe the same-path `--from-existing` recovery gesture in the command catalog.
  - `plan_tool/cli/roadmap_cmd.py` — keep CLI forwarding thin and render a distinct baseline-only success summary.
  - `tests/test_roadmap.py` — cover same-path acceptance, atomic source replacement, and artifact and seed isolation.
  - `tests/test_run_log.py` — cover accepted-rebind event construction and serialized fields.
  - `tests/cli/test_roadmap_cmd.py` — cover forwarding, baseline-only output, and unchanged conflicting-option behavior.
  - `tests/cli/package_surface_help.golden.txt` — refresh the intentional command-catalog wording.
  - `DATA_CONTRACT.md` — document the accepted-rebind disposition and what it does not claim.
  - `docs/cli/roadmap.md` — describe when the existing flag accepts a same-path baseline and its non-regeneration boundary.

## Implementation

The foundational logic is: **an explicit recorded-path request accepts only the current decoded-text baseline before ordinary roadmap work continues.**

- **Keep path identity strict.** In `plan_tool/roadmap.py:_resolve_brief_path` and its caller, preserve the existing refusal for a `--from-existing` path that does not resolve to the recorded brief path. The same-path gesture is the only rebind route; it must not become an alternate-source or path-migration feature.

- **Make explicit same-path rebinding a baseline-only operation.** When step 2’s source admission finds a legacy baseline or a changed digest and the caller explicitly supplies the same resolved path, record the current decoded-text digest as the accepted baseline before `_load_and_regate_below`, `_load_predecessors`, stage prompt rendering, or the stage invoker. Once the rebind succeeds, continue through the same ordinary stage path the invocation would use for a matched source; do not give the baseline write any artifact or seed authority of its own.

- **Do not make a match noisy.** An explicitly supplied same path whose recorded digest already matches must retain normal stage-run behavior. The rebind route exists only to recover from step 2’s refusal states; it must not turn every explicit re-entry into a no-op.

- **Preserve atomic source replacement.** Extend `plan_tool/roadmap.py:_write_brief_source`, or use a focused sibling at that boundary, so the persisted path and accepted digest replace `source.json` through `plan_tool/fileio.py:atomic_write_text`. Do not write a partial record or mutate an existing record before the complete replacement is ready.

- **Keep the baseline operation isolated from non-source state.** The source-record replacement itself must not call `publish_stage_artifact`, `publish_roadmap_generation`, `write_seed_state`, draft-seed materialization, or seed invalidation paths. After it completes, ordinary feedback, gate, retry, publication, and seed behavior remains unchanged; any resulting effects belong to those existing routes rather than the rebind.

- **Return a fact, not a synthetic stage outcome.** Extend `plan_tool/roadmap.py:RoadmapResult`, or introduce the smallest result fact needed by its existing caller, so `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` can report accepted rebinding alongside the invocation's ordinary `OUTCOME_COMPLETED` or `OUTCOME_COMPLETED_NO_CHANGE` result. Do not represent the rebind itself as a written stage or artifact count.

- **Extend the existing admission event.** Add `accepted-rebind` to the source-admission disposition established in step 2 and emit it before the operation returns. Keep `RoadmapSourceResolved` for source selection and `RoadmapSourceRecorded` for first successful artifact publication; do not overload either event to claim this acceptance created an artifact.

- **Render the operator-visible boundary plainly.** Add one note near `plan_tool/cli/roadmap_cmd.py:_print_completed` and `_print_completed_no_change` that says the baseline was accepted without artifact or seed effects of its own, then render the ordinary stage outcome. The same note directs semantic changes to reviewer feedback on the owning artifact or to a successor roadmap lineage. Continue to use existing CLI error and exit-code handling.

- **Update one flag’s explanation everywhere.** Align the `--from-existing` help in `plan_tool/cli/roadmap_cmd.py:register`, the roadmap catalog in `plan_tool/cli/__init__.py`, `docs/cli/roadmap.md`, and `tests/cli/package_surface_help.golden.txt`. State that a same recorded path can explicitly accept a refused legacy or changed baseline, while a different path remains refused.

## Tests

- `test_same_path_changed_digest_rebinds_before_ordinary_feedback_work` — `tests/test_roadmap.py` asserts that an explicit recorded path accepts changed decoded text before an existing open-feedback route invokes and publishes through ordinary stage behavior.
- `test_same_path_legacy_record_rebinds_before_feedback_free_reentry` — `tests/test_roadmap.py` asserts that a valid path-only legacy record gains the accepted digest before the existing feedback-free path re-gates its artifact.
- `test_same_path_matching_digest_keeps_normal_stage_behavior` — `tests/test_roadmap.py` asserts that an already matching explicit path does not take the rebind route.
- `test_different_explicit_brief_remains_refused_before_rebind` — `tests/test_roadmap.py` preserves the recorded-path identity rule and invoker-unreachable ordering.
- `test_rebind_replaces_source_record_atomically` — `tests/test_roadmap.py` asserts that the resulting `source.json` contains the recorded path and current accepted digest through the existing atomic write boundary.
- `test_rebind_has_no_independent_artifact_or_seed_authority` — `tests/test_roadmap.py` observes the boundary immediately after source-record replacement and asserts the rebind itself changes no artifact, draft-seed, promoted-seed, or seed-state bytes before ordinary stage processing resumes.
- `test_accepted_rebind_lifecycle_event_is_redacted` — `tests/test_roadmap.py` asserts the run log contains the accepted-rebind admission fact and no brief body.
- `test_roadmap_source_admission_serializes_accepted_rebind` — `tests/test_run_log.py` constructs the landed admission event with the new disposition and verifies its JSONL record.
- `test_same_path_rebind_is_forwarded_to_run_roadmap` — `tests/cli/test_roadmap_cmd.py` asserts `cmd_roadmap` forwards the existing `from_existing` argument without adding a second acceptance flag.
- `test_rebind_summary_separates_baseline_fact_from_stage_outcome` — `tests/cli/test_roadmap_cmd.py` asserts successful output names the accepted baseline without attributing any ordinary stage artifact or seed effect to it and directs semantic changes to owning-artifact feedback or a successor roadmap lineage.
- `test_rebind_keeps_existing_mode_conflicts` — `tests/cli/test_roadmap_cmd.py` preserves the current rejection of incompatible roadmap modes.
- `test_package_surface_help_matches_catalog` — `tests/cli/test_roadmap_cmd.py` remains green after refreshing `tests/cli/package_surface_help.golden.txt`.

### Tests for this step

Every test listed above must be green before this step is finished. Run the focused roadmap, run-log, and CLI suites, including the package-help assertion, before accepting the change.

## Acceptance criteria

- An explicit `--from-existing` path that resolves to the recorded brief path accepts a legacy or changed decoded-text baseline only when step 2 would otherwise refuse it.
- The accepted source record contains the same recorded path and the digest for the currently decoded brief text.
- The baseline replacement completes before artifact loading and has no independent artifact-publication, seed-invalidation, seed-state, draft-seed, or promoted-seed effect; the same invocation then retains ordinary stage behavior.
- A matching explicit same path retains ordinary roadmap behavior rather than reporting a rebind.
- A different explicit path remains refused before backend work.
- The accepted-rebind source-admission event is persisted without brief text and is documented in `DATA_CONTRACT.md`.
- CLI output separates the baseline change from the ordinary stage outcome, does not attribute any artifact or seed effect to the rebind itself, and directs semantic changes to reviewer feedback on the owning artifact or a successor roadmap lineage.
- `tests/test_roadmap.py`, `tests/test_run_log.py`, and `tests/cli/test_roadmap_cmd.py` are green.

## References

- [Roadmap Brief Source Drift plan — Read the plan intent, step boundary, and declared files for this recovery route.
- [BUG_BACKLOG.md — Read the originating changed-concept-brief risk that this step closes.
- [DATA_CONTRACT.md — Read the landed source-admission, source-resolution, and source-record lifecycle contracts.
- [ROADMAP_FORMAT.md — Read the source and re-entry rules that prevent acceptance from implying regeneration.
- [docs/ARCHITECTURE.md — Read the brief-source persistence ownership boundary.

## Applicable guardrails

- **The plan’s “## Step intent”, deliberate acceptance only:** Limit this work to accepting the current text as a source baseline. The result must not say that existing roadmap content now reflects that text.

- **The plan’s “## Out of scope”, no automatic artifact work:** Do not add regeneration, reconciliation, or artifact rewrite behavior to `plan_tool/roadmap.py` or the CLI route.

- **The plan’s “## Out of scope”, no new acceptance surface:** Reuse explicit same-path `--from-existing`; do not add a flag, prompt, or interactive branch.

- **The plan’s “## Out of scope”, preserve source identity and stage behavior:** Keep different-path refusal, candidate-lineage checks, feedback behavior, stage gates, retries, and exit behavior unchanged.

## Deferred

- Automatic regeneration or reconciliation after acceptance — the plan’s “## Out of scope” keeps artifact meaning separate from source-baseline acceptance.
- Multi-source and role-tagged source records — the plan’s “## Out of scope” routes that broader source model to the AI-DLC intake evolution work.
- Candidate-lineage source changes and feedback-rule changes — the plan’s “## Out of scope” preserves those independent contracts.
