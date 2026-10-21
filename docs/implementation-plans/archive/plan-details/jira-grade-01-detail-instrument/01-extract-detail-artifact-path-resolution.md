> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Extract detail artifact path resolution into a shared `plan_tool/detail_artifacts.py` leaf

## Summary

Move the run-grade detail-file path logic — canonical path derivation and the pointer-vs-canonical resolution that three consumer modules reimplement across six call sites (four distinct resolution families; the census below) — into a new dependency-light leaf, `plan_tool/detail_artifacts.py`, with zero behavior change. The primary consumers are `plan_tool/fingerprint.py` (two lazy-import sites), `plan_tool/review.py` (two lazy-import sites), and `plan_tool/scope_out.py` (two private resolvers); `plan_tool/detail.py` keeps its public names as re-exports. The key design decision: the shared resolver returns a small state-carrying result (pointer set? file on disk? which path?), never a bare fallback path, so each consumer keeps its own — deliberately different — missing-file semantics. On green, every existing test passes unmodified and a new characterization suite pins the four resolution families' behavior before and after the move.

## Table of Contents

- [Summary](#summary) — what moves, where, and the one design decision
- [Why](#why) — the fragmentation this step removes and why later steps need the seam
- [Input](#input) — the four existing resolution behaviors this step must preserve exactly
- [Files (creates vs edits)](#files-creates-vs-edits) — new leaf + test file, and the per-file edits
- [Implementation](#implementation) — the leaf's contents, the resolver's result shape, and the migration constraints
- [Tests](#tests) — characterization matrix, import-safety, and compatibility cases
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the one plan-level reference relevant here
- [Deferred](#deferred) — what stays with steps 2 and 3, and nearby symbols left in place

## Why

Four modules answer "where is this step's detail file?" independently — the owner plus three consumers (one census, used throughout this step: 4 modules, 6 consumer call sites outside `detail.py`, 4 resolution families). The canonical derivation lives in `plan_tool/detail.py:derive_detail_path`, and because `detail.py` imports `review.py` at load, both `plan_tool/fingerprint.py` (`compute_detail_bundle_fingerprint`, `compute_purity_cache_key`) and `plan_tool/review.py` (`_format_audit_detail_bundle`, `audit_detail_bundle_status`) must lazy-import it inside each function to avoid an import cycle. `plan_tool/scope_out.py` adds two more private resolvers (`_resolve_detail_source`, `_resolve_carved_detail_path`) with their own — intentionally different — missing-file rules. Every later step in this plan adds a second artifact grade beside these paths: step 3 adds collision-safe jira-grade routing into this same leaf, and steps 4–7 select between grades at every consumer. That work needs one module that owns path routing, importable from anywhere without cycle gymnastics. This step creates that seam as a pure refactor, so step 2's small behavior change (audit visibility for an unset pointer with an on-disk canonical file) and step 3's feature land on a stable, tested base instead of riding inside the extraction.

## Input

No upstream step feeds this one (`depends_on` is empty). The contract consumed is the **current resolution behavior at HEAD** — four families that agree on the happy paths but split on the missing-file cases. This matrix is what the characterization tests pin; the extraction must not collapse it:

| State | `plan_tool/fingerprint.py` (both producers) | `plan_tool/review.py` (bundle render + status) | `plan_tool/scope_out.py:_resolve_detail_source` | `plan_tool/scope_out.py:_resolve_carved_detail_path` |
|---|---|---|---|---|
| pointer set, file exists | hash the pointer path | render / classify as detailed | pointer path | `(pointer path, False)` |
| pointer set, file **missing** | pointer path → hash `None` → key omitted | "no detail file on disk" note / classified bare | **pointer path anyway** (a set pointer is authoritative) | `(None, True)` — lost body, no canonical fallback |
| pointer unset, canonical exists | hash the canonical path | detailed | canonical path (adoption via `find_unreferenced_detail_for_step`) | `(canonical, False)` |
| pointer unset, canonical missing | canonical path → hash `None` → omitted | bare | `None` (never detailed) | `(None, False)` |

Also consumed: `derive_detail_path`'s output convention (`<plan_dir>/plan-details/<plan_slug>/<NN>-<step_slug>.md`), `derive_step_slug`'s stopword/length rules, `_plan_slug`'s `locator.slug_from_filename` mirroring, and `find_unreferenced_detail_for_step`'s exact-canonical-name-only adoption rule (a same-`NN`-prefix different-slug sibling is never adopted).

## Files (creates vs edits)

- **New files:**
  - `plan_tool/detail_artifacts.py` — the shared leaf: canonical path derivation + the state-carrying resolver.
  - `tests/test_detail_artifacts.py` — characterization matrix (written first), leaf unit tests, import-safety and re-export compatibility tests.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — move `derive_step_slug`, `derive_detail_path`, `find_unreferenced_detail_for_step`, and the `_plan_slug` helper (plus the slug constants they use) into the leaf; keep every moved name importable from `plan_tool.detail` unchanged (re-export), including `_plan_slug`.
  - `plan_tool/fingerprint.py` — replace the two `from plan_tool.detail import derive_detail_path` lazy imports (in `compute_detail_bundle_fingerprint` and `compute_purity_cache_key`) with the shared resolver; hashing, sorted-fold, and `relative_to` guards stay in place.
  - `plan_tool/review.py` — same swap at the two lazy-import sites, `_format_audit_detail_bundle` and `audit_detail_bundle_status`.
  - `plan_tool/scope_out.py` — reimplement `_resolve_detail_source` and `_resolve_carved_detail_path` on the shared resolver (keeping their signatures and return shapes); update the `from plan_tool.detail import …` list for the moved names.
  - `plan_tool/__init__.py` — keep `derive_detail_path` / `derive_step_slug` exported exactly as today; optionally also export the new resolver for external callers.

## Implementation

**What must be true when done:** one module owns detail-artifact path logic; every consumer resolves through it; no observable behavior, path, hash key, or return value changes anywhere.

- **Make the leaf genuinely a leaf.** `plan_tool/detail_artifacts.py` may import stdlib, `plan_tool.schema` (`Plan`, `Step`), and `plan_tool.locator` (`slug_from_filename`, already a low-level module below `review`). It must **not** import `plan_tool.detail`, `plan_tool.review`, or `plan_tool.fingerprint` at module import time — the whole point is that `fingerprint.py` and `review.py` can drop their call-time lazy imports for a plain top-level import without closing the `detail` → `review` cycle. Add a test that pins this (see Tests).

- **Move, don't duplicate.** `derive_detail_path`, `derive_step_slug`, `find_unreferenced_detail_for_step`, and `_plan_slug` (plus `_SLUG_STOPWORDS` / `_SLUG_FALLBACK` / `_MAX_SLUG_LEN`) relocate into the leaf. `detail.py` re-imports them under their current names so its own ~10 internal call sites (`_plan_slug` alone has call sites from the checkpoint path through `purity_cache_path` to the run-summary block) and every external importer keep working. Compatibility constraints that are **not** free to vary:
  - `from plan_tool.detail import derive_detail_path` must keep working — `plan_tool/__init__.py`, docstrings, and tests use that path (`plan_tool/bench.py` imports other `plan_tool.detail` names — `generate_detail`, `parse_detail_file_sections`, `shell_detail_invoker` — so the module's wider import surface must stay intact too).
  - `from plan_tool.detail import _plan_slug` must keep working — `plan_tool/cli/reconcile.py`, `plan_tool/cli/authoring.py`, and `plan_tool/cli/completeness_cmd.py` import it as `_detail_plan_slug` at several sites.
  - The re-exported names must be the same function objects, so a monkeypatch on either module path patches the behavior tests actually exercise.

- **The resolver returns states, not a fallback path.** One way: a frozen dataclass — `DetailArtifactResolution` or similar — from a single function, e.g. `resolve_detail_artifact(plan_path, plan, step, repo_root)`, carrying three facts: `pointer_set: bool`, `path: Path` (the pointer path when set, else the canonical path), `on_disk: bool`. Every row of the Input matrix is derivable from those three, so each consumer maps states to its own behavior at its own call site. The rejected alternative — a resolver that returns `Path | None` with a built-in fallback policy — erases the set-but-missing vs never-detailed distinction, which would silently change scope-out's archival target and its `detail_missing` flag (the lesson captured on exactly this extraction). The resolver does no hashing, no reading, no writing — one `is_file()` check at most.

- **Consumers keep their own policy.** `compute_detail_bundle_fingerprint` and `compute_purity_cache_key` keep their hash/omit logic and their `resolve().relative_to(root)` guards — they only swap where the path comes from. `_format_audit_detail_bundle` and `audit_detail_bundle_status` keep their render/classify branches. `scope_out._resolve_detail_source` and `_resolve_carved_detail_path` keep their exact signatures and three-case docs; they become thin maps over the resolver. Likely each site gets shorter; none gets different.

- **Do not touch neighbors that look related but aren't.** `scope_out.py` also imports `_DETAIL_ID_PREFIX_RE` and `_repo_relative` from `detail.py` — those serve detail-file *migration/archival*, not resolution; leave them where they are. `detail.py:_detail_step_input_hash` is an intentionally-narrow resume key, not path logic — untouched. No jira-grade path derivation lands here: step 3 owns the collision-safe jira-grade routes and edits `plan_tool/detail_artifacts.py` then. `Step.detail` remains the run-grade pointer and its meaning does not change.

- **Foundational logic and its other homes.** The extracted rule is "pointer-first, canonical-second detail-file selection." A repo grep for `derive_detail_path` confirms the six consumer sites listed above are the complete set outside `detail.py` itself; `launcher.py` and the CLI modules reach detail files only through these functions or through `step.detail` directly on already-resolved paths, so no additional call site migrates in this step.

## Tests

All in `tests/test_detail_artifacts.py` (new). Existing suites — `tests/test_detail.py` (`TestDeriveStepSlug`, `TestDeriveDetailPath`, `TestFindUnreferencedDetailForStep`), `tests/test_fingerprint.py` (`test_detail_bundle_fingerprint_hashes_present_detail`, `test_detail_bundle_fingerprint_omits_bare_step`), `tests/test_scope_out.py` (the `_resolve_carved_detail_path` and seed/archival cases), `tests/test_review.py` (the `audit_detail_bundle_status` cases) — are part of the gate and must pass unmodified.

### Test-creation order (refactor step)

Write these characterization tests **first**, against the existing public seams, and get them green **before** touching any implementation file. The pass-unchanged-after gate: these same tests, byte-for-byte unmodified, must stay green after the extraction, alongside every pre-existing suite above.

Characterization (pin current behavior; one test per matrix cell that isn't already pinned elsewhere):

- `test_bundle_fingerprint_prefers_pointer_over_canonical` — `compute_detail_bundle_fingerprint` hashes the `step.detail` path, not the canonical path, when both exist with different content.
- `test_bundle_fingerprint_set_but_missing_pointer_omits_key` — a set pointer to an absent file contributes no key, even when the canonical file exists (no fallback).
- `test_purity_key_detail_hash_uses_pointer_else_canonical` — `compute_purity_cache_key`'s `detail_hash` component follows the same selection.
- `test_audit_bundle_status_pointer_and_canonical_cases` — `audit_detail_bundle_status` classifies all four matrix states (detailed / bare) as today.
- `test_scope_out_resolve_source_returns_missing_pointer_path` — `_resolve_detail_source` returns the pointer path even when the file is absent.
- `test_scope_out_resolve_source_adopts_only_exact_canonical` — pointer unset: existing canonical file returned; same-prefix different-slug sibling is not.
- `test_carved_detail_path_three_cases` — `_resolve_carved_detail_path` returns `(pointed, False)` / `(None, True)` / `(canonical, False)` / `(None, False)` per its docstring.
- `test_derive_detail_path_format` — `plan-details/<plan_slug>/<NN>-<slug>.md` under the plan's parent; leading `<digit>-` stripped from the plan stem.
- `test_derive_step_slug_stopwords_and_length_cap` — stopword drop, single-char drop, `_MAX_SLUG_LEN` truncation on a `-` boundary, `"step"` fallback.

After the extraction (new-module unit tests):

- `test_resolver_state_matrix` — the shared resolver reports `(pointer_set, path, on_disk)` correctly for all four states.
- `test_leaf_does_not_import_detail` — importing `plan_tool.detail_artifacts` in a fresh interpreter (subprocess) leaves `plan_tool.detail` and `plan_tool.review` out of `sys.modules`.
- `test_moved_names_reexported_from_detail` — `plan_tool.detail.derive_detail_path` / `derive_step_slug` / `find_unreferenced_detail_for_step` / `_plan_slug` are the same objects as the leaf's.
- `test_package_exports_unchanged` — `from plan_tool import derive_detail_path, derive_step_slug` still works.

(Approx. 13 new tests.)

## Acceptance criteria

- `plan_tool/detail_artifacts.py` exists; its module-level imports are only stdlib, `plan_tool.schema`, and `plan_tool.locator` (checkable by reading the import block and by `test_leaf_does_not_import_detail`).
- `plan_tool/fingerprint.py` and `plan_tool/review.py` contain no `from plan_tool.detail import derive_detail_path` (the call-time lazy-import pattern for path resolution is gone).
- `from plan_tool.detail import derive_detail_path, derive_step_slug, find_unreferenced_detail_for_step, _plan_slug` all still succeed and return the leaf's objects.
- `scope_out._resolve_detail_source` and `scope_out._resolve_carved_detail_path` keep their current signatures and return exactly the Input-matrix values.
- The ~13 characterization/unit tests in `tests/test_detail_artifacts.py` pass, with the characterization subset committed green before the implementation change and unmodified after.
- `uv run pytest tests/ -q` passes with no edits to `tests/test_detail.py`, `tests/test_fingerprint.py`, `tests/test_scope_out.py`, or `tests/test_review.py`.
- No prompt text, hash key, fingerprint map, or CLI output changes — a fingerprint computed before and after this step on the same tree is the same.

## References

- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — for the characterization tests' filesystem fixtures and for verifying the re-export seam patches correctly.

## Deferred

- Audit visibility for an unset `Step.detail` pointer with an on-disk canonical file — step 2 owns that feature; this step must not change what the quality audit sees.
- Collision-safe jira-grade artifact paths and any second-grade routing — step 3 owns them and edits `plan_tool/detail_artifacts.py` then; nothing jira-grade lands here.
- Rewriting `detail.py`'s internal call sites (or the CLI modules' `_plan_slug` imports) to import the leaf directly — the re-exports make this optional churn; leave for a later cleanup if ever.
- `scope_out.py`'s `_DETAIL_ID_PREFIX_RE` / `_repo_relative` imports from `detail.py` — migration/archival helpers, not path resolution; out of scope.
- Consolidating `_detail_step_input_hash` with any resolution or fingerprint logic — deliberately separate contracts (the resume key must ignore file contents); do not merge.
