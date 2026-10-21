> **Auto-archived**: this plan was swept on 2026-07-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add the size-gate helper that flags an over-large create result

## Summary

This step creates the new thin CLI leaf `plan_tool/cli/direct_cmd.py` and lands its first piece: a deterministic **size-gate helper** that inspects a `CreateResult` and returns a pass-or-stop verdict on whether the created plan is small enough to chain safely into the downstream stages. The one design decision that matters is that the gate measures the finished plan's **step count** (via `plan_tool/parser.py:parse_plan` on `CreateResult.plan_path`) against a single fixed module constant, spends **no Claude**, and takes no invoker seam. The helper also handles the one edge case where there is no plan to size — the multi-plan split short-circuit where `CreateResult.plan_path` is `None`. On green, `direct_cmd.py` exists with the helper and its result type, `tests/cli/test_direct_cmd.py` covers the over/under/boundary and split-short-circuit cases, and no verb is registered yet (steps 4–6 add the verbs and their wiring).

## Table of Contents

- [Summary](#summary) — what the step ships and the result on green.
- [Why](#why) — why the chain needs a deterministic size stop.
- [Input](#input) — the `CreateResult` shape the gate reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files.
- [Implementation](#implementation) — the helper's contract, what it measures, and the gotchas.
- [Tests](#tests) — the cases to add with the implementation.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors.
- [References](#references) — the docs relevant to this step.
- [Deferred](#deferred) — the verbs, registration, and threshold tuning left to other steps.

## Why

The two direct pipeline verbs (steps 4–5) chain `create → detail → …` in one process, threading `create`'s result to the next stage in memory instead of re-reading the plan from disk. Nothing today guards against handing an over-large create result — a plan with far more steps than a single chained run should drive — straight into `detail`/`jira`/`run`, where it turns into a long, silent, expensive run. The plan (`docs/implementation-plans/2-direct-pipeline-commands.md`, `## Architecture`) calls the size gate "the one piece of new judgment the verbs add on top of the reused handlers." This step lands that judgment as a standalone deterministic helper — and creates the `direct_cmd.py` leaf it lives in — before either verb exists, so steps 4–5 have the gate to call. It builds on step 1's flow note (`depends_on: 1`), which documents the gate and the namespace-sink hand-off.

## Input

The gate reads a `plan_tool/create.py:CreateResult` (the object step 2's namespace sink hands back from `cmd_create`). It depends on two of its fields:

- **`plan_path: Optional[Path]`** — the created plan file to size. It is `None` **only** on the multi-plan split short-circuit (`split_proposal` set, no plan written); a normal create always sets it. The gate must branch on `plan_path is None` before using it.
- **`split_proposal`** — set on that same short-circuit. Reading it (or just the `plan_path is None` test) tells the gate there is no single plan to chain.

The gate does not depend on step 2's sink *mechanism* — step 2 owns how the `CreateResult` reaches an in-process caller; this step only reads the result object's fields. The step count comes from re-parsing the plan on disk with `plan_tool/parser.py:parse_plan`, which returns a `plan_tool/schema.py:Plan` whose `steps` list length is the measured size.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/cli/direct_cmd.py` — the new thin CLI leaf. This step adds the size-gate helper, its result type, and the threshold constant. Steps 4–5 extend this same file with the two verbs.
  - `tests/cli/test_direct_cmd.py` — unit tests for the helper. Steps 4–6 extend this same file with verb and flag-propagation tests.
- **Existing files (edits only):** none.

## Implementation

**What this step adds:** one deterministic function in `plan_tool/cli/direct_cmd.py` that takes a `CreateResult`, measures the created plan's size, compares it to a fixed threshold, and returns a small verdict object saying pass or stop. No verb, no subparser, no argparse registration — that is steps 4–6.

**Measure step count, not bytes.** The natural size signal is the plan's step count: re-parse the plan with `plan_tool/parser.py:parse_plan(result.plan_path)` and read `len(plan.steps)`. This mirrors how the rest of the tool reasons about plan size (`len(plan.steps)` is used throughout, e.g. `plan_tool/detail.py`, `plan_tool/bench.py`). The main alternative — the plan file's byte size — is noisier because it scales with prose and detail, so a fine-grained plan with lots of prose could trip it while a genuinely over-large plan with terse steps slips through. Recommend step count; if a developer finds a reason to prefer bytes, say so in the code comment and keep the threshold constant self-descriptive.

**The threshold is one fixed module constant.** Define it at module scope with a directional, self-descriptive name — one way: `MAX_CHAINABLE_STEPS`. Making it configurable or model-driven is explicitly out of scope for this plan (see `docs/implementation-plans/2-direct-pipeline-commands.md`, `## Out of scope`), so keep it a bare constant. `plan_tool/distill_thresholds.py` is the codebase's precedent for a small threshold-constant leaf with a docstring explaining what each bound means — match that style for the constant's comment. Pick a starting value and note in the comment that tuning is deferred; the exact number is not the critical part of this step.

**Return a small frozen verdict, not a `Recommendation`.** This is not a review finding, so do not route it through `plan_tool/review.py` primitives. Follow the codebase's frozen-result style (`plan_tool/scope_out.py:ScopeOutResult`, `plan_tool/launcher.py:EscalateResult`): a small `@dataclass(frozen=True)` — one way, name it `SizeGateResult` — carrying at least whether the chain may proceed (a pass/stop flag), the measured `step_count`, the `threshold` compared against, and a short human-readable `reason`. Steps 4–5 map a stop verdict to a non-zero exit and print the reason; keep that mapping out of this step — the helper only decides, it does not exit or print.

**Handle the split short-circuit as its own outcome.** When `result.plan_path is None` (the multi-plan split proposal — a documented `CreateResult` invariant), there is no single plan to size and the chain cannot proceed. The gate must not call `parse_plan(None)`. Treat this as a **stop** verdict with a reason that names the split proposal, ideally as a distinct outcome from the over-large case so the caller can print a different message. This is the one non-obvious edge case; give it an explicit test.

**No Claude, no invoker seam.** The helper is pure and deterministic — it takes no `invoker=`/`claude_invoker=` parameter and never shells out. This matches the plan's "spends no Claude" requirement and the deterministic style of `plan_tool/scope_out.py`. `tests/conftest.py`'s autouse gate already raises if any backend binary is spawned, so a plain call in a test proves it stays Claude-free.

**Foundational logic and where else it lives.** The core behavior is *a deterministic size check on a finished plan before it is chained onward*. The codebase has a related but distinct oversize check at a different point: the distill first-pass in `plan_tool/create.py:propose_distilled_seed_from_claude` handles an oversize **seed** (measured in bytes, before a plan exists) by proposing a multi-plan split (`plan_tool/distill_thresholds.py`). That is a different altitude — seed input bytes at create time vs. finished-plan step count at the chain hand-off — so it is **not** a consolidation target; the two measure different things at different points and should stay separate. Note the distinction in the constant's comment so a later reader does not try to fold the two together.

## Tests

New tests in `tests/cli/test_direct_cmd.py`. This is a **feature** step: add these unit tests with the implementation, and every one must be green before the step is considered done.

- `test_over_large_plan_returns_stop` — a `CreateResult` whose plan has more steps than the threshold yields a stop verdict.
- `test_plan_at_threshold_passes` — a plan with exactly the threshold number of steps yields a pass verdict (pins the boundary is inclusive; adjust to the chosen boundary rule).
- `test_plan_below_threshold_passes` — a small plan (well under the threshold) yields a pass verdict.
- `test_split_proposal_result_stops_without_parsing` — a `CreateResult` with `plan_path=None` and a `split_proposal` set yields a stop verdict and does not crash trying to parse a `None` path.
- `test_verdict_carries_step_count_and_threshold` — the returned verdict exposes the measured step count and the threshold, so the caller can build its stop message.
- `test_gate_spends_no_claude` — calling the helper spawns no backend (relies on the `tests/conftest.py` autouse gate) and the helper exposes no invoker parameter.

Build the fixture plans on disk with the real parser round-trip (write a minimal valid plan file, point `CreateResult.plan_path` at it), or construct a `Plan` and write it via `plan_tool/parser.py:write_plan`, so `parse_plan` reads a real plan rather than a mock. Follow the on-disk-fixture style already used in `tests/cli/test_scope_out_cmd.py`.

## Acceptance criteria

- `plan_tool/cli/direct_cmd.py` exists and defines the size-gate helper, its frozen result type, and a single module-level threshold constant.
- The helper returns a **stop** verdict for a `CreateResult` whose plan has more steps than the threshold, and a **pass** verdict for a plan at or below it.
- The helper returns a **stop** verdict (its own split-proposal outcome) for a `CreateResult` with `plan_path is None`, without raising.
- The returned verdict exposes the measured step count and the threshold it compared against.
- The helper takes no invoker parameter and spawns no backend when called (the `tests/conftest.py` autouse gate does not fire).
- All new tests in `tests/cli/test_direct_cmd.py` pass.

## References

- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — for stubbing module-level functions in the new `test_direct_cmd.py` if a test needs to intercept `parse_plan`, though on-disk fixtures are preferred.

## Deferred

- **The `direct-jira` and `direct-run` verbs** — this step adds only the size-gate helper to `direct_cmd.py`; the verbs that call it are steps 4 and 5.
- **Mapping a stop verdict to a non-zero exit and printing the reason** — steps 4–5 own how a chained verb reacts to a stop; the helper only decides.
- **Subparser registration and CLI reference** — registering the verbs in `plan_tool/cli/parser.py`/`app.py` and generating `docs/cli/*` is step 6.
- **Threshold tuning / configurability** — the gate ships with one fixed, non-configurable constant; making it configurable or model-driven is postponed per the plan's `## Out of scope`.
- **Consolidating with the distill oversize-seed split** — the create-time seed-bytes oversize check (`plan_tool/create.py:propose_distilled_seed_from_claude`) stays separate; it measures a different thing at a different point and is not folded in here.
