> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Move completeness-apply's finding-narrowing, parallel-mode decision, and files-coherence fix into completeness_phases.py

## Summary

`cmd_completeness_apply` in `plan_tool/cli/completeness_cmd.py` spends its middle section — the range right after step 3's saved-audit resolution and right before the walk dispatch step 5 owns — deciding *what* the upcoming walk will operate on: which saved findings are in play (`walk_recs`/`conceptual_walk_recs`), whether `--jobs > 1` parallel mode is legal and worthwhile (`_parallel`), and whether the plan is bare enough that the deterministic files-coherence fix and most saved sources must be withheld. This step carves that range into one new phase function, `_resolve_apply_walk_targets`, in `plan_tool/cli/completeness_phases.py`, together with the one helper it calls that has no caller left outside this range: `_apply_files_coherence`. The result is a small frozen dataclass, `_ApplyWalkTargets`, that step 5's already-written detail names by its exact field set (`walk_recs`, `conceptual_walk_recs`, `parallel`, `plan_is_bare`) plus an `ok`/`rc`/`message` triple modeled on step 3's `_SavedAuditResolution`, covering three exit points this step's range must still support: two hard `--jobs > 1` gate failures and one bare-plan early return once every saved gap has been withheld. On green, `cmd_completeness_apply`'s body between step 3's resolution and step 5's `answered = 0` collapses to one delegating call plus a four-line unpack, and the full suite passes with the `_apply_files_coherence` and `working_tree_dirty` monkeypatch/import retargets named below — no other behavior changes.

## Table of Contents

- [Why](#why) — what's still misplaced after step 3, and why this slice comes next
- [Input](#input) — what steps 1 and 3 hand this step
- [Files (creates vs edits)](#files-creates-vs-edits) — which files change and how
- [Implementation](#implementation) — the move, the result type, and the two corrections this step's own grounding surfaced
- [Tests](#tests) — required regression coverage and the optional characterization tests
- [Acceptance criteria](#acceptance-criteria) — checkable facts about the resulting tree
- [References](#references) — the plan-level references relevant to this step
- [Applicable guardrails](#applicable-guardrails) — the plan fences this step must respect
- [Deferred](#deferred) — what a reader might expect here but isn't

## Why

`plan_tool/cli/completeness_cmd.py`'s own module docstring states the target shape: `cmd_completeness_apply` should be dispatch and exit-code mapping, delegating its real work to named phases in `completeness_phases.py`. Step 3 already moved the saved-audit lookup and freshness check; this step takes the next self-contained slice, the block the plan's own Architecture section identifies as the natural second cut. It runs entirely between step 3's `data_contract_payloads = _load_saved_data_contract_payloads(saved_path)` line and the `answered = 0` line step 5 owns, and nothing downstream of it needs to reach back into it except by consuming the values it produces.

One helper function definition sits inside this range and is called from nowhere else in the production code: `_apply_files_coherence`, called once (inside the bare-plan-status branch) and otherwise only referenced from `tests/cli/test_completeness_cmd.py`'s direct-call and monkeypatch tests. It moves with this step, matching the plan's stated invariant that a local helper whose only caller is code a step relocates must move with it.

Re-deriving this step's site inventory by grep against current HEAD (the plan's own INVARIANT instructs re-deriving rather than trusting a prior enumeration) surfaced two corrections to the plan's own "confirmed owned by this step" list, both worth recording explicitly because they change what this step's `Implementation` must do:

- `_COMPLETENESS_SEVERITY_RANK` has zero references anywhere in the repo (already noted by the plan's own text as dead code, safe to move for no functional reason beyond physical proximity to the constants this step's range actually reads).
- `_DATA_CONTRACT_SOURCE` and `_DATA_CONTRACT_TARGET` are **not** read anywhere inside this step's own 377–507 range (`rg` over that exact slice returns nothing). Every real reference — the `_walk_apply_sources` frozenset, `action_fn`'s dispatch check, and all three of `_load_saved_data_contract_payloads` / `_data_contract_payload_target` / `_data_contract_completeness_redirect` — sits in code step 5 owns and that stays resident in `completeness_cmd.py` until step 5 moves it. This step still relocates both constants (the plan's ownership list is authoritative on *that*), but because their real callers don't move yet, this step must add a bare re-import of both names back into `completeness_cmd.py`'s existing `from plan_tool.cli.completeness_phases import (...)` block — the same "re-import for a surviving caller" case the plan's own INVARIANT describes, just for a different reason than the plan's prose states (mirroring how the plan's own text already self-corrected the same "read by this step's ranges" claim for `_COMPLETENESS_SEVERITY_RANK`, a few words earlier in the same guardrail).

## Input

This step depends on steps 1 and 3:

- **From step 3:** the resolved `plan_path` (non-`None` by construction — `cmd_completeness_apply` already returns 2 before this step's range if the saved audit isn't current, which requires a resolved `plan_path`), the loaded `saved` review, and the `data_contract_payloads` local variable step 3's range computes but this step does not consume (it belongs to step 5's `action_fn` closure). This step's new function takes `saved`, `args`, `ctx`, and `plan_path` as inputs and does not re-derive any of them.
- **From step 1:** `_finding_progress_label`, already `def`-owned by `completeness_phases.py`. The moved range's withheld-gap print (`print(f"  {_finding_progress_label(rec)}")`) calls it by bare name today; once this step's range lands beside it, that becomes a same-module reference needing no import.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/cli/completeness_cmd.py` — delete `_apply_files_coherence`'s definition and the module constants `_COMPLETENESS_SEVERITY_RANK`, `_CONCEPTUAL_APPLY_SOURCE_RANK`, `_BARE_PLAN_WALKABLE_SOURCES`, `_DATA_CONTRACT_SOURCE`, `_DATA_CONTRACT_TARGET`, `_SAVED_SERIAL_APPLY_SOURCE_RANK`; replace `cmd_completeness_apply`'s finding-narrowing / `--jobs` decision / files-coherence block (the range immediately following step 3's `data_contract_payloads = ...` line, up to but not including `answered = 0`) with one call into the new phase function plus the `ok`/`rc` check and a four-line unpack (see Implementation); extend the existing `from plan_tool.cli.completeness_phases import (...)` block with the new function's name and with bare re-imports of `_DATA_CONTRACT_SOURCE` / `_DATA_CONTRACT_TARGET` (needed by the `_walk_apply_sources` frozenset, `action_fn`, and the data-contract helper trio, all of which stay resident in this file until step 5 moves them).
- `plan_tool/cli/completeness_phases.py` — add `_apply_files_coherence` (verbatim body), the six relocated module constants (verbatim), the new phase function, and its result dataclass; add a module-level `from plan_tool.cli.gitcommit import working_tree_dirty` import (a live monkeypatch target — see Tests) and a module-level `from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE` import (`_SAVED_SERIAL_APPLY_SOURCE_RANK`'s definition references it at module-evaluation time, so it can't use this file's usual per-function body-local import style for this one reference).
- `tests/cli/test_completeness_cmd.py` — retarget `_apply_files_coherence`'s shared top-of-file import and its 3 monkeypatch sites; retarget the 15 `working_tree_dirty` monkeypatch sites this step's moved gate governs (see Tests).

## Implementation

**Move `_apply_files_coherence` verbatim, call site and all.** Its definition and its one call (inside the bare-plan-status branch) both move into the new phase function's body, landing as a same-module reference — no import needed on either side in production code. It keeps its own docstring and body-local imports (`plan_tool.parser.{parse_plan, ParseError, ValidationError, write_plan, ConcurrentModificationError}`, `plan_tool.review.check_files_coherence`); none of these currently have a body-local precedent elsewhere in `completeness_phases.py` (only `parse_plan`/`ParseError`/`ValidationError` do, inside `_resolve_plan_for_report`), so this is the first caller to pull in `write_plan`, `ConcurrentModificationError`, and `check_files_coherence` — follow the file's existing per-function body-local convention for all of them.

**Move the six module constants verbatim, as one block**, keeping their existing comments: `_COMPLETENESS_SEVERITY_RANK`, `_CONCEPTUAL_APPLY_SOURCE_RANK`, `_BARE_PLAN_WALKABLE_SOURCES`, `_DATA_CONTRACT_SOURCE`, `_DATA_CONTRACT_TARGET`, `_SAVED_SERIAL_APPLY_SOURCE_RANK` (the last one's `**_CONCEPTUAL_APPLY_SOURCE_RANK` spread and `GRANULARITY_SPLIT_SOURCE` reference both need their sources already bound at module-evaluation time in the new home — the spread resolves automatically since both constants move together, but `GRANULARITY_SPLIT_SOURCE` needs the module-level import named above). Two of the six (`_DATA_CONTRACT_SOURCE`, `_DATA_CONTRACT_TARGET`) need the re-import back into `completeness_cmd.py` described in Why; the other four have zero remaining references in `completeness_cmd.py` after this step and need no re-import.

**Add one new phase function that reproduces the narrowing/decision/coherence range's control flow, returning a result instead of printing-and-returning directly for its two hard exits.** Something like:

```python
def _resolve_apply_walk_targets(saved, *, args, ctx, plan_path) -> _ApplyWalkTargets:
```

following this file's `resolve_`-prefixed naming already used by `_resolve_plan_for_report` and (after step 3) `_resolve_saved_completeness_audit`. It reproduces, unchanged, in order:

- The source-rank filter and `--anchor` narrowing that build `walk_recs` from `saved.recommendations` (the `_SAVED_SERIAL_APPLY_SOURCE_RANK` membership filter, the stable sort, the `--anchor` intersection and its "no completeness finding matched" warning), then `conceptual_walk_recs` via the `_CONCEPTUAL_APPLY_SOURCE_RANK` membership filter.
- The `--jobs N>1` decision: `_parallel = getattr(args, "jobs", 1) > 1`, the degrade-to-serial warning and reset to `False` when there's nothing to parallelize, and — when still `_parallel` — the two hard gates (`-y` required, clean working tree required). Both gates keep their exact current message text and both still fail before the files-coherence write below runs, exactly as today.
- The files-coherence resolution: parse the plan, compute bundle status via `plan_tool.review.audit_detail_bundle_status` (body-local import, matching this range's current style), run `_apply_files_coherence` only when `not _parallel` and the bundle isn't bare, and on a bare plan run the withholding logic — filter `walk_recs`/`conceptual_walk_recs` down to `_BARE_PLAN_WALKABLE_SOURCES`, warn and print the withheld gaps plus the `plan-tool detail` pointer, and flag the early exit when nothing is left to walk.

**The result type carries three exit points as one uniform contract**, mirroring step 3's `_SavedAuditResolution` shape (`ok`/`rc`/`message`, required field first, the rest defaulted so a partial constructor stays valid):

```python
@dataclass(frozen=True)
class _ApplyWalkTargets:
    ok: bool
    rc: Optional[int] = None
    message: Optional[str] = None
    walk_recs: list = field(default_factory=list)
    conceptual_walk_recs: list = field(default_factory=list)
    parallel: bool = False
    plan_is_bare: bool = False
```

Keep the four non-`ok`/`rc`/`message` field names exactly as shown — step 5's own detail file already names `walk_recs`, `conceptual_walk_recs`, `parallel`, and `plan_is_bare` as the values it reads off this step's result. `ok=False` covers all three exit points this range can hit: the two `--jobs > 1` gate failures (`rc=2`, `message` set to the gate's exact current text — `cmd_completeness_apply` calls `error(resolution.message)` before returning) and the bare-plan-exhausted early return (`rc=0`, `message=None` — the withheld-gap warning already printed inside the phase function, so there's nothing left for the caller to print). `cmd_completeness_apply`'s own wiring becomes:

```python
targets = completeness_phases._resolve_apply_walk_targets(
    saved, args=args, ctx=ctx, plan_path=plan_path,
)
if not targets.ok:
    if targets.message is not None:
        error(targets.message)
    return targets.rc
walk_recs = targets.walk_recs
conceptual_walk_recs = targets.conceptual_walk_recs
_parallel = targets.parallel
_plan_is_bare = targets.plan_is_bare
```

leaving `answered = 0` and everything after it (step 5's range) unchanged and still reading `walk_recs`, `conceptual_walk_recs`, `_parallel`, and `_plan_is_bare` as local names, exactly as it does today.

**Preserve the `if plan_path is not None:` guard even though `plan_path` is always non-`None` by the time this range runs.** Step 3's range already returns 2 before this point whenever `plan_path` couldn't be resolved. The guard is vestigial at this call site today and stays vestigial after the move — removing it would be a behavior-neutral cleanup outside this step's zero-behavior-change fence, so keep it as dead-but-harmless defensive code rather than deleting it.

**Ordering that must survive the move:** the two `--jobs` gates run and can return before the files-coherence/bare-plan block ever executes, exactly as today (an early gate failure must never trigger a files-coherence write or a withheld-gap print). Preserve this by keeping the same top-to-bottom order inside the new function rather than restructuring it into, say, a gate-collecting list.

## Tests

Required — everything below must stay green with no assertion changes beyond the named import/monkeypatch retargets:

- `tests/cli/test_completeness_cmd.py::TestApplyFilesCoherence` — its top-of-file `from plan_tool.cli.completeness_cmd import (_apply_files_coherence, ...)` entry retargets to `plan_tool.cli.completeness_phases`; its five direct-call tests (`test_report_only_does_not_write`, `test_apply_adds_only_the_resolvable_path`, `test_apply_is_idempotent`, `test_threads_plan_path_so_canonical_only_details_are_seen`, `test_clean_plan_writes_nothing`) exercise the moved function's real behavior unchanged.
- `TestCompletenessApplyDetailBundleGate::test_bare_plan_skips_files_coherence_writer` and `::test_bare_plan_still_skips_files_coherence_when_the_walk_runs` — their `monkeypatch.setattr(ccmd, "_apply_files_coherence", ...)` calls retarget to `plan_tool.cli.completeness_phases`.
- `TestCompletenessApplyDetailBundleGate::test_fully_detailed_plan_runs_files_coherence_writer` — same retarget; this is the one asserting the exact call args (`calls == [(plan_path, tmp_repo.root, True)]`), so it also pins the parameter order this step must not change.
- `TestCompletenessApplyDetailBundleGate::test_bare_plan_with_only_completeness_gaps_skips_the_walk` — no retarget needed; it monkeypatches `walk_recommendations` (step 5's territory, unaffected here) and asserts it's never called. This is the test that pins the bare-plan-exhausted early return: `ok=False, rc=0` must make `cmd_completeness_apply` return before `walk_recommendations` is ever reached.
- `TestCompletenessApplyDetailBundleGate::test_bare_plan_walks_correctness_gaps`, `::test_bare_plan_withholds_completeness_gaps_from_the_walk`, `::test_bare_plan_withholds_granularity_split_from_the_walk`, `::test_bare_plan_withholds_data_contract_from_the_walk`, `::test_bare_plan_reports_withheld_gaps_with_the_detail_pointer` — no retarget needed; these drive `main()` end to end and pin the `_BARE_PLAN_WALKABLE_SOURCES` filter, the withheld-gap warning text, and the `plan-tool detail` pointer text this step's range produces.
- `TestCompletenessApplyParallel::test_dirty_tree_refused` and `::test_tty_without_yes_refused` — their `monkeypatch.setattr(ccmd, "working_tree_dirty", ...)` calls retarget to `plan_tool.cli.completeness_phases`; both assert the exact gate message text and `rc == 2`.
- The remaining 12 `working_tree_dirty` monkeypatch sites inside `TestCompletenessApplyParallel` (covering `test_parallel_applies_and_persists_annotations` and its siblings through `test_bare_plan_parallel_lane_does_not_replay_a_created_detail_file`) — same retarget; each needs the clean-tree gate to pass before it can exercise `--jobs N>1` dispatch, which is step 5's territory but gated by this step's check.
- `TestCompletenessApplyStructuralSplit::test_medium_split_not_fanned_out_in_parallel` — its `working_tree_dirty` monkeypatch retargets the same way.
- `TestCompletenessApplyParallel::test_single_anchor_degrades_to_serial` — no retarget needed; drives `main()` end to end and pins the degrade-to-serial warning text this step's range produces.

### Tests for this step

The required list above must be green before this step is considered finished. The following are recommended, direct-unit coverage of the new phase function reusing this file's existing `SimpleNamespace`/`tmp_repo`/`save_review` fixtures rather than inventing anything new — add them if convenient, don't block completion on them:

- `test_resolve_apply_walk_targets_narrows_by_anchor` — a saved review with several sources, `--anchor` naming one gap → `walk_recs` contains only the matched recommendation.
- `test_resolve_apply_walk_targets_rejects_jobs_without_yes` — `--jobs 2` without `-y` → `ok=False`, `rc=2`, `message` contains "-y".
- `test_resolve_apply_walk_targets_rejects_jobs_on_dirty_tree` — `--jobs 2 -y` with a dirty working tree → `ok=False`, `rc=2`, `message` contains "clean working tree".
- `test_resolve_apply_walk_targets_degrades_single_anchor_to_serial` — `--jobs 2` with `--anchor` naming one conceptual gap → `parallel is False` on the returned result (no `ok=False`, this path continues).
- `test_resolve_apply_walk_targets_stops_when_bare_plan_exhausts_the_walk` — a bare plan whose only saved gap is `plan-completeness` → `ok=False`, `rc=0`, `message is None`.
- `test_resolve_apply_walk_targets_keeps_correctness_gaps_on_a_bare_plan` — same bare plan, a `plan-correctness` gap present too → `ok=True`, `walk_recs` non-empty, `plan_is_bare is True`.
- `test_resolve_apply_walk_targets_skips_coherence_write_in_parallel_mode` — `_parallel` resolves `True` on a non-bare plan → `_apply_files_coherence` is not called (spy or monkeypatch).

## Acceptance criteria

- `plan_tool/cli/completeness_phases.py` defines `_apply_files_coherence`, `_resolve_apply_walk_targets`, `_ApplyWalkTargets`, and all six relocated module constants; `plan_tool/cli/completeness_cmd.py` defines none of them.
- `rg "^def _apply_files_coherence|^_COMPLETENESS_SEVERITY_RANK|^_CONCEPTUAL_APPLY_SOURCE_RANK|^_BARE_PLAN_WALKABLE_SOURCES|^_SAVED_SERIAL_APPLY_SOURCE_RANK" plan_tool/cli/completeness_cmd.py` returns no results.
- `rg "_DATA_CONTRACT_SOURCE|_DATA_CONTRACT_TARGET" plan_tool/cli/completeness_cmd.py` still returns hits (the re-import plus the still-resident `_walk_apply_sources`/`action_fn`/data-contract-trio callers), but `rg "^_DATA_CONTRACT_SOURCE =|^_DATA_CONTRACT_TARGET ="` returns none — the names are imported, not defined, in this file.
- `cmd_completeness_apply`'s body between step 3's `data_contract_payloads = ...` line and `answered = 0` is: one call into `_resolve_apply_walk_targets`, the `ok`/`rc`/`message` check, and the four-line unpack — no inline filtering, sorting, gate-checking, or files-coherence logic remains.
- Both `--jobs > 1` gate failures and the bare-plan-exhausted early return produce the same exit code and printed text as current behavior.
- `_apply_files_coherence` is not called when `--jobs N>1` resolves to `True` on a non-bare plan (unchanged from today).
- All 4 `_apply_files_coherence` and 15 `working_tree_dirty` monkeypatch/import sites named in Tests resolve against `plan_tool.cli.completeness_phases`.
- `uv run pytest tests/ -q -n auto` is green.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — the CLI dispatch/argument-validation layer (`args.anchor`, `args.jobs`, `args.yes`) that stays in `completeness_cmd.py` and is what the new phase function reads from.
- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — mechanics behind `_ApplyWalkTargets`, matching the existing `_SavedAuditResolution` (step 3) and `_DeterministicReport` pattern of a required field before defaulted ones.
- [unittest.mock — mock object library](https://docs.python.org/3/library/unittest.mock.html) — patches target the lookup namespace, the direct mechanism behind every one of this step's named `_apply_files_coherence` and `working_tree_dirty` retargets.

## Applicable guardrails

- **Plan intent (zero behavior change).** Every part of this step is a pure relocation: no flag, printed message, exit code, or check/apply/report outcome may change. Returning a result object instead of returning early with a printed message is a code-shape choice, not a behavior change — the text and codes on the two `--jobs` gates and the bare-plan early return are exactly what ship today.
- **Plan's "Out of scope."** This step doesn't touch `completeness_phases.py`'s location in the package, doesn't touch `cmd_run`, doesn't change what `completeness-apply` checks, applies, or reports, and doesn't restructure `tests/cli/COVERAGE_BASELINE.md`'s format.
- **Step intent's explicit boundary.** This step's range starts immediately after step 3's and stops before `answered = 0` — the dispatch-and-execute tail, `_apply_walk_recs_parallel`, and the data-contract helper trio's definitions belong to step 5, even though this step's result feeds them directly.
- **Step intent's INVARIANT (re-derive the site inventory by grep, don't trust a prior enumeration).** Applied directly in this step's own Why/Implementation: the grep-based re-check is what surfaced that `_DATA_CONTRACT_SOURCE`/`_DATA_CONTRACT_TARGET` need a re-import back into `completeness_cmd.py` for a reason different from the plan's stated one, and that `_apply_files_coherence` needs none (its only caller travels with it).

## Deferred

- Moving the dispatch-and-execute walk tail (serial and parallel), `_apply_walk_recs_parallel`, `_completeness_apply_commit_subject`, and the data-contract helper trio's own definitions (`_load_saved_data_contract_payloads`, `_data_contract_payload_target`, `_data_contract_completeness_redirect`) — step 5's range, which consumes this step's `_ApplyWalkTargets` result directly.
- Threading `plan_is_bare` into whatever parameter shape step 5's dispatch function ends up needing for its `_allow_split` computation — this step hands the value off as `targets.plan_is_bare`; how it crosses into step 5's own function signature is step 5's implementation detail, not this one's.
- Correcting `plan_tool/cli/completeness_cmd.py`'s or `plan_tool/cli/completeness_phases.py`'s own module docstrings — the plan's step 6 intent (and step 3's own Deferred) name steps 2 and 5 as the two docstring-owning steps; this step adds substantial content to `completeness_phases.py` but doesn't touch either docstring.
- Plan-level `## Overview` elaboration (`13f827ff8629927d3a6a0073f8ae5459c920f29fa9b0d4f9b62b7b225cff48fb`) — this step's own Summary/Why cover its scope; nothing to add.
- Plan-level `## Problem statement` elaboration (`4b4dcef2a7b9e8a282249afea4c39824f19247e7ea3e9623fdfd2b838992c25e`) — already names this step's exact range.
- Plan-level `## Architecture` elaboration (`bafd6791befc230e29100c87744ed929a6cb00c4e71a1168fdcba790706ccf06`) — already states this step's range and the constants it must relocate; this step follows it (with the two corrections recorded in Why) rather than revising it.
- Plan-level `## Risks` elaboration (`72dda8dc73e851118ec2b57fd1e28be9e7d6f49be6b5c0a9a2e437e275d6f220`) — a behavior-preserving move of a self-contained, mostly-non-monkeypatched range adds no new risk beyond what the plan's Risks section already tracks.
- Plan-level `## Steps` elaboration (`e466d1d8f95285e23e97261ab7abd97ab96cce3efabc6d644048f28408f2d8e6`) — this step changes no step's id, title, or dependency graph.
- Plan-level `## Testing` elaboration (`ae9498b434b81c33da8d95ace0435bde26c3d0bd30666b5abafc922433320955`) — this step's own Tests section is the elaboration.
- Plan-level `## Acceptance criteria` elaboration (`62c5ad026e319cb492c516a319e2ecb9354e2dc133ce9949667b12e3d31ca665`) — covered by this step's own Acceptance criteria section.
- Plan-level `## References` elaboration (`10e39018ee270585a0a462209a0dc33bb3a9b23c1c290219a91237462d9cdb42`) — covered by this step's own References section.
- Plan-level `## Out of scope` elaboration (`74b73f49705a852b50f557668e68847846dfbb86c7128a8a3a3e8a8c026fd252`) — the plan's Out of scope section already covers this move; nothing step-specific to add.
- Plan-level `## Deferred` elaboration (`4fe0e8e39d6eebcd154f82f1a8950f81d32bc14792eef42ffcd530c52665cc6d`) — this step's own Deferred section (above) is the elaboration for its own range.
