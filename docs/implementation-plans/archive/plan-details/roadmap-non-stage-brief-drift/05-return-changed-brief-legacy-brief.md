> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Return changed-brief and legacy-brief enrollment refusals before version and accepted-head writes

## Summary

Extend `plan_tool/roadmap.py:enroll_roadmap_root` so changed and legacy recorded briefs return distinct closed enrollment refusals instead of reaching immutable-version publication. Update `plan_tool/cli/roadmap_cmd.py` to render those redacted outcomes and return status `1`; successful enrollment keeps its current version-id output. Preserve the existing writer guard, recovery-first ordering, final snapshot recheck, and publication journal cleanup. On green, neither refusal creates version members, changes the accepted head, or leaves a pending-generation journal.

## Table of Contents

- [Summary](#summary) — States the completed enrollment behavior.
- [Table of Contents](#table-of-contents) — Lists the detail sections in order.
- [Why](#why) — Explains why root enrollment needs its own brief-drift policy.
- [Input](#input) — Defines the snapshot and publication contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the scoped code, tests, and documentation edits.
- [Implementation](#implementation) — Describes the refusal boundary and preserved writer behavior.
- [Tests](#tests) — Names focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Lists observable completion conditions.
- [References](#references) — Links to the governing route and source contracts.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s authority and disclosure limits.
- [Deferred](#deferred) — Records adjacent routes and shared work outside this step.

## Why

`plan_tool/roadmap.py:enroll_roadmap_root` turns a live roadmap into immutable authority, but its current snapshot failure path does not distinguish a changed accepted brief from a legacy source record. Root enrollment must not make that authority claim until step 1 confirms the recorded decoded-text baseline, including during the final writer-window recheck.

## Input

- **Step 1 snapshot classification:** `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot` and `plan_tool/roadmap_impact_snapshot.py:recheck_roadmap_impact_snapshot` provide the changed-versus-legacy result this route consumes. This step selects the root-enrollment policy; it does not recreate the comparison.

- **Source meaning:** `plan_tool/roadmap_source.py:read_recorded_brief_source` supplies the accepted decoded-text `brief_digest`. Keep it separate from the raw source-record digest and the stored immutable-brief digest.

- **Root publication:** `plan_tool/roadmap_versions.py:prepare_root_version_from_snapshot` and `plan_tool/roadmap_versions.py:build_root_enrollment_generation` prepare the immutable members only after admission succeeds.

- **Writer window:** `plan_tool/roadmap_revision_publish.py:recover_roadmap_publication` and `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation` own guarded recovery, durable journal creation, final-recheck ordering, replacement, and journal cleanup.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — extend `ImmutableRootEnrollmentResult` and `enroll_roadmap_root` with closed changed-brief and legacy-brief refusals.
  - `plan_tool/cli/roadmap_cmd.py` — update `_cmd_roadmap_enroll_version` and `_render_immutable_root_enrollment_result` to render redacted enrollment outcomes and map refusal status, and make `--enroll-version` help own the refusal policy.
  - `tests/test_roadmap.py` — cover initial capture and final-recheck refusals, recovery ordering, and pending-journal cleanup.
  - `tests/cli/test_roadmap_cmd.py` — cover changed and legacy CLI output, status `1`, and unchanged successful output.
  - `ROADMAP_FORMAT.md` — document root enrollment’s brief-baseline prerequisite and its no-write refusal boundary.
  - `docs/cli/roadmap.md` — regenerate `--enroll-version`’s changed-brief and legacy-brief behavior from parser help.
  - `tests/test_roadmap_format.py` — bind the documented enrollment policy to the source and immutable-authority contracts.
  - `tests/cli/test_cli_reference.py` — retain the generated CLI-reference drift guard after the `--enroll-version` help and reference regeneration.

## Implementation

- **Foundational logic: root-enrollment brief-baseline refusal classification.** Make `plan_tool/roadmap.py:enroll_roadmap_root` map only step 1’s distinct changed and legacy classifications to closed enrollment results. Do not infer either case from exception text, and do not turn malformed, unreadable, gate-invalid, or other snapshot failures into either refusal.

- **Keep the refusal result safe to render.** Evolve `plan_tool/roadmap.py:ImmutableRootEnrollmentResult` so callers can distinguish successful enrollment from `changed-brief` and `legacy-brief` without a version id on a refusal. Only a successful result may expose a version identity.

- **Preserve the existing ordering.** Keep `_roadmap_writer_owner`, `_require_root_enrollment_recovery_only`, `recover_roadmap_publication`, and `is_roadmap_enrolled` ahead of snapshot capture. An interrupted eligible root-enrollment generation must still recover before a new attempt decides brief status; an already enrolled roadmap must retain its existing refusal instead of being reclassified from its current source.

- **Stop before immutable publication on initial capture.** When the initial capture reports either brief state, return the closed refusal before `prepare_root_version_from_snapshot`, `build_root_enrollment_generation`, or `publish_roadmap_generation`. Do not write immutable version members, an accepted-head selector, a source baseline, stage artifact, seed state, or a journal.

- **Apply the same policy at the final recheck.** Retain `enroll_roadmap_root`’s final call to `recheck_roadmap_impact_snapshot` through `publish_roadmap_generation`’s `before_replace` seam. If the brief becomes changed or legacy after capture, return the same closed refusal before member replacement or accepted-head publication.

- **Reuse publication cleanup unchanged.** `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation` already writes the journal before final recheck and removes it when that recheck raises. Keep that sequence intact; do not add a root-enrollment-specific journal protocol or leave a recoverable journal behind for a safe brief refusal.

- **Keep CLI output redacted.** Have `plan_tool/cli/roadmap_cmd.py:_render_immutable_root_enrollment_result` print the closed outcome and status for refusals, with no brief text, source path, digest, journal detail, or version id. Map `changed-brief` and `legacy-brief` to status `1`; retain current usage-error handling and the successful `enrolled version:` output.

- **Document the two digest roles precisely.** In `ROADMAP_FORMAT.md` and the `--enroll-version` parser help in `plan_tool/cli/roadmap_cmd.py:register`, describe the admission check as the step 1 decoded-text baseline check. Regenerate `docs/cli/roadmap.md` with `uv run python -m plan_tool.cli_reference --write`; do not hand-edit the generated reference. Do not describe the immutable stored-brief byte digest in `plan_tool/roadmap_versions.py` as the source-admission baseline.

## Tests

### Tests for this step

- `test_immutable_root_enrollment_refuses_unaccepted_brief_before_version_or_head_writes` — parameterizes changed and legacy initial snapshots and leaves immutable storage, accepted head, artifacts, seed state, and journal absent.

- `test_immutable_root_enrollment_final_recheck_brief_refusal_cleans_journal` — parameterize changed and legacy final-recheck failures; assert the journal exists during the recheck, then is removed without version-member or accepted-head writes.

- `test_immutable_root_enrollment_recovers_before_brief_refusal` — preserve recovery-shape validation and guarded recovery before the route evaluates the new brief state.

- `test_immutable_root_enrollment_preserves_non_brief_snapshot_failures` — malformed or unrelated snapshot failures retain the existing error path rather than becoming a closed brief refusal.

- `test_root_enrollment_accepts_crlf_brief_digest_written_by_stage_admission` — asserts a matching CRLF baseline emitted by stage admission retains ordinary immutable-root enrollment.

- `test_enroll_version_cli_renders_redacted_brief_refusal_with_status_one` — parameterize both refusal outcomes and assert status `1`, no version-id line, and no sensitive source facts.

- `test_enroll_version_dispatches_without_backend_or_stage_run` — retain successful dispatch, version-id output, and the no-stage/no-backend boundary.

- `test_enroll_version_help_describes_brief_refusals` — keep parser help aligned with the documented changed-brief and legacy-brief enrollment behavior.

- `test_root_enrollment_brief_refusal_guidance_matches_source_admission_contract` — assert `ROADMAP_FORMAT.md` distinguishes the decoded-text admission baseline, the two refusal states, and the no-write root-enrollment boundary.

- `TestCliReferenceDrift.test_every_generated_file_matches_disk` — assert the regenerated Roadmap CLI reference matches the landed `--enroll-version` help.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap.py:enroll_roadmap_root` returns distinct `changed-brief` and `legacy-brief` results for step 1’s initial-capture classifications.

- The same two results are returned when the final recheck detects those states after journal creation but before immutable member replacement.

- Both refusal results leave no accepted-head selector, immutable version members, or pending-generation journal.

- Successful root enrollment retains guarded recovery, final recheck, immutable member publication, and `enrolled version:` output.

- `plan-tool roadmap <slug> --enroll-version` renders each refusal without brief text, paths, digests, or version ids and exits with status `1`.

- `ROADMAP_FORMAT.md`, `docs/cli/roadmap.md`, and their focused tests state that root enrollment uses the decoded-text source baseline rather than the stored immutable-brief byte digest.

## References

- [BACKLOG.md closed route-local brief-drift record](../../../../../BACKLOG.md) — Read the route-specific non-stage brief-drift scope.

- [Roadmap AI-DLC integration delivery handoff](../../../../../handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md) — Read the delivery order and writer-scope boundary.

- [plan_tool/roadmap_impact_snapshot.py](../../../../../plan_tool/roadmap_impact_snapshot.py) — Read the capture and recheck classification seam from step 1.

- [plan_tool/roadmap.py](../../../../../plan_tool/roadmap.py) — Read `enroll_roadmap_root` and its current immutable-root lifecycle.

- [ROADMAP_FORMAT.md](../../../../../ROADMAP_FORMAT.md) — Read the source identity and immutable accepted-head contracts.

## Applicable guardrails

- **The plan’s “## Step intent”:** Limit this work to preventing root enrollment from claiming authority over a changed or unknown brief baseline. Do not change another non-stage route’s policy.

- **The plan’s “## Out of scope”:** Do not add generic source admission, baseline rebinding, stage-run changes, prompts, stages, semantic re-grounding, or broader rewrite authority.

- **The plan’s “### Contracts and constraints,” digest meaning:** Use step 1’s decoded-text comparison and keep raw source-record and immutable stored-brief evidence separate.

- **The plan’s “### Contracts and constraints,” writer-window rule:** Preserve capture and final recheck under the existing writer guard before any immutable enrollment claim.

- **The plan’s “### Contracts and constraints,” disclosure rule:** Keep API results, CLI output, and documentation redacted to the route’s existing safe facts.

## Deferred

- `plan_tool/roadmap_impact_run.py` and `plan_tool/roadmap_structural_revision_run.py` — steps 2 through 4 own their separate changed-brief and legacy-brief policies.

- `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation` — retain its shared final-recheck cleanup behavior; changing publication protocol is outside this focused route change.

- Broad operator-guide updates and `BACKLOG.md` closure — step 6 owns the cross-route documentation sweep.

- A generic non-stage source-admission or baseline-rebind mechanism — excluded by the plan’s route-specific authority boundary.
