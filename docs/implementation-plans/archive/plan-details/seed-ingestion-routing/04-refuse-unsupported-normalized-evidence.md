> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Refuse unsupported normalized evidence before every later create authoring call

## Summary

Add a pre-authoring evidence gate in `plan_tool/create.py` for the normalized
result supplied by step 3. The gate rejects a file-backed normalized candidate
when any evidence-only body section lacks validated raw-source provenance,
before risk classification, step work, References research, body synthesis,
publication, or convergence. Extend `tests/test_create.py` to prove the same
no-cost refusal in iterative and non-iterative modes. On green, a normalized
candidate with unsupported scope, risk, testing, acceptance, or deferral content
returns the existing refused route rather than reaching a late placeholder check.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the evidence gate and its result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The lost evidence distinction this step closes.
- [Input](#input) — The normalized result and evidence policy this gate consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Required gate placement, scope, and call suppression.
- [Tests](#tests) — Focused cases for supported and unsupported normalized evidence.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant language and test-fixture references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit the gate.
- [Deferred](#deferred) — Lifecycle work owned by later steps.

## Why

Step 3 retains the normalized section map and its validated raw-source spans
because `plan_tool/create.py:_render_distilled_markdown` emits only materialized
text. Without a gate that reads that typed result, a non-null model string can
masquerade as evidence and `plan_tool/create.py:_prepare_create_plan` can spend
downstream model calls or publish an invented commitment. The five evidence-only
sections are commitments the normalizer must not invent, so absent or invalid
provenance must become the existing refused preparation result before later work
starts.

## Input

- **Step 3 normalized result:** Consume step 3’s typed normalized section map
  and validated evidence-span map. Support means a nonempty materialized
  excerpt with matching in-range raw-source spans, not merely a present model
  string. Do not infer this distinction from rendered markdown.

- **Existing policy split:** Use `plan_tool/create.py:_canonical_body_section_keys` and `_DERIVE_FROM_INTENT_SECTIONS` as the policy source. At HEAD, the evidence-only set is `Out of scope`, `Risks`, `Testing`, `Acceptance criteria`, and `Deferred`; `Overview`, `Problem statement`, and `Architecture` remain derivable from stated intent.

- **Route result contract:** Return through the normalized/split/refused preparation contract step 3 establishes. This gate must not invent another route, a raw-text fallback, or a second repair attempt.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — validate retained normalized evidence and convert an unsupported normalized result to the existing refused result before downstream calls.
  - `tests/test_create.py` — add supported-evidence, missing-evidence, no-call, no-write, and iteration-mode coverage.

## Implementation

- **Foundational logic:** Refuse a normalized file-backed candidate when an evidence-only canonical section has no retained source support.

- **Keep the check narrow.** Add a small private validator near
  `plan_tool/create.py:_validate_distilled_sections` or the normalized-result
  handling in `_prepare_create_plan`. It inspects only the five evidence-only
  fields and their step-3-validated provenance: each must have nonempty exact
  materialized source text and at least one valid source span. Do not add
  semantic scoring, heading aliases, or a general seed-quality audit.

- **Reject absent or untrusted provenance.** A missing span, invalid span,
  empty materialized excerpt, or `None` evidence gap is unsupported. A non-null
  model string without validated provenance is equally unsupported. The gate
  does not judge prose quality or fabricate replacement content.

- **Keep validated evidence authoritative.** The accepted materialized map
  reaches the canonical-complete body-synthesis skip only after step 3 has
  already accepted non-empty derived `Overview`, `Problem statement`, and
  `Architecture` fields. If a later writer sees that map, it preserves the five
  evidence-only fields rather than replacing them with a model result. Carry the protected-field set into scope-decision
  rendering, concept synchronization, and convergence so the same rule holds
  through finalization, not only round-zero preparation.

- **Run before rebinding and before any later model call.** In `plan_tool/create.py:_prepare_create_plan`, apply the gate as soon as step 3 returns a normalized result and before assigning normalized text to `seed_body` or `from_description`. The refusal must precede `_propose_risk_profile_from_seed`, `propose_steps_from_claude`, `propose_references_from_claude`, `propose_body_sections`, and their later review or intent-authoring paths.

- **Use the existing refusal boundary.** Convert the unsupported normalized candidate to step 3’s refused result and let its existing pre-publication exit stop the flow. It must not reach `_publish_create_plan`, `write_new_plan`, `append_to_manifest`, or `_converge_create_plan`.

- **Cover both budget modes at the same seam.** Put the gate before publication rather than in `plan_tool/create.py:_converge_create_plan`. This makes `create_plan` refuse before round-zero downstream authoring whether `IterativeBudget.enabled` is false or true, and makes convergence re-proposals unreachable.

- **Leave unrelated routes unchanged.** Direct file-backed sources, preparation splits, preparation refusals, and inline inputs must retain the routes step 2 and step 3 establish. Missing optional `Input`, `Outcome`, or recognized guardrail context must not count as an evidence-only failure.

- **Leave lifecycle reporting to later work.** Keep this step limited to the in-memory refused result and no-write boundary. Step 5 owns operator wording and exit behavior; step 6 owns checkpoint and archive handling.

## Tests

### Tests for this step

- `test_normalized_evidence_gate_requires_each_evidence_only_section` —
  parameterize the five evidence-only canonical sections and assert each
  missing provenance or `None` value produces a refusal that names the
  unsupported section.

- `test_normalized_evidence_gate_allows_source_supported_evidence` — a
  normalized map with all five exact materialized excerpts and matching spans
  continues through the normal preparation path.

- `test_non_null_model_evidence_without_spans_is_refused` — an invented
  non-null model value cannot pass the gate without validated source spans.

- `test_validated_evidence_skips_later_body_synthesis` — later body synthesis
  cannot replace a materialized evidence-only field.

- `test_normalized_evidence_gate_ignores_absent_optional_context` — absent `Input`, `Outcome`, and recognized guardrail context does not trigger the evidence gate when required evidence-only sections are present.

- `test_unsupported_normalized_evidence_stops_before_risk_steps_references_and_synthesis` — after the allowed preparation call, an unsupported normalized result makes no later model-backed create call.

- `test_unsupported_normalized_evidence_refuses_before_publication_without_iteration` — with `IterativeBudget.enabled=False`, refusal produces no plan or manifest entry and does not reach the late placeholder gate.

- `test_unsupported_normalized_evidence_refuses_before_publication_with_iteration` — with `IterativeBudget.enabled=True`, refusal produces no plan or manifest entry and never calls `_converge_create_plan` or an iteration re-proposal.

Every listed test in `tests/test_create.py` must be green before this step is complete.

## Acceptance criteria

- A normalized file-backed result with missing, invalid, or `None` provenance
  for any of `Out of scope`, `Risks`, `Testing`, `Acceptance criteria`, or
  `Deferred` becomes refused before any later create authoring call.

- The evidence check reads step 3’s retained normalized section map and
  validated span map rather than rendered markdown, a non-null model string,
  or a second raw-source scan.

- An unsupported normalized candidate reaches no risk-classification, step, References, body-synthesis, publication, manifest, or convergence path.

- The refusal occurs before publication with both enabled and disabled iteration budgets.

- A normalized candidate with all five exact source-materialized evidence-only
  sections and step 3's non-empty derived fields continues normally, body
  synthesis cannot replace that evidence, and absent optional context does not
  cause refusal.

- Direct, split, already-refused, and inline paths retain their established routing behavior.

- `uv run pytest tests/test_create.py -q` passes.

## References

- [Python enum — Support for enumerationshttps: — Reference for preserving the closed normalized/split/refused result vocabulary.

- [pytest temporary directorieshttps: — Reference for hermetic no-plan and no-manifest assertions.

## Applicable guardrails

- **The plan’s “## Plan intent”, source-supported preparation:** reject missing evidence rather than letting later model calls fill commitments the source does not establish.

- **The plan’s “## Step intent”, early refusal:** place the gate before downstream authoring and the late placeholder path.

- **The plan’s “## Out of scope”, validation boundary:** limit the check to the named normalized evidence fields; do not create a universal semantic audit or broaden heading recognition.

- **The plan’s “## Out of scope”, authoring-contract boundary:** do not alter the step, References-research, or body-synthesis response contracts.

## Deferred

- **Terminal route lifecycle** (`22a740fdbaa54ae54299f4be8f7189fd05c322dc42e247bba3ec3e71d1b4abdc`) — steps 5 and 6 own route reporting, exit mapping, checkpoints, and archive timing.
