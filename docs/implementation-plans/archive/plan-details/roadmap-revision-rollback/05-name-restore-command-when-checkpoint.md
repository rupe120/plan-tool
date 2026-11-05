> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Name the restore command at every non-completion exit of `cmd_roadmap`, when a checkpoint exists

<!-- plan-tool:detail-format-version: 1 -->

## Summary

`plan_tool/cli/roadmap_cmd.py:cmd_roadmap`'s stage-run dispatch can leave a roadmap without completing through four separate, structurally disconnected paths: the `RoadmapResult`-based branch that reaches `_print_invalid`/`_print_exhausted`, the `except (OSError, RoadmapEnvironmentalError)` branch, the `except (RoadmapError, RoadmapArtifactError, RoadmapWriterGuardError)` branch, and the `except KeyboardInterrupt` branch. None of them tells the operator that steps 1–4 have already built a restore route (`--restore-revision --confirm-restore-revision`), or that a checkpoint exists to restore from. This step adds one small helper, `_print_restore_hint(plans_dir, *, slug)`, that checks step 1's `load_checkpoint(plans_dir, slug)` and, only when it returns non-`None`, prints a line naming the exact restore command; the same helper is called once from each of the four sites, right after that site's existing failure/interrupt message. Nothing is called at the successful branch (`OUTCOME_COMPLETED` / `OUTCOME_COMPLETED_NO_CHANGE`) — a completed run never gets the hint, matching the plan's own "a completed run is never rolled back" rule. The fourth site's `except KeyboardInterrupt:` closes one `try:` shared by six other, non-stage-run dispatch branches too (`--apply`, `--enroll-baselines`, `--refresh-seeds`, `--accept-seed`, `--materialize`, `--view` — see Implementation for why this is accepted rather than split out). On green, an operator who hits any of the four non-completion paths — or interrupts one of those six other actions while an unrelated checkpoint happens to exist — sees the restore command spelled out whenever a checkpoint is actually there to restore, and sees nothing extra when it isn't.

## Table of Contents

- [Summary](#summary) — what this step delivers and where the line is drawn
- [Why](#why) — the gap this step closes
- [Input](#input) — the contracts this step reads and must fit
- [Files (creates vs edits)](#files-creates-vs-edits) — what changes, file by file
- [Implementation](#implementation) — the helper, its four call sites, and the gotchas
- [Tests](#tests) — test roster
- [Acceptance criteria](#acceptance-criteria)
- [References](#references)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

Steps 1–4 give an operator whose stage run stopped partway a real way back: a checkpoint records the pre-run state, a restore runner (`plan_tool/roadmap_revision_rollback.py:restore_roadmap_revision`) turns it into a write, and `--restore-revision --confirm-restore-revision` invokes it. None of that is discoverable from the failure itself. An operator who hits `_print_invalid`, `_print_exhausted`, the environmental-failure branch, the usage-error branch, or a Ctrl-C sees only the failure and has to already know the restore route exists (or go read step 6's not-yet-written docs) to use it. This step closes exactly that discoverability gap, at the CLI layer, at every point a stage run can end without completing.

The four paths are worth naming separately rather than folded into one because they are genuinely disconnected in the source: the `RoadmapResult` branch is reached only when `run_roadmap` returns normally with a non-success outcome; the two `except` clauses are reached only when it raises; and the `except KeyboardInterrupt` wrapping the whole `try` is reached only on an operator interrupt. A fix aimed at only one of them (e.g. patching `_print_exhausted` alone) leaves the other three silent.

## Input

- **Step 1's checkpoint contract** (`plan_tool/roadmap_revision_checkpoint.py`) — `load_checkpoint(plans_dir, slug) -> RevisionCheckpoint | None`, returning `None` when no checkpoint file exists and raising `RoadmapRevisionCheckpointError` (a `ValueError` subclass) for a malformed one. This step calls only `load_checkpoint`; it needs no other operation from that module. Read the landed module for the exact names if they drifted from step 1's detail file during that step's own implementation.
- **Step 2's discard-on-completion invariant** (`plan_tool/roadmap.py:_run_roadmap`) — a checkpoint is discarded exactly when the run reaches `OUTCOME_COMPLETED` or `OUTCOME_COMPLETED_NO_CHANGE`, and left in place for every other outcome or for any exception escaping the function. This is the fact that makes "checkpoint exists" and "the run did not complete" the same statement, and it is why this step's gate is a single disk check rather than four different conditions per branch.
- **A checkpoint's existence is not tied to which of the four paths fired, or to this invocation at all.** A checkpoint can outlive several consecutive failed runs in the same lineage (the plan's own "one checkpoint per roadmap, spanning consecutive failed runs" rule). So a run whose *own* failure happens before it ever reaches checkpoint capture (for example, an `OUTCOME_STAGE_INVALID` returned from an early preflight check, or a `RoadmapError` raised before `recover_roadmap_publication` runs) can still be sitting on top of an *earlier* run's still-undischarged checkpoint. The correct check is always "does `load_checkpoint(plans_dir, slug)` return non-`None` right now", never "did this particular failure create the checkpoint" — the four call sites must not try to be clever about provenance.
- **Step 4's flag names** (`plan_tool/cli/roadmap_cmd.py`, not yet built when this step is authored — treat `docs/implementation-plans/plan-details/roadmap-revision-rollback/04-paired-restore-confirm-options-plan.md` as authoritative): `--restore-revision` and `--confirm-restore-revision`, the exact pair this step's message must name. If step 4 lands with different flag spelling, read the landed `register()` call and its `add_argument` names, not this detail file or the plan text.
- **What step 4 does not give this step** — no function that answers "should I print a hint" or "does a checkpoint exist" on its own; step 4's own dispatch calls `restore_roadmap_revision` directly and never calls `load_checkpoint`. This step is the first (and, per the plan's scope guardrails, only) place `cmd_roadmap` reads the checkpoint purely to decide what to print, without acting on it.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/cli/roadmap_cmd.py` — one new private helper (`_print_restore_hint` or an equivalently named function), a new import of `load_checkpoint` and `RoadmapRevisionCheckpointError` from `plan_tool.roadmap_revision_checkpoint`, and one call to the helper added at each of the four named sites inside `cmd_roadmap`.
- `tests/cli/test_roadmap_cmd.py` — the new test roster below, plus whatever import of `plan_tool.roadmap_revision_checkpoint` (for `write_checkpoint`, `RevisionCheckpoint`, `CheckpointEntry`, or step 1's equivalents) the fixtures need to plant a checkpoint on disk.

## Implementation

**One helper, called four times.** Add a small function, e.g.:

```python
def _print_restore_hint(plans_dir: Path, *, slug: str) -> None:
    try:
        checkpoint_exists = load_checkpoint(plans_dir, slug) is not None
    except RoadmapRevisionCheckpointError:
        return
    if not checkpoint_exists:
        return
    detail(
        "a checkpoint from an incomplete run still exists for this roadmap — "
        f"restore it with: plan-tool roadmap {slug} --restore-revision --confirm-restore-revision"
    )
```

The exact wording is not load-bearing (no test should assert the full sentence verbatim) — what matters is that the printed line contains the slug and both flag names exactly as step 4 spells them, so the command an operator copies actually runs. Naming both flags is what keeps `-y` from being read as a substitute for `--confirm-restore-revision` (it isn't, per step 4's Architecture note) — the printed line is what stops an operator from guessing at that.

**Call it at exactly these four sites, and nowhere else:**

1. In the `RoadmapResult`-based branch (`if is_successful_roadmap_outcome(result.outcome): ... elif result.outcome == OUTCOME_STAGE_INVALID: ... else: ...`) — add the call inside the `elif` (right after `_print_invalid(result, slug=args.slug)`) and inside the `else` (right after `_print_exhausted(result, slug=args.slug)`). Do **not** add it to the `if` branch (`_print_completed` / `_print_completed_no_change`) — that is the one outcome this step must never touch.
2. `except (OSError, RoadmapEnvironmentalError) as exc:` — right after `error(str(exc))`, before `return _RC_INCOMPLETE`.
3. `except (RoadmapError, RoadmapArtifactError, RoadmapWriterGuardError) as exc:` — right after `error(str(exc))`, before `return _RC_USAGE`.
4. `except KeyboardInterrupt:` — right after `error("interrupted")`, before `return 130`. `plans_dir` is already bound by this point (computed before the `try:` opens), so nothing needs to be threaded in.

Every one of the four call sites already has `plans_dir` and `args.slug` in scope — this step reads them, it does not compute anything new.

**This fourth `except KeyboardInterrupt:` is not exclusive to the stage-run dispatch.** It closes one `try:` (the comment above it in `cmd_roadmap` reads "One handler for the whole dispatch: every branch below (stage run, `--refresh-seeds`, `--accept-seed`, `--materialize`, `--apply`, `--view`) invokes the backend or reads disk the same non-interactive way") that is shared by six other dispatch branches, distinct from the six *earlier* `except KeyboardInterrupt:` clauses guarding the candidate-lifecycle, feedback-reopen, structural-rewrite, impact-analysis, receipt-creation, and revise-feedback blocks (which this step's call is never added to). So interrupting `--apply`, `--enroll-baselines`, `--refresh-seeds`, `--accept-seed`, `--materialize`, or `--view` also reaches this step's new call, and the hint prints whenever `load_checkpoint` finds one — regardless of which of the seven branches was actually interrupted. **This is accepted, not a defect to fix by splitting the except.** Per this step's own Input section, a checkpoint's existence is never tied to which action or invocation created it — "the correct check is always 'does `load_checkpoint` return non-`None` right now'" — so telling the operator a restorable checkpoint exists is equally correct information regardless of which of the seven actions they happened to interrupt; it never claims the interrupted action itself produced that checkpoint. Splitting the shared `except` so the hint fires only for the stage-run branch would add a second exception-handling path to `cmd_roadmap` purely to withhold accurate information, which this plan does not do.

**Never call it at the successful branch, and never call it unconditionally in the shared post-branch tail.** `cmd_roadmap`'s existing tail (`for line in _feedback_summary_lines(result): detail(line)`, and its three siblings) runs for every outcome, success included — that is correct for those four, because a completed run can still carry pending decisions or feedback awaiting review. The restore hint is different: it must never appear after `OUTCOME_COMPLETED` or `OUTCOME_COMPLETED_NO_CHANGE`, so it cannot live in that shared tail or in any code path reachable from the `if` branch. Keep it inside the two `elif`/`else` arms and the three `except` clauses only.

**Stream choice is a recommendation, not a constraint.** `_print_invalid` and `_print_exhausted` write everything through `error()`/raw `print(..., file=sys.stderr)`; the shared post-branch tail (`_feedback_summary_lines` etc.) writes through `detail()` to stdout regardless of outcome. Either default `detail()` (stdout) or `detail(..., stream=sys.stderr)` is defensible; pick whichever reads better next to that call site's existing output and stay consistent across all four calls.

**A corrupted on-disk checkpoint file is swallowed here, unlike steps 1–3.** `load_checkpoint` raises `RoadmapRevisionCheckpointError` for malformed checkpoint content. Steps 1–3 leave that error to propagate uncaught because they *act* on the checkpoint — a corrupted checkpoint is genuinely damaged tool state a write or a restore cannot safely proceed past. This step only *reads* the checkpoint to decide whether to print an informational line; it takes no action on the roadmap either way. Letting the error escape here would turn an otherwise-clean non-completion exit (`_RC_INCOMPLETE`, `130`, or the stage-invalid/exhausted `_RC_INCOMPLETE`) into an uncaught traceback purely because of a hint this step is trying to print, which is a worse operator experience than simply not printing the hint. `_print_restore_hint` therefore catches `RoadmapRevisionCheckpointError` and treats it the same as "no checkpoint" — the existing branch's clean return/exit code is unaffected.

## Tests

### Tests for this step

All cases live in `tests/cli/test_roadmap_cmd.py`. Every one must be green before this step is done.

- `test_stage_invalid_names_the_restore_command_when_a_checkpoint_exists` — plant a checkpoint on disk by hand (step 1's `write_checkpoint`, or an equivalent fixture helper), stub `run_roadmap` to return an `OUTCOME_STAGE_INVALID` result, and assert the printed output contains the slug and both `--restore-revision`/`--confirm-restore-revision` flag names.
- `test_stage_exhausted_names_the_restore_command_when_a_checkpoint_exists` — same, for an `OUTCOME_STAGE_EXHAUSTED` result.
- `test_escaping_environmental_failure_names_the_restore_command_when_a_checkpoint_exists` — plant a checkpoint, stub `run_roadmap` to raise `OSError` (or `RoadmapEnvironmentalError`), and assert the hint is printed alongside the existing error message and `cmd_roadmap(...)` still returns `1`.
- `test_escaping_roadmap_error_names_the_restore_command_when_a_checkpoint_exists` — plant a checkpoint, stub `run_roadmap` to raise `RoadmapError` (or `RoadmapArtifactError` / `RoadmapWriterGuardError`), and assert the hint is printed and `cmd_roadmap(...)` still returns `2`. This is the case the plan's own Testing section names explicitly.
- `test_keyboard_interrupt_names_the_restore_command_when_a_checkpoint_exists` — plant a checkpoint, stub `run_roadmap` to raise `KeyboardInterrupt`, and assert both `"interrupted"` and the restore command appear, with `cmd_roadmap(...)` still returning `130`.
- `test_keyboard_interrupt_on_a_non_stage_run_action_also_names_the_restore_command_when_a_checkpoint_exists` — plant a checkpoint, then interrupt a non-stage-run action sharing the same `except KeyboardInterrupt:` (e.g. stub `_cmd_roadmap_view` to raise `KeyboardInterrupt` under `--view`) and assert the restore command still prints — pinning that the hint is deliberately provenance-agnostic across all seven branches the shared `except` guards, not a leak to fix.
- `test_no_restore_hint_at_any_non_completion_path_without_a_checkpoint` — parametrized over the same four outcomes/exceptions as the tests above, with no checkpoint file present: assert the printed output contains neither flag name.
- `test_completed_run_never_prints_a_restore_hint_even_with_a_checkpoint_present` — plant a checkpoint on disk, stub `run_roadmap` to return a completed result (`OUTCOME_COMPLETED`), and assert the flag names appear nowhere in stdout or stderr — proving the gate is the outcome branch itself, not just the checkpoint's usual absence after a real completed run. This is the step title's own "never after a completed run" clause, named directly rather than left to be inferred from the other cases.
- `test_completed_no_change_run_never_prints_a_restore_hint_even_with_a_checkpoint_present` — same, for `OUTCOME_COMPLETED_NO_CHANGE`.
- `test_restore_hint_names_the_slug_that_was_actually_requested` — run with a non-default `slug` (via `_ns(tmp_path, slug=...)`) and assert the printed command uses that slug, not a hardcoded one.
- `test_corrupted_checkpoint_file_is_swallowed_by_the_restore_hint_check` — write unparseable bytes directly to the checkpoint path (mirroring step 1's `test_capture_and_round_trip_tolerate_syntactically_invalid_tracked_file_content`-style fixture setup, but for the checkpoint file itself rather than a tracked file), stub `run_roadmap` to return an `OUTCOME_STAGE_INVALID` result, and assert `cmd_roadmap(...)` still returns its ordinary `_RC_INCOMPLETE` with no restore hint printed and no exception escaping — pinning that this step's read-only use of the checkpoint does not let a corrupted file turn a clean non-completion exit into a traceback, unlike steps 1–3's own precedent for the same error.

(11 tests)

**Existing test to extend, not just re-run:** `test_returned_outcomes_emit_one_terminal_after_existing_summaries` (in `TestStageLifecycleStatus`) monkeypatches `_print_invalid`/`_print_exhausted` themselves and asserts an exact ordered `calls` list. Since this step's call sites sit right next to those two functions rather than inside them, that test's monkeypatching leaves this step's new calls unaffected and the test should keep passing unchanged — confirm this by running it, and only touch it if it turns out `_print_restore_hint` needs to be monkeypatched away too for the assertion to hold (for example, if a real `load_checkpoint` call during that test would touch a `plans_dir` that does not exist yet in that fixture).

## Acceptance criteria

- A checkpoint present on disk for `args.slug` produces a printed line naming both `--restore-revision` and `--confirm-restore-revision` and the slug, at all four of: the `OUTCOME_STAGE_INVALID` branch, the `OUTCOME_STAGE_EXHAUSTED` branch, the `except (OSError, RoadmapEnvironmentalError)` branch, the `except (RoadmapError, RoadmapArtifactError, RoadmapWriterGuardError)` branch, and the `except KeyboardInterrupt` branch wrapping the stage-run dispatch.
- No checkpoint present produces no such line at any of those five outcomes/branches (four paths, five outcomes counting both `OUTCOME_STAGE_INVALID`/`OUTCOME_STAGE_EXHAUSTED` under the first path).
- `OUTCOME_COMPLETED` and `OUTCOME_COMPLETED_NO_CHANGE` never print the hint, even when a checkpoint happens to be present on disk at that moment.
- The fourth call site's shared `except KeyboardInterrupt:` also prints the hint for an interrupted `--apply`, `--enroll-baselines`, `--refresh-seeds`, `--accept-seed`, `--materialize`, or `--view` invocation when a checkpoint exists — accepted breadth, not a leak, since the hint never claims the interrupted action produced that checkpoint.
- Existing return codes for all five branches (`1`, `1`, `1`, `2`, `130`) are unchanged.
- A corrupted on-disk checkpoint file at the hint-check point does not turn a clean non-completion exit into an uncaught exception; the hint is simply not printed.
- `uv run pytest tests/cli/test_roadmap_cmd.py -q` passes, and the full suite (`uv run pytest tests/ -q -n auto`) passes.

## References

- `plan_tool/cli/roadmap_cmd.py`: `cmd_roadmap`'s four non-completion paths, `_print_invalid`, `_print_exhausted`, `_print_completed`, `_print_completed_no_change`, `_print_baseline_rebind` — the existing print helpers this step's call sites sit beside, and the style (`error`/`detail` from `plan_tool.style`) they use.
- `docs/implementation-plans/plan-details/roadmap-revision-rollback/01-roadmap-revision-checkpoint-file-that.md` — `load_checkpoint`'s exact contract.
- `docs/implementation-plans/plan-details/roadmap-revision-rollback/02-move-run-roadmap-confirmed-brief-rebind.md` — the discard-on-completion invariant that makes "checkpoint exists" mean "the run did not complete".
- `docs/implementation-plans/plan-details/roadmap-revision-rollback/04-paired-restore-confirm-options-plan.md` — the `--restore-revision`/`--confirm-restore-revision` flag pair this step's message names.

## Applicable guardrails

- The plan's `## Scope guardrails`, "No automatic restore, and no restore offered on anything but an explicit command" — this step only prints text naming a command; it never calls `restore_roadmap_revision` itself, and the operator must still type the confirmed pair by hand.
- The same guardrails, "No new persisted state except the checkpoint" — this step only reads the checkpoint via `load_checkpoint`; it writes nothing.
- The same guardrails, "Eligibility never reads run logs" — the decision to print or withhold the hint is based solely on `load_checkpoint`'s return value; nothing here reads `.plan-tool/runs/`.

## Deferred

- Adding the restore-hint call to the six *earlier* `except KeyboardInterrupt:` clauses guarding the candidate-lifecycle, feedback-reopen, structural-rewrite, impact-analysis, receipt-creation, and revise-feedback branches — those are untouched. The fourth of this step's own four call sites already reaches `--apply`/`--enroll-baselines`/`--refresh-seeds`/`--accept-seed`/`--materialize`/`--view` interruptions too, since it shares one `except` with them; see Implementation for why that breadth is accepted rather than split out.
- Recovering from a corrupted on-disk checkpoint file in a way that *acts* on it — this step only swallows the error for its own read-only hint decision (see Implementation); steps 1–3 still leave it to propagate uncaught where they act on the checkpoint, and that precedent is unchanged.
- Operator documentation describing the restore route and this hint — step 6.
- Exact wording of the printed line beyond naming the slug and both flag names — left to the implementer; no test should pin the full sentence verbatim.
