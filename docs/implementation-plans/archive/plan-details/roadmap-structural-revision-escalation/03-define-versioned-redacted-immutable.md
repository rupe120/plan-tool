> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Define versioned, redacted immutable receipts for one selected artifact

## Summary

Add `plan_tool/roadmap_escalation.py` as the pure version-1 receipt contract and extend `plan_tool/roadmap_artifacts.py` with the selector-derived source-path fact it needs. The receipt has one closed, immutable JSON shape, a deterministic semantic id that is also its storage final name, and a strict redaction boundary. It consumes step 2’s accepted selection facts plus injected stage configuration; it does not read, write, publish, or inspect storage. When green, later steps can create and validate a stable receipt payload without trusting a stored source path or carrying reviewer content.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected modules.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why receipt facts need a strict persisted contract.
- [Input](#input) — Upstream selection and configured-stage facts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — New contract files and focused path tests.
- [Implementation](#implementation) — Receipt schema, identity, path binding, and redaction rules.
- [Tests](#tests) — Unit coverage for the schema and immutable identity contract.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for strict models, JSON, hashing, and fixtures.
- [Applicable guardrails](#applicable-guardrails) — Plan limits that bind this receipt contract.
- [Deferred](#deferred) — Storage, CLI, and impact work left to later steps.

## Why

Step 2 can prove that one selected feedback row is eligible for a structural receipt, but the codebase has no contract for the exact safe facts that may persist or how those facts identify one immutable record. `plan_tool/roadmap_artifacts.py:FeedbackRow.request` and artifact bodies contain reviewer content, while identifiers may be arbitrary strings, so a closed receipt format must prevent either from becoming stored evidence. A deterministic schema and source-path binding give later storage and view code one small trusted payload instead of asking each caller to rebuild identity, redaction, and path rules.

## Input

- **Step 2 selection outcome:** Consume only the accepted receipt-selection facts from `plan_tool/roadmap_escalation_selection.py`; do not re-run selection policy or copy feedback prose into the receipt contract.

- **Configured stage facts:** Accept the selected stage’s key and `artifact_path` fact through caller-supplied configuration shaped like `plan_tool/roadmap.py:RoadmapStage`. Keep the fixed `plan_tool/roadmap.py:STAGES` table outside this module.

- **Roadmap root:** Use `plan_tool/roadmap_artifacts.py:roadmap_dir` as the only base for the stored stage path. The receipt stores a derived relative string, never an input path that a later reader may follow.

- **Source evidence:** Consume step 2’s raw-byte SHA-256 digest and canonical selection result. Do not read the selected artifact again or retain its bytes, parsed body, rows, or feedback request.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_escalation.py` — Pure version-1 receipt construction, strict parsing, canonical rendering, semantic-id calculation, final-name validation, and redaction-safe value types.
  - `tests/test_roadmap_escalation.py` — Direct contract tests for receipt schema, identity, path binding, and rejected input.

- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py` — Add a pure helper beside `roadmap_dir` that derives one normalized POSIX stage path relative to the roadmap root.
  - `tests/test_roadmap_artifacts.py` — Cover the new relative-path helper, including equivalent `plans_dir` spellings and an artifact path outside the roadmap root.

## Implementation

- **Foundational logic:** Build and validate one closed, redacted version-1 receipt whose semantic id and storage final name are the same SHA-256 value.

- **Keep the receipt contract pure.** Make `plan_tool/roadmap_escalation.py` a construction, parse, render, and validation boundary. It must not open an artifact path, write a file, call a backend, emit telemetry, or invoke `plan_tool/roadmap_evidence_store.py:publish_evidence` or `plan_tool/roadmap_evidence_store.py:scan_evidence`.

- **Derive the source path from configuration.** Add a helper in `plan_tool/roadmap_artifacts.py` next to `roadmap_dir` that takes the resolved plans directory, roadmap slug, and selected configured stage path, then returns the path relative to that roadmap root as normalized POSIX. Reject a configured path outside the roadmap root rather than recording an absolute, dot-relative, or escaping path. Equivalent absolute, relative, and dot-normalized `plans_dir` inputs must produce the same receipt source path.

- **Keep stage configuration injected.** The receipt module may accept a caller-supplied stage key set and derived path fact, but must not import or modify `plan_tool/roadmap.py:STAGES`. The runner and view layers own selection of the configured stage; this contract owns validating the facts they pass.

- **Define one exact version-1 object.** Use strict, frozen Pydantic models or an equivalent immutable value design, following the closed-model configuration in `plan_tool/roadmap_revision.py:ReplaceRowPresentationOperation`. The root object has exactly `schema_version`, `selector`, `feedback_state`, `target`, `reason`, `source`, `handoff`, `semantic_id`, and `created_at`; each nested object is closed too.

- **Validate every field without coercion.**
  - `schema_version` is the JSON integer `1`, never a boolean, float, or string.
  - `selector` contains only receipt-safe `artifact_key` and `feedback_id`; the key must belong to the injected stage-key set and the feedback id must still satisfy step 1’s selector grammar.
  - `feedback_state` is exactly `open`.
  - `target` contains only `kind` and `id`; it permits only `artifact` or `row`, and an artifact target’s id must equal the selector artifact key.
  - `reason` accepts only step 2’s closed reason vocabulary.
  - `source` contains only `relative_stage_path` and `sha256`; the path is normalized relative POSIX and the digest is 64 lowercase hexadecimal characters.
  - `handoff` is exactly `requires-scope-review`.
  - `created_at` is a valid UTC RFC 3339 timestamp to whole seconds in `YYYY-MM-DDTHH:MM:SSZ` form.

- **Reject duplicate JSON members before model validation.** Parse receipt bytes with a duplicate-detecting object-pairs hook, modeled on `plan_tool/roadmap_revision.py:_decode_single_json_object` and `plan_tool/roadmap_revision.py:_reject_duplicate_keys`. Apply it at every object depth, reject non-finite constants and floating-point values, then pass the duplicate-free decoded data to the closed schema validator. Do not use a JSON-to-model shortcut that silently keeps the last duplicate key.

- **Make receipt values immutable.** Parsed and newly built receipts must expose frozen values so a caller cannot alter one nested selector, target, or source fact after semantic validation. Do not expose mutable mappings as receipt state.

- **Bind identity to the semantic preimage.** Construct canonical JSON from exactly the seven semantic fields: `schema_version`, `selector`, `feedback_state`, `target`, `reason`, `source`, and `handoff`. Sort object keys, use compact separators, preserve Unicode code points with `ensure_ascii=False`, and hash the UTF-8 bytes with SHA-256. These encoding choices match `plan_tool/checkpoint.py:compute_input_hash`, but this module must own the receipt-specific preimage and validation.

- **Exclude observational and derived fields from the preimage.** `semantic_id` and `created_at` do not affect the digest. Validate that the stored `semantic_id` equals the recomputed digest, and expose the identical lowercase hexadecimal value as the final name without an extension.

- **Make redaction structural.** Permit only the closed receipt fields above. Never accept, retain, render, or derive `FeedbackRow.request`, artifact body text, target-row prose, relation data, source-brief content, seed content, raw selector text, or arbitrary reason text. A valid receipt records the accepted closed reason and safe resolved identifiers only.

- **Preserve the limited handoff.** Every valid receipt carries `requires-scope-review`; do not add impact analysis, relation closure, route selection, or a structural patch recommendation.

## Tests

### Tests for this step

- `tests/test_roadmap_artifacts.py::test_stage_path_is_normalized_posix_relative_to_roadmap_root` — Derives the same source path from absolute, relative, and dot-normalized forms of one plans directory.

- `tests/test_roadmap_artifacts.py::test_stage_path_rejects_a_path_outside_the_roadmap_root` — Refuses a configured artifact path that cannot become a safe roadmap-root-relative receipt fact.

- `tests/test_roadmap_escalation.py::test_receipt_v1_round_trips_as_a_frozen_closed_value` — Builds, renders, parses, and compares a valid receipt while proving its nested values cannot be mutated.

- `tests/test_roadmap_escalation.py::test_receipt_json_rejects_duplicate_members_at_root_and_each_nested_object` — Rejects repeated names in the root, `selector`, `target`, and `source` before any last value can win.

- `tests/test_roadmap_escalation.py::test_receipt_rejects_missing_unknown_wrong_typed_and_float_values` — Rejects omitted fields, extra fields, nulls, coercible alternatives, booleans for `schema_version`, and every floating-point representation.

- `tests/test_roadmap_escalation.py::test_receipt_rejects_unsupported_version_invalid_timestamp_and_bad_digest` — Enforces schema version 1, whole-second UTC timestamps, and lowercase SHA-256 source digests.

- `tests/test_roadmap_escalation.py::test_receipt_requires_configured_safe_selector_and_target_facts` — Requires an injected stage key, step 1-compatible feedback id, receipt-safe identifiers, and the artifact-target-id-equals-selector-key rule.

- `tests/test_roadmap_escalation.py::test_receipt_source_path_rejects_absolute_dot_and_escaping_forms` — Refuses stored source paths outside the normalized POSIX receipt representation.

- `tests/test_roadmap_escalation.py::test_semantic_id_uses_exact_canonical_preimage_and_unescaped_unicode` — Pins sorted compact canonical JSON, UTF-8 hashing, and unescaped Unicode output across the seven included fields.

- `tests/test_roadmap_escalation.py::test_semantic_id_excludes_created_at_and_is_the_final_name` — Proves changing only creation time leaves the semantic id unchanged and the final name equals that id exactly.

- `tests/test_roadmap_escalation.py::test_receipt_rejects_a_semantic_id_that_does_not_match_its_preimage` — Rejects a self-consistent-looking schema whose stored identity differs from the recomputed digest.

- `tests/test_roadmap_escalation.py::test_rendered_receipt_contains_only_redacted_schema_fields` — Proves valid receipt bytes contain safe resolved facts and exclude supplied reviewer request, artifact prose, relation data, and raw input text.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap_artifacts.py` derives one normalized POSIX stage path relative to `roadmap_dir` and rejects a selected stage path outside that root.

- `plan_tool/roadmap_escalation.py` builds and parses an immutable receipt with exactly the version-1 root and nested fields.

- Duplicate JSON members, unknown fields, omitted fields, alternate types, floating-point values, unsupported versions, malformed timestamps, invalid selector or target facts, and invalid source paths are rejected.

- The recomputed semantic id is the lowercase SHA-256 digest of canonical JSON over exactly the seven semantic fields; `semantic_id` and `created_at` are excluded.

- A receipt’s final name equals its validated semantic id without an extension.

- Valid receipt bytes contain only receipt-safe routing identifiers, the closed reason, source digest and path, and the fixed handoff; they contain no reviewer or artifact content.

- `tests/test_roadmap_artifacts.py` and `tests/test_roadmap_escalation.py` pass.

## References

- [Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/) — Use strict, frozen, extra-forbidden models for the closed receipt schema.

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use for duplicate-aware decoding and canonical semantic-preimage serialization.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Use for SHA-256 source and semantic identity binding.

- [pytest: How to use temporary directories and files](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — Use for isolated roadmap-root-relative path fixtures.

## Applicable guardrails

- **The plan’s “## Step intent”, receipt identity:** Bind one version-1 receipt to selector-derived facts only; do not add broader scope or route decisions.

- **The plan’s “## Plan intent”, receipt-only record:** Keep this step limited to evidence representation and validation, with no artifact, feedback, seed, or Git mutation.

- **The plan’s “## Out of scope”, immutable-evidence storage:** Do not implement publication, namespace handling, enumeration, durability, or temporary-file cleanup.

- **The plan’s “## Out of scope”, local revision compatibility:** Do not change `plan_tool/roadmap_revision.py:preflight_feedback_revision` or its local write policy.

- **The plan’s “## Out of scope”, identifier grammar:** Apply receipt-safe validation only at this persisted receipt boundary; do not narrow roadmap artifact parsing or the shared local-revision selector contract.

- **The plan’s “## Out of scope”, impact analysis:** Do not inspect another roadmap artifact or infer a relation closure from the selected target or reason.

## Deferred

- Immutable publication and lifecycle mapping — Step 4 consumes this schema through `plan_tool/roadmap_evidence_store.py:publish_evidence` and `plan_tool/roadmap_evidence_store.py:scan_evidence`; this step neither calls nor changes them.

- CLI creation, receipt views, telemetry, and process status — Later steps own `plan_tool/cli/roadmap_cmd.py` and `plan_tool/run_log.py` integration.

- Cross-artifact impact analysis and structural revision — The receipt ends at `requires-scope-review`; later work decides whether any broader action is safe.

- Shared JSON and hash helper consolidation — `plan_tool/roadmap_revision.py:_reject_duplicate_keys`, `plan_tool/concept_tree.py:_reject_duplicate_keys`, and `plan_tool/checkpoint.py:compute_input_hash` serve different contracts and error types. Consolidating them requires a separately scoped refactor.
