> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Pull the shared bare/jira apply fence in `completeness_report.py` into one helper

## Summary

`suggested_next_steps` and `suggested_next_step_commands` in `plan_tool/completeness_report.py` each carry their own copy of the same three-line rule: a bare plan or a jira-grade audit withholds both conceptual gap sets from the `completeness-apply` route. This step moves that rule into one module-level helper both renderers call, so the report prose and the console command block read one definition instead of two. Nothing about what either renderer prints changes — this is a pure extraction, and the existing bare/jira tests in `tests/test_completeness_report.py` stay green untouched. On green, the literal `bare_plan or jira_grade` exists at most once in the module (the plan's `gate:` on this step), and step 2 has a single place to split the fence by axis.

## Table of Contents

- [Summary](#summary) — what the step does and what stays the same.
- [Why](#why) — the two copies of one rule, and what they cost step 2.
- [Input](#input) — the `bundle_status` and `detail_grade` contracts the fence reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches.
- [Implementation](#implementation) — the helper's shape, what stays behind in each renderer, and the sites deliberately left alone.
- [Tests](#tests) — the new helper cases plus the drift guard, and which existing tests must stay green unchanged.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the files worth reading before starting.
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step.
- [Deferred](#deferred) — same-file sites this step does not touch, and why.

## Why

The rule "a bare plan or a jira-grade audit gets no `completeness-apply` route for its conceptual gaps" is written twice in `plan_tool/completeness_report.py` — once in `suggested_next_steps` (the markdown report's prose bullets) and once in `suggested_next_step_commands` (the console `(command, description)` block). Both copies are three lines: the `unappliable` flag plus the two gap lists it zeroes out. The two renderers describe **one audit run**, so any difference between them is a reporting defect — and the module already treats that as a rule worth enforcing structurally: `_reconcile_drift_prose` and `_reconcile_drift_command` exist as a pair precisely "so the prose bullet and the console command stay one definition." The fence never got the same treatment. Step 2 changes this rule (correctness gaps keep the route on a bare plan; completeness gaps do not), and with two copies that is two edits that can disagree. One helper makes it one edit.

## Input

- **`bundle_status`** — a `plan_tool/review.py:DetailBundleStatus` (or `None`). The fence reads only its `is_bare` property, which is `True` when at least one step has no detail file on disk. Both renderers read it defensively via `getattr(bundle_status, "is_bare", False)` because the parameter defaults to `None` and the suites pass a `SimpleNamespace`. Keep that defensive read — dropping it turns a `None` bundle status into an `AttributeError` on a path that currently renders fine.
- **`detail_grade`** — a grade string compared against `GRADE_JIRA` from `plan_tool/jira_grade.py` (already imported in this module alongside `GRADE_RUN`). The renderers' default is `GRADE_RUN`.
- **`correctness` / `advisory_conceptual`** — the two conceptual finding sets, both `list[Recommendation]`. Note `correctness` defaults to an empty **tuple** `()`, not a list, so whatever the helper returns must tolerate a tuple input.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/completeness_report.py` — add one module-level helper holding the fence; replace the duplicated three-line blocks in `suggested_next_steps` and `suggested_next_step_commands` with a call to it; trim the now-duplicated fence explanation out of both docstrings/comments so the rule is stated once.
  - `tests/test_completeness_report.py` — add direct cases for the new helper plus a drift guard asserting the two renderers agree; leave the existing bare/jira renderer tests unchanged.

## Implementation

**The foundational logic is one predicate: which conceptual gap sets can name `completeness-apply` this run.** It lives at exactly two sites today — the `unappliable = bare_plan or jira_grade` block in `suggested_next_steps` and the identical block in `suggested_next_step_commands`. Both are followed by the same two derived lists (`actionable_advisory`, `actionable_correctness`). Fold all three lines, not just the boolean: the boolean alone leaves the two derivations duplicated, and those are what step 2 actually changes.

**Recommended shape — one keyword-only helper returning the two lists.** Something like:

```
def _actionable_conceptual_gaps(*, correctness, advisory_conceptual,
                                bundle_status, detail_grade) -> tuple[list, list]
```

returning `(actionable_correctness, actionable_advisory)`. Points that matter:

- **The helper owns both flag derivations** — the `getattr(bundle_status, "is_bare", False)` read and the `detail_grade == GRADE_JIRA` compare. Passing raw inputs rather than pre-computed booleans means a call site cannot hand it a stale flag, and it puts "what counts as bare for the apply fence" in one place for step 2 to change. *One alternative if you prefer it:* take `bare_plan` / `jira_grade` booleans instead — the renderers already compute both for other reasons, so the call gets shorter. Either satisfies the gate; the raw-input version is the one this file recommends.
- **Return order is part of the contract** — correctness first, matching the order both renderers already present them in (correctness leads, completeness follows). Pin it with a test rather than relying on the reader. A small frozen record with named fields is fine if you'd rather not depend on tuple order; it's more machinery than a low-complexity refactor needs, so it's latitude, not a requirement.
- **Normalize both returns to `list(...)`.** Today `actionable_correctness` is copied and `actionable_advisory` is passed through by reference — an inconsistency with no consumer, since both are only tested for truthiness and length. Copying both is behavior-preserving here; check that assumption holds before relying on it.

**What stays behind in each renderer.** Do not fold the other uses of these two flags — they are different jobs that happen to read the same inputs, and pulling them in would change behavior:

- `suggested_next_steps` keeps `bare_plan` for `bare_detail_diagnostic_count` and the `DETAIL_LEVEL_DIAGNOSTIC_SOURCES` filter, and keeps `jira_grade` for the hand-fix bullet and the `open_findings` gate.
- `suggested_next_step_commands` keeps `bare_plan` for the same diagnostic filter, and keeps `jira_grade` for the `files-coherence`, `detail-coverage`, and `open_findings` gates.

After the extraction both renderers still declare their own `bare_plan` / `jira_grade` locals for those uses; the literal `bare_plan or jira_grade` disappears from them entirely. The step's `gate:` is `-le 1`, so zero occurrences passes.

**Sweep the prose, not just the code.** Both renderer docstrings and the inline comments restate the fence in words ("Both are withheld in a bare-plan audit", the jira-grade paragraph about withheld apply bullets). Leaving two prose copies behind re-creates the drift the extraction removes. Move the rationale onto the helper's docstring and have each renderer point at it in a line or two.

**Sites in this same file that read the same two flags but are not this fence** — read them so you don't fold them by reflex, and leave all three alone:

- `build_report_md`'s conceptual-completeness section picks its intro prose from `bare_plan` / `jira_grade` (the bare-plan "informational for now" paragraph vs. `WHY['advisory-conceptual']` vs. `_HAND_FIX_INTRO`), and gates the per-finding `Address: plan-tool completeness-apply --anchor` sub-bullet on `not bare_plan and not jira_grade`. Same inputs, different output — section prose, not the next-step list.
- `build_report_md`'s conceptual-**correctness** section renders `CORRECTNESS_INTRO` (which names `plan-tool completeness-apply`) on any non-jira grade, bare or not. So the report body already names the apply verb for correctness gaps on a bare plan while the next-steps list withholds it. That inconsistency is the gap step 2 closes — do not "fix" it here, and do not extend the new helper to cover it.
- `diagnostic_remedies` reads `jira_grade` alone for its files-coherence remedy; it has no bare-plan arm and is not part of this fence.

**Callers outside this module need no change.** `plan_tool/cli/completeness_phases.py` calls `suggested_next_step_commands` (and `build_report_md` reaches `suggested_next_steps`) with `bundle_status=` and `detail_grade=` keywords; the helper is private to `completeness_report.py` and neither signature moves. Both renderers' public signatures must stay exactly as they are.

## Tests

All cases live in `tests/test_completeness_report.py`. The file already has `_steps(**kw)` and `_cmds(**kw)` builders for the two renderers and a `_rec(...)` factory — reuse them rather than adding new fixtures.

### Tests for this step

New cases (approx. 5):

- `test_actionable_conceptual_gaps_detailed_run_grade_returns_both` — a non-bare `bundle_status` at run grade returns both finding sets intact, correctness first.
- `test_actionable_conceptual_gaps_bare_plan_withholds_both` — `SimpleNamespace(is_bare=True)` returns two empty lists.
- `test_actionable_conceptual_gaps_jira_grade_withholds_both` — `detail_grade=GRADE_JIRA` returns two empty lists on an otherwise detailed plan.
- `test_actionable_conceptual_gaps_missing_bundle_status_is_not_bare` — `bundle_status=None` behaves as non-bare, pinning the defensive `getattr` default.
- `test_next_steps_and_commands_share_one_apply_fence` — the drift guard, and the case that operationalizes this step's intent: for each of bare / jira-grade / detailed / `bundle_status=None`, feeding the same correctness + completeness findings to both renderers yields the same answer to "does this run name `completeness-apply`". Assert agreement between the two, not a hard-coded expectation per case, so step 2's change keeps the guard meaningful.

Existing cases that must stay green **with no edits** — they are the behavior-preserving proof for this refactor:

- `test_next_steps_bare_plan_suppresses_conceptual_apply_action`
- `test_next_step_commands_bare_plan_suppresses_conceptual_apply_action`
- `test_next_step_commands_correctness_withheld_in_bare_plan`
- `test_next_step_commands_detailed_plan_keeps_detail_level_actions`
- `test_next_step_commands_count_correctness_gaps`
- `test_next_step_commands_are_command_description_tuples`
- `test_suggested_next_steps_grade_jira_withholds_apply_bullets`
- `test_suggested_next_step_commands_grade_jira_withholds_apply`

If any of those needs an edit to pass, the extraction changed behavior — treat it as a defect in the refactor, not as a test to update.

**Green-before-done gate:** every case above — the five new ones and the eight existing ones — must pass before this step is finished. Run `uv run pytest tests/test_completeness_report.py -q` for the fast loop, then `uv run pytest -m "not integration" tests/ -q` before calling it done, since `plan_tool/cli/completeness_phases.py` consumes one of these renderers.

## Acceptance criteria

- `grep -c 'bare_plan or jira_grade' plan_tool/completeness_report.py` returns 0 or 1 (the step's declared `gate:`).
- Exactly one module-level helper in `plan_tool/completeness_report.py` computes the conceptual apply fence, and both `suggested_next_steps` and `suggested_next_step_commands` call it — neither derives `actionable_correctness` or `actionable_advisory` on its own.
- The public signatures of `suggested_next_steps` and `suggested_next_step_commands` are unchanged (same parameter names, order, and defaults).
- The eight existing bare/jira renderer tests listed above pass with zero diff to their source.
- `uv run pytest tests/test_completeness_report.py -q` is green, and `uv run pytest tests/test_duplication.py -q` is green with no new `ALLOWED_DUPLICATE_GROUPS` entry.
- `build_report_md` output is unchanged: no diff to the conceptual-correctness section, the conceptual-completeness section's intro selection, or the per-finding `Address:` sub-bullet gate.

## References

- [`plan_tool/completeness_report.py`](../../../plan_tool/completeness_report.py) — the whole step lands here; read `suggested_next_steps`, `suggested_next_step_commands`, and the `_reconcile_drift_prose` / `_reconcile_drift_command` pair, which is the in-repo precedent for a shared prose/command definition.
- [`plan_tool/review.py`](../../../plan_tool/review.py) — `DetailBundleStatus` and its `is_bare` property, the binary fact the fence reads.
- [`plan_tool/cli/completeness_phases.py`](../../../plan_tool/cli/completeness_phases.py) — the console caller of `suggested_next_step_commands`; confirms the keyword call shape this step must not disturb.
- [`tests/test_completeness_report.py`](../../../tests/test_completeness_report.py) — the `_steps` / `_cmds` / `_rec` builders and the existing bare/jira cases that serve as this refactor's regression net.

## Applicable guardrails

- **The plan's `## Out of scope`, per-finding coverage routing refusal** — the helper's inputs stay at plan level (`bundle_status`, `detail_grade`). It must not take a `Recommendation` and decide per finding, and it must not read `rec.step_id` or an anchor prefix.
- **The plan's `## Out of scope`, "no new gate, exit-code flip, blocking severity, or refusal-to-advance"** — this step adds a rendering helper only. Nothing it returns may reach a severity check, `has_blocking_findings`, or an exit code.
- **The plan's `## Out of scope`, jira-grade behavior** — the jira-grade arm of the fence moves into the helper unchanged. Do not adjust what jira grade withholds while relocating it.
- **The plan's `## Architecture`, decision 1 (split by axis at plan level)** — this step performs no split. It only creates the single place where step 2 will make one.
- **The plan's `## Out of scope`, `DATA_CONTRACT.md` left unchanged** — the helper is a private rendering detail; it persists nothing and adds no field to any saved artifact.

## Deferred

- **Splitting the fence by axis** — step 2 owns it. This step only makes the fence a single definition.
- **The `BLOCKED` next-step remedy in `_blocked_next_step`** — step 3 owns it; untouched here even though it sits between the two renderers in the same file.
- **`build_report_md`'s conceptual-completeness intro selection and its `Address:` sub-bullet gate** — same two flags, different job (section prose, not the next-step list). Left alone; step 2 decides whether the report body's apply-verb wording follows the axis split.
- **The bare-plan inconsistency in the correctness section** — `CORRECTNESS_INTRO` already names `plan-tool completeness-apply` on a bare plan while the next-steps list withholds it. Evidence for step 2, not work for step 1.
- **Consolidating the `getattr(bundle_status, "is_bare", False)` read across all three sites in this module** — a wider cleanup than this fence, touching `build_report_md`'s unrelated prose selection. If it still looks worth doing after step 2, file it in `BACKLOG.md` rather than widening this step.
