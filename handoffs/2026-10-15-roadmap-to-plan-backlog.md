# Roadmap to plan backlog update

## Pickup

Branch `docs/roadmap-to-plan-backlog`, based on `5ecee088`, in
`/private/tmp/plan-tool-roadmap-to-plan-backlog`. This is a tracking-only change;
no feature, schema, workflow gate or execution policy is implemented.

## Changes and next route

- BACKLOG #492 is the single authority for the staged roadmap-to-plan route.
  Start with its bounded composition-handoff investigation. Existing inputs or
  no tool change are valid outcomes.
- #493 shared-context delivery and #494 recorded-prerequisite status output are
  separate evidence-gated follow-ons. No seeds or implementation plans are
  authored before their input/value decisions are settled.
- Existing #462 receives newer evidence without broadening its advisory conflict
  scope or declaring its evidence gate met. #485 keeps its authority decision
  open; #490 receives evidence while retaining its convergence-evidence owner.
  #484 remains independent.
- The existing roadmap arc routes to #492 rather than duplicating stage scope.
  The new evidence record distinguishes project observations from proposed
  benefits and supplies source/commit provenance for the Integration case.

Do not promote roadmap-owned work through the lead's ordinary Jira route.
Keep each entry's route/readiness and the arc's owner decisions authoritative.
Do not bulk-author later seeds or implement a new semantic readiness gate.

## Verification and review

- Fetched all configured remotes and scanned all-ref merge-aware BACKLOG history
  plus current entries. Highest previously used ID was 491; selected 492–494.
  Recheck IDs against refreshed refs before publication and resolve collisions.
- Existing `tests/test_backlog_ids.py` and `tests/test_backlog_readability.py`:
  30 passed. No new tests or production files are needed for these tracking edits.
- Checked the three new scope contracts, explicit evidence-gated labels,
  single arc authority, named consumer paths and added local links.
- Independent read-only review: no material correctness/completeness findings;
  existing owners and #462's scope/evidence gate are preserved. Reviewed files:
  BACKLOG, roadmap arc and the new Integration evidence record. This handoff records
  that result and does not introduce another product decision.
- `git diff --check` passes. Review output is local ignored scratch under
  `.tmp/roadmap-to-plan-review.md` and `.tmp/roadmap-to-plan-review.log`.

The main checkout's pre-existing `integrations/shared/DIRECTIVES.md` model
selection edit remains untouched and is not included in this branch. Nothing
is pushed; normal publication and canonical-install delivery rules still apply
before any future updated tool is tested against Integration.
