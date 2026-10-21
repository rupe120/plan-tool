> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Tell the operator how many feedback rows await their review, and what to do about them in the artifact

## Summary

Add one advisory block to `plan_tool/cli/roadmap_cmd.py`: when a run wrote artifacts carrying feedback the model has answered, the summary says how many rows await the reviewer and names the actions the reviewer takes in their editor — close, reopen, defer, and (when the model answered with a question) amend the request in place and reopen. The count comes from step 6's `RoadmapResult` field; this step renders it and nothing else. The key design decision: **the block is emitted for both outcomes, like the overwrite advice** — a stage that answered feedback and wrote it before a later stage ran out of attempts still produced a response the reviewer needs to read. On green, a revision run ends with a line naming the count and the document-native next action, a first run prints nothing new, and the exit code is untouched by any count.

## Table of Contents

- [Summary](#summary) — what lands and what is observable on green.
- [Why](#why) — step 6 produces the count and nothing tells the human about it.
- [Input](#input) — the result contract step 6 hands this step, and what it deliberately does not carry.
- [Files (creates vs edits)](#files-creates-vs-edits) — two edits, no new files.
- [Implementation](#implementation) — where the block goes, what it says, and the wording that is not free to vary.
- [Tests](#tests) — the roster in `tests/cli/test_roadmap_cmd.py` and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the grammar the printed advice tells an operator to edit.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step.
- [Deferred](#deferred) — what steps 8–10 own, and what is deliberately not taken.

## Why

After step 6 a revision run writes the model's answers into the artifact and reports `feedback_awaiting_review` on `RoadmapResult` — and the operator's terminal says nothing about it. `plan_tool/cli/roadmap_cmd.py:_print_completed` lists the artifacts and the pending decisions, then `cmd_roadmap` prints the overwrite advice; a reviewer who wrote three requests into `01-domain.md` and re-entered at stage 1 sees the same output they saw before the feedback channel existed. They have to know to open the file and look for `proposed_response` fields to discover the loop worked. Worse, the one piece of advice the summary *does* give about re-entry — copy your hand edit aside, because `--from-stage N` rewrites artifact N — reads as a warning against exactly the thing this position wants them to do, since writing feedback into an artifact and re-entering at its stage is now the supported loop rather than a way to lose work. This step closes both gaps with one advisory block, and it is the last piece of the loop the human actually touches.

## Input

This step reads one contract from step 6 and three that already ship. Each must stay true.

- **Step 6 produces the count.** `RoadmapResult.feedback_awaiting_review` is an `int` defaulted to `0`, counting `awaiting-review` feedback rows across the artifacts the run wrote, read back off disk. It counts carried rows as well as rows this run transitioned, so the number is "how many are waiting on you", not "how many are new".
- **Step 6 decided there is no per-artifact breakdown.** The result carries one total, plus `overwritten_stages`, which names exactly the stages that revised an artifact. There is no map from a feedback id to the file that holds it, and this step does not add one — the ids live in the artifacts already listed in the summary.
- **Step 1 owns the lifecycle vocabulary.** `FeedbackState` with `OPEN = "open"`, `AWAITING_REVIEW = "awaiting-review"`, `DEFERRED = "deferred"`, and `FeedbackRow.proposed_response`. The printed advice names these states; take the words from the enum rather than typing them again (see [Implementation](#implementation)).
- **Step 2 decides what a re-entry preserves.** Every predecessor feedback row survives a revision with its `request` text untouched, and every design row survives or is dropped by a cited removal. That is what makes "re-enter at that stage to send a reopened row back" safe advice rather than a way to lose the row.
- **`_overwrite_summary_lines` is the shape to copy.** It takes the result, returns a `list[str]`, returns an empty list when there is nothing to say, and `cmd_roadmap` prints its lines for **both** outcomes with `plan_tool/style.py:detail`. Its docstring states the reason for the both-outcomes rule; the same reason applies here.
- **The exit-code convention.** `cmd_roadmap` returns 0 for a completed run and 1 for an exhausted one. A count is a finding, never a failure-to-complete, so nothing here touches the returned code.
- **What this step cannot verify.** Every case drives a stubbed `run_roadmap` or a stubbed invoker. It can prove the summary says the right thing about a given result; it cannot prove a reviewer finds the advice useful. Step 9's real-run exercise owns that.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/cli/roadmap_cmd.py` — add the feedback advisory helper and its call in `cmd_roadmap`, plus the import of step 1's lifecycle vocabulary. Extend the module docstring's paragraph about the review channel to say the summary now points at feedback awaiting review.
- `tests/cli/test_roadmap_cmd.py` — add the cases in [Tests](#tests), and extend the `_completed` builder and the `_e2e_domain_text` helper so a result and an artifact can carry feedback.

No edit is needed outside this list. `docs/cli/roadmap.md` is generated from the argparse parser and this step adds no flag, so it stays byte-for-byte the same and its drift guard in `tests/cli/test_cli_reference.py` stays green.

## Implementation

### What must be true when this is done

- A run that wrote at least one artifact holding an `awaiting-review` feedback row prints how many rows await the reviewer.
- The block names the actions the reviewer takes in the artifact: close by deleting the row, reopen by setting the state back to `open`, defer by setting it to `deferred`, and — when the response is a clarifying question — amend that row's `request` in place before reopening.
- The block says nothing about whether the model's response is any good.
- A run with a zero count prints nothing new — including a first run, which cannot have a predecessor.
- An exhausted run that wrote a revision before halting prints the block too.
- The exit code is exactly what it is at HEAD for every result.
- Nothing outside `plan_tool/cli/roadmap_cmd.py` and `tests/cli/test_roadmap_cmd.py` changes.

### Put it beside the overwrite advice, not inside `_print_completed`

Add `_feedback_summary_lines(result) -> list[str]` next to `_overwrite_summary_lines`, and call it from `cmd_roadmap` for both outcomes, before the overwrite lines.

- **Both outcomes, for the reason the overwrite block already states.** Stage 1 can revise `01-domain.md`, answer the reviewer's requests, and write the file; stage 2 can then spend its budget and halt. The response is on disk and the reviewer needs to read it, and it is no less real because the arc did not finish. `_print_completed` runs on one outcome only, so it is the wrong home.
- **Feedback first, overwrite second.** The feedback block is why the operator ran the revision; the overwrite block is a caution about what a *further* run would replace. Reading them in that order matches the order the reviewer acts in.
- **Empty list when the count is zero**, so the whole block disappears on a first run without a caller-side check — same as the overwrite helper.
- **Rejected alternative: `plan_tool/cli/console.py:_print_next_steps`.** Its `steps` argument is a list of `(command, description)` pairs and it renders each entry as a runnable command. The next action here is an editor action on a file, not a command, so that renderer would either print a command that does not exist or force this step to invent one — which the plan's fence forbids. Use `plan_tool/style.py:detail`, as the rest of this module's subordinate lines do.

### What the block says

Roughly three lines; the exact prose is the implementer's, but each of these facts has to land:

- **The count and where to look.** How many rows await review, and that the responses sit beside the requests in the artifacts already listed above. Say `proposed_response` by its field name — the reviewer is about to open YAML and that is what they will be scanning for.
- **The actions, in the reviewer's terms.** Close by deleting the row (git keeps the record). Reopen by setting `state` back to `open` and clearing or replacing the response. Defer by setting `state` to `deferred`, which keeps the row in the file and stops sending it as active guidance — its text still travels inside the artifact. And when the response is a question rather than a change, amend the row's `request` to answer it, then reopen: `request` is immutable to the *model*, not to the reviewer, and reopening an unchanged request only re-asks the same thing.
- **How to get another revision.** Re-enter at that artifact's own stage. This is the one place the advice differs from the pending-decision line a few lines above it, and the difference is real: a reopened row is sent again only by a run of the stage that owns it, and step 2's gates are what make that re-entry keep the row instead of regenerating over it. Do not repeat the copy-aside caution here, but do scope it where it is printed: `_overwrite_summary_lines` carries the copy-aside caution in **two** branches — the no-pointer branch's "copy it aside first if you edited it by hand" and the `rewritten_again` branch's "copy that aside first if you edited it by hand" — and both are now wrong as blanket advice, because a revision preserves ids, feedback rows, and settled decisions. Narrow **both** lines to what a revision does not preserve — free prose in the body, which no gate protects — and narrow `_print_completed`'s never-re-enter comment to pending decisions rather than feedback rows. Both live in `plan_tool/cli/roadmap_cmd.py`, which this step already owns.

Two wording rules that are not free to vary:

- **Never say the feedback was resolved, addressed, handled, or done.** The model proposed a response; whether it answered the request is the reviewer's call and the plan puts that judgment permanently out of scope. "Awaiting your review" is the whole claim the tool is entitled to make.
- **Name no command for closing a row.** Closing, deferring, and reopening all happen in the editor. A command in this block would be a command that does not exist.

### Take the state words from the vocabulary, not from your keyboard

Import `FeedbackState` from `plan_tool/roadmap_artifacts.py` and build the advice from `FeedbackState.OPEN.value` and `FeedbackState.DEFERRED.value` rather than typing `"open"` and `"deferred"` into the message.

- **Why:** the printed advice tells an operator to type a literal into YAML that step 1's parser then has to accept. A rename in the leaf silently makes this module's advice wrong, and nothing red fires. Sourcing the words from the enum turns that into a failing import or a failing test.
- **The import is already legal.** This module imports `RoadmapArtifactError` from the same leaf, and the one-way line `roadmap_artifacts.py → roadmap_gates.py → roadmap.py → cli/roadmap_cmd.py` puts the vocabulary below this module. No new dependency edge.
- **`AWAITING_REVIEW` is a different case.** It names a state the reviewer reads rather than types, so whether the message spells it out is a wording choice; the two states the reviewer *writes* are the ones worth binding.

### Latitude, and one caveat if you take it

- **Naming the revised artifacts in the block is optional.** `_artifact_filenames(result)` plus `overwritten_stages` gives you the filenames of exactly the stages that revised something, and the helper's docstring already explains why that lookup stays sound on an exhausted run. If you use it, do not phrase the line so it *claims* every awaiting-review row lives in those files — the count is taken across everything the run wrote.
- **Count-only is the simpler recommendation.** The artifacts are printed directly above the block, so pointing at "the artifacts above" costs the reader nothing.

### Constraints that are not free to vary

- **No TTY branch, no confirm, no prompt.** This module's docstring states the rule and this block is exactly where an interactive review walk is tempting: the tool now knows something is waiting for a human. It prints and returns.
- **The count never changes the exit code.** A completed run with twenty rows awaiting review exits 0.
- **The block reads the result, nothing else.** No file is opened, no artifact is re-parsed, no directory is scanned. `plan_tool/roadmap.py` already read the files back; this module renders what it was handed.
- **`_print_exhausted` keeps writing to stderr and the new block keeps writing to stdout**, matching the overwrite lines. Do not move either stream to match the other.
- **`cmd_roadmap`'s docstring is in this file and repeats the three-kind/pre-flight-cause list**, so it is an edit site here for the same reason the operator docs are step 8's. Widen it with step 6's fourth kind and step 5's added pre-flight causes.
- **The fourth failure kind needs an exhaustion report, and this step owns the printer.** Step 6 adds a rejection kind beside `FAILURE_INVOKE` / `FAILURE_PARSE` / `FAILURE_GATES`; `_print_exhausted` in this file branches on `FAILURE_GATES` and `FAILURE_INVOKE` only, so without an arm here a stage exhausting on the new kind prints `(<kind> failure)` and nothing actionable — no offending ids, no correction text, no next step. Add the arm: name the invented feedback ids and tell the operator the model authored rows it was not given, which is a model failure rather than anything in their artifact to fix. This is why `tests/cli/test_roadmap_cmd.py` is this step's file and not step 6's.
- **The pending-decision block stays where it is and says what it says.** The two advisories describe different things — a pending decision is the model's own unsettled guess, an awaiting-review row is its answer to something the reviewer wrote — and each has its own re-entry advice for a good reason. Leave the pending-decision line's own advice alone; the scoped correction above touches only the copy-aside caution and the never-re-enter comment.

## Tests

All cases go in `tests/cli/test_roadmap_cmd.py`. Reuse `_stub_run`, `_ns`, `_completed` / `_two_stage_completed` / `_exhausted`, and the `capsys` idiom the file already uses; keep the section-comment layout.

Two helper edits come first:

- `_completed` gains an `awaiting: int = 0` keyword forwarded as `feedback_awaiting_review=`. `_exhausted` needs no edit — it merges `**kwargs` into its base dict, so it already accepts the field.
- `_e2e_domain_text` gains an optional feedback argument so the integration class can stage an artifact carrying an open row and a reply carrying the answered one. Its existing no-argument callers must stay unchanged.

### Tests for this step

Approx. 17 new cases across two classes. Every one must be green before this step is done, and `tests/test_roadmap.py`, `tests/test_roadmap_gates.py`, `tests/test_roadmap_artifacts.py`, and `tests/test_run_log.py` must stay green **without being edited**.

New class `TestFeedbackAwaitingReview` (stubbed `run_roadmap`, like every other class here):

- `test_a_completed_run_with_awaiting_review_feedback_reports_the_count` — the number appears in stdout.
- `test_a_zero_count_prints_no_feedback_line` — the block is absent, including the word `feedback`.
- `test_a_zero_count_prints_nothing_even_when_a_stage_was_overwritten` — the overwrite block still prints; the feedback block does not.
- `test_an_exhausted_run_that_wrote_a_revision_still_reports_the_count` — the both-outcomes rule, mirroring `test_an_exhausted_run_that_overwrote_still_warns`.
- `test_an_exhausted_run_with_no_written_revision_reports_nothing`.
- `test_the_block_names_deleting_the_row_as_the_close_action`.
- `test_the_block_names_reopening_by_setting_the_state_back_to_open`.
- `test_the_block_names_deferring_the_row`.
- `test_the_printed_state_words_come_from_the_feedback_vocabulary` — the message contains `FeedbackState.OPEN.value` and `FeedbackState.DEFERRED.value` rather than hard-coded spellings.
- `test_the_block_points_at_the_proposed_response_field_by_name`.
- `test_the_block_never_claims_the_feedback_was_resolved` — none of "resolved", "addressed", "handled", "done" appears.
- `test_the_block_names_no_command_for_closing_feedback` — no `plan-tool` command in the feedback lines.
- `test_the_reopen_advice_points_at_the_artifacts_own_stage` — the re-entry advice names `--from-stage`.
- `test_awaiting_review_feedback_does_not_change_the_exit_code` — 0 for completed, 1 for exhausted, with a non-zero count on both.
- `test_the_feedback_block_precedes_the_overwrite_advice` — on a result carrying both, the count line's offset in stdout is lower.
- `test_the_feedback_block_and_the_pending_decision_line_both_appear` — a result carrying both prints both, and neither swallows the other.
- `test_the_command_module_makes_no_interactive_call` — read the module source; no `input(` and no `isatty`.

New class `TestFeedbackSummaryOverTheRealOrchestrator`, marked `@pytest.mark.integration` beside `TestOverwriteAdviceIsPrintedExactlyOnce` and following its stance — the layer-isolated tests on both sides passed once while a real run printed the same advice twice:

- `test_the_awaiting_review_line_appears_once_across_both_streams` — pre-write a domain artifact with an open feedback row, reply with the answered version, assert the count line appears exactly once in `out + err`.
- `test_the_printed_count_matches_the_rows_on_disk` — re-parse the written artifact and compare.

## Acceptance criteria

- `cmd_roadmap` over a completed result with `feedback_awaiting_review=3` prints a line containing `3` and the word `review` on stdout.
- The same result with `feedback_awaiting_review=0` prints no line mentioning feedback.
- An exhausted result with `feedback_awaiting_review=2` prints the block and still returns 1; a completed result with any count returns 0.
- The printed block contains the exact strings `FeedbackState.OPEN.value` and `FeedbackState.DEFERRED.value` resolve to, and contains `proposed_response`.
- The printed block contains none of "resolved", "addressed", "handled", "done", and no `plan-tool ` command string.
- On a result that both overwrote a stage and left feedback awaiting review, both blocks appear on stdout and the feedback block comes first.
- A real-orchestrator run over an artifact carrying one open feedback row prints the count line exactly once across stdout and stderr.
- `rg -n 'input\(|isatty' plan_tool/cli/roadmap_cmd.py` returns nothing.
- `rg -n '_print_next_steps' plan_tool/cli/roadmap_cmd.py` returns nothing.
- `uv run pytest tests/cli/test_roadmap_cmd.py tests/test_roadmap.py tests/test_roadmap_gates.py tests/test_roadmap_artifacts.py tests/test_run_log.py -q` is green, with the last four files unmodified.
- `uv run pytest tests/cli/test_cli_reference.py tests/test_duplication.py -q` is green, with no change to `docs/cli/roadmap.md` and no new `ALLOWED_DUPLICATE_GROUPS` entry.
- `git diff --name-only` lists exactly `plan_tool/cli/roadmap_cmd.py` and `tests/cli/test_roadmap_cmd.py`.

## References

- [YAML 1.2.2](https://yaml.org/spec/1.2.2/) — the frontmatter grammar the reviewer edits by hand when they act on this advice, which is why the block names field and state values exactly as they must be typed.

## Applicable guardrails

- **The plan's "## Out of scope", no TTY walk, confirm, or new feedback subcommand.** This binds this step hardest: it is the first surface that knows a human is needed, and the whole answer is to print and return. No prompt, no confirm, no new verb.
- **The plan's "## Out of scope", no judging whether a revision honored feedback and no automatic transition out of awaiting-review.** The summary reports a count and names actions. It rates nothing and changes no state.
- **The plan's "## Out of scope", no second store or hidden feedback state.** The block reads the result the orchestrator handed it. It opens no file and writes nothing.
- **The plan's "## Out of scope", no cap or rejection keyed on feedback count.** A large count is printed, never trimmed, warned about, or turned into a failure.
- **The plan's "## Out of scope", cross-artifact propagation.** The block describes the artifacts this run wrote and points the reviewer at the stage that owns a row. It never suggests an instruction in one artifact reaches another.
- **The plan's "## Architecture", `cli/roadmap_cmd.py` only renders the operator summary.** No counting, no parsing, no policy — every fact printed arrives on `RoadmapResult`.
- **The plan's "## Architecture", the one-way dependency line.** Importing the lifecycle vocabulary from `plan_tool/roadmap_artifacts.py` runs with that line, not against it.
- **The plan's "## Acceptance criteria", first-run behavior unchanged.** A run with no predecessor prints exactly what it prints at HEAD.

## Deferred

- **Documenting the feedback lifecycle, the human-close action, and this summary block for operators** — step 8, in `ROADMAP_FORMAT.md`, `RUNBOOK.md`, `USE_CASES.md`, and `CAPABILITIES.md`.
- **Recording whether real reviewers found the advice usable** — step 9's real-run exercise. Stubbed results prove the block says what it should, not that it helps.
- **Reconciling BACKLOG #208 and sweeping the architecture description** — step 10.
- **Naming which artifact holds which feedback id** — not taken. Step 6 decided the result carries one total and no per-row location; adding a breakdown means a new result field, which is a plan-level decision.
- **A `--json` or machine-readable summary for the roadmap verb** — not taken; no such surface exists on this command and nothing in this position needs one.
- **Reporting pending decisions on an exhausted run** — not taken. `_print_exhausted` has never printed them; it predates this position and has nothing to do with feedback. If it matters it is a `BACKLOG.md` entry, not a widening of this step.
- **Folding this advisory in with `plan_tool/cli/inspect.py:_print_pending_decisions`** — not taken. That renders concept-scope deferrals from `check_concept_coverage` over a `Plan`; it shares the "something awaits a human, print it, never change the exit code" shape and no data, so there is nothing to consolidate.
- **Any model-driven close, defer, or reopen, and any summary claim about response quality** — permanently outside this position by the plan's "## Out of scope". A finding proposing one is invalid, not deferred.
