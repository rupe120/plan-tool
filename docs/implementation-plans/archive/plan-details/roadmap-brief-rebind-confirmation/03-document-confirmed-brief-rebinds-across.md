> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Document confirmed brief rebinds across the source contract and operator guides

## Summary

Document explicit brief-rebind consent across the roadmap contract and operator guides. Update the source lifecycle references, command examples, and automation guidance to name `--confirm-brief-rebind` and distinguish refusal from a confirmed baseline-only rebind. Keep `RoadmapSourceAdmission` redacted and unchanged as the lifecycle record. On green, the documentation tests prevent any guide from implying that repeating `--from-existing` alone replaces a changed or legacy baseline.

## Table of Contents

- [Summary](#summary) — The completed documentation result.
- [Table of Contents](#table-of-contents) — Links to this detail’s sections.
- [Why](#why) — Why the current guidance needs a consent boundary.
- [Input](#input) — Upstream admission, CLI, and lifecycle contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The documentation and drift guards to update.
- [Implementation](#implementation) — The required guidance contract and scope limits.
- [Tests](#tests) — Documentation drift checks to extend.
- [Acceptance criteria](#acceptance-criteria) — Observable completed behavior.
- [References](#references) — Source-admission and CLI ownership references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this sweep.
- [Deferred](#deferred) — Work owned by adjacent steps.

## Why

Current guidance says a same-path `--from-existing` accepts a changed or legacy baseline, but step 1 makes that action require separate consent and step 2 exposes that consent only on stage runs. Leaving the old wording in operator-facing documents would encourage a command that now refuses safely, while hiding the narrow confirmed route that replaces only the recorded baseline.

## Input

- **Step 1 admission outcome:** `plan_tool/roadmap.py:run_roadmap` and `plan_tool/roadmap.py:_run_roadmap` retain the decoded-text and same-path admission facts, while step 1 adds the explicit consent required for an `accepted-rebind`.

- **Step 2 CLI outcome:** `plan_tool/cli/roadmap_cmd.py:register` and `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` expose `--confirm-brief-rebind` only to ordinary stage runs and reject it for non-stage routes.

- **Lifecycle record:** `plan_tool/run_log.py:RoadmapSourceAdmissionDisposition` and `plan_tool/run_log.py:RoadmapSourceAdmission` retain the existing dispositions and redacted fields. The documentation must not invent a new event, disposition, or payload field.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — Update `## Concept-brief source admission and lifecycle` as the detailed source-contract reference.
  - `DATA_CONTRACT.md` — Update `### Roadmap source admission lifecycle event (`run_log.py`)` to describe confirmed `accepted-rebind` admission without changing its persisted shape.
  - `README.md` — Update `# CLI usage` and `### 0. \`roadmap\` — stage a project-sized concept` command and lifecycle guidance.
  - `RUNBOOK.md` — Update the roadmap quick-reference and `## Workflow: turn a concept brief into architecture artifacts (`roadmap`)`.
  - `USE_CASES.md` — Update `### 11. Ground a project-sized concept before you write a seed`.
  - `CAPABILITIES.md` — Update `## Architecture roadmap` with the confirmed stage-run boundary.
  - `docs/ARCHITECTURE.md` — Update `**Brief-source persistence.**` with the source-admission rule.
  - `docs/ROADMAP_WALKTHROUGH.md` — Update `## Command sequence at a glance` and `## 2. Generate the roadmap`.
  - `integrations/claude/SKILL.md` — Update the roadmap entries in `## Decision tree for common user asks` and `## Subcommands at a glance`.
  - `tests/test_roadmap_format.py` — Extend source-admission guidance drift checks across every listed guide.
  - `tests/test_data_contract.py` — Add lifecycle-documentation coverage for explicit confirmation.

## Implementation

- **Foundational logic:** document the confirmed-rebind admission rule consistently.

- **State the two outcomes clearly:** a changed or legacy baseline at the recorded path must remain `refused-changed` or `refused-legacy` when an operator repeats `--from-existing` without `--confirm-brief-rebind`. The same recorded path plus the explicit flag may produce `accepted-rebind`.

- **Keep the rebind narrow:** every guide must say that a confirmed rebind replaces only `source.json`’s accepted decoded-text baseline. It must not claim artifact publication, seed-state changes, feedback changes, regeneration, reconciliation, or semantic approval.

- **Keep normal admission unchanged:** initial and matching-baseline stage runs remain ordinary runs with or without the flag; documentation must not imply that confirmation is required when no baseline replacement is needed or that supplying it changes those routes.

- **Use the source contract as the detailed home:** update `ROADMAP_FORMAT.md:## Concept-brief source admission and lifecycle` with the complete condition, refusal behavior, baseline-only result, and redaction boundary. Keep shorter guides linked to this contract rather than duplicating unrelated lifecycle detail.

- **Preserve event meaning:** update `DATA_CONTRACT.md:### Roadmap source admission lifecycle event (`run_log.py`)` so `accepted-rebind` means an explicitly confirmed same-path baseline acceptance. Keep `plan_tool/run_log.py:RoadmapSourceAdmission` as the authority for event fields and preserve the no-brief-text guarantee.

- **Sweep each operator audience:** update the roadmap guidance in `README.md`, `RUNBOOK.md`, `USE_CASES.md`, `CAPABILITIES.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP_WALKTHROUGH.md`, and `integrations/claude/SKILL.md`. Use the command form with both `--from-existing` and `--confirm-brief-rebind` where an example is useful.

- **Keep confirmation route-specific:** describe `--confirm-brief-rebind` as stage-run-only. Do not present it as an interactive prompt, a synonym for `--apply -y`, or an extension of `--confirm-feedback-reopen`. Non-stage analysis, structural rewrite, and root enrollment retain their separate brief-baseline rules.

- **Make the drift guard cover the class:** extend `tests/test_roadmap_format.py:_SOURCE_ADMISSION_GUIDES` and `_SOURCE_ADMISSION_GUIDANCE` so every guide in this step is checked for the confirmed and unconfirmed paths. Do not add a parallel documentation registry.

## Tests

- `tests/test_roadmap_format.py:test_source_admission_guidance_sweep_matches_landed_contract` — Assert every source-admission guide names explicit confirmation and no guide treats repeated `--from-existing` alone as consent.

- `tests/test_roadmap_format.py:test_source_admission_guidance_keeps_artifact_and_seed_isolation` — Assert confirmed rebind wording remains baseline-only and preserves artifact, feedback, and seed isolation.

- `tests/test_roadmap_format.py:test_non_stage_brief_drift_guidance_does_not_offer_stage_rebind_to_non_stage_routes` — Assert stage-only rebind guidance does not become recovery guidance for non-stage routes.

- `tests/test_data_contract.py:test_roadmap_source_admission_contract_requires_confirmed_rebind` — Assert the `RoadmapSourceAdmission` documentation ties `accepted-rebind` to explicit confirmation while retaining the existing redacted event contract.

### Verification (non-code step)

1. Run `uv run pytest tests/test_roadmap_format.py tests/test_data_contract.py -q`.
2. Compare every roadmap command example against `plan-tool roadmap --help` and `docs/cli/roadmap.md`; step 2 remains the owner of parser-derived reference output.
3. Search the edited guide set for stale wording that says a same-path `--from-existing` alone accepts current text.
4. Check Markdown links and code anchors named by the updated documentation.

## Acceptance criteria

- Every listed operator guide distinguishes unconfirmed refusal from `--confirm-brief-rebind` baseline acceptance.

- No listed guide states or implies that repeating `--from-existing` alone replaces a changed or legacy baseline.

- Every confirmed-rebind description limits its effect to the recorded source baseline and preserves the existing artifact, feedback, and seed boundaries.

- `DATA_CONTRACT.md` documents `accepted-rebind` as confirmed admission without adding a lifecycle event, disposition, or payload field.

- No guide offers confirmed rebind as recovery for a non-stage roadmap route.

- `uv run pytest tests/test_roadmap_format.py tests/test_data_contract.py -q` passes.

## References

- [BACKLOG #367](BACKLOG.md) — Read the confirmed scope and delivery boundary.

- [Roadmap source admission](plan_tool/roadmap.py) — Read `run_roadmap`, `_run_roadmap`, and `_resolve_brief_path` for admission ownership.

- [Roadmap CLI dispatch](plan_tool/cli/roadmap_cmd.py) — Read `register` and `cmd_roadmap` for stage-route flag handling.

- [Roadmap admission lifecycle](plan_tool/run_log.py) — Read `RoadmapSourceAdmissionDisposition` and `RoadmapSourceAdmission` for persisted event meaning.

- [Roadmap format contract](ROADMAP_FORMAT.md) — Read `## Concept-brief source admission and lifecycle` for the canonical operator-facing lifecycle.

## Applicable guardrails

- **Explicit operator intent:** the plan’s `## Plan intent` limits this documentation to the confirmed same-recorded-path admission boundary; document that boundary without adding alternate consent paths.

- **Narrow confirmation:** the plan’s `## Scope guardrails` limits guidance to the existing source identity and digest facts. Do not describe quality checks, semantic comparisons, automation inference, or interactive confirmation.

- **Non-stage separation:** the plan’s `## Out of scope` keeps non-stage writer behavior outside this sweep. Document their separation from stage-run confirmation without changing their contracts.

## Deferred

- `docs/cli/roadmap.md` regeneration — Step 2 owns the parser-derived reference update from `plan_tool/cli/roadmap_cmd.py:register`.

- Runtime admission and CLI behavior — Steps 1 and 2 own changes to `plan_tool/roadmap.py` and `plan_tool/cli/roadmap_cmd.py`.
