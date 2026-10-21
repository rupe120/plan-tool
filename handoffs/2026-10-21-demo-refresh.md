# Demonstration refresh pickup

**Deferred by owner decision, 2026-10-21. The demo needs updating before its
next presentation.** Resume this work separately from repository cleanup and
release preparation. Preserve the four remote demo branches; the local fixture
commits below are preparation material, not approved replacements.

Keep `demo/1-seed`, `demo/2-plan`, `demo/3-detail` and `demo/4-jira` on both
Bitbucket and GitHub. Each branch presents one checkpoint of the same generic
dark-mode-toggle example. This handoff owns the local preparation and remaining
verification; the [release handoff](2026-10-19-public-onboarding-and-release.md)
owns remote publication.

The [sanitized publication record](2026-10-21-sanitized-publication.md) confirms
that all four remote demo names point to a shared needs-updating notice on the
new history. Their previous staged contents remain in private recovery bundles.
The fixture tips below remain local preparation material for a future refresh.

## Local candidate

The local review repository is `.tmp/public-release-demo-refresh-v2`. Its bundle
is `.tmp/public-release-demo-refresh.bundle`, and its machine-readable ref and
verification receipts are `.tmp/public-release-demo-refresh.refs.json` and
`.tmp/public-release-demo-refresh.verification.json`. These files are local
preparation artifacts, not remote refs. Copy the private recovery bundle named
in the release handoff to durable private storage before replacing remote refs.

| Ref | Local target | What it presents |
| --- | --- | --- |
| sanitized root | `949e6dd5e8c093e7c073e004d468eb022a15484c` | 2,608 selected paths from source `256f466380dda423117273da0ed69735048474d3` |
| `main` | `d8aa550190c8a2cc3cf3d5284d385e30633b4231` | Release 0.2.0 metadata and collected changelog |
| `v0.2.0` | annotated tag object `4a534a841c7b3daaa0fe8e60ec4916da0c28c2f9` | Points to the local release commit |
| `demo/1-seed` | `9ff9e70e6f1ff15e66f56b9155e7f6fb751c7733` | Scope-fenced brief with the required References section |
| `demo/2-plan` | `6e22cdd88dbe1f7ad71e46ca8dba3264b98b9842` | Current-format plan with intent, three steps and test footprints |
| `demo/3-detail` | `d1bde66e824430b907d9fb7db7bd59b9facaf274` | Three run-grade detail files |
| `demo/4-jira` | `c563f3202885c54e3dee0e18faeb7872c4103870` | Local story export and paired developer handoff |

The demo commits form one direct chain above `main`. The repository has one
parentless root, no remotes or alternates, and no old source commits reachable
from its refs. The bundle verifies and `git fsck` passes. The old `v0.1.0` tag
is retained in private recovery material and remains unchanged on both hosts.
The 2,608-path base includes the primary documentation-folder
READMEs and the documentation placement handoff. Its path and content digests
are recorded in `.tmp/public-release-demo-base.verification.json`. The earlier
2,601-path [final-selection receipt](../docs/evidence/public-release-final-selection-verification-20261021.json)
continues to describe its own frozen candidate, not these later bytes.

## Verification and presentation boundary

The plan parses, all three detail files carry the supported format marker, and
the current Jira renderer produced the stories and paired handoff from explicit
local fixture input. `plan-tool jira dark-mode-toggle --lint` exits successfully
with three advisory warnings: the 3h, 2h and 2h stories are below its 4h soft
decomposition floor. The prepared cards disclose that these are presentation
fixtures. No model-generated plan, qualified bare-plan audit or qualified
detail-grounded audit is claimed for these branches.

The first full-suite run exposed a missing `## References` section in the demo
seed. The current `create --from-existing` preflight requires it; the seed and
all four local demo commits were refreshed, and that specific test passes. Five
other failures came from an isolated test PATH without the installed `codex`
executable; the focused fallback test passes with the executables on PATH. The
final isolated run on `demo/4-jira` passes: **14,698 passed, 66 skipped in
58.00 seconds**, using locked dependencies and the local Python 3.14 interpreter.

## Work to resume when the demo is needed

1. Review the exact local refs, stage differences, bundle and old remote tips.
2. Exercise live `create` → bare audit → `detail` → detail audit → Jira in a
   separate React consuming repository with a working test command and
   authenticated backend. Keep the actual coverage and convergence reports.
   This is required before describing the live workflow as verified.
3. Review and authorize the demo ref updates separately, then read both hosts
   back and confirm matching tips. Main, release tags, public visibility and any
   GitHub organization transfer remain with the release workflow.

Use [the demo guide](../docs/demos/planning-demo.md) for the reusable workflow.
Use [the documentation placement handoff](2026-10-21-documentation-placement-review.md)
for the primary-folder README and how-to review record.
