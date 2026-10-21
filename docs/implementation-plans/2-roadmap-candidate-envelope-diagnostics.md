---
format_version: 1
title: Roadmap Candidate Envelope Diagnostics
intent: A ledger-batch roadmap candidate proposal whose reply mixes collection vocabulary
  into the operation envelope, or carries a row field the parser does not accept,
  receives one correction that names every such defect under a collection or known
  class-name `row_type`, so a compliant retry reaches a stored inert structural candidate;
  the model-facing prompt shows operation shapes derived from the parser's own key
  sets.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-candidate-envelope-diagnostics.md
steps:
- id: 1
  title: Move operation key sets into shared parser constants
  intent: The parser and batch prompt use one source for each operation's fields.
  files:
  - plan_tool/roadmap_candidate.py
  - tests/test_roadmap_candidate.py
  allowed_mentions:
  - plan_tool/roadmap_candidate_run.py
  complexity: low
  change_type: refactor
  detail: docs/implementation-plans/plan-details/roadmap-candidate-envelope-diagnostics/01-move-operation-key-sets-shared-parser.md
  status: done
- id: 2
  title: Name missing and unknown record fields with closed diagnostic names
  intent: A correction tells the model which fields to fix without repeating arbitrary
    model text.
  files:
  - plan_tool/roadmap_candidate.py
  - tests/test_roadmap_candidate.py
  allowed_mentions:
  - plan_tool/roadmap_candidate_run.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/roadmap-candidate-envelope-diagnostics/02-name-missing-unknown-record-fields.md
  status: done
- id: 3
  title: Report all operation and row defects in one correction
  intent: One bounded retry can correct every envelope defect and the decision source
    defect together.
  files:
  - plan_tool/roadmap_candidate.py
  - tests/test_roadmap_candidate.py
  - tests/test_roadmap_candidate_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/roadmap-candidate-envelope-diagnostics/03-report-all-operation-row-defects-one.md
  status: done
- id: 4
  title: Show exact batch operation shapes in the candidate prompt
  intent: The model sees complete operations that differ clearly from capsule identity
    records.
  files:
  - plan_tool/prompts/roadmap-candidate-delta.md
  - plan_tool/roadmap_candidate_run.py
  - tests/test_roadmap_candidate_run.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/roadmap-candidate-envelope-diagnostics/04-show-exact-batch-operation-shapes.md
  status: done
- id: 5
  title: Reshape collection hints so their records do not resemble operations
  intent: The model can identify each existing row's collection, including pattern
    rows, without copying hint fields into an operation.
  files:
  - plan_tool/roadmap_candidate_context.py
  - tests/test_roadmap_candidate_context.py
  - tests/test_roadmap_candidate_run.py
  complexity: low
  change_type: feature
  depends_on:
  - 4
  detail: docs/implementation-plans/plan-details/roadmap-candidate-envelope-diagnostics/05-reshape-collection-hints-so-their.md
  status: done
- id: 6
  title: Prove malformed batch retries reach an inert structural candidate
  intent: Synthetic replies shaped like both stored attempts receive complete corrections,
    while successful and exhausted retries retain their storage and receipt boundaries.
  files:
  - tests/test_roadmap_candidate_run.py
  complexity: medium
  change_type: non-code
  depends_on:
  - 3
  - 5
  detail: docs/implementation-plans/plan-details/roadmap-candidate-envelope-diagnostics/06-prove-malformed-batch-retries-reach.md
  status: done
- id: 7
  title: Close the resolved bug entry and record the Integration re-run outcome
  intent: The backlog reflects the tested fix and records any residual model behavior
    for separate work.
  files:
  - BUG_BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 6
  detail: docs/implementation-plans/plan-details/roadmap-candidate-envelope-diagnostics/07-close-resolved-bug-entry-record-integration-re.md
  status: done
---
# Roadmap Candidate Envelope Diagnostics

## Overview

Source: BUG_BACKLOG "Candidate proposal retries still emit incompatible row-operation envelopes after the collection-vocabulary repair" (not promoted; no Jira ticket). It follows the `6718b039` collection-vocabulary/retry fix, whose bounded two-attempt correction loop already exists (`roadmap_candidate_run.py:_run_batch_candidate_proposal`). The retry is in place; what it carries is empty. `_require_keys` raises one fixed string, `candidate record has missing or unknown fields`, which the loop forwards unchanged as the correction, so attempt 2 receives no information attempt 1 lacked.

## Problem statement

The 2026-09-25 Integration run (`plan-tool --backend codex --model gpt-5.6-sol roadmap integration-aidlc-mvp --propose-candidate`) exhausted both attempts with that identical reason and wrote nothing. Replaying the two stored responses (in the Integration checkout: run `2026-09-25T20-23-24+00-00-2d917e`, response digests `16f4a9cac838cfb9` and `36917014f93df48d`) through `parse_candidate_delta` shows three defects:

1. All 10 operations carry `collection` plus a class-name `row_type` (`EntityRow`, `DecisionRow`, …); the `add-row`s also carry `row_id`, which only `replace-row`/`remove-row` accept. Repairing only these makes attempt 2 parse in full.
2. The prompt shows operation-like records from two sources and never shows an operation. The immutable capsule's `full_members[].identity` is `{artifact_key, row_type: <ClassName>, row_id}` (`roadmap_candidate_context.py:_render_batch_payload`). The `existing_rows` records that `candidate_collection_hints` adds (since `6718b039`) repeat that shape plus `collection`. The emitted extra fields match the hint record key for key. The batch prompt (`prompts/roadmap-candidate-delta.md`) names `feedback_id` and `row_type` in prose but never gives any operation's complete field set. Which record the model copied is an inference, because the prompt text is not persisted.
3. Attempt 1's `decisions` `add-row` carries `"source": null`, so attempt 1 still fails after the envelope repair (5 of 6 operations parse). The capsule serializes every dataclass field of a full member row (`_wire_value`), so a decision member shows `source`. `_parse_stage_row`'s `decisions` branch accepts no `source` key. Comparing all 13 collections' row dataclass fields with the parser's accepted keys finds `DecisionRow.source` as the only mismatch.

## Architecture

Settled decisions:

- **The parser's key sets are the single source.** The required/optional key sets for each operation, now inline literals in `roadmap_candidate.py:_parse_operation`, become shared constants that the parser checks and the batch prompt renders from. The prompt renders one exact shape per operation (`add-row`, `replace-row`, `remove-row`), including a complete `add-row` with `row_type: "entities"` and no `collection` or `row_id`, and states that `source` is not writable on a `decisions` row.
- **The collection hint stops looking like an operation.** `candidate_collection_hints` keeps its class-to-collection vocabulary; its `existing_rows` records are reshaped so that none of an operation's identity field names (`artifact_key`, `row_type`, `row_id`) and no `collection` key appears at a record's top level. That is the shape the stored replies reproduced key for key; matching some operation's complete field set is not the property, since the old record already fails that. The hint is reshaped, never removed: it retains, for every existing row, a mapping to its collection. `PatternRow` maps to both `system_patterns` and `component_patterns`, so a row's class name alone cannot identify its collection, and without the mapping the model cannot address an existing pattern row. The specific shape is `detail`'s choice, judged against the two stored responses. The capsule's own class-name `identity` records stay as they are, because they are persisted evidence. The prompt's operation shapes therefore carry the load of distinguishing an operation from an identity record, and the hint reshape alone is not expected to suffice.
- **Diagnostics are closed and complete in one pass.** The bounded retry has one correction, so a diagnostic naming only the first defect cannot succeed on attempt 2. Today `_require_keys` runs before `row_type` is checked, so the existing `candidate row type … is not allowed` message is never reached on the stored replies. Parsing instead collects every operation's envelope defects and row-body defects before raising. Row-body checking needs a schema: a valid collection name selects its schema as today, and a known internal class name selects its schema **for diagnosis only**. Each class maps to exactly one row schema (`system_patterns` and `component_patterns` share `PatternRow` and one parser branch), and the response is still rejected. That is how attempt 1's `source` defect surfaces in the first correction despite its class-name `row_type`. An unrecognized `row_type` leaves no schema, so its body goes unchecked; that is a stated limit. The reason vocabulary is `missing-field`, `unknown-field`, and `invalid-row-type`; deriving each value's exact rendering is `detail`'s job.
- **These three reasons never repeat arbitrary model text.** Mechanism: a field name is rendered only when it is a name the tool itself defines: operation keys, row and nested-record keys, row dataclass fields (so `source`), and the keys of records the prompt shows (capsule identity, `row_digest`, the hint's `collection`). The stored defects are named that way, not flattened to `other`. An invalid `row_type` is rendered only when it is a known internal class name, alongside its valid collection name(s). Anything else renders as `other`. Owner: the parser diagnostic in `roadmap_candidate.py`. It lands before the retry loop consumes the new reason. The existing messages that echo a model-supplied value (an unknown `op`, a duplicate JSON key) stay unchanged. They are not part of this defect, and closing them is separate work.
- **Existing channels carry the reason.** The diagnostic travels in the existing parse-failure `reason` field and the existing correction text appended by `render_candidate_delta_prompt`; neither channel changes shape. Because `_require_keys` is shared by every record kind (envelope, row bodies, field records, ordering entries), its improved message covers all of them.

## Scope guardrails

The binary observable is that a reply shaped like either stored Integration attempt produces one correction naming every envelope defect (and, for attempt 1's shape, the `decisions` `source` field), and a compliant retry stores an inert structural candidate. The strict parser accepts exactly the key sets it accepts today. Issued capsule bytes, receipt and digest identities, and replay keys do not change. The `missing-field`, `unknown-field`, and `invalid-row-type` diagnostics render no field name or `row_type` outside the closed vocabularies.

## References

- `BUG_BACKLOG.md` § "Candidate proposal retries still emit incompatible row-operation envelopes after the collection-vocabulary repair" — source entry and scope contract.
- `ROADMAP_FEEDBACK_FORMAT.md` — ledger-to-candidate and approval lifecycle.
- `ROADMAP_FORMAT.md` — immutable artifact and structural route contract.
- `plan_tool/roadmap_candidate.py:parse_candidate_delta`, `_parse_operation`, `_parse_stage_row`, `_require_keys` — strict wire contract and its current diagnostic.
- `plan_tool/roadmap_candidate_context.py:candidate_collection_hints` — the model-facing hint whose record shape the stored replies reproduce.
- `plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt`, `_run_batch_candidate_proposal`, `record_candidate_failure_diagnostics` — prompt, correction, bounded retry, and receipts.
- `plan_tool/roadmap_artifacts.py:DecisionRow` — the `source` field the parser does not accept.
- `plan_tool/prompts/roadmap-candidate-delta.md`, `roadmap-candidate-delta-selector.md` — batch and selector response contracts.
- `plan-seeds/archive/roadmap-candidate-vocabulary-retry.replaced.md` — the predecessor effort (`6718b039`) this builds on.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Parse-time coercion or silent dropping of unknown fields, class names, or `source`. A rejected response is corrected by a retry, never repaired. Using a class name to pick a row schema for diagnosis is not acceptance: the response is still rejected.
- Rewording the existing value-echoing messages (unknown `op`, duplicate JSON key).
- Per-row-type example bodies beyond `entities`. Every other row's dataclass fields already equal the parser's accepted keys, so the capsule shows those rows in a shape the parser accepts.
- Changing the capsule's persisted `identity` or row rendering, including dropping `source` from rendered decision members.
- A run-log schema change; `record_candidate_failure_diagnostics` reuses the parse-failure record by design.
- Redacting parse-failure receipts; they keep the exact rejected bytes and digest identity.
- The two-attempt bound, the persisted capsule row-type/evidence contract, receipt/digest/replay identity, and accepted-head publication.
- The selector prompt (`roadmap-candidate-delta-selector.md`), which already spells out the envelope; it shares `parse_candidate_delta` and so receives the improved reason with no other change.

## Risks

- Reshaping the hint changes prompt bytes only; the issued capsule and receipt must stay byte-identical, which the replay test proves.
- Collecting all defects before raising changes `CandidateDeltaError` message text; nothing outside `roadmap_candidate.py` pins the current string today, but new tests must assert reason keys rather than full prose.
- A model may keep emitting the old shape despite the fix; the residual is filed in `BUG_BACKLOG.md` with the new stored responses (step 7) rather than repaired at parse time. The capsule's class-name `identity` records are the remaining suspect; changing them is persisted-evidence work outside this plan.

## Testing

What proves the Outcome:

- The rendered operation shapes match the parser's key sets.
- The chosen hint shape is pinned against the old record shape.
- Synthetic replies reproducing each stored attempt's shape (not verbatim Integration content) each get one complete correction and succeed on a compliant retry. The attempt-1 shape includes the `decisions` `source` defect under a class-name `row_type`.
- An exhausted sequence stores no candidate and keeps both exact receipts and digests.
- A row-body case pins the class-wide diagnostic change.
- Existing strict-parser, receipt/digest, and replay tests pass unchanged.
- Recorded acceptance, not a gate: re-run the Integration command above. The model is non-deterministic, so the tests prove the deterministic side and the re-run shows whether the prompt change reaches the model.

## Acceptance criteria

- The batch prompt renders each operation's exact shape from the parser's shared key sets, including an `add-row` with a collection-name `row_type` and no `collection` or `row_id`, and states `source` is not writable on a `decisions` row.
- No collection-hint record carries an operation identity field name or `collection` at its top level, so the former flat record shape fails the check, and the records still identify each existing row's collection, including both pattern collections.
- One correction names every envelope defect across all operations, plus row-body defects for every operation whose `row_type` is a collection name or a known class name, using only the closed reason vocabulary and closed names (`other` otherwise).
- A compliant retry after that correction stores an inert structural candidate that reaches the structural approval gate.
- Strict parsing, the two-attempt bound, receipt bytes, digests, and replay identity are unchanged.
- The originating `BUG_BACKLOG.md` entry is removed in the final step only after the implementation and tests ship; while execution is pending it is marked plan-authored.

## Deferred

*(none)*. Example bodies for other row types are deliberately out of scope rather than deferred, since no other row has a dataclass/parser mismatch.
