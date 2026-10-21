> **Replaced**: this file has been superseded by `docs/implementation-plans/2-data-contract-subsystem.md`.
> Preserved here for history; do not edit.

# Plan seed: data-contract subsystem

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/data-contract-subsystem.md --iterate
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Source: BACKLOG.md #63** ("Data-contract subsystem"), grounding facet of the
> Quality/accuracy lens. This plan MUST update `BACKLOG.md #63` when the work
> ships — remove the entry, or mark the shipped subsystem and split any deferred
> remainder into a new backlog item. The existing hand-authored
> `DATA_CONTRACT.md` and drift guard are bootstrap artifacts, not the finished
> subsystem.

---

## Overview

Build a first-class data-contract subsystem for plan-tool's persisted and
serialized structures. The subsystem should turn today's hand-maintained
`DATA_CONTRACT.md` into a maintained contract surface with deterministic drift
detection, an interactive update/apply workflow, and create/detail integration
for plans that depend on existing data shapes.

The target is one coherent capability with four touchpoints:

1. Canonical app-level contract reference for persisted/serialized structures.
2. Completeness-audit detection for structures or fields missing contract
   coverage.
3. Bespoke interactive apply/walk to create or update contract entries.
4. Conditional per-plan `Input contract` sections, verified against code at HEAD,
   when a plan consumes an existing contract.

## Problem Statement

Plan-tool has strong authoring-format docs (`PLAN_FORMAT.md`,
`DETAIL_FORMAT.md`, `JIRA_FORMAT.md`), but the persisted layer consumed by
reconcile, completeness, annotations, and saved reports has only a bootstrapped
manual contract. That gap has already caused planning against imagined saved
schemas: #57's convergence work originally reasoned about a `SavedReview` shape
that did not match what was actually persisted.

The existing `DATA_CONTRACT.md` plus `tests/test_data_contract.py` prove the
discipline is useful, but they are not enough:

- The code cannot yet tell the operator which persisted dataclass or sidecar
  field lacks contract coverage during completeness audit.
- Updating the contract is manual, even though field candidates can be
  discovered deterministically.
- Plans that consume an existing persisted/API/output contract have no
  standardized, HEAD-verified `Input contract` section to ground their premises.
- There is no workflow boundary between deterministic detection and
  judgment-heavy field classification.

## Design

### Canonical App-Level Contract

Keep source of truth in code: dataclasses, JSON sidecar readers/writers, and
serialization code win if documentation disagrees. The contract document is a
human-readable reference and audit target, not an alternate schema engine.

Scope the initial app-level contract to persisted/serialized structures already
named by the backlog item and current code:

- saved review / reconcile / completeness sidecar JSON records
- `Recommendation` and related finding metadata
- annotation output structures
- fingerprints and freshness metadata
- `.plan-tool/plans.json` or any current plan-tool registry/config file that is
  treated as durable state

Do not broaden into every in-memory dataclass. The trigger is persistence,
serialization, public output consumed by later commands, or data that a plan may
need to depend on.

### Deterministic Completeness-Audit Check

Add a deterministic authoring check that discovers persisted structures and
compares them to contract coverage. It should report findings alongside existing
well-formedness / files-coherence / structural diagnostics.

The check should detect at least:

- a persisted dataclass or sidecar object with no contract entry
- a documented structure whose code target no longer exists
- a persisted field missing from the contract entry
- a documented field missing from the current code

Keep this deterministic and conservative. It should identify candidate drift and
coverage gaps; it should not infer semantic invariants by itself.

### Bespoke Interactive Apply

Add an apply/walk path for data-contract findings. Introspection can generate
candidate structures and fields, but deciding the public contract is judgment:
stable versus internal, required versus optional, invariant wording, migration
notes, and intentionally undocumented fields.

The apply flow should mirror the conceptual-gaps discipline:

- audit detects candidates and saves findings
- apply walks each finding interactively
- user approves contract edits
- generated edits update the contract reference, not production code

Do not make the initial contract update a one-shot dump of every field. The
output must be maintainable prose that a later plan can cite.

### Per-Plan Input Contract Section

Teach create/detail to add an `Input contract` section only when a plan's
correctness depends on an existing data structure, persisted schema, API surface,
or output format.

This is conditional, not universal. Do not add ceremony to greenfield feature
plans, pure refactors, docs/process changes, or bug fixes that do not consume an
existing contract.

When present, the section should state:

- the existing contract being consumed
- the fields or shape the plan depends on
- the code locations verified at HEAD
- any known limits: field shape is verified, but semantic misuse still requires
  the normal plan audit loop

Mechanized check: named fields in the section must exist in code at HEAD, using
the existing grounding/fingerprint style where practical. Absence or drift should
be a correctness finding.

## Step Decomposition Guidance

Propose single-concern steps. A reasonable plan shape is:

1. **Discovery spike / contract inventory** — identify the current persisted
   structures, readers, writers, and existing `DATA_CONTRACT.md` conventions.
   Output should guide the remaining implementation steps and avoid over-scoping
   to in-memory-only dataclasses.
2. **Deterministic contract coverage check** — add the audit-side detector and
   focused tests for missing structure, missing field, stale documented field,
   and intentionally out-of-scope structures.
3. **Report and saved-finding integration** — surface contract findings in
   completeness reports with a clear domain/source so they can be routed
   separately from conceptual correctness gaps.
4. **Interactive data-contract apply/walk** — add the bespoke update path that
   edits `DATA_CONTRACT.md` or the canonical contract reference after operator
   approval.
5. **Create/detail `Input contract` authoring** — add conditional plan-section
   generation when existing contracts are consumed.
6. **HEAD verification for per-plan Input contracts** — assert referenced fields
   still exist and route drift as correctness findings.
7. **Docs and backlog reconciliation** — update `RUNBOOK.md` / relevant format
   docs, and reconcile `BACKLOG.md #63` with shipped/deferred scope.

If the subsystem is too large after detail authoring, prefer splitting at the
boundary between app-level contract maintenance and per-plan `Input contract`
integration. Do not silently drop backlog touchpoint 4; split it into an
explicit follow-up if needed.

## Out Of Scope

- A runtime validation framework for every persisted JSON file.
- A full migration/versioning subsystem for old sidecars.
- Semantic correctness of a plan that uses valid fields incorrectly. The
  contract section verifies shape and existence; conceptual audit still validates
  meaning.
- Universal `Input contract` sections on every plan.
- Treating generated introspection output as authoritative without human review.

## Risks

- **Over-documenting internal fields.** Mitigation: make public/stable versus
  internal/implementation detail an explicit interactive apply decision.
- **False confidence from HEAD shape checks.** Mitigation: document that shape
  verification is a floor, not the semantic audit.
- **Import cycles from introspection helpers.** Mitigation: keep discovery in a
  leaf or body-local imports; mirror existing completeness/report patterns.
- **Audit noise from broad discovery.** Mitigation: start with persisted and
  serialized structures only; require an explicit allowlist or discovery rule.
- **Ceremonial plan sections.** Mitigation: `Input contract` is conditional on
  consuming an existing contract; tests should prove unrelated plans do not get
  the section.

## Acceptance Criteria

- Completeness audit deterministically reports contract coverage drift for
  persisted/serialized structures missing from the canonical contract.
- Stale contract entries and missing documented fields are detected with clear,
  actionable findings.
- Data-contract findings have a distinct source/domain in saved reports so the
  apply/walk path can route them without confusing them with conceptual gaps.
- An interactive apply/walk can add or update a contract entry while preserving
  operator judgment over stability, invariants, and intentional exclusions.
- `create` / `detail` add an `Input contract` section only for plans that consume
  an existing contract.
- `Input contract` sections name code locations and fields verified at HEAD; a
  missing field produces a correctness finding.
- Existing `DATA_CONTRACT.md` drift guard remains green or is replaced by a more
  complete deterministic guard with equivalent or stronger coverage.
- `BACKLOG.md #63` is reconciled in the final step.

## Suggested Validation

- Unit tests for the discovery/checker layer using small fixture dataclasses and
  sidecar-like structures.
- Completeness-report tests showing data-contract findings grouped/routed
  distinctly.
- Apply/walk tests proving approved contract edits are written and rejected edits
  leave files unchanged.
- Create/detail tests proving `Input contract` appears for contract-consuming
  plans and is absent for unrelated plans.
- Drift tests proving referenced fields in a per-plan `Input contract` are
  checked against HEAD.

## Deferred Candidates

If scope must be split, defer explicitly:

- historical sidecar migration/version handling
- richer semantic invariants beyond field existence and documented meaning
- cross-repo contract references
- generated contract diagrams or schema exports
- telemetry linking contract findings to later reconcile failures
