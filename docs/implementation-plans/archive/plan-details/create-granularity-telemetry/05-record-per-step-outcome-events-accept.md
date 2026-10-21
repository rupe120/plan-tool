> **Auto-archived**: this plan was swept on 2026-06-27 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Record per-step outcome events for accept, override, and split actions

## Summary

Make `plan_tool/create.py`'s interactive change-type review record one **outcome event** per operator answer — `accept`, `override`, `unclassified-accepted`, `unclassified-classified`, and the split sequence (`split-requested` plus a terminal `split-applied` / `split-unusable` / `split-invalid` / `split-error`) — so the tool can later ask what operators actually do with create-stage split hints and proposals. The work lives in the interactive `while` loop of `_review_step_change_types` plus one small best-effort helper, and in `tests/test_create.py`. The helper classifies each answer into one of step 3's exported `action` constants and hands primitives to step 3's `record_create_step_outcome`; split outcomes also carry the successful splice counts (`before_steps` / `after_steps`) or `error_class`. The key design call: detect the action by comparing the resolved change type to the proposal (no need to thread the raw keystroke out of `_ask_change_type`), and keep the recording a pure side effect — a telemetry failure must never change `reviewed`, the prompts, or the return value. On green, an interactive create run leaves one `kind="granularity"`, `decision="create-step-outcome"` line per shown step (plus a terminal line per split attempt) readable through `read_decisions`.

## Table of Contents

- [Summary](#summary) — what this step ships and the result on green
- [Why](#why) — the missing per-step observation this fills
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the outcome helper, the action mapping, and the record sites in the loop
- [Tests](#tests) — unit cases added with the implementation
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors
- [References](#references) — stdlib and pytest docs for this step
- [Deferred](#deferred) — work left to other steps

## Why

Step 4 records one per-pass **assessment** event (how big the plan was, which split signals fired) but nothing about what the operator *did* with each reviewed step. BACKLOG #51 wants to tune the plan-level "this is probably more than one plan" boundary, and that needs the operator-action distribution: how often a `granularity-split` hint precedes an actual `(s)plit` request, how often a split proposal succeeds versus comes back unusable, invalid, or fails in the proposer, and how often the operator overrides the proposed change type. Today `_review_step_change_types`'s interactive loop already resolves each of these gestures — accept (Enter), override (`r`/`f`/`n`), and split (`s` → `_propose_step_split` → `_apply_step_split`) — but persists none of them. This step wires step 3's `record_create_step_outcome` into that loop so each gesture leaves a telemetry line. It adds observation only; it changes no review behavior.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — add a best-effort helper that records one outcome event for a reviewed step's answer, and call it from the interactive `while` loop in `_review_step_change_types` for each branch (accept / override / unclassified-accepted / unclassified-classified / split-requested / split terminal). Add imports for step 3's `record_create_step_outcome` and the `CREATE_ACTION_*` constants.
  - `tests/test_create.py` — add a test class (e.g. `TestStepReviewOutcomeTelemetry`) asserting the outcome events through `read_decisions` for each action, the split attempt fields, the omit-when-absent split keys, and that an advisor/telemetry failure leaves the review unchanged.

## Implementation

**What changes.** The interactive `while i < len(reviewed)` loop in `plan_tool/create.py: _review_step_change_types` gains one side effect: after each `_ask_change_type` answer it records one `create-step-outcome` event, and a split attempt records its terminal result too. This builds on step 3 (the `record_create_step_outcome` recorder + the `CREATE_ACTION_*` constants) and step 4 (which already added the create-side telemetry imports and the per-pass assessment). The outcome event carries **no `mode`** — it is inherently interactive, since the `--yes`, non-TTY, and checkpoint-resume branches return before the loop and never present a per-step gesture.

**Confirm step 3's landed shape first.** Step 3 is a `depends_on` and is not yet at HEAD (the symbols are absent from `plan_tool/telemetry.py` today). Before wiring, read `plan_tool/telemetry.py` and pass only the keyword arguments `record_create_step_outcome`'s actual signature accepts, and reference the real `CREATE_ACTION_*` constant names. Step 3's documented contract: `record_create_step_outcome(repo_root, *, plan_slug, step_id, had_split_hint, action, proposed_change_type, resolved_change_type, before_steps=None, after_steps=None, error_class=None)`, where `plan_slug` is forwarded to `record_decision` as the top-level event identity and the split-only keys appear in the event only when not `None`. Treat that as the expected shape, not a guarantee — match HEAD.

**Add one best-effort helper.** Put it next to `_granularity_split_hints` / step 4's `_record_create_assessment` in `plan_tool/create.py`, e.g. `_record_step_outcome(step, *, action, had_split_hint, resolved, repo_root, plan_slug, before_steps=None, after_steps=None, error_class=None)`. It should:

- **Skip when there's nowhere to write.** Return early if `repo_root is None`. Several callers and tests drive the loop without a `repo_root`; they must record nothing (this is also what keeps the existing `TestStepReviewLoop` cases, which pass no `repo_root`, recording-free).
- **Convert the change types to primitives.** `proposed_change_type = step.change_type.value if step.change_type else None`; `resolved_change_type = resolved.value if isinstance(resolved, ChangeType) else None`. `step_id = str(step.id)` — the recorder's `step_id` is a string, and for a split it is the pre-split id of the step being decomposed.
- **Delegate to step 3's recorder.** Pass `plan_slug=plan_slug or ""`, the primitives, and any split-only counts. Do not wrap the recorder call in a second try/except — it is already best-effort.
- **Swallow its own extraction errors.** Wrap the helper body in one `try/except Exception: return`, mirroring `_granularity_split_hints` and step 3's helper. This guards the helper's own primitive-building, which is distinct from the recorder's internal swallow; it is not a double-wrap of the recorder.

**Classify the action by value comparison (recommended).** In the loop, `answer` from `_ask_change_type` is one of: the `_SPLIT` sentinel, a concrete `ChangeType`, or `None` (Enter on an unproposed step). Decide the action without changing `_ask_change_type` — compare the resolved value to the proposal:

- **`answer is _SPLIT`** → `CREATE_ACTION_SPLIT_REQUESTED`, then the split terminal (below).
- **`step.change_type is None and answer is None`** → `CREATE_ACTION_UNCLASSIFIED_ACCEPTED` (Enter accepting an unproposed step).
- **`step.change_type is None and answer is a concrete ChangeType`** → `CREATE_ACTION_UNCLASSIFIED_CLASSIFIED` (first-time classification of an unproposed step; not an override because there was no proposal to disagree with).
- **`answer == step.change_type`** → `CREATE_ACTION_ACCEPT` (the proposal kept unchanged).
- **otherwise** → `CREATE_ACTION_OVERRIDE` (a proposed classification changed to a different concrete value).

One way to keep this clean: a tiny local function `_classify_answer(proposed, resolved) -> str` returning the constant, so the loop reads one line. Value comparison is the recommended approach because it needs no new return channel from `_ask_change_type`; if you would rather distinguish "typed the same letter" from "hit Enter," you would have to surface the raw keystroke, which is extra coupling for no telemetry gain — note the choice in a comment.

**`had_split_hint`.** Read it off the per-iteration `hint_map` already computed at the top of the loop: `had_split_hint = bool(hint_map.get(step.id))`. This is what lets analysis ask "did a granularity hint precede this gesture." When `can_split` is False the loop builds an empty `hint_map`, so `had_split_hint` is always False and no split gesture is possible — consistent.

**The split branch records two events.** The operator's choice and the attempt's resolution are separate observations (step 3's vocabulary deliberately carries both `split-requested` and terminal actions), so record:

- **`split-requested`** right after `answer is _SPLIT`, before proposing — carries `had_split_hint`, `proposed_change_type`, `resolved_change_type=None`. This is the gesture.
- **the terminal**, after the attempt resolves, inside the existing branches:
  - `_propose_step_split` raises → `CREATE_ACTION_SPLIT_ERROR` with
    `error_class=type(exc).__name__`, then re-raise exactly as today so create
    abort behavior is unchanged. This prevents a dangling `split-requested`
    event with no terminal on proposer failure.
  - `_propose_step_split` returns `None` → `CREATE_ACTION_SPLIT_UNUSABLE` (no counts; no exception).
  - `_apply_step_split` raises `CreateError` → `CREATE_ACTION_SPLIT_INVALID` with `error_class="CreateError"` (class name only, never the message — high-cardinality and possibly noisy). Record it before the `continue` that re-prompts the step.
  - success → `CREATE_ACTION_SPLIT_APPLIED` with `before_steps=len(reviewed)` captured **before** the splice and `after_steps=len(reviewed)` after. Do not record a separate proposal-size field: `_propose_step_split` returns either exactly two replacements or `None`, so the action partition already captures usability.

Capture `before_steps` before `reviewed = _apply_step_split(...)` reassigns the list, since the success record reads both sizes.

**Record sites and ordering — do not change the flow.** Place each helper call so it cannot alter `reviewed`, `i`, the prompts, the checkpoint write, or the split/retry `continue` flow:

- Accept / override / unclassified-accepted / unclassified-classified: record once, right before `reviewed[i] = step.model_copy(...)` / `i += 1`.
- `split-requested`: record right after the `if answer is _SPLIT:` guard.
- Split terminals: record inside the existing `replacements is None`, `except CreateError`, and success arms, before their respective `continue`.

A retry is naturally a new gesture: if a split comes back unusable and the operator then picks `r`, that records `split-requested` + `split-unusable` for the first answer, then `override` for the second — which is the intended history.

**Foundational logic.** The new rule is "record one outcome event per operator answer in the change-type review loop." Grep confirms this gesture loop is unique to `plan_tool/create.py: _review_step_change_types`; the only other split actuators are `detail.py`'s `escalate_to_split` (the detail-phase mixed-step bridge) and `cli/review_actions.py`'s structural-escalation arm, which are different paths with their own contracts and are out of scope here. There is no duplicated outcome-recording block to consolidate.

## Tests

All new cases go in `tests/test_create.py`, driving `_review_step_change_types` directly (as `TestStepReviewLoop` does) with `monkeypatch.setattr("sys.stdin.isatty", lambda: True)`, passing `repo_root=tmp_path` and a `slug`, and asserting through `plan_tool.telemetry.read_decisions(tmp_path)` — never by reading raw `decisions.jsonl` bytes. A new class (e.g. `TestStepReviewOutcomeTelemetry`) is the natural home. Enumerate (approx. 10 tests):

- `test_accept_records_outcome` — Enter on a proposed step writes one event with `decision="create-step-outcome"`, `action="accept"`, `resolved_change_type` equal to the proposal, and no split-only keys.
- `test_override_records_outcome` — typing `r` over a `feature` proposal records `action="override"` with `proposed_change_type="feature"`, `resolved_change_type="refactor"`.
- `test_unclassified_accepted_records_outcome` — Enter on an unproposed step records `action="unclassified-accepted"` with `proposed_change_type` and `resolved_change_type` both absent/`None`.
- `test_unclassified_classified_records_outcome` — choosing a concrete `ChangeType` on an unproposed step records `action="unclassified-classified"` rather than `override`.
- `test_split_requested_then_applied_records_two_events` — `s` on a splittable step records a `split-requested` event then a `split-applied` event carrying `before_steps` and `after_steps`.
- `test_split_unusable_records_terminal` — an invoker whose proposal can't parse (so `_propose_step_split` returns `None`) records `split-requested` then `split-unusable` with no count keys.
- `test_split_invalid_records_error_class` — a proposal that makes `_apply_step_split` raise `CreateError` records `split-invalid` with `error_class="CreateError"` and no message text.
- `test_split_proposer_exception_records_split_error_then_reraises` — an invoker/proposer exception records `split-requested` followed by `split-error` with the exception class, then re-raises so create abort behavior is unchanged.
- `test_had_split_hint_flag` — a mixed-title step that fires a deterministic split hint records `had_split_hint=true`; a clean step records `had_split_hint=false`.
- `test_no_repo_root_records_nothing` — driving the loop with `repo_root=None` records no outcome event and returns the reviewed list unchanged.
- `test_outcome_recording_failure_does_not_break_review` — monkeypatch `record_create_step_outcome` (or the helper's advisor/extraction) to raise; the review still returns the reviewed steps and the loop completes.
- `test_outcome_step_id_is_presplit_id` — the `split-requested`/terminal events carry the id of the step being split (string form), not a post-renumber id.
- `test_outcome_events_carry_plan_slug` — accept and split-terminal events read back with the `slug` passed into `_review_step_change_types`, proving the helper threads plan identity into step 3's recorder.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Write each test above alongside the helper and the loop record sites. **Green-before-done gate:** every new test must pass, the existing `TestStepReviewLoop`, `TestCreatePlanStepReviewYes`, `TestStepReviewCheckpoint`, and step 4's assessment tests must stay green, and `test_hint_suppressed_when_cannot_split` (which passes no `repo_root`) must stay green unmodified, before this step is finished. Run at minimum `uv run pytest tests/test_create.py tests/test_telemetry.py -q`.

## Acceptance criteria

- An interactive accept (Enter on a proposed step) writes one event readable via `read_decisions` with `kind="granularity"`, `decision="create-step-outcome"`, `action="accept"`, and no `before_steps` / `after_steps` / `error_class` keys.
- An override (`r`/`f`/`n` changing the value) records `action="override"` with the proposed and resolved change types.
- Enter on an unproposed step records `action="unclassified-accepted"`.
- Choosing a concrete type on an unproposed step records `action="unclassified-classified"` with no proposed change type.
- A `(s)plit` gesture records a `split-requested` event; a successful split also records `split-applied` with `before_steps` and `after_steps`; an unusable proposal records `split-unusable`; a rejected splice records `split-invalid` with `error_class="CreateError"` and no message; a proposer exception records `split-error` with the exception class and then preserves the existing abort.
- Outcome events carry the review loop's `slug` as top-level `plan_slug` (using `slug or ""` if the caller supplied `None`).
- `had_split_hint` is `true` exactly when the reviewed step carried a granularity hint that pass.
- Calling the loop with `repo_root=None`, or when the recorder raises, writes no event and leaves the reviewed list, prompts, and return value unchanged.
- The non-interactive branches (`--yes`, non-TTY, checkpoint-resume) record no per-step outcome event.
- All new tests pass and existing `tests/test_create.py` cases stay green.

## References

- [JSON Lines (jsonlines.org)](https://jsonlines.org/) — the one-object-per-line format each outcome event is appended in.
- [How to use temporary directories and files in tests — pytest documentation](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the `tmp_path` fixture used as `repo_root` to read events back through `read_decisions`.
- [Fixtures reference — pytest documentation](https://docs.pytest.org/en/stable/reference/fixtures.html) — `monkeypatch` and `sys.stdin.isatty` stubbing used to drive the interactive loop offline.

## Deferred

- **The recorder and the action/mode constants** — step 3 owns `record_create_step_outcome` and the `CREATE_ACTION_*` vocabulary in `plan_tool/telemetry.py`; this step only calls them.
- **The per-pass assessment event** — step 4 records `decision="create-review"` once per pass in every mode; this step records only the per-step interactive outcomes.
- **Outcome events for `--yes` / non-TTY bulk accept** — those branches accept verbatim with no per-step operator gesture; the step-3 assessment already counts them, so no per-step outcome is emitted there.
- **`DATA_CONTRACT.md` documentation** — step 6 documents the new `decision="create-step-outcome"` value and its context keys and updates `tests/test_data_contract.py`; this step writes no contract doc.
- **Aggregation / `plan-tool telemetry` report** — reading these events back into a summary is a separate future surface.
- **Outcome recording for `detail.py`'s `escalate_to_split` and the review/reconcile structural-escalation path** — different actuators with their own contracts; out of scope here.
