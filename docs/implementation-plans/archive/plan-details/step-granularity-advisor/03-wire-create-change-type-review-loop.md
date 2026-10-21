> **Auto-archived**: this plan was swept on 2026-06-20 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Surface decompose-time `granularity-split` advice in create's change-type review loop

## Summary

Wire the step-1 advisor leaf into `create`'s interactive change-type review so the operator sees a per-step "this step looks splittable" hint right where the `(s)plit` action already lives. In `plan_tool/create.py`, add a best-effort helper `_granularity_split_hints` that builds a throwaway `Plan` from the current step list, calls `assess_granularity(plan, stage="create", evidence=GranularityEvidence())` (deterministic only — **no Claude at create stage**, `invoker` stays `None`), keeps only `source="granularity-split"` recs, and returns a `step_id → hint lines` map; `_review_step_change_types` recomputes that map each loop iteration and passes the current step's hint into `_ask_change_type`, which prints it alongside the existing proposal/rationale. The key design decision: the advisor only advises — it never auto-splits, never changes the exit code, and a failure to assess (an unbuildable graph) silently yields no hint rather than breaking create. On green, a step with a mixed refactor+feature title (or an unrelated file span) shows a split hint in the review prompt; a clean step shows none; merge recs and the `--yes`/non-TTY/resume paths surface nothing.

## Table of Contents

- [Summary](#summary) — what the wiring adds and the observable result on green.
- [Table of Contents](#table-of-contents) — this list.
- [Why](#why) — create leaves decomposition entirely to Claude with no granularity feedback.
- [Files (creates vs edits)](#files-creates-vs-edits) — two edited files, no new files.
- [Implementation](#implementation) — the helper, the loop recompute, the `_ask_change_type` hint line, and the scoping decisions.
- [Tests](#tests) — unit cases over the helper and the loop, written with the code.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors.
- [References](#references) — typing + import-system docs for the acyclic leaf import.
- [Deferred](#deferred) — non-interactive coverage, merge surfacing, telemetry.

## Why

`create` leaves step count and shape entirely to Claude's decomposition prompt, then asks the operator to confirm each step's `change_type` in `plan_tool/create.py: _review_step_change_types` — the one place a mixed step can be caught and split via the `(s)plit` action (`_SPLIT` sentinel → `_propose_step_split` → `_apply_step_split`). But nothing tells the operator *which* steps look mixed: they must eyeball every proposal. Step 1 built `plan_tool/granularity.py` with deterministic, no-Claude split detectors (mixed refactor+feature title, two-clause title conjunction, unrelated file span) that read only plan structure. This step feeds the finalized step list through that advisor and shows its `granularity-split` recs as a hint next to each step's prompt, turning the existing manual `(s)plit` choice into an informed one — with zero new Claude spend and zero risk to the create flow.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py`
    - Add a module-top import of the step-1 leaf: `from plan_tool.granularity import assess_granularity, GranularityEvidence, GRANULARITY_SPLIT_SOURCE`.
    - Add the best-effort helper `_granularity_split_hints(steps) -> dict[int, list[str]]`.
    - Add a `granularity_hint` keyword to `_ask_change_type` and print it alongside the rationale.
    - In `_review_step_change_types`, recompute the hint map per loop iteration and pass the current step's hint into `_ask_change_type`.
  - `tests/test_create.py` — add unit cases for the helper and loop-level cases for hint display, suppression, recompute-after-split, the no-Claude guarantee, and the failure-is-silent guard.

## Implementation

### Confirm step-1 symbols against landed code first

- **depends_on: 1.** `plan_tool/granularity.py` does not exist at HEAD yet (step 1 is `current`, not landed). Before wiring, confirm the exact public names against the landed leaf at HEAD — `assess_granularity`, `GranularityEvidence`, `GRANULARITY_SPLIT_SOURCE`, and the `assess_granularity(plan, *, stage, evidence, invoker=None)` signature. The code wins on any conflict with step 1's sibling detail file; do not copy names from that detail if implementation renamed them.

### `plan_tool/create.py`

**Import discipline — module-top is correct and acyclic.**
- Add `from plan_tool.granularity import assess_granularity, GranularityEvidence, GRANULARITY_SPLIT_SOURCE` at module top with the other `plan_tool.*` imports.
- `granularity.py` imports only `plan_tool.schema` and `plan_tool.review` (both already top-imported by `create.py`), and `granularity` never imports `create` — so the leaf sits below `create` and this import adds **no cycle**. Do not use a body-local import: there is no cycle to dodge, no cost to fence (the call is cheap and deterministic), and create's tests already patch `plan_tool.create.*` module globals (e.g. `apply_finding`, `write_plan`), so a top-level binding stays patchable as `plan_tool.create.assess_granularity`.

**`_granularity_split_hints(steps: list[Step]) -> dict[int, list[str]]` (new helper).**
- **Build a throwaway `Plan`** from `steps` mirroring `_apply_step_split`'s dry-run construction: `Plan(title="dry-run", status=PlanStatus.PLANNING, priority=Priority.LOW, steps=steps)`. The advisor's deterministic detectors read only `step.title` / `step.change_type` / `step.depends_on` / `step.all_files`, so the placeholder title/priority do not matter.
- **Call the advisor with no Claude:** `assess_granularity(plan, stage="create", evidence=GranularityEvidence(), invoker=None)`. `GranularityEvidence()` defaults `detail_bodies` to empty — correct, because create has no authored implementation prose yet. Passing `invoker=None` is the structural guarantee that create-stage assessment never shells out; the deterministic split battery is the only thing that runs.
- **Keep only split recs:** filter the returned list to `rec.source == GRANULARITY_SPLIT_SOURCE`, then build `dict[int, list[str]]` keyed on `rec.step_id`, each value a short hint line (prefer `rec.suggested_action`, falling back to `rec.title`/`rec.body`). Append, so a step tripping more than one split predicate carries more than one line.
- **Best-effort: never break create.** Wrap the build + assess in `try: … except Exception: return {}`. An incoming step list that cannot form a valid `Plan` (e.g. a `depends_on` graph not yet validated — validation only happens later at the real `Plan(...)` in `create_plan`) must yield no hints, not a traceback. Advisory output is a convenience; create must complete regardless.
- **Do not surface merge recs.** `assess_granularity` also returns `granularity-merge` recs; drop them here. There is no interactive merge action in the review loop, merge is advisory-only until the merge executor lands, and step 4's completeness audit is where merge advice surfaces. Filtering to the one source keyed to this loop's `(s)plit` action keeps the hint actionable.

**`_ask_change_type` — add the hint line.**
- Add a keyword-only `granularity_hint: Optional[list[str]] = None` (default keeps every existing caller and test valid).
- Print the hint right after the rationale block, before the options line — e.g. a `  granularity: <line>` per hint line, styled like the existing `  rationale:` print. It is informational only: it does **not** add a new option letter; it nudges the operator toward the already-present `(s)plit`.

**`_review_step_change_types` — recompute per iteration and pass the hint.**
- Compute the hint map at the **top of each `while i < len(reviewed)` iteration** from the current `reviewed` list (not once before the loop). A `(s)plit` renumbers every step id via `_apply_step_split`, so a map keyed on pre-split ids would point at the wrong step afterward; recomputing each iteration keeps the keys aligned with current ids. The recompute is deterministic and Claude-free, so per-iteration cost is negligible.
- Gate hint display on `can_split` (`invoker is not None`). When split is unavailable the operator cannot act on a "consider splitting" nudge, so suppress it to avoid noise — compute `hint_map` only when `can_split`, else pass `granularity_hint=None`.
- Pass `granularity_hint=hint_map.get(step.id)` into the `_ask_change_type` call.
- **Leave the early-return paths untouched.** The resume-checkpoint restore, the `--yes` branch, and the non-TTY branch all `return` before the prompt loop — they surface no hint, which is correct: granularity advice at create is operator-facing and interactive-only. Non-interactive granularity coverage is step 4's completeness audit.

**Foundational logic + sibling detectors.**
- This step's core behavior: *call `assess_granularity(stage="create")` and surface its split recs as per-step hints in the change-type review loop.* The advisor leaf owns the detection rule (step 1); this step only feeds it create's evidence and renders the result.
- A sibling mixed-step detector already lives in `plan_tool/create.py: _proposal_scenario_signals` (`CATEGORY_MIXED_STEP`), but it sits on a different axis: it flags an *already-split* refactor→feature pair as a positive A/B telemetry signal for scenario capture, not an *un-split* mixed step needing advice. Do not consolidate the two — leave `_proposal_scenario_signals` unchanged.
- The split *executor* path (`_SPLIT` → `_propose_step_split` → `_apply_step_split`) is unchanged: the hint only informs the operator's choice; it never auto-triggers a split.

## Tests

Test file: `tests/test_create.py`. Add to the existing `# --- Step 3: per-step change-type review gate` region near `TestAskChangeType` / `TestStepReviewLoop`. Drive the loop with `_queue_input` and `monkeypatch.setattr("sys.stdin.isatty", lambda: True)` (mirror `TestStepReviewLoop.test_split_then_review_expands_list`); use `_appending_invoker(_SPLIT_PAIR_JSON)` where a split round-trip is needed. Capture prompt/stdout via `capsys` to assert the hint line. Build `Step`/`Plan` inline from `plan_tool.schema`.

- `test_split_hints_filters_to_split_source` — `_granularity_split_hints` over a list with both a split smell and a merge smell returns a map keyed on the split step's id only; the merge step is absent.
- `test_split_hints_empty_on_unbuildable_graph` — a step list whose `depends_on` cannot form a valid `Plan` returns `{}` (the best-effort guard), no raise.
- `test_split_hints_passes_invoker_none` — patch `plan_tool.create.assess_granularity` to record kwargs; assert it is called with `stage="create"` and `invoker=None` (no Claude at create stage).
- `test_mixed_title_step_shows_hint` — drive `_review_step_change_types` with one step whose title trips a step-1 split detector and an `invoker` present; capture stdout and assert the `granularity:` hint line appears in that step's prompt; operator Enters to accept.
- `test_clean_step_shows_no_hint` — a single-concern step yields no `granularity:` line in its prompt.
- `test_hint_suppressed_when_cannot_split` — same mixed-title step with `invoker=None` (`can_split` False): no hint line printed (and `assess_granularity` is not consulted for display).
- `test_advisor_failure_does_not_break_review` — patch `plan_tool.create.assess_granularity` to raise; the review loop still completes and returns the reviewed steps, no hint, no crash.
- `test_hint_recomputed_after_split` — start with a mixed-title step, press `(s)plit`; assert the post-split halves' prompts carry the correct (or no) hint for their renumbered ids — i.e. no stale hint pointing at a pre-split id.
- `test_merge_smell_not_surfaced_in_loop` — a step list with only a `granularity-merge` smell shows no hint line in the review loop.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Write each test with the code it covers, smallest first: the two `_granularity_split_hints` unit cases and the `invoker=None` pin, then the `_ask_change_type` hint-display cases, then the loop-level display/suppression/recompute/failure cases. **Green-before-done gate:** every new test must pass (`uv run pytest tests/test_create.py -q`) before this step is considered finished, and the existing `TestAskChangeType` / `TestStepReviewLoop` cases must stay green (the new `granularity_hint` kwarg defaults to `None`, so they require no edits).

## Acceptance criteria

- `_granularity_split_hints(steps)` returns a `dict[int, list[str]]` containing only `source="granularity-split"` recs keyed by `step_id`; `granularity-merge` recs are excluded.
- `_granularity_split_hints` returns `{}` (no raise) when the step list cannot build a valid `Plan`.
- `assess_granularity` is invoked from create with `stage="create"` and `invoker=None` — no Claude subprocess is spawned for the granularity assessment.
- In an interactive review with a Claude invoker present, a step that trips a step-1 split detector prints a `granularity:` hint line in its `_ask_change_type` prompt; a clean step prints none.
- With no invoker (`can_split` False), no hint line is printed regardless of the step's shape.
- A raising `assess_granularity` leaves `_review_step_change_types` completing normally and returning the reviewed steps.
- After a `(s)plit`, hints reflect the renumbered ids — no hint points at a vanished/wrong step id.
- The `--yes`, non-TTY, and resume early-return paths emit no granularity hint and are unchanged in behavior.
- `uv run pytest tests/test_create.py -q` is green.

## References

- [typing — Support for type hints (Python 3.13)](https://docs.python.org/3.13/library/typing.html) — for the `dict[int, list[str]]` return annotation and the keyword-only `granularity_hint` parameter on `_ask_change_type`.
- [Python Language Reference — The import system (Python 3.13)](https://docs.python.org/3.13/reference/import.html) — confirms the module-top `from plan_tool.granularity import …` is acyclic since `granularity` never imports `create`.

## Deferred

- **Non-interactive granularity coverage** — `--yes`, piped/CI, and resume paths surface no hint; step 4's `assess_granularity(stage="completeness")` audit is the non-interactive backstop.
- **Merge advice at create** — `granularity-merge` recs are produced by the advisor but not shown here (no interactive merge action; the `plan-tool merge` executor has landed but no auto-escalation bridge routes a merge finding to it, so the operator hand-runs `plan-tool merge`); step 4 surfaces merge in the completeness audit.
- **Telemetry / run-log capture of granularity recs** — this step renders hints to stdout only; logging the recs to `run_logger` or scenario capture is out of scope.
- **Auto-splitting on a hint** — the advisor never triggers `_apply_step_split`; the operator still chooses `(s)plit` explicitly. No change to that posture.
- **Consolidating `_proposal_scenario_signals`'s mixed-step detector with the advisor** — left as-is; the two sit on different axes (A/B telemetry vs operator advice).
