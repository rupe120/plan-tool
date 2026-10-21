> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Write the revision the model returned, and leave every feedback row for the human to close

## Summary

Turn the revision loop into a real write: `plan_tool/roadmap.py` persists the model's gate-cleared artifact with its feedback rows intact, records one `RevisionFeedbackDelivered` run-log event per written revision, and reports how many rows now await the reviewer on `RoadmapResult`. The whole change lives in `run_roadmap`'s stage loop plus two small helpers; no new file, no new stage-table field, no new import beyond `hashlib`. The key design decision: **the orchestrator never edits a feedback row** — it does not flip a state, does not clear an answered row, and does not put back a row the model dropped; writing the artifact that cleared step 2's gates is how the `open` → `awaiting-review` transition lands on disk. On green, a re-run over a roadmap carrying reviewer feedback writes an artifact where every request still reads as the reviewer wrote it and every answered row carries the model's response, the run log proves which ids were delivered and against which prior bytes without holding a word of either text, and a first run behaves exactly as it does today.

## Table of Contents

- [Summary](#summary) — what lands and what is observable on green.
- [Why](#why) — steps 1–5 built the loop; nothing has written one yet.
- [Input](#input) — the contracts steps 1, 3, 4, and 5 hand this step.
- [Files (creates vs edits)](#files-creates-vs-edits) — two edits, no new files.
- [Implementation](#implementation) — the write rule, the delivery event, the result field, and the repairs not to add.
- [Tests](#tests) — the roster in `tests/test_roadmap.py`, the one case this step rewrites, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the docs bearing on the digest and the lifecycle.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step.
- [Deferred](#deferred) — what steps 7–10 own.

## Why

After step 5, a revision runs end to end and nothing records that it happened. The reviewer's rows reach the prompt, the three predecessor gates judge the reply, and `_write_artifact` puts the result on disk — but no test says the feedback survived that write, the `RevisionFeedbackDelivered` event step 3 minted has no caller, and `RoadmapResult` cannot tell `plan_tool/cli/roadmap_cmd.py` that anything is waiting for a human. The gap that matters most is the one nobody would notice: the obvious "finish the loop" move is to clear answered feedback after a successful write, so the next re-entry does not resend it. That would delete the reviewer's request before they ever read the response to it, and it is the exact failure this position exists to prevent — the plan's answer is that only a human removes a row, and the reason the loop still does not accumulate is that step 4 sends only `open` rows as active guidance. This step makes the write honest, records the delivery, and pins the negative behavior so a later author does not add the cleanup that feels missing.

## Input

This step reads contracts steps 1, 3, 4, and 5 land, plus three that already ship. Each must stay true.

- **Step 5 produces the predecessor snapshot.** Before any stage runs, `run_roadmap` holds one optional `_LoadedArtifact` per stage-to-run, carrying the prior artifact's on-disk `text` and its parsed `artifact` from a single read. This step reads both: the text for the digest, the parse for the ids and counts. It loads nothing itself.
- **Step 3 produces the run-log event.** `RunLogWriter.revision_feedback_delivered` takes keyword-only `phase`, `stage`, `predecessor_digest`, `feedback_count`, `feedback_ids`, and `counts_by_state`, bounds the id list itself, and never raises `RunLogLineTooLarge`. It hashes nothing — the digest arrives as a string. Its `**extra` bag is the one text channel step 3 could not close, and closing it is this step's contract.
- **Step 4 decides what the model is asked for.** Only `open` rows go into the active-feedback block; `awaiting-review` and `deferred` rows reach the model only inside the prior-artifact text. That is why no cleanup is needed after a write, and it is the fact any "the loop will resend forever" objection has to be checked against.
- **Step 2 decides what an acceptable revision is.** By the time an artifact reaches the write, the gates have already checked that every feedback row survived with its source text untouched, that the only state move was `open` → `awaiting-review`, and that every dropped design row carries a cited removal. This step adds no check of its own and re-reports nothing.
- **Step 1 owns the vocabulary.** `FeedbackState` (`open` / `awaiting-review` / `deferred`), `FeedbackRow.state`, and the `feedback` collection defaulting to `()` on both artifacts. The counts this step emits use those values as their keys; `plan_tool/run_log.py` deliberately holds no copy of them.
- **`_write_artifact` is the one writer and already writes the renderer's output.** It renders the parsed artifact, writes atomically, and returns `(path, replaced)`. Step 1's round-trip property is what makes the feedback rows survive that render, so this step changes nothing about how bytes reach disk.
- **`_pending_decision_count` is the shape to copy for counting.** It reads `getattr(artifact, "decisions", ())` off the artifact **read back from disk**, so the number describes the file rather than the model's reply, and it asks no stage which artifact it is holding.
- **`RoadmapResult` is constructed by keyword everywhere, including `tests/cli/test_roadmap_cmd.py`'s `_completed` / `_exhausted` builders.** A new field with a default keeps that file — which this step does not own and must not edit — compiling and green.
- **What this step cannot verify.** Every case here drives canned replies. It can prove the artifact on disk holds what the model returned and that the log holds no text; it cannot prove a model writes a useful response. Step 9's real-run exercise owns that.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/roadmap.py` — add the artifact-digest helper, the awaiting-review counter, the delivery emit in `run_roadmap`'s stage loop, and one defaulted `RoadmapResult` field. Add the `hashlib` import. Correct the module docstring and `RoadmapResult`'s docstring to describe the revision write.
- `tests/test_roadmap.py` — add the cases in [Tests](#tests), and rewrite the one case named there.

No edit is needed outside this list: step 3 already registered the event in `plan_tool/data_contract.py` and documented it in `DATA_CONTRACT.md`, and `plan_tool/cli/runs.py` renders any event kind generically.

## Implementation

### What must be true when this is done

- A revision that clears its gates lands on disk with every feedback row the predecessor had, each request's text unchanged up to trailing whitespace (the normalization `check_feedback_integrity` applies — step 2), each answered row carrying `state: awaiting-review` and its `proposed_response`, and each `deferred` row exactly as it was.
- The orchestrator changes no field of any feedback row on the way to disk.
- Each stage that writes a revision emits exactly one `RevisionFeedbackDelivered` event, inside that stage's phase, naming the stage, the digest of the prior artifact's bytes, the delivered ids, and the counts by state.
- No feedback request or proposed response appears anywhere in the run log.
- A first run emits no delivery event and behaves exactly as it does today.
- `RoadmapResult` reports how many feedback rows await review across the artifacts this run wrote.
- Nothing outside `plan_tool/roadmap.py` and `tests/test_roadmap.py` changes.

### The write already preserves the lifecycle — the work is not adding a repair

`_write_artifact` renders the artifact the gates accepted, so after steps 1–5 the rows already survive. Keep it that way, and write the reasons down in the code, because all three repairs below look like finishing the job:

- **Do not normalize feedback states after the gates pass.** An `open` row that the model left `open` never reaches the write — step 2 rejects it and the attempt retries. Code that flips it would only ever run on an artifact the gates already refused, which means it exists to smuggle one past them.
- **Do not put back a feedback or design row the model dropped.** Same reasoning, worse effect: the gate exists so a model that ignored the reviewer fails visibly. A repair pass would write a file that looks obedient and hide the fact that the response does not match it.
- **Do not clear, close, or defer an answered row after writing.** This is the one the step is named for. It reads as housekeeping — "the model answered it, so stop resending it" — and it deletes the reviewer's request before they have read the response. Nothing needs to stop the resend: step 4 sends only `open` rows, so an `awaiting-review` row is carried in the artifact and never re-delivered as active guidance. The reviewer closes it by deleting the row in their editor, which the next run sees as an absence in the predecessor and therefore never questions.
- **State the division in the module docstring**, beside the existing "Disk is the interface between stages" paragraph: the model may propose a response; only a human may remove, defer, or reopen a row. A reader who does not find that rule in the code will add one of the three repairs above.

### Emit the delivery once per written revision

Put the emit in `run_roadmap`'s stage loop, right after `_write_artifact` returns and before `phase_end`, and only when that stage had a predecessor.

- **Once per written revision, not per attempt.** Per-attempt delivery is already visible through `claude_call_start`, and step 3 dropped an `attempt` field for this reason. A stage that spends its budget writes nothing, so it delivers nothing to record — the evidence for that run is its `gate_violations` lines and the exhaustion report.
- **`run_roadmap`'s loop is the right site, not `_run_stage`.** `_run_stage` runs per attempt and does not know whether the write happened; the loop has the predecessor entry, the stage, the phase string, and the writer already in hand.
- **The delivered set is the predecessor's whole feedback inventory**, not just its `open` rows. The model saw every row — the whole prior artifact is in the prompt — and `counts_by_state` only says something when the non-active rows are counted. A reviewer asking "did this run see all three of my requests, and which were active?" reads the ids beside the counts; `counts_by_state["open"]` recovers the active subset.
  - **Rejected alternative:** ids limited to the `open` rows. Then `counts_by_state` has exactly one possible shape and carries no information, and a `deferred` row the reviewer forgot about is invisible.
  - **The event's counts and the printed count are measured at different moments, and both are right.** `counts_by_state` describes the artifact **as delivered** — measured on the predecessor, before the revision, so a row this run answers still counts `open`. `RoadmapResult.feedback_awaiting_review` describes the artifact **as written**, read back off disk. A run that answers two requests therefore logs `{open: 2, awaiting-review: 0}` and prints that 2 rows await review; that is not a contradiction, and the docs must say which is which or it reads as one.
  - **`counts_by_state` carries every lifecycle state, zeros included** — all three of `open`, `awaiting-review`, `deferred`, always. A reader of one JSONL line can then compare states without knowing which were present, and the "recover the active subset" reading above holds unconditionally: `counts_by_state["open"]` is always a key lookup, never a `.get` against a missing state. A sparse map would make an absent key mean "zero" in the log and "unknown" in every other reader.
- **Measure the counts on the predecessor, before the revision.** The event records what went out, so a row answered by this run counts as `open`. What resulted is on disk and in git.
- **Digest the predecessor's bytes as read.** One small helper over `_LoadedArtifact.text`, `hashlib.sha256(...).hexdigest()` — the full hex, not a prefix. It identifies the exact document the reviewer edited and the model was shown, which a re-render or the model's reply would not. `plan_tool/review_persistence.py` uses the full digest and `plan_tool/telemetry.py` truncates for display; there is no display constraint here and one 64-character string is nothing against the run log's 4096-byte line cap.
- **Emit even when the predecessor carries no feedback rows** — `feedback_count` 0, empty ids, and `counts_by_state` still carrying all three lifecycle states at zero (not an empty map — the all-states rule holds unconditionally, which is what lets a reader index it without a `.get`). The event is the only record that a *revision* landed and against which bytes, which is what tells a reviewer whose edit did not save apart from a run that had nothing to deliver.

### Keep the text out, including out of `**extra`

Step 3 shipped an event whose own fields cannot hold a request or a response; the remaining hole is the emit helper's `**extra` bag, and this producer is the only caller.

- **Pass no `**extra` keys carrying artifact content.** The phase and stage are enough.
- **Pin it against the whole file, not against the event's fields.** Drive a run whose request and proposed-response strings are distinctive sentinels and assert neither appears anywhere in the JSONL — that catches a leak through `extra` and through any other event the run writes.

### What the result reports

- **Add one defaulted field:** `feedback_awaiting_review: int = 0`, placed after `overwritten_stages` so every field below it keeps its default. It counts `awaiting-review` rows across the artifacts this run wrote, computed from the artifact **read back from disk**, exactly as `pending_decisions` is.
- **Both result constructions carry the field, not just the completed one.** Step 7 prints the block on a completed *and* an exhausted run, because a stage can answer feedback and write it before a later stage spends its budget; if only the completed path populates the field, that advisory is a guaranteed zero on exactly the run where the reviewer most needs it. A two-stage run whose first stage writes a revision and whose second exhausts must still report the first stage's `awaiting-review` count.
- **Count carried rows too, not just rows this run transitioned.** A row that has been waiting through two runs is still waiting for the same human. Reporting only the new ones would quietly hide the older ones, and telling them apart needs a comparison against the predecessor that no consumer asked for.
- **One way to compute it:** a sibling of `_pending_decision_count` reading `getattr(artifact, "feedback", ())` and comparing `state` to `FeedbackState.AWAITING_REVIEW`. The two bodies differ in their attribute names and enum member, so `tests/test_duplication.py` — which normalizes past docstrings, function names, and parameter names, and compares string literals — sees no duplicate group.
- **Do not add a second field listing which stages were revisions.** `overwritten_stages` already names exactly those stages: a stage has a predecessor when its artifact was on disk at pre-flight, and `_write_artifact` sets `replaced` from the same file existing at write time. Pin the one-way containment with a test — every stage that wrote a revision is recorded overwritten — rather than shipping a field that always equals another one. Step 7 has both facts it needs: the count here and the stage numbers there.

### Constraints that are not free to vary

- **The event fires only after a successful write.** Emitting at prompt time would record a delivery for a stage that then exhausted its budget and left the prior artifact in place, which reads as "the model answered your feedback" when nothing changed.
- **Model-authored feedback is refused in the attempt loop, as a fourth rejection kind — not at the write.** Gate 2 ships no invented-feedback rule (step 2 assigns the defect here), and every predecessor-derived rule is inert without one, so a stage with **no** predecessor — a first authoring run, or a constraints stage authoring fresh after the reviewer deleted the artifact — could otherwise emit `feedback` rows and cited `removals` with nothing to reject them, and on the next run they are indistinguishable from the reviewer's.
  - **Why the attempt loop and not the writer.** `_run_stage` has one call site, inside the stage loop, and only ever parses a model reply; `_load_and_regate_below` never enters it. So the loop already distinguishes "this run generated these bytes" from "the reviewer's rows on a below-stage artifact", and it already owns a correction channel. A refusal at the write sits *after* the loop returned a gate-cleared artifact: it could feed no correction, would match none of `FAILURE_INVOKE` / `FAILURE_PARSE` / `FAILURE_GATES`, and has no member in the closed `completed` / `stage-exhausted` outcome vocabulary — a dead end that spends the reply and reports nothing usable.
  - **The shape.** Add a fourth failure kind beside the existing three, raised when a parsed reply carries **a feedback row or a `removals` record** absent from its predecessor — or, on a predecessor-free stage, any of either. Both halves are required, and the removal half is the sharper one: gate 1's always-on rules check only a non-blank rationale, a non-empty `feedback_ids` list, and that the removal names no present row, while "each cited id names an `open` predecessor feedback row" is predecessor-derived and therefore inert exactly where this kind is needed. A fabricated removal that reaches disk becomes carried history no later revision re-judges, and its always-on `VIOLATION_REMOVAL_NAMES_A_PRESENT_ROW` then permanently blocks re-declaring the row it names. It is **retryable**, with its own correction text naming the offending ids and telling the model that feedback rows and removal records are the reviewer's and may only be carried, never authored. It consumes an attempt like a gate violation does, and a stage that spends its budget on it exits `stage-exhausted` with the artifact unchanged.
  - This keeps step 6's "adds no check of its own and re-reports nothing" true of the *write*, which is the claim that sentence is about.
- **The emit sits inside the phase.** `phase_start` … `revision_feedback_delivered` … `phase_end`, so `runs show` groups it with the stage that produced it.
- **A logging failure must not break the run.** The bounding is step 3's; add no size check, no truncation, and no cap of your own here.
- **No branch on which stage is running.** The predecessor, the digest, and the counts all come from a stage row's own snapshot, so `RoadmapStage` gains no field and the loop gains no stage-identity comparison.
- **First-run behavior is unchanged.** No predecessor means no event, no digest, and a zero count — the same prompts, the same writes, the same result as HEAD.

## Tests

All new cases go in `tests/test_roadmap.py`, in the file's existing section-comment layout. Reuse `_Env.write_domain` / `write_constraints` to stage a predecessor, `_StubInvoker` for canned replies, `env.run_log_events()` for the log, and the `feedback_row(...)` / `removal(...)` / `_predecessor(...)` helpers steps 4 and 5 added to this file — do not mint second copies. Cases driving the real gate sets go under `@pytest.mark.integration`, beside `TestReEntryAgainstTheRealGateSets`.

### Tests for this step

Approx. 34 new cases plus 1 rewritten. Every one must be green before this step is done, and `tests/test_roadmap_artifacts.py`, `tests/test_roadmap_gates.py`, `tests/test_run_log.py`, and `tests/cli/test_roadmap_cmd.py` must stay green **without being edited**.

Rewritten (red once the event is emitted):

- `test_no_new_run_log_event_is_emitted` — step 5 added it to assert a revision run writes only the event kinds a first run writes. A revision now legitimately writes one more, so it becomes `test_a_first_run_emits_no_delivery_event`, which keeps the half that is still true.

The written artifact keeps the lifecycle:

- `test_a_written_revision_keeps_every_feedback_row` — re-parse the file; the ids equal the predecessor's.
- `test_a_request_reads_on_disk_exactly_as_the_reviewer_wrote_it`.
- `test_an_answered_row_lands_as_awaiting_review_with_its_response`.
- `test_a_deferred_row_is_written_back_unchanged`.
- `test_the_orchestrator_changes_no_feedback_state_on_the_way_to_disk` — the file's feedback rows equal the model's parse.
- `test_a_cited_removal_lands_with_its_rationale_and_citation`.
- `test_nothing_is_cleared_after_a_successful_revision` — the headline negative.
- `test_a_second_revision_carries_the_answered_row_again` — two runs back to back; the row survives the second and is absent from its active-feedback block.
- `test_a_model_that_dropped_feedback_never_reaches_disk` — real gates; the stage exhausts and the file is unchanged.

The human owns the close:

- `test_a_row_the_human_deleted_before_the_run_is_not_restored`.
- `test_a_reopened_row_is_delivered_again_and_gets_a_fresh_response`.

The delivery event:

- `test_a_written_revision_emits_one_delivery_event`.
- `test_the_event_names_its_stage_and_phase`.
- `test_the_digest_is_the_sha256_of_the_predecessor_bytes` — the bytes read off disk, not a re-render and not the reply.
- `test_the_event_carries_every_predecessor_feedback_id`.
- `test_the_counts_are_keyed_by_lifecycle_state`.
- `test_the_counts_describe_the_predecessor_not_the_written_artifact` — an answered row counts as `open`.
- `test_a_revision_with_no_feedback_still_emits_a_zero_count_event`.
- `test_an_exhausted_stage_emits_no_delivery_event`.
- `test_a_reply_inventing_a_feedback_row_is_rejected_and_retried` — the fourth rejection kind consumes an attempt and its correction text names the invented id.
- `test_a_predecessor_free_stage_rejects_any_model_authored_feedback_row` — the first-run/fresh-authoring case, which no gate can see.
- `test_the_event_fires_once_for_a_stage_that_needed_two_attempts`.
- `test_a_full_re_run_emits_one_event_per_revised_stage`.
- `test_the_event_lands_between_its_phase_start_and_phase_end`.
- `test_no_request_or_response_text_appears_anywhere_in_the_run_log` — sentinel strings over the whole JSONL.
- `test_a_large_feedback_set_still_writes_one_line_and_does_not_raise`.

The result contract:

- `test_feedback_awaiting_review_counts_the_written_artifacts_rows`.
- `test_a_carried_awaiting_review_row_is_counted_too`.
- `test_feedback_awaiting_review_is_zero_on_a_first_run`.
- `test_feedback_awaiting_review_sums_across_both_stages`.
- `test_an_exhausted_stage_contributes_nothing_to_the_count`.
- `test_every_stage_that_wrote_a_revision_is_recorded_overwritten`.
- `test_the_new_result_field_is_defaulted` — what keeps `tests/cli/test_roadmap_cmd.py` unedited.

Across stages and end to end (integration, real gate sets):

- `test_a_stage_one_revision_hands_stage_two_the_revised_artifact`.
- `test_stage_one_feedback_is_not_stage_twos_active_feedback` — the plan's locality rule, checked on stage 2's prompt.
- `test_a_redirect_dropping_a_row_completes_with_its_cited_removal_on_disk`.

No new surface:

- `test_prompt_bytes_is_still_recorded_for_a_revision_attempt` — the budget advisory path below `plan_tool/shell.py:claude_invoke` is untouched and never fails a run.
- `test_a_synthetic_stage_without_feedback_writes_and_logs_normally` — the `getattr` default, through `TestSyntheticThirdStage`'s table.
- `test_run_is_non_interactive` stays green unchanged.

If any case other than the rewritten one needs an edit to pass, that is the signal that the write path is changing something it should only be carrying.

## Acceptance criteria

- After a revision run, re-parsing the written artifact yields feedback rows whose ids equal the predecessor's, whose `request` strings match the predecessor's under the same trailing-whitespace normalization `check_feedback_integrity` uses — assert it that way, not with a bare `==`, or the assertion is stricter than the gate that let the artifact through — and whose `deferred` rows are identical to the predecessor's.
- A row the model answered reads `state: awaiting-review` on disk with a non-blank `proposed_response`; no row's state differs from the model's reply.
- A run whose reply drops a feedback row writes nothing for that stage and leaves the file on disk unchanged.
- Each stage that wrote a revision produces exactly one `revision_feedback_delivered` line; a first run and an exhausted stage produce none.
- That line's `predecessor_digest` equals `hashlib.sha256(<the file's bytes before the run>).hexdigest()`, its `feedback_ids` hold every predecessor feedback id, and its `counts_by_state` keys are step 1's state values.
- A run whose feedback request and proposed response are distinctive sentinel strings writes a run log containing neither sentinel.
- A predecessor carrying 200 feedback rows still writes one line per revised stage, under 4096 bytes, and raises nothing.
- `result.feedback_awaiting_review` equals the number of `awaiting-review` rows across the files this run wrote, and is `0` on a first run.
- Every stage number in `result.overwritten_stages` covers every stage that wrote a revision.
- `RoadmapResult(outcome=…, artifacts=…, stages_run=…, pending_decisions=…, overwritten_stages=…)` still constructs, and `tests/cli/test_roadmap_cmd.py` passes unmodified.
- `rg -n 'stage\.(name|number) ==' plan_tool/roadmap.py` returns nothing, and `RoadmapStage` declares no new field.
- `rg -n 'input\(|isatty' plan_tool/roadmap.py` returns nothing.
- `rg -n 'suppress_prompt_budget_backstop' plan_tool/roadmap.py` returns nothing.
- `uv run pytest tests/test_roadmap.py tests/test_roadmap_gates.py tests/test_roadmap_artifacts.py tests/test_run_log.py tests/cli/test_roadmap_cmd.py -q` is green, with the last four files unmodified.
- `uv run pytest tests/test_duplication.py -q` is green with no new `ALLOWED_DUPLICATE_GROUPS` entry.
- `git diff --name-only` lists exactly `plan_tool/roadmap.py` and `tests/test_roadmap.py`.

## References

- [Increase output consistency — Claude Docs](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency) — why a closed lifecycle vocabulary written back unchanged is what makes the review state readable across runs.
- [Prompt caching — Claude Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) — why identifying the prior artifact by a digest of its exact bytes is the useful record when revision prompts are later measured.
- [YAML 1.2.2](https://yaml.org/spec/1.2.2/) — the frontmatter grammar the written artifact is re-rendered into and re-parsed from on the read-back.

## Applicable guardrails

- **The plan's "## Out of scope", no automatic transition out of awaiting-review and no judging whether feedback was honored.** This binds this step hardest: the write path is exactly where closing an answered row feels like finishing the loop. Write what the gates accepted and nothing else.
- **The plan's "## Acceptance criteria", the reviewer closes feedback by removing it.** Deleting a row before a run is a human close, and this step must leave that reading intact — the run sees an absence in the predecessor and asks nothing about it.
- **The plan's "## Out of scope", no second store, sidecar, or hidden feedback state.** The run-log event is evidence that a delivery happened; nothing in it may be read back as review state by a later run. The artifact stays the only place that state lives.
- **The plan's "## Out of scope", no cap or rejection keyed on feedback length, shape, count, or semantics.** The id list's byte budget bounds a log line only. Nothing here counts, trims, or refuses feedback, and the prompt-budget advisory stays the only pressure signal.
- **The plan's "## Out of scope", cross-artifact propagation.** A stage's delivery event and its awaiting-review count read that stage's own artifacts. An upstream artifact's feedback never counts toward a later stage.
- **The plan's "## Out of scope", no TTY walk, confirm, or new command.** A run that has both versions in hand still asks nothing.
- **The plan's "## Out of scope", optimistic write conflicts.** No lock, no mtime check, no re-read before the write.
- **The plan's "## Architecture", a stage is data and the revision wrapper is shared.** Everything added here is computed from a stage row's own snapshot; the loop gains no branch on which stage it is running.
- **The plan's "## Architecture", the one-way dependency line.** `plan_tool/roadmap.py` reads the artifact and gate leaves and calls down into `plan_tool/run_log.py`; nothing here reverses that, and the lifecycle vocabulary stays in `plan_tool/roadmap_artifacts.py`.
- **The plan's "## Acceptance criteria", first-run behavior unchanged.** No predecessor means no event, no count, and the same bytes on disk as HEAD.

## Deferred

- **Printing anything about feedback awaiting review** — step 7, in `plan_tool/cli/roadmap_cmd.py`. This step supplies the count and leaves the operator summary alone.
- **Documenting the lifecycle, the human-close action, and the delivery event for operators** — step 8, which reads whatever actually lands here.
- **Measuring real redirect and clarification feedback, prompt bytes, advisory level, and retry counts** — step 9. Canned replies prove the write preserves what it was given, not that a model responds well.
- **Reconciling BACKLOG #208 and sweeping the architecture description** — step 10.
- **Any model-driven close, defer, or reopen** — permanently outside this position by the plan's "## Out of scope" first bullet. A finding proposing one is invalid, not deferred.
- **Comparing the written artifact to the predecessor and reporting a diff to the operator** — not taken. Git already shows the diff, and summarizing it is a judgment about whether the revision was good.
- **A per-attempt delivery event** — not taken; step 3 dropped `attempt` for the same reason, and `claude_call_start` already records each attempt.
- **Naming the new event's fields in `plan_tool/cli/runs.py`'s `runs show` extras allowlist** — step 3 routed it to `BACKLOG.md`; the line renders by kind today.
- **Deriving `_write_artifact`'s `replaced` flag from the predecessor snapshot** — still not taken. Step 5 declined it as a behavior-preserving refactor riding inside a feature step; the containment test is the answer instead.
- **Calibrating `MAX_STAGE_ATTEMPTS` for the larger revision prompt** — BACKLOG #215's separate decision, per the plan's Deferred list.
