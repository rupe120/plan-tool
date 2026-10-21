# Step 1 — Share detail artifact paths while keeping legacy run details

## Summary

Create `plan_tool/detail_artifacts.py` as the shared owner of detail-artifact path selection. Move the current pointer-first, canonical-fallback path rules out of individual consumers while preserving the existing run-grade file layout and `Step.detail` meaning. Update `plan_tool/detail.py`, `plan_tool/fingerprint.py`, `plan_tool/review.py`, and `plan_tool/scope_out.py` to use the shared contract where they read, fingerprint, audit, adopt, rename, or archive existing detail files; keep `generate_detail()` canonical-only authoring unchanged. Existing run-grade and legacy detail bundles retain their selected paths, while an unset pointer with an on-disk canonical detail is now included in quality auditing; the shared path seam is ready for step 2’s separate jira-grade artifacts.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the shared artifact-path refactor.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — Why duplicated detail-path rules risk incompatible artifact selection.
- [Input](#input) — Existing `Step.detail` and canonical path behavior this step preserves.
- [Files (creates vs edits)](#files-creates-vs-edits) — New path owner and the consumers moved to it.
- [Implementation](#implementation) — Required path-selection invariants and migration approach.
- [Tests](#tests) — Characterization and shared-helper coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable compatibility and routing outcomes.
- [References](#references) — Path and test APIs relevant to the refactor.
- [Deferred](#deferred) — Later jira-grade authoring and consumer work.

## Why

Detail paths are currently selected in several places: some honor `Step.detail`, some derive the legacy canonical path, and scope-out has its own pointer-first fallback rules. That duplication makes it easy for a later jira-grade artifact to be read by one workflow and missed, renamed, or fingerprinted differently by another. This step creates one path-selection boundary while treating every existing `detail:` value and canonical legacy bundle as run-grade, so the experiment can add a second artifact without changing the control path.

## Input

- **Legacy run detail pointer:** `plan_tool/schema.py:Step.detail` remains the authoritative stored path when resolving an existing artifact. This step must not reinterpret it as jira-grade or change its serialized shape; `plan_tool/detail.py:generate_detail()` continues to author to the canonical path and update the pointer to that path.
- **Canonical legacy location:** `plan_tool/detail.py:derive_detail_path()` defines the existing `plan-details/<plan-slug>/<NN>-<step-slug>.md` fallback for steps without a pointer.
- **Legacy orphan behavior:** `plan_tool/detail.py:find_unreferenced_detail_for_step()` only adopts an exact canonical filename; same-ID files with a stale slug remain orphans rather than being silently claimed.
- **Pointer-first scope-out behavior:** `plan_tool/scope_out.py:_resolve_detail_source()` and `_resolve_carved_detail_path()` distinguish an unset pointer from a set pointer whose file is missing. Preserve that distinction because scope-out uses it to decide whether to archive a body or render a missing-detail notice.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/detail_artifacts.py` — Define the shared detail-artifact path contract and legacy run-grade resolution helpers.
  - `tests/test_detail_artifacts.py` — Cover the contract directly, including pointer, canonical fallback, missing-pointer, and collision-safe future artifact routing cases.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — Keep `derive_detail_path()`, canonical-only `generate_detail()` authoring, and `find_unreferenced_detail_for_step()` compatible, then route adoption, detail-body reads, and `collect_detail_quality_findings()` through the shared artifact contract where appropriate.
  - `plan_tool/fingerprint.py` — Replace duplicated `Step.detail` versus `derive_detail_path()` selection in `compute_detail_bundle_fingerprint()` and `compute_purity_cache_key()` with the shared run-detail resolution.
  - `plan_tool/review.py` — Use the shared contract for selected-artifact resolution in `check_detail_coverage()`, `_format_audit_detail_bundle()`, `audit_detail_bundle_status()`, and `_filter_symbols_by_detail()` so audit rendering, detail presence, and detail-based symbol filtering agree with fingerprinting; retain `check_detail_coverage()`'s separate `plan-details/<slug>/<NN>-*.md` scan for stale-slug orphans.
  - `plan_tool/scope_out.py` — Use the shared pointer-first result in `_resolve_detail_source()` and `_resolve_carved_detail_path()` so seed capture, rename planning, and archival identify the same run artifact.
  - `tests/test_detail.py` — Keep existing path and orphan-adoption behavior covered after extraction.
  - `tests/test_fingerprint.py` — Keep legacy fingerprint output stable and add coverage that it follows the shared resolver.
  - `tests/test_review.py` — Keep coverage and audit-bundle behavior stable for pointed and canonical legacy details.
  - `tests/test_scope_out.py` — Keep seed/archive path parity and missing-pointer behavior stable after the shared resolver is introduced.

## Implementation

- **Make existing-artifact selection the foundational rule.** Put the rule in `plan_tool/detail_artifacts.py`: when resolving an existing artifact, an explicit legacy `Step.detail` path wins; when it is absent, the canonical run-grade path from `plan_tool/detail.py:derive_detail_path()` is the fallback. Return enough state for callers that need to distinguish “no artifact exists yet” from “a declared pointer is missing.” This resolver does not change `generate_detail()`’s canonical-only authoring output.

- **Keep the legacy control unchanged.** Existing run-grade artifacts remain in the layout produced by `plan_tool/detail.py:derive_detail_path()`. A plan with `detail: docs/details/custom.md` must continue to use that exact path when resolving its existing artifact, even when it does not match the canonical filename. `generate_detail()` continues to write the canonical path and update `Step.detail`; do not otherwise rewrite pointers, move legacy bundles, or add a new schema field in this refactor.

- **Reserve isolated routing for the later jira-grade artifact.** Have `plan_tool/detail_artifacts.py` export `derive_jira_detail_path()` as the collision-safe Jira-grade path selector, alongside any depth-specific path object needed to represent both the retained run artifact and the future Jira artifact without relying on filename guessing. Step 1 only establishes the routing contract; step 2 owns writing Jira-grade files and setting any new selection metadata.

- **Preserve canonical orphan adoption rules.** `plan_tool/detail.py:find_unreferenced_detail_for_step()` must still accept only the exact canonical legacy filename. Do not broaden it to accept any `<NN>-*.md`, because a stale title slug is an orphan that must stay visible to validation instead of being attached to the wrong step.

- **Retain coverage's orphan scan.** After `plan_tool/review.py:check_detail_coverage()` uses the shared resolver for the selected artifact, it must continue to scan `plan-details/<slug>/<NN>-*.md` separately to report same-ID stale-slug files as unreferenced. The resolver's exact canonical fallback must not replace that validation scan.

- **Move consumers to the same resolver.** Replace the repeated pointer-or-derived branches in:
  - `plan_tool/fingerprint.py:compute_detail_bundle_fingerprint()` and `compute_purity_cache_key()`;
  - `plan_tool/review.py:_format_audit_detail_bundle()` and `audit_detail_bundle_status()`;
  - `plan_tool/scope_out.py:_resolve_detail_source()` and `_resolve_carved_detail_path()`;
  - `plan_tool/detail.py:_read_step_detail_body()`, `_step_detail_relpath()`, and `collect_detail_quality_findings()` where the new contract removes duplicate existing-artifact selection logic;
  - `plan_tool/review.py:_filter_symbols_by_detail()` so an unset pointer with an on-disk canonical detail is filtered from the same run artifact that fingerprinting and audit use; add `plan_path` to its signature and propagate it from `heuristic_already_done` and its callers so the resolver can derive that canonical fallback.

- **Preserve import safety.** `plan_tool/detail.py` imports `plan_tool.review` through lazy paths, while `plan_tool/fingerprint.py` and `plan_tool/review.py` currently lazy-import `derive_detail_path()` to avoid closing that cycle. Keep `plan_tool/detail_artifacts.py` dependency-light and structure imports so the shared module does not create a `detail`/`review` import cycle.

- **Keep scope-out’s missing-pointer signal exact.** A set `Step.detail` whose target is missing must not fall back to a canonical file. `plan_tool/scope_out.py:_resolve_carved_detail_path()` relies on this to report a lost declared detail rather than treating the step as never detailed.

- **Do not change run behavior while extracting.** `plan_tool/detail.py:generate_detail()` must continue to author to the canonical path and update `Step.detail`; review prompt rendering, fingerprints, and scope-out must continue to resolve the same legacy run artifact for the same plan state. The rejected alternative is adding jira-grade behavior directly to these existing branches before the shared contract exists; that would mix a behavior change with this compatibility refactor.

## Tests

- `tests/test_detail_artifacts.py:test_explicit_legacy_detail_path_wins — A step with `Step.detail` resolves to that repo-relative run artifact, even when its filename is noncanonical.
- `tests/test_detail_artifacts.py:test_unset_legacy_pointer_uses_canonical_run_path — A step without `Step.detail` resolves to the path defined by `plan_tool/detail.py:derive_detail_path()`.
- `tests/test_detail_artifacts.py:test_missing_explicit_pointer_is_not_canonical_fallback — A missing declared path stays distinguishable from a step that has never had a detail artifact.
- `tests/test_detail_artifacts.py:test_depth_specific_paths_do_not_collide — Run-grade and reserved jira-grade routes for one plan step are distinct and deterministic.
- `tests/test_detail.py:TestDeriveDetailPath — Existing canonical layout and zero-padded step-id behavior remain unchanged.
- `tests/test_detail.py:TestFindUnreferencedDetailForStep — Exact canonical adoption remains allowed while stale-slug siblings remain unadopted.
- `tests/test_fingerprint.py:test_detail_bundle_fingerprint_hashes_present_detail — A pointed legacy run detail produces the same fingerprint entry as before.
- `tests/test_fingerprint.py:test_detail_bundle_fingerprint_omits_bare_step — A step with no on-disk legacy artifact still contributes no fingerprint key.
- `tests/test_review.py:check_detail_coverage coverage — Pointed missing files, canonical unreferenced files, same-ID stale-slug orphans, and bare steps keep their current findings.
- `tests/test_review.py:audit_detail_bundle_status coverage — Audit presence status matches the shared artifact resolver for explicit and canonical legacy details.
- `tests/test_detail.py:collect_detail_quality_findings coverage — An unset pointer with an on-disk canonical detail is evaluated as the same legacy run artifact selected by fingerprinting and audit.
- `tests/test_review.py:_filter_symbols_by_detail coverage — An unset pointer with an on-disk canonical detail drives symbol filtering from that legacy run artifact.
- `tests/test_scope_out.py:test_carved_detail_path_matches_narrow_archive — The detail body captured in a carve seed and the artifact scheduled for archive remain the same path.
- `tests/test_scope_out.py:test_set_but_missing_detail_pointer_passes_detail_missing — Scope-out continues to report a declared-but-missing detail without falling back to canonical storage.

### Test-creation order (refactor step)

1. `tests/test_detail_artifacts.py` characterization cases — Pin explicit-pointer precedence, canonical fallback, and the declared-missing versus never-detailed distinction before moving any call site.
2. Existing legacy behavior cases in `tests/test_detail.py`, `tests/test_fingerprint.py`, `tests/test_review.py`, and `tests/test_scope_out.py` — Confirm the current callers’ observable outputs before replacing their local selection branches.
3. Shared future-route collision case in `tests/test_detail_artifacts.py` — Pin that the contract can name a separate jira-grade location without changing the selected run path.

Those characterization tests must stay green, unmodified, after the restructuring.

## Acceptance criteria

- `Step.detail` continues to select the same legacy run-grade file whenever an existing pointed artifact is resolved.
- `plan_tool/detail.py:generate_detail()` continues to author to the canonical run-grade path and update `Step.detail`, including when a prior pointer is custom.
- A step without `Step.detail` continues to use `plan_tool/detail.py:derive_detail_path()` for its legacy run-grade artifact.
- A missing explicit `Step.detail` is distinguishable from an unset pointer and never silently falls back to a canonical file.
- `plan_tool/fingerprint.py:compute_detail_bundle_fingerprint()`, `plan_tool/review.py:audit_detail_bundle_status()`, and `plan_tool/scope_out.py:_resolve_carved_detail_path()` agree on the run-detail path for the same plan state.
- `plan_tool/detail.py:collect_detail_quality_findings()` and `plan_tool/review.py:_filter_symbols_by_detail()` use the same legacy run-detail resolution as fingerprinting and audit, including an unset pointer with an on-disk canonical detail.
- A canonical detail file is still adopted only when its full canonical filename matches; `check_detail_coverage()` retains its separate `plan-details/<slug>/<NN>-*.md` scan so a same-ID stale-slug file remains unreferenced.
- The shared artifact contract can derive a deterministic jira-grade route that does not collide with the retained run-grade route for the same step.
- All existing tests in `tests/test_detail.py`, `tests/test_fingerprint.py`, `tests/test_review.py`, and `tests/test_scope_out.py` remain green, with quality-audit coverage updated to assert that an unset pointer with an on-disk canonical detail is audited.
- `tests/test_detail_artifacts.py` passes its explicit-pointer, fallback, missing-pointer, and collision cases.

## References

- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — Use `Path` operations for deterministic, collision-safe artifact routing.
- [pytest API Reference](https://docs.pytest.org/en/stable/reference/reference.html) — Use temporary directories and parametrized cases for resolver compatibility tests.

## Deferred

- Jira-grade detail authoring, validation, and persistence — Step 2 owns producing the separate compact artifacts after this shared path contract exists.
- Jira consuming jira-grade detail directly — Step 3 owns that consumer and its prompt contract.
- Opt-in run rendering from jira-grade detail — Step 4 owns that renderer while this step keeps the current run path unchanged.
- Bulk migration or rewriting of legacy run-grade bundles — Explicitly out of scope; legacy artifacts remain readable as run-grade control data.
