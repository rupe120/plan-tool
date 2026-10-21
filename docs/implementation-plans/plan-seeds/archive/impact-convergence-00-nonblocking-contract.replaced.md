> **Replaced**: this file has been superseded by `docs/implementation-plans/2-trace-high-impact-contract.md`.
> Preserved here for history; do not edit.

# Plan seed: resolve the reachable non-blocking, high-impact recommendation contract before #152

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing docs/implementation-plans/plan-seeds/impact-convergence-00-nonblocking-contract.md --iterate
```

> **Source:** `BACKLOG.md` **#157** — “Resolve the impact-bearing non-blocking
> severity contract before #152’s augment gate.” This is a prerequisite for
> #152’s augment slice and therefore for the declared #153/#154 sequencing.
> The final status step must update #157 and #152 accurately: authoring alone
> does not mark either item shipped; record the resulting evidence and leave
> #152 blocked until a valid implementation scope is established.

## Problem statement

#152’s seed and scope contract use a `medium`-severity, `impact=high` finding
as the example that the proposed augment predicate newly promotes. At HEAD,
`is_blocking` already blocks `medium`; the parser also maps Claude `LOW` to
`medium`. The proposed example therefore does not demonstrate an added behavior.
The plan must trace the real parsed `Recommendation` severity/impact vocabulary
and the loop-continuation input paths to establish whether a non-blocking
recommendation can carry `impact=high` and reach a continuation gate. It must
not assume the answer is `low`, `nit`, or `info` before grounding it in code and
fixtures.

## Scope contract (inherited from #157)

- **Outcome:** a grounded, testable #152 augment scenario whose impact axis can
  add a blocking result beyond the existing severity rule.
- **In scope:** the severity parser/map, `Recommendation` construction, and the
  existing continuation-gate input paths needed to trace that scenario; #152’s
  seed/plan/backlog wording after the evidence is established.
- **Out of scope / Non-goals:** implementing the #152 predicate/call-site swaps,
  changing the prompt/schema vocabulary, recurrence routing (#153), calibration
  (#154), or impact-only demotion.
- **Allowed behavior changes:** none until the evidence determines a valid #152
  implementation; this is a read/trace-and-re-scope decision.
- **Allowed reorganization:** none.
- **Verification:** tests or saved fixtures demonstrate the selected
  non-blocking, `impact=high` input reaches the claimed gate; otherwise the
  corrected #152 scope explicitly says no observable augment exists today.
- **Stop / defer:** a need for new impact emission/plumbing becomes a separate
  backlog entry, not an implicit expansion of #152.

## Grounding seams

- `plan_tool/review.py` — `Recommendation`, `_CLAUDE_SEVERITY_MAP`, triage-tag
  parsing, and construction paths for audit/reconcile recommendations.
- `plan_tool/convergence.py` — `is_blocking`, `ConvergenceState`, and
  `should_continue`’s continuation contract.
- `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/reconcile.py`, and
  `plan_tool/review.py` — the seven #152 continuation/materiality sites and the
  actual collections they inspect.
- Existing tests/fixtures that construct recommendations and exercise
  completeness, reconcile, and review convergence paths.

## Required plan outcomes

1. Trace and document the exact severity normalization plus the set of parsed
   recommendation shapes that can have `impact=high`.
2. Trace which of those shapes can reach each named #152 continuation site, with
   a minimal deterministic fixture/test strategy proving the result.
3. Re-scope #152, its archived/replacement seed as appropriate, and its backlog
   contract only from that evidence. If no reachable non-blocking high-impact
   shape exists, state that the augment has no observable behavior today and
   defer any new plumbing as a separate backlog item.
4. Update #157/#152 status and the arc dependency wording without claiming
   implementation has shipped.

## Acceptance criteria

- The plan distinguishes normalized severity values from prompt labels and
  identifies every currently reachable non-blocking shape that can carry
  `impact=high`, or records grounded evidence that none exists.
- The plan identifies exactly which #152 continuation sites can observe each
  candidate, rather than assuming every site sees the same recommendation list.
- The proposed verification uses existing test homes/fixtures and proves the
  chosen result without adding production behavior.
- #152’s future implementation scope is corrected only to the evidence found;
  no predicate/call-site change, prompt/schema change, or new plumbing is added.
- `BACKLOG.md` records #157 as plan-authored while execution remains pending and
  retains #152 as blocked until #157’s evidence is implemented/reconciled.
