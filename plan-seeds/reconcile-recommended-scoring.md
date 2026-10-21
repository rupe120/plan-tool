# Plan seed: deterministic reconcile-yield scoring + `review` pre-filter

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/reconcile-recommended-scoring.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per
step.

Source: BACKLOG #38 → promoted to IPPT-14 (2026-09-27). This seed carries
that entry's scope contract; the ticket holds the working brief.

> **Scope boundary — read before decomposing.** This seed adds a new plan
> frontmatter field. `DATA_CONTRACT.md`'s break rule holds that **any** new
> frontmatter key is a break, even an optional one (`Plan`/`Step` declare
> `extra="forbid"`). The entry this seed is drawn from did not account for
> this. **The format-version transition contract is not optional scope** —
> it is the first thing this plan must design, before the scorer or the
> dispatch flag.

## Outcome

`plan-tool detail` computes a deterministic (no-LLM) drift-likelihood score
per step at write time and records it in plan frontmatter;
`plan-tool reconcile-plan` surfaces those scores and gains an
`--auto-reconcile-above {maybe|yes}` flag that dispatches
`detail --reconcile --step N` only at or above the threshold — replacing
blind per-step reconcile iteration with targeted dispatch.

## In scope

- **The versioned-contract transition** (do this first): bump
  `PLAN_FORMAT_VERSION` past its current `1` in `plan_tool/schema.py`; extend
  `plan_tool/parser.py:upgrade_plan_frontmatter_to_current` with the new
  version's path from every prior supported version; document the new
  version in `DATA_CONTRACT.md` and `PLAN_FORMAT.md`; add fixtures proving
  both the upgrade and its refusal boundary (`MISSION.md` principle 2).
- `plan_tool/schema.py` (`Step`): new optional `reconcile_recommended:
  yes|maybe|no` field, plus optional `drift_likelihood: low|medium|high`.
  Distinct from `complexity` (implementation difficulty, not audit-yield
  likelihood).
- `plan_tool/detail.py` (or its writer path): a deterministic scoring helper
  weighing detail body length, citation density, `## Tests` /
  `## Acceptance criteria` section length, code-vs-detail mtime gap, and
  existing-code surface in `step.files`. Conservative toward `maybe`: a
  false-negative skip is costlier than a false-positive flag.
- `plan_tool/cli/review_cmd.py` (`reconcile-plan`): surfaces per-step scores;
  a new `--auto-reconcile-above {maybe|yes}` flag dispatches
  `detail --reconcile --step N` at or above the threshold. Default: surface
  only, no dispatch.

## Out of scope / Non-goals

- Any LLM-based scoring. The scorer is deterministic signals only.
- Changing `detail --reconcile`'s behavior when invoked directly by an
  operator (unaffected by this seed).
- Resolving the overlap with `review`'s existing low-confidence-hint
  suggested-action dispatch beyond naming it as a design question — decide
  during decomposition whether the two paths share plumbing or stay
  independent; do not silently merge or silently ignore the overlap.
- A rescore command for existing plans (`plan-tool annotate <slug>` rescore)
  — named as a future need by the source entry, not this seed's Outcome.

## Allowed behavior changes

None beyond the Outcome: plans written under the new format version carry
the new field; `reconcile-plan` gains the new flag and surfaced scores. A
plan at a prior supported version reads and writes exactly as documented by
the transition contract above — no other behavior change.

## Allowed reorganization

None beyond what the transition contract requires in `parser.py`.

## Verification

- A plan written at every prior supported format version round-trips through
  `upgrade_plan_frontmatter_to_current` to the new version.
- A plan at a version newer than what a given release supports refuses to
  read, per the support-window rule in `DATA_CONTRACT.md`.
- `reconcile-plan --auto-reconcile-above yes` dispatches only steps scored
  `yes` on a fixture plan with mixed scores; `maybe`/`no` steps are not
  dispatched.
- `uv run pytest tests/test_schema.py tests/test_data_contract.py
  tests/test_detail.py tests/cli/test_review_cmd.py -q` is green.

## Stop / defer

Stop and surface to the user if the format-version transition contract
cannot be written before the scorer or dispatch flag are designed — this
seed ships no schema break without it. Stop and surface the
low-confidence-hint overlap as an explicit decision rather than resolving it
by assumption.

## References

- `DATA_CONTRACT.md` § "Plan format" — the break rule (`extra="forbid"`,
  any new frontmatter key breaks) this seed's transition contract must
  satisfy first.
- `plan_tool/schema.py` (`PLAN_FORMAT_VERSION`, `Step`) — the version
  constant to bump and the model gaining the new field.
- `plan_tool/parser.py` (`upgrade_plan_frontmatter_to_current`) — where
  every prior version's upgrade path is defined.
- `plan_tool/detail.py`, `plan_tool/cli/review_cmd.py` — the scorer and the
  `reconcile-plan` dispatch flag this seed adds.

## Backlog reconciliation

`BACKLOG.md`'s `#38` entry is already a promotion stub pointing at IPPT-14.
No further backlog edit is required when this plan ships.
