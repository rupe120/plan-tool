> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Validate the documented boundary and record Backlog

## Summary

Align the authoritative audit-shape records in `CLAUDE.md` with the landed registry and make `plan_tool/cli/inspect.py:cmd_validate()` report any drift as a no-model advisory. Update the convergence-policy wording so the new advisory’s material evidence use does not imply a new convergence gate or routing path. Update `BACKLOG.md:#125` and `BACKLOG.md:#224` to record the shipped arm-clustering scope and the work left for later. When green, a valid plan’s `validate` output exposes documentation drift without changing its verdict, exit behavior, or audit/apply behavior.

## Table of Contents

- [Summary](#summary) — The completed documentation, validation, and backlog outcome.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why the registry and operator guidance need a checked boundary.
- [Input](#input) — Upstream registry, advisory, and validate contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The four in-scope edits.
- [Implementation](#implementation) — The comparison rule, advisory integration, and backlog record.
- [Tests](#tests) — Focused command-level coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for parsing and test coverage.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that keep this work advisory-only.
- [Deferred](#deferred) — Follow-up work outside this step.

## Why

Steps 1–3 make the audit-shape boundary executable and visible, but `CLAUDE.md` and the current backlog entry can still describe a broader or differently ordered policy. `plan_tool/cli/inspect.py:cmd_validate()` already has a valid-plan advisory path, so it is the right read-only place to reveal that mismatch before a user relies on stale guidance.

## Input

- **Step 1 registry:** Read the landed `plan_tool/audit_shapes.py:AUDIT_SHAPES` records as the sole source for ID, tell, classification, and order. The landed registry wins over sibling detail files if they differ.

- **Steps 2 and 3 outcome:** Preserve the dedicated `AuditShapeAdvisory` transport and the advisory-only arm-clustering presentation. This step documents and validates that boundary; it does not evaluate an arm or render a new prompt.

- **Validation contract:** Extend only the successful path in `plan_tool/cli/inspect.py:cmd_validate()`. Keep its `INVALID:` return path, `OK:` verdict, smell routing, capability-catalog advisory, and `--fail-on-findings` behavior intact.

- **Materiality boundary:** Keep `CLAUDE.md:# Convergence policy boundary` aligned with `plan_tool/convergence.py:is_blocking_impact()`. The documentation must distinguish the audit’s use of settled material evidence from a new blocking, continuation, or dispatch policy.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `CLAUDE.md` — make the authoritative audit-shape list a complete ordered representation of the landed registry and clarify the bounded materiality-policy use.
  - `plan_tool/cli/inspect.py` — compare the documented records with the registry during successful validation and render drift as a separate advisory.
  - `tests/cli/test_inspect_cmds.py` — cover matching records, drift cases, absent documentation, invalid plans, and unchanged exit behavior.
  - `BACKLOG.md` — update `#125` and `#224` to describe the shipped bounded outcome and point remaining observable-contract work to its existing seed.

## Implementation

- **Make complete documented-record comparison the foundational logic.** Compare the authoritative `CLAUDE.md` audit-shape list with `plan_tool/audit_shapes.py:AUDIT_SHAPES` by exact ID, tell, classification, uniqueness, and order. Do not treat a prose mention elsewhere in `CLAUDE.md` as a match.

- **Use one narrowly parseable, repository-owned documentation form.** Update `CLAUDE.md:## Audit the why, not the what` so every registry record has the fields needed for deterministic comparison in a repeatable form. Place a fixed `<!-- plan-tool:audit-shapes -->` ownership marker immediately before that authoritative list. Keep the human explanation and override guidance; limit extraction to this marked list. Clarify that the tool's advisory is not a software gate while the existing agent-facing, user-visible scope-decision rule still governs a human or agent who chooses to apply conceptual findings.

- **Keep the registry authoritative.** Have `plan_tool/cli/inspect.py:cmd_validate()` read expected records directly from `AUDIT_SHAPES`, and update the marked `CLAUDE.md` list by copying those settled records verbatim. In particular, replace the retired count-taper arm tell with the registry's count-free arm tell. Do not add a second hard-coded record list, classification map, eligibility rule, or prose-based inference in the CLI or tests.

- **Apply the check only to an owned document.** Locate only the repository-root `CLAUDE.md` for the plan being validated, and run audit-shape extraction only when it carries the fixed ownership marker. A marked list with a missing, duplicate, unknown, malformed, reordered, tell-drifted, or classification-drifted record must yield an actionable advisory result. A target repository with no `CLAUDE.md`, or with an unrelated unmarked `CLAUDE.md`, stays quiet rather than report plan-tool-specific drift.

- **Integrate after plan parsing succeeds.** Run the comparison only on `cmd_validate()`’s valid-plan path, alongside its existing advisory checks. Render a clearly labeled audit-shape documentation advisory when findings exist; preserve the existing `OK:` and `INVALID:` forms.

- **Keep validation read-only and advisory.** Documentation drift must not call a model, mutate files, change blocking state, or alter the return value with or without `--fail-on-findings`.

- **Document the materiality and operator boundary precisely.** Replace the stale tapering/count-series carve prompt in `CLAUDE.md` with the typed `arm-clustering` advisory's evidence rule. Describe the settled conceptual-audit material selection without implying a new caller class or convergence control, and distinguish the non-blocking product prompt from the pre-existing user-facing override obligation. Keep the advisory separate from `plan_tool/review.py:partition_findings_for_triage()` and normal finding dispatch.

- **Record the bounded backlog result.** Revise `BACKLOG.md:#224` so it records the shipped registry, the single arm-clustering advisory, the documentation-drift check, and the remaining judgment-only boundary. State that the advisory creates no software gate while the pre-existing user-visible override policy still governs an operator who elects to apply findings. Record the legacy generic `review-walk` completeness-sidecar bypass as an explicitly deferred entrypoint decision pointing to `plan-seeds/audit-shape-advisory-generic-walk.md`; do not change generic routing in this plan. Update `BACKLOG.md:#125` to remove stale count-only operator guidance while retaining the settled low-yield convergence history it owns.

- **Leave similar checks separate.** Use `plan_tool/capability_catalog.py:check_capabilities()` as the read-only advisory precedent, but do not merge the two checks: their source documents and comparison rules differ.

## Tests

### Tests for this step

Every test below belongs in `tests/cli/test_inspect_cmds.py` and must be green before this step is complete.

- `test_validate_accepts_matching_ordered_audit_shape_records` — a complete authoritative list matching `AUDIT_SHAPES` produces no audit-shape documentation advisory.

- `test_validate_reports_audit_shape_documentation_drift_as_advisory` — missing, duplicate, unknown, malformed, reordered, tell-drifted, and classification-drifted records produce labeled actionable output.

- `test_validate_audit_shape_documentation_check_is_inert_without_an_owned_marker` — a valid plan in a target repository with no `CLAUDE.md` or an unrelated unmarked `CLAUDE.md` remains successful and prints no false repository-level drift.

- `test_validate_audit_shape_documentation_drift_never_changes_exit_code` — drift leaves `validate` successful both normally and with `--fail-on-findings`.

- `test_validate_documented_arm_advice_preserves_operator_override_without_a_software_gate` — the parseable record and surrounding guidance describe the bounded advisory, retire count-series wording, and retain the separate user-visible scope-decision rule.

- `test_invalid_plan_does_not_render_audit_shape_documentation_advisory` — the existing `INVALID:` path returns before the new valid-plan advisory work.

## Acceptance criteria

- `CLAUDE.md:## Audit the why, not the what` contains one ordered, parseable documented record for every landed `AUDIT_SHAPES` record.

- The documented records match the registry’s ID, tell, classification, uniqueness, and order.

- `CLAUDE.md:# Convergence policy boundary` and the active shape guidance retire count-series carving language, describe the advisory’s bounded materiality use, and distinguish its non-blocking product behavior from the existing user-visible override rule.

- A missing, duplicate, unknown, malformed, reordered, tell-drifted, or classification-drifted record appears as a labeled `cmd_validate()` advisory after a valid `OK:` result.

- A missing or unmarked repository-root `CLAUDE.md` produces no audit-shape advisory for an unrelated target repository; a marked document is the only audited source.

- Documentation drift does not invoke a model, mutate a file, change blocking state, alter `INVALID:` handling, or change the `cmd_validate()` exit code.

- `BACKLOG.md:#125` no longer describes retired count-only operator guidance, and `BACKLOG.md:#224` records the bounded shipped design with its deferred follow-up.

- Every listed test in `tests/cli/test_inspect_cmds.py` passes.

## References

- [Python regular-expression operations](https://docs.python.org/3.13/library/re.html) — Use strict matching for the bounded documented-record form.

- [pytest parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Cover the documentation-drift matrix without duplicating command setup.

## Applicable guardrails

- **The plan’s `## Plan intent`, dedicated advisory transport** — keep this work limited to documenting and checking the non-executable boundary; do not create a `Recommendation` route or apply target.

- **The plan’s step 4 intent, documented boundary** — keep the production behavior to an ordered-record check, advisory rendering, and a truthful backlog record.

- **The plan’s `## Out of scope`, automation and policy fence** — do not add a gate, exit-code change, automatic action, new detector, generic dispatch change, or materiality-policy expansion.

## Deferred

- `check-saturation` and `self-seeded-finding` emitters — remain future observable-contract work in `plan-seeds/audit-shape-saturation-and-provenance.md`.

- Measurement-instrument adequacy and remedy proportionality detectors — remain judgment-only under the plan’s scope fence.

- A shared repository-document honesty-check framework — leave `plan_tool/capability_catalog.py:check_capabilities()` separate because consolidating distinct document contracts needs separately scoped work.
