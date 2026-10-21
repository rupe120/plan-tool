# Step 2 — Make invalid concept output leave the input tree unchanged

## Summary

This step makes `plan_tool/concept_tree.py:emit_concept_tree` a fail-soft boundary for invalid concept output while preserving the caller’s `ConceptTree` unchanged. It updates `plan_tool/shell.py:shell_concept_invoker` so a failed backend cannot pass valid-looking stdout to the concept parser. Candidate construction and merging happen only on copied state, and accepted enrichment returns a separate tree without saving it. On green, malformed output, invalid Unicode, and backend failure all return `None`, while unrelated programming errors remain visible.

## Table of Contents

- [Summary](#summary) — Overview of the boundary and its observable result.
- [Why](#why) — The remaining mutation and backend-status risks.
- [Input](#input) — Contracts this step receives from step 1 and existing APIs.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped source and test changes.
- [Implementation](#implementation) — Required failure, copying, and exception behavior.
- [Tests](#tests) — Unit coverage and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — Behaviors reviewers and CI can verify.
- [References](#references) — Primary validation and JSON references.
- [Deferred](#deferred) — Related work intentionally left outside this step.

## Why

`plan_tool/concept_tree.py:emit_concept_tree` already returns `None` for common parse failures, builds additions on a deep copy, and leaves persistence to `save_concepts`, so this step is partly present. Two gaps remain: output-derived failures such as an unpaired surrogate can escape later from `concept_id`, and `plan_tool/shell.py:shell_concept_invoker` discards the exit code from `claude_invoke`, allowing valid-looking stdout from a failed backend to be parsed as success. The boundary must reject both cases without changing deterministic or reviewed concepts, while avoiding a broad catch that hides unrelated defects.

## Input

- **Step 1 output contract:** Step 1 supplies the strict, bounded concept-response validation used by `plan_tool/concept_tree.py:_parse_emitted_concepts`. This step consumes its accepted-versus-rejected result and does not redefine grounding, field, depth, breadth, or output-size rules.
- **Concept tree contract:** `plan_tool/concept_tree.py:ConceptTree` and `ConceptNode` are caller-owned input records. Existing nodes, their order, review fields, and `source_metadata` must remain unchanged on every failure.
- **Invocation contract:** `plan_tool/shell.py:claude_invoke` returns `(exit_code, stdout)`, including nonzero status with partial stdout and exit 127 when the executable is unavailable.
- **Caller contract:** `plan_tool/create.py:create_plan` already treats `emit_concept_tree(...) is None` as no enrichment and keeps the deterministic tree. Its `concept_invoker: Callable[[str], str]` seam should remain compatible without editing `plan_tool/create.py`.
- **Persistence contract:** `plan_tool/concept_tree.py:save_concepts` remains the only persistence operation. `emit_concept_tree` must not call it or otherwise write files.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — narrow the fail-soft boundary in `emit_concept_tree`, keep all candidate work off the input tree, and handle the dedicated concept invocation failure.
  - `plan_tool/shell.py` — preserve failure status in `shell_concept_invoker` through a concept-specific exception while keeping successful calls stdout-only.
  - `tests/test_concept_emit.py` — add invalid-Unicode, backend-failure, immutability, successful-copy, and unexpected-error coverage.
  - `tests/test_shell.py` — pin the success and nonzero contracts of `shell_concept_invoker`, including valid-looking stdout on failure.

## Implementation

The foundational logic is a **fail-soft, copy-before-merge concept enrichment boundary with backend-status preservation**.

- **Keep the public producer shape.** `plan_tool/concept_tree.py:emit_concept_tree` should continue accepting an injected `Callable[[str], str]` and returning `Optional[ConceptTree]`. Valid enrichment returns a separate candidate; rejected model output or a known concept-invocation failure returns `None`.

- **Preserve backend status at the adapter.** Change `plan_tool/shell.py:shell_concept_invoker` to inspect both values returned by `claude_invoke`. On exit zero, return stdout as today. On any nonzero status, including `EXEC_NOT_FOUND_EXIT`, raise a dedicated exception such as `ConceptInvocationError` before stdout can reach `_parse_emitted_concepts`. Carry the exit code for diagnostics, but never expose failed stdout as a successful concept response.

- **Keep the exception concept-specific.** Do not change `plan_tool/shell.py:claude_invoke` or the behavior of unrelated stdout-only adapters such as `plan_tool/create.py:shell_claude_invoker` and `plan_tool/detail.py:shell_detail_invoker`. Their callers have separate fallback contracts.

- **Catch only expected boundary failures.** `plan_tool/concept_tree.py:emit_concept_tree` should translate `ConceptInvocationError` and failures proven to come from untrusted concept values into `None`. Remove the current broad `except Exception` behavior. An unexpected exception from an injected invoker, prompt-file read, copy operation, or merge implementation should remain visible rather than being mislabeled as invalid model output.

- **Reject unsafe output before publication.** Step 1 should normally reject invalid Unicode during parsing, but this step must keep a defensive path around normalization, UTF-8 encoding in `concept_id`, nested parent-path derivation, node construction, and final candidate validation. One workable approach is to convert failures at those output-only operations into one internal rejection result, avoiding a broad catch around the whole function.

- **Never mutate the input.** Treat the passed `ConceptTree` as read-only. Build new `ConceptNode` objects and run `plan_tool/concept_bootstrap.py:rederive_concepts` against copied candidate state. Preserve the existing post-merge rule that replaces every pre-existing node with a deep copy of its original record, so reviewed decisions and metadata cannot be rewritten by enrichment bookkeeping.

- **Return no partial candidate.** If any candidate in an otherwise mixed response is invalid, return `None` for the complete enrichment attempt. Do not return earlier additions, reorder existing nodes, or partially merge the accepted subset.

- **Keep persistence caller-owned.** `emit_concept_tree` must never call `save_concepts`, `write_concepts`, or filesystem helpers. `plan_tool/create.py:create_plan` remains responsible for choosing `enriched or fresh_concepts` and later publishing through its owning workflow.

- **Preserve success behavior.** Valid output still adds unsigned concepts with tool-derived IDs, deterministic order, and unchanged existing records. The returned tree must not share mutable newly copied records with the caller’s tree.

## Tests

- `test_emit_invalid_unicode_returns_none_and_preserves_input` — parameterizes unpaired surrogates in a title, cited span or rationale, and a nested title that becomes a parent-path component.
- `test_emit_backend_failure_with_valid_json_returns_none_and_preserves_input` — proves a dedicated invocation failure cannot be parsed even when its stdout looks valid.
- `test_emit_mixed_valid_and_invalid_output_returns_no_partial_candidate` — proves one invalid candidate rejects the whole response and leaves the input unchanged.
- `test_emit_success_returns_new_tree_without_mutating_input` — proves valid enrichment returns a distinct tree while the original serialized state and existing node records stay unchanged.
- `test_emit_unexpected_invoker_error_propagates` — proves unrelated programming errors are not hidden by the fail-soft boundary.
- `test_emit_failure_does_not_persist` — proves every rejected path leaves the concept sidecar absent or unchanged.
- `test_shell_concept_invoker_returns_stdout_on_zero` — proves successful status retains the existing string-return contract.
- `test_shell_concept_invoker_raises_on_nonzero_with_valid_stdout` — proves nonzero status is preserved and stdout cannot masquerade as success.
- `test_shell_concept_invoker_raises_when_backend_is_missing` — proves exit 127 follows the same concept-specific failure path.

### Test-creation order (feature step)

1. Add the `plan_tool/shell.py:shell_concept_invoker` success and nonzero-status tests in `tests/test_shell.py`.
2. Add backend-failure and invalid-Unicode immutability tests in `tests/test_concept_emit.py`.
3. Add whole-response rejection and successful-copy tests.
4. Add the unexpected-error test to guard the narrow exception boundary.
5. Keep the existing deterministic ordering, reviewed-decision preservation, no-persistence, and injected-invoker tests green.

Every new test and the existing focused suites `tests/test_concept_emit.py` and `tests/test_shell.py` must be green before this step is finished.

## Acceptance criteria

- `plan_tool/shell.py:shell_concept_invoker` returns stdout only when `claude_invoke` returns exit code zero.
- A nonzero concept invocation raises a concept-specific failure before its stdout reaches `_parse_emitted_concepts`.
- `emit_concept_tree` returns `None` for known invocation failures and invalid model-controlled Unicode.
- Every rejected response leaves the input `ConceptTree`, its nested nodes, ordering, decisions, rationale, and metadata unchanged.
- A response containing both valid and invalid candidates produces no partial enrichment.
- Valid enrichment returns a distinct `ConceptTree` and leaves the input tree unchanged.
- `emit_concept_tree` performs no filesystem writes on success or failure.
- Unexpected programming and prompt-file errors remain visible to the caller.
- `tests/test_concept_emit.py` and `tests/test_shell.py` pass.

## References

- [Claude API Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — Review refusal, truncation, and client-side validation requirements for responses that do not satisfy the expected contract.
- [RFC 7493: The I-JSON Message Format](https://www.rfc-editor.org/rfc/rfc7493.html) — Use its Unicode and interoperability restrictions to define unsafe JSON string values.
- [Python json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Review Python’s handling of malformed input, duplicate names, non-finite values, and Unicode edge cases.

## Deferred

- Step 1 response validation and output acquisition limits — owned by step 1; this step consumes its accepted-or-rejected result.
- Other stdout-only backend adapters — `plan_tool/create.py:shell_claude_invoker` and `plan_tool/detail.py:shell_detail_invoker` have separate caller contracts and are not concept enrichment boundaries.
- Concept persistence and multi-artifact publication — remain with `save_concepts` and the concept publication plan; this producer stays write-free.
- Detail response and replacement failures — owned by steps 3–6 of this plan.
