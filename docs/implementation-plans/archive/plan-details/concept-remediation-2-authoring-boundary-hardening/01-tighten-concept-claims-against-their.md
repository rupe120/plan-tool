# Step 1 — Tighten concept claims against their cited evidence

## Summary

This step makes concept enrichment accept only labels with literal provenance in their cited evidence span. It tightens parsing and merge validation in `plan_tool/concept_tree.py`, aligns the response contract in `plan_tool/prompts/concept-emit.md`, and adds bounded output acquisition through `plan_tool/shell.py:shell_concept_invoker`. The key rule is deliberately narrow: validation proves that the evidence mentions the normalized concept label, not that the evidence endorses or establishes it as true. On green, invented labels, malformed candidate fields, unsafe text, and oversized responses produce no enrichment, while valid negated or critical mentions remain usable.

## Table of Contents

- [Summary](#summary) — Overview of the grounding rule and affected surfaces.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — The gap between cited excerpts and supported concept labels.
- [Input](#input) — Contracts read by the parser and enrichment producer.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped files and their changes.
- [Implementation](#implementation) — Required validation, parsing, merge, and output-cap behavior.
- [Tests](#tests) — Unit coverage and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Primary specifications relevant to strict JSON and Unicode handling.
- [Deferred](#deferred) — Related hardening owned by later steps.

## Why

`plan_tool/concept_tree.py:_parse_emitted_concepts` currently proves only that `evidence_rationale` is copied from the supplied evidence; it can still accept an unrelated invented title. It also accepts fields such as `suggested_state` even though `plan_tool/concept_tree.py:emit_concept_tree` always creates unsigned candidates, and its structural limits do not yet cover unsafe text or total response size. Tightening this boundary matters because accepted titles become stable IDs and persisted concept sources later in the workflow. The correct deterministic guarantee is literal provenance: the cited span mentions the label after conservative normalization, without claiming that lexical matching can prove the label semantically true.

## Input

- **Existing concept record:** `plan_tool/concept_tree.py:ConceptTree` is the deterministic base. `plan_tool/concept_tree.py:emit_concept_tree` may return an enriched deep copy but must not mutate or persist the supplied tree.
- **Evidence envelope:** `plan_tool/concept_tree.py:render_concept_emit_prompt` supplies `evidence` and optional `plan_context`. Only `evidence` can support a candidate; `plan_context` remains orientation text.
- **Response shape:** accept one top-level `concepts` array. Each candidate contains required string fields `title` and `evidence_rationale`, plus optional recursive `children`; all other fields, including `id` and `suggested_state`, are invalid.
- **Existing hierarchy limits:** retain `plan_tool/concept_tree.py:CONCEPT_EMIT_MAX_DEPTH` at 3 and `plan_tool/concept_tree.py:CONCEPT_EMIT_MAX_BREADTH` at 12 items per collection.
- **Backend transport:** `plan_tool/shell.py:shell_concept_invoker` must continue routing through `plan_tool/shell.py:claude_invoke` so concept enrichment keeps backend selection, retries, prompt-budget handling, spawn-directory behavior, and the real-backend test guard.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — define the strict candidate contract, add the literal-provenance predicate and text/size bounds, reject unsafe hierarchy entries, and preserve unsigned fail-soft enrichment behavior.
  - `plan_tool/shell.py` — add bounded stdout acquisition for concept enrichment without changing uncapped callers of `claude_invoke`.
  - `plan_tool/prompts/concept-emit.md` — describe the exact response fields, omit `suggested_state`, and state the same title-to-span provenance rule enforced by code.
  - `tests/test_concept_emit.py` — replace permissive state tests and cover provenance, normalization, field rejection, bounds, hierarchy handling, Unicode, and merge results.
  - `tests/test_shell.py` — cover acquisition-time byte limiting and unchanged behavior for callers that do not request a limit.

## Implementation

The foundational logic is a **literal-provenance predicate: a normalized title phrase occurs in its normalized cited span, and that span occurs in the supplied evidence**.

- **Keep the claim narrow.** Treat `title` as a label for something the evidence mentions. Do not attempt to infer whether the evidence endorses, negates, warns about, or proves the label. For example, a label can be accepted from a span saying the feature is unsupported, provided the label itself occurs in that span.

- **Use one deterministic normalization rule.** Add a focused helper near `plan_tool/concept_tree.py:_parse_emitted_concepts` and use it for both containment checks. A suitable rule applies Unicode normalization, case folding, consistent punctuation-to-separator handling, and whitespace collapse. It must not stem words, reorder tokens, drop meaningful words, or accept a title based only on scattered token overlap.

- **Validate text before deriving hierarchy or IDs.** Every model-controlled string must:
  - be a non-empty string after normalization;
  - stay within named title and evidence-span limits;
  - encode as strict UTF-8;
  - contain no surrogate code points or control characters.

  The plan does not fix numeric title, span, decoded-response, or transport-byte ceilings. Choose named constants once, document their units, and test their exact boundaries. Prefer conservative limits sized for the existing depth-3, breadth-12 contract rather than inline numbers spread through the parser.

- **Require exact candidate fields.** In `plan_tool/concept_tree.py:_parse_emitted_concepts`, accept only `title`, `evidence_rationale`, and optional `children`. Reject `suggested_state`, `id`, review decisions, ownership metadata, and any other unknown field. Keep duplicate JSON-member rejection through `plan_tool/concept_tree.py:_reject_duplicate_keys`.

- **Validate provenance in two stages.**
  - The normalized `evidence_rationale` must occur in normalized supplied evidence.
  - The normalized `title` must occur as one contiguous whole-token phrase within that normalized span. Match token boundaries rather than substrings, so `art` does not ground against `partial`.
  - A title whose normalized tokens are all stop words is invalid even when that phrase occurs literally; mixed content retains stop words as ordinary interior tokens.

  This rejects an invented title even when the candidate cites a real but unrelated excerpt. Punctuation, case, and ordinary whitespace differences may normalize away; word order and phrase continuity may not.

- **Validate the candidate batch atomically.** A malformed top-level envelope, duplicate JSON key, or any candidate with bad fields, text, provenance, position, duplicate sibling identity, or unsafe hierarchy invalidates the complete response. The parser may collect candidate-indexed rejection reasons for diagnostics, but it must not return a surviving sibling subset. This gives step 2 one accepted batch or `None` and prevents descendants or sibling order from depending on partial rejection.

- **Keep merging unsigned and locally derived.** `plan_tool/concept_tree.py:emit_concept_tree` should continue deriving IDs through `plan_tool/concept_tree.py:concept_id`, copying the accepted evidence span into `ConceptNode.source`, and leaving `decision`, `rationale`, and `review_state` at their unsigned defaults. Existing concepts, especially reviewed ones, remain unchanged. If no candidate survives validation or all survivors already occupy their positions, return `None`.

- **Preserve the producer boundary.** `plan_tool/concept_tree.py:emit_concept_tree` remains an `Optional[ConceptTree]` producer: invalid or empty enrichment returns `None`, it never calls `plan_tool/concept_tree.py:save_concepts`, and callers retain sole ownership of persistence. No new persisted field or schema version is needed.

- **Cap raw stdout while reading it.** Extend the `plan_tool/shell.py:claude_invoke` path with an optional byte limit used only by `plan_tool/shell.py:shell_concept_invoker`. Enforce the limit as raw stdout is acquired, before the complete backend stream is held in memory. A limit breach must stop collection, terminate and reap the subprocess safely, and produce no truncated text that could be parsed as a valid response.

- **Keep uncapped shell behavior unchanged.** Calls to `plan_tool/shell.py:claude_invoke` without the optional limit must retain their current argv/stdin transport, retry behavior, stdout normalization, usage capture, sink events, and `(exit_code, stdout)` result. One likely approach is a bounded branch inside `plan_tool/shell.py:_run_once`; avoid a separate concept subprocess path that bypasses `claude_invoke`.

- **Retain a parser-side backstop.** Check decoded response size before `json.loads` in `plan_tool/concept_tree.py:_parse_emitted_concepts`. This is defense in depth for injected invokers and direct parser tests; it does not replace acquisition-time enforcement in `plan_tool/shell.py`.

- **Keep the prompt and validator identical in meaning.** Update `plan_tool/prompts/concept-emit.md` to show only the accepted fields, state that the title phrase must appear in the copied span, and retain the distinction between evidence and `PLAN CONTEXT`. The prompt can improve output quality, but `plan_tool/concept_tree.py:_parse_emitted_concepts` remains the authority.

The rejected alternative is meaningful-token overlap. It can accept reversed relationships or labels assembled from unrelated words and cannot distinguish support from negation. Contiguous normalized phrase provenance is stricter, deterministic, and matches the guarantee this step can honestly make.

## Tests

Add or update these cases in `tests/test_concept_emit.py`:

- `test_parse_requires_title_inside_cited_span` — a real evidence excerpt with an unrelated invented title is rejected.
- `test_parse_accepts_negated_literal_label` — a title literally mentioned in a negated or critical span remains valid provenance.
- `test_parse_normalizes_case_whitespace_and_punctuation` — documented normalization differences do not cause false rejection.
- `test_parse_does_not_match_reordered_or_scattered_terms` — token overlap without one contiguous normalized phrase is rejected.
- `test_parse_requires_span_inside_supplied_evidence` — a title cannot rescue an invented evidence span.
- `test_parse_rejects_suggested_state_and_other_unknown_fields` — `suggested_state`, `id`, and arbitrary fields violate the response contract.
- `test_parse_rejects_empty_and_whitespace_only_labels` — empty normalized titles do not reach ID derivation.
- `test_parse_rejects_surrogates_and_control_characters` — unsafe model-controlled text fails validation in titles and evidence spans.
- `test_parse_enforces_title_span_and_decoded_response_bounds` — each named limit accepts its boundary and rejects the first value beyond it.
- `test_parse_rejects_mixed_valid_and_invalid_candidate_batch` — one invalid candidate rejects the complete response; no independent sibling is returned.
- `test_parse_title_match_requires_token_boundaries` — substring-only overlap such as `art` in `partial` is rejected.
- `test_parse_rejects_stop_word_only_title` — an all-stop-word label cannot establish grounding by itself.
- `test_parse_drops_descendants_of_rejected_parent` — no child survives with an unaccepted parent path.
- `test_parse_rejects_duplicate_normalized_sibling_position` — equivalent sibling labels cannot create duplicate positional identities.
- `test_emit_returns_none_when_no_grounded_candidate_survives` — deterministic concepts remain the only usable tree when enrichment is empty.
- `test_emit_keeps_grounded_additions_unsigned` — accepted additions use local IDs and evidence sources without a scope decision.
- `test_render_concept_emit_prompt_matches_strict_contract` — the prompt requires title-in-span provenance and contains neither `suggested_state` nor `id`.

Add or update these cases in `tests/test_shell.py`:

- `test_concept_invoker_caps_stdout_during_acquisition` — the reader stops at the configured byte ceiling instead of accumulating the complete oversized stream.
- `test_concept_invoker_never_returns_a_truncated_valid_prefix` — a limit breach cannot turn a response prefix into accepted JSON.
- `test_bounded_invoke_terminates_and_reaps_process` — the oversized-output path leaves no live or waiting child process.
- `test_unbounded_invoke_keeps_existing_transport_contract` — callers without a byte limit retain current argv, normalized stdout, and result shape.
- `test_bounded_invoke_counts_encoded_bytes` — multibyte UTF-8 output is limited by bytes, not Python character count.

### Test-creation order (feature step)

1. Add the response-contract and title-provenance tests in `tests/test_concept_emit.py`, then implement the shared normalization and validation rule.
2. Add hierarchy, duplicate-position, unsafe-text, and parser-bound tests, then complete candidate filtering and merge behavior.
3. Add the acquisition-cap tests in `tests/test_shell.py`, then add the bounded `claude_invoke` path used by `shell_concept_invoker`.
4. Update prompt-contract assertions after `plan_tool/prompts/concept-emit.md` matches the validator.
5. Run `tests/test_concept_emit.py` and `tests/test_shell.py`, followed by the full suite.

Every new and updated test must be green before this step is finished.

## Acceptance criteria

- `plan_tool/concept_tree.py:_parse_emitted_concepts` accepts a candidate only when its normalized title is one contiguous phrase in its normalized `evidence_rationale`, and that span occurs in supplied evidence.
- A negated or critical evidence span can produce a concept whose label it literally mentions.
- An invented label is rejected even when `evidence_rationale` is a real excerpt.
- The accepted candidate shape contains `title`, `evidence_rationale`, and optional `children`; `suggested_state`, `id`, and all other unknown fields are rejected.
- Unsafe Unicode, control characters, empty normalized labels, oversized strings, excessive depth, excessive breadth, duplicate keys, and duplicate normalized sibling positions do not produce concept nodes.
- Any invalid candidate, including a rejected parent or descendant, rejects the complete enrichment batch; deterministic input concepts remain unchanged.
- Accepted additions have locally derived IDs, preserve the cited span in `ConceptNode.source`, and remain unreviewed with no decision or rationale.
- `plan_tool/concept_tree.py:emit_concept_tree` returns `None` when no candidate survives, does not mutate its input tree, and never persists.
- `plan_tool/shell.py:shell_concept_invoker` limits raw backend stdout during acquisition and never returns a truncated prefix after the limit is exceeded.
- `plan_tool/shell.py:claude_invoke` retains its existing behavior for callers that do not request an output limit.
- The focused `tests/test_concept_emit.py` and `tests/test_shell.py` suites and the full test suite pass.

## References

- [Claude API Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — Review refusal, truncation, and client-side validation requirements even when output shape is constrained.
- [JSON Schema Draft 2020-12 Validation](https://json-schema.org/draft/2020-12/json-schema-validation) — Use its object, array, string, required-field, and extra-field concepts when defining the strict response contract.
- [RFC 7493: The I-JSON Message Format](https://www.rfc-editor.org/rfc/rfc7493.html) — Follow its interoperable Unicode and unique-object-member restrictions at the untrusted JSON boundary.
- [Python `json` — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Review duplicate-name handling, Unicode behavior, decoding hooks, and the need to limit untrusted input size.

## Deferred

- Backend exit-status preservation — step 2 owns preventing valid-looking stdout from a nonzero backend result from being accepted.
- Full fail-soft coverage through normalization, ID derivation, copying, and merge — step 2 owns the complete non-mutating producer boundary and its exception classification.
- Detail response-envelope validation and replacement recovery — steps 3–6 own the separate detail-authoring boundary.
- Native provider-specific schema-constrained generation — this step retains the backend-neutral CLI path and enforces the response contract locally.
