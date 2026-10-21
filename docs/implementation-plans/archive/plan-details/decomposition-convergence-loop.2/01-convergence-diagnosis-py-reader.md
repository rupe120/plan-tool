> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add `convergence_diagnosis.py` reader + normalized history model with committed fixture

## Summary

This step creates `plan_tool/convergence_diagnosis.py` and seeds it with the bottom layer the whole `plan-tool convergence` feature stands on: a reader, `load_report_history(plan_path)`, that loads a plan's saved completeness/reconcile report sidecars off disk and flattens them into a small, normalized, chronologically-ordered model — `ReportHistory` → `RunSnapshot` → `RunFinding`. The design decisions:

- **Reuse the parser.** `review_persistence.list_saved_reviews` / `load_review` is the single schema parser — never re-glob or re-deserialize.
- **Filter on the typed kind.** Which runs count is decided by the `SavedReview.kind` field via a `HISTORY_KINDS` frozenset, not by the filename suffix.
- **Persisted-field whitelist.** The model carries only what the JSON actually persists (recommendations + walk annotations + fingerprints), so `RunFinding` has **no** per-finding apply verdict.
- **`report_bytes` proxy.** `RunSnapshot.report_bytes` is `len(report_md)` — the only on-disk growth proxy.
- **Fixture purpose.** A committed 3-run SPINNING fixture under `tests/fixtures/convergence/sample-report-history.json` backs the tests and is authored expressly for step 2 to consume.

On green, `load_report_history` returns a `ReportHistory` whose `runs` are sorted oldest→newest by `created_at`, each run carrying its walk `annotations` verbatim for step 2's closed-state rule, with **no** region matching, **no** verdict, and **no** CLI (those are steps 2–4).

## Table of Contents

- [Why](#why) — what's missing today and why the reader is its own foundational step
- [Files (creates vs edits)](#files-creates-vs-edits) — the three new files this step creates
- [Implementation](#implementation) — the three records, the reuse-the-parser reader, the persisted-field whitelist, and the fixture
- [Tests](#tests) — unit cases for loading, ordering, kind-filtering, annotation pass-through, and empty/missing dirs
- [Acceptance criteria](#acceptance-criteria) — checkable outputs of `load_report_history`
- [References](#references) — json/datetime/glob/pytest docs for this step's surfaces
- [Deferred](#deferred) — region model, verdict, classifier, CLI, and the persisted-data limits

## Why

The `plan-tool convergence` diagnostic must decide, from a plan's saved report history, whether the audit/apply loop is patching *around* a mis-decomposition rather than closing it. Every later layer — region matching (step 2), the spinning-vs-converging verdict (step 3), the localized-vs-structural fork and CLI (step 4) — reads **cross-run report data**, but nothing in the codebase loads that history into a shape those layers can consume. `review_persistence.py` lists and parses one report at a time into a `SavedReview` (rich, in-memory, more fields than the JSON carries), and the saved JSON drops things a naive model would assume exist (per-finding apply verdicts, plan/detail byte sizes). This step is the one place that loads the on-disk reports once, deterministically, and flattens them into a normalized model whose fields are exactly the persisted subset — so no downstream step re-globs the directory, re-derives the schema, or keys on a field the JSON never wrote.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/convergence_diagnosis.py` — the new module: the three record types (`ReportHistory`, `RunSnapshot`, `RunFinding`), the `HISTORY_KINDS` frozenset, and the `load_report_history(plan_path)` entry point. Top-level imports only (the module is a cycle-free leaf, see below).
  - `tests/test_convergence_diagnosis.py` — unit tests for the reader and model.
  - `tests/fixtures/convergence/sample-report-history.json` — a committed single-file fixture describing a 3-run **spinning** completeness series (one medium+ region recurring without shrinking across all three runs), authored for step 2's detector tests to reuse verbatim.
- **Existing files (edits only):** none. This step adds files only.

> **Fixture-shape note.** The fixture is **one** JSON file, not three sidecars in a `reports/` tree. It encodes the already-normalized 3-run series (a small list of run dicts) so model-level tests can build `ReportHistory`/`RunSnapshot`/`RunFinding` from it directly without standing up a fake reports directory. Tests that exercise `load_report_history`'s disk-reading path instead write real `SavedReview` sidecars into a `tmp_path` reports dir via `review_persistence.save_review` (see Tests).

## Implementation

### Module placement — cycle-free leaf, top-level imports

- `plan_tool/convergence_diagnosis.py` imports from `plan_tool` only: `review_persistence` (`list_saved_reviews`, `load_review`, `ReviewLoadError`, `SavedReview`, `Annotation`), `review` (the `Recommendation` type, for annotations/typing), and `locator` (`slug_from_filename`). None of these import `convergence_diagnosis`, and none import `plan_tool.cli` — so place every import at module top. Do **not** body-localize; there is no cycle to remedy here.
- Do **not** import `plan_tool.convergence.is_blocking` in this step. The medium+ blocking threshold belongs to step 2's region/detector layer (a forward-deferred reuse). Step 1 loads **all** findings unfiltered; scoping happens later.
- Standard-library imports: `dataclasses` (`dataclass`, `field`), `datetime` (`datetime.fromisoformat`, to order runs), `pathlib.Path`, `typing`.

### `RunFinding` — the per-finding flattened record (frozen dataclass)

Carry only fields the saved JSON actually persists, drawn from each `Recommendation` plus its matching walk annotation:

- `id: str` — the content-addressed `Recommendation.id`.
- `source: str` — `Recommendation.source` (e.g. `plan-completeness`, `plan-correctness`, `detail-reconcile`). Kept raw; **not** filtered here.
- `severity: str` — `Recommendation.severity` (`critical|high|medium|nit|info`). Kept raw; the medium+ gate is step 2's.
- `step_id: Optional[int]` — `Recommendation.step_id`. **None for completeness findings** (`plan-completeness`/`plan-correctness` carry `step_id=None`); set only for per-step reconcile findings. Step 2/3 resolve the step a completeness finding is *about* by parsing its `anchor`, not this field.
- `anchor: Optional[str]` — `Recommendation.anchor` (the Claude-minted slug, e.g. `step5-over-pack`; None for sluggless/deterministic findings).
- `title: str` — `Recommendation.title`.

> **No `resolved` field.** `RunFinding` carries **no** per-finding resolved/closed flag. Closed-state is not a property of one finding in one run — it is a *sticky, series-wide, region-level* judgment (step 2) that reads each run's raw `Annotation` (`status == "skip"` **and** `halt_reason == ""`). An `applied`-yet-recurring finding is **unresolved** and *is* the spin signature the detector exists to catch, so a flag named after `applied` would invert the design's stance and mislead any future consumer. The raw closed-state inputs live on `RunSnapshot.annotations`; step 2 derives closed-state from there.

> **Whitelist source.** The field list above is the subset `RunFinding` carries; the JSON serializes more, but only the verdict is genuinely unpersisted. `Recommendation` carries more (`body`, `suggested_action`, `impact`, `complexity`, `redirect`, `file_path`), and the in-memory apply path carries a per-finding verdict (`BLOCKED`/`BLOCKED-STRUCTURAL`) — **none of the verdict reaches the JSON**, so `RunFinding` deliberately omits it. Model from what `save_review` writes, not from the richer runtime types. Both omissions (verdict, file byte sizes) are named in Deferred.

### `RunSnapshot` — one saved report (frozen dataclass)

One record per kept sidecar, built from a `SavedReview`:

- `kind: str` — `SavedReview.kind`. The discriminator that decides inclusion (see `HISTORY_KINDS`) and that step 2 partitions series on.
- `step_id: Optional[int]` — `SavedReview.step_id`. **None for completeness**, set for reconcile kinds. Step 2 keys reconcile series on `(kind, step_id)` so audits of *different* steps don't get compared as one recurring region.
- `created_at: str` — `SavedReview.created_at` (ISO-8601 UTC). Used to order the history.
- `plan_fingerprint: str` — `SavedReview.plan_fingerprint`. **`""` means unset** (matches the persistence sentinel); step 3's stability certificate must skip an all-`""` streak rather than treat it as evidence.
- `code_fingerprint: dict[str, str]` and `code_fingerprint_present: bool` — carried through verbatim; `code_fingerprint_present` (not dict truthiness) is the sentinel: `False` means never-computed, while `True` with an empty `code_fingerprint` dict means computed-but-no-watched-files.
- `report_bytes: int` — `len(SavedReview.report_md)`. The **only** on-disk growth proxy, since neither plan nor detail file byte sizes are persisted. Named, not invented.
- `findings: list[RunFinding]` — one `RunFinding` per `Recommendation` in this report.
- `annotations: dict[str, Annotation]` — `SavedReview.annotations` carried through **verbatim**, keyed by finding id. This is the **sole** carrier of closed-state inputs: step 2's sticky closed-state rule reads both `status == "skip"` **and** `halt_reason == ""` off the per-run `Annotation` (`snapshot.annotations.get(finding.id)`). The raw map must be retained because flattening to a per-finding bool would discard `halt_reason` and silently disable skip-suppression. Empty `{}` on the `--iterate`-only workflow (see Deferred).

### `ReportHistory` — the whole series for one plan (frozen dataclass)

- `plan_slug: str` — resolved once via `locator.slug_from_filename(plan_path)`. The default `default_to_stem=True` means this **never returns None** — no None-guard needed. Step 4's renderer reads `diagnosis.plan_slug` straight off the diagnosis (carried from here), so this is the single source for the slug.
- `plan_path: str` — the repo-relative/posix plan path the history was loaded for.
- `runs: list[RunSnapshot]` — **sorted oldest→newest by `created_at`** (ascending). `list_saved_reviews` returns newest-first; the M-of-N *trailing* window logic in steps 2–3 wants chronological order, so sort ascending here, once.

### `HISTORY_KINDS` — which kinds count

- Define `HISTORY_KINDS: frozenset[str] = frozenset({"completeness", "detail-reconcile", "run-reconcile"})`.
- **Excludes** the bare `kind="review"` reconcile-plan report (the suffixless `<timestamp>.json`). Filter on the parsed `SavedReview.kind` field, **not** the filename suffix — robust to any future rename of the file-naming scheme, and keeps one source for the directory layout.

### `load_report_history(plan_path: Path) -> ReportHistory` — the entry point

- **Resolve the slug**: `slug = slug_from_filename(plan_path)` (no None-guard).
- **List the sidecars**: call `list_saved_reviews(slug, repo_root, plan_path=plan_path)` where the leading `repo_root` positional is **vestigial and ignored** — pass any non-`None` placeholder (e.g. `plan_path` reused for convenience, with an inline `# repo_root: ignored` comment) and do **not** read it as a requirement that `repo_root` equal `plan_path`. The reports dir derives solely from the `plan_path` keyword (`<plan_path.parent>/plan-details/<slug>/reports/`). When the dir is absent, `list_saved_reviews` returns `[]` → an empty `ReportHistory` (no error).
- **Parse defensively**: loop the returned paths, `load_review(p)` inside a `try/except ReviewLoadError: continue` so one corrupt sidecar doesn't sink the whole read. Skip any loaded review whose `kind not in HISTORY_KINDS`.
- **Flatten**: build a `RunSnapshot` per kept review; build its `findings` as one `RunFinding` per `Recommendation`, and carry `SavedReview.annotations` through verbatim onto `RunSnapshot.annotations` for step 2's closed-state rule.
- **Order**: sort the snapshots ascending by `datetime.fromisoformat(created_at)`. Guard a malformed `created_at` by skipping that run (or sorting it last) rather than raising — keep the reader total.
- **Return** `ReportHistory(plan_slug=slug, plan_path=str(plan_path), runs=sorted_runs)`.

### Foundational logic & shared locations

- **Core behavior added:** "load this plan's saved reports off disk and flatten them into a normalized, chronologically-ordered cross-run model, keying inclusion on the typed `kind` and carrying each run's walk annotations through verbatim for step 2's closed-state rule."
- **Single on-disk parser already exists** — `plan_tool/review_persistence.py` (`list_saved_reviews` + `load_review`). This step **reuses** it rather than re-globbing; that is the one source for the reports-dir layout and the sidecar schema. Any other reader of saved reports should do the same — there is no second glob/parse to consolidate, and this step must not introduce one.

## Tests

All tests live in `tests/test_convergence_diagnosis.py` (new), are unmarked **unit** tests (hermetic, own `tmp_path`), and must be green before this step is done. Tests that drive the disk path write real sidecars with `review_persistence.save_review` into a `tmp_path` reports dir; model-shape tests load the committed fixture.

### Test-creation order (feature step)

Author these alongside the implementation; each new test must be green before the step is considered finished.

- `test_load_report_history_empty_when_no_reports_dir` — `load_report_history` on a plan whose reports dir is absent returns a `ReportHistory` with `runs == []` and the resolved `plan_slug` (no exception).
- `test_load_report_history_reads_saved_sidecars` — write two `completeness` sidecars via `save_review`, then load: two `RunSnapshot`s, each with its findings flattened from the persisted recommendations.
- `test_runs_sorted_oldest_to_newest` — write sidecars with out-of-order `created_at`, assert `runs` come back ascending by `created_at` (covers the reverse of `list_saved_reviews`' newest-first order).
- `test_kind_filter_excludes_bare_review` — write one `kind="review"` (suffixless) report alongside a `completeness` report; only the `completeness` run is kept (filtered on `kind`, not filename).
- `test_kind_filter_keeps_reconcile_kinds` — `detail-reconcile` and `run-reconcile` sidecars are kept; their `RunSnapshot.step_id` is preserved (not None).
- `test_completeness_finding_step_id_is_none` — a `plan-completeness` finding's `RunFinding.step_id` is None while its `anchor` carries the `step<N>-...` slug (pins that step 2 must parse the anchor).
- `test_annotations_carried_through_verbatim` — a sidecar with a `skip`/`halt_reason=""` annotation loads such that `RunSnapshot.annotations[id]` carries the raw `Annotation` (both `status` and `halt_reason`) intact, so step 2's closed-state rule has its inputs.
- `test_run_finding_omits_resolved` — `RunFinding` exposes no `resolved` attribute (guards the deliberate omission; e.g. `not hasattr(finding, "resolved")`).
- `test_report_bytes_is_len_report_md` — `RunSnapshot.report_bytes == len(report_md)` for the written sidecar.
- `test_corrupt_sidecar_is_skipped` — a malformed JSON sidecar in the dir is skipped (`ReviewLoadError` swallowed) and the valid runs still load.
- `test_run_finding_omits_verdict` — `RunFinding` exposes no per-finding apply-verdict attribute (guards the deliberate omission; e.g. `not hasattr(finding, "verdict")`).
- `test_fixture_loads_into_model` — `tests/fixtures/convergence/sample-report-history.json` deserializes into the 3-run spinning `ReportHistory` shape (3 runs, the recurring medium region present in each), proving the committed fixture matches the model step 2 will consume.

## Acceptance criteria

- `plan_tool/convergence_diagnosis.py` exists and exports `load_report_history`, `ReportHistory`, `RunSnapshot`, `RunFinding`, and `HISTORY_KINDS`.
- `load_report_history(plan_path)` on a plan with no reports dir returns `ReportHistory(plan_slug=<stem-derived slug>, runs=[])` and raises nothing.
- `load_report_history` skips a present-but-unparseable sidecar (one that raises `ReviewLoadError`) rather than propagating, so a single corrupt sidecar among valid ones is dropped and the valid runs still load (read-only diagnosis completes and exits 0).
- `load_report_history` returns `runs` sorted ascending by `created_at`, with `kind="review"` reports excluded and `completeness`/`detail-reconcile`/`run-reconcile` reports included.
- `RunSnapshot.annotations` carries each run's walk `Annotation` map through verbatim (raw `status` and `halt_reason` retained) as the sole closed-state input for step 2.
- `RunSnapshot.report_bytes == len(report_md)`; `RunSnapshot.plan_fingerprint`/`code_fingerprint` are carried through verbatim with `""`/`{}` preserved as the unset sentinels.
- `RunFinding` has no apply-verdict field and no `resolved` field; `RunFinding.step_id` is None for completeness findings.
- `tests/fixtures/convergence/sample-report-history.json` is committed and its test hand-maps directly into a 3-run spinning `ReportHistory`/`RunSnapshot`/`RunFinding` shape (not via `load_report_history`, which reads sidecars from a reports dir).
- `tests/test_convergence_diagnosis.py` passes under `uv run pytest tests/test_convergence_diagnosis.py -q`.

## References

- [json — JSON encoder and decoder (Python docs)](https://docs.python.org/3/library/json.html) — for the committed fixture's shape and for understanding what `load_review` defensively parses out of each sidecar.
- [datetime — Basic date and time types (Python docs)](https://docs.python.org/3/library/datetime.html) — `datetime.fromisoformat()` and its ISO-8601 limitations, needed to order `runs` by `created_at`.
- [glob — Unix style pathname pattern expansion (Python docs)](https://docs.python.org/3/library/glob.html) — background on the directory listing `review_persistence.list_saved_reviews` performs (this step reuses it rather than globbing directly).
- [How to use temporary directories and files in tests (pytest docs)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the `tmp_path` fixture used to write real sidecars and exercise the disk-reading path hermetically.

## Deferred

- **Region matching / cross-run identity** — grouping findings that are "the same problem re-flagged" (tiered step-focus → anchor → fuzzy-title key, `RegionTrend`) is **step 2**; this step lands the flat model only.
- **Medium+ / apply-eligible scoping** — `is_blocking` and `APPLY_ELIGIBLE_SOURCES` filtering belong to step 2's region builder (applied once there); step 1 loads findings unfiltered.
- **Spinning-vs-converging verdict and the four-state enum** — `diagnose_convergence`, recurrence/no-shrinkage, and the fingerprint-stable converging certificate are **steps 2–3**.
- **Localized-vs-structural fork and `plan-tool convergence` CLI** — the classifier and the read-only subcommand are **steps 3–4**.
- **Per-finding apply verdict** — `BLOCKED`/`BLOCKED-STRUCTURAL` is never written to the report JSON, so `RunFinding` cannot carry it; a structural-block signal must come from recurrence (step 3), not a structured field. Tracked as a producer-change if ever needed.
- **Plan/detail file byte sizes** — not persisted; `report_bytes = len(report_md)` is the only growth proxy. A real size signal would need a write-side producer change.
- **Granularity-split findings in history** — `cli/completeness_cmd.py` persists only `correctness_recs + conceptual_recs`; the granularity advisor's `smell_recs` (source `granularity-split`) are dropped before `save_review`, so they never reach this reader in v1. Any localized-fork path keyed on `granularity-split` is inert until a producer change lands.
- **Empty annotations on the `--iterate`-only workflow** — `write_completeness_report` persists empty annotations; only the interactive completeness-apply walk populates them. So `RunSnapshot.annotations` is `{}` for every run on the standard authoring workflow, and step 2's closed-state suppression is inert there — a producer-side limitation, not a reader bug, parked for a later producer change.
