# Step 3 — Tighten detail envelope and deferral validation

## Summary

Harden `plan_tool/detail.py:parse_structured_detail_response` so the detail envelope is treated as bounded, untrusted JSON and accepted only when its deferrals match the Markdown and reviewed concept state. Keep `plan_tool/detail.py:parse_detail_response` responsible for the existing Markdown section rules while the structured parser owns envelope shape, identity, ordering, and semantic checks. Extend `tests/test_detail.py:TestParseStructuredDetailResponse` with malformed JSON, invalid identifiers, duplicate data, bounds, Unicode, ordering, and prose-parity cases. On green, invalid envelopes return `None` through the existing retry path and cannot become publishable detail results.

## Table of Contents

- [Summary](#summary) — The parser-hardening outcome and affected files.
- [Why](#why) — Why the current checks leave malformed or contradictory envelopes acceptable.
- [Input](#input) — The response, plan, step, and concept-tree contracts being validated.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two existing files changed by this step.
- [Implementation](#implementation) — The required envelope and deferral validation rules.
- [Tests](#tests) — Focused parser cases for valid and hostile responses.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary specifications for strict JSON validation.
- [Deferred](#deferred) — Fresh-response routing and publication work owned by later steps.

## Why

`plan_tool/detail.py:parse_structured_detail_response` already separates Markdown from a transport envelope and checks basic field shape, duplicate deferral pairs, reviewed state, ownership, and IDs mentioned under `## Deferred`. It remains only partially hardened: `json.loads` silently accepts duplicate object names, context-free parsing does not enforce the stable concept-ID format, the deferral array is not bounded, and set-based prose parity hides repeated IDs and ignores required concept ordering. Tightening this boundary now gives later authoring changes one strict parser whose `None` result safely enters the existing bounded retry and failure flow.

## Input

- **Structured response grammar:** `plan_tool/detail.py:_DETAIL_DEFERRALS_RE` separates the trailing `plan-tool-detail-deferrals` comment from the Markdown body. The envelope must contain exactly one `deferrals` member whose value is an array of objects containing exactly `concept_id` and `step_id`.
- **Markdown grammar:** `plan_tool/detail.py:parse_detail_response` and `plan_tool/detail.py:parse_detail_file_sections` define the accepted body and expose the optional `## Deferred` section. This step must not weaken their required-heading behavior or write the transport comment into the returned body.
- **Deferral identity:** `plan_tool/schema.py:Step` ownership links and the concept records supplied to `plan_tool/detail.py:parse_structured_detail_response` use lowercase 64-character SHA-256 hexadecimal IDs. Titles and prose are not substitutes.
- **Reviewed concept state:** semantic validation reads `plan_tool/concept_tree.py:ConceptTree.concepts` together with the supplied `Plan` and `Step`. An accepted deferral must name an existing approved concept whose decision is `defer`, and it must not belong only to another step.
- **Caller contract:** callers treat `None` from `plan_tool/detail.py:parse_structured_detail_response` as an unparseable response. Keep this fail-soft return contract; malformed model data must not raise into authoring orchestration.

## Files (creates vs edits)

- **New files:**

  - None.

- **Existing files (edits only):**

  - `plan_tool/detail.py` — strengthen `parse_structured_detail_response`, its JSON decoding boundary, deferral bounds, identifier validation, reviewed-state checks, concept ordering, and Markdown-to-envelope parity.
  - `tests/test_detail.py` — expand `TestParseStructuredDetailResponse` and its response fixtures to cover every accepted and rejected envelope class.

## Implementation

- **Use one strict validation boundary.** Make `plan_tool/detail.py:parse_structured_detail_response` the foundational logic for deciding whether a Markdown body and deferral envelope form one publishable result. Keep `plan_tool/detail.py:parse_detail_response` as the Markdown validator instead of duplicating its heading rules.

- **Reject ambiguous JSON.** Decode the envelope with duplicate-member detection at every object level. A repeated `deferrals`, `concept_id`, or `step_id` key must return `None`; Python’s default last-value-wins behavior is not acceptable for an authoring decision.

- **Keep the envelope exact.** Require one top-level object with only `deferrals`, an array value, and entries containing only `concept_id` and `step_id`. Reject alternate containers, unknown members, missing members, booleans used as integers, and non-integral step IDs.

- **Validate stable identifiers before context lookup.** Require every `concept_id` to match lowercase `[0-9a-f]{64}` even when no `ConceptTree` is supplied. Reject uppercase, short, long, whitespace-padded, non-hex, control-character, and malformed-Unicode values instead of relying on a later dictionary miss.

- **Bound the deferral list.** Add a named, documented maximum in `plan_tool/detail.py` and reject an envelope above it before building `DetailDeferral` records. Choose a limit large enough for a real step’s reviewed concepts but small enough to prevent an untrusted response from creating an unbounded candidate list; when a concept tree is available, also reject a count that exceeds the concepts eligible for this step.

- **Reject invalid Unicode safely.** Verify model-controlled response text can be encoded as UTF-8 without surrogate code points. Encoding or JSON-decoding failures must return `None`, matching the parser’s fail-soft contract rather than raising `UnicodeEncodeError`.

- **Preserve complete semantic context.** Keep the existing all-or-none rule for `step`, `plan`, and `concept_tree`. With all three supplied, require each deferral’s `step_id` to equal `step.id`, require the concept to exist with `review_state == "approved"` and `decision == "defer"`, and reject a concept owned only by another step. Do not infer an ID or owner from a title.

- **Enforce one deferral per concept.** Reject repeated concept IDs, not only repeated `(step_id, concept_id)` pairs. A response is scoped to one step, so allowing the same concept under another step ID would only hide an invalid step association.

- **Enforce concept order.** Return deferrals in the reviewed concept order exposed by `ConceptTree.concepts`, and reject an envelope that reorders the signed-off concepts contrary to the prompt contract. Do not sort by hash or title because both would lose the operator-reviewed order.

- **Require exact prose parity.** Read stable IDs from the body’s `## Deferred` section through `plan_tool/detail.py:parse_detail_file_sections`. Each envelope concept must appear exactly once in that section, every stable concept ID in the section must appear exactly once in the envelope, and an empty envelope must pair with no stable concept IDs in the section. Use count-aware comparison rather than sets so repeated prose IDs cannot pass.

- **Preserve free-form deferrals.** Allow `## Deferred` to contain follow-up prose with no stable concept ID. Reject only invented stable-looking IDs or mismatches with the structured candidates; do not try to turn arbitrary prose into a concept.

- **Keep the returned artifact clean.** `ParsedDetailResponse.body` must contain only the validated Markdown, while `ParsedDetailResponse.deferrals` contains the ordered immutable records. Never retain the transport comment in the body.

- **Keep invalid data fail-soft.** Catch only decoding, encoding, and validation failures attributable to the untrusted response and return `None`. Do not add persistence or mutate `Plan`, `Step`, or `ConceptTree` inside the parser.

- **Preserve detail backend status.** Change `plan_tool/detail.py:shell_detail_invoker` to inspect the exit code returned by `claude_invoke` and raise a dedicated detail-invocation error on any nonzero result before stdout reaches structured parsing. A failed backend’s valid-looking envelope is not authoring success. `_author_step_detail` maps that dedicated error into the existing bounded attempt/failure result without publishing artifacts.

- **Make malformed-Unicode failure logging fail-soft.** `_log_parse_failure`, raw-byte accounting, and diagnostic persistence must use surrogate-safe escaped or replacement diagnostics, or catch encoding failures attributable to model output. An unpaired surrogate must reach the normal retry/exhaustion result; logging must not raise while trying to describe it.

## Tests

Tests in `tests/test_detail.py`:

- `test_parse_structured_detail_response_accepts_valid_ordered_deferrals` — valid Markdown and ordered reviewed deferrals produce a clean body and ordered `DetailDeferral` tuple.
- `test_parse_structured_detail_response_accepts_explicit_empty_deferrals` — an empty array paired with no stable ID in `## Deferred` succeeds.
- `test_parse_structured_detail_response_rejects_duplicate_json_keys` — duplicate top-level and nested member names return `None`.
- `test_parse_structured_detail_response_rejects_unknown_or_missing_fields` — extra and missing members at either object level return `None`.
- `test_parse_structured_detail_response_rejects_invalid_concept_id_shapes` — uppercase, non-hex, short, long, padded, and control-bearing IDs return `None`.
- `test_parse_structured_detail_response_rejects_unpaired_surrogate` — malformed Unicode in the response returns `None` without raising.
- `test_parse_structured_detail_response_rejects_boolean_and_invalid_step_ids` — booleans, strings, non-positive values, and the wrong current step ID are rejected.
- `test_parse_structured_detail_response_rejects_deferral_limit_overflow` — an array above the named maximum returns `None`.
- `test_parse_structured_detail_response_rejects_duplicate_concept` — the same concept cannot appear more than once in one response.
- `test_parse_structured_detail_response_rejects_unreviewed_or_non_deferred_concept` — missing, unsigned, included, and otherwise ineligible concepts return `None`.
- `test_parse_structured_detail_response_rejects_concept_owned_only_by_other_step` — another step’s concept cannot be deferred by the current step.
- `test_parse_structured_detail_response_rejects_out_of_order_concepts` — envelope order must match reviewed concept order.
- `test_parse_structured_detail_response_requires_exact_deferred_parity` — missing, extra, invented, or repeated stable IDs in `## Deferred` return `None`.
- `test_parse_structured_detail_response_allows_free_form_deferred_prose` — prose without a stable concept ID remains valid with an empty or otherwise matching envelope.
- `test_parse_structured_detail_response_strips_transport_envelope` — the parsed body contains no `plan-tool-detail-deferrals` marker or JSON payload.
- `test_parse_structured_detail_response_requires_complete_semantic_context` — supplying only part of the `step`/`plan`/`concept_tree` group returns `None`.
- `test_shell_detail_invoker_rejects_nonzero_status_with_valid_envelope` — failed backend stdout cannot enter structured parsing.
- `test_detail_parse_failure_logging_handles_unpaired_surrogate` — diagnostic logging does not raise and the attempt reaches bounded retry/exhaustion.

### Test-creation order (feature step)

Add strict JSON-shape, identifier, Unicode, and bound tests with the decoder changes. Add reviewed-state, ownership, ordering, and exact prose-parity tests with the semantic validation changes. Add the clean-body and fail-soft regression cases before completion. Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/detail.py:parse_structured_detail_response` returns `None` for duplicate JSON member names, malformed Unicode, invalid concept IDs, invalid step IDs, unknown fields, and arrays above the named limit.
- A valid response returns a `ParsedDetailResponse` whose body excludes the transport envelope and whose deferrals follow reviewed concept order.
- Semantic validation rejects unknown, unsigned, non-deferred, wrongly owned, wrongly ordered, and duplicate concepts.
- Stable concept IDs in `## Deferred` and the envelope match one-for-one; an empty envelope is accepted only when that section contains no stable concept ID.
- Free-form deferred follow-up prose remains valid when it does not invent a stable concept ID.
- Invalid response data returns `None` without mutating the supplied `Plan`, `Step`, or `ConceptTree` and without raising a model-data exception.
- All new cases in `tests/test_detail.py:TestParseStructuredDetailResponse` pass.

## References

- [Claude API Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — Use the refusal, truncation, schema, and client-side validation guidance for model-authored envelopes.
- [JSON Schema Draft 2020-12 Validation](https://json-schema.org/draft/2020-12/json-schema-validation) — Use the object, required-field, string, and array constraints as the structural model for the parser.
- [RFC 7493: The I-JSON Message Format](https://www.rfc-editor.org/rfc/rfc7493.html) — Follow its Unicode and unique-object-member restrictions for interoperable JSON.
- [Python json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Account for Python’s default duplicate-name behavior, Unicode handling, and `object_pairs_hook` support.

## Deferred

- **Require structured parsing on every fresh authoring path** — step 4 removes the sidecar-dependent fallback in `plan_tool/detail.py:_author_step_detail` and handles checkpoint compatibility.
- **Recoverable detail-file replacement** — step 5 owns preservation and restoration of an existing active body when replacement fails.
- **Bound and deduplicate include-triggered regeneration** — step 6 owns orchestration after parser validation succeeds.
- **Prompt-schema changes** — the current `plan_tool/prompts/detail.md` already requires the envelope; any change to its response shape requires adding that file to a future step’s declared scope.
- **Structural deferral-link remapping and lifecycle coverage** — those ownership-accounting rules belong to `concept-remediation-3-ownership-lifecycle-accounting`.
