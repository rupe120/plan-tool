> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Ask create's step proposal for a one-line intent per step and parse it

## Summary

This step makes `plan-tool create`'s step proposal ask the model for a one-line `intent` per step and lands the answer on step 1's `Step.intent`. Two edits in `plan_tool/create.py`: `_render_from_prompt` gains an instruction plus the `intent` key in its JSON-shape line, and `_parse_steps_json` reads the key and passes it to the `Step(...)` it already builds. The main design decision is that **intent goes straight onto the `Step`, not into a caller-supplied side dict** — the neighbouring `rationale` uses `rationales_out` only because it has no schema slot, and copying that shape is the tempting mistake. The read is soft like `change_type` and `gate`: a missing, null, non-string, or blank `intent` becomes `None` and never sinks the proposal. On green, a proposal that returns intents produces a plan whose steps each carry one, and a proposal that returns none produces exactly the plan file `create` writes today.

## Table of Contents

- [Summary](#summary) — what ships, the field-not-side-dict decision, and the result on green.
- [Why](#why) — why the one moment a model decides *why* each step exists is the cheapest place to capture it.
- [Input](#input) — the six contracts this step reads and does not own, and what the tests cannot prove.
- [Files (creates vs edits)](#files-creates-vs-edits) — two edited files, no new files.
- [Implementation](#implementation) — the parse, the prompt item, the rejected alternative, and six gotchas.
- [Tests](#tests) — approx. 19 new cases, two rewritten assertions, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the YAML, pytest, and prompt-wording docs this step leans on.
- [Applicable guardrails](#applicable-guardrails) — the fence entries that bind, and the two places breaking them is tempting.
- [Deferred](#deferred) — what steps 8, 9, and 10 own, and the producers left without an intent on purpose.

## Why

Step 6 fills a plan's intent from the seed's `## Outcome`. Nothing fills a *step's*, and the step-level why is exactly what the plan says gets thrown away and re-derived on every `detail` pass. `create`'s step proposal is the one moment where a model has just decided why each step exists: item 6 of the prompt already makes it argue the decomposition out loud, asking for a one-line `rationale` defending each `change_type` classification. That reasoning is captured, shown once in the interactive review, and dropped — `_parse_steps_json` keeps it in a caller-supplied dict because `Step` had nowhere to put it. Step 1 gives it somewhere. So the marginal cost here is one instruction and one assignment, and the payoff is that every step a `create` run authors arrives with its purpose already stated instead of waiting for an author to backfill it.

## Input

Six contracts this step reads and does not own. Read each off HEAD before you start; where a landed name differs from a name below, the landed name wins.

- **Step 1's step-level field.** `Step.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD), `Optional[str] = None`, storing whatever it is handed with no stripping, no cap, and no validator. This step is the first producer of a per-step value, so whatever shaping happens has to happen here.
- **Step 6's one-line rule.** Step 6 fills `Plan.intent` from the seed's `## Outcome` and settles what "one line" means for this plan: collapse every whitespace run to a single space, no truncation, no sentence splitting. Apply the same rule to the step-level value. Read what step 6 actually landed — if the collapse is a standalone helper, call it; if it is inline in step 6's lift, either lift it out or repeat the two-line collapse. Do not invent a second, different rule for the same field.
- **`_parse_steps_json`'s strict-vs-soft split.** The function already treats its keys two ways, and the two sit within a few lines of each other. `complexity`, `files`, `creates`, `depends_on`, and `concept_ids` **reject the whole proposal** on a bad value (`return None`). `change_type`, `rationale`, and `gate` are **soft** — a bad value is dropped and the loop continues. `intent` joins the soft group; the existing comments in the function explain why the split exists and are worth reading before adding to it.
- **The parser's three callers.** `propose_steps_from_claude` calls it for the primary response and again for the one repair retry, and `_propose_step_split` calls it for the create-wizard's `(s)plit` action. One read site in the parser covers all three; there is no second parse to update.
- **The checkpoint contract.** `_initial_steps_input_hash` keys the `create-initial-steps` checkpoint on slug + description + output dir (+ iteration when non-zero). It does **not** hash the prompt text, so a checkpoint saved before this change still validates and replays a response with no `intent` keys.
- **The step-review round trip.** `_review_step_change_types` checkpoints its result as `Step.model_dump(mode="json", exclude_none=True)` and `_deserialize_reviewed_steps` rebuilds it with `Step(**item)`. Intent rides both directions with no edit, and `exclude_none=True` keeps an absent intent out of the payload. Pin it with a test; do not add code to it.

**What the tests cannot prove.** Every case here drives a canned invoker response. That shows the parse handles what a model can return and that the prompt states a contract a model *can* satisfy — it says nothing about how often a real model returns a useful intent rather than a restated title. Measuring that needs real briefs and somewhere to record the result; it is out of this step.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/create.py`
  - `_render_from_prompt` — add the per-step intent instruction and the `intent` key to the JSON-shape object line; adjust the dynamic numbering start for the gate / foundational tail items.
  - `_parse_steps_json` — read `intent` softly, collapse it to one line, and pass it to the `Step(...)` construction.
- `tests/test_create.py`
  - New parser cases, new prompt cases, new end-to-end cases.
  - Rewrite the two `TestRenderFromPromptABMode` assertions that pin the current six-item core (named in [Implementation](#implementation)).

## Implementation

**What must be true on green:**

- A proposal whose objects carry a usable `"intent"` produces steps whose `Step.intent` holds that text as one line.
- A proposal that omits the key, or returns a bad value for it, produces exactly the steps `create` produces today — `intent` is `None`, the step list is not rejected, nothing warns.
- The proposal prompt asks for the key in **all four** `_render_from_prompt` arms, and its numbered items stay contiguous in each.

### The parse

- **Put the value on the `Step`, not in a side dict.** The `rationale` handling three lines away writes into a caller-supplied `rationales_out` because `rationale` has no `Step` field. `intent` does. Adding an `intents_out` parameter mirrors the wrong half of the neighbour and creates a second channel for a value that already has a home.
- **Read it softly.** A missing key, JSON `null`, a non-string (int, list, mapping), or a blank / whitespace-only string all become `None` and the loop continues. Never `return None` for the whole list on a bad `intent`.
- **Collapse to one line, then strip.** Per step 6's rule. A JSON string can legally carry `\n`, and a multi-line value here becomes a multi-line YAML scalar in the written plan.
- **Do not truncate.** An over-long intent is a mechanical property this plan routes to step 2's advisory channel. Cutting the text at N characters manufactures a false statement to dodge an advisory finding.
- **Nothing here judges the value.** No comparison against the step's title, `files`, or `rationale`.

### The prompt

**Recommended shape:** a new numbered item **7**, sitting after item 6 and before the dynamic tail, so it survives both A/B arms the way item 6 does. The tail's `next_num` then starts at 8, and the existing renumbering machinery keeps the gate and foundational items gap-free when either is omitted. Add `"intent": str` to the JSON-shape object line beside `"rationale": str`.

What the instruction has to say:

- **One line, stating what the step is for** — the purpose, not a restatement of the title and not a summary of the file list.
- **How it differs from `rationale`, explicitly.** `rationale` defends the `change_type` classification; `intent` states why the step exists. The two keys are adjacent in the shape line and adjacent in the instructions, so without a stated contrast the model returns the same sentence twice and the field carries nothing new.
- **Plain, everyday words**, matching the rule the trailing paragraph already imposes on `title`.

**The alternative, and its trade:** hang the instruction off the trailing shape paragraph instead — the place the plain-words `title` rule already lives. That is lower churn: no renumbering, and the two A/B numbering tests below stay green. It also buries a per-step contract in a paragraph about JSON shape, which is why the numbered item is the recommendation. Either is defensible; if you take the trailing-paragraph path, the two rewritten test cases below are unnecessary and the rest of the roster stands.

### Gotchas

- **Two A/B tests are correct-by-design today and this reddens them.** `TestRenderFromPromptABMode::test_split_renumbers_when_gate_omitted` asserts the foundational item takes number 7 when the gate item is omitted, and `test_split_both_omitted_drops_to_six_items` asserts `"7. "` never appears with both omitted. A fixed item 7 makes both wrong. Rewrite them — including the second's name, which states a count — and keep them asserting contiguity rather than a hardcoded ceiling.
- **`_DERIVE_FROM_INTENT_SECTIONS` is a different thing entirely.** Grepping `intent` in `plan_tool/create.py` lands on the body-section synthesis policy — the `[derive from intent]` tag `_render_section_shapes_block` emits, which tells the distill and synthesis passes which plan-body sections may be authored from a stated goal. It has nothing to do with `Step.intent`. Leave it alone, and do not name the new work anything that reads like it.
- **A stale checkpoint replays without intents.** Because the prompt text is not hashed, a `create-initial-steps` checkpoint from before this change resumes cleanly and yields steps with no intent. The soft parse makes that harmless and `--no-resume` is the operator's out. Do **not** fix it by hashing the prompt — that invalidates every checkpoint on disk on every future prompt edit, which is the scenario the hash's docstring says it exists to avoid.
- **The create-wizard split clears intent, and that is the decision.** `_propose_step_split`'s prompt names a closed key list that does not include `intent`, so both replacement halves come back `None` and the original step's value disappears with the step. That matches this plan's rule that a propagation must be able to *clear* the field rather than carry a value the split made false. Pin it with a test so it stays a decision instead of an accident. The `plan-tool split` / `merge` verbs (`plan_tool/detail.py:split_step`) are step 8's, not this step's.
- **Do not move any other key across the strict/soft line.** The change is additive; `complexity` keeps rejecting the list, `gate` keeps dropping bad entries.
- **No prompt-budget bookkeeping to add.** `_maybe_warn_create_budget` measures the rendered prompt, so the extra instruction is accounted for already.

## Tests

All cases land in `tests/test_create.py`, reusing its existing `_queue_input` / `_basic_metadata_answers` / recording-invoker helpers rather than adding fixtures. Parser cases fit a new class beside `TestParseStepsJsonChangeType` and `TestParseStepsJsonGate` (suggested `TestParseStepsJsonIntent`); prompt cases extend `TestRenderFromPromptABMode`; the end-to-end cases extend the `create_plan` classes that already drive a canned proposal.

### Tests for this step

Parser cases (approx. 9):

- `test_intent_lands_on_the_step` — a one-line `"intent"` comes back on `Step.intent` unchanged.
- `test_missing_intent_key_leaves_none` — an object with no `intent` key parses, `intent is None`.
- `test_null_intent_leaves_none` — JSON `null` is not an error.
- `test_non_string_intent_leaves_none` — parametrized over int, list, and mapping.
- `test_whitespace_only_intent_leaves_none` — `"   "` is absence, not a value.
- `test_multi_line_intent_collapses_to_one_line` — a `\n`-bearing string comes back with no newline and single spaces.
- `test_bad_intent_does_not_reject_the_proposal` — one step with a bad `intent` still yields the full list with every other step's fields intact.
- `test_long_intent_is_not_truncated` — a 400-character intent comes back whole.
- `test_intent_is_not_captured_in_rationales_out` — the two keys stay separate channels; `rationales_out` holds only rationales.

Prompt cases (approx. 5, in `TestRenderFromPromptABMode`):

- `test_prompt_asks_for_a_per_step_intent` — the instruction is present in the combined arm and in the both-omitted arm.
- `test_prompt_declares_the_intent_json_key` — `"intent": str` appears in the shape line in every arm.
- `test_prompt_separates_intent_from_rationale` — the sentence distinguishing the two keys is present.
- `test_split_renumbers_when_gate_omitted` *(rewritten)* — with the gate item omitted, the foundational item takes the number right after the intent item and no number is skipped.
- `test_split_both_omitted_drops_to_seven_items` *(rewritten and renamed from `..._six_items`)* — with both omitted, items 1–7 are present, nothing higher is, and the intent item is one of them.

End-to-end cases (approx. 5):

- `test_proposed_step_intents_land_in_the_written_plan` — canned proposal with intents; re-parse the written plan and check each `step.intent`.
- `test_proposal_without_intents_writes_no_intent_key` — no `intent:` line anywhere in the written file, and the same number of backend calls as the intent-bearing run.
- `test_intent_survives_the_step_review_checkpoint` — seed a `create-step-review` checkpoint holding intents and confirm the restored steps still carry them.
- `test_stale_checkpoint_without_intent_still_creates` — a cached `create-initial-steps` payload with no `intent` keys resumes and writes a plan whose steps have none, with no warning and no failure.
- `test_create_split_replacements_carry_no_intent` — `_propose_step_split`'s two halves both come back with `intent is None`.

**Green-before-done gate:** every case above, plus the existing `tests/test_create.py` and `tests/test_parser.py` suites with no assertion edits beyond the two rewritten A/B numbering cases, must be green before this step is finished.

## Acceptance criteria

- `_parse_steps_json(json.dumps([{"title": "t", "intent": "Make X true."}]))[0].intent == "Make X true."`.
- A proposal object carrying `"intent": 3` still yields a one-step list, and that step's `intent is None` — the list is not rejected.
- `"\n" not in step.intent` for every step the parser returns with a non-`None` intent.
- `_render_from_prompt("x")` and `_render_from_prompt("x", omit_gate_item=True, omit_foundational_item=True)` both contain the intent instruction and the literal `"intent": str`.
- In all four `_render_from_prompt` arms the numbered items run contiguously from 1 with no gap — asserted on the rendered numbers, not against a hardcoded maximum.
- A `create_plan` run over a canned proposal carrying intents writes a plan where `rg '^  intent:' <plan>` matches once per step; the same run with the key removed writes a file where it matches nothing.
- Both replacements returned by `_propose_step_split` have `intent is None`.
- `rg 'intents_out' plan_tool/create.py` returns nothing — no second side channel was added.

## References

- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — scalar styles and line folding: what "one line" has to mean for a value that gets written into frontmatter.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — `safe_dump` wrapping and re-parse folding, the round-trip behavior a long collapsed intent depends on.
- [Be clear, direct, and detailed — Claude Docs](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct) — phrasing the new prompt item so it constrains what the model returns instead of restating the title.
- [How to parametrize fixtures and test functions — pytest](https://docs.pytest.org/en/stable/how-to/parametrize.html) — table-driven form for the bad-value cases (int, list, mapping, blank, null).

## Applicable guardrails

- **Nothing becomes required at parse time, and no plan on disk is migrated.** A missing or malformed `intent` must never reject a proposal, never warn, and never block a create. **The place breaking this is tempting:** the parser's strict arm. `complexity` sits a few lines above and rejects the entire step list on a bad value, so copying the nearest neighbour is exactly the wrong move here — copy the `change_type` / `gate` treatment instead.
- **No check comparing an intent against prose or against a diff.** This step parses a value and stores it. **The second tempting place:** the change-type review loop, where the operator already sees the title and the rationale side by side and a "these two disagree" nudge would be one line. Do not add it; the plan bans intent-vs-work agreement checking at every level, and cites the withdrawn per-`change_type` test-ordering contract as the precedent.
- **Findings asking for more than presence go to the backlog.** A finding that a proposal should be rejected for a missing intent, or that intent should become required, is outside this fence — file it in `BACKLOG.md` rather than applying it.
- **Allowed behavior changes.** The fence's list covers rendering the two fields *into* the detail and run prompts (steps 4 and 5). This step changes the create step-proposal prompt in the other direction — asking the model to *produce* the field, which is what the plan's own scope names ("`create` proposes step intents"). It renders no intent into any prompt, adds no flag, no report line, and no body section.

## Deferred

- **The interactive step wizard** — the hand-authored path that builds a step from `input_fn` answers gains no intent question. There is no model to ask, and step 6 made the same call for the plan-level field on the no-seed path. An author adds `intent:` by hand.
- **Canonical seed import** — `extract_steps_from_canonical` copies fields out of `plan_tool/canonical.py`'s strict `## Steps` shape, which has no `Intent:` line. Adding one means changing that module's re-render round-trip equality check, outside this step's files. File it in `BACKLOG.md`.
- **Showing the intent in the change-type review loop** — `_ask_change_type` already displays the proposed `change_type` and its rationale; adding the intent beside them is display-only polish with no bearing on whether the value lands.
- **Consolidation steps from the foundational-logic sweep** — `plan_tool/foundational_logic.py:merge_sweep_into_steps` appends a fresh `refactor` step with no intent. Another module, and step 2's advisory check surfaces the absence.
- **`plan-tool split` and `plan-tool merge`** — step 8 states what those verbs do with a step's intent, in `plan_tool/detail.py`. This step covers only the create wizard's own `(s)plit` action, whose two halves come back cleared.
- **The scope-out and reground forward seeds** — step 9.
- **Surfacing a missing or over-long intent** — step 2's advisory check owns it and fires on the written plan; this step reads no cap constant.
- **Getting the intent in front of a model** — step 4 renders it into the detail prompt, step 5 into the run and run-jira prompts.
- **Documenting the field and the propagation rules** — step 11, in `PLAN_FORMAT.md` and `SEED_FORMAT.md`.
