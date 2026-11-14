# Roadmap candidate vocabulary retry — plan review pickup

The plan for `IPPT-10` (resolve the site from `.claude/local/project-context.json`) is on branch `plan/structural-candidate-vocabulary-retry`. It is ready for the required plan pull request and architect review before `run`. The plan and all three detail files are committed; implementation has not started.

## Current artifacts

- Plan: `docs/implementation-plans/2-roadmap-candidate-vocabulary-retry.md`.
- Details: `docs/implementation-plans/plan-details/roadmap-candidate-vocabulary-retry/` (3 of 3).
- Source seed: `plan-seeds/archive/roadmap-candidate-vocabulary-retry.replaced.md`.
- Tracking: `BUG_BACKLOG.md` retains the IPPT-10 promotion stub until implementation ships.
- Remote plan branch: `origin/plan/structural-candidate-vocabulary-retry`.

## Audit gate evidence

These are 2026-09-25 observations, not current checkout qualification. Captures
and sidecars are omitted; the retained summaries preserve their limits.

The bare-plan gate uses `plan-tool --backend codex --model gpt-5.6-terra completeness-audit roadmap-candidate-vocabulary-retry --iterate --commit --audit-passes 1 -y`. Three committed snapshots move from two correctness findings, through two newly exposed correctness findings, to zero. The final bare report is [retained historical summary](../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions): 0 of 3 details, confirmed coverage, current revision, converged, no correctness or completeness findings. Detail-level axes are withheld at this gate.

`plan-tool --backend codex --model gpt-5.6-terra detail roadmap-candidate-vocabulary-retry -y --commit` writes all three details. Its built-in conceptual check finds two detail contradictions: overlapping retry ownership in step 1 and missing source-bound hints in stored-candidate review calls. The session-directed correction assigns all retry behavior to step 2 and covers both review replacement and structural edit prompts in step 1.

The detail-grounded gate uses the same `completeness-audit --iterate --commit --audit-passes 1 -y` command. The final report is [retained historical summary](../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions): 3 of 3 details, confirmed coverage, current revision, converged, zero correctness and completeness findings. The four claim-versus-footprint INFO heuristics are advisory and do not describe an unowned contract. The branch push runs and passes the repository's pre-push test suite.

## Next action

Open a Bitbucket pull request from `plan/structural-candidate-vocabulary-retry` to `main`, link it on IPPT-10, and obtain the plan review and merge. The available Atlassian MCP tools in this session do not expose Bitbucket pull-request creation, so the PR is not opened here. After merge, branch from updated `main`, run the plan with `--commit`, then drive `reconcile-code --all` and code review to convergence. Do not bypass the plan merge check.
