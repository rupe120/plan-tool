> **Auto-archived**: this plan was swept on 2026-07-04 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Add fingerprint-tagged telemetry and the drift diff (plan-text vs history-driven)

## Summary

This step wires the telemetry write and the drift diff into the per-plan evaluator that steps 3–4 built in `plan_tool/split_criteria.py`. `evaluate_split_criteria` now reads the recorded telemetry history first, computes a drift diff between the plan as it looks right now (the fresh breakdown) and the most recent recorded breakdown that had a *different* plan fingerprint, then records this run's breakdown through step 1's `record_plan_criteria_breakdown`. The recorded event is tagged with `compute_plan_fingerprint(plan_path)` plus an optional borrowed `code_fingerprint`, so a later run can tell when the plan was re-decomposed and its criteria evaluation changed. The one design decision that shapes everything: read history *before* recording so the diff never sees this run's own event, and diff only the fires? criteria — never the run-state split-safety gate, which the fingerprint doesn't hash. On green, one `plan-criteria-breakdown` event lands per per-plan run, `render_plan_breakdown` prints a drift note when both the fingerprint and the results changed, and a recorder failure never breaks the command.

## Table of Contents

- [Summary](#summary) — what the step adds and the observable result on green
- [Why](#why) — the metrics/drift gap steps 1–4 leave open
- [Files (creates vs edits)](#files-creates-vs-edits) — the one code file and its test file this step extends
- [Implementation](#implementation) — the read-before-record order, the drift diff, the fingerprint tags, and the constraints
- [Tests](#tests) — unit tests in tests/test_split_criteria.py for the recorder wiring and the drift diff
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — hashlib + jsonl/json docs relevant to this step
- [Deferred](#deferred) — the recorder itself, the CLI, and the cross-plan dashboard owned by other steps

## Why

Steps 1–4 build the recorder, the catalog + legend, the deterministic evaluator, and the split-safety gates — but nothing calls step 1's recorder yet, and nothing captures a plan's criteria evaluation over time. Step 3 deliberately records nothing — its `test_evaluate_records_no_telemetry` and its Deferred both name telemetry + drift as step 5's job. Without this step the breakdown is a one-shot read: it answers "why is this plan shaped this way *right now*?" but not "did its decomposition drift since a previous version?" That drift signal is the whole point of tagging each breakdown with the plan's fingerprint — it's the metrics half of the feature (BACKLOG #72, single-plan slice). This step lands the write and the diff last, after the evaluator is reviewable on its own, matching how `plan-tool convergence` leans on `record_convergence` behind an already-built diagnostic.

## Files (creates vs edits)

This step's frontmatter declares no `files:`. Both paths below are the files the whole feature is built in (step 2 creates them; steps 3–4 extend them); step 5 extends them again. No new file is introduced.

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/split_criteria.py`
    - Extend `evaluate_split_criteria` to read telemetry history, compute the drift diff, and record this run's breakdown at the end.
    - Add a small frozen drift record (suggest `CriteriaDrift`) and a pure helper (suggest `compute_criteria_drift`) that diffs the current fires? results against a prior recorded breakdown.
    - Add a `drift` field to `PlanCriteriaBreakdown` (step 3's in-memory record) so the renderer can show the note.
    - Extend `render_plan_breakdown` (step 3/4's renderer) to print a drift note section, plain when color is off.
  - `tests/test_split_criteria.py` — add the recorder-wiring and drift-diff unit tests below.

`plan_tool/telemetry.py` is **not** edited here — `record_plan_criteria_breakdown` and its `PLAN_CRITERIA_BREAKDOWN_KIND` are step 1's. `DATA_CONTRACT.md` / `tests/test_data_contract.py` are **not** edited here — step 1 documents this decision kind and its context keys; step 5 adds no new persisted key.

## Implementation

**Foundational logic: read history → diff → record, in that order, inside `evaluate_split_criteria`.** The evaluator already computes the fires? `CriterionResult` rows (step 3) and the `SplitSafetyGate` records (step 4). Step 5 wraps three additions around that existing body:

- **Read the recorded history first, before recording anything.** Call `telemetry.read_decisions(repo_root)` near the top of `evaluate_split_criteria` (or at least before the record call). Reading first is what makes the diff independent of write timing — the current run's event isn't in the log yet, so it can never be diffed against itself. Pin this with a test; it is the same read-before-record invariant the accumulated lessons call out.
- **Record this run's breakdown at the end**, through step 1's `telemetry.record_plan_criteria_breakdown` (already imported — step 3's evaluator imports `telemetry`). Pass `repo_root`, the `plan_slug`, the `plan_fingerprint`, the optional `code_fingerprint`, and the primitive projection of the fires? results as the `criteria` keyword; the recorder derives the counts. **The evaluator is the recorder site, not the CLI** — step 6's `cmd_split_criteria` must not record (it would double-count). Note this for step 6.
- **The recorder is best-effort and must stay that way.** `record_plan_criteria_breakdown` delegates to `record_decision`, which swallows every error. Do not wrap the call in your own try/except or let a telemetry failure change the evaluator's return value.

**Tag the event with the plan's fingerprint.** Compute `plan_fingerprint = review_persistence.compute_plan_fingerprint(plan_path)` — `review_persistence` is already imported. Derive `plan_slug` from `plan_path` with `plan_tool/locator.py:slug_from_filename` (the same helper `compute_plan_fingerprint` uses). This digest covers plan + detail bytes only; it does **not** hash run state — which is exactly why the drift diff below excludes the split-safety gate.

**Borrow the code fingerprint from the most-recent saved report — don't compute one.** `split_criteria.py` is a leaf and must not import `scope_guard` / `drift_detection` to walk the repo. Instead:
- Borrow it from the **already-loaded** `load_report_history(plan_path)` result — the same history step 3's altitude-3 signal reads — taking its **newest run entry**, rather than a raw `load_review` on the newest sidecar. This is deliberate for the exits-0 posture: `load_report_history` **swallows `ReviewLoadError`** and skips an unparseable sidecar, whereas a direct `load_review` (or `list_saved_reviews` + `load_review`) would **raise** on a corrupt newest report and crash `evaluate_split_criteria`, breaking the always-exits-0 contract. Reuse the history the evaluator already loaded; do not re-read the newest sidecar with a raising loader.
- **Key the decision on that newest run's `code_fingerprint_present` bool, not on whether any run exists.** If it has `code_fingerprint_present == True`, pass its `code_fingerprint` (the opaque path→hash map) to the recorder. If it's `False` (never computed) — or the history is empty (no runs, including when the newest sidecar was unparseable and skipped) — **omit the `code_fingerprint` key entirely** (pass `None`, the same "missing key means not-applicable" shape as `record_create_step_outcome`). A report that never computed a code fingerprint records no `code_fingerprint` key.
- `code_fingerprint` is recorded context for later cross-plan analysis; it is **not** part of the drift decision (which keys on plan fingerprint + results).

**The drift diff — current plan vs last recorded (last different fingerprint).** Add `compute_criteria_drift(prior_events, *, current_results, current_fingerprint, plan_slug)` returning a frozen `CriteriaDrift`. One way to shape it:
- **Pick the history-driven side.** From `prior_events`, keep only `kind == PLAN_CRITERIA_BREAKDOWN_KIND` and `plan_slug ==` this plan. Walk newest-to-oldest (append order in `decisions.jsonl` is chronological — the log is append-only) and pick the first event whose recorded `plan_fingerprint` differs from `current_fingerprint`. That event is the last time the plan looked structurally different. If none exists, there's no prior version to diff — return a `CriteriaDrift` with `has_prior=False` and render no note.
- **Diff the fires? results only.** Compare the current fires? result-set against the prior event's recorded results by criterion `id`: which ids fire now but didn't (`newly_firing`), which stopped (`stopped_firing`), and which changed severity (`severity_changed`). Suggested fields: `has_prior`, `prior_fingerprint`, `current_fingerprint`, `newly_firing`, `stopped_firing`, `severity_changed`, and a derived `changed` bool.
- **Render the note only when the fingerprint changed *and* the result-set changed.** A reshaped plan whose criteria evaluate identically is not drift — leave the note off (a terse "plan reshaped; criteria unchanged" line is optional latitude). The note belongs to the same "why is this plan shaped this way?" surface, so render it in `render_plan_breakdown` and keep it plain when color is off.

**Constraints and gotchas — the parts not free to vary:**
- **The drift diff must exclude the split-safety gate.** Diff only the `CriterionResult` fires? rows, never the `SplitSafetyGate` records step 4 added. Split-safety reads run state, which `compute_plan_fingerprint` does not hash — a changed fingerprint can never reflect a split-safety change, so folding gates into the diff would misattribute a run-state change to re-decomposition. Do not record the gates in the drift-diffable results either.
- **Record a primitive projection, not the dataclasses.** `telemetry.py` is a stdlib-only leaf and takes JSON primitives. Convert each fires? `CriterionResult` to a plain dict (id str, fired bool, severity str-or-`None`, hit step ids) before handing it to the recorder — don't pass `CriterionResult` / `PlanCriteriaBreakdown` objects. `PlanCriteriaBreakdown` and `CriteriaDrift` stay in-memory only, so they carry no DATA_CONTRACT obligation; the persisted shape is the primitive context step 1 documents.
- **No new signature params.** `evaluate_split_criteria(plan, *, plan_path, repo_root)` already carries `repo_root` (added in step 4) — reuse it for both `read_decisions` and the record call. No new required argument.
- **Keep the leaf posture.** Use only the already-imported `telemetry` and `review_persistence` seams plus `locator.slug_from_filename`. Do not add a module-top import of `scope_guard`, `drift_detection`, or any orchestrator to compute a code fingerprint.
- **The evaluator owns the read → diff → record; the CLI (step 6) does not.** This step pins the contract: `evaluate_split_criteria` reads history, computes drift into `PlanCriteriaBreakdown.drift`, and records, so `render_plan_breakdown(breakdown, *, color=…)` reads `breakdown.drift` with **no** `drift=` kwarg, and `compute_criteria_drift(prior_events, *, current_results, current_fingerprint, plan_slug)` is the one signature. Step 6's handler neither reads decisions, computes drift, nor records — all three live inside the evaluator.

## Tests

Add these to `tests/test_split_criteria.py` (created in step 2). Seed prior history by calling step 1's `record_plan_criteria_breakdown` directly with chosen fingerprints/results, then run `evaluate_split_criteria` and assert through `telemetry.read_decisions`.

- `test_evaluator_records_plan_criteria_breakdown` — after `evaluate_split_criteria`, `read_decisions` returns exactly one `plan-criteria-breakdown` event carrying the fires? results and counts.
- `test_recorded_event_carries_plan_fingerprint` — the event's `plan_fingerprint` equals `compute_plan_fingerprint(plan_path)`.
- `test_recorded_results_are_primitives` — the event `context` results are plain dicts (ids/bools/strings/ints), not dataclass instances.
- `test_code_fingerprint_recorded_when_present` — with a newest saved report whose `code_fingerprint_present` is True, the event carries that report's `code_fingerprint`.
- `test_code_fingerprint_omitted_when_not_computed` — with a report whose `code_fingerprint_present` is False (and separately, with no saved report), the event has no `code_fingerprint` key.
- `test_evaluator_reads_before_recording` — the drift diff ignores this run's own just-written event (read happens before record).
- `test_drift_note_when_fingerprint_and_results_change` — seed a prior different-fingerprint event with different fires? results; `breakdown.drift.changed` is True and `newly_firing` / `stopped_firing` name the right ids.
- `test_no_drift_when_no_prior_different_fingerprint` — with only same-fingerprint history (or none), `drift.has_prior` is False and no note renders.
- `test_no_drift_when_results_unchanged` — prior different fingerprint but identical results → `drift.changed` is False, no changed note.
- `test_drift_excludes_split_safety_gate` — a run-state change that flips a split-safety gate does not appear in the drift diff.
- `test_telemetry_failure_never_breaks_evaluate` — point `repo_root` at a path that can't hold the file (a regular file, not a dir); `evaluate_split_criteria` still returns its breakdown without raising.
- `test_render_plan_breakdown_shows_drift_plain` — with color off, the rendered breakdown includes the drift note text when the diff changed.

### Test-creation order (feature step)

This is a **feature** step — new behavior (the telemetry write and the drift diff). Add every test above alongside the implementation; each covers one behavior it introduces. Green-before-done gate: all new tests must pass, and the existing step 2–4 tests in `tests/test_split_criteria.py` must stay green — **with one intentional supersession**: step 3's `test_evaluate_records_no_telemetry` asserted the evaluator writes no telemetry, which this step reverses by design. Under `enforce_step_tests: true` that test would fail, so **update it here** (the evaluator now records exactly one `plan-criteria-breakdown` event per per-plan run — the behavior `test_evaluator_records_plan_criteria_breakdown` above asserts) rather than leaving the stale no-write assertion.

## Acceptance criteria

- After `evaluate_split_criteria(plan, plan_path=..., repo_root=...)`, `telemetry.read_decisions(repo_root)` contains one `plan-criteria-breakdown` event for the plan.
- That event's `context` carries `plan_fingerprint == compute_plan_fingerprint(plan_path)`, the fires? results as primitives, and the counts step 1's recorder expects.
- The event carries `code_fingerprint` only when the newest saved report has `code_fingerprint_present == True`; otherwise the key is absent.
- The drift diff selects the most recent recorded event with a *different* `plan_fingerprint` and ignores the current run's own event.
- `PlanCriteriaBreakdown.drift` reports `newly_firing` / `stopped_firing` / `severity_changed`, and `render_plan_breakdown` prints a drift note only when both the fingerprint and the fires? result-set changed.
- The drift diff and the recorded drift-diffable results exclude the split-safety gate.
- A recorder failure does not raise from or change the return of `evaluate_split_criteria`.
- All new tests in `tests/test_split_criteria.py` pass; the step 2–4 tests stay green.

## References

- [hashlib — Secure hashes and message digests (Python docs)](https://docs.python.org/3/library/hashlib.html) — the sha256/hexdigest primitive behind `compute_plan_fingerprint`, the plan-side tag this step records and diffs on.
- [JSON Lines (jsonl) format specification](https://jsonlines.org/) — the append-only newline-delimited format `telemetry.py` writes to `.plan-tool/telemetry/decisions.jsonl`; each event this step records is one line.
- [json — JSON encoder and decoder (Python docs)](https://docs.python.org/3/library/json.html) — `json.dumps`/`json.loads` behind the DecisionEvent context (per-criterion results, fingerprints, counts) written and read back for the diff.

## Deferred

- The `record_plan_criteria_breakdown` recorder, the `plan-criteria-breakdown` kind, and its `DATA_CONTRACT.md` documentation — owned by step 1; step 5 only calls the recorder.
- Wiring the CLI (`plan_tool/cli/split_criteria_cmd.py`) — step 6; that handler must not record telemetry, read decisions, or compute drift — all three live inside the evaluator, and `render_plan_breakdown` reads `breakdown.drift`.
- Computing a fresh code fingerprint — split-criteria borrows the last saved report's `code_fingerprint`; it never walks the repo (leaf posture). A never-computed report records no `code_fingerprint` key.
- Cross-plan / over-time aggregation and threshold-tuning dashboards — BACKLOG #72 phase 2–3; this step ships the single-plan capture + per-plan drift diff that motivates it.
