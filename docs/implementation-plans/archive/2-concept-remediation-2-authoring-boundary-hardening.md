---
title: Concept Remediation 2 — Authoring Boundary Hardening
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Tighten concept claims against their cited evidence
  files:
  - plan_tool/concept_tree.py
  - plan_tool/shell.py
  - plan_tool/prompts/concept-emit.md
  - tests/test_concept_emit.py
  - tests/test_shell.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/concept-remediation-2-authoring-boundary-hardening/01-tighten-concept-claims-against-their.md
  status: current
- id: 2
  title: Make invalid concept output leave the input tree unchanged
  files:
  - plan_tool/concept_tree.py
  - plan_tool/shell.py
  - tests/test_concept_emit.py
  - tests/test_shell.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/concept-remediation-2-authoring-boundary-hardening/02-make-invalid-concept-output-leave-input.md
- id: 3
  title: Tighten detail envelope and deferral validation
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/concept-remediation-2-authoring-boundary-hardening/03-tighten-detail-envelope-deferral.md
- id: 4
  title: Remove the sidecar-dependent Markdown fallback for detail responses
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/concept-remediation-2-authoring-boundary-hardening/04-remove-sidecar-dependent-markdown.md
- id: 5
  title: Make detail replacement restore the previous body on failure
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: high
  change_type: feature
  depends_on:
  - 4
  detail: docs/implementation-plans/plan-details/concept-remediation-2-authoring-boundary-hardening/05-make-detail-replacement-restore.md
- id: 6
  title: Bound and deduplicate include-triggered detail regeneration
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/concept-remediation-2-authoring-boundary-hardening/06-bound-deduplicate-include-triggered.md
---
# Concept Authoring Boundary Hardening

## Overview

Harden the two model-authored boundaries in the concept workflow so untrusted output either becomes a validated, recoverably published artifact or causes no artifact change. Concept enrichment accepts only concepts whose title has literal provenance in supplied evidence and fails softly for all invalid model output, while fresh detail generation always requires the structured response envelope and preserves the prior body if replacement fails. This plan may execute only after `concept-remediation-1-publication-transactions` has shipped its prepared-detail and publication contracts. It owns validation, parsing, bounded regeneration, and local detail replacement, but not worker-write extraction, multi-artifact concept publication, coverage policy, or structural ownership transformations.

## Problem statement

The completed integration validates response shape without consistently validating meaning or preserving artifacts. `_parse_emitted_concepts()` accepts an unrelated title when `evidence_rationale` merely contains a literal excerpt, and an unpaired surrogate can pass parsing before ID derivation raises `UnicodeEncodeError` outside the fail-soft boundary. `_author_step_detail()` permits legacy Markdown when no concept tree is loaded, and `_archive_existing_detail()` removes the active detail before the replacement is known to be safe. The serial/concurrent regeneration contract also lacks coverage for sibling preservation, deduplication, bounded retries, persistence failure, dry-run, and command failure.

The reconciliation evidence is recorded in `docs/implementation-plans/plan-details/concept-signoff-integrations/convergence-evidence-and-split-recommendation.md`: `step2-run-reconcile-ce244a8e`, `step2-run-reconcile-84957c73`, `step4-run-reconcile-8ae6c687`, `step4-run-reconcile-04ac0dba`, `step4-run-reconcile-28491d51`, and `step4-run-reconcile-a6c41ba8`. The publication API gap identified by `step4-run-reconcile-5830b0ac` belongs to `concept-remediation-1-publication-transactions`, so closing it with another local schema or direct save would violate the intended ownership boundary.

## Architecture

Concept enrichment uses a conservative provenance rule shared by `plan_tool/prompts/concept-emit.md` and `plan_tool/concept_tree.py`. The title is a concept label, not an assertion that the evidence says the concept is true: its normalized phrase must occur literally inside the bounded evidence span, and that span must occur literally in the supplied evidence. This rejects invented labels while correctly permitting a concept that the evidence negates or discusses critically. The response contract omits `suggested_state` because enrichment adds unsigned candidates and must not make a scope decision; any returned `suggested_state` is an unknown field and is rejected. Parsing also bounds title, rationale/span, hierarchy depth, breadth, and rejects duplicate keys, unknown fields, empty or whitespace-only labels, control characters, invalid Unicode, and unsafe hierarchy outcomes. A byte cap is enforced while acquiring backend stdout in `shell_concept_invoker`, before the full output is accumulated; the parser retains a defensive decoded-size cap. If every enriched candidate is rejected, deterministic concepts remain.

The fail-soft producer boundary begins before backend invocation and extends through normalization, encoding, ID/source-key derivation, candidate construction, and merge into a deep copy. `shell_concept_invoker` must preserve backend success/failure status through a typed result or raise a dedicated invocation error on nonzero exit before stdout is parsed; valid-looking stdout from a failed backend is never accepted. Backend invocation/output failures return the documented no-enrichment result without changing the input tree, while programmer and filesystem errors outside that narrow untrusted-output path remain visible.

Every fresh response handled by `plan_tool/detail.py` follows the structured protocol defined by `plan_tool/prompts/detail.md`, regardless of sidecar presence, serial or parallel execution, resume, or reprompt. The envelope separates the detail body from structured deferral candidates and permits prose/candidate parity validation. Existing opaque checkpoints cannot prove payload provenance, so pre-feature detail checkpoints are invalidated and re-invoked instead of parsed as legacy Markdown. Absence of a sidecar cannot enable permissive parsing, and malformed fresh output exhausts the bounded reprompt policy without replacing an artifact.

Detail replacement is a recoverable local operation. The new body is rendered and validated before the old file moves, and a journal records the old active path and archive destination. Failure during the new write or post-write validation restores the prior active bytes; restoration failure produces a distinct error containing the recoverable archive path. The canonical active filename used by plan pointers and downstream tools remains unchanged.

Include-triggered regeneration is deduplicated by affected step and bounded. It consumes the prepared-body/deferral worker outcome already shipped by `concept-remediation-1-publication-transactions`; this plan does not move writes out of workers or introduce another persistence path. The serial parent validates all required bodies and asks the shipped publication authority to commit them. Contradictory output stops with an actionable unresolved-candidate report and retains the last known-good artifacts. Relevant implementation locations are `plan_tool/concept_tree.py`, `plan_tool/shell.py`, and `plan_tool/detail.py`.

## References

- [Claude API Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — Documents schema-constrained responses, unsupported constraints, refusal and truncation exceptions, and required client-side validation.
- [JSON Schema Draft 2020-12 Validation](https://json-schema.org/draft/2020-12/json-schema-validation) — Defines structural validation keywords for bounding strings, arrays, objects, required fields, and permitted values.
- [RFC 7493: The I-JSON Message Format](https://www.rfc-editor.org/rfc/rfc7493.html) — Specifies interoperable JSON restrictions including UTF-8 encoding, rejection of surrogate code points, and unique object member names.
- [Python json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Documents input-size risks, duplicate-name behavior, Unicode handling, and hooks for enforcing stricter JSON decoding.
- [Pydantic Models](https://pydantic.dev/docs/validation/latest/concepts/models/) — Covers validation of untrusted nested data, strict mode, field constraints, extra-field rejection, and model copying.
- [Pydantic Validators](https://pydantic.dev/docs/validation/latest/concepts/validators/) — Explains field and model validators for enforcing semantic relationships such as evidence-to-claim grounding and envelope parity.
- [Python os — Operating System Interfaces](https://docs.python.org/3.13/library/os.html#os.replace) — Documents replacement, renaming, synchronization, and low-level filesystem operations needed for recoverable detail-file updates.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Create collision transactions, sidecar-only resume, manifest recovery, and scope-out publication are excluded because they are separate publication concerns.
- Defining the canonical publisher, moving writes out of detail workers, and replacing direct deferral saves are excluded; those changes ship in `concept-remediation-1-publication-transactions`, and this plan consumes their public contracts.
- `wont_do` completeness semantics and structural deferral-link remapping are excluded as ownership and lifecycle concerns.
- A second model call to judge whether the first model's claim is grounded is excluded in favor of deterministic validation.
- Rewriting old detail files solely to add envelopes is excluded; compatibility, if retained, is provenance-gated.
- General-purpose filesystem transactions are excluded beyond detail artifact replacement.

## Risks

- Grounding can be too strict and reject useful enrichment. The control is to prefer false negatives because deterministic seeds remain, document normalization, and test real evidence phrases.
- Grounding can be too permissive through weak overlap such as stop words. The control is to require a claim-to-span relationship rather than any shared stop word or literal rationale.
- Opaque checkpoints cannot prove detail-protocol provenance. The control is to invalidate and re-invoke pre-feature payloads rather than retain a compatibility parser that malformed fresh output could reach.
- A broad fail-soft catch can hide programmer defects. The control is to catch only errors attributable to invocation or model-output processing and verify that unrelated errors surface.
- Regeneration can loop on contradictory output. The control is to cap attempts, deduplicate by step, report unresolved candidates, and retain known-good artifacts on exhaustion.
- Parallel workers can race while updating shared concept state. The control is for workers to return immutable outcomes while only the serial parent merges and publishes.
- Detail restoration can itself fail. The operation must surface a distinct error and retain the recoverable archive path rather than describing archival as successful recovery.

## Testing

Unit coverage belongs primarily in `tests/test_concept_emit.py`, `tests/test_shell.py`, and `tests/test_detail.py`, following the conventions documented by `TESTING.md`. Cross-module publication/CLI failure behavior remains in the prerequisite publication plan's test matrix.

In `tests/test_concept_emit.py`, exercise `_parse_emitted_concepts()` and enrichment for literal and invented title phrases sharing the same rationale excerpt; negated/critical mentions; punctuation and case normalization; repeated terms; nested candidates and rejected parents; duplicate siblings and duplicate keys; unknown fields including `suggested_state`; empty labels; bounds; mixed valid and invalid candidates; unpaired surrogates in titles, evidence spans, rationale, and parent paths; backend failures; and byte-for-byte input-tree immutability. In `tests/test_shell.py`, prove nonzero backend status cannot yield accepted JSON and the transport byte cap stops acquisition before unbounded stdout is accumulated.

In `tests/test_detail.py`, exercise `_author_step_detail()` with and without a concept record, resumed current-format checkpoints, invalidation/re-invocation of opaque pre-feature checkpoints, malformed envelopes, empty candidates, prose/candidate mismatch, and bounded reprompt exhaustion. Exercise `_archive_existing_detail()` and its replacement operation with injected failures at archive creation, move, new write, post-write validation, and restoration, asserting exact active and archived paths and bytes. Cover serial and parallel candidate collection, sibling preservation, multi-concept deduplication, bounded include regeneration, repeated contradiction, shared-record publication failure, and consumption of the prerequisite plan's prepared-worker outcome.

Run the focused suites, the full suite, prompt/data-contract drift checks, and `reconcile-code`; the plan does not invent existing test function or class identifiers beyond the implementation symbols above.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.

## Acceptance criteria

- An enriched concept title must be a normalized literal phrase from its cited evidence span, and that span must occur in supplied evidence; invented labels are rejected even when the rationale contains an unrelated literal excerpt, while negated or critical mentions remain valid provenance.
- The enrichment response has no `suggested_state`; candidates remain unsigned, and output that attempts to choose a state is rejected as an unknown field.
- Every invalid model-controlled Unicode value fails softly, and `tests/test_concept_emit.py` proves that the input tree remains byte-for-byte unchanged.
- A nonzero concept-backend result cannot be accepted even when stdout contains valid-looking JSON, and backend stdout is capped during acquisition rather than only after full capture.
- Fresh detail authoring through `_author_step_detail()` always requires the structured response envelope, independent of sidecar presence and job count, as verified in `tests/test_detail.py`.
- Opaque pre-feature detail checkpoints are invalidated and re-invoked; no legacy Markdown parser is selected from generic checkpoint schema version or sidecar absence.
- A failed detail replacement leaves the prior body active byte-for-byte; if restoration fails, the error is distinct and reports the recoverable archive location.
- Include-triggered regeneration is deduplicated and bounded and consumes the prepared-worker/publication contracts already shipped by `concept-remediation-1-publication-transactions` without reimplementing their write extraction or save path.
- Concept enrichment accepts a response atomically: one invalid candidate rejects the full enrichment attempt and preserves the input tree. Ordinary multi-step detail authoring may publish a successfully prepared subset when another sibling fails before publication; only an include-triggered regeneration cohort is all-or-restored. A recoverable publisher or backend-command failure preserves the applicable last-known-good bundle, while rollback failure reports every uncertain path without claiming preservation.
- Focused tests, the full suite, prompt/data-contract drift checks, and `reconcile-code` pass without an authoring-boundary finding.

## Deferred

- Publication transaction mechanics remain with `concept-remediation-1-publication-transactions` because that plan owns the canonical publication API.
- Coverage and lifecycle conservation remain with `concept-remediation-3-ownership-lifecycle-accounting` because they are separate ownership-accounting concerns.
