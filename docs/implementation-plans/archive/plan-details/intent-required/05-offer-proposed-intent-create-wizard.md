> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Offer the proposed intent in the create wizard when the seed, `--from` text, or interactive path supplies none

## Summary

Add one operator decision gate to `plan_tool/create.py`'s `create_plan`: after the concept review settles the step list, work out which intents are missing, ask step 4's `plan_tool/intent_proposal.py` for drafts in one backend round-trip, walk the operator through accept / edit / decline, and fold the kept values into the in-memory `Plan` **before** `write_new_plan` runs. The key design decision is that this pass works entirely in memory (`propose_intents` / `review_intent_drafts` / `apply_intent_drafts`) — the plan file does not exist yet, so there is nothing to re-parse and nothing to rewrite. The pass costs zero extra calls when nothing is missing, and it skips entirely on non-TTY stdin without `--yes`, so the existing create suite's recorded call counts do not move. On green, a `create` from a seed with no usable `## Outcome`, from a `--from` one-liner, or from the interactive path writes a plan whose frontmatter carries an operator-approved `intent:` — and `plan_tool/review.py:check_intent_presence` returns nothing against it.

## Table of Contents

- [Summary](#summary) — what the step does and what is true on green.
- [Why](#why) — which authoring paths still produce an intent-less plan today.
- [Input](#input) — the contracts from steps 1, 2, and 4 this step consumes, and what it cannot check.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched and the per-file edits.
- [Implementation](#implementation) — where the pass goes, the mode ladder, the constraints, and the alternatives rejected.
- [Tests](#tests) — the cases this step adds and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checks a reviewer or CI can run.
- [References](#references) — the docs bearing on this step's surfaces.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step's code.
- [Deferred](#deferred) — the producers, callers, and later steps this one leaves alone.

## Why

Steps 2 and 3 close the two paths that have a value to carry forward: a seed's `## Outcome` becomes `Plan.intent`, and the step-proposal JSON carries `Step.intent`. Everything else in `create_plan` still lands with nothing:

- A seed with no `## Outcome`, or one whose Outcome is a placeholder, maps no plan intent.
- `--from "one line"` supplies no `## Outcome` at all.
- The interactive path (`prompt_steps` → `_prompt_one_step`) asks for title, complexity, files, and `depends_on` — never a why.
- `extract_steps_from_canonical` copies title / files / creates / `change_type` / `depends_on` from a canonical source and nothing else.
- The wizard's own split reuses `_parse_steps_json` through `_propose_step_split`, but that prompt asks for `title`, `change_type`, `files`, `creates`, `concept_ids`, and `rationale` — not `intent` — so a split replacement arrives empty even after step 3.
- The tool-generated forward seeds (`plan_tool/scope_out.py:render_carved_seed`, `plan_tool/reground.py:render_rebaseline_seed`) emit no `## Outcome`, so a plan created from a carve or a re-baseline maps nothing.

Step 6 makes `check_intent_presence` blocking. Every path above would produce a plan that blocks on the round it is created. This step is the last authoring gap, and it closes all of them at one site instead of teaching six producers to ask.

## Input

This step consumes three sibling contracts and changes none of them. **None of the three exists at HEAD** — `plan_tool/intent_proposal.py` is absent and `plan_tool/review.py` still carries the private `_is_usable_intent` — so this step is blocked until steps 1, 2, and 4 land.

- **Step 1's `plan_tool/review.py:is_usable_intent`** — the public presence predicate. Plain-string signature (`Optional[str] -> bool`); its three non-values are `None`, empty after `.strip()`, and a bare TODO/TBD marker. This step calls it in exactly one place: building the missing set. Do not write a second emptiness or placeholder test in `create.py`. `create.py` already has a module-level `from plan_tool.review import (...)` block (`FileCheck`, `check_file_existence`, `collect_deterministic_findings`, …), so this is one more name in an existing import — no new module edge.
- **Step 2's outcome** — `create_plan` passes `intent=` into its single `Plan(...)` construction, so by the time this pass runs the plan-level field is already filled when the seed supplied one. This step reads `plan.intent`; it does not re-read the seed and does not re-run the `## Outcome` map.
- **Step 4's `plan_tool/intent_proposal.py`** — the drafting module. This step consumes four of its public symbols: `propose_intents` (one round-trip, returns `None` on an unparseable response and `[]` when the model proposed nothing), `review_intent_drafts` (the accept / edit / decline walk, driven by an injected `input_fn`), `apply_intent_drafts` (a pure `Plan` → `Plan` transform that collapses whitespace and returns a copy), and the `IntentDraft` record (`step_id=None` means the plan-level field). The module's `invoker` is a **required** keyword with no default — `create_plan`'s existing `claude_invoker` parameter is what gets passed.

**What this step cannot check.** Only that a value is present and is not a placeholder — the same limit step 4 states for a draft and step 2 states for a mapped Outcome. Nothing here judges whether a drafted intent is true, whether it matches the plan body or the step's title, or whether it is one line. The tests drive canned responses through the real parse and the real predicate, which shows the contract is satisfiable, not that the backend usually satisfies it.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — add `is_usable_intent` to the existing `from plan_tool.review import (...)` block and a module-level import of the step 4 module; add one private pass function beside `_review_step_gates`; call it from `create_plan` after the concept review; if the pass is checkpointed, add the checkpoint-name constant beside `_STEP_GATE_REVIEW_CHECKPOINT_NAME` and extend both the glob tuple and the kind ladder in `create_plan`'s checkpoint-cleanup block.
  - `tests/test_create.py` — add a test class beside `TestCreatePlanFromDescription`, reusing `_queue_input`, `_basic_metadata_answers`, and `_single_step_answers`.

## Implementation

**What must be true when the step is done.** No `create_plan` path can write a plan whose `intent:` is absent unless the operator was offered one and turned it down — or unless there was no operator to ask. The offer costs one backend call, only when something is actually missing, and the plan file is written exactly once with the accepted values already in it.

### Where the pass goes

Put the call immediately after the concept review's `plan = plan.model_copy(update={"steps": reviewed_steps})` in `create_plan`, before the `propose_references` phase. Three reasons this position is the constraint, not a preference:

- **Step ids are final there.** `_review_step_change_types` can split and merge (`_apply_step_split` renumbers every step by position), and `_review_step_gates` runs after it. A draft that names a step id has to name a post-review id.
- **Nothing is on disk yet.** The fail-loud `_(TODO)_` body check, collision archival, `write_new_plan`, and the post-write `parse_plan` reparse all come later, so a declined draft leaves no trace and an accepted one rides the single initial write.
- **It joins the existing run of decision gates.** Change-type → gates → concepts → intent keeps the operator's create walk in one stretch instead of scattering a fifth prompt after the research and synthesis round-trips.

Assemble the missing set from the plan the concept review returned:

- `plan_needs_intent = not is_usable_intent(plan.intent)`
- `step_ids = [s.id for s in plan.steps if not is_usable_intent(s.intent)]`

If both are empty, return immediately — no call, no prompt.

### The pass's shape

Add one private function beside `_review_step_gates`, likely `_offer_missing_intents(plan, *, input_fn, invoker, repo_root, slug, output_dir, resume, run_logger, yes, source_text) -> Plan`. Model it on `_review_step_gates`, which is the closest sibling: a fast path, a mode ladder, an interactive loop, and a docstring that spells the ladder out. The mode ladder:

- **Nothing missing** → return `plan` unchanged. Run-log the phase as `skipped` with `skip_reason="nothing_missing"`.
- **`yes=True`** → propose, then accept every draft verbatim without prompting, and name what was accepted in one `tool(..., level="note")` line. This is a **deliberate divergence from `_review_step_gates`**, which drops suggestions under `--yes`, and the docstring must say so: a `gate:` is an executable shell command that must not be baked in unvetted, while an intent is inert prose, and `--yes` already means "take every prompt default" — step 4's wizard defaults to accept.
- **Non-TTY stdin without `yes`** → skip silently, no call. Run-log `skipped` with `skip_reason="non_interactive"`. This mirrors the non-TTY branches both sibling gates already take (`if not sys.stdin.isatty():`), and it is what keeps the extra round-trip strictly opt-in.
- **Interactive** → `propose_intents`, then `review_intent_drafts`, then `apply_intent_drafts` on whatever survives.

Two response cases need naming, and neither fails the create:

- `propose_intents` returns `None` (unparseable) → leave intents unset, run-log `skipped` with `skip_reason="unusable_response"`. Follow the precedent of `propose_references_from_claude`, whose failure "never blocks the create".
- Every draft declined, or the model proposed none → run-log `skipped` with `skip_reason="all_declined"`.

The four skip reasons follow `propose_body_sections`' precedent in this same function, where the comment states the rule directly — *the reason IS the gate* — so `plan-tool runs show` can never disagree with what happened.

### The scope decision to be aware of

**Proposing under `--yes` is the judgment call in this step.** It is what keeps the unattended pipelines (`direct-run` / `direct-jira`) from producing plans that step 6 blocks, and it is the `-y`-as-second-opt-in idiom `plan_tool/scope_out.py:scope_out_step` and `plan_tool/reground.py:reground_bridge` already use. The cost is real and should be stated rather than hidden: `plan_tool/bench.py` drives `create_plan` with `yes=True` and its own measured invoker, so a bench seed with no `## Outcome` now spends one extra call inside a harness built to isolate the proposal signal. The alternative — skip under `yes` as well, offering only to a live operator — keeps bench and every unattended run at today's call count but leaves the `--yes` path producing intent-less plans. If that trade should go the other way, the switch is one branch in the ladder above; the bench opt-out is routed to [Deferred](#deferred) because `plan_tool/bench.py` is not in this step's file list.

### What the post-write `--iterate` loop does to the accepted values

**This pass is not the last writer of `intent`, and the plan must say so.** `create --iterate` is ON by default, and its post-write convergence loop re-runs `propose_steps_from_claude` against the edited plan and merges the fresh steps back preserving only `status`. So intents the operator accepted here are replaced by whatever that re-proposal returns — and step 3's soft-keep path can legitimately return steps with `intent is None`, landing an intent-less plan on the very round step 6 blocks, with no second offer.

**The rule: the re-proposal is a step producer like any other, so it is subject to step 3's retry and is *not* authoritative over an operator's accepted value.** The merge preserves an existing usable `intent` the same way it preserves `status` — a re-proposed step that carries no usable intent keeps the one already on the step rather than nulling it. This is the cheaper half of the fix and it needs no new prompt: an accepted intent is operator-reviewed prose, and a later automated pass has no standing to discard it. Where the re-proposal genuinely adds a *new* step, that step has no prior value to preserve and falls to the finding and the walk, exactly like any other post-create producer named in the plan's Architecture.

### Grounding text

`create_plan` already resolves `body_source` (`seed_body` ≻ `from_description`) once, well before this insertion point, with a comment recording why it is resolved once rather than re-derived per consumer. Pass that same value through as step 4's `source_text`, and pass `""` when it is `None` (the interactive path). Do not build a second source ladder, and do not re-read the seed from disk. On the interactive path the prompt is grounded by the `Plan` model alone — step 4's `render_intent_prompt` already builds from the plan title and each target step's title, files, `change_type`, `complexity`, and `depends_on`; `_build_research_context` is the in-file precedent for that same fallback.

### Constraints that are not free to vary

- **Write the plan once.** The accepted values go into the in-memory `Plan` before `write_new_plan`. Do not write, then re-open the path to fill intents, then rewrite — that is a second `write_plan` plus a second reparse for a file `create` owns outright.
- **Only the missing targets are asked about.** A plan or step whose intent already passes `is_usable_intent` must not appear in `plan_needs_intent` / `step_ids`, so its value never reaches the prompt and can never be overwritten. Step 4's parse drops off-target drafts as a backstop; the caller must still not ask.
- **Merge with `model_copy`, never in place.** `apply_intent_drafts` returns a new `Plan`; rebind the local. The concept review's own `model_copy(update={"steps": reviewed_steps})` is the pattern already in this function.
- **Zero extra calls on the happy path.** Once steps 2 and 3 land, a conforming seed leaves nothing missing and this pass never invokes. That is what makes the plan's "no additional Claude call versus today's proposal count" criterion hold for the common case.
- **Do not touch the finding.** `check_intent_presence`, its severity, its two-per-plan roll-up shape, and its `intent-presence` source token belong to steps 6 and 8.
- **No new CLI flag and no new plan-body section.** Intent is frontmatter. Leave `PLAN_BODY_SECTIONS`, `_render_plan_body`, and the distill vocabulary alone.

### If the pass is checkpointed

Every other backend round-trip in `create_plan` is checkpointed — seven constants (`_INITIAL_STEPS_CHECKPOINT_NAME` through `_STEP_GATE_REVIEW_CHECKPOINT_NAME`) — and the operator-decision gates checkpoint their *post-review* result so answers survive a resume. Adding `create-intent` in the same shape is the recommended path, because the most likely failure after this pass is the fail-loud `_(TODO)_` body gate, and without a checkpoint a re-run re-spends the call and re-asks every accept / edit question.

If you add it, **three sites are one set** — add all three or none:

1. the `_INTENT_CHECKPOINT_NAME = "create-intent"` constant beside its six siblings;
2. the seven-pattern glob tuple in `create_plan`'s post-write checkpoint-cleanup block;
3. the `stem.startswith(...)` kind ladder just below it, so `runs` logs the discard under a stable kind label rather than the raw stem.

The payload has to carry the plan-level value as well as the steps, so `_deserialize_reviewed_steps` and `_step_review_input_hash` are models to follow rather than symbols to reuse directly. Skipping the checkpoint is acceptable if the pass's docstring records that decision and its reason.

### Shared locations for the same rule

The core behavior here is *decide which intents are missing, then get one*. Four other places touch that rule and none is edited by this step:

- `plan_tool/review.py:check_intent_presence` computes the same missing set with the same predicate. The two must agree, which is exactly why both call step 1's shared `is_usable_intent` instead of testing emptiness locally. The overlap is two comprehensions, below `tests/test_duplication.py`'s four-line threshold, so it will not trip the guard; consolidating it would need a refactor step `detail` cannot mint. Routed to [Deferred](#deferred).
- `plan_tool/create.py:_propose_step_split`'s prompt never asks for `intent`, so split replacements arrive empty. Placing this pass *after* `_review_step_change_types` catches that gap without teaching a second producer.
- `plan_tool/create.py:_prompt_one_step` and `extract_steps_from_canonical` likewise produce steps with no intent, and are likewise covered by placement rather than by edit.
- `plan_tool/scope_out.py:render_carved_seed` and `plan_tool/reground.py:render_rebaseline_seed` emit no `## Outcome`; step 2 already routed that to [Deferred](#deferred) and this step inherits it — a plan created from a carve or re-baseline reaches this pass with nothing mapped, which is the intended path.

## Tests

All cases land in `tests/test_create.py`, in a new class beside `TestCreatePlanFromDescription`, reusing `_queue_input`, `_basic_metadata_answers`, and `_single_step_answers`. Interactive cases patch the TTY the way the file's existing gate tests do (`monkeypatch.setattr("sys.stdin.isatty", lambda: True)`); `claude_invoker` is a recording fake that returns canned JSON per prompt, so nothing spawns a backend — `tests/conftest.py`'s autouse gate would raise anyway.

### Tests for this step

Gap detection:

- `test_no_call_when_plan_and_every_step_have_intents` — nothing missing means zero intent invocations and a `skipped` / `nothing_missing` phase.
- `test_seed_outcome_leaves_only_the_step_gaps` — a seed with `## Outcome` makes the plan a non-target; only the step ids are asked about.
- `test_step_with_a_usable_intent_is_never_a_target` — its id is absent from the request and its value never appears in the prompt.

Mode ladder:

- `test_non_interactive_without_yes_skips_the_proposal` — no intent call, plan lands with `intent is None`, phase `skipped` / `non_interactive`.
- `test_yes_accepts_every_draft_without_prompting` — the drafts land on the plan and the named steps with no `input_fn` consumption.
- `test_yes_notes_accepted_targets_on_stderr` — one note naming what was accepted.
- `test_interactive_accept_keeps_the_drafted_text` — the draft is what reaches the frontmatter.
- `test_interactive_edit_writes_the_replacement` — the operator's typed text wins over the draft.
- `test_declining_every_draft_leaves_intents_unset` — the plan is written with no `intent:` key and the create still succeeds.
- `test_unusable_response_does_not_fail_the_create` — a `None` proposal leaves intents unset, create returns normally, phase `skipped` / `unusable_response`.

Placement and ordering:

- `test_intents_ride_the_single_initial_plan_write` — `parse_plan` on the written file shows the intents; the file is written once.
- `test_drafts_target_post_split_step_ids` — a wizard split renumbers the steps and the request names the renumbered ids.
- `test_split_replacement_is_offered_an_intent` — a step produced by `_apply_step_split` is in the target set.
- `test_interactive_fallback_steps_are_offered_intents` — steps from `prompt_steps` are targets.
- `test_canonical_extracted_steps_are_offered_intents` — steps from `extract_steps_from_canonical` are targets.

Wiring to step 4's module:

- `test_create_passes_its_claude_invoker_through` — the injected fake is the invoker the proposal uses; no second seam and no real-backend default.
- `test_seed_text_is_the_prompt_grounding` — `body_source` reaches `source_text`.
- `test_interactive_path_passes_empty_grounding` — with no seed, `source_text` is empty and the prompt is built from the plan alone.

Observability:

- `test_run_log_records_the_intent_phase` — a phase entry with the expected outcome and `skip_reason`.
- `test_resume_restores_the_reviewed_intents` — emit only if the checkpoint is added; drop it otherwise.

End-to-end boundary:

- `test_created_plan_emits_no_intent_presence_finding` — `check_intent_presence` over the written plan returns an empty list. This is the case that proves the authoring half is closed.

Approx. 21 cases (20 without the checkpoint). **Green-before-done gate:** the plan sets `enforce_step_tests: true` and this step is `change_type: feature`, so every case above plus `uv run pytest tests/test_create.py -q` must be green before the step is finished. The full suite must also be green — the non-TTY skip is what keeps the file's existing recorded call counts unchanged, so a red elsewhere in `tests/test_create.py` means the ladder is wrong.

## Acceptance criteria

- A `create_plan` run on a TTY, from a seed with no usable `## Outcome`, proposes an intent and — on accept — writes a plan whose `parse_plan(path).intent` is the accepted text.
- The same run with every draft declined writes a plan with `intent is None` and no `intent:` key, and returns a normal `CreateResult`.
- `create_plan(..., yes=True)` with a missing intent writes the drafted value without consuming an `input_fn` answer, and prints one note naming the accepted targets.
- `create_plan` with non-TTY stdin and `yes=False` makes zero intent-proposal invocations, and the total recorded invoker calls match a run whose plan and steps all carry intents.
- A plan and steps that all carry usable intents produce zero intent-proposal invocations.
- The plan file is written once: `parse_plan` on the result path shows the accepted intents, and no second `write_plan` call occurs on the create path.
- After a wizard split, the proposal request names the post-split step ids, and a replacement step with no intent is among them.
- `check_intent_presence(parse_plan(result.plan_path))` returns `[]` for a run in which every draft was accepted.
- **An accepted intent survives the post-write `--iterate` re-proposal.** A full `create --iterate` run in which the operator accepts a drafted intent, and whose re-proposal returns the same step carrying `intent: None`, ends with the operator's accepted text still on that step — the merge preserves a usable existing `intent` the way it preserves `status`.
- `plan_tool/create.py` imports `is_usable_intent` from `plan_tool.review` and defines no second presence or placeholder check — `rg -n 'def .*usable_intent|def .*placeholder_intent' plan_tool/create.py` returns nothing.
- The run log carries a proposal phase whose `skip_reason` is one of `nothing_missing`, `non_interactive`, `unusable_response`, `all_declined` on each skip, and is omitted on the applied path.
- If a checkpoint constant was added, it appears in the cleanup block's glob tuple **and** its kind ladder; if none was added, the pass's docstring says why.
- `git diff --stat` touches only `plan_tool/create.py` and `tests/test_create.py`.
- `uv run pytest tests/ -q` is green, including `tests/test_duplication.py`.
- Every plan already under `docs/implementation-plans/` still parses, and none is rewritten by this step.

## References

- [Increase output consistency (JSON mode) — Claude Platform Docs](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency) — Official guidance on pinning a response shape and handling malformed output; read it for why an unparseable draft response is a skip rather than a create failure.
- [Structured outputs — Claude API Docs](https://docs.claude.com/en/docs/build-with-claude/structured-outputs) — Schema-validated model output, the reference behind step 4's draft-response contract this step consumes.
- [Run Claude Code programmatically (headless mode)](https://docs.claude.com/en/docs/claude-code/headless) — The non-interactive invocation and result envelope behind the `claude_invoker` seam this pass forwards.
- [Models — Pydantic](https://docs.pydantic.dev/latest/concepts/models/) — `model_copy` semantics, for confirming that folding accepted drafts into the plan leaves the concept review's `steps` update and every other field intact.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Loader/dumper reference for the frontmatter round-trip, relevant because the accepted intent becomes an `intent:` value that must re-read equal after the post-write reparse.

## Applicable guardrails

- **The plan's "## Plan intent"** — this step serves the authoring half: closing the paths that can still produce an intent-less plan. Nothing downstream of the plan file is threaded here.
- **The plan's "## Step intent"** — close the last authoring path, and stop there. Do not widen the pass into judging or improving intents that already exist.
- **The plan's "## Out of scope", any validation past presence** — this is the fence that binds hardest here, because a wizard prompt is exactly where a "that looks too short" check feels natural. The only test any value gets is step 1's shared presence predicate. No length cap, no shape rule, no comparison against the plan body, `## Why`, a detail file, or acceptance criteria. The plan marks this permanently refused, so a finding proposing one against this step is invalid rather than deferrable.
- **The plan's "## Out of scope", no parse-time requirement and no migration** — `Plan.intent` and `Step.intent` stay optional, and this pass touches only the plan being created. It never sweeps, backfills, or reads another plan on disk.
- **The plan's "## Out of scope", propagation through the structural verbs listed there** — this step wires nothing into those verbs. The wizard's own in-function split is covered by *placement*, not by editing it.
- **The plan's "## Out of scope", delivery to further consumers** — nothing past the plan file is threaded; the templates that already render the fence pick the value up unchanged.
- **The plan's "## Out of scope", no new parallel surfaces** — serial, one round-trip, no worker pool.
- **The plan's Architecture, "Allowed reorganization: none"** — no module moves and no renderer changes. `plan_tool/scope_fence.py` is not touched; step 4's module owns the whitespace collapse.
- **The plan's Architecture, "the proposer is a remedy on the existing finding, not a new verb"** — this step registers no CLI subcommand, adds no flag, and mints no finding source. It only decides *when* create offers the remedy step 4 built.
- **The plan's Architecture, "produce before require"** — this step must land before step 6 flips the severity. Do not touch `check_intent_presence` here.

## Deferred

- **Teaching `_propose_step_split`'s prompt to ask for `intent`** — step 3 owns the step-proposal contract; this step catches the residual gap by running after the review instead of adding a second producer. Route the prompt change to reconcile or `BACKLOG.md`.
- **Adding `## Outcome` to the tool-generated forward seeds** (`plan_tool/scope_out.py:render_carved_seed`, `plan_tool/reground.py:render_rebaseline_seed`) — neither file is in this step's list; step 2 already routed it, and a plan created from a carve reaches this pass with nothing mapped, which is the intended path.
- **A `create_plan` opt-out so `plan_tool/bench.py` keeps its measured call count flat** — `plan_tool/bench.py` is not in this step's file list, and a parameter with no caller setting it buys nothing. File it in `BACKLOG.md` if the extra call distorts a bench measurement.
- **Consolidating the missing-intent set computation shared with `plan_tool/review.py:check_intent_presence`** — two short comprehensions over the same shared predicate, below the duplication guard's threshold; merging them needs a refactor step `detail` cannot mint.
- **The parseable directive on the `intent-presence` finding** — step 6 owns it. This pass computes its own targets from the `Plan` model and parses no finding.
- **Raising the finding to `medium` and making it blocking** — step 6, deliberately last.
- **Documenting the create-time offer** — step 7 owns `PLAN_FORMAT.md`, `SEED_FORMAT.md`, and `docs/CREATE_FROM_EXISTING_FLOW.md`.
- **Recording the accept / edit / decline choice through `plan_tool/telemetry.py:record_decision`** — a new decision kind is not among the plan's allowed behavior changes; raise it as a scope decision rather than adding it here.
- **Offering an intent inside the post-write convergence loop** (`--iterate`) — that loop re-proposes steps after the plan is on disk; this step is create's pre-write gate. The merge preserves an accepted intent (see above) rather than re-offering.
