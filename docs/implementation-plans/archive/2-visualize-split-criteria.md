> **Auto-archived**: this plan was swept on 2026-07-04 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Visualize Split Criteria
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add a plan-criteria telemetry recorder and document its decision kind
  files:
  - plan_tool/telemetry.py
  - tests/test_telemetry.py
  - DATA_CONTRACT.md
  - tests/test_data_contract.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/visualize-split-criteria/01-plan-criteria-telemetry-recorder.md
  status: done
- id: 2
  title: Build the split-criteria catalog and legend renderer
  creates:
  - plan_tool/split_criteria.py
  - tests/test_split_criteria.py
  allowed_mentions:
  - plan_tool/cli/split_criteria_cmd.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/visualize-split-criteria/02-build-split-criteria-catalog-legend.md
  status: done
- id: 3
  title: Add the deterministic criteria evaluator and breakdown renderer (altitudes
    1-3)
  complexity: high
  change_type: feature
  enforce_test_authoring: false
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/visualize-split-criteria/03-deterministic-criteria-evaluator.md
  status: done
  status_note: 'test-authoring gate exempted: the evaluator''s tests (evaluate_split_criteria,
    14 assertions in tests/test_split_criteria.py) were authored during step 2''s
    over-delivering call, so step 3''s own call touched no test file. Deliverable
    is complete and green (committed aec478f); marked done directly rather than re-running
    a completed step. See BACKLOG #87: step 2 absorbed step 3 (granularity-merge).'
- id: 4
  title: Add split-safety as two separate signals (split-safe and scope-out-blocked)
  complexity: high
  change_type: feature
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/visualize-split-criteria/04-split-safety-two-separate-signals-split.md
  status: done
- id: 5
  title: Add fingerprint-tagged telemetry and the drift diff (plan-text vs history-driven)
  complexity: high
  change_type: feature
  enforce_test_authoring: false
  depends_on:
  - 4
  detail: docs/implementation-plans/plan-details/visualize-split-criteria/05-fingerprint-tagged-telemetry-drift-diff.md
  status: done
  status_note: 'test-authoring gate exempted: the drift tests were authored during
    step 4''s over-delivering call, so step 5''s own call touched no test file (same
    2-absorbs-3 pattern, BACKLOG #87). Step 5''s drift impl had an integration bug
    (compute_frontmatter_hash ParseError on a frontmatter-less plan file) fixed
    directly in f587ed3; deliverable is complete and green. Marked done rather than
    re-running a completed step.'
- id: 6
  title: Wire the split-criteria CLI command and its capabilities/reference docs
  files:
  - plan_tool/cli/parser.py
  - plan_tool/cli/app.py
  - plan_tool/cli/__init__.py
  - CAPABILITIES.md
  - docs/cli/README.md
  - tests/test_split_criteria.py
  creates:
  - plan_tool/cli/split_criteria_cmd.py
  - docs/cli/split-criteria.md
  allowed_mentions:
  - plan_tool/split_criteria.py
  complexity: medium
  change_type: feature
  depends_on:
  - 5
  detail: docs/implementation-plans/plan-details/visualize-split-criteria/06-wire-split-criteria-cli-command-its.md
  status: done
  status_note: deliverable complete and verified end-to-end (both command modes render,
    exit 0; full suite green at 4013; capability catalog honest) and committed d4c6ccb.
    The step's own subprocess exited 1 after finishing the work (spurious/terminal,
    not a defect), so the sweep did not auto-advance; marked done directly.
- id: 7
  title: Document split-criteria for operators across the guide docs
  files:
  - README.md
  - RUNBOOK.md
  - USE_CASES.md
  complexity: low
  change_type: non-code
  depends_on:
  - 6
  detail: docs/implementation-plans/plan-details/visualize-split-criteria/07-document-split-criteria-operators.md
  status: done
---
# Visualize Split Criteria

## Overview

Adds `plan-tool split-criteria [<plan>]`, a read-only subcommand that explains why a plan is decomposed the way it is by evaluating it against every **deterministically-evaluable** structural-split criterion the tool already applies across three altitudes (plan-too-big, decompose-into-steps, conditionally-split-one-step). It has two modes selected by an optional plan argument: **legend mode** (no arg) prints the plan-independent reference of all criteria plus the *altitude × disposition* remedy vocabulary; **per-plan mode** (`<plan>` arg) evaluates that plan and prints a per-criterion breakdown (fires?/on which steps/severity/one-line explanation). Both render from one declarative criteria catalog so a criterion is described once. The mixed-step detail-purity criterion is **Claude-authored upstream** — Claude writes its MIXED-STEP findings into each detail file's structural-findings block during `detail` — but per-plan mode **surfaces those already-recorded findings deterministically**: `assess_granularity` at `stage="detail"` never calls the invoker, it lifts the findings from `evidence.detail_bodies` via `parse_mixed_step_findings` (a regex parse), so the evaluator populates `GranularityEvidence(detail_bodies=…)` from the detail bundle and reports any recorded mixed-step findings with no Claude. The one criterion left **not evaluated (Claude-judged)** in the no-Claude per-plan breakdown is the **Altitude-1 distill split** decision — judged live by Claude on the *seed*, before any plan file exists — which the legend renders as prose. Same posture as `plan-tool convergence`: no Claude, no plan/code mutation, exits 0, no `--fail-on-findings`. Each per-plan run records its breakdown to telemetry tagged with the plan's fingerprint so the criteria evaluation can be compared across plan versions to surface drift.

## Problem statement

The tool makes structural-split decisions at three altitudes, but those criteria are scattered across `granularity.py`, `convergence_diagnosis.py`, `review.py`, `create.py` (distill), `launcher.py` (`escalate_to_split`), and `scope_out.py`, and they only fire *inside* other commands (create's change-type loop, detail's purity check, completeness's advisory bucket, `plan-tool convergence`). There is no single surface that answers "why is *this* plan shaped this way?" — no place that runs every criterion against a given plan and explains the resulting decomposition, and nothing captures those per-criterion results over time so drift is detectable. `plan-tool convergence` is the closest prior art (per-plan, read-only, records telemetry) but covers only the convergence/spinning altitude. This generalizes it to all three altitudes and adds the metrics.

## Architecture

**Foundation — declarative criteria catalog:** build the catalog first, each split criterion declared once as data — `id`, `altitude` (1/2/3), human `description`, the live `threshold`/`lexicon`/`source-set` it reads, its `apply_eligibility` (advisory vs actuating), the `detector` it maps to, and its `remedy` (split / merge / scope-out / re-seed). Both legend and per-plan modes render from this catalog; the per-plan evaluator maps each detector finding back to its catalog `id`. This is the single source of truth that avoids building the render twice and closes the prose-drift gap. Additive and leaf-safe — descriptors, **not** predicates; it must not invert the dependency arrow or refactor the correctness-sensitive deciders (`granularity`, `convergence_diagnosis`, `review`) to serve this read-only surface.

**Evaluation layer — reuse existing detectors (orchestration, not new detection):** the per-plan evaluator runs the detectors that already exist and maps their output to catalog criteria, writing no new detection logic. Altitude 2 (create-time granularity smells): `granularity.assess_granularity(plan, *, stage, evidence, invoker=None) -> list[Recommendation]`; the deterministic split/merge detectors (`_title_mixes_refactor_and_feature`, `_title_conjoins_clauses`, `_step_spans_unrelated_areas`, `_merge_signal_identical_file_sets`, `_merge_signal_trivial_refactor_feeding_one_feature`) read only plan structure — no Claude — so the evaluator calls them without an `invoker`. The mixed-step (detail-purity) finding is also no-Claude here: `assess_granularity` never calls the invoker; at `stage="detail"` it lifts already-recorded MIXED-STEP findings from `evidence.detail_bodies` via `parse_mixed_step_findings`, so the evaluator populates `GranularityEvidence(detail_bodies=…)` from the detail bundle and surfaces them deterministically rather than marking the criterion un-evaluable. Altitude 3 (post-review step split / spin): `convergence_diagnosis.load_report_history(plan_path)` → `diagnose_convergence(history)` → `classify_fork(...)` for the spinning/converging verdict, region trends, severities, and fork arm (`FORK_LOCALIZED` / `FORK_SCOPE_OUT` / `FORK_STRUCTURAL`); also surface each step's split-safety — but **as run-state *gates*, not smells that "fire"**, rendered with distinct wording, never the fires? row's "a shape defect is present" polarity. Step 4 (authoritative) produces **two independent per-step signals** that answer different questions and can disagree: **`split-safe`** ("can this step be re-split in place right now?" — `split_safety.split_is_safe`; not-safe means a downstream non-`PENDING`/run-started step *blocks* the sibling split, a healthy default for any in-flight plan, not a decomposition defect) and **`scope-out-blocked`** ("would carving this step out at plan scope be refused right now?" — `scope_out.compute_narrow`'s read-only blockers: inbound dependent, non-canonical numbering). Both are read-only checks (`launcher.py:escalate_to_split` / `split_safety.split_is_safe` and `scope_out.py`'s blockers) rendered as "splittable now?" / "carve-out-able now?" gates, never "split these." Altitude 1 (plan too big → many plans): the distill *split* decision is Claude-judged (render as prose from the catalog), but per-plan surface the data-backed signal — the `distill_thresholds.py` advisories (`DISTILL_SKIP_BELOW_BYTES`, `DISTILL_ADVISE_ABOVE_BYTES`), which gate the create-time **seed** (a big seed often describes multiple plans), not a finished plan file. The distill decision already ran on the seed before any plan exists for `split-criteria` to read, and an authored plan's bytes (frontmatter + steps + prose) are not the seed the threshold judges — so surface these thresholds as reference values with that caveat rather than comparing the plan file's own bytes against them.

**Metrics + drift — telemetry tagged with plan fingerprint:** each per-plan run records the breakdown through `telemetry.py` (#72; best-effort, never raises, appends to `.plan-tool/telemetry/decisions.jsonl`), matching how `plan-tool convergence` calls `record_convergence`. Add a decision kind `"plan-criteria-breakdown"` and a convenience recorder `record_plan_criteria_breakdown` (sibling of `record_convergence` / `record_create_granularity_assessment`). Its `DecisionEvent` `context` carries `plan_fingerprint = review_persistence.compute_plan_fingerprint(plan_path)` (and `code_fingerprint` keyed on the most-recent saved report's `code_fingerprint_present` bool — the never-computed-vs-computed sentinel — not on whether history exists, so a report that never computed a code fingerprint records no `code_fingerprint` key), plus the per-criterion results (criterion `id`, fired bool, severity, the step ids it hit) and counts. Drift is detectable because every event is tagged with the plan hash: for a given `plan_slug`, a changed `plan_fingerprint` accompanied by a changed criteria result-set = the plan was re-decomposed and its criteria evaluation drifted; the report renders a drift note by diffing the latest breakdown against the most recent event with a *different* `plan_fingerprint` (fingerprint precedent: `record_create_granularity_assessment`'s `candidate_fingerprint`). The drift note **excludes the split-safety gates** (both `split-safe` and `scope-out-blocked`): their input is run state, which `compute_plan_fingerprint` does not hash (it digests only plan + detail bytes), so a changed `plan_fingerprint` can never reflect a split-safety change — attributing one to re-decomposition would misreport it.

**New surfaces:** `plan_tool/split_criteria.py` (catalog + evaluator + pure renderers — no Claude, no plan mutation), `plan_tool/cli/split_criteria_cmd.py` (thin handler + `register`, modeled on `cli/convergence_cmd.py`, taking an optional plan positional), the `record_plan_criteria_breakdown` recorder in `plan_tool/telemetry.py`, `tests/test_split_criteria.py`, `docs/cli/split-criteria.md`, a `CAPABILITIES.md` entry. **Reused (verify before extending):** `granularity.assess_granularity`; `convergence_diagnosis` (`load_report_history` / `diagnose_convergence` / `classify_fork` / `render_diagnosis`); `review_persistence.compute_plan_fingerprint`; `telemetry.record_decision` / `DecisionEvent`; `distill_thresholds.py`; `launcher.escalate_to_split` + `split_safety.split_is_safe`; `scope_out.py` blockers; `style.py` (TTY-aware color); `cli/console.py` (next-steps block); `cli/convergence_cmd.py` (command template); `capability_catalog.py` (`orphan-subcommand` guard).

**Import placement — cycle-safe:** `split_criteria.py` sits *above* `granularity` / `convergence_diagnosis` / `review` / `review_persistence` / `telemetry` (it imports them) exactly as the CLI layer does; nothing in those modules imports it back. `telemetry.py` stays a stdlib-only leaf. No heavy orchestrator is imported (`create.py` is not imported — distill thresholds live in the `distill_thresholds.py` leaf, and Altitude-1's split decision is Claude-judged prose).

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python docs)](https://docs.python.org/3/library/argparse.html) — Official reference for add_subparsers/add_parser and optional positional arguments, needed to wire the new read-only `split-criteria [<plan>]` subcommand with its optional plan argument.
- [hashlib — Secure hashes and message digests (Python docs)](https://docs.python.org/3/library/hashlib.html) — Documents sha256/hexdigest hashing, the primitive behind compute_plan_fingerprint used to tag each telemetry breakdown and diff for decomposition drift.
- [JSON Lines (jsonl) format specification](https://jsonlines.org/) — Defines the newline-delimited JSON text format that telemetry.py appends to `.plan-tool/telemetry/decisions.jsonl`, so each DecisionEvent is one valid line.
- [How to mark test functions with attributes (pytest docs)](https://docs.pytest.org/en/stable/how-to/mark.html) — Reference for custom markers used to add the @pytest.mark.integration test that drives main(["split-criteria"]) and the per-plan mode end-to-end.
- [json — JSON encoder and decoder (Python docs)](https://docs.python.org/3/library/json.html) — Covers json.dumps serialization of the DecisionEvent context (per-criterion results, fingerprints, counts) written to the telemetry sidecar.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Any plan mutation** — this surface only explains and advises; the actuators remain `plan-tool split` / `merge` / `scope-out` and the create/detail loops. No auto-split.
- **New detection logic** — reuse the existing detectors; the evaluator is orchestration + mapping.
- **Refactoring the deciders' control flow** — the catalog holds descriptors, not predicates (leaf-safe guardrail); do not invert the dependency arrow to serve this read-only surface.
- **The full #72 cross-plan aggregation/tuning dashboard** — this ships the single-plan fingerprint-tagged capture + a per-plan drift diff; broad over-time tuning surfaces stay in #72.
- **A per-plan *actuating* "auto-fix the decomposition"** — recommend-only, like the granularity advisor.

## Risks

- **Scope creep** — this bundles catalog + legend + evaluator + metrics + report. Acceptable as one plan, but if `create`'s distill judges it ≥2 independent efforts it will propose a split (catalog+legend vs evaluator+metrics+report) — that's a fine outcome; relay it.
- **Telemetry is a write** — appending to `decisions.jsonl` is the one non-read effect; keep it best-effort (never raises into the command), exactly as `convergence`/`record_convergence` do. The command stays read-only w.r.t. the plan and code.
- **Detector→criterion mapping drift** — each detector `source`/finding must map to a stable catalog `id`; the drift-guard test locks the thresholds, and the catalog keys the mapping.
- **Drift semantics** — define "drift" precisely: same `plan_slug`, a *changed* `plan_fingerprint`, and a changed criteria result-set. Don't over-claim a live-status round-trip — it's a fingerprint diff over recorded breakdowns.
- **Private-symbol coupling** — the detectors' constants are underscore-private (`_SEVERITY_RANK`, `_REFACTOR_VERBS`, …). Importing them couples the catalog to internals; the drift-guard turns that into a feature (a rename breaks the test loudly). The catalog is where a public surface, if wanted, is formalized.

## Testing

Unit-test the catalog, both renderers (plain when color off), the evaluator's detector→criterion mapping, and the fingerprint-tagged recorder + drift diff. Include a **drift-guard** test that every rendered threshold traces to its live constant. Add an `@pytest.mark.integration` test driving `main(["split-criteria"])` (legend mode) and `main(["split-criteria", <plan>])` (per-plan mode). Tests live in `tests/test_split_criteria.py`, mirroring `plan_tool/split_criteria.py`. Keep the existing `plan-tool validate` / `capability_catalog` checks and `DATA_CONTRACT.md` drift guard green.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (non-code) — doc-appropriate verification (link/render checks on the updated guides); no unit tests.

## Acceptance criteria

- `plan-tool split-criteria` (no arg) prints the legend — all criteria across the three altitudes + the remedy header — rendered from the declarative catalog; colored on a TTY, plain when piped; no Claude, no mutation, exits 0.
- `plan-tool split-criteria <plan>` prints the per-plan breakdown — per criterion: fires?/on which steps/severity/explanation — by running the existing detectors (`assess_granularity`, `convergence_diagnosis`, the distill/escalate/scope-out signals) and mapping to catalog ids; no new detection logic. Split-safety surfaces as **two** run-state gates, not fires? rows — `split-safe` ("can this step be re-split in place now?") and `scope-out-blocked` ("would carving it out at plan scope be refused now?") — which answer different questions and can disagree.
- Each per-plan run records a `"plan-criteria-breakdown"` telemetry event whose `context` carries `plan_fingerprint` from `compute_plan_fingerprint(plan)` (+ `code_fingerprint` where available) and the per-criterion results — enabling drift detection; the report renders a drift note when the latest breakdown differs from the most recent event with a different `plan_fingerprint`. Best-effort telemetry: a recorder failure never changes the command outcome.
- Legend and per-plan modes render from one catalog (no divergence; drift-guard test passes).
- `plan-tool validate` stays green (owning `CAPABILITIES.md` entry, no `orphan-subcommand`); `docs/cli/` regenerated; `DATA_CONTRACT.md` updated for the new telemetry decision kind (its drift guard passes).
- `plan-tool split-criteria` is **discoverable from the narrative guides** — `README.md`, `RUNBOOK.md`, and `USE_CASES.md` (the guides step 7 updates) each reference it — not just `docs/cli/` and `plan-tool validate`, so step 7's discoverability purpose is asserted by a plan-level criterion.

## Deferred

- **Cross-plan / over-time tuning dashboards** (aggregate every plan's breakdowns to recommend threshold changes) — #72 phase 2–3; this plan ships the single-plan fingerprint-tagged capture + drift diff that motivates it.
- **A generated Mermaid / `docs/SPLIT_CRITERIA.md` companion** sourced from the same catalog.
- **Actuating the recommendation** (auto-running `split`/`merge`/`scope-out` from the breakdown) — stays operator-driven and gated, like the existing structural remedies.
