> **Auto-archived**: this plan was swept on 2026-06-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add `plan_tool/grounding.py`: a tracked grounding sidecar + a pure code-drift check

## Summary

- **Add `plan_tool/grounding.py`**, a persistence-plus-pure-logic leaf that reads/writes a single tracked `grounding.json` sidecar (the `compute_code_fingerprint` code map + the `compute_plan_fingerprint` plan digest + an ISO-8601 UTC timestamp) and exposes a pure `check_grounding_drift` that diffs a stored code map against the current one.
- **Primary files:** `plan_tool/grounding.py` (new) and `tests/test_grounding.py` (new). No existing files change.
- **Load-bearing decision:** the sidecar is **one deterministic file** at `<plan-dir>/plan-details/<slug>/grounding.json` (overwritten on each grounding, never timestamped/accumulated) and it is a `.json` file, so `plan_tool/review_persistence.py:compute_plan_fingerprint`'s non-recursive `*.md` glob never folds it into the plan digest — the sidecar can be re-stamped without perturbing the very fingerprint it stores.
- **`check_grounding_drift` delegates to `plan_tool/fingerprint.py:diff_code_fingerprint`** (added by step 1, `depends_on: 1`) — it mints no new diff logic, returning the same `(code_match, drifted_code)` pair, so the drift gate stays single-sourced.
- **On green:** a grounded plan round-trips its code map + plan digest + timestamp; `read_grounding` returns `None` (never raises) for an absent/malformed/old-schema sidecar so a pre-feature plan reads as "needs grounding"; and `check_grounding_drift` reports `(True, [])` on an unchanged tree and the exact changed absolute paths on drift — with zero Claude involvement.

## Table of Contents

- [Why](#why) — what grounding persistence buys and why it's a standalone leaf
- [Files (creates vs edits)](#files-creates-vs-edits) — the new module and its test file
- [Implementation](#implementation) — the sidecar path, the `Grounding` record, read/write fail-soft posture, the pure drift check
- [Tests](#tests) — round-trip, fail-soft reads, drift cases, and the plan-digest non-perturbation guard
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer/CI can check
- [References](#references) — hashlib / json / pytest monkeypatch docs for this step's surfaces
- [Deferred](#deferred) — stamping wiring, the refresh entry point, the atomic-write extraction threshold

## Why

- **The refresh feature needs a place to record "the code state this plan was last grounded against," and that fact must travel with the plan** through PR/merge and diff in review. Per the plan's *Where the grounding fingerprint lives* decision, this is a **tracked** artifact (the deliberate contrast with the branch-awareness plan's untracked per-clone binding). A dedicated sidecar avoids editing the plan markdown on every grounding (frontmatter churn) while staying committed alongside the plan's detail files.
- **The drift gate has no home yet.** `plan_tool/fingerprint.py:compute_code_fingerprint` produces the code map and step 1's `diff_code_fingerprint` does the deletion-aware diff, but nothing persists a baseline map to diff *against* across save/reload. This step is that persistence layer plus the thin pure check that wires the stored baseline into the existing diff.
- **Keeping persistence + the pure check in one small leaf** lets step 3's `plan_tool/refresh.py` and step 5's authoring stamp consume one module without pulling in the reconcile engine, and keeps the no-Claude drift decision unit-testable in isolation (the plan's *Testing* requirement).

## Files (creates vs edits)

- **New files:**
  - `plan_tool/grounding.py` — the `Grounding` dataclass, `grounding_path`, `write_grounding`, `read_grounding`, and `check_grounding_drift`, plus module-private `GROUNDING_FILENAME` / `GROUNDING_SCHEMA_VERSION` constants and an inlined `_atomic_write_text`.
  - `tests/test_grounding.py` — unit coverage for the round-trip, the fail-soft read paths, the drift cases, the timestamp format, and the plan-digest non-perturbation guard.
- **Existing files (edits only):** none. The stamping call sites (`plan_tool/cli/authoring.py`) and the CLI/refresh wiring are explicitly later steps (5 / 3-4) — see [Deferred](#deferred).

## Implementation

### Module placement and imports

- **`plan_tool/grounding.py` sits above `plan_tool/fingerprint.py`** and uses only the stdlib for persistence. Import `diff_code_fingerprint` **function-locally inside `check_grounding_drift`** (mirroring `plan_tool/review_persistence.py`'s local `from plan_tool.locator import slug_from_filename`) so the read/write path stays import-light — `read_grounding`/`write_grounding` pull in no diff machinery (and the `fingerprint.py → scope_guard.py → launcher.py` chain they would reach) at import time.
- Import `slug_from_filename` **function-locally inside `grounding_path`**, matching `plan_tool/review_persistence.py:plan_reports_dir` / `compute_plan_fingerprint`.
- Module-level stdlib imports: `contextlib`, `json`, `os`, `tempfile`, `dataclasses` (`asdict`, `dataclass`, `field`), `datetime` (`datetime`, `timezone`), `pathlib.Path`, `typing.Optional`.

### The sidecar path — `grounding_path(plan_path: Path) -> Path`

- **Return `<plan_path.parent>/plan-details/<slug>/grounding.json`**, where `slug = slug_from_filename(plan_path)` (`default_to_stem=True`, so never `None` — `assert slug is not None`). This deliberately reuses the directory `plan_tool/review_persistence.py:plan_reports_dir` anchors to (`<plan-dir>/plan-details/<slug>/`), making the grounding sidecar a sibling of the `reports/` subdir.
- **Module constant `GROUNDING_FILENAME = "grounding.json"`.** One fixed filename — not a timestamped name like `review_persistence.py:_timestamp_filename` produces — so each grounding **overwrites** the prior one and the file never accumulates. Re-grounding is a single in-place rewrite, which is what makes the tracked artifact diff cleanly in review.
- **Load-bearing non-perturbation:** `plan_tool/review_persistence.py:compute_plan_fingerprint` hashes the plan markdown plus `bundle_dir.glob("*.md")` **non-recursively**. A `grounding.json` is not `*.md`, so the glob never matches it. So writing/re-stamping the sidecar **cannot** change the `plan_fingerprint` it stores — pinned by a test below.

### The record — `Grounding`

- **A `@dataclass`** with fields mirroring the relevant `plan_tool/review_persistence.py:SavedReview` naming so the two records read consistently:
  - `plan_slug: str`
  - `grounded_at: str` — ISO-8601 UTC with trailing `Z` (e.g. `"2026-06-16T12:34:56Z"`), same format `review_persistence.py:_utc_now_iso` emits.
  - `plan_fingerprint: str` — the `compute_plan_fingerprint` digest; `""` is the unset sentinel.
  - `code_fingerprint: dict[str, str]` — the `compute_code_fingerprint` `{repo-relative-posix-path: sha256-hex}` map, stored verbatim and opaque (this module never recomputes or interprets it, matching `SavedReview.code_fingerprint`).
  - `schema_version: int = GROUNDING_SCHEMA_VERSION` (`GROUNDING_SCHEMA_VERSION = 1`).
- **No `code_fingerprint_present` marker** is needed: an absent sidecar already means "never grounded" (`read_grounding` returns `None`), so the `{}`-is-ambiguous problem `SavedReview` solves with a present flag does not arise here. State this as a deliberate divergence from `SavedReview`.

### Write — `write_grounding(plan_path, *, plan_fingerprint, code_fingerprint, now=None) -> Path`

- **Derive `plan_slug` internally** via `slug_from_filename(plan_path)` rather than accepting it as a parameter — single-sources the slug from the same place `grounding_path` does, so the stored `plan_slug` can never disagree with the file location.
- **`grounded_at`** = `now.strftime("%Y-%m-%dT%H:%M:%SZ")` when `now` is supplied (injectable for deterministic tests, matching `save_review`'s `now` param), else `datetime.now(timezone.utc).strftime(...)`.
- **`mkdir(parents=True, exist_ok=True)`** on the sidecar's parent before writing (the `plan-details/<slug>/` dir usually exists from detail files, but be safe).
- **Serialize** `asdict(Grounding(...))` as `json.dumps(payload, indent=2) + "\n"` and write via the inlined `_atomic_write_text` (tempfile + `os.fsync` + `os.replace`, byte-identical to `plan_tool/review_persistence.py:_atomic_write_text`). Return the absolute sidecar path.
- **Inline `_atomic_write_text` is the third *shape*-match copy** (the existing two are `plan_tool/review_persistence.py:_atomic_write_text` and `plan_tool/lessons.py:_atomic_write_text`, which materially differ — `lessons.py` uses `mkstemp`/`os.fdopen`, no `os.fsync`, `except Exception`, and mkdirs the parent; `review_persistence.py` uses `NamedTemporaryFile`+`os.fsync`+`except BaseException`+`contextlib.suppress`, no mkdir — so copy `review_persistence.py`'s fsync variant here) and the **fourth atomic-write *call site* overall**, counting the divergent-signature `plan_tool/cli/console.py:_atomic_write` (which is not a shape match). Per the convention documented in `review_persistence.py`'s docstring — *"no shared atomic_write_json helper until a fourth call site appears"* — inlining here is correct and the extraction is explicitly deferred (the fourth call site is now the trigger). See [Deferred](#deferred).

### Read — `read_grounding(plan_path: Path) -> Optional[Grounding]`

- **Fail-soft to `None`** — the deliberate divergence from `plan_tool/review_persistence.py:load_review`, which *raises* `ReviewLoadError`. The plan's *Stale/absent fingerprint* risk mandates "treat as needs grounding, never crash on the missing field," so every degenerate case returns `None`:
  - sidecar absent (no file at `grounding_path`)
  - unreadable / malformed JSON (`OSError`, `json.JSONDecodeError`)
  - top-level not a dict
  - `schema_version` absent or `!= GROUNDING_SCHEMA_VERSION`
  - a required field missing or wrong-typed (`KeyError`/`TypeError` constructing `Grounding`)
- **On success**, return a `Grounding` populated from the payload (`code_fingerprint` defaulting to `{}`, `plan_fingerprint` to `""`, `plan_slug`/`grounded_at` required). A caller (step 3) reading `None` runs reconcile unconditionally; a caller reading a `Grounding` proceeds to the drift check.

### The pure drift check — `check_grounding_drift(grounding, current_code_fp, repo_root) -> tuple[bool, list[Path]]`

- **Signature:** `check_grounding_drift(grounding: Grounding, current_code_fp: dict[str, str], repo_root: Path) -> tuple[bool, list[Path]]`.
- **Body is one delegating line:** `from plan_tool.fingerprint import diff_code_fingerprint` (local), then `return diff_code_fingerprint(grounding.code_fingerprint, current_code_fp, repo_root)`. It mints no diff logic — the deletion-aware `changed | deleted | new` map-diff is owned solely by step 1's helper.
- **The caller supplies `current_code_fp`** (computed via `plan_tool/fingerprint.py:compute_code_fingerprint`); this module never walks the repo, keeping it pure dict-in. Returned `drifted_code` paths are absolute, resolved under `repo_root.resolve()`, and sorted — exactly the key shape `plan_tool/scope_guard.py:build_file_to_step_map` attributes against, so step 3 can scope reconcile to the drifted files with no re-resolution.
- **Code axis only.** `grounding.plan_fingerprint` is stored and travels with the sidecar but is **not** consulted here — the refresh gate's question is "did the code drift since grounding," and the plan-side digest feeds the reconcile engine's own reuse machinery (`SavedReview.plan_fingerprint`), not this gate. Call this out so a later reader doesn't fold a plan-digest comparison into the code-drift check.

### Shared-logic scan

- **Foundational logic:** persist-and-reload of a `{code map + plan digest + timestamp}` record, plus a pure stored-vs-current code-map drift check.
- **The map-diff itself** lives only in `plan_tool/fingerprint.py:diff_code_fingerprint` after step 1 — `check_grounding_drift` reuses it, adding no parallel copy.
- **Atomic JSON write** appears in `plan_tool/review_persistence.py:_atomic_write_text` and `plan_tool/lessons.py:_atomic_write_text` (near-copies — they differ in tempfile API, `os.fsync`, exception breadth, and mkdir) and a divergent-signature `plan_tool/cli/console.py:_atomic_write`. This step adds the third near-copy under the documented "extract at the fourth" rule; consolidating the three into one shared helper is a cross-module refactor `detail` cannot mint — routed to [Deferred](#deferred).
- **Sidecar-path derivation** parallels `plan_tool/review_persistence.py:plan_reports_dir` (same `<plan-dir>/plan-details/<slug>/` anchor); `grounding_path` is a sibling, not a duplicate — it returns a single file, not the `reports/` directory.

## Tests

All tests live in `tests/test_grounding.py`, are hermetic (`tmp_path`), and invoke **no** Claude (no invoker seam is touched — this module never shells out).

### Test-creation order (feature step)

This is a **feature** step. Add every test below **with** the implementation; all must be green before the step is considered finished.

- `test_grounding_path_is_sidecar_under_plan_details` — `grounding_path` returns `<plan-dir>/plan-details/<slug>/grounding.json` for a numeric-prefixed plan filename (slug strips the `<digit>-` prefix).
- `test_write_then_read_round_trips` — `write_grounding` then `read_grounding` yields a `Grounding` whose `code_fingerprint`, `plan_fingerprint`, `grounded_at`, `plan_slug`, and `schema_version` equal what was written.
- `test_write_returns_sidecar_path` — the path `write_grounding` returns is `grounding_path(plan_path)` and the file exists on disk.
- `test_second_write_overwrites_in_place` — a second `write_grounding` replaces the file (no second/timestamped file appears in the directory); the reloaded record reflects the second write.
- `test_write_creates_missing_parent_dirs` — writing under a not-yet-existing `plan-details/<slug>/` succeeds.
- `test_grounded_at_is_iso_utc_z` — with an injected `now`, `grounded_at` equals `now.strftime("%Y-%m-%dT%H:%M:%SZ")` (trailing `Z`, no microseconds).
- `test_read_absent_returns_none` — no sidecar on disk → `None`.
- `test_read_malformed_json_returns_none` — non-JSON bytes → `None` (never raises).
- `test_read_wrong_schema_version_returns_none` — a payload with `schema_version = 999` → `None`.
- `test_read_missing_required_field_returns_none` — a payload lacking `code_fingerprint` (or `plan_slug`) → `None`.
- `test_check_drift_unchanged_matches` — stored map == current map → `(True, [])`.
- `test_check_drift_changed_file_reports_absolute_path` — one differing digest → `(False, [<repo_root>/<rel>])`, the path absolute and resolved.
- `test_check_drift_deletion_aware` — a key present in the stored map, absent from current → `code_match=False` (delegated deletion-awareness).
- `test_check_drift_new_file` — a key in current absent from stored → drift.
- `test_check_drift_drifted_code_sorted_and_absolute` — combined changed+deleted+new → all paths absolute under `repo_root.resolve()` and sorted (the shape `build_file_to_step_map` keys on).
- `test_grounding_json_excluded_from_plan_fingerprint` — `plan_tool/review_persistence.py:compute_plan_fingerprint(plan_path)` returns the same digest before and after `write_grounding`, pinning that the `.json` sidecar never folds into the plan digest.

## Acceptance criteria

- `plan_tool/grounding.py` exists exporting `Grounding`, `grounding_path`, `write_grounding`, `read_grounding`, `check_grounding_drift`, with `GROUNDING_FILENAME == "grounding.json"` and `GROUNDING_SCHEMA_VERSION == 1`.
- `grounding_path(Path("docs/implementation-plans/2-foo.md"))` ends in `plan-details/foo/grounding.json`.
- `write_grounding(...)` then `read_grounding(...)` reproduces the stored `code_fingerprint`, `plan_fingerprint`, `grounded_at`, and `plan_slug` exactly.
- `read_grounding` returns `None` (raises nothing) for an absent file, malformed JSON, a mismatched `schema_version`, and a missing required field.
- `check_grounding_drift(g, current_fp, root)` returns `(True, [])` when `g.code_fingerprint == current_fp`, and `(False, [<absolute resolved paths sorted>])` otherwise, matching `plan_tool/fingerprint.py:diff_code_fingerprint`'s output for the same inputs.
- `compute_plan_fingerprint` of a plan is byte-identical before and after a `write_grounding` call.
- `plan_tool/grounding.py` imports nothing from the reconcile engine / CLI; its only first-party dependencies are `plan_tool.fingerprint` (function-local) and `plan_tool.locator.slug_from_filename` (function-local).
- `uv run pytest -m "not integration" tests/test_grounding.py -q` is green.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — the SHA-256 hexdigests this module stores and compares verbatim (it never recomputes them); confirms equal bytes ⟺ equal digest.
- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — `dumps(..., indent=2)` for the sidecar payload and the `JSONDecodeError` that `read_grounding` swallows into `None`.
- [tempfile — Generate temporary files and directories](https://docs.python.org/3/library/tempfile.html) and [os.replace](https://docs.python.org/3/library/os.html#os.replace) — the atomic tempfile-then-replace write the inlined `_atomic_write_text` performs.
- [datetime — Basic date and time types](https://docs.python.org/3/library/datetime.html) — `datetime.now(timezone.utc)` and `strftime` for the ISO-8601 `Z` timestamp.
- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — for the `now`-injection / no-real-clock test discipline, and to confirm (in step 3's wiring) the invoker is never spawned on the no-drift path.

## Deferred

- **Stamping the grounding fingerprint after `create`/`detail`** — `plan_tool/cli/authoring.py` wiring is step 5; this step only provides `write_grounding`.
- **The refresh entry point + `reconcile-plan --refresh` surface** — `plan_tool/refresh.py` (step 3) and the CLI/help wiring (step 4) consume `read_grounding` / `check_grounding_drift`; not in this step's footprint.
- **A plan-side staleness gate over `plan_fingerprint`** — stored here but intentionally not part of `check_grounding_drift`; if plan-digest drift ever needs gating it belongs to the reconcile engine's reuse path, not this leaf.
- **Extracting a shared `atomic_write_json` helper** — this is the third `_atomic_write_text` near-copy (after `plan_tool/review_persistence.py` and `plan_tool/lessons.py`, which themselves diverge); the documented threshold is a fourth call site, which this now reaches — track the extraction as a follow-up refactor reconcile can pick up.
- **Widened watched surface (shared-file sweep) and normalized/whitespace-insensitive hashing** — plan-level deferrals; the code map is exactly `compute_code_fingerprint`'s declared surface with whole-file hashing.
