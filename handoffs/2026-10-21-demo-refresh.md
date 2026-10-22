# Demonstration refresh pickup

The assistant-led guides and authored reading samples support review of the
retained dark-mode and TTRPG scenarios. **The live dark-mode rehearsal needs
verification:** Codex cannot initialize its app-server client in the restricted
verification runtime. Remote checkpoint publication remains pending and requires
separate authorization through the [release handoff](2026-10-19-public-onboarding-and-release.md).

The [verification record](../docs/evidence/skill-led-demo-examples-verification.md)
owns the reviewed revision, reading checks, runtime error, fixture availability,
and every unverified stage. Documentation readiness, a live rehearsal and remote
publication are separate results.

Keep `demo/1-seed`, `demo/2-plan`, `demo/3-detail` and `demo/4-jira` on both
Bitbucket and GitHub. The [sanitized publication record](2026-10-21-sanitized-publication.md)
records their shared needs-updating notice. Private recovery bundles retain the
previous staged contents; local fixture tips below are not approved replacements.

## Current plan pickup: use the plan-tool skill

[Teach demos and examples through the plan-tool skill](../docs/implementation-plans/2-skill-led-demo-examples.md)
provides the maintained walkthroughs and learning entry points. Steps 1–3 are
done at the verification snapshot; this step supplies evidence and status.
The launcher owns plan status and the post-flight check. Do not re-author the
seed, restart the guide conversion or reopen scenario selection.

Next pickup: resolve the runtime blocker, then use the plan-tool skill to
rehearse [the dark-mode walkthrough](../docs/demos/planning-demo.md) in an isolated
consuming repository with working application tests. Monitor each original
command to confirmed exit and retain actual results. Follow the
[shared directives](../integrations/shared/DIRECTIVES.md) and
[audit procedure](../docs/how-to/pipeline/audit.md); do not infer qualification
or convergence from an exit code.

### Plan scope and user review

Dark mode remains the planning scenario; TTRPG remains the advanced roadmap
scenario. TTRPG receives contract review here, not full regeneration.
No CLI, skill, schema or monitoring changes belong to this effort.

The guides ask the assistant to link actual artifacts, summarize changes and
ask for corrections or continuation at seed, bare-plan/audit and detail/audit
boundaries. Wait for the user's response unless explicit prior delegation covers
the transition. Export requires its separate request after detail review.
The verification record confirms these narrative checkpoints, not actual user
approval of nonexistent rehearsal artifacts or fresh model-audit results.

### Authoring evidence and audit trajectory

Dated plan-authoring provenance, 2026-10-21: the plan's bare and detailed audit
reports record the following snapshots. These audit this documentation plan,
not a consuming-repository dark-mode rehearsal.

| Snapshot | Coverage and retained conclusion | Report |
| --- | --- | --- |
| Bare | 0 of 4; clean, confirmed; detail/completeness apply withheld | [23:38 report](../docs/implementation-plans/plan-details/skill-led-demo-examples/reports/20261021-233834-completeness.md) |
| Initial detailed | 4 of 4; clean, confirmed; superseded by user-review amendment | [23:44 report](../docs/implementation-plans/plan-details/skill-led-demo-examples/reports/20261021-234419-completeness.md) |
| Amended detailed | 4 of 4; clean, confirmed; zero blocking/deferred findings | [23:47 report](../docs/implementation-plans/plan-details/skill-led-demo-examples/reports/20261021-234705-completeness.md) |

The original authoring handoff records 14,698 passed and 66 skipped in 62.83s.
That dated result does not replace the launcher's current post-flight result or
verify the live demo. The [archived source brief](../plan-seeds/archive/skill-led-demo-examples.replaced.md)
and retained reports provide durable authoring provenance; transient logs are
not required to read the current guides.

## Local candidate

Dated preparation provenance, 2026-10-21: the following describes the original
local candidate snapshot. Its scratch repository and receipts are absent in
this clone; none of these checks is a fresh verification.

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

## Remaining demo verification and publication

1. Resolve the Codex runtime permission blocker identified in the verification
   record. Confirm backend availability in the consuming environment.
2. Rehearse grounded seed → create → bare audit → detail → grounded audit with
   actual user reviews or explicit delegation at each boundary. Retain report
   coverage, qualification, conclusions and unresolved findings.
3. After the separate local-export request, inspect stories and the paired
   developer handoff; lint the actual story artifact and record warnings separately.
4. Update the verification record with captured evidence before describing the
   live route as verified. Recheck local checkpoint refs, stage differences,
   bundles and old remote tips before proposing replacements.
5. Obtain separate review and authorization for remote demo ref updates, then
   read both hosts back. Main, tags, visibility and organization transfer remain
   with the release workflow.

Use [the planning guide](../docs/demos/planning-demo.md) for the workflow and
[the documentation placement handoff](2026-10-21-documentation-placement-review.md)
for the primary-folder review record. No remote publication is performed here.
