> **Replaced**: this file has been superseded by `docs/implementation-plans/2-concept-authoring-boundary-hardening.md`.
> Preserved here for history; do not edit.

## Overview

Harden the two model-authored boundaries in the concept workflow so untrusted output either becomes a validated, recoverably published artifact or causes no artifact change. Concept enrichment accepts only claims grounded in supplied evidence and fails softly for all invalid model output, while fresh detail generation always requires the structured response envelope and preserves the prior body if replacement fails. Deferral persistence must consume the public publication contract from `concept-publication-transactions`; this plan owns validation, parsing, bounded regeneration, and local detail replacement, but not multi-artifact concept publication, coverage policy, or structural ownership transformations.

## Problem statement

The completed integration validates response shape without consistently validating meaning or preserving artifacts. `_parse_emitted_concepts()` accepts an unrelated title when `evidence_rationale` merely contains a literal excerpt, and an unpaired surrogate can pass parsing before ID derivation raises `UnicodeEncodeError` outside the fail-soft boundary. `_author_step_detail()` permits legacy Markdown when no concept tree is loaded, and `_archive_existing_detail()` removes the active detail before the replacement is known to be safe. The serial/concurrent regeneration contract also lacks coverage for sibling preservation, deduplication, bounded retries, persistence failure, dry-run, and command failure.

The reconciliation evidence is recorded in `docs/implementation-plans/plan-details/concept-signoff-integrations/convergence-evidence-and-split-recommendation.md`: `step2-run-reconcile-ce244a8e`, `step2-run-reconcile-84957c73`, `step4-run-reconcile-8ae6c687`, `step4-run-reconcile-04ac0dba`, `step4-run-reconcile-28491d51`, and `step4-run-reconcile-a6c41ba8`. The publication API gap identified by `step4-run-reconcile-5830b0ac` belongs to `concept-publication-transactions`, so closing it with another local schema or direct save would violate the intended ownership boundary.

## Architecture

Concept enrichment uses a conservative, deterministic grounding rule shared by `plan_tool/prompts/concept-emit.md` and `plan_tool/concept_tree.py`. A response must provide a bounded evidence span and a claim/title whose normalized meaningful tokens are demonstrably present in or tied to that span; candidates are rejected when lexical validation cannot establish support. Parsing also bounds title, rationale/span, hierarchy depth, breadth, and total output size and rejects duplicate keys, unknown fields, invalid suggested states, empty or whitespace-only claims, control characters, invalid Unicode, and unsafe hierarchy outcomes. If every enriched candidate is rejected, deterministic concepts remain.

The fail-soft producer boundary begins before backend invocation and extends through normalization, encoding, ID/source-key derivation, candidate construction, and merge into a deep copy. Backend-output failures return the documented no-enrichment result without changing the input tree, while programmer and filesystem errors outside that narrow untrusted-output path remain visible.

Every fresh response handled by `plan_tool/detail.py` follows the structured protocol defined by `plan_tool/prompts/detail.md`, regardless of sidecar presence, serial or parallel execution, resume, or reprompt. The envelope separates the detail body from structured deferral candidates and permits prose/candidate parity validation. Any legacy parsing retained must be selected through explicit checkpoint version/provenance; absence of a sidecar cannot enable it, and malformed fresh output exhausts the bounded reprompt policy without replacing an artifact.

Detail replacement is a recoverable local operation. The new body is rendered and validated before the old file moves, and a journal records the old active path and archive destination. Failure during the new write or post-write validation restores the prior active bytes; restoration failure produces a distinct error containing the recoverable archive path. The canonical active filename used by plan pointers and downstream tools remains unchanged.

Include-triggered regeneration is deduplicated by affected step and bounded. Workers return bodies and candidates without mutating shared concept state; the serial parent validates all required bodies, merges candidates, and publishes through the public authority supplied by `concept-publication-transactions`. Contradictory output stops with an actionable unresolved-candidate report and retains the last known-good artifacts. Relevant implementation locations are `plan_tool/concept_tree.py`, `plan_tool/detail.py`, `plan_tool/cli/authoring.py`, and checkpoint metadata if explicit legacy recognition is required.

## Out of scope

- Create collision transactions, sidecar-only resume, manifest recovery, and scope-out publication are excluded because they are separate publication concerns.
- Defining or implementing the canonical concept publisher is excluded; this plan consumes the public contract from `concept-publication-transactions`.
- `wont_do` completeness semantics and structural deferral-link remapping are excluded as ownership and lifecycle concerns.
- A second model call to judge whether the first model's claim is grounded is excluded in favor of deterministic validation.
- Rewriting old detail files solely to add envelopes is excluded; compatibility, if retained, is provenance-gated.
- General-purpose filesystem transactions are excluded beyond detail artifact replacement.

## Risks

- Grounding can be too strict and reject useful enrichment. The control is to prefer false negatives because deterministic seeds remain, document normalization, and test real evidence phrases.
- Grounding can be too permissive through weak overlap such as stop words. The control is to require a claim-to-span relationship rather than any shared stop word or literal rationale.
- Compatibility fallback can reopen permissive parsing. The control is to gate legacy parsing on explicit persisted provenance and never on sidecar absence.
- A broad fail-soft catch can hide programmer defects. The control is to catch only errors attributable to invocation or model-output processing and verify that unrelated errors surface.
- Regeneration can loop on contradictory output. The control is to cap attempts, deduplicate by step, report unresolved candidates, and retain known-good artifacts on exhaustion.
- Parallel workers can race while updating shared concept state. The control is for workers to return immutable outcomes while only the serial parent merges and publishes.
- Detail restoration can itself fail. The operation must surface a distinct error and retain the recoverable archive path rather than describing archival as successful recovery.

## Testing

Unit coverage belongs primarily in `tests/test_concept_emit.py` and `tests/test_detail.py`; cross-module CLI behavior belongs in `tests/cli/test_authoring_cmds.py`, following the conventions documented by `TESTING.md`.

In `tests/test_concept_emit.py`, exercise `_parse_emitted_concepts()` and enrichment for grounded and ungrounded titles sharing the same rationale excerpt; stop-word-only overlap; punctuation and case normalization; repeated terms; nested candidates and rejected parents; duplicate siblings and duplicate keys; unknown fields; invalid suggested states; empty claims; bounds; mixed valid and invalid candidates; unpaired surrogates in titles, evidence spans, rationale, and parent paths; backend failures; and byte-for-byte input-tree immutability.

In `tests/test_detail.py`, exercise `_author_step_detail()` with and without a concept record, resumed fresh-format checkpoints, explicitly recognized legacy checkpoints, malformed envelopes, empty candidates, prose/candidate mismatch, and bounded reprompt exhaustion. Exercise `_archive_existing_detail()` and its replacement operation with injected failures at archive creation, move, new write, post-write validation, and restoration, asserting exact active and archived paths and bytes. Cover serial and parallel candidate collection, sibling preservation, multi-concept deduplication, bounded include regeneration, repeated contradiction, shared-record publication failure, and the rule that workers never persist shared concept state.

In `tests/cli/test_authoring_cmds.py`, cover dry-run and command-failure concept-state behavior, including the case where a failed sibling must not allow successful siblings to publish inconsistent shared state. Run the focused suites, the full suite, prompt/data-contract drift checks, and `reconcile-code`; the seed does not name existing test function or class identifiers beyond the implementation symbols above.

Per-step test strategy: contract tightening, fail-soft handling, structured detail parsing, recoverable replacement, and regeneration/CLI behavior are implemented with their focused tests; any refactoring needed to expose these seams receives characterization coverage first; checkpoint metadata or documentation-only changes receive artifact-appropriate validation.

## Acceptance criteria

- A concept title or claim unsupported by its cited evidence span is rejected even when its rationale contains a literal excerpt, as verified through `_parse_emitted_concepts()` coverage in `tests/test_concept_emit.py`.
- Every invalid model-controlled Unicode value fails softly, and `tests/test_concept_emit.py` proves that the input tree remains byte-for-byte unchanged.
- Fresh detail authoring through `_author_step_detail()` always requires the structured response envelope, independent of sidecar presence and job count, as verified in `tests/test_detail.py`.
- If legacy parsing is retained, `tests/test_detail.py` proves that it is reachable only through explicit persisted provenance and cannot accept malformed fresh output.
- A failed detail replacement leaves the prior body active byte-for-byte; if restoration fails, the error is distinct and reports the recoverable archive location.
- Include-triggered regeneration is deduplicated and bounded, and tests prove workers never write shared concept state.
- Deferral persistence calls the publication contract from `concept-publication-transactions` and does not introduce a local schema or direct save path.
- Concurrent sibling candidates are preserved, while publisher failure or a failed sibling causes no inconsistent shared-state publication.
- Dry-run and CLI command failures leave concept state unchanged, as verified in `tests/cli/test_authoring_cmds.py`.
- Focused tests, the full suite, prompt/data-contract drift checks, and `reconcile-code` pass without an authoring-boundary finding.

## Deferred

- Publication transaction mechanics remain with `concept-publication-transactions` because that plan owns the canonical publication API.
- Coverage and lifecycle conservation remain with `concept-ownership-lifecycle-accounting` because they are separate ownership-accounting concerns.
