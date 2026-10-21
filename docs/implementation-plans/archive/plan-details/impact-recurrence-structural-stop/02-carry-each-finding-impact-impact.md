# Step 2 — Carry each finding's impact and impact provenance into RunFinding

## Summary

Widen `plan_tool/convergence_diagnosis.py`'s `RunFinding` so it keeps each persisted finding's `Recommendation.impact` plus a small provenance token saying whether that impact was actually recorded or is missing (legacy/untagged evidence). `_finding_from_recommendation` fills both, mirroring how it already fills `purity_verdict_provenance` for `granularity-split` findings. No persistence-code change is needed: `plan_tool/review_persistence.py` round-trips `Recommendation` generically through `asdict` / `Recommendation(**r)`, so `impact` already survives a save/load cycle — this step pins that with a test instead of editing the schema. On green, step 3's classifier can ask "is this region's high impact real evidence or an absent field?" without re-reading sidecars.

## Table of Contents

- [Summary](#summary) — what the step does and the observable result.
- [Why](#why) — why impact must survive history normalization.
- [Input](#input) — the persisted contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — per-file edit list.
- [Implementation](#implementation) — the new fields, provenance rule, and constraints.
- [Tests](#tests) — the unit tests to add and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes.
- [References](#references) — the docs worth reading for this step.
- [Deferred](#deferred) — what this step deliberately leaves alone.

## Why

`Recommendation` carries an `impact` triage level (`low` / `medium` / `high`, `None` when untagged), but `convergence_diagnosis._finding_from_recommendation` drops it when it flattens a saved report into `RunFinding`. Step 3's impact-recurrence classifier reads normalized history, not raw sidecars, so today it has no way to see impact at all. Impact is also independent of severity — a high-impact finding can normalize to advisory `nit` or `info` — so severity is not a stand-in. The plan's evidence rule needs a second fact beyond the value itself: a row written before this ships has no impact tag, and "untagged" must read as *unknown*, not as *low impact*, so a legacy row can never start or extend a recurrence streak.

## Input

- **`plan_tool/review.py: Recommendation`** — reads `impact: Optional[str]`, populated by `check_plan_audit` and the reconcile extractors from the inline `(impact=…, complexity=…)` tag via `_split_triage_tags` (which already lowercases). `None` means the producer emitted no tag.
- **`plan_tool/review_persistence.py: save_review` / `load_review`** — the saved-review sidecar. Recommendations serialize with `asdict(r)` and rebuild with `Recommendation(**r)`, so any dataclass field with a default round-trips with no schema-specific code. A legacy row simply omits the key and the default applies.
- **Step 1's outcome** — the shared history helpers in `plan_tool/convergence_diagnosis.py` are public; this step widens the finding model those helpers hand out, and does not change their signatures.

Verification limit: no sidecar in the repo predates the field, so "legacy row" behavior is proven by writing a JSON payload with the key removed, not by finding one on disk.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — add two fields to `RunFinding`, add the provenance token constants, fill both in `_finding_from_recommendation`, and update the `RunFinding` docstring/whitelist comment so the persisted-field list stays honest.
  - `tests/test_convergence_diagnosis.py` — unit tests for the normalization rule and for the default on a directly-built `RunFinding`.
  - `tests/test_review_persistence.py` — round-trip test that `impact` survives `save_review` → `load_review`, plus a legacy-row test where the key is absent.

## Implementation

**What must be true when the step is done**

- `RunFinding` carries the finding's impact and a provenance token, both with defaults so existing direct constructions in tests and later steps still work.
- `_finding_from_recommendation` is the single place that decides provenance; nothing else infers it.
- An absent or empty `Recommendation.impact` yields the *unknown* token, never a fabricated level.
- `plan_tool/convergence_diagnosis.py` stays a cycle-free leaf — no new imports beyond what it already has.

**Recommended shape**

- Add to `RunFinding`:
  - `impact: Optional[str] = None` — the raw persisted level, kept as-is (`low` / `medium` / `high`). Don't re-normalize case here; the producer's `_split_triage_tags` already lowercases, and a second normalizer is a place for the two to drift.
  - `impact_provenance: str = IMPACT_PROVENANCE_UNKNOWN` — how the impact value was obtained.
- Add two module-level constants beside `HISTORY_KINDS`, named so a reader grasps them without a glossary. One way: `IMPACT_PROVENANCE_RECORDED = "recorded"` and `IMPACT_PROVENANCE_UNKNOWN = "unknown"`. Export them by name so step 3 imports the tokens instead of retyping string literals.
- In `_finding_from_recommendation`, set provenance to *recorded* only when `rec.impact` is a non-empty string, otherwise *unknown*; pass `rec.impact` straight through as `impact`. Treat `""` the same as `None` — an empty tag is not evidence.
- **Default direction matters.** The dataclass default for `impact_provenance` must be *unknown*, not *recorded*. A hand-built `RunFinding` fixture in step 3 that forgets the field must not read as real evidence; forcing the fixture to opt in is the safe direction.
- **Keep provenance kinds separate.** `purity_verdict_provenance` describes how a MIXED-STEP purity verdict was obtained (`fresh` / `exact-cache` / `below-floor-reuse` / legacy `unknown`) and applies only to `granularity-split` findings. Impact provenance is a different question on every finding. Don't fold them into one field or one helper even though both use the word "unknown".
- **Rejected alternative:** adding an explicit `impact` column to the saved-review JSON writer in `plan_tool/review_persistence.py`. Unnecessary — the generic `asdict` / `Recommendation(**r)` seam already carries it, and a schema-specific branch there would be a second place to keep in sync.

**Shared-logic sweep**

The same "flatten a persisted finding into a smaller analysis model" logic exists in `plan_tool/telemetry_analysis.py`, which consumes `convergence_diagnosis`'s normalized history for saved-audit-finding calibration. It reads the model this step widens, so it inherits the new fields for free and needs no edit here; a calibration cohort keyed on impact provenance is separate work and stays out of this step's footprint. `plan_tool/convergence.py:is_blocking_impact` also reads `Recommendation.impact`, but it is a live-loop policy predicate over raw recommendations, not history — leave it untouched (widening its callers is named out of scope in the plan).

## Tests

In `tests/test_convergence_diagnosis.py`:

- `test_finding_carries_recorded_impact` — a `Recommendation` with `impact="high"` normalizes to `impact == "high"` and provenance *recorded*.
- `test_finding_without_impact_is_unknown_provenance` — a `Recommendation` with `impact=None` normalizes to `impact is None` and provenance *unknown*.
- `test_empty_impact_string_is_not_evidence` — `impact=""` normalizes to provenance *unknown*, not *recorded*.
- `test_run_finding_defaults_to_unknown_impact_provenance` — a directly-built `RunFinding` with no impact arguments defaults to `impact is None` and provenance *unknown*.
- `test_history_load_preserves_impact_through_snapshot` — a saved report whose recommendations carry mixed impact values loads through `load_report_history` with per-finding impact and provenance intact (proves the field survives the whole `SavedReview` → `RunSnapshot` → `RunFinding` path, not just the leaf helper).
- `test_impact_provenance_is_independent_of_purity_provenance` — a high-impact `granularity-split` finding gets both provenance fields set independently (purity `unknown` for a legacy purity verdict, impact *recorded*).

In `tests/test_review_persistence.py`:

- `test_impact_round_trips_through_saved_review` — `save_review` with an `impact="high"` recommendation then `load_review` returns `impact == "high"`.
- `test_legacy_recommendation_without_impact_loads` — a sidecar JSON with the `impact` key removed from a recommendation object loads without raising and yields `impact is None`.

**Test-creation order (feature step):** these tests land with the implementation in the same change. Every one of them (approx. 8 tests) must be green — `uv run pytest tests/test_convergence_diagnosis.py tests/test_review_persistence.py -q` — before the step is done, and the full suite must stay green.

## Acceptance criteria

- `plan_tool/convergence_diagnosis.py: RunFinding` has an `impact` field defaulting to `None` and an impact-provenance field defaulting to the *unknown* token.
- The two provenance token constants are module-level names in `plan_tool/convergence_diagnosis.py`, importable by name.
- `_finding_from_recommendation` returns provenance *recorded* only for a non-empty `Recommendation.impact`, and *unknown* for `None` or `""`.
- `load_report_history` yields findings whose `impact` matches the value saved in the sidecar.
- `save_review` → `load_review` preserves `impact`, and a sidecar missing the key loads with `impact is None` and raises no error.
- `plan_tool/review_persistence.py` is unchanged.
- `purity_verdict_provenance` behavior is unchanged: still set only for `granularity-split` findings, still `unknown` for a legacy purity verdict.
- All new tests pass and the existing suite stays green.

## References

- [Python `dataclasses` — Data Classes](https://docs.python.org/3/library/dataclasses.html) — `frozen=True`, field defaults, and `asdict`, which is exactly why a defaulted optional field round-trips through the saved-review sidecar with no persistence edit.
- [Python `json` — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — how the sidecar is written and re-read, relevant to the legacy-row test that removes a key from the persisted object.
- [RFC 8259 — The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259) — the value-type rules the persisted impact string must conform to.
- [pytest — How to use temporary directories and files (`tmp_path`)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the hermetic fixture the save/load round-trip tests write into.

## Deferred

- **Backfilling impact onto sidecars written before this step** — legacy rows stay *unknown* provenance; a migration pass over historical sidecars is tracked in the plan's Deferred section.
- **The recurrence classifier that consumes these fields** — owned by step 3 (`plan_tool/impact_recurrence.py`), which depends on this step's model.
- **Any change to `convergence.is_blocking_impact` or its calibrated policy** — named out of scope by the plan; this step only records evidence, it makes no blocking decision.
- **Calibration cohorts keyed on impact provenance in `plan_tool/telemetry_analysis.py`** — that module reads the widened model without edits here; a new cohort dimension is separate work.
- **Normalizing or validating impact values on read** — the producer's triage-tag parser already lowercases and constrains the level set; a second validator in the history reader would be a place for the two to drift.
