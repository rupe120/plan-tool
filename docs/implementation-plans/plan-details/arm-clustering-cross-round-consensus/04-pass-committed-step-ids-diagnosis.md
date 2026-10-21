# Step 4 — Pass committed step ids to the diagnosis from the convergence and completeness surfaces

## Summary

This step turns the cross-round `arm-clustering` advisory on for real operators by threading a plan's actual committed step ids, per-step status, and audit grade into `diagnose_convergence` from the two places that call it: `cmd_convergence` in `plan_tool/cli/convergence_cmd.py` and the completeness stderr advisory tail (`_convergence_loop_advisory_lines` → `_emit_convergence_loop_advisories` → `finalize_completeness_run`) in `plan_tool/cli/completeness_cmd.py`. Step 3 already hoists a parsed `Plan` (or `None`, on a parse failure) into `cmd_convergence`; `finalize_completeness_run` already holds a guaranteed non-`None` `Plan` from its own `_resolve_plan_for_report` call. Step 4's only new work is building `declared_step_ids` / `step_statuses` from each of those already-in-scope `Plan` objects and passing them, plus `repo_root` and `detail_grade`, into `diagnose_convergence`'s four step-2 keyword parameters, which today default to no-ops everywhere. `detail_grade` needs no new plumbing to reach either call site — `cmd_convergence` already computes `args.grade` for `_current_audit_stage`, and `_emit_convergence_loop_advisories` already receives `detail_grade` for its own jira-grade early return — this step's only new work there is forwarding a value each site already has, one hop further than it goes today. The key design decision: each call site derives its own `declared_step_ids` / `step_statuses` locally with the same one-line idiom `plan_tool/review.py` and `plan_tool/completeness_report.py` already use for the same purpose, rather than adding a shared helper — the plan's declared `files:` list has no home for one, and a two-line derivation duplicated at two call sites matches an already-established repo pattern rather than inventing a new cross-module edge. On green, `plan-tool convergence <name>` and completeness-audit's stderr tail both actually render the cross-round `arm-clustering` line on a real plan once two qualifying same-stage rounds exist, closing the gap step 2 deliberately left open.

## Table of Contents

- [Summary](#summary) — what this step delivers and where the line is drawn
- [Why](#why) — the gap this step closes
- [Input](#input) — the contracts steps 2 and 3 already committed to, that this step must fit
- [Files (creates vs edits)](#files-creates-vs-edits) — what changes, file by file
- [Implementation](#implementation) — the two wiring sites and the shared design decision behind them
- [Tests](#tests) — test roster
- [Acceptance criteria](#acceptance-criteria)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

Step 2 added `declared_step_ids`, `step_statuses`, and `repo_root` as keyword-only parameters to `diagnose_convergence`, all defaulting to no-ops specifically so every existing caller kept compiling and behaving unchanged without passing them (step 2's own Summary: "wiring real committed-step data into those callers is step 4's job, not this one's"). Step 3 separately hoists `parse_plan(path)` out of `_current_audit_stage` and into `cmd_convergence`, so a parsed `Plan` (or `None`, on failure) is already sitting in a local variable there — step 3's own Deferred section names reading `plan.steps` to build these two arguments as explicitly step 4's job. Until this step lands, the cross-round advisory stays permanently `None` in production on both surfaces: `plan-tool convergence` prints nothing for it, and completeness-audit's stderr tail (`_convergence_loop_advisory_lines`) never sees a fired `arm-clustering` line, no matter how many qualifying `--audit-passes 1` rounds a plan accumulates. This step is the one that actually makes the plan's stated goal true for a real operator running these two commands.

## Input

- **`diagnose_convergence`'s new keyword-only contract** (`plan_tool/convergence_diagnosis.py`, landed by step 2) — `declared_step_ids: Sequence[int] = ()`, `step_statuses: Optional[Mapping[int, StepStatus]] = None`, `repo_root: Optional[Path] = None`, `detail_grade: str = GRADE_RUN`, alongside the existing `window` / `audit_stage` / `classify_domain`. All four new parameters default to no-ops; this step is the first caller to supply real values for them. Internally `diagnose_convergence` passes them straight to step 2's `classify_arm_clustering`, which itself short-circuits to `None` whenever `repo_root is None` and needs no separate guard for an empty `declared_step_ids` (step 1's currency check already drops every candidate against an empty sequence) — this step does not need to special-case an unresolved plan beyond passing through whatever it has. `detail_grade` is not optional in practice: leaving it at `GRADE_RUN` for a jira-graded plan fingerprints the wrong detail bundle (step 2's Architecture point 7/Input) — this step's whole job for that parameter is making sure real callers never fall back to the default.
- **`cmd_convergence`'s post-step-3 shape** (`plan_tool/cli/convergence_cmd.py`) — after step 3, `cmd_convergence` holds a local `plan: Plan | None` (parsed once, `None` on any failure) before it calls `_current_audit_stage(ctx, path, plan, detail_grade=args.grade)` and then branches on `audit_stage is None` to call `diagnose_convergence` one of two ways. Both branches call `diagnose_convergence` today; this step must add the four new keyword arguments to **both**, not just the `else` branch — the cross-round advisory does not depend on `audit_stage` being resolved (step 2 Implementation §3: "In practice `classify_arm_clustering` will itself return `None` on an empty `history.runs`... this is about field completeness and consistency with the sibling advisories"), so a plan whose audit stage can't be determined but whose body still parses should still get a real `declared_step_ids` / `step_statuses` / `detail_grade`. `args.grade` — the same value already passed to `_current_audit_stage` two lines above — is what supplies `detail_grade` here; no new value needs deriving.
- **The completeness-audit call chain** (`plan_tool/cli/completeness_cmd.py`) — `finalize_completeness_run(plan, path, ctx, args, ...)` already receives `plan` and `ctx` as parameters, and its first line (`plan = _resolve_plan_for_report(path, outcome, plan)`) guarantees a non-`None` `Plan` from that point on — unlike `cmd_convergence`, there is no unparseable-plan case to degrade here, because a completeness-audit run cannot reach `finalize_completeness_run` at all without a parseable plan. Near the end of that function it calls `_emit_convergence_loop_advisories(path, detail_grade=detail_grade, report_path=report_path, skip_sidecar_write=skip_sidecar_write, audit_stage=audit_stage)`, which in turn calls `_convergence_loop_advisory_lines(path, audit_stage=audit_stage)` — **not** forwarding the `detail_grade` it already received as its own parameter (used only for its own `if detail_grade == GRADE_JIRA: return []` early return, `completeness_cmd.py:1837`) — which loads history and calls `diagnose_convergence(history, audit_stage=audit_stage, classify_domain=lambda f: f.domain or "unknown")`. None of the three functions in this chain take `plan` or `repo_root` today, and `detail_grade` stops one hop short of `diagnose_convergence` even though it is already sitting in `_emit_convergence_loop_advisories`'s own scope.
- **The existing `declared_step_ids` idiom, used unchanged twice already** — `plan_tool/completeness_report.py` (`prepare_audit_shape_advisory_display`) and `plan_tool/review.py` (`audit_plan_until_stable`'s same-execution consensus path) both build `tuple(step.id for step in plan.steps if step.scope is StepScope.COMMITTED)` inline, rather than through the `Plan.committed_steps` property (`plan_tool/schema.py`), which returns the same steps as a `list["Step"]`. Either is a correct source for `declared_step_ids`; the inline `tuple(step.id for step in plan.steps if step.scope is StepScope.COMMITTED)` form matches the two existing sibling call sites exactly.
- **`Step.status` / `StepScope.COMMITTED`** (`plan_tool/schema.py`) — `StepStatus` is a `str, Enum` with `PENDING` / `CURRENT` / `DONE`; `StepScope.COMMITTED` is the default scope value gating whether a step counts toward the plan's critical path. `{s.id: s.status for s in plan.steps}` (over **all** steps, not filtered to committed) is a pattern this repo already uses for similar per-id lookups (`scope_by_id`, `titles_by_id`, `title_by_id` elsewhere in the codebase) — building it over every step, not just the committed subset, is what guarantees every id that survives `declared_step_ids`' committed-only filter also has a status entry, since both maps are derived from the same `plan.steps` list.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/cli/convergence_cmd.py`:
  - In `cmd_convergence`, after step 3's hoisted `plan` local is available, build `declared_step_ids` and `step_statuses` from it (empty/`{}` when `plan is None`) and pass them, plus `repo_root=ctx.repo_root` and `detail_grade=args.grade` (`args.grade` is already computed two lines above for `_current_audit_stage`), into both `diagnose_convergence` calls (the `audit_stage is None` branch and the `else` branch).
  - Add a top-level import for `StepScope` (and `StepStatus`, if used in a type hint) from `plan_tool.schema` — neither is imported in this module today.
  - Update `cmd_convergence`'s docstring, which currently describes only the `audit_stage` / `classify_domain` wiring, to also name the new committed-step-id, status, and grade threading.
- `plan_tool/cli/completeness_cmd.py`:
  - Add `plan`, `repo_root`, and `detail_grade` parameters to `_convergence_loop_advisory_lines`; add `plan` and `repo_root` to `_emit_convergence_loop_advisories` (it already has `detail_grade` as its own parameter — forward that existing value rather than adding a second one). Thread `plan=plan, repo_root=ctx.repo_root` from `finalize_completeness_run`'s existing locals at the one call site (`_emit_convergence_loop_advisories(...)`, near the end of `finalize_completeness_run`); `detail_grade` needs no new threading there since `finalize_completeness_run` already passes its own `detail_grade` to that call today.
  - Inside `_convergence_loop_advisory_lines`, derive `declared_step_ids` / `step_statuses` from the received `plan` (same idiom as above) and pass them, plus `repo_root` and `detail_grade`, into its own `diagnose_convergence` call.
  - Add the same `StepScope` (and `StepStatus`, if used in a hint) import from `plan_tool.schema` this module doesn't have today.
  - Update `_convergence_loop_advisory_lines`'s docstring ("Impact-recurrence and edit-drift lines for completeness stderr") to also name `arm-clustering`, since after this step it is a third advisory this function can surface.
- `tests/cli/test_convergence_cmd.py` — new coverage for the wiring (see Tests).
- `tests/cli/test_completeness_cmd.py` — new coverage inside the existing `TestCompletenessStderrConvergenceAdvisories` class (see Tests).

## Implementation

### 1. `cmd_convergence` (`plan_tool/cli/convergence_cmd.py`)

Build the two new arguments once, right after step 3's `plan` local is available and before the `audit_stage is None` branch, then pass them into **both** `diagnose_convergence` calls:

```python
declared_step_ids: tuple[int, ...] = ()
step_statuses: dict[int, StepStatus] = {}
if plan is not None:
    declared_step_ids = tuple(
        step.id for step in plan.steps if step.scope is StepScope.COMMITTED
    )
    step_statuses = {step.id: step.status for step in plan.steps}
```

`repo_root=ctx.repo_root` and `detail_grade=args.grade` can both be passed unconditionally in both branches — `ctx` is already loaded and always carries a `repo_root`, and `args.grade` is already resolved (and already used for `_current_audit_stage`) independent of whether the plan parsed. Only `declared_step_ids` / `step_statuses` are conditioned on `plan is not None`; when it's `None`, passing the empty defaults reproduces exactly the no-op behavior `diagnose_convergence` already has for callers that don't supply them, so an unparseable plan degrades to "no arm-clustering advisory" the same way it already degrades to "no stage-aware blocking" — no new failure mode, no new branch needed beyond the existing `audit_stage is None` split.

### 2. The completeness-audit chain (`plan_tool/cli/completeness_cmd.py`)

Thread `plan` and `repo_root` down two hops rather than pre-computing `declared_step_ids` / `step_statuses` at the top of `finalize_completeness_run` and passing the derived collections down — `_convergence_loop_advisory_lines` is the function that actually calls `diagnose_convergence`, and deriving the two collections right next to that call (mirroring `cmd_convergence`'s own shape) keeps the parameter surface of the two intermediate functions to one new value each instead of two, and keeps the derivation logic in one place per file rather than split across a builder and a consumer:

```python
def _convergence_loop_advisory_lines(
    path: Path,
    *,
    audit_stage: str,
    plan,
    repo_root: Path,
    detail_grade: str,
) -> list[str]:
    ...
    declared_step_ids = tuple(
        step.id for step in plan.steps if step.scope is StepScope.COMMITTED
    )
    step_statuses = {step.id: step.status for step in plan.steps}
    diagnosis = diagnose_convergence(
        history,
        audit_stage=audit_stage,
        classify_domain=lambda f: f.domain or "unknown",
        declared_step_ids=declared_step_ids,
        step_statuses=step_statuses,
        repo_root=repo_root,
        detail_grade=detail_grade,
    )
    ...
    if diagnosis.arm_clustering is not None:
        lines.extend(_arm_clustering_lines(diagnosis.arm_clustering))
```

At its one call site inside `_emit_convergence_loop_advisories` (`_convergence_loop_advisory_lines(path, audit_stage=audit_stage)`), add `plan=plan, repo_root=repo_root, detail_grade=detail_grade` — `detail_grade` is `_emit_convergence_loop_advisories`'s **own existing parameter** (already used for its `if detail_grade == GRADE_JIRA: return []` early return), forwarded one hop further, not a new value threaded from anywhere; only `plan` and `repo_root` are genuinely new parameters `_emit_convergence_loop_advisories` itself must gain, purely to pass them through. Its own early-return checks (`detail_grade == GRADE_JIRA`, `skip_sidecar_write or report_path is None`) are unaffected and still short-circuit before any of the three parameters is ever used. At the one call site inside `finalize_completeness_run`, add `plan=plan, repo_root=ctx.repo_root` to the existing `_emit_convergence_loop_advisories(...)` call — both are already local names in scope there; `detail_grade` is already passed at that call site today.

Because `_convergence_loop_advisory_lines` and `_emit_convergence_loop_advisories` are both module-private with exactly one production call site each (grep confirms no other caller in `plan_tool/` or `tests/`), making `plan` and `repo_root` required keyword-only parameters (no defaults) is a reasonable choice here — it means a future edit that forgets to thread them fails at call time instead of silently reintroducing the "advisory always `None`" state this step exists to fix. Giving them the same `plan=None` / `repo_root=None` no-op defaults `diagnose_convergence` itself uses is also defensible for signature symmetry; either is acceptable, but whichever is chosen, the one real call site in `finalize_completeness_run` must always pass the real values — never rely on a default there.

### What does not change

- `classify_arm_clustering_consensus` (step 1) and `classify_arm_clustering` / the `ArmClusteringAdvisory` render (step 2) are consumed exactly as they already exist — this step supplies their two inputs from a real `Plan`, nothing about their matching, materiality, or currency logic changes.
- `_current_audit_stage`'s signature and behavior (step 3) are untouched; this step only reads the `plan` local that step 3 already exposes in `cmd_convergence`.
- No other caller of `diagnose_convergence` gains these arguments — the plan's declared `files:` list for this step is exactly `plan_tool/cli/convergence_cmd.py` and `plan_tool/cli/completeness_cmd.py`; any other caller (this module's own test suite calling `diagnose_convergence` directly, if any exist) is out of this step's footprint.

## Tests

### Tests for this step

`tests/cli/test_convergence_cmd.py`:

- `test_convergence_passes_declared_step_ids_and_statuses_to_diagnose_convergence` — monkeypatches `diagnose_convergence` (module-global spy, matching this file's existing `monkeypatch.setattr(convergence_cmd, "compute_plan_fingerprint", _boom)` pattern) against a plan with a mix of committed and deferred/wont_do steps and at least one `status: done` step; asserts the captured `declared_step_ids` kwarg contains exactly the committed step ids (excluding the parked one) and the captured `step_statuses` kwarg maps every step id — including the parked one and the `done` one — to its real `StepStatus`, proving the map is built over all steps, not just committed ones.
- `test_convergence_passes_repo_root_to_diagnose_convergence` — same spy approach; asserts `repo_root` is passed as `ctx.repo_root`, in both the `audit_stage is None` branch and the resolved-stage branch (two sub-cases or two assertions).
- `test_convergence_passes_grade_to_diagnose_convergence` — same spy approach, run once with `--grade run` and once with `--grade jira`; asserts the captured `detail_grade` kwarg equals `args.grade` in both cases, in both branches — proving the fingerprint capture (step 2) never silently falls back to `GRADE_RUN` for a jira-graded plan.
- `test_convergence_degrades_to_empty_step_data_on_unparseable_plan` — writes an invalid plan body (mirroring `test_current_audit_stage_falls_back_to_none_on_unparseable_plan`'s fixture), drives `convergence` through `main(...)`, and asserts `rc == 0` with no exception — spying on `diagnose_convergence` to confirm `declared_step_ids == ()` and `step_statuses == {}` were passed rather than the call being skipped or raising.
- New fixture helper: a plan-writer producing at least 3 committed steps (the `registered_plan` fixture's default `1-demo` plan has exactly one step, which can never support arm-clustering's strict-majority-of-committed-steps requirement) — write the plan body directly via `(registered_plan.plans_dir / "1-demo.md").write_text(...)`, matching how `test_current_audit_stage_detail_at_jira_grade_when_run_grade_is_bare` already overwrites the fixture plan in place.
- New fixture helper: a `Recommendation` builder that sets `audit_step_target` (step 1's new field) rather than relying on `step_id` (always `None` for these sources) or `anchor` alone, since that's the field step 1's classifier actually reads for cross-round target agreement.
- `test_convergence_prints_arm_clustering_advisory_from_real_history` — using the two helpers above, seeds two qualifying same-`audit_stage` (`"bare"`) completeness rounds whose material findings agree on `audit_step_target` values forming a strict-majority arm over the 3-committed-step plan (matching step 2's own `test_arm_clustering_fires_with_real_evidence_and_fingerprint` fixture shape, but driven through `main(["convergence", ...])` rather than calling `classify_arm_clustering` directly); asserts the printed output names the arm's step ids and a round-count/stage phrase (step 2's stated wording pattern, e.g. containing both the round count and `"bare"` — assert on presence of the count and stage, not on step 2's exact sentence).
- `test_convergence_arm_clustering_silent_with_insufficient_history` — one qualifying round only (or a single-committed-step plan) still exits 0 and prints no arm-clustering line, proving the wiring alone doesn't fabricate a false positive.

`tests/cli/test_completeness_cmd.py` (extending `TestCompletenessStderrConvergenceAdvisories`):

- `test_completeness_stderr_passes_real_step_data_to_diagnose_convergence` — spies on `plan_tool.convergence_diagnosis.diagnose_convergence` (imported lazily inside `_convergence_loop_advisory_lines`, so patch it at that module) during a `completeness-audit` run against `_prepare_clean_demo_plan`'s single-step fixture; asserts the captured `declared_step_ids` / `step_statuses` / `repo_root` / `detail_grade` reflect the real demo plan and the run's actual grade rather than the no-op defaults, without requiring the advisory to actually fire (single-step plan can't support an arm).
- New fixture: a `steps:` block with 3 committed steps (mirroring `_INTENT_BEARING_STEPS`'s shape — each step needs an `intent:` to stay clean against the intent-presence detector) fed through the existing `_sectioned_plan_text` helper, since `_INTENT_BEARING_STEPS`'s single step can never support an arm.
- `test_completeness_stderr_prints_arm_clustering_when_history_fires` — using the new steps block and `_save_advisory_sidecar` with `Recommendation`s carrying `audit_step_target` (not just `anchor`/`title`), seeds two qualifying rounds forming a majority arm, runs `completeness-audit`, and asserts the arm-clustering line appears in stderr alongside (or independent of) the existing impact-recurrence / edit-drift assertions in this class.
- Extend `test_completeness_stderr_skips_advisories_on_jira_grade` with an additional assertion that the arm-clustering text is also absent — this is a one-line addition to an existing test (per this class's existing convention of extending, not duplicating, the "skips on jira grade" case for each advisory), not a new test.

Every test above must be green before this step is considered finished.

## Acceptance criteria

- `cmd_convergence` calls `diagnose_convergence` with real `declared_step_ids` (the parsed plan's committed step ids) and real `step_statuses` (every step's current `StepStatus`, keyed by id) whenever the plan parses, in both its `audit_stage is None` and resolved-stage branches — and with the empty no-op defaults, never an exception, when the plan doesn't parse.
- `cmd_convergence` always passes `repo_root=ctx.repo_root` and `detail_grade=args.grade` to `diagnose_convergence`, independent of whether the plan parsed.
- `finalize_completeness_run`'s convergence-advisory tail (`_emit_convergence_loop_advisories` / `_convergence_loop_advisory_lines`) calls `diagnose_convergence` with the same real `declared_step_ids` / `step_statuses` / `repo_root` / `detail_grade`, derived from the `Plan` `finalize_completeness_run` already holds and the `detail_grade` it already received.
- A plan whose saved completeness history was audited at jira grade gets a jira-grade `AuditInputSnapshot` fingerprint (step 2) via `plan-tool convergence --grade jira`, not a silent run-grade default.
- A real plan with ≥3 committed steps and two qualifying same-stage saved completeness rounds whose findings agree on a majority-arm `audit_step_target` produces a visible `arm-clustering` line from both `plan-tool convergence <name>` and completeness-audit's stderr tail.
- An unparseable plan file still makes `plan-tool convergence` exit `0` and print no arm-clustering line — no new exception path is introduced by this step.
- `cmd_convergence`'s always-exits-0 contract (step 3) and `_emit_convergence_loop_advisories`'s jira-grade / no-sidecar early returns are both unaffected by the new parameters.
- No new blocking gate, exit-code flip, or apply-dispatch reads the now-firing advisory any differently than before — it still feeds only printed text on both surfaces.
- `plan_tool/audit_shapes.py`, `plan_tool/convergence_diagnosis.py`, and `plan_tool/review.py` are unmodified by this step's diff — every change lands in `plan_tool/cli/convergence_cmd.py` and `plan_tool/cli/completeness_cmd.py` (plus their tests).

## Applicable guardrails

The plan's `## Out of scope` section binds this step on several points:

- No change to `evaluate_arm_clustering`'s signature or arm math, and no change to the same-execution (`--audit-passes N > 1`) consensus path in `plan_tool/review.py` — this step's declared files don't include either module, and nothing in this step's wiring touches them.
- No new blocking gate, exit-code flip, or apply-dispatch keyed on the advisory — turning the advisory on for real data must not change `cmd_convergence`'s or completeness-audit's return codes; it stays print-only exactly as `impact_recurrence` / `edit_drift` already are.
- No reviving the retired `spinning` / `FORK_*` region-trending diagnostic's vocabulary — nothing introduced by this step's plumbing resembles it.
- Cross-round materiality and currency logic (`is_blocking_finding`, the target-agreement and `declared_step_ids`/`status` checks) stay exactly as steps 1 and 2 built them — this step supplies their inputs, never re-derives or adjusts their rules.
- Rendering stays silent when nothing fires (plan Architecture point 8) — this step must not add any "insufficient evidence" text; a plan with too little history, no majority arm, or an unparseable plan must simply print nothing extra, matching the sibling advisories' existing silent-`None` behavior.

## Deferred

- Any change to `classify_arm_clustering_consensus` (step 1), `classify_arm_clustering` / `ArmClusteringAdvisory` / `_arm_clustering_lines` (step 2), or `evaluate_arm_clustering`'s own math (`plan_tool/audit_shapes.py`) — all landed and consumed unchanged by this step.
- Any change to `_current_audit_stage`'s bare/detail stage derivation or signature — step 3's concern; this step only reads the `plan` local step 3 already exposes.
- Updating CLAUDE.md, `docs/ARCHITECTURE.md`, `docs/how-to/pipeline/audit.md`, and closing out `BACKLOG.md` #264 — step 5, once this step's real wiring has actually landed.
- Threading `declared_step_ids` / `step_statuses` / `repo_root` into any caller of `diagnose_convergence` beyond `cmd_convergence` and the completeness-audit stderr tail — the plan's declared `files:` list scopes this step to exactly those two call sites.
- Consolidating the `declared_step_ids` derivation into a shared helper module — this step deliberately duplicates the existing two-line idiom at both call sites (matching the precedent already set by `plan_tool/completeness_report.py` and `plan_tool/review.py`) rather than introducing a new shared leaf; a genuine three-or-more-site consolidation, if it becomes warranted later, is a separate refactor.
