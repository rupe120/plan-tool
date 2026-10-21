# Plan seed: verify a plan's body against its fetched reference-doc links

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/verify-plan-doc-links.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per
step.

Source: BACKLOG #30 → promoted to IPPT-15 (2026-09-27). This seed carries
that entry's scope contract; the ticket holds the working brief.

## Outcome

A new `review.py` primitive re-fetches the developer docs a plan cites in
`## References`, compares the plan body's claims against the fetched text,
and emits a finding on mismatch — catching a stale anchor, version drift, or
a paraphrase error introduced at `create` time. Wired into `reconcile-plan`'s
existing audit path.

## In scope

- `plan_tool/review.py`: a new finding-producing primitive, in the style of
  the existing `_reject_unmatched_*_fence` checks, that reads a plan
  section's claim and the doc content `plan_tool/fetch.py:fetch_reference_docs`
  returns for its cited URL.
- `plan_tool/prompts/`: a new prompt for the claude call comparing the plan
  section's prose against the fetched doc text.
- Wiring into `review_plan_full` / `cmd_review` so the primitive runs
  alongside the audit's existing checks.
- Failure handling: a fetch failure (network, 404, gated doc) emits a
  finding, not a crash — `fetch.py` already funnels failures into a
  `FetchedDoc` with an `error` field; follow that pattern. Cache fetched
  content within one audit run.

## Out of scope / Non-goals

- The detail-file half of this check (verifying an individual step's
  detail-body claims against a fetched doc). It depends on BACKLOG #312,
  which is unbuilt — a step's prose has no reliable, capturable link back to
  fetched doc content today. Land #312 first if that half becomes the
  target; this seed's Outcome is the plan-body half only.
- Any new fetch dependency. Reuse `plan_tool/fetch.py` exclusively.
- Re-fetching or re-verifying at any time other than a `reconcile-plan`
  audit run (no background job, no `create`-time re-check).

## Allowed behavior changes

None beyond the Outcome: `reconcile-plan` gains one more finding category. No
other audit behavior changes.

## Allowed reorganization

None.

## Verification

- The primitive emits a finding for a plan section whose claim contradicts a
  fixture's fetched doc content.
- The primitive emits nothing for a plan section whose claim matches the
  fetched doc content.
- A fetch-failure fixture produces a finding, not a crash.
- `uv run pytest tests/test_review.py -q` is green.

## Stop / defer

Stop and surface to the user if `create`'s synthesis grounding
(`synthesize-body.md`) — the claim-to-source link this seed's plan-body half
depends on — doesn't hold on a real plan. That would mean the source entry's
dependency claim is wrong and this primitive has nothing reliable to verify
against.

## References

- `plan_tool/fetch.py` (`fetch_reference_docs`, `fetch_url`, `FetchedDoc`) —
  the existing fetch layer this seed reuses; no new fetch dependency.
- `plan_tool/review.py` (`review_plan_full` / `cmd_review`'s audit path,
  the sibling `_reject_unmatched_*_fence` primitives) — where the new
  primitive is wired in and the style it follows.
- `plan_tool/prompts/` — where the new claim-vs-doc comparison prompt goes.

## Backlog reconciliation

`BACKLOG.md`'s `#30` entry is already a promotion stub pointing at IPPT-15.
No further backlog edit is required when this plan ships.
