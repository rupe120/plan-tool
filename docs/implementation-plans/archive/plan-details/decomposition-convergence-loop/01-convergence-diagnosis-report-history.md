# Step 1 — Add convergence_diagnosis report-history reader and normalized per-run model

## Summary

- Adds a new leaf module `plan_tool/convergence_diagnosis.py` that reads a plan's saved completeness/reconcile report history off disk and flattens each report into a small, frozen, normalized per-run model. No detection, no classification, no CLI yet — just the reader + data model that steps 2–4 build on.
- The reader reuses `plan_tool/review_persistence.py`'s existing list/load primitives (`list_saved_reviews`, `load_review`) rather than re-globbing, so the on-disk JSON schema has one parser. It spends zero Claude and writes nothing.
- Most important design decision: the normalized model carries exactly the fields the non-convergence signature keys on — per-finding `anchor`, `step_id`, `severity`, `source`, plus a per-run `report_bytes` growth proxy and a chronological run order — and the reader is **defensive** (a malformed report file is skipped, a missing reports dir yields an empty history, missing optional fields become `None`).
- Adds `tests/test_convergence_diagnosis.py` and one committed fixture `tests/fixtures/convergence/sample-report-history.json` (a 3-run spinning series) that pins the report-JSON fields the detector depends on, so report-schema drift is caught here.
- On green: `load_report_history(plan_path)` returns a `ReportHistory` of `RunSnapshot`s ordered oldest→newest, each exposing its findings normalized for steps 2–4.

## Table of Contents

- [Why](#why) — what's missing today and why the reader/model comes first
- [Files (creates vs edits)](#files-creates-vs-edits) — the three new files
- [Implementation](#implementation) — the data model, the reader, defensive rules, and reuse decisions
- [Tests](#tests) — unit + fixture-schema-pin cases and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors
- [References](#references) — stdlib docs for the surfaces this step touches
- [Deferred](#deferred) — detection, classifier, CLI, and verdict-reading left for later steps

## Why

- The pipeline converges on content, never on structure: `create` decides decomposition once, and the audit/apply loop can only edit prose, so a mis-decomposition gets re-found under a new anchor every pass and never converges (see the plan's Problem statement).
- v1 automates the **detection-and-recommendation** half of the missing "audit-detects-bad-decomposition → re-decompose" edge. Every later step (signature detector, localized-vs-structural fork, CLI seam) needs one thing first: a trustworthy, normalized cross-run view of the saved report history.
- That view does not exist yet. The reports are on disk (`docs/implementation-plans/plan-details/<slug>/reports/*.json`) but only `plan_tool/review_persistence.py` reads them, and it returns a `SavedReview` shaped for the walk loop (full `report_md`, raw `Recommendation` list, walk `annotations`) — not the per-run, per-anchor recurrence/severity/size shape the convergence signature keys on. This step builds exactly that shape and nothing more, so steps 2–3 are pure logic over a clean model.

## Files (creates vs edits)

**New files:**
- `plan_tool/convergence_diagnosis.py` — the reader + normalized per-run model (this step's whole code surface).
- `tests/test_convergence_diagnosis.py` — unit tests for the reader and model, plus the fixture-schema pin.
- `tests/fixtures/convergence/sample-report-history.json` — a committed 3-run spinning series (same anchor re-flagged across 3 consecutive completeness runs, no shrinkage) used by this step's tests and reused by steps 2–3.

**Existing files (edits only):**
- None. This step is self-contained new code. It imports existing symbols from `plan_tool/review_persistence.py`, `plan_tool/review.py`, and `plan_tool/locator.py` but edits none of them.

## Implementation

### `plan_tool/convergence_diagnosis.py` (new)

**Module posture.** A leaf below the CLI. Top-level imports only:
- `from __future__ import annotations`, `from dataclasses import dataclass`, `from pathlib import Path`, `from typing import Optional`.
- `from plan_tool.review_persistence import list_saved_reviews, load_review, ReviewLoadError, SavedReview`.
- `from plan_tool.locator import slug_from_filename`.

These are all acyclic: `plan_tool/review_persistence.py` is a stdlib-only leaf that imports only `plan_tool/review.py`'s `Recommendation`, and never imports this new module — so a **top-level** import is safe here. Do not lazy-import; the plan's "lazy-import if it would close a cycle" caveat does not apply because no cycle exists. State this in a one-line module docstring note so a later reader doesn't body-localize it reflexively.

**Module constant — which report kinds count as history.**
- `HISTORY_KINDS: frozenset[str] = frozenset({"completeness", "detail-reconcile", "run-reconcile"})`.
- This matches the plan's `*-completeness.json` / `*-reconcile.json` globs by `kind`, not by filename: `plan_tool/review_persistence.py:_timestamp_filename` writes `-completeness.json`, `-detail-reconcile.json`, `-run-reconcile.json`, and the plain `reconcile-plan` `kind="review"` report is the bare `<timestamp>.json` (no suffix) — excluded on purpose. Filter on `SavedReview.kind` after load; it is the same set the suffixes encode and is robust to a future filename change.
- **The recurrence series is per-kind, not unified.** Completeness (`kind="completeness"`, plan↔plan conceptual findings) and reconcile (`detail-reconcile` / `run-reconcile`, code↔plan findings) draw their `anchor` and `step_id` from different spaces, so folding them into one per-region series would conflate an unrelated reconcile finding with a completeness one under a colliding key, or interleave two cadences as one trend. `load_report_history` loads all `HISTORY_KINDS` into one `ReportHistory`, but every run carries its `kind` (`RunSnapshot.kind`) so step 2's recurrence/shrinkage detector **partitions runs by `kind` first and computes a separate recurrence series per kind** — a region's recurrence key is therefore `(kind, anchor || step_id || normalized-title-similarity)`, never anchor/step alone. No cross-kind region match exists in v1; this step only needs to preserve `kind` faithfully on every snapshot so step 2 can split on it.

**The normalized model — three frozen dataclasses.** Use `@dataclass(frozen=True)`, matching `plan_tool/review.py: Recommendation`'s posture.

- `RunFinding` — one open/recorded finding inside one report run, flattened from a `Recommendation`:
  - `anchor: Optional[str]` — from `Recommendation.anchor` (the concept slug the recurrence detector keys on first; slug stability across separate audit invocations is only *encouraged*, not guaranteed, so step 2 falls back to `step_id`/title-similarity when the slug drifts run-over-run; `None` when Claude omitted it).
  - `step_id: Optional[int]` — from `Recommendation.step_id` (note: `plan-completeness` findings frequently carry `step_id=None` and name the step inside the title/anchor instead — preserve the `None`, don't synthesize one).
  - `severity: str` — from `Recommendation.severity` (`"critical" | "high" | "medium" | "nit" | "info"`).
  - `source: str` — from `Recommendation.source` (e.g. `"plan-completeness"`, `"plan-correctness"`, and the granularity advisor's `"granularity-split"` / `"granularity-merge"` when present).
  - `rec_id: str` — from `Recommendation.id` (used to look up the walk annotation).
  - `title: str` — from `Recommendation.title` (for human-readable diagnosis output in step 3, and the title-similarity fallback step 2 uses to match a recurring region when the anchor slug drifts run-over-run).
  - `resolved: bool` — `True` iff this rec's `Annotation.status` is a closed state (`"applied"` or `"skip"`) in the run's `annotations` dict; a deliberate `"skip"` is a triaged WONTFIX/out-of-scope decision and counts as closed so step 2's recurrence never re-flags it. `False` when the annotation is absent or `"open"`.
    - **Which report kinds populate annotations.** Only walked / `completeness-apply` sidecars and the reconcile kinds carry `annotations`; the audit-created `kind="completeness"` save path (`completeness_report.py: write_completeness_report` → `save_review`) writes **no** annotations. So for the primary completeness history `resolved` is structurally always `False`, and the streak-breaking branch step 2 relies on never fires for audit-created sidecars. This is intended: for audit-created completeness sidecars, cross-run progress is gated by the **no-shrinkage open-finding count** (step 2's trend), not by `resolved`. The `resolved` flag still earns its place for the walked/reconcile kinds, where annotations exist.

- `RunSnapshot` — one normalized report run:
  - `created_at: str` — ISO-8601 UTC, e.g. `"2026-06-20T11:31:16Z"`, copied verbatim from `SavedReview.created_at` (the sort key; lexically sortable).
  - `kind: str` — `SavedReview.kind` (one of `HISTORY_KINDS`).
  - `step_id: Optional[int]` — the **report-level** `SavedReview.step_id` (set for the reconcile kinds, `None` for completeness). Distinct from `RunFinding.step_id`; keep both.
  - `report_bytes: int` — `len(SavedReview.report_md)`. The available monotone-growth proxy: the report JSON does **not** persist the plan/detail file sizes, so `report_md` length is the only size signal on disk. Step 2 reads this for the no-shrinkage/growth trend.
  - `findings: tuple[RunFinding, ...]` — every normalized finding in the run.
  - `path: Path` — the source file (`SavedReview.path`), for diagnostics and as a stable secondary sort key.
  - Add a derived read-only `open_findings` property returning `tuple(f for f in self.findings if not f.resolved)`. Cheap, and the natural seam step 2's recurrence/shrinkage logic reads. Do **not** add severity filtering here — the medium+ threshold (and any `plan_tool/convergence.py: BLOCKING_SEVERITIES` reuse) belongs to step 2's detector, not this model.

- `ReportHistory` — the whole series for one plan:
  - `plan_slug: str`.
  - `runs: tuple[RunSnapshot, ...]` — ordered **oldest→newest** so step 2 reads trends chronologically.

**The reader — `load_report_history`.**
- Signature: `def load_report_history(plan_path: Path, *, kinds: frozenset[str] = HISTORY_KINDS) -> ReportHistory:`.
- Resolve the slug via `slug_from_filename(plan_path)` (default-to-stem → never `None`).
- List candidate report files by reusing `list_saved_reviews(slug, plan_path, plan_path=plan_path)`. `list_saved_reviews` already derives the canonical dir via `plan_reports_dir`, returns `[]` when the dir is absent, and filters to `.json`. Its `repo_root` positional is documented vestigial (the dir comes from `plan_path`); pass `plan_path` for it and add a one-line comment noting it's ignored — this keeps a single source for the glob rather than re-implementing it.
- For each path: `try: saved = load_review(p) except ReviewLoadError: continue`. A malformed file, a wrong `version`, or a bad recommendation must skip that one file, never abort the history — this is the schema-drift defense from the plan's Risks.
- Skip any loaded run whose `saved.kind not in kinds`.
- Normalize each kept `SavedReview` through a private `_normalize_run(saved) -> RunSnapshot` helper (below).
- Sort the resulting runs ascending by `(run.created_at, run.path.name)` so equal-second timestamps stay deterministic, then return `ReportHistory(plan_slug=slug, runs=tuple(runs))`.

**The normalizer — `_normalize_run(saved: SavedReview) -> RunSnapshot`.**
- Build each `RunFinding` from `saved.recommendations`, reading `Recommendation.anchor / step_id / severity / source / id / title`.
- Compute `resolved` by looking up `saved.annotations.get(rec.id)`: `resolved = ann is not None and ann.status in {"applied", "skip"}`. A `"skip"` is a deliberate triage decision (WONTFIX/out-of-scope) and is a closed state, so it never accrues a recurrence streak. (The loader already rewrites the legacy `"done"` → `"applied"`, so only `"applied"` and `"skip"` need be checked.)
- Set `report_bytes = len(saved.report_md)`.
- Carry `created_at`, `kind`, report-level `step_id`, and `path` straight through.

**Foundational logic and where else it lives.**
- This step's core rule is **"flatten one saved report into per-finding (anchor, step_id, severity, source, resolved) tuples + a per-run size."** The only other place that reads these saved reports is `plan_tool/review_persistence.py` (`load_review` / `list_saved_reviews`) and `plan_tool/completeness_report.py: resolve_reusable_audit` (which reuses the newest completeness sidecar for freshness, not for cross-run trends). This step **reuses** the former (single parser) and does **not** touch the latter — its freshness check is a different concern (one report vs. current disk state, not a series). No consolidation step is needed; the read paths stay distinct by design.
- Note for later steps: per-finding apply **verdicts** (the `AppliedOutcome.verdict` `BLOCKED` value from `plan_tool/completeness_report.py: AppliedOutcome`) are **not** persisted to the report JSON — only `recommendations` and walk `annotations` are. So this model cannot expose a per-finding verdict. The plan's "structural `[BLOCKED]`" signal must come from recurrence (step 2) and/or parsing `report_md`, not from a structured verdict field. Surfacing that is step 2's job; this step deliberately leaves it out rather than inventing a field the JSON doesn't carry.
- Note for later steps: the `source` field this model exposes on `RunFinding` is what step 2's detector must use to **exclude (or separately bucket)** the never-auto-applied `plan-completeness` advisory-conceptual source from the recurrence/no-shrinkage signal — those advisories are deferred-by-design and re-emitted by every fresh audit, so counting them would read a converged plan as `spinning`. This step only carries `source` faithfully; the filtering itself is step 2's.

### `tests/fixtures/convergence/sample-report-history.json` (new)

- A JSON **array** of three full report payloads, each shaped exactly like a real saved report (`version: 1`, `plan_slug`, `plan_path`, `created_at`, `kind: "completeness"`, `step_id`, `plan_fingerprint`, `code_fingerprint`, `code_fingerprint_present`, `report_md`, `recommendations`, `annotations`). Use `created_at` values one minute apart and corresponding sortable timestamps.
- Make it a **spinning** series: the same `anchor` slug (e.g. `"step5-over-pack"`) re-flagged at `severity: "medium"` in all three runs, all unresolved (`annotations: {}`), with non-shrinking finding counts and non-decreasing `report_md` length — the canonical input steps 2–3 classify.
- Keep each payload minimal but schema-valid so `load_review` accepts it (every `Recommendation` field present: `id, source, severity, step_id, title, body, suggested_action, impact, complexity, redirect, file_path, anchor`).
- The test materializes these into a tmp reports dir (see Tests), so the array form is the single fixture file the step's frontmatter names, while still exercising the real directory-glob path.

### `tests/test_convergence_diagnosis.py` (new)

- Load the fixture via the standard idiom `Path(__file__).parent / "fixtures" / "convergence" / "sample-report-history.json"` (mirrors `tests/test_parser.py`'s `FIXTURES` pattern).
- A helper writes each array element to `<tmp_path>/docs/implementation-plans/plan-details/<slug>/reports/<ts>-completeness.json` (matching `plan_reports_dir`'s layout: `<plan_path.parent>/plan-details/<slug>/reports/`) and returns the synthetic `plan_path`, so tests drive the real `load_report_history(plan_path)` glob+load+normalize path. The committed fixture is three `completeness` runs only and the helper writes the `-completeness.json` suffix, so `test_report_level_step_id_and_kind_preserved` and `test_only_history_kinds_loaded` construct the other report kinds inline — copy a fixture payload, set its `kind` to `detail-reconcile` / `run-reconcile` / `review`, and write it with the matching filename suffix (`-detail-reconcile.json` / `-run-reconcile.json` / bare `<ts>.json`); don't assume the fixture supplies them.
- Tests are pure unit tests (no `main([...])`, no orchestrator, no Claude) — leave them unmarked; the integration `plan-tool convergence` end-to-end test is step 4's.

## Tests

Reference file: `tests/test_convergence_diagnosis.py`. Fixture: `tests/fixtures/convergence/sample-report-history.json`.

- `test_load_history_orders_runs_oldest_first` — the 3-run fixture loads into a `ReportHistory` whose `runs` are ascending by `created_at`.
- `test_normalizes_finding_fields` — a `RunFinding` carries `anchor`, `step_id`, `severity`, `source`, `rec_id`, `title` mapped from the underlying `Recommendation`.
- `test_resolved_flag_from_applied_annotation` — a finding whose annotation `status=="applied"` → `resolved is True`; a deliberate `status=="skip"` annotation (closed/WONTFIX) → `resolved is True`; an absent annotation and a `status=="open"` annotation → `resolved is False`.
- `test_open_findings_excludes_resolved` — `RunSnapshot.open_findings` drops resolved findings and keeps the rest.
- `test_report_bytes_is_report_md_length` — `RunSnapshot.report_bytes == len(report_md)`.
- `test_report_level_step_id_and_kind_preserved` — a `detail-reconcile` run keeps its report-level `step_id` and `kind` on the `RunSnapshot`, distinct from per-finding `step_id`.
- `test_only_history_kinds_loaded` — a `kind="review"` file dropped into the same dir is skipped; `completeness` and `*-reconcile` runs are kept.
- `test_malformed_report_skipped_not_raised` — an invalid-`version` / junk-JSON file in the dir is skipped while valid runs still load (no exception escapes).
- `test_missing_reports_dir_returns_empty_history` — a `plan_path` whose reports dir doesn't exist yields `ReportHistory` with `runs == ()`.
- `test_missing_anchor_and_step_id_tolerated` — a rec with `anchor=null` and `step_id=null` normalizes to `RunFinding(anchor=None, step_id=None)` without crashing.
- `test_fixture_schema_fields_pinned` — load the committed fixture and assert each run exposes the exact fields the detector depends on (`created_at`, `kind`, `report_bytes`, and per-finding `anchor`, `severity`, `source`, `step_id`, `rec_id`); this is the schema-drift guard called for in the plan's Risks.

### Test-creation order (feature step)

- This is a **feature** step. Write each test above **alongside** the `convergence_diagnosis.py` symbol it covers — model dataclasses first (`RunFinding`/`RunSnapshot`/`ReportHistory` field tests), then the reader (`load_report_history` ordering, kind-filter, defensive-skip, empty-history tests), then the fixture-schema pin.
- Green-before-done gate: every new test in `tests/test_convergence_diagnosis.py` must pass before this step is considered finished. Run `uv run pytest tests/test_convergence_diagnosis.py -q`.

## Acceptance criteria

- `plan_tool/convergence_diagnosis.py` exists and imports cleanly with no import cycle (`python -c "import plan_tool.convergence_diagnosis"` succeeds; the module's only `plan_tool` imports are `review_persistence`, `review` indirectly, and `locator`).
- `load_report_history(plan_path)` returns a `ReportHistory` whose `runs` are `RunSnapshot`s ordered oldest→newest by `created_at`.
- A reports dir containing one `completeness`, one `detail-reconcile`, one `run-reconcile`, and one `review`-kind file yields exactly three runs (the `review` one excluded).
- A malformed report file in the dir is skipped, not raised; the remaining valid runs still load.
- A `plan_path` with no reports directory returns a `ReportHistory` with `runs == ()`.
- `RunFinding` exposes `anchor`, `step_id`, `severity`, `source`, `rec_id`, `title`, `resolved`; `RunSnapshot` exposes `created_at`, `kind`, `step_id`, `report_bytes`, `findings`, `open_findings`, `path`.
- `RunSnapshot.report_bytes == len(report_md)` for each run.
- The module spends zero Claude calls and writes no files (no `invoker` parameter anywhere; no write/`save_review` call).
- `tests/fixtures/convergence/sample-report-history.json` is committed and `tests/test_convergence_diagnosis.py` passes in full.

## References

- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — `Path` construction and `Path.iterdir` semantics behind the reused `list_saved_reviews` glob and the test's tmp reports-dir layout.
- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — `json.load` / `JSONDecodeError` handling that `load_review` raises through as `ReviewLoadError`, which this reader catches to skip malformed reports.
- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — `@dataclass(frozen=True)` for the three normalized record types and the `property`-based `open_findings` accessor.

## Deferred

- **Non-convergence signature detection** (recurrence across N consecutive runs, no-shrinkage, monotone-growth → `converging`/`spinning`) — step 2. This step only supplies the normalized model the detector reads; it includes no thresholds and no `plan_tool/convergence.py: BLOCKING_SEVERITIES` import.
- **Localized-vs-structural fork classifier and forked recommendation renderer** — step 3.
- **`plan-tool convergence <plan>` CLI seam and the zero-Claude integration test** — step 4 (`plan_tool/cli/convergence_cmd.py`, parser registration, generated reference).
- **Reading per-finding apply verdicts (`BLOCKED`)** — not modeled here because `AppliedOutcome.verdict` is not persisted to the report JSON. If step 2's recurrence signal proves insufficient for the "structural `[BLOCKED]`" case, parsing `report_md` (or persisting verdicts) is a step-2/follow-up decision, not this model's field.
- **True plan/detail byte-size growth signal** — this step uses `len(report_md)` as the on-disk growth proxy. Computing the plan/detail bundle size from disk at HEAD would couple the reader to the working tree and is out of v1's read-only-of-saved-reports scope.
- **Plain `kind="review"` `reconcile-plan` reports** — excluded from `HISTORY_KINDS` to match the plan's completeness/`*-reconcile` history. Revisit only if a future detector needs the bare-`reconcile-plan` series.
