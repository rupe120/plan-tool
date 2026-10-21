> **Auto-archived**: this plan was swept on 2026-06-01 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add a severity-count banner under the report header in `assemble_report`

## Summary

- Add a one-line severity histogram (e.g. `Findings: 1 critical · 2 high · 3 medium · 4 info`) directly under the `Metadata` / `Repo root` header in `assemble_report` (`plan_tool/review.py`), tallying every finding the report surfaces by severity level.
- **Load-bearing decision:** derive the tally from the already-built `list[Recommendation]` rather than re-classifying primitives inside `assemble_report`. Each `Recommendation.severity` is already set from the existing constants (`_FILE_CHECK_MISSING_PARENT_SEV`, `_HEURISTIC_HIT_SEV`, `_DEP_*_SEV`, `_PATH_STYLE_SEV`, the completeness `_*_SEV` set, and `_CLAUDE_SEVERITY_MAP`), so counting `rec.severity` reuses those constants transitively and guarantees the banner matches the per-step / walk findings exactly — no parallel severity scheme, no second copy of the "does this finding exist and at what severity" logic.
- Primary files: `plan_tool/review.py` (new `recommendations=` param on `assemble_report`, a `_render_severity_banner` helper, a display-order tuple, and a reorder in `review_plan_full` so recommendations are computed before the report) and `tests/test_review.py`.
- **Observable result on green:** an interactive or headless `plan-tool review` prints a `Findings:` line summarizing severity counts under the repo-root header; runs with no findings print `Findings: none`; existing direct `assemble_report` callers that pass no recommendations are byte-identical (no banner).

## Table of Contents

- [Why](#why) — the missing at-a-glance triage summary
- [Files (creates vs edits)](#files-creates-vs-edits) — the two edited files and their changes
- [Implementation](#implementation) — the banner helper, the new param, and the `review_plan_full` reorder
- [Tests](#tests) — banner presence/absence, severity tally, ordering, position, empty case
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — Counter / pytest docs relevant to this step
- [Deferred](#deferred) — per-source breakdown and dry-run banner, both out of scope

## Why

- `assemble_report` renders the header (`## Plan Review`, `Metadata:`, `Repo root:`), then the Claude section, then per-step status, then completeness, then suggested actions. A reader must scan the whole report to gauge how bad the plan is — there is no top-of-report count answering "how many critical/high findings am I about to read?".
- The severity per finding is already computed once, in the `_*_recommendation` builders feeding `extract_recommendations`. A banner that re-derives severity from `file_checks` / `dep_issues` / the completeness lists would duplicate that classification in a second sibling and drift from it (the report-assembly chain is explicitly a mirror pair — see the accumulated lessons on `assemble_report` ↔ `extract_recommendations`). Counting the existing `Recommendation` objects is the single-source approach.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py`
    - Add `from collections import Counter` (or `import collections`) to the module imports — `Counter` is not imported at HEAD and `_render_severity_banner` requires it.
    - Add a module-level display-order tuple (e.g. `_SEVERITY_BANNER_ORDER`) next to the severity constants block (near `_FILE_CHECK_MISSING_PARENT_SEV` … `_PATH_STYLE_SEV`).
    - Add `_render_severity_banner(recs)` returning the single banner line.
    - Add keyword-only `recommendations: Optional[Sequence[Recommendation]] = None` to `assemble_report` and emit the banner under the `Repo root:` line when it is provided.
    - In `review_plan_full`, move the `extract_recommendations(...)` call above the `assemble_report(...)` call and pass `recommendations=recommendations` into `assemble_report`.
  - `tests/test_review.py` — add banner cases to `TestAssembleReport` plus one `review_plan_full` integration assertion (`Recommendation` and `extract_recommendations` are already imported module-level).

## Implementation

### `plan_tool/review.py` — display-order constant

- **Add `_SEVERITY_BANNER_ORDER = ("critical", "high", "medium", "nit", "info")`** beside the severity-constant block. This is display ordering of the *existing* severity levels (the values the `_*_SEV` constants and `_CLAUDE_SEVERITY_MAP` already produce), not a new severity scheme. Highest-urgency first, mirroring the report's intent that critical/high read before advisory levels.

### `plan_tool/review.py` — `_render_severity_banner`

- **Signature:** `_render_severity_banner(recs: Sequence[Recommendation]) -> str`.
- **Tally** with `collections.Counter(r.severity for r in recs)`. Counting `rec.severity` directly reuses the constants — every builder (`_file_check_recommendation`, `_heuristic_recommendation`, `_dep_recommendation`, `_path_style_recommendation`, the `_*_completeness`/`_lessons`/`_detail_*` builders, and `_claude_recommendations` via `_CLAUDE_SEVERITY_MAP`) already stamps one of the canonical level strings.
- **Render** one line: iterate `_SEVERITY_BANNER_ORDER`, emit `"{count} {level}"` only for non-zero counts, join with `" · "`, prefix `"Findings: "`. Drop zero-count levels so the line stays short. When `recs` is empty (or every level is zero), return `"Findings: none"`.
- **Severities outside the order tuple** (defensive — none expected) sort after the known levels in stable insertion order so an unknown value still surfaces rather than being silently dropped.

### `plan_tool/review.py` — `assemble_report`

- **Add keyword-only param** `recommendations: Optional[Sequence[Recommendation]] = None` to the existing `*`-separated signature (place it alongside the other optional structured inputs).
- **Emit the banner** immediately after `lines.append(f"Repo root: \`{repo_root}\`")` and before the existing blank-line `lines.append("")` that precedes the `### Claude's semantic review` header. Guard on `if recommendations is not None:` so the banner is part of the header block, not a separate section.
- **Default `None` keeps every current direct caller byte-identical** — the nine `assemble_report` calls in `tests/test_review.py` pass no recommendations and therefore render no banner. The default-preserves-current-output convention follows the optional-param style already used for `assemble_report`'s structured inputs (the sibling step 2 `include_suggested_actions` param is a forward reference, not yet present at HEAD).
- **Do not re-scope by `step_filter` inside the banner** — `review_plan_full` already passes `step_filter` to `extract_recommendations`, so a step-filtered run hands `assemble_report` an already-scoped list and the banner counts only that step's findings for free.

### `plan_tool/review.py` — `review_plan_full`

- **Reorder:** move the `recommendations = extract_recommendations(...)` block to *before* the `report = assemble_report(...)` block, then pass `recommendations=recommendations` into `assemble_report`. Both are pure functions over the same primitives, so the swap is behavior-preserving; `extract_recommendations` does not consume `report`.
- **The `claude_stdout=claude_stdout_for_recs` argument is already in scope** at the current `extract_recommendations` call site, so the move needs no new data plumbing.
- **No change to `review_plan`** (the str-returning wrapper) or to the `if dry_run:` early return — the banner lives entirely inside `review_plan_full`'s post-checks path, so the back-compat wrapper inherits it automatically and the dry-run prompt is unaffected.
- **`save_review` coupling:** the saved artifact carries `result.report` verbatim, so the banner flows into saved reviews with no extra work (intended — printed and saved markdown stay identical).

## Tests

`tests/test_review.py`, in `TestAssembleReport` unless noted. Build recommendations via `extract_recommendations(...)` over the existing `_write_review_fixture` plan so the tally exercises real builder severities; `Recommendation` is already imported module-level for the hand-built cases.

- `test_severity_banner_absent_without_recommendations` — `assemble_report` called without `recommendations=` produces no `Findings:` line (back-compat guard).
- `test_severity_banner_tallies_real_findings` — pass `extract_recommendations(...)` output for the fixture (step-3 MISSING_PARENT `high` + step-4 heuristic `info`); assert the banner shows `1 high` and `1 info` and omits zero levels.
- `test_severity_banner_orders_high_before_info` — with mixed hand-built `Recommendation` severities, assert `critical`/`high` appear left of `medium`/`nit`/`info` in the line.
- `test_severity_banner_none_when_empty` — empty recommendations list yields `Findings: none`.
- `test_severity_banner_position_under_repo_root` — banner line appears after `Repo root:` and before `### Claude's semantic review`.
- `test_severity_banner_respects_step_filter` — `review_plan_full(..., step_id=4, invoker=None)` banner counts only step 4's finding (scoped via the recommendations passed in).
- `test_render_severity_banner_unit` — direct `_render_severity_banner` call on a small hand-built list asserts the exact `Findings: …` string for a known severity mix.

## Acceptance criteria

- `assemble_report(..., recommendations=<list>)` output contains a `Findings: …` line between the `Repo root:` line and the `### Claude's semantic review` header.
- `assemble_report(...)` called with no `recommendations=` argument contains no `Findings:` line; the existing `TestAssembleReport` substring assertions still pass.
- `_render_severity_banner([])` returns `"Findings: none"`.
- Banner severity labels are exactly the canonical level strings (`critical`/`high`/`medium`/`nit`/`info`) produced by the existing severity constants — no new level names introduced.
- For the `_write_review_fixture` plan with `invoker=None`, `review_plan_full(...).report` banner counts equal `len(result.recommendations)` grouped by `severity`.
- `pytest tests/test_review.py` passes.

## References

- [collections.Counter — Container datatypes (Python docs)](https://docs.python.org/3/library/collections.html#collections.Counter) — Reference for the severity tally; `Counter(...)` plus ordered iteration over `_SEVERITY_BANNER_ORDER` gives a stable, zero-suppressing histogram.
- [pytest — Full documentation](https://docs.pytest.org/en/stable/) — Test framework used in `tests/test_review.py` for the new banner cases.
- [How to use temporary directories and files in tests (pytest tmp_path)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — `tmp_path` fixture used by the existing fixtures (`_write_review_fixture`) the banner tests reuse.

## Deferred

- **Per-source breakdown** (e.g. separate counts for semantic vs file-check vs completeness) — out of scope; the step asks for a single severity histogram aggregated across all sources. Revisit only if a reviewer asks to attribute counts to producers.
- **Banner on the dry-run path** — `review_plan_full` returns the rendered prompt before any checks run, so there are no recommendations to tally; no banner there by design.
- **Re-deriving severities inside `assemble_report` from primitives** — explicitly rejected to avoid a second copy of the existence-and-severity logic that would drift from `extract_recommendations` (the mirror-pair lesson).
- **Threading a `recommendations` param through `review_plan`** — unnecessary; the banner is computed inside `review_plan_full`, which the wrapper already delegates to.
