# Step 1 — Extract the shared typed roadmap diff while preserving candidate add, replace, and remove behavior

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Extract the typed roadmap-diff records and comparison logic from `plan_tool/roadmap_candidate.py` into new `plan_tool/roadmap_diff.py`. Keep candidate materialization using the same deterministic results, including row additions, replacements, removals, plan ordering entries, artifact digests, and declared relation occurrences. Add focused unit coverage in `tests/test_roadmap_diff.py` and retain candidate regression coverage in `tests/test_roadmap_candidate.py`. On green, later read-only comparison work has one policy-free typed diff owner without changing candidate behavior.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the extraction and its green result.
- [Table of Contents](#table-of-contents) — Links to the detail sections.
- [Why](#why) — Why roadmap concepts need one deterministic comparison owner.
- [Input](#input) — Existing typed artifacts and ordering contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — New leaf module and focused test updates.
- [Implementation](#implementation) — Required extraction boundary and compatibility rules.
- [Tests](#tests) — Focused diff and candidate-regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Existing roadmap contract and ownership references.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that keep this extraction read-only.
- [Deferred](#deferred) — Adjacent comparison work left to later steps.

## Why

`plan_tool/roadmap_candidate.py:_build_predecessor_diff` already computes the typed facts needed to compare roadmap snapshots, but it sits inside candidate policy and lifecycle code. A new comparison surface needs the same artifact, row, ordering, and declared-relation facts without duplicating their identity or ordering rules. Extracting the pure comparison seam now keeps candidate review authoritative over its policy while giving later read-only work a single deterministic source.

## Input

- **Typed roadmap artifacts:** Read the `RoadmapArtifact` variants and row collections defined in `plan_tool/roadmap_artifacts.py`, including the plans artifact’s separate `ordering` sequence.
- **Fixed stage order:** Preserve the stage order supplied through `plan_tool/roadmap.py:STAGES` and the fixed stored-version inventory in `plan_tool/roadmap_versions.py:VERSION_ARTIFACT_INVENTORY`.
- **Declared relations:** Use `plan_tool/roadmap_relations.py:extract_declared_relations` as the source of relation facts; relation comparison must retain repeated occurrences.
- **Candidate result contract:** Preserve the existing `CandidatePredecessorDiff` consumers, including `plan_tool/roadmap_candidate.py:materialize_candidate` and `candidate_impact_atoms_for_diff`.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_diff.py` — Own the immutable typed diff records and pure artifact, row, ordering, and relation comparison helpers.
  - `tests/test_roadmap_diff.py` — Cover the shared comparison contract directly.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate.py` — Import and use the shared diff owner while retaining the candidate-facing compatibility surface needed by existing callers and persisted candidate evidence.
  - `tests/test_roadmap_candidate.py` — Keep or adjust candidate tests so authorized add, replace, and remove flows prove the extraction did not change candidate behavior.

## Implementation

- **Foundational logic:** Extract the ordered typed snapshot diff: compare corresponding typed roadmap artifacts and return changed artifact bytes, rows, ordering entries, and declared relation occurrences.

- **Make `plan_tool/roadmap_diff.py` policy-free.** Move the records currently represented by `CandidateArtifactDiff`, `CandidateRowDiff`, `CandidateRelationDiff`, and `CandidatePredecessorDiff`, plus the comparison behavior behind `_build_predecessor_diff`, `_artifact_row_diffs`, `_ordered_stage_collections`, and relation-occurrence matching, into the new module or equivalent public shared seams.

- **Keep candidate authority in `plan_tool/roadmap_candidate.py`.** Candidate context authorization, delta parsing, materialization, review requirements, impact identity, and mutation decisions must remain there. `candidate_impact_atoms_for_diff` may consume the shared diff facts, but the new module must not import candidate-policy types or decide candidate review requirements.

- **Preserve existing candidate consumers.** `plan_tool/roadmap_candidate_run.py`, `plan_tool/roadmap_candidate_review.py`, and `plan_tool/roadmap_version_promotion.py` currently reach the candidate diff surface. Retain compatible candidate-facing imports or forwarding helpers so this step does not require edits outside its declared files and does not alter stored-evidence reproduction.

- **Preserve row identity and ordering.** Compare rows by stable `id`, never by label or prose. Emit removals and changed base rows in base source order, then target-only additions in target source order. Preserve the existing special handling for `PlansArtifact.ordering`; an ordering entry is a typed change even though it is not a design-row collection.

- **Preserve byte and typed distinctions.** A changed artifact digest must reflect differing artifact bytes. A reorder, narrative edit, comment change, or formatting-only change may change bytes without creating a typed row delta. Do not normalize bytes or turn unmatched raw changes into invented row changes.

- **Preserve candidate-compatible relation changes.** Use the declared relations from
  `extract_declared_relations` and compare each occurrence without collapsing
  duplicates. When a declared relation changes a surviving row, retain that full
  row difference in the shared stream as current candidate review and impact
  identity require, alongside deterministic added and removed relation facts.
  Step 2 may project that row out of a comparison card; this shared layer must not.

- **Keep the shared API adaptable but narrow.** One reasonable approach is a public comparison function that accepts the before/after artifact mappings, corresponding bytes, and ordered stages. This preserves candidate test injection and lets a later snapshot reader supply the fixed inventory without making this leaf responsible for loading versions or files.

- **Do not duplicate presentation logic.** `plan_tool/roadmap_view.py:display_label` and its index builders remain the owner of human labels and lookup behavior. This step returns typed facts only; it does not render comparison cards or add a CLI surface.

## Tests

### Tests for this step

- `tests/test_roadmap_diff.py:test_identical_artifacts_have_no_typed_or_artifact_diffs` — identical typed artifacts and bytes return empty artifact, row, and relation differences.
- `tests/test_roadmap_diff.py:test_changed_row_reports_complete_before_and_after_values` — one stable-id row edit reports one changed row with both complete typed values and the changed artifact digest.
- `tests/test_roadmap_diff.py:test_removed_and_added_stable_ids_remain_distinct_row_diffs` — an id change is represented as one removal plus one addition, not as a semantic replacement.
- `tests/test_roadmap_diff.py:test_plan_ordering_change_is_retained_as_a_typed_diff` — plans ordering changes remain separate typed entries with the established `ordering` row type.
- `tests/test_roadmap_diff.py:test_relation_only_change_retains_candidate_row_diff_and_relation_occurrence` — a declared relation change retains its existing full row diff plus the separate relation occurrence.
- `tests/test_roadmap_diff.py:test_repeated_relation_occurrences_are_not_collapsed` — repeated declared relation occurrences retain their separate added or removed facts.
- `tests/test_roadmap_diff.py:test_row_diff_order_follows_base_then_target_source_order` — removed and changed rows follow base order, followed by target-only additions in target order.
- `tests/test_roadmap_candidate.py:test_candidate_applies_only_an_authorized_complete_row_replacement` — authorized replacement behavior remains unchanged through the extracted diff seam.
- `tests/test_roadmap_candidate.py:test_candidate_authorized_existing_relation_change_returns_review_required` — a relation-only replacement still requires review and retains the same row and relation impact atoms.
- `tests/test_roadmap_candidate.py:test_candidate_valid_plan_removal_with_its_ordering_remains_gate_clean` — candidate removal still carries its ordering companion correctly.
- `tests/test_roadmap_candidate.py:test_candidate_adds_a_cross_artifact_row_only_when_full_endpoints_anchor_it` — candidate addition authorization and resulting diff behavior remain unchanged.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap_diff.py` owns one deterministic typed comparison surface for roadmap artifact bytes, typed rows, plan ordering, and declared relations.
- `plan_tool/roadmap_candidate.py` consumes that shared surface without changing candidate add, replace, or remove outcomes.
- A stable-id change produces a removal and an addition, never label-based matching.
- A plan ordering change appears as a typed ordering difference.
- A relation-only change retains the candidate-compatible full row difference and
  distinct declared-relation occurrence facts, preserving review and impact
  identity behavior.
- Repeated declared relation occurrences remain distinct comparison facts.
- Byte-only changes can produce an artifact digest change with no invented typed row delta.
- `tests/test_roadmap_diff.py` and the affected `tests/test_roadmap_candidate.py` cases pass.

## References

- [BACKLOG.md #402](BACKLOG.md) — Read the source feature contract, especially the requirement to reuse the candidate typed diff without a parallel semantic-diff engine.
- [ROADMAP_FORMAT.md](ROADMAP_FORMAT.md) — Read the fixed artifact, row, ordering, relation, and stable-id contracts.
- [plan_tool/roadmap_versions.py](plan_tool/roadmap_versions.py) — Read `VERSION_ARTIFACT_INVENTORY`, `load_accepted_version`, and `load_stored_version` for fixed snapshot membership.
- [plan_tool/roadmap_candidate.py](plan_tool/roadmap_candidate.py) — Read `CandidatePredecessorDiff`, `_build_predecessor_diff`, `_artifact_row_diffs`, and `candidate_impact_atoms_for_diff` as the extraction source.
- [plan_tool/roadmap_view.py](plan_tool/roadmap_view.py) — Read `display_label` and roadmap-wide index builders to keep presentation ownership outside this typed diff leaf.
- [SEED_FORMAT.md](SEED_FORMAT.md) — Read plan-seed scope and verification rules without expanding this step into seed comparison.

## Applicable guardrails

- **The plan’s “## Step intent”, deterministic comparison owner:** Keep this step limited to one read-only typed-diff owner; do not add snapshot selection, command wiring, or output rendering.
- **The plan’s “## Scope guardrails”, read-only behavior:** The extracted module and candidate changes must not write, accept, promote, repair, or alter roadmap lifecycle metadata.
- **The plan’s “## Scope guardrails”, raw evidence role:** Do not claim the typed diff replaces Git evidence or add any filtering of raw artifact differences.
- **The plan’s “## Scope guardrails”, stable identity:** Match rows only by their stable ids; do not add label, field, or prose similarity matching.
- **The plan’s “## Scope guardrails”, deterministic output:** Keep the comparison pure and model-free, with no generated summary or recommendation fields.
- **The plan’s “## Scope guardrails”, compatibility:** Preserve existing roadmap view and lifecycle-writer behavior by retaining candidate-facing compatibility where current callers rely on it.
- **The plan’s “## Out of scope”:** Do not extend comparison beyond the fixed roadmap artifacts or change candidate proposal and review policy.

## Deferred

- **Snapshot resolution, Git unified-diff collection, and terminal or machine-readable rendering** — Later steps own the read-only comparison command and its evidence presentation.
- **Human-label rendering and roadmap-wide lookup changes** — Reuse `plan_tool/roadmap_view.py:display_label` unchanged when a later presentation layer needs labels.
- **Candidate-policy consolidation beyond the typed diff seam** — Keep authorization, review requirements, and impact identity in `plan_tool/roadmap_candidate.py` to avoid changing candidate lifecycle behavior.
