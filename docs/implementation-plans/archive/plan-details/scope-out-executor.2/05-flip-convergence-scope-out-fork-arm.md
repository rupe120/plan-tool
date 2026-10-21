> **Auto-archived**: this plan was swept on 2026-06-25 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Flip the convergence scope-out fork-arm to a runnable `plan-tool scope-out --step N` command for single-step evidence

## Summary

- Turns the convergence diagnostic's scope-out recommendation from prose-only into a runnable line. Edits `plan_tool/convergence_diagnosis.py`: add a `_scope_out_command(plan_slug, step)` builder (mirroring `_split_command`), fill the now-empty `command` field in `classify_fork`'s `FORK_SCOPE_OUT` branch, and append the command line in `_spinning_body`'s scope-out arm.
- The scope-out arm itself (`FORK_SCOPE_OUT`, `_region_triggers_scope_out`, the `classify_fork` branch, the `_spinning_body` arm) is built by the sibling **advisory** plan (`structural-remedy-vocabulary`, step 1) and is expected at HEAD when this step runs. This step only flips its `command=""` to the runnable verb now that step 4 shipped the `plan-tool scope-out` executor.
- Key decision: the runnable line emits **only when `command` is non-empty** (the single-resolved-step case, where `step_focus` is set); non-single-step evidence remains the structural re-seed path, while only a defensive empty `FORK_SCOPE_OUT.command` keeps the advisory plan's carve/defer prose as a **prose-only fallback** so it never prints a broken `--step None` line.
- On green: `plan-tool convergence` on a spinning plan whose localized step has a severe-and-not-improving region prints the carve/defer prose **plus** preview framing that the runnable `plan-tool scope-out <slug> --step N` line may return `unsafe` under the executor's safety gate; localized (re-split) and structural (re-seed) arms are unchanged.

## Table of Contents

- [Why](#why) — the advisory plan left the scope-out command empty for this step to fill
- [Files (creates vs edits)](#files-creates-vs-edits) — the two in-scope files, both edits
- [Implementation](#implementation) — the command builder, the `classify_fork` fill, the `_spinning_body` arm
- [Tests](#tests) — command-builder, `classify_fork`, and `render_diagnosis` cases plus the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors
- [References](#references) — the surfaces this step edits and the sibling-plan handoff
- [Deferred](#deferred) — multi-step carve, reconcile-side routing, command-builder consolidation

## Why

- The advisory plan ships the scope-out **recommendation** with `command=""` on purpose — it renders prose-only so it never points at a `plan-tool scope-out` verb that did not exist yet. It carries `step_focus` on the `FORK_SCOPE_OUT` recommendation precisely so this executor plan can read it and fill the empty command (the cross-plan encoding of detection-unconditional / mutation-gated).
- Steps 1–4 of this plan built and wired the executor: `plan_tool/scope_out.py:scope_out_step(...)` and the `plan-tool scope-out <name> --step N` CLI (step 4). The verb now exists and is recommend-only by default, so the diagnostic can safely print it.
- This step closes the handoff: flip the scope-out arm so a spinning, single-step, severe-and-not-improving diagnosis tells the operator the exact runnable line instead of describing the remedy in prose. Nothing else recommends scope-out, so `convergence_diagnosis.py` is the only edit surface — confirm with `grep -rn "scope.out" plan_tool/ tests/` **only after the sibling advisory step lands** (consistent with the pre-flight gate below): the advisory plan adds the first `scope-out` references, so at HEAD before it lands this grep returns zero matches — that empty result is expected, not a contradiction. Once it lands, every match falls in `convergence_diagnosis.py` (or its test), no other recommender.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — add `_scope_out_command(plan_slug, step)` beside `_split_command` / `_reseed_command`; fill `command` in `classify_fork`'s `FORK_SCOPE_OUT` branch; append the runnable line in `_spinning_body`'s scope-out arm (keep the carve/defer prose as the prose-only fallback when `command` is empty).
  - `tests/test_convergence_diagnosis.py` — add `_scope_out_command`, `classify_fork`, and `render_diagnosis` cases for the runnable command; extend the import block with `_scope_out_command` (and `FORK_SCOPE_OUT` if the advisory plan's import addition is not already present).

## Implementation

### `plan_tool/convergence_diagnosis.py`

**Foundational logic of this step:** render one runnable `plan-tool scope-out <slug> --step N` line for the single-resolved-step scope-out fork, falling back to prose when no step is resolved. The fork classification, the `_region_triggers_scope_out` predicate, and the `FORK_SCOPE_OUT` constant are **inputs** owned by the advisory plan — this step does not re-derive them. The repo's split-recommendation command shape lives in `plan_tool/completeness_report.py:_blocked_next_step` (the `plan-tool split … --step … --into …` source); the scope-out verb is a new, distinct recommendation, so it gets its own small builder rather than reusing the split shape.

**Pre-flight gate — run BEFORE any edit (advisory-plan dependency `depends_on:` can't express).** The scope-out arm this step flips (`FORK_SCOPE_OUT`, `_region_triggers_scope_out`, the `classify_fork` `FORK_SCOPE_OUT` branch, the three-way `_spinning_body` dispatch) is built by the *sibling* `structural-remedy-vocabulary` plan (step 1), not by this plan's `depends_on: 4`. If an executor runs this step before that advisory plan lands, the arm is absent and the edits below target a two-way dispatch that no longer matches these instructions. Confirm the arm exists before editing — both checks must pass:

```bash
grep -n FORK_SCOPE_OUT plan_tool/convergence_diagnosis.py        # must return at least one match
grep -n _region_triggers_scope_out plan_tool/convergence_diagnosis.py   # must return at least one match
```

If either returns no match, **stop and fail fast** — the advisory plan (`structural-remedy-vocabulary` step 1) has not landed yet; do not edit a two-way `_spinning_body` dispatch. Also confirm `_spinning_body` is already the three-way fork dispatch (`if rec.fork == FORK_SCOPE_OUT: … elif rec.fork == FORK_LOCALIZED: … else: # FORK_STRUCTURAL`) before appending to its scope-out arm.

- **Add `_scope_out_command(plan_slug: str, step: Optional[int]) -> str`** beside `_split_command` and `_reseed_command`:
  - Return `f"plan-tool scope-out {plan_slug} --step {step}"` when `step is not None`.
  - Return `""` when `step is None` — the prose-only fallback signal, mirroring the advisory plan's `command=""` convention so a scope-out recommendation with no resolved step degrades to prose rather than emitting `--step None`.
  - Recommend-only form: no `--apply` / `-y` in the printed line. The operator runs it to preview the carve (the executor's default is recommend-only), then re-runs with `--apply -y` to commit — consistent with the mutation-gated invariant the executor already enforces.
  - **No placeholder.** Unlike `_split_command` (`--into "<first sub-step>"` placeholders) and `_reseed_command` (`<seed.md>` placeholder), the scope-out line is fully runnable as printed — the executor derives the forward-seed path itself. Keep the docstring terse and note this no-placeholder distinction.

- **Edit `classify_fork`** — fill the command in the existing `FORK_SCOPE_OUT` branch (the advisory plan's branch inside the single-resolved-step arm, gated by `any(_region_triggers_scope_out(r) for r in regions)`):
  - Change the return from `ForkRecommendation(FORK_SCOPE_OUT, step, "", regions, False)` to `ForkRecommendation(FORK_SCOPE_OUT, step, _scope_out_command(diagnosis.plan_slug, step), regions, False)`.
  - `step` is the resolved single step (guaranteed non-None in this arm), so `command` is always filled here in practice; the `Optional` handling in `_scope_out_command` is the defensive floor, not the live path.
  - **Leave `FORK_LOCALIZED` and `FORK_STRUCTURAL` untouched.** They keep `_split_command` / `_reseed_command`. Scope-out fires only in the single-resolved-step case (the executor is single-step `--step N`); distinct-step / unresolvable evidence still falls to `FORK_STRUCTURAL`.

- **Edit `_spinning_body`** — append the runnable line in the existing scope-out branch of the three-way fork dispatch (`if rec.fork == FORK_SCOPE_OUT: … elif rec.fork == FORK_LOCALIZED: … else: # FORK_STRUCTURAL`):
  - Keep the advisory plan's carve/defer prose unchanged: it names the over-packed step (`step {rec.step_focus}`) as the trigger and states the remedy acts at plan scope (carve the step out into a forward-seed and defer it so the rest of the plan converges, then re-plan the carved work on its own).
  - Add one sentence before the command line that frames the command as a preview: the executor's safety gate may still refuse the carve and return `unsafe`.
  - Append the command line **only when `rec.command`** is truthy: `if rec.command: lines.append(f"  {rec.command}")`. When `rec.command` is empty (no resolved step — defensive), render prose only, preserving the advisory plan's prose-only behavior as the floor.
  - Do **not** touch the `FORK_LOCALIZED` (`_split_command`) or `FORK_STRUCTURAL` (`_reseed_command` + hand-author note + ambiguous note) arms.

- **No CLI change.** `render_diagnosis` is the only render path and `plan_tool/cli/convergence_cmd.py:cmd_convergence` already prints its output verbatim; the runnable line flows through unchanged.

## Tests

Reference: `tests/test_convergence_diagnosis.py`. Reuse the existing in-memory builders `_fork_region` (accepts `step_id`, `anchor`, `focus`, `first`, `last`, `peak`), `_series`, and `_diag`. Extend the top-of-file import block with `_scope_out_command` (and `FORK_SCOPE_OUT` if the advisory plan's import line is not already present in the merged file).

### Test-creation order (feature step)

This is a **feature** step — new behavior (flipping the empty command to a runnable line). Add these unit tests **with** the implementation. Every new test must be green, and the full `tests/test_convergence_diagnosis.py` suite must stay green, before the step is considered finished.

`_scope_out_command`:

- `test_scope_out_command_single_step` — `_scope_out_command("spinner", 5)` returns exactly `"plan-tool scope-out spinner --step 5"`.
- `test_scope_out_command_no_placeholder` — the returned string contains no `<`, no `--into`, and no `<seed.md>` (distinguishes it from the split/reseed placeholder builders).
- `test_scope_out_command_empty_when_no_step` — `_scope_out_command("spinner", None)` returns `""` (the prose-only fallback source).

`classify_fork`:

- `test_classify_scope_out_fills_runnable_command` — one spinning series, single region on step 5 with `first=high, last=high, peak=high` → `fork == FORK_SCOPE_OUT`, `step_focus == 5`, `command == "plan-tool scope-out spinner --step 5"`, `ambiguous is False`.
- `test_classify_scope_out_command_not_placeholdered` — same scope-out diagnosis → `command` contains `plan-tool scope-out` and `--step 5`, and contains no `<`/`--into` (the scope-out command is fully runnable, unlike split/reseed).
- `test_classify_localized_command_unchanged` — single medium region on step 5 stays `FORK_LOCALIZED` with a `plan-tool split … --step 5` command (guards the localized arm against regression).
- `test_classify_structural_command_unchanged` — two high-flat regions on steps 3 and 5 stay `FORK_STRUCTURAL` with a `plan-tool create` command (scope-out never fires on multi-step evidence).

`render_diagnosis`:

- `test_render_scope_out_emits_runnable_command` — spinning diagnosis whose single step (5) has a high-and-flat region → output contains `plan-tool scope-out spinner --step 5`, still names the step and describes carving/deferring it, frames the command as a preview the executor may refuse with `unsafe`, and still shows the per-region severity-trend line.
- `test_render_scope_out_only_scope_out_verb` — the same output contains `plan-tool scope-out` but **not** `plan-tool split` and **not** `plan-tool create` (the scope-out arm renders only the scope-out verb).

Already-green regression guards (no edits needed, confirm they stay green): `test_classify_localized_single_region_one_step` and `test_render_spinning_localized_emits_split_command` use default medium-severity regions, so they keep classifying `FORK_LOCALIZED` and rendering the split command; `test_diagnose_then_classify_on_spinning_fixture` consumes the all-medium `sample-report-history.json` fixture, so it keeps rendering the split command; the advisory plan's `test_render_scope_out_prose_no_command` is the one guard this step intentionally inverts — update it (or supersede it with `test_render_scope_out_emits_runnable_command`) since the scope-out arm now **does** emit a runnable line.

## Acceptance criteria

- `_scope_out_command("spinner", 5)` returns `"plan-tool scope-out spinner --step 5"`; `_scope_out_command("spinner", None)` returns `""`.
- `classify_fork` on a spinning, single-resolved-step, severe-and-not-improving diagnosis returns `fork == FORK_SCOPE_OUT`, `step_focus` set to the resolved step, and `command == "plan-tool scope-out <slug> --step <step>"` (no placeholder tokens).
- A medium-only or improving localized region still returns `FORK_LOCALIZED` with the `plan-tool split … --step N` command; multi-step / unresolvable evidence still returns `FORK_STRUCTURAL` with `plan-tool create … --from-existing <seed.md>` — both unchanged.
- `render_diagnosis` on a scope-out diagnosis prints the carve/defer prose **and** the runnable `plan-tool scope-out <slug> --step N` line, frames the command as a preview the executor may refuse with `unsafe`, still shows the severity-trend line, and prints no `plan-tool split` / `plan-tool create` line in that arm.
- All new tests pass and the full `tests/test_convergence_diagnosis.py` suite is green.

## References

- `plan_tool/convergence_diagnosis.py` — `classify_fork`, `ForkRecommendation` (`command` / `step_focus`), `_split_command` / `_reseed_command`, `_spinning_body`, `render_diagnosis`; the surfaces this step edits, and the `FORK_SCOPE_OUT` / `_region_triggers_scope_out` inputs the advisory plan adds.
- `docs/implementation-plans/plan-details/structural-remedy-vocabulary/01-prose-only-scope-out-fork-arm-localized.md` — the sibling advisory step that builds the prose-only scope-out arm and leaves `command=""` for this step to fill; states `step_focus` is carried for exactly this flip.
- `docs/implementation-plans/plan-details/scope-out-executor/04-wire-plan-tool-scope-out-cli-command.md` — step 4's CLI wiring; pins the `plan-tool scope-out <name> --step N` shape this builder must emit.
- `plan_tool/completeness_report.py` — `_blocked_next_step` / `_blocked_split_targets`, the repo's source-of-truth split-command shape `_split_command` mirrors; the scope-out builder follows the same one-line-builder convention.

## Deferred

- **Multi-step / multi-region carve** — scope-out fires only in the single-resolved-step arm; distinct-step evidence stays `FORK_STRUCTURAL` (re-seed). A multi-step `plan-tool scope-out` is out of scope for the executor's first cut.
- **Reconcile-side routing of the scope-out recommendation** — `convergence` is read-only; wiring a reconcile/apply path that auto-runs `plan-tool scope-out` from the recommendation is a separate follow-up, not this step.
- **`--apply`/`-y` in the printed line** — the recommendation prints the recommend-only form so the operator previews before committing; auto-emitting the mutating form would undercut the mutation-gated invariant.
- **Consolidating `_split_command` / `_reseed_command` / `_scope_out_command` into one shared command-builder** — a behavior-preserving refactor `detail` cannot mint; route to reconcile (the same standing consolidation noted for the repo's three renumber/split-command builders).
