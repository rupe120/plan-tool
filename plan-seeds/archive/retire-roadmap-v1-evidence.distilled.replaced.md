> **Replaced**: this file has been superseded by `docs/implementation-plans/2-retire-roadmap-v1-evidence.md`.
> Preserved here for history; do not edit.

## Overview

Retire the version-1 roadmap evidence path so every receipt, impact-analysis, and structural-evidence reader in `plan_tool/roadmap_*.py` supports exactly one evidence schema: version 2. The persisted `schema_version: 2` discriminator remains unchanged, while version-specific reader branches collapse to the sole surviving freshness rule. Existing projects must reissue or archive live version-1 evidence before removal, and post-retirement readers must fail closed on unarchived version-1 records without crashing, routing, or converting them. No new CLI syntax or version-2 creation behavior is introduced.

## Problem statement

The evidence readers currently dispatch between version 1's exact-raw-byte freshness and version 2's writer-owned baseline-identity freshness. Scattered dispatch logic has caused three confirmed regressions: applying the wrong version rule to a version-2 snapshot, allowing admission and consumption predicates to disagree, and failing to reject an unsupported version at `_preflight_is_canonical` in `roadmap_structural_revision_run.py:446`.

`BACKLOG.md` #307 consolidates the identical currentness predicate in `admitted_source_is_current` while leaving four architecturally different operations separate. Integration was the only known real consumer of the version-1 path and has migrated to version 2, so retaining the unused alternate path preserves the generative cause of this regression class and its maintenance cost.

## Architecture

- The `schema_version` field remains part of the persisted wire format, but 2 becomes its only legal value. `is_supported_evidence_schema_version` or its successor retains its intent-naming call sites and collapses from two-value membership to a single legal-value check; call sites do not inline a bare `== 2`.

- Existing projects upgrade before their version-1 reader is retired. Immutable version-1 finals are never converted in place and never acquire a baseline identity by inference. A project with live version-1 route evidence establishes its writer-owned version-2 baseline, reissues a fresh version-2 receipt from still-eligible current feedback, and regenerates its derived version-2 analysis. Evidence that cannot safely be reissued is archived as history while the project remains on a version-1-capable release; any live version-1 record blocks retirement. The release gate inventories every known project and live evidence namespace and records each reissue or archival result.

- Both dispatch idioms are enumerated during `detail`: explicit `schema_version == 1` or `!= 1` branches, and checks such as `evidence_version == 2` that otherwise fall through to version-1 behavior. Every implicit fallthrough is replaced with explicit rejection of values other than 2.

- `admitted_source_is_current` remains the shared currentness gate and loses only its version-1 branch. `BACKLOG.md` #307's four do-not-merge findings remain settled because admission, comparison, self-consistency, and full-byte-render equality are different operations.

- New receipt and analysis creation remains on `NEW_RECEIPT_SCHEMA_VERSION = 2`, with no CLI override or new syntax. Each reader selects and documents a defined invalid/unavailable, no-route result for unarchived version-1 evidence; it never crashes, silently upgrades the record, or labels it current.

- The implementation scope includes `plan_tool/roadmap_source_identity.py` and its version-dispatch primitives (`EVIDENCE_SCHEMA_VERSIONS`, `is_supported_evidence_schema_version`, `admitted_source_is_current`, and `admit_baseline_backed_source`); `roadmap_escalation.py`, `roadmap_escalation_run.py`, `roadmap_escalation_selection.py`, `roadmap_impact_analysis.py`, `roadmap_impact_run.py`, `roadmap_impact_snapshot.py`, `roadmap_structural_revision.py`, `roadmap_structural_revision_run.py`, and `roadmap_structural_operations.py`; and `plan_tool/cli/roadmap_cmd.py` only where it renders or gates version-specific behavior. The published reader contract in `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, and `docs/ARCHITECTURE.md`, plus every test file mirroring a touched module, follows the same single-version contract.

## Out of scope

- Changes to version-2 semantics, admission rules, or the baseline/canonical-identity contract; this plan deletes the alternate path rather than redesigning the surviving one.
- Reopening or re-litigating `BACKLOG.md` #307's closed consolidation or its do-not-merge findings.
- `BACKLOG.md` #242 and Integration's "receipt preflight" gate; that work is unrelated, already in progress on Integration's side, and untouched by this removal.
- A generic in-place version-1-to-version-2 evidence converter; version-1 evidence lacks the writer-owned baseline identity such a converter would have to infer, so scoped reissue or archival remains the upgrade path.

## Risks

- **Failure shape:** A removed version-1 branch may also perform validation or field population absent from its version-2 sibling. **Severity:** The surviving version-2 path can silently lose behavior. **Mitigation:** Compare each removed branch's complete body with the version-2 branch before deletion, not only its comparison expression. **Unresolved gap:** The affected branch bodies must be enumerated during `detail`.
- **Failure shape:** Removing an implicit version-1 fallthrough without explicitly rejecting unsupported values repeats the known `_preflight_is_canonical` regression. **Severity:** Unsupported evidence can bypass fail-closed handling. **Mitigation:** Every site converted from "checks == 2, else assumes v1" explicitly rejects anything other than 2 and receives a proving test. **Unresolved gap:** Both explicit and implicit dispatch idioms must be found.
- **Failure shape:** An identifier-only documentation edit can leave version-1 comparisons, framing, and cross-references describing a contract that no longer ships. **Severity:** `ROADMAP_FORMAT.md` and `DATA_CONTRACT.md` can misstate the reader contract. **Mitigation:** Sweep version-1 vocabulary as well as identifiers across `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, and `docs/ARCHITECTURE.md`. **Unresolved gap:** Dated migration or retirement provenance is the only permitted remaining version-1 reference.
- **Failure shape:** An undisclosed version-1 consumer or live record remains at release time. **Severity:** Retirement is blocked. **Mitigation:** Inventory every known deployment and live evidence location and record its reissue or archival result. **Unresolved gap:** No other consumer is currently known.

## Testing

- Keep every mirrored test file for a touched module green after deleting, rather than skipping or marking `xfail`, its version-1-only tests and updating version-1-dependent fixture defaults to the sole remaining version.
- Add a fail-closed assertion for every site converted from the implicit-fallthrough idiom, using a value other than 2.
- Keep `tests/test_roadmap_format.py` identity-bound example-parsing tests passing with only the version-2 reference example.
- Cover the transition with fixtures for a version-1 record that safely reissues as version 2, an un-reissuable record that blocks release pending archival, and a post-retirement reader that refuses unarchived version-1 evidence without a route or implicit conversion.
- Run `uv run pytest tests/ -q -n auto`. The full suite must leave no roadmap-evidence-owned production module, matching test, or versioned roadmap contract reference treating 1 as an evidence schema version; unrelated format versions such as `SOURCE_IDENTITY_VERSION = 1` remain excluded from this sweep.

## Acceptance criteria

- No production code path branches on `schema_version` or `evidence_version` taking any value other than 2, and the shared validity check enforces exactly one legal value.
- `schema_version: 2` remains persisted and parseable on every evidence type, and Integration's existing version-2 evidence parses unchanged.
- Every known project and live evidence namespace has a recorded reissue or archival result; any un-reissuable live version-1 record blocks retirement.
- `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, and `docs/ARCHITECTURE.md` describe one evidence contract, with no residual version-1 vocabulary or cross-reference beyond dated migration or retirement provenance.
- Every reader returns its documented fail-closed, no-route result for an unarchived legacy record; none crashes, silently upgrades it, or treats it as current.
- `uv run pytest tests/ -q -n auto` passes, no test retains version 1 as a supported evidence path or an `xfail`/skip, and the explicit legacy fixture remains only to prove the documented fail-closed refusal.

## Deferred

_(none)_
