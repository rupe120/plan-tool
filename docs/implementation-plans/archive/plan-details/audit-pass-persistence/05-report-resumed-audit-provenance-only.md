> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Report resumed audits as provenance only

## Summary

Add a human-readable provenance note when a conceptual audit resumes from step 3’s sampler checkpoint. Thread the sampler’s positive resume result through `plan_tool/cli/completeness_phases.py` and `plan_tool/cli/completeness_cmd.py` into the Markdown report and concise iterate summary in `plan_tool/completeness_report.py`. Keep the note separate from `qualified_result`, `audit_coverage`, saved-review fields, and the `--json` payload. Green means a resumed run tells the operator it resumed, while its final verdict and coverage match the equivalent uninterrupted run.

## Table of Contents

- [Summary](#summary) — The completed behavior and its reporting boundary.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why resumption needs visible provenance without changing audit evidence.
- [Input](#input) — The sampler result and final-report contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The scoped source and test changes.
- [Implementation](#implementation) — Provenance flow, presentation, and invariant boundaries.
- [Tests](#tests) — Focused report, console, and JSON-contract coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Public JSON-contract reference.
- [Applicable guardrails](#applicable-guardrails) — Plan fences that limit this reporting change.
- [Deferred](#deferred) — Work intentionally left to later steps.

## Why

Step 3 lets the sampler continue a matching interrupted audit, but the final completeness output does not yet tell an operator that part of the audit came from a durable pass boundary. That history helps an operator interpret elapsed work and the report trail, but it must not affect whether the audit is qualified or how complete its sampling was. This step makes the recovery visible while preserving final-evidence comparability.

## Input

- **Step 3 sampler result** — Consume the sampler-owned resumed or fresh/declined result that `plan_tool/review.py:audit_plan_until_stable` exposes to callers. Treat a positive resume as the only condition that adds final-report provenance; do not inspect checkpoint files again in reporting code.

- **Final decision** — Keep `plan_tool/cli/completeness_cmd.py:classify_qualified_audit_result` and `QualifiedAuditResult.as_dict` driven only by their current evidence inputs.

- **Coverage record** — Preserve the coverage selected in `plan_tool/cli/completeness_cmd.py:finalize_completeness_run` from `_sample_conceptual_audit` or `_IterateOutcome.budget`. Step 3 guarantees a resumed sampler produces the same record as an uninterrupted sampler.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/completeness_report.py` — Add a focused human-facing resume-provenance rendering path and let `console_summary` display it without changing report persistence or decision payloads.
  - `plan_tool/cli/completeness_phases.py` — Carry the sampler’s positive resume result through `_sample_conceptual_audit`, `_run_iterate_convergence_loop`, `_IterateOutcome`, `_render_grouped_report`, and `_persist_and_present_report`.
  - `plan_tool/cli/completeness_cmd.py` — Preserve the audit-only and iterative resume result through `cmd_completeness` and `finalize_completeness_run` without passing it to `classify_qualified_audit_result` or `_render_completeness_json`.
  - `tests/test_completeness_report.py` — Cover human-readable report and concise-summary provenance rendering.
  - `tests/cli/test_completeness_cmd.py` — Cover both command paths and the unchanged qualified-result, coverage, and JSON contracts.

## Implementation

- **Make resume presentation a positive, presentation-only fact.** Use the signal step 3 returns for a successful resume. A fresh audit, a declined checkpoint, an unreadable checkpoint, or a malformed checkpoint must render like today’s normal final output; they must not receive a misleading resume marker.

- **Keep the sampler as the source of truth.** Forward the result from `plan_tool/review.py:audit_plan_until_stable` through `plan_tool/cli/completeness_phases.py:_sample_conceptual_audit` for audit-only runs and through `plan_tool/cli/completeness_phases.py:_run_iterate_convergence_loop` plus `_IterateOutcome` for `--iterate`. Do not infer it from the reports directory after sampling, because a later read could describe a different artifact state.

- **Render the provenance in both human result paths.** One approach is a short, clearly labelled audit-provenance block in `plan_tool/cli/completeness_phases.py:_render_grouped_report`, so the audit-only console output and saved Markdown report share the same statement. Pass the same fact to `plan_tool/completeness_report.py:console_summary` so an iterative run’s concise final summary also names the resume.

- **Keep the note outside the verdict.** `plan_tool/cli/completeness_cmd.py:finalize_completeness_run` must calculate and preserve `QualifiedAuditResult` exactly as it does for an uninterrupted audit. Resume provenance must not become a field in `QualifiedAuditResult`, alter its headline or revision status, or affect the inputs to `classify_qualified_audit_result`.

- **Keep coverage unchanged.** Do not append a resume marker to `_IterateOutcome.budget`, the selected audit coverage, or the projection helpers in `plan_tool/cli/completeness_phases.py:_project_audit_coverage_for_public_output`. The resumed and uninterrupted paths must expose the same coverage object when their logical passes and replies match.

- **Preserve the public JSON contract.** `plan_tool/cli/completeness_phases.py:_render_completeness_json` must not gain a resume field or change its existing `coverage` or `qualified_result` values. The provenance belongs only in human-readable output.

- **Do not extend saved-review persistence.** Keep `plan_tool/completeness_report.py:write_completeness_report` and its `SavedReview` payload shape unchanged. The timestamped Markdown report may record the provenance through its rendered text, but final sidecars must retain their current evidence-only fields and reader behavior.

## Tests

- `test_grouped_report_renders_resumed_audit_provenance_only_for_positive_resume` — A resumed audit adds the labelled provenance note, while a fresh or declined audit does not.

- `test_console_summary_renders_resumed_audit_provenance` — The concise `--iterate` summary tells the operator that the completed audit resumed.

- `test_resumed_audit_finalization_matches_uninterrupted_qualified_result` — Controlled resumed and uninterrupted runs produce equal `QualifiedAuditResult.as_dict()` values.

- `test_resumed_audit_finalization_matches_uninterrupted_coverage` — Controlled resumed and uninterrupted runs preserve the same selected coverage record.

- `test_resumed_audit_json_contract_has_no_resume_field` — `completeness-audit --json` keeps its existing top-level keys and leaves `coverage` and `qualified_result` unchanged by resume provenance.

### Tests for this step

- `tests/test_completeness_report.py:test_grouped_report_renders_resumed_audit_provenance_only_for_positive_resume` — Covers the persisted and audit-only human report boundary.

- `tests/test_completeness_report.py:test_console_summary_renders_resumed_audit_provenance` — Covers the concise iterative console summary.

- `tests/cli/test_completeness_cmd.py:test_resumed_audit_finalization_matches_uninterrupted_qualified_result` — Proves resume does not change the verdict.

- `tests/cli/test_completeness_cmd.py:test_resumed_audit_finalization_matches_uninterrupted_coverage` — Proves resume does not change coverage evidence.

- `tests/cli/test_completeness_cmd.py:test_resumed_audit_json_contract_has_no_resume_field` — Proves the public JSON shape remains unchanged.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A completed resumed audit includes a clear resume-provenance note in its human-readable final report.

- A completed `--iterate` audit includes the same resume provenance in its concise final console summary.

- Fresh and declined-resume audits omit the final resume-provenance note.

- For controlled equivalent runs, resumed and uninterrupted audits produce equal `qualified_result` values and equal audit-coverage records.

- `completeness-audit --json` has no new resume-related key and retains its existing `coverage` and `qualified_result` values.

- The final saved-review sidecar schema remains unchanged.

- All tests named in `## Tests` pass.

## References

- [json — JSON encoder and decoderhttps: — Use this to preserve the existing machine-readable JSON contract while adding human-only provenance.

## Applicable guardrails

- **The plan’s step intent** — Limit this step to telling an operator about a resumed audit; do not make resumption part of the audit’s verdict.

- **The plan’s “## Out of scope”, finding and coverage semantics** — Do not change finding union, severity, confirmation, qualification, or coverage behavior.

- **The plan’s “## Out of scope”, public output boundary** — Do not add a `completeness-audit --json` field or another CLI control.

- **The plan’s “## Out of scope”, final-evidence readers** — Do not make a checkpoint reusable or alter saved-audit selection, apply, walk, or final-reader eligibility.

- **The plan’s “## Out of scope”, non-conceptual surfaces** — Keep resume presentation confined to the conceptual completeness-audit paths named in this step.

## Deferred

- Operator documentation for resume, decline, and checkpoint disposal — Step 6 owns the flow documentation and backlog update.

- Persisted resume provenance beyond the Markdown report — Requires a separate schema and reader decision; this step keeps final sidecars unchanged.
