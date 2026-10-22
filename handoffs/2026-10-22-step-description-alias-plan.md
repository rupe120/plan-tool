# Step description alias: plan review handoff

| Item | Current record |
| --- | --- |
| Base and branch | `4bbd335c0`, `plan/step-description-alias` |
| Plan | `docs/implementation-plans/2-step-description-alias.md` |
| Scope | BACKLOG #517; planning only, no implementation |
| Authoring backend | Codex, explicit `gpt-6.1-sol` |
| Detail coverage | 4 of 4, run grade |
| Audit result | Both gates clean, confirmed-dry, current at completion |
| Next boundary | Owner review and architect-tier plan PR; merge before implementation |

## Settled decisions

Owner-confirmed 2026-10-22: prefer step `description`, keep accepting legacy
`title`, retain format v1 and existing-plan writes without explicit upgrades.
The implementation narrowly revises DATA_CONTRACT.md's strict new-key break
rule and documents older installations rejecting newly emitted description
keys. No upgrade command, bulk migration, plan/feature title rename, or
unrelated schema relaxation belongs here.

The reviewable plan accepts equal valid dual-key strings and rejects conflicts
or invalid peers. Internal Step.title/default model dumps remain unchanged;
both authored-plan serializers emit description, including ordinary rewrites.
Reading alone never rewrites a file. These are the proposed concrete boundary
choices for owner plan review; runtime code is unchanged.

## Commands and evidence

- Seed review checks the actual Step model, both serializers and version
  policy. Existing format/upgrade tests: 39 passed in 0.24s.
- `plan-tool --backend codex --model gpt-6.1-sol create step-description-alias
  --from-existing docs/implementation-plans/plan-seeds/step-description-alias.md
  --output-dir docs/implementation-plans --iterate -y < /dev/null`
  completes on the direct file-backed route. The initial preflight refusal
  (missing References) invokes no model; the corrected seed passes. Create
  archives the exact selected seed under plan-seeds/archive.
- `plan-tool --backend codex --model gpt-6.1-sol completeness-audit
  step-description-alias --iterate --commit --audit-passes 1 -y < /dev/null`
  clears the bare gate: 0/4 detailed, no conceptual findings; report
  `reports/20261022-135635-completeness.md`, confirmed-dry, not budget-limited.
  Bare completeness/detail application is withheld; no such findings exist.
- `plan-tool --backend codex --model gpt-6.1-sol detail
  step-description-alias --commit -y < /dev/null` completes all four details
  with per-step commits. Its embedded conceptual audit has no findings; its
  deterministic anchor check cannot resolve the field citation Step.title.
  Report `reports/20261022-140445-completeness.md` retains that diagnostic.
- Session-directed correction `fce79a600` verifies the field exists and cites
  the resolvable Step class with the field named separately, at both sibling
  sites. It also replaces three redundant prose-only test proposals with
  updates to existing policy checks. No implementation code changes.
- The same explicit iterative audit command clears the detail gate: 4/4
  detailed, no deterministic or conceptual findings; report
  `reports/20261022-140600-completeness.md`, confirmed-dry, not budget-limited.
  The three completed snapshots show clean bare concepts, one limited anchor
  diagnostic, then a clean complete bundle; no recurring material finding.

Report paths above are relative to
`docs/implementation-plans/plan-details/step-description-alias/`.
Logs are `.tmp/step-description-alias.*.log`. The audit revision binds plan
and detail digests; later bookkeeping changes do not claim to re-audit code.
No Claude Code /code-review convergence is claimed for this planning pass.
Both gates use the actual Codex-backed plan audit, not a substitute code review.

## Pickup

Review the plan and detail choices, then create its plan PR when requested.
Keep BACKLOG #517 while execution is pending. Do not implement before the
approved bundle is merged to the default branch; subsequent run requires its
own branch, --commit, reconcile-code tail and actual Claude Code review loop.
