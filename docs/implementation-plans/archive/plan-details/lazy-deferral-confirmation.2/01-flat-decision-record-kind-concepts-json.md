> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a flat decision-record kind to concepts.json and skip fingerprint validation when loading it

## Summary

Add a second record kind to `plan-details/<slug>/concepts.json` — a **flat decision record** whose nodes carry a coarse `bucket` tag and a `defer`/`wont_do` decision, with no hierarchy — and make `plan_tool/concept_tree.py:load_concepts` skip the `plan_fingerprint` staleness check for that kind. The whole change lands in `plan_tool/concept_tree.py` (two new dataclass fields, a loosened decoder, a load-time branch, per-kind validation) plus field-row updates in `DATA_CONTRACT.md`. The key design decision is a `record_kind` discriminator on `ConceptTree` that defaults to the legacy value, so every existing full-tree record keeps its current fingerprint-gated behavior byte-for-byte. On green, a `record_kind="decision-record"` sidecar round-trips through `save_concepts`/`load_concepts` and loads cleanly even when the plan text has changed since it was written, while a legacy full-tree record still raises `StaleConceptTreeError` on a fingerprint mismatch.

## Table of Contents

- [Why](#why) — the staleness guard is wrong for a decision that is confirmed after edits
- [Input](#input) — the two on-disk record shapes that must both stay loadable
- [Files (creates vs edits)](#files-creates-vs-edits) — one code file, one doc, two test files
- [Implementation](#implementation) — the discriminator, the loosened decoder, the load branch, per-kind validation
- [Tests](#tests) — round-trip, no-stale-on-edit, legacy-still-stale, decode tolerance
- [Acceptance criteria](#acceptance-criteria) — observable behaviors on green
- [References](#references) — dataclasses / json / typing docs for the record shape
- [Deferred](#deferred) — who writes flat records, migration, and identity-collision follow-up

## Why

A pending deferral is confirmed *later*, after more plan edits — that is the whole point of "confirm the concepts the tool defers." But today every `concepts.json` record is fingerprint-validated on load: `plan_tool/concept_tree.py:load_concepts` raises `StaleConceptTreeError` when the stored `plan_fingerprint` differs from the current plan fingerprint. So by confirm time the record is stale and the read/confirm paths (`scope-review`, `status`, `check_concept_coverage`) dead-end or crash. A decision record is an operator/tool decision, not a cache of plan text, so the fingerprint guard is simply the wrong check for it. This step lays the foundation: a record shape that carries the decision plus a coarse `bucket`, and a load path that does **not** fingerprint-validate that shape. It changes no writer or reader wiring yet — steps 2, 4, and 6 do that — so on its own it only makes the new shape persistable and loadable alongside the untouched legacy shape.

## Input

This step reads and extends the persisted `plan-details/<slug>/concepts.json` contract owned by `plan_tool/concept_tree.py`. Two shapes must both stay loadable through the single seam `load_concepts(plan_path, expected_plan_fingerprint)`:

- **Legacy full-tree record** — the current `ConceptTree`/`ConceptNode` shape produced by `bootstrap_concepts` / `emit_concept_tree`, with `parent_path`, `order`, and a per-bundle `plan_fingerprint` that is checked on load. Behavior here must not change.
- **Flat decision record** (new) — `{bucket, title, rationale, decision (defer|wont_do), review_state}`, no hierarchy, whose `plan_fingerprint` is stored for provenance but **not** checked on load.

The load seam's signature stays frozen — every caller passes the bundle fingerprint. The staleness *rule* branches internally on the decoded record's kind. No caller changes in this step.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — add `ConceptTree.record_kind` (discriminator, defaults to legacy) and `ConceptNode.bucket` (defaults `""`); loosen `_decode_tree` from exact-field-set equality to a required-subset bound at both tree and node levels; branch `load_concepts` so the flat kind skips the `StaleConceptTreeError` check; extend `_validate_tree`/`_validate_node` with the flat-kind rules.
  - `DATA_CONTRACT.md` — add a `record_kind` field row to the `### ConceptTree` table and a `bucket` field row to the `### ConceptNode` table under `## Concept sidecar`, plus prose noting the flat kind is not fingerprint-validated on load.
  - `tests/test_concept_tree.py` — new unit tests for the flat round-trip, no-stale-on-edit, legacy-still-stale, and decode tolerance for records missing the new keys.
  - `tests/test_data_contract.py` — extend the concept-contract coverage so the new runtime fields are documented (the drift guard fires automatically once the fields exist).

## Implementation

**Add a `record_kind` discriminator to `ConceptTree`, defaulting to the legacy value.** Add `record_kind: str = "full-tree"` to `plan_tool/concept_tree.py:ConceptTree`. The legacy default is load-bearing: a record on disk with no `record_kind` key decodes as `"full-tree"` and keeps the exact fingerprint-gated behavior it has now. Use `"decision-record"` as the flat kind's literal — self-descriptive, no glossary needed. One good move: define both as module constants next to `CONCEPTS_SCHEMA_VERSION` (e.g. a `RECORD_KIND_FULL_TREE` / `RECORD_KIND_DECISION` pair) so the load branch and validator reference one source, not scattered string literals.

**Add a `bucket` field to `ConceptNode`, defaulting to `""`.** Add `bucket: str = ""` to `plan_tool/concept_tree.py:ConceptNode`. Legacy nodes leave it empty; a flat node stores its coarse section-level tag here. The default keeps `ConceptNode(**raw)` building cleanly for legacy records that never had the key.

**Loosen `_decode_tree` from exact-set equality to a required-subset bound.** Today `_decode_tree` rejects any record whose key set is not exactly the four tree fields / nine node fields. That rejects every legacy record the moment the new fields exist. Loosen both checks to the `required <= set(raw) <= allowed` shape — the exact pattern `plan_tool/concept_tree.py:_parse_emitted_concepts` already uses (`required_fields <= set(raw) <= allowed_fields`). Reuse that shape rather than inventing a new one:
- **Tree level:** `required` stays the current four keys; `allowed` adds `record_kind`.
- **Node level:** `required` stays the current nine keys; `allowed` adds `bucket`.

This keeps unknown keys rejected (tamper protection) while letting old records missing the new keys pass. Construct the dataclasses so a missing key falls back to the field default (splatting the decoded dict works because both new fields have defaults).

**Branch `load_concepts` so the flat kind skips the staleness check.** After `_decode_tree` and `_validate_tree`, the `tree.plan_fingerprint != expected_plan_fingerprint → StaleConceptTreeError` check must run **only** when `tree.record_kind == "full-tree"`. For `"decision-record"`, return the validated tree without consulting `expected_plan_fingerprint`. Keep the seam signature and every caller untouched — callers still pass the fingerprint; it is simply not consulted for the flat kind. Keep the `isinstance(expected_plan_fingerprint, str)` type guard where it is so callers still get a clear error on a bad argument regardless of kind.

**Extend validation for the flat kind in `_validate_tree` / `_validate_node`.** The hard requirements when `record_kind == "decision-record"`:
- `bucket` is a non-empty string on every node — it is the record's only validity anchor (later steps check whether the bucket still resolves to a body section).
- `parent_path` is empty — the flat record has no hierarchy, so the ancestor-existence loop in `_validate_tree` has nothing to check.
- `decision` is one of `defer` / `wont_do`, and `review_state` stays within the existing `CONCEPT_REVIEW_STATES` set. Constraining `decision` here pins the record contract that steps 2/4/6 write against; one way is a small allowed-set check gated on the flat kind.

For `record_kind == "full-tree"`, keep every current check exactly, and validate `record_kind` itself is one of the two known literals (an unknown kind is invalid, mirroring the existing `unsupported schema_version` rejection). `id` stays recomputed as `concept_id(title, parent_path)` for both kinds — the tamper check is unchanged and gives a flat node the stable `id` token that `scope-review --concept` will consume later.

**Constraints and gotchas:**
- **`save_concepts` needs no new branch** — it already calls `_validate_tree` and serializes via `asdict`, so both new fields round-trip once validation accepts the flat kind. Confirm a saved flat record includes `record_kind` and `bucket`.
- **Keep `plan_fingerprint` a required non-empty string for both kinds.** A flat record still carries it as provenance; it is just not checked on load. Do not relax `_validate_tree`'s non-empty `plan_fingerprint` rule.
- **Flat-record identity keys on `title` only** (empty `parent_path`), so two flat deferrals with the same title but different buckets would collide on `id` and be rejected as duplicates. This is acceptable for the MVP (deferral titles are section-level and effectively unique). If it ever bites, bucket-scoped identity is a follow-up — see Deferred; do not expand this step to solve it speculatively.
- **`DATA_CONTRACT.md` is drift-guarded** by `tests/test_data_contract.py`, which keys documented field rows per section against the runtime dataclass fields (`plan_tool/data_contract.py` derives the field set via `dc.fields`). So the new fields need backticked rows in the `### ConceptTree` / `### ConceptNode` tables under `## Concept sidecar`, and **no** edit to `plan_tool/data_contract.py`. Add the fingerprint-skip note as plain prose in the existing `## Concept sidecar` section — new field-shaped rows or new sections are what trip the guard; prose in an existing section is safe.

## Tests

Add to `tests/test_concept_tree.py` (the suite already has `_node` / `_tree` helpers; add a small flat-record helper alongside them):

- `test_flat_decision_record_round_trips` — a `record_kind="decision-record"` tree with a `bucket`, `decision="defer"` node saves and loads back equal.
- `test_flat_record_loads_after_unrelated_edit` — save a flat record, then `load_concepts` with a **different** `expected_plan_fingerprint` returns the record and raises no `StaleConceptTreeError` (the staleness fix, pinned directly).
- `test_legacy_full_tree_still_stale_on_fingerprint_mismatch` — the existing `test_plan_fingerprint_mismatch_is_stale` behavior still holds for a `record_kind="full-tree"` (default) record; a mismatch raises `StaleConceptTreeError`.
- `test_legacy_record_without_new_keys_still_loads` — a JSON record on disk lacking `record_kind` and `bucket` decodes as a full-tree record with the defaults (backward compatibility of the loosened decoder).
- `test_flat_record_requires_non_empty_bucket` — a flat node with an empty `bucket` is rejected as invalid.
- `test_flat_record_rejects_hierarchy_and_bad_decision` — a flat node with a non-empty `parent_path`, and a flat node whose `decision` is neither `defer` nor `wont_do`, are each rejected as invalid.
- `test_unknown_record_kind_is_invalid` — a record whose `record_kind` is some third literal is rejected.
- `test_unknown_extra_key_still_rejected` — the loosened decoder still rejects a record carrying a key outside the allowed set (tamper protection survives the loosening).

Add to `tests/test_data_contract.py`:

- Extend the concept-contract check so `record_kind` (on `ConceptTree`) and `bucket` (on `ConceptNode`) are covered by the drift guard — `test_concept_contract_discovers_runtime_fields` already compares `field_names` against `dc.fields`, so it fails until the DATA_CONTRACT.md rows exist; add an assertion that the documented sections name the new fields if the existing tests don't already force it.

### Test-creation order (feature step)

This is a **feature** step. Write each test above **with** the code that makes it pass — start with `test_flat_decision_record_round_trips` and `test_flat_record_loads_after_unrelated_edit` (they pin the two headline behaviors), then the validation-rejection tests as you add the per-kind checks, then the decode-tolerance and legacy-still-stale tests. Green-before-done gate: every new test in `tests/test_concept_tree.py` and `tests/test_data_contract.py` must pass, and the full existing `tests/test_concept_tree.py` / `tests/test_data_contract.py` suites must stay green, before this step is finished.

## Acceptance criteria

- `ConceptTree` has a `record_kind` field defaulting to the legacy full-tree literal, and `ConceptNode` has a `bucket` field defaulting to `""`.
- `load_concepts` returns a `record_kind="decision-record"` record without raising `StaleConceptTreeError`, even when `expected_plan_fingerprint` differs from the record's stored `plan_fingerprint`.
- `load_concepts` still raises `StaleConceptTreeError` for a `record_kind="full-tree"` (or key-absent) record whose `plan_fingerprint` does not match.
- A `concepts.json` on disk that lacks `record_kind` and `bucket` still loads (decodes as full-tree with defaults); a record carrying an unknown key is still rejected as invalid.
- A flat record with an empty `bucket`, a non-empty `parent_path`, a `decision` outside `{defer, wont_do}`, or an unknown `record_kind` is rejected as invalid.
- `save_concepts` round-trips a flat record so a subsequent `load_concepts` returns an equal tree.
- `DATA_CONTRACT.md` documents `record_kind` and `bucket` in the `## Concept sidecar` tables, and `tests/test_data_contract.py` passes.
- The full `tests/test_concept_tree.py` and `tests/test_data_contract.py` suites pass.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — field defaults for the new optional `record_kind` / `bucket` fields so `ConceptNode(**raw)` still builds on legacy records.
- [json — JSON encoder and decoder (Python 3.13)](https://docs.python.org/3/library/json.html) — serializing/deserializing the record and the record-kind decode branch that keeps both shapes loadable.
- [typing — Support for type hints (Python 3.13)](https://docs.python.org/3/library/typing.html) — annotations for the constrained `decision` (`defer`/`wont_do`) and `review_state` fields.

## Deferred

- Wiring any writer or reader to produce/consume flat records — `create`'s deferral-only gate (step 2), `check_concept_coverage` totality (step 3), `scope-review` confirm (step 4), the pending-decision surfaces (step 5), and detail's shared-find routing (step 6). This step only makes the shape persistable and loadable.
- Migrating existing legacy full-tree `concepts.json` records to the flat shape — legacy stays dormant and loadable; migration is a separate concern (plan Out of scope).
- Bucket-scoped flat-record identity (including `bucket` in `concept_id`) to prevent same-title-different-bucket `id` collisions — deferred as a follow-up; the MVP keys identity on `title` and accepts the constraint. If it needs solving, route it to reconcile/BACKLOG rather than expanding this step, since it would touch the shared `concept_id` contract.
- Removing the shipped hierarchical machinery (`emit_concept_tree`, `Step.concept_ids`) — left in place, not deleted (plan Out of scope).
