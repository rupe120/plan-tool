# Step 10 — Add machine-readable accounting to re-baseline seeds

## Summary

This step extends `plan_tool/reground.py:render_rebaseline_seed()` so a re-baseline seed carries a bounded JSON accounting envelope alongside its existing human-readable sections. The envelope records exact per-step concept ownership, each step’s seed role, structured non-delivery records from step 2, and a fingerprint of the source concept record. `plan_tool/reground.py:reground_bridge()` loads and validates current accounting before writing the seed while preserving its seed-first plan-update order. On green, `tests/test_reground.py` proves that re-baseline seeds preserve exact machine-readable accounting without changing mark-done behavior or relying on prose parsing.

## Table of Contents

- [Summary](#summary) — The seed-accounting change and observable result.
- [Why](#why) — Why the current prose-only ownership hints are insufficient.
- [Input](#input) — The plan and step-2 accounting contracts consumed by the renderer.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two scoped files and their changes.
- [Implementation](#implementation) — The envelope shape, provenance, loading, and ordering rules.
- [Tests](#tests) — Focused coverage for rendering, validation, and bridge behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable requirements for completion.
- [References](#references) — Primary specifications for canonical JSON, hashing, and validation.
- [Deferred](#deferred) — Carved-seed production and create-time restoration owned by later steps.

## Why

`plan_tool/reground.py:_rebaseline_step_bullet()` currently places `concept_ids` only in prose, while `render_rebaseline_seed()` carries no structured non-delivery records and no fingerprint tying the seed to the source concept record. A later create run would have to parse descriptive Markdown or guess how source steps map to new steps, which cannot safely distinguish dropped, invented, stale, or ambiguous accounting. A bounded JSON envelope preserves the exact source facts for step 11’s explicit restoration review without making the seed prose authoritative.

## Input

- **Step 2 output:** Consume its durable `ConceptTree` non-delivery collection and record contract. Preserve every record field and its established order; this step does not redefine record identity, review state, or migration behavior.
- **Plan ownership:** Read exact ordered ownership from `plan_tool/schema.py:Step.concept_ids`. Shared ownership is valid, and an ID must remain attached to every source step that owns it.
- **Current concept record:** Load through `plan_tool/concept_tree.py:load_concepts()` using `plan_tool/review_persistence.py:compute_plan_fingerprint()`. Treat an invalid or stale present sidecar as unsafe input rather than emitting accounting from it.
- **Existing seed roles:** Derive machine-readable roles from the same partition already used by `plan_tool/reground.py:render_rebaseline_seed()` and its `_rebaseline_done_context_block()`, `_rebaseline_scope_block()`, and `_rebaseline_deferred_block()` helpers.
- **Legacy plans:** A plan with no concept sidecar and no concept ownership remains eligible for its existing prose-only re-baseline path. Do not fabricate a signed record or non-delivery entries.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/reground.py` — Define and render the versioned seed-accounting envelope, load current concept accounting for the re-baseline branch, and pass it into `render_rebaseline_seed()`.
  - `tests/test_reground.py` — Add exact envelope, fingerprint, non-delivery, legacy, validation-failure, and no-regression coverage.

## Implementation

The foundational logic is **exact seed accounting serialization: emit one deterministic structured snapshot of source ownership and non-delivery records without deriving accounting from prose or changing it during re-grounding**.

- **Keep the existing seed body.** Preserve the human-readable header, `Done-context`, `Scope to re-plan`, `Deferred (parked)`, and `Provenance` sections produced by `plan_tool/reground.py:render_rebaseline_seed()`. Add a distinct machine-readable HTML-comment envelope; do not replace those sections or require human readers to inspect JSON.

- **Define a versioned, bounded envelope.** Use a stable marker such as `plan-tool seed-accounting` and a module constant for its schema version. The JSON must contain:
  - the envelope schema version;
  - a source kind identifying a re-baseline seed;
  - the source plan path and source plan fingerprint;
  - the source concept-record fingerprint;
  - the ordered re-grounded step IDs;
  - one ordered step-accounting object per rendered source step, containing `source_step_id`, a seed role, and that step’s ordered `concept_ids`;
  - the ordered structured non-delivery records supplied by step 2.

  Use three unambiguous seed-role values such as `done_context`, `replan`, and `parked`. Keep these separate from a non-delivery record’s `defer` or `wont_do` disposition.

- **Serialize deterministically.** A recommended approach is UTF-8 JSON with sorted object keys, compact separators, preserved list order, and no non-finite values. Step-accounting objects should follow plan step order, while concept IDs and non-delivery records retain their source order. Do not sort or union concept IDs across steps.

- **Fingerprint the source concept record.** Compute the SHA-256 digest from a documented canonical projection of the loaded step-2 `ConceptTree`, not from current files later in the operation. Pin the format tag, UTF-8 encoding, key ordering, separators, and one golden input-to-digest vector in `tests/test_reground.py`. The envelope must carry the empty sentinel only when no concept record exists; it must never substitute the plan fingerprint for the concept-record fingerprint.

- **Keep rendering pure.** Extend `plan_tool/reground.py:render_rebaseline_seed()` with an optional structured accounting input, or introduce a small pure helper beside it. The renderer must not load files, calculate live fingerprints, invoke Claude, or write the seed. Direct renderer tests should remain fully in-memory.

- **Load accounting in the bridge.** In the `DISPOSITION_REBASELINE` apply path of `plan_tool/reground.py:reground_bridge()`, calculate the current plan fingerprint and load the step-2 concept record before rendering. Validate that every `Step.concept_ids` value present in the plan names a concept in the loaded record. Unknown IDs, a stale record, or a malformed record must stop the re-baseline before either the seed or plan is written.

- **Preserve legacy behavior deliberately.** If no concept record exists:
  - allow the existing path when the plan has no `concept_ids`;
  - refuse to emit an authoritative accounting envelope when any step has concept ownership, because there is no signed record against which those IDs can be checked.

  This distinguishes a genuinely legacy unowned plan from a concept-enabled plan whose record is missing.

- **Preserve bridge gates.** `step-missing`, `unsafe`, `noop`, `recommended`, and declined-confirmation results must still write no seed and need not load concept accounting. The default `DISPOSITION_MARK_DONE` path must not gain a concept-sidecar dependency.

- **Publish the re-baseline generation together.** Once accounting validation succeeds, prepare the complete seed plus the marked plan and refreshed concept fingerprint, then submit seed creation, plan replacement, and sidecar update through the prerequisite publication API. The envelope records both the pre-mark source fingerprint used for review compatibility and the intended final marked-plan fingerprint. A restored failure removes the seed and restores the original plan/sidecar; rollback failure reports uncertainty.

- **Keep all source steps represented.** The envelope must cover the same flagged, remaining committed, and remaining deferred steps rendered in prose. Already-done steps outside the flagged set are not re-planned and should follow the renderer’s existing inclusion rules rather than being added only for accounting.

- **Do not infer restoration mappings.** Record source facts only. Do not map source steps to proposed replacement steps, change review state, approve records, or resolve conflicts in this step.

- **Keep the import boundary narrow.** `plan_tool/reground.py` must continue to avoid module-level imports from `plan_tool/detail.py`, `plan_tool/launcher.py`, and `plan_tool/scope_out.py`. Function-local imports for concept loading and fingerprint computation are consistent with the existing leaf boundary.

## Tests

- `test_rebaseline_seed_contains_versioned_accounting_envelope` — a concept-enabled seed contains one parseable JSON envelope with the expected marker and schema version.
- `test_rebaseline_accounting_classifies_all_rendered_steps` — flagged, remaining committed, and deferred steps receive `done_context`, `replan`, and `parked` roles respectively.
- `test_rebaseline_accounting_preserves_per_step_concept_order` — every step retains its exact ordered `concept_ids` without sorting, union, or deduplication across owners.
- `test_rebaseline_accounting_preserves_shared_ownership` — one concept owned by several source steps appears on every corresponding step-accounting object.
- `test_rebaseline_accounting_carries_non_delivery_records_exactly` — all step-2 record fields and ordering survive serialization unchanged.
- `test_rebaseline_accounting_fingerprint_has_golden_vector` — a fixed concept record produces the documented SHA-256 value.
- `test_rebaseline_accounting_fingerprint_changes_with_source_record` — changing reviewed accounting changes the source-record fingerprint.
- `test_rebaseline_accounting_is_deterministic` — equivalent inputs render the same envelope bytes.
- `test_rebaseline_rejects_unknown_owned_concept_before_writes` — ownership absent from the loaded concept record produces no seed and leaves the plan unchanged.
- `test_rebaseline_rejects_stale_or_invalid_concept_record_before_writes` — stale and malformed sidecars cannot produce a seed or mark steps done.
- `test_rebaseline_rejects_missing_record_for_concept_owned_plan` — a missing sidecar does not turn plan ownership into unsigned authoritative accounting.
- `test_rebaseline_legacy_unowned_plan_remains_supported` — a plan with no sidecar and no concept IDs retains the existing re-baseline behavior.
- `test_mark_done_disposition_does_not_load_concept_accounting` — ordinary mark-done remains independent of the sidecar.
- `test_rebaseline_refusal_paths_do_not_load_or_write_accounting` — noop, recommendation, and declined-confirmation paths remain mutation-free.
- `test_rebaseline_seed_uses_pre_mark_accounting_snapshot` — the written envelope describes the source plan before the flagged steps are marked done.
- `test_reground_import_boundary_remains_intact` — the module still has no forbidden module-level detail, launcher, or scope-out import.

### Test-creation order (feature step)

1. Add pure renderer tests for the envelope shape, step roles, exact ownership, shared ownership, and non-delivery records.
2. Add the golden fingerprint and deterministic-rendering tests with the canonical projection helper.
3. Add bridge tests for current, absent, stale, malformed, and unknown-concept sidecars.
4. Add refusal-path, mark-done independence, seed-first snapshot, and import-boundary regressions.

Every new test listed for this step and the existing focused suite in `tests/test_reground.py` must be green before this step is considered finished.

## Acceptance criteria

- A re-baseline seed produced from a current concept record contains exactly one parseable, versioned machine-readable accounting envelope.
- The envelope identifies the source plan, source plan fingerprint, source concept-record fingerprint, re-grounded step IDs, per-step seed roles, exact ordered ownership, and all structured non-delivery records.
- Flagged, remaining committed, and deferred source steps receive distinct machine-readable roles matching their prose sections.
- Shared concept ownership remains attached to every owning source step and is never collapsed into a plan-wide union.
- The source concept-record digest matches the documented golden vector and changes when the canonical source accounting changes.
- `render_rebaseline_seed()` remains deterministic and performs no file I/O.
- A stale, malformed, missing-required, or ownership-inconsistent concept record causes no seed write and no plan mutation.
- A plan with no concept record and no concept ownership retains the existing re-baseline behavior.
- `DISPOSITION_MARK_DONE` and every non-applied `reground_bridge()` outcome remain independent of concept-accounting loading and write no seed.
- A successful re-baseline publishes the seed, marked plan, and refreshed sidecar together; its envelope distinguishes the reviewed pre-mark source fingerprint from the final published generation.
- Existing ownership prose and all focused tests in `tests/test_reground.py` continue to pass.

## References

- [JSON Schema Validation Draft 2020-12](https://json-schema.org/draft/2020-12/json-schema-validation) — Use its required-field, enum, array, and uniqueness rules when defining the bounded envelope.
- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Use its deterministic JSON principles when fixing the source-record fingerprint projection.
- [hashlib — Secure Hashes and Message Digests](https://docs.python.org/3/library/hashlib.html) — Use Python’s SHA-256 API for the reproducible concept-record fingerprint.
- [pytest: How to Parametrize Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use parametrization for stale, malformed, missing, and inconsistent concept-record cases.

## Deferred

- `plan_tool/scope_out.py:render_carved_seed()` and `render_carved_region_seed()` — step 10 adds machine-readable accounting to carved seeds; reconcile should ensure both seed producers use one compatible envelope contract rather than independent formats.
- `plan_tool/create.py:create_plan()` restoration parsing, source-record comparison, proposal mapping, and operator review — step 11 consumes the seed accounting and decides whether replacement mappings are exact, ambiguous, stale, dropped, or invented.
- Non-delivery approval and decision transitions — step 3 owns review semantics; this step copies the step-2 records without changing them.
- Lifecycle-wide restoration coverage — step 12 tests re-baseline accounting together with create, split, merge, scope-out, regeneration, and completeness.
