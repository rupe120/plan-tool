> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add an intent-proposal helper module that drafts a one-liner and takes accept, edit, or decline

> **Carved 2026-08-03.** The apply-or-recommend bridge this step
> originally built (`propose_intent_bridge`) was deleted in `ff908421`:
> the review/reconcile walk-dispatch arm was its only consumer and was
> carved out to `plan-seeds/intent-required-carved-*`. This step ships
> the in-memory halves only. Do not re-add it here.


## Summary

Create `plan_tool/intent_proposal.py`: a domain module that asks the backend for a one-line `intent` for a plan and for the steps that lack one, shows each draft to the operator as accept / edit / decline, and returns the plan carrying the accepted values for the caller to persist. The design decision is that the module is shaped like `plan_tool/gates.py` — pure domain logic, no CLI imports, an `invoker` the caller must pass — so step 5's create path can use it without a plan file on disk. The only check applied to a draft is step 1's shared `plan_tool/review.py:is_usable_intent`; nothing judges quality, length, or shape. On green, one backend round-trip produces drafts for a whole plan, declining every draft leaves the plan file unchanged, and accepting writes a one-line `intent:` onto the plan and each named step.

## Table of Contents

- [Summary](#summary) — what the step builds and what is true on green.
- [Why](#why) — why the missing-intent finding needs a remedy attached to it.
- [Input](#input) — the four contracts this module reads and the limits on checking them.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files, and why nothing else is touched.
- [Implementation](#implementation) — the module's public surface, the constraints that are not free to vary, and the rejected alternatives.
- [Tests](#tests) — the cases this step adds and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checks a reviewer or CI can run.
- [References](#references) — the docs bearing on a JSON response contract and an injected backend call.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this module's code.
- [Deferred](#deferred) — the consumer, the docs, and the severity flip this step leaves alone.

## Why

`plan_tool/review.py:check_intent_presence` fires on every plan in the repo and offers no fix. Its `suggested_action` is literally "add a one-line `intent:` to the plan frontmatter" — a reprimand, not a remedy. That is the shape the plan's Problem statement names as the way to train operators out of a finding channel. The plan makes the finding blocking in step 6, and a blocking finding with no attached fix is worse than an advisory one. This module is the fix: it drafts the line, hands it to the operator, and writes what the operator keeps. It lands before its consumer (step 5's create wizard) so that step wires to a module that already exists and is already tested on its own.

## Input

This module reads four contracts and changes none of them.

- **`plan_tool/review.py:is_usable_intent`** — step 1 publishes this predicate. Plain-string signature (`Optional[str] -> bool`); its three non-values are `None`, empty after `.strip()`, and a bare TODO/TBD marker. This module uses it in exactly two places: dropping a draft the model returned that carries nothing, and treating a blank or placeholder edit as a decline. It is the *only* check any draft gets. The plan's `depends_on` does not record an edge from this step to step 1 — step 1 is `current`, so it lands first in practice; if it has not, the public name does not exist yet and this step is blocked on it. Do not import the private `_is_usable_intent` as a workaround, and do not write a second copy of the check.
- **`plan_tool/schema.py`, `Plan.intent` and `Step.intent`** — both `Optional[str] = None`, both elided from rewritten frontmatter when `None`. The field comments record that empty, placeholder, and multi-line values all parse: presence is checked in `review.py`, never at parse time. Nothing here changes that.
- **`plan_tool/scope_fence.py:collapse_intent_to_one_line`** — the one whitespace normalizer every intent writer shares, so a stored value is byte-identical to what the fence renders.
- **`plan_tool/scope_fence.py:_render_intent_section`** — the shipped fence renderer collapses whitespace in an intent before rendering it, because a real newline in the value could put a `##` at line start and forge a heading inside a block the prompt labels authoritative. That is the reason to write a single-line value here too. `scope_fence.py` is read for this fact only; the plan's "Allowed reorganization: none" keeps it untouched.

**What this module cannot verify.** Only that a draft is present and is not a placeholder. Nothing checks that a drafted intent is *true*, that it matches the plan body or a step's `## Why`, or that it is one line — the prompt asks for one line, and asking is not checking. The tests drive canned responses through the real parser and the real predicate, which proves the response contract is satisfiable, not that the backend usually satisfies it.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/intent_proposal.py` — the whole module: prompt render, response parse, the accept/edit/decline wizard, and the pure plan transform.
  - `tests/test_intent_proposal.py` — the module's suite.
- **Existing files (edits only):** none. Nothing in `plan_tool/` imports this module yet — step 5 wires the one consumer. The prompt text lives inside the module rather than in a new file under `plan_tool/prompts/`, so this step adds no third file (see [Implementation](#implementation)).

## Implementation

**What must be true when the step is done.** A caller holding a `Plan` and the ids of the steps missing an intent can get drafts in one backend round-trip, walk the operator through them, and end with either accepted values applied or nothing changed. No accepted value reaches the returned plan without the operator saying yes.

**Shape: follow `plan_tool/gates.py`.** That module is the closest sibling — it proposes a per-step value through the backend, parses strict JSON, and hands the result to a wizard that keeps / edits / drops each one. Mirror its layering:

- **No CLI imports.** This module is imported by `plan_tool/create.py` (step 5). First-party imports stay at `plan_tool.schema`, `plan_tool.parser`, `plan_tool.review` (for the predicate), This is not a leaf module and does not need to be — but check the edge stays acyclic: `review.py` imports `create` / `detail` / `launcher` only inside functions, so nothing pulls this module back into `review`.
- **`invoker` is a required keyword, with no default.** `gates.py:suggest_gates` takes `invoker: GateInvoker` with no default and the CLI passes `plan_tool/create.py:shell_claude_invoker`. Do the same. A real-backend default would put this module on TESTING.md's fallback-seam catalog, and TESTING.md is not in this step's file list — a required seam removes the obligation instead of deferring it. Declare the alias beside the dataclasses (`IntentInvoker = Callable[[str], str]`).

**Recommended public surface** (names are a recommendation; the split between them is not):

- `IntentDraft` — a frozen record: `step_id: Optional[int]` (`None` means the plan-level field) and `text: str`.
- `render_intent_prompt(plan, *, plan_needs_intent: bool, step_ids: list[int], source_text: str = "") -> str` — builds the prompt from the `Plan` model only. `source_text` is free-text grounding the *caller* supplies: step 5 passes the seed text. The module never decides where grounding comes from and never opens a file to find it. Grounding material otherwise is the plan title plus each target step's title, files, `change_type`, `complexity`, and `depends_on`.
- `parse_intent_drafts(raw, *, plan_needs_intent: bool, valid_step_ids: set[int]) -> Optional[list[IntentDraft]]` — lenient on entries, strict on the envelope, exactly like `gates.py:parse_gate_suggestions`: no parseable `[...]` returns `None` so the caller can tell "unparseable" from "the model proposed nothing", which is a valid empty array. Drop an entry whose `target` is neither `"plan"` nor an id in `valid_step_ids`, and drop one whose text fails `is_usable_intent`. Do **not** retarget a bad id the way gates does — a gate lands on a step the operator can move it off, but an intent written onto the wrong step is a false statement about that step.
- `propose_intents(plan, *, invoker, plan_needs_intent, step_ids, source_text="", run_logger=None) -> Optional[list[IntentDraft]]` — one round-trip for the whole plan. When `run_logger` is passed, bracket the call with `install_call_end_sink` / `uninstall_call_end_sink` in a `try/finally` the way `suggest_gates` does, so the call shows up in `plan-tool runs`.
- `review_intent_drafts(drafts, *, input_fn) -> list[IntentDraft]` — the accept / edit / decline walk, modelled on `plan_tool/cli/gates_cmd.py:_ask_suggestion` (which is the keep/edit/move/drop version of the same idea). Enter defaults to accept; `(e)dit` reads a replacement; a blank or placeholder replacement is a decline; `(d)ecline` drops the draft; an unrecognized key re-prompts rather than guessing.
- `apply_intent_drafts(plan, drafts) -> Plan` — pure model transform, no IO, mirroring `gates.py:apply_gate_suggestions`. Use `model_copy(update=…)` and return a new `Plan`; steps with no accepted draft come back unchanged.

**Constraints that are not free to vary:**

- **Only the named targets get written.** A draft for a step outside `step_ids`, or for the plan when the plan already has a usable intent, must never reach `apply_intent_drafts`. The operator asked about specific gaps.
- **Collapse whitespace before writing.** Write one line. This is normalization, not validation — nothing is rejected for being long or oddly shaped. The reason is the fence-forging hazard `scope_fence.py:_render_intent_section` already guards at render time.
- **One round-trip per plan, not one per step.** Cost, and it matches the finding's at-most-two-per-plan roll-up shape.
- **Mint no `Recommendation` and add no source token.** `reground.py`'s module docstring states the rule and it applies here: the caller already holds the `intent-presence` finding that fired this.
- **Watch `tests/test_duplication.py`.** `_confirm_reground`, `scope_out._confirm_scope_out`, and `detail._confirm_merge` share a non-TTY-declines idiom, and the guard's baseline is zero duplicate function bodies of four lines or more (normalized past docstrings, function names, and parameter names). The three-way re-prompting walk here is genuinely different code, so it should not collide — but if a helper you write does, `ALLOWED_DUPLICATE_GROUPS` with a stated reason is the supported answer, not a merge that drags three modules into this diff.
- **The prompt stays inside the module.** `gates.py` builds its prompts as Python strings and this step's file list has room for exactly two files. A template under `plan_tool/prompts/` would be a third file, and templates there render through `renderer.render_prompt` with `${...}` placeholders — machinery this one directed call does not need.

## Tests

All cases live in `tests/test_intent_proposal.py`. Every one uses a fake `invoker` returning canned text and a fake `input_fn`, so nothing spawns a backend or blocks on stdin — `tests/conftest.py`'s autouse gate would raise anyway.

### Tests for this step

Prompt:

- `test_prompt_names_every_requested_step_id` — each id in `step_ids` appears in the rendered prompt.
- `test_prompt_omits_the_plan_arm_when_the_plan_intent_is_present` — `plan_needs_intent=False` produces no plan-level ask.
- `test_prompt_carries_the_callers_source_text` — the caller's grounding text reaches the prompt verbatim.
- `test_prompt_never_quotes_an_existing_intent` — a step whose intent is fine is not a target and its value is not in the prompt.

Parse:

- `test_unparseable_response_returns_none` — prose with no JSON array is `None`, not an empty list.
- `test_empty_array_parses_as_no_drafts` — a valid `[]` is an empty list, distinct from `None`.
- `test_malformed_entry_is_dropped_not_fatal` — one bad object does not sink the batch.
- `test_draft_for_an_unknown_step_id_is_dropped` — an id outside the plan is dropped, never retargeted.
- `test_draft_for_a_step_not_requested_is_dropped` — a step with a usable intent gets no new one.
- `test_placeholder_draft_is_dropped` — a `_(TODO)_` draft fails `is_usable_intent` and never reaches the operator.
- `test_plan_target_maps_to_the_plan_level_draft` — `"target": "plan"` yields `step_id=None`.

Wizard:

- `test_accept_keeps_the_drafted_text` — `a` returns the draft unchanged.
- `test_enter_defaults_to_accept` — empty input accepts.
- `test_edit_replaces_the_text` — the typed replacement is what comes back.
- `test_blank_edit_is_a_decline` — an empty replacement drops the draft.
- `test_placeholder_edit_is_a_decline` — a `TODO` replacement fails the shared predicate and drops.
- `test_decline_drops_the_draft` — `d` returns nothing for that target.
- `test_unrecognized_key_re_prompts` — a junk key asks again instead of guessing.

Pure transform:

- `test_apply_sets_the_plan_and_step_intents` — accepted drafts land on the right targets.
- `test_apply_leaves_untargeted_steps_unchanged` — every other step comes back as it was.
- `test_apply_collapses_whitespace_to_one_line` — a multi-line draft is written as one line.
- `test_apply_returns_a_copy` — the input `Plan` is not mutated.

Bridge:

- `test_noop_when_nothing_is_missing` — outcome `noop`, invoker never called.
- `test_missing_step_id_refuses_before_any_call` — outcome `step-missing`, invoker never called.
- `test_unparseable_response_is_proposal_unusable` — outcome `proposal-unusable`, file unchanged.
- `test_declining_every_draft_leaves_the_file_unchanged` — outcome `recommended`, file bytes equal before and after.
- `test_accepted_drafts_are_written_to_the_frontmatter` — outcome `applied`; re-`parse_plan` shows the values.
- `test_non_tty_without_yes_declines_and_writes_nothing` — the unattended path never mutates.
- `test_invoker_has_no_default` — introspect the signature; a real-backend default is what the required seam exists to prevent.

Approx. 30 cases. **Green-before-done gate:** the plan sets `enforce_step_tests: true` and this step is `change_type: feature`, so `tests/test_intent_proposal.py` must exist and every case above must pass before the step is finished.

## Acceptance criteria

- `plan_tool/intent_proposal.py` and `tests/test_intent_proposal.py` exist; `uv run pytest tests/test_intent_proposal.py -q` is green.
- `uv run pytest tests/ -q` is green, including `tests/test_duplication.py`.
- `rg 'from plan_tool.cli' plan_tool/intent_proposal.py` returns nothing.
- The module calls `is_usable_intent` and defines no second presence check of its own — `rg 'def .*usable|def .*placeholder' plan_tool/intent_proposal.py` returns nothing.
- The propose function's `invoker` parameter has no default value.
- Declining every draft on the interactive path leaves the plan file's bytes unchanged.
- Accepting a draft with an embedded newline writes a single-line `intent:` value that `parse_plan` reads back equal to the collapsed text.
- The module mints no `Recommendation` — `rg 'Recommendation' plan_tool/intent_proposal.py` returns nothing.
- No file outside this step's two `creates:` paths is modified.

## References

- [Structured outputs — Claude API Docs](https://docs.claude.com/en/docs/build-with-claude/structured-outputs) — Schema-validated model output, the reference for pinning the draft-response shape rather than hoping for it.
- [Increase output consistency (JSON mode) — Claude Platform Docs](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency) — Official guidance on pinning a response shape and handling malformed output, which is what the strict-envelope / lenient-entry parse implements.
- [Run Claude Code programmatically (headless mode)](https://docs.claude.com/en/docs/claude-code/headless) — The non-interactive invocation and result envelope behind the `invoker` seam this module requires its caller to supply.
- [dataclasses — Data Classes — Python 3 documentation](https://docs.python.org/3/library/dataclasses.html) — Frozen dataclass and field-default rules for `IntentDraft`.

## Applicable guardrails

- **The plan's "## Out of scope", any validation past presence.** This is the fence that binds this step hardest, because a drafting module is exactly where a length cap or a quality check feels natural. The only check on a draft is the shared presence predicate. No cap on length, no required phrasing, no comparison against the plan body, `## Why`, a detail file, or acceptance criteria. Asking for one line in the prompt is allowed; rejecting a draft for not being one line is not. A finding proposing such a check is invalid, not deferrable.
- **The plan's "## Out of scope", no parse-time requirement and no migration of existing plans.** This module writes one plan at a time, only after a confirm. It never sweeps, never backfills, and never touches a plan the caller did not name.
- **The plan's "## Out of scope", propagation through the structural verbs listed there.** This module is not wired into any of them.
- **The plan's "## Out of scope", no new parallel surfaces.** Serial, one round-trip, no worker pool.
- **The plan's Architecture, "Allowed reorganization: none".** `plan_tool/scope_fence.py` is read for one fact and left alone; no module moves and no renderer changes.
- **The plan's Architecture, "the proposer is a remedy on the existing finding, not a new verb".** This step registers no CLI subcommand and mints no new finding source. Detection stays where it is; only mutation is gated.
- **The step's stated intent.** The deliverable is a fix an operator can accept. Do not extend it into deciding *when* to offer that fix — that judgment belongs to the two consumers.

## Deferred

- **Wiring into the create wizard** — step 5 owns it; that path has no plan file on disk yet, which is why this module never opens or writes one.
- **Dispatch from the review and reconcile apply walk** — step 7 owns it, including the opt-in token and the staleness guard its sibling dispatchers carry.
- **The parseable directive on the `intent-presence` finding** — step 6 owns it. This module takes step ids as plain input and parses no finding.
- **Raising the finding to `medium` and making it blocking** — step 6, and deliberately last: the requirement lands only after authoring can satisfy it.
- **Documenting both intent fields and the `## Outcome` mapping** — step 7 owns `PLAN_FORMAT.md`, `SEED_FORMAT.md`, and the flow docs.
- **A `CAPABILITIES.md` entry** — none is owed. `plan_tool/capability_catalog.py:check_capabilities` pairs capabilities with registered subcommands, and this step registers none.
- **Recording the accept / edit / decline choice through `plan_tool/telemetry.py:record_decision`** — a new decision kind is not in the plan's allowed behavior changes. Raise it as a scope decision rather than adding it here.
- **Bulk-filling intents across the repo's existing plans** — the plan's no-migration fence rules it out; the remedy runs one plan at a time behind a confirm.
