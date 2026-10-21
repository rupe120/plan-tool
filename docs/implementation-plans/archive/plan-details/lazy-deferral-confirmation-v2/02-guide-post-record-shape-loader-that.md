# Step 2 — Add the guide-post record shape and a loader that validates against the scoped anchor, keeping legacy full-tree records loadable

## Summary

Give `plan_tool/concept_tree.py` a second, flat record shape — the **guide post** — and teach `load_concepts` which staleness rule to apply per record. A guide post is a `ConceptNode` that carries two new fields (`bucket` and `bucket_anchor`, the scoped hash from step 1) plus the existing `decision`/`review_state`; a `record_kind` tag on `ConceptTree` marks the whole record as `"guide-post"` vs the legacy `"full-tree"`. The key decision: for a guide-post record the loader **skips** the whole-bundle `plan_fingerprint` staleness check (the fix in plan section **B**), while a legacy full-tree record keeps raising `StaleConceptTreeError` on a bundle-fingerprint mismatch exactly as today. Legacy records on disk — which lack the new keys — must still decode, so the record decoder loosens from an exact-field-set match to a required-subset match. On green, a guide-post record round-trips through `save_concepts`/`load_concepts`, survives an unrelated plan edit without raising, and both `DATA_CONTRACT.md` and its drift guard document the new fields.

## Table of Contents

- [Why](#why) — what the bundle-wide guard breaks and what this step adds
- [Input](#input) — the record contract and the step-1 primitive this builds on
- [Files (creates vs edits)](#files-creates-vs-edits) — the files this step touches
- [Implementation](#implementation) — the fields, the decoder loosening, and the loader branch
- [Tests](#tests) — unit cases added with the code
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — dataclasses, json, hashlib
- [Deferred](#deferred) — what later steps wire in

## Why

A pending deferral is confirmed *after* more edits, but `load_concepts` compares the stored `plan_fingerprint` against `compute_plan_fingerprint` over the whole plan plus every detail file and raises `StaleConceptTreeError` on any mismatch — so a deferral is normally stale by confirm time and `scope-review`, `status`, and `check_concept_coverage` dead-end on it. Plan section **B** fixes this by validating a deferral against a hash scoped to only its own bucket's source text. Step 1 added the primitive that computes that hash (`compute_bucket_anchor`). This step adds the record shape that stores the hash and the loader that stops applying the wrong (bundle-wide) staleness rule to these records — the first place the scoped anchor actually replaces the bundle fingerprint on a read path. It does not yet re-validate a guide post against current bucket text (that needs the plan parsed — steps 5 and 6); it makes the loader stop crashing on a guide-post record so those steps have something loadable to validate.

## Input

This step extends a persisted schema and consumes one upstream primitive, so its correctness rests on both staying shaped as expected:

- **`plan-details/<slug>/concepts.json`** decoded by `plan_tool/concept_tree.py:load_concepts` / `_decode_tree` / `_validate_tree` / `_validate_node`. Today `_decode_tree` demands an **exact** field set on both the top-level record (`{plan_slug, plan_fingerprint, concepts, schema_version}`) and every node (the nine `ConceptNode` fields). A legacy full-tree record on disk lacks any new field, so the exact-set check is the thing that would reject it once new fields exist — this step must loosen it without opening the door to arbitrary unknown keys.
- **Step 1's `plan_tool/review_persistence.py:compute_bucket_anchor(bucket, bucket_source_text) -> str`** — the deterministic 64-char digest a guide post stores in `bucket_anchor`. Step 1 produces this primitive; this step only stores its output as a string. Step 2 does **not** call it (no bucket text is extracted here — that is the callers' job in steps 4/5/6); it defines the field that holds its result.
- **The staleness guard being replaced** — the stored `plan_fingerprint` vs `compute_plan_fingerprint` comparison in `load_concepts` and the `StaleConceptTreeError` it raises. The scoped anchor supplants this guard **only** for guide-post records; legacy records keep it.
- **`concept_id(title, parent_path)`** — positional identity. A guide post is flat (empty `parent_path`), so its `node.id` is `concept_id(title, [])` — the bare token plan section **E** hands to `scope-review --concept`. Identity must keep excluding the new fields.

## Files (creates vs edits)

- **New files:**
  - `tests/test_concept_tree.py` already exists; no new file is strictly required. **Added to scope:** this step's loader/record behavior tests belong in `tests/test_concept_tree.py` (mirror convention for `plan_tool/concept_tree.py`), which is **not** in the plan's declared `files:` for this step. Add it to the step's file list — the record-shape and loader-branch behavior cannot be tested from `tests/test_data_contract.py` alone (that file only guards documentation).
- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — add `bucket` and `bucket_anchor` fields to `ConceptNode`; add `record_kind` to `ConceptTree`; loosen `_decode_tree`'s exact-set checks to required-subset; branch `load_concepts` on `record_kind` so guide-post records skip the bundle-fingerprint staleness check; add the per-kind validation to `_validate_tree`/`_validate_node`.
  - `DATA_CONTRACT.md` — document the three new fields in the `ConceptNode` / `ConceptTree` sections and add prose to the `## Concept sidecar` section that guide-post records validate per-bucket against a scoped anchor rather than being rejected on the bundle fingerprint.
  - `tests/test_data_contract.py` — add targeted assertions that the new fields and the guide-post staleness note are documented.
  - `tests/test_concept_tree.py` — the loader/record behavior unit tests (see Files note above).

## Implementation

**Foundational logic of this step:** *decide which staleness rule a loaded concept record gets (scoped anchor for guide posts, bundle fingerprint for legacy) and define the fields a guide post carries.* The load-path branch lives only in `load_concepts`; the callers that will later re-validate a guide post against current bucket text (`plan_tool/review.py:check_concept_coverage`, `plan_tool/cli/scope_review_cmd.py:cmd_scope_review`, `plan_tool/detail.py`, `plan_tool/scope_out.py`) are **out of scope here** — see Deferred.

- **Add two fields to `ConceptNode`, both optional with empty-string defaults.** Recommended names: `bucket: str = ""` (the coarse tag — the body-section / top-level area the concept belongs to) and `bucket_anchor: str = ""` (the digest from `compute_bucket_anchor`). Empty defaults are what let a legacy node — which never had these keys — construct cleanly via `ConceptNode(**raw)`. A guide post sets both; a legacy full-tree node leaves both `""`.
- **Add a record-kind discriminator to `ConceptTree`.** Recommended: `record_kind: str = "full-tree"` with the new value `"guide-post"`. The default is load-bearing: a legacy record on disk has no `record_kind` key, so it decodes as `"full-tree"` and keeps the current staleness behavior. *One alternative, rejected:* infer the kind from node contents (any node with a non-empty `bucket_anchor` ⇒ guide-post record). It avoids a tree field but makes a tree-level decision from per-node data and is ambiguous for a mixed record; an explicit tag is testable and unambiguous. You have latitude, but if you infer, pin the inference rule in a test and document it.
- **Loosen `_decode_tree` from exact-set to required-subset — do not accept arbitrary keys.** Change both checks from `set(...) != <exact>` to `not (required <= set(...) <= allowed)`, mirroring the `required_fields <= set(raw) <= allowed_fields` shape already in `_parse_emitted_concepts`. For the tree, `required` stays the current four fields and `allowed` adds `record_kind`; for a node, `required` stays the current nine and `allowed` adds `bucket` and `bucket_anchor`. Absent optional keys fall to the dataclass defaults; an unknown key still raises `InvalidConceptTreeError`. This is the single change that keeps legacy records loadable while admitting the new shape.
- **Branch `load_concepts` on `record_kind` for the staleness decision only.** Keep the signature `load_concepts(plan_path, expected_plan_fingerprint)` unchanged (every current caller stays byte-for-byte compatible). After `_decode_tree` + `_validate_tree`:
  - `record_kind == "full-tree"` (legacy/default): unchanged — compare `tree.plan_fingerprint` against `expected_plan_fingerprint` and raise `StaleConceptTreeError` on mismatch.
  - `record_kind == "guide-post"`: **skip** that comparison and return the record. `expected_plan_fingerprint` is simply not consulted for the staleness decision. This is the whole point — a guide post persists across unrelated edits; its per-bucket staleness is a caller concern in later steps.
- **Keep `_validate_tree`'s structural guards; add only per-kind checks.** Recommended constraints, stated so a reviewer sees they're deliberate:
  - Keep `plan_fingerprint` required and non-empty for **both** kinds (the guide-post writer in step 4 sets it as provenance; the loader just stops gating staleness on it). Do not relax it.
  - For a guide-post record, require every node's `decision` to be `defer` or `wont_do` and its `bucket`/`bucket_anchor` to be non-empty — a guide post with no decision or no anchor is malformed. This per-kind check is genuinely new validation; if you'd rather let step 4's writer own decision validation, you have latitude, but at minimum reject a guide-post node with an empty `bucket_anchor` (an anchor is the point of the record).
  - Validate the two new fields are strings in `_validate_node` (alongside the existing `source`/`decision`/`rationale` string checks). **Do not** add them to identity — `concept_id` and the `node.id == expected_id` check must stay exactly as they are, so the bare id a guide post exposes is stable regardless of bucket churn.
- **Serialization is free but the writer wiring is not this step.** `save_concepts` serializes via `asdict(tree)`, so the new fields round-trip with no code change — a guide-post `ConceptTree` you build in a test saves and loads. The **production writer** for guide posts (create's deferral-only gate, which routes through `synchronize_concepts`) is step 4; this step only proves the shape round-trips, it does not wire a live producer.
- **Update the sidecar docs as guard-safe prose plus two field rows.** In `DATA_CONTRACT.md`: add `bucket`, `bucket_anchor` rows to the `ConceptNode` table and a `record_kind` row to the `ConceptTree` table (the drift guard `tests/test_data_contract.py:test_every_persisted_field_is_documented_in_own_section` requires every runtime field to appear as `` `name` `` in its own section — new fields flow into the registry automatically via `dc.fields`, so `plan_tool/data_contract.py` needs no edit, but an undocumented field fails the guard). Extend the `## Concept sidecar` prose to say a guide-post record validates each guide post per-bucket against a scoped anchor and is **not** rejected on the bundle `plan_fingerprint`, and add `bucket`/`bucket_anchor` to the node section's "Identity excludes …" sentence. These are field rows plus prose in **existing** sections — no new top-level section, which is what would trip the guard.

## Tests

New behavior — add these unit tests **with** the implementation. Every one must be green before the step is done (the plan sets `enforce_step_tests: true`).

In `tests/test_concept_tree.py` (mirror the existing round-trip/stale style):

- `test_guide_post_record_round_trips` — a `ConceptTree(record_kind="guide-post")` with a flat node carrying `bucket`, `bucket_anchor`, `decision="defer"`, `review_state="unreviewed"` saves via `save_concepts` and loads back equal.
- `test_guide_post_record_ignores_bundle_fingerprint` — a guide-post record whose stored `plan_fingerprint` differs from the `expected_plan_fingerprint` passed to `load_concepts` returns the record and raises **no** `StaleConceptTreeError`.
- `test_legacy_full_tree_record_still_stale_on_mismatch` — a full-tree record with a mismatched fingerprint still raises `StaleConceptTreeError` (current behavior unchanged).
- `test_legacy_record_missing_new_fields_loads` — an on-disk record whose JSON lacks `record_kind` and whose nodes lack `bucket`/`bucket_anchor` decodes, defaulting `record_kind="full-tree"`, `bucket=""`, `bucket_anchor=""`.
- `test_unknown_field_still_rejected` — a record with an extra unknown node or tree key still raises `InvalidConceptTreeError` (the loosening did not admit arbitrary keys).
- `test_guide_post_identity_excludes_bucket_fields` — two nodes with the same title/parent_path but different `bucket`/`bucket_anchor` share the same `id`; a hand-tampered `id` is still rejected.
- `test_guide_post_requires_decision_and_anchor` — a guide-post node with `decision` not in `{defer, wont_do}`, or with an empty `bucket_anchor`, is rejected as invalid (adjust to match the per-kind strictness you chose).

In `tests/test_data_contract.py`:

- `test_concept_node_documents_guide_post_fields` — `bucket` and `bucket_anchor` appear as backticked field names in the `ConceptNode` section.
- `test_concept_tree_documents_record_kind_and_scoped_anchor` — `record_kind` appears in the `ConceptTree` section and the `## Concept sidecar` prose mentions the guide-post / scoped-anchor staleness rule.

### Test-creation order (feature step)

This is a **feature** step. Author all the cases above alongside the `concept_tree.py` and `DATA_CONTRACT.md` edits. The existing `tests/test_concept_tree.py` cases (round-trip, stale-on-mismatch, tamper rejection) must stay green unchanged — legacy behavior is preserved, not replaced. Green before the step is finished.

## Acceptance criteria

- `ConceptNode` has string fields `bucket` and `bucket_anchor` defaulting to `""`; `ConceptTree` has a string field `record_kind` defaulting to `"full-tree"`.
- `load_concepts` returns a guide-post record (`record_kind == "guide-post"`) without raising `StaleConceptTreeError` even when its stored `plan_fingerprint` differs from `expected_plan_fingerprint`.
- `load_concepts` still raises `StaleConceptTreeError` for a full-tree record whose stored `plan_fingerprint` differs from `expected_plan_fingerprint`.
- A legacy on-disk record missing `record_kind`, `bucket`, and `bucket_anchor` loads successfully with those fields defaulted.
- A record with any unknown top-level or node key still raises `InvalidConceptTreeError`.
- `node.id` is unchanged by any value of `bucket`/`bucket_anchor`; a tampered `id` is still rejected.
- A guide-post `ConceptTree` round-trips through `save_concepts` → `load_concepts` unchanged.
- `DATA_CONTRACT.md` documents `bucket`, `bucket_anchor`, and `record_kind`, and states guide-post records validate per-bucket against a scoped anchor rather than the bundle fingerprint.
- `uv run pytest tests/test_concept_tree.py tests/test_data_contract.py -q` passes, including the new cases.
- `plan_tool/concept_tree.py` imports no new first-party module (no change to its import surface).

## References

- [dataclasses — Data Classes (Python docs)](https://docs.python.org/3/library/dataclasses.html) — adding fields with defaults to `ConceptNode`/`ConceptTree` and how `asdict` serializes them.
- [json — JSON encoder and decoder (Python docs)](https://docs.python.org/3/library/json.html) — `object_pairs_hook` (duplicate-key rejection) and decode behavior the loader relies on to keep both record shapes parseable.
- [hashlib — Secure hashes and message digests (Python docs)](https://docs.python.org/3/library/hashlib.html) — background for the `bucket_anchor` value produced by step 1's `compute_bucket_anchor`.

## Deferred

- Re-validating a guide post against **current** bucket source text (recompute `compute_bucket_anchor` on the drilled section and compare to the stored `bucket_anchor`) so a bucket-level mismatch means "re-derive," never a crash — this needs the plan parsed and belongs to the read/confirm callers: `plan_tool/review.py:check_concept_coverage` and its `collect_*` callers (step 6), and `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` (step 5).
- The production **writer** that records a proposed deferral as a pending guide post through `synchronize_concepts` — create's deferral-only gate (step 4). This step defines the shape and proves it round-trips; it wires no live producer.
- Detail's shared-find routing recording a guide post on a narrowed or absent record — step 8.
- Migrating existing eager full-tree `concepts.json` records to the guide-post shape — out of scope plan-wide; legacy records stay loadable as-is.
- Bucket-source extraction (deciding *which* text is a bucket's source) — the callers own it in steps 4/5/6; `concept_tree.py` never parses the plan here.
