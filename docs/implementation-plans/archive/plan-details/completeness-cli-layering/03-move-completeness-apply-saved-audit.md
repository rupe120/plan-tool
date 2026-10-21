> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Move completeness-apply's saved-audit lookup and freshness check into completeness_phases.py

## Summary

`cmd_completeness_apply` in `plan_tool/cli/completeness_cmd.py` opens with a block that has nothing to do with argument parsing or exit-code mapping: it locates the newest (or `--id`-pinned) saved completeness audit, loads it, checks it is a completeness save with current qualified evidence, builds the audit-shape advisory display, and checks whether the detail bundle drifted since the save. This step carves that block, plus the two small helper functions it calls (`_detail_bundle_staleness`, `_saved_audit_revision_is_current`), out of the CLI handler and into `plan_tool/cli/completeness_phases.py` — the module the rest of this plan is already relocating `completeness-audit`'s orchestration logic into. The main design decision is what the new phase function returns: enough (`plan_path`, `saved_path`, the loaded `saved` review, the built advisory-display object, and the drift list) for `cmd_completeness_apply` to keep printing its existing advisories and mapping its existing exit codes in the existing order, with zero output or behavior change. On green, `plan_tool/cli/completeness_cmd.py` no longer defines either helper, `cmd_completeness_apply`'s first ~120 lines collapse to one delegating call plus its existing exit-code/print logic, and the full suite passes with only the two named test-import retargets changed.

## Table of Contents

- [Why](#why) — what's misplaced today and why this slice goes first
- [Input](#input) — the saved-review sidecar schema this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — which files change and how
- [Implementation](#implementation) — what moves, what's new, and the ordering constraint that must survive the move
- [Tests](#tests) — required regression coverage and the optional characterization tests
- [Acceptance criteria](#acceptance-criteria) — checkable facts about the resulting tree
- [References](#references) — stdlib docs relevant to this step's own surface
- [Applicable guardrails](#applicable-guardrails) — the plan fences this step must respect
- [Deferred](#deferred) — what a reader might expect here but isn't

## Why

`plan_tool/cli/completeness_cmd.py`'s module docstring already states the target shape: `cmd_completeness_apply` should be dispatch and exit-code mapping, delegating its real work to named phases in `completeness_phases.py`, the way `cmd_completeness` already does for `_run_deterministic_checks` and `_sample_conceptual_audit`. Today `cmd_completeness_apply` doesn't follow that shape — its saved-audit lookup and freshness check sit inline, mixed with the `--commit` clean-tree gate, the docstring, and printed advisories. This step is the first of three (3, 4, 5) that carve `cmd_completeness_apply`'s ~559 non-CLI lines out piece by piece; it takes the slice the plan's own Architecture section identifies as the natural first cut, because it is self-contained — nothing downstream of it (the `--anchor` narrowing step 4 owns, the walk dispatch step 5 owns) needs to reach back into it except by consuming its output values.

Two helper function *definitions* sit just above `cmd_completeness_apply` in the same file and are called only from inside the range this step moves: `_detail_bundle_staleness` (called once, inside the freshness check) and `_saved_audit_revision_is_current` (called twice — once while scanning for a current saved audit, once re-checking the pinned `--id` case). Neither made step 1's 18-helper list (that pass covered `_run_iterate_convergence_loop`'s call graph, not `cmd_completeness_apply`'s), so they move here instead — matching the plan's stated invariant that a local helper whose only caller is code a step relocates must move with it.

## Input

This step reads the saved-review sidecar `save_review`/`load_review` persist under `<plan-dir>/plan-details/<slug>/reports/` — documented in `DATA_CONTRACT.md`'s "## Saved review sidecar" section and its nested `### SavedReview` field table. The fields the moved code depends on:

- `kind` — must be `"completeness"`; anything else is the "not a completeness audit" rejection.
- `qualified_result` (via `SavedReview.qualified_result`) and `is_pre_apply_checkpoint` — read by `plan_tool.review_persistence.project_saved_completeness_result` / `SavedCompletenessResultView.is_current_final_qualified` (see `DATA_CONTRACT.md`'s "### Qualified audit result" section), which is what `_saved_audit_revision_is_current` actually tests. A save with no `qualified_result` (a legacy version-1/2/3 sidecar, or one saved by a test that didn't set one) is never current, full stop.
- `detail_bundle_fingerprint` / `detail_bundle_fingerprint_present` — read by `_detail_bundle_staleness` for the drift diff.
- `audit_shape_advisory` — read by `plan_tool.completeness_report.prepare_audit_shape_advisory_display` (`DATA_CONTRACT.md`'s "### AuditShapeAdvisory" section); absent or fingerprint-mismatched advisories are simply unavailable, not an error.
- `created_at` — quoted verbatim into the staleness warning text.

One thing worth knowing before writing or reading tests against this range: `tests/cli/test_completeness_cmd.py` carries a module-level `autouse` fixture, `_save_current_completeness_fixtures`, that wraps `review_persistence.save_review` for every test in the file — any `save_review(kind="completeness", ...)` call that doesn't pass its own `qualified_result` gets one backfilled from a real `AuditInputSnapshot.capture` of the plan/detail on disk at save time. That's why the file's existing `_save_completeness`-style test fixtures (e.g. `TestCarriedFindingsWiring._save_completeness`) already produce a *current* save without spelling out `qualified_result` by hand — a test for this step's new phase function can rely on the same fixture behavior rather than hand-building a `qualified_result` dict.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/cli/completeness_cmd.py` — delete `_detail_bundle_staleness` and `_saved_audit_revision_is_current`'s definitions; replace `cmd_completeness_apply`'s saved-audit lookup/freshness block with a call into the new phase function, its `ok`/`rc` check, and the unchanged closure/print/`data_contract_payloads` lines that must stay behind (see Implementation); extend the existing `from plan_tool.cli.completeness_phases import (...)` block with the new function's name.
- `plan_tool/cli/completeness_phases.py` — add `_detail_bundle_staleness` and `_saved_audit_revision_is_current` (verbatim bodies) plus the new phase function and its result type.
- `tests/cli/test_completeness_cmd.py` — retarget `TestDetailBundleStaleness`'s two `from plan_tool.cli.completeness_cmd import _detail_bundle_staleness` imports to `plan_tool.cli.completeness_phases`; optionally add characterization tests for the new phase function (see Tests).

## Implementation

**Move the two helpers verbatim.** `_detail_bundle_staleness(saved, plan_path, repo_root) -> list` and `_saved_audit_revision_is_current(saved, plan_path, repo_root) -> bool` move body-for-body into `completeness_phases.py`, keeping their existing docstrings, signatures, and body-local imports (`plan_tool.fingerprint`, `plan_tool.parser.parse_plan`, `plan_tool.review_persistence.project_saved_completeness_result`). Unlike step 1's 18 helpers, neither needs a bare-name re-import back into `completeness_cmd.py`: every call site of both functions falls inside the range this step also moves, so once the move lands, `completeness_cmd.py` has no remaining reference to either name. Retarget `TestDetailBundleStaleness`'s two direct imports (its `test_flags_drift_and_clean` and `test_empty_for_legacy_save_without_snapshot` cases) to `plan_tool.cli.completeness_phases`; no other test in the file monkeypatches or directly imports either name, and `plan_tool/cli/app.py` doesn't re-export them, so neither needs touching.

**Add one new phase function that does the lookup and returns a result, not a printed decision.** Something like `_resolve_saved_completeness_audit(args, ctx)` in `completeness_phases.py`, following this file's existing `resolve_`-prefixed naming (`_resolve_plan_for_report` already lives here; `resolve_saved_review`/`resolve_plan_for_context`/`_resolve_audit_reuse` are the same pattern elsewhere in this command). It reproduces, unchanged, the control flow currently inline in `cmd_completeness_apply` between the `--commit` gate and the `walk_recs = [...]` sort (the plan's own Architecture section names this as lines ~247–364/365):

- Resolve `plan_path` via `resolve_plan_for_context(ctx, args.name)`, swallowing any exception to `None` — unchanged.
- Either resolve a pinned `saved_path` via `resolve_saved_review(args.name, ctx.repo_root, review_id=args.id, plan_path=plan_path)` (when `args.id` is set), or scan `list_saved_reviews(args.name, ctx.repo_root, plan_path=plan_path)` for the newest `*-completeness.json` whose loaded review is `kind == "completeness"` and current per `_saved_audit_revision_is_current` — unchanged, including the `FileNotFoundError` catch around the whole resolution and the "no current final qualified completeness audit is available" message when the scan finds nothing.
- Load `saved` via `load_review` when the `--id` path didn't already produce one, catching `ReviewLoadError`.
- Re-check `saved.kind != "completeness"` and re-check `_saved_audit_revision_is_current` a second time (this second check is redundant on the scan-loop path — a picked candidate is already current by the way the scan loop selects it — but it's the *only* currency check on the `--id` path, so it stays; don't collapse the two checks into one, that would be a behavior change past this step's fence).
- Build `pre_apply_advisory_display` via `prepare_audit_shape_advisory_display(saved.audit_shape_advisory, plan=current_plan, plan_path=plan_path, repo_root=ctx.repo_root)`, guarded by the same `parse_plan(plan_path)` / `except (OSError, ParseError, ValidationError)` fallback to `None` that's there today — unchanged, and note the current call site does *not* pass `detail_grade` (unlike `write_pre_apply_audit_checkpoint`'s call to the same function), so don't add it here either.
- Compute `drifted_detail = _detail_bundle_staleness(saved, plan_path, ctx.repo_root)` when `plan_path is not None` — unchanged.

Every failure exit in that sequence (the "no current final qualified..." case, the `FileNotFoundError` catch, the `ReviewLoadError` catch, the "not a completeness audit" kind check, and the second currency re-check) keeps its exact current message text and exact current return code (2, 2, 1, 2, 2 respectively) — just carried on the result object instead of printed and returned directly. One reasonable shape, left to your judgment on exact field names:

```python
@dataclass(frozen=True)
class _SavedAuditResolution:
    ok: bool
    rc: Optional[int] = None
    message: Optional[str] = None
    plan_path: Optional[Path] = None
    saved_path: Optional[Path] = None
    saved: Optional[object] = None
    pre_apply_advisory_display: Optional[object] = None
    drifted_detail: list = field(default_factory=list)
```

(required field first, defaulted fields after — the same ordering `_DeterministicReport` already uses in this file, for the same reason: it keeps a partial/positional constructor valid.) `cmd_completeness_apply` then becomes:

```python
resolution = completeness_phases._resolve_saved_completeness_audit(args, ctx)
if not resolution.ok:
    error(resolution.message)
    return resolution.rc
plan_path = resolution.plan_path
saved_path = resolution.saved_path
saved = resolution.saved
pre_apply_advisory_display = resolution.pre_apply_advisory_display
```

**The print order between the advisory and the staleness warning must not change — this is the one real gotcha in an otherwise mechanical move.** Today, the audit-shape advisory prints (if any) *before* the staleness warning prints (if any), because the closure that presents the advisory is built and called at line ~346, and the staleness check (and its `warn()`) runs after, at line ~348–364. If the new phase function both computed *and* printed the staleness warning, it would print before `cmd_completeness_apply` gets a chance to call the advisory-presenting closure — reversing the order from what ships today. Keep the phase function pure (compute `drifted_detail`, don't call `warn()`), and keep both prints where they already are in `cmd_completeness_apply`:

```python
advisory_presented = False

def _present_pre_apply_advisory() -> None:
    nonlocal advisory_presented
    if advisory_presented or pre_apply_advisory_display is None:
        return
    from plan_tool.completeness_report import render_audit_shape_advisory_console
    print(render_audit_shape_advisory_console(pre_apply_advisory_display))
    advisory_presented = True

_present_pre_apply_advisory()

if resolution.drifted_detail:
    warn(
        f"this saved completeness audit may be stale — "
        f"{len(resolution.drifted_detail)} detail file(s) changed since it was "
        f"saved ({saved.created_at}); its findings may no longer match those "
        f"files. Re-run `plan-tool completeness-audit {args.name}` for current "
        f"findings before applying."
    )

data_contract_payloads = _load_saved_data_contract_payloads(saved_path)
```

**The closure and its guard flag stay in `cmd_completeness_apply` — do not move them into the phase function.** The plan's Architecture section is explicit that `_present_pre_apply_advisory` and its `advisory_presented` flag must cross into step 5's territory (the `pre_apply_presentation=` argument to the eventual parallel-apply dispatch) as *one shared object*, not independently reconstructed on each side. Since that later call site is outside this step's range, the closure has to keep living in `cmd_completeness_apply`'s own scope, closing over the `pre_apply_advisory_display` value the phase function returns — building it inside the phase function and handing back a pre-built closure would be a different design than what step 5 is written to expect.

**Leave `_load_saved_data_contract_payloads(saved_path)` and its call where they are.** Its definition (and its two siblings, `_data_contract_payload_target` / `_data_contract_completeness_redirect`) sit further down `completeness_cmd.py` and are a dependency shared between this step's range (which calls it once, at the boundary) and step 5's range (which calls it again, mid-walk). Step 5 owns relocating that trio (see its own detail file); this step just keeps issuing the existing call, now fed by `resolution.saved_path` instead of a freshly-resolved local.

**Wiring:** add `_resolve_saved_completeness_audit` to `completeness_cmd.py`'s existing `from plan_tool.cli.completeness_phases import (...)` block (the one that already names `_run_deterministic_checks`, `_sample_conceptual_audit`, etc.). In `completeness_phases.py`, give the new function its own body-local imports for `plan_tool.locator.resolve_plan_for_context`, `plan_tool.review_persistence.{ReviewLoadError, list_saved_reviews, load_review, resolve_saved_review}`, `plan_tool.parser.{ParseError, ValidationError, parse_plan}`, and `plan_tool.completeness_report.prepare_audit_shape_advisory_display` — this file already imports `review_persistence`/`parser`/`completeness_report` symbols body-locally per function rather than at module scope (`compute_plan_fingerprint` alone is body-imported three separate times), so follow that existing convention rather than hoisting these to the top of the file.

## Tests

Required — everything below must stay green with no assertion changes beyond the two named import retargets:

- `tests/cli/test_completeness_cmd.py::TestDetailBundleStaleness::test_flags_drift_and_clean` — import retargeted to `plan_tool.cli.completeness_phases`; asserts drift detection still returns the changed path(s).
- `tests/cli/test_completeness_cmd.py::TestDetailBundleStaleness::test_empty_for_legacy_save_without_snapshot` — import retargeted; asserts a legacy save with no fingerprint snapshot reports no drift.
- `tests/test_review_walk.py::TestCliCompletenessApplySubcommand::test_errors_when_no_saved_completeness_audit` — unchanged; still drives `main()` and asserts rc 2 with "no current final qualified completeness audit" in stderr.
- `tests/test_review_walk.py::TestCliCompletenessApplySubcommand::test_rejects_non_completeness_save_via_id` — unchanged; still drives `main()` with `--id` against a non-completeness save and asserts rc 2 with "not a completeness audit".
- Every other `tests/cli/test_completeness_cmd.py` class that drives `completeness-apply` through `main()` (`TestCarriedFindingsWiring`, `TestCompletenessApplyParallel`, `TestCompletenessApplyCommit`, `TestApplyFilesCoherence`, `TestCompletenessApplyDetailBundleGate`, `TestCompletenessApplyRunLog`, `TestCompletenessApplyStructuralSplit`) — unchanged; these exercise the moved range only indirectly and prove the refactor didn't change observable behavior.

The plan's own Testing section treats isolated unit coverage for this extraction as a nice-to-have, not a requirement, given the existing `main()`-driven suite already proves the refactor and no new behavior is introduced. The following are recommended, reusing infrastructure already in the file (`SimpleNamespace` args/ctx the way `TestRunDeterministicChecks` builds them, `tmp_repo`, `save_review`) rather than inventing anything new — add them if convenient, don't block completion on them:

- `test_resolve_returns_ok_with_the_newest_current_save` — a current save on disk resolves with `ok=True` and the expected `plan_path`/`saved_path`/`saved.recommendations`.
- `test_resolve_reports_rc_2_when_no_current_save_exists` — no sidecar at all → `ok=False`, `rc=2`, message names `plan-tool completeness-audit`.
- `test_resolve_reports_rc_2_for_a_stale_pinned_id` — a completeness save pinned via `args.id` whose recorded revision no longer matches the plan/detail on disk → `ok=False`, `rc=2`, message says the evidence isn't current. (No existing test exercises this branch today — it's only reachable via `--id`, and the existing `--id` test covers the wrong-`kind` case, not the stale-but-right-kind case.)
- `test_resolve_reports_rc_2_for_a_non_completeness_save_via_id` — mirrors the existing `main()`-level test, but asserted directly against the phase function's return value.
- `test_resolve_reports_rc_1_for_a_malformed_save` — a corrupted sidecar JSON on the pinned `--id` path → `ok=False`, `rc=1`.
- `test_resolve_reports_drift_without_blocking` — a detail file changed after the save → `ok=True` and `drifted_detail` non-empty.
- `test_resolve_advisory_display_present_only_when_shape_advisory_matches` — a saved `audit_shape_advisory` whose fingerprint matches the current plan/detail → `pre_apply_advisory_display is not None`; a save with none → `None`.
- `test_advisory_prints_before_staleness_warning_when_both_fire` — an end-to-end `main()` drive with both a matching `audit_shape_advisory` and a drifted detail file present; asserts the advisory text's position in captured output comes before the staleness-warning text's position. This is the one behavior a purely-static read of the diff won't catch if the ordering constraint above gets missed.

### Tests for this step

The required list above must be green before this step is considered finished; the recommended list is optional and doesn't gate completion. No new test covers new behavior, because this step introduces none — the required tests exist to prove the move didn't change anything observable.

## Acceptance criteria

- `plan_tool/cli/completeness_phases.py` defines `_detail_bundle_staleness`, `_saved_audit_revision_is_current`, and the new resolution phase function; `plan_tool/cli/completeness_cmd.py` defines none of the three.
- `rg "_detail_bundle_staleness|_saved_audit_revision_is_current" plan_tool/cli/completeness_cmd.py` returns no results.
- `cmd_completeness_apply`'s body between the `--commit` gate and `walk_recs = [...]` is: one call into the new phase function, the `ok`/`rc` check, the unchanged `_present_pre_apply_advisory` closure and its immediate call, the unchanged staleness `warn()`, and the unchanged `data_contract_payloads = _load_saved_data_contract_payloads(saved_path)` call.
- Every exit code and printed message text for the five failure/warning paths named in Implementation is the same as current behavior.
- When both an audit-shape advisory and detail-bundle drift apply in the same run, the advisory text appears before the staleness-warning text in captured output — matching today's order.
- `plan_tool/cli/app.py` has no diff (neither moved helper is re-exported there today).
- `uv run pytest tests/ -q -n auto` is green.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — the CLI dispatch/argument-validation layer (`args.name`, `args.id`) that stays in `completeness_cmd.py` and is what the new phase function reads from.
- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — mechanics behind the frozen result type this step adds, matching the existing `_DeterministicReport` pattern (required fields before defaulted ones).
- [unittest.mock — mock object library](https://docs.python.org/3/library/unittest.mock.html) — patches target the lookup namespace, which is why `TestDetailBundleStaleness`'s imports must retarget to wherever the function's `def` actually lives.

## Applicable guardrails

- **Plan intent (zero behavior change).** Every part of this step is a pure relocation: no flag, printed message, exit code, or check/apply/report outcome may change. The ordering constraint and the "leave `_load_saved_data_contract_payloads` in place" rule in Implementation both exist specifically to hold this line.
- **Plan's "Out of scope."** This step doesn't touch `completeness_phases.py`'s location in the package, doesn't touch `cmd_run`, and doesn't change what `completeness-apply` checks, applies, or reports — it only relocates the two named helpers and the lookup/freshness block. It also doesn't restructure `tests/cli/COVERAGE_BASELINE.md` — that table has no existing row for either moved helper, so nothing there needs an entry.
- **Step intent's explicit boundary.** The moved range stops at (and includes) the `_load_saved_data_contract_payloads(saved_path)` call; everything from `walk_recs = [...]` onward belongs to step 4. The `_present_pre_apply_advisory` closure and its `advisory_presented` flag are carried forward *by reference* to whatever step 5 becomes, not relocated now.

## Deferred

- Moving `walk_recs`'s source-ranking/`--anchor` narrowing, the `--jobs`/`--parallel` decision, and the files-coherence apply/skip logic — step 4's range, starting immediately after this step's.
- Moving `_load_saved_data_contract_payloads`, `_data_contract_payload_target`, and `_data_contract_completeness_redirect`'s definitions — a dependency shared with step 5's range; left in place here because step 5 owns the full data-contract trio's relocation (see its own detail file).
- Moving the `_present_pre_apply_advisory` closure and its `advisory_presented` flag out of `cmd_completeness_apply` — they stay inline so step 5 can consume the same object by reference, per the plan's Architecture section.
- Moving the dispatch-and-execute walk tail (serial and parallel) — step 5's range.
- Editing `plan_tool/cli/completeness_cmd.py`'s or `plan_tool/cli/completeness_phases.py`'s own module docstrings — the plan's step 6 intent names steps 2 and 5 as owning those edits (they're the steps whose completion falsifies the docstrings' current claims), not this one.
- Plan-level `## Overview` elaboration (`13f827ff8629927d3a6a0073f8ae5459c920f29fa9b0d4f9b62b7b225cff48fb`) — this step's own Summary/Why cover its scope; the plan's Overview already states the whole-plan goal and needs nothing added on this step's account.
- Plan-level `## Problem statement` elaboration (`4b4dcef2a7b9e8a282249afea4c39824f19247e7ea3e9623fdfd2b838992c25e`) — already covers this range specifically ("saved-audit resolution and freshness/revision-currency checks"); nothing to add.
- Plan-level `## Architecture` elaboration (`bafd6791befc230e29100c87744ed929a6cb00c4e71a1168fdcba790706ccf06`) — the plan's Architecture section already names this step's exact range and the state that must be threaded by reference; this step follows it rather than revising it.
- Plan-level `## Risks` elaboration (`72dda8dc73e851118ec2b57fd1e28be9e7d6f49be6b5c0a9a2e437e275d6f220`) — a behavior-preserving move of a self-contained, non-monkeypatched range adds no new risk beyond what the plan's Risks section already tracks.
- Plan-level `## Steps` elaboration (`e466d1d8f95285e23e97261ab7abd97ab96cce3efabc6d644048f28408f2d8e6`) — this step changes no step's id, title, or dependency graph.
- Plan-level `## Testing` elaboration (`ae9498b434b81c33da8d95ace0435bde26c3d0bd30666b5abafc922433320955`) — this step's own Tests section (above) is the elaboration; the plan's Testing section already states the per-step strategy this follows.
- Plan-level `## Acceptance criteria` elaboration (`62c5ad026e319cb492c516a319e2ecb9354e2dc133ce9949667b12e3d31ca665`) — covered by this step's own Acceptance criteria section.
- Plan-level `## References` elaboration (`10e39018ee270585a0a462209a0dc33bb3a9b23c1c290219a91237462d9cdb42`) — covered by this step's own References section.
- Plan-level `## Out of scope` elaboration (`74b73f49705a852b50f557668e68847846dfbb86c7128a8a3a3e8a8c026fd252`) — the plan's Out of scope section already covers this move; nothing step-specific to add.
- Plan-level `## Deferred` elaboration (`4fe0e8e39d6eebcd154f82f1a8950f81d32bc14792eef42ffcd530c52665cc6d`) — this step's own Deferred section (above) is the elaboration for its own range.
