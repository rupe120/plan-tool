> **Auto-archived**: this plan was swept on 2026-07-04 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add the per-plan split-criteria evaluator, breakdown renderer, and drift note

## Summary

Adds the per-plan half of `plan_tool/split_criteria.py`: an evaluator that runs the tool's existing structural-split detectors against one plan and maps each result back to a catalog criterion, a renderer that prints the per-criterion breakdown (fires?/which steps/severity/one-line reason), and a drift note that diffs the current breakdown against the most recent recorded run whose `plan_fingerprint` differs. The evaluator writes **no new detection logic** — it orchestrates `granularity.assess_granularity` (altitude 2), `convergence_diagnosis` (altitude 3), and the `distill_thresholds.py` byte advisories (altitude 1), then reuses step 1's `telemetry.record_plan_criteria_breakdown` to record the run tagged with `review_persistence.compute_plan_fingerprint`. On green, `evaluate_split_criteria(plan, plan_path=..., repo_root=...)` returns a breakdown mapped to the step-2 catalog ids, the per-plan renderer prints it (plain text when color is off), the drift note reads prior `plan-criteria-breakdown` events and reports what changed, and every rendered threshold still traces to its live constant.

## Table of Contents

- [Summary](#summary) — what the step adds and the observable result on green
- [Why](#why) — the missing per-plan surface and drift capture this step fills
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step edits (both created in step 2)
- [Implementation](#implementation) — the evaluator's detector→criterion mapping, the breakdown renderer, the drift diff, and the telemetry write
- [Tests](#tests) — unit tests in tests/test_split_criteria.py plus the drift-guard and drift-diff cases
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — fingerprint, telemetry, and JSONL docs relevant to this step
- [Deferred](#deferred) — the CLI wiring, operator docs, and cross-plan aggregation owned by later steps

## Why

The tool decides how to split work at three altitudes, but every criterion only fires *inside* another command, and step 2 built only the plan-independent legend. Nothing yet answers "why is *this* plan shaped this way?" or captures the per-criterion result over time so decomposition drift is detectable. This step lands that per-plan surface: it runs the criteria that already exist against a given plan, maps each result onto the step-2 catalog, and records the breakdown tagged with the plan's fingerprint. Step 1 landed the `record_plan_criteria_breakdown` recorder and step 2 landed the catalog + legend; this step is the consumer that turns both into a working per-plan evaluation, so step 4 only has to wire a thin CLI handler around it. Landing the evaluator + drift note before the CLI keeps the evaluation logic reviewable on its own, matching how `plan-tool convergence` leans on `convergence_diagnosis` behind a thin `cli/convergence_cmd.py`.

## Files (creates vs edits)

- **New files:** none. Both files are created in step 2.
- **Existing files (edits only):**
  - `plan_tool/split_criteria.py` — add the evaluator (`evaluate_split_criteria`), the per-plan breakdown renderer, the drift-diff helper, and a small result record (`CriterionResult` / `PlanCriteriaBreakdown`). The step-2 catalog (`SPLIT_CRITERIA`, `SplitCriterion`) and legend renderer (`render_split_criteria`) stay unchanged in shape; the per-plan mode reads the same catalog.
  - `tests/test_split_criteria.py` — add unit tests for the detector→criterion mapping, the per-plan renderer, the drift diff, the telemetry record + read-back, and the read-before-record ordering.

## Implementation

**Foundational logic: orchestrate the existing detectors and map each result back to a step-2 catalog id — never write new detection.** The evaluator is pure orchestration + mapping. It must not copy, re-implement, or refactor any predicate in `plan_tool/granularity.py`, `plan_tool/convergence_diagnosis.py`, or `plan_tool/review.py`. Reuse the same criteria logic those modules own; read it by calling their public functions and mapping their `source`/fork/threshold output onto the catalog `id`s step 2 already reused from them.

**Add one evaluator entry point.** One way: `evaluate_split_criteria(plan: Plan, *, plan_path: Path, repo_root: Path, decisions: Sequence[DecisionEvent] | None = None) -> PlanCriteriaBreakdown`. It builds a per-criterion result for every catalog entry, computes the plan fingerprint once, records the breakdown, and returns the record (renderers take the returned object). Keep the return a frozen dataclass — suggest `PlanCriteriaBreakdown` holding `plan_slug`, `plan_fingerprint`, an optional `code_fingerprint`, and an ordered list of `CriterionResult` (`criterion_id`, `fired: bool`, `severity: str | None`, `step_ids: tuple[int, ...]`, `reason: str`). This is an in-memory record built and consumed inside the command; it is **never** serialized to a sidecar (only the telemetry event is), so it is correctly out of `DATA_CONTRACT.md`.

**Map each altitude through its existing detector:**

- **Altitude 2 (create-time granularity smells) — `granularity.assess_granularity`.** Call `assess_granularity(plan, stage="create", evidence=GranularityEvidence(), invoker=None)` (`plan_tool/granularity.py`). The deterministic split/merge battery reads only plan structure and never shells out, so pass no invoker. Partition the returned recs by `source`: `GRANULARITY_SPLIT_SOURCE` recs map to a split-criterion id via `granularity.split_predicate_key(rec)` (at `stage="create"` with an empty `GranularityEvidence()` this is always one of the three deterministic keys — `"mixed-verbs"` / `"two-clauses"` / `"multi-area"`; the prose `"mixed-step"` kernel is lifted only at `stage="detail"` from populated `evidence.detail_bodies`, so it never fires here); `GRANULARITY_MERGE_SOURCE` recs map to the catalog's `merge` criterion (step 2 now provides that id — plus a `split-safety` id and a `mixed-step` id). The catalog's **`mixed-step`** criterion is `deterministic=False`: never map a create-stage rec onto it — instead render it in the breakdown as **"not evaluated (Claude-judged)"** (it appears in the row list marked skipped, so the breakdown still names every catalog id without claiming a no-Claude evaluation it can't do). Collect each fired criterion's `rec.step_id`s and carry `rec.severity` straight through (deterministic recs are `_GRANULARITY_SEV = "info"`).
- **Altitude 3 (post-review step split / spin) — `convergence_diagnosis`.** Chain `load_report_history(plan_path)` → `diagnose_convergence(history)` → `classify_fork(diagnosis)` (`plan_tool/convergence_diagnosis.py`). The fork arm names the criterion id (`FORK_LOCALIZED` / `FORK_SCOPE_OUT` / `FORK_STRUCTURAL`); `fired` is true when the verdict is `VERDICT_SPINNING` and the fork is not the no-op arm. Use `ForkRecommendation.step_focus` for the step ids and the fork's `regions` (each `RegionTrend.last_severity`) for severity. When history is `no-history` / `insufficient-history`, mark the altitude-3 criteria not-fired with a short "not enough saved runs" reason — do not raise.
- **Split-safety (altitude 3, deterministic) — the read-only safe-gate + scope-out blockers.** For each step, call `detail._split_is_safe(plan, step_id)` and compute `scope_out.py`'s blockers (both read-only — no mutation, no Claude). Map the result onto the catalog's `split-safety` id: `fired` when a step is *not* split-safe (a downstream non-`PENDING`/run-started step blocks a split, or a scope-out blocker applies), carrying those step ids and a one-line reason. This delivers the split-safety signal the plan's Architecture + AC2 promise; it is deterministically-evaluable (its *result* is computable without Claude even though its *rule* is control-flow prose).
- **Altitude 1 (plan too big → many plans) — `distill_thresholds.py`, data-backed only.** Surface `DISTILL_SKIP_BELOW_BYTES` (16384) and `DISTILL_ADVISE_ABOVE_BYTES` (262144) as pinned **reference values**, not a live comparison against the plan file. These constants gate the create-time **seed** (a big seed often describes multiple plans); the distill decision already ran on the seed before any plan exists for `split-criteria` to read, and an authored plan file's bytes (`plan_path.stat().st_size` — frontmatter + steps + prose) are **not** the seed the threshold judges, so do not drive an altitude-1 result off a plan-file-byte comparison against them. Render the two byte advisories with that caveat. `len(plan.steps)` is a step count, not a byte size; do not compare it against the `DISTILL_*_BYTES` constants and do **not** surface a step-count signal — it has no threshold, basis, or catalog id, and the plan's Architecture drops it. The distill *split* decision itself is Claude-judged; render it as **unpinned prose** from the catalog (the two-tier rule) — do not try to reproduce the judgment here.

**Add the per-plan breakdown renderer as a sibling of the legend renderer.** Keep step 2's `render_split_criteria()` no-arg legend signature unchanged (step 2's tests pin it). One way: a new `render_plan_breakdown(breakdown: PlanCriteriaBreakdown, *, drift: CriteriaDrift | None = None, color: bool | None = None)` that walks the catalog in order and prints one line per criterion — fired/not, the step ids, severity, and the catalog's one-line description — with the drift note appended when present. Reuse `plan_tool/style.py`'s `color_enabled` / `paint` for TTY-aware color exactly as the legend renderer does; the plain-text form (color off) is the test surface. Both modes render from the same `SPLIT_CRITERIA` catalog so a criterion is described once.

**Add the drift note as a diff over prior recorded breakdowns.** Define "drift" precisely: same `plan_slug`, a **changed** `plan_fingerprint`, and a changed fired-criteria result set. One way: `compute_criteria_drift(current: PlanCriteriaBreakdown, decisions: Sequence[DecisionEvent]) -> CriteriaDrift`. Filter `decisions` to `kind="plan-criteria-breakdown"` events for the same `plan_slug`, take the most recent one whose `context["plan_fingerprint"]` differs from `current.plan_fingerprint`, and diff the fired-criteria sets: which criteria newly fire, which stopped firing, which changed their step ids. **Normalize each side's step-id set to one representation before comparing** — the in-memory `current` carries `step_ids: tuple[int, ...]` while a recorded event carries `step_ids: list[str]` (step 1's row contract), so map both to a common form (e.g. a `set` of `str`) before diffing; otherwise `(1, 2)` never equals `["1", "2"]` and every still-firing criterion is falsely reported as step-id drift. Drift must reflect a real change, not the int-vs-str record shape. When there is no prior event or none with a different fingerprint, the note says "no prior version to compare" rather than claiming drift. Do **not** over-claim a live-status round-trip — this is a fingerprint diff over recorded breakdowns, nothing more.

**Record the breakdown through step 1's recorder, best-effort.** Call `telemetry.record_plan_criteria_breakdown` (owned by step 1) with `plan_fingerprint = review_persistence.compute_plan_fingerprint(plan_path)`, the optional `code_fingerprint` taken from the **most-recent saved report** in the `load_report_history(plan_path)` already loaded for altitude 3 — and **omitted** when history is absent (the recorder stores `code_fingerprint` only when passed), so two evaluations of the same code state tag consistently rather than sometimes-present/sometimes-absent — and the per-criterion result rows (`criteria`) — the recorder derives `criteria_count`/`fired_count` internally, so the caller passes no counts. At this handoff convert each result to step 1's telemetry row shape: the in-memory `CriterionResult.step_ids` is `tuple[int, ...]`, but step 1's row contract is `step_ids: list[str]`, so map `int → str` (`[str(sid) for sid in result.step_ids]`) before passing `criteria` — do not hand the raw int tuple to the stdlib-only recorder. The recorder is already best-effort and never raises into the caller, so add no second `try/except`. Ordering constraint that must hold: **read the prior decisions before recording the current event** — either read `read_decisions(repo_root)` at the top of `evaluate_split_criteria` (pass it into `compute_criteria_drift`), or record after computing drift. Recording first would make the run diff against a different-fingerprint precedent correctly (the just-written event shares the current fingerprint and is excluded by the filter), but reading first keeps the drift computation independent of write timing and is the clearer invariant to test.

**Constraints and gotchas:**
- **Keep `split_criteria.py` cycle-safe.** At module top level it imports `granularity`, `convergence_diagnosis`, `review_persistence`, `telemetry`, `distill_thresholds`, `schema`, and `style` — all leaves below it — exactly as the CLI layer does. Nothing in those modules imports it back. `telemetry.py` stays a stdlib-only leaf; convert plan/finding types to JSON primitives before handing them to the recorder.
- **Split-safety needs two heavier modules — import them lazily.** `detail._split_is_safe` (in the `detail` orchestrator) and `scope_out.py`'s blocker computation are deterministic/read-only but live in heavier modules. Import them **inside the split-safety branch** (a function-body import), NOT at module top level, so `split_criteria.py` stays light to import and no cycle forms through the detail/scope-out orchestrators.
- **Do not import `create.py`.** Altitude-1 thresholds live in the `distill_thresholds.py` leaf; the split decision is Claude-judged prose, so no heavy orchestrator import is needed at all.
- **Reuse severity from `review._SEVERITY_BANNER_ORDER` if you sort criteria by severity** — it is the full `critical→info` vocabulary. Never reuse `convergence_diagnosis._SEVERITY_RANK`, which omits `nit`/`info` and `KeyError`s on them.
- **The evaluator is read-only w.r.t. plan and code.** The one non-read effect is the telemetry append; keep it best-effort, exactly as `plan-tool convergence` keeps `record_convergence`.

## Tests

Add to `tests/test_split_criteria.py` (created in step 2). Enumerate the unit tests with the implementation; every new test must be green before this step is done.

- `test_evaluator_maps_granularity_split_to_catalog_id` — a plan with a mixed-verb step yields a fired `mixed-verbs` criterion result with that step's id.
- `test_evaluator_maps_granularity_merge_to_catalog_id` — a plan tripping a merge signal yields a fired merge criterion result.
- `test_evaluator_maps_convergence_fork_to_catalog_id` — a seeded spinning report history yields a fired `localized`/`scope-out`/`structural` criterion matching `classify_fork`.
- `test_evaluator_no_history_marks_altitude3_not_fired` — a plan with no saved reports marks altitude-3 criteria not-fired without raising.
- `test_evaluator_altitude1_surfaces_distill_thresholds` — the altitude-1 output surfaces `DISTILL_SKIP_BELOW_BYTES` / `DISTILL_ADVISE_ABOVE_BYTES` as reference values (with the seed-not-plan-file caveat), not a plan-file-byte comparison against them.
- `test_evaluator_maps_split_safety` — a plan with a step that is not split-safe (a downstream non-`PENDING`/run-started step) yields a fired `split-safety` criterion carrying that step's id, via `detail._split_is_safe` / `scope_out` blockers (no Claude).
- `test_evaluator_marks_mixed_step_not_evaluated` — the `mixed-step` (`deterministic=False`) criterion appears in the breakdown marked "not evaluated (Claude-judged)" and never fires, even on a plan whose detail fuses refactor+feature.
- `test_evaluator_code_fingerprint_from_latest_report_or_omitted` — with a saved report present, the recorded event's `code_fingerprint` equals the most-recent report's; with no history, the key is omitted.
- `test_breakdown_renderer_plain_text` — with color off, the renderer prints one line per catalog criterion in catalog order (fired flag, step ids, severity).
- `test_breakdown_renderer_covers_every_catalog_criterion` — the rendered output names every `SPLIT_CRITERIA` id (no criterion silently dropped).
- `test_drift_note_reports_changed_criteria` — a prior event with a different `plan_fingerprint` and a different fired set produces a drift note listing what changed.
- `test_drift_note_absent_without_prior_version` — no prior event → the note says "no prior version to compare", not drift.
- `test_drift_note_ignores_same_fingerprint_events` — a prior event with the *same* fingerprint is not treated as a precedent.
- `test_evaluator_records_breakdown_through_telemetry` — after `evaluate_split_criteria`, `read_decisions` returns one `plan-criteria-breakdown` event carrying the plan fingerprint and per-criterion rows (assert through `read_decisions` with a pinned clock, never raw jsonl bytes).
- `test_evaluator_reads_before_recording` — the current run's drift diffs against the prior different-fingerprint event, not against its own just-written event.
- `test_evaluator_is_best_effort_never_raises` — pointing `repo_root` at a path that can't hold the file returns without raising (mirrors `test_record_is_best_effort_never_raises`).
- `test_evaluator_spends_no_claude` — the autouse real-backend gate is not tripped (no `invoker` reaches a real backend; `assess_granularity` called with `invoker=None`).
- `test_rendered_thresholds_trace_to_live_constants` — extend step 2's drift-guard: the altitude-1 byte thresholds in the per-plan output equal the imported `DISTILL_*` constants, not re-typed literals.

## Acceptance criteria

- `evaluate_split_criteria(plan, plan_path=..., repo_root=...)` returns a `PlanCriteriaBreakdown` whose criterion ids are all drawn from the step-2 catalog.
- A plan with a mixed-verb / two-clause / multi-area step produces the matching fired criterion with the correct step ids.
- A seeded spinning report history produces the fork criterion `classify_fork` selects; a plan with no saved reports marks altitude-3 criteria not-fired without raising.
- A step that is not split-safe produces a fired `split-safety` criterion (via `detail._split_is_safe` / `scope_out` blockers, no Claude); the `mixed-step` criterion is always marked "not evaluated (Claude-judged)" and never fires.
- The recorded event's `code_fingerprint` is the most-recent saved report's when history exists and is omitted when it does not.
- The per-plan renderer prints one line per catalog criterion in catalog order and names every criterion id when color is off.
- A prior recorded run with a different `plan_fingerprint` and a different fired set yields a drift note; no prior version yields "no prior version to compare".
- After an evaluation, `read_decisions(repo_root)` returns one `plan-criteria-breakdown` event tagged with `compute_plan_fingerprint(plan_path)` and the per-criterion rows.
- The evaluation spends no Claude (the autouse backend gate stays green) and raises nothing when the telemetry write can't land.
- The altitude-1 byte thresholds in the output equal the live `DISTILL_SKIP_BELOW_BYTES` / `DISTILL_ADVISE_ABOVE_BYTES` constants; the step-2 legend drift-guard tests stay green.
- `plan_tool/split_criteria.py` imports only leaves below it and is never imported back by `granularity` / `convergence_diagnosis` / `review` / `telemetry`.

## References

- [hashlib — Secure hashes and message digests (Python docs)](https://docs.python.org/3/library/hashlib.html) — the primitive behind `compute_plan_fingerprint`, the plan hash that tags each breakdown and drives the drift diff.
- [JSON Lines (jsonl) format specification](https://jsonlines.org/) — the newline-delimited format `telemetry.py` appends to `.plan-tool/telemetry/decisions.jsonl`, one `DecisionEvent` per line.
- [json — JSON encoder and decoder (Python docs)](https://docs.python.org/3/library/json.html) — `json.dumps` of the `DecisionEvent` context (per-criterion results, fingerprints, counts) written to the telemetry sidecar.

## Deferred

- **The `plan-tool split-criteria [<plan>]` CLI command** — the thin handler `plan_tool/cli/split_criteria_cmd.py`, parser wiring, and `docs/cli/split-criteria.md` are step 4. This step delivers the evaluator + renderers the CLI calls.
- **Operator guide docs and skill routers** (README / RUNBOOK / USE_CASES / both `integrations/*/SKILL.md`) — step 5.
- **`CAPABILITIES.md` entry + `capability_catalog` orphan-subcommand check** — lands with the CLI in step 4.
- **The full #72 cross-plan aggregation / tuning dashboard** — this step ships single-plan capture plus a per-plan drift diff; broad over-time tuning stays in #72.
- **Any plan mutation or auto-fix** — recommend-only, like the granularity advisor; the actuators remain `plan-tool split` / `merge` / `scope-out`.
- **Refactoring the deciders' control flow** — the evaluator orchestrates the existing detectors; it does not restructure `granularity` / `convergence_diagnosis` / `review` to serve this read-only surface.
- **`DATA_CONTRACT.md` changes for `PlanCriteriaBreakdown`** — it is an in-memory, within-run record, never serialized; only step 1's telemetry event schema is documented there.
