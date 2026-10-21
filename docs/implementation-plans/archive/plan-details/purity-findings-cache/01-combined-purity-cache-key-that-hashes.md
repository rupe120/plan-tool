> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a combined purity-cache key hashing the detail file plus the step's declared files

## Summary

Add one pure function to `plan_tool/fingerprint.py` that produces a stable cache key for a step's purity/MIXED-STEP judgment — **and exposes the key's individual components**, because later steps compare them one at a time. The key covers: the content hash of that step's detail file; a content fingerprint of every file the purity prompt shows the model; the step's verdict-affecting frontmatter (`change_type` and `depends_on`); and a **`PURITY_VERDICT_LOGIC_VERSION`** constant that stands in for the MIXED-STEP verdict *logic* itself (the `prompts/detail-quality.md` criteria + `parse_mixed_step_findings`). The design decisions are *what the key covers* and *that the components are individually retrievable*: (a) it must hash `step.all_files` (declared `files:` **and** `creates:`), exactly the surface `plan_tool/detail.py:_format_files_contents_block` folds into the prompt; (b) it must fold in `change_type`/`depends_on`, because `change_type` *directs the MIXED-STEP verdict* (the prompt states "a `non-code` step is never mixed") yet lives in the plan frontmatter, so a `refactor`→`feature`/`non-code` flip would otherwise hit a stale entry; (c) it must fold in `PURITY_VERDICT_LOGIC_VERSION`, so editing the verdict logic (with every input unchanged) invalidates every entry rather than serving verdicts computed under the old prompt; and (d) it must **return the components alongside the combined digest** (e.g. `(combined_key, PurityKeyComponents)`), because step 4's below-floor grading has to tell *which* component moved on a miss — a single opaque digest cannot. No call sites change in this step — later steps (2 persists the key + components, 3 routes the purity call sites through it, 4 grades component-by-component) consume it. On green, `compute_purity_cache_key(plan, plan_path, step, repo_root)` returns a deterministic combined digest plus its components; the digest changes when the detail file, any `all_files` byte, `change_type`/`depends_on`, or `PURITY_VERDICT_LOGIC_VERSION` change, and is stable otherwise.

## Table of Contents

- [Why](#why) — what's missing today and why the combined key must exist first
- [Input](#input) — the prompt and fingerprint contracts the key must match
- [Files (creates vs edits)](#files-creates-vs-edits) — the one edited module and its test file
- [Implementation](#implementation) — the new function, what it hashes, and the soundness constraints
- [Tests](#tests) — the unit cases proving the key is content-sound and deterministic
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer can run
- [References](#references) — stdlib hashing/serialization docs
- [Deferred](#deferred) — what this step intentionally leaves to steps 2–4

## Why

The per-step MIXED-STEP purity judgment is an expensive Claude call (BACKLOG #133 measured ~130–255s per step) and it runs from independent call sites — `detail.py`'s post-authoring loop and `completeness_phases._collect_purity_split_findings` — with no shared cache. Before any caching can be added, there must be a sound way to tell "this step's purity-relevant inputs are unchanged since the last check." A hash of the detail file alone is not sound: `render_detail_quality_prompt` also folds in the current bytes of the step's declared files (via `_format_files_contents_block`) **and** the step's `change_type`/`depends_on` frontmatter, so a step whose prose is unchanged but whose source files moved — or whose `change_type` flipped — underneath it could legitimately flag differently, and a detail-only (or detail+files-only) key would serve a stale verdict. `change_type` is the load-bearing case: it directs the MIXED-STEP verdict but lives in frontmatter, outside every file this key hashes, so it must be folded in explicitly. Two further inputs the key must carry, both caught by the round-3 audit: the **verdict logic** itself (`PURITY_VERDICT_LOGIC_VERSION`) — the key covers the prompt's *inputs* but not the prompt template / `parse_mixed_step_findings`, so without a version a change to the MIXED-STEP criteria would leave every input unchanged and serve verdicts computed under the old logic forever; and the key's **individual components**, returned alongside the digest, because step 4 must isolate a source-file change from a trivial detail edit and the opaque combined digest moves on any miss. This step delivers that key (with components) and nothing else, so steps 2–4 can build the persistence, wiring, and grading on a correct foundation.

## Input

This step adds a pure producer; its correctness depends on matching what the purity prompt actually reads and reusing the existing fingerprint primitives:

- **The purity prompt's file surface** — `plan_tool/detail.py:_format_files_contents_block` iterates `step.all_files` (i.e. `files:` **plus** `creates:`), not just `step.files`. The key must cover the same set, or a change to a `creates:` file underneath an unchanged detail body would be missed. This is the one non-obvious contract: the plan's "declared `files:`" wording is looser than the code — ground on `step.all_files`.
- **The prompt's verdict-affecting frontmatter** — `render_detail_quality_prompt` also folds in the step's `change_type` (as a directive that steers the MIXED-STEP judgment) and `depends_on`. These live on the `Step` frontmatter, not in any hashed file, so they must be folded into the key directly. `change_type` is mandatory for soundness (the `refactor`→`feature` stale-hit); `depends_on` is included both because the prompt folds it in and because #144's frontmatter-change OR (step 4) keys off it. `title`/`complexity` are also folded into the prompt but excluded (decision 5, low-impact staleness).
- **Content-hash primitive** — `plan_tool/drift_detection.py:compute_content_hash(path)` returns a streamed SHA-256 hex, or `None` for a missing/unreadable file. This is the same primitive `compute_code_fingerprint` uses; reuse it, don't re-hash by hand.
- **Detail-path resolution** — resolve this step's detail file the way `compute_detail_bundle_fingerprint` does: `step.detail` if set (under `repo_root`), else `plan_tool/detail.py:derive_detail_path(plan_path, plan, step)`.
- **Schema fields** — `plan_tool/schema.py:Step.all_files` (property) is the declared+created list; `Step.change_type` and `Step.depends_on` are the verdict-affecting frontmatter folded into the key; `Step.detail` is the optional detail path.
- **The verdict-logic version** — define a module-level `PURITY_VERDICT_LOGIC_VERSION` constant (an int, e.g. `1`) in `plan_tool/fingerprint.py`, folded into the key. It is a **maintainer-bumped** stand-in for the MIXED-STEP verdict logic — `plan_tool/prompts/detail-quality.md`'s criteria, `plan_tool/detail.py:parse_mixed_step_findings`, and `plan_tool/detail.py:_format_tests_order_directive` (the code that injects the `change_type` framing into the prompt). Bump it in the same change that edits any of them, so every cached verdict invalidates at once. (A hash of the prompt file would also work but couples the key to prompt whitespace; a hand-bumped constant is the deliberate, low-noise choice.)

Limit on verifying this contract: `title`/`complexity` and lessons-file content are also folded into the prompt but are deliberately excluded from the key (plan decision 5) — an accepted staleness window, not something this key can detect.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/fingerprint.py` — add the `compute_purity_cache_key` function (a new public leaf function alongside `compute_code_fingerprint` / `compute_detail_bundle_fingerprint`). No change to existing functions.
  - `tests/test_fingerprint.py` — add unit tests for the new function.

## Implementation

**Add one function returning the combined key *and* its components: `compute_purity_cache_key(plan, plan_path, step, repo_root) -> tuple[str, PurityKeyComponents]`.** The combined SHA-256 hex string changes iff any purity-relevant input changes; the `PurityKeyComponents` (a small frozen dataclass) carries the pieces step 2 persists and step 4 compares one at a time: `detail_hash: str | None`, `all_files_fingerprint: str`, `change_type: str`, `depends_on: tuple[int, ...]`, and `logic_version: int`. Signature mirrors the module's existing producers but adds `step`: `compute_purity_cache_key(plan: Plan, plan_path: Path, step: Step, repo_root: Path) -> tuple[str, PurityKeyComponents]`.

**What it hashes — the key design decision.** Compute the components:
- `detail_hash` — `compute_content_hash` of the step's detail file (resolved via `step.detail` else `derive_detail_path`), or `None` if absent.
- `all_files_fingerprint` — fold a map of `{repo-relative-posix-path: sha256-hex}` over every entry in `step.all_files` (each digested with `compute_content_hash`, missing paths omitted) into one stable sub-digest. **Keep this a distinct sub-fingerprint** — step 4 compares it in isolation to tell a source-file change from a detail edit, so it cannot be blended irreversibly into the combined digest.
- `change_type`, `depends_on` — read from the `Step` frontmatter.
- `logic_version` — the module `PURITY_VERDICT_LOGIC_VERSION`.

Then fold the components into the combined digest: `hashlib.sha256` over a canonical serialization (e.g. `json.dumps({"detail": detail_hash, "all_files": all_files_fingerprint, "change_type": change_type, "depends_on": sorted(depends_on), "logic_version": logic_version}, sort_keys=True)`), returning `.hexdigest()`. What must hold: deterministic and byte-stable across runs/machines (sort first — mirror `compute_code_fingerprint`'s sorted order), every component included so any of them changing alters the digest, and the components returned intact alongside it.

**Ground on `step.all_files`, not `step.files`.** This is one load-bearing soundness constraint. `_format_files_contents_block` shows the model `step.all_files`; if the key hashes only `step.files`, a changed `creates:` file serves a stale verdict. Use `step.all_files`.

**Fold in `change_type` and `depends_on`.** This is the other load-bearing input constraint. The MIXED-STEP verdict is directed by `change_type` (frontmatter, not in any hashed file), so a key over files+detail alone would hit a stale entry on a `refactor`→`feature`/`non-code` flip. Include both `change_type` and `depends_on` in the folded digest. Do **not** include `title`/`complexity` (decision 5 — folded into the prompt but excluded to avoid over-invalidating on cosmetic edits).

**Fold in `PURITY_VERDICT_LOGIC_VERSION`, and enforce the bump.** The key otherwise covers only the prompt's *inputs*; the MIXED-STEP *logic* (prompt criteria + `parse_mixed_step_findings`) is invisible to it, so editing that logic would serve verdicts from the old prompt indefinitely. Fold the constant in so a bump invalidates every entry at once — **and** add the drift-guard test (see Tests: `test_purity_verdict_logic_version_bumped_on_logic_change`) that hashes the prompt + parser source and fails if they change without a version bump. The hand-bumped constant is the deliberate low-noise key input; the drift-guard is what makes the required bump *enforced* rather than discipline-dependent (the analog of `tests/test_data_contract.py` for the contract shapes).

**Return the components, not just the digest.** Build the `PurityKeyComponents` and return it with the combined key. This is load-bearing for step 4: on a miss the combined digest has moved but cannot say *which* input changed, and the below-floor grading must confirm the `all_files_fingerprint` is unchanged (a source-file change must never be graded as a trivial detail edit). Keep `all_files_fingerprint` as its own sub-digest inside the components so it is comparable in isolation.

**Missing files: omit, don't crash.** `compute_content_hash` returns `None` for a file not on disk; skip those keys (same as `compute_code_fingerprint`). Omission is still change-detecting: a file present-then-deleted (or absent-then-created) changes the set of keys, so the folded digest changes. A missing detail file likewise contributes no key. The function must never raise on a missing path.

**Keys are repo-relative posix.** Resolve `repo_root.resolve()` and express each path relative to it as a posix string (guard the `relative_to` with the same `try/except ValueError` fallback `compute_detail_bundle_fingerprint` uses for a path outside the root), so the key reproduces across clones and is independent of absolute location.

**Rejected alternatives:**
- *Detail-hash-only key* — unsound (misses declared-file changes); this is the whole reason the key is "combined."
- *Detail+files-only key (no frontmatter)* — also unsound: it hits a stale entry on a `change_type` flip, which changes the MIXED-STEP verdict without changing any hashed file. This is the HIGH gap the round-1 audit caught; fold `change_type`/`depends_on` in.
- *A single opaque digest with no exposed components* — this was the shape before the round-3 audit; it's unsound for step 4, which must compare the `all_files_fingerprint` in isolation to distinguish a source-file change from a trivial detail edit. Return `(combined_key, PurityKeyComponents)`: the combined digest stays the one hit-test, and the components make component-by-component grading possible.
- *Reusing `compute_detail_bundle_fingerprint` and indexing this step's entry* — that hashes every step's detail file (wasteful) just to read one; resolve this step's detail path directly instead. Note it as the multi-step sibling, don't call it here.

**Boundary note — this is not the same as the existing `detail.py:_detail_step_input_hash`.** That hash is a narrow resume/recovery key for the detail-body write path and deliberately does **not** hash file contents. The purity key is a different concern (content-grounded, includes file bytes) and belongs in `fingerprint.py` as a leaf, not folded into that recovery hash. Keep them separate — do not consolidate.

No new imports beyond what's already at hand: `compute_content_hash` (already imported), `derive_detail_path` (lazy-import inside the function, as `compute_detail_bundle_fingerprint` already does, to keep this leaf out of the `detail` → `review` import cycle), plus `hashlib`/`json` from the stdlib.

## Tests

All new cases go in `tests/test_fingerprint.py`, reusing the existing `_fingerprint_plan` / `_seed_code_files` helpers (extend or add a small sibling helper if a case needs a `creates:` entry). Each asserts against `compute_purity_cache_key`.

- `test_purity_cache_key_is_deterministic` — two calls on identical disk state return the same hex string.
- `test_purity_cache_key_changes_on_detail_edit` — editing the step's detail file bytes changes the key.
- `test_purity_cache_key_changes_on_declared_file_edit` — editing a `step.files` file's bytes (detail unchanged) changes the key. *This is the core soundness case — proves the key isn't detail-only.*
- `test_purity_cache_key_covers_creates_entries` — a step with a `creates:` file: editing that created file's bytes changes the key (proves it grounds on `all_files`, not just `files`).
- `test_purity_cache_key_changes_on_change_type_flip` — flipping the step's `change_type` (`refactor`→`feature`) with detail and all files unchanged changes the key. *This is the HIGH-finding soundness case — proves a `change_type` flip can't hit a stale entry.*
- `test_purity_cache_key_changes_on_depends_on_edit` — changing the step's `depends_on` (detail/files unchanged) changes the key.
- `test_purity_cache_key_stable_when_title_or_complexity_changes` — changing only `title`/`complexity` leaves the key unchanged (decision 5 — those are excluded).
- `test_purity_cache_key_changes_on_logic_version_bump` — bumping `PURITY_VERDICT_LOGIC_VERSION` (monkeypatch the module constant), with every input unchanged, changes the combined key. *Proves a verdict-logic change invalidates the cache (the [prompt-version-invalidation] guard).*
- `test_purity_verdict_logic_version_bumped_on_logic_change` — a **drift-guard** that enforces the maintainer bump, mirroring `tests/test_data_contract.py`'s contract-drift test. It computes a hash over the current MIXED-STEP verdict logic — `plan_tool/prompts/detail-quality.md`'s content, the `plan_tool/detail.py:parse_mixed_step_findings` source, **and the source of the code that assembles verdict-steering prompt text: `plan_tool/detail.py:_format_tests_order_directive`** (the sole channel injecting the `change_type` "refactor/feature" framing the purity section branches on, via `${change_type_directive_block}` in `render_detail_quality_prompt`) — all via `inspect.getsource` — and asserts it equals a **pinned expected hash paired with the current `PURITY_VERDICT_LOGIC_VERSION`** (a small `{version: hash}` pin or a single `(version, hash)` constant in the test). The pinned surface must cover *every* input that steers the verdict, not just the `.md` and the parser, or a reworded directive changes framing while the guard stays green. Editing the prompt criteria or the parser changes the hash and **fails the test**, whose message instructs: bump `PURITY_VERDICT_LOGIC_VERSION` and update the pinned hash. This closes the [purity-verdict-logic-version] gap — the bump no longer relies on unenforced discipline; a forgotten bump is a red test, not a silently-stale cache. *(Whitespace-only prompt edits will trip it; that is the accepted cost of enforcement — bump-and-repin is cheap, a stale verdict is not.)*
- `test_purity_cache_key_exposes_components` — the returned `PurityKeyComponents` carries the `detail_hash`, `all_files_fingerprint`, `change_type`, `depends_on`, and `logic_version`, and its `all_files_fingerprint` changes on an `all_files` edit while its `detail_hash` changes on a detail edit — proving the components are individually comparable (what step 4 needs).
- `test_purity_cache_key_stable_when_unrelated_file_changes` — editing a file not in this step's `all_files` or detail leaves the key unchanged.
- `test_purity_cache_key_missing_detail_does_not_raise` — a step whose detail file isn't on disk returns a key without raising.
- `test_purity_cache_key_missing_declared_file_does_not_raise` — a declared file absent from disk is omitted and does not raise.
- `test_purity_cache_key_returns_digest_and_components` — the return is a `(str, PurityKeyComponents)` tuple whose first element is a 64-char lowercase hex `str`.

### Test-creation order (feature step)

This is a feature step. Add every test above alongside the `compute_purity_cache_key` implementation in the same change. Green-before-done gate: all new tests must pass (and the existing `tests/test_fingerprint.py` suite must stay green) before this step is considered finished. Run `uv run pytest tests/test_fingerprint.py -q`.

## Acceptance criteria

- `plan_tool/fingerprint.py` defines `compute_purity_cache_key(plan, plan_path, step, repo_root)` returning `(combined_key: str, components: PurityKeyComponents)`, and a `PURITY_VERDICT_LOGIC_VERSION` constant.
- Two calls on unchanged disk state return equal combined keys.
- Editing the step's detail file bytes changes the key.
- Editing any `step.all_files` entry's bytes (detail unchanged) changes the key **and** the components' `all_files_fingerprint` — including a `creates:` entry.
- Flipping the step's `change_type` (or editing `depends_on`), with detail and all files unchanged, changes the key.
- Bumping `PURITY_VERDICT_LOGIC_VERSION`, with every input unchanged, changes the key.
- A drift-guard test fails if `prompts/detail-quality.md`, `parse_mixed_step_findings`, **or `_format_tests_order_directive`** (the change_type-framing channel) changes without a `PURITY_VERDICT_LOGIC_VERSION` bump (the bump is enforced, not discipline-dependent).
- The returned components expose `detail_hash`, `all_files_fingerprint`, `change_type`, `depends_on`, `logic_version` individually.
- Changing only `title`/`complexity` leaves the key unchanged.
- Editing a file outside the step's detail + `all_files` leaves the key unchanged.
- A missing detail file or a missing declared file yields a key without raising (the missing path is omitted).
- All new tests in `tests/test_fingerprint.py` pass and the existing suite stays green.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — `sha256`/`hexdigest`, the primitive under both `compute_content_hash` and the folded combined key.
- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — `json.dumps(..., sort_keys=...)` as one deterministic way to serialize the sorted `(path, hash)` items before the final hash.

## Deferred

- Persisting the key and the cached verdict/section text to `.plan-tool/purity-cache/<slug>.json` — owned by step 2 (the persistence module).
- Routing the three purity call sites through a shared cache helper that skips Claude on an unchanged key — owned by step 3.
- The below-0.5% Implementation/Tests diff short-circuit and the audit-path advisory (BACKLOG #144) — owned by step 4; that logic diffs section *text*, a separate signal from this content key.
- Including lessons-file content in the key — a permanent, accepted staleness window per the plan's Out-of-scope (decision 5), not a follow-up for this step.
