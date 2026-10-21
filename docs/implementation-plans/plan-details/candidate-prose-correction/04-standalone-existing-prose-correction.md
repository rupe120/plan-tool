# Step 4 — Add the standalone existing-prose correction operation to candidate deltas

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds a fourth candidate operation, `correct-prose`, to `plan_tool/roadmap_candidate.py`. It replaces one issued shared-narrative span in an artifact body, with no typed-row change. Closed parsing, a candidate-local byte ceiling, and binding to the capsule-issued span (from step 3) are enforced. Application uses step 2's splice helper on the predecessor body before add-row fragments are appended. The corrected body then goes through the existing complete-roadmap gates, and a gate failure refuses. The key design decision is to make the correction a member of the `operations` union, not a new root field, so stored `normalized_operations` replay it. On green, a delta with one correction yields a candidate whose only body change is the issued span. Every refusal case publishes nothing.

## Table of Contents

- [Why](#why) — what candidates cannot do today
- [Input](#input) — step 1–3 outputs and current candidate shapes this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — operation shape, parsing, binding, refusals, application order
- [Tests](#tests) — cases pinning each rule and carve-out
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — standards behind digests and byte limits
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work other steps or plans own

## Why

`plan_tool/roadmap_candidate.py:CandidateAddRowProseAmendment` is the only prose authority a candidate has, and it only appends text for a row the same candidate adds. A stale shared paragraph (for example a Decisions paragraph naming several rows) cannot be corrected without a typed-row change that the feedback does not call for. Steps 1–3 define and issue the shared span. This step gives admitted feedback the operation that consumes it.

## Input

- **Step 1 contract:** `ROADMAP_FORMAT.md` § "Reviewer feedback and candidate lifecycle" defines the owning set, the refusal values, the byte ceiling, the combined-operation rule, and the removed-row rule. Read the landed text first. Where this detail and the doc disagree on the contract, the doc wins.
- **Step 2 output:** the public splice helper in `plan_tool/roadmap_revision_patch.py` takes plain `(start, end, replacement)` edits, refuses overlap with `stage prose amendments overlap`, and splices back to front. Use it; do not copy the splice.
- **Step 3 output:** each issued span in the capsule carries the span id, text, and the owning-set row ids. It is carried on `source_spans` of `CandidateContextFullMember` in `plan_tool/roadmap_candidate_context.py`. Read the landed field names from that module. A span whose owning set has one row is a valid correction target (step 1's ruling); a legacy single-owner span carries no owning-set field and is read as an owning set of one.
- **Operation union today:** `CandidateDeltaOperation` is `CandidateAddRow | CandidateReplaceRow | CandidateRemoveRow`. `_parse_operation`, `_operation_diagnostics`, `_delta_is_well_formed`, `_prepare_operations` (target-row dedupe and sort key), `_classify_validated_operations`, and `_validate_operation_authority` all assume a row target.
- **Replay contract:** `normalized_operations` is stored on candidate evidence and re-parsed through `parse_candidate_delta` after `_operations_wire_for_reparse` in `plan_tool/roadmap_candidate_run.py` and `plan_tool/roadmap_candidate_review.py`. Operations absent from that tuple would be lost on replay.
- **Sibling bounds:** `_parse_add_row_prose_amendment` shows the parse-time style: nonblank text, UTF-8 byte ceiling `HARD_MAX_PROSE_AMENDMENT_BYTES` from `plan_tool/project_config.py`.
- **Gates:** `plan_tool/roadmap_gates.py:check_inventory_has_prose` requires each prose-inventory row id to appear as a whole token. It never judges prose quality, and this step does not add a quality check.
- **Limit on verification:** the operation can be proved only with synthetic capsules and bodies in the tests. No model-authored correction has been observed.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate.py`: add the `CandidateCorrectProse` record and its key set, add it to `CandidateDeltaOperation`, extend the parser, diagnostics, and shape check, add a binding and authorization pass, add an apply step, and fold it into `normalized_operations`.
  - `tests/test_roadmap_candidate.py`: add the cases under Tests.
- **Zero-diff files (deliberate):** `plan_tool/roadmap_candidate_run.py`, `plan_tool/roadmap_candidate_review.py`, `plan_tool/cli/roadmap_cmd.py`, `plan_tool/roadmap_compare_run.py`. They consume `normalized_operations`; whether they render or iterate it correctly for the new member belongs to other steps (see Deferred). This step must not edit them.

## Implementation

**Operation shape (recommended).**

- `CandidateCorrectProse` on `_FrozenCandidateRecord`, `op: Literal["correct-prose"]`, with `feedback_id`, `artifact_key`, `span_id`, `replacement`.
- Add `CORRECT_PROSE_REQUIRED_KEYS` / `_OPTIONAL_KEYS` beside the sibling key sets. Optional keys are empty.
- Include the new keys in `_OPERATION_FIELD_NAMES` so unknown-key diagnostics name them.
- The model supplies only the span id and the replacement. Span text, digest, and owning rows come from the capsule, never from the model.
- **Rejected alternative:** a separate `prose_corrections` root field. It leaves `_prepare_operations` untouched, but `normalized_operations` replay would drop it silently.

**Closed parsing.**

- Add a `correct-prose` arm to `_parse_operation` and to `_operation_diagnostics`.
- Parse-time refusals use `CandidateDeltaError` with messages that name the field.
- `replacement` must be nonblank after trimming. It must be no longer than a candidate-local byte ceiling, a module constant in `roadmap_candidate.py` set to the value step 1 settles (UTF-8 bytes). Do not change `HARD_MAX_PROSE_AMENDMENT_BYTES` or `project_config.py`.
- Extend `_delta_is_well_formed` with a shape-only branch for the new class, like its siblings.
- Re-check the ceiling and nonblank rule in the materialization-side pass too, since a hand-built delta skips the parser.

**Keep row-assuming code unaware of it.**

- In `materialize_candidate`, split corrections from row operations before `_prepare_operations`. `_prepare_operations` keeps its row-only contract and its sort key.
- Sort corrections deterministically by `(artifact stage order, span start in the predecessor body, span_id)`.
- Set `normalized_operations` to the sorted row operations followed by the sorted corrections. Pass this combined tuple to `BatchGateCleanCandidate`, `ReviewRequiredCandidate`, and `_content_identity`.
- Leave `_classify_validated_operations` as is. Its existing "anything not a replace is structural" rule makes a correction `STRUCTURAL`; that is deliberate, and it keeps a correction out of the presentation-only path.

**Binding checks (new pass, runs after bindings are verified and before any apply).** Each refusal returns a `CandidateRefusal` using an existing reason (`invalid-bindings` for binding and authority, `invalid-operation` for shape and span problems). Do not widen `CandidateRefusalReason` unless step 1 names a new value; if it does, use that value.

- **Unauthorized feedback:** `feedback_id` must be among the admitted ids, using the same check `_validate_operation_authority` applies to row operations.
- **Unknown span:** `span_id` must be among the spans the capsule issued for `artifact_key`. Otherwise refuse.
- **Unauthorized span:** every row id in the span's owning set must be a full member in the capsule authority map (`_full_member_authority`). Otherwise refuse.
- **Stale or ambiguous:** find the issued span text in the predecessor body, which is the body of the artifact parsed by `_parse_predecessor_artifacts`. Zero matches means stale. More than one match means ambiguous. Also recompute the span id and the SHA-256 digest of the text and compare them to the issued values; a mismatch means stale.
- **Duplicate:** two corrections naming one `span_id` refuse. This is separate from the existing "cannot target one row twice" rule.
- **Overlapping:** pass all correction edits to step 2's helper and map its overlap error to a refusal. A range starting exactly where another ends is not an overlap.
- **Combined with a row change:** refuse when the delta also adds, replaces, or removes any row in a correction's owning set within the same artifact. Use step 1's wording for what counts as "in the set" for an added row; the landed doc wins.
- **Owning set source:** computed from the predecessor's live rows only (step 1). A correction that merely names a row the same delta adds is allowed; an add of an id already in the owning set is refused.
- **Other feedback items:** a different feedback item's row operations on the same artifact are allowed unless they touch the owning set. One feedback item may carry a correction alongside its other operations, so long as those operations are outside the owning set.
- **Stale-row authority:** a removed-row id in the replacement text or in the span grants nothing. Authority comes from the owning-set check only.

**Application order.**

- In `materialize_candidate`, apply the typed row operations as today, then apply corrections, then `_append_added_row_prose`.
- Corrections edit the body only. Frontmatter delimiters and all bytes outside the span stay unchanged.
- Offsets come from the predecessor body. Before splicing, assert the candidate artifact's body still equals the predecessor body. If it does not, refuse as `invalid-operation`; do not guess new offsets.
- Add-row fragments append after the splice, so appended text never shifts a span offset.
- Catch the helper's refusal type explicitly. The existing `except (AttributeError, TypeError, ValueError)` around the apply loop may not cover it.

**Gates.**

- Do not add a new gate. The corrected body flows through `_assemble_candidate_artifacts` and `check_complete_roadmap_gates`. A failure returns the existing `gate-failed` refusal through `_gate_correction`.
- A replacement that drops a live row id from the inventory therefore fails through `check_inventory_has_prose`. This is the intended safety net.

**Constraints.**

- Smallest change: no marker syntax, no regex edit, no multi-span-per-operation form.
- Step 4 must not change span issuance (step 3) or the splice helper (step 2).

## Tests

All in `tests/test_roadmap_candidate.py`, using `_resolved()` fixtures extended with a shared paragraph, and the existing capsule builders.

- `test_correction_may_target_a_block_naming_one_live_row_and_a_removed_row` — the stale-paragraph case after a row removal: a legacy single-owner span is a valid target and the correction applies.
- `test_correct_prose_parses_closed_keys` — a well-formed operation parses; an unknown key and a missing key are diagnosed by name.
- `test_correct_prose_replacement_must_be_nonblank` — an empty or whitespace replacement is a `CandidateDeltaError`.
- `test_correct_prose_replacement_byte_ceiling_counts_utf8_bytes` — a replacement at the ceiling passes; one byte over fails; a multibyte string over by bytes but under by characters fails.
- `test_correct_prose_ceiling_is_candidate_local_and_leaves_add_row_limit_unchanged` — the add-row fragment limit stays `HARD_MAX_PROSE_AMENDMENT_BYTES`.
- `test_correction_replaces_only_the_issued_span_bytes` — the body outside the span and the frontmatter delimiters are unchanged byte for byte.
- `test_correction_applies_before_add_row_fragments_append` — a delta with a correction and an add-row yields the corrected span and the appended fragment at the end.
- `test_correction_may_name_a_row_the_same_delta_adds` — the owning set comes from the predecessor's live rows, so naming an added row is accepted.
- `test_one_feedback_item_carries_correction_and_outside_set_row_operation` — a correction plus a row operation outside the owning set under one feedback id succeeds.
- `test_unknown_span_id_refuses` / `test_unissued_artifact_span_refuses` — a span the capsule never issued is refused.
- `test_span_whose_owning_row_is_not_a_capsule_member_refuses` — the unauthorized case.
- `test_stale_span_text_refuses` — the predecessor body no longer contains the issued text.
- `test_ambiguous_span_text_refuses` — the issued text occurs twice in the body.
- `test_digest_mismatch_refuses` — the issued digest does not match the text.
- `test_stale_removed_row_reference_grants_no_authority` — pins that naming a removed id in the replacement or span does not authorize anything.
- `test_duplicate_correction_for_one_span_refuses` — two corrections, one span id.
- `test_overlapping_spans_refuse_and_adjacent_spans_are_allowed` — pins the boundary rule `start < prior_end`.
- `test_correction_with_row_edit_in_owning_set_refuses` — replace, remove, and add each refuse (three cases).
- `test_correction_refuses_unadmitted_feedback_id` — the feedback id is not admitted.
- `test_corrected_body_failing_inventory_gate_refuses_with_gate_failed` — a replacement that omits a live row id returns `gate-failed` and no candidate.
- `test_refusal_publishes_no_candidate` — every refusal above leaves `candidate`, `batch_candidate`, and `review_required` as `None`.
- `test_normalized_operations_include_corrections_and_reparse_round_trip` — the stored tuple re-parses through `parse_candidate_delta` after `_operations_wire_for_reparse` to an equal delta.
- `test_correction_classifies_as_structural_not_presentation_only` — pins the deliberate classification.
- `test_content_identity_changes_with_the_replacement_text` — two corrections differing only in text produce different identities.
- Update any existing test that asserts the operation union or root/operation key sets, to include the new member.

### Tests for this step

The cases above are the roster: parsing, binding refusals, application order, gate refusal, and replay. All must be green before this step is finished, together with the existing `tests/test_roadmap_candidate.py` suite and `tests/test_duplication.py`. Mutation check: widen the owning-set refusal to ignore adds, and `test_correction_with_row_edit_in_owning_set_refuses` must go red.

## Acceptance criteria

- `parse_candidate_delta` accepts `{"op":"correct-prose", ...}` with exactly its four keys and rejects extra or missing keys with a diagnostic naming the key.
- A replacement over the candidate-local byte ceiling is rejected at parse and again at materialization.
- A valid correction yields a gate-clean candidate whose body differs from the predecessor only inside the issued span, with frontmatter delimiters unchanged.
- Each of the following refuses with no candidate published: unknown, unauthorized, stale, ambiguous, duplicate, overlapping, oversized, and unadmitted-feedback spans; a same-candidate row change in the owning set; a corrected body that fails the artifact gates.
- A correction and a row operation outside the owning set under one feedback id both apply.
- `normalized_operations` includes corrections and round-trips through `parse_candidate_delta`.
- `git diff --stat` shows only `plan_tool/roadmap_candidate.py` and `tests/test_roadmap_candidate.py`.
- `rg 'HARD_MAX_PROSE_AMENDMENT_BYTES' plan_tool/project_config.py` shows that constant unchanged.

## References

- [hashlib — Secure hashes and message digests (Python standard library)](https://docs.python.org/3/library/hashlib.html) — the SHA-256 digest compared against the issued span text.
- [RFC 3629 — UTF-8](https://www.rfc-editor.org/rfc/rfc3629) — why the ceiling counts encoded bytes and not characters.
- [dataclasses — Data Classes (Python standard library)](https://docs.python.org/3/library/dataclasses.html) — frozen-record conventions the new operation follows.

## Applicable guardrails

- **The plan's "## Scope guardrails", arbitrary-replacement item:** the operation names one issued span by id. This step must not add marker or pattern editing, or any way to name text that was not issued.
- **The plan's "## Scope guardrails", weaker-gates item:** the corrected body goes through the existing gates unchanged. This step must not add exemptions or soften `check_inventory_has_prose`.
- **The plan's "## Scope guardrails", stale-row authority item:** a removed-row reference in the span or the replacement grants no authority. The binding pass checks the owning set against the capsule only, and the stale-row test pins that.
- **The plan's "## Out of scope", Group 4 and unresolved-contradiction items:** this step adds no new feedback group and no contradiction detection. It works only on feedback the capsule already admits.
- **Step intent:** a refusal publishes no candidate, and bytes outside the span stay unchanged.

## Deferred

- Showing the approver the exact before/after text, and rendering corrections in review and CLI output — owned by later steps of this plan; comparison output is carved to BACKLOG #436. Existing renderers that read `normalized_operations` (`plan_tool/roadmap_candidate_review.py`, `plan_tool/roadmap_compare_run.py`, `plan_tool/cli/roadmap_cmd.py`) are not edited here. A check that they tolerate the new member belongs to the step that owns that surface.
- Prompt text and run orchestration that lets a model emit `correct-prose` (`plan_tool/roadmap_candidate_run.py`) — a later step; this step only accepts the operation.
- Format documentation sync to landed symbols — the plan's docs step.
- Consolidating the parse-time and materialize-time byte checks into one helper — a consolidation find; file it in `BACKLOG.md` if wanted, not here.
