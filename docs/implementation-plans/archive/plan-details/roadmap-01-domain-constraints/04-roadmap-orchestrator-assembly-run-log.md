> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add the roadmap orchestrator: assembly, run log, gate retry loop, and `--from-stage` re-entry

## Summary

This step creates `plan_tool/roadmap.py`, the module that actually runs a roadmap: it walks a table of stages, renders each stage's prompt, makes the one Claude call, parses the response, runs that stage's gates, retries with the violations quoted back when they fail, writes the artifact when they pass, and halts the arc when a stage runs out of attempts. It also creates `tests/test_roadmap.py` and adds one row to `TESTING.md`'s backend-seam table. The main design decision is that **a stage is a row in a table, not a branch in the loop** — the run loop reads `(prompt file, artifact path, parser, gate set)` off a frozen `RoadmapStage` and never asks which stage it is running, which is what lets steps 5 and 6 add stages without touching the loop. On green the module ships a working skeleton with an **empty stage table**: the orchestrator, its retry policy, its run log, and its `--from-stage` re-entry are all exercised by tests that inject their own stages, and no real stage exists until step 5.

## Table of Contents

- [Summary](#summary) — what the step ships and the one design decision behind it.
- [Why](#why) — why the skeleton lands before either real stage.
- [Input](#input) — the contracts steps 1 and 2 hand this module, and the run-log and shell contracts it joins.
- [Files (creates vs edits)](#files-creates-vs-edits) — two new files plus one table row in `TESTING.md`.
- [Implementation](#implementation) — the stage table, the attempt loop, writing, re-entry, the run log, the result type, and the rules that are not free to vary.
- [Tests](#tests) — the 59 cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the docs worth reading for the retry and prompt decisions.
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences that bind this step.
- [Deferred](#deferred) — what other steps own, and the consolidation routed to reconcile.

## Why

Steps 1 and 2 produce a contract and seven gates that nothing calls. There is no code that opens a prompt, spends a Claude call, decides whether the answer is good enough, or puts a file on disk — so the plan's central rule, *Claude runs only inside a stage and deterministic code decides whether its output counts*, has no place to live. The skeleton lands before either real stage for one reason: the plan's structural bet is that a stage is data. If the domain stage were written first, its assembly, retry handling, and write path would sit inline in a function shaped around one stage, and the constraints stage would arrive as a second branch — exactly the shape the bet exists to avoid. Building the loop against an empty table with test-injected stages forces the interface to be honest, because there is no real stage available to special-case. It also means steps 5 and 6 are additions to a tuple plus a prompt file, not edits to control flow.

## Input

This step consumes the outcomes of steps 1 and 2, plus three existing repo contracts it joins rather than reinvents.

- **Step 1 produces the artifact contract** — `plan_tool/roadmap_artifacts.py`: the path helpers taking `(plans_dir, slug)`, the parse/load pairs, the renderer, and the one error type carrying the offending path. This module never derives an artifact path itself and never shapes YAML itself.
- **Step 2 produces the gates and their input envelope** — `plan_tool/roadmap_gates.py`: the two stage gate sets, both taking the same envelope (the artifact under check plus the already-parsed upstream artifacts). That shared shape is what makes the stage table's `gate_set` field a plain callable with no adapter. Fill the envelope the same way for every stage — with every artifact below this stage, **always loaded back from disk**, never carried forward in memory — so the loop never learns which gate needs what. Never say "written so far": on a re-entry run nothing has been written yet, and an empty upstream envelope is what makes `--from-stage` fail. The plan's Architecture section fixes the direction here: "a stage writes its artifact; the next stage re-reads it from disk rather than receiving in-memory state", and it budgets for the cost ("a re-parse per stage, negligible against a Claude call and paid deliberately") — a cost that only exists if a fresh run re-reads what it just wrote.
- **The landed names win over any name this file suggests.** Steps 1 and 2 mint the row types, path helpers, gate-set names, and envelope type; open both modules and use what actually shipped.
- **The run-log contract** — `plan_tool/run_log.py`: `RunLogWriter.start(repo_root=, slug=, command=, argv=, flags=)` writes `run_start` plus the in-flight snapshot; `phase_start` / `phase_end` / `claude_call_start` / `bind_shell_sink` bracket work; `run_end` must be called once from a single `finally:`. `run_log.run_log_path` puts the file at `<repo_root>/.plan-tool/runs/<slug>/<run_id>.jsonl`, which is what the plan's "run log beside every other verb's" criterion asks for.
- **The backend seam contract** — `plan_tool/shell.py:claude_invoke` returns `(rc, stdout)`, and `plan_tool/review.py:shell_review_invoker` is the in-repo example of a module-level `(str) -> tuple[int, str]` production invoker. Rate-limit waiting, backend switching, and transient backoff already live below that call in `plan_tool/rate_limit_loop.py`; this module inherits them and must not add a retry loop for transport failures.
- **What this step cannot verify.** No stage prompt file exists until step 5, so nothing here proves a real model can satisfy the gates. Every test drives injected stages and canned responses; the prompts' hit rate against the contract is step 5/6 work and is named as an open risk in the plan.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap.py` — the orchestrator: stage table, prompt assembly, the invoker seam, the attempt loop, the writer, `--from-stage` re-entry, the run log, and the result type.
  - `tests/test_roadmap.py` — the suite listed under [Tests](#tests).
- **Existing files (edits only):**
  - `TESTING.md` — add one row to the **Backend fallback seams** table for `roadmap.py` → `run_roadmap(invoker=...)`, defaulting to this module's shell invoker, with the neutralization recipe. That table's closing line ("When you add a new orchestrator with a real-backend default, add a row here") makes this required, not optional. No other section changes.

## Implementation

### The stage table

- **One frozen dataclass per stage, and a module-level tuple of them.** A workable shape for `RoadmapStage`: the stage number, a short name for logs, the prompt filename under `plan_tool/prompts/`, a path callable taking `(plans_dir, slug)`, the parser for that artifact, and the gate set. Every field is one of step 1's or step 2's public symbols — the table holds references, never copies of their logic.
- **Ship the tuple empty.** `STAGES: tuple[RoadmapStage, ...] = ()` with a comment naming steps 5 and 6 as its entries. An empty table is a completed run that writes nothing; that is the correct answer for a skeleton and it keeps steps 5 and 6 additive.
- **Make the table injectable.** `run_roadmap(..., stages=STAGES)` so tests build two fake stages with canned parsers and gate sets and drive the entire loop without a prompt file or a real artifact. This is the seam that makes a high-complexity orchestrator unit-testable before any stage exists.
- **The loop must never branch on stage identity.** No `if stage.name == ...`, no per-stage special case in prompt assembly, writing, or gating. If something feels like it needs one, it belongs as a field on `RoadmapStage`. This is the plan's structural bet and the thing a reviewer should check first.

### Assembling a stage prompt

- **Load templates through `plan_tool/renderer.py:prompts_dir()`**, the accessor eleven existing call sites already use (`plan_tool/detail.py`, `plan_tool/create.py`, `plan_tool/review.py`, `plan_tool/jira.py`, …). Do not mint a second `_PROMPTS_DIR` copy.
- **Substitute with `string.Template.safe_substitute`**, matching `renderer.render_prompt`. `${...}` placeholders let markdown braces pass through untouched.
- **The variables a stage prompt gets:** the slug, the brief text, and the rendered text of **every artifact below this stage, loaded from disk**. Say it that way, never "written so far": on a `--from-stage 2` run nothing has been written yet, so "so far" would hand the constraints prompt an empty upstream, the model would invent anchor ids, and the anchor gate would reject every attempt until the budget exhausted — killing the one flow `--from-stage` exists for. **There is one source, not two:** a fresh run and a re-entry both read the upstream back off disk, so the two paths are byte-identical and only *which stage produced the file* differs. Two sources would make the Architecture's claim that the anchor gate "reads upstream exactly the way a later run or a human does" false on the fresh path, and would hide a writer or renderer defect until someone re-entered. Keep the set small and uniform — every stage gets the same map, which is what keeps steps 5 and 6 from needing loop changes.
- **A missing template is a hard failure.** Raise, naming the expected path, the way `renderer.render_prompt` raises `FileNotFoundError`. Never fall back to a generic prompt.
- **Read the brief once, before the loop.** `--from-existing <concept.md>` is required on every invocation, including re-entry, because each stage's prompt is grounded in it. An unreadable or missing brief is a pre-flight failure naming the path.

### The attempt loop — the core of this step

Per stage, in this order, and the order is not free to vary:

1. Render the prompt (attempt 1) or the prompt plus the corrections block (later attempts).
2. Call the invoker.
3. Lift the artifact text out of the response.
4. Parse it with the stage's parser.
5. Build step 2's envelope from this artifact plus every artifact below this stage, loaded from disk, and run the stage's gate set.
6. Empty violation list → write, **load the artifact back from disk for the next stage's envelope and prompt map**, and advance. Otherwise → next attempt.

- **Bound it with a module constant.** Something like `MAX_STAGE_ATTEMPTS = 3` (one first pass plus two corrections), overridable by a parameter so tests drive exhaustion in two calls instead of three. `plan_tool/detail.py:_MAX_INVOKE_ATTEMPTS` is the naming precedent.
- **One retry channel, three failure kinds.** A non-zero rc or empty stdout, an unliftable/unparseable response, and gate violations all consume an attempt and all feed the same corrections block. Separate channels would mean separate budgets and separate halting rules for outcomes the operator experiences identically.
- **One channel, but the exhaustion *report* must still say which kind ran out.** Record the last attempt's failure kind and, for the invoke and parse kinds, its diagnostic text (rc, the head of the backend's stdout reply, or the unliftable reply's head). A backend failing rc≠0 on every attempt otherwise exhausts the budget and reports "a stage exhausted its retry budget without passing its gates" with an **empty violation list** — step 7 then prints the failed stage and its final violations, which is nothing, next to advice to fix the brief the operator never wrote wrong. The single channel is the right call; a failure report that cannot distinguish "the model disagreed with the gates" from "the backend never answered" is not.
- **Render corrections as bare bullets appended after the prompt**, mirroring `plan_tool/detail.py:_jira_retry_suffix` — each violation on its own `- {message}` line, under a short header saying these were rejected. Step 2 wrote every message to survive exactly this trip, so quote them verbatim and add nothing.
- **Corrections *replace*, they do not accumulate.** Each attempt's block carries only the violations that attempt produced. This matters by attempt 3: a response that fixes violation A and introduces B is told about B alone, so nothing stops it re-breaking A while fixing B and oscillating until the budget is spent — which halts the arc, the plan's top-named risk. Replacement is nonetheless the right rule and the precedent settles it (`_jira_retry_suffix` renders only the findings passed for the current rejection): an accumulated block re-asserts violations the artifact no longer has, and correcting a violation that is already fixed is how a model reintroduces it. The mitigation for oscillation is the bounded budget and the exhaustion report, not a growing correction list. Write the rule down either way — leaving it unstated is what makes the third attempt's behavior a coin flip. Appending (rather than substituting a `${corrections}` placeholder) keeps steps 5 and 6's prompt files free of retry plumbing.
- **Be tolerant lifting, strict parsing.** The response should be the artifact text, but models add preamble and code fences. `plan_tool/detail.py:parse_detail_response` is the precedent for the tolerant half: strip a leading and a trailing fence independently, then skip everything before the first `---`. Once lifted, hand the text to step 1's strict parser unchanged — the tolerance stops at the module boundary.
- **The same generate-parse-retry shape exists twice already** — `plan_tool/detail.py:generate_detail`'s per-step attempt loop and `plan_tool/create.py:propose_steps_from_claude`'s two-attempt re-prompt. Mirror their shape; import neither. They loop over plan steps with plan-schema types and different result contracts, so only the shape is shared. Consolidating the three is a cross-module refactor this step cannot mint — see [Deferred](#deferred).
- **Do not re-implement transport retry.** 429 handling, backend switching, and transient backoff live in `plan_tool/rate_limit_loop.py` below `shell.claude_invoke`. This loop's budget counts *content* attempts only.

### Writing the artifact

- **Write only after the gates pass, and write the renderer's output, not the raw response.** Feeding the parsed artifact back through step 1's renderer guarantees the on-disk bytes re-parse (step 1 pins `parse(render(a)) == a`), which is what the plan's "each artifact round-trips through the loader without error" criterion needs. The rejected alternative — write the raw lifted text for byte fidelity to the model's output — loses that guarantee for nothing, since the prose body is preserved by the renderer anyway.
- **Write atomically** with `plan_tool/fileio.py:atomic_write_text`, so an interrupted run never leaves a half-written artifact that the next `--from-stage` re-entry would parse.
- **Re-read the artifact from disk after writing it, and hand *that* to the stages above.** Do not pass the in-memory parsed artifact forward. This is the plan's disk-is-the-interface rule applied to the fresh path, and it is what makes the fresh run and the re-entry run travel one code path instead of two: a renderer that drops a field, or a writer that mangles encoding, then fails on the very next stage rather than lying dormant until an operator re-enters.
- **A failed stage leaves no file.** Nothing is written for a stage that exhausts its budget, and artifacts from earlier stages are left exactly as they were.
- **Create the roadmap directory on the write path**, not at start-up, so a failed first stage leaves no empty directory behind.

### Halting and re-entry

- **An exhausted stage halts the arc immediately.** The next stage's prompt is never rendered and its invoker is never called. Admitting a gate-failing artifact would hand every downstream stage a bad ground truth, which is the failure the whole gate design exists to prevent.
- **`from_stage` skips, it does not re-run.** Stages below it are not invoked and their artifacts are not rewritten. Later stages read those artifacts from disk when the envelope is built, which is the whole point of disk-as-the-interface: a hand edit is visible to the gates without re-running the stage that produced it.
- **Any stage that runs overwrites its artifact, deliberately and without a confirm.** Re-running `plan-tool roadmap <slug>` with no `--from-stage` regenerates stage 1 over an existing `01-domain.md`, discarding a hand edit. That is the correct default for a non-interactive verb — there is no operator to prompt, and a `--force` flag would only move the surprise — but it must be *stated*, because the plan's own review channel is "hand-edit the artifact and re-run", and the naive re-run is the one that destroys the edit. The tool's obligation is to make the safe path obvious — but that obligation is discharged by **step 7**, which owns every operator-facing line this verb prints. This step's half is the *data*: record on the result which stage numbers replaced an existing artifact, so the handler can build the pointer. Rendering it here as well would put one rule in two phrasings on two streams, which is exactly what shipped and had to be removed; `run_roadmap` prints nothing.
- **Re-entry overwrites too, and the warning must say so.** `--from-stage N` skips the stages *below* N; every stage from N up still runs and still rewrites its artifact. So a `--from-stage 2` run over an existing `02-constraints.md` overwrites it exactly as a full run does — the flow the operator reaches for *after* hand-editing `01-domain.md` is itself destructive to the artifact above. Recording overwrite per stage actually written, rather than per run, is what keeps the warning honest here; a contract that says re-entry never overwrites switches the protection off in the one flow where hand edits are most likely to exist.
- **The pointer is computed from the lowest overwritten stage, and it preserves only what sits *below* it.** Name `--from-stage <lowest overwritten stage + 1>`. Be exact about what that buys: `--from-stage N` skips stages below N, so it preserves their artifacts and **rewrites every stage from N up all over again**. It is not a way to keep everything that was just overwritten — it is a way to keep the *earliest* thing that was.
- **So the pointer alone is insufficient whenever more than one stage overwrote**, which is every full re-run of a populated directory. When any stage at or above the pointer was also rewritten, the message must additionally name **copying those artifacts aside before re-running** — otherwise an operator who hand-edited `02-constraints.md`, re-ran the verb, and followed a printed `--from-stage 2` loses the same edit a second time, having done exactly what the tool told them. Two overwritten stages is the common case, not the edge case, so this branch carries most of the traffic.
- **When the pointer would exceed the table's highest stage** — only the last stage overwrote, so no re-entry point skips it — there is no `--from-stage` value to print at all: say that a re-run rewrites it and name copying it aside. A message pointing at a stage number `run_roadmap` rejects as out of range is worse than no pointer. Step 7's summary carries the same pointer, the same copy-aside condition, and the same out-of-range case after a completed run.
- **A missing upstream artifact on re-entry is a pre-flight failure**, naming the path and which stage writes it. Do not silently run the stage anyway with an empty envelope.
- **A malformed upstream artifact surfaces as step 1's parse error**, carrying the path. Let it propagate as a run failure rather than catching it into a violation — the plan's Risks section calls for exactly this.
- **A loaded upstream artifact is re-run through its own stage's gate set, not merely parsed.** Parsing proves shape; the gates prove relations, and on re-entry nothing else ever checks them. Without this, hand-deleting an entity that a workflow still names leaves `01-domain.md` internally broken and the run proceeds: only constraints pointing at the deleted id would surface, and only through the anchor gate. That contradicts this step's own reason for halting an exhausted stage — admitting a gate-failing artifact hands every downstream stage a bad ground truth — and it is the case the seed names when it requires a lower artifact failing its gate on re-entry to stop the run. A re-gate failure is a **pre-flight failure**, not a retry: nothing was invoked, and re-prompting a stage the operator edited by hand would silently discard their edit.
- **Define "the table's range" explicitly: it is the set of stage numbers the table actually holds**, not `1..len(stages)`. The two coincide for the shipped 1-then-2 table but diverge for any injected table, and the overwrite pointer's "exceeds the table's highest stage" branch reads the same set — so state it once here and let both rules cite it. `from_stage` naming a number outside that set is a pre-flight failure, checked before any Claude call.
- **An empty table accepts the default and runs nothing.** `STAGES` ships empty and step 7 gives `--from-stage` `default=1`, so every invocation of the skeleton arrives with `from_stage=1` against a table whose stage-number set is empty. Range-checking that literally would make the skeleton's own documented behavior — "an empty stage table is a completed run that writes nothing" — impossible to reach, and `test_empty_stage_table_completes_writing_nothing` would contradict `test_from_stage_outside_the_table_raises_before_any_call`. **The rule: an empty table skips the range check and completes, writing nothing.** The range check applies only to a non-empty table. Say this in the code and pin it, because it is the one case where two otherwise-correct rules claim the same input.

### The run log

- **This module opens its own writer.** `RunLogWriter.start(command="roadmap", slug=<roadmap slug>, ...)` when the caller passes none, and a `run_logger=` parameter for a caller that already has one. Nine CLI handlers open writers today (`plan_tool/cli/run_cmd.py`, `plan_tool/cli/authoring.py`, …), but step 7's handler must stay thin arg-to-orchestrator wiring, and this step must be runnable and observable with no CLI at all. `plan_tool/bench.py` is the in-repo precedent for a non-CLI module calling `RunLogWriter.start`.
- **One phase pair per stage** (`phase_start` / `phase_end` with an outcome), one `claude_call_start` per attempt carrying `prompt_bytes`, and `bind_shell_sink(phase=..., attempt=...)` around the invoker call so shell-level call accounting lands on the right attempt — the bracketing `plan_tool/detail.py`'s attempt loop uses.
- **Call `run_end` once from a single `finally:`** covering every return and raise path, so the in-flight snapshot is always cleaned up.
- **Type the parameter structurally.** `plan_tool/create.py`'s `RunLoggerLike = object` exists so tests pass recording fakes without the real writer's filesystem dependencies; do the same here.

### The result type and the exit-code convention

- **Return a frozen `RoadmapResult`; raise only for problems that stop the run before it starts.** `plan_tool/scope_out.py:ScopeOutResult` and `plan_tool/launcher.py:escalate_to_split`'s `EscalateResult` are the shape: a closed `outcome` vocabulary plus the facts a caller needs. Two outcomes are enough here — the run completed, or a stage exhausted its budget. A `RoadmapError` covers the pre-flight failures above (bad slug, missing brief, missing or malformed upstream artifact, `from_stage` out of range, missing template).
- **Carry on the result:** the artifacts written, the stages run, the count of `pending` decisions across those artifacts, **the stage numbers whose write replaced an existing artifact** (empty when none did), and — on failure — which stage failed, its final violation list, **its last attempt's failure kind (invoke / parse / gates), and that attempt's diagnostic text for the invoke and parse kinds** (rc and the head of the backend's stdout reply, or the unliftable reply's head). The failure-kind pair is not optional detail: without it an every-attempt backend failure reaches step 7 as an empty violation list, which reads as "the model disagreed with the gates" — the outcome the attempt-loop section above says must not happen. A field the report needs but the result does not carry is a requirement stated in one place and contradicted in another. The overwrite field is the same shape of obligation: a single boolean cannot tell step 7 *which* stage to build the `--from-stage` pointer from once more than one artifact is rewritten, so the result carries the stage numbers and the handler takes the lowest.
- **`pending` decisions never change the outcome.** They are the plan's review channel. A completed run carrying twenty `pending` decisions is still completed, and step 7's handler maps that to rc 0.
- **The rc mapping itself belongs to step 7.** This module returns facts; it never calls `sys.exit` and never prints an operator-facing summary.

### Constraints that are not free to vary

- **This is the only module in the group that shells out.** One `invoker=` seam of shape `(str) -> tuple[int, str]`, defaulting to a module-level shell invoker delegating to `plan_tool.shell.claude_invoke`. Tests override it; the autouse gate in `tests/conftest.py` fails loudly if one forgets.
- **No interactive surface.** No `input()`, no `sys.stdin.isatty()`, no confirm gate, no TTY branch anywhere. The verb behaves the same unattended as under an operator.
- **No artifact under `.plan-tool/`.** Only the run log goes there. Artifacts land under the plans directory.
- **Take `repo_root` and `plans_dir` as parameters.** Resolution is the caller's job (`plan_tool/locator.py:resolve_repo_root` / `resolve_explicit_plans_dir`), matching the choice step 1 made for the same reason: `--plans-dir` and `PLAN_TOOL_PLANS_DIR` mean there is no constant to re-derive.
- **No re-export in `plan_tool/__init__.py`.** That file is outside this step's declared list and nothing needs the symbols at package level yet.

## Tests

All cases live in `tests/test_roadmap.py`. Most are plain unit tests driving `run_roadmap` with an injected two-stage table, canned parsers and gate sets, and a fake invoker — no prompt files, no real artifacts. Likely mark one end-to-end class `@pytest.mark.integration` where a test drives the real step-1 parser, the real step-2 gate sets, and real disk writes together; keep the rest unmarked and fast.

This is a `feature` step in a plan with `enforce_step_tests: true`, so the test-authoring gate applies and `tests/test_roadmap.py` must land with the module.

### Tests for this step

59 cases. Every one must be green before this step is finished.

**Stage table and dispatch**

- `test_stage_table_ships_empty` — `STAGES` has no entries; steps 5 and 6 add them.
- `test_empty_stage_table_completes_writing_nothing` — a run over the shipped table returns the completed outcome and touches no file.
- `test_stages_run_in_table_order` — two injected stages are invoked lowest-number-first.
- `test_gate_envelope_carries_every_artifact_below_the_stage` — stage 2's gate set receives stage 1's parsed artifact, not just its own, on a fresh run *and* on a re-entry that loaded it from disk.
- `test_upstream_is_re_read_from_disk_on_the_fresh_path` — the artifact stage 2 receives is the one parsed back off disk, not the in-memory object stage 1 produced: mutating the file between the two stages changes what stage 2 sees. This is the disk-is-the-interface rule on the path where it is easiest to skip.
- `test_fresh_run_and_re_entry_build_an_identical_envelope` — the same on-disk `01-domain.md` yields an equal envelope whether stage 1 just wrote it or a `--from-stage 2` run loaded it, so the two paths cannot diverge.

**The clean path**

- `test_clean_run_writes_one_artifact_per_stage` — both artifact paths exist after a run where every gate set returns nothing.
- `test_written_artifact_reparses_through_the_loader` — the bytes on disk load back through step 1's loader without error.
- `test_written_bytes_come_from_the_renderer_not_the_raw_response` — a response with a fence and a preamble lands on disk as clean rendered artifact text.
- `test_no_roadmap_artifact_is_written_under_plan_tool` — nothing but the run log appears under `.plan-tool/`.
- `test_clean_run_returns_the_completed_outcome` — the result's outcome and its list of written artifacts.

**The retry loop**

- `test_violations_are_appended_to_the_retried_prompt` — attempt 2's prompt contains the corrections block; attempt 1's does not.
- `test_retry_prompt_carries_every_violation_message_verbatim` — each message appears as its own `- {message}` bullet, unedited.
- `test_corrections_replace_rather_than_accumulate` — a stage whose second attempt trades violation A for violation B gets a third prompt naming B only; A's message is absent, so the block always describes the artifact actually rejected.
- `test_second_attempt_passing_gates_writes_the_artifact` — a stage that fails once and passes once writes and advances.
- `test_unparseable_response_is_retried_like_a_violation` — a parse failure consumes an attempt and produces a correction, not a raise.
- `test_failed_invoke_consumes_an_attempt` — a non-zero rc from the invoker is an attempt, not an immediate failure.
- `test_empty_response_consumes_an_attempt` — empty stdout behaves the same as a non-zero rc.
- `test_attempt_count_is_bounded_by_the_budget` — an always-violating stage calls the invoker exactly the budget's number of times.

**Halting**

- `test_exhausted_budget_halts_before_the_next_stage` — stage 2's invoker is never called after stage 1 exhausts.
- `test_exhausted_budget_writes_no_artifact_for_the_failed_stage` — the failed stage's path does not exist.
- `test_exhausted_budget_leaves_earlier_artifacts_intact` — stage 1's file is unchanged when stage 2 exhausts.
- `test_exhausted_budget_returns_the_stage_exhausted_outcome` — the result names the failed stage and carries its final violations.

**The exit-code convention**

- `test_pending_decisions_do_not_change_the_outcome` — artifacts full of `pending` decisions still complete.
- `test_pending_decision_count_is_reported_on_the_result` — the count matches the rows across both artifacts.
- `test_outcome_vocabulary_is_closed` — only the two documented outcome values are ever returned.

**`--from-stage` re-entry**

- `test_from_stage_two_invokes_only_the_later_stage` — stage 1's invoker is never called.
- `test_from_stage_two_reads_stage_ones_artifact_from_disk` — the envelope holds the on-disk artifact, not a regenerated one.
- `test_hand_edited_upstream_is_visible_to_the_later_stages_gates` — deleting an entity from `01-domain.md` by hand turns a previously clean constraint into a violation on re-entry.
- `test_from_stage_leaves_earlier_artifacts_unmodified` — stage 1's bytes are the same before and after.
- `test_missing_upstream_artifact_raises_naming_the_path` — re-entry with no `01-domain.md` fails pre-flight.
- `test_malformed_upstream_artifact_surfaces_as_a_parse_error` — step 1's error type propagates carrying the path.
- `test_from_stage_outside_the_table_raises_before_any_call` — the invoker is never called; the rejected value is outside the set of stage numbers the table holds.
- `test_empty_table_accepts_the_default_from_stage_and_completes` — `STAGES` empty plus step 7's `default=1` completes writing nothing, rather than failing the range check. The empty table is the one input the range rule and the no-op-run rule both claim, and this pins which wins.
- `test_range_check_reads_the_tables_stage_numbers_not_its_length` — an injected table numbered 2 and 5 accepts `--from-stage 5` and rejects `--from-stage 3`.

**Run log**

- `test_run_log_lands_under_the_runs_directory` — a JSONL file appears at `.plan-tool/runs/<slug>/`.
- `test_each_stage_emits_a_phase_pair` — one `phase_start` / `phase_end` per stage run.
- `test_each_attempt_emits_a_claude_call_start` — three attempts produce three events with rising attempt numbers.
- `test_run_end_is_emitted_on_the_failure_path` — the in-flight snapshot is cleaned up when a stage exhausts.

**Inputs and seams**

- `test_missing_brief_raises_naming_the_path` — pre-flight failure before any call.
- `test_brief_text_reaches_the_stage_prompt` — a marker string in the brief appears in the rendered prompt.
- `test_missing_prompt_template_raises_naming_the_expected_path` — a stage pointing at a file that is not in `plan_tool/prompts/` fails loudly.
- `test_default_invoker_is_the_shell_seam` — the parameter's default is this module's shell invoker, so a caller that forgets to override it is caught by `tests/conftest.py`'s gate.
- `test_run_is_non_interactive` — no `input(`, no `isatty` anywhere in the module source.

**Failure-kind reporting and overwrite warning**

- `test_exhaustion_by_gates_carries_the_gates_failure_kind` — a stage that keeps producing gate-violating output reports the gates kind and a non-empty violation list.
- `test_exhaustion_by_invoke_carries_the_invoke_kind_and_diagnostic` — an invoker returning rc≠0 on every attempt reports the invoke kind, an rc, and the head of the backend's stdout reply — **not** an empty violation list.
- `test_exhaustion_by_parse_carries_the_parse_kind_and_reply_head` — an unliftable reply on every attempt reports the parse kind and the head of the offending reply.
- `test_gate_exhaustion_has_no_invoke_diagnostic` — the diagnostic fields are absent (not empty strings) when the run really did fail on gates, so step 7 can branch on presence.
- `test_overwriting_an_existing_artifact_records_the_stage_number` — a full run over a directory that already holds `01-domain.md` records stage 1 on the result's overwritten-stages field.
- `test_the_orchestrator_renders_no_operator_advice` — that run records the overwritten stage on its result and writes nothing to either stream, so the pointer has exactly one implementation (step 7's) and cannot be printed twice.
- `test_re_entry_records_the_stages_it_rewrote` — `--from-stage 2` over an existing `02-constraints.md` records stage 2: re-entry skips the stages *below* N and rewrites every stage from N up, so it overwrites like any other run.
- `test_stages_skipped_by_from_stage_are_not_recorded_as_overwritten` — stage 1 is absent from the field on that run, because it never ran.
- `test_the_orchestrator_renders_no_operator_advice` — a run rewriting both artifacts records the stage numbers on its result and writes nothing to either stream. The pointer's rendering — lowest-overwritten-plus-one, the copy-aside caveat when a stage at or above the pointer is rewritten again, and the no-pointer case at the table's highest stage — is step 7's, and is asserted there in `tests/cli/test_roadmap_cmd.py`. Keeping message assertions here too is what let one rule ship in two phrasings on two streams.
- `test_a_run_that_overwrote_nothing_records_an_empty_field` — a first run into an empty directory reports no overwritten stages and emits no pointer.
- `test_re_entry_regates_the_loaded_upstream_artifact` — a hand-edited `01-domain.md` whose workflow still names a deleted entity fails pre-flight on re-entry. Parsing alone would accept it: the break is a *relation*, and only stage 1's own gate set checks relations, so without this the run proceeds on a broken ground truth.
- `test_re_entry_regate_failure_is_pre_flight_not_a_retry` — the failing upstream stage is not re-invoked; re-prompting a stage the operator edited by hand would silently discard their edit.

## Acceptance criteria

- `plan_tool/roadmap.py` and `tests/test_roadmap.py` exist, and `TESTING.md` gains exactly one row in its **Backend fallback seams** table naming `run_roadmap`'s `invoker=` seam and how to neutralize it. No other file in the repo changes.
- `STAGES` is an empty tuple at the end of this step, and running with it returns the completed outcome having written nothing.
- The run loop contains no branch on a stage's identity: `rg 'stage\.(name|number) ==' plan_tool/roadmap.py` returns nothing, and both injected test stages travel the same code path.
- A run whose every gate set returns no violations writes one artifact per stage under `<plans_dir>/roadmaps/<slug>/`, and each written file loads back through step 1's loader without error.
- A response wrapped in a code fence with leading preamble still produces a clean artifact on disk; the bytes written come from step 1's renderer, not the raw response.
- A stage whose gate set returns violations is retried with those messages appended as `- {message}` bullets, each appearing verbatim; the first attempt's prompt has no corrections block.
- A stage that never clears its gates calls the invoker exactly `MAX_STAGE_ATTEMPTS` times, writes no artifact, and stops the run — the next stage's invoker is never called.
- A completed run carrying `pending` decisions returns the completed outcome, and the result reports the `pending` count. The only non-completed outcome is a stage exhausting its budget.
- `--from-stage 2` invokes only stage 2, reads `01-domain.md` from disk into the gate envelope, leaves that file byte-for-byte unchanged, and surfaces a hand-deleted entity as an anchor violation.
- Re-entry with a missing, malformed, or out-of-range upstream fails before any Claude call, with the offending path or stage number in the message.
- The run log appears at `<repo_root>/.plan-tool/runs/<slug>/<run_id>.jsonl` with a phase pair per stage and a `claude_call_start` per attempt; `run_end` is emitted on both the success and the failure path. No roadmap artifact is written anywhere under `.plan-tool/`.
- `rg 'input\(|isatty' plan_tool/roadmap.py` returns nothing, and `rg 'sys.exit' plan_tool/roadmap.py` returns nothing.
- An exhausted-stage result carries the last attempt's failure kind; for the invoke and parse kinds it also carries the diagnostic text (rc and the head of the backend's stdout reply, or the unliftable reply's head), and for the gates kind those diagnostic fields are absent rather than empty.
- A run that rewrites an existing artifact records that stage's number on its result, and `run_roadmap` prints nothing about it — building the `--from-stage` pointer, the copy-aside caveat, and the no-pointer-above-the-top case from that field is step 7's, so the rule has one implementation on one stream. A `--from-stage N` re-entry records every stage from N up that replaced an existing artifact, and none below N.
- Every stage's upstream artifacts reach both the prompt map and the gate envelope **loaded from disk**, on the fresh path as well as on re-entry, so the two paths build an identical envelope from identical bytes.
- The corrections block carries only the violations from the attempt that produced it; it never accumulates across attempts.
- The accepted `from_stage` values are exactly the stage numbers the table holds; an **empty** table accepts the default and completes writing nothing rather than failing the range check.
- Re-entry fails pre-flight, before any Claude call, when a loaded upstream artifact violates its own stage's gate set — the message names the offending row id, and the upstream stage is not re-invoked.
- The 59 cases in `tests/test_roadmap.py` pass under `uv run pytest tests/test_roadmap.py -q`, and the full suite (`uv run pytest tests/ -q`) stays green with no `@pytest.mark.allow_real_claude` opt-out anywhere in the new suite.
- `plan_tool/schema.py`, `plan_tool/parser.py`, `plan_tool/locator.py`, `plan_tool/roadmap_artifacts.py`, `plan_tool/roadmap_gates.py`, and `plan_tool/__init__.py` carry no diff.

## References

- [Structured outputs — Claude API Docs](https://docs.claude.com/en/docs/build-with-claude/structured-outputs) — what a forced, machine-checkable output contract looks like; read it when deciding how much shape to demand of a stage response before the tolerant lift.
- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — the flag semantics (`--from-stage`, `--from-existing`) step 7 will wire; read it to keep this module's parameter names and types wireable without translation.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — `YAMLError` behavior, so the re-entry parse-failure path handles a hand-broken upstream the way step 1 expects.
- [MADR — Markdown Architectural Decision Records](https://adr.github.io/madr/) — the decision-record shape whose `pending` status this loop counts and deliberately never blocks on.

## Applicable guardrails

- **No components or plan-derivation stages.** The table ships empty and gains its two entries in steps 5 and 6. Add no third stage, no component artifact path, and no seed emission here.
- **No actuator for the `FORK_STRUCTURAL` re-seed arm.** `plan_tool/convergence_diagnosis.py` keeps its hand-authored placeholder; nothing in this module writes a `create` seed or touches that diagnostic.
- **No change to plan discovery, the plan schema, or the manifest.** This module writes only under `<plans_dir>/roadmaps/<slug>/` and `.plan-tool/runs/<slug>/`. It never reads or writes `plans.json` and imports nothing from `plan_tool/schema.py`.
- **No standalone audit or reconcile surface.** Correctness here is the in-run gates. No report file, no saved sidecar, no `--fail-on-findings`-style verdict, no findings roll-up.
- **No sign-off command for `pending` decisions.** The loop counts them and never blocks on them. Hand edit plus `--from-stage N` is the whole review channel.
- **No interactive or TTY surface.** This is the guardrail that binds this step hardest, because a retry loop is exactly where a prompt-the-operator branch is tempting. There is none.
- **No per-project configuration of the quality-attribute list.** This module reads step 1's constant indirectly through the gates and reads no config file or environment variable of its own.
- **The concept brief is the operator's input.** This module reads it and passes it to the prompts; it never authors, distills, or rewrites it.

## Deferred

- **The two stage prompt files and their table entries** — steps 5 and 6 create `plan_tool/prompts/roadmap-domain.md` and `roadmap-constraints.md` and add the matching `RoadmapStage` rows. This step ships the loop those entries travel.
- **The CLI verb, its flags, the help catalog, and `CAPABILITIES.md`** — step 7. Nothing here parses argv, prints an operator summary, or maps an outcome to an exit code; the result type is the handoff.
- **Printing the run summary** — step 7's handler renders `RoadmapResult`. This step computes and carries the counts, including the `pending` decision count step 2 routed here.
- **Operator docs and the BACKLOG #208 reconciliation** — step 8.
- **Durable logging of rejected stage responses.** `plan_tool/detail.py:_log_parse_failure` writes them under `.plan-tool/parse-failures/<slug>/`; reusing it would mean importing `detail.py` into this module for one helper, and copying it would mint a second implementation. The run log's per-attempt events are the accounting for now — route the shared-helper question to reconcile.
- **Checkpoint and resume across stages** — `plan_tool/checkpoint.py` exists and would let a re-run skip an already-passed stage, but `--from-stage N` already covers the operator's correction loop and a cache keyed on a Claude-authored artifact needs a fingerprint decision this plan has not made.
- **Consolidating the repo's three generate-parse-retry loops** — `plan_tool/detail.py:generate_detail`, `plan_tool/create.py:propose_steps_from_claude`, and this module. Same shape, three different result contracts and three different content types; a shared loop would be a cross-module refactor this step cannot mint. Route it to reconcile or a `BACKLOG.md` entry.
- **Re-exporting anything in `plan_tool/__init__.py`** — no caller needs package-level access, and that file is outside this step's declared list.
- **Extending `tests/test_data_contract.py` to the run-log events this verb emits** — the events reuse the existing schema; the plan defers roadmap-side contract guarding while the artifact contract is still settling.
