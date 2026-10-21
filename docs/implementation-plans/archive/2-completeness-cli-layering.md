> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Completeness Cli Layering
intent: 'Restore the "thin CLI handler" contract for `plan_tool/cli/completeness_cmd.py`
  over its two largest orchestration blocks: `_run_iterate_convergence_loop`
  (~1086 lines) and the non-CLI logic chunks inside `cmd_completeness_apply`
  (~559 lines) move to `plan_tool/cli/completeness_phases.py` — already the
  de facto orchestrator for this command''s supporting logic — with zero
  behavior change. `finalize_completeness_run`, `_resolve_audit_reuse`, and
  the qualified-audit-result classification cluster deliberately stay in
  `completeness_cmd.py` (see Acceptance criteria) — this plan thins the two
  largest blocks, not every non-dispatch function in the module.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Move the --iterate loop's private helper functions into completeness_phases.py
  intent: Unblock moving the --iterate loop out of the CLI handler by relocating the
    18 completeness_cmd.py-local helpers it (transitively) calls — the original 14
    (_fmt_finding_counts, _finding_progress_label, _resolution_for_verdict, _effective_audit_passes,
    _completeness_detail_grade, _sampled_bundle_status, _coverage_input_from_reusable_audit,
    _conceptual_bar_from_audit_recs, _warn_if_audit_incomplete, _sc_manual_fix_note,
    _remap_iterate_stop_for_conceptual_bar, _conceptual_bar_remedy_lines, _print_conceptual_bar_stop_remedies,
    _print_all_auto_apply_deferred_halt_message) plus 4 more a transitive-closure
    pass over those 14's own call graph surfaced — compute_conceptual_bar_blocking_ids
    (called by _conceptual_bar_from_audit_recs), _warn_audit_incomplete (called by
    _warn_if_audit_incomplete), _split_conceptual_recs (called by both _conceptual_bar_remedy_lines
    and _print_all_auto_apply_deferred_halt_message), and _conceptual_completeness_manual_fix_note
    (called by both of those same two). completeness_phases.py's own module docstring
    states the import edge is one-directional (completeness_cmd -> completeness_phases)
    specifically to avoid a back-import cycle, which is exactly what leaving any of
    these 4 behind would force. Re-import every one of the 18 back into completeness_cmd.py
    for its own surviving callers -- do not assume "moved" means "no longer needed
    here" — cmd_completeness and finalize_completeness_run need _effective_audit_passes,
    _completeness_detail_grade, _sampled_bundle_status, _coverage_input_from_reusable_audit,
    _conceptual_bar_from_audit_recs, _warn_if_audit_incomplete; finalize_completeness_run
    additionally needs _split_conceptual_recs (a caller the original helper list never
    named); cmd_completeness_apply (staying in completeness_cmd.py until steps 3-5
    land) needs _finding_progress_label and _resolution_for_verdict; _resolve_audit_reuse
    needs _warn_audit_incomplete; _completeness_has_blocking_findings needs compute_conceptual_bar_blocking_ids.
    Outside completeness_cmd.py, plan_tool/cli/app.py re-exports _finding_progress_label
    and _fmt_finding_counts from this module onto the plan_tool.cli package surface;
    tests/cli/test_completeness_cmd.py imports _finding_progress_label, _fmt_finding_counts,
    _resolution_for_verdict, and _print_all_auto_apply_deferred_halt_message directly
    for isolated unit tests; and tests/test_convergence.py separately imports compute_conceptual_bar_blocking_ids
    directly in four tests (test_compute_conceptual_bar_blocking_ids_bare_medium_correctness_blocks
    and three siblings) -- all three external consumers need a module-level (not function-local)
    re-import somewhere they resolve, and the choice of where must be made explicitly
    rather than left to whichever happens to still resolve (completeness_cmd.py's
    own re-import of compute_conceptual_bar_blocking_ids, already required above for
    _completeness_has_blocking_findings's sake, satisfies test_convergence.py's four
    tests as a side effect -- confirm that side effect rather than treating it as
    incidental).
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/app.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_convergence.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/completeness-cli-layering/01-move-iterate-loop-private-helper.md
  status: done
- id: 2
  title: Move the --iterate convergence loop itself into completeness_phases.py
  intent: 'Restore the thin-handler contract for the completeness-audit CLI module
    by relocating its single largest orchestration block into the module that already
    houses this command''s other phase logic (_run_deterministic_checks, _sample_conceptual_audit,
    the rendering/persistence tail). completeness_cmd.py calls the relocated function
    via a qualified reference (completeness_phases._run_iterate_convergence_loop(...),
    importing the module not the bare name) -- matching this codebase''s own established
    convention for a relocated phase (completeness_phases.py''s docstring already
    states this for apply_finding and shell_review_invoker: "patched on their domain
    modules, so relocating these phases retargets nothing"). Under a qualified reference,
    every monkeypatch or import that currently targets completeness_cmd.py''s bare
    _run_iterate_convergence_loop name stops resolving once the call site moves and
    must retarget to completeness_phases: the direct monkeypatch at tests/cli/test_completeness_cmd.py:11100;
    the module-level `from plan_tool.cli.completeness_cmd import _run_iterate_convergence_loop`
    at that file''s line 73 and its ~14 direct, unmocked calls reusing that name (e.g.
    lines 7434, 8128, 8857, 9167, 10819, 10872, 10934, 10994, 11223, 11286, 11440,
    11591, 12442, 12461) plus 7 `inspect.getsource(_run_iterate_convergence_loop)`
    checks across 7 distinct tests (six single-line calls plus one multi-line call
    a naive single-line grep misses -- this plan body deliberately does not restate
    the per-test line numbers here, since step 2''s own detail file already carries
    the verified, complete site list and duplicating it in two places is exactly how
    an earlier round of this plan drifted -- see that file''s Tests section for the
    authoritative mapping); and the three tests patching `completeness_cmd.write_pre_apply_audit_checkpoint`
    (lines 7419, 8844, 9144) to intercept the loop''s own call to that already-relocated
    completeness_phases.py:488 function -- once the loop''s body sits in the same
    module as that function, the call resolves locally and those three patches go
    silent. Retarget every one of these sites to completeness_phases in this step,
    not discovered mid-implementation; this is the concrete, complete site list the
    qualified-reference design choice above implies, not a partial one. Also update
    completeness_phases.py''s own module docstring, which currently gives the pinned
    _fmt_finding_counts/_finding_progress_label re-export as the reason _run_iterate_convergence_loop
    stays in completeness_cmd.py -- both the reason (step 1 moves those helpers) and
    the conclusion (this step moves the loop itself) are false once this step lands.'
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_completeness_cmd.py
  complexity: high
  change_type: refactor
  depends_on:
  - 1
  depends_on_notes:
    1: relocates the loop's 18 local helper dependencies first, removing the back-import
      cycle completeness_phases.py's own docstring says currently keeps the loop pinned
      to completeness_cmd.py
  detail: docs/implementation-plans/plan-details/completeness-cli-layering/02-move-iterate-convergence-loop-itself.md
  status: done
- id: 3
  title: Move completeness-apply's saved-audit lookup and freshness check into completeness_phases.py
  intent: Give completeness-apply's saved-audit lookup and freshness/revision-currency
    check (completeness_cmd.py lines ~247-365, the code preceding the source-ranking
    logic step 4 moves -- extended by one line from an earlier round's ~247-364 to
    include the data_contract_payloads = _load_saved_data_contract_payloads(saved_path)
    call at line 365, which neither this step's nor step 4's stated range previously
    covered) a home in the orchestrator module instead of the CLI handler, as the
    first slice of the apply-side extraction. Also relocate two helper function *definitions*
    that sit just above this range (immediately before cmd_completeness_apply begins
    at line 195) but are called only from inside it -- _detail_bundle_staleness (completeness_cmd.py:130-157,
    called at line 353) and _saved_audit_revision_is_current (completeness_cmd.py:183-194,
    called at lines 274 and 303) -- neither is in step 1's 18-helper list or this
    step's own prior scope, even though both are exactly the class of local dependency
    the invariant in steps 4/5 already names. Retarget _detail_bundle_staleness's
    two direct test imports (tests/cli/test_completeness_cmd.py:7836, :7858) to completeness_phases
    as part of this step. Confirmed clean of the test-seam hazard steps 2, 4, and
    5 carry — no monkeypatch targets this range in tests/cli/test_completeness_cmd.py,
    so its other tests need only import-path updates. Also carries the _present_pre_apply_advisory
    closure and its advisory_presented flag (~337-344) forward by reference to whatever
    step 5 becomes (see step 5's intent) and shares _load_saved_data_contract_payloads
    / _data_contract_payload_target / _data_contract_completeness_redirect (~1057-1108)
    with step 5's range -- step 5 owns relocating all three (including the _data_contract_completeness_redirect
    monkeypatch retarget), settled in step 5's own detail file; this step only calls
    _load_saved_data_contract_payloads at its own boundary and re-imports it back
    into completeness_cmd.py for that call.
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_completeness_cmd.py
  complexity: low
  change_type: refactor
  detail: docs/implementation-plans/plan-details/completeness-cli-layering/03-move-completeness-apply-saved-audit.md
  status: done
- id: 4
  title: Move completeness-apply's finding-narrowing, parallel-mode decision, and
    files-coherence fix into completeness_phases.py
  intent: 'Move three sequential, jointly-scoped blocks (completeness_cmd.py lines
    ~377-507, immediately following step 3''s range) out of the CLI handler and next
    to the rest of the apply orchestration: (a) source ranking / --anchor narrowing
    (~377-402) producing walk_recs/conceptual_walk_recs; (b) the --jobs/--parallel
    decision (~404-438) that resolves _parallel and validates its preconditions (-y
    required, clean working tree) -- deliberately grouped with (a) because it reads
    conceptual_walk_recs to decide whether parallel mode degrades to serial; (c) the
    files-coherence apply/skip logic (~440-507), gated on both _parallel (from b)
    and the plan''s bare/detail-bundle status. Do not extend this step''s range into
    the dispatch-and-execute logic starting at "answered = 0" (~509) -- that is step
    5''s, including the parallel dispatch call at line ~542, which sits inside step
    5''s range positionally even though it is a consequence of this step''s _parallel
    decision. INVARIANT (do not treat the line ranges above as a complete inventory
    -- re-derive this by grep at implementation time, the same way step 1''s transitive-closure
    method was used, rather than trusting this plan''s own prior enumeration): every
    completeness_cmd.py-local helper function or module constant whose only caller
    is code this step moves must move with it, or be identified as needing a re-import
    back for a surviving caller -- leaving one behind while its sole caller relocates
    recreates exactly the back-import cycle this whole plan exists to remove. Already
    found this way and confirmed owned by this step: _apply_files_coherence''s own
    definition (completeness_cmd.py ~941-1032; its only call site is inside this step''s
    ~440-507 range) and the module constants _CONCEPTUAL_APPLY_SOURCE_RANK, _BARE_PLAN_WALKABLE_SOURCES,
    _DATA_CONTRACT_SOURCE, _DATA_CONTRACT_TARGET, _SAVED_SERIAL_APPLY_SOURCE_RANK
    (~1033-1056), read by this step''s ranges, plus _COMPLETENESS_SEVERITY_RANK (same
    range) -- verified this round to have zero references anywhere in the repo, so
    it is dead code rather than "read by this step''s ranges" as an earlier round
    claimed; its relocation stays harmless, just for a different reason than stated.
    This step also owns five apply-side test-retarget classes, not the four named
    in an earlier round: monkeypatch retargets for _apply_files_coherence (3 tests:
    test_bare_plan_skips_files_coherence_writer, test_bare_plan_still_skips_files_coherence_when_the_walk_runs,
    and one asserting exact call args) and for working_tree_dirty''s clean-tree-gate
    check -- not 2 sites (test_dirty_tree_refused, test_tty_without_yes_refused) but
    15 total, since every --jobs N>1 test must clear this same gate before reaching
    step 5''s parallel dispatch: 12 more inside TestCompletenessApplyParallel (lines
    9854, 9951, 9981, 10009, 10050, 10085, 10174, 10222, 10253, 10287, 10331, 10384)
    and one in TestCompletenessApplyStructuralSplit (line 10629), all confirmed passing
    --jobs > 1. Also retarget _apply_files_coherence''s shared module-level import
    (tests/cli/test_completeness_cmd.py:69-77, the same `from plan_tool.cli.completeness_cmd
    import (...)` block step 2''s _run_iterate_convergence_loop is also on) and its
    6 direct, non-monkeypatch calls in TestApplyFilesCoherence (lines 6742, 6753,
    6761, 6764, 6788, 6803), which exercise its real behavior rather than stubbing
    it -- getting either of _apply_files_coherence''s new-home imports wrong breaks
    not just its own call sites but the shared 69-77 import statement in its entirety.
    Not step 5, which an earlier round of this plan incorrectly assigned the monkeypatch
    retargets to.'
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 1
  - 3
  depends_on_notes:
    1: this chunk also calls _finding_progress_label, already relocated to completeness_phases.py
      in step 1
    3: needs the saved review, plan_path, and data-contract payloads step 3 resolves
  detail: docs/implementation-plans/plan-details/completeness-cli-layering/04-move-completeness-apply-finding.md
  status: done
- id: 5
  title: Move completeness-apply's walk execution (serial and parallel) into completeness_phases.py
  intent: 'Move the dispatch-and-execute tail of cmd_completeness_apply (completeness_cmd.py
    lines ~509-753, everything from "answered = 0" through the function''s closing
    return) into completeness_phases.py, along with the standalone _apply_walk_recs_parallel
    function it delegates to for the --jobs N>1 path (completeness_cmd.py lines ~756-927,
    ~172 lines -- a sibling top-level function doing the same class of non-CLI orchestration
    work as the serial engine, not itself part of cmd_completeness_apply''s body but
    called from inside the range this step moves), and the small _completeness_apply_commit_subject
    helper (~935-939) both call -- also imported directly (not monkeypatched) in test_apply_subject_singular_and_plural
    (tests/cli/test_completeness_cmd.py:6518) to assert its exact output string, a
    third retarget site alongside its two production call sites. This completes the
    apply-side extraction, leaving cmd_completeness_apply as a short sequence of calls
    into the functions steps 3-5 extracted. This step owns retargeting two of the
    five apply-side monkeypatch names (an earlier round said four; _data_contract_completeness_redirect''s
    own monkeypatch at tests/cli/test_completeness_cmd.py:7075 is a fifth, owned by
    step 3/5''s shared dependency per step 3''s intent, not this bullet''s two) --
    walk_recommendations and _build_review_action_fn (exact site counts deliberately
    not restated here -- this plan body''s own audit history shows that restating
    a site count in two places is exactly how it drifts; step 5''s own detail file
    carries the verified, current list) -- plus the working_tree_dirty call site(s)
    inside this step''s own ~509-753 range specifically (distinct from the clean-tree-gate
    check step 4 owns, all 15 of them per step 4''s own corrected intent). _apply_files_coherence''s
    monkeypatch, shared import, and direct-call sites all belong to step 4, not here,
    per the same correction. Also carry forward, by reference not by copy, the _present_pre_apply_advisory
    closure and its advisory_presented flag (defined in step 3''s range, ~337-344,
    an at-most-once guard against double-printing the audit-shape advisory across
    a worker/replay per its own comment) -- it is passed into this step''s _apply_walk_recs_parallel
    call as pre_apply_presentation, so whatever step 3 becomes must hand this exact
    object to whatever step 5 becomes, not have each independently reconstruct a presented
    flag. Same invariant as step 4''s: re-derive the full local-helper/constant dependency
    list by grep at implementation time rather than trusting this step''s own line
    ranges as exhaustive; in particular, _load_saved_data_contract_payloads / _data_contract_payload_target
    / _data_contract_completeness_redirect (completeness_cmd.py ~1057-1108) are called
    from both step 3''s range (~366, at that step''s own boundary) and this step''s
    range (~662). This step owns relocating all three, including the _data_contract_completeness_redirect
    monkeypatch retarget (tests/cli/test_completeness_cmd.py:7075) -- step 3 only
    calls _load_saved_data_contract_payloads and re-imports it back as a bare name
    for that one call, per step 3''s own intent. Also update completeness_cmd.py''s
    own module docstring, which currently lists _run_iterate_convergence_loop as one
    of its own named phase helpers (false after step 2) and claims apply-side monkeypatches
    target completeness_cmd (false after this step) -- this step is the last of the
    two to land, so it owns clearing both stale claims.'
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_completeness_cmd.py
  complexity: high
  change_type: refactor
  depends_on:
  - 1
  - 4
  depends_on_notes:
    1: the walk engine calls _resolution_for_verdict and _finding_progress_label,
      already relocated in step 1
    4: consumes the narrowed walk_recs/conceptual_walk_recs and the parallel-mode
      decision (_parallel) step 4 produces
  detail: docs/implementation-plans/plan-details/completeness-cli-layering/05-move-completeness-apply-walk-execution.md
  status: done
- id: 6
  title: Sweep every doc/backlog citation of the relocated functions and confirm the
    full suite is still green
  intent: 'Every function this plan relocates out of completeness_cmd.py may be cited
    by file path in prose elsewhere in the repo; grep each of the 18 step-1 helpers,
    _run_iterate_convergence_loop, compute_conceptual_bar_blocking_ids, and _apply_walk_recs_parallel
    across docs/, both backlog files, and every other plan under docs/implementation-plans/
    rather than assuming only the two names this plan happens to mention are cited.
    Known hits beyond docs/AUDIT_FLOW.md''s source-map table (whose "Conceptual bar
    blocking set" row cites compute_conceptual_bar_blocking_ids as living in completeness_cmd.py):
    BUG_BACKLOG.md''s "A reused conceptual audit never reports budget_limited coverage
    as unconfirmed" entry cites _run_iterate_convergence_loop''s reused_audit_recs
    branch as living in completeness_cmd.py; BACKLOG.md''s item 88 cites completeness_cmd.py
    for where completeness-apply persists annotations per finding; two other in-progress
    plans cite _run_iterate_convergence_loop''s pre-move path -- docs/implementation-plans/plan-details/per-call-timeout-budgets/02-give-purity-scans-conceptual-audits.md:112
    (a still-open reconciliation this plan should not silently resolve by moving the
    code out from under it -- flag it there, do not edit that plan''s own open question)
    and docs/implementation-plans/plan-details/security-check-command/08-iterate-apply-convergence-loop-security.md
    (cites the path five times as the pattern its own new function is modeled "member-for-member"
    on -- update the citation, do not touch that plan''s design). Also sweep .plan-tool/lessons/project.md
    (21 citations, verified -- tracked in git, not a report, not archived, and read
    by future plan-tool sessions, so a stale entry here is worse than a stale doc
    citation) and three more status: completed sibling-plan detail files sitting in
    the live docs/implementation-plans/ tree, not archive/, each citing a relocated
    symbol with a file-path prefix (three of stage-differentiated-blocking''s four
    detail files -- see this step''s own detail file for the exact per-citation list).
    Scope call: a completed-but-unarchived plan is a live citation needing the fix,
    not closed record like archive/ -- only archive/ and generated report snapshots
    are exempt. Three more sibling-plan detail files (convergence-non-severity-advisories/06,
    completeness-stage-bar-reporting/01, and stage-differentiated-blocking''s remaining
    fourth file, 03-hoist-one-stage-derivation-before.md) were checked and confirmed
    to need no edit -- two cite the symbols by bare name only or already cite both
    post-move files collectively, and 03''s mentions either span both files jointly
    or are its own historical Files-list record of a completed edit, not a live location
    claim -- see this step''s own detail file for why; do not add them back without
    re-verifying they still need no change. plan_tool/cli/completeness_phases.py''s
    and plan_tool/cli/completeness_cmd.py''s own module docstrings are NOT this step''s
    job (they are real .py-file edits, and this step is deliberately non-code) --
    see steps 2 and 5, which now each own updating the docstring claim their own completion
    falsifies. Update every doc/backlog hit found here, then run the full suite and
    confirm zero failures beyond the planned import-path/monkeypatch-target updates
    named in steps 1, 2, 4, and 5.'
  files:
  - docs/AUDIT_FLOW.md
  - BUG_BACKLOG.md
  - BACKLOG.md
  - docs/implementation-plans/plan-details/per-call-timeout-budgets/02-give-purity-scans-conceptual-audits.md
  - docs/implementation-plans/plan-details/security-check-command/08-iterate-apply-convergence-loop-security.md
  - .plan-tool/lessons/project.md
  - docs/implementation-plans/plan-details/stage-differentiated-blocking/03-hoist-one-stage-derivation-before.md
  - docs/implementation-plans/plan-details/stage-differentiated-blocking/04-surface-pass-conformance-compute.md
  - docs/implementation-plans/plan-details/stage-differentiated-blocking/05-steer-iterate-loop-mid-run-stage-bar.md
  - docs/implementation-plans/plan-details/stage-differentiated-blocking/07-update-gate-docs-close-backlog-91-248.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  - 5
  depends_on_notes:
    2: documents the --iterate loop's new home
    5: documents the apply walk's new home
  detail: docs/implementation-plans/plan-details/completeness-cli-layering/06-sweep-every-doc-backlog-citation.md
  status: done
---
# Completeness Cli Layering

## Overview

Restore the thin CLI handler contract for `plan_tool/cli/completeness_cmd.py` by moving `_run_iterate_convergence_loop` (~1086 lines) and the non-CLI logic chunks inside `cmd_completeness_apply` (~559 lines) into `plan_tool/cli/completeness_phases.py`, which already functions as the de facto orchestrator for this command's supporting logic. After the move, `completeness_cmd.py` holds only argument validation, dispatch, and terminal-output/exit-code mapping, calling into the extracted functions with zero behavior change. This is a pure code-motion refactor: no flag, output, exit code, or check/apply/report behavior changes, and observable behavior (terminal output, return codes, files written, run-log contents) must be identical before and after.

## Problem statement

`plan_tool/cli/completeness_cmd.py` currently embeds two large orchestration blocks that don't belong in a CLI handler: `_run_iterate_convergence_loop` (~1086 lines, covering setup/lock acquisition, the up-front conceptual audit, the per-finding `while True` dispatch loop, and teardown) and roughly 559 lines of non-CLI logic inside `cmd_completeness_apply` (saved-audit resolution and freshness/revision-currency checks, source ranking/`--anchor` narrowing, the `--jobs`/parallel-mode decision, the files-coherence fix, and the walk-orchestration engine covering both the serial and parallel execution paths). This violates the project's CLI layering convention, under which handler modules stay thin — argument validation, dispatch, and terminal-output/exit-code mapping — while the real orchestration logic lives in top-level orchestrator modules. `completeness_phases.py` already serves that role for this command's other supporting logic, with 30+ top-level functions in its back half (an approximate count as of this plan's authoring — re-check rather than trust it, since the file has already grown once mid-plan from an unrelated fix), so the same "orchestration logic filed under `cli/`" pattern these two functions exhibit is otherwise absent from this module today.

## Architecture

Move `_run_iterate_convergence_loop`'s full body into `completeness_phases.py` as a named function preserving its existing signature/return contract (`_IterateOutcome`, already defined there at line 102). `completeness_cmd.py` calls it via a **qualified reference** (`completeness_phases._run_iterate_convergence_loop(...)`), matching this codebase's own established convention for a relocated phase (`completeness_phases.py`'s docstring already states this for `apply_finding`/`shell_review_invoker`: "patched on their domain modules, so relocating these phases retargets nothing"). That design choice has a concrete, complete consequence list, not just "retarget the monkeypatch": the direct monkeypatch at `tests/cli/test_completeness_cmd.py:11100`; that file's module-level `from plan_tool.cli.completeness_cmd import _run_iterate_convergence_loop` (line 73) and its ~14 direct, unmocked calls reusing that name plus its `inspect.getsource(...)` checks (see step 2's detail file for the verified count and full site list, per this plan's no-restate policy); and the three tests patching `completeness_cmd.write_pre_apply_audit_checkpoint` to intercept the loop's own call to that already-relocated `completeness_phases.py:488` function. See step 2's intent for the full site list.

Extract `cmd_completeness_apply`'s logic into three sequential ranges, matching its actual control flow (verified by reading the function, not inferred from its step titles alone): saved-audit resolution + freshness/revision-currency checks (~lines 247–364, step 3); source ranking/`--anchor` narrowing, the `--jobs`/`--parallel` decision, and the files-coherence apply/skip logic (~lines 377–507, step 4 — these three are grouped because the files-coherence logic reads the parallel decision's result, and the parallel decision reads the source-ranking output); and the dispatch-and-execute tail (~lines 509–753) together with the standalone `_apply_walk_recs_parallel` function it delegates to for `--jobs N>1` (~lines 756–927, step 5). `cmd_completeness_apply` retains the genuinely CLI-shaped front and back — arg validation, the clean-tree/`--commit` precheck, printed advisories, and exit-code mapping — and becomes a short sequence of calls into the extracted functions.

**These line ranges name what's known so far, not a certified-exhaustive inventory** — round 2 of this plan's own bare-plan audit found several completeness_cmd.py-local helper functions and constants (`_apply_files_coherence`'s own definition, six module constants, the shared data-contract-payload helpers) that steps 3–5's ranges call but never relocate, exactly the kind of gap step 1's helper list had before its own transitive-closure pass. The governing invariant, stated once here rather than re-derived per round: **every completeness_cmd.py-local helper or constant whose only caller is code a step moves must move with it, or be named as needing a re-import back for a surviving caller.** Steps 3, 4, and 5's intents above name what this invariant has surfaced so far; re-run the same grep-based check (not a re-read of the moved code alone) at each step's `detail`/implementation time, since the plan body is not the authoritative source for this — the code is.

Every piece of load-bearing state threaded through today must be preserved exactly, by reference rather than by copy: `ConvergenceState`, the drift-detection iteration-lock context manager (released on every early-return path, including halts), `ScopeGuardBuffer` (accumulated across iterations, flushed once at the end), `_carried_resolution` / `applied_fingerprints`, `run_logger` phase bracketing, `WalkState`, `saved.recommendations`'s in-place, order-sensitive narrowing (the walker persists annotations keyed by `rec.id`), and the `_present_pre_apply_advisory` closure with its `advisory_presented` flag (defined in step 3's range, consumed again in step 5's range as `_apply_walk_recs_parallel`'s `pre_apply_presentation` argument — an at-most-once guard against double-printing the audit-shape advisory that must cross the step 3 → step 5 boundary as one shared object, not two independently-tracked flags).

Steps 2, 4, and 5's relocated code is called from `tests/cli/test_completeness_cmd.py` via `monkeypatch.setattr(completeness_cmd, name, fake)` for names that must retarget to `plan_tool.cli.completeness_phases` in the same step that moves their call site: step 2 owns `_run_iterate_convergence_loop` (see its full site list above); step 4 owns `_apply_files_coherence` and the clean-tree-gate `working_tree_dirty` check (both gate code inside step 4's own range, corrected from an earlier round of this plan that assigned both to step 5); step 5 owns `walk_recommendations`, `_build_review_action_fn`, `working_tree_dirty`'s other call site(s) inside step 5's own range, and `_data_contract_completeness_redirect` — step 5's own detail file settles this last one unambiguously (it owns the full data-contract trio's relocation), superseding the plan body's earlier "neither step owns exclusively" hedge.

`_run_iterate_convergence_loop` and `cmd_completeness_apply`'s extracted logic stay as separate named functions rather than being folded together, even where the extracted shapes end up looking structurally similar — they serve different commands (`completeness-audit --iterate` vs. `completeness-apply`) with different state contracts. No file other than `completeness_phases.py`, `completeness_cmd.py`, and `app.py` (step 1's re-export accounting) changes shape as part of this move.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — Official CPython reference for building the CLI dispatch/argument-validation layer that must stay in completeness_cmd.py after the extraction.
- [contextlib — Utilities for with-statement contexts](https://docs.python.org/3/library/contextlib.html) — Official CPython reference for context-manager semantics, relevant to preserving the drift-detection iteration-lock's release-on-every-early-return-path behavior during the move.
- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Official CPython reference for the dataclass mechanics behind state containers like ConvergenceState and the _IterateOutcome return contract that must thread by reference unchanged.
- [unittest.mock — mock object library](https://docs.python.org/3/library/unittest.mock.html) — Official CPython reference explaining that patches target the lookup namespace — the direct mechanism behind every monkeypatch-retargeting requirement named in steps 2, 4, and 5.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- `completeness_phases.py` physically moving out of `plan_tool/cli/` to sit beside `completeness_report.py` as a first-class top-level orchestrator — it already functions as the landing spot for this command's logic regardless of its own package location; relocating the file is a separate, larger reorganization question, named as a candidate follow-up in this plan's docs rather than acted on.
- `plan_tool/cli/run_cmd.py:cmd_run` (505 lines) — re-verified against current HEAD, it is not a CLI-layering violation like the two functions above: every phase inside it needs `argparse.Namespace` access, terminal output, or exit-code mapping, and its one real execution step (`run_step`) is already correctly factored into `launcher.py`. Its size is a decompose-in-place problem, not a relocation problem, and belongs to a future, separate, much-lower-risk effort.
- Any change to what `completeness-audit --iterate` or `completeness-apply` actually check, apply, or report — this is a pure code-motion refactor.
- Restructuring `tests/cli/COVERAGE_BASELINE.md`'s format — update its `cmd_completeness_apply` row only if its own convention requires an entry for the newly-named extracted functions.

## Risks

- The relocation-target list (step 1's 18 helpers; steps 3–5's local-helper/constant additions) was built by transitive closure plus a full external-caller search, and **rounds 2 and 3 of this plan's own audit each found more of the same class after the prior round's fix** — three consecutive rounds now (`_conceptual_bar_from_audit_recs`'s callees in round 1; `_apply_files_coherence`/data-contract constants in round 2; `_detail_bundle_staleness`/`_saved_audit_revision_is_current`/13 more `working_tree_dirty` sites/a dead-constant false claim/an internal range-boundary contradiction in round 3). **This is the decisive signal, not just a mitigation note: a bare-plan audit can keep finding one more instance indefinitely, because it can read the actual code as thoroughly as this plan body tries to describe it.** Stopping point reached — round 3 is the third snapshot of this repo's own three-snapshot minimum trajectory window, and the class is not converging through further plan-text enumeration. Resolution: apply everything round 3 found (done, this round), then stop iterating this specific axis in the plan body and proceed to `detail`, where the invariant above is re-derived directly against live code per step and any remaining gap surfaces as a failing test instead of another audit finding — not a fourth bare-plan audit round chasing the same pattern.
- Test monkeypatches that target `completeness_cmd.<name>` silently stop intercepting the real call once that name's call site moves to `completeness_phases.py` — confirmed live on step 2's own centerpiece function (not only steps 4/5, as the originating audit pass first found), on two of the (now five, not four) apply-side names being owned by the wrong step (step 5 instead of step 4, corrected round 2), and on step 4's `working_tree_dirty` retarget covering only 2 of its actual 15 sites (corrected round 3 — 13 more inside `TestCompletenessApplyParallel`/`TestCompletenessApplyStructuralSplit` all gate the same clean-tree check). Mitigation: steps 2, 4, and 5 each name their specific monkeypatch retargets explicitly above and were each individually checked, not assumed by pattern from a sibling step (step 3 has none — confirmed clean, per its own detail file) — but per the entry above, treat these counts as what's known as of round 3, not a certified-final tally.
- `cmd_completeness_apply`'s three chunks are threaded through by mutable, order-sensitive state (`WalkState`, `_carried_resolution`, `saved.recommendations` narrowed in place, `_present_pre_apply_advisory`'s closure). Extracting them risks accidentally copying state instead of sharing a reference, or reordering a read/write that currently depends on being interleaved with the surrounding CLI code. Trace each piece of state named under Architecture through the extraction and confirm the same object identity is threaded, not a copy.
- Two other in-progress plans (`per-call-timeout-budgets` step 2, `security-check-command` step 8) cite `_run_iterate_convergence_loop`'s current file path — one as a deliberately-open reconciliation question, one as a "modeled member-for-member" pattern reference. Step 6 updates the citation in both; neither plan's own design is this plan's to change. If either lands its own steps before this plan's step 2, re-check the citation is still accurate rather than trusting this plan's step 6 sweep as the last word.
- This repo is under active concurrent development on the same shared remote (confirmed: a merge landed mid-plan, `8d673886`, bringing in an unrelated `roadmap-incremental-revision`/`roadmap-structural-revision-escalation` arc plus a fix for the exact crash this plan's own audit round 2 hit — see `BUG_BACKLOG.md`'s now-resolved entry). That merge inserted a new test and an exception-isolation block into `completeness_phases.py`/`tests/cli/test_completeness_cmd.py` before most of step 2's cited line numbers, shifting all of them by a confirmed uniform +26 (test file) — already corrected above as of that commit. Nothing in the merge changed this plan's scope (the new code and test both concern `_run_deterministic_checks`'s already-correctly-homed detector-running logic, not anything steps 1–5 relocate), but **line numbers are a live target in this repo, not a fixed one** — re-verify any citation this plan still carries against HEAD immediately before using it to make an edit, not just once at plan-authoring time.

## Testing

`tests/cli/test_completeness_cmd.py` already covers both functions, including calling `_run_iterate_convergence_loop` directly and monkeypatching several of the 18 relocated helpers and five apply-side names (`walk_recommendations`, `working_tree_dirty`, `_apply_files_coherence`, `_build_review_action_fn`, `_data_contract_completeness_redirect`) — these tests are the primary behavior-preservation proof and must pass with only import-path updates and the named monkeypatch-target retargets, no assertion changes. Add unit-level characterization coverage for the newly named `cmd_completeness_apply` extraction targets only if doing so doesn't require inventing new test infrastructure — exercising them through the existing full-`cmd_completeness_apply` tests is sufficient to prove the refactor; isolated unit tests are a nice-to-have, not a requirement.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — tests covering the behavior this step changes; green before completion.
- step 2 (refactor) — tests covering the behavior this step changes, including the `_run_iterate_convergence_loop` monkeypatch retarget; green before completion.
- step 3 (refactor) — tests covering the behavior this step changes; green before completion.
- step 4 (refactor) — tests covering the behavior this step changes, including all 15 `working_tree_dirty` clean-tree-gate retargets and `_apply_files_coherence`'s shared import block plus its 5 direct-call tests; green before completion.
- step 5 (refactor) — tests covering the behavior this step changes, including its two named monkeypatch retargets (`walk_recommendations`, `_build_review_action_fn`) plus `_completeness_apply_commit_subject`'s direct test-import retarget; green before completion.
- step 6 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- All 18 relocated helpers, `_run_iterate_convergence_loop`, and `cmd_completeness_apply`'s three logic chunks (including `_apply_walk_recs_parallel`) live in `plan_tool/cli/completeness_phases.py`; `plan_tool/cli/completeness_cmd.py`'s versions are thin callers or re-imports for surviving local use.
- Every non-moving caller identified in step 1's intent (`cmd_completeness`, `finalize_completeness_run`, `cmd_completeness_apply`, `_resolve_audit_reuse`, `_completeness_has_blocking_findings`) and every external importer (`app.py`'s re-export, the four direct test imports) still resolves.
- Every monkeypatch target named in steps 2, 4, and 5 is retargeted to `plan_tool.cli.completeness_phases`.
- Full test suite green with no assertion changes beyond the named import-path and monkeypatch-target updates.
- No CLI-facing behavior (flags, output, exit codes) changed.
- `docs/AUDIT_FLOW.md`, `BUG_BACKLOG.md`, and `BACKLOG.md` cite the relocated functions' correct new location.

## Deferred

`completeness_phases.py`'s own location in the `cli/` package, and `cmd_run`'s internal decomposition, are named above as related findings but explicitly not part of this seed's scope — file them separately if worth pursuing.
