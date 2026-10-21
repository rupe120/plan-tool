# Step 4 — Add the recommend-only next action and rendering for a recurring high-impact seam

## Summary

Give `plan_tool/impact_recurrence.py` the second half of its contract: turn step 3's tripped-seam result into one recommend-only next action (a step-localized `plan-tool split` or `plan-tool scope-out` when the impact evidence names a step, otherwise a conservative `plan-tool create --from-existing` re-decompose) and render an operator-facing block that reports the non-successful `recurring_high_impact_seam` outcome with its per-pass evidence. Both live in the same leaf module step 3 creates, with unit tests in `tests/test_impact_recurrence.py`. The key decision: the action is a plain data record plus a command string — this module never calls `scope_out_step`, `escalate_to_split`, or any other mutator, and never imports `plan_tool.cli`. On green, steps 6 and 7 can stop a live loop and print a ready-to-run recommendation without deciding the remedy themselves.

## Table of Contents

- [Summary](#summary) — what the step adds and the observable result.
- [Why](#why) — why the stop needs its own action and render.
- [Input](#input) — the step-3 result and the history model this reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — per-file edit list.
- [Implementation](#implementation) — the remedy rule, the render shape, and the constraints.
- [Tests](#tests) — the unit tests to add and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes.
- [References](#references) — the docs worth reading for this step.
- [Deferred](#deferred) — what this step deliberately leaves alone.

## Why

Step 3 can tell that the same open high-impact region survived three passes without shrinking, but a bare boolean is useless to an operator: the loop would stop and say nothing actionable. The existing offline diagnosis already solved the shape of that answer — `plan_tool/convergence_diagnosis.py: classify_fork` picks a remedy and `render_diagnosis` prints it — but it forks on *severity* trends from saved report history, and the plan keeps the two verdicts deliberately separate so an operator never mistakes one for the other. So the live seam needs its own picker and its own printed block, using its own outcome word, while still recommending the same real `plan-tool` commands an operator would run by hand. BACKLOG.md #158 pins the rule this step implements: recommend a localized split or scope-out **only** when the impact evidence itself resolves a step; otherwise recommend conservative re-decomposition, and never mutate plan structure from the loop.

## Input

- **Step 3's outcome** — the impact-recurrence classifier in `plan_tool/impact_recurrence.py` and its frozen result describing whether a seam tripped, the seam's identity, and its per-pass trajectory. Read the landed symbol names and field names off step 3's code before writing against them; do not guess them from this file or from the plan's prose. If step 3 already defines the `recurring_high_impact_seam` token, import it — do not retype the literal.
- **`plan_tool/convergence_diagnosis.py: RegionTrend`** — the shape step 3's seam identity is built from. The fields this step reads for the remedy choice and the render are `step_id`, `anchor`, `focus`, `first_severity`, `last_severity`, `max_severity`, `run_indices`, and `open_counts`.
- **Step 2's outcome** — each `RunFinding` carries its impact plus an impact-provenance token. This step displays provenance in the render as the evidence line; it makes no eligibility decision of its own (that is step 3's).
- **`plan_tool/convergence_diagnosis.py`'s step-focus rule** — `_region_step_focus` resolves a region to a step number via `step_id`, else a `step<N>` token in `anchor`, else None. Prefer whatever step 1 made public over a second copy of that rule.

Verification limit: no real saved history in this repo carries three consecutive high-impact passes, so every test builds its seam fixtures by hand.

## Files (creates vs edits)

- **New files:** none — step 3 creates both paths.
- **Existing files (edits only):**
  - `plan_tool/impact_recurrence.py` — add the action-kind constants, a frozen recommendation record, the picker that maps a tripped seam to one command, and the render function.
  - `tests/test_impact_recurrence.py` — unit tests for each remedy arm, the recommend-only command form, and the render's content.

## Implementation

**What must be true when the step is done**

- One function takes step 3's classifier result and returns a frozen recommendation record: the action kind, the resolved step (or None), and a ready-to-run `plan-tool` command string.
- The command is always **recommend-only** — never carries `--apply`, `-y`, or `--yes`.
- A seam whose evidence resolves exactly one step gets a step-localized remedy. Anything else — no resolvable step, or occurrences spread across more than one step — gets the conservative re-decompose command.
- One render function returns a printable block naming the `recurring_high_impact_seam` outcome, the seam's per-pass evidence, and the recommended command. It never reports success and never prints a `convergence:` headline or a `FORK_*` word.
- `plan_tool/impact_recurrence.py` stays a leaf: no `plan_tool.cli` import, no mutator import, no Claude call, no file writes.

**Recommended shape**

- **Action kinds.** Define module-level string constants and comment them the way `plan_tool/convergence_diagnosis.py` comments its `FORK_*` block ("do not inline the literals downstream"). Pick self-describing names — one way: `ACTION_SPLIT_STEP`, `ACTION_SCOPE_OUT_STEP`, `ACTION_RE_DECOMPOSE`, and `ACTION_NONE` for a result with no tripped seam. Deliberately different words from `FORK_LOCALIZED` / `FORK_SCOPE_OUT` / `FORK_STRUCTURAL`, so a reader can't confuse a live stop with the offline fork.
- **The record.** A `@dataclass(frozen=True)` mirroring `ForkRecommendation`'s spirit: action kind, `step_focus: Optional[int]`, `command: str` (`""` on `ACTION_NONE`), and enough of the seam to render without re-walking history. Give any field later steps might not set a default, matching the module's frozen-record convention.
- **Picking the remedy.** Two decisions in order:
  1. **Does the evidence resolve one step?** Collect the step focus of every region the seam covers. If they all resolve and agree on one number, that is the localized case. If any is unresolvable, or two or more distinct numbers appear, fall to re-decompose. Do not guess a step from title prose.
  2. **Split in place, or carve out?** Within the localized case, choose the carve (`plan-tool scope-out <slug> --step N`) when the seam is still severe and not improving — current severity high or critical **and** the first→last trend flat or worse — else the in-place re-split (`plan-tool split <slug> --step N --into "<first sub-step>" --into "<second sub-step>"`). This bar is a real discriminator, not dead code: impact is independent of normalized severity, so a high-impact seam can sit at advisory severity and still deserve a plain re-split. Reuse `convergence_diagnosis`'s severity-rank ordering rather than inventing a second severity table.
- **Command text.** Reuse the command builders in `plan_tool/convergence_diagnosis.py` (`_split_command`, `_scope_out_command`, `_reseed_command`) if step 1 exported them under public names. If it did not, write local builders in `plan_tool/impact_recurrence.py` that emit the same strings, and keep them small and obviously parallel — the duplicate is called out under Deferred rather than fixed here, because consolidating them is a refactor across a file this step does not own.
- **The render.** Return one string built from a `list[str]` joined with `"\n"`, the same way `render_diagnosis` does. Content, in order:
  - A headline naming the outcome token and the plan slug — the words must make it obvious this is a stop, not a clean finish.
  - The seam's identity (its focus) and its per-pass evidence: the passes it appeared in, its open counts across them, and the impact provenance carried by its findings.
  - A short prose line saying why another pass is the wrong operation, then the recommended command indented under it, plus the "the executor may refuse it as unsafe" caveat on the carve arm — same caveat `_spinning_body` already prints.
  - When the action is re-decompose, keep the `<seed.md>` placeholder note so the operator knows the command is not runnable as printed.
- **Rejected alternative:** building a `ConvergenceDiagnosis` out of the impact evidence and delegating to `classify_fork` / `render_diagnosis`. It would reuse code but produce the offline verdict's vocabulary and headline, which is exactly what the plan says the two surfaces must not share; it would also drag this module's correctness onto `classify_fork`'s severity semantics, which BACKLOG #158 names out of scope for change.

**Shared-logic sweep**

The "pick a structural remedy and print a runnable command" rule already exists in `plan_tool/convergence_diagnosis.py` (`classify_fork` + `_spinning_body`), and the same command strings are produced a third time by `plan_tool/completeness_report.py`'s BLOCKED split renderer. This step adds a fourth producer scoped to the live impact stop. Folding all of them into one shared command renderer is a consolidation refactor across three modules that `detail` cannot mint — it is listed under Deferred for reconcile, not pulled into this step's footprint. The step-focus rule (`step_id` → `step<N>` anchor → None) must **not** be re-implemented: use step 1's public helper.

## Tests

In `tests/test_impact_recurrence.py`:

- `test_no_tripped_seam_yields_no_action` — a classifier result with no seam returns action `ACTION_NONE`, `step_focus is None`, and `command == ""`.
- `test_seam_on_one_step_recommends_in_place_split` — a seam whose regions all resolve to step 5 with a non-severe or improving severity trend returns the split action and the `plan-tool split <slug> --step 5 --into …` command.
- `test_severe_not_improving_seam_recommends_scope_out` — the same seam with `last_severity="high"` and a flat-or-worse trend returns the scope-out action and `plan-tool scope-out <slug> --step 5`.
- `test_seam_with_step_only_in_anchor_resolves_the_step` — a region with `step_id=None` and anchor `step7-…` still resolves to step 7.
- `test_seam_without_resolvable_step_recommends_re_decompose` — a region with `step_id=None` and a bare title-slug anchor returns the re-decompose action, `step_focus is None`, and the `plan-tool create <slug> --from-existing <seed.md> --iterate` command.
- `test_seam_spanning_two_steps_recommends_re_decompose` — regions on step 2 and step 4 do not produce a split or carve.
- `test_recommended_commands_are_never_auto_applying` — every arm's command contains no `--apply`, `-y`, or `--yes`.
- `test_render_names_the_seam_outcome` — the rendered block contains the `recurring_high_impact_seam` token and the recommended command.
- `test_render_reports_a_stop_not_a_success` — the block contains no success wording and no `converging` / `convergence:` headline.
- `test_render_shows_per_pass_evidence` — the three passes' open counts and the seam's focus appear in the block.
- `test_render_shows_the_unsafe_caveat_on_a_carve` — the scope-out arm's block warns the executor may refuse the carve; the split arm's does not.
- `test_render_of_no_action_result_is_empty` — an `ACTION_NONE` result renders to `""` so a caller can print unconditionally without emitting a stray block.
- `test_module_performs_no_structural_mutation` — the module source imports neither `scope_out_step`/`escalate_to_split`/`reground_bridge` nor `plan_tool.cli`, pinning the recommend-only, leaf-module contract.

**Test-creation order (feature step):** these tests land in the same change as the implementation. All of them (approx. 13 tests) must be green — `uv run pytest tests/test_impact_recurrence.py -q` — before the step is done, and the full suite must stay green.

## Acceptance criteria

- `plan_tool/impact_recurrence.py` exports four action-kind constants and a frozen recommendation record with an action kind, `step_focus`, and `command`.
- The picker returns the split command for a one-step seam that is not severe-and-not-improving, and the scope-out command for one that is.
- The picker returns the re-decompose command whenever the seam's evidence resolves zero steps or more than one distinct step.
- No command string produced by this module contains `--apply`, `-y`, or `--yes`.
- The render returns `""` for a no-seam result and, for a tripped seam, a block containing the `recurring_high_impact_seam` token, the seam's focus, its per-pass open counts, and the recommended command.
- The render contains no `convergence:` headline and none of the `FORK_*` words.
- `plan_tool/impact_recurrence.py` imports no `plan_tool.cli` module and no structural mutator, and calls no backend.
- `plan_tool/convergence_diagnosis.py` behavior is unchanged — `classify_fork` and `render_diagnosis` return the same output for the same input as before this step.
- All new tests pass and the existing suite stays green.

## References

- [Python `dataclasses` — Data Classes](https://docs.python.org/3/library/dataclasses.html) — `frozen=True` and field defaults, the convention this module's recommendation record follows.
- [Python `enum` — Support for enumerations](https://docs.python.org/3/library/enum.html) — background for modeling the action kinds; note the codebase's existing choice is plain module-level string constants (`FORK_*`), which this step matches.
- [pytest — How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — the table-driven form that fits the four remedy arms cleanly.

## Deferred

- **Consolidating the three copies of the split/scope-out/re-seed command builders** — `plan_tool/convergence_diagnosis.py`, `plan_tool/completeness_report.py`, and this module each build them. A single shared renderer is a cross-module refactor `detail` cannot mint; route it to reconcile or a follow-up BACKLOG entry.
- **A contiguous-range carve (`--step N --through M`)** — the offline fork supports a multi-step band; this step recommends re-decompose whenever the seam spans more than one step. Revisit only if field evidence shows multi-step seams are common.
- **Wiring the action into the live loops** — steps 6 and 7 own the completeness and reconcile call sites; this step only produces the record and the text.
- **The `structural_stop` continuation reason** — owned by step 5 in `plan_tool/convergence.py`.
- **Actually applying any remedy** — mutation stays behind the existing `--apply` + confirm gates on `plan-tool scope-out` / `plan-tool split`; the plan names auto-apply out of scope.
- **Unifying this block with the offline `plan-tool convergence` render** — the two are kept deliberately distinct; the plan's Deferred section tracks reconciling them.
