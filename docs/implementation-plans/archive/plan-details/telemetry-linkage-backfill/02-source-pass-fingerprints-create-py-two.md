> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Source and pass fingerprints into create.py's two telemetry recorder calls

## Summary

Thread caller-computed fingerprints into the two create-stage decision recorders in `plan_tool/create.py`: `record_create_granularity_assessment` (through the `_record_create_assessment` wrapper) and `record_create_step_outcome` (through the `_record_step_outcome` wrapper). Both fire inside `_review_step_change_types` during the create wizard's confirm/override/split loop — which runs **before** `write_new_plan`, so the plan markdown is not on disk yet. The key design fact: at that point `code_fingerprint` (the current on-disk state of the code the steps will touch) is real and meaningful, while `plan_fingerprint` (which reads the plan file) has no file to read — a missing-file digest is a useless constant, so the create sites carry `code_fingerprint` **only** and leave `plan_fingerprint=""`. The step computes `code_fingerprint` once per review pass — best-effort, guarded, hoisted above the per-step loop — and forwards it into both recorders. On green, a newly recorded `create-review` and `create-step-outcome` event carries a non-empty `code_fingerprint` map (when a step's declared files exist on disk; for a greenfield plan whose files don't yet exist the map is `{}` — a documented weak-anchor limitation) with no change to create's control flow, exit code, or output.

## Table of Contents

- [Why](#why) — what create decisions can't be joined on today
- [Input](#input) — the recorder API, fingerprint helpers, and the pre-write timing this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the one source module and one test file touched
- [Implementation](#implementation) — how the two wrappers get the fingerprints, the plan_path wrinkle, and the hoist
- [Tests](#tests) — per-site fingerprint assertions plus the best-effort and degrade paths
- [Acceptance criteria](#acceptance-criteria) — the observable checks a reviewer runs
- [References](#references) — the fingerprint/telemetry docs relevant here
- [Deferred](#deferred) — sites and behavior owned by other steps

## Why

Phase 1 gave `DecisionEvent` fields to carry the join keys, but the two create-stage recorder calls still pass nothing and rely on the `""`/`{}` defaults. So every `create-review` and `create-step-outcome` event stays unjoinable on a code-state anchor a phase-3 resolver could correlate on. These two sites are the create slice of Part A (step 1 covered the on-disk review/completeness/convergence sites). Both recorders already accept the defaulted `plan_fingerprint`/`code_fingerprint` params — the callers just never wire them. The wrinkle this step must respect: unlike step 1's sites, create decisions are made **before the plan is written**, so the meaningful anchor here is the code state, not an on-disk plan digest. This step makes the two create producers stamp the code-state key without touching the wizard's control flow, exit code, or output.

## Input

This step populates two fixed contracts and reads a third timing fact. It changes none of them.

- **Existing recorder signatures** — `plan_tool/telemetry.py:record_create_granularity_assessment` and `record_create_step_outcome` each already accept `plan_fingerprint: str = ""` and `code_fingerprint: Optional[dict[str, str]] = None`. This step relies on those defaults so no recorder signature changes. `record_decision` already swallows every error, so the recorder call is safe; the only added risk is the fingerprint-compute above it.
- **Fingerprint compute helpers** — `plan_tool/fingerprint.py:compute_code_fingerprint(plan, plan_path, repo_root)` returns the `{repo-relative-posix-path: sha256-hex}` map over the plan's in-scope code files, digesting each file's current bytes and omitting missing ones. It needs a parsed `Plan`, a `plan_path`, and `repo_root`. `plan_tool/review_persistence.py:compute_plan_fingerprint(plan_path)` reads the plan markdown (and its detail bundle) — it needs the file to exist to return a meaningful digest.
- **The pre-write timing (correctness-critical)** — `_review_step_change_types` is called from `create_plan` at the confirm/override/split gate, which runs **before** `write_new_plan`. The plan markdown does not exist yet when either recorder fires. This decides what each fingerprint can carry (see Implementation).
- **`run` telemetry state** — `run_id` needs no backfill here. It auto-flows from the `telemetry`-owned `_active_run_id` ContextVar, bound only at the two `run` entrypoints. `create` is not a run, so `run_id=""` is correct and this step leaves it alone.

Limit on verifying the contract: this step reads the recorder signatures, the fingerprint helpers, and the create call ordering at HEAD. If any defaulted param, helper return shape, or the pre-write ordering has drifted, re-check the two sites before wiring.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — add an optional `code_fingerprint` param to `_record_create_assessment` and `_record_step_outcome` and forward it to the recorders (`plan_fingerprint` stays the recorders' `""` default, uncomputed); add a small best-effort helper that computes `code_fingerprint` for the create-review step set; compute it once in `_review_step_change_types` and pass it into every `_record_create_assessment` and `_record_step_outcome` call; add a body-local import of `compute_code_fingerprint`.
  - `tests/test_create.py` — add fingerprint assertions to `TestStepReviewAssessmentTelemetry` and `TestStepReviewOutcomeTelemetry`, plus a best-effort test and a degrade-when-no-output_dir test.

## Implementation

**Foundational logic of this step:** compute caller-side fingerprints for the create-review step set and pass them into the two create-stage decision recorders. The other five backfill sites that exercise this same "compute-then-pass" logic — `record_code_reveals_split`, `record_granularity`, `record_audit_coverage`, `record_convergence` — are step 1's file set and are out of scope here (see [Deferred](#deferred)).

- **Carry `code_fingerprint` — it's the meaningful anchor at create time.** `compute_code_fingerprint` hashes the current on-disk bytes of the files a step declares (`step.files`/`creates`), skipping ones not yet on disk. That is a real snapshot of the code the create decision is about, and it ties a create decision to the code state a later run/outcome will also see. This is the primary deliverable of the step.
- **Derive a prospective `plan_path` — the exact filename does not matter.** `compute_code_fingerprint` uses `plan_path` only to exclude the plan markdown and per-step detail files from the watched set (via `plan_tool/scope_guard.py:compute_drift_watched_paths`). At create time those plan-owned paths are not in the in-scope set anyway (in-scope is `step.files`/`creates`), so the exclusion is a no-op and any plausible path works. Recommended: derive `plan_path = output_dir / f"{slug}.md"` inside the compute helper. Do **not** thread `priority` in just to call `plan_tool/create.py:predict_plan_path` — the priority-bucket prefix has no effect on either fingerprint here (the plan file is absent regardless of prefix, and the code map does not depend on the prefix).
- **Do not carry `plan_fingerprint` at create time — it would be a useless constant.** `compute_plan_fingerprint` on a not-yet-written path returns the stable empty/missing-file digest — non-empty, but **the same value for every fresh create**, so it is worthless as a join key (it can't distinguish one create decision from another). The plan-level decision (body Architecture ground rule 3 + AC): create sites carry `code_fingerprint` **only** and leave `plan_fingerprint=""` (its default). Do **not** call `compute_plan_fingerprint` here at all — computing a constant just to fill the field is wasted work and misleads a resolver into thinking the events share a plan state. State plainly in a comment that `code_fingerprint` is the meaningful create-time anchor and `plan_fingerprint` is intentionally left empty pre-write.
- **Hoist the compute above the per-step loop.** `_record_step_outcome` fires once per step inside the `while i < len(reviewed)` loop in `_review_step_change_types` (on accept/override/split-requested/split-applied/split-error/split-invalid/split-unusable). The on-disk code bytes do not change during the review, so compute the two fingerprints **once** near the top of `_review_step_change_types` (over the initial `steps`) and reuse the same values for every `_record_step_outcome` and `_record_create_assessment` call. Never recompute inside the loop — that would re-hash the file set per step for no gain.
- **Thread the value, don't recompute inside the wrappers.** Give `_record_create_assessment` and `_record_step_outcome` one new optional param — `code_fingerprint: Optional[dict[str, str]] = None` — and forward it straight into `record_create_granularity_assessment` / `record_create_step_outcome` (leave `plan_fingerprint` at the recorders' `""` default). Both wrappers already sit inside a `try/except` that returns on any error, and `_review_step_change_types` is their only caller (every call site lives inside that function), so the threading is self-contained.
- **Guard the compute — the wrappers' safety does not cover it.** The wrappers swallow errors and `record_decision` swallows errors, but the fingerprint-compute is caller code that runs before the wrapper call. Wrap the compute helper's body in its own `try/except` returning `("", {})` on any failure, and return `("", {})` early when any of `repo_root`/`output_dir`/`slug` is `None`. That keeps create's interactive loop control-flow-neutral: a fingerprint error can never break the wizard.
- **Add the import body-local, mirroring the sibling site.** `plan_tool/create.py` does not import the compute helper today. Add a lazy import inside the compute helper — `from plan_tool.fingerprint import compute_code_fingerprint` (only; `compute_plan_fingerprint` is not used here) — matching the body-local style the sidecar tail in `plan_tool/cli/completeness_phases.py` already uses. Build the dry-run `Plan` for `compute_code_fingerprint` the same way `_record_create_assessment` already does (`Plan(title="dry-run", status=PLANNING, priority=LOW, steps=steps)`); a step list that can't form a valid `Plan` falls into the same guarded `except` and yields `{}`.

One recommended shape: a module-local `_create_decision_code_fingerprint(steps, *, repo_root, output_dir, slug) -> dict[str, str]` that returns `{}` unless all inputs are present, else derives the prospective `plan_path`, builds the dry-run `Plan`, and returns `compute_code_fingerprint(plan, plan_path, repo_root)`, swallowing every error. `plan_fingerprint` is not computed — the wrappers receive only `code_fingerprint` and `plan_fingerprint` stays its `""` default. The constraints that must hold: compute once per review pass, guard the compute, degrade to `{}` on missing inputs, and forward the value into both wrappers.

## Tests

Add to `tests/test_create.py`. New tests drive `_review_step_change_types` directly (as the existing telemetry tests do) and read events back with `plan_tool.telemetry.read_decisions`. To get a non-empty `code_fingerprint`, a test must pass `output_dir` **and** write at least one `step.files` entry onto disk under `repo_root`; the existing tests pass neither, so they keep empty fingerprints and stay green.

In `TestStepReviewAssessmentTelemetry`:
- `test_assessment_records_code_fingerprint` — with `output_dir` set and a `step.files` entry written under `repo_root`, the `create-review` event's `code_fingerprint` is a non-empty `{path: hash}` map keyed by the on-disk file.
- `test_assessment_code_fingerprint_empty_without_output_dir` — calling `_review_step_change_types` with no `output_dir` (the existing tests' shape) leaves `code_fingerprint == {}`, proving the degrade path and no regression.
- `test_assessment_code_fingerprint_omits_missing_files` — a step whose declared file does not exist on disk yields an empty (or that-file-omitted) map, matching `compute_code_fingerprint`'s skip-missing behavior.

In `TestStepReviewOutcomeTelemetry`:
- `test_step_outcome_records_code_fingerprint` — an accept/override outcome event carries the same non-empty `code_fingerprint` as the assessment event from the same pass.
- `test_step_outcome_fingerprint_computed_once_across_loop` — over a multi-step review, every `create-step-outcome` event carries the same `code_fingerprint` value (proves the hoist: one compute, reused per step).
- `test_step_outcome_best_effort_when_fingerprint_raises` — monkeypatch the compute helper (or `compute_code_fingerprint`) to raise; `_review_step_change_types` still returns the reviewed steps and records events with empty fingerprints, unchanged control flow.

Pre-write anchor check:
- `test_create_event_plan_fingerprint_empty` — assert both the `create-review` and `create-step-outcome` events carry `plan_fingerprint == ""` (the create sites deliberately do not compute it pre-write; `code_fingerprint` is the create-time anchor), so a future change that starts stamping it is a visible diff.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Author the unit tests above alongside the implementation, each covering the behavior it names. Green-before-done gate: every new test must pass, and the existing `TestStepReviewAssessmentTelemetry` / `TestStepReviewOutcomeTelemetry` tests (which drive `_review_step_change_types` without `output_dir`) must stay green unmodified, before this step is considered finished.

## Acceptance criteria

- A newly recorded `create-review` event (from `record_create_granularity_assessment`) carries a non-empty `code_fingerprint` `{path: hash}` map when a declared `step.files` entry exists on disk and `output_dir`/`slug`/`repo_root` are all present.
- A newly recorded `create-step-outcome` event (from `record_create_step_outcome`) carries the same `code_fingerprint` under the same conditions.
- Every `create-step-outcome` event in a single multi-step review carries an identical `code_fingerprint` value (compute is hoisted above the loop, not per-step).
- With no `output_dir` (the existing tests' call shape), both events keep `code_fingerprint == {}` and every pre-existing telemetry test in `tests/test_create.py` passes unmodified.
- A forced failure in the fingerprint-compute leaves `_review_step_change_types`'s return value, the create command's exit code, and its stdout unchanged; events still record with empty fingerprints.
- `plan_tool/telemetry.py` is unchanged (no signature change; the recorders already accept the defaulted params); `TELEMETRY_SCHEMA_VERSION` is not bumped.

## References

- [hashlib — Secure hashes and message digests (Python 3.13)](https://docs.python.org/3/library/hashlib.html) — the digest APIs underlying `compute_plan_fingerprint`/`compute_code_fingerprint`, useful when reasoning about the empty-file digest and the code-map hashes.
- [JSON Lines](https://jsonlines.org/) — the newline-delimited JSON format `decisions.jsonl` uses; the one-object-per-line append contract these recorders emit and `read_decisions` reads back.
- [contextvars — Context Variables (Python 3.13 Standard Library)](https://docs.python.org/3/library/contextvars.html) — the ContextVar semantics behind `_active_run_id`, the reason `run_id` stays `""` at create-time and needs no backfill here.

## Deferred

- **The other five backfill sites** (`record_code_reveals_split`, `record_granularity`, `record_audit_coverage`, `record_convergence`) — owned by step 1; do not touch them here.
- **Part B's three new recorder families** (drift-gate, apply-verdict, escalate-to-split) — steps 3–5.
- **A meaningful (non-constant) `plan_fingerprint` at create time** — not achievable until the plan is on disk, which is after this gate runs; revisit only if phase 3 needs an on-disk plan anchor for create decisions. The meaningful create-time anchor this step lands is `code_fingerprint`.
- **Consolidating the create compute with `completeness_phases.py`'s sidecar-tail compute** — the two mirror the same `compute_plan_fingerprint` + `compute_code_fingerprint` shape but exist for different reasons (telemetry join keys vs report staleness); folding them into one helper is a reconcile-owned refactor, not part of this backfill.
- **`BACKLOG #72` bookkeeping** — step 6 updates the tracking entry after steps 1–5 land.
