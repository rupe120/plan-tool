> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Move the --iterate loop's private helper functions into completeness_phases.py

## Summary

`plan_tool/cli/completeness_cmd.py` defines 18 small, mostly-pure helper functions (severity formatters, coverage/bar-blocking computations, halt-message renderers) whose only real consumer is `_run_iterate_convergence_loop` — the `--iterate` loop that step 2 will relocate next. This step moves all 18 function bodies verbatim into `plan_tool/cli/completeness_phases.py` (the module that already hosts this command's other phase logic) and re-imports every one of them back into `completeness_cmd.py`, so every existing caller — `_run_iterate_convergence_loop` itself, `cmd_completeness`, `finalize_completeness_run`, `cmd_completeness_apply`, `_resolve_audit_reuse`, `_completeness_has_blocking_findings`, `plan_tool/cli/app.py`'s re-export, and the direct test imports in `tests/cli/test_completeness_cmd.py` / `tests/test_convergence.py` — keeps resolving with zero call-site edits. The key design decision is importing the 18 names as **bare names**, not through a qualified `completeness_phases.<name>` reference, which keeps `_run_iterate_convergence_loop`'s ~1096-line body completely untouched (its own relocation is step 2's job). Observable result on green: identical CLI behavior (flags, output, exit codes, files written) and a full test suite that passes with no assertion changes beyond two new tests pinning the new module-ownership invariant.

## Table of Contents

- [Why](#why) — what's out of place today and why this step exists
- [Files (creates vs edits)](#files-creates-vs-edits) — which files change and how
- [Implementation](#implementation) — the move, the import rewiring, and what must not change
- [Tests](#tests) — existing coverage that must stay green, plus two new invariant tests
- [Acceptance criteria](#acceptance-criteria) — checkable facts about the resulting tree
- [References](#references) — the one plan-level reference relevant to this step
- [Applicable guardrails](#applicable-guardrails) — the plan fences this step must respect
- [Deferred](#deferred) — what a reader might expect here but isn't

## Why

`completeness_cmd.py` is supposed to be a thin CLI handler — argument validation, dispatch, and terminal-output/exit-code mapping — but it currently also hosts 18 small support functions for the `--iterate` convergence loop (severity-count formatting, coverage/bar-blocking computation, halt-message rendering) that have nothing to do with argparse or dispatch. `completeness_phases.py` already exists as the landing spot for this command's other phase logic (`_run_deterministic_checks`, `_sample_conceptual_audit`, the rendering/persistence tail), but its own module docstring currently states these particular 18 stay behind because moving them "would force a back-import (cycle)." That claim doesn't hold: `completeness_phases.py` never needs to import anything back from `completeness_cmd.py` to house these functions, since none of the 18 call anything that only exists in `completeness_cmd.py`. Relocating them first is what step 2 needs before it can move `_run_iterate_convergence_loop` itself — the loop's own callees have to already live somewhere that isn't the module being vacated.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/cli/completeness_cmd.py` — delete the 18 function definitions; extend the existing `from plan_tool.cli.completeness_phases import (...)` block with all 18 names; trim the now-unused `CARRIED_RESOLUTION_APPLIED` / `CARRIED_RESOLUTION_BLOCKED` / `CARRIED_RESOLUTION_OPEN` names from its `plan_tool.review` import (keep `CARRIED_RESOLUTION_SKIPPED` — still used directly).
- `plan_tool/cli/completeness_phases.py` — add the 18 function definitions verbatim; add `GRADE_DEFAULT` to its existing `plan_tool.jira_grade` import line; add the handful of function-local imports the moved bodies need (detailed below).
- `plan_tool/cli/app.py` — no code changes. Its existing `from plan_tool.cli.completeness_cmd import (_finding_progress_label, _fmt_finding_counts, ...)` line must keep resolving through `completeness_cmd.py`'s re-import; verify this rather than assume it.
- `tests/cli/test_completeness_cmd.py` — no changes to any existing import statement or assertion; add one small new test class pinning the module-ownership invariant this step establishes.
- `tests/test_convergence.py` — no changes required. Its four function-local `from plan_tool.cli.completeness_cmd import compute_conceptual_bar_blocking_ids` imports continue to resolve unchanged.

## Implementation

**The move.** Cut all 18 function definitions — signature, docstring, and body, unedited — out of `plan_tool/cli/completeness_cmd.py` and paste them into `plan_tool/cli/completeness_phases.py`: `_fmt_finding_counts`, `_finding_progress_label`, `_resolution_for_verdict`, `_effective_audit_passes`, `_completeness_detail_grade`, `_sampled_bundle_status`, `_coverage_input_from_reusable_audit`, `_conceptual_bar_from_audit_recs`, `_warn_if_audit_incomplete`, `_sc_manual_fix_note`, `_remap_iterate_stop_for_conceptual_bar`, `_conceptual_bar_remedy_lines`, `_print_conceptual_bar_stop_remedies`, `_print_all_auto_apply_deferred_halt_message`, `compute_conceptual_bar_blocking_ids`, `_warn_audit_incomplete`, `_split_conceptual_recs`, `_conceptual_completeness_manual_fix_note`. None of their docstrings claim their own file location, so nothing in the moved text itself needs editing. Placement inside `completeness_phases.py` isn't load-bearing (module-level function calls resolve at call time, not definition order) — one reasonable spot is beside the audit-stage/bundle-status helpers already relocated there (`derive_audit_stage`, `emit_bare_plan_banner`, `emit_coverage_unconfirmed`), since these 18 are the same class of `--iterate`-loop support logic, but group them however reads cleanest.

**Import adjustments in `completeness_phases.py`.** This module already has an established split: module-level imports for light dependencies (`jira_grade`, `audit_shapes`, `style`), function-local imports for the heavier domain modules (`plan_tool.review`, `plan_tool.review_persistence`, `plan_tool.convergence`) — every existing `plan_tool.review*` reference in this file is already a per-function `from ... import ...` inside the function body, never a module-level one. Follow that convention for the moved bodies:

- `_completeness_detail_grade` reads `GRADE_DEFAULT` — add it to the existing `from plan_tool.jira_grade import (GRADE_JIRA, GRADE_RUN)` line.
- `_resolution_for_verdict` reads `CARRIED_RESOLUTION_APPLIED` / `_BLOCKED` / `_SKIPPED` / `_OPEN` — give it its own function-local `from plan_tool.review import (...)`.
- `_sampled_bundle_status` constructs a `DetailBundleStatus` — function-local `from plan_tool.review import DetailBundleStatus`. (Its `-> DetailBundleStatus` return annotation needs no import: `from __future__ import annotations` is active in this file, so annotations are strings.)
- `_conceptual_bar_from_audit_recs` and `_warn_if_audit_incomplete` both call `audit_coverage_qualifies_sample` — function-local `from plan_tool.review_persistence import audit_coverage_qualifies_sample` in each, matching this file's existing per-function pattern.
- `compute_conceptual_bar_blocking_ids` already imports its two dependencies (`plan_tool.convergence.CONCEPTUAL_SOURCES` / `is_blocking_finding`, `plan_tool.review.classify_finding_domain`) function-locally inside its own body — moves as-is, no change.
- The remaining 12 (`_fmt_finding_counts`, `_finding_progress_label`, `_sc_manual_fix_note`, `_effective_audit_passes`, `_coverage_input_from_reusable_audit`, `_remap_iterate_stop_for_conceptual_bar`, `_conceptual_completeness_manual_fix_note`, `_split_conceptual_recs`, `_conceptual_bar_remedy_lines`, `_print_conceptual_bar_stop_remedies`, `_print_all_auto_apply_deferred_halt_message`, `_warn_audit_incomplete`) need nothing new — `sys`, `warn`, and `info` are already module-level in `completeness_phases.py`.

**Re-import in `completeness_cmd.py`.** Extend the existing `from plan_tool.cli.completeness_phases import (...)` block (currently `_IterateOutcome`, `_persist_and_present_report`, `_render_completeness_json`, `_render_grouped_report`, `_resolve_plan_for_report`, `_run_deterministic_checks`, `_sample_conceptual_audit`, `derive_audit_stage`, `write_pre_apply_audit_checkpoint`) to add all 18 names as bare names. `_run_iterate_convergence_loop` alone directly calls 14 of them by bare name across its body — `_sampled_bundle_status`, `_completeness_detail_grade`, `_effective_audit_passes`, `_coverage_input_from_reusable_audit`, `_conceptual_bar_from_audit_recs`, `_warn_if_audit_incomplete`, `_sc_manual_fix_note`, `_remap_iterate_stop_for_conceptual_bar`, `_conceptual_bar_remedy_lines`, `_print_conceptual_bar_stop_remedies`, `_print_all_auto_apply_deferred_halt_message`, `_resolution_for_verdict`, `_fmt_finding_counts`, `_finding_progress_label` — so it is, by itself, the reason nearly all 18 need re-importing. The remaining names have their own surviving callers: `cmd_completeness` calls `_effective_audit_passes`, `_completeness_detail_grade`, and `_sampled_bundle_status` directly; `finalize_completeness_run` calls `_coverage_input_from_reusable_audit`, `_conceptual_bar_from_audit_recs`, `_warn_if_audit_incomplete`, and `_split_conceptual_recs` directly; `cmd_completeness_apply` calls `_finding_progress_label` and `_resolution_for_verdict`; `_resolve_audit_reuse` calls `_warn_audit_incomplete`; `_completeness_has_blocking_findings` calls `compute_conceptual_bar_blocking_ids`. One of the 18, `_conceptual_completeness_manual_fix_note`, has no caller left directly inside `completeness_cmd.py` once its own callers (`_conceptual_bar_remedy_lines`, `_print_all_auto_apply_deferred_halt_message`) move alongside it — re-import it anyway, for uniformity with the other 17 rather than computing a smaller subset by hand.

Import all 18 as **bare names** (`from plan_tool.cli.completeness_phases import _fmt_finding_counts`), not as a qualified `completeness_phases.<name>` access rewritten into each call site. `_run_iterate_convergence_loop`'s body already calls these by bare name; a bare-name import keeps every one of those call sites at a zero-line diff, because the function's `__globals__` is still `completeness_cmd`'s module dict and `from X import Y` binds `Y` directly into that dict. Rewriting ~15 call sites across a ~1096-line function to a qualified form is both unnecessary here and not this step's job — that qualified-reference convention belongs to step 2, applied once the loop's own definition relocates.

**Trim what becomes unused.** `CARRIED_RESOLUTION_APPLIED`, `CARRIED_RESOLUTION_BLOCKED`, and `CARRIED_RESOLUTION_OPEN` in `completeness_cmd.py`'s `plan_tool.review` import become dead once `_resolution_for_verdict` moves — their only reference in this file was inside that function's body. Remove them. Keep `CARRIED_RESOLUTION_SKIPPED`: `_run_iterate_convergence_loop` constructs a `(CARRIED_RESOLUTION_SKIPPED, "deferred")` tuple directly for a deferred finding, independent of `_resolution_for_verdict`. Keep `GRADE_DEFAULT` and `audit_coverage_qualifies_sample` in `completeness_cmd.py`'s own imports too — both have surviving direct callers outside the 18 (`register()`'s argparse default/help text for `GRADE_DEFAULT`; `_resolve_audit_reuse` and `classify_qualified_audit_result` for `audit_coverage_qualifies_sample`), so neither import goes away even though `completeness_phases.py` now also imports its own copy independently.

**What not to touch.** Leave both modules' docstrings alone beyond the import-list change already described. `completeness_phases.py`'s module docstring currently gives the "pinned, re-exported `_fmt_finding_counts`/`_finding_progress_label`" claim as the reason the `--iterate` loop stays in `completeness_cmd.py`; correcting that belongs to step 2, whose own intent states both the reason and the conclusion go false once that step lands and names itself as owner of the fix. `completeness_cmd.py`'s own module docstring still correctly describes `_run_iterate_convergence_loop` as one of its named phase helpers after this step — that line only goes stale once step 2 actually relocates the loop, and step 5's intent names itself as owner of clearing it. Don't touch `docs/AUDIT_FLOW.md`'s "Conceptual bar blocking set" row (which cites `compute_conceptual_bar_blocking_ids` as living in `completeness_cmd.py`) or the `BUG_BACKLOG.md`/`BACKLOG.md` citations of these functions — step 6 sweeps every doc/backlog citation of every function this plan relocates, once all the moves are done. Don't restructure `tests/cli/COVERAGE_BASELINE.md`: its rows name the *test* that covers a symbol, not the *module* it's defined in (per the table's own "Verdict definitions" section), and none of the 18 are renamed, so no row's content becomes inaccurate.

## Tests

Existing direct-test classes in `tests/cli/test_completeness_cmd.py` — `TestFmtFindingCounts`, `TestFindingProgressLabel`, `TestResolutionForVerdict`, `TestEffectiveAuditPasses` — must pass unmodified; none of their own source needs to change since the names they import keep resolving. The remaining 14 of the 18 are exercised indirectly through full-flow tests of `cmd_completeness`, `cmd_completeness_apply`, `finalize_completeness_run`, and `_run_iterate_convergence_loop` in `tests/cli/test_completeness_cmd.py`, `tests/test_convergence.py`, and `tests/test_cli.py`; these must also pass unmodified — this is the primary behavior-preservation proof for a pure code-motion refactor.

Two new tests pin the invariant this step actually establishes (which module owns these 18 definitions now), rather than re-testing behavior the existing suite already covers:

- `test_relocated_iterate_helpers_are_defined_in_completeness_phases` — for each of the 18 names, asserts the function object's `__module__` is `"plan_tool.cli.completeness_phases"`, checked through both `plan_tool.cli.completeness_phases`'s own attribute and `plan_tool.cli.completeness_cmd`'s re-imported attribute. Checking `__module__` through *both* modules in one assertion is what proves `completeness_cmd.py` re-imports each name rather than redefining it — a stray leftover `def` in `completeness_cmd.py` would report `__module__ == "plan_tool.cli.completeness_cmd"` and fail this check even though every call site still works.
- `test_completeness_phases_source_never_imports_completeness_cmd` — a source-text scan of `plan_tool/cli/completeness_phases.py` asserting no import statement (module-level or function-local) names `completeness_cmd`, matching this repo's existing leaf-import-discipline idiom (source-text regex, as in `tests/test_rate_limit_loop.py:test_leaf_has_no_first_party_runtime_import`) and mechanically checking the one-directional-edge claim `completeness_phases.py`'s own module docstring already makes.

### Tests for this step

- `test_relocated_iterate_helpers_are_defined_in_completeness_phases` (new, `tests/cli/test_completeness_cmd.py`) — pins that all 18 names are owned by `completeness_phases` and merely re-imported by `completeness_cmd`.
- `test_completeness_phases_source_never_imports_completeness_cmd` (new, `tests/cli/test_completeness_cmd.py`) — pins the one-directional import edge.
- Every pre-existing test that imports or exercises any of the 18 names (directly or transitively through `cmd_completeness`/`cmd_completeness_apply`/`finalize_completeness_run`/`_run_iterate_convergence_loop`) — unchanged, must stay green.

Green-before-done gate: the two new tests plus the full existing suite (`uv run pytest tests/ -q -n auto`) must all pass before this step is considered finished.

## Acceptance criteria

- All 18 named functions are defined (their `def` statement) in `plan_tool/cli/completeness_phases.py`; `plan_tool/cli/completeness_cmd.py` contains no `def` for any of the 18, only a module-level re-import.
- `plan_tool/cli/completeness_cmd.py`'s module namespace exposes all 18 names, so `_run_iterate_convergence_loop`'s existing bare-name calls, `cmd_completeness`, `cmd_completeness_apply`, `finalize_completeness_run`, `_resolve_audit_reuse`, and `_completeness_has_blocking_findings` keep resolving with zero edits to their own call sites.
- `_run_iterate_convergence_loop`'s own body has a zero-line diff — the only changes inside `completeness_cmd.py` are the 18 function-body deletions and the import-block edits.
- `plan_tool/cli/app.py` has zero code changes; its existing `_finding_progress_label`/`_fmt_finding_counts` import from `completeness_cmd` still resolves.
- `tests/cli/test_completeness_cmd.py` and `tests/test_convergence.py` require no changes to any existing import statement.
- `plan_tool/cli/completeness_phases.py`'s source contains no import of `plan_tool.cli.completeness_cmd`, in any form, at module level or inside a function body.
- Full test suite (`uv run pytest tests/ -q -n auto`) is green, including the two new tests.
- No CLI-facing behavior changes: flags, printed output, exit codes, and files written by `completeness-audit`/`completeness-apply` are identical before and after.

## References

- [unittest.mock — mock object library](https://docs.python.org/3/library/unittest.mock.html) — explains that a patch targets the namespace holding the name, not the function's original definition site. That's exactly why this step needs **zero** monkeypatch retargeting even though it changes where 18 functions live: no existing test patches any of the 18 by name, and `_run_iterate_convergence_loop`'s own bare-name calls resolve through `completeness_cmd`'s module dict either way, whether that dict holds the original `def` or a re-import.

## Applicable guardrails

- The plan's "## Out of scope" pure-code-motion fence — this step may not change what `completeness-audit --iterate` or `completeness-apply` actually check, apply, or report. Only the module a function is defined in, and the import lines naming it, may change; every function body, signature, and docstring moves unedited.
- The plan's "## Out of scope" note on `tests/cli/COVERAGE_BASELINE.md` — this step does not restructure that file's format. Confirmed no row needs updating: the table tracks test coverage by symbol name, not the symbol's source module, and none of the 18 are renamed.

## Deferred

- Correcting `completeness_phases.py`'s module docstring (the "pinned, re-exported" claim) — step 2's job, once it actually relocates `_run_iterate_convergence_loop` and the claim's conclusion goes false alongside its reason.
- Correcting `completeness_cmd.py`'s module docstring (still lists `_run_iterate_convergence_loop` as its own phase helper) — step 5's job, once the loop's relocation is complete.
- Updating `docs/AUDIT_FLOW.md`'s citation of `compute_conceptual_bar_blocking_ids`'s file location, and the `BUG_BACKLOG.md`/`BACKLOG.md` citations of these functions — step 6's job, which sweeps every doc/backlog citation of every function this plan relocates in one pass after all the moves land.
- Relocating `_run_iterate_convergence_loop` itself, and any of `cmd_completeness_apply`'s internal logic chunks — steps 2 through 5, respectively; this step only unblocks them by moving their shared dependencies.
