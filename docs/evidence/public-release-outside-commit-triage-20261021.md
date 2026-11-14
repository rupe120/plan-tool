# Outside-commit triage and approved deletion results

Use this record to decide what remains on the two hosts before shared-root replacement.
No additional branch deletion or implementation replay is authorized by this triage.

## Approved cleanup result

On 2026-10-21, the 23 branches in the [approved proposal](public-release-ref-disposition-20261021.md#proposed-deletions-contained-non-main-branches)
are deleted: four from Bitbucket and 19 from GitHub. Each deletion uses its
reviewed old tip as an explicit lease; each host push is atomic. Both pre-push
full-suite checks pass, and remote reads verify all 23 refs are absent. Main and
tags are not changed by these operations. The prior-history bundle preserves
the deleted refs under host-qualified names.

## Remaining ref decisions

The 22 rows refer to the outside refs in the proposal, not a fresh deletion list.
Patch identity uses `git patch-id --stable` over the complete branch delta from
its merge base, compared with 6,483 non-merge patches reachable from the observed
main. A match proves historical patch equivalence; it does not prove a feature
still ships unchanged today. Per-commit `git cherry` also identifies two branches
whose individual non-merge patches are all equivalent.

The baseline advances to PR #126 (`25fe3b1ff87e79e9783ef3b2c36abc14c06d5b5b`) during triage. Its five
evidence files are integrated into this working branch. Final release selection
must account for those new files; the prior sanitized candidate does not include
them automatically.

| Host | Branch | Recommendation | Evidence |
| --- | --- | --- | --- |
| bitbucket | `demo/1-seed` | Keep this demonstration branch on both hosts (owner decision, 2026-10-21). Update its staged content separately; exclude it from branch deletion. | Four same-named host pairs have identical tips; staged demo seed/plan/detail/Jira artifacts are distinct from main. |
| bitbucket | `demo/2-plan` | Keep this demonstration branch on both hosts (owner decision, 2026-10-21). Update its staged content separately; exclude it from branch deletion. | Four same-named host pairs have identical tips; staged demo seed/plan/detail/Jira artifacts are distinct from main. |
| bitbucket | `demo/3-detail` | Keep this demonstration branch on both hosts (owner decision, 2026-10-21). Update its staged content separately; exclude it from branch deletion. | Four same-named host pairs have identical tips; staged demo seed/plan/detail/Jira artifacts are distinct from main. |
| bitbucket | `demo/4-jira` | Keep this demonstration branch on both hosts (owner decision, 2026-10-21). Update its staged content separately; exclude it from branch deletion. | Four same-named host pairs have identical tips; staged demo seed/plan/detail/Jira artifacts are distinct from main. |
| bitbucket | `docs/backlog-run-accept-and-seed-frontmatter-followups` | Merged patch retained; branch deleted with owner approval, absence verified 2026-10-21. | ca6fdaf25bd00c8016df23c0677adf610476d995 |
| bitbucket | `docs/token-ledger-harness-evidence` | Merged through PR #126; source branch is already absent. | PR #126; fetched main 25fe3b1ff87e79e9783ef3b2c36abc14c06d5b5b |
| bitbucket | `fix/audit-next-steps-open-correctness` | Owner-approved deletion complete; Bitbucket absence verified 2026-10-21. Main supersedes the six commits; no replay. | [Behavior and test comparison](public-release-audit-next-steps-comparison-20261021.md): 2,319 report/CLI/review tests and 11 authoring tests pass; mutation confirms the blockers. |
| bitbucket | `test-suite-performance` | Preserve experiment archive; do not replay wholesale. Separate retained conclusions from harnesses, abandoned trials and plan artifacts. | PR #48/#51 merge performance work; 52 touched paths are absent from current main, including 48 non-report experiment/plan/handoff paths. PR #126 retains five selected evidence files. |
| github | `agent/ground-create-synthesis-local-code` | All code, test and backlog edits match the landing patch; branch deleted with owner approval, absence verified 2026-10-21. | e61516bfe: exact equality of the three implementation/test files; BACKLOG.md differs. |
| github | `cleanup/backlog-drift-and-version-flag` | Merged patch retained; branch deleted with owner approval, absence verified 2026-10-21. | c41efd753901dd1bfbc3aa30c08af226ee2968ee |
| github | `codex/roadmap-feedback-batch-revision` | Merged patch retained; branch deleted with owner approval, absence verified 2026-10-21. | 30484873f04fbc3c9badded704fc870ad13f298b |
| github | `codex/roadmap-stack-aware-approval-seed` | Complete tree matches the landing commit; branch deleted with owner approval, absence verified 2026-10-21. | 93fbda8f4: exact equality under plan_tool/ and tests/. |
| github | `codex/roadmap-structural-approval-handoff` | Merged patch retained; branch deleted with owner approval, absence verified 2026-10-21. | 950365c2507dd7feddb1a7d11282b0f862777fd1 |
| github | `demo/1-seed` | Keep this demonstration branch on both hosts (owner decision, 2026-10-21). Update its staged content separately; exclude it from branch deletion. | Four same-named host pairs have identical tips; staged demo seed/plan/detail/Jira artifacts are distinct from main. |
| github | `demo/2-plan` | Keep this demonstration branch on both hosts (owner decision, 2026-10-21). Update its staged content separately; exclude it from branch deletion. | Four same-named host pairs have identical tips; staged demo seed/plan/detail/Jira artifacts are distinct from main. |
| github | `demo/3-detail` | Keep this demonstration branch on both hosts (owner decision, 2026-10-21). Update its staged content separately; exclude it from branch deletion. | Four same-named host pairs have identical tips; staged demo seed/plan/detail/Jira artifacts are distinct from main. |
| github | `demo/4-jira` | Keep this demonstration branch on both hosts (owner decision, 2026-10-21). Update its staged content separately; exclude it from branch deletion. | Four same-named host pairs have identical tips; staged demo seed/plan/detail/Jira artifacts are distinct from main. |
| github | `docs/developer-front-door` | Merged patch retained; branch deleted with owner approval, absence verified 2026-10-21. | 79a8e131de107ad74dff42a40d3bcde6a9b01850 |
| github | `fix/backlog-entry-id-uniqueness` | Merged patch retained; branch deleted with owner approval, absence verified 2026-10-21. | c41efd753901dd1bfbc3aa30c08af226ee2968ee |
| github | `fix/reconcile-all-round-2` | Merged patch retained; branch deleted with owner approval, absence verified 2026-10-21. | ff6c9fb29622e379b9e81ef98c20511b78e13744 |
| github | `plan/telemetry-linkage-backfill` | Merged patch retained; branch deleted with owner approval, absence verified 2026-10-21. | 1218701ab833e5681d499422d64e6b9c2904e329 |
| github | `read-only-audit-split` | Deleted on GitHub with owner approval; expected-tip lease and remote absence verified. The backup retains the historical decision. | Only unique commit files former BACKLOG #103 about _actuate_scope_out; current convergence_cmd.py is read-only and has no such actuator. |

## Final triage of the eleven merged-work refs

The [per-branch proof record](public-release-merged-branch-triage-20261021.json)
resolves all eleven refs with merged-work evidence:

- Nine match the added and removed line sequences for every changed path against
  their landing commits, including the grounding branch's backlog removal. No
  branch-only change needs replay. Differences in unrelated landing-time context
  in `handoffs/README.md` and `BACKLOG.md` do not change those patch comparisons.
- `codex/roadmap-stack-aware-approval-seed` matches the complete tree at
  `93fbda8f4`, including plan and review artifacts, not only runtime/tests.
- `docs/token-ledger-harness-evidence` is an ancestor of main through PR #126.
  The latest remote read shows that source branch is already absent.

Owner-approved retirement is complete on 2026-10-21: one Bitbucket and nine
GitHub branches are deleted with reviewed-tip leases and atomic per-host pushes.
Both full-suite pre-push checks pass. Reads verify all ten refs are absent and
all remaining branch tips are unchanged. The private backup retains provenance.
Demo, experiment, old-decision and correctness branches remain preserved.

## Next bounded work

1. Preserve the completed retirement evidence; all eleven merged-work refs are
   absent. Keep further cleanup scoped to separately reviewed remaining refs.
2. Keep `demo/1-seed`, `demo/2-plan`, `demo/3-detail` and `demo/4-jira` on
   both hosts. Update the demo instructions and stage artifacts separately.
   Before public visibility, prepare and verify demo histories from the sanitized
   base while retaining the four branch names and their demonstration purpose;
   the retention decision does not authorize changing their current tips.
3. Correctness-branch retirement is complete; keep its behavior/test comparison
   as evidence. Select any remaining experiment material from the private backup.
   A concurrent remote update removes `test-suite-performance`; this cleanup
   deletes only the correctness branch. Main advances through PR #127 to
   `f012872af`, adding the token-optimization retro.
4. Settle the old release tag and outstanding refs, then regenerate the final
   candidate from the chosen current source. Keep remote root replacement separate.

Raw per-commit patch lists, branch statistics and evidence classifications are
in `.tmp/public-release-outside-commit-triage.json`. The [pickup handoff](../../handoffs/public-onboarding-and-release.md)
owns the current route.
