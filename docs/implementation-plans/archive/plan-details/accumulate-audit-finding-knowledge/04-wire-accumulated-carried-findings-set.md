> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Wire the accumulated `carried_findings` set from the convergence loop into both `apply_finding` call sites

## Summary

Feed the `CarriedFinding` set the iterate loop accumulates (step 1's record) into every `apply_finding` call the completeness surface drives, so each apply pass sees what the loop already surfaced and how earlier applies resolved. Touches two files: `plan_tool/cli/completeness_cmd.py` builds and threads the set at both its apply sites — the direct call in `_run_iterate_convergence_loop` (built live from the loop's own apply verdicts) and the `_build_review_action_fn` call in `cmd_completeness_apply` (seeded from the saved review's findings + annotations, then updated as the replay walk lands fresh apply verdicts) — and `plan_tool/cli/review_actions.py` gains a `carried_findings` kwarg on `_build_review_action_fn` that `_dispatch_apply_finding` forwards to `apply_finding`. The key design call: this step is the **populator** of `CARRIED_RESOLUTION_BLOCKED` — step 1 reserved that value for "the live apply path wired in step 4," and the live apply paths derive it from the `BLOCKED` / `BLOCKED-STRUCTURAL` verdict `parse_apply_verdict` returns. On green: each apply call in a multi-round completeness loop and saved-audit replay walk receives a non-empty `carried_findings` reflecting earlier applied/blocked/skipped findings in the same invocation, and every existing `_build_review_action_fn` caller outside completeness keeps the empty default unchanged.

## Table of Contents

- [Why](#why) — what the apply pass still can't see after step 3
- [Files (creates vs edits)](#files-creates-vs-edits) — two source edits plus their test files
- [Implementation](#implementation) — the kwarg thread, the live resolution map, the saved-annotation build
- [Tests](#tests) — verdict-mapping unit tests + forwarding/assembly tests
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — sorting + dataclass docs
- [Deferred](#deferred) — the create / reconcile apply sites left on the default

## Why

Step 3 gave `plan_tool/launcher.py:apply_finding` an advisory `carried_findings` kwarg and a renderer, but every caller still passes the empty default — so the kwarg is dead until a caller supplies a real set. The completeness convergence loop in `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop` is exactly where the accumulated knowledge lives: it audits the plan's concepts once, then applies open findings round after round, tracking which ids it already dispatched in `applied_fingerprints` and the per-finding `apply_result.verdict`. `applied_fingerprints` already stops the *same* finding from being re-dispatched in a later round (a dispatched id is added regardless of verdict and `open_findings` filters it out), so the unmet need is the **cross-finding** case: none of that verdict history reaches the apply prompt, so applying a *new* finding whose remedy resembles one a sibling already established won't land re-proposes the same dead end. This step is the consumer that closes that gap: assemble step 1's `CarriedFinding` set from the loop's live verdict history and hand it to each `apply_finding` call, and do the same for the saved-audit replay in `cmd_completeness_apply` by seeding from persisted annotations via step 1's `carried_resolution_from_annotations` adapter, then accumulating this replay walk's fresh apply verdicts before later findings run. It also makes `CARRIED_RESOLUTION_BLOCKED` real for the first time — the only resolution step 1 could not derive from a saved annotation.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/review_actions.py` — add a `carried_findings: Sequence[CarriedFinding] | Callable[[], Sequence[CarriedFinding]] = ()` kwarg to `_build_review_action_fn`; resolve it immediately before the `apply_finding(...)` call inside `_dispatch_apply_finding` so dynamic replay providers can reflect earlier findings in the same walk; forward it into the two recursive `_build_review_action_fn` sub-builder calls (both detail-reconcile subwalks inside `_dispatch_detail_reconcile` — the reuse path and the fresh-run path) so nested applies inherit the same context provider; add a `TYPE_CHECKING` import of `Callable`, `Sequence`, and `CarriedFinding`.
  - `plan_tool/cli/completeness_cmd.py` — add a small pure `_resolution_for_verdict` helper mapping an apply verdict to a `(resolution, reason)` tuple; in `_run_iterate_convergence_loop` maintain a per-run `_carried_resolution` map and pass `carried_findings=assemble_carried_findings(...)` to the direct `apply_finding` call; in `cmd_completeness_apply` seed a replay `_carried_resolution` map from the full saved review + its annotations, pass a provider that rebuilds the carried set to `_build_review_action_fn`, and update that map from this replay walk's fresh apply verdicts.
  - `tests/cli/test_review_actions.py` — forwarding + default-empty + subwalk-inherits tests.
  - `tests/cli/test_completeness_cmd.py` — `_resolution_for_verdict` unit tests + loop/replay forwarding integration tests.

## Implementation

### `plan_tool/cli/review_actions.py`

- **Add the kwarg to `_build_review_action_fn`.** Insert `carried_findings: Sequence[CarriedFinding] | Callable[[], Sequence[CarriedFinding]] = ()` into the keyword-only signature, beside the existing `reconcile_scope_guard` parameter. Default `()` keeps every current caller — the three `reconcile.py` call sites and the three `review_cmd.py` call sites — unchanged. (Completeness's only `_build_review_action_fn` caller is `cmd_completeness_apply`, which this step itself modifies, so it is not an unchanged caller; `_run_iterate_convergence_loop` calls `apply_finding` directly and its files-coherence path is deterministic, never building an action fn.)
- **Type the annotation without a runtime import.** The module already runs under `from __future__ import annotations`, so annotations are lazy strings — mirror the existing `reconcile_scope_guard: Optional["ReconcileScopeGuard"]` quoted-forward-ref pattern. Add a `TYPE_CHECKING` block importing `Callable` and `Sequence` from `typing` and `CarriedFinding` from `plan_tool.review`. Do **not** add a module-top `from plan_tool.review import CarriedFinding` — `review_actions.py` keeps no module-top `import review` (its review names resolve through the builder's body-local `from plan_tool.review import (...)`), and a top import would add weight this leaf deliberately avoids.
- **Forward into the apply call.** In `_dispatch_apply_finding`, resolve the kwarg just before applying — `_carried = carried_findings() if callable(carried_findings) else carried_findings` — and add `carried_findings=_carried,` to the `apply_finding(plan_path, ...)` call (the one passing `finding_body=rec.body` and `operator_feedback=...`). The closure already closes over the builder's parameters, so both the static sequence and dynamic provider forms are in scope with no extra plumbing.
- **Forward into the recursive sub-builders.** Both `sub_action_fn = _build_review_action_fn(...)` calls (both detail-reconcile subwalks dispatched from `_dispatch_detail_reconcile` — the reuse path and the fresh-run path) gain `carried_findings=carried_findings,` so a nested subwalk's applies see the same run-level context or provider as the parent walk.

### `plan_tool/cli/completeness_cmd.py`

- **Add a pure verdict→resolution helper.** Add `_resolution_for_verdict(verdict: str) -> tuple[str, str]` near the other small module-private helpers (`_fmt_finding_counts`, `_finding_progress_label`). It maps the vocabulary `plan_tool/launcher.py:parse_apply_verdict` returns:
  - `"APPLIED"` → `(CARRIED_RESOLUTION_APPLIED, "")`
  - `"BLOCKED"` or `"BLOCKED-STRUCTURAL"` → `(CARRIED_RESOLUTION_BLOCKED, verdict)` — this is the step that makes `blocked` reachable; the reason carries the exact verdict so `BLOCKED-STRUCTURAL` is distinguishable downstream.
  - `"NOT-APPLICABLE"` → `(CARRIED_RESOLUTION_SKIPPED, verdict)` — the apply ran and deliberately found no applicable edit.
  - `"UNKNOWN"` (and any other unrecognized verdict) → `(CARRIED_RESOLUTION_OPEN, verdict)` — the apply result is untrusted, so no choice was made and later apply passes must not read it as a deliberate skip.
  - Import `CARRIED_RESOLUTION_APPLIED`, `CARRIED_RESOLUTION_BLOCKED`, `CARRIED_RESOLUTION_OPEN`, and `CARRIED_RESOLUTION_SKIPPED` from `plan_tool.review` (the existing module-top `from plan_tool.review import (...)` block).
- **Maintain a live resolution map in `_run_iterate_convergence_loop`.** Inside the `if budget.enabled:` body, beside `applied_fingerprints: set[str] = set()`, add `_carried_resolution: dict[str, tuple[str, str]] = {}`. Also add the body-local import `from plan_tool.review import assemble_carried_findings` alongside the existing body-local `audit_plan_until_stable` import (keep it body-local so the domain suites' monkeypatch seams keep intercepting through `main()`).
- **Assemble and pass `carried_findings` at the direct apply call.** Immediately before the `apply_result = apply_finding(path, ...)` call in the per-finding dispatch loop, build the set from everything surfaced this run plus the resolutions known so far:
  - Dedupe the union by id at the call site first — `assemble_carried_findings` emits one `CarriedFinding` **per input rec** with no dedup (step 1), and `current_findings` (`_open_findings_now`) overlaps `_audit_recs` for every unapplied plan-correctness id, so `[*_audit_recs, *current_findings]` would otherwise duplicate those entries. Collapse to one rec per id: `_union = {r.id: r for r in [*_audit_recs, *current_findings]}` (a later duplicate overwrites the same key, leaving exactly one rec per id), then `carried = assemble_carried_findings(list(_union.values()), resolution_by_id=_carried_resolution)`; ids absent from `_carried_resolution` render as `CARRIED_RESOLUTION_OPEN`.
  - Add `carried_findings=carried,` to the `apply_finding(...)` keyword arguments (beside `targeted_fix=...`, `run_logger=run_logger`).
  - The finding currently being applied appears in the set with resolution `open` until its verdict lands; that is acceptable — step 3's renderer frames the block as "already surfaced this run," and the finding being applied is shown separately by the existing prompt body.
- **Record the verdict after each apply.** After `apply_result = apply_finding(...)` returns (and after the existing `applied_fingerprints.add(rec.id)` / verdict-print logic), set `_carried_resolution[rec.id] = _resolution_for_verdict(apply_result.verdict)`. Also fold deferred findings in: where the loop already does `_deferred_recs.setdefault(_r.id, _r)` for `open_deferred`, add `_carried_resolution.setdefault(_r.id, (CARRIED_RESOLUTION_SKIPPED, "deferred"))` so a finding triaged-away (never dispatched) reads as skipped, not open.
- **Build and update the saved-audit carried set in `cmd_completeness_apply`.** This verb starts from a persisted audit, then accumulates its own fresh apply verdicts as the replay walk runs:
  - Capture the full finding set **before** the in-memory narrowing: after the `saved.kind != "completeness"` guard and before the `saved.recommendations = completeness_recs` reassignment, add `_all_saved_recs = list(saved.recommendations)`. Building from the full set (not the `--anchor`-narrowed `completeness_recs`) keeps the carried context complete even when the operator walks a single gap.
  - Seed `_carried_resolution = carried_resolution_from_annotations(saved.annotations)`, importing `carried_resolution_from_annotations` from `plan_tool.review_persistence`; this seed never emits `blocked` because saved annotations only carry `applied` / `skip` / `open`.
  - Add a local `_build_carried()` provider that returns `assemble_carried_findings(_all_saved_recs, resolution_by_id=_carried_resolution)`, importing `assemble_carried_findings` from `plan_tool.review`. Pass `carried_findings=_build_carried,` to the `_build_review_action_fn(ctx=..., plan_path=..., ...)` call that builds `action_fn` for the walk, so each replay apply sees verdicts recorded by earlier applies in the same invocation.
  - Extend the action-result handling for this replay walk so after each apply returns, `_carried_resolution[rec.id] = _resolution_for_verdict(apply_result.verdict)` for the recommendation just walked. A fresh `BLOCKED` or `BLOCKED-STRUCTURAL` verdict therefore appears as `blocked` for later replay findings, while ids not yet touched keep their saved-annotation resolution or `open` default.

### Foundational logic and other apply sites

- **Foundational logic:** "supply a real `carried_findings` set to `apply_finding`, derived from the run's accumulated resolution history." The same shape exists at two other apply sites left out of this step's set of files:
  - `plan_tool/create.py` — the create convergence loop's `apply_finding(...)` call keeps the `()` default; wiring create's loop is a separate change (create's convergence loop does not yet route through this knowledge). See [Deferred](#deferred).
  - `plan_tool/cli/reconcile.py:_iterate_reconcile_loop` — its `_build_review_action_fn(...)` call now accepts the kwarg but passes nothing, keeping the `()` default. Threading the reconcile loop's own accumulated set is out of scope here. See [Deferred](#deferred).

## Tests

### Test-creation order (feature step)

Write each test alongside the edit it covers; every test below must be green before this step is done.

**`tests/cli/test_completeness_cmd.py`** (pure helper — no Claude, no I/O):

- `test_resolution_for_verdict_maps_applied` — `_resolution_for_verdict("APPLIED")` returns `(CARRIED_RESOLUTION_APPLIED, "")`.
- `test_resolution_for_verdict_maps_blocked` — `"BLOCKED"` and `"BLOCKED-STRUCTURAL"` each return `CARRIED_RESOLUTION_BLOCKED` with the verdict as the reason (this is the only path that produces `blocked`).
- `test_resolution_for_verdict_maps_skipped` — `"NOT-APPLICABLE"` returns `CARRIED_RESOLUTION_SKIPPED` with the verdict as reason.
- `test_resolution_for_verdict_maps_unknown_open` — `"UNKNOWN"` returns `CARRIED_RESOLUTION_OPEN` with the verdict as reason so an untrusted apply result stays retry-neutral.

**`tests/cli/test_completeness_cmd.py`** (integration — drive `main()`; mark the class `@pytest.mark.integration`, stub the audit at `plan_tool.review.audit_plan_until_stable` / the launcher seam so no real Claude fires):

- `test_iterate_loop_forwards_accumulated_carried_findings` — drive `main(["completeness-audit", name, "--iterate", ...])` with a stub `apply_finding` capturing each call's `carried_findings`; assert a later round's call carries the earlier round's finding marked `applied` (and a `BLOCKED`-verdict finding marked `blocked`).
- `test_completeness_apply_builds_carried_from_full_saved_set` — drive `cmd_completeness_apply` against a saved review holding both completeness gaps and a non-completeness finding with an `applied`/`skip` annotation, narrowed by `--anchor`; assert the captured `carried_findings` covers the **full** saved set with resolutions from the annotations, not just the walked gap.
- `test_completeness_apply_accumulates_replay_verdicts` — drive `cmd_completeness_apply` across multiple walked recommendations with a stub apply returning `BLOCKED` or `APPLIED` for the first one; assert a later replay apply receives a rebuilt `carried_findings` set that includes the earlier replay verdict, not only the saved annotations.
- `test_carried_findings_do_not_touch_scope_guard_surface` — the caller-level scope-guard invariant step 3 deferred here (03-optional-advisory-carried-findings.md Deferred). Assert the structural boundary instead of re-calling the same guard path: `compute_in_scope_paths(plan, path, ctx.repo_root)` has no `carried_findings` parameter, the loop computes it once at loop entry before the round loop, and `carried_findings` is passed only to `apply_finding` as advisory prompt context, never into the tracked/scope-guard inputs.

**`tests/cli/test_review_actions.py`** (mirror `TestOperatorFeedbackSteersApply`: monkeypatch `plan_tool.launcher.apply_finding` to capture kwargs, build via `_build_review_action_fn`, drive one rec):

- `test_builder_forwards_carried_findings_to_apply_finding` — a builder given `carried_findings=[<one CarriedFinding>]` forwards that exact value to `apply_finding`.
- `test_builder_resolves_carried_findings_provider_per_apply` — a builder given a zero-arg carried-findings provider calls it immediately before each apply so mutable replay state is reflected in later dispatches.
- `test_builder_defaults_carried_findings_to_empty` — a builder created without the kwarg forwards `carried_findings=()` (pins the unchanged default for reconcile / review callers).
- `test_detail_reconcile_subwalk_inherits_carried_findings` — the recursive `sub_action_fn` built inside `_dispatch_detail_reconcile` receives the same `carried_findings` the parent builder held.

## Acceptance criteria

- `_resolution_for_verdict("APPLIED")`, `("BLOCKED")`, `("BLOCKED-STRUCTURAL")`, `("NOT-APPLICABLE")`, and `("UNKNOWN")` each return the documented `(resolution, reason)` tuple, with `UNKNOWN` staying `open` rather than `skipped`.
- `_build_review_action_fn` accepts a `carried_findings` keyword defaulting to `()`, and `_dispatch_apply_finding` forwards a static sequence verbatim or resolves a zero-arg provider immediately before calling `apply_finding`.
- A builder created without `carried_findings` forwards the empty tuple — every non-completeness caller is unaffected.
- In a multi-round completeness `--iterate` run, a later round's `apply_finding` call receives a non-empty `carried_findings` whose entry for an already-applied id carries `CARRIED_RESOLUTION_APPLIED`, and a `BLOCKED`-verdict id carries `CARRIED_RESOLUTION_BLOCKED`.
- `cmd_completeness_apply` seeds `carried_findings` from the full saved finding set + saved annotations (resolutions via `carried_resolution_from_annotations`), unaffected by `--anchor` narrowing, and accumulates this replay walk's fresh apply verdicts into the carried set before later findings run.
- The scope guard is structurally independent of `carried_findings`: `compute_in_scope_paths` takes no `carried_findings` input, the loop computes it once before per-finding apply dispatch, and the advisory context never enters the tracked/scope-guard surface.
- All tests above pass; the full suite stays green (`uv run pytest tests/cli/test_completeness_cmd.py tests/cli/test_review_actions.py -q`).

## References

- [Sorting Techniques — Python 3 documentation](https://docs.python.org/3/howto/sorting.html) — confirms `assemble_carried_findings`' `(severity, anchor)` ordering is stable, so the carried set handed to each apply is deterministic across rounds.
- [dataclasses — Data Classes — Python 3 documentation](https://docs.python.org/3/library/dataclasses.html) — reference for the frozen `CarriedFinding` record this step assembles and forwards.

## Deferred

- **Wiring `plan_tool/create.py`'s convergence loop apply site** — create's loop still passes the `()` default; threading its own accumulated set is a separate change, not this step's set of files.
- **Wiring `plan_tool/cli/reconcile.py:_iterate_reconcile_loop`'s carried set** — the reconcile loop's `_build_review_action_fn` call now accepts the kwarg but supplies nothing; building and passing the reconcile loop's verdict history is left for a follow-up so this step stays inside its two declared source files.
- **Consolidating verdict→resolution mapping** — `_resolution_for_verdict` is local to `completeness_cmd.py`; if create / reconcile later need the same mapping, fold the three into one shared helper via reconcile rather than duplicating, per the repo's local-now / consolidate-via-reconcile convention.
- **No DATA_CONTRACT change** — `CarriedFinding` is an in-memory, within-run record assembled at the apply call and never serialized (step 1), so `DATA_CONTRACT.md` and `tests/test_data_contract.py` are untouched.
