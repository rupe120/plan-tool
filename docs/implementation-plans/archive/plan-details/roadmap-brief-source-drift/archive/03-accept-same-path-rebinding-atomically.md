> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Accept same-path rebinding while isolating the baseline operation from artifact and seed effects

## Summary

Extend the existing `--from-existing` gesture so supplying the already-recorded brief path explicitly accepts a legacy or changed decoded-text baseline. Update `plan_tool/roadmap.py` to replace only `source.json` atomically, record the `accepted-rebind` lifecycle result, and expose that fact to the CLI summary. Update `plan_tool/cli/roadmap_cmd.py`, `plan_tool/cli/__init__.py`, `docs/cli/roadmap.md`, and help snapshots so operators understand that acceptance changes the source baseline only. On green, the baseline-replacement operation itself leaves artifacts and seed state untouched, the output does not imply semantic regeneration, and any subsequent stage work retains its ordinary behavior.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the baseline-only acceptance change.
- [Table of Contents](#table-of-contents) — Section map for this detail.
- [Why](#why) — Why a fail-closed source check needs an explicit recovery path.
- [Input](#input) — Step 2 admission and source-record contracts this step uses.
- [Files (creates vs edits)](#files-creates-vs-edits) — In-scope code, test, help, and contract edits.
- [Implementation](#implementation) — Required same-path rebinding behavior and boundaries.
- [Tests](#tests) — Focused regression coverage for acceptance, isolation, and reporting.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant roadmap source and lifecycle contracts.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries for this recovery path.
- [Deferred](#deferred) — Related work this step leaves out.

## Why

Step 2 correctly refuses a changed or legacy source before roadmap work begins, but an operator needs a deliberate way to say that the current text is now the accepted baseline. Reusing the recorded path through `--from-existing` keeps the existing path-identity rule intact while making the choice explicit. The acceptance must be narrow: updating a digest cannot claim that existing roadmap artifacts now describe the revised brief.

## Input

- **Step 2 source admission:** `plan_tool/roadmap.py:_run_roadmap` owns the pre-artifact admission decision and the `roadmap_source_admission` lifecycle record. This step adds only the explicit same-path acceptance outcome.

- **Recorded source contract:** `plan_tool/roadmap_source.py:RecordedBriefSource`, `read_recorded_brief_source`, and `digest_decoded_text` provide the recorded path and decoded-text digest state. Do not reparse `source.json` outside that shared reader.

- **Durable write boundary:** `plan_tool/roadmap.py:_write_brief_source` and `plan_tool/fileio.py:atomic_write_text` define the existing source-record write shape. The rebind must preserve that atomic replacement property.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — recognize explicit same-path acceptance, replace only the recorded source baseline, expose the result, and emit the accepted-rebind lifecycle fact.
  - `plan_tool/run_log.py` — extend the source-admission event surface only as needed for the accepted-rebind result.
  - `plan_tool/cli/__init__.py` — update the roadmap command catalog wording for the explicit same-path gesture.
  - `plan_tool/cli/roadmap_cmd.py` — preserve thin CLI-to-orchestrator wiring and print a baseline-only acceptance summary.
  - `tests/test_roadmap.py` — cover same-path acceptance, atomic replacement, and artifact/seed preservation.
  - `tests/test_run_log.py` — cover accepted-rebind event construction and serialization.
  - `tests/cli/test_roadmap_cmd.py` — cover command forwarding, user-facing wording, and existing conflicting-option behavior.
  - `tests/cli/package_surface_help.golden.txt` — refresh the intentional top-level help change.
  - `DATA_CONTRACT.md` — document the accepted-rebind lifecycle disposition and its narrow meaning.
  - `docs/cli/roadmap.md` — document the existing `--from-existing` same-path acceptance gesture and its limits.

## Implementation

The foundational logic is: **explicitly rebind a recorded brief’s decoded-text baseline only when the operator supplies that same path.**

- **Keep the gesture path-scoped.** Adapt `plan_tool/roadmap.py:_resolve_brief_path` and `_run_roadmap` so an explicitly supplied path that resolves to the recorded path can authorize acceptance of a legacy or changed digest. A different resolved path must retain the current refusal behavior.

- **Require explicit input.** A normal re-entry without `--from-existing` must remain refused for legacy or changed source content under step 2’s admission rules. Do not turn a digest mismatch into an implicit baseline update.

- **Replace only `source.json`.** Write the current decoded-text digest and the existing recorded brief reference through the source-record writer, using atomic replacement. The rebind must not rewrite roadmap artifacts, baseline sidecars, draft seeds, promoted seeds, or seed-state files.

- **Keep acceptance before artifact admission.** Complete the source-record update before the ordinary artifact-loading path can consume the accepted brief. If the source replacement fails, preserve the old record and stop without artifact, seed, or backend effects.

- **Preserve normal stage behavior after acceptance.** The acceptance operation changes only the source baseline. Any subsequent stage behavior remains governed by the existing stage table, feedback routes, gates, retry budget, and publication rules; do not add a re-grounding or reconciliation pass.

- **Report the precise lifecycle fact.** Use `plan_tool/run_log.py:RoadmapSourceAdmission` and `RunLogWriter` to emit exactly one `accepted-rebind` disposition for this route. The event must retain source identity facts only and must not claim that artifacts were regenerated or semantically checked against the new brief.

- **Make the result visible without overclaiming.** Extend the roadmap result and `plan_tool/cli/roadmap_cmd.py` rendering only as needed to state that the source baseline changed. The summary must direct semantic changes to the existing feedback or successor-lineage route rather than describing the roadmap as updated.

- **Keep the existing CLI surface.** Do not add a new acceptance flag, confirmation prompt, or TTY branch. `--from-existing` remains compatible with ordinary stage invocation and must continue through existing argument conflict checks.

- **Update the operator-facing contract.** Align `plan_tool/cli/__init__.py`, `docs/cli/roadmap.md`, `DATA_CONTRACT.md`, and `tests/cli/package_surface_help.golden.txt` with the actual same-path behavior. State that the explicit path accepts the source baseline, not the semantic content of existing artifacts.

## Tests

### Tests for this step

- `tests/test_roadmap.py::test_same_path_from_existing_accepts_changed_brief_baseline_before_artifact_admission` — asserts explicit same-path input admits the changed digest while ordinary re-entry remains refused.

- `tests/test_roadmap.py::test_same_path_from_existing_accepts_legacy_source_record_without_digest` — asserts explicit same-path input can establish a digest baseline for a valid legacy record.

- `tests/test_roadmap.py::test_same_path_rebind_replaces_only_source_json_and_preserves_artifacts_and_seed_state` — asserts every existing artifact and seed-state byte remains unchanged by the rebind itself.

- `tests/test_roadmap.py::test_same_path_rebind_failure_keeps_the_previous_source_record_and_stops_before_artifact_work` — asserts failed atomic replacement preserves the old baseline and reaches no artifact loader, invoker, or seed mutation.

- `tests/test_roadmap.py::test_different_from_existing_path_remains_refused_during_source_rebind` — asserts the existing path-identity rule remains in force.

- `tests/test_roadmap.py::test_same_path_rebind_emits_one_accepted_rebind_admission_event` — asserts the lifecycle result appears once before artifact admission and contains no brief text.

- `tests/test_run_log.py::test_roadmap_source_admission_serializes_accepted_rebind_without_artifact_claims` — asserts the closed disposition serializes with source facts only.

- `tests/cli/test_roadmap_cmd.py::test_same_path_from_existing_forwards_the_explicit_rebind_gesture_to_roadmap` — asserts the CLI passes the existing path through unchanged.

- `tests/cli/test_roadmap_cmd.py::test_rebind_summary_states_only_the_source_baseline_changed` — asserts output does not claim artifact regeneration or semantic reconciliation.

- `tests/cli/test_roadmap_cmd.py::test_same_path_rebind_keeps_existing_broad_mode_conflicts` — asserts unrelated roadmap modes still reject incompatible companions.

Every listed test must be green before this step is complete.

## Acceptance criteria

- Supplying `--from-existing` with the recorded path explicitly accepts a changed or legacy decoded-text source baseline.

- Omitting `--from-existing` continues to refuse changed and legacy source content before artifact admission.

- A supplied path different from the recorded path remains refused.

- Rebinding atomically replaces only `source.json`; existing artifact, baseline, draft-seed, promoted-seed, and seed-state bytes remain unchanged by the acceptance operation.

- A failed rebind preserves the prior `source.json` and prevents artifact loading, backend invocation, and seed mutation.

- The accepted route emits exactly one `roadmap_source_admission` event with the `accepted-rebind` disposition and no brief text.

- CLI output states that the source baseline changed and does not imply that artifacts were regenerated or reconciled.

- `tests/test_roadmap.py`, `tests/test_run_log.py`, and `tests/cli/test_roadmap_cmd.py` pass.

## References

- [Roadmap Brief Source Drift plan](docs/implementation-plans/2-roadmap-brief-source-drift.md) — Read the accepted-rebind, lifecycle, and scope contract.

- [BUG_BACKLOG.md](BUG_BACKLOG.md) — Read the originating same-path source-drift risk.

- [plan_tool/roadmap.py](plan_tool/roadmap.py) — Consult `_resolve_brief_path`, `_write_brief_source`, `_run_roadmap`, and `run_roadmap`.

- [plan_tool/roadmap_source.py](plan_tool/roadmap_source.py) — Use the recorded-source and decoded-text digest contract from step 1.

- [DATA_CONTRACT.md](DATA_CONTRACT.md) — Keep the source lifecycle event documentation aligned with the final event shape.

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Preserve the “Brief-source persistence” one-shot binding boundary.

- [ROADMAP_FORMAT.md](ROADMAP_FORMAT.md) — Preserve source/re-entry and feedback ownership rules.

## Applicable guardrails

- **The plan’s “## Step intent”, explicit baseline acceptance** — limit this step to accepting current source text without claiming artifact regeneration.

- **The plan’s “## Out of scope”, artifact regeneration and reconciliation** — do not add semantic comparison, artifact rewriting, or automatic re-grounding.

- **The plan’s “## Out of scope”, source acceptance surfaces** — reuse the existing same-path gesture; do not add a flag or interactive prompt.

- **The plan’s “## Out of scope”, existing roadmap semantics** — preserve candidate lineage, feedback, artifact gates, retries, exits, and source path identity.

## Deferred

- Multi-source and role-tagged source identity — remains outside this focused source-record rebind.

- Candidate-lineage source checks — remain unchanged because this acceptance route owns only roadmap stage-run source admission.
