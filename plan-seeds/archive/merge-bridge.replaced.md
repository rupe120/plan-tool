> **Replaced**: this file has been superseded by `docs/implementation-plans/2-merge-bridge.md`.
> Preserved here for history; do not edit.

# Merge Bridge Follow-Up Seed

This is a `plan-tool create --from-existing` seed for BACKLOG #94:
**Merge bridge: a walk-surfaced pairwise-merge producer + the deferred merge
actuation**.

## Goal

Finish the deferred merge arm of the structural-remedy auto-bridge work.
The completed `auto-bridge-structural-remedies` plan shipped two reachable
bridges:

- scope-out: `convergence --apply-scope-out` -> `scope_out_step`
- re-ground: reconcile/review walk dispatch -> `reground_bridge`

It deliberately did **not** ship the merge bridge, because no production walk
producer surfaced pairwise `granularity-merge` findings into the saved
recommendation walk. This follow-up must add that producer and then wire the
retained merge bridge design so the merge path is reachable end to end.

## Current State To Preserve

Do not re-plan or re-implement the already shipped bridges.

- `convergence --apply-scope-out` already exists and is out of scope.
- `reground.py`, `mark_steps_done`, and the re-ground walk dispatch already exist
  and are out of scope except where the shared structural-walk gate is extended
  to also recognize merge.
- The merge bridge was intentionally deferred. In
  `docs/implementation-plans/2-auto-bridge-structural-remedies.md`, step 2 is
  parked with `scope: deferred`, and the body states that the merge bridge waits
  for a walk-surfaced pairwise-merge producer.
- The retained detailed design for the primitive lives at
  `docs/implementation-plans/plan-details/auto-bridge-structural-remedies/02-gated-merge-bridge-that-wraps-merge.md`.

## Problem

`granularity.py` can already identify adjacent fragmented dependent steps and
emit a `granularity-merge` recommendation through `_merge_rec`, but today that
signal is not available to the interactive apply walk that
`reconcile-plan-walk` / `review-walk` drive.

The existing producer fires only in surfaces such as create-side change-type
review, detail split-criteria output, and completeness advisory smells. Those
surfaces report advice but do not feed `saved.recommendations` in the
reconcile/review walk. Therefore a gated `merge_bridge` without a walk producer
would be dead production code, exercised only by synthetic tests.

The user-visible gap is still manual actuation: the tool can recognize that two
steps should probably merge, and `plan-tool merge` can do the mutation, but the
operator cannot review/apply that remedy from the same structural walk used for
other auto-bridges.

## Scope Of Work

Let `create` decompose this into implementation steps. The plan must cover these
capabilities in dependency order.

### 1. Add A Walk-Surfaced Pairwise-Merge Producer

Add the missing producer that emits a `merge`-kind `granularity-merge` finding
into the reconcile/review apply-walk surface.

Requirements:

- The producer must create recommendations that the saved recommendation walk can
  load and dispatch. It is not enough to print advisory text in a report section.
- The finding must carry enough structured data for dispatch to recover the
  flagged member ids without reparsing prose.
- It must not conflate pairwise merge with re-ground. Re-ground findings also
  reuse historical `granularity-merge` vocabulary, but their remedy is
  mark-done/re-baseline, not merge.
- It should reuse the existing granularity signal where possible instead of
  inventing a new semantic rule.
- If the signal can produce non-contiguous pairs, the producer must preserve that
  fact so the bridge can recommend-only rather than silently widening to
  `lo..hi`.

Likely files:

- `plan_tool/granularity.py`
- `plan_tool/review.py`
- `plan_tool/review_persistence.py` if recommendation persistence needs an
  additional structured field
- `tests/test_granularity.py`
- `tests/test_review.py`

### 2. Build The Gated Merge Bridge Primitive

Implement the deferred primitive from the parked step detail:
`docs/implementation-plans/plan-details/auto-bridge-structural-remedies/02-gated-merge-bridge-that-wraps-merge.md`.

Requirements:

- Add a frozen result type and bridge function near the existing merge primitives
  in `plan_tool/detail.py`.
- Reuse `_merge_is_safe`, `_confirm_merge`, and `merge_steps`; do not implement a
  new merge/renumber algorithm.
- The default path must recommend only, spend no Claude, and mutate nothing.
- Mutation requires explicit opt-in plus confirm or `-y`, and the safety gate must
  hold.
- The bridge must handle malformed merge sets without leaking `DetailError` into
  the walk. At minimum:
  - fewer than two distinct ids
  - unknown ids
  - non-canonical numbering
  - mixed scope
  - non-contiguous flagged pairs
- The bridge must forward the detail-authoring invoker seam and related
  `merge_steps` passthroughs so tests do not spawn a real backend.

Likely files:

- `plan_tool/detail.py`
- `tests/test_detail.py`

### 3. Add Parseable Merge Suggested Actions

Extend the recommendation shape / action text so merge findings are parseable by
the walk dispatcher.

Requirements:

- Merge and re-ground actions must be distinct. Do not dispatch based solely on a
  historical `granularity-merge` literal.
- The parser must recover the intended ids and action kind from structured data
  or a stable suggested-action format.
- Gapped pair handling must be explicit: a gapped flagged pair is un-actuatable
  and recommends manual operator judgment. The bridge must not auto-widen to the
  full id range, because that can fold unflagged intermediate steps into a merge.

Likely files:

- `plan_tool/granularity.py`
- `plan_tool/review.py`
- `tests/test_granularity.py`
- `tests/test_review.py`

### 4. Wire The Interactive Walk Dispatch

Teach the reconcile/review walk to dispatch merge-kind findings to the merge
bridge.

Requirements:

- Reuse the already shipped structural walk gate where appropriate
  (`--apply-structural`), but consider whether per-remedy flags
  (`--merge`, `--reground`) should be added now or deferred.
- Every unattended / non-TTY / no-opt-in / declined / unsafe / invalid path must
  remain recommend-only.
- Applied merge must halt or invalidate subsequent directive-carrying findings in
  the same walk. Merge renumbers survivors; unlike re-ground mark-done, a later
  saved finding can point at shifted-but-valid step ids after the first merge.
  The plan must specify either:
  - halt-on-first-applied-merge, or
  - a plan-stability key / fingerprint guard that prevents stale directives from
    mutating shifted steps.
- The walk output must tell the operator whether the result was applied,
  recommended, unsafe, or invalid.

Likely files:

- `plan_tool/review_walk.py`
- `plan_tool/cli/review_actions.py`
- `plan_tool/cli/parser.py`
- `plan_tool/cli/reconcile.py`
- `tests/cli/test_review_actions.py`

### 5. Document The Merge Bridge

Update operator docs to describe the completed third bridge and the safety model.

Requirements:

- Document that merge is opt-in and confirm-gated.
- Document that gapped pairs are recommend-only and require manual judgment.
- Document the stale-directive behavior after an applied merge.
- Keep docs consistent with the existing scope-out and re-ground bridge wording.

Likely files:

- `CLAUDE.md`
- `RUNBOOK.md`
- possibly `docs/cli/reconcile-plan-walk.md` / generated CLI docs if flags change

## Non-Goals

- Do not rebuild the completed scope-out bridge.
- Do not rebuild the completed re-ground mark-done bridge.
- Do not add auto re-baseline via `create --from-existing`; re-ground
  re-baseline remains human-authored unless the create pass deliberately scopes a
  separate step and justifies it.
- Do not make merge apply by default.
- Do not widen gapped merge pairs to contiguous ranges automatically.
- Do not make `granularity-merge` apply-eligible globally without the structural
  gate. The bridge is an explicit walk actuation path, not a broad change to
  recommendation semantics.
- Do not add a new merge algorithm or a new structural primitive.

## Acceptance Criteria

- A pairwise merge finding can be produced into the saved recommendation walk
  from a real plan shape, not only from a synthetic unit-test recommendation.
- `reconcile-plan-walk` / `review-walk` can dispatch a merge-kind finding to the
  merge bridge.
- With no opt-in, non-TTY, declined confirm, unsafe state, invalid ids, or a
  gapped pair, the walk recommends only and mutates nothing.
- With opt-in + confirm or `-y` + safe contiguous member ids, the walk applies the
  merge through `merge_steps`.
- Applied merge invalidates or halts subsequent directive-carrying findings so
  renumbering cannot make later saved recommendations mutate the wrong steps.
- Re-ground findings still route to `reground_bridge`, never to merge.
- Scope-out and re-ground behavior remain unchanged.
- Tests cover producer, bridge gate matrix, dispatch, gapped pair handling, and
  stale-directive/renumber protection.

## Risks

- **Dead bridge risk:** building the bridge without the producer repeats the
  reason the completed auto-bridge plan deferred this work. The producer is the
  first-class requirement.
- **Wrong-step mutation after renumber:** merge changes step ids. A walk that
  keeps applying saved directives after a merge can mutate shifted steps. Guard
  this explicitly.
- **Merge vs re-ground confusion:** both have historical ties to
  `granularity-merge`. Dispatch must use remedy/action shape, not the literal
  source string alone.
- **Over-application:** pairwise merge advice can be lower-confidence than a
  structural correctness finding. Keep explicit opt-in and confirmation.
- **Claude spend in apply path:** merge re-authors detail. The bridge must forward
  the invoker seam and keep every non-applied path no-Claude.

## Suggested Create Command

Use this seed directly:

```bash
.agents/plan-tool.sh create merge-bridge --iterate -y \
  --output-dir docs/implementation-plans \
  --from-existing plan-seeds/merge-bridge.md
```

Then follow the normal recipe:

```bash
.agents/plan-tool.sh detail merge-bridge --iterate -y
.agents/plan-tool.sh completeness merge-bridge --iterate -y
.agents/plan-tool.sh run merge-bridge --all --commit -y
```
