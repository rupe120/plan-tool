> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Add a CLI flag to materialize recoverable draft-seed states

## Summary

Adds `--materialize [PLAN_ID]` to `plan-tool roadmap`, a third explicit-regeneration entry point beside `--apply` and `--refresh-seeds`. With no `PLAN_ID` it regenerates every plan step 3's `classify_draft_seeds` currently classifies `missing`, `stale`, `malformed`, `path-escaping`, or `digest-mismatched`; with one it targets that plan alone and refuses — naming the actual classification — an id that doesn't exist in the roadmap or one already `current`/`duplicate`. The batch loop and its before/after report live in `plan_tool/cli/roadmap_cmd.py`, calling step 2's `materialize_plan_seed` once per targeted plan through two small, purely additive helpers this step adds to `plan_tool/roadmap.py` (`materialize_and_diff_one_plan`, `write_seed_refresh_report`) so the diff/report shape stays byte-for-byte the one `--refresh-seeds` already produces. The batch result is built as a `RoadmapSeedRefreshResult` and rendered through the existing `_render_seed_refresh_result` step 4 ships, reusing its outcome/result types and its `_RC_PARTIAL`/`_RC_INCOMPLETE` rc constants — step 4 never extracts a separate rc-mapping function (its mapping is inlined in `_cmd_roadmap_refresh_seeds`'s own return), so this step's own dispatch re-derives the identical three-branch `outcome → rc` logic inline against the same constants, rather than calling a shared mapping function that does not exist. The result is that `--materialize` reports the identical three-way outcome (`SEED_REFRESH_OUTCOME_APPLIED` / `_PARTIAL` / `_EXHAUSTED`, rc `0`/`_RC_PARTIAL`/`_RC_INCOMPLETE`) `--refresh-seeds` does. On green, an operator can backfill a fresh roadmap's first missing drafts or resume a partial/content-drift failure one call at a time, without regenerating a draft that is already fine.

## Table of Contents

- [Why](#why) — the gap between "regenerate everything" and "regenerate the one thing that's broken"
- [Input](#input) — step 2's and step 3's contracts, and the step 4 shapes this step reuses
- [Files (creates vs edits)](#files-creates-vs-edits) — the declared CLI files plus two necessary `roadmap.py` additions
- [Implementation](#implementation) — the flag, target selection, the two-way refusal, the shared per-plan primitive, and reused rendering
- [Tests](#tests) — argparse, target-selection, refusal, and rendering coverage
- [Acceptance criteria](#acceptance-criteria)
- [References](#references)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

Today the only way to regenerate a draft seed is `--refresh-seeds`, which — even after step 4 makes it per-plan and failure-isolated — always walks every plan row in the roadmap. There is no way to backfill just the one plan a fresh roadmap hasn't materialized yet, or to retry just the one plan that came back `digest-mismatched` after a hand edit, without also re-spending a backend call on every plan that is already `current`. Step 3's `classify_draft_seeds` already answers "which plans actually need regenerating" for every other consumer this plan adds (promotion refusal, the two view steps, the accept action); this step is the first one to act on that answer by choosing *which* plan ids to hand to step 2's `materialize_plan_seed`, rather than only reporting it.

The two-way refusal (unknown id vs. a known id that's already fine) exists so `--materialize` never silently no-ops or silently redoes work a human didn't ask for — mirroring the promotion refusal step 6 will add for the same reason: a command that regenerates a draft nobody asked it to touch is exactly the "writing a replacement without the explicit materialization/refresh action" the plan's `## Out of scope` forbids.

## Input

This step is built on three contracts, two of which it consumes as-is and one of which (step 4's) it reuses by construction rather than by dependency:

- **Step 2's `materialize_plan_seed(slug, plan_id, *, repo_root, plans_dir, invoker=shell_roadmap_invoker, max_attempts=MAX_STAGE_ATTEMPTS)`.** On success it has already written the draft file (and, when the plan is already promoted, the `plan-seeds/<id>.md` copy) by the time it returns; on an exhausted attempt it writes nothing and leaves whatever was there before untouched, carrying the last attempt's `failure_kind` (`FAILURE_INVOKE`/`FAILURE_PARSE`/`FAILURE_GATES`), `failure_detail`, and `violations`. As step 4's own detail notes, the exact field(s) the *success* path exposes are not pinned by any earlier step — check step 2's landed `RoadmapSeedMaterializeResult` for its actual success/failure discriminator when implementing this step (a populated-on-success field that is empty/`None` on failure, or an explicit outcome constant), the same hedge step 4 already carries forward.
- **Step 3's `classify_draft_seeds(artifact, *, plans_dir, slug) -> dict[str, DraftSeedClassification]`** (`plan_tool/roadmap_seed_manifest.py`), plus its seven state constants and `DraftSeedClassification(plan_id, state, detail="")`. This step is the first *targeting* consumer: it reads the returned mapping to build the set of plan ids eligible for `--materialize` and to decide what a refusal names. It never mutates anything the classifier reports — target selection is a pure read. **Targeting a plan the classifier calls `malformed` where the true cause is an unacknowledged revision (see step 3's detail — this window closes once step 9 lands) still materializes it correctly**, since `--materialize` regenerates any of the five recoverable states identically; only the pre-materialize reason line can be misleading during that window, not the outcome.
- **Step 4's landed `refresh_roadmap_seeds` shapes**, required by this step's own `depends_on: [2, 3, 4]` (see the plan's `depends_on_notes` for step 5), not an independent design choice: `RoadmapSeedRefreshChange(plan_id, target, previous, action, diff)`, `RoadmapSeedRefreshFailure(plan_id, failure_kind, failure_detail=None, violations=())`, `RoadmapSeedRefreshResult(outcome, changes=(), failures=(), report_path=None)`, the outcome constants `SEED_REFRESH_OUTCOME_APPLIED` / `SEED_REFRESH_OUTCOME_PARTIAL` / `SEED_REFRESH_OUTCOME_EXHAUSTED`, and `plan_tool/cli/roadmap_cmd.py`'s `_render_seed_refresh_result` plus its `_RC_PARTIAL` constant. Reusing these — rather than minting a parallel "materialize result" type — is required precisely because both commands regenerate seeds through the identical primitive and must report identical vocabulary to an operator or a script parsing exit codes; minting a second vocabulary here would itself be the drifting-copy risk this plan avoids elsewhere (step 1's shared validators, step 3's single classifier). Confirm the landed field names against step 4's actual code before wiring this step; if step 4 shipped different names than its own detail proposed, follow what is on disk.
- **What this step does not read**: it never reads `RoadmapStage`, `STAGES`, or any stage-4 bundle machinery — `--materialize` runs no stage and invokes the backend only through `materialize_plan_seed`, exactly like `--refresh-seeds`.

## Files (creates vs edits)

**Existing files (edits only):**

- `plan_tool/cli/roadmap_cmd.py` — add the `--materialize` flag to the existing mutually-exclusive run-mode group, `_cmd_roadmap_materialize`, the materializable-state set, the two refusal messages, and the dispatch branch in `cmd_roadmap`.
- `tests/cli/test_roadmap_cmd.py` — new argparse, target-selection, refusal, and rendering coverage; extend the shared `_ns()` namespace-builder helper's defaults with `materialize=None`.

**Necessary additions (not in the plan's declared list — see below):**

- `plan_tool/roadmap.py` — add `materialize_and_diff_one_plan` and `write_seed_refresh_report`, both new, purely additive functions. Neither edits an existing function's body.
- `tests/test_roadmap.py` — unit tests for the two new `roadmap.py` functions, independent of the CLI layer.
- `docs/cli/roadmap.md` — the generated per-subcommand flag reference. `--materialize` is a real, new argparse flag on `plan-tool roadmap`; `CLAUDE.md` states this file is drift-guarded by `tests/cli/test_cli_reference.py`, and that test is **not** part of this step's own acceptance-criterion test command (`pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py -q`), so a step that lands the flag without regenerating the doc would pass its own gate while leaving the full suite red. Regenerate with `python -m plan_tool.cli_reference --write` after the argparse change lands; do not hand-edit it.

**Why the addition is necessary:** the plan's own step 5 intent commits to writing "the same before/after diff `--refresh-seeds` already produces (`seed-refresh-report.md`)". That diff/report machinery — `_seed_refresh_diff`, `_latest_seed_archive`, `_render_seed_refresh_report` — is private to `plan_tool/roadmap.py`, and reimplementing it a second time inside `roadmap_cmd.py` is exactly the drifting-copy risk step 1 extracted `validate_draft_seed_content` to avoid. The two new functions this step adds are thin, additive wrappers that call those existing private helpers *from within the same module* (no cross-module private access, no visibility change to any existing symbol, no edit to `refresh_roadmap_seeds`'s own body) and give `roadmap_cmd.py` one clean, testable entry point each. This mirrors steps 1, 2, 3, and 4's own precedent of declaring a necessary file addition with its reason rather than silently expanding the plan's `files:` list. `docs/cli/roadmap.md` is a necessary addition for the same class of reason as the other two: a real, observable surface (here, the generated CLI reference) this step's own flag change makes stale, that the step's declared files/test command would otherwise leave unaddressed.

## Implementation

### The flag

Add `--materialize` to the existing `run_mode_group` in `register()` (`plan_tool/cli/roadmap_cmd.py`), alongside `--apply`, `--refresh-seeds`, `--from-stage`, and `--view` — mutually exclusive with all four, and, like `--refresh-seeds`, not requiring `--from-existing` and not gated by `-y`/`--yes` (there is no interactive confirm to bypass; naming the flag *is* the explicit opt-in, the same stance `--refresh-seeds` already takes).

Use `nargs="?"` with a sentinel `const` to distinguish three states cleanly — flag absent (`None`), flag present with no value (regenerate every recoverable plan), flag present with a value (regenerate exactly that plan id):

```
_MATERIALIZE_ALL = object()  # --materialize with no PLAN_ID: every recoverable plan

run_mode_group.add_argument(
    "--materialize",
    nargs="?",
    const=_MATERIALIZE_ALL,
    default=None,
    metavar="PLAN_ID",
)
```

A sentinel `object()` (not a string) is the recommended approach — it can never collide with an operator-chosen plan id, which a reserved string sentinel could. In `cmd_roadmap`, dispatch on `args.materialize is not None`, placed beside the `--refresh-seeds` branch (both are "explicit regeneration, no stage table, backend called only through `materialize_plan_seed`" modes). `cmd_roadmap`'s own docstring is this file's authoritative rc/dispatch-mode contract, already documenting `--apply`/`--view` as modes — add `--materialize` to that same listing in this edit, matching how step 4 adds `_RC_PARTIAL` to it for the refresh outcome.

### Selecting targets: reusing step 3's classification

`_cmd_roadmap_materialize` loads `04-roadmap.md` directly — there is no `RoadmapResult` to read it off, unlike `_create_handoff_lines`'s path:

```
try:
    artifact = load_plans_artifact(plans_path(plans_dir, args.slug))
except RoadmapArtifactError as exc:
    error(str(exc)); return _RC_USAGE

try:
    classifications = classify_draft_seeds(artifact, plans_dir=plans_dir, slug=args.slug)
except RoadmapSeedStateError as exc:
    error(str(exc)); return _RC_USAGE
```

`RoadmapArtifactError` and `RoadmapSeedStateError` are both already imported into `roadmap_cmd.py`; `plans_path` and `classify_draft_seeds` (plus the seven state constants) are the two new imports this step adds — from `plan_tool.roadmap_artifacts` and `plan_tool.roadmap_seed_manifest` respectively.

Define the materializable set once, from step 3's constants — deliberately excluding `DRAFT_SEED_STATE_CURRENT` (nothing to fix) and `DRAFT_SEED_STATE_DUPLICATE` (a plan-row collision no regeneration resolves):

```
_MATERIALIZABLE_STATES = frozenset({
    DRAFT_SEED_STATE_MISSING,
    DRAFT_SEED_STATE_STALE,
    DRAFT_SEED_STATE_MALFORMED,
    DRAFT_SEED_STATE_PATH_ESCAPING,
    DRAFT_SEED_STATE_DIGEST_MISMATCHED,
})
```

`path-escaping` belongs in this set because a fresh `materialize_plan_seed` call writes the sidecar's `draft_seed_path` field from the *plan row's* own path — already gated safe at parse time — never from the corrupted sidecar value that made the draft classify `path-escaping` in the first place; regenerating intrinsically clears that state.

### The two-way refusal

```
target = args.materialize
if target is _MATERIALIZE_ALL:
    plan_ids = [row.id for row in artifact.plans
                if classifications[row.id].state in _MATERIALIZABLE_STATES]
else:
    classification = classifications.get(target)
    if classification is None:
        error(f"roadmap {args.slug}: no such plan in this roadmap: {target!r}")
        return _RC_USAGE
    if classification.state not in _MATERIALIZABLE_STATES:
        error(
            f"roadmap {args.slug}: plan {target!r} classifies as "
            f"{classification.state!r} — nothing to materialize"
            + (f" ({classification.detail})" if classification.detail else "")
        )
        return _RC_USAGE
    plan_ids = [target]
```

This is a precondition check, not part of the batch result — it returns `_RC_USAGE` directly, the same rc every other "the input this command was given doesn't resolve" case in this module uses (`_cmd_roadmap_view`'s bad-slug/missing-directory checks, `_cmd_roadmap_apply`'s caught `RoadmapError`). When `plan_ids` is empty (no id given, nothing currently recoverable), print an `info(...)` line ("nothing to materialize — every draft classifies current" or similar) and return `0` without entering the batch loop or writing a report — mirroring step 4's "a zero-plan roadmap ... trivially applied" rule, but as its own early return so the operator doesn't read a "materialized 0 of 0" line that a bare reuse of `_render_seed_refresh_result` would otherwise produce.

### The batch loop and its shared per-plan primitive

For each targeted plan id, in `artifact.plans` order, look up its `PlanRow` and call the new `plan_tool.roadmap.materialize_and_diff_one_plan`:

```
def materialize_and_diff_one_plan(
    slug: str,
    row: PlanRow,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: StageInvoker = shell_roadmap_invoker,
    max_attempts: int = MAX_STAGE_ATTEMPTS,
) -> tuple[tuple[RoadmapSeedRefreshChange, ...], RoadmapSeedRefreshFailure | None]:
```

Capture the "before" state for both possible targets — `draft_path = resolve_draft_seed_path(plans_dir, slug, row.draft_seed_path)` and `promoted_path = repo_root / "plan-seeds" / f"{row.id}.md"` — the same `target if target.is_file() else _latest_seed_archive(target)` pattern `refresh_roadmap_seeds` uses, captured *before* calling `materialize_plan_seed` since a successful call may overwrite either file. On success, re-read whichever target(s) now exist and build one `RoadmapSeedRefreshChange` each via `_seed_refresh_diff`, using the same `unchanged`/`updated`/`recreated`/`created` classification `refresh_roadmap_seeds` already computes (previous path equals the target → existed before; a non-`None` previous that isn't the target itself → recreated from archive; `None` → newly created). On failure, return one `RoadmapSeedRefreshFailure` built from the result's `failure_kind`/`failure_detail`/`violations` and no changes. `PlanRow` needs adding to `roadmap.py`'s existing `plan_tool.roadmap_artifacts` import block.

`_cmd_roadmap_materialize`'s own loop is then just:

```
changes: list[RoadmapSeedRefreshChange] = []
failures: list[RoadmapSeedRefreshFailure] = []
extra = {"invoker": invoker} if invoker is not None else {}
for row in artifact.plans:
    if row.id not in plan_ids:
        continue
    plan_changes, failure = materialize_and_diff_one_plan(
        args.slug, row, repo_root=repo_root, plans_dir=plans_dir, **extra
    )
    changes.extend(plan_changes)
    if failure is not None:
        failures.append(failure)
```

No early return on a failure — every targeted plan gets its own attempt, matching step 4's per-plan failure isolation the plan's own intent commits this step to sharing. Do not wrap the loop body in `try/except RoadmapError`: an unknown-id raise from `materialize_plan_seed` cannot fire here, since every `row.id` this loop passes already came from `classifications`/`artifact.plans` — the same "this defends other callers, not this one's own loop" reasoning step 4's Input section gives for the identical raise.

### Reusing step 4's report and result shapes

Write the report through the second new function:

```
def write_seed_refresh_report(
    slug: str,
    changes: Sequence[RoadmapSeedRefreshChange],
    failures: Sequence[RoadmapSeedRefreshFailure] = (),
    *,
    plans_dir: Path,
) -> Path | None:
    if not changes and not failures:
        return None
    report_path = seed_refresh_report_path(roadmap_dir(plans_dir, slug))
    atomic_write_text(report_path, _render_seed_refresh_report(slug, changes, failures))
    return report_path
```

Both `atomic_write_text` and `seed_refresh_report_path` are already imported into `roadmap.py`; `_render_seed_refresh_report` is called from within the same module, so it needs no visibility change. Note for the implementer: confirm `_render_seed_refresh_report`'s landed signature actually takes `failures` as a third positional/keyword parameter once step 4 has landed — if step 4 shipped a different parameter name or order, match what's on disk rather than this sketch.

Determine the outcome with the identical three-way rule step 4 uses (`failures` empty → `SEED_REFRESH_OUTCOME_APPLIED`; non-empty with `changes` empty → `SEED_REFRESH_OUTCOME_EXHAUSTED`; both non-empty → `SEED_REFRESH_OUTCOME_PARTIAL`), build a `RoadmapSeedRefreshResult(outcome=outcome, changes=tuple(changes), failures=tuple(failures), report_path=report_path)`, and render it through the existing `_render_seed_refresh_result` — reused unmodified, or with one small optional addition: a `verb: str = "refreshed"` keyword parameter so `--materialize` can pass `verb="materialized"` and print "materialized N of M tracked file(s)" instead of the refresh-specific wording, with the default preserving `--refresh-seeds`'s existing text byte-for-byte. Map the outcome to an rc with the same `0`/`_RC_PARTIAL`/`_RC_INCOMPLETE` values step 4 defines — reuse the constant, don't mint a second one.

### The one shared-logic gap this step deliberately leaves open

`materialize_and_diff_one_plan`'s before/after-diff shape duplicates, in miniature, the per-row loop body `refresh_roadmap_seeds` runs inline after step 4 lands — both capture a "before" path, call `materialize_plan_seed`, and classify the same four actions. This step does not refactor `refresh_roadmap_seeds` to call the new shared function instead of its own inline loop: that would mean editing step 4's already-landed function body inside a step whose own title and declared `files:` list frame it as CLI-flag work, and doing so purely to remove a small, already-isolated duplication is exactly the "shared location that needs consolidating into a single source... requires a refactor/consolidation step `detail` cannot mint" case — routed to Deferred rather than folded in here.

### What this step does not do

- Does not touch `--apply`'s promotion preflight, stage 4's own inline generation, or any bundle machinery — those are steps 6 and 9.
- Does not add a new outcome vocabulary, a new rc value, or a new report format — it reuses step 4's three-way outcome, rc mapping, and report shape by design (see Implementation), per the plan's own step 5 intent ("reports the same three-way outcome for its own batch runs").
- Does not skip a plan a roadmap revision left genuinely unaffected — every currently `missing`/`stale`/`malformed`/`path-escaping`/`digest-mismatched` plan is a candidate; that finer-grained skip needs `roadmap-incremental-revision.md` (see Deferred).

## Tests

### Tests for this step

**`tests/test_roadmap.py` — the two new `roadmap.py` functions, unit-level with an injected `_StubInvoker` (reusing `_Env`/`env`, `_seed_text`, `_plans`):**

- `test_materialize_and_diff_reports_created_for_a_first_time_draft` — no prior file: a clean call returns one `RoadmapSeedRefreshChange` with `action="created"`, no failure.
- `test_materialize_and_diff_reports_updated_for_an_existing_current_draft` — a prior draft with different content: `action="updated"`.
- `test_materialize_and_diff_reports_unchanged_when_the_regenerated_body_matches` — the stub reply reproduces the prior file's exact bytes: `action="unchanged"`.
- `test_materialize_and_diff_reports_recreated_from_an_archived_copy` — prior file moved to `archive/<name>.replaced.md`: `action="recreated"`, `previous` points at the archive path.
- `test_materialize_and_diff_also_diffs_a_promoted_copy_when_published` — sidecar `published: true`: two changes, one per target.
- `test_materialize_and_diff_returns_a_failure_and_no_changes_on_exhaustion` — every attempt bad: `changes == ()`, `failure.failure_kind` is one of `FAILURE_INVOKE`/`FAILURE_PARSE`/`FAILURE_GATES`, matching the stub's induced failure.
- `test_materialize_and_diff_leaves_the_prior_draft_untouched_on_exhaustion` — seed a draft, exhaust every attempt: file bytes unchanged after the call (mirrors step 2's own exhaustion contract, exercised through this wrapper).
- `test_materialize_and_diff_default_invoker_is_shell_roadmap_invoker` — signature/default check, matching the existing convention for `run_roadmap`/`refresh_roadmap_seeds`/`materialize_plan_seed`.

**`write_seed_refresh_report`:**

- `test_write_seed_refresh_report_writes_the_report_and_returns_its_path` — non-empty `changes`: file exists at `seed_refresh_report_path(...)`, contains the change's plan id.
- `test_write_seed_refresh_report_includes_failures` — non-empty `failures`, empty `changes`: report names the failed plan id and failure kind.
- `test_write_seed_refresh_report_returns_none_and_writes_nothing_when_both_are_empty` — no file created, `None` returned.

**`tests/cli/test_roadmap_cmd.py` — argparse (added to `TestArgparseWiring`):**

- `test_materialize_defaults_to_none` — `--materialize` absent: `args.materialize is None`.
- `test_materialize_with_no_value_yields_the_all_sentinel` — bare `--materialize`: `args.materialize is roadmap_cmd._MATERIALIZE_ALL`.
- `test_materialize_with_a_value_captures_the_plan_id` — `--materialize plan-a`: `args.materialize == "plan-a"`.
- `test_materialize_mutually_exclusive_with_apply_and_refresh_seeds_and_view` — each pairing raises `SystemExit`.
- `test_help_documents_materialize` — `--materialize` appears in `_roadmap_help()`.

**`tests/cli/test_roadmap_cmd.py` — a new `TestMaterializeMode` class, mirroring `TestApplyMode`'s monkeypatch style (`_ns()` extended with `materialize=None` by default; `MODULE.classify_draft_seeds`, `MODULE.materialize_and_diff_one_plan`, `MODULE.load_plans_artifact` stubbed at the `roadmap_cmd` module level):**

- `test_materialize_delegates_without_running_stages_or_apply` — stubbing `run_roadmap`/`apply_roadmap_seeds` to raise `AssertionError`, confirms neither runs.
- `test_materialize_all_targets_every_recoverable_plan_and_skips_current` — a fixture with one `current` and two `missing`/`stale` plans: only the two non-current plan ids reach `materialize_and_diff_one_plan`.
- `test_materialize_one_targets_only_that_plan` — `--materialize plan-a` with plan-a `stale` and plan-b `missing`: only plan-a is called.
- `test_materialize_unknown_plan_id_refuses_naming_no_such_plan` — a plan id absent from the roadmap: `error` output contains "no such plan in this roadmap"; rc `_RC_USAGE`; `materialize_and_diff_one_plan` never called.
- `test_materialize_current_plan_id_refuses_naming_the_classification` — a known, `current`-classifying id: output names `current`; rc `_RC_USAGE`; nothing called.
- `test_materialize_duplicate_plan_id_refuses_naming_the_classification` — a known, `duplicate`-classifying id: output names `duplicate`; rc `_RC_USAGE`.
- `test_materialize_nothing_recoverable_prints_info_and_returns_zero_without_a_report` — every plan `current`: rc `0`; no `seed-refresh-report.md` written; `materialize_and_diff_one_plan` never called.
- `test_materialize_applied_outcome_returns_zero` — every targeted plan succeeds: rc `0`, output shows the "materialized" wording (or the reused wording, per whichever the implementation chose).
- `test_materialize_partial_outcome_returns_rc_partial` — one of two targeted plans fails: `cmd_roadmap(...) == roadmap_cmd._RC_PARTIAL` (asserted as the literal `3`, matching this file's existing convention of asserting rc as a literal).
- `test_materialize_exhausted_outcome_returns_rc_incomplete` — every targeted plan fails: rc `1`; report still written (mirrors step 4's own "every plan fails still writes a report naming the failures" behavior once `write_seed_refresh_report` is fed a non-empty `failures`).
- `test_materialize_writes_the_same_report_path_refresh_seeds_would` — assert the written path equals `seed_refresh_report_path(roadmap_dir(plans_dir, slug))`, the identical destination `--refresh-seeds` uses.
- `test_materialize_forwards_a_supplied_invoker` / `test_materialize_omits_invoker_kwarg_when_none_supplied` — mirrors `TestOrchestratorWiring`'s equivalent pair for `run_roadmap`.
- `test_materialize_bad_roadmap_artifact_returns_usage_rc` — `load_plans_artifact` stubbed to raise `RoadmapArtifactError`: rc `_RC_USAGE`, `classify_draft_seeds` never called.
- `test_materialize_corrupt_seed_state_returns_usage_rc` — `classify_draft_seeds` stubbed to raise `RoadmapSeedStateError`: rc `_RC_USAGE`.

**Against the real classifier and a real fixture (mirrors `TestApplyMode`'s use of `_write_apply_fixtures`; new helper, e.g. `_write_materialize_fixtures`, extending the existing pattern with a `seed-state.json` sidecar so the fixture actually exercises more than one classification):**

- `TestMaterializeAgainstTheRealClassifier::test_materialize_all_over_a_mixed_roadmap_regenerates_only_the_recoverable_plans` — a three-plan roadmap on disk (one `current` via a matching sidecar digest, one `missing`, one `digest-mismatched` via a hand-edited file) with a `_StubInvoker` supplying clean per-plan replies; asserts only the two non-`current` plans' draft files change and the `current` plan's bytes are untouched.

Every test above is green before this step is considered finished.

## Acceptance criteria

- `plan-tool roadmap <slug> --materialize` (no id) regenerates every plan step 3 classifies `missing`, `stale`, `malformed`, `path-escaping`, or `digest-mismatched`, and leaves every plan classified `current` or `duplicate` untouched — checkable via the mixed-roadmap integration test.
- `plan-tool roadmap <slug> --materialize <plan-id>` naming a `current` or `duplicate` plan refuses, printing that exact classification, and calls neither `materialize_plan_seed` nor `materialize_and_diff_one_plan`.
- `plan-tool roadmap <slug> --materialize <plan-id>` naming an id absent from the roadmap refuses with a message containing "no such plan in this roadmap".
- One targeted plan's exhausted regeneration does not prevent another targeted plan in the same invocation from succeeding — `rg -n "materialize_and_diff_one_plan" plan_tool/cli/roadmap_cmd.py` shows it called inside a loop with no early `return` on a per-plan failure.
- A `--materialize` batch reports `SEED_REFRESH_OUTCOME_APPLIED`/`_PARTIAL`/`_EXHAUSTED` and exits `0`/`_RC_PARTIAL`/`_RC_INCOMPLETE` using the same constants `--refresh-seeds` uses — `rg -n "SEED_REFRESH_OUTCOME_|_RC_PARTIAL" plan_tool/cli/roadmap_cmd.py` shows no second outcome or rc vocabulary minted for materialize.
- Materializing any state with a prior draft file (`stale`/`malformed`/`path-escaping`/`digest-mismatched`) writes the same `seed-refresh-report.md` destination and diff format `--refresh-seeds` writes.
- `--materialize` is mutually exclusive with `--apply`, `--refresh-seeds`, `--from-stage`, and `--view` at the argparse layer.
- `plan_tool.roadmap.materialize_and_diff_one_plan` and `plan_tool.roadmap.write_seed_refresh_report` exist, are called from `plan_tool/cli/roadmap_cmd.py`, and neither one's addition changes `refresh_roadmap_seeds`'s existing behavior — `uv run pytest tests/test_roadmap.py -q -k TestRefreshRoadmapSeeds` (or whatever step 4 names that class) stays green unmodified.
- `docs/cli/roadmap.md` documents `--materialize` (regenerated via `python -m plan_tool.cli_reference --write`, not hand-edited); `uv run pytest tests/cli/test_cli_reference.py -q` is green.
- `cmd_roadmap`'s docstring lists `--materialize` alongside `--apply`/`--view` as a dispatch mode.
- `uv run pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py tests/cli/test_cli_reference.py -q` is green.

## References

- `ROADMAP_FORMAT.md` — the `seed-state.json`/classification contract this flag targets against (documented in full by step 3); not edited by this step.
- `DATA_CONTRACT.md` — `seed-state.json`'s persisted shape and the `draft_seed_count` field this plan's manifest work extends; unchanged by this step.

## Applicable guardrails

- **Step intent's own fence — "a separate, coexisting entry point from `--refresh-seeds`, not a replacement for it."** This step adds no change to `refresh_roadmap_seeds` or its CLI wiring; `--refresh-seeds` keeps regenerating every plan unconditionally.
- **Plan's `## Out of scope` — "regenerating every seed on a roadmap revision... or writing a replacement without the explicit materialization/refresh action."** The two-way refusal is what keeps this true for `--materialize`: it never regenerates a plan the operator didn't name or that isn't in the recoverable set.
- **Plan's `## Out of scope` — "a correctness gate on seed style, length, or model agreement."** Target selection reads step 3's classification only; this step adds no new judgment of a reply's content beyond what `materialize_plan_seed` (step 2) already runs.
- **Plan's Architecture — "one seed materialization job owns one draft path... without asking a backend to reconstruct siblings" and no concurrency.** The batch loop calls `materialize_and_diff_one_plan` serially, one plan at a time, matching `CLAUDE.md`'s standing architecture stance against in-process fan-out over shared mutable state (`seed-state.json`).
- **Plan's Architecture — composition with `roadmap-incremental-revision.md`, not yet promoted to a plan.** This step's "every currently recoverable plan id" default has nothing finer to skip until that sibling ships; see Deferred.

## Deferred

- **Skipping a plan a revision left genuinely unaffected.** Needs `docs/implementation-plans/plan-seeds/roadmap-incremental-revision.md`, not yet promoted to a plan; until it ships, `--materialize` (no id) always processes every currently recoverable plan id, informed only by step 3's live classification.
- **Consolidating `materialize_and_diff_one_plan`'s before/after-diff shape with `refresh_roadmap_seeds`'s own inline per-row loop.** Both do the same four-way (unchanged/updated/recreated/created) classification around one `materialize_plan_seed` call; folding `refresh_roadmap_seeds` onto the new shared function is a behavior-preserving refactor of step 4's landed code, out of this step's own footprint — route to reconcile or `BACKLOG.md`.
- **Promotion refusal on any non-`current` classification.** Step 6 — this step never touches `apply_roadmap_seeds` or its preflight.
- **Surfacing these seven states in the roadmap views.** Steps 7 and 8 — this step ships no change to `plan_tool/roadmap_view.py`.
- **Retiring stage 4's own inline seed generation and the bundle machinery.** Step 9 — untouched here.
- **Accepting a hand-edited, `digest-mismatched` draft as current without regenerating it.** Step 10's accept action — `--materialize` always calls `materialize_plan_seed`, which always generates fresh content; it has no path that preserves a live hand edit as-is.
- **Model-call observability for the backend calls this batch loop makes.** Out of scope for this plan (see the plan's own Deferred section); routed to the batch-authoring-observability plan lineage.
