# Proposal seed — clean single feature

Prose the backend turns into a plan via `create`. This seed describes one
self-contained, additive feature with no behavior-preserving refactor mixed
in, so a correct proposal should stay small and type-pure.

## Request

The cart module (`src/cart.py`) computes an order subtotal today. Add support
for a single percentage-off coupon: callers pass a coupon code and percentage,
and the cart applies it to the subtotal to produce a discounted total. Persist
nothing — the discount is computed on demand. Add a small `src/coupons.py`
holding the coupon lookup table and the percentage-clamp logic, and wire
`src/cart.py` to call it. Cover the new path with unit tests.

## Expected labels (answer key)

The proposal scorer reads only this block. All three checks are
set/range comparisons — no LLM judge.

```json
{
  "expected_step_count_range": [1, 2],
  "expected_change_types": ["feature"],
  "expected_dependency_shape": "linear",
  "must_split": false,
  "expected_source_footprint": true,
  "notes": "One additive feature. Every emitted step must be change_type=feature. No refactor step is warranted; a 2-step split (table first, then apply) is acceptable but both halves stay feature and chain linearly."
}
```
