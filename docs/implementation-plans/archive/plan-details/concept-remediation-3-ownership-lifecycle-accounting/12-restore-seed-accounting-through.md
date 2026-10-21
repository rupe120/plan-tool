# Step 12 — Restore seed accounting through explicit create review

## Summary

This step makes `plan_tool create --from-existing` consume the machine-readable accounting envelopes produced by steps 9 and 10. `plan_tool/concept_tree.py` parses and validates the envelope, while `plan_tool/create.py:create_plan()` reconciles its exact concept IDs and accounting links with the settled destination steps through an explicit operator review. `plan_tool/prompts/distill-seed.md` keeps the envelope out of model-authored prose so it cannot become a second authority. On green, valid reviewed mappings reach the new plan and concept sidecar exactly, while stale, unknown, dropped, invented, contradictory, ambiguous, or unattended mappings cannot be silently accepted.

## Table of Contents

- [Summary](#summary) — The restoration behavior and observable result.
- [Why](#why) — Why prose-only seed handling loses authoritative accounting.
- [Input](#input) — The upstream envelope and current create contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The four scoped source and test changes.
- [Implementation](#implementation) — Parsing, validation, review, and publication rules.
- [Tests](#tests) — Unit and integration cases for exact restoration and refusal paths.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions required for completion.
- [References](#references) — Primary guidance for validation and test matrices.
- [Deferred](#deferred) — Related work owned by later steps or existing publishers.

## Why

`plan_tool/create.py:create_plan()` currently replaces the raw seed with distilled text before concept derivation, then `plan_tool/concept_tree.py:emit_concept_tree()` and `plan_tool/create.py:_review_create_concepts()` work only from prose-derived concepts and optional single-owner hints. The exact ownership and structured non-delivery accounting emitted by re-baseline and carved seeds therefore has no authoritative consumer: IDs can disappear, model output can invent replacements, and title similarity can appear to restore a link that was never reviewed. Parsing the envelope before distillation and requiring an exact review against the settled step list closes that gap without making seed prose authoritative.

## Input

- **Step 2 output:** Consume the structured non-delivery records on `plan_tool/concept_tree.py:ConceptTree`. Preserve their stable IDs, exact concept IDs, dispositions, artifact references, routing data, and review states; do not define a create-only persisted record.
- **Step 9 output:** Consume the bounded accounting envelope produced by `plan_tool/reground.py:render_rebaseline_seed()`, including its source provenance and the classifications needed to tell restoration scope from contextual source accounting.
- **Step 10 output:** Consume the same accounting contract from `plan_tool/scope_out.py:render_carved_seed()` and `plan_tool/scope_out.py:render_carved_region_seed()`.
- **Raw source boundary:** `plan_tool/create.py:create_plan()` captures `raw_seed` before `propose_distilled_seed_from_claude()` can replace `from_description` and `seed_body`. Parse accounting from that original value only.
- **Settled destination steps:** Review restoration after `plan_tool/create.py:_review_step_change_types()`, `_review_step_gates()`, and `_seed_initial_step_status()` have produced the final destination step IDs and scopes.
- **Existing publication boundary:** Keep `plan_tool/create.py:synchronize_concepts()` for signed concept publication and `plan_tool/concept_tree.py:save_concepts()` for unsigned resume state. This step changes the candidate supplied to those writers, not their transaction behavior.
- **Legacy input:** A seed without the upstream envelope remains valid and follows the existing bootstrap, enrichment, and concept-review path. Prose such as “Concept IDs owned by this step” is context only and must not be parsed as authoritative accounting.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — Add a strict, write-free parser and validation/preparation helpers for the shared seed-accounting envelope.
  - `plan_tool/create.py` — Parse accounting before distillation, reconcile it against the final proposed steps, require explicit review, and pass the reviewed candidate through the existing publication path.
  - `plan_tool/prompts/distill-seed.md` — Tell the distillation pass to ignore the machine envelope as prose and never reinterpret its identifiers or decisions.
  - `tests/test_create.py` — Cover parsing integration, exact mapping, non-delivery restoration, conflict detection, unattended refusal, legacy behavior, and no-write failures.

## Implementation

The foundational logic is an **exact seed-accounting reconciliation gate**: every accounting item selected for restoration must retain its stable concept identity and end with either explicitly reviewed destination ownership or a matching reviewed non-delivery record.

- **Parse the original seed before any model pass.** In `plan_tool/create.py:create_plan()`, inspect `raw_seed` before `propose_distilled_seed_from_claude()` can replace the downstream source text. An absent envelope selects the existing legacy path. A present but malformed envelope is an accounting error, not an invitation to fall back to prose.

- **Keep envelope parsing in `plan_tool/concept_tree.py`.** Add a small typed result and a public helper with a clear name such as `parse_seed_accounting()`. Validate the exact contract delivered by steps 9 and 10:
  - reject duplicate JSON keys, unknown fields, invalid types, duplicate concept or record identities, and malformed source references;
  - require every stored concept ID and non-delivery record ID to satisfy the step-2 identity rules;
  - preserve input order where the upstream contract defines order;
  - return a validated value without mutating or saving a `ConceptTree`;
  - distinguish “no envelope” from “present but invalid.”

  Do not maintain separate parsers in `plan_tool/create.py`, `plan_tool/reground.py`, and `plan_tool/scope_out.py`. The two producers own serialization; `plan_tool/concept_tree.py` should own the matching read contract.

- **Verify provenance before proposing mappings.** Compare the envelope’s source fingerprint and accounting references using the fields and framing owned by steps 9 and 10. Reject stale or internally inconsistent source accounting before prompting. Do not recompute historical source state from current files, use title matching, or treat narrative provenance text as a substitute for the machine fields.

- **Keep model passes away from accounting authority.** Update `plan_tool/prompts/distill-seed.md` so the accounting block is treated as opaque control metadata already consumed by the caller. The distillation response must not copy it into a body section, paraphrase its identifiers, change its disposition, or use it to invent steps. The existing eight-key single-plan response remains unchanged.

- **Build a restoration candidate before enrichment.** Use the validated envelope to seed the exact concept identities and applicable structured records before calling `plan_tool/concept_tree.py:emit_concept_tree()`. Continue to allow evidence-backed enrichment, but preserve restored nodes and records exactly unless the operator changes them through review. `emit_concept_tree()` must remain fail-soft, return `None` rather than raise for unusable model output, and never persist.

- **Reconcile only against settled destination steps.** Extend `plan_tool/create.py:_review_create_concepts()` or place a focused restoration helper beside it. Run this review after change-type and gate review, when destination step IDs, scopes, splits, and dependencies are stable. The review should show source accounting and the proposed destination mapping together.

- **Require exact ownership choices.**
  - Map a delivered concept only to explicitly selected committed destination steps.
  - Allow multiple destination owners and preserve their reviewed order without duplicates.
  - Reject owners that do not exist or are `deferred`/`wont_do`.
  - Never infer an owner from a matching title, file path, source step number, or model-proposed `concept_ids`.
  - Treat a source-to-destination mapping with several plausible targets as unresolved until the operator chooses.

- **Review structured non-delivery as accounting, not ownership.** Preserve the step-2 record’s concept ID, disposition, rationale or evidence, and stable artifact reference. Show those fields during review and require the final concept decision to agree with the record. Do not allow the same concept to leave review with both active committed ownership and an approved whole-concept non-delivery record unless the shared contract explicitly supports that combination.

- **Enforce conservation across the review.** Compare the reviewed result with the validated restoration set:
  - every applicable source concept appears exactly once in the reviewed concept tree;
  - every active delivery link appears on at least one explicitly selected committed step;
  - every deliberate non-delivery has a matching structured record;
  - no destination step or record contains an invented concept ID;
  - no source concept is silently dropped;
  - no record points to an incompatible decision or stale routing target.

  Report all detected conflicts together where practical so the operator can correct the seed or mapping in one pass.

- **Do not forge review in unattended mode.** When a seed contains accounting that requires restoration decisions, `yes=True` or a non-TTY run must not approve mappings or records from defaults. Refuse before collision archival, plan writing, sidecar writing, or manifest mutation, and explain that the command must be rerun interactively. A seed with no accounting envelope keeps the current unattended behavior.

- **Keep split proposals write-free.** If distillation returns a multi-plan split proposal, preserve `create_plan()`’s existing no-write result. Do not divide one accounting envelope heuristically among several destination plans; restoration begins only when one concrete destination plan and its settled steps exist.

- **Use the existing create publication tail.** After successful review, update `Step.concept_ids` and the candidate `ConceptTree`, then let `plan_tool/create.py:synchronize_concepts()` validate and publish signed accounting. Preserve the current cleanup on synchronization failure and append to the manifest only after plan and sidecar publication succeed.

- **Keep legacy behavior separate.** Seeds without the machine envelope continue through `plan_tool.concept_bootstrap.bootstrap_concepts()`, `plan_tool/concept_tree.py:emit_concept_tree()`, and the ordinary `plan_tool/create.py:_review_create_concepts()` flow. Do not promote headings, bullets, or legacy `source_metadata["step_id"]` hints into authoritative restoration data.

## Tests

- `test_seed_accounting_absent_uses_legacy_create_flow` — a seed without an envelope keeps current bootstrap, enrichment, and review behavior.
- `test_seed_accounting_is_parsed_before_distillation` — valid raw accounting remains available after the downstream source text is replaced by distilled Markdown.
- `test_distill_prompt_excludes_accounting_from_plan_prose` — the prompt tells the model not to copy, reinterpret, or invent from the machine envelope while retaining the existing JSON shape.
- `test_malformed_seed_accounting_fails_before_model_invocation` — invalid machine metadata raises `CreateError` without invoking step, concept, reference, or body synthesis.
- `test_stale_seed_accounting_fingerprint_is_rejected` — provenance that does not identify the embedded source accounting cannot enter review.
- `test_restoration_preserves_exact_concept_ids` — reviewed destination steps receive the source IDs without title-based replacement.
- `test_restoration_allows_shared_explicit_ownership` — one concept can be assigned to several committed destination steps in reviewed order.
- `test_restoration_rejects_unknown_or_uncommitted_owner` — missing, deferred, and `wont_do` destination steps cannot own restored delivery.
- `test_restoration_does_not_infer_owner_from_title_or_source_step_id` — apparent textual or numeric matches remain unresolved without an explicit choice.
- `test_restoration_rejects_dropped_concept_id` — review cannot finish when an applicable source concept has no owner or valid non-delivery record.
- `test_restoration_rejects_invented_concept_id` — destination steps and records cannot introduce an ID absent from the validated restoration set or approved enrichment.
- `test_restoration_rejects_ambiguous_source_mapping` — several possible destination steps require operator selection rather than an automatic choice.
- `test_restoration_preserves_matching_non_delivery_record` — reviewed `defer` or `wont_do` accounting retains its stable record identity and source artifact reference.
- `test_restoration_rejects_decision_record_conflict` — a concept decision and structured non-delivery disposition must agree.
- `test_restoration_rejects_delivery_and_whole_concept_non_delivery` — contradictory final accounting cannot be published.
- `test_restoration_yes_refuses_before_any_write` — unattended create with review-required accounting writes no plan, sidecar, archive, or manifest entry.
- `test_restoration_non_tty_refuses_before_any_write` — a closed or non-interactive terminal cannot approve restoration defaults.
- `test_restoration_split_proposal_writes_nothing` — a multi-plan distill result does not heuristically divide or publish the envelope.
- `test_restoration_success_publishes_plan_and_sidecar_together` — the written plan, concept sidecar, and manifest contain the explicitly reviewed accounting.
- `test_restoration_sync_failure_removes_create_owned_artifacts` — publication rejection keeps the existing plan/sidecar cleanup behavior and leaves the manifest unchanged.

### Test-creation order (feature step)

Add the absent, valid, malformed, duplicate, and stale-envelope cases with the `plan_tool/concept_tree.py` parser. Add exact ownership, shared ownership, non-delivery, dropped, invented, ambiguous, and contradictory cases with the review integration. Add unattended, non-TTY, split, successful publication, and cleanup cases when wiring the gate into `plan_tool/create.py:create_plan()`. Every new test listed for this step and the existing focused create tests must be green before the step is considered finished.

## Acceptance criteria

- `plan_tool/create.py:create_plan()` parses seed accounting from the original raw seed before distillation or synthesis.
- A seed without an accounting envelope follows the existing create behavior.
- A present malformed, duplicate, or stale envelope raises `CreateError` instead of falling back to prose.
- Distillation does not copy or reinterpret machine accounting as plan-body content.
- Restored concepts retain their exact stable IDs.
- Every restored delivery link is explicitly assigned to one or more committed destination steps.
- No title, file-path, source-step-number, or model-output match becomes authoritative without review.
- Reviewed structured non-delivery records retain their stable IDs, dispositions, evidence, and artifact references.
- Dropped, invented, unknown, ambiguous, contradictory, or stale accounting cannot be published.
- `yes=True` and non-TTY execution cannot approve restoration mappings or non-delivery records.
- Refused restoration writes no plan, concept sidecar, collision archive, or manifest entry.
- A distill split proposal remains write-free and does not divide accounting heuristically.
- Successful interactive restoration publishes matching `Step.concept_ids` and `ConceptTree` accounting through the existing synchronization path.
- Focused tests in `tests/test_create.py` pass.

## References

- [JSON Schema Validation Draft 2020-12](https://json-schema.org/draft/2020-12/json-schema-validation) — Use its validation concepts for required fields, bounded values, uniqueness, and conditional envelope constraints.
- [pytest: How to Parametrize Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use parametrized cases for malformed fields, provenance failures, conflicting decisions, and invalid destination mappings.

## Deferred

- Full lifecycle integration matrix — step 12 verifies create restoration together with split, merge, re-ground, scope-out, regeneration, and completeness.
- Publication and rollback internals — this step keeps `plan_tool/create.py:synchronize_concepts()` and the existing create cleanup sequence unchanged.
- Legacy prose recovery — seeds without the step-9/step-10 envelope remain supported, but prose concept bullets never become authoritative restoration metadata.
- Multi-plan allocation — a split proposal stays write-free; accounting is reviewed only after a concrete destination plan exists.
