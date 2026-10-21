# Public-release coordination arc

## File intent

Use this route to prepare public onboarding and select a safe publication
boundary. BACKLOG #508–#515 own the scope contracts; this file coordinates their
order without replacing the installed-skill and operator-workflow arcs.

## Choose this arc when

The owner selects public-release preparation. This route does not authorize
publication, remote changes, history rewriting, or independent team-policy changes.

## Ordered route

| Position | Work | Result needed for the next position |
| --- | --- | --- |
| 1 | Content preparation — complete (#513) | PR #123 is merged; its selected bytes match the independently verified 2,588-path prose candidate. Preserve the selection and verification evidence when preparing a release. |
| 2 | #514 distribution, license and history decisions | Apache-2.0, the GitHub source and a shared sanitized root for both hosts define the release route. Review install/update and synchronization guidance, then verify the final candidate and destinations. |
| 3 | #508 and the onboarding/workflow-consistency bug | Installed guidance is portable and first-task instructions agree with canonical audit/iteration rules. |
| 4 | #509, #511, #512 and existing #377 | Hosting selection, skill installation/refresh, model guidance and seed authoring support the consuming repository. These are separate bounded items, not one combined implementation. |
| 5 | #510, then #515 | A skill-first walkthrough works in a fresh consuming repository, with prerequisites resolved or explicitly dispositioned. |

The installed-skill arc owns #508/#509/#511/#512 and #377. The
operator-workflow arc owns #510/#515. This coordination arc routes the separate
remaining release prerequisite #514 and consults the other arcs for their lanes.
Do not duplicate #378/#379 tracker-convention or stale-entry work.

Next bounded action: review #514's [install/update instructions](../../how-to/install-and-update.md)
and [shared-root sync procedure](../../RELEASING.md#keep-bitbucket-and-github-synchronized),
then verify the final candidate and both destinations. The [pickup handoff](../../../handoffs/2026-10-19-public-onboarding-and-release.md#next-actions)
owns the current route. Keep distribution, updates and fresh-consumer verification
with their separate work items.

## Decision gates

- Retain clone plus `uv tool install --editable .` as the supported method;
  package publishing is outside this route. Explain clone retention, release
  selection, dependency updates and copied-skill refresh.
- Classify owner-controlled projects, clients and legitimate third-party names
  before removing references. Inventory paths and structured content as well as
  prose. A search hit is a review candidate, not proof of private ownership.
- Current-tree cleanup does not certify Git history. #514 needs an explicit
  owner decision before a history rewrite, public remote or publication action.
- Provider selection must have a defined reader; a configuration example alone
  cannot deliver #509. Git hosting does not imply Jira or team approval policy.
- Distinguish model recommendations from inherited defaults, published token
  prices from measured task cost, and API billing from subscription allowances.

## Delivery cadence

Use each item's declared route and scope. Plan-route work retains seed review,
both audit gates, committed baselines and the post-run reconciliation/review tail.
Commit independent concerns separately. Never publish automatically. Changes to
CLAUDE.md retain architect-tier review.

## Exit and handoff

Content preparation is accepted through PR #123. #514 retains distribution/update
guidance, destination checks and sync procedures; #515 retains consumer evidence.
Use the exact candidate identity and results in the
[prose verification record](../../evidence/public-release-prose-verification-20261020.json).
A new selection requires its own verification. Publication remains a separate
owner-authorized action.

End a bounded session with its inventory, decisions or implementation checkpoint
recorded. Public onboarding sign-off requires #515's fresh-repository evidence;
unresolved ownership, license, history or credential coverage stays explicit.
Publication is a separate owner-authorized action. Keep durable records in the
backlog and canonical documentation; retire pickup handoffs when their route ends.

## Out of scope

No mass rename before ownership classification, generalized hosting framework,
automatic model router, pricing service, benchmarking framework, new semantic
quality gate, PyPI pipeline, or silent weakening of local approval rules.
