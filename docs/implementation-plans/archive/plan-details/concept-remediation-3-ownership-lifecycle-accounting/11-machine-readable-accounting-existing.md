# Step 11 — Add machine-readable accounting to carved seeds

## Summary

This step adds a bounded, versioned accounting envelope to the carved seeds rendered by `plan_tool/scope_out.py:render_carved_seed` and `render_carved_region_seed`. The envelope records exact concept IDs, their source-step and artifact links, dispositions, structured non-delivery records, and source provenance without treating the seed’s prose as authoritative. `plan_tool/scope_out.py:scope_out_step` builds the envelope from the same validated accounting snapshot prepared for the scope-out transaction. On green, every newly rendered carved seed contains deterministic JSON that step 11 can validate and present for explicit restoration review.

## Table of Contents

- [Summary](#summary) — The seed-envelope change and observable result.
- [Why](#why) — Why the current prose cannot safely restore accounting.
- [Input](#input) — The dependency-owned accounting and scope-out snapshots.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two scoped files and their changes.
- [Implementation](#implementation) — The envelope contents, rendering rules, and orchestration.
- [Tests](#tests) — Unit coverage for exact, deterministic accounting output.
- [Acceptance criteria](#acceptance-criteria) — Observable requirements for completion.
- [References](#references) — Primary specifications relevant to the envelope.
- [Deferred](#deferred) — Parsing, sibling seed work, and lifecycle integration owned elsewhere.

## Why

`plan_tool/scope_out.py:_scope_block` currently renders `Step.concept_ids` as Markdown bullets, but those bullets do not identify a structured non-delivery record, prove which signed concept snapshot supplied the IDs, or distinguish exact restoration data from explanatory prose. A create flow could only recover that information by parsing human-readable text or matching titles, both of which the plan forbids as accounting authority. A bounded JSON envelope lets step 11 detect dropped, invented, stale, contradictory, or ambiguous input before any restored ownership is published.

## Input

- **Step 2 accounting contract:** Consume the durable structured non-delivery records delivered by step 2, including their stable record identity, exact concept ID, disposition, rationale, artifact reference, optional source-step routing, and review state. Do not define a second durable record model in `plan_tool/scope_out.py`.
- **Step 8 scope-out result:** Consume the validated, explicitly reviewed accounting candidate and its publication precondition produced by step 8. The seed projection and the scope-out publication must describe the same prepared transition.
- **Source ownership:** `plan_tool/schema.py:Step.concept_ids`, `Step.scope`, `Step.detail`, and `Step.all_files` provide exact authored ownership, disposition, and artifact context. Titles and detail prose are display context only.
- **Narrow preview:** `plan_tool/scope_out.py:NarrowPreview`, especially `carved_ids`, `new_steps`, and `narrowed_plan`, identifies the carved region and which concepts retain committed owners after the carve.
- **Transaction snapshot:** `plan_tool/scope_out.py:_ConceptNarrowUpdate` carries the original and prepared concept states used by stale checks and rollback. Extend or project this internal result as needed so seed rendering does not reread mutable disk state.
- **Verification limit:** Because `scope_out_step` writes the seed before `apply_narrow`, a surviving seed does not prove that the narrow was published. Its provenance must let step 11 detect that mismatch rather than claim the prepared state is current.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/scope_out.py` — Build a bounded accounting projection from the validated scope-out snapshot, render it in both single-step and region seeds, and pass it through `scope_out_step`.
  - `tests/test_scope_out.py` — Add exact-envelope, ordering, provenance, many-owner, empty-accounting, and seed-first failure coverage.

## Implementation

The foundational logic is: **every newly generated carved seed carries one deterministic machine-readable projection of the exact accounting transition, while prose remains non-authoritative context.**

- **Keep the renderers pure.** `plan_tool/scope_out.py:render_carved_seed` and `render_carved_region_seed` should receive an already-prepared accounting projection and serialize it without filesystem access. Require an explicit empty projection when no concepts or records apply so every new carved seed is distinguishable from a legacy prose-only seed.

- **Use one clearly delimited, versioned JSON envelope.** Place it consistently near the existing `plan-tool scope-out carved-seed` provenance header so step 11 can find it without scanning Markdown sections. Include a format discriminator and schema version; reject the alternative of recovering ownership from `Concept IDs owned by this carved step` bullets or detail text.

- **Keep the envelope bounded to the carved operation.** Carry only the concepts, ownership links, and non-delivery records needed to explain the carved region and its prepared transition. Do not serialize the whole `ConceptTree` or unrelated plan content.

- **Preserve exact source identity.** For each carved source step, retain:
  - its source step ID and stable artifact reference when one exists;
  - its scope or accounting disposition;
  - its ordered `concept_ids`, including an explicit empty list;
  - the applicable step-2 non-delivery record identities and fields needed for later validation; and
  - whether another committed owner survives when that fact affects the prepared transition.

  Keep repeated concept IDs attached to each source owner. Do not union them into one synthetic owner or collapse valid many-owner relationships.

- **Carry both sides of the seed-first boundary.** Record provenance for the validated source snapshot and identify the prepared post-carve accounting projection separately. If `apply_narrow` later fails, the durable seed must remain parseable but fail step 11’s current-source comparison instead of presenting the unpublished candidate as current.

- **Use dependency-owned fingerprints and identities.** Reuse the source-record fingerprint, stable non-delivery record IDs, and artifact references supplied by steps 2 and 8. Do not hash titles, Markdown bodies, mutable step numbers, or a fresh filesystem read to create replacement identities in this step.

- **Project from the same prepared state used for publication.** In `plan_tool/scope_out.py:scope_out_step`, build the envelope after `_prepare_concept_narrow_update` and the explicit step-8 review gate have produced a valid candidate, but before selecting the single-step or region renderer. Pass that same projection to either renderer and then pass the unchanged prepared update to `apply_narrow`.

- **Preserve gate ordering.** Blocked, recommend-only, declined, non-TTY, and missing-accounting paths must continue to write no seed. Only the confirmed apply branch renders the envelope and writes the seed before the narrow transaction.

- **Keep single-step and region semantics aligned.** `render_carved_seed` should encode one source-step entry. `render_carved_region_seed` should encode one entry per carved step in normalized carved-ID order, without losing in-region ownership links or merging distinct records.

- **Make serialization reproducible.** Use a fixed JSON field order or canonical key ordering, UTF-8 output, no non-finite values, and compact deterministic separators. Preserve authored order where order is part of the accounting contract; sort only sets whose existing scope-out contract already normalizes them.

- **Retain the current prose for people.** `plan_tool/scope_out.py:_scope_block`, `_done_context_block`, `_upstream_block`, and the `## Provenance` section remain useful review context. They may repeat display values, but only the JSON envelope is intended for machine restoration.

## Tests

- `tests/test_scope_out.py:test_carved_seed_contains_versioned_accounting_envelope` — a single-step seed contains one parseable envelope with its format discriminator and schema version.
- `tests/test_scope_out.py:test_carved_seed_records_exact_source_ownership` — ordered concept IDs remain attached to the correct source step and artifact reference.
- `tests/test_scope_out.py:test_region_seed_keeps_accounting_per_source_step` — a region emits one ordered source entry per carved step without unioning their IDs.
- `tests/test_scope_out.py:test_region_seed_preserves_many_owner_concepts` — a concept linked to multiple carved steps retains every exact ownership link.
- `tests/test_scope_out.py:test_carved_seed_records_surviving_external_owner` — shared ownership is distinguished from a concept that becomes ownerless.
- `tests/test_scope_out.py:test_carved_seed_carries_prepared_non_delivery_records` — ownerless concepts carry the exact reviewed step-8 records, including stable identity, disposition, artifact reference, and review state.
- `tests/test_scope_out.py:test_carved_seed_does_not_copy_unrelated_accounting` — concepts and records outside the carved operation are absent from the bounded envelope.
- `tests/test_scope_out.py:test_carved_seed_emits_explicit_empty_accounting` — a carve with no concept links still emits a valid modern envelope with empty collections.
- `tests/test_scope_out.py:test_carved_seed_accounting_is_deterministic` — identical inputs produce identical envelope bytes and preserve required authored ordering.
- `tests/test_scope_out.py:test_carved_seed_provenance_separates_source_and_prepared_state` — the envelope identifies both the validated source snapshot and the proposed post-carve accounting.
- `tests/test_scope_out.py:test_seed_surviving_failed_narrow_does_not_claim_publication` — a seed retained after `apply_narrow` fails remains marked as a prepared transition whose source comparison can fail.
- `tests/test_scope_out.py:test_non_apply_paths_write_no_accounting_seed` — blocker, recommend-only, declined, and non-TTY paths create no seed.
- `tests/test_scope_out.py:test_accounting_envelope_does_not_depend_on_prose` — changing titles or detail prose does not change exact concept and record identities in the envelope.

### Test-creation order (feature step)

Add the pure single-step and region renderer tests with the envelope projection and serialization work first. Add `scope_out_step` tests when wiring the step-8 prepared candidate into the seed-first apply branch, then add refusal and failed-narrow cases to protect the transaction boundary. Every new test listed for this step and the existing focused tests in `tests/test_scope_out.py` must be green before the step is considered finished.

## Acceptance criteria

- Every seed produced by `plan_tool/scope_out.py:render_carved_seed` or `render_carved_region_seed` contains exactly one parseable, versioned accounting envelope.
- A seed with no applicable concept accounting contains explicit empty collections rather than omitting the envelope.
- The envelope preserves each carved step’s ordered concept IDs and does not infer identity from titles, detail prose, or file names.
- Region seeds retain separate source-step entries and preserve valid many-owner links without unioning ownership.
- Ownerless concepts carry the exact reviewed structured non-delivery records prepared by step 8.
- Concepts with surviving committed owners are distinguishable from concepts that become ownerless.
- The envelope includes provenance sufficient to compare its source accounting snapshot with the current signed record.
- A seed written before a failed narrow does not claim that its prepared accounting transition was published.
- Identical renderer inputs produce identical envelope bytes.
- Blocked, recommend-only, declined, and non-TTY scope-out paths write no seed.
- Existing human-readable scope, done-context, prerequisite, and provenance sections remain present.
- The focused `tests/test_scope_out.py` suite passes.

## References

- [JSON Schema Validation Draft 2020-12](https://json-schema.org/draft/2020-12/json-schema-validation) — Use its required-field, enum, uniqueness, and conditional-constraint model when fixing the bounded envelope shape consumed by step 11.
- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Use its deterministic JSON principles to keep equivalent accounting projections reproducible.
- [pytest: How to Parametrize Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use parametrization for single-step, region, shared-owner, ownerless, and empty-accounting cases.

## Deferred

- `plan_tool/create.py` seed parsing, stale-source validation, proposal mapping, and explicit restoration review — step 11 consumes the envelope and decides whether accounting may be restored.
- `plan_tool/reground.py:render_rebaseline_seed` — step 9 adds the equivalent machine-readable envelope to re-baseline seeds; this step does not edit that sibling renderer.
- A shared cross-module seed-envelope serializer — extracting one would add a shared production file outside this step and step 9; reconcile should consider consolidation if the two dependency-scoped implementations cannot reuse an already delivered helper.
- Full create-to-scope-out lifecycle conservation coverage — step 12 verifies the completed producer and restoration flow across module boundaries.
