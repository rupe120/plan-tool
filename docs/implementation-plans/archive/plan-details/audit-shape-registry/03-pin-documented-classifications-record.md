> **Replaced**: this file has been superseded by `docs/implementation-plans/2-audit-shape-registry.md`.
> Preserved here for history; do not edit.

# Step 3 — Pin documented classifications and record the bounded outcome

## Summary

Synchronize the authoritative audit-shape list in `CLAUDE.md` with step 1’s registry and add a read-only drift check to `plan_tool/cli/inspect.py:cmd_validate()`. Extend `plan_tool/audit_shapes.py` with leaf-safe document parsing and comparison helpers, then cover both the helper and CLI behavior in the scoped tests. Update `BACKLOG.md`’s `#224` record to describe the shipped bounded outcome and its deferred follow-up. On green, documentation drift is visible as an advisory without changing validation verdicts, exit codes, files, or audit behavior.

## Table of Contents

- [Summary](#summary) — The documentation, validation, and backlog outcome.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why executable and documented classifications need one checkable boundary.
- [Input](#input) — The registry and validation contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The six in-scope file changes.
- [Implementation](#implementation) — The comparison rule, advisory integration, and bounded record.
- [Tests](#tests) — Focused helper and command coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for immutable records and tests.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that keep this advisory-only.
- [Deferred](#deferred) — Work that remains outside this step.

## Why

Step 1 makes the five-shape classification executable in `plan_tool/audit_shapes.py:AUDIT_SHAPES`, while the authoritative guidance and `BACKLOG.md:#224` can otherwise describe a different boundary. A valid plan currently reaches `plan_tool/cli/inspect.py:cmd_validate()` without checking that documentation contract, so a quiet prose edit could promote, remove, or reorder a shape without any no-Claude signal. This step makes the documented contract auditable and records the reduced scope for the two deferred observable-contract investigations.

## Input

- **Step 1 registry.** Read the landed `plan_tool/audit_shapes.py:AUDIT_SHAPES` records as the sole code-side source for each shape’s ID, tell, order, and classification. The landed registry wins over either sibling detail file if they differ.

- **Step 2 advisory boundary.** Preserve step 2’s use of `plan_tool/audit_shapes.py:is_advisory_emitter_eligible()` without adding another emitter, evaluator, or report route. This step checks documentation consistency only.

- **Validate contract.** Extend the successful `plan_tool/cli/inspect.py:cmd_validate()` path, which already prints `OK:` and renders advisory checks without changing the normal return value. Keep its early `INVALID:` return unchanged.

- **Deferred follow-up.** Treat `plan-seeds/audit-shape-saturation-and-provenance.md:## Scope` as the existing destination for future saturation and provenance observability work; this step records and links that boundary but does not edit the seed.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `CLAUDE.md` — make the authoritative `## Audit the why, not the what` list expose each registry record in one consistent, narrowly parseable form while keeping its human guidance and override rule.
  - `BACKLOG.md` — update `#224 — An audit-shape registry` with the bounded shipped outcome and a clear pointer to the deferred seed.
  - `plan_tool/audit_shapes.py` — add leaf-safe documented-record extraction and drift comparison beside `AUDIT_SHAPES`.
  - `plan_tool/cli/inspect.py` — render audit-shape documentation drift from `cmd_validate()` as a separate advisory block.
  - `tests/test_audit_shapes.py` — extend the step 1 registry suite with document parsing, comparison, and shipped-document checks.
  - `tests/cli/test_inspect_cmds.py` — extend `TestCmdValidate` with advisory rendering and unchanged-exit coverage.

## Implementation

- **Compare complete records, not prose mentions.** Make the foundational logic a deterministic comparison between the ordered documented entries and `plan_tool/audit_shapes.py:AUDIT_SHAPES`. It must check the stable ID, concise tell, classification, uniqueness, and order; a matching ID elsewhere in `CLAUDE.md` must not satisfy the check.

- **Keep the authoritative list bounded.** Update `CLAUDE.md`’s `## Audit the why, not the what` section so each of its five entries provides the fields the checker needs in a repeatable form. Limit extraction to that section and its list, so surrounding discussion cannot create false matches.

- **Keep the registry authoritative.** Derive expected records directly from `plan_tool/audit_shapes.py:AUDIT_SHAPES`; do not add a second list, classification map, or eligibility rule in the parser, CLI, documentation, or tests. The checker may return structured drift results with stable codes and actionable messages so the renderer does not need to rebuild comparison logic.

- **Fail closed on a present bad document.** Missing entries, duplicate IDs, unknown IDs, malformed annotations, reordered entries, changed tells, and changed classifications must each produce an advisory result. Do not guess a record from surrounding prose or silently accept a partial list.

- **Stay quiet outside the documented repository.** Follow the absent-document behavior of `plan_tool/capability_catalog.py:check_capabilities()`: when a target repository has no `CLAUDE.md`, the audit-shape check is inert rather than reporting a false project-level defect. A present but unusable authoritative section is drift, not absence.

- **Preserve the leaf boundary.** Keep `plan_tool/audit_shapes.py` standard-library-only. It must not import `plan_tool/cli/inspect.py`, `plan_tool/review.py`, persistence code, or model-invocation code; `plan_tool/cli/inspect.py:cmd_validate()` owns filesystem context and presentation.

- **Integrate after schema success only.** Invoke the checker from the valid-plan path in `plan_tool/cli/inspect.py:cmd_validate()`, alongside the existing advisory checks. Render a clearly labeled audit-shape documentation block only when drift exists, while preserving `OK:`, `INVALID:`, advisory smell routing, and capability-catalog output.

- **Keep validation advisory.** Documentation drift must not affect `--fail-on-findings`, blocking state, model use, or file mutation. It is a visible agreement check, not a plan-schema error or a scope decision.

- **Record the bounded backlog outcome.** Revise `BACKLOG.md:#224` so it no longer promises saturation or self-seeded emitters from unproven data. Record the one checked advisory boundary, retain the remaining classifications as judgment-only, and point future observable-contract and reclassification work to `plan-seeds/audit-shape-saturation-and-provenance.md`.

## Tests

### Tests for this step

- `tests/test_audit_shapes.py:test_documented_audit_shape_records_match_registry_in_order` — a complete authoritative list yields the same ordered ID, tell, and classification records as `AUDIT_SHAPES`.

- `tests/test_audit_shapes.py:test_documented_audit_shape_records_report_missing_duplicate_unknown_malformed_and_reordered_entries` — every structural mismatch produces explicit drift rather than a prose-based match.

- `tests/test_audit_shapes.py:test_documented_audit_shape_records_report_tell_and_classification_drift` — a known ID with changed documented fields still reports drift.

- `tests/test_audit_shapes.py:test_audit_shape_documentation_check_is_inert_without_claude` — a repository without `CLAUDE.md` produces no finding.

- `tests/test_audit_shapes.py:test_shipped_claude_audit_shape_list_matches_registry` — the committed authoritative list agrees with the landed registry.

- `tests/cli/test_inspect_cmds.py:test_validate_surfaces_audit_shape_documentation_drift_as_advisory` — `TestCmdValidate` renders the labeled advisory block after a valid plan.

- `tests/cli/test_inspect_cmds.py:test_validate_audit_shape_documentation_drift_never_changes_exit_code` — drift leaves `validate` successful both normally and with `--fail-on-findings`.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `CLAUDE.md`’s `## Audit the why, not the what` list contains one parseable, ordered documented record for every `plan_tool/audit_shapes.py:AUDIT_SHAPES` entry.

- The documented records match `AUDIT_SHAPES` by exact ID, tell, classification, uniqueness, and order.

- A missing, duplicate, unknown, malformed, reordered, tell-drifted, or classification-drifted record produces an advisory result.

- `plan_tool/cli/inspect.py:cmd_validate()` renders audit-shape documentation drift only after a plan parses successfully.

- A missing `CLAUDE.md` leaves the audit-shape check quiet for an unrelated target repository.

- Documentation drift never invokes a model, mutates a file, changes blocking state, or changes `cmd_validate()` exit behavior.

- `BACKLOG.md:#224` records the bounded outcome and directs saturation and provenance follow-up to `plan-seeds/audit-shape-saturation-and-provenance.md`.

- Every listed test in `tests/test_audit_shapes.py` and `tests/cli/test_inspect_cmds.py` passes.

## References

- [Python dataclasses documentation](https://docs.python.org/3/library/dataclasses.html) — Reference for immutable registry and drift-result records.

- [Python unittest documentation](https://docs.python.org/3/library/unittest.html) — Reference for focused behavior and command-boundary tests.

## Applicable guardrails

- **The plan’s `## Plan intent`, checked-versus-judgment-only boundary** — keep classification authority in the registry and expose drift without creating a new decision signal.

- **The plan’s step 3 intent, documented and executable agreement** — limit production behavior to a no-Claude documentation check and a bounded backlog record.

- **The plan’s `## Out of scope`, detector and automation fence** — do not add an emitter, persistence contract, gate, exit-code behavior, automatic remedy, or semantic judgment while checking the documentation.

## Deferred

- `plan-seeds/audit-shape-saturation-and-provenance.md:## Scope` — saturation and self-seeded provenance remain future observable-contract investigations; this step records their boundary but does not reclassify or implement them.

- Measurement-instrument adequacy and remedy proportionality detectors — remain judgment-only under the plan’s scope fence.

- A shared repository-document honesty-check framework — leave `plan_tool/capability_catalog.py:check_capabilities()` and the new audit-shape checker separate because their documents and comparison rules differ; consolidation needs separate scope.
