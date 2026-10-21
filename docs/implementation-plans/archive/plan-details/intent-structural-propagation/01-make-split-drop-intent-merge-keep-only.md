> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

## Summary

This step fixes what `plan_tool/detail.py`'s `split_step` and `merge_steps` do with `Step.intent` after a structural edit. Split already leaves halves without an intent (it never passes the field); this step states that rule in comments and tests so nobody "helpfully" copies `change_type`-style inheritance onto it. Merge gains one fold beside the existing `merged_change_type` / `merged_eta` assembly: keep the shared intent only when every member states the same *usable* value under the **fence presence set** (`TODO` / `_(TODO)_` count as absent; `TBD` is outside this named set), otherwise clear. The main design decision is **prefer absent over a half-true why** — a member's intent never survives a fold alone. On green, every surviving step has an intent that is still true of it, or none, and intent-free plans still rewrite with no new `intent:` keys.

## Table of Contents

- [Summary](#summary) — the two rules and the green result.
- [Why](#why) — why a carried-over why is worse than none.
- [Input](#input) — schema field, create transforms, write_plan omit rules, shared collapse helper.
- [Files (creates vs edits)](#files-creates-vs-edits) — one production edit, two test files.
- [Implementation](#implementation) — split pin, merge fold, rejected alternatives, gotchas.
- [Tests](#tests) — cases across detail and create suites.
- [Acceptance criteria](#acceptance-criteria) — checkable facts.
- [References](#references) — YAML dump and collapse APIs this step leans on.
- [Applicable guardrails](#applicable-guardrails) — plan fence entries that bind here.
- [Deferred](#deferred) — forward seeds, audit prompt, docs, and out-of-scope neighbors.

## Why

Split and merge are the verbs that change which steps exist. They already fold `files`, `change_type`, `complexity`, `depends_on`, `status`, and `concept_ids` with written rules (`_MERGE_CHANGE_TYPE_RANK`, `plan_tool/create.py:_apply_step_split`, `plan_tool/create.py:_apply_step_merge`). `Step.intent` sits on the same model with no matching rule. The silent default is almost right for split (unset → `None`) and wrong for merge (also unset → always clear, even when every member agreed). Worse: the next edit to `split_step`'s `replacements = [Step(...)]` list will see `change_type` and `complexity` inherited and add `intent=target.intent` in the same spirit — one line that stamps a parent's purpose onto two half-steps. Prefer absent over false: after this step, both verbs leave every survivor with a why that still fits, or with none.

## Input

Contracts this step reads and does not own. Confirm each at HEAD before coding.

- **`plan_tool/schema.py:Step` / `plan_tool/schema.py:Plan`.** Each carries an optional `intent: Optional[str] = None` field. Stored values may be `None`, blank, a one-liner, or contain real newlines — the fold must decide what each means without inventing a new normalizer.
- **`plan_tool/create.py:_apply_step_split`.** Trusts the caller for content; owns only `id`, `depends_on`, and `status` via `rep.model_copy(update={...})`. Whatever `split_step` puts (or omits) on a replacement is what lands. No conservation rule for `intent` (unlike `concept_ids`); do not add one.
- **`plan_tool/create.py:_apply_step_merge`.** Trusts the assembled `merged` step for authored content; owns `id`, `depends_on`, `status`, and `concept_ids`. An `intent=` set on `merge_steps`'s `merged = Step(...)` survives unchanged. No `plan_tool/create.py` production edit.
- **`plan_tool/parser.py:write_plan`.** Dumps with `model_dump(exclude_defaults=True, exclude_none=True)`, so `None` writes no key. Cleared intent must stay `None`, never `""`, or intent-free plans gain a new `intent:` line.
- **`plan_tool/scope_fence.py:collapse_intent_to_one_line`.** The shared whitespace-collapse helper the plan's Architecture names. Use it as the merge comparison key; do not mint a third copy.

**What these tests cannot prove.** A kept intent reaching the merged re-author prompt goes through the fence renderer already wired in `generate_detail`. Asserting that end-to-end is optional polish once the fold lands on disk; the contract here is the frontmatter field after write.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — add a unanimous-intent helper beside `_MERGE_CHANGE_TYPE_RANK` / `_MERGE_COMPLEXITY_RANK`; pass its result as `intent=` in `merge_steps`'s `merged = Step(...)` assembly; extend the comment above `split_step`'s `replacements = [Step(...)]` list and both verbs' docstrings so each states its intent rule; import `collapse_intent_to_one_line` from `plan_tool.scope_fence` (add to the existing import block).
  - `tests/test_detail.py` — add an `intents=` parameter to `_build_merge_plan`; add split/merge/bridge cases under `TestSplitStepOnDemand`, `TestInteractiveSplit`, `TestMergeSteps`, and `TestMergeBridge`.
  - `tests/test_create.py` — pin `plan_tool/create.py:_propose_step_split` so fixture responses without an `intent` key yield halves with `intent is None` (production `create.py` stays zero-diff).

Deliberate zero-diff production files (reviewer check): `plan_tool/create.py`, `plan_tool/launcher.py`, `plan_tool/cli/authoring.py`, `plan_tool/schema.py`, `plan_tool/parser.py`.

## Implementation

### The two rules

State both in the verbs' docstrings:

- **Split: a half never inherits the target's intent.** The target's line described the whole step; the split exists because that was two things. Copying it onto both halves makes it authoritative and wrong on both.
- **Merge: the survivor keeps an intent only when every folded member states the same usable value.** Anything else clears. Usable = survives the fence presence set (`None`, blank, whitespace, and `TODO` / `_(TODO)_` are absent; **`TBD` is outside this set** and may survive as a literal). Compare usable values after `collapse_intent_to_one_line`; keep the first member's text as written (comparison key ≠ stored rewrite).

Neither verb touches `Plan.intent`. Structure changes; plan purpose does not.

### Split — pin the existing behavior

`split_step` already builds:

```text
Step(id=0, title=t, change_type=..., complexity=..., concept_ids=...)
```

with no `intent=`, so halves default to `None`. `_apply_step_split` does not invent fields. **No production logic change** — extend the inheritance comment above `replacements` so intent is named as *not* inherited, and add the rule to `split_step`'s docstring next to the `change_type`/`complexity` sentence. The tests are the contract against the plan's Risks bullet ("helpfully copies intent on split by analogy with `change_type`").

**Second split producer — pin, do not edit.** `plan_tool/launcher.py:escalate_to_split` builds halves via `plan_tool/create.py:_propose_step_split` → `_parse_steps_json`. Those steps come from model JSON, never from `target.intent`. The split prompt's key list still omits `intent`. A volunteered per-half intent would be that half's own (allowed); copying the target is what the rule forbids. Cover both paths:

- `tests/test_detail.py:TestInteractiveSplit` — Phase-B / `generate_detail` + `_SPLIT_JSON` (no `intent` key) → halves `intent is None`.
- `tests/test_create.py` — direct `_propose_step_split` with a canned body that omits `intent` → both returned steps have `intent is None`.

### Merge — one small fold

Add a helper beside the rank tables — one way: `_unanimous_intent(member_steps) -> Optional[str]`.

Contract:

- Return `None` when any member's intent is `None`, empty, whitespace-only, or a `TODO` / `_(TODO)_` placeholder — use the fence omit path; do not invent a second placeholder regex and do not import `is_usable_intent` from `review`.
- Return `None` when collapsed forms of the *usable* values differ.
- Otherwise return **the first member's text as written** (collapse is comparison-only).

Pass `intent=_unanimous_intent(member_steps)` into the existing `merged = Step(...)` block beside `merged_files` / `merged_change_type` / `merged_eta`. That is the only assembly site; `merge_bridge` and `cmd_merge` both call `merge_steps`, so they inherit the rule with no second copy.

**Reuse `collapse_intent_to_one_line` and the fence presence check.** Add the collapse helper to `detail.py`'s existing `from plan_tool.scope_fence import (...)` block. Use the fence omit path (same predicate `_render_intent_section` uses) — **not** `is_usable_intent` — so `TBD` stays outside this plan's named set even though `detail` already imports `review` for other reasons. Do not invent a second placeholder regex. Do not hand-roll `re.sub(r"\s+", " ", ...)` — the plan Architecture forbids a third normalization copy.

**Rejected alternatives:**

- **Join distinct intents with `"; "`.** Invents machine prose that then reads as the author's stated purpose.
- **Keep the one member that has an intent when others are silent.** The survivor also does the silent members' work; a partial why is the false-but-authoritative shape this step exists to refuse.
- **Ask Claude to compose one from `prior_body`.** Token spend plus quality judgment — out of this plan's fence.
- **CLI `--intent` on split/merge.** No CLI file in this step's list; see Deferred.

### Gotchas

- **Never write `""`.** Cleared intent is `None` so `write_plan` omits the key.
- **Leave `plan.intent` alone.** Persist via the existing `plan.model_copy(update={"steps": new_steps})` shape.
- **Keep the fold out of `merge_bridge`.** Bridge owns confirm/outcome; `merge_steps` owns the fold.
- **Do not grow `SplitResult.new_plan` / `MergeResult.new_plan`.** Preview rows stay `(id, title, depends_on)`.
- **Do not pass intent into the re-author separately.** `merge_steps` writes the plan before `generate_detail`; the re-author re-parses disk and already sees the fold result.
- **Compare intents to each other only.** Never to plan prose, detail bodies, or a diff — `prior_body` sitting beside the fold is the temptation to watch for.
- **Embedded newlines.** Collapse for equality; if members agree after collapse, keep the first member's original string (newlines and all). Do not silently rewrite stored frontmatter in this step.

### Foundational-logic sweep

Core rule: **after a structural fold, keep a step intent only when it remains true of the survivor; otherwise clear.**

Other sites that exercise the same idea:

| Site | Disposition |
|---|---|
| `plan_tool/detail.py:split_step` / `merge_steps` | **This step** — pin split; implement merge fold. |
| `plan_tool/create.py:_propose_step_split` / `launcher.py:escalate_to_split` | Same split rule; **tests only** (`tests/test_create.py`, `TestInteractiveSplit`). |
| `plan_tool/create.py:_apply_step_split` / `_apply_step_merge` | Trust callers; zero-diff. |
| `plan_tool/scope_out.py` / `plan_tool/reground.py` forward-seed renderers | **Step 2** — different verb, attach-to-owner rule. |
| Conceptual-audit prompt | **Step 3**. |
| Shared collapse helper extract / further consolidation | Already shared via `collapse_intent_to_one_line`; further merge of helpers → Deferred / reconcile, not this step. |

## Tests

### Tests for this step

All green before the step is done. Prefer extending existing classes and helpers (`_build_merge_plan(..., intents=...)`, `_owned_pending_plan`-style seed-then-write for split targets).

`tests/test_detail.py` — `TestSplitStepOnDemand`:

- `test_split_halves_do_not_inherit_the_target_intent` — target has an intent; after `split_step` both halves have `intent is None`.
- `test_split_leaves_the_plan_intent_untouched` — plan-level intent unchanged after write.
- `test_split_writes_no_intent_key_when_nothing_carries_one` — intent-free plan's rewritten text has no `intent:` line.

`tests/test_detail.py` — `TestInteractiveSplit`:

- `test_phase_b_split_halves_do_not_inherit_the_target_intent` — seed target intent; drive `generate_detail` with `_SPLIT_JSON`; neither half equals the target's text; both are `None`.

`tests/test_detail.py` — `TestMergeSteps` (table-drive the five shapes where useful: `None`, `""`, whitespace, one-liner, embedded newline):

- `test_merged_step_keeps_a_unanimous_member_intent` — same intent on every member; survivor keeps it.
- `test_merged_step_keeps_the_first_members_text_verbatim` — members differ only in spacing; stored value is the first member's string.
- `test_merged_step_clears_on_differing_member_intents` — different intents → `None`.
- `test_merged_step_clears_when_a_member_has_no_intent` — one `None`, one set → `None`.
- `test_merged_step_clears_when_a_member_intent_is_blank` — whitespace-only counts as absent → `None`.
- `test_merged_step_clears_when_members_are_unanimous_placeholders` — every member `TODO` / `_(TODO)_` → `None` (presence non-value, not an agreed why).
- `test_merged_step_keeps_unanimous_tbd` — every member `TBD` → survivor keeps `TBD` (`TBD` is outside the fence presence set for this plan).
- `test_merged_step_has_no_intent_when_no_member_carries_one` — all absent → `None`, no raise.
- `test_merge_leaves_the_plan_intent_untouched`
- `test_merge_writes_no_intent_key_when_nothing_carries_one`

`tests/test_detail.py` — `TestMergeBridge`:

- `test_merge_bridge_applied_fold_uses_the_same_intent_rule` — applied path; survivor obeys the fold (proves no second copy in the bridge).

`tests/test_create.py`:

- `test_propose_step_split_replacements_carry_no_intent` — canned split JSON without `intent`; both returned steps have `intent is None` (pins the second producer; no `create.py` edit).

**Green-before-done:** every case above plus the existing `TestSplitStepOnDemand`, `TestInteractiveSplit`, `TestMergeSteps`, `TestMergeBridge`, `TestMergeIsSafe`, and `TestSplitIsSafe` classes. Loop with `uv run pytest tests/test_detail.py tests/test_create.py -q`; full suite before closing. No edits to unrelated on-disk plan fixtures.

## Acceptance criteria

- Splitting a step with a set `intent` leaves every half with `intent is None` in the written plan.
- Phase-B / `escalate_to_split` (via `generate_detail`) and `_propose_step_split` both leave halves without the target's intent text when the fixture omits `intent`.
- Merging members that all state the same usable intent (ignoring whitespace; placeholders absent) leaves the survivor with the first member's text exactly as written.
- Merging members with differing intents, or any missing/blank member intent, leaves the survivor with `intent is None`.
- After either verb, `parse_plan(plan_path).intent` equals the pre-edit value.
- After either verb on a fully intent-free plan, `"intent:" not in plan_path.read_text()`.
- `split_step` and `merge_steps` docstrings each state their intent rule; the `replacements` comment names intent as not inherited.
- `git diff` for production code touches only `plan_tool/detail.py` among non-test files (plus the two test modules).
- `uv run pytest tests/test_detail.py tests/test_create.py -q` passes; full suite passes.

## References

- [dataclasses.replace — Python 3.13 Library Reference](https://docs.python.org/3.13/library/dataclasses.html#dataclasses.replace) — pattern note only; `Step` is a pydantic model — use the existing `Step(...)` assembly / `model_copy(update=...)` path, not `dataclasses.replace`.
- [YAML 1.2.2 Specification](https://yaml.org/spec/1.2.2/) — how optional scalars omit, fold, or keep newlines after rewrite.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — `safe_dump` behavior behind `write_plan`; why `None` writes no key.
- [pydantic BaseModel API](https://docs.pydantic.dev/latest/api/base_model/) — `model_copy(update=...)` semantics that let create's transforms carry a caller-set `intent` unchanged.

## Applicable guardrails

- **The plan's "## Plan intent"** — every surviving step after this step's mutations must carry an intent that is true of that step, or none. Split and merge must not invent a quietly false carry-over.
- **The plan's "## Step intent"** — same boundary scoped to this step: after split/merge, survivors are true-or-absent only.
- **The plan's "## Out of scope"** — do not reopen shipped intent authoring/fence work; do not add content validation; leave #212 and #161/#162 alone. This step only sets the structural fold rules for split/merge.

## Deferred

- **Forward-seed intent attach** — step 2 owns `plan_tool/scope_out.py` / `plan_tool/reground.py`.
- **Conceptual-audit `${intent_block}`** — step 3 owns `plan_tool/review.py` / `plan_tool/prompts/plan-audit.md`.
- **Documenting the four verb rules** — step 4 owns `PLAN_FORMAT.md` and the parent Deferred close-out.
- **Operator-named `--intent` on `plan-tool split` / `merge`** — no CLI file in this step's list; file in `BACKLOG.md` if wanted.
- **Growing dry-run preview rows with intent** — would change `SplitResult` / `MergeResult` public shapes; `BACKLOG.md`.
- **Asking `_propose_step_split`'s prompt for per-half intent** — rule allows a fresh per-half value, but editing that prompt is a `create.py` production change outside this step's files.
- **`intent` conservation in `_apply_step_split`** — unnecessary (rule is clear, not conserve) and `create.py` is zero-diff here.
- **BACKLOG #212 (`apply_finding` stale intent)** — named in the plan's Out of scope / Deferred.
