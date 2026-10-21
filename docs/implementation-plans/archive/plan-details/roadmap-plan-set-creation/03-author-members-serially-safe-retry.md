> **Withdrawn 2026-10-16** — Owner correction 2026-10-16: improve existing roadmap mapping to seeds to plans; the separate opt-in plan-set layer exceeds the requested scope. Replacement effort: roadmap-plan-derivation, BACKLOG #496.
> Preserved here for history; do not edit.

# Step 3 — Author members serially with safe retry and preserve completed outputs

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Extend `plan_tool/roadmap_plan_set.py` to persist the validated set and author its members serially through existing create machinery. Keep progress replacement separate from seed and plan creation: only a verified record owned by this set may be replaced. Retry must retain the pinned source, skip recorded completed members and stop on ambiguous existing outputs. Extend `tests/test_roadmap_plan_set.py` to prove interruption recovery, source checks and preservation of completed and unrelated work.

## Table of Contents

- [Summary](#summary) — Deliverables and observable result.
- [Table of Contents](#table-of-contents) — Section navigation.
- [Why](#why) — Why member authoring needs its own recovery boundary.
- [Input](#input) — Upstream records and existing create contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Changes within the declared footprint.
- [Implementation](#implementation) — Serial authoring, ownership and retry rules.
- [Tests](#tests) — Cases that establish safe recovery.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Source contracts and existing owners.
- [Applicable guardrails](#applicable-guardrails) — Limits on authoring behavior.
- [Deferred](#deferred) — Later integration and separate shared work.

## Why

`plan_tool/create.py:create_plan` authors an individual plan and provides its own checkpoints, collision handling and manifest integration. `plan_tool/roadmap.py:materialize_plan_seed` owns a different lifecycle tied to accepted roadmap rows. Neither owns progress across the derived members produced by step 2. The set needs a separate recovery boundary so an interrupted sequence retains its source identity and completed work without treating an existing destination as permission to replace it.

## Input

- **Step 1’s record contract:** Read the landed parser, renderer, structural checks, path helpers and progress fields in `plan_tool/roadmap_plan_set_artifacts.py`. Their actual names and meanings take precedence over suggested names in detail prose; this step must not introduce another persisted schema.
- **Step 2’s validated breakdown:** Consume its complete source-bound record and dependency order. Retry reads the saved breakdown rather than deriving another set around already-authored members.
- **Verified source:** `plan_tool/roadmap_versions.py:load_accepted_version` selects accepted content; `plan_tool/roadmap_versions.py:load_resolved_stored_version` verifies a particular stored version. Use both roles without treating an arbitrary stored version as an accepted selection.
- **Individual authoring:** `plan_tool/create.py:create_plan` accepts `from_existing_path`, `output_dir_override`, `manifest_path`, `replace_on_collision` and `resume`. `plan_tool/create.py:CreateResult` distinguishes an actual `plan_path` from outcomes that produce no plan.
- **Evidence limits:** Fake create calls establish orchestration and preservation rules. They do not establish semantic completeness or the quality of generated member plans.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `plan_tool/roadmap_plan_set.py` — Add set persistence, source-bound seed delivery, serial member authoring and recovery outcomes.
  - `tests/test_roadmap_plan_set.py` — Add ownership, collision, interruption, source-drift and create-boundary tests.

## Implementation

- **Foundational logic: resume only unfinished members of the same source-bound set.** Extend the orchestrator created by step 2; recommend a focused authoring entry point with an injectable create callable. Reuse step 1’s ordering and validation rather than implementing another dependency sorter or progress format.

- **Persist the breakdown before authoring.** Save step 1’s rendered record before the first member call. Subsequent progress writes must preserve set identity, source binding, member definitions, responsibilities and dependency order.

- **Verify ownership before replacing progress.** An existing set-record path must parse, identify the same set and pinned source, and retain the same authoring definition. A matching filename alone must not establish ownership. Reject malformed, foreign or conflicting records without changing them.

- **Separate replacement from creation.** Use `plan_tool/fileio.py:durable_create_text` for new records and seeds where exclusive creation is required; its parent directory must exist. Use `plan_tool/fileio.py:durable_write_text` only for verified owned progress replacement. These helpers provide write mechanics, not ownership checks; never use replacement as a shortcut around a destination collision.

- **Preflight the saved set and destinations.** Before spending authoring calls, run step 1’s structural and destination checks against caller-resolved roots. Reject unrelated existing outputs, directories and symlink conflicts. Recheck the next member’s destinations immediately before its writes; a stale preflight must not authorize an overwrite.

- **Keep the source pinned.** Verify the saved source identity and artifact digests on retry and before further member authoring. If the accepted selection changes or the pinned bundle no longer verifies, stop with an explicit source-drift outcome. Preserve existing outputs and the original binding; never silently switch to the newer head or rederive remaining members.

- **Deliver source-bound member seeds.** Each seed must carry compact set/source attribution, the member’s bounded intent, its responsibilities and consumers, dependencies and unresolved prerequisites. Preserve the accepted prohibitions and eventual acceptance obligations as authoring content. References must identify the pinned source and relevant set context rather than only a mutable accepted-head path.

- **Preserve saved seeds.** Create a member seed once. Reuse an existing seed only when saved ownership and the seed’s source/member binding establish that it belongs to this member; otherwise stop for review. Retry must not regenerate or replace an existing seed, including one the operator edits.

- **Delegate individual creation unchanged.** Read the owned saved seed as UTF-8 immediately before each initial or resumed member call. Pass its current complete text as `from_description` and its path as `from_existing_path` to `plan_tool/create.py:create_plan`, alongside the resolved output location/manifest and `replace_on_collision=False`. `from_existing_path` supplies source identity and does not read the text; do not substitute an earlier in-memory rendering, empty text or path string for `from_description`. Leave `seed_body` unset for this single file-backed source so it cannot override the current saved text. A read/decoding failure prevents the create call and every later member. Retain its native checkpoint, logging and registration behavior. Do not invoke CLI handlers from this module or archive seeds through CLI post-processing.

- **Author one member at a time.** Advance only after the current member returns an actual authored plan and its completed progress is saved. Record the returned destination rather than assuming the requested filename is the result. A `CreateResult.plan_path` of `None`, an exception or an unusable result must stop the sequence and identify uncompleted members.

- **Preserve completed members on retry.** Verify that recorded completed outputs remain present and readable, then skip their create calls. Missing or malformed completed outputs require an explicit recovery outcome; they must not trigger automatic recreation. Valid operator edits to completed plans must remain untouched.

- **Handle the completion-write gap conservatively.** Create can write a plan before the set’s completion update succeeds. If retry finds that plan without a trustworthy completed record, stop and report the ambiguity. Do not overwrite it, delete it or infer successful ownership merely from its expected path.

- **Stop without rolling back useful work.** Member failure or progress-write failure must prevent every later create call. Retain completed plans, saved seeds and the last valid set record. Do not add an outer automatic retry loop around create; explicit retry re-enters this saved state while create owns its internal recovery.

- **Keep registration with its existing owner.** Let `plan_tool/create.py:create_plan` register actual authored plans. The set orchestrator must not register intended paths, seeds or the set record, and must not remove manifest entries during failure cleanup.

## Tests

### Tests for this step

Add these cases in `tests/test_roadmap_plan_set.py`, using temporary repositories and fake authoring calls. Keep step 2’s derivation-only tests unchanged. Every case must be green before completion; run the focused and full suites, and temporarily break preservation and ordering checks to confirm their named tests fail.

- `test_set_record_is_saved_before_first_member_call` — The first authoring call sees the rendered, reloadable breakdown on disk.
- `test_progress_replacement_requires_matching_set_source_and_definition` — Foreign, malformed or changed records remain untouched and prevent authoring.
- `test_initial_record_and_seed_creation_do_not_replace_existing_files` — Exclusive creation preserves conflicting files, including a target appearing after preflight.
- `test_members_run_serially_in_validated_dependency_order` — Each call observes its predecessor’s saved completion before it starts.
- `test_member_seed_preserves_source_ownership_dependencies_and_acceptance` — Seed content and create input retain the member’s supplied obligations and unresolved prerequisites.
- `test_create_receives_saved_seed_and_disallows_collision_replacement` — The adapter passes the exact current saved text in `from_description`, the source path in `from_existing_path`, no overriding `seed_body`, and `replace_on_collision=False`, both initially and on retry; read failures invoke no create call.
- `test_retry_reuses_owned_seed_without_rewriting_operator_edits` — A matching saved seed remains unchanged; an operator edit to its body is passed as the exact resumed `from_description` with the same `from_existing_path`, rather than stale rendered text.
- `test_unowned_or_mismatched_seed_stops_without_changes` — An existing filename cannot establish seed ownership.
- `test_retry_skips_completed_members_and_preserves_edited_plans` — Completed members receive no create calls and their files remain unchanged.
- `test_missing_or_malformed_completed_output_requires_recovery` — Retry reports the inconsistency without recreating the member.
- `test_partial_failure_retains_outputs_and_stops_later_members` — A failed member preserves prior plans and seeds and prevents downstream calls.
- `test_source_drift_stops_before_further_authoring_without_rebinding` — Changed accepted selection or invalid pinned bytes halt initial entry, retry and between-member continuation.
- `test_no_plan_result_does_not_mark_member_complete` — A result without `plan_path` stops the sequence without advancing progress.
- `test_actual_returned_plan_destination_is_recorded` — Completion records the authored path returned by create.
- `test_progress_write_failure_stops_before_next_member` — A failed update leaves the last valid record and completed outputs intact.
- `test_plan_written_before_completion_record_is_preserved_as_ambiguous` — Retry neither adopts nor overwrites an unrecorded existing plan.
- `test_destination_conflicts_fail_before_authoring` — Unrelated files, directories, symlink escapes and protected-source conflicts produce no create calls.
- `test_authoring_leaves_accepted_roadmap_and_seed_state_unchanged` — Derived progress never writes accepted-row lifecycle state.
- `test_registration_contains_only_actual_authored_plans` — A hermetic seam case using real create orchestration with backend proposals stubbed excludes intended-only paths, seeds and set records.

## Acceptance criteria

- Initial and resumed member calls receive the owned saved seed’s current UTF-8 text as `from_description` and its path as `from_existing_path`; unreadable or undecodable seeds stop before member authoring. Tests assert both inputs and preservation of operator body edits.

- Only `plan_tool/roadmap_plan_set.py` and `tests/test_roadmap_plan_set.py` change.
- A saved set reloads through step 1’s contract before any member authoring begins.
- Retry uses the same breakdown and verified source, skips completed members and preserves their plans and seeds.
- Only a verified owned progress record is replaced; conflicting outputs remain unchanged.
- Source drift, member failure and progress-write failure prevent further member calls.
- An existing plan without recorded completion produces an explicit recovery outcome without destructive cleanup.
- Create receives source-bound seeds, disables collision replacement and retains ownership of actual-plan registration.
- `uv run pytest tests/test_roadmap_plan_set.py -q` and `uv run pytest tests/ -q -n auto` pass.

## References

- [BACKLOG.md](../../../BACKLOG.md) — Read entry #496 for the authoring and recovery scope.
- [ROADMAP_FORMAT.md](../../../ROADMAP_FORMAT.md) — Preserve accepted-source authority and existing seed provenance.
- [SEED_FORMAT.md](../../../SEED_FORMAT.md) — Follow the seed content contract without turning seeds into detail bundles.
- [plan_tool/create.py](../../../plan_tool/create.py) — Read `create_plan` and `CreateResult` for collision, checkpoint and registration behavior.
- [plan_tool/fileio.py](../../../plan_tool/fileio.py) — Distinguish exclusive creation from durable replacement.
- [plan_tool/roadmap_versions.py](../../../plan_tool/roadmap_versions.py) — Use accepted selection and verified stored-version reads.

## Applicable guardrails

- **The plan’s “## Scope guardrails,” structural enforcement:** Ownership and retry checks must inspect persisted state, paths and source identity; seed meaning remains judged content.
- **The plan’s “## Out of scope,” existing behavior:** The adapter must preserve ordinary create and accepted-row lifecycle contracts.
- **The plan’s “## Out of scope,” serial authoring:** Keep continuation in one serial loop without worker or merge machinery.
- **The plan’s “## Scope guardrails,” authoring boundary:** Generated seeds must retain obligations without performing the application work they describe.

## Deferred

- CLI dispatch and argument compatibility — Step 4 connects this orchestration to `plan_tool/cli/authoring.py:cmd_create`.
- Recovery documentation and backlog reconciliation — Step 6 documents the landed behavior.
- Changes to `plan_tool/roadmap.py:materialize_plan_seed`, `plan_tool/roadmap_seed_manifest.py` and `plan_tool/roadmap_seed_state.py` — These own accepted-row lifecycle state; derived-set recovery must not change that authority.
- Changes to shared create checkpoints, collision policy or publication behavior in `plan_tool/create.py:create_plan` — Reuse them unchanged; any required shared behavior change needs separate intentional work.
- Semantic decomposition evidence — Step 5 owns the isolated comparison; successful serial authoring does not certify completeness.
