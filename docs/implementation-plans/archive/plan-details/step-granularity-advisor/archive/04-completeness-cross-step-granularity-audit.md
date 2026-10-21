> **Auto-archived**: this plan was swept on 2026-06-20 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add a cross-step granularity audit to completeness via `assess_granularity(stage="completeness")`, surfaced in the advisory smell bucket

## Summary

Wire the step-1 advisor leaf into `completeness-audit` so the deterministic battery reports cross-step granularity smells (a step that looks too big, two fragmented steps that should merge). In `plan_tool/cli/completeness_phases.py`, `_run_deterministic_checks` calls `assess_granularity(plan, stage="completeness", evidence=GranularityEvidence(), invoker=None)` — no Claude — and folds the resulting `granularity-split` / `granularity-merge` recs into the `smell_recs` bucket it already returns. The key design decision: ride the existing advisory smell plumbing rather than mint a new finding bucket — `_DeterministicReport.smell_recs` already fans out to all three render surfaces (grouped report, `--json`, persisted report) and is never passed to `_completeness_has_blocking_findings`, so granularity advice surfaces everywhere yet can never flip the exit code, and the orchestrator `plan_tool/cli/completeness_cmd.py:cmd_completeness` (out of this step's footprint) needs no edit. On green, a plan with a mixed-concern step or a redundant adjacent pair shows a granularity line in the Smells (advisory) section of the audit report and `--json`, rc stays 0 in both default and `--fail-on-findings` mode, and the advisory smell section text names granularity advice so the bucket reads honestly.

## Table of Contents

- [Summary](#summary) — what the wiring adds and the observable result on green.
- [Table of Contents](#table-of-contents) — this list.
- [Why](#why) — completeness does no granularity reasoning today and cross-step merge has no surface anywhere.
- [Files (creates vs edits)](#files-creates-vs-edits) — two edited source files plus the test files that cover them.
- [Implementation](#implementation) — the `_run_deterministic_checks` call, the fold into `smell_recs`, the header wording, and why no new bucket.
- [Tests](#tests) — unit cases over the wiring, the render, and the never-gates guarantee.
- [Test-creation order (feature step)](#test-creation-order-feature-step) — write-with-implementation list and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors.
- [References](#references) — Python 3.13 docs for the leaf import and dataclass evidence envelope.
- [Deferred](#deferred) — the live-invoker prose path at completeness, merge execution, a dedicated bucket.

## Why

`completeness-audit` does no granularity reasoning today: its deterministic battery in `plan_tool/cli/completeness_phases.py:_run_deterministic_checks` checks well-formedness (sections, files, deps, lessons) and the step-2 advisory smell detectors (`review.collect_smell_findings` — brittle feature refs, suppression-shaped / self-referential steps), but nothing flags that a step is too big or that two adjacent dependent steps were fragmented and should merge. Cross-step **merge** advice has no surface anywhere in the tool — `create`'s change-type loop (step 3) only surfaces `granularity-split` next to its `(s)plit` action and drops merge recs. Step 1 built `plan_tool/granularity.py` with a deterministic, no-Claude cross-step battery (`granularity-split` + `granularity-merge`) that reads only plan structure. Completeness — which already reads the whole plan and persists a reusable report — is the natural home for that whole-plan audit. This step feeds the plan through the advisor at the `completeness` stage and surfaces its recs as advisory findings, with zero new Claude spend and zero risk to the exit-code convention.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py`
    - In `_run_deterministic_checks`: add a body-local import of the step-1 leaf next to the existing `from plan_tool.review import (...)` body-local block, call `assess_granularity(plan, stage="completeness", evidence=GranularityEvidence(), invoker=None)`, and append its recs to the `smell_recs` list returned in `_DeterministicReport`.
    - In `_render_grouped_report`: broaden the `### Smells (advisory)` descriptive sentence so it names step-granularity split/merge advice (the bucket now carries it).
  - `plan_tool/completeness_report.py`
    - In `build_report_md`: broaden the `## Smells (advisory)` descriptive sentence the same way. No new parameter — granularity recs ride in the existing `smells` argument the orchestrator already passes (`smell_recs=det.smell_recs`).
  - `tests/test_completeness_report.py` — add a `build_report_md` case proving a `granularity-merge` (and `granularity-split`) rec renders in the Smells (advisory) section through the existing `smells` param.
  - `tests/cli/test_completeness_cmd.py` — **required test footprint addition (not in the plan's `files:`).** The `_run_deterministic_checks` harness, `_DeterministicReport`, and the JSON/grouped render tests all live here (the declared `tests/test_completeness_report.py` only exercises the pure report-builder). The new wiring case (assess_granularity called, recs folded into `smell_recs`) and the never-gates case belong beside the existing smell-wiring tests (`TestRunDeterministicChecks`, the smells-JSON / smells-grouped cases). State it explicitly; it is the same kind of out-of-`files:` test edit step 2 used for `review.py`.

## Implementation

### `plan_tool/cli/completeness_phases.py` — `_run_deterministic_checks`

- **Confirm step-1 symbols against landed code first (depends_on: 1).** `plan_tool/granularity.py` does not exist at HEAD yet (step 1 is `current`). Before wiring, confirm the exact public names against the landed leaf: `assess_granularity`, `GranularityEvidence`, and the stage literal `"completeness"`. Step 1's contract is `assess_granularity(plan, *, stage, evidence, invoker=None) -> list[Recommendation]`, with split recs `source="granularity-split"` and merge recs `source="granularity-merge"`, both `severity="info"`. The code wins on any rename — fix this detail, don't copy names from sibling detail files.
- **Add the call as a third step in the existing battery.** `_run_deterministic_checks` already runs correctness primitives (1), completeness primitives (2), then advisory smells (3, `collect_smell_findings`). Add the granularity audit alongside step 3 (still advisory, still no Claude) and union its recs into the `smell_recs` it returns:
  - Import body-local, next to the existing `from plan_tool.review import (...)` block: `from plan_tool.granularity import assess_granularity, GranularityEvidence`. Body-local matches the file's established convention (the `review` detectors are imported the same way) and keeps the import resolvable to any test patch on the domain module. Note there is **no cycle** to dodge here — `granularity` is a leaf that imports only `schema` + `review` primitives and imports nothing from `plan_tool.cli`; the body-local form is the file's house style, not a cycle break.
  - Call `assess_granularity(plan, stage="completeness", evidence=GranularityEvidence(), invoker=None)`.
    - **`invoker=None` is the no-Claude guarantee.** `_run_deterministic_checks` is the no-Claude well-formedness battery by contract; passing `None` runs only step 1's deterministic split/merge detectors (which read plan structure). The prose judgment behind the invoker seam is the `detail` stage's job (step 2), not completeness's.
    - **`GranularityEvidence()` (empty) is sufficient.** The deterministic cross-step battery reads only `plan` structure (titles, `change_type`, `depends_on`, `files`/`creates`). `GranularityEvidence.detail_bodies` feeds only the invoker prose path, which is off here. Do not load detail files just to populate evidence the deterministic path ignores.
  - Append the returned recs to the `smell_recs` list before constructing `_DeterministicReport` — e.g. `smell_recs = collect_smell_findings(...) + assess_granularity(...)`. One bucket, one render path.
- **No guard needed.** `plan` is already a validated `Plan` here (`cmd_completeness` parsed it before calling this phase), so the deterministic detectors won't raise. This matches `collect_smell_findings`, which is also called unguarded. (Contrast step 3's `create` wiring, which guards because it feeds an *unvalidated* interim step list.)
- **Leave the deterministic-count tail unchanged.** The `if not quiet:` count sums only the seven well-formedness lists and deliberately excludes `smell_recs`. Granularity recs ride in `smell_recs`, so they correctly do **not** inflate that well-formedness count — an advisory heads-up must not read as a blocking-volume signal.

### `plan_tool/cli/completeness_phases.py` — `_render_grouped_report`

- **Broaden the `### Smells (advisory)` descriptive sentence** so it names granularity advice — the bucket now carries `granularity-split` / `granularity-merge` recs alongside the feature-ref / suppression / self-referential smells. Keep the heading text `### Smells (advisory)` unchanged (existing tests key on it) and keep the "never auto-applied and never block the run" clause.
- **No other change.** The section already iterates every rec in `det.smell_recs` via `_fmt_finding_line`-style rendering, and `has_any` already includes `det.smell_recs`, so a granularity-only plan renders the Smells section (not the "no completeness issues detected" sentinel) with no predicate edit.

### `plan_tool/completeness_report.py` — `build_report_md`

- **Broaden the `## Smells (advisory)` descriptive sentence** to match the grouped report's wording (name granularity split/merge advice). Keep the heading `## Smells (advisory)` and the disposition clause unchanged.
- **No new parameter.** Granularity recs arrive through the existing `smells` argument — `cmd_completeness` already passes `smell_recs=det.smell_recs` into `_persist_and_present_report`, which forwards it as `smells=` to `build_report_md`. Because granularity recs are folded into `det.smell_recs` upstream, every surface (`--json` `checks.smells`, grouped `### Smells`, persisted `## Smells`) gets them with no signature churn.

### Why fold into `smell_recs` instead of a new bucket

- **A dedicated `granularity_recs` field would force an out-of-scope orchestrator edit.** A new `_DeterministicReport` field would have to be threaded by `cmd_completeness` into `_persist_and_present_report` (the `smell_recs=det.smell_recs` call site) and is read by `_render_completeness_json` / `_render_grouped_report` — and `cmd_completeness` lives in `plan_tool/cli/completeness_cmd.py`, which is **not** in this step's `files:`. Riding `smell_recs` reaches all three surfaces by reusing the call sites that already read it.
- **Disposition is identical.** Granularity findings and smells are both advisory plan-structure heuristics: never auto-applied, never blocking, info severity. They belong in the same bucket, not a parallel one with the same semantics.

### The never-gates guarantee (the exit-code convention)

- **Primary guarantee — structural exclusion.** `smell_recs` is never an argument to `_completeness_has_blocking_findings` (which `cmd_completeness` calls with `path_style_hint`, `dep_issues`, the five completeness lists, and `audit_recs` — not smells). Folding granularity recs into `smell_recs` keeps them out of the blocking gate by construction, so they can never flip rc in any mode, including `--fail-on-findings`.
- **Secondary guarantee — severity.** Step 1 emits granularity recs at `severity="info"`; even if they reached the gate, the medium+ threshold would skip them. Structural exclusion is the load-bearing one and survives a future severity bump.
- This satisfies the plan's exit-code acceptance criterion (rc stays 0 unless `--fail-on-findings`) with a stronger property: for these advisory findings rc stays 0 in both modes.

### Foundational logic and other call sites

- **The foundational behavior:** "run the cross-step granularity advisor at the completeness stage and surface its recs as advisory, non-gating findings." The advisor itself is single-sourced in `plan_tool/granularity.py:assess_granularity` (step 1); this step only adds the `completeness` call site.
- **Other stage call sites (do not touch):** `detail` consumes the advisor via step 2's `parse_mixed_step_findings` fold; `create` via step 3's `_granularity_split_hints`. Each stage feeds its own evidence and surfaces a different subset — no shared wiring to consolidate here.
- **Sibling advisory collector (do not re-route):** `review.collect_deterministic_findings` is the broadcast fan-out wired into the `--iterate` apply loop. Granularity recs must **not** go there — `apply_finding` edits prose and can't act on a structural granularity smell. Keeping the call only in `_run_deterministic_checks` (the post-loop battery) is the guarantee it never reaches the apply loop, exactly as `collect_smell_findings` is kept out of `collect_deterministic_findings`.

## Tests

`tests/test_completeness_report.py` (the pure report-builder):

- `test_report_renders_granularity_merge_in_smells_section` — a `granularity-merge` rec passed via `smells=` renders under `## Smells (advisory)` with its full body (reuses the existing `_rec` helper with `source="granularity-merge"`).
- `test_report_renders_granularity_split_in_smells_section` — same for `source="granularity-split"`.
- `test_report_smells_blurb_names_granularity` — the broadened descriptive sentence mentions granularity, and the `## Smells (advisory)` heading is unchanged.

`tests/cli/test_completeness_cmd.py` (the `_run_deterministic_checks` harness — required out-of-`files:` addition):

- `test_run_deterministic_checks_folds_granularity_into_smells` — patch `plan_tool.granularity.assess_granularity` to return one `granularity-merge` rec; assert it appears in `report.smell_recs` alongside the (patched) `collect_smell_findings` output.
- `test_run_deterministic_checks_passes_completeness_stage_and_no_invoker` — capture the kwargs `assess_granularity` is called with; assert `stage="completeness"` and `invoker is None` (the no-Claude guarantee).
- `test_granularity_recs_excluded_from_deterministic_count` — granularity-only smells leave the `[1/2]` deterministic count at 0 (smells don't inflate the well-formedness count).
- `test_granularity_smell_does_not_flip_rc_under_fail_on_findings` — drive `main(["completeness-audit", name, "--fail-on-findings", ...])` with a plan whose only finding is a granularity smell (patch the conceptual audit to return nothing and the deterministic well-formedness lists empty); assert rc 0 — proving granularity never reaches `_completeness_has_blocking_findings`.
- `test_json_payload_includes_granularity_in_smells_group` — `--json` `checks.smells` carries the granularity rec keyed on `source` (`granularity-merge`/`granularity-split`), not `axis`.

### Test-creation order (feature step)

This is a **feature** step. Write each test with the implementation it covers:

1. The `build_report_md` render cases first (pure function, no harness) — they pin the Smells-section rendering and the broadened blurb.
2. The `_run_deterministic_checks` fold + kwargs cases — pin the wiring and the `stage`/`invoker` contract.
3. The never-gates and JSON cases — pin the exit-code convention and the machine surface.

**Green-before-done gate:** every new test above must be green, and the full suite (`uv run pytest -m "not integration" tests/ -q`) must stay green, before this step is considered finished. The existing smell tests in `tests/cli/test_completeness_cmd.py` and `tests/test_completeness_report.py` (which key on the `## Smells (advisory)` / `### Smells (advisory)` headings, not the descriptive sentence) must pass unchanged.

## Acceptance criteria

- `_run_deterministic_checks` calls `assess_granularity(plan, stage="completeness", evidence=GranularityEvidence(), invoker=None)` and the returned recs appear in `_DeterministicReport.smell_recs`.
- A plan with a `granularity-merge` (or `granularity-split`) smell renders that line in the `### Smells (advisory)` section of the grouped report and the `## Smells (advisory)` section of the persisted report, and in `--json` `checks.smells` keyed on `source`.
- `completeness-audit <plan> --fail-on-findings` returns rc 0 when the only findings are granularity smells (no well-formedness or conceptual blocking finding present).
- The `[1/2]` deterministic finding count does not count granularity recs.
- The Smells (advisory) descriptive sentence (both render sites) names step-granularity split/merge advice; the section headings are unchanged.
- `grep -n "granularity" plan_tool/cli/completeness_cmd.py` returns nothing — the orchestrator is untouched; the wiring lives entirely in `_run_deterministic_checks`.
- The full non-integration suite passes.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3.13/library/dataclasses.html) — for constructing the empty `GranularityEvidence()` evidence envelope and reading `_DeterministicReport`'s frozen `smell_recs` field.
- [typing — Support for type hints (Python 3.13)](https://docs.python.org/3.13/library/typing.html) — for the keyword-only `assess_granularity(plan, *, stage, evidence, invoker=None)` contract this step calls.
- [Python Language Reference — The import system (Python 3.13)](https://docs.python.org/3.13/reference/import.html) — confirms the body-local import of the `granularity` leaf is a style choice (no cycle), since `granularity` imports nothing from `plan_tool.cli`.

## Deferred

- **Live invoker / prose judgment at completeness** — completeness runs the deterministic battery only (`invoker=None`). Feeding authored detail bodies through the invoker for a semantic whole-plan granularity judgment is a later step; it would add Claude spend to `_run_deterministic_checks`, which is the no-Claude phase today.
- **Merge execution** — `granularity-merge` is recommend-only until `merge-steps-executor.md` lands; completeness surfaces the advice but no completeness verb actuates a merge.
- **A dedicated granularity report bucket/section** — deferred to reconcile if granularity advice ever needs its own disposition rationale; today it shares the smells bucket, and a separate field would require an out-of-scope edit to `plan_tool/cli/completeness_cmd.py`.
- **`create --reprocess` / reconcile surfaces** — out of scope; this step touches only the completeness audit.
