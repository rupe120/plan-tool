# Jira-grade retirement plan pickup

| Item | Current state |
| --- | --- |
| Work | BACKLOG #308 / IPPT-17; retire legacy Jira-grade detail inputs and selectors |
| Branch | `plan/IPPT-17-retire-jira-grade-detail` |
| Plan | [Retire Jira Grade Detail](../docs/implementation-plans/2-retire-jira-grade-detail.md), eight steps, all detailed |
| Latest audited snapshot | `09596f729`; report/checkpoint commit `de15e59a8` |
| Latest result | Clean, confirmed coverage, current revision, detail stage, zero findings |
| Next action | Review the plan bundle; publish and merge its plan PR before implementation |
| Implementation/publication | No implementation, branch push, or PR creation in this session |

## Settled scope

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

## Audit evidence

All explicit audits use `--iterate --commit --audit-passes 1 -y` with closed
stdin. Detail authoring uses `--commit -y` without iteration.

| Snapshot | Model and coverage | Result and disposition |
| --- | --- | --- |
| [Bare audit](../docs/implementation-plans/plan-details/retire-jira-grade-detail/reports/20261029-192028-completeness.md) | `gpt-5.6-terra`; 0 of 8 details | Clean, confirmed/current. Completeness apply remains withheld at bare stage; no conceptual findings need application. |
| [Detail command's audit tail](../docs/implementation-plans/plan-details/retire-jira-grade-detail/reports/20261029-193426-completeness.md) | `gpt-5.6-terra`; 8 of 8 details | A dotted-method citation does not fit the anchor checker, and live docs are missing from the sweep. `41c5110e9` corrects the citation and extends the existing docs responsibility. |
| [Detail re-audit](../docs/implementation-plans/plan-details/retire-jira-grade-detail/reports/20261104-013137-completeness.md) | `gpt-5.6-terra`; 8 of 8 details | Confirmed/current advisory-only result: active seed and project lessons also carry stale guidance. `62b433490` adds those sources to the same final step. |
| [Final detail audit](../docs/implementation-plans/plan-details/retire-jira-grade-detail/reports/20261104-013523-completeness.md) | `gpt-6.1-sol`; 8 of 8 details | Clean, confirmed/current, zero correctness and completeness findings. |

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
