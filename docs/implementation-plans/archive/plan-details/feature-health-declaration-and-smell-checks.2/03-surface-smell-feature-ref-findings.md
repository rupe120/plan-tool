> **Auto-archived**: this plan was swept on 2026-06-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Surface smell/feature-ref findings through the completeness-audit post-loop report, never the apply loop

## Summary

Adds a `smell_recs` bucket to `plan_tool/cli/completeness_phases.py:_DeterministicReport` and renders it across all three completeness-audit output surfaces: the grouped console report (`_render_grouped_report`), the `--json` payload (`_render_completeness_json`), and the persisted markdown report (`plan_tool/completeness_report.py:build_report_md`). The smell findings come from step 2's `collect_smell_findings`, called inside `_run_deterministic_checks` (the post-loop battery) — **never** added to `plan_tool/review.py:collect_deterministic_findings`, which is the only feed into the `--iterate` apply loop. The key design decision: smells are surfaced but structurally excluded from both the apply loop (not in `collect_deterministic_findings`) and the blocking gate (never passed to `_completeness_has_blocking_findings`), so they can be read and acted on by a human but can never auto-apply or flip the exit code. On green, a plan carrying a suppression-shape / self-referential / feature-ref smell shows a `### Smells (advisory)` section in every surface, the `--iterate` loop never dispatches it to `apply_finding`, and `has_blocking_findings` / the process rc stay unaffected.

## Table of Contents

- [Why](#why) — what's missing today and why smells need their own surface.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two source files and their tests.
- [Implementation](#implementation) — the new field, the wiring point, the three render surfaces, and the two deliberate omissions.
- [Tests](#tests) — the cases to add with the implementation, plus the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — the dataclass-default ordering rule relevant here.
- [Deferred](#deferred) — surfaces and behaviors left for other steps.

## Why

Step 2 builds the advisory smell layer — `validate_feature_refs`, `detect_suppression_shape`, `detect_self_referential_features`, fanned out by a new `collect_smell_findings(plan, repo_root, *, plan_name)` collector in `plan_tool/review.py`. Step 2 deliberately leaves that collector **unwired**: it is not in `collect_deterministic_findings`, so nothing surfaces it yet. This step gives it a home in the completeness-audit report. The audit is the right surface because it is the plan-health command an operator already runs, and its report layer already renders several advisory finding classes (conceptual-completeness gaps, files-coherence nits) that are reported-but-never-auto-applied. Smells are exactly that shape: an `info`-severity heads-up about a brittle plan structure that a prose-editing `apply_finding` pass cannot fix. The whole point is to surface them **without** letting them enter the apply loop or the blocking gate — both of which would mis-handle a structural smell (the loop would dispatch a finding `apply_finding` can only return NOT-APPLICABLE for; the gate would let an advisory note flip a CI exit code).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` — add `smell_recs` (last field, default empty) to `_DeterministicReport`; add a keyword-only `plan_name` param to `_run_deterministic_checks` and call `collect_smell_findings` there; render `### Smells (advisory)` in `_render_grouped_report` and add `det.smell_recs` to its `has_any` predicate; add a `smells` group to `_render_completeness_json`; thread `smell_recs` through `_persist_and_present_report` into `build_report_md`.
  - `plan_tool/completeness_report.py` — add an optional `smells` param (default `None`) to `build_report_md` and render a `## Smells (advisory)` section when non-empty.
  - `plan_tool/cli/completeness_cmd.py` — update the one `_run_deterministic_checks(...)` call to pass `plan_name=args.name`, and the `_persist_and_present_report(...)` call to pass `smell_recs=det.smell_recs`. (This file is in scope as a call-site edit, not a new behavior owner — note the addition explicitly.)
  - `tests/test_completeness_report.py` — `build_report_md` smell-section tests.
  - `tests/cli/test_completeness_cmd.py` — `_run_deterministic_checks` / `_render_grouped_report` / `_render_completeness_json` smell tests; the `_empty_det()` helper stays valid.

## Implementation

### `plan_tool/cli/completeness_phases.py`

**Add `smell_recs` to `_DeterministicReport`.**
- `_DeterministicReport` is a `@dataclass(frozen=True)` whose seven existing fields have no defaults. Add `smell_recs: list = field(default_factory=list)` as the **last** field so positional and partial constructors stay valid — the `_empty_det()` test helper builds it by keyword and keeps working untouched.
- Update the docstring to name eight issue lists, and note smells are the one bucket the blocking-gate check never reads.

**Add `plan_name` to `_run_deterministic_checks` and call the collector.**
- Change the signature to `_run_deterministic_checks(plan, path, ctx, *, plan_name: str, quiet: bool)`. `plan_name` is needed so `collect_smell_findings` mints stable ids via `review._make_rec_id` (same `plan_name=` contract `collect_deterministic_findings` already uses).
- Inside the function, after the seven existing detectors, add `collect_smell_findings` to the body-local `from plan_tool.review import (...)` block and call it: `smell_recs = collect_smell_findings(plan, ctx.repo_root, plan_name=plan_name)`. The body-local import is correct for the same reason the others are — none of these detectors is monkeypatched in the suites except via the domain module (`plan_tool.review`), and a body-local re-import resolves to that patch. There is **no** import cycle to break here; do not cite cycle-breaking.
- Pass `smell_recs=smell_recs` into the returned `_DeterministicReport`.
- Leave the `quiet`-gated deterministic-count tail counting the seven well-formedness lists only; smells are advisory and need not inflate that count (state this as a deliberate choice, not an oversight).

**Render `### Smells (advisory)` in `_render_grouped_report`.**
- No signature change — read `det.smell_recs`. Add the section after the `### Conceptual completeness` block and before the `has_any` computation:
  - Heading `### Smells (advisory)`, a one-line italic blurb (advisory plan-structure heuristics; never auto-applied), then one bullet per rec rendered with the full body: `- {rec.severity.upper()}{tag}: {body}` where `tag = f" \`[{rec.anchor}]\`" if rec.anchor else ""` and `body = (rec.body or rec.title).strip()` — mirroring the existing conceptual/correctness bullet form.
- **Add `det.smell_recs` to the `has_any` predicate.** Without this, a smell-only plan would print both the `### Smells (advisory)` section and the `_(no completeness issues detected)_` line — a self-contradiction with no test to catch it. This is the single most important non-obvious edit.

**Add a `smells` group to `_render_completeness_json`.**
- In `out["checks"]`, add a `"smells"` list (place it after `"plan_audit"`), one entry per `det.smell_recs` rec: `{"severity": r.severity, "source": r.source, "id": r.id, "title": r.title, "body": r.body}`. Use `source` (not `axis`) because smells carry the step-2 source tokens `feature-ref` / `suppression-shape` / `self-referential`, not the correctness/completeness axis.
- Do **not** touch the `has_blocking` computation — smells are not an input to `_completeness_has_blocking_findings`.

**Thread `smell_recs` through `_persist_and_present_report`.**
- Add a keyword param `smell_recs` (default `()` / empty list) to `_persist_and_present_report` and pass it into `build_report_md(..., smells=smell_recs)`. The grouped report embedded in the persisted file already carries the smells via `grouped_md`; the dedicated `## Smells (advisory)` section in `build_report_md` is the curated top-level surface, so both appear in the saved report.

### `plan_tool/completeness_report.py`

**Add the optional `smells` param to `build_report_md`.**
- Add `smells: Optional[list[Recommendation]] = None` to the keyword-only params. The `None` default keeps every existing call and the byte-output suite in `tests/test_completeness_report.py` green — callers that don't track smells get the same output as today.
- Render a `## Smells (advisory)` section (only when `smells` is non-empty), placed after the `## {_HEADINGS['advisory-conceptual']}` block. Render each rec inline with the existing `_fmt_finding_line(rec)` helper (it already emits the full body + `[anchor]`), preceded by a one-line rationale stating these are advisory plan-structure heuristics that are reported but never auto-applied.
- Render this as a plain inline section — do **not** add a `WHY` / `_HEADINGS` dict entry. Smells are not a *deferred-disposition* bucket (the `deferred_kind` gate ladder doesn't classify them); they're a separate advisory class, like the `## Applied this run` section that is also rendered inline.

### `plan_tool/cli/completeness_cmd.py`

**Update the two call sites.** Both are inside `cmd_completeness`, which has `det` and `args.name` in scope:
- The `_run_deterministic_checks(plan, path, ctx, quiet=budget.enabled)` call → add `plan_name=args.name`.
- The `_persist_and_present_report(...)` call → add `smell_recs=det.smell_recs`.

**Leave the apply loop untouched.** The `--iterate` convergence loop (`_run_iterate_convergence_loop`) feeds `apply_finding` only through `_collect_det_findings` → `review.collect_deterministic_findings` (and `_open_findings_now`, which unions that with conceptual-correctness recs). Since `collect_smell_findings` is **not** in `collect_deterministic_findings`, smells never reach the loop. This omission is the key guarantee that a smell is never dispatched to `apply_finding` — keep `collect_deterministic_findings` unchanged.

### Two deliberate omissions (the guarantees)

- **Smells never enter the apply loop** — they live only in `_run_deterministic_checks` (post-loop battery), never in `review.collect_deterministic_findings` (the broadcast fan-out wired into `_collect_det_findings`).
- **Smells never block / flip rc** — `det.smell_recs` is never passed to `_completeness_has_blocking_findings`. This is severity-independent structural exclusion; the `info` severity is only a secondary guarantee. A smell can't flip `has_blocking_findings` or the exit code even under `--fail-on-findings`, regardless of any future severity bump.

## Tests

### Test-creation order (feature step)

This is a **feature** step — new behavior. Write these unit tests with the implementation; every one must be green before the step is done.

**`tests/cli/test_completeness_cmd.py`** (patch `plan_tool.review.collect_smell_findings` on the domain module — the body-local import in `_run_deterministic_checks` resolves to the patch):

- **Update the two existing `TestRunDeterministicChecks` call sites** — `test_clean_plan_yields_empty_report` and `test_returns_deterministic_report_type` call `_run_deterministic_checks(plan, path, ctx, quiet=True)`; add `plan_name=` to both so they keep passing once `plan_name` becomes a required keyword-only param.
- `test_run_deterministic_checks_threads_plan_name_and_collects_smells` — with `collect_smell_findings` stubbed to return one rec, `_run_deterministic_checks(..., plan_name="p", quiet=True)` returns a report whose `smell_recs` holds that rec.
- `test_run_deterministic_checks_no_smells_yields_empty_bucket` — stub returns `[]`; `report.smell_recs == []`.
- `test_deterministic_report_constructs_without_smell_recs` — `_DeterministicReport(...)` with the seven existing fields and no `smell_recs` builds fine (default empty), proving `_empty_det()` stays valid.
- `test_grouped_report_renders_smells_section` — `det` with a smell rec → `### Smells (advisory)` and the rec body appear in `_render_grouped_report` output.
- `test_grouped_report_omits_smells_section_when_none` — empty `smell_recs` → no `### Smells (advisory)` heading.
- `test_smell_only_plan_not_reported_as_no_issues` — `det` with only `smell_recs` populated (all seven well-formedness lists empty) → output contains the smells section and does **not** contain `_(no completeness issues detected)_`. (Pins the `has_any` edit.)
- `test_json_payload_includes_smells_group` — `_render_completeness_json` with a smell-bearing `det` → `data["checks"]["smells"]` lists the rec with `severity`/`source`/`id`/`title`/`body`; empty list when none.
- `test_smells_do_not_affect_has_blocking` — a smell-only `det` driven through `_render_completeness_json(..., has_blocking=False)` keeps `has_blocking_findings` false (smells are not a blocking input).

**`tests/test_completeness_report.py`**:

- `test_report_renders_smells_section_when_present` — `build_report_md(..., smells=[smell_rec])` contains `## Smells (advisory)` and the rec body.
- `test_report_omits_smells_section_when_none` — `build_report_md(...)` with `smells` defaulted to `None` produces no `## Smells (advisory)` heading (existing byte-output tests stay green).

## Acceptance criteria

- `_DeterministicReport` has a `smell_recs` field, declared last, defaulting to an empty list; constructing it with only the seven prior fields succeeds.
- `_run_deterministic_checks(plan, path, ctx, *, plan_name, quiet)` calls `collect_smell_findings(plan, ctx.repo_root, plan_name=plan_name)` and returns its result in `report.smell_recs`.
- `_render_grouped_report` emits a `### Smells (advisory)` section iff `det.smell_recs` is non-empty, and `det.smell_recs` is part of the `has_any` predicate (a smell-only plan never prints `_(no completeness issues detected)_`).
- `_render_completeness_json` output has a `checks.smells` list with one `{severity, source, id, title, body}` entry per smell rec.
- `build_report_md(..., smells=[...])` renders a `## Smells (advisory)` section; `build_report_md(...)` with `smells=None` renders identically to today.
- `plan_tool/review.py:collect_deterministic_findings` is unchanged, so the `--iterate` loop never dispatches a smell to `apply_finding`.
- `_completeness_has_blocking_findings` takes no smell argument; a smell-only plan reports `has_blocking_findings == False` and exits 0 even under `--fail-on-findings`.
- All new tests above are green.

## References

- [Data Classes — `field()` and default ordering (Python docs)](https://docs.python.org/3/library/dataclasses.html#dataclasses.field) — confirms a field with a default must follow fields without one, why `smell_recs` is declared last, and how `field(default_factory=list)` gives each instance its own list.

## Deferred

- **`validate` surfacing of smells** — step 4 wires `collect_smell_findings` into `plan_tool/cli/inspect.py:cmd_validate`; out of scope here.
- **`PLAN_FORMAT.md` documentation of the smell checks** — step 5 documents the advisory layer and the `### Smells (advisory)` / `checks.smells` labels; not this step.
- **A `console_summary` smell count line** — the concise terminal summary is not extended; smells appear in the grouped report, the `--json` payload, and the persisted report only. Add a count line later if operators ask for it.
- **A dedicated `WHY` / `_HEADINGS` disposition entry for smells** — smells are rendered inline (like `## Applied this run`), not routed through the `deferred_kind` ladder; promoting them to a keyed disposition is unnecessary unless they ever need per-bucket triage rationale.
