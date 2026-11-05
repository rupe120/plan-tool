> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Default the --compare target to the active candidate and refuse without --comparison-target when none is active

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step removes the working-tree snapshot loader from `plan_tool/roadmap_compare_run.py`. An omitted `--comparison-target` now resolves to the active candidate named by the candidate admission pointer. When no candidate is active, `--compare` refuses with an error that tells the operator to pass `--comparison-target`. An omitted `--comparison-base` still means the accepted head. A folder with no accepted head is refused with step 6's no-published-version error. The CLI help for `--compare` and `--comparison-target` in `plan_tool/cli/roadmap_cmd.py` changes to match. On green, `--compare` never reads top-level `0N-*.md` files, so a promoted change cannot show up as reverted against stale files.

## Table of Contents

- [Why](#why) — what the working-tree target gets wrong after promotion
- [Input](#input) — what steps 3 and 6 supply and what tests cannot show
- [Files (creates vs edits)](#files-creates-vs-edits) — the four files edited
- [Implementation](#implementation) — target resolution, refusals, constraints
- [Tests](#tests) — cases per behavior and invariant
- [Acceptance criteria](#acceptance-criteria) — observable end state
- [References](#references) — docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves to other steps

## Why

- `_resolve_target_snapshot` falls back to `_load_working_snapshot` when no target id is given. That function reads the top-level artifact files under `roadmap_dir`.
- After step 3, a first run writes no top-level files. A hand-converted or older folder can still hold stale ones.
- Promotion moves the accepted head forward in the version store only. A compare against a stale top-level bundle then shows the promoted changes as reverted.
- The plan wants one stored copy of roadmap content that every command reads. The natural default target for "what is pending against the head" is the active candidate.

## Input

- **Step 3 output:** every roadmap has a root version and an accepted head, and no top-level `0N-*.md` files are written. Take the "no head" meaning from step 3's refusal wording.
- **Step 6 output:** `NoPublishedRoadmapVersionError` in `plan_tool/roadmap_seed_manifest.py`. Read its landed name, base class, and message from that module. The landed names win over any name in this detail.
- **Admission pointer:** `plan_tool/roadmap_candidate_run.py:load_candidate_admission(plans_dir=, slug=)` returns `CandidateProposalAdmission | None`. Its `active_candidate_version_id` is the active candidate, or `None` when none is active. It can raise `CandidateProposalError` for an unreadable or mismatched record.
- **Existing resolvers (unchanged):** `load_accepted_version` and `load_resolved_stored_version` in `plan_tool/roadmap_versions.py`.
- **Limit:** tests build a version store from literal records. They cannot show how the default reads on a real Integration store with a live candidate. The post-ship hand run covers that.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_compare_run.py` — remove `_load_working_snapshot`. Remove `"working"` from the `kind` Literal on `RoadmapComparisonSnapshot` and on `_build_snapshot`. Make `_resolve_target_snapshot` default to the active candidate. Make `_resolve_base_snapshot` raise the step 6 error when there is no accepted head. Update the `run_roadmap_comparison` docstring. Drop the `roadmap_dir` import and `OSError` handling if nothing else uses them.
  - `plan_tool/cli/roadmap_cmd.py` — make `_cmd_roadmap_comparison` report the step 6 error through the same rc 2 path as `RoadmapComparisonRunError`. Update the help text on `--compare` and `--comparison-target`.
  - `tests/test_roadmap_compare_run.py` — replace the working-bundle cases (see Tests).
  - `tests/cli/test_roadmap_cmd.py` — update `test_comparison_default_target_uses_the_read_only_operation` and add the refusal-reporting case.

## Implementation

**Behavior that must hold when the step is done:**

- **Default target.** With no target id, the target is the stored version named by `load_candidate_admission(...).active_candidate_version_id`, resolved through `load_resolved_stored_version`. It is a normal `candidate` snapshot, so `_bound_prose_amendment_evidence` binds prose amendments the same way as for an explicit candidate id.
- **No active candidate.** When the admission record is missing, or its `active_candidate_version_id` is `None`, raise `RoadmapComparisonRunError`. The message must name `--comparison-target` and say no candidate is active. No Git process is spawned before this refusal.
- **Missing head.** When no base id is given and `load_accepted_version` returns `None`, raise step 6's no-published-version error. An explicit `--comparison-base` that names an unknown version keeps its current error path.
- **No top-level reads.** No code in this module reads `<roadmap folder>/0N-*.md`. The `"working"` snapshot kind no longer exists anywhere in this module.
- **Explicit ids unchanged.** An explicit base and target still read only the version store.

**Recommended approach:**

- Keep the change inside `_resolve_target_snapshot`: when `version_id` is `None`, look up the admission pointer, then reuse the explicit-id branch with the pointer's id.
- Let `CandidateProposalError` from `load_candidate_admission` surface as a refusal. Either wrap it in `RoadmapComparisonRunError` inside `run_roadmap_comparison`'s existing `except` tuple, or add it to the CLI's catch list. Pick one; the CLI must exit rc 2 either way.
- Rejected alternative: default the target to the accepted head and the base to its predecessor. It changes what an omitted `--comparison-base` means and goes past this step's intent.
- Rejected alternative: fall back to the working tree when no candidate is active. That keeps the stale-file defect the step removes.

**Constraints:**

- **Order of refusals.** Resolve the base before the target, so a folder with no head reports the no-published-version error and not "no active candidate".
- **Read-only.** The operation must not write any roadmap or Git state, as today.
- **Callers of the `kind` Literal.** `plan_tool/roadmap_compare_render.py` serializes `snapshot.kind` generically. Grep `plan_tool/` and `tests/` for `"working"` before finishing. Any hit outside this step's four files is routed to Deferred, not edited here.
- **Help text.** The `--compare` help must say the default target is the active candidate and that it needs `--comparison-target` when none is active. Remove the "working roadmap" wording from both options.

## Tests

### `tests/test_roadmap_compare_run.py`

- `test_default_target_is_the_active_candidate` — with an accepted head and an active admission pointer, an omitted target yields a `candidate` snapshot whose `version_id` is the pointer's id, and the base is the accepted head.
- `test_no_active_candidate_refuses_naming_comparison_target` — an admission pointer with `active_candidate_version_id` of `None` raises `RoadmapComparisonRunError` whose message names `--comparison-target`.
- `test_missing_admission_record_refuses_naming_comparison_target` — no admission file at all gives the same refusal.
- `test_refusal_without_active_candidate_spawns_no_git_process` — monkeypatch the Git capture to fail the test if called; the refusal happens first.
- `test_no_accepted_head_raises_the_no_published_version_error` — an empty store and an omitted base raise step 6's error, not the active-candidate refusal.
- `test_top_level_artifact_files_are_never_read` — write stale top-level files with `_write_working`, delete or break them, and show the result is unchanged. This pins that the working-tree loader is gone, not only unused.
- `test_default_target_binds_prose_amendment_evidence_like_an_explicit_candidate` — the default target takes the same `bound` path as an explicit candidate id.
- Rewrite or remove the cases that compare against a working bundle: `test_invalid_working_member_refuses_before_any_git_invocation` and the `_write_working`-driven cases near it. Drop the `("working", None, "root")` row from the `test_non_candidate_pairs_are_not_applicable_and_load_no_candidate_evidence` parametrization. Keep that test's `root` and `candidate` rows.
- `test_explicit_stored_base_and_target_do_not_read_working_bundle` keeps its intent; rename it if the name no longer fits.

### `tests/cli/test_roadmap_cmd.py`

- `test_comparison_default_target_uses_the_read_only_operation` — update the docstring and assertions to the new default; the call still passes `target_version_id=None` to `run_roadmap_comparison`, because resolution lives in the library.
- `test_comparison_no_active_candidate_refusal_exits_usage_with_message` — a stubbed `run_roadmap_comparison` raising the refusal returns rc 2 and prints a message naming `--comparison-target`.
- `test_comparison_no_published_version_error_exits_usage` — the step 6 error takes the same rc 2 path.
- `test_compare_help_describes_active_candidate_default` — the parser help for `--compare` and `--comparison-target` mentions the active candidate and no longer says "working roadmap".

### Tests for this step

Every case above must be green before this step is finished. Verify by mutation: restore a working-tree fallback in `_resolve_target_snapshot` and confirm `test_top_level_artifact_files_are_never_read` and the refusal cases go red. Run `uv run pytest tests/test_roadmap_compare_run.py tests/cli/test_roadmap_cmd.py -q`, then the full suite with `-n auto`.

## Acceptance criteria

- `rg "_load_working_snapshot|\"working\"" plan_tool/roadmap_compare_run.py` returns nothing.
- `--compare` with an active candidate and no `--comparison-target` compares the accepted head with that candidate.
- `--compare` with no active candidate and no `--comparison-target` exits 2 with a message naming `--comparison-target`, and spawns no Git process.
- `--compare` on a folder with no accepted head and no `--comparison-base` exits 2 with step 6's no-published-version message.
- An explicit `--comparison-base` and `--comparison-target` pair still compares two stored versions and reads no top-level file.
- `--help` for `--compare` and `--comparison-target` mentions the active candidate default and does not mention the working roadmap.
- `tests/test_roadmap_compare_run.py` and `tests/cli/test_roadmap_cmd.py` pass.

## References

- `BACKLOG.md` #441 — source entry, decision, and scope contract.
- `ROADMAP_FORMAT.md` § "Immutable candidate-version authority" — accepted head and direct-reader boundary.
- `plan_tool/roadmap_candidate_run.py` — `load_candidate_admission`, `CandidateProposalAdmission`, `load_stored_candidate_proposal`.
- `plan_tool/roadmap_versions.py` — `load_accepted_version`, `load_resolved_stored_version`.
- `plan_tool/roadmap_seed_manifest.py` — `NoPublishedRoadmapVersionError` (step 6).

## Applicable guardrails

- The plan's "## Out of scope", candidate and version-record contracts: this step reads the admission pointer and stored versions and changes neither. It must not edit `plan_tool/roadmap_candidate_run.py` or `plan_tool/roadmap_versions.py`.
- The plan's "## Out of scope", read-only top-level mirror: the refusal when no candidate is active is the answer. This step must not add any mirror or working-tree fallback.
- The plan's "## Out of scope", tool-driven migration: a legacy folder with top-level files gets the no-published-version refusal. This step must not convert it.

## Deferred

- Operator docs for `--compare` in `docs/how-to/roadmap.md` — owned by the plan's docs step.
- Any `"working"` kind references found outside this step's four files, such as in `plan_tool/roadmap_compare_render.py` or its tests — route to the plan's docs/guard steps or `BACKLOG.md` after the grep in Implementation.
- A flag to compare two arbitrary versions without naming ids, or a base other than the accepted head — outside the plan's intent.
