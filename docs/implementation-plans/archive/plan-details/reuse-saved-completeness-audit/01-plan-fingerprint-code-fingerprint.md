> **Auto-archived**: this plan was swept on 2026-06-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add `plan_fingerprint` + `code_fingerprint` to `SavedReview` and a `compute_plan_fingerprint` helper

## Summary

- Widen `SavedReview` in `plan_tool/review_persistence.py` with three new persisted fields — `plan_fingerprint: str` (a deterministic SHA-256 over the plan markdown + its detail bundle), `code_fingerprint: dict[str, str]` (an **opaque** path→hash map the caller supplies), and `code_fingerprint_present: bool` (an explicit marker distinguishing a never-computed code fingerprint from a computed-but-empty one) — plus a `compute_plan_fingerprint(plan_path)` helper that computes the plan-side digest.
- Wire both fields through the three serialization seams: `save_review` writes them into the JSON payload, `load_review` reads them with `.get(...)` defaults (legacy tolerance), and `update_annotation` preserves them on annotation write-back.
- **Load-bearing decision:** `SCHEMA_VERSION` stays `1` and the new keys ride inside the existing v1 payload as optional keys — exactly the additive pattern `kind`/`step_id` already use. Bumping the version would make `load_review`'s strict `version != SCHEMA_VERSION` gate reject every pre-existing saved file.
- **Second load-bearing decision:** `code_fingerprint` is stored verbatim as a `dict[str, str]`, never computed here — keeping `review_persistence.py` a leaf that imports only `plan_tool.review` (no `scope_guard` / `drift_detection` edge). The downstream consuming step computes the code surface and passes the dict in.
- On green: a saved review round-trips both fingerprints and the presence marker; a legacy sidecar lacking them loads with `plan_fingerprint == ""`, `code_fingerprint == {}`, and `code_fingerprint_present == False`; a computed-but-empty code fingerprint round-trips as `code_fingerprint == {}` with `code_fingerprint_present == True`; `compute_plan_fingerprint` returns a stable hex digest that changes iff a plan or detail byte (or the detail file set) changes.

## Table of Contents

- [Why](#why) — what reuse needs from the persistence layer and why it lands first.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two in-scope files and the edits per file.
- [Implementation](#implementation) — field additions, helper design, and the three serialization seams.
- [Tests](#tests) — round-trip, legacy-tolerance, opacity, and digest-sensitivity cases.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — stdlib docs for hashlib / dataclasses / json / pathlib.
- [Deferred](#deferred) — code-fingerprint computation left to later steps; the streamed-hash copy is a permanent leaf-preserving duplication, not deferred.

## Why

The "Reuse Saved Completeness Audit" feature decides whether a previously-saved audit is still valid by comparing the plan and code state captured at save time against current state. That comparison needs a stored fingerprint on each saved review, but `SavedReview` and its JSON payload carry no such field today — `plan_tool/review_persistence.py:SavedReview` stops at `kind`/`step_id`. This step adds the storage substrate (both fingerprint axes) and the plan-side compute helper so later steps can populate the fields at save time and read them back at reuse time. It lands first because every downstream step (the reuse toggle, the staleness warning, the lookup helper) consumes these fields.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review_persistence.py` — add `plan_fingerprint` + `code_fingerprint` + `code_fingerprint_present` fields to `SavedReview`; add `compute_plan_fingerprint`; thread all three fields through `save_review`, `load_review`, and `update_annotation`.
  - `tests/test_review_persistence.py` — add round-trip, legacy-tolerance, present-marker, opacity, and digest-sensitivity cases (approx. 11 tests).

## Implementation

### `plan_tool/review_persistence.py`

**`SavedReview` dataclass — three new defaulted fields.**
- Add after `step_id` (all trailing fields already carry defaults):
  - `plan_fingerprint: str = ""` — the plan-side digest from `compute_plan_fingerprint`; empty string is the "unset / legacy" sentinel.
  - `code_fingerprint: dict[str, str] = field(default_factory=dict)` — opaque path→hash map. `field` is already imported. `{}` is **ambiguous on its own**: it is both a legacy/unset sidecar and a valid sidecar for a plan whose watched-code surface is legitimately empty (docs-only plans, or pre-implementation plans whose `step.all_files` are all not-yet-created `(new)` files). Emptiness alone must therefore never be read as "unset" — that is what `code_fingerprint_present` is for.
  - `code_fingerprint_present: bool = False` — explicit marker disambiguating the two `{}` states: `False` = the code fingerprint was never computed (legacy/unset → stale), `True` = it was computed (even when the resulting map is empty because the watched-code surface has no extant files → a valid, reusable capture). Downstream freshness logic gates on this marker, never on `code_fingerprint` truthiness, so a pre-implementation plan can still reuse its audit on a plan-only match.
- All default-valued, so legacy sidecars constructed via `load_review` without these keys deserialize cleanly (same mechanism the dataclass already relies on for `annotations`).
- Document in the docstring that `code_fingerprint` is **opaque to this module** — keys/values are caller-defined (a relative-path string → content-hash hex), and this module never interprets, validates, or recomputes it. State the leaf-preservation rationale: storing it as plain data is what keeps `review_persistence.py` free of a `scope_guard` / `drift_detection` import.

**`compute_plan_fingerprint(plan_path: Path) -> str` — new module-level helper.**
- **Purpose:** deterministic SHA-256 hex digest over the plan markdown file plus every detail file in its bundle. This is the *plan-side* axis only; the code axis is the caller-supplied `code_fingerprint`.
- **Detail bundle location:** mirror `plan_reports_dir` — the bundle is `<plan_path.parent>/plan-details/<slug>/*.md`, where `<slug>` comes from `plan_tool.locator.slug_from_filename` (already lazily imported inside `plan_reports_dir`; import it the same lazy way to avoid widening the module's top-level imports). The conventional detail-file layout is `derive_detail_path` in `plan_tool/detail.py` (`plan-details/<slug>/<NN>-<step_slug>.md`); the `reports/` subdir is excluded by globbing `*.md` at the bundle root, not recursively.
- **Determinism:** enumerate detail files with `Path.glob("*.md")` then `sorted(...)` by name so filesystem enumeration order never perturbs the digest (the `sorted()` plan-level reference). Feed into one `hashlib.sha256()`:
  1. the plan file's bytes,
  2. then, for each sorted detail file, its **name** followed by its bytes.
- **Include the filename in the hash**, not just content — so adding, removing, or renaming a detail file changes the digest even when the surviving files' bytes are unchanged. Use a fixed length-or-separator framing (e.g. hash `name.encode()` then a `b"\0"` delimiter then content) so concatenation is unambiguous.
- **Missing-file tolerance:** a non-existent plan file or unreadable detail contributes a fixed sentinel (e.g. skip with a recorded marker) rather than raising — matches `_compute_content_hash`'s "return None / skip silently" posture in `plan_tool/drift_detection.py`. Stream reads in 64 KB chunks, mirroring `_compute_content_hash`, so a large plan or detail bundle never spikes memory.
- **Signature:** take `plan_path: Path` only — the bundle dir derives from `plan_path.parent`, so no `repo_root` is needed. `plan_path` may be absolute or repo-relative; resolve the bundle dir relative to whatever is passed (callers hand it the absolute plan path, the same one `save_review` already resolves via `_abs_plan_path`).

**`save_review` — persist both fields.**
- Add keyword params `plan_fingerprint: str = ""` and `code_fingerprint: Optional[dict[str, str]] = None`.
- Add three keys to the `payload` dict: `"plan_fingerprint": plan_fingerprint`, `"code_fingerprint": code_fingerprint or {}`, and `"code_fingerprint_present": code_fingerprint is not None`. The `None` param sentinel records "never computed" (`present = False`); a caller passing `{}` — a computed-but-empty watched-code surface — sets the marker `True`. Presence is derived from the param sentinel, so callers never pass the marker explicitly.
- No `SCHEMA_VERSION` change — keep `version: SCHEMA_VERSION` (= 1). The keys are additive within v1.

**`load_review` — read with legacy tolerance.**
- After the existing `kind`/`step_id` reads, pull `plan_fingerprint = data.get("plan_fingerprint", "")`, `code_fingerprint = data.get("code_fingerprint", {})`, and `code_fingerprint_present = data.get("code_fingerprint_present", False)`. A legacy file lacking the marker key defaults to `False` (never-computed → stale), which is the safe verdict.
- Pass all three into the `SavedReview(...)` constructor. Do **not** add them to the required-key set or the `version` gate — a v1 file lacking them must still load.
- No type-coercion/validation on `code_fingerprint` beyond the `.get` default; it is opaque (consistent with the leaf-module rationale).

**`update_annotation` — preserve both fields on write-back.**
- This rebuilds the payload from the loaded `SavedReview`, so it **must** add `"plan_fingerprint": saved.plan_fingerprint`, `"code_fingerprint": saved.code_fingerprint`, and `"code_fingerprint_present": saved.code_fingerprint_present` to its `payload` dict — otherwise the first walk annotation silently drops the fingerprints (and would flip a computed-but-empty capture back to the unset state). This is the easy-to-miss seam: the failure only surfaces after a save-then-annotate round-trip.

### Foundational logic / shared locations

- **The rule this step adds:** "a saved review carries a plan-state fingerprint and an opaque code-state fingerprint, both surviving save → load → annotate round-trips." The only place that rule lives is `review_persistence.py`'s three serialization seams (`save_review`, `load_review`, `update_annotation`) — there is no parallel persistence path. Confirmed by grep: no existing `plan_fingerprint` / `code_fingerprint` / `compute_plan_fingerprint` references anywhere in `plan_tool/` or `tests/`.
- **Streamed-hash duplication (permanent, not deferred):** `compute_plan_fingerprint`'s chunked SHA-256 loop is the same shape as `plan_tool/drift_detection.py:_compute_content_hash`. Inlining it here keeps `review_persistence.py` a leaf; importing the shared helper — even after step 2 promotes `_compute_content_hash` to a public `compute_content_hash` — would add a `drift_detection` edge the leaf-preservation rule forbids. So this copy is never deduped away for this module: the duplication is an accepted, permanent cost of leaf status, not a later-step consolidation. (Step 2's promotion serves the *other* callers; `review_persistence.py` deliberately does not become one of them.)

## Tests

All tests go in `tests/test_review_persistence.py` (the established mirror; new classes alongside `TestSaveReview` / `TestLoadReview`).

### Test-creation order (feature step)

Author these **with** the implementation; every case green before the step is done (green-before-done gate):

- `test_save_persists_plan_and_code_fingerprint` — `save_review(..., plan_fingerprint="abc", code_fingerprint={"a.py": "h1"})` writes both keys into the JSON payload verbatim.
- `test_round_trip_fingerprints` — save with both set → `load_review` returns `plan_fingerprint == "abc"` and `code_fingerprint == {"a.py": "h1"}`.
- `test_save_defaults_fingerprints_empty` — `save_review` without the new args writes `plan_fingerprint == ""`, `code_fingerprint == {}`, and `code_fingerprint_present == False` in the payload.
- `test_save_computed_empty_code_fingerprint_marks_present` — `save_review(code_fingerprint={})` (an explicit empty dict, not the `None` default) writes `code_fingerprint == {}` and `code_fingerprint_present == True`, and the value round-trips through `load_review` — distinguishing a computed-but-empty watched-code surface from a never-computed one.
- `test_load_legacy_without_fingerprints_defaults` — hand-write a v1 JSON file with **no** fingerprint keys (like `TestLoadReview`'s legacy fixtures); `load_review` yields `plan_fingerprint == ""`, `code_fingerprint == {}`, and `code_fingerprint_present == False`, no raise.
- `test_code_fingerprint_opaque_roundtrip` — an arbitrary `{"x/y.py": "deadbeef", "z.ts": "cafe"}` round-trips byte-for-byte; the module imposes no key/value schema.
- `test_update_annotation_preserves_fingerprints` — save with both fingerprints set, call `update_annotation`, reload; `plan_fingerprint`, `code_fingerprint`, and `code_fingerprint_present` all survive unchanged (guards the write-back seam, including a computed-but-empty capture not regressing to the unset state).
- `test_compute_plan_fingerprint_deterministic` — same plan + detail bundle hashed twice returns the identical digest.
- `test_compute_plan_fingerprint_changes_on_plan_or_detail_edit` — editing one plan byte changes the digest; editing one detail-file byte changes it; the digest is sensitive to both axes.
- `test_compute_plan_fingerprint_changes_on_detail_set_change` — adding a new `plan-details/<slug>/*.md` file and deleting an existing one each change the digest (filename participates in the hash), while a stray non-`.md` file in the bundle dir does **not**.
- `test_compute_plan_fingerprint_no_detail_bundle` — a plan whose `plan-details/<slug>/` dir is absent still returns a stable non-empty digest (plan file alone), and is repeatable.

## Acceptance criteria

- `SavedReview` has `plan_fingerprint: str` (default `""`), `code_fingerprint: dict[str, str]` (default `{}`), and `code_fingerprint_present: bool` (default `False`).
- `save_review(plan_fingerprint=..., code_fingerprint=...)` persists all three keys into the JSON payload; omitting them writes `""` / `{}` / `False`; passing `code_fingerprint={}` writes `{}` with `code_fingerprint_present == True`.
- `load_review` on a v1 file **without** the fingerprint keys returns `plan_fingerprint == ""`, `code_fingerprint == {}`, and `code_fingerprint_present == False` (no exception, no version bump).
- `load_review` on a file **with** the keys returns them verbatim; `code_fingerprint` round-trips any string→string dict unchanged; a never-computed (`code_fingerprint_present == False`) capture is distinguishable from a computed-but-empty (`code_fingerprint_present == True`, `code_fingerprint == {}`) one.
- `update_annotation` preserves all three fields across the load → mutate → write-back cycle.
- `compute_plan_fingerprint(plan_path)` returns a hex SHA-256 string that is identical for identical plan+detail bytes and differs when any plan byte, any detail byte, or the detail-file set changes.
- `SCHEMA_VERSION` remains `1`; `review_persistence.py` gains no new first-party import (no `scope_guard` / `drift_detection` edge); only stdlib `hashlib` is added.
- All ~11 new tests in `tests/test_review_persistence.py` pass; the existing suite stays green.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — `sha256()` constructor + `update`/`hexdigest` for the streamed plan-side fingerprint.
- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — adding defaulted fields (`= ""`, `field(default_factory=dict)`) so legacy sidecars deserialize without error.
- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — serializing the widened payload and `.get(...)`-tolerating missing keys on load.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — `Path.glob("*.md")` over the detail bundle and resolving the bundle dir from `plan_path.parent`.
- [Built-in `sorted()`](https://docs.python.org/3/library/functions.html#sorted) — deterministic detail-file ordering so the digest is enumeration-order-independent.

## Deferred

- **Computing `code_fingerprint`** — enumerating the code surface (`plan_tool/scope_guard.py:compute_drift_watched_paths` over `step.all_files`) and hashing each entry into the path→hash dict belongs to the downstream consuming step that calls `save_review`; this step only stores/loads the opaque dict. Keeping that computation out of `review_persistence.py` is what preserves its leaf status.
- **Note — the streamed-hash copy is NOT deferred:** `compute_plan_fingerprint` inlines a chunked SHA-256 loop duplicating `plan_tool/drift_detection.py:_compute_content_hash`. This copy is *not* a deferred dedup — the leaf-preservation rule forbids `review_persistence.py` from importing `drift_detection`, so there is no later step that can share the helper into this module without breaking that rule. Step 2 promotes `_compute_content_hash` to a public `compute_content_hash` for other callers; `review_persistence.py` keeps its own inlined copy permanently. (Listed here only to retract the earlier "left to later steps" framing.)
- **Staleness comparison / reuse decision** — comparing a saved review's `plan_fingerprint`/`code_fingerprint` against current state to accept or reject reuse (and the operator-facing drift warning via `plan_tool/drift_detection.py:render_attributed_path_line` + `plan_tool/scope_guard.py:build_file_to_step_map`) is downstream; this step only provides the stored substrate.
- **CLI toggle wiring** (`--reuse-audit` / `--reuse-audit-id`) — a separate step per the plan; the `argparse` plan-level reference applies there, not here.
