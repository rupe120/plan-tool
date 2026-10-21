> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Make canonical-only detail files visible to the completeness quality audit

## Summary

At HEAD the completeness audit has a split brain: the audit prompt's detail bundle (`plan_tool/review.py:_format_audit_detail_bundle` / `audit_detail_bundle_status`) falls back to a step's canonical detail path when `Step.detail` is unset, but every deterministic quality check that reads a detail body (`check_detail_body_completeness`, `check_files_coherence`, `check_input_contract_references`, `detect_suppression_shape`, `_read_detail_body`) skips the step on `step.detail is None`. This step routes those checks through step 1's shared resolver in `plan_tool/detail_artifacts.py` so a step with an unset pointer but an on-disk canonical file gets its body judged too, with findings labeled by the canonical repo-relative path. The key design decision: a set pointer stays authoritative — a set-but-missing pointer never falls back to the canonical file, so `check_detail_coverage`'s `missing_on_disk` diagnostic keeps its meaning. On green, a completeness audit over a canonical-only plan reports detail-body findings it silently skipped before, and every pointer-set plan behaves exactly as today.

## Table of Contents

- [Summary](#summary) — the visibility gap and the one resolution rule that closes it
- [Why](#why) — why the audit prompt and the deterministic checks must agree
- [Input](#input) — the step 1 resolver contract this step consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — per-file edits, plus two noted additions to the declared list
- [Implementation](#implementation) — the closed set of check sites, the labeling rule, and the threading constraints
- [Tests](#tests) — new cases per check, all in existing `tests/test_review.py` classes
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the one plan-level reference relevant here
- [Deferred](#deferred) — nearby detail readers deliberately left alone

## Why

A step whose `detail:` pointer was never persisted (the normal state after a split renumbers an unpointed plan, or when authoring wrote the file but the frontmatter update was lost) is already *conceptually* audited: `audit_detail_bundle_status` classifies it as detailed and `_format_audit_detail_bundle` renders its canonical body into the audit prompt. But the deterministic quality battery the same audit runs first — section completeness, footprint coherence, Input contract references, test-strategy contradiction, suppression shape — skips the step entirely, so the audit judges a body no well-formedness check ever looked at. The plan's Architecture section names this exact feature as the behavior change the old step 1 fused into its extraction; step 1 (done first, `depends_on: 1`) shipped the shared resolver precisely so this step is a small, isolated behavior change instead of a rider on a refactor. Step 7 builds on this: grade-aware audit grounding assumes the quality checks and the rendered bundle already share one resolution rule.

## Input

- **Step 1's resolver** (plan_tool/detail_artifacts.py — **step 1 is `done` and the module is merged; verify against it, not against this description**): step 1 produced a state-carrying resolver — pointer set?, resolved path (pointer path when set, else canonical path), on disk? — plus the moved `derive_detail_path` family, with `plan_tool.review` free to import the leaf at module top level (no lazy-import cycle gymnastics). This step consumes that resolver; it must not re-derive canonical paths locally or add a second path convention.
- **The resolution matrix** step 1's characterization tests pin: this step changes only the "pointer unset, canonical exists" row for the quality checks (skip → read). The other three rows — pointer set + exists, pointer set + missing, both absent — keep today's behavior at every site.
- **`audit_detail_bundle_status`'s classification** (already canonical-aware at HEAD): the set of steps the quality checks read must equal the set this function classifies as detailed, so the prompt bundle and the deterministic findings never disagree about which steps have a detail body.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/review.py` — switch the detail-body-reading check sites (enumerated in Implementation) from the inline `step.detail is None` skip to the step 1 resolver; label findings with the resolved repo-relative path; thread `plan_path` to the checks from their in-module callers (`collect_deterministic_findings`, `review_plan_full`, `collect_smell_findings` / the self-consistency battery).
  - `tests/test_review.py` — new cases in the existing per-check classes (see Tests).

- **Also in the step's declared file list** (the plan frontmatter declares both):
  - `plan_tool/cli/completeness_phases.py` — two one-line edits in `_run_deterministic_checks`: pass `plan_path=path` to the `check_detail_body_completeness` and `check_files_coherence` calls (the sibling calls to `check_detail_coverage`, `check_input_contract_references`, and `collect_smell_findings` already pass the plan path). Without this, the named target — the completeness audit — never supplies the plan path and the feature is dead at the command surface.
  - `tests/cli/test_completeness_cmd.py` — one regression case pinning that threading (a canonical-only step's detail-body finding appears in the audit report).

## Implementation

- **The behavior change, in one sentence:** every deterministic quality check in `plan_tool/review.py` that reads a step's detail body treats "pointer unset, canonical file on disk" as "has a detail body", using the canonical file; everything else is unchanged.

- **The closed set of sites to change** (all in `plan_tool/review.py`; grep for `step.detail is None` to confirm the set is still closed at implementation time):
  - `check_detail_body_completeness` — the seven-section check; a canonical-only body now gets `missing` / `placeholder` findings.
  - `check_files_coherence` — footprint-vs-body drift; a canonical-only body now yields `detail_only` / `files_only` findings.
  - `check_input_contract_references` — the per-step `## Input` loop only; the plan-level branch is untouched.
  - `detect_suppression_shape` — the Summary/Why scan; recommend converting its inline read to `_read_detail_body` while there.
  - `_read_detail_body` — the shared helper; extending it gives `build_plan_footprint` and `_deliverable_deferred` (hence `detect_orphaned_deliverable` / `detect_claim_vs_delivery`'s referenced side) the same visibility for free when a plan path is supplied.
  - **Not** `_format_audit_detail_bundle` / `audit_detail_bundle_status` — already canonical-aware; step 1 moved them onto the resolver.
  - **Not** `check_test_strategy_alignment` — it was a site when this step was authored, via the detail loop that re-tagged `collect_change_type_test_order_findings`. That loop and its producer were **removed 2026-07-30** with the withdrawn per-`change_type` test-ordering contract (`CLAUDE.md` § "Withdrawn: …"), so the check reads no detail body at either grade and takes no `plan_path`. Do not re-add it to this set.

- **One resolution rule, owned by the leaf.** Every changed site resolves through step 1's resolver — likely via one small review-local helper that maps the resolver result to "(body text, repo-relative label) or skip", so the selection logic exists once. The invariant: the steps these checks read must match `audit_detail_bundle_status`'s detailed set exactly. Do not fold `check_detail_coverage`'s claimed-by-another-step set into resolution — the bundle doesn't consult it, and matching the bundle is the rule.

- **A set pointer is authoritative — no fallback.** When `step.detail` is set but the file is missing, the checks skip exactly as today; `check_detail_coverage`'s `missing_on_disk` remains the signal. The rejected alternative — "read whichever file exists" — would silently audit a body the launcher will never load and erase the set-but-missing diagnostic (the same collapse step 1's resolver design exists to prevent).

- **Findings label the resolved path, never `None`.** `DetailBodyIssue.detail_path`, `check_input_contract_references`' `location=".../## Input"` and `path=`, and any other field currently fed `step.detail` must carry the canonical file's repo-relative POSIX path for a canonical-only step. Mirror `_format_audit_detail_bundle`'s `relative_to(repo_root)` with the `ValueError` → `as_posix()` fallback.

- **Thread the plan path additively.** Canonical derivation needs the plan file's location, and several changed signatures (`check_detail_body_completeness(plan, repo_root)`, `check_files_coherence(plan, repo_root)`, `_read_detail_body(step, repo_root, max_bytes)`) don't take one. Follow the existing pattern on `build_plan_footprint` / `detect_orphaned_deliverable` / `detect_claim_vs_delivery`: a keyword-only `plan_path: Optional[Path] = None` (plus `plan` where the helper lacks it), where `None` means "no canonical fallback possible — pointer-only, today's behavior". That keeps the out-of-footprint callers (`plan_tool/bench.py`'s coherence count, `plan_tool/cli/inspect.py`'s smell listing, `plan_tool/cli/completeness_cmd.py`'s allowed-mentions promotion) compiling and behaving unchanged without edits. Callers that must pass it: the two review-lane orchestration sites in `plan_tool/review.py` (`collect_deterministic_findings`, `review_plan_full` — both have `plan_path` in scope) and the two calls in `plan_tool/cli/completeness_phases.py:_run_deterministic_checks` noted under Files.

- **Preserved behaviors — not free to vary:**
  - `done` steps stay skipped at the three sites that already skip them — `check_detail_body_completeness`, `check_files_coherence`, `check_input_contract_references` (their findings are pre-execution authoring signals). `detect_suppression_shape` has **never** filtered `done` — it scans every step with a readable body — so the resolution rule applies to it uniformly rather than inventing a `done` carve-out it doesn't otherwise make. Consequence to expect, not to "fix": a `done` step with an unset pointer and a canonical file now reaches that check.
  - `check_detail_coverage`'s `unreferenced_on_disk` finding keeps firing for a canonical-only step. Visibility and the reattach-the-pointer diagnostic are complementary: the audit now judges the body *and* still tells the operator the pointer was never persisted (`plan-tool detail --step N` adopts it).
  - Pointer-set plans are unchanged at every site — the existing suites listed in Tests are the gate and must pass without edits.
  - The changed checks are shared with the reconcile/review lane (`collect_deterministic_findings`, `review_plan_full`); those lanes gain the same visibility. That is intended — the deterministic findings should describe the same bundle the prompts render — and is the "always surface the more-correct plan" direction.
  - Nothing jira-grade lands here. "Canonical" means the run-grade canonical path only; step 3 owns jira-grade routes in the leaf, and steps 7–9 own grade-aware audit grounding. `Step.detail` is never written by this step.

## Tests

New cases in `tests/test_review.py`, inside the existing classes (`TestCheckDetailBodyCompleteness`, `TestCheckFilesCoherence`, `TestCheckTestStrategyAlignment`, `TestSuppressionShape`, `TestBuildPlanFootprint`, `TestCheckDetailCoverage`, `TestDetailBundleStatus`), plus one CLI case in `tests/cli/test_completeness_cmd.py`. All checks here are deterministic — no invoker stubbing needed beyond the existing fixtures.

- `test_detail_body_completeness_reads_canonical_when_pointer_unset` — a canonical-only detail file missing a required H2 yields a `DetailBodyIssue` whose `detail_path` is the canonical repo-relative path.
- `test_detail_body_completeness_set_pointer_never_falls_back` — pointer set to a missing file with a defective canonical file present: no body issues; `check_detail_coverage` still reports `missing_on_disk`.
- `test_detail_body_completeness_plan_path_none_keeps_pointer_only` — omitting `plan_path` reproduces today's skip (pins the compatibility default for `bench.py`-style callers).
- `test_files_coherence_reads_canonical_when_pointer_unset` — a near-miss path cited only in the canonical body surfaces as `detail_only`.
- `test_input_contract_references_labels_canonical_path` — an `## Input` reference issue from a canonical-only body carries `<canonical rel path>:## Input` and the step id.
- `test_suppression_shape_scans_canonical_summary_why` — an unexcused suppression phrase in a canonical-only body's Summary/Why trips the `suppression-shape` rec.
- `test_plan_footprint_referenced_side_includes_canonical_body` — `build_plan_footprint` with `plan_path` counts canonical-body path mentions in the referenced side.
- `test_done_step_canonical_detail_still_skipped` — a `done` step with a canonical-only file produces no findings from any changed check.
- `test_unreferenced_on_disk_still_fires_for_audited_step` — the same canonical-only step that now yields body findings still gets its `unreferenced_on_disk` coverage finding.
- `test_quality_visibility_matches_bundle_status` — a step `audit_detail_bundle_status` classifies as detailed via canonical fallback is read by `check_detail_body_completeness`, and a bare step is skipped by both.
- `test_completeness_audit_reports_canonical_only_detail_findings` (in `tests/cli/test_completeness_cmd.py`) — a completeness audit over a plan with one canonical-only step includes that step's detail-body finding (pins the `_run_deterministic_checks` threading).

(Approx. 12 new tests.)

### Test-creation order (feature step)

Add the unit tests with the implementation, check by check — each changed site lands with its canonical-visibility case and its unchanged-pointer-behavior case in the same edit. Gate: every new test above green, and the existing suites (`tests/test_review.py` as it stands, `tests/test_detail_artifacts.py` from step 1, `tests/cli/test_completeness_cmd.py`) green with no edits to pre-existing cases, before this step is finished.

## Acceptance criteria

- For a step with `Step.detail` unset and its canonical detail file on disk: `check_detail_body_completeness`, `check_files_coherence`, `check_input_contract_references`, and `detect_suppression_shape` all evaluate the canonical body when given the plan path, and every finding names the canonical repo-relative path (no `None` labels).
- For a step with `Step.detail` set: all listed checks behave exactly as at HEAD, including no canonical fallback when the pointed file is missing — pre-existing tests pass unmodified.
- `check_detail_coverage` still emits `unreferenced_on_disk` for a canonical-only step and `missing_on_disk` for a set-but-missing pointer — neither diagnostic is weakened.
- Every changed signature defaults `plan_path` (and any added `plan` param) so `plan_tool/bench.py`, `plan_tool/cli/inspect.py`, and `plan_tool/cli/completeness_cmd.py`'s existing calls run unchanged.
- `plan_tool/cli/completeness_phases.py:_run_deterministic_checks` passes `plan_path` to `check_detail_body_completeness` and `check_files_coherence`; a `plan-tool completeness-audit` over a canonical-only plan reports the step's detail-body findings.
- Path resolution in the changed sites goes through `plan_tool/detail_artifacts.py`'s resolver — no new local canonical-path derivation appears in `plan_tool/review.py` (grep-checkable).
- The ~12 new tests pass; `uv run pytest tests/ -q` is green with no edits to pre-existing test cases.

## References

- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — for the tmp-path plan/detail fixtures the new deterministic-check cases build on.

## Deferred

- Canonical fallback for `heuristic_already_done` / `_filter_symbols_by_detail` — reconcile-lane evidence heuristics, not the completeness quality audit; widening their evidence base is a separate decision to route through reconcile or the backlog.
- Threading `plan_path` into `plan_tool/cli/completeness_cmd.py`'s allowed-mentions promotion call to `check_files_coherence` (it has `plan_path` in scope) — behavior there stays pointer-only for now; thread it when step 9, which owns that file, lands.
- Jira-grade artifact visibility, routing, and grade selection — step 3 owns the collision-safe jira-grade paths; steps 7–9 own grade-aware audit grounding.
- Reattaching the `detail:` pointer automatically when a canonical file is found — `plan-tool detail --step N` adoption remains the repair path; this step audits and never writes frontmatter.
- Prefix-orphan detail files (same `NN-` id, different slug) — remain invisible to the quality checks by design, matching the resolver's exact-canonical-name adoption rule and `validate`'s ownership of that diagnostic.
