> **Replaced**: this file has been superseded by `docs/implementation-plans/2-telemetry-producer-hardening.md`.
> Preserved here for history; do not edit.

# Telemetry Producer Hardening

## Source and objective

Finish the producer-side residual retained under `BACKLOG.md` **#72 —
Decision/outcome telemetry** after phase 3 shipped the resolver and `plan-tool
telemetry` surface.

The resolver is only as trustworthy as its inputs. Several known producer paths
still omit, misroute, over-duplicate, or silently drop decision events. Build a
small, independently reviewable hardening plan that closes those gaps without
changing the phase-3 resolver's outcome vocabulary or introducing auto-tuning.

This plan must update `BACKLOG.md` when it ships: remove the completed producer
hardening residual from #72, update the stale Priority/Readiness text that still
calls the already-shipped #72 resolver the next concrete pick, and retain only
any explicitly named residual that the plan genuinely defers.

## Current implementation seams

- `plan_tool/telemetry.py` owns the stdlib-only, swallow-all-errors recorder,
  `DecisionEvent`, `_MAX_LINE_BYTES`, `record_decision`, the create assessment
  and per-step outcome helpers, and `record_apply_verdict`.
- `plan_tool/launcher.py:apply_finding` records normal apply verdicts. A backend
  invocation failure currently exists only in the run log and emits no distinct
  `apply-verdict` telemetry token.
- `plan_tool/cli/completeness_apply_parallel.py` applies findings inside isolated
  worker worktrees. Telemetry written from a worker can land in the disposable
  worktree, or reach the canonical decision log without the canonical repo/run
  keys. The replayed canonical result must own the durable telemetry event.
- `plan_tool/telemetry.py:record_decision` silently returns when the serialized
  line exceeds `_MAX_LINE_BYTES`. Large `code_fingerprint` path→hash maps are the
  dominant risk on drift-gate, code-reveals-split, and create recorder sites.
- Create granularity assessment records one full `code_fingerprint` map and then
  repeats it on every `create-step-outcome`. The per-step outcome should join to
  the assessment through stable compact keys instead of copying the map.
- Existing coverage is concentrated in `tests/test_telemetry.py`,
  `tests/test_launcher.py`, `tests/test_review.py`, and
  `tests/cli/test_completeness_apply_parallel.py` /
  `tests/cli/test_completeness_cmd.py`. Preserve their established helpers and
  real-path tests rather than building a parallel fake telemetry layer.
- `DATA_CONTRACT.md` drift-guards the persisted telemetry schema. Any new event
  token, compact digest, dropped-event artifact, or changed create join contract
  must be documented and guarded in the same step that introduces it.

## Required outcomes

### 1. Backend invocation failures are observable apply outcomes

When `apply_finding` cannot obtain a usable backend response, emit one distinct,
documented `apply-verdict` value that is distinguishable from `APPLIED`,
`NOT-APPLICABLE`, `BLOCKED`, and `BLOCKED-STRUCTURAL`.

- Preserve the host failure behavior and return/exception path exactly.
- Emit at most one event for one failed apply attempt.
- Carry the same plan slug, step/finding anchor, plan fingerprint, and run binding
  available to ordinary apply verdicts.
- The recorder remains best-effort: a telemetry exception must never replace or
  mask the backend failure.
- Extend inline outcome mapping in `telemetry_analysis.py` only if the new token
  needs an explicit `still-open`/`no-op` interpretation; do not invent a fifth
  outcome verdict.

### 2. Parallel completeness workers produce canonical telemetry

For `completeness-apply --jobs N`, ensure each durable per-finding apply result is
recorded once in the canonical repository's decision log, with canonical
`repo_root`, `plan_slug`, run id, plan fingerprint, step id, and anchor.

- Worker-local logs in disposable worktrees are not authoritative and must not
  create duplicates when canonical replay succeeds.
- A failed worker, replay conflict/retry, skipped finding, and successful apply
  need deterministic exactly-once rules.
- Keep the worker isolation and deterministic replay ordering intact.
- Do not make telemetry a reason for the parallel apply command to fail.
- Cover both the lower-level worker/replay seam and the command-level `--jobs N`
  path with regression tests.

### 3. Oversized events are observable or made compact before the cap

Eliminate silent, unknowable loss at `_MAX_LINE_BYTES` for the fingerprint-heavy
producer families.

During plan authoring, choose and document one coherent design after inspecting
real payload consumers:

- Prefer a compact, deterministic code-state digest when downstream correlation
  only needs identity/equality, while retaining a full map only at the one
  artifact that genuinely needs per-path diffs; or
- scope the full map at each producer and add a small best-effort dropped-event
  counter/diagnostic for payloads that still exceed the cap.

Constraints:

- Do not truncate JSON into an invalid or ambiguous event.
- Do not weaken `telemetry.py`'s stdlib-only leaf or swallow-all-errors contract.
- A digest must have a canonical ordering/framing and focused collision-resistant
  hash, with tests proving identical maps are stable and changed maps differ.
- A dropped-event signal must not recursively use the same oversized event path.
- Document any persisted shape in `DATA_CONTRACT.md` and update its drift guard.

### 4. Create outcomes stop duplicating the full code fingerprint

Carry the full code fingerprint (or its chosen compact replacement) once on the
create assessment event. Per-step `create-step-outcome` events must carry only
the compact join identity needed to associate them with that assessment.

- Prefer an explicit assessment/decision id returned or supplied through the
  create flow over a fragile timestamp-only join if the existing API can support
  it without widening cycles.
- If compatibility requires `plan_slug` + timestamp, define collision and
  ordering behavior and test it.
- Keep schema-v1/v2 historical decision rows readable.
- Update `telemetry_analysis.py` only where required to preserve inline outcome
  resolution and aggregation.

### 5. Close the named regression-test gaps

Add direct tests for every apply-loop telemetry threading site and the Part-A /
escalate best-effort wrappers named by #72:

- kwargs and canonical keys are forwarded unchanged;
- a raising fingerprint computation or recorder never perturbs the host command;
- no successful, failed, retried, or skipped path double-records;
- ownerless/legacy rows remain tolerated;
- telemetry writes remain local, gitignored, and best-effort.

Favor parameterized tests over copy-pasted cases, but keep assertions at the
public seam so a missing caller is caught.

## Scope and decomposition guidance

This is a multi-module feature/hardening plan, not one broad step. Decompose it
so each code step owns its production change and real tests in the same commit.
A likely dependency order is:

1. compact/dropped-event primitive and persisted contract;
2. create assessment/outcome deduplication on that primitive;
3. backend-failure apply verdict;
4. canonical parallel-apply telemetry routing;
5. cross-caller regression sweep;
6. docs, capability/data-contract reconciliation, and BACKLOG #72 closure.

The authoring pass may adjust this order when code grounding reveals a cleaner
dependency boundary. Do not combine unrelated producer paths merely to reduce
step count. Set `enforce_step_tests: true`.

## Out of scope

- Changes to the four public derived verdicts: `acted-on`, `no-op`, `reverted`,
  `still-open`.
- Auto-tuning thresholds or mutating plans/configuration from telemetry.
- A new analytics command, dashboard, cache, or second decision log.
- General run-log redesign or telemetry rotation/time-windowing beyond what is
  strictly needed to expose oversized decision-event loss.
- Backfilling historical local telemetry files.
- Broad parallel-apply refactoring unrelated to canonical telemetry ownership.

## Deferred

No known producer-hardening requirement is deferred at seed time: the five
named #72 residuals are the scope of this plan. If code grounding or the final
completeness audit proves that one item needs a separate architectural effort,
the plan must name that residual precisely, record it in `BACKLOG.md`, and state
why it cannot safely ship here. Do not silently defer a named residual or use a
generic “future work” placeholder.

## Acceptance criteria

- Backend invocation failure produces exactly one documented, joinable
  `apply-verdict` event without changing the host failure behavior.
- Parallel `completeness-apply --jobs N` records each durable per-finding result
  exactly once in the canonical repo with its join keys; disposable worktrees do
  not retain authoritative duplicates.
- Fingerprint-heavy producer events no longer disappear silently at the byte cap;
  the chosen compactness/observability mechanism is deterministic, tested, and
  documented.
- Create assessment owns the heavyweight fingerprint once; per-step outcomes use
  a compact, unambiguous join identity and remain resolvable.
- Direct regression tests cover all named apply-loop forwarding and best-effort
  wrapper sites.
- `DATA_CONTRACT.md`, relevant architecture/operator docs, and drift guards match
  the final persisted shapes.
- `BACKLOG.md` #72 no longer lists shipped producer hardening, and its priority
  lens no longer calls the shipped resolver the next concrete pick.
- Focused suites and the full test suite pass; telemetry remains stdlib-only,
  read-only from the analysis command, best-effort at every producer, and never
  a reason a host command fails.

## Required workflow for this plan

- Create the plan from this seed using the Codex backend.
- Author every detail file with `detail --no-iterate`; do not run per-step detail
  convergence tails.
- Only after all detail files exist, run one conceptual completeness audit.
  Review its saved findings manually and edit the plan/detail files directly to
  close valid gaps; do not blanket auto-apply conceptual findings.
- Execute the plan step by step with per-step commits and tests.
- After execution, run plan-canonical `reconcile-code` to convergence, correcting
  implementation gaps without changing the plan to fit deficient code.
- Finish with a code-review pass, fix findings, and re-review until clean.
