# Candidate capsule fixes — code review ledger

| Field | Value |
| --- | --- |
| Change | Two `BUG_BACKLOG.md` entries: "Stored candidate capsules cannot restore any Decision row" and "Candidate source-span evidence duplicates shared text until an approved full feedback batch exceeds the context ceiling" |
| Branch | `docs/candidate-capsule-bugs` |
| Review range | pass 1: `d4f1833c..ce4976fe` (Decision-row restore `918fe02a`; changelog `8c3c23e0`; span table `ce4976fe`); pass 2: `d4f1833c..6720212a` |
| Checks run | Full suite `uv run pytest tests/ -q -n auto`: 14,362 passed, 190 skipped; the two route tests below were added after that run and pass with the three candidate test files (`-n auto`). Both fixes verified by mutation (reverting each turns its new tests red). Behavior checks that the static reviews could not make: see "Behavior checks". |
| Reviewer | headless `claude -p` session, report-only, `high` effort (`.tmp/candidate-capsule-code-review-N.stream.log`) |
| Disposition | passes 1 and 2 triaged; pass 3 pending (convergence needs two consecutive clean or low-yield passes) |

## Settled decisions (hand to each reviewer)

- `_parse_stage_row` stays strict for model-proposed rows; it rejects `source` on a
  decisions row, and `tests/test_roadmap_candidate_run.py` pins that.
- Stored rows restore through `_restore_stored_stage_row`: a Decision row has its own
  restore that admits `source`, and every restored row must round-trip to its stored
  wire form. The restored row id must match the member identity.
- Batch payloads are schema 2: a top-level `shared_source_spans` table holds each
  shared span once, keyed by `(artifact_key, span_id)`, and a member names its shared
  spans in `shared_source_span_ids` (absent when it has none). Single-owner spans stay
  inline in the member's `source_spans` in their schema-1 form, so a batch with no
  shared span is no larger than before. Selector payloads stay schema 1 because stored
  ones are verified by exact recompilation.
- Stored batch capsules are bound by digest and member receipts and are never
  re-rendered, so schema-1 batch capsules keep verifying. A test covers this.
- Member `source_spans` stay on `CandidateContextFullMember` and the receipts; only the
  rendered payload changed. Edit authority, receipts, and the 192 KiB ceiling are unchanged.
- Deliberately not in the span-table fix: filtering spans to those eligible for the
  admitted feedback batch, and a per-section size breakdown on `payload-over-budget`.
- The clean structural seal pin in `tests/test_roadmap_candidate_review.py` was
  re-recorded twice with the narrative check disabled, as originally recorded (the pre-change
  code reproduces the original id). Payload bytes changed, approval behavior did not.

## Review pass 1 — /code-review (high, headless), 2026-10-05

Scope: `d4f1833c..ce4976fe`. Method: static reading plus grep over every consumer of capsule
`source_spans` and `schema_version`; the reviewer did not run the suite and no permission denial
thinned the review (stream log `.tmp/candidate-capsule-code-review-1.stream.log`, findings
`.tmp/candidate-capsule-code-review-1.md`). No bug in the primary paths of either fix.

### 1. The span table made single-owner spans larger, so an unshared batch could newly exceed the ceiling — medium
`plan_tool/roadmap_candidate_context.py:1114`. Each single-owner span gained a member id entry, a
repeated `span_id`, and an `artifact_key`: about 100 bytes per span, and only shared spans got cheaper.
**Disposition:** fixed 6720212a — the table holds only shared spans (`shared_source_spans`);
single-owner spans stay inline in their schema-1 form, and a member with no shared span carries no
extra key. A batch with no shared span differs from schema 1 only by `"shared_source_spans":[]`.
Pinned by `test_batch_payload_without_a_shared_span_is_no_larger_than_the_schema_one_layout` and
`test_batch_payload_keeps_single_owner_spans_inline_and_omits_the_empty_shared_id_list`; reverting to
the all-in-table layout turns those and three sibling tests red. The seal pin was re-recorded again.
This corrects the earlier schema-2 design in the settled decisions above.

### 2. `_hydrate_capsule` refuses stored rows of 5 of 12 row types — medium
`plan_tool/roadmap_candidate_run.py:2056`.
**Disposition:** refuted — `_DELTA_ROW_TYPES` has all 12 row types (Entity, BusinessRule, Workflow,
Decision, AttributeDisposition, Constraint, Hosting, Pattern, Store, Component, Plan, Assumption); the
reviewer counted 6. No row type reaches the "unsupported row type" raise. Not run: the reviewer's
reachability scenario, since there is no unmapped type to build it from.

### 3. Batch re-entry compares the whole receipt, so an upgrade changes the answer for an existing active candidate — low
`plan_tool/roadmap_candidate_run.py:1581`.
**Disposition:** declined — receipt equality is the existing contract: any change to the compiled
context (an earlier ceiling change included) makes a re-run build a fresh candidate instead of
returning the stored one. Reachable only by re-running `--propose-candidate` on an unchanged ledger
after the upgrade, and the outcome is a new candidate, not a wrong one. The reviewer could not confirm a
live path and neither could we; this has not been exercised end to end.

### 4. `ROADMAP_FORMAT.md` still states the per-owner repetition as current — low
`ROADMAP_FORMAT.md:977`.
**Disposition:** fixed 6720212a — the clause is removed; the replacement byte ceiling is the
lasting reason a large shared block is not issued.

### 5. The restore error embeds stored identity strings unescaped — low
`plan_tool/roadmap_candidate_run.py:2058`.
**Disposition:** declined — `where` is the artifact key and row id of a capsule that already passed
`_capsule_is_intact`, and both come from the artifact parser's id rules, not free text.

## Review pass 2 — /code-review (high, headless), 2026-10-05

Scope: `d4f1833c..6720212a`. Method: static reading and grep over every consumer of the span and
schema-version fields. A permission denial blocked the reviewer's Python runs, so it executed
nothing and its runtime question (finding 2) was checked afterward in the driving session (stream
log `.tmp/candidate-capsule-code-review-2.stream.log`, findings `.tmp/candidate-capsule-code-review-2.md`).

### 1. Decision rows stored before `DecisionRow.source` existed now refuse instead of restoring — medium, plausible
`plan_tool/roadmap_candidate.py:1285`.
**Disposition:** declined — a stored row's `row_digest` was computed before `source` joined the row
wire form, so it can never equal the live `_row_digest`, and `candidate_collection_hints`
(`roadmap_candidate_context.py:311`) refuses that mismatch on the proposal-prompt path. Accepting the
row at restore would move the refusal to a later site rather than make the candidate usable. Reasoned
from the code; a pre-2026-09-16 stored candidate was not built and run. The `missing-source` test case
stays, and its name says "malformed".

### 2. Decision-row restore is only tested on a hand-built wire dict, never on the persisted form — medium-low
`tests/test_roadmap_candidate_run.py:4167`.
**Disposition:** fixed 9d6a48f1 — the reviewer's worry that `exclude_none=True` strips
`source: null` is refuted by running it: the persisted row keeps `"source": null`, authored and inherited.
The missing coverage was real: `test_decision_row_survives_the_persisted_evidence_round_trip` dumps a
capsule with `exclude_none=True`, reloads it as dicts, and hydrates it. Swapping the restore back to
`_parse_stage_row` turns both cases red.

### 3. The prompt does not say how a shared-table entry maps to the operation's `artifact_key` — low
`plan_tool/prompts/roadmap-candidate-delta.md:38`.
**Disposition:** fixed 9d6a48f1 — one sentence: a table entry belongs to the artifact in its
`artifact_key`; copy that and its `span_id` into the operation. No code change.

### 4. Per-owner repetition wording disagrees across four sites after pass 1 finding 4 — low
`plan_tool/roadmap_revision.py:1354`, two test docstrings, `ROADMAP_FORMAT.md:977`.
**Disposition:** fixed 9d6a48f1 — an incomplete vocabulary sweep in the pass 1 fix. One
statement now holds at all four sites: a selector capsule repeats a shared span per owner and a batch
capsule issues it once, and the replacement ceiling is why a larger shared block is not issued.

### 5. The schema-1 batch compatibility test cannot see a layout change in a consumer — low
`tests/test_roadmap_candidate_context.py:1085`.
**Disposition:** declined — the proposal prompt renders the stored payload bytes verbatim and no
consumer parses the payload JSON (the reviewer's own Method says so), so the suggested extension tests a
hypothetical consumer.

### 6. Three passes over `member.source_spans` repeat one predicate — low (simplification)
`plan_tool/roadmap_candidate_context.py:1115`.
**Disposition:** declined — three one-line uses of `owning_row_ids is None`; a helper adds an indirection
for no current behavior difference, and the smallest change that closes the span-size finding is the one
already landed.

### 7. Both backlog entries remain and the span-table entry describes a design that did not ship — low
`BUG_BACKLOG.md:1286`, `:1354`.
**Disposition:** tracked — removed at close-out, after the Integration check below and review convergence, in
the PR that ships the fixes. Until then the span-table entry's single-table description is stale.

### 8. A machine-specific launcher alias is written into the shared directive — low
`integrations/shared/DIRECTIVES.md:1072`.
**Disposition:** declined for now — the owner asked for this edit directly (2026-10-05, "update the
directives to either use claude or claude-personal"); moving the alias name to the machine-local
`~/.claude/CLAUDE.md` is the owner's call and is raised in the pass summary.

## Behavior checks (run in the driving session, 2026-10-05)

Both review passes were static reads; these ran the changed code on the paths a user takes.

- **Decision-row restore, real routes.** A stored batch candidate on the Integration decisions root has five
  Decision rows as full members. Through `decide_structural_candidate(..., "edit")` and
  `request_replacement`, with the restore fix reverted, each refuses with `stored capsule row
  domain decision-config-vs-run-split cannot be restored: decisions row has unknown-field source` — the
  message Integration reported. With the fix both proceed. Approval does not restore rows, so the existing Integration
  end-to-end test stays green without the fix (checked by reverting it); the two new route tests
  (`..._can_be_edited_after_reload_from_disk`, `..._can_request_a_replacement_after_reload`) are the
  coverage that was missing.
- **Persisted form.** A capsule dumped with `exclude_none=True` keeps `"source": null` on a Decision row,
  so the restore matches what is written to disk.
- **Payload size on the Integration paragraph fixture** (5 references to 1 unique 1,288-byte span): 16,457
  bytes before the span table, 10,310 after, about 1,540 bytes per removed copy. Real Group 5 (99
  references, 31 unique spans) is an extrapolation from this, not a measurement; recompiling the
  reopened Integration batch is still the owner's check.
- **Not run:** a pre-2026-09-16 stored candidate (pass 2 finding 1), and a real batch of the reported
  shape.

## Review pass 3 — pending
