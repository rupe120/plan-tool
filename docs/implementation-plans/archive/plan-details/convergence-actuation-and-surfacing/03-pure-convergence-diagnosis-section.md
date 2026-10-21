> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add a pure convergence-diagnosis section renderer to `completeness_report.py`, gated on a spinning verdict

## Summary

Add a pure function to `plan_tool/completeness_report.py` that renders the convergence diagnosis as a markdown section for the completeness report, emitting output only when the loop is *spinning* and returning `""` for every other verdict. The renderer takes an already-computed `ConvergenceDiagnosis` (from `plan_tool/convergence_diagnosis.py`) — it does no disk I/O, spawns no Claude, and reuses the existing `render_diagnosis` block so the fork/remedy prose stays single-sourced. It also threads an optional `convergence_diagnosis` parameter into `build_report_md` (default `None`) that places the rendered section near the top of the report; the default keeps the report exactly the same as before. The observable result on green: given a spinning diagnosis the report gains a visible "loop is spinning" section with the remedy command, and given a converging/healthy/absent diagnosis it renders unchanged. Computing the diagnosis and counting the current run once is step 4's job (`cli/completeness_phases.py`); this step only renders whatever diagnosis it is handed.

## Table of Contents

- [Why](#why) — a silently spinning completeness loop shows no in-report signal today
- [Input](#input) — the `ConvergenceDiagnosis` contract this renderer reads
- [Files (creates vs edits)](#files-creates-vs-edits) — one module edit plus its test file
- [Implementation](#implementation) — the pure renderer, the spinning gate, and the optional `build_report_md` hook
- [Tests](#tests) — the renderer gate cases and the report-integration cases to add
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the Python-docs subset relevant to this step
- [Deferred](#deferred) — the diagnosis computation and run-counting owned by step 4

## Why

A completeness audit/apply loop can spin — re-surface the same over-packed region across runs with no shrinkage — and today the report says nothing about it. The only way to learn the loop is stuck is to run the separate `plan-tool convergence <name>` command, which most operators never think to do mid-loop. `plan_tool/convergence_diagnosis.py` already classifies a four-state verdict (`VERDICT_SPINNING` / `VERDICT_CONVERGING` / `VERDICT_INSUFFICIENT_HISTORY` / `VERDICT_NO_HISTORY`) and renders a full human-readable block via `render_diagnosis`, but nothing projects that into the completeness report. This step adds the pure renderer half of that projection: a function that turns a spinning diagnosis into a report section and stays silent on a healthy one, so step 4 can wire it into the report without any rendering logic of its own.

## Input

This step consumes one existing contract; it defines no new schema.

- **`ConvergenceDiagnosis` from `plan_tool/convergence_diagnosis.py`.** The renderer reads `diagnosis.verdict` (to gate) and passes the whole object to `render_diagnosis`. Relevant fields: `verdict` (one of the four `VERDICT_*` constants), `plan_slug`, `window`, and `series`. The renderer does not recompute or re-fork anything — `render_diagnosis` already owns the headline, per-series breakdown, spinning body, and fork remedy command (`classify_fork` → `_split_command` / `_scope_out_command` / `_reseed_command`).
- **The gate constant `VERDICT_SPINNING`** — import it by name from `convergence_diagnosis` and compare against `diagnosis.verdict`. Do not inline the `"spinning"` literal; the module comment on the `VERDICT_*` block says downstream code keys on the constants.
- **Who builds the diagnosis:** step 4 (`plan_tool/cli/completeness_phases.py:_persist_and_present_report`) owns loading the report history and calling `diagnose_convergence`, including the subtlety of counting the current run exactly once. This step assumes a correct diagnosis is handed in and only limits what it does with it (render vs stay silent).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/completeness_report.py` — add a module-top import from `plan_tool/convergence_diagnosis.py`, add the pure `render_convergence_section` function, and thread an optional `convergence_diagnosis` parameter into `build_report_md` that renders and places the section.
  - `tests/test_completeness_report.py` — add unit tests for the renderer gate (spinning vs the three non-spinning verdicts) and for the `build_report_md` integration (section present when spinning, absent by default / when not spinning).

## Implementation

**Add a pure section renderer.** Add a function — one reasonable name is `render_convergence_section(diagnosis: ConvergenceDiagnosis) -> str` — to `plan_tool/completeness_report.py`. Its whole job:

- **Gate on the spinning verdict.** Return `""` immediately unless `diagnosis.verdict == VERDICT_SPINNING`. So a converging, insufficient-history, or no-history diagnosis adds no section — a healthy loop stays quiet. This is the step's core rule.
- **Reuse `render_diagnosis`, don't reimplement it.** When spinning, call `plan_tool/convergence_diagnosis.py:render_diagnosis(diagnosis)` to get the human-readable block (headline + per-series breakdown + spinning body with the forked remedy command), and wrap it as a markdown section under a heading such as `## Convergence — the completeness audit/apply loop is spinning`. The heading names the *completeness* loop deliberately: step 4 supplies a diagnosis scoped to the completeness series (not `diagnose_convergence`'s plan-wide worst-of), so this section never overstates the completeness loop's state when only a reconcile series is spinning. This keeps the fork/trend prose single-sourced with the `plan-tool convergence` command; do not re-derive the remedy line or the severity trend here.
- **Preserve the block's formatting.** `render_diagnosis` returns plain text with indented `•`-bulleted trend lines. One clean way to keep that intact inside a markdown report is a fenced code block (```` ``` ````) around the rendered text, under the heading, with a one-line prose intro above it (e.g. "This loop is spinning — the same region keeps re-surfacing without shrinking. Consider the remedy below before continuing."). The exact wrapper is yours to choose; the constraint is that the fork remedy command and the slug from `render_diagnosis` survive into the output.
- **Bridge to one-command actuation in the wrapper intro.** `render_diagnosis`'s spinning body prints only the hand-run recipe (`plan-tool split … --into …` for `FORK_LOCALIZED`, `plan-tool scope-out …` for `FORK_SCOPE_OUT`) and — reused unchanged (out of scope to modify) — never mentions the one-command actuation Lever 1 exists to provide. The operator seeing this section in the completeness report has not run `plan-tool convergence`, so the authored wrapper prose above the fenced block must point them at `plan-tool convergence <name> --apply-split` / `--apply-scope-out` as the one-command remedy (behind the shared apply-or-recommend gate), so the report routes them to the actuation path rather than the manual one. The intro names the actuation; it does not touch the diagnostic leaf.
- **Stay pure.** No file reads/writes, no `parse_plan`, no fingerprint calls, no invoker. Everything comes from the passed-in `diagnosis`. This is why the diagnosis is an argument, not something the renderer loads.

**Thread the section into `build_report_md`.** Add an optional keyword parameter to `build_report_md` (one reasonable name is `convergence_diagnosis: Optional[ConvergenceDiagnosis] = None`). When it is not `None`, call the renderer and, if the result is non-empty, insert it into the `lines` list. The default `None` must render byte-for-byte the same report as today — this is the compatibility constraint that lets step 4 land the wiring without disturbing existing callers.

- **Placement:** put the section high in the report — after the `## Disposition summary` block (and after the `## Halt` block when present), before `## Applied this run`. A spinning loop is a "stop and reconsider the decomposition" signal, so a reader should see it before drilling into individual findings. Keep the existing blank-line spacing convention (each `## ` heading is preceded and followed by a `""` line in the `lines` list).
- **Naming caution:** if you use `from plan_tool.convergence_diagnosis import VERDICT_SPINNING, render_diagnosis` (rather than `import plan_tool.convergence_diagnosis`), the module name is never bound as a local, so a parameter named `convergence_diagnosis` does not shadow anything. If you prefer the `import module` style, pick a non-colliding parameter name.

**Constraints and gotchas that are not free to vary:**

- **Import at module top, no cycle.** Add the `convergence_diagnosis` import to the existing import block at the top of `plan_tool/completeness_report.py`. `convergence_diagnosis` imports only `convergence`, `locator`, `review`, and `review_persistence`, none of which import `completeness_report`, so this edge is acyclic. `completeness_report` is imported only by `plan_tool/cli/completeness_phases.py` and `plan_tool/cli/completeness_cmd.py`, so nothing below it gains a dependency.
- **The gate is exactly `VERDICT_SPINNING`.** The acceptance requires empty output for converging *and* both sub-threshold verdicts (`insufficient-history`, `no-history`). Do not widen the gate to "anything that isn't converging" — that would surface a section on a plan with too little history.
- **Do not compute the diagnosis here.** Loading history and calling `diagnose_convergence` — and the run-counting that step 4's risk calls out — belong to step 4. Pulling that in would break this step's purity and duplicate step 4's counting.
- **Do not add a new structural-remedy primitive.** The remedy text comes entirely from `render_diagnosis` / `classify_fork`; this renderer is a read-only projection.

**Rejected alternative:** having `build_report_md` re-implement the spinning body (severity trend + fork command) inline instead of calling `render_diagnosis`. That would fork the remedy prose between the report and the `convergence` command, so the two would drift. Reusing `render_diagnosis` is the point.

## Tests

All new cases live in `tests/test_completeness_report.py`. Construct `ConvergenceDiagnosis` (and the nested `SeriesDiagnosis` / `RegionTrend`) directly from `plan_tool/convergence_diagnosis.py` in a small local helper — these are frozen dataclasses, so a spinning fixture is a `ConvergenceDiagnosis(..., verdict=VERDICT_SPINNING, series=(...,))` with one recurring region on a resolvable step; the non-spinning fixtures set `verdict` to each of the other three constants.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add these unit tests with the implementation; every one must be green before the step is done.

- `test_convergence_section_empty_when_converging` — `render_convergence_section` returns `""` for a `VERDICT_CONVERGING` diagnosis.
- `test_convergence_section_empty_when_insufficient_history` — returns `""` for `VERDICT_INSUFFICIENT_HISTORY`.
- `test_convergence_section_empty_when_no_history` — returns `""` for `VERDICT_NO_HISTORY`.
- `test_convergence_section_renders_when_spinning` — returns a non-empty string for a `VERDICT_SPINNING` diagnosis, containing the section heading and the plan slug.
- `test_convergence_section_embeds_render_diagnosis_remedy` — the spinning output contains the fork remedy command (e.g. the `plan-tool split …` or `plan-tool scope-out …` line) proving it reuses `render_diagnosis` rather than re-deriving the remedy.
- `test_convergence_section_is_pure` — the renderer is called with an in-memory diagnosis and touches no disk (the test does no `tmp_path` I/O and the function reads only the passed object); documents that it spends no Claude and does no file I/O.
- `test_report_includes_convergence_section_when_spinning` — `build_report_md(..., convergence_diagnosis=<spinning>)` includes the convergence section, and it appears after `## Disposition summary` and before `## Applied this run`.
- `test_report_omits_convergence_section_by_default` — `build_report_md(...)` with `convergence_diagnosis` unset renders no convergence section (byte-identical to the pre-change report for the same inputs).
- `test_report_omits_convergence_section_when_not_spinning` — `build_report_md(..., convergence_diagnosis=<converging>)` renders no convergence section.

## Acceptance criteria

- `render_convergence_section(diagnosis)` returns `""` when `diagnosis.verdict` is `VERDICT_CONVERGING`, `VERDICT_INSUFFICIENT_HISTORY`, or `VERDICT_NO_HISTORY`.
- `render_convergence_section(diagnosis)` returns a non-empty markdown string when `diagnosis.verdict == VERDICT_SPINNING`, containing a `## `-level heading, the plan slug, and the fork remedy command from `render_diagnosis`.
- The rendered spinning section's wrapper intro references the one-command actuation (`plan-tool convergence <name> --apply-split` / `--apply-scope-out`), not only `render_diagnosis`'s hand-run recipe; asserted by a `tests/test_completeness_report.py` case checking the section body names the actuation flag.
- The renderer performs no disk I/O and calls no invoker — it reads only the passed-in `ConvergenceDiagnosis`.
- `build_report_md(...)` with no `convergence_diagnosis` argument renders the same report as before (no convergence section).
- `build_report_md(..., convergence_diagnosis=<spinning>)` inserts the convergence section after the `## Disposition summary` block and before `## Applied this run`.
- `build_report_md(..., convergence_diagnosis=<converging>)` inserts no convergence section.
- `plan_tool/completeness_report.py` imports from `plan_tool/convergence_diagnosis.py` at module top with no import cycle.
- All new `tests/test_completeness_report.py` cases pass.

## References

- [How to monkeypatch/mock modules and environments (pytest docs)](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — for the test hygiene around asserting the renderer stays pure (no invoker, no disk) if a spy is useful.

## Deferred

- Computing the diagnosis (loading report history, calling `diagnose_convergence`) and counting the current run exactly once — owned by step 4 (`cli/completeness_phases.py:_persist_and_present_report`); this step renders a diagnosis it is handed.
- Surfacing the convergence section in reconcile or other report-producing commands — out of scope per the plan; the in-report projection lands only in the completeness report.
- Any change to `render_diagnosis` / `classify_fork` in `convergence_diagnosis.py` — this step reuses them unchanged and adds no new remedy prose.
- The `--apply-split` actuator and its flag — Lever 1 (steps 1–2), unrelated to this renderer.
