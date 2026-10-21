> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Retire Roadmap V1 Evidence
intent: Every receipt, impact-analysis, and structural-evidence reader in `plan_tool/roadmap_*.py`
  supports exactly one evidence schema (today's version 2) instead of dispatching
  between two, so the codebase carries one freshness rule instead of two and stops
  paying the maintenance cost of a path nothing exercises.
status: completed
priority: medium
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/retire-roadmap-v1-evidence.md
steps:
- id: 1
  title: Inventory live evidence, reissue eligible records as version 2, retain only
    non-routable legacy history, and block retirement on unresolved legacy finals
    without overwriting immutable finals
  intent: Ensure no project loses a usable evidence route when version-1 readers are
    removed.
  creates:
  - docs/history/roadmap-evidence-v1-retirement.md
  complexity: medium
  change_type: non-code
  detail: docs/implementation-plans/plan-details/retire-roadmap-v1-evidence/01-inventory-live-evidence-reissue.md
  status: done
- id: 2
  title: Make version 2 the only legal roadmap evidence schema, keep schema_version,
    and preserve structural journal recovery and replacement
  intent: Establish one enforceable evidence contract before removing the now-unreachable
    reader branches.
  files:
  - plan_tool/roadmap_source_identity.py
  - plan_tool/roadmap_escalation.py
  - plan_tool/roadmap_impact_analysis.py
  - plan_tool/roadmap_impact_snapshot.py
  - plan_tool/roadmap_structural_revision_run.py
  - ROADMAP_FORMAT.md
  - DATA_CONTRACT.md
  - docs/ARCHITECTURE.md
  - tests/test_roadmap_source_identity.py
  - tests/test_roadmap_escalation.py
  - tests/test_roadmap_escalation_run.py
  - tests/test_roadmap_escalation_selection.py
  - tests/test_roadmap_impact_analysis.py
  - tests/test_roadmap_impact_run.py
  - tests/test_roadmap_impact_snapshot.py
  - tests/test_roadmap_revision_publish.py
  - tests/test_roadmap_structural_revision.py
  - tests/test_roadmap_structural_revision_proof.py
  - tests/test_roadmap_structural_revision_run.py
  - tests/test_roadmap_format.py
  - tests/cli/test_roadmap_cmd.py
  allowed_mentions:
  - plan_tool/roadmap_impact_run.py
  - plan_tool/roadmap_structural_revision.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: The completed inventory proves that rejecting version-1 evidence will not strand
      a live project or namespace.
  detail: docs/implementation-plans/plan-details/retire-roadmap-v1-evidence/02-make-version-only-legal-roadmap.md
  status: done
- id: 3
  title: Remove unreachable version dispatch from receipt admission and inspection
    while keeping immutable receipt publication unchanged
  intent: Keep receipt creation and inspection from carrying a second freshness path
    that can drift from the shared rule.
  files:
  - plan_tool/roadmap_source_identity.py
  - plan_tool/roadmap_escalation.py
  - plan_tool/roadmap_escalation_selection.py
  - plan_tool/roadmap_escalation_run.py
  - tests/test_roadmap_source_identity.py
  - tests/test_roadmap_escalation.py
  - tests/test_roadmap_escalation_selection.py
  - tests/test_roadmap_escalation_run.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 2
  depends_on_notes:
    2: The strict schema gate makes the old raw-digest admission and receipt-rendering
      branches unreachable.
  detail: docs/implementation-plans/plan-details/retire-roadmap-v1-evidence/03-remove-unreachable-version-dispatch.md
  status: done
- id: 4
  title: Remove unreachable version dispatch from the impact-analysis lifecycle while
    keeping immutable analysis publication unchanged
  intent: Give impact analysis one baseline-identity freshness rule from snapshot
    capture through route inspection.
  files:
  - plan_tool/roadmap_impact_analysis.py
  - plan_tool/roadmap_impact_run.py
  - plan_tool/roadmap_impact_snapshot.py
  - tests/test_roadmap_impact_analysis.py
  - tests/test_roadmap_impact_run.py
  - tests/test_roadmap_impact_snapshot.py
  - tests/cli/test_roadmap_cmd.py
  complexity: high
  change_type: refactor
  depends_on:
  - 3
  depends_on_notes:
    3: Receipt admission now supplies impact analysis with only version-2 evidence
      and the sole currentness rule.
  detail: docs/implementation-plans/plan-details/retire-roadmap-v1-evidence/04-remove-unreachable-version-dispatch.md
  status: done
- id: 5
  title: Remove legacy structural preflight branches while preserving journal recovery
    and journaled artifact-and-seed replacement
  intent: Prevent unsupported evidence from reaching a structural route while leaving
    the established destructive publication safeguards intact.
  files:
  - plan_tool/roadmap_structural_revision.py
  - plan_tool/roadmap_structural_revision_run.py
  - tests/test_roadmap_structural_revision.py
  - tests/test_roadmap_structural_revision_run.py
  allowed_mentions:
  - plan_tool/roadmap_structural_operations.py
  complexity: high
  change_type: refactor
  depends_on:
  - 4
  depends_on_notes:
    4: The impact lifecycle now supplies a version-2-only analysis and snapshot pair
      for structural preflight.
  detail: docs/implementation-plans/plan-details/retire-roadmap-v1-evidence/05-remove-legacy-structural-preflight.md
  status: done
---
# Retire Roadmap V1 Evidence

## Overview

Retire the version-1 roadmap evidence path so every receipt, impact-analysis, and structural-evidence reader in `plan_tool/roadmap_*.py` supports exactly one evidence schema: version 2. The persisted `schema_version: 2` discriminator remains unchanged, while version-specific reader branches collapse to the sole surviving freshness rule. Existing projects must reissue live version-1 routes or move only non-routable history out of active evidence namespaces before removal; post-retirement readers must fail closed on an unarchived version-1 record without crashing, routing, or converting it. No new CLI syntax or version-2 creation behavior is introduced.

## Problem statement

The evidence readers currently dispatch between version 1's exact-raw-byte freshness and version 2's writer-owned baseline-identity freshness. Scattered dispatch logic has caused three confirmed regressions: applying the wrong version rule to a version-2 snapshot, allowing admission and consumption predicates to disagree, and failing to reject an unsupported version at `_preflight_is_canonical` in `roadmap_structural_revision_run.py:446`.

`BACKLOG.md` #307 consolidates the identical currentness predicate in `admitted_source_is_current` while leaving four architecturally different operations separate. Integration was the only known real consumer of the version-1 path and has migrated to version 2, so retaining the unused alternate path preserves the generative cause of this regression class and its maintenance cost.

## Architecture

- The `schema_version` field remains part of the persisted wire format, but 2 becomes its only legal value. `is_supported_evidence_schema_version` or its successor retains its intent-naming call sites and collapses from two-value membership to a single legal-value check; call sites do not inline a bare `== 2`.

- Existing projects upgrade before their version-1 reader is retired. Neither `plan_tool.roadmap_artifacts.roadmap_dir` (which resolves a supplied slug against the plans directory) nor `plan_tool.roadmap_evidence_store.scan_evidence` (which scans the resulting root's namespace) discovers "every known project" on its own. The release record's operator therefore curates the inventory universe explicitly: every project and roadmap slug known to use this package's roadmap evidence store, named by path, as of the record's stated cutoff date. Retirement proceeds only against that named, dated roster; an unresolved "every known project" claim with no roster behind it is itself a blocking condition. `DATA_CONTRACT.md`'s version-evolution policy requires "a user-approved retirement after every known consumer and live record has migrated or been deliberately archived" — the release record therefore also carries a dated, named approval of its roster, its dispositions, and the retirement decision itself; a zero-blocker record with no recorded approval is not a clean record. Immutable version-1 finals are never converted in place and never acquire a baseline identity by inference. Step 1 records exactly one disposition for every discovered version-1 final: **reissue** when current, eligible feedback can establish a writer-owned version-2 baseline and produce the replacement receipt and derived analysis, every consumer on the release record's dated consumer roster confirms cutover to the replacement, and the original's immutable bytes then move to the same dated history location outside every active evidence namespace that an archive-safe record uses — a reissued original left active is routable-in-name only and contradicts this Overview's "move only non-routable history out of active evidence namespaces"; **archive-safe** only when its owner confirms no current workflow needs the final as a route and the immutable bytes move to that same dated history location outside every active evidence namespace; or **blocking** when it remains an active route, cannot be reissued, or lacks that archival or cutover-and-retention confirmation. Every release record preserves the original final, its namespace, its replacement or history path, and the verification result. Retirement proceeds only when no blocking record remains and every reissue and archive-safe record alike proves both historical retention and absence from active scans.

- Both dispatch idioms are enumerated during `detail`: explicit `schema_version == 1` or `!= 1` branches, and checks such as `evidence_version == 2` that otherwise fall through to version-1 behavior. Every implicit fallthrough is replaced with explicit rejection of values other than 2.

- `admitted_source_is_current` remains the shared currentness gate and loses only its version-1 branch. `BACKLOG.md` #307's four do-not-merge findings remain settled because admission, comparison, self-consistency, and full-byte-render equality are different operations.

- New receipt and analysis creation remains on `NEW_RECEIPT_SCHEMA_VERSION = 2`, with no CLI override or new syntax. `build_receipt`'s own bare default (`RECEIPT_SCHEMA_VERSION = 1`) is never reached in production: its one call site (`_run_roadmap_escalation_receipt_while_guarded`) always threads the caller's `schema_version`, and that caller's (`run_roadmap_escalation_receipt`) own default is `NEW_RECEIPT_SCHEMA_VERSION`; the CLI's own call site never overrides it. A fresh process cannot therefore create a version-1 final through any CLI or known-consumer path. **Correction 2026-08-28:** this reasoning did not cover a process that had already imported the module before an editable source update; the two later Integration-local version-1 finals are archive-safe historical residue, and the stale-process mechanism remains unverified. The reader-refusal matrix retains each boundary's established failure shape for an unarchived version-1 record: `current_escalation_receipt` and the escalation view return `invalid` with no handoff; `run_roadmap_impact_analysis` returns `invalid` with no route or publication; `current_impact_analysis` and the impact-analysis view return `invalid` with no route; and `load_structural_revision_preflight` raises `StructuralRevisionPreflightError`, which `run_structural_revision` renders as `preflight-rejected` / `evidence-rejected`, once the evaluator is confirmed available, without invoking the model transport or publishing evidence. `verified_structural_evaluator` wraps evidence preflight, so an unavailable evaluator is classified `evaluator-rejected` before any evidence — legacy or current — is examined; that ordering is pre-existing and unchanged by this plan. Each matrix entry receives a direct boundary test and its CLI-view test where applicable; none crashes, silently upgrades the record, or labels it current.

- The implementation scope includes `plan_tool/roadmap_source_identity.py` and its version-dispatch primitives (`EVIDENCE_SCHEMA_VERSIONS`, `is_supported_evidence_schema_version`, `admitted_source_is_current`, and `admit_baseline_backed_source`); `roadmap_escalation.py`, `roadmap_escalation_run.py`, `roadmap_escalation_selection.py`, `roadmap_impact_analysis.py`, `roadmap_impact_run.py`, `roadmap_impact_snapshot.py`, `roadmap_structural_revision.py`, and `roadmap_structural_revision_run.py`; and `plan_tool/cli/roadmap_cmd.py` only where it renders or gates version-specific behavior. The published reader contract in `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, and `docs/ARCHITECTURE.md`, plus every test file mirroring a touched module, follows the same single-version contract.

- The structural-revision operation envelope's independent `version: 1` remains live and unchanged. `plan_tool/roadmap_structural_operations.py`, its tests, and the corresponding `ROADMAP_FORMAT.md` reference describe evaluator operations, not roadmap evidence schemas; they are excluded from this retirement and from its evidence-vocabulary sweep.

## References

- [Validators | Pydantic Docshttps: — Covers field and model validators for rejecting unsupported schema versions and enforcing cross-field evidence invariants.
- [Fields | Pydantic Docshttps: — Explains required fields, defaults, strict constraints, and default validation needed to remove legacy version fallbacks safely.
- [Serialization | Pydantic Docshttps: — Documents model serialization behavior used to preserve the schema_version discriminator in version-2 evidence.
- [PyYAML Documentationhttps: — Provides the safe_load and safe_dump APIs used to parse and render YAML evidence records and frontmatter.
- [YAML 1.2.2 Specificationhttps: — Defines the persisted YAML wire format, scalar typing, mappings, document markers, and loading failure behavior.
- [How to parametrize fixtures and test functionshttps: — Shows how to exercise every evidence reader against version 2 and unsupported legacy-version cases systematically.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changes to version-2 semantics, admission rules, or the baseline/canonical-identity contract; this plan deletes the alternate path rather than redesigning the surviving one.
- Reopening or re-litigating `BACKLOG.md` #307's closed consolidation or its do-not-merge findings.
- `BACKLOG.md` #242 and Integration's "receipt preflight" gate; that work is unrelated, already in progress on Integration's side, and untouched by this removal.
- A generic in-place version-1-to-version-2 evidence converter; version-1 evidence lacks the writer-owned baseline identity such a converter would have to infer, so scoped reissue or archival remains the upgrade path.
- The structural-revision operation envelope's independent `version: 1` protocol, including `plan_tool/roadmap_structural_operations.py`, its tests, and its `ROADMAP_FORMAT.md` reference.

## Risks

- **Failure shape:** A removed version-1 branch may also perform validation or field population absent from its version-2 sibling. **Severity:** The surviving version-2 path can silently lose behavior. **Mitigation:** Compare each removed branch's complete body with the version-2 branch before deletion, not only its comparison expression. **Unresolved gap:** The affected branch bodies must be enumerated during `detail`.
- **Failure shape:** Removing an implicit version-1 fallthrough without explicitly rejecting unsupported values repeats the known `_preflight_is_canonical` regression. **Severity:** Unsupported evidence can bypass fail-closed handling. **Mitigation:** Every site converted from "checks == 2, else assumes v1" explicitly rejects anything other than 2 and receives a proving test. **Unresolved gap:** Both explicit and implicit dispatch idioms must be found.
- **Failure shape:** An identifier-only documentation edit can leave roadmap-evidence-schema version-1 comparisons, framing, and cross-references describing a contract that no longer ships. **Severity:** `ROADMAP_FORMAT.md` and `DATA_CONTRACT.md` can misstate the reader contract. **Mitigation:** Sweep roadmap-evidence-schema version-1 vocabulary as well as identifiers across `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, and `docs/ARCHITECTURE.md`, while retaining the unrelated structural-operation envelope reference. **Unresolved gap:** Dated migration or retirement provenance is the only permitted remaining evidence-schema version-1 reference.
- **Failure shape:** An undisclosed version-1 consumer or live record remains at release time. **Severity:** Retirement is blocked. **Mitigation:** The release record names an explicit, dated project/roadmap roster and a separate dated consumer roster (see `## Architecture`) and inventories both namespaces for every roster entry; a roster with no named entries, or an "every known project" claim with no roster behind it, is itself blocking. Neither `_load_requested_receipt` nor `load_structural_revision_preflight` can discover a consumer from code — the consumer roster is the operator's own attestation, the same as the project roster. **Unresolved gap:** Integration is the only consumer currently known to the operator; both rosters must still be stated explicitly rather than left implicit, and the release record's dated approval (see `## Architecture`) is the accountable owner's sign-off that the named rosters are complete.

## Testing

- Keep every mirrored test file for a touched module green after deleting, rather than skipping or marking `xfail`, its roadmap-evidence-schema-version-1-only tests and updating evidence-version-1-dependent fixture defaults to the sole remaining version. Keep the unrelated structural-operation-envelope `version: 1` tests unchanged.
- Add a fail-closed assertion for every site converted from the implicit-fallthrough idiom, using a value other than 2.
- Keep `tests/test_roadmap_format.py` identity-bound example-parsing tests passing with only the version-2 reference example.
- Prove the three transition outcomes — a version-1 record that safely reissues as version 2, an archive-safe record retained outside active evidence namespaces, and a record that remains blocking because it needs a route or lacks archival confirmation — through step 1's own release-record verification (`verify_reissue_chain`, `verify_archive_retention_and_absence`, `verify_archive_confirmation`, `verify_blocking_gate`), not automated pytest fixtures: no production code classifies a disposition, so there is no code path for a fixture to exercise, and the human-reviewed record is the reviewable proof for these three cases. Prove every reader-matrix entry refuses an unarchived version-1 record: receipt inspection and its CLI view report `invalid` with no handoff; impact publication reports `invalid` with no route or evidence write; impact inspection and its CLI view report `invalid` with no route; and, given an available evaluator, structural preflight rejects the pair before any model invocation or publication — prove the legacy rejection reaches neither the model transport nor the publisher.
- Run `uv run pytest tests/ -q -n auto`. The full suite must leave no roadmap-evidence-owned production module, matching test, or versioned roadmap contract reference treating 1 as an evidence schema version; unrelated format versions such as `SOURCE_IDENTITY_VERSION = 1` and the structural-operation-envelope `version: 1` remain excluded from this sweep.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (non-code) — verification appropriate to the artifacts rather than unit tests.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (refactor) — tests covering the behavior this step changes; green before completion.
- step 4 (refactor) — tests covering the behavior this step changes; green before completion.
- step 5 (refactor) — tests covering the behavior this step changes; green before completion.

## Acceptance criteria

- No production code path branches on `schema_version` or `evidence_version` taking any value other than 2, and the shared validity check enforces exactly one legal value.
- `schema_version: 2` remains persisted and parseable on every evidence type, and Integration's existing version-2 evidence parses unchanged.
- The release record states an explicit, dated project/roadmap roster and a separate dated consumer roster, and, for every roster entry's live evidence namespace, either records no active version-1 evidence or assigns every discovered version-1 final exactly one reissue, archive-safe, or blocking disposition; any active route, failed reissue, unconfirmed consumer cutover, or unconfirmed archive blocks retirement, while every reissue and archive-safe result alike retains immutable history outside active scans. The record carries a dated, named approval of its rosters, dispositions, and retirement decision, per `DATA_CONTRACT.md`'s user-approved-retirement requirement.
- `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, and `docs/ARCHITECTURE.md` describe one evidence contract, with no residual roadmap-evidence-schema version-1 vocabulary or cross-reference beyond dated migration or retirement provenance; the unrelated structural-operation-envelope `version: 1` reference remains intact.
- Receipt inspection, impact publication, impact inspection, structural preflight, and their applicable CLI views return the reader-matrix's documented fail-closed result for an unarchived version-1 record; none crashes, silently upgrades it, invokes the model transport, publishes evidence, or treats it as current.
- `uv run pytest tests/ -q -n auto` passes, no test retains version 1 as a supported evidence path or an `xfail`/skip, and the explicit legacy fixture remains only to prove the documented fail-closed refusal.

## Deferred

_(none)_
