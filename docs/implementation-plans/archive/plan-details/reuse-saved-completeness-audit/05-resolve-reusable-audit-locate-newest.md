> **Auto-archived**: this plan was swept on 2026-06-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Add `resolve_reusable_audit()` to locate, load, and freshness-check a saved completeness sidecar

## Summary

- Add `resolve_reusable_audit(plan_slug, repo_root, *, plan_path, review_id=None)` and a small `ReusableAudit` result dataclass to `plan_tool/completeness_report.py`. It locates the newest `-completeness.json` sidecar (or a specific one by `--reuse-audit-id` stem), loads it via `load_review`, recomputes **both** fingerprints against current disk, and returns the loaded `SavedReview`, its conceptual recs split by axis (`plan-correctness` vs `plan-completeness`), a `fresh: bool` (plan fingerprint match **AND** code fingerprint match), and `drifted_code: list[Path]` for the staleness warning step 6 renders.
- **Load-bearing decision:** this step is the **read/verdict** seam only — it reuses step 1's `compute_plan_fingerprint`, step 3's `compute_code_fingerprint`, and the existing `list_saved_reviews` locator rather than re-globbing or re-hashing. It computes a freshness verdict and a drift diff; it does **not** prompt, warn, or touch the CLI (that is step 6).
- **Deletion-aware diff:** unlike the live-edit `check_drift` (which ignores vanished files), the saved-vs-current diff reports **changed**, **deleted** (was hashed, now gone), and **new** (a `(new)` entry that has since landed) keys as drift — a vanished in-scope file across a save/reload boundary is a genuine staleness signal.
- **Observable result on green** — input → verdict:
  - unchanged plan + unchanged code → `fresh=True`, empty `drifted_code`.
  - plan edit → `fresh=False`, empty `drifted_code`.
  - code edit, deletion, or newly-landed `(new)` file → `fresh=False`, offending path in `drifted_code`.
  - missing sidecar → `None`.
  - legacy fingerprint-less sidecar → `fresh=False`.

## Table of Contents

- [Why](#why) — what the CLI reuse decision needs from a pure lookup+verdict helper.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two in-scope files and the edits per file.
- [Implementation](#implementation) — the `ReusableAudit` shape, sidecar location, both-fingerprint recompute, the deletion-aware diff, and the axis split.
- [Tests](#tests) — fresh / stale-by-plan / stale-by-code / deleted / new-landed / missing / pinned-by-id / legacy / axis-split cases.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — stdlib pathlib / sorted / dataclasses and the in-repo producers this step consumes.
- [Deferred](#deferred) — the CLI flags, prompt, and rendered warning left to step 6.

## Why

The reuse feature needs a single place that answers "is the newest saved completeness audit still valid, and which findings does it carry?" Steps 1–4 built the storage and population substrate: `SavedReview` now carries `plan_fingerprint` + `code_fingerprint` (step 1), `compute_plan_fingerprint(plan_path)` and `compute_code_fingerprint(plan, plan_path, repo_root)` produce the current-state digests (steps 1 and 3), and `_persist_and_present_report` writes both axes + both fingerprints into the sidecar (step 4). Nothing yet **reads** that sidecar back and computes a freshness verdict. Step 6's CLI reuse-decision helper needs exactly that verdict — plus the saved recs split by axis and the set of drifted code files — to decide whether to substitute saved findings for a fresh `audit_plan_until_stable` call and to render the attributed code-drift warning. This step lands that verdict helper as a pure, Claude-free function so step 6 stays thin wiring over it.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/completeness_report.py` — add the `ReusableAudit` dataclass and the `resolve_reusable_audit(...)` function; add top-level imports of `compute_plan_fingerprint`, `list_saved_reviews`, `load_review` (from `plan_tool.review_persistence`) and `parse_plan` (from `plan_tool.parser`). The `depends_on: 1, 3` edge sequences this step after the producers, but the step-1/step-3 symbols it consumes (`compute_code_fingerprint` in this module; `Plan` / `compute_drift_watched_paths` / `compute_content_hash` imports; the `SavedReview.plan_fingerprint` / `SavedReview.code_fingerprint` fields and the `save_review(..., plan_fingerprint=, code_fingerprint=)` kwargs) are **not present at HEAD** — confirm each one's exported name and arity in the actual source before consuming it here, rather than assuming the shape this body describes.
  - `tests/test_completeness_report.py` — add `resolve_reusable_audit` freshness/diff cases (approx. 11 tests).

## Implementation

### `plan_tool/completeness_report.py`

**New imports (top-level).** This module is already an assembly node (it imports `plan_tool.review`, `plan_tool.review_persistence`, and — from step 3 — `plan_tool.drift_detection` / `plan_tool.scope_guard` / `plan_tool.schema`), so adding these is cycle-free:
- `from plan_tool.review_persistence import compute_plan_fingerprint, list_saved_reviews, load_review` (extend the existing `review_persistence` import block that already pulls `_atomic_write_text`, `plan_reports_dir`, `save_review`).
- `from plan_tool.parser import parse_plan` — needed to obtain the `Plan` for `compute_code_fingerprint`. `parse_plan(path)` returns a `Plan` (`plan_tool/parser.py:parse_plan`).

**`ReusableAudit` dataclass.** Mirror the `AppliedOutcome` dataclass convention already in this file (`@dataclass`, terse field docstring):
- `saved: SavedReview` — the loaded sidecar (carries `report_md`, `recommendations`, `created_at`, `path`, and both fingerprints). `SavedReview` is imported transitively; add it to the `review_persistence` import if not already in scope.
- `correctness_recs: list[Recommendation]` — saved recs with `source == "plan-correctness"`.
- `conceptual_recs: list[Recommendation]` — saved recs with `source == "plan-completeness"`.
- `fresh: bool` — `plan_match and code_match` (defined below).
- `plan_match: bool` — saved `plan_fingerprint` is non-empty and equals the current plan fingerprint.
- `code_match: bool` — saved `code_fingerprint_present` is `True` (the fingerprint was computed, even if the map is empty) and the saved→current diff is empty.
- `drifted_code: list[Path]` — absolute, resolved, sorted paths whose code hash changed, that were deleted, or that newly landed. Empty when `code_match` is true.

Expose `plan_match` / `code_match` separately (not just `fresh`) so step 6 can tell plan-side staleness (empty `drifted_code`, a one-line note) from code-side staleness (`drifted_code` non-empty, the structured attributed warning).

**`resolve_reusable_audit(plan_slug, repo_root, *, plan_path, review_id=None) -> Optional[ReusableAudit]`.** (The architecture prose names the first arg `plan_name`; use `plan_slug` to match the `list_saved_reviews` / `resolve_saved_review` locators it delegates to.)

1. **Locate the sidecar — completeness-only.** Call `list_saved_reviews(plan_slug, repo_root, plan_path=plan_path)` (newest-first over `.json` files in `plan_reports_dir`). Filter to completeness sidecars by name: keep paths whose `name` ends with `-completeness.json` (the filename `write_completeness_report` → `save_review(kind="completeness")` produces via `_timestamp_filename`). This excludes `review` / `reconcile` sidecars in the same directory.
   - With `review_id` set: select the candidate whose `path.stem` equals `review_id` **or** `f"{review_id}-completeness"` (accept the bare timestamp stem or the full `<ts>-completeness` stem). Return `None` if none match — step 6 distinguishes "id given but unresolved" and surfaces the user error.
   - Without `review_id`: take the first (newest) completeness candidate. Return `None` when the filtered list is empty (no sidecar → fresh audit).
2. **Load it.** `saved = load_review(path)` — yields a `SavedReview` carrying `plan_fingerprint` / `code_fingerprint` (step 1). A malformed file raises `ReviewLoadError`; let it propagate (the caller already trusts on-disk sidecars it just listed).
3. **Recompute current fingerprints.**
   - `current_plan_fp = compute_plan_fingerprint(plan_path)` (step 1 — no `repo_root` arg; it derives the detail bundle from `plan_path.parent`).
   - `plan = parse_plan(plan_path)`; `current_code_fp = compute_code_fingerprint(plan, plan_path, repo_root)` (step 3 — a `{repo_rel_posix: sha256}` dict over `compute_drift_watched_paths`, missing files skipped).
4. **Plan verdict.** `plan_match = bool(saved.plan_fingerprint) and saved.plan_fingerprint == current_plan_fp`. Empty saved fingerprint (legacy/unset) → `False`.
5. **Code diff + verdict.** Compare `saved.code_fingerprint` (a `dict[str, str]`) against `current_code_fp`:
   - **legacy short-circuit:** when `not saved.code_fingerprint_present` (the fingerprint was never computed — legacy/unset), set `code_match = False` and `drifted_code = []` and skip the diff entirely — there is no baseline to diff against, so every current file would otherwise be a spurious `new` key flooding `drifted_code`. A computed-but-empty capture (`code_fingerprint_present == True`, empty map — a docs-only or all-`(new)` plan) does **not** short-circuit: it diffs normally, so it stays reusable on a plan-only match and only drifts if a watched file has since landed.
   - **changed:** key in both, hash differs.
   - **deleted:** key in saved, absent from current (file removed, or now unreadable so it dropped out of the current map).
   - **new:** key in current, absent from saved (a `(new)` file that was skipped at capture and has since landed).
   - `drifted_rel = changed | deleted | new` (set of repo-relative posix keys). `code_match = saved.code_fingerprint_present and not drifted_rel`. Never-computed (`code_fingerprint_present == False`) → `False`; a computed-but-empty map with an empty diff → `True`.
   - `drifted_code = sorted((repo_root / rel).resolve() for rel in drifted_rel)` — absolute resolved Paths so step 6's `build_file_to_step_map` (keyed by resolved absolute paths) and `render_attributed_path_line` attribute them without re-resolving. Sort for deterministic operator output.
6. **Axis split.** `correctness_recs = [r for r in saved.recommendations if r.source == "plan-correctness"]`; `conceptual_recs = [r for r in saved.recommendations if r.source == "plan-completeness"]`. Step 4 persists the union of both axes; this is the inverse split keyed on the `Recommendation.source` discriminator.
7. **Return** `ReusableAudit(saved=saved, correctness_recs=..., conceptual_recs=..., fresh=plan_match and code_match, plan_match=plan_match, code_match=code_match, drifted_code=drifted_code)`.

**Explicit `--audit-samples` detection (sentinel default).** Step 6's `_resolve_audit_reuse` reads `args.audit_samples` to honor the Architecture/step-6 policy that an explicitly passed `--audit-samples N` suppresses the `--yes` / non-TTY auto-accept and forces a fresh audit (the default count does not). argparse cannot distinguish the concrete int default (`AUDIT_DEFAULT_MAX_SAMPLES`) from an explicit pass, so the `completeness-audit` subparser registers `--audit-samples` with a **sentinel `default=None`** (resolving to `AUDIT_DEFAULT_MAX_SAMPLES` downstream): `args.audit_samples is not None` means explicit. The helper applies it as: explicit `--audit-samples` → suppress auto-accept, audit fresh; default (`None`) → no suppression; explicit `--reuse-audit` → overrides the suppression and reuses when fresh. This step only fixes the verdict; the sentinel default and the suppression read land in step 6.

**Foundational logic — saved-vs-current code-map diff.** The "changed/deleted/new key" set-diff over a `{path: hash}` map is the rule this step adds. It is deliberately **distinct** from `plan_tool/drift_detection.py:check_drift`, which diffs a live in-process snapshot and **ignores deletions** (a file vanishing mid-iteration is the apply loop's own churn there). Do not consolidate the two: the semantics differ (deletion-significant across a save/reload boundary vs deletion-ignored within a live lock). No other call site computes a saved-sidecar code diff today, so there is nothing to share; if a second consumer ever needs "diff two code-fingerprint maps," promote a small helper then — out of scope here.

## Tests

All cases in `tests/test_completeness_report.py`, hermetic on `tmp_path`, no Claude stubbed. Build sidecars by calling `save_review(..., kind="completeness", plan_fingerprint=<fp>, code_fingerprint=<map>)` directly (step 1 added those kwargs), so the suite does not depend on step 3's caller wiring. Build the `code_fingerprint` map with the real `compute_code_fingerprint(plan, plan_path, repo_root)` (step 3) over a plan whose `step.files` point at a code file written under `tmp_path` (reuse step 3's `compute_code_fingerprint` plan-writing pattern, or the code-bearing-plan fixtures in `tests/test_scope_guard.py` / `tests/test_drift_detection.py`). Set `plan_fingerprint` with `compute_plan_fingerprint(plan_path)`.

- `test_resolve_reusable_audit_fresh` — unchanged plan + code after save → `fresh is True`, `plan_match`/`code_match` True, `drifted_code == []`.
- `test_resolve_reusable_audit_stale_by_plan` — edit a per-step detail file (or plan body) after save → `plan_match is False`, `fresh is False`, `drifted_code == []`.
- `test_resolve_reusable_audit_stale_by_code` — rewrite an in-scope `step.files` code file after save → `code_match is False`, `fresh is False`, that file's resolved abs path in `drifted_code`.
- `test_resolve_reusable_audit_deleted_in_scope_file` — delete a code file present in the saved map → its path in `drifted_code`, `fresh is False` (proves deletions are reported, unlike `check_drift`).
- `test_resolve_reusable_audit_new_file_landed` — a `(new)` entry absent at capture (skipped from the saved map), then created before resolve → reported in `drifted_code` as new, `fresh is False`.
- `test_resolve_reusable_audit_missing_returns_none` — no sidecar in the reports dir → returns `None`.
- `test_resolve_reusable_audit_picks_newest_completeness` — two completeness saves (distinct `now=`), plus a non-completeness `review` save → picks the newest `-completeness.json`, ignoring the `review` sidecar.
- `test_resolve_reusable_audit_pinned_by_id` — two completeness saves; `review_id=<older stem>` resolves the older one; accepts both the bare-timestamp and `<ts>-completeness` stem forms.
- `test_resolve_reusable_audit_pinned_id_missing_returns_none` — `review_id` with no match → `None`.
- `test_resolve_reusable_audit_legacy_sidecar_is_stale` — sidecar saved with `plan_fingerprint=""` and a never-computed code fingerprint (`code_fingerprint_present == False`) → `plan_match`/`code_match`/`fresh` all False, `drifted_code == []`.
- `test_resolve_reusable_audit_computed_empty_code_fingerprint_reusable` — sidecar saved for a docs-only / all-`(new)` plan with a computed-but-empty code fingerprint (`code_fingerprint_present == True`, empty map) and an unchanged plan → `code_match`/`fresh` True, `drifted_code == []` (gating on the marker, not dict-truthiness, so the empty-but-present capture still reuses).
- `test_resolve_reusable_audit_axis_split` — saved recs mixing `plan-correctness` and `plan-completeness` sources → `correctness_recs` and `conceptual_recs` partition them with no overlap or loss.

### Test-creation order (feature step)

Feature step — author the unit tests **with** the implementation. Each new test must be green before the step is considered finished. Build sidecars via `save_review` + the real fingerprint producers; assert verdicts and the `drifted_code` set on the returned `ReusableAudit`.

## Acceptance criteria

- `resolve_reusable_audit(plan_slug, repo_root, plan_path=p)` returns `None` when no `-completeness.json` sidecar exists under `plan_reports_dir(p)`.
- For an unchanged plan + unchanged code, it returns a `ReusableAudit` with `fresh is True` and `drifted_code == []`.
- Editing the plan or any per-step detail file flips `plan_match` (and `fresh`) to `False` with `drifted_code == []`.
- Editing, deleting, or newly creating a `(new)` in-scope `step.files` code file flips `code_match` (and `fresh`) to `False` and lists that file's resolved absolute path in `drifted_code` (sorted).
- A legacy sidecar (`plan_fingerprint == ""`, `code_fingerprint_present == False`) yields `fresh is False` (a never-computed fingerprint is stale), not an error; a computed-but-empty code fingerprint (`code_fingerprint_present == True`, empty map) on an unchanged plan yields `code_match`/`fresh` True — the verdict gates on the presence marker, never on `code_fingerprint` dict-truthiness.
- `review_id` pins a specific completeness sidecar by stem (bare `<ts>` or `<ts>-completeness`); a non-matching id returns `None`.
- `correctness_recs` / `conceptual_recs` partition `saved.recommendations` by `source` with no item lost or duplicated.
- An explicitly passed `--audit-samples N` is distinguishable from the default sample count via the sentinel (`None`) default and suppresses the `--yes` / non-TTY reuse auto-accept (forcing a fresh audit); the default sample count does not suppress reuse, and an explicit `--reuse-audit` overrides the suppression and reuses when fresh.
- The function issues zero Claude calls and reads only from disk.
- All ~11 new tests in `tests/test_completeness_report.py` pass under `uv run pytest tests/test_completeness_report.py -q`.

## References

- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — `Path.stem` / `Path.name` for the completeness-sidecar name filter and id match, and `(repo_root / rel).resolve()` for the `drifted_code` absolute paths.
- [sorted() — Built-in functions](https://docs.python.org/3/library/functions.html#sorted) — deterministic ordering of `drifted_code` for stable operator output regardless of set iteration order.
- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — the `ReusableAudit` result record (mirrors the existing `AppliedOutcome` dataclass shape).
- `plan_tool/review_persistence.py` (in-repo) — `list_saved_reviews` (newest-first sidecar locator) and `load_review` (sidecar → `SavedReview` with both fingerprints) consumed here; `compute_plan_fingerprint` is a step-1 addition to this module, not present at HEAD.
- `plan_tool/scope_guard.py` / `plan_tool/drift_detection.py` (in-repo) — `compute_drift_watched_paths` underpins `compute_code_fingerprint`; `build_file_to_step_map` + `render_attributed_path_line` consume `drifted_code` in step 6 (this step only produces the resolved-absolute paths they expect).

## Deferred

- CLI flags `--reuse-audit` / `--no-reuse-audit` / `--reuse-audit-id`, the interactive prompt, and the reuse-decision helper — step 6 (`plan_tool/cli/completeness_cmd.py`).
- Rendering the attributed code-drift warning from `drifted_code` (via `render_attributed_path_line` + `build_file_to_step_map`) and the `detail --reconcile` recovery hint — step 6; this step only returns the path set and the `code_match` flag.
- Distinguishing "explicit `--reuse-audit-id` miss" (user error) from "no sidecar" — both return `None` here; step 6 owns the user-facing error when an id was explicitly passed.
- A shared "diff two code-fingerprint maps" helper — only one consumer exists today; promotion waits for a second, per the no-premature-consolidation rule.
