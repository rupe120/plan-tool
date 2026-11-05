> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Delete the Jira-grade schema and path helper

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Delete `plan_tool/jira_grade.py` and `tests/test_jira_grade.py` after steps 2, 3, 4, and 6 remove every production consumer. Remove `derive_jira_detail_path` and its Jira-only directory constant from `plan_tool/detail_artifacts.py`, while keeping canonical run-grade derivation and pointer-first resolution unchanged. Remove the obsolete Jira-grade type reference from `plan_tool/roadmap_gates.py` without changing roadmap violations or validation behavior. On green, retired APIs and live Jira-grade bundles are absent, while canonical detail paths and resolution retain their current behavior.

## Table of Contents

- [Summary](#summary) — The removal and preserved detail-path behavior.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the final schema and path ownership must go away.
- [Input](#input) — Upstream removals and retained detail-resolution contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Deleted and edited files in this step.
- [Implementation](#implementation) — The deletion boundary and preserved invariants.
- [Tests](#tests) — Focused checks for absence and canonical resolution.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Test parametrization guidance.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for the retirement.
- [Deferred](#deferred) — Work this step does not take on.

## Why

The Jira-grade contract and its derived `jira/` path are dead once the authoring, execution, export, persistence, and completeness consumers from steps 2, 3, 4, 5, and 6 are gone. Leaving their schema, path helper, or roadmap-gate attribution in place makes the retired lane look supported and invites a later caller to recreate it. This step removes that last authority while protecting the run-grade path and resolution rules that surviving consumers use.

## Input

- **Steps 2, 3, 4, and 6 remove consumers.** Confirm production imports of `plan_tool.jira_grade` and `plan_tool.detail_artifacts.derive_jira_detail_path` are gone before deleting their owners. Do not replace a removed consumer with a compatibility import or fallback.

- **Canonical detail resolution remains supported.** `plan_tool/detail_artifacts.py:derive_detail_path` and `plan_tool/detail_artifacts.py:resolve_detail_artifact` remain the single run-grade path and pointer-resolution contract. Preserve the distinction between a missing declared `Step.detail` target and an unset pointer that can use its canonical path.

- **Roadmap validation remains independent.** `plan_tool/roadmap_gates.py:Violation` keeps its existing fields and blocking-stage meaning. Its Jira-grade comparison is documentation-only and must not become a new dependency or alter gate output.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/jira_grade.py` — Delete the retired Jira-grade schema, validators, grade constants, and prose checks.
  - `plan_tool/detail_artifacts.py` — Remove `_JIRA_GRADE_DIRNAME`, `derive_jira_detail_path`, and Jira-grade-only module documentation; retain canonical path and resolution APIs.
  - `plan_tool/roadmap_gates.py` — Remove the obsolete `jira_grade.JiraGradeFinding` comparison from `Violation` documentation without changing the type or validation logic.
  - `tests/test_jira_grade.py` — Delete the retired schema, validator, path, and leaf-import tests.
  - `tests/test_detail_artifacts.py` — Retain canonical-path characterization and add focused assertions for removed Jira-grade surfaces and absent live bundles.

## Implementation

- **Delete the retired authority only after its callers are gone.** Use a repository-wide import and symbol search for `plan_tool.jira_grade`, `derive_jira_detail_path`, and Jira-grade constants before removing `plan_tool/jira_grade.py` and its test module. A remaining consumer is a prerequisite failure, not a reason to keep a compatibility API.

- **Keep `plan_tool/detail_artifacts.py` run-grade-only.** Remove only the Jira-specific derivation branch. Preserve `derive_step_slug`, `_plan_slug`, `derive_detail_path`, `find_unreferenced_detail_for_step`, and `resolve_detail_artifact` contracts, including their current canonical fallback and set-but-missing-pointer behavior.

- **Preserve roadmap gate behavior.** Update `plan_tool/roadmap_gates.py:Violation` prose so it describes the type directly rather than naming a deleted Jira-grade type. Do not change `Violation` fields, its callers, gate tables, or emitted messages.

- **Audit live Jira-grade bundles immediately before deletion.** Enumerate files under live `docs/implementation-plans/plan-details/<slug>/jira/` paths. The audited snapshot has none; if any appear before execution, delete only those live Jira-grade files and their empty live Jira directories. Preserve canonical detail files and every path under `docs/implementation-plans/archive/`.

- **Do not add cleanup machinery.** A one-time audit is enough for this retirement. Do not add a recurring sweep, migration, compatibility reader, replacement artifact type, or runtime dependency.

## Tests

### Tests for this step

- `test_retired_jira_grade_module_is_absent` — asserts `plan_tool/jira_grade.py` is no longer present in the source tree.

- `test_detail_artifacts_has_no_jira_path_derivation` — asserts `plan_tool/detail_artifacts.py` no longer exposes `derive_jira_detail_path` or Jira-only path state.

- `test_no_live_jira_grade_detail_bundles_exist` — asserts live `docs/implementation-plans/plan-details/` contains no `jira/` detail bundle while leaving archive paths outside the check.

- `test_canonical_detail_path_format` — preserves the existing `derive_detail_path` path format for numbered and manually named plans.

- `test_resolver_state_matrix_preserves_pointer_and_canonical_behavior` — preserves pointer-first selection, no fallback for a set-but-missing pointer, canonical fallback for an unset pointer, and the bare state when neither exists.

- `tests/test_detail_artifacts.py` — every focused test and the existing characterization suite must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/jira_grade.py` and `tests/test_jira_grade.py` are absent.

- `plan_tool/detail_artifacts.py` has no `derive_jira_detail_path` or Jira-only directory constant.

- No production module imports `plan_tool.jira_grade` or `derive_jira_detail_path`.

- `plan_tool/roadmap_gates.py:Violation` no longer references Jira-grade schema types, and its existing roadmap-gate tests remain green.

- Live `docs/implementation-plans/plan-details/<slug>/jira/` bundles are absent; canonical details and all archived artifacts remain untouched.

- `derive_detail_path` and `resolve_detail_artifact` pass their existing canonical-path and resolution-matrix tests unchanged.

## References

- [pytest parametrization documentation — Use parametrized cases where they make the preserved resolution matrix easier to read and maintain.](https://docs.pytest.org/en/stable/how-to/parametrize.html)

## Applicable guardrails

- **The plan's “## Step intent”.** Remove every remaining schema and path helper that could recreate or read the retired lane; keep the surviving run-grade path contract intact.

- **The plan's “## Scope guardrails”.** Do not add compatibility behavior, migration logic, a replacement grade, or a new cleanup mechanism while deleting the retired lane.

- **The plan's “## Out of scope”.** Do not change run-grade authoring, Jira export rendering or publication behavior, or archived historical evidence.

## Deferred

- Archive cleanup or historical-evidence rewriting — remains outside this step under the plan's “## Out of scope”; preserve archived artifacts unchanged.
