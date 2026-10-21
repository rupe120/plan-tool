> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Add a CLI flag to materialize recoverable draft-seed states

## Summary

Adds `plan-tool roadmap <slug> --materialize [--plan-id ID]`, a new run mode in `plan_tool/cli/roadmap_cmd.py` that regenerates exactly the plan ids step 3's classifier (`plan_tool.roadmap_seed_manifest.classify_draft_seeds`) reports as recoverable — `missing`, `stale`, `malformed`, `path-escaping`, or `digest-mismatched` — leaving an already-`current` draft alone and refusing a `duplicate` one outright. Omitting `--plan-id` processes every recoverable plan in one call, isolating each plan's failure the way `--refresh-seeds` does; supplying it targets exactly one plan and refuses (naming the reason) when that id doesn't exist in the roadmap or already classifies `current`/`duplicate`. The orchestration this needs — classify, pick targets, call step 2's `materialize_plan_seed` per target, isolate failures, write the shared before/after report — is new business logic that belongs beside `refresh_roadmap_seeds`, not inside the CLI handler, so this step adds `materialize_roadmap_seeds` to `plan_tool/roadmap.py` as a necessary file addition (see Files). On green, an operator can backfill a fresh roadmap's first materialization or resume a partial/content-drift failure without touching any draft that is already fine.

## Table of Contents

- [Why](#why) — the gap this flag closes and why the loop can't live in the CLI file alone
- [Input](#input) — step 2's and step 3's contracts this step calls directly
- [Files (creates vs edits)](#files-creates-vs-edits) — the declared files plus three necessary additions
- [Implementation](#implementation) — the new orchestrator function, the CLI flags, and the outcome/rc mapping
- [Tests](#tests) — coverage for the orchestrator and the CLI wiring
- [Acceptance criteria](#acceptance-criteria)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

Today there is no way to regenerate one plan's draft, or every currently-broken draft, without either running `--refresh-seeds` (which regenerates *every* plan unconditionally, including ones that are already fine) or hand-editing `seed-state.json`. Step 3's classifier now exists to answer "is this plan's draft safe to use", and step 2's `materialize_plan_seed` now exists to regenerate exactly one plan — but nothing yet asks the classifier which plans need it and drives the primitive over that set. This step is that driver, wired to its own CLI flag.

`--materialize` is a genuinely different selection from `--refresh-seeds`, not a faster version of it: it never touches an already-`current` draft, and it never touches `duplicate` (a plan-row collision no regeneration can fix — the operator has to resolve the colliding rows in a roadmap revision instead). Skipping drafts a *revision* left genuinely unaffected is a separate, not-yet-shipped capability (`docs/implementation-plans/plan-seeds/roadmap-incremental-revision.md`, cited by the plan's own Architecture and Deferred) — until it lands, a revision still invalidates every tracked draft together, so right after one, `--materialize`'s recoverable set is the same as `--refresh-seeds`'s full set. This step's standing value is backfilling a brand-new roadmap's first materialization and resuming a partial or content-drift failure without regenerating drafts nothing is wrong with.

`plan_tool/cli/roadmap_cmd.py`'s own module docstring is explicit that this file is "deliberately thin: the stage table, the gates, the retry budget, and the artifact contract all live in `plan_tool.roadmap`... this module owns only path resolution, the exit-code mapping, and the operator summary." Classifying every plan, deciding which ids are in scope, looping over them with per-plan failure isolation, and writing a before/after report is exactly the retry-budget-and-artifact-contract kind of logic that rule reserves for `plan_tool/roadmap.py` — it is also, structurally, the same shape step 4 already built for `--refresh-seeds` (`refresh_roadmap_seeds`). Putting it in the CLI file instead would duplicate that shape in the one module that is supposed to stay thin.

## Input

This step calls two contracts it does not own, from two different plan steps:

- **Step 3's classifier**, `plan_tool.roadmap_seed_manifest.classify_draft_seeds(artifact: PlansArtifact, *, plans_dir: Path, slug: str) -> dict[str, DraftSeedClassification]`, keyed by plan id, where `DraftSeedClassification(plan_id: str, state: str, detail: str = "")`. `state` is one of the seven module-level constants step 3 defines (`DRAFT_SEED_STATE_CURRENT`, `_MISSING`, `_STALE`, `_MALFORMED`, `_PATH_ESCAPING`, `_DUPLICATE`, `_DIGEST_MISMATCHED`); `classify_draft_seeds` never writes anything (step 3's own "never writes" constraint), so calling it here is read-only preflight. `plan_tool.roadmap_seed_manifest` is a leaf module (imports only `roadmap_artifacts`, `roadmap_gates`, `roadmap_seed_state`); `plan_tool.roadmap` importing it is exactly the edge step 3's own Implementation names as expected ("consumed by `cli/authoring.py`... designed to be called from `roadmap.py`/`roadmap_view.py`").
- **Step 2's primitive**, `plan_tool.roadmap.materialize_plan_seed(slug, plan_id, *, repo_root, plans_dir, invoker=shell_roadmap_invoker, max_attempts=MAX_STAGE_ATTEMPTS) -> RoadmapSeedMaterializeResult` — already defined in this same module by step 2, `depends_on`'s note for step 2 says this call generates one plan's draft, writes its `seed-state.json` entry, and resyncs an already-promoted `plan-seeds/<id>.md` copy, all inside the one call, or leaves everything untouched on an exhausted attempt. Step 2's own result type name (`RoadmapSeedMaterializeResult`) is reused here for step 2's *single-plan* result; this step's own new result type needs a different name to avoid a collision — see Implementation.
- **What this step does not assume about step 4.** Step 4 (`refresh_roadmap_seeds`) adds `SEED_REFRESH_OUTCOME_PARTIAL` and a new `RoadmapSeedRefreshFailure` type to this same module for an almost-identical per-plan batch shape, but this step's `depends_on` is `[2, 3]`, not `4` — nothing here may assume those step-4 symbols already exist in `plan_tool/roadmap.py` at implementation time. This step mints its own outcome constants and its own per-plan failure record instead of importing step 4's (see Implementation, Deferred). It *does* reuse `RoadmapSeedRefreshChange` and the report helpers (`_seed_refresh_diff`, `_render_seed_refresh_report`, `seed_refresh_report_path`) directly, because those already exist in `plan_tool/roadmap.py` at HEAD, independent of step 4 landing — the plan's own step 5 intent text says this flag "writes the same before/after diff `--refresh-seeds` already produces (`seed-refresh-report.md`)," so sharing the file and its renderer is the point, not an accident of ordering.

## Files (creates vs edits)

**Existing files (edits only), as declared:**

- `plan_tool/cli/roadmap_cmd.py` — the `--materialize`/`--plan-id` flags, the pre-dispatch validation, `_cmd_roadmap_materialize`, `_render_materialize_result`, and the module/CLI docstring updates.
- `tests/cli/test_roadmap_cmd.py` — argparse wiring, dispatch wiring, and outcome→rc coverage for the new flags.

**Necessary additions (not in the plan's declared list — see below):**

- `plan_tool/roadmap.py` — add `materialize_roadmap_seeds`, its result/failure types, and its outcome constants.
- `tests/test_roadmap.py` — tests for `materialize_roadmap_seeds`, mirroring where step 2's and step 4's own tests for their new `roadmap.py` primitives live.
- `TESTING.md` — one new invoker-neutralization row for `materialize_roadmap_seeds(invoker=...)`, following the existing `roadmap.py → run_roadmap(invoker=...)` row's format (step 2's own detail added the equivalent row for `materialize_plan_seed`).

**Why the additions are necessary:** the plan's `enforce_step_tests: true` requires a real test-authoring delta, and the orchestration this flag needs (classify, select targets, loop with per-plan isolation, write the report) is exactly the kind of logic `plan_tool/cli/roadmap_cmd.py`'s own docstring reserves for `plan_tool.roadmap` (see Why). Step 2's and step 4's detail files set this same precedent explicitly for their own `roadmap.py` additions and TESTING.md rows; this step follows it for the same reason.

## Implementation

### `materialize_roadmap_seeds` in `plan_tool/roadmap.py`

Recommended signature, alongside `refresh_roadmap_seeds`:

```
def materialize_roadmap_seeds(
    slug: str,
    *,
    repo_root: Path,
    plans_dir: Path,
    plan_id: str | None = None,
    invoker: StageInvoker = shell_roadmap_invoker,
    max_attempts: int = MAX_STAGE_ATTEMPTS,
) -> RoadmapSeedMaterializeBatchResult:
```

The name follows the module's existing `refresh_roadmap_seeds`/`apply_roadmap_seeds` family (verb + `roadmap_seeds`), and is deliberately plural where step 2's `materialize_plan_seed` is singular — the same singular/plural split the module already uses between `materialize_plan_seed` (one plan, unconditional) and `refresh_roadmap_seeds` (every plan). The result type needs its own name (`RoadmapSeedMaterializeBatchResult` or similar) because `RoadmapSeedMaterializeResult` is already step 2's return type for the single-plan primitive — reusing that name here would either collide or force an import alias; picking a distinct name for the batch/targeted result keeps both readable at their call sites.

**Preflight**, mirroring `refresh_roadmap_seeds`: validate `roadmap_dir(plans_dir, slug)` (`ValueError` → `RoadmapError`), then load only the plans artifact — `loaded = _load_stage_artifact(STAGES[-1], plans_dir=plans_dir, slug=slug); artifact = loaded.artifact` — with the same defensive `isinstance(artifact, PlansArtifact)` check `refresh_roadmap_seeds` already has.

**Classify.** Call `classify_draft_seeds(artifact, plans_dir=plans_dir, slug=slug)`. Wrap the call in `try/except RoadmapSeedStateError: raise RoadmapError(...) from exc`, mirroring `_load_roadmap_seed_state`'s existing one-line conversion — step 3's module has no `RoadmapError` of its own to raise (it cannot import this leaf-consuming module), so the conversion belongs at this call site, the same way it already does for every other `roadmap.py` reader of the sidecar.

**Select targets**, in `artifact.plans` order (not dict-iteration order, even though step 3's classifier happens to build its dict in that same order — iterate the artifact directly so the ordering guarantee doesn't quietly depend on a fact this function doesn't own):

- Define `MATERIALIZABLE_DRAFT_SEED_STATES` at module scope as a tuple of the five recoverable state constants imported from `plan_tool.roadmap_seed_manifest` (`DRAFT_SEED_STATE_MISSING`, `_STALE`, `_MALFORMED`, `_PATH_ESCAPING`, `_DIGEST_MISMATCHED`) — read the spellings off step 3's constants, never re-typed string literals, the same "read it off the enum" rule `cli/roadmap_cmd.py`'s own `_feedback_summary_lines`/`_newly_settled_summary_lines` already follow for `FeedbackState`/`DecisionStatus`.
- **No `plan_id` given (batch mode):** `targets = [row.id for row in artifact.plans if classifications[row.id].state in MATERIALIZABLE_DRAFT_SEED_STATES]`.
- **`plan_id` given (targeted mode):**
  - Not a key in `classifications` at all (no plan row with that id) → raise `RoadmapError` naming the slug and the plan id, mirroring the existing "`--from-stage 9` is not a stage of this roadmap" precedent for "the operator named something this roadmap doesn't have." The invoker must never be called on this path.
  - A key whose `state` is `DRAFT_SEED_STATE_CURRENT` or `DRAFT_SEED_STATE_DUPLICATE` → return immediately with the batch result's `SEED_MATERIALIZE_OUTCOME_REFUSED` outcome (see below) and `refusal_reason` set to that `state` value — mirroring step 6's promotion refusal per this step's own plan intent. No invoker call, no write, no report.
  - Otherwise → `targets = [plan_id]`.

**Loop**, one plan at a time, no concurrency (Architecture's "one seed materialization job owns one draft path... without asking a backend to reconstruct siblings" and its explicit no-concurrency stance, plus `CLAUDE.md`'s standing rule against in-process fan-out over shared mutable state — `seed-state.json` is exactly that shared document). For each `target_id` in `targets`, in order:

1. Capture the "before" state for both possible write targets, the same pattern step 4 uses: `draft_path = resolve_draft_seed_path(plans_dir, slug, row.draft_seed_path)` and `promoted_path = repo_root / "plan-seeds" / f"{target_id}.md"`, each snapshotted as `target if target.is_file() else _latest_seed_archive(target)` *before* the call.
2. Call `materialize_plan_seed(slug, target_id, repo_root=repo_root, plans_dir=plans_dir, invoker=invoker, max_attempts=max_attempts)`.
3. On success, re-read whichever of the two targets now exist on disk and build a `RoadmapSeedRefreshChange` for each, exactly as step 4's Implementation describes (reuse `_seed_refresh_diff` unchanged and the same `unchanged`/`updated`/`recreated`/`created` classification) — append to `changes`.
4. On failure, append one new `RoadmapSeedMaterializeFailure(plan_id=target_id, failure_kind=result.failure_kind, failure_detail=result.failure_detail, violations=result.violations)` to `failures`. Neither target is read.
5. Continue regardless of outcome — no early return.

**Outcome**, same three-way rule as step 4's (independently derived here, not imported, per Input):

- `failures` empty → `SEED_MATERIALIZE_OUTCOME_APPLIED` (covers the batch-mode zero-target case too: nothing recoverable, nothing failed).
- `failures` non-empty and `changes` empty → `SEED_MATERIALIZE_OUTCOME_EXHAUSTED`.
- both non-empty → `SEED_MATERIALIZE_OUTCOME_PARTIAL`.

**The report.** Write via `_render_seed_refresh_report`/`seed_refresh_report_path(roadmap_dir(plans_dir, slug))`/`atomic_write_text` whenever `changes or failures` is non-empty; skip only when both are empty (nothing was targeted). This deliberately writes to the *same* `seed-refresh-report.md` a `--refresh-seeds` run also writes — the plan's own intent text commits to sharing this file, so whichever of the two commands ran most recently is the one whose report is on disk; that is the accepted design, not a gap to close here. If step 4 has already extended `_render_seed_refresh_report`'s signature to accept a `failures` sequence by the time this step is implemented, call that extended form directly; if not, extend it here with the same shape step 4's Implementation describes (one `## {plan_id} — failed ({failure_kind})` section per failure, its violation messages, and `failure_detail` when present) — do not add a second, parallel failure-rendering code path in the same function.

**New types**, module scope, alongside the refresh types:

```
SEED_MATERIALIZE_OUTCOME_APPLIED = "materialized"
SEED_MATERIALIZE_OUTCOME_PARTIAL = "materialize-partial"
SEED_MATERIALIZE_OUTCOME_EXHAUSTED = "materialize-exhausted"
SEED_MATERIALIZE_OUTCOME_REFUSED = "materialize-refused"

@dataclass(frozen=True)
class RoadmapSeedMaterializeFailure:
    plan_id: str
    failure_kind: str
    failure_detail: str | None = None
    violations: tuple[Violation, ...] = ()

@dataclass(frozen=True)
class RoadmapSeedMaterializeBatchResult:
    outcome: str
    changes: tuple[RoadmapSeedRefreshChange, ...] = ()
    failures: tuple[RoadmapSeedMaterializeFailure, ...] = ()
    report_path: Path | None = None
    refusal_reason: str | None = None
```

`refusal_reason` is populated only for `SEED_MATERIALIZE_OUTCOME_REFUSED` (the known-but-`current`/`duplicate` case); every other outcome leaves it `None`. The unknown-plan-id refusal never reaches this type at all — it is a raised `RoadmapError`, per Select targets above, so it reuses the CLI's existing `except (RoadmapError, RoadmapArtifactError)` handling with no new branch.

**No run-log or telemetry wiring.** Matches step 2's and step 4's own stance: this function accepts no `run_logger` and emits no run-log events. Call-level observability for roadmap seed backend calls is routed to the batch-authoring-observability plan lineage, not built here (see the plan's own Deferred section).

### CLI wiring in `plan_tool/cli/roadmap_cmd.py`

**Two new arguments in `register()`:**

- `--materialize` (`action="store_true"`) added as a fifth member of the existing `run_mode_group` mutually-exclusive group, alongside `--apply`/`--refresh-seeds`/`--from-stage`/`--view`.
- `--plan-id` (`default=None`, `metavar="PLAN_ID"`, dest `plan_id`) as a standalone top-level argument, *not* in the mutually-exclusive group — the same shape `--mode`/`--id` already use relative to `--view`, because argparse's mutually-exclusive-group machinery cannot express "meaningful only alongside this one sibling flag" any more than it could there.

**Pre-dispatch validation**, alongside the existing `--mode`/`--id`-require-`--view` block in `cmd_roadmap`: reject `--plan-id` without `--materialize` before any path resolution, the same pattern and the same `_RC_USAGE` result.

**Dispatch**, in `cmd_roadmap`, ordered after the existing `--refresh-seeds` branch and before the `--view` branch: `if getattr(args, "materialize", False): return _cmd_roadmap_materialize(args, repo_root=repo_root, plans_dir=plans_dir, invoker=invoker)`.

**`_cmd_roadmap_materialize`**, modeled on `_cmd_roadmap_refresh_seeds`: call `materialize_roadmap_seeds(args.slug, repo_root=repo_root, plans_dir=plans_dir, plan_id=args.plan_id, **extra)` inside the same `try/except (RoadmapError, RoadmapArtifactError): error(...); return _RC_USAGE` shape — this is what makes the unknown-plan-id `RoadmapError` reach the operator with no new CLI branch. On a returned result, call `_render_materialize_result` and map the outcome to an rc:

- `SEED_MATERIALIZE_OUTCOME_APPLIED` → `0`
- `SEED_MATERIALIZE_OUTCOME_PARTIAL` → `_RC_PARTIAL` — check whether step 4 has already added `_RC_PARTIAL = 3` to this module (step 4 is lower-numbered and, in an ordinary sequential run, lands first); reuse it if present, since both commands' "partial" rc means the same thing (a mixed batch). Add it locally, same value, only if step 4 has not landed it yet.
- `SEED_MATERIALIZE_OUTCOME_EXHAUSTED` → `_RC_INCOMPLETE` (already module-level, already reused across `run_roadmap` and `refresh_roadmap_seeds`).
- `SEED_MATERIALIZE_OUTCOME_REFUSED` → `_RC_USAGE`, matching `_apply_roadmap_seeds`'s own `APPLY_OUTCOME_REFUSED` → `_RC_USAGE` mapping.

**`_render_materialize_result`**, a new function modeled closely on `_render_seed_refresh_result` — do not merge the two into one shared renderer: `RoadmapSeedMaterializeBatchResult` carries a `REFUSED` outcome and a `refusal_reason` field `RoadmapSeedRefreshResult` has no equivalent for, so a merged function would need an `isinstance`/outcome-vocabulary branch either way, and `tests/test_duplication.py`'s zero-duplicate-groups guard applies to identical bodies, not to same-shaped functions with genuinely different branches.

- `APPLIED`/`PARTIAL` render the existing-style success block (per-change `plan_id: action target` lines, the report path) plus, when `failures` is non-empty, one `error(...)` line per failure (plan id, failure kind, violation messages, failure detail) — mirroring `_render_seed_refresh_result`'s planned `PARTIAL` handling from step 4's own Implementation (both blocks, not `elif`).
- `EXHAUSTED` renders only the failure block.
- `REFUSED` renders one `error(f"roadmap {slug}: refusing to materialize plan '{plan_id}' — classifies as '{result.refusal_reason}'")`-shaped line, mirroring `_render_apply_result`'s `APPLY_OUTCOME_REFUSED` branch's tone.
- **Zero-target batch** (`APPLIED` with `changes == () and failures == ()`) is a real, expected outcome (every plan already `current`) — render a distinct, informative line for it (e.g. `info(f"roadmap {slug}: every recoverable draft is already current; nothing to materialize")`) rather than falling through to a "0 of 0" success line that would read as nothing having run.

**Docstrings.** Add a `--materialize` paragraph to the module docstring alongside the existing `--apply`/`--refresh-seeds` ones, and extend `cmd_roadmap`'s own docstring's rc-mapping enumeration: rc 2 gains "a `--materialize` target absent from the roadmap, or `--plan-id` without `--materialize`"; rc 1's "a stage exhausted its retry budget" note extends to "or a `--materialize` batch where every targeted plan failed"; note the new rc for a partial `--materialize` batch. Extend `register()`'s subparser `help=` string and the `--apply`/`-y` help paragraph is unaffected (`-y` stays scoped to `--apply` only, per the parser's existing `yes_parent` comment — `--materialize` needs no confirm, the same as `--refresh-seeds`).

## Tests

### Tests for this step

**`tests/test_roadmap.py`, new `TestMaterializeRoadmapSeeds` class**, reusing `_Env`/`env`, `_StubInvoker`, `_seed_text`, `_plans`/`_PLAN_ORDER`/`_PLAN_AUTH`, and a `seed-state.json` fixture built directly per case (mirroring the fixture shape `tests/test_roadmap_seed_manifest.py`, step 3, already establishes for its own classification cases):

- `test_materialize_batch_regenerates_every_recoverable_plan_and_skips_current` — three plans classifying `current`, `missing`, and `stale`; `invoker.calls == 2`; the `current` plan's file is untouched; `result.changes` covers the other two; `result.outcome == SEED_MATERIALIZE_OUTCOME_APPLIED`.
- `test_materialize_batch_isolates_one_failing_plan_and_returns_partial` — two recoverable plans, one clean reply, one bad on every attempt: `SEED_MATERIALIZE_OUTCOME_PARTIAL`; `changes` covers only the first; `failures == (RoadmapSeedMaterializeFailure(plan_id=<second>, failure_kind=FAILURE_GATES, ...),)`.
- `test_materialize_batch_returns_exhausted_and_still_writes_a_report_when_every_targeted_plan_fails` — two recoverable plans, both bad every attempt: `SEED_MATERIALIZE_OUTCOME_EXHAUSTED`, `changes == ()`, `len(failures) == 2`, `report_path is not None` and the file names both plan ids.
- `test_materialize_batch_with_nothing_recoverable_returns_applied_with_no_changes_and_no_report` — every plan classifies `current`: `invoker.calls == 0`, `changes == ()`, `failures == ()`, `report_path is None`, outcome `APPLIED`.
- `test_materialize_batch_skips_a_duplicate_classified_plan` — one plan classifies `duplicate` (a basename collision with a sibling): excluded from the batch target set; invoker never called for it.
- `test_materialize_single_plan_id_regenerates_only_that_plan` — three recoverable plans; `plan_id=<one of them>`: `invoker.calls == 1`; the other two plans' files are untouched.
- `test_materialize_unknown_plan_id_raises_without_calling_the_invoker` — `plan_id` absent from `04-roadmap.md`'s `plans`: `RoadmapError` naming the slug and plan id; `invoker.calls == 0`.
- `test_materialize_current_plan_id_refuses_naming_the_classification` — targeted plan classifies `current`: `outcome == SEED_MATERIALIZE_OUTCOME_REFUSED`, `refusal_reason == DRAFT_SEED_STATE_CURRENT`; invoker never called; file untouched; no report written.
- `test_materialize_duplicate_plan_id_refuses_naming_the_classification` — same, for `DRAFT_SEED_STATE_DUPLICATE`.
- `test_materialize_retries_a_failing_plan_up_to_max_attempts` — one recoverable plan, every reply bad, `max_attempts=2`: `invoker.calls == 2`, proving the parameter threads into `materialize_plan_seed`'s own `max_attempts`.
- `test_materialize_resyncs_a_promoted_copy_through_the_shared_primitive` — a targeted plan whose sidecar entry says `published`: after materialize, `plan-seeds/<id>.md` is updated too (thin coverage — step 2's own tests own the resync logic itself; this pins that the batch loop reads the target back correctly).
- `test_materialize_default_invoker_is_shell_roadmap_invoker` — signature/default check, mirroring the equivalent checks for `run_roadmap`/`refresh_roadmap_seeds`/`materialize_plan_seed`.

**`TestMaterializeRoadmapSeedsAgainstTheRealPrimitive`** (`@pytest.mark.integration`, mirrors step 4's `TestRefreshRoadmapSeedsAgainstTheRealPrimitive`): `shipped_env`, a real four-artifact roadmap on disk with a mixed classification set (one `current`, one `missing`), a `_StubInvoker` supplying a real conforming per-plan reply, calling `materialize_roadmap_seeds` with no `plan_id`. Asserts `SEED_MATERIALIZE_OUTCOME_APPLIED`, exactly one draft file written (the missing one), and a report on disk — the first place this loop and the shipped `roadmap-seed.md` prompt (step 2) and `classify_draft_seeds` (step 3) actually run together.

**`tests/cli/test_roadmap_cmd.py`:**

- `test_materialize_is_a_run_mode_of_its_own` — `--materialize` parses; mutually exclusive with `--apply`, `--refresh-seeds`, `--from-stage`, and `--view`, mirroring `test_refresh_seeds_is_a_run_mode_of_its_own`.
- `test_plan_id_argparse_default_is_none` — mirroring `test_id_argparse_default_is_none`.
- `test_plan_id_requires_materialize` — `--plan-id X` without `--materialize` returns `_RC_USAGE` and prints the requirement, mirroring `test_mode_requires_view`-shaped coverage (the existing `--mode`/`--id` block).
- `test_help_documents_materialize_and_plan_id` — mirroring `test_help_documents_view_mode_and_id`.
- `test_cmd_roadmap_materialize_calls_materialize_roadmap_seeds_with_the_parsed_args` — stub `materialize_roadmap_seeds` (mirroring `_stub_run`'s pattern); assert `slug`, `repo_root`, `plans_dir`, `plan_id`, and (when supplied) `invoker` all reach it.
- `test_materialize_applied_outcome_returns_zero_and_prints_the_summary`
- `test_materialize_zero_target_batch_prints_the_nothing_to_materialize_message` — an `APPLIED` result with empty `changes`/`failures`: the distinct "already current" line appears, not a bare "0 of 0" line.
- `test_materialize_partial_outcome_returns_a_distinct_rc` — asserts the literal rc value, mirroring this file's existing convention of asserting rc as a literal rather than an imported constant.
- `test_materialize_exhausted_outcome_returns_rc_one`
- `test_materialize_refused_outcome_returns_rc_two_and_names_the_classification` — a stubbed `REFUSED` result; asserts the classification name (e.g. `current`) appears in stderr.
- `test_materialize_unknown_plan_id_error_returns_rc_two` — stub `materialize_roadmap_seeds` raising `RoadmapError`; assert the message reaches stderr, mirroring `test_roadmap_error_returns_a_usage_shaped_code_and_prints_the_message`.

Every test above is green before this step is considered finished.

## Acceptance criteria

- `plan-tool roadmap <slug> --materialize` regenerates every plan id `classify_draft_seeds` reports as `missing`, `stale`, `malformed`, `path-escaping`, or `digest-mismatched`, and touches no plan classified `current` or `duplicate` — checkable with `rg -A5 'def materialize_roadmap_seeds' plan_tool/roadmap.py`.
- `plan-tool roadmap <slug> --materialize --plan-id <id>` regenerates only that plan when it is recoverable; every other plan's draft file is byte-for-byte unchanged.
- `--plan-id` naming an id absent from the roadmap exits 2 with a "no such plan" message and never calls the invoker.
- `--plan-id` naming a `current` or `duplicate` plan exits with a usage-shaped rc naming that exact classification, never silently no-ops, and never calls the invoker.
- A batch with one failing plan among several regenerates every other plan, returns a partial outcome with its own distinct exit code, and the failing plan's prior draft (if any) is left byte-for-byte unchanged.
- A batch where every targeted plan fails returns an exhausted outcome and exits 1.
- A batch with nothing recoverable exits 0, calls the invoker zero times, and prints a message naming that every draft is already current rather than a bare zero-count success line.
- Every successful materialize (batch or targeted) writes its before/after diff to the same `seed-refresh-report.md` path `--refresh-seeds` writes.
- `--plan-id` without `--materialize` exits with a usage-shaped rc and never resolves a repo root or plans dir.
- `TESTING.md` documents `materialize_roadmap_seeds(invoker=...)`'s neutralization recipe.
- `uv run pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py -q` is green.

## Applicable guardrails

- **Plan's Architecture — "one seed materialization job owns one draft path... without asking a backend to reconstruct siblings" and its no-concurrency stance.** This step's loop calls `materialize_plan_seed` serially, one plan at a time, matching `CLAUDE.md`'s standing rule against in-process fan-out over shared mutable state — `seed-state.json` is one document every call in the loop reads and writes in turn.
- **Plan's Out of scope — auto-promoting drafts, treating draft materialization as user approval.** This step never writes to `plan-seeds/` directly; any promoted-copy write happens only inside `materialize_plan_seed`'s own resync-of-an-already-promoted-copy branch (step 2), which never creates a first promotion.
- **Plan's Out of scope — a correctness gate on seed style, length, or model agreement.** This step adds no new content check; it only selects *which* plan ids to hand to step 2's primitive, which runs step 1's structural/provenance validator exactly as it already does.
- **Plan's Out of scope — general background scheduling, parallelism policy, or backend liveness instrumentation.** No `run_logger`, no concurrency, no new telemetry surface.
- **Plan's step intent — a separate, coexisting entry point from `--refresh-seeds`, not a replacement.** This step does not change `--refresh-seeds`'s own behavior (full, unconditional, every-plan regeneration) and does not gate `--materialize`'s recoverable set on a revision's actual blast radius — that is `roadmap-incremental-revision.md`'s job, not yet promoted to a plan.

## Deferred

- **Skipping drafts a revision left genuinely unaffected.** `docs/implementation-plans/plan-seeds/roadmap-incremental-revision.md`, not yet promoted to a plan — until it ships, `--materialize`'s recoverable set after a revision is the same as `--refresh-seeds`'s full set (see Why).
- **Promotion refusal in `--apply` for non-`current` drafts.** Step 6 — this step's own targeted refusal (naming `current`/`duplicate`) is a *selection* refusal for regeneration, not `--apply`'s promotion preflight, which step 6 rewires separately.
- **Routing the roadmap views through step 3's classification.** Steps 7 and 8 — this step ships no change to `plan_tool/roadmap_view.py`.
- **Accepting a hand-edited, `digest-mismatched` draft as current without regenerating it.** Step 10's accept action — `--materialize` always regenerates a `digest-mismatched` draft's content; it never records a live file's digest as-is.
- **Consolidating `RoadmapSeedMaterializeFailure` with step 4's `RoadmapSeedRefreshFailure`.** Both carry the same four fields (`plan_id`, `failure_kind`, `failure_detail`, `violations`) once both steps land, and `tests/test_duplication.py`'s zero-duplicate-groups guard may flag the pair. Folding them touches step 4's already-declared files too, which is outside this step's own footprint — route to `BACKLOG.md`, or resolve inline with a recorded `ALLOWED_DUPLICATE_GROUPS` entry citing this note, once both types are on disk.
- **Model-call observability for the per-plan `materialize_plan_seed` calls this loop makes.** Out of scope for this plan (see the plan's own Deferred section); routed to the batch-authoring-observability plan lineage.
- **Retiring stage 4's own inline seed generation or its bundle-based gates.** Step 9 — untouched by this step.

<!-- plan-tool-detail-deferrals
{"deferrals":[]}
-->
