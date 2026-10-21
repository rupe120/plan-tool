> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Concept Decision Record Core
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add the stable concept record and integrity-aware persistence
  files:
  - plan_tool/data_contract.py
  - DATA_CONTRACT.md
  - tests/test_data_contract.py
  creates:
  - plan_tool/concept_tree.py
  - tests/test_concept_tree.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/concept-decision-record-core/01-stable-concept-record-integrity-aware.md
  status: done
- id: 2
  title: Move plan body section parsing into the parser
  files:
  - plan_tool/parser.py
  - plan_tool/review.py
  - tests/test_parser.py
  - tests/test_review.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/concept-decision-record-core/02-move-plan-body-section-parsing-parser.md
  status: done
- id: 3
  title: Add deterministic concept bootstrap and conflict-aware re-derivation
  files:
  - plan_tool/parser.py
  - plan_tool/schema.py
  creates:
  - plan_tool/concept_bootstrap.py
  - tests/test_concept_bootstrap.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/concept-decision-record-core/03-deterministic-concept-bootstrap.md
  status: done
- id: 4
  title: Add three-state concept review and scoped sign-off
  creates:
  - plan_tool/concept_review.py
  - tests/test_concept_review.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 3
  detail: docs/implementation-plans/plan-details/concept-decision-record-core/04-three-state-concept-review-scoped-sign.md
  status: done
- id: 5
  title: Add the canonical concept and plan synchronizer
  files:
  - plan_tool/parser.py
  - plan_tool/schema.py
  creates:
  - plan_tool/concept_sync.py
  - tests/test_concept_sync.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/concept-decision-record-core/05-canonical-concept-plan-synchronizer.md
  status: done
- id: 6
  title: Add the scope-review command and register its CLI surface
  files:
  - plan_tool/cli/app.py
  - plan_tool/cli/parser.py
  - plan_tool/cli/__init__.py
  - CAPABILITIES.md
  - docs/cli/README.md
  - tests/cli/package_surface_help.golden.txt
  - tests/cli/test_app_lock.py
  - tests/cli/test_package_surface.py
  - tests/cli/test_cli_reference.py
  creates:
  - plan_tool/cli/scope_review_cmd.py
  - docs/cli/scope-review.md
  - tests/cli/test_scope_review_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/concept-decision-record-core/06-scope-review-command-register-its-cli.md
  status: done
- id: 7
  title: Document the concept decision contract and scope-review workflow
  files:
  - CLAUDE.md
  - RUNBOOK.md
  - TESTING.md
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 6
  detail: docs/implementation-plans/plan-details/concept-decision-record-core/07-document-concept-decision-contract.md
  status: done
---
# Concept Decision Record Core

## Overview

This plan adds a stable concept decision record that can be built from a plan, reviewed in scoped parts, and kept in sync with the plan body. It exists so concept decisions retain their identity and review state as plans change, while detecting stale data and re-derivation conflicts instead of silently overwriting them. The design uses deterministic bootstrap defaults, integrity-aware persistence, shared parser and schema integration, and a `scope-review` CLI whose exit codes distinguish successful review from conflicts or invalid state.

## Problem statement

Plans currently encode concept decisions only in mutable prose, without a stable record that preserves decision identity, review state, or the relationship between reviewed concepts and their source sections. As a plan evolves, tooling cannot reliably distinguish an intentional edit from stale derived data, detect conflicting re-derivation, or keep the plan body and reviewed concept state synchronized. Users therefore risk losing prior review decisions or silently carrying obsolete scope forward, with no command that can report and resolve those conflicts before sign-off.

## Architecture

The core is a persisted concept tree whose nodes carry stable identity, source linkage, decision content, and review state. `plan_tool/concept_tree.py` owns that domain model, while the existing data-contract layer defines its serialized form and integrity metadata. Persistence validates the record and its plan fingerprint before use and publishes updates atomically, favoring explicit stale or invalid-state failures over silently accepting partially written or obsolete data.

Plan-body section parsing moves into `plan_tool/parser.py` as shared infrastructure rather than remaining coupled to review behavior. Bootstrap and synchronization both consume the same parsed representation and schema rules, so section boundaries and validation semantics have one authority. This refactor precedes derivation because deterministic source-to-concept mapping depends on stable parser output.

`plan_tool/concept_bootstrap.py` derives the initial tree deterministically from parsed plan sections and re-derives it when the source changes. Stable source-derived identifiers preserve concept identity across unchanged input; when new derivation conflicts with reviewed or independently changed state, the operation reports a conflict instead of overwriting either side. The trade-off is additional reconciliation state in exchange for preserving human decisions and making drift observable.

`plan_tool/concept_review.py` applies three-state review decisions to explicit concept scopes, and sign-off is valid only for the selected scope and current source state. `plan_tool/concept_sync.py` is the canonical boundary for propagating accepted changes between the concept record and plan body; it depends on the shared parser, schema, persistence, and derivation contracts so other callers do not implement competing merge behavior.

The `scope-review` command is a thin orchestration layer over bootstrap, review, and synchronization. It loads and validates state, limits work to the requested scope, persists the record and Markdown consistently, and maps success, conflict, and invalid state to distinct exit outcomes. Keeping CLI policy above the domain modules leaves those modules reusable and testable while making conflict handling explicit to automation.

## References

- [Python uuid — UUID Objects](https://docs.python.org/3/library/uuid.html) — Documents the standard-library APIs for generating, parsing, and preserving opaque stable UUID identifiers.
- [RFC 9562 — Universally Unique IDentifiers](https://www.rfc-editor.org/rfc/rfc9562.html) — Defines UUID formats and generation semantics relevant to stable concept identity and deterministic source-derived identifiers.
- [Python json — JSON Encoder and Decoder](https://docs.python.org/3/library/json.html) — Covers strict JSON serialization and parsing options needed for exact persisted-record round trips and integrity validation.
- [Python os — Miscellaneous Operating System Interfaces](https://docs.python.org/3/library/os.html) — Documents os.replace, fsync, and related filesystem primitives needed to publish staged files safely.
- [Python tempfile — Generate Temporary Files and Directories](https://docs.python.org/3/library/tempfile.html) — Covers secure temporary-file creation and platform caveats relevant to staging atomic record and Markdown updates.
- [Python hashlib — Secure Hashes and Message Digests](https://docs.python.org/3/library/hashlib.html) — Documents deterministic digest APIs suitable for plan fingerprints and stale-record detection.
- [Python argparse — Parser for Command-Line Options](https://docs.python.org/3/library/argparse.html) — Defines command, flag, help, and error-handling APIs applicable to the scope-review CLI surface.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- General-purpose plan editing outside concept-backed sections — this plan limits synchronization to the canonical concept decision boundary.
- Collaborative or remote review workflows — the scope-review contract covers local persisted state and CLI orchestration only.
- Automatic resolution of re-derivation or synchronization conflicts — preserving reviewed human decisions requires explicit reconciliation.
- Migration of existing plan prose into reviewed concept state without bootstrap — deterministic bootstrap remains the required entry point for legacy plans.

## Risks

- Stable source-derived identifiers can change when section boundaries or normalization rules change, orphaning prior review state; severity: high; mitigation: centralize parsing and schema rules and treat identity changes as re-derivation conflicts; unresolved gap: intentional structural rewrites still require explicit reconciliation.
- A stale fingerprint, partial write, or mismatched concept record can cause reviewed decisions to be applied to the wrong plan state; severity: high; mitigation: validate integrity and the plan fingerprint before use and publish updates atomically; unresolved gap: failures between coordinated record and Markdown updates may still require recovery from the last valid state.
- Bootstrap or synchronization can overwrite reviewed or independently edited content when both sides diverge; severity: high; mitigation: route propagation through the canonical synchronizer and surface conflicts instead of choosing a winner; unresolved gap: conflict resolution remains a manual workflow.
- Scope selection can omit dependent concepts or allow sign-off over an incomplete decision set; severity: medium; mitigation: bind review state and sign-off to the explicit scope and current source state; unresolved gap: the initial contract may not detect every semantic dependency between concepts.
- Distinct conflict and invalid-state failures can be collapsed or mishandled by CLI automation; severity: medium; mitigation: assign stable, documented exit outcomes and cover them with command tests; unresolved gap: downstream callers must still interpret those outcomes correctly.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- Persisted concept records round-trip without changing stable concept identifiers, source linkage, decision content, or three-state review values, and loading rejects malformed integrity metadata or a plan-fingerprint mismatch; `tests/test_concept_tree.py` and `tests/test_data_contract.py` prove these cases.
- Plan-body section parsing in `plan_tool/parser.py` produces the same section boundaries and review behavior characterized before the refactor; `tests/test_parser.py` and `tests/test_review.py` pass unchanged expectations.
- Repeated bootstrap of unchanged plan content produces the same concept tree and identifiers, while re-derivation reports a conflict rather than overwriting reviewed or independently changed state; `tests/test_concept_bootstrap.py` covers both outcomes.
- Review operations accept all three review states only within the requested concept scope, and sign-off fails when that scope is incomplete or its source state is stale; `tests/test_concept_review.py` verifies the contract.
- Synchronization through `plan_tool/concept_sync.py` propagates accepted changes between the concept record and plan body, preserves unrelated Markdown, and reports divergent edits as conflicts without choosing a winner; `tests/test_concept_sync.py` verifies these invariants.
- `plan-tool scope-review` is present in package help, limits changes to the requested scope, persists consistent record and Markdown results on success, and returns distinct nonzero outcomes for conflicts and invalid state; `tests/cli/test_scope_review_cmd.py`, `tests/cli/test_package_surface.py`, and the package help golden file cover the public behavior.
- `CAPABILITIES.md`, `docs/cli/scope-review.md`, `docs/cli/README.md`, `RUNBOOK.md`, and `TESTING.md` document the same scope-review command, three-state review contract, conflict behavior, and exit outcomes exposed by the CLI.

## Deferred

- Automated resolution of re-derivation and synchronization conflicts — postpone until the manual reconciliation workflow establishes safe resolution policies.
- Transactional recovery across coordinated concept-record and Markdown updates — defer as a separate durability concern beyond atomic publication of each artifact.
- Semantic dependency detection between concepts — postpone until dependency relationships can be modeled without weakening explicit scoped sign-off.
