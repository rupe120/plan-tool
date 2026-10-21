> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 9 — Run the feedback loop against a real brief and record the reviewer's outcomes in `BACKLOG.md`

## Summary

Drive the shipped revision loop once against a real concept brief, with at least two feedback rows a human actually wrote — one domain redirect and one genuinely ambiguous request — and write what happened into `BACKLOG.md` as a dated measurement block. The record names the commands, the two requests, the model's response per feedback id, and the reviewer's own verdict on each; it also carries the operational numbers (attempts per stage, `prompt_bytes`, advisory level, cost) and an id-continuity observation against the 85/60/30/25 regeneration baseline. The key design decision: **the record lives in `BACKLOG.md`, not a new `docs/` file** — the artifacts, the brief, and the run logs are all gitignored, so a backlog block is the only durable carrier, and the repo already records real `roadmap` runs exactly this way (#208's "First real run, 2026-08-01" bullet, #215's two measurement tables). On green, a reader who never ran the loop can see what a human asked for, what the model proposed back, whether the human accepted it, and what the run cost — and nothing in the record gates anything.

## Table of Contents

- [Summary](#summary) — what the exercise produces and where it lands.
- [Why](#why) — the loop's whole claim is about a human, and no test can see one.
- [Input](#input) — what steps 6 and 7 hand this step, what is on disk today, and what one reading cannot prove.
- [Files (creates vs edits)](#files-creates-vs-edits) — one edit; everything else stays scratch.
- [Implementation](#implementation) — the fixture, the two feedback items, the reading rule, and where the block goes.
- [Tests](#tests) — the substitute verification for a non-code step.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the docs bearing on the revision prompt and the run's numbers.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step.
- [Deferred](#deferred) — what step 10 owns, and what is deliberately not measured.

## Why

Steps 1–7 build a loop whose whole value is a claim about a person: that a reviewer can write an ordinary sentence into an artifact, re-enter at that stage, and get back a proposal they can judge. Every test in this plan is hermetic and drives canned responses through the real parser and gates — which proves the contract is satisfiable, and proves nothing about whether a real model does something useful with a real request, or whether a real reviewer can read the result. That gap is structural, not an authoring shortcut: there is no assertion that can see "the human understood the response and agreed with it."

The repo also has one measurement that reads as this loop's obstacle and has never been re-measured under it. #208's id-stability bullet records two `--from-stage 1` runs on an identical brief sharing 85% of entity ids, 60% of workflow, 30% of business-rule and 25% of decision ids, with **0 of 11** shared entities keeping the same field-name set — the reason feedback naming a row could not survive the re-proposal it was feedback on. This step is where somebody points the shipped loop at that same brief and writes down what actually comes back.

## Input

This step consumes what steps 6 and 7 land, plus three facts about the tree that are true at HEAD. It reads names **off the landed modules**, not out of this file — a name written while a step was being planned is a proposal, and the landed name wins on any disagreement.

- **Step 6 produces the count and the write.** A revision run writes the model's answers into the artifact and reports how many feedback rows now await the reviewer on `RoadmapResult` (`feedback_awaiting_review` as proposed). It also emits one `RevisionFeedbackDelivered` run-log event per written revision, carrying stage, predecessor digest, feedback ids, and counts by state — and deliberately no request or response text. That event is the record's proof of *delivery*; the artifact is the proof of *content*.
- **Step 7 produces the operator's view.** The completion summary in `plan_tool/cli/roadmap_cmd.py` gains a block naming the count and the three document-native actions. It sits beside the existing `_print_completed` and `_overwrite_summary_lines` output. Capture that block verbatim — whether it told the reviewer enough is part of what this exercise measures.
- **Steps 1–5 own the artifact shape.** The feedback collection, its lifecycle vocabulary (`open` / `awaiting-review` / `deferred`), the target union (artifact-level vs a `row_id`), `proposed_response`, and the removal records live in `plan_tool/roadmap_artifacts.py`. If step 8's `ROADMAP_FORMAT.md` section has landed by execution time, write the feedback rows from **that** doc rather than from the module — a reviewer following the shipped documentation is closer to the thing this step is trying to observe, and any place the doc misleads is itself a finding worth recording.
- **The brief the plan names is local and gitignored.** `.tmp/roadmap-smoke.cfp-concept.md` (124 lines, a volunteer-run conference call-for-proposals) is the brief. `.tmp/` is gitignored, so the record must stand on its own: quote enough of each request that a reader who cannot open the brief can still judge the response.
- **The artifacts already sitting in `.tmp/roadmap-smoke-plans/` cannot be the predecessor.** They predate the `EntityRow.fields` contract and no longer parse: `load_domain_artifact` on `.tmp/roadmap-smoke-plans/roadmaps/cfp-review/01-domain.md` raises `RoadmapArtifactError: 'entities' row 'proposal' is missing required key 'fields'`. Step 5's pre-flight treats a present-but-unreadable predecessor as an error rather than "no predecessor", so pointing the exercise at that directory fails before any call is made. The exercise starts from a fresh baseline run.
- **What one reading cannot prove.** This is n=1 — one brief, one reviewer, one pass. It cannot give a hit rate, a failure rate, or a comparison against anything. It is a recorded observation, and the record says so in its own words.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — two additions, both dated:
    - a new bullet under **#208** carrying the feedback-loop exercise: the commands, the two-plus feedback items, the per-id human outcome, the document actions the reviewer took, and the id-continuity observation. Add a **new bullet**; do not edit #208's `Status:` field or its `Framing` prose — step 10 owns those.
    - a sample appended to **#215**'s measurement section: attempts per stage under revision mode, `prompt_bytes`, advisory level, wall, and cost, in the shape of the tables already there. Record the sample; do not resolve the entry.

Everything the exercise produces besides those two edits is scratch and stays uncommitted: the scratch plans directory, the revised artifacts, the run logs, and any helper script. Name every scratch file for this task (`.tmp/roadmap-02-feedback.*`), per the repo's `.tmp/` naming rule.

## Implementation

### 1. Write the reading rule before running anything

The outcome vocabulary and the routing rule go into the `BACKLOG.md` block **before** any evidence, and stay above it in document order. Four values, from the plan's Testing section — **accepted**, **partially accepted**, **declined**, **required clarification** — plus one sentence stating that the result is recorded and gates nothing. A vocabulary invented after reading the responses is a vocabulary fitted to them.

This is checkable at review: the reading rule appears before the first result in the finished file.

### 2. Build the fixture: a fresh baseline, in a scratch plans directory

- **Isolate with the global `--plans-dir`.** It is a top-level flag, so it goes *before* the subcommand: `plan-tool --plans-dir .tmp/roadmap-02-feedback.plans roadmap cfp-review --from-existing .tmp/roadmap-smoke.cfp-concept.md`. The committed tree has no `docs/implementation-plans/roadmaps/` directory today and must not gain one from this step.
- **Run the arc once with no feedback.** That first run is the predecessor and the baseline, and it exercises the "no predecessor → authoring path unchanged" half for free. Record its numbers too.
- **Do not reuse `.tmp/roadmap-smoke-plans/`.** See [Input](#input) — those artifacts fail to parse at HEAD.

### 3. Write at least two feedback rows by hand, against the ids the baseline actually produced

Ids are not stable across runs — that is the problem this position exists to fix — so the row targets must be read off the artifact the baseline just wrote, never copied from an older one or from this file.

The plan's floor is two non-confirming items: one **domain redirect** and one **genuinely ambiguous request**. Non-confirming means the request asks for something the artifact does not already do, so a response cannot be a trivial "already handled."

- **The redirect** names one row and asks for a substantive change. One way, grounded in the brief: the brief says a reviewer's conflict of interest is *declared or inferred, and a declared conflict always wins over an inference*, while the baseline is likely to carry a single conflict entity. Asking whether that one row can carry both kinds, and to split it or say why not, is a real correction with a checkable consequence in the next artifact.
- **The ambiguous request** should be one the artifact genuinely cannot resolve from the brief, so the honest response is a focused question rather than an invented answer. Pick it after reading the baseline; the point is to see whether `proposed_response` asks or guesses.
- **One way to get more coverage for free:** make the redirect row-targeted and the ambiguous one artifact-targeted, so the run exercises both arms of the target union. Not required — the floor is the two kinds, not the two target shapes.
- **Keep the requests quotable.** This brief is synthetic, so the record can quote both requests in full and should. If a later exercise ever uses a real project brief, summarize instead — `BACKLOG.md` is committed and the run log deliberately holds no text.

### 4. Re-enter, and capture the run

Re-enter at the artifact's own stage: `--from-stage 1` for feedback written into `01-domain.md`. Two consequences to record rather than work around:

- **`--from-stage N` rewrites every stage from N up.** A domain-only redirect still re-runs and pays for stage 2. That is the shipped behavior and it is an operational fact a reviewer needs; note the cost split per stage.
- **Stage 2 is the one with no demonstrated retry margin** (`MAX_STAGE_ATTEMPTS = 3` in `plan_tool/roadmap.py`; five prior samples, two of them one attempt from the cap). Its attempt count under revision mode — with a predecessor and a feedback block added to an already-large prompt — is the single most useful number this exercise produces for #215.

Capture, per attempt, from the run log at `.plan-tool/runs/<slug>/<run_id>.jsonl` (gitignored; `plan-tool runs list --slug <slug>` finds the run id):

- `prompt_bytes` from each `claude_call_start`, and `cost_usd` from each `claude_call_end`;
- any `gate_violations` events — what consumed a retry, if one was consumed;
- the `RevisionFeedbackDelivered` event step 3 mints: which ids were delivered, against which predecessor digest;
- the prompt-budget advisory level printed by the shell path. `shell_roadmap_invoker` calls `plan_tool/shell.py:claude_invoke`, which runs the backstop in `_maybe_warn_shell_prompt_budget`, so the levels are `plan_tool/prompt_budget.py`'s `LEVEL_OK` / `LEVEL_WARN` / `LEVEL_HIGH`. Record which one fired, including `ok` — "the advisory never fired" is a result.

Also capture step 7's completion block verbatim, and note whether it told the reviewer where to look without them reading source.

### 5. Review as a human, act in the document, and record both

For each feedback id, read `proposed_response` beside the artifact diff and assign one of the four predeclared outcomes. Then take the document action the outcome calls for — delete the row to close it, set it to `deferred`, or set it back to `open` (clearing or replacing the response) to reopen — and record which action was taken per id. Do not manufacture an action the outcomes do not support; an honest "all three were accepted, so nothing was deferred" is a result.

If any item comes back as **required clarification**, answering it and running a second re-entry is the strongest available evidence that the loop closes rather than just delivers. Run it if the budget allows and record it; if not, say it was skipped and why.

### 6. Record id continuity as a safety observation, and say why it is weaker than it looks

Compare the revision's ids against the predecessor's, in the same four kinds as the 85/60/30/25 baseline (entity / workflow / business-rule / decision), and report the ratios beside those numbers. Then state the limit plainly, because a reader will otherwise take a high number as proof the model behaved:

- **Design-row id continuity is now partly gate-enforced.** Step 2's continuity gate covers every design row kind — `plan_tool/roadmap_gates.py:_domain_rows` includes decisions, and `_constraints_rows` covers dispositions, constraints, and decisions — so near-100% is what a *working gate* produces, not evidence of a well-behaved model. A number below 100% means either a declared removal or a gate escape, and the record should say which by listing every removal record with the feedback id it cites.
- **Entity field-name sets are the part no gate covers.** `check_entity_fields` judges presence and within-row uniqueness, not continuity across a revision, so comparing each surviving entity's field-name set against its predecessor's is a genuine behavioral measurement — and it is exactly the number the baseline recorded as 0 of 11. Report it.
- **This is a safety observation, never the headline.** The step's intent says so, and the plan's Testing section says so. The headline is the per-id human outcome.

### 7. Land the block

Two edits in `BACKLOG.md`, in the shape the file already uses:

- **#208** gains a new dated bullet — model it on the existing `**Evidence:**` bullet, which names its `.tmp/` files and then says outright that `.tmp/` is gitignored and local and *this bullet is the durable record*. Same move here.
- **#215** gains a sample in its existing table shape, labelled as revision mode so it is not read as another authoring sample. Record it and stop: the calibration decision stays #215's, and `MAX_STAGE_ATTEMPTS` is not touched by this step.

**The step completes whichever way the exercise goes.** A declined outcome, a clarification the model never asked for, or a stage that exhausts its budget are all results to write down. The only failure mode is not recording what happened. Anything surprising that needs work gets a `BACKLOG.md` / `BUG_BACKLOG.md` entry per that file's decision rule — never a change to the loop inside this step.

**The main alternative, rejected:** a committed record under `docs/`, the way `jira-grade`'s falsification check was written. It reads better as a standalone document, and it is out of this step's declared file list — and the fact that pushed the earlier check into its own file (a four-arm comparison with finding sets) does not apply to one reviewer's reading of two requests. If the record ever grows past what a backlog bullet holds, that is a plan-level decision, not a quiet file addition.

## Tests

This step is `change_type: non-code` and changes no production code. The plan's `enforce_step_tests: true` gate keys on `change_type` and fires only for `feature` / `refactor` steps, so it does not apply here; the verification below is the substitute, and it is what a reviewer runs.

### Verification (non-code step)

Roughly a dozen checks, all runnable against the finished `BACKLOG.md` and the working tree:

1. **reading-rule-precedes-evidence** — the four-value outcome vocabulary and the "this gates nothing" sentence appear above the first result in document order.
2. **commands-recorded-verbatim** — every invocation appears as a literal command line, including the global `--plans-dir` placement and the `--from-stage` value.
3. **two-kinds-present** — the block carries at least one domain redirect and at least one genuinely ambiguous request, each quoted, each labelled with its kind and its target (artifact or row id).
4. **per-id-outcome-present** — every feedback id has exactly one of the four predeclared outcomes, and no fifth value appears.
5. **document-action-recorded** — every id carries what the reviewer did in the artifact afterwards (closed by deletion, deferred, reopened, or left as-is with a reason).
6. **delivery-proved-from-the-log** — the block names the delivered ids and the predecessor digest taken from the `RevisionFeedbackDelivered` event, not from the artifact alone.
7. **numbers-present** — attempts per stage, `prompt_bytes` per attempt, advisory level, wall, and cost, each attributed to its stage.
8. **continuity-reported-and-qualified** — the four ratios appear beside the 85/60/30/25 baseline, the entity field-name-set comparison appears, and the block states in its own words that design-row continuity is now gate-enforced and is a safety observation rather than the result.
9. **removals-listed-with-citations** — every removal record in the revision is listed with the feedback id it cites, or the block says there were none.
10. **215-sample-added-not-decided** — #215 carries the new sample labelled as revision mode, and `git diff` shows no change to `plan_tool/roadmap.py`.
11. **208-status-untouched** — this step's diff leaves #208's `Status:` field and `Framing` bullet unchanged; step 10 owns them.
12. **footprint-is-one-file** — the commit touches only `BACKLOG.md`; `git status` shows nothing new under `docs/implementation-plans/roadmaps/`.
13. **paths-resolve-or-are-marked-local** — every path the block names either exists at HEAD or is explicitly marked gitignored and local to the machine that ran it.

## Acceptance criteria

- `BACKLOG.md` carries a dated feedback-loop exercise bullet under **#208** containing: the brief, the verbatim commands, at least two quoted feedback requests labelled redirect / ambiguous with their targets, the model's proposed response per id, one of the four predeclared outcomes per id, and the document action the reviewer took for each.
- The block's reading rule — the outcome vocabulary plus the statement that the result gates nothing — appears before any evidence in document order.
- The block reports attempts per stage, `prompt_bytes` per attempt, the prompt-budget advisory level (including `ok`), wall, and cost; **#215** carries the same sample in its table shape, labelled revision mode.
- The block reports id continuity for entities, workflows, business rules, and decisions against the 85/60/30/25 baseline, reports the entity field-name-set comparison, and states that design-row continuity is gate-enforced and is a safety observation rather than the headline result.
- Every removal record written by the revision is listed with the feedback id it cites, or the block records that there were none.
- `plan_tool/roadmap.py` is unchanged by this step; `MAX_STAGE_ATTEMPTS` still reads `3`.
- #208's `Status:` field and `Framing` bullet are unchanged by this step's diff.
- This step's commit touches only `BACKLOG.md`, and no file appears under `docs/implementation-plans/roadmaps/`.
- Anything surprising that needs follow-up work exists as a `BACKLOG.md` or `BUG_BACKLOG.md` entry, not as a change to the loop.

## References

- [Long context prompting tips — Claude Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips) — read when judging whether the revision prompt's prior-artifact and feedback blocks stayed legible at the sizes this run actually produced.
- [Prompt caching — Claude Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) — relevant to reading the recorded cost: a retried stage re-sends a stable prior-artifact prefix, so cost per attempt is not flat.
- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference) and [headless mode](https://docs.claude.com/en/docs/claude-code/headless) — the invocation and exit-status contract under the stage orchestrator, for reading a non-zero run correctly.

## Applicable guardrails

- **The plan's "## Out of scope", no judging or scoring a revision** — this step records a human verdict and nothing else. It adds no score, no threshold, no pass/fail reading, and no automatic transition of a feedback row; a declined outcome does not fail the step.
- **The plan's "## Out of scope", non-interactive and roadmap-only** — the exercise drives the shipped verb and a text editor. Any measurement helper stays a gitignored `.tmp/` script and never becomes a command, flag, or committed surface.
- **The plan's "## Out of scope", no cap or rejection based on feedback size or shape** — the prompt-budget level is recorded as an observation. This step must not propose or apply a limit on request length, count, or content.
- **The plan's "## Out of scope", no second store for feedback state** — the artifact stays the live review state. The backlog block is a dated record of one run, not a place feedback lives.
- **The plan's "## Out of scope", nothing past stages 1–2** — the exercise stops at the two shipped artifacts and reaches no components, seed derivation, or completion verdict.
- **The plan's "## Risks", retry-budget calibration stays with BACKLOG #215** — record the sample; do not change the budget or resolve the entry.
- **The step's own intent, continuity is a safety metric** — the record may not present id continuity as evidence that feedback was honored.

## Deferred

- **Flipping #208's arc-position status and replacing its no-feedback / regenerate-not-revise statements** — step 10 owns that reconciliation, along with the `CLAUDE.md` roadmap-architecture sweep. This step adds evidence beside them, never edits them.
- **Deciding whether `MAX_STAGE_ATTEMPTS` is right** — BACKLOG #215's own decision. This step feeds it one revision-mode sample.
- **A second brief, a second reviewer, or any repeated sampling** — this is one reading by design. Further samples are later observations routed to #208 / #215, not scope here.
- **Any repeatable harness, benchmark, or scoring surface for revision quality** — the plan's Out of scope refuses the scoring half, and the machinery half would be a new surface no step in this plan owns.
- **Committing the artifacts, the brief, or the run logs** — all three are gitignored by design; the backlog block is the durable carrier, which is why it must stand alone.
- **A `docs/` record file** — outside this step's declared file list; see the rejected alternative in [Implementation](#implementation).
- **Exercising cross-artifact feedback** — the plan's Out of scope keeps feedback local to its artifact.
