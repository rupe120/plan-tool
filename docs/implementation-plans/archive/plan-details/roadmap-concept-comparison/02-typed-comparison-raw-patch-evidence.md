> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add typed comparison and raw patch evidence

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Create `plan_tool/roadmap_compare.py` as the pure, read-only layer that turns step 1’s typed roadmap diff into ordered comparison facts and binds them to complete raw patch evidence. Add `tests/test_roadmap_compare.py` for concept identity, changed-field projection, relation separation, raw-only unmapped evidence, and deterministic raw-evidence identity. Keep the typed comparison distinct from the patch: cards explain structured changes, while every raw byte difference remains available as evidence. On green, later snapshot loading, Git collection, and rendering steps can consume one deterministic comparison contract.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the comparison contract.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why typed changes and raw evidence need one owner.
- [Input](#input) — Typed diff and raw evidence contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — New comparison leaf and focused tests.
- [Implementation](#implementation) — Required comparison, evidence, and identity rules.
- [Tests](#tests) — Unit coverage for the new pure contract.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Roadmap comparison contracts and existing owners.
- [Applicable guardrails](#applicable-guardrails) — Read-only and evidence-preservation boundaries.
- [Deferred](#deferred) — Work owned by later comparison steps.

## Why

Step 1 supplies typed row, ordering, artifact, and relation differences, but a reviewer also needs a deterministic way to see which concepts those facts describe while retaining the complete raw patch as exact evidence. A raw-only artifact difference needs an explicit fact, but a mixed artifact does not need an invented byte-to-concept partition. Without a separate comparison contract, renderers can each invent their own field projection, relation handling, or raw-evidence identity and drift from the typed diff or accidentally hide formatting, narrative, and reorder-only changes.

## Input

- **Shared typed diff:** Depend on step 1’s public typed comparison result from `plan_tool/roadmap_diff.py`. Its base-first row ordering, special plans ordering entries, artifact digests, and relation-occurrence handling are input contracts, not behavior to recreate here.
- **Typed roadmap records:** Read the row types and `RoadmapArtifact` variants from `plan_tool/roadmap_artifacts.py` only as needed to describe changed fields and distinguish ordinary rows from the plans artifact’s ordering entries.
- **Declared relations:** Use `plan_tool/roadmap_relations.py:RoadmapRelation` and its declared-relation helpers to keep relation changes out of ordinary field changes.
- **Raw evidence:** Accept complete per-artifact patch evidence as supplied data. Step 4 owns Git invocation and validation; this step must not read files, run Git, or infer missing patches.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_compare.py` — Defines immutable comparison cards, unmapped-evidence facts, and deterministic raw-evidence identity from the shared typed diff and supplied patches.
  - `tests/test_roadmap_compare.py` — Covers the pure comparison and raw-patch-evidence contract.

- **Existing files (edits only):**
  - None.

## Implementation

- **Foundational logic:** Build deterministic concept cards, raw-only unmapped facts,
  and complete per-artifact patch evidence from a typed roadmap diff.

- **Keep one semantic diff owner.** Consume step 1’s typed comparison surface from `plan_tool/roadmap_diff.py`; `plan_tool/roadmap_compare.py` must not reimplement stable-id matching, artifact digest comparison, row ordering, plans ordering handling, or relation-occurrence matching.

- **Represent one concept by stable identity.** Give each card the identity `(artifact key, row kind, stable id)` and retain complete typed before/after values. An id change must remain a removed card plus an added card; labels, prose, and field similarity must not match records across ids.

- **Classify cards from their endpoints.** A missing base value is `added`, a missing target value is `removed`, and two present unequal values are `changed`. Preserve the base-first ordering supplied by the shared diff: removed and changed records follow base order, then target-only additions follow target order.

- **Separate fields from relations.** Project declared-relation fields out before
  deciding whether a shared row difference becomes a comparison card. If the
  projected endpoints are equal, emit no card and retain the added or removed
  relation occurrences instead. This is comparison presentation only: preserve
  the full shared row difference for candidate review and impact identity. Do not
  report a declared relation twice as both an ordinary field change and a
  relation change.

- **Keep ordering entries typed.** Treat the shared diff’s `ordering` row type as a comparison concept with its own stable plan id. Do not fold it into its corresponding `PlanRow` card.

- **Make raw evidence complete and passive.** Accept complete patch text per fixed artifact pair and retain it unchanged. A typed card may point to its artifact’s raw evidence, but it must not replace, slice, normalize, or claim ownership of the patch text.

- **Report raw-only artifacts explicitly.** Produce an unmapped/raw-text fact when
  an artifact’s bytes differ but it has no typed row, ordering, or relation delta.
  This includes narrative, comments, formatting, and reorder-only byte changes.
  For an artifact that has both a typed delta and byte-only edits, retain the
  complete patch without inventing either a concept card or a byte-level
  partition.

- **Bind raw evidence deterministically.** Define a stable raw-evidence identity over the exact supplied evidence in fixed artifact-inventory order, with unambiguous framing between artifact records. The identity must change when any retained patch bytes or their artifact association changes, and it must not include model-generated text.

- **Keep the leaf read-only and presentation-free.** `plan_tool/roadmap_compare.py` may expose typed facts ready for later renderers, but it must not load versions, invoke Git, print cards, write files, or import candidate policy from `plan_tool/roadmap_candidate.py`. `plan_tool/roadmap_view.py:display_label` remains the later renderer’s label owner.

## Tests

### Tests for this step

- `tests/test_roadmap_compare.py:test_changed_row_becomes_one_card_with_complete_endpoints` — a stable-id row replacement produces one `changed` card retaining both typed values.
- `tests/test_roadmap_compare.py:test_stable_id_change_remains_removed_then_added_cards` — a changed id does not receive semantic matching by label or prose.
- `tests/test_roadmap_compare.py:test_card_order_uses_shared_base_then_target_order` — removed and changed cards retain base order before target-only additions.
- `tests/test_roadmap_compare.py:test_ordering_entry_is_a_separate_comparison_card` — a plans ordering delta remains distinct from its plan row.
- `tests/test_roadmap_compare.py:test_changed_card_excludes_declared_relation_fields` — ordinary changed-field facts omit declared-relation values.
- `tests/test_roadmap_compare.py:test_relation_only_change_has_no_card_and_keeps_duplicate_occurrences` — a candidate-compatible relation-only row difference produces no comparison card while its added and removed relation occurrences remain separate without deduplication.
- `tests/test_roadmap_compare.py:test_raw_only_byte_change_is_reported_as_unmapped` — patch evidence with no typed change remains visible as unmapped evidence and creates no card.
- `tests/test_roadmap_compare.py:test_mixed_typed_and_raw_byte_change_preserves_complete_patch_without_partition` — a typed row edit plus a comment, narrative, formatting, or reorder-only edit in the same artifact retains its card and exact complete patch without invented raw-byte ownership.
- `tests/test_roadmap_compare.py:test_raw_evidence_identity_changes_with_patch_bytes_or_artifact_binding` — the framed identity changes for either altered patch bytes or a different artifact association.
- `tests/test_roadmap_compare.py:test_raw_evidence_identity_is_deterministic_in_inventory_order` — equivalent complete evidence yields the same identity regardless of caller construction order.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap_compare.py` consumes the shared typed diff from step 1 without creating a second semantic diff implementation.
- Each typed row or ordering delta produces an ordered added, removed, or changed concept card keyed only by artifact key, row kind, and stable id.
- Changed-card field facts exclude declared relations; a relation-only shared row
  difference produces no comparison card, while added and removed relation
  occurrences remain separate and retain duplicates.
- Raw patch evidence remains complete and unchanged; a raw-only artifact produces
  explicit unmapped evidence, while a mixed artifact retains its complete patch
  without an invented byte-level partition.
- The raw-evidence identity is deterministic, framed by artifact association, and changes when retained evidence changes.
- `tests/test_roadmap_compare.py` passes.

## References

- [BACKLOG.md #402](BACKLOG.md) — Read the comparison feature contract, especially complete Git evidence and unmapped raw-text behavior.
- [ROADMAP_FORMAT.md](ROADMAP_FORMAT.md) — Read the fixed artifact, row, ordering, relation, and stable-id contracts.
- [plan_tool/roadmap_versions.py](plan_tool/roadmap_versions.py) — Read `VERSION_ARTIFACT_INVENTORY` for the fixed artifact order that evidence follows.
- [plan_tool/roadmap_candidate.py](plan_tool/roadmap_candidate.py) — Read `CandidatePredecessorDiff` and `candidate_impact_atoms_for_diff` as the pre-extraction comparison source.
- [plan_tool/roadmap_relations.py](plan_tool/roadmap_relations.py) — Read `RoadmapRelation` and `extract_declared_relations` for relation-occurrence semantics.
- [plan_tool/roadmap_view.py](plan_tool/roadmap_view.py) — Read `display_label` to preserve the later renderer’s label ownership.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, read-only behavior:** Keep `plan_tool/roadmap_compare.py` pure; it must not write or change roadmap lifecycle state.
- **The plan’s “## Scope guardrails”, raw evidence role:** Preserve supplied raw
  evidence as the record; report raw-only artifacts but do not infer byte-level
  ownership for mixed patches.
- **The plan’s “## Scope guardrails”, stable identity:** Match comparison concepts by stable id only.
- **The plan’s “## Scope guardrails”, deterministic comparison:** Do not add model calls, generated summaries, acceptance recommendations, or nondeterministic output fields.
- **The plan’s “## Scope guardrails”, compatibility:** Do not change existing roadmap views, lifecycle writers, or candidate authority.
- **The plan’s “## Out of scope”:** Do not add snapshot selection, Git execution, CLI wiring, HTML rendering, broader artifact families, or acceptance actions.

## Deferred

- **Snapshot resolution and controlled Git patch collection** — Step 4 owns loading, Git invocation, and refusal behavior.
- **Terminal cards, patch output, and JSON rendering** — Step 5 owns presentation while consuming this step’s typed facts unchanged.
- **Labels and roadmap-wide lookup behavior** — A later renderer reuses `plan_tool/roadmap_view.py:display_label` and its index builders without changing them.
- **Candidate admission, review identity, and lifecycle policy** — `plan_tool/roadmap_candidate.py` remains the owner because comparison is read-only.
