> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Let `completeness-apply` walk correctness gaps on a bare plan while still skipping completeness gaps

## Summary

Split the bare-plan gate inside `cmd_completeness_apply` in `plan_tool/cli/completeness_cmd.py` by finding source: on a bare plan the walk now runs for `plan-correctness` gaps and every other saved source stays withheld and reported. The key decision is an **allow-list of one source** rather than an exclusion list — on a bare plan only `plan-correctness` is walkable, so `plan-completeness`, `data-contract`, and `granularity-split` keep today's report-and-skip behavior with no per-source argument to make. The narrowing happens inside the existing bare branch and rebinds both rec lists, so the serial walk and the `--jobs N` parallel lane inherit it from one place. Two safety obligations ride with the opening: the apply prompt must be told when a step's **declared** `detail:` path has no bytes on disk, and a bare-plan apply must leave no detail file behind that was absent before it ran. The deterministic files-coherence writer stays skipped on a bare plan. This step lands **first** in the plan, so no commit ever advertises a route that does not work. On green, a bare plan carrying a correctness gap gets a real per-gap apply prompt instead of the "conceptual apply actions require a complete detail bundle" skip, and the verb's own `--help` no longer claims otherwise.

## Table of Contents

- [Summary](#summary) — what changes and what stays the same.
- [Why](#why) — what the verb does today, and the bare-safety claim that does not hold as written.
- [Input](#input) — the contracts this step reads: the plan's axis decision, the saved sidecar, `is_bare`, and `apply_finding`'s two detail-file mechanisms.
- [Files (creates vs edits)](#files-creates-vs-edits) — the four code/test files plus three re-baselined artifacts.
- [Implementation](#implementation) — where the split goes, the two safety obligations, the rules that are not free to vary, and the alternative rejected.
- [Tests](#tests) — new cases, the inherited case this step rewrites, and the regression net that must stay green.
- [Acceptance criteria](#acceptance-criteria) — checkable facts.
- [References](#references) — what to read before starting.
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step.
- [Deferred](#deferred) — nearby work this step does not take, and where it goes.

## Why

The plan's whole point is a bare plan's correctness gaps having a route. Run `plan-tool completeness-apply` on one today and the verb refuses: `cmd_completeness_apply` computes `audit_detail_bundle_status`, and on `is_bare` it warns *"skipping conceptual gap walk / saved completeness walk: conceptual apply actions require a complete detail bundle for this saved audit"*, prints the gap labels, and returns 0 having applied nothing. This step is what makes the route real, and it lands **before** steps 2 and 5 so no commit in this plan's history advertises a route that dead-ends one command later — a state worse than today's honest refusal, because the operator spends a command to learn it.

The refusal is also not grounded in what the apply path needs. `plan_tool/prompts/apply-finding.md` edits the plan file "and/or the step's detail file **if applicable**" and reserves `BLOCKED` for a finding that genuinely needs a missing file, so a plan-body-only correctness edit needs no detail bundle at all.

**But the apply path is not bare-safe for free, and the gap is in the prompt, not the tracking.** Two different mechanisms in `plan_tool/launcher.py:apply_finding` treat a missing detail file differently, and only one of them is safe:

- **Snapshot tracking is already correct.** The tracking loop takes the step's declared `detail:` path when there is one, and otherwise falls back to `resolve_detail_artifact`, skipping the step when the resolution is not `on_disk`. Either way `_snapshot_text_files` handles an absent path, so the diff and the revert stay sound.
- **The `detail_path` prompt variable is not.** It renders the literal `(no detail file declared for this step)` **only when `step.detail is None`**. A plan authored by `create` always declares a `detail:` path — the file's *absence* is what makes `is_bare` true — so on the dominant bare shape the prompt receives a real-looking path string with **no signal that nothing is there**. The model is handed a file reference it can neither read nor be expected to recognize as empty, and the prompt's `BLOCKED` rule ("a finding that requires a new file") is the one thing standing between that and a created file.

So the safety claim this step rests on is **declared-but-absent**, not "no detail declared". Grounding it is part of this step: before the verb opens on bare plans, the apply prompt must be able to tell that a declared path has no bytes on disk. That is the first of the two Implementation obligations below.

## Input

- **The plan's `## Architecture` decision 1, not another step's code.** This step lands before the three reporting surfaces, so there is no landed fence to read: the axis is settled by the plan — conceptual-**correctness** opens on a bare plan, conceptual-**completeness** does not — and this step is the first place it becomes real. Steps 2 and 5 later describe what this verb does. Do not import from `plan_tool/completeness_report.py`; the two modules answer different questions (what to walk vs. what to advertise) and must agree on the axis, nothing more.
- **`DetailBundleStatus.is_bare`** (`plan_tool/review.py`, computed by `audit_detail_bundle_status`) — `True` when at least one step has no detail file on disk. This is the only coverage fact the gate may read. `cmd_completeness_apply` already computes it inside a `try` guarded by `(ParseError, ValidationError)`, leaving `_bundle_status` as `None` when the plan will not parse; that fail-open path skips the whole gate today and must keep doing so.
- **The saved sidecar's `recommendations`** — a `SavedReview` loaded by `load_review`. Findings carry `source`, `severity`, `id`, `anchor`, and `title`; `step_id` is `None` for the large majority of conceptual findings (the plan's `## Out of scope` records the measurement). The gate keys on `source` alone and must not try to resolve a finding to a step.
- **The four sources this verb walks**, ranked by `_SAVED_SERIAL_APPLY_SOURCE_RANK` in `plan_tool/cli/completeness_cmd.py`: `plan-correctness` and `plan-completeness` (both in `_CONCEPTUAL_APPLY_SOURCE_RANK`), `_DATA_CONTRACT_SOURCE`, and `GRANULARITY_SPLIT_SOURCE`. The rank map itself is unchanged by this step; only which recs survive to the walk changes.
- **`apply_finding`'s two detail-file mechanisms**, in `plan_tool/launcher.py` — read both before building on either, and re-confirm them at HEAD:
  - the **tracking loop**, which takes `tracked_step.detail` when the step declares one and otherwise falls back to `resolve_detail_artifact` with an `on_disk` skip. `_snapshot_text_files` stores `None` for an absent path, and `_restore_text_files` deletes a path whose snapshot was `None`. So a declared-but-absent detail file is already tracked, and a *reverted* apply already cleans up a file created there.
  - the **`detail_path` prompt variable**, which renders `(no detail file declared for this step)` only when `step.detail is None`. On a `create`-authored bare plan `step.detail` is a real string and the file is simply absent, so the prompt currently carries no missing-file signal. This is the gap the step closes.
- **`plan_tool/prompts/apply-finding.md`'s rule 5** — the model must not create files and must emit `BLOCKED` instead. It is a prompt rule, so it is the *floor*, not the guarantee; the Implementation below adds a mechanical backstop on both lanes rather than resting on it.
- **`plan_tool/cli/completeness_apply_parallel.py:_capture_changes`** — diffs every path in `apply_finding`'s `pre_snapshot`. A declared-but-absent detail path is already in that snapshot (`pre=None`), so a worker-created file **is** captured and replayed — it is not ignored. The comment that claims newly-created files are out of scope is false for this shape and must be corrected when the shared `apply_finding` backstop lands. Do not treat `_capture_changes` as the parallel safety net.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_cmd.py` — narrow the walk by source inside the bare branch of `cmd_completeness_apply`; replace the whole-walk skip warning with a withheld-gaps notice; correct `cmd_completeness_apply`'s docstring, the `_walk_apply_sources` comment's stale rationale, and the `completeness-apply` subparser help in `register`.
  - `plan_tool/launcher.py` — give the `detail_path` prompt variable an absent-file signal, and make an accepted apply refuse a detail file it created.
  - `tests/cli/test_completeness_cmd.py` — new cases in `TestCompletenessApplyDetailBundleGate` and `TestCompletenessApplyParallel`; rewrite the inherited `test_bare_plan_skips_conceptual_walk`.
  - `tests/test_launcher.py` — cases for the two `apply_finding` changes.

**Three further declared artifacts, noted explicitly.** Changing the subparser help text reddens two drift guards, and both are regenerated rather than hand-edited:

  - `docs/cli/completeness-apply.md` and `docs/cli/README.md` — re-baseline with `python -m plan_tool.cli_reference --write`; guarded by `tests/cli/test_cli_reference.py`.
  - `tests/cli/package_surface_help.golden.txt` — re-baseline by running the suite with `UPDATE_CLI_GOLDEN=1`; guarded by `tests/cli/test_package_surface.py`.

All three are in the step's frontmatter `files:`, so the declared list and the work match. The help-string edit is not droppable: without it `plan-tool completeness-apply --help` keeps telling operators that apply actions "run only when a complete detail bundle exists", which this step makes false on exactly the surface the plan exists to fix.

## Implementation

**What must be true when the step is done**

- A bare plan with at least one `plan-correctness` gap reaches `walk_recommendations` (or the parallel lane), and the walker sees **only** the correctness gaps.
- The apply prompt for a step whose declared `detail:` path has no file on disk says so.
- No bare-plan apply leaves a detail file on disk that was absent before it ran, on either lane.
- Every withheld gap is still named on screen — count, per-finding label, and the verb that unblocks it. Nothing is dropped silently.
- A bare plan with no correctness gap behaves exactly as today: nothing applied, gaps reported, rc 0.
- A fully-detailed plan and a plan that fails to parse behave exactly as today.
- No new exit code, and one scoped rc change (below).

**Obligation 1 — the prompt must be able to tell a declared path has no bytes**

The safety claim is *declared-but-absent*, not *not declared* (see [Why](#why)). Close the gap where the prompt variable is built: when `step.detail` is set but the resolved path is not a file, `detail_path` must carry that fact rather than a bare path string. One way — keep the path and append the signal, e.g. `docs/…/03-foo.md (not authored yet — no file at this path)` — so the model still knows where the file *would* go and cannot mistake it for readable content. The exact string is the implementer's; three things are not free to vary:

- **Resolve against `repo_root`, the same way the tracking loop does.** Two different notions of "the step's detail file" in one function is the drift to avoid.
- **The `step.detail is None` arm keeps its current literal.** Existing cases pin it and that shape is unaffected.
- **Signal only; no behavior branch.** This adds no gate, no verdict, and no skip. The apply prompt's existing `BLOCKED` rule is what acts on the information.

**Obligation 2 — an accepted apply must not keep a detail file it created**

The revert path is already safe: a declared-but-absent path is tracked, its `pre_snapshot` entry is `None`, and `_restore_text_files` deletes a `None`-snapshot path that now exists. The hole is the **accepted** apply — verdict `APPLIED`, operator keeps the edit, and a file created at the tracked path survives. Under `--jobs N -y` there is no operator in the loop at all.

- **One backstop in `apply_finding`, shared by both lanes.** Treat a tracked path whose `pre_snapshot` was `None` and whose final on-disk state is not as a **created file**, restore that one path, and report it. The finding's own edits to the plan body are unaffected — only the created file is undone. Do not rely on the operator noticing a new-file hunk in the diff.
- **Run the backstop on the final post-follow-up snapshots, not only the primary pass.** `cmd_completeness_apply` calls `apply_finding` with `auto_fix_introduced=True`, so a second Claude pass can still write the declared-but-absent path after a clean primary `APPLIED`. Comparing only the primary `post_snapshot` misses that write. The check that returns from `apply_finding` must see the state after any auto-fix follow-up has finished (or been skipped).
- **Do not attribute parallel safety to `_capture_changes`.** At HEAD that helper diffs every path in `pre_snapshot`, and a declared-but-absent detail path is already in that snapshot with `pre=None`, so a worker-created file becomes a `FileChange(pre=None, post=…)` that `_write_change` **does** replay onto the canonical tree. The comment at `completeness_apply_parallel.py` that claims newly-created files are ignored is wrong for this shape — correct it in the same edit, and pin the parallel test to the shared `apply_finding` cleanup (worker creates the file → after the walk, no detail file on the canonical tree), not to an inherent property of `_capture_changes`.
- **Rule 5 of `plan_tool/prompts/apply-finding.md` stays the first line of defense** and is not edited here. It is a prompt rule, which is why the mechanical backstop above exists; the plan's `## Risks` names the hazard and the acceptance criteria pin the outcome.

**The one scoped rc change, stated rather than denied**

Opening the walk moves a bare plan with a correctness gap and non-interactive stdin from rc 0 (today's whole-walk skip returns before the guard) to rc 2 (the existing `isatty()` guard). This is **not** a new exit code and **not** a new gate: it is the bare path reaching a guard that predates this plan and that a fully-detailed plan already hits, which is the point — the two lanes now behave the same. The plan's `## Out of scope` records it as an accepted, scoped exception to "no exit-code flip". Every other rc is unchanged: the bare withheld path stays 0, the empty-sidecar path stays 0, and `--fail-on-findings` is untouched.

**Recommended shape — narrow inside the existing bare branch**

The bare branch already sits in `cmd_completeness_apply` under the `_bundle_status` block, beside the `_apply_files_coherence` call it skips. Do the narrowing there and rebind both local rec lists:

- Partition the local `walk_recs` into the kept set (`source == "plan-correctness"`) and a withheld set (everything else). Rebind `walk_recs` to the kept set.
- Rebind `conceptual_walk_recs` from the narrowed `walk_recs` using the same `_CONCEPTUAL_APPLY_SOURCE_RANK` membership test the original derivation uses, so the `--jobs N` lane cannot fan out a withheld gap.
- When the withheld set is non-empty, warn with its count and the reason, then print one `_finding_progress_label(rec)` line per withheld gap — the same rendering the current skip path uses.
- Return 0 early **only when something was withheld and nothing is left to walk**. Guarding the early return on the withheld set (not on an empty `walk_recs` alone) keeps the empty-sidecar path on its existing `No saved completeness findings to walk in <path>` message instead of silently re-routing it to the bare tail.
- Otherwise fall through unchanged: the non-interactive-stdin check, the `_all_saved_recs` capture, the walker, `--commit`, and the closing `next:` line all keep their current behavior.

**Why an allow-list of one source, and the alternative rejected**

- The plan splits the fence **by axis** and says nothing about the two non-conceptual sources. An allow-list of `plan-correctness` gives them today's behavior for free and needs no argument about whether a structural split or a `DATA_CONTRACT.md` redirect is appropriate on a bare plan. An exclusion list (`source != "plan-completeness"`) would quietly widen the step to open the split bridge and the data-contract redirect on bare plans — a separate decision with its own risk, and outside this step's intent.
- **Rejected:** hoisting the `audit_detail_bundle_status` call above the source filter so both rec lists derive from one already-narrowed set. It reads cleaner, but it is a behavior-preserving move of a read-only computation with no observable effect — a refactor riding inside a feature step. The in-branch rebind gets the same guarantee without it. Worth doing on its own later if anyone wants it; see [Deferred](#deferred).

**Constraints that are not free to vary**

- **`_apply_files_coherence` stays skipped on a bare plan**, including when the walk now runs. It promotes citations found in detail **bodies** into a step's `allowed_mentions:`, and a bare step has no body to read. Keep its existing warning. Do not "finish the split" by opening it.
- **`_walk_apply_sources` does not change.** `plan-correctness` is already in that frozenset; the gate this step edits is the *rec list*, not the source set. The frozenset must keep flowing to both `_build_review_action_fn`'s `extra_apply_sources` and `walk_recommendations`' — the walker's dispatchability predicate and the action router have to see the same set. Its comment claims `plan-correctness` is safe to dispatch here "because the detail-bundle gate above already ran"; that rationale is now wrong and must be corrected in the same edit. The claim that survives is the real one: the *generic* reconcile/review walks must still never auto-apply `plan-correctness` (`_APPLY_AS_FINDING_SOURCES` in `plan_tool/review_walk.py` keeps it out of the base set).
- **The full saved set stays the carried context.** `_all_saved_recs` is captured from `saved.recommendations` before the in-memory reshape, and the narrowing must operate on the local list, never on `saved.recommendations` — a correctness apply on a bare plan should still see the withheld completeness gaps as context.
- **Leave the `--anchor` matching and its "no completeness finding matched" warning where they are**, above the bare branch. An anchor that names a withheld gap should match, then be reported as withheld — that tells the operator *why* their anchor did nothing, which a "no match" warning would not.
- **A `BLOCKED-STRUCTURAL` verdict from a correctness gap must not restructure a bare plan.** `apply_finding` can return `BLOCKED-STRUCTURAL`, which `plan_tool/cli/review_actions.py:_dispatch_structural_escalation` routes to `escalate_to_split` when `--apply-structural` is set. On a bare plan that would mutate structure off the back of a finding raised against a plan whose steps have no detail bodies — the same reason this step withholds a *saved* `granularity-split`. Withhold the bridge the same way: on a bare plan the escalation is **recommend-only**, whatever `--apply-structural` says. Relying on the existing TTY confirm is not enough; it is bypassed by `-y`, which the `--jobs N` lane requires. The plan's fence is "the split is by axis and only `plan-correctness` opens" — a structural mutation arriving through the correctness lane is that fence leaking.
- **No new gate or blocking severity, and exactly one scoped rc change** (the non-interactive 0→2 above, which the plan's `## Out of scope` accepts). The bare withheld path keeps returning 0 and nothing about `--fail-on-findings` changes.
- **No plan-body staleness warning is added.** The lane's only freshness gate is `_detail_bundle_staleness`, and on a fully bare plan its map is empty, so a plan body edited since the audit is applied against without a warning. That is **accepted** here, explicitly: comparing `SavedReview.plan_fingerprint` would be a new gate on a new lane, which the plan refuses, and the detailed lane has no such warning either. Do not build it; [Deferred](#deferred) files it forward.
- **Message wording is yours, with three requirements:** it must not claim the walk was skipped when it was not; it must name `plan-tool detail <name>` as the verb that unblocks the **specific** withheld gaps it just listed — the same remedy step 3 puts on the BLOCKED bullet, so the surfaces describing one run agree; and it must not read as a blanket "author details to unlock apply" precondition. The plan's `## Architecture` rule governs: `plan-tool detail` appears only as the unblock for a named BLOCKED or withheld finding.

**Prose to correct in the same edit** (grep the phrase, not just the identifier)

- `cmd_completeness_apply`'s docstring — the paragraph stating the deterministic files-coherence fix "runs without a prompt when a complete detail bundle exists" is still true; the surrounding framing that conceptual applies need one is not.
- The `completeness-apply` subparser `help=` in `register` — the sentence "Apply actions, including the deterministic files-coherence fix, run only when a complete detail bundle exists." The `--jobs` help's "applies both conceptual sources correctness-first" is also narrower on a bare plan; correcting it is optional and covered by the same two re-baselines.
- **The `--iterate` halt stderr** in `cmd_completeness` / the convergence loop that says "Conceptual findings are saved for `plan-tool completeness-apply`" for every deferred conceptual finding. On a bare plan that over-promises for `plan-completeness` the same way the old next-step renderers did. Axis-scope it: name `completeness-apply` only when a deferred correctness gap is among what was saved, and say completeness gaps stay informational until a detail bundle exists. This is the sixth operator surface the plan's Risks section lists; it lives in this step's declared file.

## Tests

Cases live in `tests/cli/test_completeness_cmd.py` and `tests/test_launcher.py`.

### Tests for this step

New cases in `tests/test_launcher.py`, covering the two `apply_finding` obligations:

- `test_apply_finding_prompt_marks_a_declared_detail_path_with_no_file` — `step.detail` set, no file on disk: the rendered prompt's `detail_path` carries the absent-file signal alongside the path.
- `test_apply_finding_prompt_keeps_the_undeclared_literal` — `step.detail is None` still renders `(no detail file declared for this step)`, unchanged.
- `test_apply_finding_prompt_names_the_file_when_it_exists` — regression: a step with an on-disk detail file gets the plain path, no signal.
- `test_apply_finding_removes_a_detail_file_the_apply_created` — an accepted (`APPLIED`) apply whose invoker writes to the declared-but-absent path leaves no file behind, and the result reports it.
- `test_apply_finding_removes_a_detail_file_the_autofix_followup_created` — primary pass is clean; the `auto_fix_introduced` follow-up writes the declared-but-absent path; after `apply_finding` returns the file is gone. Pins that the backstop reads the final post-follow-up state.
- `test_apply_finding_keeps_edits_to_an_existing_detail_file` — regression: the created-file backstop does not touch a file that existed before the call.

New cases in `TestCompletenessApplyDetailBundleGate` (its `_save_conceptual_completeness` helper seeds a `plan-completeness` rec; add sibling helpers for the other sources rather than changing that one):

- `test_bare_plan_walks_correctness_gaps` — a bare plan with one `plan-correctness` gap reaches `walk_recommendations`, which today's gate never calls.
- `test_bare_plan_withholds_completeness_gaps_from_the_walk` — bare plan, one correctness + one completeness gap: the walker's rec list holds only the correctness gap.
- `test_bare_plan_withholds_granularity_split_from_the_walk` — a medium `granularity-split` on a bare plan is reported, never dispatched to the split bridge.
- `test_bare_plan_withholds_data_contract_from_the_walk` — a `data-contract` finding on a bare plan is reported, never routed to the redirect wrapper.
- `test_bare_plan_reports_withheld_gaps_with_the_detail_pointer` — the withheld notice names the count and `plan-tool detail <name>`.
- `test_bare_plan_still_skips_files_coherence_when_the_walk_runs` — with a correctness gap present, `_apply_files_coherence` is still not called.
- `test_bare_plan_carried_context_keeps_the_withheld_gaps` — the carried findings handed to the action builder still cover the withheld completeness gap.
- `test_bare_plan_non_interactive_stdin_exits_2` — bare plan, correctness gap, piped stdin: gaps reported, rc 2, nothing applied. Pins the scoped 0→2 move as intended behavior rather than an accident, and pins it against the detailed path's existing rc.
- `test_bare_plan_blocked_structural_verdict_does_not_reach_the_split_bridge` — a correctness apply returning `BLOCKED-STRUCTURAL` on a bare plan under `--apply-structural`: `escalate_to_split` is not called with an applying disposition, and the outcome is reported as a recommendation.
- `test_fully_detailed_plan_blocked_structural_still_escalates` — regression: the bridge is withheld on bareness, not disabled.
- `test_fully_detailed_plan_walks_both_conceptual_sources` — regression: off the bare path both sources still reach the walker in correctness-first order.
- `test_bare_iterate_halt_names_apply_only_for_correctness` — bare `--iterate` halt stderr: when the deferred set includes `plan-correctness`, it names `completeness-apply`; when it carries only `plan-completeness`, it does not promise that verb and says those gaps stay informational until a detail bundle exists.

Rewritten:

- `test_bare_plan_skips_conceptual_walk` → **`test_bare_plan_with_only_completeness_gaps_skips_the_walk`** — same setup (a lone `plan-completeness` rec), same rc 0 and gap label, updated assertion strings for the new withheld wording.

New cases in `TestCompletenessApplyParallel`:

- `test_bare_plan_parallel_lane_fans_out_only_correctness` — a bare plan under `--jobs 2 -y` with both sources saved: the parallel runner receives the correctness gap only.
- `test_bare_plan_parallel_lane_does_not_replay_a_created_detail_file` — a worker whose apply writes to a declared-but-absent detail path: after the walk, the plan-body edit is on the canonical tree and no detail file remains. Pins the shared `apply_finding` created-file cleanup under `--jobs N`, not an inherent `_capture_changes` property.

Must stay green untouched (the regression net):

- `TestCompletenessApplyDetailBundleGate::test_bare_plan_skips_files_coherence_writer` — empty sidecar on a bare plan; nothing to walk, writer still not called.
- `TestCompletenessApplyDetailBundleGate::test_fully_detailed_plan_runs_files_coherence_writer`.
- The rest of `TestCompletenessApplyParallel` (dirty-tree refusal, `-y` requirement, single-anchor degrade, pre-skip mirroring) — all run on detailed plans and must not shift.
- `tests/test_review_walk.py::test_plan_correctness_dispatch_scoped_to_completeness_apply` — the generic walks still refuse `plan-correctness`.
- `tests/cli/test_cli_reference.py` and `tests/cli/test_package_surface.py` — green **after** the two re-baselines, not before.

**Green-before-done gate:** every case above must pass, plus the full `uv run pytest tests/ -q` suite. Do not add cases that only restate the gate's existing behavior.

## Acceptance criteria

- `plan-tool completeness-apply <name>` on a bare plan whose saved audit carries a `plan-correctness` finding invokes the per-gap apply walk; the walker's rec list contains that finding.
- The same run's walker rec list contains no `plan-completeness`, `data-contract`, or `granularity-split` finding.
- Every withheld finding is printed with its `<source>/<severity>: <title>` label, and the notice names `plan-tool detail <name>` as the unblock for those named gaps — not as a precondition on applying anything.
- A bare plan whose saved audit carries only non-correctness findings applies nothing and exits 0.
- A bare plan with an empty saved audit still prints `No saved completeness findings to walk in <path>` and exits 0.
- A bare plan with a correctness gap and non-interactive stdin exits 2 and applies nothing — the same rc a fully-detailed plan already returns there.
- `apply_finding`'s rendered prompt marks a declared `detail:` path that has no file on disk; the `step.detail is None` literal is unchanged; a step with an on-disk detail file gets the plain path.
- After an `APPLIED` apply on a bare plan, no file exists at a tracked detail path that was absent before the call — on the serial walk and after the `--jobs N` replay tail.
- A `BLOCKED-STRUCTURAL` verdict on a bare plan does not mutate plan structure, even with `--apply-structural` and `-y`; on a fully-detailed plan the bridge still applies.
- `_apply_files_coherence` is not called on a bare plan under any of the above.
- `--jobs 2 -y` on a bare plan dispatches only correctness findings to `run_parallel_apply`.
- A fully-detailed plan's behavior is unchanged: both conceptual sources walk, correctness first, and the files-coherence writer runs.
- `grep -n 'run only when a complete detail bundle exists' plan_tool/cli/completeness_cmd.py` returns nothing.
- On a bare `--iterate` run, the halt stderr names `completeness-apply` only when a deferred `plan-correctness` gap was saved; when only `plan-completeness` gaps were deferred it does not name that verb and says they stay informational until a detail bundle exists.
- `uv run pytest tests/cli/test_cli_reference.py tests/cli/test_package_surface.py -q` passes with the regenerated artifacts committed — specifically `docs/cli/completeness-apply.md`, `docs/cli/README.md`, and `tests/cli/package_surface_help.golden.txt`.

## References

- `plan_tool/cli/completeness_cmd.py` — this step's file: `cmd_completeness_apply`'s bare branch, `_apply_files_coherence`, `_finding_progress_label`, `_CONCEPTUAL_APPLY_SOURCE_RANK` / `_SAVED_SERIAL_APPLY_SOURCE_RANK`, `_apply_walk_recs_parallel`, and the `completeness-apply` subparser in `register`.
- `plan_tool/prompts/apply-finding.md` — the apply contract: edits the plan file "and/or the step's detail file **if applicable**", never creates a file, and reserves `BLOCKED` for a genuinely missing detail file. The evidence that a plan-body-only correctness edit needs no detail bundle.
- `plan_tool/launcher.py` — this step's second file: `apply_finding`'s detail-tracking loop, `_snapshot_text_files` / `_restore_text_files`, and the `detail_path` prompt variable with its `(no detail file declared for this step)` fallback. The two obligations above land here.
- `plan_tool/review.py` — `audit_detail_bundle_status` and `DetailBundleStatus.is_bare`, the binary fact this gate routes on.
- `plan_tool/review_walk.py` — `_APPLY_AS_FINDING_SOURCES`, `should_apply_as_finding`, and `split_escalation_target`; the reason `plan-correctness` must stay out of the base set even as this step opens it on bare plans.
- `plan_tool/cli/completeness_apply_parallel.py` — `run_parallel_apply` and the `_capture_changes` comment that falsely claims newly-created files are ignored for declared-but-absent detail paths; this step corrects that comment and relies on the shared `apply_finding` cleanup, not on capture.
- `plan_tool/cli/review_actions.py` — `_dispatch_structural_escalation`, the path a `BLOCKED-STRUCTURAL` verdict takes to `escalate_to_split`; the bridge this step withholds on bare plans.
- `plan_tool/completeness_report.py` — the reporting surfaces steps 2 and 5 bring into line **after** this step lands. Read only to keep the axis vocabulary consistent; this step does not depend on it.
- `CLAUDE.md` § "Correctness gates" — states the blanket detail-bundle contract this plan replaces; step 7 corrects it, not this step.

## Applicable guardrails

- **The plan's `## Out of scope`, no new gate — and the one scoped rc exception.** This step may not add a blocking severity, a refusal-to-advance, or a new exit code. The single accepted movement is a non-interactive bare run with a correctness gap going 0→2 at the pre-existing `isatty()` guard, which the plan records; the bare withheld path keeps rc 0.
- **The plan's `## Out of scope`, no plan-body staleness warning.** Bare apply's missing freshness signal is accepted for this effort. Adding a `plan_fingerprint` comparison here is out of bounds.
- **The plan's `## Architecture`, when `plan-tool detail` may be named on a bare plan.** The withheld notice names it as the unblock for the gaps it just listed. A blanket "author details first" sentence re-creates the contract this plan replaces.
- **The plan's `## Out of scope`, per-finding coverage routing refused.** The gate keys on the plan-level bare flag and the finding's `source`. It may not read `step_id`, parse a `step<N>` anchor prefix, or otherwise decide per finding whether its target step has detail.
- **The plan's `## Architecture`, decision 1 — the split is by axis.** Only `plan-correctness` opens on a bare plan. Widening to the structural or data-contract sources is a different decision and belongs to whoever makes it.
- **The plan's `## Out of scope`, jira grade and `#85` untouched.** Nothing here changes the read-only-audit split or any jira-grade behavior; `completeness-apply` stays the sole mutator of the conceptual gap map.
- **The plan's `## Risks`, the surfaces describing one run must stay in step.** The verb's withheld notice must name the same remedy step 3 puts on the BLOCKED bullet, so the console block, the report, and this verb do not describe one run three ways.

## Deferred

- **Opening `granularity-split` or `data-contract` on a bare plan** — both stay withheld here. A structural split needs no detail bundle and is arguably already allowed at bare, but that is a separate scope decision with its own risk; file it in `BACKLOG.md` if it is wanted.
- **Hoisting the `audit_detail_bundle_status` call above the source filter** — a behavior-preserving move that would let both rec lists derive from one narrowed set. Not taken: it is a refactor with no observable effect and would make this a mixed step. Route to `BACKLOG.md`.
- **The stale complete-bundle rationale in `plan_tool/review_walk.py` and `tests/test_review_walk.py`** — comment and docstring text only; every behavior claim they guard still holds. Outside this step's declared files; file one `BACKLOG.md` entry naming both anchors. (`plan_tool/cli/completeness_apply_parallel.py`'s copy is corrected here, since this step pins the behavior that comment describes.)
- **A plan-body staleness gate for the bare apply lane** — accepted as absent for this effort (see the plan's `## Out of scope`). If it is wanted, it is a `BACKLOG.md` entry: compare `SavedReview.plan_fingerprint` against the plan at apply time and warn, for **both** lanes rather than only the bare one, since the detailed lane has the same hole.
- **Opening the split bridge on bare plans** — withheld here by decision. If a bare plan's `BLOCKED-STRUCTURAL` verdicts should be able to restructure, that is a scope decision with its own risk; `BACKLOG.md`.
- **`CLAUDE.md`, `docs/AUDIT_FLOW.md`, and BACKLOG #83** — step 7 owns that sweep.
- **`plan_tool/cli/completeness_phases.py`'s grouped-report next steps** — step 5 owns it.
- **The audit prompt's bare-step edge-case conditioning** — step 6 owns it.
