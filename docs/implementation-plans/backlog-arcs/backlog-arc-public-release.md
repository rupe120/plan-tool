# Public-release coordination arc

## File intent

Use this route to prepare public onboarding and select a safe publication
boundary. `BACKLOG.md` owns the open scope contracts for #514 and #515. This
file coordinates their order alongside the installed-skill and operator-workflow
arcs.

## Choose this arc when

The owner selects public-release preparation. This route does not authorize
publication, remote changes, history rewriting, or independent team-policy changes.

## Ordered route

| Position | Work | Result needed for the next position |
| --- | --- | --- |
| 1 | Content preparation — complete (#513) | PR #123 is merged; its selected bytes match the independently verified 2,588-path prose candidate. Preserve the selection and verification evidence when preparing a release. |
| 2 | #514 distribution, license and history decisions | Apache-2.0, the GitHub source and a shared sanitized root for both hosts define the release route. Review install/update and synchronization guidance, then verify the final candidate and destinations. |
| 3 | Portable guidance and recipe consistency — complete (#508) | Installed guidance is portable and first-task instructions agree with canonical audit/iteration rules. |
| 4 | Installed onboarding guidance — complete (#509, #511, #512) | Hosting selection, skill installation and refresh, and model guidance support the consuming repository. Seed-authoring support is complete (#377). |
| 5 | #515 | A fresh reader verifies the #510 walkthrough, with prerequisites resolved or explicitly dispositioned. |

The installed-skill arc records delivery of #508/#509/#511/#512. The operator-workflow arc
owns #515 and the completed #510 walkthrough. This coordination arc routes
the separate release prerequisite #514 and consults the other arcs for their lanes.
The installed skill's shared filing guidance ships in PR #292.

The candidate verification below covers the pinned Bitbucket commit. For
synchronization, follow the
[shared-root sync procedure](../../RELEASING.md#keep-bitbucket-and-github-synchronized).
After an approved sync, read both destination heads back.

### Destination verification

On 2026-11-18, the GitHub repository responded without authentication and
reported `main` and Apache-2.0. The GitHub `main` commit `b1ccba9ca` also
carried tag `v1.6.0`. The Git URL install, pinned tag install, and editable
install from a fresh clone each reported plan-tool 1.6.0 in isolated uv tool
environments. `uv tool upgrade plan-tool` found the Git install current.

GitHub `main` and Bitbucket `main` at `bd0ea279e` shared the reviewed root
`9c10d74ca`. The GitHub head was an ancestor of the Bitbucket head, 111
commits behind. This checks the public installation route at that revision.

Gitleaks 8.30.1 scanned the history reachable from GitHub `main` and the
range `b1ccba9ca..bd0ea279e`, including first-parent merge diffs. The public
scan's 68 generic matches all correspond to 64-character file digests in
archived reports' `detail_bundle_fingerprint` maps. The Bitbucket range
produced no matches. The scan covers those commit ranges and the enabled
credential patterns.

#### Candidate checked 2026-11-20

| Check | Result |
| --- | --- |
| Source and ancestry | Anonymous GitHub `main` and tag `v1.8.0` resolve to `a87270388b92d35c3efc77326d14c6a454e3219b`. Bitbucket candidate `c132a1a6a7ab0598e7d29eaf27150d1e284ce9d3` is 43 commits ahead, with no GitHub-only commits. Both share the reviewed root `9c10d74ca`. |
| Incoming history | Gitleaks 8.30.1 reported zero matches in `a87270388..c132a1a6a`, covering 28 ordinary commits and 15 first-parent merge diffs with allowlist suppressions disabled. Targeted checks found no newly added local home paths, AWS account IDs in ARNs, private IPv4 addresses, Atlassian Cloud URLs, or email-address patterns in those merge diffs. The range contains no added or changed binary files. |
| Candidate tree | The full-tree scan reported 75 matches. All match byte-identical public files: 68 archived detail-bundle fingerprints and seven test fixtures. |
| Installation and upgrade | In isolated Python 3.14.7 tool environments, anonymous GitHub installs from `main` and `v1.8.0`, a fresh editable clone, and an upgrade check on public `main` passed. A local replica advanced from the public tip to the candidate and `uv tool upgrade` installed the candidate, verified by commit in package metadata. An editable candidate install and a copied Codex skill refresh also passed. The candidate package includes the Apache-2.0 license, LICENSE, and NOTICE. |
| Bitbucket CI | [Pipeline #63](https://bitbucket.org/protagona/plan-tool/pipelines/results/63) passed on the exact candidate commit. |

The scan covers the pinned commit range and candidate tree. Its results
are limited to the enabled patterns and reviewed matches. The candidate
still declares version 1.8.0, so the upgrade check uses the installed Git
commit to distinguish builds. The checks run without model authentication.
#515 owns independent fresh-reader verification. This receipt is recorded
after the verified candidate. Recheck any newer tip before synchronization
and compare both destination heads after it.

## Decision gates

- Users install with `uv tool install git+https://github.com/rupe120/plan-tool`; the
  clone plus `uv tool install --editable .` is the contributor route (owner
  decision, 2026-11-06, #514). Package publishing is outside this route (#523).
  Explain release selection, dependency updates and copied-skill refresh.
- Classify owner-controlled projects, clients and legitimate third-party names
  before removing references. Inventory paths and structured content as well as
  prose. A search hit is a review candidate, not proof of private ownership.
- Current-tree cleanup does not certify Git history. #514 needs an explicit
  owner decision before a history rewrite, public remote or publication action.
- Provider selection is router guidance (detect from the remote, confirm with the
  user), not a configuration reader (#509). Git hosting does not imply Jira or
  team approval policy.
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
