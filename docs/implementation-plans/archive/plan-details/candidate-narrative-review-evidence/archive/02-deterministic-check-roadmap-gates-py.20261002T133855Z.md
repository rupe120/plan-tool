> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add the removed-id-in-live-prose check to roadmap_gates.py

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds one deterministic check to `plan_tool/roadmap_gates.py`. It finds a removed design row's id still named in live prose, meaning outside the structurally marked historical and rejected-alternative context. Each hit is reported with the artifact, the row id, and the span. The check is a standalone function kept out of every `run_*_gates` stage tuple, so no existing gate behavior changes. It is pinned on the real Integration Decisions paragraph through `tests/fixtures/roadmap/integration-decisions-paragraph.md`, which IPPT-18 must check in first. On green, step 5 can consume the check, and the Integration case fails the check the way the plan says it must.

## Table of Contents

- [Summary](#summary) — what the step adds and the observable result
- [Why](#why) — the gap the check closes
- [Input](#input) — contracts this step reads and the entry condition
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the check's contract and the approach
- [Tests](#tests) — cases, including the Integration pin and the carve-outs
- [Acceptance criteria](#acceptance-criteria) — observable done conditions
- [References](#references) — specs relevant to fence and token handling
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work other steps own

## Why

The gates check typed rows against typed rows. `check_inventory_has_prose` only asks whether a live row is named in prose. Nothing asks whether a *removed* row is still named as if it existed. A reviewer who removes a row can leave a paragraph (the Integration Decisions paragraph is the real case) that still describes it, and nothing stops approval. This is the plan's one machine-checked fact, and it is decidable on ids alone, so it stays inside the plan's ban on semantic gates.

## Input

- **Entry condition (hard stop):** the plan requires IPPT-18 to land first and check in `tests/fixtures/roadmap/integration-decisions-paragraph.md`. At HEAD the directory `tests/fixtures/roadmap/` holds only `integration-scale-domain.md`; the Decisions-paragraph fixture is absent. Before writing any code, confirm the fixture exists. If it does not, **stop and report to the user**. Do not author or guess the fixture here, and do not substitute `integration-scale-domain.md`.
- **Removal records:** `plan_tool/roadmap_artifacts.py:RemovalRecord` (`removed_id`, `rationale`, `feedback_ids`). Every artifact dataclass carries `removals: tuple[RemovalRecord, ...]`. Reviewers prune a record by deleting it from this tuple.
- **Envelope:** `plan_tool/roadmap_gates.py:ArtifactEnvelope` supplies `artifact_under_check`, `filename_under_check`, and `predecessor` (`None` on a first run).
- **Whole-token match:** `_ID_CHARACTER` and `_prose_names_id` in `plan_tool/roadmap_gates.py`. Reuse them. A bare substring match would flag `entity-1-extra` as `entity-1`.
- **Fence scanner:** `plan_tool/jira_grade.py:fenced_spans` (already imported pattern in `review.py`). `plan_tool/scope_fence.py` is already imported by this module for `_fenced_code_spans`; read both and reuse whichever already fits. Do not write a new fence recognizer.
- **Historical-context marker, evidence classes, and the removed-id source:** step 1 owns them in the new "Candidate narrative review evidence" section of `ROADMAP_FORMAT.md`. Read the marker's exact syntax and the class name off that landed section. The landed text wins over any spelling in this file.
- **Violation type:** `Violation` carries `kind`, `artifact`, `row_id`, `message`. It has no span field. The span goes in the message text (see Implementation).

## Files (creates vs edits)

- **New files:** none. The fixture belongs to IPPT-18 and is only read here.
- **Existing files (edits only):**
  - `plan_tool/roadmap_gates.py` — add a `VIOLATION_*` kind constant, the check function, and its small helpers (id-set builder, live-prose span finder). Do not add the function to `DOMAIN_GATES`, `CONSTRAINTS_GATES`, `COMPONENTS_GATES`, or `PLANS_GATES`, and do not touch `_run_gates` or any `run_*_gates`.
  - `tests/test_roadmap_gates.py` — add the new test class and the Integration pin.

## Implementation

**Behavior.** One public function, shaped like the other gates: takes an `ArtifactEnvelope`, returns `list[Violation]`, never raises. Name it for what it finds, for example `check_removed_ids_in_live_prose`. It is called by step 5, not by a stage tuple.

**Which ids are checked.**
- Start from the removed ids the candidate itself carries: `artifact_under_check.removals`. That set is the carried records plus those the candidate adds.
- A record the reviewer pruned is absent from that tuple, so it is deliberately no longer checked. Do not re-add it from `predecessor`.
- A feedback-free candidate has no reviewer edit, so check it against its predecessor's removals (`envelope.predecessor.removals`). When `predecessor` is `None` and the candidate carries no removals, the id set is empty and the check returns `[]`.
- Confirm the exact union rule against step 1's "removed-id source" text. If that text and this paragraph disagree, step 1 wins.

**What counts as live prose.** The candidate's `body`, minus:
- fenced code spans (use the existing fence scanner), and
- the structurally marked historical and rejected-alternative context that step 1 defines.
Match each removed id as a whole token with `_prose_names_id`'s alphabet. Never use keyword matching, and never judge meaning. A named id in live prose is the whole decision.

**Output.**
- One `Violation` per (removed id, span). Cardinality is per occurrence-group, not one per id: a reviewer needs the location. Keep it to one per distinct id per live-prose span (paragraph or marked block), not one per mention.
- `row_id` is the removed id. `artifact` is `envelope.filename_under_check`.
- The message must be self-contained, because it may be pasted as a bullet into a retry or shown beside evidence. Name the id, the filename, and the span by its stable anchor (the nearest heading text plus the paragraph's first words, or the paragraph ordinal under its heading). Never use a line number or byte offset.
- Say in the message how to resolve it: restate the paragraph without the id, or move the mention inside the historical marker. Do not name IPPT-18's operation by symbol; use only what step 1's section says.

**Key design decisions.**
- Recommended: a fixed function with one pass, not a rule engine. Reject a configurable matcher.
- Rejected: adding the check to a stage tuple. It would change what existing stages retry on, which the plan forbids.
- Rejected: a new fence recognizer. The repo already has one; reusing it avoids a second implementation that could be defeated differently (see the plan's fence-recognizer lesson).
- Rejected: a new field on `Violation` for the span. It widens a shared type for one consumer.

**Constraints.**
- The module stays a leaf: no new first-party imports beyond what it already imports.
- The check must stop early on an empty id set so a normal first-run candidate costs nothing.
- It must not read `feedback` or judge feedback state; that belongs to later steps.
- `plan_tool/gates.py` is unrelated (the `gate:` shell-command suggester). Do not import it.

## Tests

All in `tests/test_roadmap_gates.py`, unit tests built from dataclasses directly (the module's convention), plus one fixture-based case.

### Tests for this step

- `test_integration_decisions_paragraph_names_a_removed_id_in_live_prose` — feeds the checked-in `tests/fixtures/roadmap/integration-decisions-paragraph.md` body through the check with the removal record IPPT-18's fixture implies, and asserts one violation naming that id and the Decisions span. The fixture is read, never edited. The test is skipped-never: if the fixture is missing it must fail, not skip (a skipped pin would hide the entry-condition failure).
- `test_removed_id_in_live_prose_is_reported_with_artifact_id_and_span` — a hand-built body; the violation carries `artifact`, `row_id`, and a span anchor in the message.
- `test_whole_token_match_ignores_a_longer_id` — `entity-1-extra` in the body does not flag removed `entity-1`.
- `test_reference_inside_marked_historical_context_is_not_reported` — carve-out pinned by name: the marked historical block is exempt.
- `test_reference_inside_marked_rejected_alternative_is_not_reported` — the second carve-out, separately.
- `test_reference_inside_fenced_code_is_not_reported` — fence exempt; includes a `~~~` fence and an unclosed fence (spans to end of text) so the reused scanner's behavior is exercised, not assumed.
- `test_pruned_removal_record_is_deliberately_not_checked` — a predecessor removal absent from the candidate's `removals` produces no violation even when the id is named in live prose.
- `test_feedback_free_candidate_is_checked_against_predecessor_removals` — empty candidate `removals`, predecessor with a record; the live mention is reported.
- `test_first_run_with_no_removals_returns_no_violations` — `predecessor is None`, no removals, returns `[]`.
- `test_check_is_not_in_any_stage_gate_tuple` — asserts the function is absent from `DOMAIN_GATES`, `CONSTRAINTS_GATES`, `COMPONENTS_GATES`, and `PLANS_GATES`, so adding it cannot silently change stage behavior.
- `test_one_violation_per_id_per_span_not_per_mention` — two mentions in one paragraph yield one violation; a second paragraph yields a second.

Every test above must be green before this step is done. Verify the carve-out tests by mutation: temporarily make the check ignore the marker and watch the two marked-context tests go red.

## Acceptance criteria

- The entry condition holds: `tests/fixtures/roadmap/integration-decisions-paragraph.md` exists at HEAD before work starts, else the step stops and goes to the user.
- The new check returns a violation for the Integration fixture and `[]` for the marked-context, fenced, pruned, and first-run cases above.
- `rg 'check_removed_ids' plan_tool/roadmap_gates.py` shows the definition and no appearance in any `*_GATES` tuple.
- `run_domain_gates`, `run_constraints_gates`, `run_components_gates`, and `run_plans_gates` return the same results as before on every existing test; no existing test needs editing.
- `uv run pytest tests/test_roadmap_gates.py -q` is green.
- `tests/test_duplication.py` stays green (no new duplicate fence or token helper).
- Violation messages contain no line numbers or byte offsets.

## References

- [CommonMark Spec 0.31.2: Fenced code blocks](https://spec.commonmark.org/0.31.2/#fenced-code-blocks) — the opening and closing rules the reused scanner implements; read for the unclosed-fence and `~~~` cases.
- [pytest: How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — for folding the carve-out cases into one parametrized test.

## Applicable guardrails

- The plan's "## Scope guardrails": this step supplies evidence only. It does not rewrite prose and does not close feedback.
- The plan's "## Scope guardrails", remedy bullet: IPPT-18's prose-correction operation is not built or called here.
- The plan's "## Not allowed" list: the check decides on id presence only. No keyword matching, no quality or agreement check between prose artifacts, and no semantic "pending versus settled" judgment.
- The plan's "## Out of scope", behavior bullet: no stage tuple, refusal, or exit-code behavior changes in this step. Refusal wiring is step 5's.

## Deferred

- Wiring the check into the approval path (`seal_review`, `decide_structural_candidate`) — step 5 owns it.
- Evidence classes, the candidate-narrative module, and CLI display — later steps own them; this step cites none by symbol.
- Authoring or editing `tests/fixtures/roadmap/integration-decisions-paragraph.md` — IPPT-18 owns the fixture.
- Consolidating the duplicated frontmatter or fence helpers across modules — file in `BACKLOG.md` if noticed; not this step's work.

<!-- plan-tool-detail-deferrals
{"deferrals":[]}
-->
