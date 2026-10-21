> **Replaced**: this file has been superseded by `docs/implementation-plans/2-data-contract-subsystem.md`.
> Preserved here for history; do not edit.

## Overview

Build a first-class data-contract subsystem for plan-tool's persisted and serialized structures. The subsystem keeps code as the source of truth while turning `DATA_CONTRACT.md` into a maintained contract reference with deterministic drift detection, interactive update/apply support, and create/detail integration for plans that depend on existing data shapes. The initial scope is persisted or serialized structures such as saved review / reconcile / completeness sidecar JSON records, `Recommendation` metadata, annotation outputs, fingerprints and freshness metadata, and `.plan-tool/plans.json` or any current durable registry/config file.

## Problem statement

Plan-tool has strong authoring-format docs (`PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, `JIRA_FORMAT.md`), but its persisted layer is covered only by a bootstrapped manual `DATA_CONTRACT.md` and `tests/test_data_contract.py`. That gap has already let plans reason against imagined saved schemas, including #57's original `SavedReview` assumptions not matching actual persisted data. Operators cannot yet see which persisted dataclasses or sidecar fields lack contract coverage, contract updates are manual despite deterministic field discovery being possible, and plans that consume existing persisted/API/output contracts have no standard HEAD-verified `Input contract` section.

## Architecture

The canonical app-level contract remains documentation and audit surface, not a schema engine. Dataclasses, JSON sidecar readers/writers, and serialization code are authoritative when documentation disagrees; the contract reference records the public persisted or serialized shapes that later plans may cite.

Discovery and audit should be deterministic and conservative. A new authoring check discovers persisted structures and compares them with contract coverage, reporting missing contract entries, stale documented structures, missing documented fields, and fields present in code but absent from the contract alongside existing well-formedness / files-coherence / structural diagnostics. The checker should identify candidate drift and coverage gaps without inferring semantic invariants.

Data-contract apply/walk is a bespoke interactive path. Introspection can generate candidate structures and fields, but the operator decides which fields are stable versus internal, required versus optional, what invariants and migration notes to record, and which fields are intentionally undocumented. Approved edits update `DATA_CONTRACT.md` or the canonical contract reference, not production code.

Create/detail gains a conditional `Input contract` section only when a plan's correctness depends on an existing data structure, persisted schema, API surface, or output format. When present, it names the consumed contract, depended-on fields or shape, HEAD-verified code locations, and limits of the verification. Named fields in the section must exist in code at HEAD using the existing grounding/fingerprint style where practical, and absence or drift should become a correctness finding.

Final delivery must update `RUNBOOK.md` / relevant format docs and reconcile `BACKLOG.md #63` by removing the shipped entry or marking shipped scope and splitting deferred remainder into a new backlog item.

## Out of scope

- Runtime validation framework for every persisted JSON file; this plan maintains documentation and audit coverage rather than adding runtime validation.
- Full migration/versioning subsystem for old sidecars; historical migration handling is outside the initial subsystem.
- Semantic correctness of a plan that uses valid fields incorrectly; the contract section verifies shape and existence while conceptual audit validates meaning.
- Universal `Input contract` sections on every plan; the section is only for plans that consume an existing contract.
- Treating generated introspection output as authoritative without human review; apply/walk preserves operator judgment.

## Risks

- Over-documenting internal fields; severity: contract noise and accidental stability promises. Mitigation: make public/stable versus internal/implementation detail an explicit interactive apply decision. Unresolved gap: judgment remains operator-dependent.
- False confidence from HEAD shape checks; severity: plans may pass shape verification while still misusing a field semantically. Mitigation: document that shape verification is a floor, not the semantic audit. Unresolved gap: semantic misuse remains covered by the normal plan audit loop.
- Import cycles from introspection helpers; severity: audit/checker code may become hard to import or run. Mitigation: keep discovery in a leaf or use body-local imports, mirroring existing completeness/report patterns.
- Audit noise from broad discovery; severity: operators may see irrelevant contract findings. Mitigation: start with persisted and serialized structures only and require an explicit allowlist or discovery rule.
- Ceremonial plan sections; severity: create/detail output becomes noisier for unrelated work. Mitigation: `Input contract` is conditional on consuming an existing contract, and tests should prove unrelated plans do not get the section.

## Testing

- Unit tests for the discovery/checker layer using small fixture dataclasses and sidecar-like structures.
- Completeness-report tests showing data-contract findings grouped/routed distinctly.
- Apply/walk tests proving approved contract edits are written and rejected edits leave files unchanged.
- Create/detail tests proving `Input contract` appears for contract-consuming plans and is absent for unrelated plans.
- Drift tests proving referenced fields in a per-plan `Input contract` are checked against HEAD.
- Existing `DATA_CONTRACT.md` drift guard, currently covered by `tests/test_data_contract.py`, must remain green or be replaced by a stronger deterministic guard with equivalent or stronger coverage.

## Acceptance criteria

- Completeness audit deterministically reports contract coverage drift for persisted/serialized structures missing from the canonical contract.
- Stale contract entries are detected with clear, actionable findings.
- Missing documented fields are detected with clear, actionable findings.
- Data-contract findings have a distinct source/domain in saved reports so the apply/walk path can route them separately from conceptual gaps.
- An interactive apply/walk can add or update a contract entry while preserving operator judgment over stability, invariants, and intentional exclusions.
- `create` / `detail` add an `Input contract` section only for plans that consume an existing contract.
- `Input contract` sections name code locations and fields verified at HEAD.
- A missing field referenced by an `Input contract` section produces a correctness finding.
- Existing `DATA_CONTRACT.md` drift guard remains green or is replaced by a more complete deterministic guard with equivalent or stronger coverage.
- `BACKLOG.md #63` is reconciled in the final step.

## Deferred

- Historical sidecar migration/version handling; defer because it is larger than the initial contract coverage subsystem.
- Richer semantic invariants beyond field existence and documented meaning; defer because semantic correctness remains handled by conceptual audit.
- Cross-repo contract references; defer as a separate concern beyond local plan-tool contracts.
- Generated contract diagrams or schema exports; defer as presentation/export work after the maintained contract surface exists.
- Telemetry linking contract findings to later reconcile failures; defer until the core detection and apply workflow ship.
