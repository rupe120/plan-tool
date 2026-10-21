# Step 3 — Surface advisory smell findings through the completeness-audit deterministic layer (report + JSON), excluded from the blocking-finding gate

## Summary

Wire step 2's `plan_tool/review.py:collect_smell_findings` into the `completeness-audit` deterministic battery so the two advisory smell detectors (suppression-shape, self-referential) appear in the grouped report, the persisted report, and the `--json` payload — **without** ever flipping `has_blocking_findings` or the exit code. The key decision is that the exclusion is **structural, not severity-based**: smell findings travel in a new `_DeterministicReport.smell_recs` field that is *never passed* to `plan_tool/cli/completeness_cmd.py:_completeness_has_blocking_findings`, and are *never* added to `collect_deterministic_findings` (so the `--iterate` convergence loop never tries to apply them). Primary files: `plan_tool/cli/completeness_phases.py` (compute + render), `plan_tool/cli/completeness_cmd.py` (thread `plan_name` + `smells` through), `plan_tool/completeness_report.py` (persisted-report section). On green: a plan whose only findings are smells renders a `### Smells (advisory)` section and a `checks.smells` JSON group, yet `has_blocking_findings` is `False` and rc is `0`.

## Table of Contents

- [Why](#why) — what's missing and why smells surface here first
- [Files (creates vs edits)](#files-creates-vs-edits) — the four declared files and their edits
- [Implementation](#implementation) — the field, the compute site, the three render surfaces, and the structural exclusion
- [Tests](#tests) — phase-helper unit cases in `tests/cli/test_completeness_cmd.py`
- [Test-creation order (feature step)](#test-creation-order-feature-step) — author tests with the code; green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — the pydantic/stdlib docs relevant to this step
- [Deferred](#deferred) — out-of-scope items (`validate` surfacing, report-unit tests, smell-specific next-step lines)

## Why

Step 2 (this step's `depends_on` dependency) ships the detectors behind one public `plan_tool/review.py:collect_smell_findings` entry, but deliberately wires it into **no** flow — surfacing is this step's owned scope. These symbols do **not** exist at HEAD; step 2 produces them. Before wiring, confirm `collect_smell_findings`'s exported name and arity at HEAD (per the cross-step-contract rule) — the assumed call `collect_smell_findings(plan, ctx.repo_root, plan_name=plan_name)` matches step 2's detail signature. Once step 2 lands, the detectors exist and are unit-tested but no operator-facing command runs them. `completeness-audit` is the right first surface: it already front-runs a no-Claude deterministic battery (`plan_tool/cli/completeness_phases.py:_run_deterministic_checks`) before the conceptual Claude audit, and renders to three places (grouped console report, persisted markdown sidecar, `--json`). This step adds smells to all three. The hard constraint from the plan: smells are **advisory** — they must not flip the exit code, `has_blocking_findings`, or enter the `--iterate` apply loop. The plan's exit-code convention ([[feedback_exit_code_convention]]) already says a completed audit exits 0; this step preserves it by keeping smells out of the blocking gate entirely.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` —
    - add a `smell_recs: list = field(default_factory=list)` field to `_DeterministicReport`;
    - extend `_run_deterministic_checks` to take a `plan_name: str` keyword-only param, body-local-import `collect_smell_findings`, call it, and populate `smell_recs`;
    - add a `### Smells (advisory)` section to `_render_grouped_report` (conditional) and add `det.smell_recs` to its `has_any` predicate;
    - add a `smells` group to `_render_completeness_json`'s `checks` payload;
    - add a `smells` param to `_persist_and_present_report` and forward it to `build_report_md` / `console_summary`.
  - `plan_tool/cli/completeness_cmd.py` — in `cmd_completeness`: pass `plan_name=args.name` to `_run_deterministic_checks`, and `smells=det.smell_recs` to `_persist_and_present_report`. **No edit** to either `_completeness_has_blocking_findings` call (the exclusion).
  - `plan_tool/completeness_report.py` — add an optional `smells` param to `build_report_md` (disposition-summary count + a `## Smells (advisory)` section) and to `console_summary` (a count line), both defaulting to `None` so existing callers stay unchanged.
  - `tests/cli/test_completeness_cmd.py` — add smell cases to `TestRunDeterministicChecks`, `TestRenderGroupedReport`, `TestRenderCompletenessJson`, `TestPersistAndPresentReport`; update `_empty_det()` / the `_run_deterministic_checks` call sites for the new `plan_name` param.

## Implementation

### `plan_tool/cli/completeness_phases.py`

**`_DeterministicReport` — add the smell bundle.**
- Add `smell_recs: list = field(default_factory=list)` as the **last** field (the dataclass is `@dataclass(frozen=True)`; all existing fields are default-less, so a default-bearing field must come last). `field` is already imported (`from dataclasses import dataclass, field`).
- The default keeps `_empty_det()` and any other positional/partial constructor valid; `_run_deterministic_checks` sets it explicitly.
- Update the class docstring's "seven issue lists" wording to note the eighth, advisory `smell_recs` list and that it is **excluded from the blocking gate**.

**`_run_deterministic_checks` — compute smells.**
- Change the signature to `_run_deterministic_checks(plan, path, ctx, *, plan_name: str, quiet: bool)` (new required keyword-only `plan_name`). It mirrors `plan_tool/review.py:collect_deterministic_findings`, which already requires `plan_name=` to mint stable ids via `_make_rec_id`.
- Add `collect_smell_findings` to the existing body-local `from plan_tool.review import (...)` block (the import is body-local because none of these detectors is monkeypatched in the suites — keep that rationale).
- Call once, after the seven existing detectors: `smell_recs = collect_smell_findings(plan, ctx.repo_root, plan_name=plan_name)`. `collect_smell_findings` is deterministic and I/O-bounded (reads `.plan-tool/config.json` for the self-referential set, scans titles) — no Claude, safe in this battery.
- Fold `len(smell_recs)` into the `_det_total` count printed under the non-`quiet` deterministic-count tail so the `[1/2]` banner reports them.
- Pass `smell_recs=smell_recs` into the returned `_DeterministicReport`.

**`_render_grouped_report` — add the advisory section.**
- After the `if conceptual_recs:` block and before the `has_any = (...)` computation, add:
  ```
  ### Smells (advisory)

  _Deterministic shape heuristics — never block. A feature/step whose
  stated purpose is to suppress an audit gate, or whose set of files
  overlaps the validation machinery. Legitimate cases exist; dismiss by
  eye._
  ```
  then one bullet per `rec` in `det.smell_recs`: `- {rec.severity.upper()}: {(rec.body or rec.title).strip()}`. Smells carry no `rec.anchor` (step 2 mints none), so render plain — same shape as the lessons/body-issue bullets, not the anchor-tagged correctness/conceptual bullets.
- **Add `det.smell_recs` to the `has_any` predicate.** Without it, a smell-only plan prints both the `### Smells (advisory)` section *and* the `_(no completeness issues detected)_` line — a contradiction.
- **Do not** let smells flip the `_structural` / `_missing_detail` / `conceptual_recs` next-step bullets. They are advisory: a smell-only plan should fall through to the existing `if not _next_steps:` → `if has_any:` "_Remaining finding(s) above are advisory… no follow-up command needed._" line. Verify by reading the `_structural` predicate — it lists path-style/dep/body/detail-body/files-coh/lessons/correctness; leave it unchanged so smells don't enter it.

**`_render_completeness_json` — add the `smells` group.**
- Add a `"smells"` key under `out["checks"]`, a list comprehension over `audit_recs`'s sibling argument `det.smell_recs`:
  ```
  "smells": [
      {
          "severity": r.severity,
          "source": r.source,
          "step_id": r.step_id,
          "id": r.id,
          "title": r.title,
          "body": r.body,
      }
      for r in det.smell_recs
  ],
  ```
  Shape mirrors the existing `plan_audit` entries but carries `source` (so a consumer distinguishes `suppression-shape` from `self-referential`).
- **Do not** touch `out["has_blocking_findings"]` — it stays the value the orchestrator computed from the seven non-smell buckets + `audit_recs`. The `smells` group is reported but never gates.

**`_persist_and_present_report` — forward smells to the persisted report.**
- Add a keyword param `smells: Optional[list] = None`.
- Pass `smells=smells` to the `build_report_md(...)` call and to the `console_summary(...)` call. Both are body-local imports from `plan_tool.completeness_report` already in this function.
- No other change — the grouped report (which `build_report_md` embeds under "Full grouped report") already carries the smell section, so this only adds the curated top-level summary section/count.

### `plan_tool/cli/completeness_cmd.py`

**`cmd_completeness` — thread the two new args.**
- Pass `plan_name=args.name` into the `_run_deterministic_checks(plan, path, ctx, quiet=budget.enabled)` call (now `…, plan_name=args.name, quiet=budget.enabled`).
- Pass `smells=det.smell_recs` into the `_persist_and_present_report(...)` call.
- **Leave both `_completeness_has_blocking_findings(...)` calls byte-unchanged** (the `--json` `has_blocking` computation and the `--fail-on-findings` gate). This is the structural exclusion: `smell_recs` is never one of its keyword arguments, so a smell can never make the audit report blocking or flip rc — independent of severity. State this in a one-line comment at each call site.

### `plan_tool/completeness_report.py`

**`build_report_md` — optional curated smell section.**
- Add `smells: Optional[list[Recommendation]] = None` (mirror the existing optional `correctness` param's pattern, default `None`).
- When `smells` is **non-empty**: add a disposition-summary line `- **Smells (advisory, never blocking):** {len(smells)}` in the `## Disposition summary` block, and a dedicated section:
  ```
  ## Smells (advisory)

  _Deterministic shape heuristics. Advisory only — they never flip the
  exit code or `has_blocking_findings`. Each names a brittle shape
  (gate-suppression intent, self-referential file set); the remedy is to
  extract or cut the feature, not an apply edit._
  ```
  then one `_fmt_finding_line(rec)` per smell. Reuse `_fmt_finding_line` (it already renders `rec.body` full + optional anchor tag).
- When `smells` is `None` or `[]`: emit nothing — preserves the unchanged output the out-of-scope `tests/test_completeness_report.py` pins.
- Do **not** add a `_HEADINGS` / `WHY` entry: those dicts are keyed by *deferral disposition* (`diagnostic`/`triage`/…); smells are not a deferral kind. Use a literal heading/why string in-place.

**`console_summary` — count line.**
- Add `smells: Optional[list[Recommendation]] = None`; when non-empty, append a `  smells    {len(smells)} advisory shape finding(s) — see report` line. Omit when `None`/empty.

### Foundational logic / shared-location audit

- **Core rule:** surface `collect_smell_findings` output through the completeness deterministic layer, advisory-only, excluded from the blocking gate.
- **The single seam** is `plan_tool/review.py:collect_smell_findings` (step 2). This step consumes it; it does not re-enumerate the detectors.
- **Parallel surfacing site (Deferred, not this step):** step 4 wires the *same* `collect_smell_findings` into `validate` (`plan_tool/cli/inspect.py`). That is a sibling consumer, not a consolidation target — each surface owns its own rendering. Do **not** factor a shared renderer here.
- **`plan_tool/review.py:collect_deterministic_findings` stays unedited** (confirmed at HEAD: it appends only `check_test_strategy_alignment`, not smells). It is the broadcast fan-out the `--iterate` loop's `_collect_det_findings` calls (`plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop`); keeping smells out of it is what guarantees the convergence loop never dispatches a smell to `apply_finding`. The post-loop `_run_deterministic_checks` is the *only* place smells are collected.
- **Severity band (belt-and-suspenders):** smells are `severity="info"` (step 2's `_SUPPRESSION_SHAPE_SEV` / `_SELF_REFERENTIAL_SEV`), below `plan_tool/convergence.py:BLOCKING_SEVERITIES`. Even if a smell leaked into `audit_recs`, `is_blocking` would return `False`. The structural exclusion (never passed to the gate) is the primary guarantee; the `info` severity is the secondary.

## Tests

All cases land in `tests/cli/test_completeness_cmd.py` (the step's declared test file). They reach the phase helpers directly from `plan_tool.cli.completeness_phases` — the documented internal-seam exception this module already uses — and patch only the *domain* seam (`plan_tool.review.collect_smell_findings`) when a stubbed return is needed, never a `plan_tool.cli` global.

**Harness updates (existing cases):**
- `_empty_det()` — leave the call unchanged (the new `smell_recs` field defaults via `field(default_factory=list)`); optionally add `smell_recs=[]` for explicitness.
- `TestRunDeterministicChecks` — pass the new required `plan_name` to the two `_run_deterministic_checks(plan, path, ctx, quiet=True)` calls. The value is only an id-minting namespace the assertions never read, so any string works (e.g. `plan_name="x"`) — it does not matter. Add `"smell_recs"` to the field tuple in `test_returns_deterministic_report_type`.

**`TestRunDeterministicChecks` (new):**
- `test_clean_plan_has_empty_smell_recs` — a clean plan yields `report.smell_recs == []`.
- `test_smell_findings_populated` — patch `plan_tool.review.collect_smell_findings` to return one `info`/`suppression-shape` rec; assert it lands in `report.smell_recs` and nowhere in the seven structural fields.

**`TestRenderGroupedReport` (new):**
- `test_smells_section_conditional` — a `_DeterministicReport` with one smell rec → `### Smells (advisory)` present; an empty-smell det → absent.
- `test_smell_only_not_reported_as_no_issues` — det with only `smell_recs` non-empty → `_(no completeness issues detected)_` **not** in md, and the `### Smells (advisory)` section **is**.
- `test_smells_do_not_add_structural_next_step` — a smell-only det → the next-steps block carries the advisory "no follow-up command needed" line, **not** `completeness-audit … --iterate` / `reconcile-plan-walk`.

**`TestRenderCompletenessJson` (new):**
- `test_smells_group_present` — det with one smell rec → `data["checks"]["smells"]` is a one-element list carrying `source`/`severity`/`id`/`title`/`body`.
- `test_smells_do_not_flip_has_blocking` — render with `has_blocking=False` and a non-empty `smell_recs`; assert `data["has_blocking_findings"] is False` and `rc == 0` (the smell never reaches the gate).

**`TestPersistAndPresentReport` (new):**
- `test_smells_section_in_persisted_report` — call `_persist_and_present_report(..., smells=[_rec("info", source="suppression-shape")])` with the write seam real; read the returned report file and assert it contains `## Smells (advisory)`.
- `test_no_smells_omits_section` — `smells=[]` (or omitted) → the persisted report has no `## Smells` section (unchanged from today).

## Test-creation order (feature step)

This is a **feature** step — new surfacing behavior. Author every case above **in the same change** as the `completeness_phases.py` / `completeness_cmd.py` / `completeness_report.py` edits: write the failing assertion, add the field/param/section, watch it pass. Behaviors covered: smell collection in the deterministic battery, the conditional grouped/persisted/JSON sections, the `has_any` fix for smell-only plans, the advisory next-step fall-through, and — the most important one — that smells never flip `has_blocking_findings` or rc. **Green-before-done gate:** every new case must pass (`uv run pytest -m "not integration" tests/cli/test_completeness_cmd.py -q`), and the pre-existing `tests/cli/test_completeness_cmd.py` and `tests/test_completeness_report.py` suites must stay green (the `None`-default params guarantee the latter is untouched).

## Acceptance criteria

- `plan_tool/cli/completeness_phases.py:_DeterministicReport` has a `smell_recs` list field; `_run_deterministic_checks(plan, path, ctx, *, plan_name=…, quiet=…)` populates it from `plan_tool/review.py:collect_smell_findings`.
- A plan tripping a smell detector renders a `### Smells (advisory)` section in the grouped report and a `checks.smells` array in `--json`; a clean plan renders neither.
- A smell-only plan does **not** print `_(no completeness issues detected)_` and does **not** surface a structural/iterate next-step bullet.
- `--json` `has_blocking_findings` is `False` and the process rc is `0` for a smell-only plan, including under `--fail-on-findings` (smell_recs is never an argument to `_completeness_has_blocking_findings`).
- `plan_tool/completeness_report.py:build_report_md(smells=…)` renders a `## Smells (advisory)` section + disposition count when smells are present, and is unchanged from today when `smells` is `None`/`[]`.
- `plan_tool/review.py:collect_deterministic_findings` is unchanged (smells never enter the `--iterate` apply loop).
- All new test cases pass; `tests/cli/test_completeness_cmd.py` and `tests/test_completeness_report.py` stay green.

## References

- [Python `dataclasses` — `field(default_factory=…)` and frozen dataclasses](https://docs.python.org/3/library/dataclasses.html) — the default-field-ordering rule for adding `smell_recs` to the frozen `_DeterministicReport` without breaking positional constructors.
- [Python `json` — `json.dumps`](https://docs.python.org/3/library/json.html#json.dumps) — the `--json` payload shape for the new `checks.smells` group.
- [Validators — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — confirms step 1's `Plan._validate_features` guarantees `feature.steps` resolve, which the self-referential detector (whose findings this step surfaces) relies on.

## Deferred

- **`validate` surfacing of `collect_smell_findings`** — step 4 (`plan_tool/cli/inspect.py` / `tests/cli/test_inspect_cmds.py`). A parallel consumer of the same seam; out of this step's scope.
- **Smell-finding unit cases in `tests/test_completeness_report.py`** — the dedicated `build_report_md` / `console_summary` byte-output suite. This step tests the smell-rendering path through `_persist_and_present_report` (in `tests/cli/test_completeness_cmd.py`, in scope); deeper byte-pinning of the new `## Smells (advisory)` section belongs in that out-of-scope file and can be added by reconcile if desired.
- **Smell-specific next-step lines** in `suggested_next_step_commands` / `diagnostic_remedies` (e.g. "extract or cut the flagged feature") — smells fall through to the generic advisory line for now; a tailored remedy is a cosmetic follow-up.
- **A `--no-smell-checks` opt-out flag** — would require a `docs/cli/` regen step (per the plan's own note); not introduced here.
