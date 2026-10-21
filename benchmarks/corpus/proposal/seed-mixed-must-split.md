# Proposal seed — refactor + feature that MUST split

Prose the backend turns into a plan via `create`. This seed deliberately
braids a behavior-preserving refactor together with net-new behavior in a
single described unit. A correct proposal must split it into two type-pure
steps — the refactor FIRST (make the change easy), the feature SECOND (make
the easy change) — with the feature depending on the refactor. This mirrors
`plan_tool/create.py:_apply_step_split` and `_propose_step_split`.

## Request

`src/pricing.py` has a 60-line `compute_invoice()` that inlines line-item
rounding, tax lookup, and total assembly in one function. We want to add
multi-currency support: invoices can be rendered in a requested currency with
per-currency rounding rules. To do that cleanly, first extract the rounding
and tax-lookup logic out of `compute_invoice()` into named helpers WITHOUT
changing any current output (a pure refactor, pinned by the existing tests),
THEN add the currency parameter and per-currency rounding on top of the
extracted helpers. The refactor must land green before the feature builds on
it.

## Expected labels (answer key)

The proposal scorer reads only this block. All checks are set/range
comparisons against the production split contract — no LLM judge.

```json
{
  "expected_step_count_range": [2, 2],
  "expected_change_types": ["refactor", "feature"],
  "expected_dependency_shape": "refactor->feature",
  "must_split": true,
  "expected_source_footprint": true,
  "split_contract": {
    "first_step_change_type": "refactor",
    "second_step_change_type": "feature",
    "second_depends_on_first": true
  },
  "notes": "Exactly two steps. Step order and dependency wiring must match _apply_step_split: a refactor step, then a feature step that depends_on the refactor. A single mixed-type step is a scoring failure even if the prose is otherwise good."
}
```
