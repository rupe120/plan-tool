> **Auto-archived**: this plan was swept on 2026-06-27 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Expose split predicate recovery helper from the granularity advisor

## Summary

Add the feature half of the predicate-key work: an exported vocabulary and a
`split_predicate_key(rec)` helper that maps a `granularity-split`
`Recommendation` back to its stable predicate key without parsing human prose.
This step builds on step 1's constants and adds the new behavior later create
telemetry consumes.

## Table of Contents

- [Summary](#summary) — what this feature ships
- [Why](#why) — why create telemetry needs prose-free predicate recovery
- [Files (creates vs edits)](#files-creates-vs-edits) — the files touched
- [Implementation](#implementation) — exported vocabulary and helper behavior
- [Constraints and Gotchas](#constraints-and-gotchas) — matching and ownership rules
- [Tests](#tests) — helper-recovery and non-split cases
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — local code and stdlib references
- [Deferred](#deferred) — create-side consumers left to later steps

## Why

Step 1 makes the deterministic predicate values importable, but create-side
telemetry still receives ordinary `Recommendation` objects from
`assess_granularity`. Those recommendations do not carry a predicate field. A
caller needs a prose-free way to recover the key so it can build
`predicate_counts` reliably.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/granularity.py` — add `SPLIT_PREDICATE_MIXED_STEP`, exported
    vocabulary containers, and `split_predicate_key(rec)`.
  - `tests/test_granularity.py` — add helper-recovery tests for deterministic
    split recs, prose MIXED-STEP recs, and non-split recs.

## Implementation

Add a prose-kernel key and exported vocabulary:

- `SPLIT_PREDICATE_MIXED_STEP = "mixed-step"`
- `DETERMINISTIC_SPLIT_PREDICATE_KEYS = frozenset({...})`
- `SPLIT_PREDICATE_KEYS = frozenset({...})`

The deterministic set contains the three constants from step 1. The full set
also contains `SPLIT_PREDICATE_MIXED_STEP`.

Add:

```python
def split_predicate_key(rec: Recommendation) -> Optional[str]:
    ...
```

The helper returns `None` for any non-`granularity-split` recommendation. For a
deterministic split rec, recover the key by re-deriving the ids this module
already owns:

```python
for key in DETERMINISTIC_SPLIT_PREDICATE_KEYS:
    expected = _make_rec_id(
        rec.step_id,
        GRANULARITY_SPLIT_SOURCE,
        f"split:{key}:{rec.step_id}",
    )
    if rec.id == expected:
        return key
```

For a `granularity-split` rec that matches no deterministic key, return
`SPLIT_PREDICATE_MIXED_STEP`. The producer set is closed: the three
deterministic detectors plus `parse_mixed_step_findings`. This avoids parsing
the title/body and keeps the prose wording free to change.

## Constraints and Gotchas

- **Do not parse recommendation prose.** The whole reason for the helper is to
  avoid title/body wording dependencies.
- **Do not add a field to `Recommendation`.** That dataclass is a wider review
  contract. This helper is sufficient for telemetry and keeps the change local
  to `granularity.py`.
- **Keep `granularity.py` cycle-free.** Reuse the already-imported
  `Recommendation` and `_make_rec_id`; do not import `telemetry`, `create`, or
  CLI modules.
- **Treat no-match split recs as prose `mixed-step`.** At create stage only the
  deterministic detectors fire, but detail-stage mixed-step findings share the
  `granularity-split` source and need a stable key too.

## Tests

Add tests in `tests/test_granularity.py`:

- `test_exported_split_predicate_set_is_exact` pins the deterministic and full
  vocabulary sets.
- `test_mixed_verbs_rec_recovers_its_key`.
- `test_conjoined_clauses_rec_recovers_its_key`.
- `test_unrelated_areas_rec_recovers_its_key`.
- `test_prose_mixed_step_rec_recovers_mixed_step_key`.
- `test_non_split_rec_returns_none`.
- `test_every_deterministic_split_rec_maps_to_a_known_key`.

### Test-creation order (feature step)

This is a feature step. Add the helper tests with the implementation and run
`uv run pytest tests/test_granularity.py -q`.

## Acceptance criteria

- `plan_tool/granularity.py` exports the deterministic split predicate set and
  the full split predicate set.
- `split_predicate_key(rec)` returns the matching deterministic key for each
  deterministic `granularity-split` rec.
- `split_predicate_key(rec)` returns `SPLIT_PREDICATE_MIXED_STEP` for prose
  MIXED-STEP recs.
- `split_predicate_key(rec)` returns `None` for non-split recommendations.
- Recovery reads no human title/body prose and does not modify
  `review.Recommendation`.
- New and existing `tests/test_granularity.py` cases pass.

## References

- [dataclasses — Data Classes — Python documentation](https://docs.python.org/3/library/dataclasses.html) — the frozen-dataclass style `Recommendation` follows; relevant for reading rec fields without mutating them.
- [hashlib — Secure hashes and message digests — Python documentation](https://docs.python.org/3/library/hashlib.html) — SHA-256 behavior behind `review._make_rec_id`, explaining why the predicate key cannot be sliced back out of a rec id and must be re-derived.

## Deferred

- **Create-stage `predicate_counts` wiring** — step 4 consumes this helper.
- **Detail-stage telemetry for prose `mixed-step` findings** — helper support
  exists, but no stage records it yet.
