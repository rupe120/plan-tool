> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Make explicit seed refresh generate each plan's seed independently

## Summary

Rewrites `refresh_roadmap_seeds` in `plan_tool/roadmap.py` to call step 2's `materialize_plan_seed` once per plan row instead of making one combined backend call for every plan in `04-roadmap.md`. Each plan's call is isolated: one plan's exhausted attempt no longer discards every other plan's already-succeeded regeneration, and the refresh reports which plans landed and which stayed invalidated. A new `SEED_REFRESH_OUTCOME_PARTIAL` outcome, a new `RoadmapSeedRefreshFailure` record, and a new `plan_tool/cli/roadmap_cmd.py` exit code make a mixed batch distinguishable from full success and full exhaustion at both the library and CLI layers. `plan_tool/prompts/roadmap-refresh-seeds.md` and its synthetic `_refresh_stage_for_artifact` stage are deleted — nothing renders the old "one fenced block per plan" reply format once every plan's seed is generated through step 2's own `roadmap-seed.md` prompt instead. On green, `refresh_roadmap_seeds` no longer calls `_run_stage`, builds a `RoadmapStage`, or reads `STAGES[-1].side_output_seed_paths`, which is the precondition step 9 needs before it can retire that plumbing for good.

## Table of Contents

- [Why](#why) — what today's single combined call costs and what step 2's primitive replaces it with
- [Input](#input) — step 2's `materialize_plan_seed` contract and what this step assumes about its result shape
- [Files (creates vs edits)](#files-creates-vs-edits) — the declared files plus the CLI files this step's own "own exit code" commitment requires
- [Implementation](#implementation) — the rewritten loop, the new outcome/failure types, the deleted prompt and stage, and the CLI rc mapping
- [Tests](#tests) — the rewritten and new test coverage
- [Acceptance criteria](#acceptance-criteria)
- [References](#references)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

Today's `refresh_roadmap_seeds` builds one synthetic `RoadmapStage` (`_refresh_stage_for_artifact`) and drives it through `_run_stage` with a wrapped invoker (`_seed_only_invoker`) that appends the model's reply to the already-accepted `04-roadmap.md` text and reuses stage 4's multi-fence lift (`_lift_multi_fence_reply`) and gates (`run_plans_gates`). The model is asked, in one call, to emit a fenced seed block for *every* plan row (`roadmap-refresh-seeds.md`'s "Emit exactly one block for every `plans` row" instruction). If that one call's reply is unliftable, fails a gate, or the backend errors on every attempt, the whole call exhausts and nothing is written — even a plan whose seed the model would have produced perfectly. There is no way to say "9 of 10 plans refreshed cleanly; `plan-auth` needs another look."

Step 2's `materialize_plan_seed(slug, plan_id, ...)` is exactly the smaller primitive this needs: one call, one plan, its own retry budget, and a write that either lands completely (draft file plus its `seed-state.json` entry, plus a promoted-copy resync when the plan is already promoted) or changes nothing. Looping over `artifact.plans` and calling it once per row turns refresh from one big attempt into N independent attempts, and isolating each one's failure is what lets the run report which plans landed and which didn't instead of an all-or-nothing verdict.

This step is also the reason step 9 can later delete `_lift_multi_fence_reply`, `_plans_side_output_seed_paths`, and `STAGES[-1].side_output_seed_paths` without breaking `--refresh-seeds`: after this step, `refresh_roadmap_seeds` never calls `_run_stage` and never reads a stage's `side_output_seed_paths` field. Stage 4's own inline generation (the normal 4-stage `run_roadmap` arc) still uses that bundle plumbing until step 9 retires it — this step touches only the refresh path.

## Input

This step is built entirely on step 2's primitive, whose exact result field names are not pinned by this step (step 2 owns that decision):

- **`materialize_plan_seed(slug, plan_id, *, repo_root, plans_dir, invoker=shell_roadmap_invoker, max_attempts=MAX_STAGE_ATTEMPTS) -> RoadmapSeedMaterializeResult`** (step 2). On success it has already written the draft file at `resolve_draft_seed_path(plans_dir, slug, plan.draft_seed_path)` and, when the plan is already promoted, `repo_root / "plan-seeds" / f"{plan.id}.md"` too — both writes are done by the time the call returns. On an exhausted attempt it writes nothing and leaves whatever was there before untouched, and the result carries the last attempt's `failure_kind` (one of module-level `FAILURE_INVOKE` / `FAILURE_PARSE` / `FAILURE_GATES`), `failure_detail`, and `violations` (step 2's Implementation section names these three fields explicitly; the fields step 2 exposes on the *success* path are otherwise not pinned here).
- **What this step deliberately does not depend on**: the exact field(s) `RoadmapSeedMaterializeResult` uses to carry a successful attempt's written text. Rather than read that text off the result, this step re-reads the target files from disk after a successful call (see Implementation) — the files are already written by the time `materialize_plan_seed` returns, so re-reading them makes this step's diff/report logic correct regardless of exactly how step 2's result type exposes the written body. What this step *does* depend on, and must branch on, is whichever success/failure discriminator the landed `RoadmapSeedMaterializeResult` exposes (mirroring `_StageOutcome`'s own "a populated-on-success field is `None` on failure" convention, or an explicit outcome constant — check step 2's landed code for the actual shape when implementing this step).
- **Unknown plan id.** Step 2's primitive raises `RoadmapError` when `plan_id` doesn't match any row in the roadmap's current `04-roadmap.md`. This step's loop always passes `row.id` from the same `PlansArtifact` it iterates, so this raise path is not expected to fire from this step's own loop; if it ever did (e.g. a concurrent hand edit mid-run), it is a precondition failure, not a per-plan content failure, and should propagate out of `refresh_roadmap_seeds` rather than being caught and recorded as one plan's `failures` entry — see Implementation.

## Files (creates vs edits)

**Existing files (edits only):**

- `plan_tool/roadmap.py` — rewrite `refresh_roadmap_seeds`; delete `_refresh_stage_for_artifact`; add `SEED_REFRESH_OUTCOME_PARTIAL`, `RoadmapSeedRefreshFailure`, and the widened `RoadmapSeedRefreshResult`.
- `tests/test_roadmap.py` — rewrite the refresh test currently inside `TestSideOutputStages` into a dedicated `TestRefreshRoadmapSeeds` class; add the new per-plan-isolation coverage; update the shipped-prompt glob-exactness assertion.

**Deleted:**

- `plan_tool/prompts/roadmap-refresh-seeds.md` — nothing renders it once `refresh_roadmap_seeds` stops building a synthetic stage around it; keeping an unused prompt template on disk is stale documentation of a protocol this step retires, not a live contract (see Why).

**Necessary additions (not in the plan's declared `files:` list — see below):**

- `plan_tool/cli/roadmap_cmd.py` — the step's own intent text commits to "a third outcome... with its own exit code," and the exit-code mapping for `--refresh-seeds` lives only in `_cmd_roadmap_refresh_seeds`/`_render_seed_refresh_result` in this file. No later step in this plan's `files:` lists claims this edit: step 5 (`--materialize`) also touches `cli/roadmap_cmd.py` and `depends_on` this step to reuse its landed outcome vocabulary (`SEED_REFRESH_OUTCOME_PARTIAL`, `_RC_PARTIAL`, `_render_seed_refresh_result`) for a different plan-id subset, by requirement, not as an independent design choice — see step 5's `depends_on_notes` and Input section; step 9 touches `cli/roadmap_cmd.py` for unrelated reasons (routing `_create_handoff_lines` through step 3's classification, rewriting `_overwrite_summary_lines`). Without this edit, the new `SEED_REFRESH_OUTCOME_PARTIAL` value would fall through `_cmd_roadmap_refresh_seeds`'s existing binary `return 0 if ... APPLIED else _RC_INCOMPLETE` and collapse onto the same exit code as full exhaustion — the opposite of "its own exit code."
- `tests/cli/test_roadmap_cmd.py` — coverage for the new rc mapping and the new per-plan failure lines in `_render_seed_refresh_result`. Mirrors step 1's own precedent of adding this same test file to its declared list for an analogous reason.

## Implementation

### The rewritten `refresh_roadmap_seeds` loop

Load only the plans artifact up front — not all four stages the way today's implementation does:

```
loaded = _load_stage_artifact(STAGES[-1], plans_dir=plans_dir, slug=slug)
artifact = loaded.artifact
```

This step no longer needs domain/constraints/components loaded at this level: today's implementation loaded all four only to hand `upstream=loaded[:3]` into `_run_stage`'s own prompt rendering, and that rendering now happens once per plan, inside `materialize_plan_seed`, which re-reads all four stages itself (per step 2's Implementation — "every call is self-contained and re-reads its own ground truth"). The redundant re-read per plan is intentional (step 2's own design decision, not something to optimize away here) — refresh's own single upfront read exists only to get the list of plan ids to loop over. Keep the existing `isinstance(artifact, PlansArtifact)` defensive check and its `RoadmapError` message.

For each `row` in `artifact.plans`, in artifact order:

1. **Capture "before" state for both possible targets**, using the same pattern today's code already uses for `_seed_refresh_diff`'s `previous`/`before` inputs — `target if target.is_file() else _latest_seed_archive(target)` — applied to both `draft_path = resolve_draft_seed_path(plans_dir, slug, row.draft_seed_path)` and `promoted_path = repo_root / "plan-seeds" / f"{row.id}.md"` (the same inline construction today's code already uses for the promoted destination). This must happen *before* the call, since `materialize_plan_seed` may overwrite both files by the time it returns.
2. **Call `materialize_plan_seed(slug, row.id, repo_root=repo_root, plans_dir=plans_dir, invoker=invoker, max_attempts=max_stage_attempts)`.** `max_stage_attempts` is `refresh_roadmap_seeds`'s own existing parameter (unchanged name, for backward compatibility with existing callers) — thread it through as `materialize_plan_seed`'s `max_attempts` keyword. Each plan therefore gets its *own* full `max_stage_attempts`-sized budget: a full refresh over an N-plan roadmap can now issue up to N × `max_stage_attempts` calls where it issued at most `max_stage_attempts` before. This is the plan's own accepted Risk ("the direct cost of the resumability and backend-call independence this plan exists to buy") — do not add throttling or a shared budget here.
3. **On success**, re-read whichever of the two targets now exist on disk (always `draft_path`; `promoted_path` only when the plan was already promoted or is being resynced from an archive-only history — checking `target.exists()` *after* the call is sufficient and needs no separate "is this plan published" check, since `materialize_plan_seed` never creates a first promotion for an unpromoted plan). For each existing target, build a `RoadmapSeedRefreshChange` exactly the way today's code does — reuse `_seed_refresh_diff` unchanged and the same `unchanged`/`updated`/`recreated`/`created` action classification (`target == previous` from step 1 above means the file already existed; otherwise a non-`None` `previous` means it was recreated from an archive; otherwise it's newly created). Append each to a `changes` list.
4. **On failure** (however `RoadmapSeedMaterializeResult` signals it — see Input), append one `RoadmapSeedRefreshFailure(plan_id=row.id, failure_kind=result.failure_kind, failure_detail=result.failure_detail, violations=result.violations)` to a `failures` list. Neither target is read or reported for this plan — nothing changed.
5. **Continue to the next plan regardless of the outcome.** No early return, no aborting the loop on a failure — this is the whole point of the step.

Do not wrap the `materialize_plan_seed` call in a `try/except RoadmapError` inside the loop. A `RoadmapError`/`RoadmapArtifactError` raised from inside it (a broken upstream domain/constraints/components artifact, surfaced on the very first plan) is a precondition failure common to every plan in the batch, not something regenerating one plan differently could fix — let it propagate out of `refresh_roadmap_seeds` uncaught, exactly as it already does for the up-front `roadmap_dir`/`_load_stage_artifact` checks. `_cmd_roadmap_refresh_seeds` already catches `(RoadmapError, RoadmapArtifactError)` and maps it to `_RC_USAGE` — this step does not change that path.

### Determining the outcome

`changes` is non-empty exactly when at least one plan succeeded — a successful `materialize_plan_seed` call always writes `draft_path`, so `draft_path.exists()` is always true afterward and always produces at least one `RoadmapSeedRefreshChange`. Use that instead of tracking a separate succeeded-plan-id list:

- `failures` empty → `SEED_REFRESH_OUTCOME_APPLIED` (this also covers a zero-plan roadmap: no rows, no failures, trivially applied).
- `failures` non-empty and `changes` empty → `SEED_REFRESH_OUTCOME_EXHAUSTED` (every plan failed).
- `failures` non-empty and `changes` non-empty → `SEED_REFRESH_OUTCOME_PARTIAL` (the new outcome).

### The report

Write the report (`_render_seed_refresh_report`, still at `seed_refresh_report_path(roadmap_dir(plans_dir, slug))`, still via `atomic_write_text`) whenever `changes or failures` is non-empty — i.e. whenever there is something to say. Skip it only when both are empty (a zero-plan roadmap). This changes today's behavior of writing no report at all on exhaustion: a batch where every plan failed still has something worth persisting (which plans, which failure kind) now that there can be more than one. Extend `_render_seed_refresh_report`'s signature to accept the `failures` sequence and render one `##` section per failed plan beside the existing per-change sections — mirror the existing `## {change.plan_id} — {change.action}` heading shape with `## {failure.plan_id} — failed ({failure.failure_kind})`, followed by each violation's message and the `failure_detail` when present. Exact formatting is not load-bearing; the requirement is that a failed plan's id and cause are readable in the persisted file, not only in the returned dataclass.

### New types

```
SEED_REFRESH_OUTCOME_PARTIAL = "refresh-partial"

@dataclass(frozen=True)
class RoadmapSeedRefreshFailure:
    plan_id: str
    failure_kind: str
    failure_detail: str | None = None
    violations: tuple[Violation, ...] = ()

@dataclass(frozen=True)
class RoadmapSeedRefreshResult:
    outcome: str
    changes: tuple[RoadmapSeedRefreshChange, ...] = ()
    failures: tuple[RoadmapSeedRefreshFailure, ...] = ()
    report_path: Path | None = None
```

`RoadmapSeedRefreshResult`'s old scalar `failure_kind`/`failure_detail`/`violations` fields are dropped, not kept alongside `failures` — they described "the one combined call's failure," which has no meaning once a batch can have zero, one, or many per-plan failures. `rg -n "\.failure_kind\|\.failure_detail\|\.violations" tests/test_roadmap.py` shows every existing reference to those three names on a result object is against the unrelated `RoadmapResult` (the main 4-stage run's result, defined earlier in this module and untouched by this step) — only `plan_tool/cli/roadmap_cmd.py`'s `_render_seed_refresh_result` reads them off the seed-refresh result specifically, and this step rewrites that function anyway (below). This dataclass, and the module's other seed-refresh types, are not imported anywhere outside `roadmap.py` and `roadmap_cmd.py`, so the field removal has no other call site to sweep.

### Deleted

- **`_refresh_stage_for_artifact`** — the synthetic-stage constructor. Nothing else in the module or test suite calls it (its only caller was `refresh_roadmap_seeds`'s own body).
- **The local `_seed_only_invoker` closure** inside the old `refresh_roadmap_seeds` — goes with the function body it lived in.
- **`plan_tool/prompts/roadmap-refresh-seeds.md`** — see Files.

**Not deleted, and out of this step's footprint:** `_lift_multi_fence_reply`, `_is_seed_fence_label`, `_plans_side_output_seed_paths`, and `STAGES[-1].side_output_seed_paths` all stay exactly as they are. Stage 4's own inline generation inside the normal `run_roadmap` arc still uses every one of them until step 9 retires that path. Do not touch `STAGES`, `PLANS_GATES`, `_write_stage_outputs`, or `_lift_stage_reply` in this step.

### CLI: a distinct exit code for the partial outcome

In `plan_tool/cli/roadmap_cmd.py`:

- Import `SEED_REFRESH_OUTCOME_PARTIAL` alongside the existing `SEED_REFRESH_OUTCOME_APPLIED` import.
- Add `_RC_PARTIAL = 3` beside the existing `_RC_USAGE = 2` / `_RC_INCOMPLETE = 1` constants — a value distinct from both.
- `_cmd_roadmap_refresh_seeds`'s return: `0` on `APPLIED`, `_RC_PARTIAL` on `PARTIAL`, `_RC_INCOMPLETE` on `EXHAUSTED` (the existing fallback rc, now reached only by the genuinely-all-failed case).
- `_render_seed_refresh_result`: render the existing success block (unchanged) whenever `result.changes` is non-empty, and — separately, not `elif` — render one `error(...)` line per `result.failures` entry (plan id, failure kind, each violation message, the failure detail when present) whenever `result.failures` is non-empty. A `PARTIAL` result renders both blocks; `APPLIED` renders only the first; `EXHAUSTED` renders only the second. This replaces today's single if/else branch, which assumed exactly two mutually exclusive outcomes.
- `cmd_roadmap`'s own docstring is this file's authoritative rc/dispatch-mode contract (it already documents `--apply`/`--view` as modes) — add `_RC_PARTIAL` to its rc listing in the same edit that defines the constant, rather than leaving the docstring silent about a code the dispatcher can now actually return.

## Tests

### Tests for this step

All new/changed cases live in `tests/test_roadmap.py`'s new `TestRefreshRoadmapSeeds` class (moved out of `TestSideOutputStages`, which keeps only stage-4's own inline-bundle coverage) unless noted, reusing `_Env`/`env`, `_StubInvoker`, `_seed_text`, `_plans`/`_PLAN_ORDER`/`_PLAN_AUTH`, and `_seed_plans_upstream`:

- `test_refresh_calls_materialize_plan_seed_once_per_plan_on_a_clean_run` — a 2-plan roadmap (`_plans()`'s default `(_PLAN_ORDER, _PLAN_AUTH)`), an invoker whose first two replies are clean per-plan `_seed_text(...)` bodies: `invoker.calls == 2`, `result.outcome == SEED_REFRESH_OUTCOME_APPLIED`, `result.changes` has an entry for each plan's draft path.
- `test_refresh_recreates_an_archived_seed_and_writes_its_diff_report` — rewrite of today's test with the same archive-recreation setup (seed a draft, move it to `archive/order-core.replaced.md`, delete the live file), but the invoker now supplies one plain per-plan reply per call (no multi-fence wrapping, no custom `roadmap-refresh-seeds.md` override — that file no longer exists). Same assertions as today: `action == "recreated"`, the diff contains the new marker text, the report file contains it too, every sidecar entry ends `status == "current"`.
- `test_refresh_isolates_one_failing_plan_and_returns_partial` — 2 plans; the first plan's reply is clean, the second's is bad on every attempt (e.g. an unresolved `roadmap_components` reference). `result.outcome == SEED_REFRESH_OUTCOME_PARTIAL`; `result.changes` covers only the first plan's target(s); `result.failures == (RoadmapSeedRefreshFailure(plan_id=<second plan's id>, failure_kind=FAILURE_GATES, ...),)`; the second plan's draft path does not exist afterward (it never existed before this call either).
- `test_refresh_returns_exhausted_and_writes_a_failure_report_when_every_plan_fails` — both plans' every reply is bad: `result.outcome == SEED_REFRESH_OUTCOME_EXHAUSTED`, `result.changes == ()`, `result.report_path is not None` and the report on disk names both failed plans and their `failure_kind`, `len(result.failures) == 2`.
- `test_refresh_retries_a_failing_plan_up_to_max_stage_attempts` — a single-plan roadmap, every reply bad, `refresh_roadmap_seeds(..., max_stage_attempts=2)`: `invoker.calls == 2` (not 3), proving the parameter threads into `materialize_plan_seed`'s own `max_attempts` rather than being ignored.
- `test_refresh_report_names_the_failed_plan_in_a_mixed_batch` — same setup as the partial-outcome case; read `result.report_path.read_text(...)` and assert it names the failed plan's id and failure kind, not only the succeeded plan's diff.
- Update `test_both_stages_use_the_one_shared_revision_template`'s shipped-`roadmap-*.md` glob-exactness list: remove `"roadmap-refresh-seeds.md"`. If step 2's own edit has not already added `"roadmap-seed.md"` to this same sorted list, add it here too, so the assertion matches whatever `prompts_dir().glob("roadmap-*.md")` actually returns once this step lands.
- `TestRefreshRoadmapSeedsAgainstTheRealPrimitive::test_refresh_regenerates_two_plans_through_the_real_materialize_call_and_prompt` (`@pytest.mark.integration`, mirrors `TestFourStageArcAgainstTheRealGates`) — `shipped_env`, a real four-artifact roadmap on disk (`_seed_plans_upstream` plus a real stage-4 write), a `_StubInvoker` supplying two real conforming per-plan seed replies in `artifact.plans` order, calling `refresh_roadmap_seeds` with no `stages=` override. This is the first place step 2's `materialize_plan_seed` and this step's loop actually run together against the shipped `roadmap-seed.md` prompt — asserts `SEED_REFRESH_OUTCOME_APPLIED`, both draft files written, and a report on disk.

In `tests/cli/test_roadmap_cmd.py`:

- `test_cmd_refresh_seeds_partial_outcome_returns_a_distinct_rc` — stub `refresh_roadmap_seeds` to return `RoadmapSeedRefreshResult(outcome=SEED_REFRESH_OUTCOME_PARTIAL)`, mirroring `test_cmd_refresh_seeds_delegates_without_running_stages`'s existing monkeypatch shape; assert `cmd_roadmap(...) == 3` (matching this file's existing convention of asserting rc as a literal, not an imported constant).
- `test_cmd_refresh_seeds_exhausted_outcome_returns_rc_one` — same shape, `outcome=SEED_REFRESH_OUTCOME_EXHAUSTED`; assert `== 1`. Closes an existing gap: no test today exercises this outcome at the CLI layer.
- `test_cmd_refresh_seeds_reports_each_failed_plans_kind` — stub result carrying one `RoadmapSeedRefreshFailure`; using `capsys` (this file's established output-capture fixture), assert the failed plan's id and `failure_kind` appear in `capsys.readouterr().err`.

Every test above is green before this step is considered finished.

## Acceptance criteria

- `refresh_roadmap_seeds` calls `materialize_plan_seed` once per plan row in `artifact.plans` order and never calls `_run_stage`, builds a `RoadmapStage`, or reads a stage's `side_output_seed_paths` — checkable with `rg -n "_run_stage|RoadmapStage\(|side_output_seed_paths" plan_tool/roadmap.py` returning no hit inside `refresh_roadmap_seeds`'s body.
- A roadmap with several plans, one of which fails every attempt, refreshes every other plan successfully; the failing plan's prior draft (if any) is left byte-for-byte unchanged, and `result.outcome == SEED_REFRESH_OUTCOME_PARTIAL`.
- A roadmap where every plan fails every attempt returns `SEED_REFRESH_OUTCOME_EXHAUSTED`, writes no draft file, and still writes `seed-refresh-report.md`, naming each failed plan and its failure kind (mirrors step 5's `--materialize`, which writes the same on an all-failed batch).
- A roadmap where every plan succeeds returns `SEED_REFRESH_OUTCOME_APPLIED`, matching today's behavior for the all-success case.
- `plan_tool/prompts/roadmap-refresh-seeds.md` no longer exists on disk, and `prompts_dir().glob("roadmap-*.md")` matches the updated `test_both_stages_use_the_one_shared_revision_template` list.
- `plan-tool roadmap <slug> --refresh-seeds` exits `0` on full success, a value distinct from both `0` and `1` on a partial batch, and `1` on full exhaustion.
- `cmd_roadmap`'s docstring documents `_RC_PARTIAL` in its rc listing.
- `uv run pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py -q` is green.

## References

- `ROADMAP_FORMAT.md` — describes `--refresh-seeds`' existing contract (feedback-invalidates-without-overwriting, the before/after report, archive recreation) that this step preserves at the per-plan level; its "Feedback invalidation and explicit refresh" subsection still describes the retired combined-call/bundle mechanics after this step lands and is not edited here (see Deferred — step 9 owns that rewrite).

## Applicable guardrails

- **This step's own intent fence.** Retires `roadmap-refresh-seeds.md`'s multi-seed reply protocol and replaces it with step 2's per-plan prompt; must land before step 9 (which deletes the bundle plumbing `_refresh_stage_for_artifact` reads today) or `--refresh-seeds` breaks. Both are satisfied by design here: this step's rewrite is the thing that stops reading that plumbing.
- **Plan's Architecture — "one seed materialization job owns one draft path... without asking a backend to reconstruct siblings" and "no concurrency."** This step's loop calls `materialize_plan_seed` serially, one plan at a time, never in parallel — matching `CLAUDE.md`'s "Architecture" stance against in-process fan-out over shared mutable state (`seed-state.json` is one shared document each per-plan call reads and writes).
- **Plan's Out of scope — general background scheduling, parallelism policy, or backend liveness instrumentation; no correctness gate on seed style, length, or model agreement.** This step adds no `run_logger`, no concurrency, and no new content check — `materialize_plan_seed`'s own `validate_draft_seed_content` call (step 1) remains the only judgment of a reply's content.
- **Plan's Risks — the accepted N× call-count cost of per-plan independence.** Cited above in Implementation; this step does not add throttling, caching, or a shared cross-plan budget to offset it.

## Deferred

- **Step 5's `--materialize` outcome and CLI wiring.** Step 5 shares this step's per-plan failure-isolation *policy* for a different plan-id subset (only `missing`/`stale`/`malformed`/`path-escaping`/`digest-mismatched` drafts, per step 3's classification), and `depends_on` this step to reuse `SEED_REFRESH_OUTCOME_PARTIAL`, `RoadmapSeedRefreshFailure`, `RoadmapSeedRefreshChange`, `RoadmapSeedRefreshResult`, `_RC_PARTIAL`, and `_render_seed_refresh_result` verbatim, by requirement (the plan's own `depends_on_notes` for step 5 states this) — not as an independent design choice this step leaves open.
- **`ROADMAP_FORMAT.md`'s "Feedback invalidation and explicit refresh" subsection and `docs/ROADMAP_WALKTHROUGH.md`'s refresh call-count description**, both of which still describe the retired combined-call/bundle-gate mechanics once this step lands. Step 9 already claims the `ROADMAP_FORMAT.md` rewrite in its own intent; step 11 already claims the walkthrough's call-count accuracy. Neither is edited here.
- **Retiring stage 4's own inline bundle generation, `PLANS_GATES`' bundle-dependent checks, `_lift_multi_fence_reply`, or `STAGES[-1].side_output_seed_paths`.** Step 9, once this step has already stopped consuming them from the refresh path.
- **Deciding which plan ids need regenerating.** Step 3's classification and step 5's targeted `--materialize`; this step's `--refresh-seeds` keeps regenerating every plan unconditionally, including ones that already succeeded earlier in the same run.
- **Model-call observability for the per-plan `materialize_plan_seed` calls this loop now makes N of.** Out of scope for this plan (see the plan's own Deferred section); routed to the batch-authoring-observability plan lineage, not built here.
