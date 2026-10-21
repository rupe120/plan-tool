> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add the purity-cache persistence module storing each step's key, verdict, and Implementation/Tests text

## Summary

Add a new leaf module `plan_tool/purity_cache.py` that reads and writes a per-plan cache file at `.plan-tool/purity-cache/<slug>.json`, keyed by step id. Each entry stores: the combined cache key (the hit test, the hex string step 1's `compute_purity_cache_key` produces); the key's **individual components** — `detail_hash`, `all_files_fingerprint`, `change_type`, `depends_on`, `purity_verdict_logic_version` — persisted separately so step 4 can compare them one at a time (it must see whether the `all_files_fingerprint` moved, which the opaque combined key cannot reveal); the cached purity verdict (the MIXED-STEP finding(s), present or explicitly empty); and the concatenated `## Implementation` + `## Tests` section text for step 4's BACKLOG #144 magnitude diff. The components feed step 4's diff-and-OR: the `all_files_fingerprint` gates whether a miss is a source change, the section text measures how much the purity-relevant prose moved, and the frontmatter values let step 4 attribute a change specifically rather than only observing that the combined key moved. The most important design decision is that an entry's *presence* means "this step was **successfully** purity-checked" — so an empty finding list reads as "checked, pure," never as "never checked" and never as "the call failed." A failed purity call (an empty/timed-out invoke → `parse_mixed_step_findings("")` → `[]`) must therefore never produce an entry; this module stores only what it is handed, and the success-gating decision (don't save on a failed call) lives in step 3's helper — so a persisted entry always reflects a call that actually returned. The module mirrors `plan_tool/review_persistence.py`'s save/load/atomic-write shape and registers the new record in `plan_tool/data_contract.py` with a matching `DATA_CONTRACT.md` section. The store is a single whole-file JSON map written atomically (`os.replace`) whose writers are already serialized by the repo mutation lock, and it prunes entries for step ids no longer in the plan on load. On green, a step's key, verdict, section text, and frontmatter values round-trip through disk, and a missing cache file loads as empty without raising.

## Table of Contents

- [Why](#why) — what step 3/4 need to persist and why it needs its own module
- [Input](#input) — the key, verdict, and finding shapes this module stores
- [Files (creates vs edits)](#files-creates-vs-edits) — the new module, the registry edit, the doc edit, and their tests
- [Implementation](#implementation) — the record shape, the file layout, the load/save contract, and the registry wiring
- [Tests](#tests) — round-trip, tolerant-load, and drift-guard cases
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer can run
- [References](#references) — stdlib JSON docs
- [Deferred](#deferred) — the key producer (step 1), the wiring (step 3), and the #144 diff (step 4)

## Why

Steps 3 and 4 need somewhere durable to record, per step, "the last purity check I ran and what it decided." Step 1 gives the sound cache key; this step gives the store the key points at. Without it, the two purity call sites — `detail.py`'s post-authoring loop and `plan_tool/cli/completeness_phases.py:_collect_purity_split_findings` — have nowhere to leave a verdict for the other to find, so each keeps paying the ~130–255s Claude call on unchanged content. The store also has to keep the raw `## Implementation` + `## Tests` section text, not just the key: step 4's BACKLOG #144 short-circuit needs to measure *how much* those sections changed on a cache miss, and a key alone tells you *that* something changed, not by how much. This step delivers the persistence layer and its data-contract registration only — no call site reads or writes it yet.

## Input

This step stores values other steps produce; its correctness depends on their shapes, not on recomputing them:

- **The cache key and its components** — step 1 produces `(combined_key, PurityKeyComponents)`: the combined key is a 64-char SHA-256 hex `str` (the hit test), and the components are its individual pieces — `detail_hash`, `all_files_fingerprint`, `change_type`, `depends_on`, and `logic_version`. This module treats the combined key as opaque (stores + compares for equality, the way `review_persistence.py` treats `code_fingerprint`) **and persists the components too**, because step 4's below-floor grading must compare them one at a time — specifically it must see whether `all_files_fingerprint` moved, which the opaque combined key cannot reveal. It never computes any of these itself. Step 1 is not in this step's `depends_on`, so store plain fields and stay agnostic about how they were built.
- **The verdict** — the cached purity finding(s) are `plan_tool/review.py:Recommendation` objects whose `source` is the `granularity-split` literal (`plan_tool/granularity.py:GRANULARITY_SPLIT_SOURCE`). Store the list as-is; an empty list is the explicit "checked, no finding" marker. Purity findings never populate `Recommendation`'s nested `redirect`/`impact`/`complexity`/`path` fields, so the stored records are flat.
- **The section text** — the concatenated `## Implementation` + `## Tests` detail-body text is a plain `str` this module stores verbatim for step 4 to diff. This step neither parses nor diffs it; it only round-trips it.
- **The prior frontmatter values** — the step's `change_type` (a `str`) and `depends_on` (a `list[int]`) at check time, stored verbatim so step 4 can detect a `change_type:`/`depends_on:`-specific change (the "frontmatter changed" half of #144's OR). Step 1's key already folds these in for *invalidation*; the entry stores them again for *attribution* — the key tells step 4 that something moved, these tell it whether the mover was the frontmatter. This step only round-trips them.

Limit on verifying this contract: step 1's key producer isn't at HEAD yet, so this module's key field can't be validated against a real key until step 3 wires them together — store and compare it as an opaque string and defer that end-to-end check to step 3.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/purity_cache.py` — the persistence module: the per-step record dataclass, the path helper, tolerant load, atomic save, and a schema-version constant.
  - `tests/test_purity_cache.py` — unit tests for the module.
- **Existing files (edits only):**
  - `plan_tool/data_contract.py` — register the new record in `persisted_dataclass_contracts()` and the new file in `json_object_contracts()`.
  - `DATA_CONTRACT.md` — add a `## Purity findings cache` file section plus a `### PurityCacheEntry` field table.
  - `tests/test_data_contract.py` — add drift-guard assertions that the new owner and file are registered and documented.
  - `.gitignore` — append `.plan-tool/purity-cache/` alongside the other per-machine `.plan-tool/` runtime-state entries (`runs`, `checkpoints`, `reviews`, `telemetry`, …), so the cache is never tracked. *(This path must also appear in this step's frontmatter `files:` list — the cache is runtime state and, if tracked, `run --commit` would sweep per-machine cache files into commits.)*

## Implementation

**Add the record dataclass.** One frozen dataclass — call it `PurityCacheEntry` — holds one step's cached check. Recommended fields:
- `step_id: int` — the step this entry is about.
- `cache_key: str` — the combined key from step 1; opaque here, the hit test.
- `detail_hash: str | None` — the detail-file hash component (step 1); `None` if the detail file was absent.
- `all_files_fingerprint: str` — the `all_files` content-fingerprint component (step 1). **Load-bearing for step 4:** it compares this in isolation to tell a source-file change from a trivial detail edit.
- `change_type: str` — the step's `change_type` at check time (component + step 4's #144 frontmatter-OR source).
- `depends_on: list[int]` — the step's `depends_on` at check time (component + step 4's #144 frontmatter-OR source).
- `purity_verdict_logic_version: int` — the `PURITY_VERDICT_LOGIC_VERSION` component at check time (step 1); a maintainer bump makes every prior entry mismatch.
- `detail_relpath: str` — the step's detail-file relpath at check time (e.g. `docs/implementation-plans/plan-details/<slug>/NN-….md`). **Load-bearing for step 4's renumber guard:** its below-floor reuse (which reuses *despite* a combined-key mismatch) requires this to equal the current step's detail relpath, so a split/merge/scope-out renumber — which changes the `NN-…` prefix — grades the miss genuine instead of leaking a different step's verdict onto a reassigned id.
- `findings: list[Recommendation]` — the cached purity verdict; `[]` = checked and pure (from a *successful* call — step 3 owns the success gate).
- `impl_tests_text: str` — concatenated `## Implementation` + `## Tests` detail-body text at check time (step 4's #144 diff source).
- `checked_at: str` — ISO-8601 UTC timestamp (`"2026-07-18T12:34:56Z"`), matching `review_persistence.py`'s `_utc_now_iso` format.

Field names and order are free to vary, but the payload pieces the step needs — the combined key, the individual components (`detail_hash`, `all_files_fingerprint`, `change_type`, `depends_on`, `purity_verdict_logic_version`), the `detail_relpath` renumber-guard token, the verdict, and the section text — must all be present and must round-trip.

**Lay out the file as an entries map keyed by step id.** The file is `.plan-tool/purity-cache/<slug>.json` (plan decision 3). Recommended JSON shape:
```json
{ "version": 1, "plan_slug": "purity-findings-cache",
  "entries": { "2": { "cache_key": "…", "detail_hash": "…", "all_files_fingerprint": "…",
                       "change_type": "feature", "depends_on": [1], "purity_verdict_logic_version": 1,
                       "detail_relpath": "docs/implementation-plans/plan-details/purity-findings-cache/02-….md",
                       "findings": [ … ], "impl_tests_text": "…", "checked_at": "…" } } }
```
- **JSON object keys are strings**, so the step id is a string key in `entries` even though `PurityCacheEntry.step_id` is an `int`. Cast at the boundary — the same `str`/`int` split telemetry documents for its step ids. One clean way: load returns `dict[int, PurityCacheEntry]` (or a small container holding it), converting keys back to `int` on read.
- **Serialize `findings` with `dataclasses.asdict`** the way `save_review` serializes its `recommendations`, and reconstruct with `Recommendation(**r)` on load, the way `load_review` does.

**Provide the path helper, tolerant load, and atomic save — mirror the siblings.** The nearest patterns to copy:
- Path helper — mirror `plan_tool/checkpoint.py:checkpoints_root` / `checkpoint_dir`: a `PURITY_CACHE_REL = (".plan-tool", "purity-cache")` tuple and `purity_cache_path(repo_root, slug)` returning `<repo_root>/.plan-tool/purity-cache/<slug>.json`. Resolve the slug the way the siblings do (`plan_tool/locator.py:slug_from_filename` if you take a `plan_path`, or accept a slug directly).
- Load — tolerant, like `checkpoint.py:load_if_valid`: a **missing file returns an empty cache, never raises**. Decide how strict to be on a malformed/newer-version file; `review_persistence.py:load_review` raises on a version mismatch, while `checkpoint.py` treats a bad checkpoint as a miss. For a best-effort cache a miss-on-malformed stance is the safer default — a corrupt cache should degrade to "recheck," not crash a `detail` run — but say which you chose in a docstring line.
- Save — atomic, tempfile + `os.replace`, exactly like `review_persistence.py:_atomic_write_text`. `mkdir(parents=True, exist_ok=True)` the directory first, as `save_review` does.

**Inline the atomic write; don't import the private helper.** `review_persistence.py:_atomic_write_text` and `checkpoint.py`'s save both inline their own copy per the codebase's stated rule (no shared `atomic_write_json` helper until a fourth call site appears). This module is the third such copy — inline a byte-identical version and leave the extract-it decision to a future step, noting the duplication in a one-line comment.

**Concurrency posture — rely on the repo mutation lock; do not add per-worker locking or per-step files.** The store is a single whole-file JSON map. A save is a read-modify-write of that map (load current entries, replace this step's, write the whole file back via the atomic `os.replace`). That read-modify-write is *not* internally locked, but it does not need to be: every command that writes this cache (`detail`, `completeness-audit`) already holds the repo mutation lock (`plan_tool/repo_lock.py`), which serializes all mutating plan-tool commands on a repo — the same lock that makes a second `detail`/`audit` on the same repo *refuse* rather than run concurrently. So the "two concurrent writers clobber each other's map entries" race cannot occur. And a cache write is best-effort regardless: a lost or clobbered entry degrades to a *re-check* (a fresh Claude call next time), never a stale verdict, because the combined key (step 1) gates correctness. Do **not** split into per-step files (the `checkpoint.py` shape) to chase concurrency — it buys nothing here and complicates load/prune; the single-map shape modeled on `review_persistence.py` is correct.

**Prune orphaned entries on load.** Entries are keyed by step id; a later split/merge/scope-out can remove or renumber a step, orphaning its entry. Orphans are *safe* — a renumbered id yields a mismatched key on next check → re-check, never a stale hit — but would accumulate unbounded. Give load a plan-aware prune: `load(..., valid_step_ids)` (or a `prune_absent(cache, plan)` helper the caller invokes) drops any entry whose step id isn't in the current plan. Cheap, deterministic, spends no Claude. When load has no plan in hand (a bare read), skip pruning rather than guess. This prunes at *entry* granularity only; a whole `<slug>.json` orphaned when its plan is renamed or deleted is **not** pruned — that matches the un-pruned `runs/`/`checkpoints/` siblings under `.plan-tool/` and is left as a conventional, low-impact accretion, not implied-complete cleanup.

**Keep the module a narrow leaf.** Import only `plan_tool.review.Recommendation` (for the verdict), `plan_tool.locator` (if you resolve the slug from a path), and stdlib. That matches `review_persistence.py`'s import surface — `Recommendation` sits below this module, so the edge is one-way and cycle-free. Do not import `detail.py`, `fingerprint.py`, or anything in `plan_tool.cli`.

**Register the new contract in `plan_tool/data_contract.py`.** Two additions, both additive:
- In `persisted_dataclass_contracts()`, add a `PersistedDataclassContract` for the record — `owner="PurityCacheEntry"`, `cls=purity_cache.PurityCacheEntry`, `section_title="PurityCacheEntry"`, `source_symbol="plan_tool/purity_cache.py:PurityCacheEntry"`, and `schema_constants=("PURITY_CACHE_SCHEMA_VERSION",)`. Add the `from plan_tool import purity_cache` import at the top.
- In `json_object_contracts()`, add a `JsonObjectContract` for the file — `owner="Purity findings cache"`, `section_title="Purity findings cache"`, `source_symbol="plan_tool/purity_cache.py"`, `path_labels=(".plan-tool/purity-cache/<slug>.json",)`, and `keys=("version", "plan_slug", "entries")`.

The registry is what the drift-guard test walks, so every field on `PurityCacheEntry` must appear in the doc section (below) or `test_every_persisted_field_is_documented_in_own_section` fails.

**Document both in `DATA_CONTRACT.md`.** Follow the existing section shape (see the Concept sidecar and Grounding sidecar sections):
- A `## Purity findings cache (`<repo-root>/.plan-tool/purity-cache/<slug>.json`)` file section: one paragraph on what the file is (a gitignored, best-effort per-plan cache of the MIXED-STEP purity verdict, keyed by step id), the `version`/`plan_slug`/`entries` keys, and the "entry present = checked, empty findings = pure" rule.
- A `### `PurityCacheEntry` (`purity_cache.py`)` sub-section: a `| Field | Meaning |` table naming every dataclass field — `step_id`, `cache_key`, `detail_hash`, `all_files_fingerprint`, `change_type`, `depends_on`, `purity_verdict_logic_version`, `detail_relpath`, `findings`, `impl_tests_text`, `checked_at` — plus the `PURITY_CACHE_SCHEMA_VERSION` constant (the `_obsolete_dataclass_sections` check keys on the `` `Name` (`file.py` `` heading format, so match it exactly). Note in the file-section prose that the entry stores the key's individual components (so step 4 can grade component-by-component), that the store prunes entries for absent step ids on load, and that its writers are serialized by the repo mutation lock (a best-effort, atomic whole-file write).

**Rejected alternatives:**
- *Storing the verdict in the audit-run sidecar under `.plan-tool/runs/<slug>/`* — those are timestamped report history, not a stable lookup target (plan decision 3). A dedicated file keyed by step id is the stable store.
- *Storing only the key's hash and no section text* — step 4 needs the raw Implementation/Tests text to compute a diff ratio; a hash detects change but not magnitude.
- *Making `purity_cache.py` a stdlib-only leaf that stores findings as raw dicts (like `checkpoint.py`)* — step 3 wants `Recommendation` objects to filter on `source` and splice back in, so storing typed records (as `review_persistence.py` does) is the better fit. If a later reviewer prefers strict leaf purity, raw-dict storage is the fallback, but it pushes reconstruction onto every reader.

## Tests

New cases in `tests/test_purity_cache.py` (build `Recommendation` objects directly; no invoker needed — this module spawns no backend):

- `test_load_missing_cache_returns_empty` — loading a path with no file on disk returns an empty cache and does not raise.
- `test_save_then_load_round_trips_entry` — save an entry, load it, and assert `cache_key`, `detail_hash`, `all_files_fingerprint`, `change_type`, `depends_on`, `purity_verdict_logic_version`, `detail_relpath`, `findings`, `impl_tests_text`, and `step_id` all survive unchanged.
- `test_purity_cache_dir_is_gitignored` — assert `.gitignore` contains a `.plan-tool/purity-cache` rule (e.g. `git check-ignore` on a sample `.plan-tool/purity-cache/x.json`, or a substring check on `.gitignore`), so the per-machine cache is never tracked.
- `test_entry_keyed_by_step_id` — two steps' entries in one file are retrievable independently by step id.
- `test_load_prunes_entries_for_absent_steps` — a cache with an entry for a step id not in the current plan drops that entry on a plan-aware load, while entries for present steps survive.
- `test_empty_findings_distinct_from_absent_entry` — an entry with `findings=[]` is present and reads as "checked, pure," distinct from a step with no entry at all.
- `test_findings_recommendation_fields_round_trip` — a stored purity `Recommendation` (source = `granularity-split`) reloads with its `id`/`source`/`severity`/`title`/`body` intact.
- `test_save_is_atomic_and_creates_dir` — saving into a not-yet-existing `.plan-tool/purity-cache/` creates the directory and leaves no `.tmp` file behind.
- `test_step_id_string_key_boundary` — the on-disk `entries` map uses string keys while the loaded record exposes `step_id` as an `int`.
- `test_purity_cache_path_location` — `purity_cache_path(repo_root, slug)` resolves to `<repo_root>/.plan-tool/purity-cache/<slug>.json`.
- `test_malformed_file_load_posture` — a corrupt/newer-version file loads per the chosen posture (miss-and-empty, or raise) — pin whichever the module documents.

New cases in `tests/test_data_contract.py` (mirror `test_grounding_contract_is_documented_from_registry` / `test_plan_manifest_contract_is_documented_from_registry`):

- `test_purity_cache_entry_is_registered` — `persisted_dataclass_contracts()` includes owner `PurityCacheEntry`.
- `test_purity_cache_entry_documented` — every registered field and the schema constant appear in the `DATA_CONTRACT.md:PurityCacheEntry` section (the parametrized `test_every_persisted_field_is_documented_in_own_section` also covers this once registered).
- `test_purity_cache_file_contract_documented` — the `Purity findings cache` `JsonObjectContract`'s `path_labels` and `keys` all appear in its doc section.

### Test-creation order (feature step)

This is a feature step — new behavior. Add every test above alongside the module and registry edits in the same change. Green-before-done gate: all new tests pass, and `tests/test_data_contract.py` stays green (the drift guard fails the build if the registry and doc disagree), before this step is considered finished. Run `uv run pytest tests/test_purity_cache.py tests/test_data_contract.py -q`.

## Acceptance criteria

- `plan_tool/purity_cache.py` defines the per-step record dataclass, a `purity_cache_path` helper resolving to `<repo_root>/.plan-tool/purity-cache/<slug>.json`, tolerant load, atomic save, and a `PURITY_CACHE_SCHEMA_VERSION` constant.
- Loading a path with no file present returns an empty cache without raising.
- A save→load round-trip preserves the cache key, its individual components (`detail_hash`, `all_files_fingerprint`, `change_type`, `depends_on`, `purity_verdict_logic_version`), the `detail_relpath`, the finding list (including empty), the Implementation/Tests section text, and the step id.
- `.gitignore` ignores `.plan-tool/purity-cache/` — the cache is never tracked, so `run --commit` cannot sweep per-machine cache files into commits.
- An entry with `findings=[]` is retrievable and distinct from a step that has no entry.
- A plan-aware load prunes entries whose step id is absent from the current plan; entries for present steps survive.
- The store's writers are serialized by the repo mutation lock and the whole-file write is atomic; a lost entry degrades to a re-check, never a stale verdict (no per-step files or per-worker locking added).
- `plan_tool/data_contract.py:persisted_dataclass_contracts()` includes owner `PurityCacheEntry`, and `json_object_contracts()` includes the `Purity findings cache` file.
- `DATA_CONTRACT.md` documents both the file and every `PurityCacheEntry` field plus its schema constant.
- `uv run pytest tests/test_purity_cache.py tests/test_data_contract.py -q` passes.

## References

- [json — JSON encoder and decoder — Python 3.14 documentation](https://docs.python.org/3/library/json.html) — reading and writing the `.plan-tool/purity-cache/<slug>.json` file and serializing the entries map.

## Deferred

- Producing the combined cache key — owned by step 1 (`compute_purity_cache_key` in `plan_tool/fingerprint.py`); this module stores the key it returns but never computes it.
- Reading or writing the cache from the purity call sites — owned by step 3, which routes `detail.py`'s loop and `_collect_purity_split_findings` through a shared helper that consults this store.
- Diffing the stored Implementation/Tests text for the below-0.5% short-circuit and the audit-path advisory — owned by step 4 (BACKLOG #144); this step only persists the text, it doesn't compare it.
- Extracting a shared atomic-write helper — deferred by the codebase's "no shared helper until a fourth call site" rule; this module inlines its own copy.
