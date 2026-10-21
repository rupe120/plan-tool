# Forward seed — advisory coverage for legacy generic walks

## Observed gap

`plan-tool review-walk` can load a saved completeness review and apply its
recommendations through the generic walk without traversing the dedicated
`completeness-apply` presentation path. The bounded arm-clustering advisory
therefore remains absent at that legacy entrypoint.

## Decision needed

Decide whether generic walks should reject completeness sidecars, delegate
them to `completeness-apply`, or render a read-only advisory before their
existing dispatch. Any option changes a generic routing contract and must be
designed separately from the non-executable advisory payload.

## Constraints

- Do not reuse advisory data as a recommendation target or generic action.
- Preserve the source-snapshot freshness rule and suppress stale presentation.
- Preserve the user-visible override policy without adding an automatic gate.
- Audit serial, parallel, generic-walk, and direct-review entrypoints together
  before selecting a routing change.

## References

- `plan_tool/review_walk.py` — shared generic walk that currently bypasses the
  completeness-specific presentation route.
- `plan_tool/cli/completeness_cmd.py` — dedicated completeness-apply entrypoint
  whose advisory presentation establishes the contrast under review.
