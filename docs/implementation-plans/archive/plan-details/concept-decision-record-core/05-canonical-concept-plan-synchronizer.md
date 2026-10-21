> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Add the canonical concept and plan synchronizer

## Summary

Add `plan_tool/concept_sync.py` as the only supported boundary for publishing concept decisions into both the persisted concept record and the plan Markdown. Extend `plan_tool/parser.py` with reusable body-section replacement and rendering support, and use the existing `plan_tool/schema.py:StepScope` values when an explicit concept source maps to a step. The synchronizer must stage the complete result, preserve unrelated Markdown, detect divergent source edits, and restore the old files if either publication fails. On green, accepted `defer` and `wont_do` decisions appear in the matching plan sections, mapped steps carry the matching scope, and `concepts.json` describes the final plan fingerprint.

## Table of Contents

- [Summary](#summary) — The synchronizer’s role and observable result.
- [Why](#why) — Why concept decisions need one guarded publication boundary.
- [Input](#input) — Contracts supplied by steps 1–3 and existing plan infrastructure.
- [Files (creates vs edits)](#files-creates-vs-edits) — New and changed files in this step.
- [Implementation](#implementation) — Required synchronization, conflict, and rollback behavior.
- [Tests](#tests) — Unit coverage for rendering, mapping, conflicts, and publication failures.
- [Acceptance criteria](#acceptance-criteria) — Behaviors that must hold before completion.
- [References](#references) — Primary documentation for staging, replacement, hashing, and JSON.
- [Deferred](#deferred) — Follow-up work outside this step.

## Why

The concept record and the plan currently have no shared writer that can keep a reviewed decision, its rendered scope prose, its mapped step scope, and its plan fingerprint consistent. Writing either artifact independently can apply a decision to stale prose, lose unrelated Markdown, or leave `concepts.json` describing plan bytes that were never published. This step establishes one conflict-aware synchronization operation so step 6 can orchestrate review without implementing another merge or persistence policy.

## Input

- **Step 1 concept persistence contract:** consume the stable concept record, integrity rules, canonical sidecar path, and serialization outcome owned by step 1 in `plan_tool/concept_tree.py`. Invalid records remain errors; the synchronizer must not replace them with bootstrap output.
- **Step 2 section parser contract:** consume the shared plan-body section representation moved into `plan_tool/parser.py` by step 2. `## Deferred` and `## Out of scope` matching must use that parser rather than a second heading scanner.
- **Step 3 bootstrap contract:** consume deterministic source mappings produced by step 3 in `plan_tool/concept_bootstrap.py`. Only an explicit mapping may change a frontmatter step; titles and fuzzy text are not identifiers.
- **Plan schema:** use `plan_tool/schema.py:Plan`, `plan_tool/schema.py:Step`, and `plan_tool/schema.py:StepScope`. Preserve `Step._scope_status_coherent()` and `Plan._validate_graph()` when applying mapped scope changes.
- **Plan write safeguards:** preserve the compare-and-swap intent of `plan_tool/parser.py:write_plan()` and `plan_tool/parser.py:ConcurrentModificationError`. A synchronization started from one snapshot must not overwrite a later frontmatter or owned-section edit.
- **Fingerprint contract:** compute the final plan fingerprint with the existing `plan_tool/review_persistence.py:compute_plan_fingerprint()` semantics. The fingerprint stored in the concept record must describe the final plan Markdown, not the pre-sync file.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/concept_sync.py` — owns rendering, explicit step mapping, conflict results, staged publication, rollback, and the public synchronization entry point.
  - `tests/test_concept_sync.py` — covers successful synchronization, stale-source conflicts, exact preservation, and failures at each publication boundary.

- **Existing files (edits only):**
  - `plan_tool/parser.py` — expose the shared plan-document and H2-section replacement operations needed to build updated Markdown in memory without writing it early.
  - `plan_tool/schema.py` — add only the narrow schema-level conversion or validation surface needed to apply explicit concept states to the existing `StepScope` vocabulary; do not add persisted fields.
  
## Implementation

The foundational logic is: **publish a concept record and its derived plan changes only when both inputs still match the snapshot used to build them, otherwise return a conflict and leave both files unchanged.**

- **Expose an in-memory plan rewrite in `plan_tool/parser.py`.** Build on the section parser delivered by step 2 and the frontmatter serialization rules in `write_plan()`. The operation should accept a validated `Plan` plus owned section bodies and return complete Markdown while preserving all headings and bodies outside `## Deferred` and `## Out of scope`.
- **Keep section parsing and replacement together.** `plan_tool/create.py:_patch_plan_body_section()`, `plan_tool/create.py:extract_h2_sections()`, and `plan_tool/review.py:split_body_sections()` show existing versions of this logic. Step 2 owns moving the shared parser into `plan_tool/parser.py`; this step should consume and extend that authority, not add another heading regular expression in `plan_tool/concept_sync.py`.
- **Render only decision-owned sections.** Render every concept whose accepted state is `defer` into `## Deferred` and every accepted `wont_do` concept into `## Out of scope`. Preserve deterministic tree order and hierarchy in a stable Markdown form so repeating synchronization produces the same bytes.
- **Keep included concepts out of scope prose.** An `include` decision may affect an explicitly mapped step, but it must not produce a bullet in either owned section.
- **Preserve unrelated Markdown exactly.** Do not rebuild the full plan body from canonical templates. Content before, between, and after the two owned H2 sections must remain unchanged, including custom sections and formatting.
- **Define missing-section behavior explicitly.** The recommended approach is to insert a missing owned section at the plan’s canonical H2 location when that state has rendered concepts, while leaving an absent empty section absent. Use the section-order contract supplied by step 2 rather than guessing from nearby headings.
- **Apply step scope only through explicit source mappings.** Convert mapped concept states to the existing `plan_tool/schema.py:StepScope` values: `include` to `COMMITTED`, `defer` to `DEFERRED`, and `wont_do` to `WONT_DO`. Do not match a step by title, list position, or concept hierarchy.
- **Reject ambiguous mappings.** Treat an unknown step id, multiple decision-bearing concepts mapped to one step with different states, or an invalid source-key shape as a synchronization conflict. Do not choose a winner.
- **Revalidate the whole plan before staging.** Scope changes can violate `Step._scope_status_coherent()` or make `Plan._validate_graph()` reject a committed step that depends on a parked step. Surface these as invalid synchronization input and publish nothing.
- **Make conflicts typed and inspectable.** `plan_tool/concept_sync.py` should distinguish success, source divergence, mapping conflict, invalid state, and publication failure without requiring callers to parse exception text. Step 6 needs these outcomes to assign stable CLI exit behavior.
- **Check both owned sources before publication.** Compare the current plan frontmatter and owned section bodies with the snapshot used to prepare the sync. Also confirm that the on-disk concept record has not changed since it was loaded. A difference is a conflict, not permission to merge automatically.
- **Stage complete outputs before replacing either target.** Serialize and validate the updated `Plan`, render the two owned sections, compute the fingerprint from the complete staged plan bytes, place that fingerprint in the final concept record, and validate the final record before publication.
- **Keep the fingerprint ordering fixed.** The final plan bytes must exist conceptually before the final record is serialized. Computing the fingerprint from the old plan or from a partially updated plan would make the newly written record stale immediately.
- **Publish through one narrow public operation.** A name such as `synchronize_concepts()` is appropriate, but the important contract is that callers provide the current plan snapshot and reviewed tree and receive a typed result. The function owns all decision-bearing writes; callers must not call the step 1 record writer before or after it.
- **Restore prior bytes after a partial failure.** Capture whether each target existed and its exact prior content. If replacement of either target fails after the other was published, restore existing targets and remove targets that were newly created. Report the publication failure only after rollback has been attempted.
- **Provide failure injection at publication boundaries.** An injected replace/publish seam is recommended so `tests/test_concept_sync.py` can fail the first publication, the second publication, and rollback itself without patching global filesystem functions.
- **Preserve parser provenance after success.** A successful plan replacement must refresh the same frontmatter provenance used by `parse_plan()` and `write_plan()`. A failed or rolled-back sync must leave provenance describing the restored file, not staged bytes.
- **Do not claim a filesystem transaction.** Same-directory temporary files and `os.replace()` make each file publication atomic, while explicit rollback provides best-effort coordination across the two targets. Crash-proof multi-file recovery is deferred by the plan.

## Tests

- `test_sync_renders_deferred_and_wont_do_sections` — accepted concepts appear only in their matching owned section.
- `test_sync_omits_included_concepts_from_scope_sections` — included concepts do not render as deferred or out of scope.
- `test_sync_preserves_unrelated_markdown_exactly` — custom headings, prose, and formatting outside owned section bodies remain unchanged.
- `test_sync_is_idempotent` — running synchronization twice with unchanged inputs produces the same plan and record bytes.
- `test_sync_updates_explicitly_mapped_step_scopes` — mapped include, defer, and wont-do concepts set the matching `StepScope`.
- `test_sync_does_not_map_steps_by_title` — an unmapped concept with the same title as a step leaves frontmatter unchanged.
- `test_sync_rejects_conflicting_mappings_without_writes` — different states mapped to one step return a conflict and preserve both files.
- `test_sync_rejects_invalid_plan_scope_graph_without_writes` — schema-invalid scope changes publish neither artifact.
- `test_sync_detects_changed_owned_plan_section` — a concurrent edit to an owned section returns a conflict rather than overwriting it.
- `test_sync_preserves_concurrent_unrelated_body_edit` — a change outside the owned sections survives when the source guards still match.
- `test_sync_detects_changed_concept_record` — a concurrently changed sidecar returns a conflict and leaves the plan untouched.
- `test_sync_stores_fingerprint_of_final_plan` — the persisted fingerprint matches the completed plan after section and scope updates.
- `test_sync_first_publication_failure_leaves_old_files` — failure before any target is replaced preserves both prior artifacts.
- `test_sync_second_publication_failure_rolls_back_first` — failure after one replacement restores both prior artifacts exactly.
- `test_sync_rollback_removes_new_sidecar` — rollback restores the absent state when `concepts.json` did not exist before synchronization.
- `test_sync_refreshes_parser_provenance_after_success` — a later guarded `write_plan()` does not mistake the synchronizer’s own write for an outside edit.

### Test-creation order (feature step)

Add the rendering, explicit-mapping, conflict, final-fingerprint, and publication-boundary tests alongside the corresponding implementation. Start with pure in-memory rendering and mapping cases, then add filesystem publication and rollback cases through the injected failure seam. Every new test in `tests/test_concept_sync.py`, plus affected parser and schema tests, must be green before this step is considered finished.

## Acceptance criteria

- A valid current concept record synchronizes its accepted `defer` and `wont_do` concepts into `## Deferred` and `## Out of scope`.
- Synchronization preserves all Markdown outside the two owned section bodies.
- An explicit deterministic step mapping applies `committed`, `deferred`, or `wont_do` through `plan_tool/schema.py:StepScope`; an unmapped concept never changes a step.
- Conflicting mappings, stale owned sections, a changed concept record, and schema-invalid scope graphs produce typed non-success results and change neither target.
- The synchronized concept record stores the fingerprint of the final plan Markdown.
- Repeating synchronization with unchanged inputs produces the same persisted result.
- Failure at either publication boundary restores both targets to their prior contents or prior absent state.
- `tests/test_concept_sync.py` and the affected `tests/test_parser.py` coverage pass.

## References

- [Python json — JSON Encoder and Decoder](https://docs.python.org/3/library/json.html) — Use the JSON encoder contract when staging and validating the final persisted concept record.
- [Python os — Miscellaneous Operating System Interfaces](https://docs.python.org/3/library/os.html) — Read the `os.replace()` semantics used to publish each staged target atomically.
- [Python tempfile — Generate Temporary Files and Directories](https://docs.python.org/3/library/tempfile.html) — Use same-directory temporary files for staged plan and record outputs.
- [Python hashlib — Secure Hashes and Message Digests](https://docs.python.org/3/library/hashlib.html) — Use deterministic digest behavior for final-plan fingerprint checks.

## Deferred

- Crash-proof recovery across both files — this step provides atomic replacement per file and rollback on observed failures; a durable transaction journal is a separate plan-level decision.
- Automatic conflict resolution — divergent source edits and ambiguous mappings remain operator-visible conflicts.
- General-purpose plan-body editing — the parser support added here serves the synchronizer’s owned sections, not arbitrary Markdown transformations.
- Synchronizer adoption outside `scope-review` — step 6 wires the command; authoring, split, merge, re-ground, and scope-out integrations remain outside this plan.
- Consolidating `plan_tool/create.py:_patch_plan_body_section()`, `plan_tool/create.py:extract_h2_sections()`, and remaining callers onto the step 2 parser API — broaden that cleanup through reconcile after the shared parser contract is stable.
