> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Ask for `intent` in the step-proposal JSON and retry once when a proposal leaves it out

## Summary

Add `intent` to the step-proposal JSON contract in `plan_tool/create.py`: `_render_from_prompt` asks for it as a required key on every proposed step, `_parse_steps_json` reads it onto `Step.intent`, and `propose_steps_from_claude` retries once when a proposal comes back missing one. The retry spends the function's **existing** single repair attempt — no new Claude round-trip is added, which is the whole point of the step. Whether a value counts is decided by step 1's public `plan_tool/review.py:is_usable_intent`, applied in exactly one place. A missing intent is a *soft* rejection: after the retry the valid steps are kept, never discarded, because the `intent-presence` finding and the steps 4/5 proposer are the standing remedy. On green, a `create` run whose proposal carries intents writes an `intent:` line onto every step in the new plan's frontmatter, and a proposal that omits them makes exactly two invoker calls instead of one.

## Table of Contents

- [Summary](#summary) — what the step does and what is true when it lands.
- [Why](#why) — why the field is unreachable today and why this call is the place to fix it.
- [Input](#input) — the four contracts this step reads and what it cannot check about them.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched and the per-file edits.
- [Implementation](#implementation) — the prompt change, the parser change, the retry design, and the rejected alternatives.
- [Tests](#tests) — the cases this step adds, the fixture sweep it forces, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checks a reviewer or CI can run.
- [References](#references) — the docs that bear on a JSON-shape contract and a re-prompt loop.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step's code.
- [Deferred](#deferred) — the other step producers and later steps this one leaves alone.

## Why

`create` cannot author a step intent today. `Step.intent` exists in `plan_tool/schema.py`, the shared fence renders it, and `plan_tool/review.py:check_intent_presence` flags its absence — but the step-proposal prompt never asks for the key and `_parse_steps_json` never reads it, so every step `create` writes lands with `intent: None`. That is why the advisory fires on the whole corpus with no fix behind it. `create` already makes one step-proposal call that asks for `title`, `complexity`, `change_type`, `files`, `creates`, `depends_on`, and a one-line `rationale`. Adding `intent` to that same object costs nothing extra — the model is already reasoning about what each step is for in order to write the title and the rationale. Asking in a second call would be the expensive answer to a problem the first call already has the context for.

## Input

This step reads four contracts and changes only the first two.

- **The step-proposal JSON contract** — built by `plan_tool/create.py:_render_from_prompt` and read by `_parse_steps_json`. The per-step object is `{"title", "complexity", "change_type", "rationale", "files", "creates", "gate", "depends_on", "concept_ids"}`. `intent` joins it as a sibling key. The parser already treats these keys in two different ways, and that split is the model to follow: `files` / `creates` / `depends_on` / `concept_ids` reject the **whole proposal** on a bad value, while `change_type` / `gate` / `rationale` coerce to nothing and let the loop continue.
- **`plan_tool/review.py:is_usable_intent`** — step 1 makes this predicate public. Plain-string signature (`Optional[str] -> bool`), three non-values: `None`, empty after `.strip()`, and a bare TODO/TBD marker. `create.py` already imports from `plan_tool.review` at module top level (`FileCheck`, `check_file_existence`, `collect_deterministic_findings`, …), so this is one more name in an existing import block — no new module edge.
- **`propose_steps_from_claude`'s one-retry contract** — the function already runs at most **one** repair retry, driven by `_attempt_parse_validate`. The retry re-sends `prompt` plus a `## Repair` block quoting the rejection reason and the rejected response, re-installs the run-log call sink at `attempt=2`, measures its own (larger) prompt through `_maybe_warn_create_budget`, and reports via `handle.notice(..., kind="retry")`. `plan_tool/foundational_logic.py` names this as the shape it mirrors, so the one-retry budget is a stated contract, not an accident.
- **The downstream merge paths** — `merge_sweep_into_steps`, `_merge_gates_into_steps`, `_seed_initial_step_status`, and `create_plan`'s iteration-loop status merge all rebuild steps with `model_copy(update={...})`, which carries every unlisted field forward. A new field on `Step` survives all four without an edit. This step relies on that and asserts it rather than changing it.

**What this step cannot verify.** Only presence. Nothing here judges whether a proposed intent is a *good* one, compares it against the step's title, `rationale`, `files`, or the plan body, or caps its length. A proposal returning one vague line per step satisfies this step completely.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — add an `intent` instruction item and the `intent` key to the JSON shape in `_render_from_prompt`; read `intent` in `_parse_steps_json`; add a helper naming the proposed steps that carry no usable intent; wire that helper into `propose_steps_from_claude` as a third rejection kind on the existing repair retry; add `is_usable_intent` to the existing `from plan_tool.review import (...)` block.
  - `tests/test_create.py` — the new cases listed in [Tests](#tests), plus the fixture sweep (add an `intent` to `_STEP_JSON`, `_INVALID_STEP_JSON`, and the inline canned bodies feeding `propose_steps_from_claude`) so existing call-count assertions keep holding.

## Implementation

### What must be true when this is done

- The rendered proposal prompt asks for `intent` on every step object, in both prompt arms (`omit_gate_item` / `omit_foundational_item` on or off).
- `_parse_steps_json` puts a proposed `intent` onto `Step.intent` and never rejects a proposal over a bad or absent one.
- A proposal in which any step lacks a usable intent triggers exactly one retry, and the total invoker calls for the whole function stay at **two**, never three.
- A proposal in which every step has a usable intent triggers **no** retry — one call, as today.
- After the retry, valid steps are returned even if intents are still missing. The function returns `None` only for the two failure kinds it already returns `None` for.

### The prompt (`_render_from_prompt`)

Add `intent` two places, matching how `rationale` already appears in both:

- **A numbered instruction item**, sitting after the existing item 6 (`change_type` classification) and **before** the dynamic tail. One line on why the step exists, in the present tense, in plain words. The item must draw the line against `rationale`, which is the one thing a reader — human or model — will get wrong: `rationale` defends the *change_type classification*; `intent` says *why the step exists at all*. Two one-liners on the same object with no stated difference will collapse into one.
- **The JSON shape string**, beside `"rationale": str`.

Gotcha that is not free to vary: `tail_items` numbers the gate and foundational items dynamically from `next_num = 7` precisely so omitting one leaves no gap. A fixed item inserted before them must move `next_num`'s initial value in lockstep, and the result has to stay gapless for **all four** on/off combinations of the two `omit_*` flags.

### The parser (`_parse_steps_json`)

Read `intent` as a **soft** field, alongside `change_type` / `gate` / `rationale`: a non-string, `null`, or whitespace-only value becomes `None` and the loop continues; a non-empty string is stripped and passed to `Step(...)`. Never return `None` for the whole list because of an `intent`.

**The parser makes no usability judgment** — it does not filter placeholders. `is_usable_intent` is applied in exactly one place, the completeness check below. The alternative (screening `TODO` out in the parser too) was rejected: two spots deciding what counts as an intent is precisely the drift step 1 exists to prevent, and downstream behavior is identical either way, since `check_intent_presence` reads a placeholder and an absent value the same.

This also matters because `_parse_steps_json` is **shared** with `_propose_step_split`. Keeping the presence enforcement in `propose_steps_from_claude` rather than in the parser is what leaves the split path untouched (see [Deferred](#deferred)).

### The retry (`propose_steps_from_claude`)

Add a small helper — something like `_steps_missing_intent(steps) -> list[int]`, returning the array positions of steps failing `is_usable_intent`. Then treat a non-empty result as a **third rejection kind** on the existing retry, not as a new loop.

Three constraints on how it hangs together:

- **One budget, one correction channel.** All three rejection kinds — unparseable, invalid graph, missing intent — consume the same single repair attempt and feed the same `## Repair` block. If the first response is unparseable and the repaired one comes back without intents, that is it: two calls, keep the steps. The plan's Risks entry asked for this to be resolved without a second round-trip; this is the resolution, and it needs no scope decision.
- **Hard and soft rejections end differently.** Unparseable and invalid-graph stay hard: after the retry they return `None`, dump the raw response via `_dump_failed_response`, and log `run_logger.parse_failure`. Missing intent is soft: the steps are valid, so keep them. Do **not** dump a parse-failure file or log a `parse_failure` entry for an intent-only shortfall — that would file a valid proposal as a parse error. Throwing away a good step graph over a missing one-liner would cost more than the gap it closes; the `intent-presence` finding and the steps 4/5 proposer already cover it.
- **A soft retry must not lose the first proposal.** If the first response parses into a valid graph but lacks intents, and the retry then returns garbage or a broken graph, return the **first** response's steps. The natural single-`raw`-variable implementation overwrites the good body with the bad one and drops it. Tied to this: the checkpoint save block writes `payload=raw`, so `raw` and the steps you return must stay in sync — otherwise a `--resume` replays a body that does not match what the previous run actually used.

- **A cached checkpoint predating this change does not trigger the soft retry.** `_initial_steps_input_hash` keys on slug + description + output dir + repo root and deliberately **not** on the prompt text, so every checkpoint written before the prompt gained `intent` stays valid. On resume, `raw` is that cached intent-less body. Do **not** let the soft rejection fire on it: a resume path that spends zero Claude calls today would start spending one, and because the save block is gated on `cached is None` the retry's better body is never written back — so every later resume of the same slug repeats the call, forever. **The rule: a cached hit is accepted as-is and skips the intent retry**; a missing intent on a resumed body is left for the proposer (step 5) and the finding to handle, exactly as it is for any other plan already on disk. Only a *live* proposal call is subject to the retry.

### The repair prompt's correction text

Name the offending steps by **array position and title**, not by step id. The prompt tells the model "Ids are assigned by the caller", so the model never emitted ids and "step 2 has no intent" points at nothing it can see. Restate the requirement in the correction (every object needs a non-empty `intent` that is not a placeholder) rather than only naming the offenders — the retry-prompt correction is read without the surrounding report, so it has to stand alone. One way: give the repair prompt a per-kind correction tail, keeping the existing `depends_on`/JSON-validity tail for the two hard kinds. Corrections **replace**, never accumulate — a single retry makes this easy to hold.

### What needs no edit, and why

`merge_sweep_into_steps`, `_merge_gates_into_steps`, `_seed_initial_step_status`, and the iteration loop's status merge in `create_plan` all use `model_copy(update={...})`, so a proposed intent rides through every one of them untouched. These are deliberate zero-diff sites; the tests below pin that rather than the code asserting it.

## Tests

All in `tests/test_create.py`.

### Tests for this step

Prompt shape:

- `test_proposal_prompt_asks_for_intent` — the rendered prompt names `intent` in the JSON shape string and in the numbered instruction list.
- `test_intent_item_survives_both_prompt_arms` — `intent` is present with `omit_gate_item` / `omit_foundational_item` each on and off.
- `test_prompt_item_numbering_has_no_gaps` — the numbered items run 1..N with no gap or repeat across all four `omit_*` combinations.

Parser:

- `test_parse_steps_json_reads_intent` — `{"intent": "why this exists"}` lands on `Step.intent`.
- `test_parse_steps_json_tolerates_missing_intent` — the key absent gives `intent is None` and a parsed list, not `None`.
- `test_parse_steps_json_tolerates_non_string_intent` — a number, `null`, or a list gives `intent is None` and never rejects the proposal.
- `test_parse_steps_json_strips_intent_whitespace` — surrounding whitespace stripped; a whitespace-only value becomes `None`.
- `test_parse_steps_json_keeps_a_placeholder_intent_verbatim` — `"TODO"` is stored, not filtered, because usability is judged in one place only.

Retry behavior (`TestProposeStepsFromClaudeProgress` or a sibling class):

- `test_no_retry_when_every_step_has_an_intent` — invoker called exactly once.
- `test_missing_intent_triggers_one_retry` — first response omits `intent`, second supplies it; two calls, returned steps carry the retry's intents, handle reports complete.
- `test_retry_prompt_names_the_steps_missing_intent` — the second prompt quotes the offending steps' titles and requires a non-placeholder `intent`.
- `test_placeholder_intent_triggers_the_retry` — `"TBD"` is treated as missing, proving `is_usable_intent` is the judge.
- `test_missing_intent_after_retry_keeps_the_proposal` — both responses omit `intent`; steps are returned (not `None`), carry `intent is None`, and the handle reports complete, not fail.
- `test_intent_shortfall_writes_no_parse_failure` — no file under `.plan-tool/parse-failures/` and no `parse_failure` run-log entry for an intent-only shortfall.
- `test_intent_retry_shares_the_single_repair_budget` — an unparseable first response repaired into an intent-less second gives exactly two calls and keeps the repaired steps.
- `test_soft_retry_keeps_first_proposal_when_retry_is_unparseable` — first parses without intents, retry returns garbage; the first proposal's steps come back.
- `test_checkpoint_saves_the_accepted_response_body` — after a soft retry, the saved initial-steps checkpoint payload is the body whose steps were returned.
- `test_retry_notice_names_the_intent_reason` — `handle.notice(..., kind="retry")` fires with a reason naming `intent`.

End-to-end and zero-diff pins:

- `test_proposed_intents_reach_the_written_frontmatter` — a `create_plan` run whose proposal carries intents writes them into the plan file, round-tripping through `parse_plan`.
- `test_intent_survives_the_iteration_status_merge` — the iteration loop's `model_copy(update={"status": ...})` keeps each step's intent.

Fixture sweep (not new coverage — keeping existing coverage honest):

- Add an `intent` to the shared `_STEP_JSON` and `_INVALID_STEP_JSON` fixtures and to the inline canned bodies feeding the roughly 29 direct `propose_steps_from_claude` call sites. Without this, the tests keyed on `step_calls["n"] == 1` (which hand back `_STEP_JSON` first and `_INVALID_STEP_JSON` second, expecting the second call to be the *iteration re-proposal*) instead feed the invalid body to the new repair retry and fail the whole first proposal. `_INVALID_STEP_JSON` needs an intent too, so the broken graph stays the only thing under test there.
- Checked non-edit: the routers in `tests/test_bench.py`, `tests/cli/test_authoring_cmds.py`, and `tests/cli/test_direct_cmd.py` key on the `"Propose an initial plan step-list"` substring, which the repair prompt still contains, and assert no call counts — they stay green while spending one extra fake call. See [Deferred](#deferred).

**Green-before-done gate.** Every test above must pass, plus the whole fast suite, before the step is finished: `uv run pytest tests/test_create.py -q` and `uv run pytest -m "not integration" tests/ -q`.

## Acceptance criteria

- `_render_from_prompt("x")` output contains `"intent"` in the JSON shape string under all four `omit_gate_item` / `omit_foundational_item` combinations, and the numbered items in each rendering run 1..N with no gap or repeat.
- `_parse_steps_json` on `[{"title": "t", "intent": "why", "files": [], "depends_on": []}]` returns one `Step` with `intent == "why"`; the same object with `intent` absent, `null`, or a non-string returns one `Step` with `intent is None` — never `None` for the list.
- A proposal whose steps all carry usable intents calls the invoker exactly once.
- A proposal missing an intent calls the invoker exactly twice and returns steps carrying the retry's intents.
- Both responses missing an intent → `propose_steps_from_claude` returns the steps (not `None`), and the progress handle records complete, not fail.
- For an intent-only shortfall: nothing is written under `.plan-tool/parse-failures/` and no `parse_failure` run-log entry is emitted.
- The saved initial-steps checkpoint payload equals the response body whose steps were returned.
- A resume against a cached checkpoint whose body carries no intents calls the invoker **zero** times — the soft retry does not fire on a cached hit — and the resumed run's call count is unchanged from before this step.
- `rg 'usable_intent' plan_tool/` shows the definition only in `plan_tool/review.py`; `create.py` imports it and defines no second predicate.
- A `create_plan` run from a proposal carrying intents produces a plan file whose steps' `intent:` values survive `parse_plan`.
- `uv run pytest tests/test_create.py -q` and `uv run pytest -m "not integration" tests/ -q` are green.

## References

- [Structured outputs — Claude API Docs](https://docs.claude.com/en/docs/build-with-claude/structured-outputs) — Read for how a required key is enforced in a schema-validated response, the strict alternative to the free-form JSON contract this step extends.
- [Increase output consistency (JSON mode) — Claude Platform Docs](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency) — Read for the re-prompt-on-malformed-output pattern this step's single retry follows, including how much of the rejected response to quote back.
- [Tool use with Claude — Claude Platform Docs](https://docs.anthropic.com/en/docs/build-with-claude/tool-use) — Read for `input_schema` required-field semantics, the fallback if the prose contract turns out not to hold the key reliably.

## Applicable guardrails

- **The plan's "## Out of scope", any validation past presence.** This step may check only that an `intent` is present and not a placeholder. No length cap, no shape or phrasing rule, no comparison against the step's `rationale`, `title`, `files`, or the plan body — in the prompt text or in code. That last one is the tempting site here: `rationale` and `intent` sit on the same object, so a "make sure they say different things" check is one line away and is out of bounds.
- **The plan's "## Out of scope", propagation through `split` / `merge` / `scope-out` / `reground`.** `_propose_step_split`'s prompt is not extended here even though it shares `_parse_steps_json`.
- **The plan's "## Out of scope", parse-time requirement and no migration.** `Step.intent` stays `Optional`, no schema change, and no plan on disk is rewritten by this step.
- **The plan's "## Architecture", step intent rides the existing proposal call.** No second Claude round-trip. The retry consumes the existing single repair attempt and adds no new invoke site.
- **The plan's "## Out of scope", new `--jobs` / parallel surfaces.** None added.
- **This step's own intent** — authoring an intent costs no extra round-trip — binds the retry design directly: a design that adds a call, even a cheap one, fails the step regardless of whether the field gets filled.

## Deferred

- **`_propose_step_split`'s two replacement steps** — carved out by the plan's "## Out of scope" split/merge/scope-out entry. Its prompt is not extended; if the model volunteers an `intent` the shared parser will carry it, and that is fine.
- **Canonical step extraction** (`plan_tool/canonical.py:extract_canonical_steps`) — this producer makes no Claude call, so there is no JSON contract to add a key to. Steps from a canonical `## Steps` section keep landing without an intent and fall to the `intent-presence` finding and the proposer.
- **The interactive `prompt_steps` / `_prompt_one_step` path** — step 5 owns the authoring paths that supply no proposal.
- **Plan-level `intent` from the seed's `## Outcome`** — step 2 owns it.
- **Preserving an on-disk step intent across the iteration re-proposal merge** — the re-proposal is authoritative for spec content the same way it already is for `title` and `files`; the merge preserves `status` only, and this step does not widen that.
- **Adding an `intent` to the canned step bodies in `tests/test_bench.py`, `tests/cli/test_authoring_cmds.py`, and `tests/cli/test_direct_cmd.py`** — outside this step's file list. Verified those routers key on a prompt substring the repair prompt still carries and assert no call counts, so they stay green; the only cost is one extra fake call each. A tidy-up, not a fix.
- **Raising `check_intent_presence` to `medium` and making it blocking** — step 6, gated on this step plus step 5.
