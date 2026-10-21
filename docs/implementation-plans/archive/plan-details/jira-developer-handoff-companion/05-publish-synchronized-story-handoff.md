> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Publish synchronized story and handoff source files without overwriting human guidance

> **Historical delivery evidence — superseded 2026-08-23.** This detail records
> the completed opt-in companion design. The unified paired-export contract in
> `JIRA_FORMAT.md` replaces its story-only compatibility claims.

## Summary

Add companion-only publication in `plan_tool/jira.py` for the regenerated story source from step 3 and the handoff Markdown from step 4. Stage both texts from the same captured snapshot, then confirm target ownership immediately before replacement. Keep normal `export_jira` and append-mode behavior unchanged when companion mode is not selected. On green, a successful companion run publishes both recognizable generated sources, while unsafe targets and detected concurrent changes stop publication with a clear error.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected surfaces.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why paired publication needs a separate safety boundary.
- [Input](#input) — Captured rendering and ownership contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact file footprint.
- [Implementation](#implementation) — Publication, ownership, and failure rules.
- [Tests](#tests) — Focused publication and non-input regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Filesystem and test-fixture references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain publication.
- [Deferred](#deferred) — Related work left to later steps.

## Why

`plan_tool/jira.py:export_jira` currently renders and writes one story artifact directly, and `plan_tool/jira.py:_export_jira_append` preserves prior ticket text for ordinary exports. Companion mode instead needs to replace a current story source and a generated handoff together from one snapshot, without treating a human file, a Jira-grade authoring artifact, or a changed generated file as safe to overwrite.

## Input

- **Captured companion state:** Step 1 supplies the immutable selected-detail inputs, all-grade detail-artifact paths for collision protection, normalized destinations, target snapshots, pair identity, and prior ownership evidence. Publication must use those captured values rather than rereading plan, detail, or source inputs.

- **Current story source:** Step 3 supplies the regenerated story text, valid dropped-history output, Jira-key carry-forward, and created-ticket update metadata. Do not route companion publication through `plan_tool/jira.py:_export_jira_append`.

- **Generated handoff contract:** Step 4 supplies rendered handoff text plus shared companion provenance writers and strict readers for the handoff and companion-only story source. Use those readers only to recognize generated sources; do not infer ownership from a filename or heading.

- **Existing detail and review boundaries:** `plan_tool/detail.py:_discover_siblings`, `plan_tool/detail.py:_archive_orphan_details`, `plan_tool/review_persistence.py:compute_plan_fingerprint`, and `plan_tool/concept_sync.py:_fingerprint` only inspect the plan-detail bundle. The default companion location must remain outside that input surface.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/jira.py` — Add companion-only staged publication, target protection, final ownership confirmation, and result or error information needed by step 6.
  - `tests/test_jira.py` — Add companion publication, failure, replacement, and target-protection coverage.
  - `tests/test_detail.py` — Prove the generated handoff does not become a detail-authoring sibling or orphan input.
  - `tests/test_review_persistence.py` — Prove the generated handoff does not change the plan fingerprint.
  - `tests/test_concept_sync.py` — Prove the generated handoff does not change concept-sync fingerprinting.

## Implementation

- **Foundational logic — preflight before rendering, then publish only unchanged, recognizable generated targets.** Add a companion-only orchestration path beside `plan_tool/jira.py:export_jira` that performs step 1's read-only target preflight before calling the step 3 model path or step 4 renderer, then accepts their rendered outputs without rereading live inputs or using append-mode preservation.

- **Keep ordinary Jira export unchanged.** Preserve the existing story-only behavior of `plan_tool/jira.py:export_jira`, `plan_tool/jira.py:_export_jira_append`, and `plan_tool/jira.py:JiraResult` for callers that do not request a companion. Any companion result additions must be optional so existing callers retain their current output and write behavior.

- **Preflight both destinations before rendering.** Before model invocation or either renderer, reject a story/handoff collision, either target equal to the plan source or any run- or Jira-grade detail artifact (including an unselected grade), a handoff target inside any plan-detail bundle, either generated target inside the independent Jira-grade authoring lane, and an existing target without recognizable same-plan complete-pair provenance. Resolve paths before comparing them so spelling variants cannot bypass the check. Keep final raw-content confirmation after staging; preflight does not replace it.

- **Require proof before replacing an existing target.** A pre-existing target is writable only when the captured evidence identifies it as the same plan’s generated source for the complete pair of normalized story destination, normalized handoff destination, and format. Reject ordinary Markdown, unrelated generated output, malformed provenance, and either source paired with another destination or format.

- **Serialize paired provenance, then stage both outputs.** Decorate the prepared companion story source and handoff with their format-specific shared provenance before staging. Both must name the same complete pair identity and fingerprint, while the story-only renderer remains unchanged. Write both temporary outputs successfully before either final replacement; `plan_tool/fileio.py:atomic_write_text` is useful single-file precedent, but its immediate replacement is not sufficient for this two-target boundary.

- **Confirm ownership at the final boundary.** After staging and before each final replacement, recheck the target against the captured existence, complete pair identity, and raw-content existence/digest proof. If a target changed after capture, including outside parsed record mappings, abort every replacement that has not started and name the changed target. Do not promise protection from an external write that occurs after its final check.

- **Report partial publication honestly.** Use atomic replacement per target, clean up staged files on success or failure, and surface an actionable `JiraError` when a final write fails. Do not claim atomic two-file publication or silently restore arbitrary target contents; a later companion invocation captures current inputs and regenerates both sources.

- **Keep the handoff out of upstream lanes.** The default location must remain outside the bundle scanned by `plan_tool/detail.py:_discover_siblings`, `plan_tool/review_persistence.py:compute_plan_fingerprint`, and `plan_tool/concept_sync.py:synchronize_concepts`. Do not change those consumers merely to recognize generated handoffs.

- **Do not generalize paired publication here.** `plan_tool/concept_sync.py:synchronize_concepts` has related staged publication and rollback behavior, but it owns plan and concept-sidecar state. Keep this companion-specific instead of coupling the two workflows.

## Tests

### Tests for this step

- `tests/test_jira.py:test_companion_publication_uses_one_captured_snapshot_and_complete_provenance_for_both_sources` — both published files carry the same captured fingerprint and complete pair identity, and reflect captured rather than later-mutated inputs.

- `tests/test_jira.py:test_companion_replaces_current_story_source_instead_of_using_append_mode` — a valid companion rerun regenerates current stories and the handoff rather than preserving append-mode story prose.

- `tests/test_jira.py:test_companion_replaces_only_unchanged_same_plan_complete_pair_targets` — unchanged recognized targets are replaced, while a human-owned, foreign, alternate-destination, or alternate-format target raises before either final write.

- `tests/test_jira.py:test_companion_target_preflight_rejects_any_grade_detail_before_model_or_renderer` — the terminal handoff never enters any detail bundle, neither generated output may occupy independent Jira-grade authoring space, and any-grade detail or ownership failure invokes neither model nor renderer.

- `tests/test_jira.py:test_companion_final_raw_content_change_aborts_unstarted_replacements` — an edit outside parsed record mappings after staging prevents every final replacement that has not begun.

- `tests/test_jira.py:test_companion_second_final_replace_failure_reports_target_and_cleans_staging` — a failure between final replacements reports the failed path, leaves no staged-file residue, and does not claim full publication.

- `tests/test_jira.py:test_companion_next_run_regenerates_both_sources_after_partial_publication` — a later run from current inputs replaces both generated sources without retaining failure state.

- `tests/test_detail.py:test_generated_handoff_is_not_a_detail_sibling_or_orphan` — a handoff under the default `jira-handoffs` root is not discovered, adopted, or archived as a detail artifact.

- `tests/test_review_persistence.py:test_generated_handoff_does_not_change_plan_fingerprint` — creating or changing the generated handoff leaves `compute_plan_fingerprint` unchanged.

- `tests/test_concept_sync.py:test_generated_handoff_does_not_change_concept_sync_fingerprint` — concept synchronization remains based on the plan and its detail bundle, not the terminal handoff.

Every listed case must be green before this step is complete.

## Acceptance criteria

- Companion target preflight refuses an unsafe destination before model invocation or either renderer; after a passing preflight, publication stages story and handoff text from one captured snapshot before either final replacement begins.

- A successful companion run replaces both recognized complete-pair generated sources, serializes matching provenance on each, and exposes both written destinations to its caller.

- A pre-existing unrecognized, foreign, alternate-pair, or raw-content-changed target prevents unsafe replacement and identifies the blocked path.

- The terminal handoff cannot be published inside any plan-detail bundle, and generated outputs cannot overwrite any run- or Jira-grade detail artifact, including an artifact of the unselected grade.

- A failure during a final replacement raises a visible publication error, cleans staged files, and permits a later current-input run to regenerate both sources.

- `tests/test_jira.py`, `tests/test_detail.py`, `tests/test_review_persistence.py`, and `tests/test_concept_sync.py` pass with the new cases.

## References

- [pathlib — Object-oriented filesystem pathshttps: — Read `Path.resolve`, path comparison, and UTF-8 file operations for destination validation.

- [tempfile — Generate temporary files and directorieshttps: — Read staging options for safely preparing both generated outputs before replacement.

- [How to use temporary directories and files in testshttps: — Use isolated target trees for replacement, ownership, and failure fixtures.

## Applicable guardrails

- **The plan’s “## Plan intent”, synchronized source state:** Publish only the story and handoff rendered from step 1’s immutable snapshot.

- **The plan’s step 5 intent, human-owned target protection:** Confirm ownership at publication time and allow replacement only for the exact generated-source relationship the plan permits.

- **The plan’s “## Out of scope”, source-authority boundary:** Keep this work to local generated-source publication; do not broaden it into authoring, plan mutation, external synchronization, or source-conflict decisions.

- **The plan’s “## Risks”, failure and compatibility boundary:** Report final-write failures clearly while retaining ordinary story-only export behavior for callers outside companion mode.

## Deferred

- CLI flags, destination derivation, and operator-facing output — Step 6 owns the public command surface.

- A shared paired-publication abstraction with `plan_tool/concept_sync.py:synchronize_concepts` — defer to reconcile if both workflows later need the same contract.
