> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Data Contract Subsystem
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add data contract discovery and drift checks
  files:
  - DATA_CONTRACT.md
  - tests/test_data_contract.py
  - plan_tool/review_persistence.py
  - plan_tool/review.py
  - plan_tool/telemetry.py
  - plan_tool/locator.py
  - plan_tool/grounding.py
  - plan_tool/project_config.py
  - tests/test_grounding.py
  - tests/test_project_config.py
  creates:
  - plan_tool/data_contract.py
  allowed_mentions:
  - DATA_CONTRACT.md
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/data-contract-subsystem/01-data-contract-discovery-drift-checks.md
  status: done
- id: 2
  title: Report data contract drift in completeness audits
  files:
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/completeness_report.py
  - plan_tool/review_persistence.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_completeness_report.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/data-contract-subsystem/02-report-data-contract-drift-completeness.md
  status: done
- id: 3
  title: Add an interactive data contract apply command
  files:
  - DATA_CONTRACT.md
  - plan_tool/cli/__init__.py
  - plan_tool/cli/app.py
  - plan_tool/cli/parser.py
  - plan_tool/review_persistence.py
  - tests/cli/test_package_surface.py
  - tests/cli/package_surface_help.golden.txt
  - tests/test_data_contract.py
  creates:
  - plan_tool/cli/data_contract_cmd.py
  - tests/cli/test_data_contract_cmd.py
  allowed_mentions:
  - DATA_CONTRACT.md
  - tests/cli/package_surface_help.golden.txt
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/data-contract-subsystem/03-interactive-data-contract-apply-command.md
  status: done
- id: 4
  title: Route data contract findings through saved audit walks
  files:
  - plan_tool/review_walk.py
  - plan_tool/cli/review_actions.py
  - plan_tool/cli/completeness_cmd.py
  - tests/cli/test_review_actions.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/data-contract-subsystem/04-route-data-contract-findings-through.md
  status: done
- id: 5
  title: Add conditional Input contract plan sections
  files:
  - plan_tool/create.py
  - plan_tool/detail.py
  - plan_tool/prompts/detail.md
  - plan_tool/prompts/synthesize-body.md
  - PLAN_FORMAT.md
  - DETAIL_FORMAT.md
  - tests/test_create.py
  - tests/test_detail.py
  allowed_mentions:
  - PLAN_FORMAT.md
  - DETAIL_FORMAT.md
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/data-contract-subsystem/05-input-contract-plan-sections.md
  status: done
- id: 6
  title: Check Input contract field references against HEAD
  files:
  - plan_tool/data_contract.py
  - plan_tool/review.py
  - plan_tool/cli/completeness_phases.py
  - tests/test_data_contract.py
  - tests/test_review.py
  - tests/cli/test_completeness_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/data-contract-subsystem/06-check-input-contract-field-references.md
  status: done
- id: 7
  title: Keep contract tests as the durable coverage gate
  files:
  - tests/test_data_contract.py
  - tests/test_review.py
  - tests/test_create.py
  - tests/test_detail.py
  - tests/test_completeness_report.py
  - tests/cli/test_completeness_cmd.py
  - tests/cli/test_review_actions.py
  - tests/cli/test_data_contract_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  detail: docs/implementation-plans/plan-details/data-contract-subsystem/07-keep-contract-tests-durable-coverage.md
  status: done
- id: 8
  title: Document data contract workflows and refresh CLI docs
  files:
  - DATA_CONTRACT.md
  - RUNBOOK.md
  - README.md
  - PLAN_FORMAT.md
  - DETAIL_FORMAT.md
  - docs/cli/README.md
  - docs/cli/completeness-audit.md
  - docs/cli/completeness-apply.md
  creates:
  - docs/cli/data-contract-apply.md
  allowed_mentions:
  - DATA_CONTRACT.md
  - RUNBOOK.md
  - README.md
  - PLAN_FORMAT.md
  - DETAIL_FORMAT.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 3
  - 4
  - 5
  - 6
  detail: docs/implementation-plans/plan-details/data-contract-subsystem/08-document-data-contract-workflows.md
  status: done
- id: 9
  title: 'Reconcile BACKLOG #63 after the subsystem ships'
  files:
  - BACKLOG.md
  allowed_mentions:
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 8
  detail: docs/implementation-plans/plan-details/data-contract-subsystem/09-reconcile-backlog-63-after-subsystem.md
  status: done
---
# Data Contract Subsystem

## Overview

Build a first-class data-contract subsystem for plan-tool's persisted and serialized structures. The subsystem keeps code as the source of truth while turning `DATA_CONTRACT.md` into a maintained contract reference with deterministic drift detection, interactive update/apply support, and create/detail integration for plans that depend on existing data shapes. The initial scope is persisted or serialized structures such as saved review / reconcile / completeness sidecar JSON records, `Recommendation` metadata, annotation outputs, fingerprints and freshness metadata, and `.plan-tool/plans.json` or any current durable registry/config file.

## Problem statement

Plan-tool has strong authoring-format docs (`PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, `JIRA_FORMAT.md`), but its persisted layer is covered only by a bootstrapped manual `DATA_CONTRACT.md` and `tests/test_data_contract.py`. That gap has already let plans reason against imagined saved schemas, including #57's original `SavedReview` assumptions not matching actual persisted data. Operators cannot yet see which persisted dataclasses or sidecar fields lack contract coverage, contract updates are manual despite deterministic field discovery being possible, and plans that consume existing persisted/API/output contracts have no standard HEAD-verified `## Input` section.

## Architecture

The canonical app-level contract remains documentation and audit surface, not a schema engine. Dataclasses, JSON sidecar readers/writers, and serialization code are authoritative when documentation disagrees; the contract reference records the public persisted or serialized shapes that later plans may cite.

Discovery and audit should be deterministic and conservative. A new authoring check discovers persisted structures and compares them with contract coverage, reporting missing contract entries, stale documented structures, missing documented fields, and fields present in code but absent from the contract alongside existing well-formedness / files-coherence / structural diagnostics. The checker should identify candidate drift and coverage gaps without inferring semantic invariants.

Data-contract apply/walk is a bespoke interactive path for contract-documentation drift, backed by structured drift payloads rather than free-form recommendation prose alone. Introspection can generate candidate structures, fields, target sections, and freshness fingerprints, but the operator decides which fields are stable versus internal, required versus optional, what invariants and migration notes to record, and which fields are intentionally undocumented. Approved edits update `DATA_CONTRACT.md` or the canonical contract reference, not production code; stale plan/detail `## Input` references are reported as plan/detail correctness findings and are not routed to the `DATA_CONTRACT.md` actuator.

Create/detail gains a conditional `## Input` section, also called the Input contract section in prose, only when a plan's correctness depends on an existing data structure, persisted schema, API surface, or output format. When present, it names the consumed contract, depended-on fields or shape, HEAD-verified code locations, and limits of the verification. Named fields in the section must exist in code at HEAD using the existing grounding/fingerprint style where practical, and absence or drift should become a correctness finding.

Final delivery must update `RUNBOOK.md` / relevant format docs and reconcile `BACKLOG.md #63` by removing the shipped entry or marking shipped scope and splitting deferred remainder into a new backlog item.

## References

- [Python dataclasses](https://docs.python.org/3/library/dataclasses.html) — Covers dataclass field introspection and metadata APIs needed to discover persisted contract shapes from code.
- [Python inspect](https://docs.python.org/3/library/inspect.html) — Documents runtime object inspection helpers useful for conservative discovery without hard-coding every structure.
- [Python ast](https://docs.python.org/3/library/ast.html) — Defines Python source parsing APIs useful for static HEAD checks of referenced fields and code locations.
- [Python json](https://docs.python.org/3/library/json.html) — Documents the standard JSON encoder and decoder behavior relevant to sidecar records and durable registry files.
- [CommonMark Specification](https://spec.commonmark.org/) — Specifies portable Markdown structure for maintaining deterministic contract documentation.
- [pytest Documentation](https://docs.pytest.org/en/stable/) — Covers fixtures and assertion patterns needed for drift, apply/walk, and create/detail contract tests.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Runtime validation framework for every persisted JSON file; this plan maintains documentation and audit coverage rather than adding runtime validation.
- Full migration/versioning subsystem for old sidecars; historical migration handling is outside the initial subsystem.
- Semantic correctness of a plan that uses valid fields incorrectly; the contract section verifies shape and existence while conceptual audit validates meaning.
- Universal `## Input` sections on every plan; the Input contract section is only for plans that consume an existing contract.
- Treating generated introspection output as authoritative without human review; apply/walk preserves operator judgment.

## Risks

- Over-documenting internal fields; severity: contract noise and accidental stability promises. Mitigation: make public/stable versus internal/implementation detail an explicit interactive apply decision. Unresolved gap: judgment remains operator-dependent.
- False confidence from HEAD shape checks; severity: plans may pass shape verification while still misusing a field semantically. Mitigation: document that shape verification is a floor, not the semantic audit. Unresolved gap: semantic misuse remains covered by the normal plan audit loop.
- Import cycles from introspection helpers; severity: audit/checker code may become hard to import or run. Mitigation: keep discovery in a leaf or use body-local imports, mirroring existing completeness/report patterns.
- Audit noise from broad discovery; severity: operators may see irrelevant contract findings. Mitigation: start with persisted and serialized structures only and require an explicit allowlist or discovery rule.
- Ceremonial plan sections; severity: create/detail output becomes noisier for unrelated work. Mitigation: `## Input` is conditional on consuming an existing contract, and tests should prove unrelated plans do not get the section.

## Testing

- Unit tests for the discovery/checker layer using small fixture dataclasses and sidecar-like structures.
- Completeness-report tests showing data-contract findings grouped/routed distinctly.
- Apply/walk tests proving approved contract edits are written and rejected edits leave files unchanged.
- Create/detail tests proving `## Input` appears for contract-consuming plans and is absent for unrelated plans.
- Drift tests proving referenced fields and code locations in a per-plan `## Input` section are checked against HEAD.
- Registry tests proving grounding sidecars, project config, stale documented fields, and obsolete contract sections are checked from code-owned registrations.
- Existing `DATA_CONTRACT.md` drift guard, currently covered by `tests/test_data_contract.py`, must remain green or be replaced by a stronger deterministic guard with equivalent or stronger coverage.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (non-code) — verification appropriate to the artifacts; no test-ordering directive.
- step 9 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- Completeness audit deterministically reports contract coverage drift for persisted/serialized structures missing from the canonical contract.
- Stale contract entries are detected with clear, actionable findings.
- Missing documented fields are detected with clear, actionable findings.
- Data-contract findings have a distinct source/domain in saved reports so the apply/walk path can route them separately from conceptual gaps.
- An interactive apply/walk can add or update a contract entry while preserving operator judgment over stability, invariants, and intentional exclusions.
- `create` / `detail` add a concrete `## Input` section only for plans that consume an existing contract.
- `## Input` sections name code locations and fields verified at HEAD.
- A missing field referenced by an `## Input` section produces a correctness finding that targets the plan/detail source, not `DATA_CONTRACT.md`.
- Existing `DATA_CONTRACT.md` drift guard remains green or is replaced by a more complete deterministic guard with equivalent or stronger coverage.
- `BACKLOG.md #63` is reconciled in the final step.

## Deferred

- Historical sidecar migration/version handling; defer because it is larger than the initial contract coverage subsystem.
- Richer semantic invariants beyond field existence and documented meaning; defer because semantic correctness remains handled by conceptual audit.
- Cross-repo contract references; defer as a separate concern beyond local plan-tool contracts.
- Generated contract diagrams or schema exports; defer as presentation/export work after the maintained contract surface exists.
- Telemetry linking contract findings to later reconcile failures; defer until the core detection and apply workflow ship.
