# Jira-grade retirement execution and review

| Item | Current state |
| --- | --- |
| Work | BACKLOG #308 / IPPT-17; retire legacy Jira-grade detail inputs and selectors |
| Implementation branch | `IPPT-17-retire-jira-grade`, based on plan PR #159's merge `2b6292993` |
| Plan | [Retire Jira Grade Detail](../docs/implementation-plans/archive/2-retire-jira-grade-detail.md), eight steps, all detailed |
| Plan-design audit snapshot | `09596f729`; report/checkpoint commit `de15e59a8` |
| Plan-design result | Clean, confirmed coverage, current revision, detail stage, zero findings |
| Next action | Review code PR #160 and plan-status PR #161; merge code first |
| Implementation | All eight steps green at `a7c140541`; reconciliation triaged and two independent clean reviews complete |
| Latest logic correction | `a6387f9aa`, remaining audit-selector removal; full suite 14,915 passed, 67 skipped |

## Settled scope

History (plan PR #159): PR preparation copied the planning commits onto
`origin/main`, excluding inherited release work. The local branch
`plan/IPPT-17-retire-jira-grade-detail` preserves the original audit snapshots;
the reports below identify those original commits. PR #159 is merged, and the
user authorizes execution through the reconciliation and review tail.

## Execution evidence

Every model-backed execution uses `--backend codex --model gpt-6.1-sol` and
per-step `--commit`. Steps 1–7 touch tests; step 8 is non-code. Each completed
step passes the full suite, and checkpoints are pushed after green steps.

- Step 2's gate exposes a deleted budget-call inventory entry and generated
  detail-reference drift. `3ebce5da7` updates both; 15,146 tests pass before
  tool acceptance.
- Step 3 requires regenerated run references after removing its selector.
  `a618a65e7` updates the page; the CLI-reference checks and acceptance pass.
- Step 4's stale cross-command test calls the retired exporter helper.
  `e5b9ca35b` preserves the remaining audit exemption and removes that export
  comparison; 15,113 tests pass before acceptance.
- Step 5's six stale expectations require fresh Jira-grade evidence. The
  consumer tests now assert rejection without fallback and construct legacy
  sidecars as raw historical fixtures. `f3eb400db` follows 1,119 consumer and
  15,130 full-suite passes; tool acceptance then advances the step.
- Step 6's 204 integration failures trace to the missed authoring follow-up
  helper boundary plus generated-reference drift. `c67af6123` completes the
  caller sweep; all 204 failed cases and 14,957 full-suite tests pass before
  acceptance. No compatibility selector is restored.
- Step 7 first refuses deletion because three production imports remain.
  `fdfaae5d3` removes the unused parser and constant imports. The new parser
  absence assertion fails when the old parser is restored; the full suite
  passes. `1fbc24480` deletes the schema/path authority and fixes test imports
  and catalog ownership; 14,911 tests pass before acceptance.
- Step 8 updates live docs, retires stale seed/lesson guidance, removes the
  #308 promotion stub, and leaves #149 deferred. Its full gate passes; the
  subsequent push hook reports 14,911 passed and 67 skipped.

Raw execution/recovery logs live under the feature-prefixed `.tmp/` files;
durable step and acceptance commits retain the implemented changes. The
source plan's statuses advance through `run` / `run --accept`, not hand edits.
This clone uses the advertised `ssh.bitbucket.org` remote after confirming
that its trusted host keys already exist locally.

Remove `detail --grade`, `jira --grade`, `completeness-audit --grade`,
`convergence --grade`, `gate-status --grade`, and `run --detail-grade`,
together with the legacy readers, paths, schema, and writer remnants.
Run-grade detail remains the sole input. Preserve Jira stories and the paired
developer handoff. Do not add artifact migration or a replacement grade.

Move the review citation-fence helper before deleting its Jira-grade owner.
Preserve its current parsing behavior, including the deliberate indented-fence
exception. A parser correction and #149's compact-schema re-baseline remain
separate work. Supported run-grade audit records remain usable; retired
Jira-grade evidence cannot certify the remaining gate.

## Post-run reconciliation

Sweep 1 audits all seven code steps against `9459459bf`, saves every report,
and skips explicit non-code step 8. It runs with `--all --no-walk --no-reuse
-y`, so findings are read and judged before application. Reports span
[`20261104-040546-run-reconcile.json`](../docs/implementation-plans/archive/plan-details/retire-jira-grade-detail/reports/20261104-040546-run-reconcile.json)
through
[`20261104-040950-run-reconcile.json`](../docs/implementation-plans/archive/plan-details/retire-jira-grade-detail/reports/20261104-040950-run-reconcile.json).
Steps 1, 2, 3, 6, and 7 are clean; steps 4 and 5 carry the findings below.

| Finding | Property, evidence, and disposition |
| --- | --- |
| Step 4, high: custom missing detail path can be an output target | **Tracked:** [BUG_BACKLOG entry](../BUG_BACKLOG.md#jira-export-can-write-onto-a-done-steps-missing-custom-detail-destination). A temporary-directory probe reproduces both story and handoff creation at a done step's missing custom pointer. The merge-base implementation also omits declared pointers, while existing tests pin canonical-path and bundle protection. Changing that output behavior is outside this retirement; the backlog owns the bounded fix. |
| Step 5, medium: public capture/freshness grade parameters remain | **Fixed `a6387f9aa`:** remove parameters and forwarding while retaining the serialized `run` marker and digest framing. The source/test call inventory identifies two remaining fixture helpers; those are updated, while intentional rejection and synthetic legacy-metadata tests stay. Four negative API cases fail when the prior implementation is restored. |
| Step 5, medium: contradictory live data-contract sections | **Fixed `a6387f9aa`:** align qualified results, saved gate verdicts, and audit JSON with one run-grade input. Drift checks assert the literal gate value and absence of retired top-level JSON keys; they do not add a prose-quality checker. Restoring the prior contract makes the new checks fail. |

The correction passes 413 focused tests, then a broader fixture retry and the
full suite (14,915 passed, 67 skipped). The next sweep verifies the changed
snapshot before code review. No post-execution `reconcile-plan` or conceptual
completeness command is used.

## Reconciliation sweep 2

Baseline `217743db7`; same explicit Codex model and full-sweep command as
sweep 1. All seven code steps complete; non-code step 8 is excluded. Reports
run from `20261104-042102-run-reconcile.json` through
`20261104-042444-run-reconcile.json` in the plan detail reports directory.
Steps 1 and 3–7 have zero recommendations. Step 2 has two medium findings:

| Finding | Property, evidence, and disposition |
| --- | --- |
| Orphan movement lacks direct unit coverage | Confirmed coverage gap. The existing integration tests cover movement; the unit helper test covers an empty sweep. `test_orphan_sweep_archives_only_stale_same_step_files` now checks archived contents and preserves canonical and other-step files. Both exemption-breaking mutations fail this test. |
| Temporary-input cleanup claim names no existing operation | Confirmed false plan/detail claim. Both merge-base and current `shell_detail_invoker` pass prompt text directly to `claude_invoke`; neither owns a temporary input. A session-directed correction removes this promise from the plan and all three detail restatements and removes the nonexistent test reference. The discrepancy resolves toward the existing implementation, preserving the retirement's behavior fence. No plan-mutating reconcile command is used. |

The identifier and vocabulary sweep finds the claim only in step 2's plan
paragraph and detail. The affected detail tests pass (617), followed by the full suite (14,916 passed,
67 skipped). Coverage lands in `e3f0c83b3`; the plan/detail claim correction
lands separately in `6c27540eb`. No production code
changes follow sweep 2; its verified coverage and claim corrections proceed
to code review without another full model sweep.

## Code-review convergence

Both fresh native Codex reviews inspect the complete merge-base diff
`2b6292993057793c384e83ccbea14b50847814c2..40ec398e4` using
`codex exec review -m gpt-6.1-sol --base 2b6292993`. Each writes its final
verdict before exiting 0. The latest production-code correction is
`a6387f9aa`; neither review prompts or applies code edits.

| Pass | Independent session | Findings and validation |
| --- | --- | --- |
| 1 | `01a1a4d1-77c7-7772-b8a9-9cc6f91428f3` | Zero actionable regressions. Full suite: 14,916 passed, 67 skipped. |
| 2 | `01a1a4d3-9df0-7133-b0fc-5062b0140c51` | Zero actionable regressions. Full suite: 14,916 passed, 67 skipped. |

Retained final verdicts:

> Pass 1: No actionable regressions were identified in the Jira-grade retirement changes. The full test suite completed with 14,916 passed and 67 skipped.

> Pass 2: No actionable regressions were identified relative to the specified base. The full test suite passed: 14,916 passed and 67 skipped.

These are two consecutive clean reviews of the same committed snapshot, with
no intervening logic changes. Local convergence is complete. The pre-existing
Jira export collision remains explicitly tracked in BUG_BACKLOG; it is not a
retirement regression. Review startup reports unavailable Atlassian MCP auth;
local diff inspection and tests complete without that external integration.

## Publication preparation

The required split prepares `IPPT-17-code` (implementation, tests, live docs,
release fragment, backlog and review ledger) and `IPPT-17-plan` (completed
statuses, corrected detail claim, retained reconcile reports and retired seed).
Both target `main`. The user authorizes both publications;
[code PR #160](https://bitbucket.org/protagona/plan-tool/pull-requests/160) and
[plan-status PR #161](https://bitbucket.org/protagona/plan-tool/pull-requests/161)
are open. Merge #160 first.
The breaking-change notice is `changelog.d/IPPT-17.md`. BACKLOG #308 / IPPT-17's
shipped stub is removed; BACKLOG #149 remains deferred.

The origin uses `git@ssh.bitbucket.org:protagona/plan-tool.git`; a trusted
`ssh.bitbucket.org` host entry exists, and fetch/push succeed. No global SSH
configuration or unrelated repository is changed.

## Audit evidence

All explicit audits use `--iterate --commit --audit-passes 1 -y` with closed
stdin. Detail authoring uses `--commit -y` without iteration.

| Snapshot | Model and coverage | Result and disposition |
| --- | --- | --- |
| [Bare audit](../docs/implementation-plans/archive/plan-details/retire-jira-grade-detail/reports/20261029-192028-completeness.md) | `gpt-5.6-terra`; 0 of 8 details | Clean, confirmed/current. Completeness apply remains withheld at bare stage; no conceptual findings need application. |
| [Detail command's audit tail](../docs/implementation-plans/archive/plan-details/retire-jira-grade-detail/reports/20261029-193426-completeness.md) | `gpt-5.6-terra`; 8 of 8 details | A dotted-method citation does not fit the anchor checker, and live docs are missing from the sweep. `41c5110e9` corrects the citation and extends the existing docs responsibility. |
| [Detail re-audit](../docs/implementation-plans/archive/plan-details/retire-jira-grade-detail/reports/20261104-013137-completeness.md) | `gpt-5.6-terra`; 8 of 8 details | Confirmed/current advisory-only result: active seed and project lessons also carry stale guidance. `62b433490` adds those sources to the same final step. |
| [Final detail audit](../docs/implementation-plans/archive/plan-details/retire-jira-grade-detail/reports/20261104-013523-completeness.md) | `gpt-6.1-sol`; 8 of 8 details | Clean, confirmed/current, zero correctness and completeness findings. |

The final command is:

```bash
plan-tool --backend codex --model gpt-6.1-sol completeness-audit retire-jira-grade-detail --iterate --commit --audit-passes 1 -y < /dev/null
```

The correction trajectory stays within step 8's existing guidance-retirement
contract; it adds no feature arm. The detail freshness warning for step 8
reflects the session-directed file-list corrections; the final audit captures
and certifies the corrected bundle. No detail regeneration is required merely
to replace that authoring fingerprint.

Creation uses `gpt-6.1-sol`; earlier detail and audit calls use the working tier
in the supplied project instructions. The user requests model verification;
the shared directives carry a newer owner decision dated 2026-10-14 selecting
`gpt-6.1-sol` for all Codex work, while `CLAUDE.md` still names the older split.
Subsequent calls explicitly use `gpt-6.1-sol`. The final audit runs against a
changed snapshot, not an unchanged resample for qualification.

## Separate companion-skills documentation

The user also requests generic recommendations across assistant CLIs.
`09596f729` adds [Choose companion skills](../docs/how-to/companion-skills.md),
README/how-to entry links, and a self-contained shared-directives summary.
The guidance is optional and introduces no package requirement or audit gate.
It covers categories, workflow compatibility, and parent-session versus
backend-subprocess discovery for Claude Code, Codex, and Cursor.

Verification: all 32 `tests/cli/test_skill_cmd.py` tests pass; relative file
links resolve; `git diff --check` passes. Documentation review checks scope,
platform wording, installed-directive portability, and the absence of a new
workflow gate. No third-party skill is installed.
