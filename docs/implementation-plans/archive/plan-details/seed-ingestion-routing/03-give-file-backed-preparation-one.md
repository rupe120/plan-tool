> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Give file-backed preparation one exhaustive result contract — normalized, split, or refused

## Summary

Define one typed preparation result in `plan_tool/create.py` for every non-direct
file-backed source. Update `plan_tool/prompts/distill-seed.md` so the model can
produce only a normalized candidate or a split proposal, while parser and retry
failure becomes an explicit refusal. For every evidence-only normalized field,
require raw-source line spans and materialize the published field from the cited
lines rather than from model prose. Update `tests/test_create.py` and
`tests/test_distill.py` to pin the bounded repair, no-passthrough, no-write, and
exact-evidence boundaries. On green, preparation cannot silently resume from raw
source text after an invalid response or publish invented evidence as normalized
content.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the preparation result contract.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The raw-passthrough gap this step closes.
- [Input](#input) — Upstream routing and existing distill contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Required preparation outcomes and routing boundaries.
- [Tests](#tests) — Focused result-contract and create-path coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary contract and test references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain the work.
- [Deferred](#deferred) — Later lifecycle work.

## Why

`plan_tool/create.py:DistillOutcome` currently represents two invalid distill attempts as an empty passthrough result, and `plan_tool/create.py:_prepare_create_plan` then continues with the raw source. Step 2 gives direct-ready sources a deliberate direct path, so a file-backed source that needs preparation must now reach a named terminal result instead of silently receiving the same raw fallback.

## Input

- **Step 1 intake result:** Consume step 1’s preparation-needed classification and its selected raw-source identity. Do not rescan transformed source text to decide whether preparation applies.
- **Step 2 dispatch:** Accept only the non-direct file-backed branch that step 2 leaves for preparation. Direct sources remain outside this normalizing call.
- **Raw-source line map:** Keep the existing numbered raw-source representation
  through parsing. Evidence spans are inclusive 1-based ranges into that exact
  representation; no later consumer reinterprets a model-selected span against
  transformed text.
- **Current distill seam:** Adapt `plan_tool/create.py:DistillOutcome`, `plan_tool/create.py:_parse_distill_json`, `plan_tool/create.py:propose_distilled_seed_from_claude`, and `plan_tool/create.py:_prepare_create_plan`.
- **Existing source context:** Keep `plan_tool/create.py:_intent_from_seed_outcome` and `_extract_supplied_guardrails` on their raw-source paths. Preserve a normalized `Input` section when supplied, but do not fabricate absent optional context.
- **Existing split shape:** Continue using `plan_tool/create.py:SplitProposal` and `SplitProposalEntry` for split results.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — replace the empty passthrough result with exhaustive normalized, split, or refused preparation results and stop refusal before publication.
  - `plan_tool/prompts/distill-seed.md` — describe the normalized-or-split model response contract without a raw-passthrough outcome.
  - `tests/test_create.py` — cover file-backed preparation routing, downstream suppression, and no-write refusal behavior.
  - `tests/test_distill.py` — cover parsing, bounded repair, normalized, split, and refused preparation results.

## Implementation

- **Foundational logic:** Turn a non-direct file-backed source into exactly one preparation result: normalized, split, or refused.

- **Use an exhaustive tagged result.** Rework `plan_tool/create.py:DistillOutcome` or replace it with an equivalently explicit preparation result. Its discriminator must contain exactly `normalized`, `split`, and `refused`; an empty object or absent payload must not stand for refusal.

- **Keep model output narrower than the full result set.** Update `plan_tool/prompts/distill-seed.md` under `# Distill a free-form seed into a canonical plan body (or propose a split)` to request only normalized or split JSON. The caller owns refusal when parsing or validation remains invalid after its one repair attempt.

- **Make the prompt's nullable fields match the result contract.** The normalized JSON example and field rules must require non-empty `Overview`, `Problem statement`, and `Architecture` whenever it emits `outcome: "single"`. Only the five evidence-only values may be `null` in a candidate, and a missing evidence span makes the candidate unsupported before later authoring. The prompt must not direct a model to emit a `single` normalization with a missing derived body field.

- **Keep repair bounded and internal.** `plan_tool/create.py:propose_distilled_seed_from_claude` must make at most two calls for a fresh response: the initial attempt and one repair. A valid repaired response returns normalized or split; a second invalid response returns refused with a usable reason and no raw-text fallback. A matching cached preparation response still enters the same parser; if invalid, discard that checkpoint and make the one repair call before refusing. This cached invalidity does not fall back to raw text or create another retry loop.

- **Validate and materialize evidence before rebinding source text.**
  `plan_tool/create.py:_parse_distill_json` must validate the full normalized
  section map before `_prepare_create_plan` replaces `seed_body` or
  `from_description`. A normalization candidate carries all eight canonical
  keys plus an `evidence_spans` map with the five evidence-only keys and an
  `Input` key only when the source establishes that input in ordinary prose.
  `Overview`, `Problem statement`, and `Architecture` must be non-empty
  derivations from stated source facts; a missing or blank derived field is an
  invalid response that follows the bounded repair/refusal path. Each map
  value is either `null` or a list of `{"start_line": int, "end_line": int}`
  objects. A non-null evidence field is reconstructed from one or more
  source-order, non-overlapping-per-field, in-range body-text spans; the same
  source lines may support more than one field. Parser input for that field
  never becomes published prose. A missing, malformed, out-of-range, or
  heading-only span is unsupported and follows the bounded repair/refusal path
  before later authoring. A supplied `## Input` body stays verbatim; a
  prose-backed `Input` is materialized from its required non-null source span.

- **Retain typed preparation provenance.** Keep both the normalized section map
  and the validated evidence-span map through the pre-authoring support check.
  Do not recover support from a non-null model string or from omitted rendered
  H2s.

- **Prevent later evidence replacement.** After the three derived fields and
  every evidence-only field are accepted, preserve that complete map as the body
  source. It satisfies the canonical-complete skip for body synthesis. Carry its protected fields
  through scope-decision rendering, concept synchronization, and convergence;
  no later reference, body, or apply writer may override a validated
  evidence-only field.

- **Preserve existing split authority.** A valid split must use `_validate_split_plans` and return through the existing `CreateResult.split_proposal` no-plan path. Do not add a new split representation or continue a split as one plan.

- **Stop refused preparation before later work.** In the non-direct file-backed path of `_prepare_create_plan`, a refused result must prevent risk classification, step proposal, References research, body synthesis, `_publish_create_plan`, `write_new_plan`, and `append_to_manifest`. The rejected alternative is continuing with the original raw source after preparation fails.

- **Keep route boundaries intact.** Do not alter `extract_steps_from_canonical`, the direct raw-source assessment, or the public `plan_tool/cli/authoring.py:cmd_create` reporting surface in this step. Step 5 owns terminal output and exit wording.

## Tests

### Tests for this step

- `test_parse_preparation_json_accepts_normalized_or_valid_split_only` — the parser accepts only the two model-produced shapes and rejects unknown or mixed payloads.
- `test_normalized_preparation_requires_all_canonical_keys_and_evidence_spans`
  — a normalized result contains every canonical key and an evidence-span entry
  for each evidence-only field; an explicit `null` span refuses before later
  authoring.
- `test_normalized_preparation_rejects_empty_derived_sections_before_rebinding`
  — missing, empty, or placeholder `Overview`, `Problem statement`, or
  `Architecture` takes the bounded repair/refusal path and never reaches
  generic body synthesis.
- `test_normalized_preparation_materializes_evidence_from_exact_source_lines`
  — model-provided text for an evidence-only field is ignored and the result
  contains only the cited raw-source lines.
- `test_normalized_preparation_rejects_invalid_evidence_spans` — malformed,
  overlapping, out-of-range, and heading-only spans enter the bounded
  repair/refused path rather than becoming source support.
- `test_normalized_preparation_preserves_recognized_optional_context` — supplied `Input` and recognized optional context survive parsing and rendering without replacement text.
- `test_normalized_preparation_materializes_prose_backed_input` — an `Input`
  established outside `## Input` uses a non-null raw-source span and publishes
  the cited lines rather than model prose.
- `test_preparation_repair_returns_normalized_after_one_invalid_response` — one invalid response followed by a valid normalized response consumes exactly two calls and returns normalized.
- `test_invalid_cached_preparation_response_is_discarded_and_repaired_once` — an invalid matching cache entry is evicted, receives one repair invocation, and returns its valid repaired result or refused outcome without raw fallback.
- `test_preparation_second_invalid_response_returns_refused_not_passthrough` — two invalid responses return a refusal with no normalized body or split entries.
- `test_file_backed_non_direct_source_prepares_even_when_distill_is_false` — a preparation-needed file-backed source cannot bypass preparation through the legacy flag.
- `test_normalized_preparation_rebinds_downstream_authoring_to_validated_text`
  — later preparation consumers receive normalized text only after the result
  validates, and body synthesis cannot replace materialized evidence.
- `test_normalized_materialized_evidence_survives_scope_sync_and_convergence`
  — approved concept decisions and an enabled convergence apply preserve every
  protected evidence-only field while still allowing unprotected plan work.
- `test_preparation_split_returns_existing_split_proposal_without_plan_or_manifest` — a preparation split uses `SplitProposal` and writes neither a plan nor a manifest entry.
- `test_refused_preparation_skips_later_model_calls_and_publication` — refusal reaches no later authoring call, plan write, manifest write, or convergence path.
- `test_refused_preparation_is_prewrite_in_iterative_and_non_iterative_create` — both budget modes stop before publication after preparation refusal.

Every listed test in `tests/test_create.py` and `tests/test_distill.py` must be green before this step is complete.

## Acceptance criteria

- Every non-direct file-backed preparation attempt returns exactly one of normalized, split, or refused.
- A malformed fresh preparation response receives one repair attempt; an invalid cached preparation response is discarded and receives that same one repair attempt. An invalid repair refuses rather than falling back to raw text.
- A normalized result contains all canonical section keys, retains optional
  context without fabrication, has non-empty derived `Overview`, `Problem
  statement`, and `Architecture` fields, and carries validated raw-source spans
  for every evidence-only field.
- Evidence-only published text is materialized from the exact cited raw lines;
  model prose alone cannot establish support or replace the materialized text
  later in authoring.
- Only an accepted normalized map has all eight non-empty canonical body
  sections and bypasses body synthesis; a normalization candidate with absent
  evidence is refused before later authoring.
- A split result uses the existing `SplitProposal` path and writes no plan or manifest entry.
- A refused preparation result reaches no later model-authoring phase, `_publish_create_plan`, `write_new_plan`, or `append_to_manifest`.
- The direct route remains outside preparation, and inline callers retain their separately owned compatibility behavior.
- `uv run pytest tests/test_create.py tests/test_distill.py -q` passes.

## References

- [Python enum — Support for enumerationshttps: — Use for the closed preparation-result vocabulary.
- [CommonMark Spec 0.31.2 — ATX Headings and Fenced Code Blockshttps: — Check the canonical H2 form rendered from a normalized section map.
- [pytest — How to use temporary directories and files in testshttps: — Use hermetic no-plan and no-manifest assertions.

## Applicable guardrails

- **The plan’s “## Plan intent”, visible preparation route:** make preparation outcomes explicit without silently replacing a refused source with raw text.
- **The plan’s “## Step intent”, bounded repair:** keep repair internal and bounded; it must not become an additional terminal route.
- **The plan’s “## Out of scope”, split boundary:** retain `SplitProposal` inside create and preserve its no-plan behavior.
- **The plan’s “## Out of scope”, authoring-contract boundary:** limit changes to preparation routing and its prompt contract; leave step, References-research, and body-synthesis contracts unchanged.
- **The plan’s “## Terminal route lifecycle”, lifecycle ownership:** expose the in-memory result only; later steps own reporting, checkpoint, archive, and exit behavior.

## Deferred

- **Terminal route lifecycle** (`22a740fdbaa54ae54299f4be8f7189fd05c322dc42e247bba3ec3e71d1b4abdc`) — steps 5 and 6 own output, exit mapping, run records, checkpoint versioning, and artifact timing.
