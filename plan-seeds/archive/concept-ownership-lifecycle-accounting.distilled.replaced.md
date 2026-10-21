> **Replaced**: this file has been superseded by `docs/implementation-plans/2-concept-ownership-lifecycle-accounting.md`.
> Preserved here for history; do not edit.

## Overview

Make concept accounting survive create restoration, split, merge, re-ground, scope-out, and include-triggered regeneration. After every supported lifecycle transformation, each reviewed concept must have an exact active owner or a valid structured non-delivery record; a decision such as `wont_do`, an unsigned proposal, or a heuristic match is not enough. The plan consumes the public mutation/publication contract from `concept-publication-transactions`, the structured authoring protocol from `concept-authoring-boundary-hardening`, and the reconciled ownership schema, merge conservation, and re-ground preservation from `concept-signoff-integrations` without reimplementing them.

## Problem statement

`Step.concept_ids` is authoritative and already survives merge and re-ground, but accounting is incomplete across the full lifecycle. `check_concept_coverage()` currently treats an approved `wont_do` node as covered without a structured non-delivery record; split and merge can leave structured deferrals pointing to removed or renumbered steps; and split tests do not directly reject invented IDs or prove exact dry-run ownership distribution.

Re-ground and scope-out render concept IDs into seeds, but create does not consume them as authoritative restoration metadata or reconcile them with the signed concept record. This permits dropped, invented, stale, contradictory, or ambiguously mapped accounting information to escape explicit review. Generated CLI documentation also derives from parser help, so editing the generated README/index directly causes drift-check failures.

The missing invariant is a conservation law covering both delivery and deliberate non-delivery. The evidence to close is `step5-run-reconcile-69028ee5`, `step5-run-reconcile-6b8b7ab0`, `step6-run-reconcile-cb54717a`, `step6-run-reconcile-be1832fa`, `structural-deferral-links`, `forward-seed-ownership-restoration`, and `step10-run-reconcile-d05fb53f`.

## Architecture

For every reviewed concept whose decision is active in the signed record, valid accounting consists of either delivery through one or more committed/done steps containing the exact stable concept ID, or a structured non-delivery record containing the concept ID, `defer` or `wont_do`, rationale/evidence, review/approval state, and a stable source/artifact reference. `Step.concept_ids` continues to allow multiple owners. Contradictory simultaneous delivery and signed non-delivery is rejected unless the data contract explicitly models a partial decision; unsigned proposals and title/body matches remain advisory.

Define one durable non-delivery accounting contract in `plan_tool/concept_tree.py`, `plan_tool/detail.py`, `plan_tool/data_contract.py`, and `DATA_CONTRACT.md`, reusing the structured detail candidate model where possible. Pure validation and transformation helpers are shared by create, detail, completeness, and structural remedies, while every durable update is persisted through the prerequisite publication API.

Deferral identity must remain independent of mutable step numbers where possible. If an emitting step/artifact reference remains, split explicitly maps it to the inheriting child or children without inventing or dropping IDs; merge maps it to the replacement step and deterministically deduplicates equivalent records; re-ground preserves unchanged links and carries restoration metadata for replacements; scope-out converts concepts with no surviving owner into structured non-delivery records and clears approval when the decision changes; and include-triggered regeneration removes a resolved deferral only after the new artifact is durable. A stable artifact ID may be introduced only with a bounded persisted contract and migration/default behavior; title matching is never a fallback.

Re-baseline and forward seeds carry a bounded machine-readable ownership/accounting envelope containing stable concept IDs, source step/artifact identity, disposition, and provenance sufficient to compare the originating signed record. Create parses this envelope before model synthesis and uses an explicit proposal/review phase to restore exact mappings. Validation detects unknown concept IDs, stale or mismatched source record fingerprints, ambiguous source-to-proposal mappings, dropped concepts, invented IDs, and conflicts with current signed decisions; unattended create stops or retains unsigned restoration proposals instead of guessing.

`check_concept_coverage()` remains read-only and inert when no record exists. For a current record, it emits one stable finding for every unaccounted reviewed concept regardless of `include`, `defer`, or `wont_do`, uses policy-appropriate remediation, preserves the separate nonblocking advisory for unsigned parked decisions, and reports dangling ownership or deferral links without counting them as coverage.

The implementation surfaces are `plan_tool/review.py`, `plan_tool/completeness_report.py`, `plan_tool/cli/completeness_phases.py`, `plan_tool/create.py`, `plan_tool/reground.py`, `plan_tool/scope_out.py`, the relevant seed/distillation prompt or parser, and the parser/help source for completeness commands. Documentation must be changed at its source and regenerated through the repository generator before updating `docs/cli/completeness-audit.md`, `docs/cli/completeness-apply.md`, `RUNBOOK.md`, `CLAUDE.md`, or `BACKLOG.md`.

## Out of scope

- Canonical publisher internals, rollback journals, create collision staging, or sidecar-only review persistence — these are not part of lifecycle accounting policy.
- Evidence grounding, Unicode fail-soft behavior, structured-response parsing, and detail active-file replacement — these belong to separate hardening work.
- Heuristic matching as coverage authority — only exact structured links count.
- Automatically inventing implementation steps to cover concepts — this plan conserves and validates accounting rather than synthesizing coverage.
- General migration of arbitrary experimental sidecars/seeds without the shipped schema/provenance — restoration is limited to the defined envelope.
- Reimplementing already-clean merge union or re-ground preservation — these remain prerequisites and regression fixtures.

## Risks

- **Deferral identity duplicates concept identity.** Severity: the two identities can be conflated in persisted accounting. Keep the concept ID and accounting record ID/source identity distinct and document their roles; no unresolved gap is stated.
- **Step-number coupling remains.** Severity: transformed records can point to the wrong or deleted step. Use stable artifact identity or explicit transform maps and never assume renumbered IDs identify the same step; the stable artifact contract is bounded to this plan if introduced.
- **Seed prose becomes authority.** Severity: create can silently restore an incorrect mapping. Parse a bounded envelope, validate it against the signed record, and treat prose as context only; unattended create must not guess.
- **Many-owner semantics collapse.** Severity: valid shared ownership can be rejected or lost. Conserve ordered sets without imposing one exclusive owner and test shared and sole ownership separately; no unresolved gap is stated.
- **`wont_do` becomes impossible to satisfy.** Severity: completeness can block every `wont_do` concept. Define the structured record and operator workflow before enabling the blocking finding; that workflow remains required implementation work.
- **Cross-plan persistence bypass.** Severity: accounting updates can escape transaction and rollback guarantees. Route every durable update through the publisher shipped by `concept-publication-transactions`; publisher internals remain outside this plan.
- **Generated docs drift.** Severity: documentation checks fail or publish inconsistent CLI behavior. Modify parser/help sources first and run the documented generator; no unresolved gap is stated.

## Testing

Use unit tests first for validation, transformation, completeness, and seed-envelope behavior. Add integration coverage only where cross-module behavior is essential: create restoration through publication, lifecycle transitions followed by completeness/reconcile behavior, CLI report production, publication failure, and rollback.

- `tests/test_concept_tree.py`: validate durable deferral/`wont_do` record identity, required fields, decision conflicts, multiple owners, unsigned records, and dangling or stale links.
- `tests/test_data_contract.py`: validate persisted schema, defaults or migration behavior, provenance, stable source/artifact identity, and malformed records.
- `tests/test_review.py`: exercise `check_concept_coverage()` for zero, one, and multiple owners; valid, missing, unsigned, dangling, stale, and contradictory non-delivery records; multiple missing concepts; unsigned included and parked candidates; renumber-stable IDs; stable finding IDs; and advisory-only behavior.
- `tests/cli/test_completeness_cmd.py`: verify producer parity, report rendering, nonblocking advisories, policy-appropriate remediation, and ownership gaps that are not apply-eligible.
- `tests/test_create.py`: verify split conservation, direct rejection of missing or invented IDs, exact dry-run ownership distribution, ambiguous deferral mapping, rejected proposals, forward/re-baseline envelope restoration, stale fingerprints, unknown/invented/dropped IDs, ambiguous mappings, legacy seeds, interactive resolution, and unattended unresolved state.
- `tests/test_detail.py`: verify split/merge transformation of structured accounting records, deterministic merge deduplication, links to removed steps, shared ownership, and include-triggered removal only after durable regeneration.
- `tests/test_reground.py`: verify mark-done and re-baseline envelopes for done, remaining, and parked steps, exact link preservation, replacement metadata, and no ownership union.
- `tests/test_scope_out.py`: verify surviving external owners, sole owners, multiple carved owners, conversion to structured non-delivery, approval clearing, blocked/declined/dry-run behavior, legacy no-sidecar input, stale/malformed records, publication failure, and rollback.
- Integration tests for completeness/reconcile behavior: run create restoration, split, merge, re-ground, scope-out, include regeneration, and completeness after each transition using fixtures with multiple concepts, shared and sole owners, `defer`, `wont_do`, unsigned proposals, and structured records. Assert exact IDs and links, absence of title inference, transaction API usage, publication failure behavior, and rollback.
- Generated documentation checks: modify parser/help sources, regenerate the CLI reference/index through the existing generator, and verify `docs/cli/completeness-audit.md`, `docs/cli/completeness-apply.md`, `RUNBOOK.md`, `CLAUDE.md`, and `BACKLOG.md` claims against actual symbols.

The focused lifecycle tests, full suite, completeness audits, generated CLI reference drift checks, and `reconcile-code` must pass. Test strategy by implementation sequence: 1. structured non-delivery accounting — tests with implementation; 2. completeness semantics and diagnostics — tests with implementation; 3. split/merge deferral conservation — characterization of shipped conservation followed by tests with implementation; 4. seed round-trip accounting — tests with implementation; 5. lifecycle conservation matrix — integration verification; 6. CLI/docs and backlog reconciliation — artifact-appropriate generation and drift verification.

## Acceptance criteria

- After every supported lifecycle operation, each reviewed concept has at least one exact committed/done owner or one valid structured non-delivery record.
- `check_concept_coverage()` does not treat a `wont_do` decision alone as complete and emits a stable finding when its structured accounting record is absent or invalid.
- Unsigned proposals and heuristic matches never satisfy blocking accounting; unsigned parked decisions retain their separate nonblocking advisory.
- Split and merge conserve exact concept IDs and valid deferral links, and no resulting link identifies a removed or incorrect step.
- Split proposal validation rejects missing and invented IDs, and dry-run results preserve the exact ownership distribution.
- Re-ground and scope-out seeds contain machine-readable exact accounting metadata, and create restores it or requires explicit review without title inference.
- Unknown, dropped, invented, stale, contradictory, or ambiguous restoration input fails or remains explicitly unsigned and is never silently accepted.
- Scope-out validates its prepared accounting transformation and publishes it only through the prerequisite transaction API.
- Parser/help sources remain authoritative for CLI documentation, regenerated artifacts pass drift checks, and no generated row is maintained by hand.
- Focused lifecycle tests, the full suite, completeness audits, generated CLI reference drift checks, and `reconcile-code` pass without accounting or generated-documentation redirects.

## Deferred

- Publication and rollback mechanics — owned by `concept-publication-transactions` and consumed here as a prerequisite.
- Model-output and detail replacement hardening — owned by `concept-authoring-boundary-hardening`.
- Automatic covering-step generation and concept-decision telemetry — remain separate future work.
