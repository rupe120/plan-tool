> **Replaced**: this file has been superseded by `docs/implementation-plans/2-step-granularity-advisor.md`.
> Preserved here for history; do not edit.

## Overview

Adds a stage-agnostic step-granularity advisor: a new cycle-free leaf `plan_tool/granularity.py` exposing a stateless `assess_granularity` contract that emits split/merge *recommendations* through the existing `review.Recommendation` model, plus thin per-stage adapters (`create`, `detail`, `completeness`) that feed it whatever evidence each stage holds. The advisor is **advisory only** — it produces findings and never mutates plan structure; SPLIT findings are executed downstream by the existing split engine via the `escalate-structural-findings-to-split.md` bridge, while MERGE findings stay recommend-only because no merge executor exists yet. Load-bearing constraints: granularity findings obey the exit-code convention (rc stays 0 unless `--fail-on-findings`), and `granularity.py` imports only `schema` + the `Recommendation` shape so it remains an acyclic leaf below `create`/`detail`/`completeness`.

## Problem statement

Step-granularity reasoning is scattered and lopsided today. `create` leaves step count entirely to Claude's decomposition prompt, `detail` runs a purity MIXED-STEP self-check (split-only) buried in its prompt template, and `completeness` does no granularity reasoning at all. There is no merge reasoning anywhere, and no shared contract for "this step should be split / these steps should be merged." The result is ad-hoc, per-stage judgments with no single reusable place to decide granularity from each stage's own evidence.

## Architecture

A new leaf `plan_tool/granularity.py` imports only `schema` (Plan, Step, ChangeType) and `review.Recommendation`; it has **no CLI and no orchestrator imports**, staying a cycle-free leaf below `create`/`detail`/`completeness` (same discipline as `backend.py`), which import *it*. It exposes a stateless contract:

```python
def assess_granularity(
    plan: Plan,
    *,
    stage: str,                 # "create" | "detail" | "completeness"
    evidence: GranularityEvidence,
    invoker: Invoker = ...,     # only used where prose judgment is needed
) -> list[Recommendation]:
    ...
```

Output is always `Recommendation`s so the iteration loop and the split escalation bridge consume them uniformly. New sources: `source="granularity-split"` (step too big / mixes concerns — generalizes today's `detail-purity`, folded in, not forked) and `source="granularity-merge"` (adjacent dependent steps artificially fragmented — advisory only).

The split between reusable and stage-specific work:

| Reusable (the leaf) | Stage-specific (the adapter) |
| --- | --- |
| The decision contract / function signature | What evidence is passed in |
| The `Recommendation` output shape + sources | The semantic "is this mixed / too small?" call |
| Deterministic signals (file-set overlap, title conjunctions, mixed `change_type`, depends_on shape) | The Claude-judged prose signals (only `detail` has prose) |

**Deterministic signals (in the leaf, no Claude).** Split smells: title conjunctions ("X **and** Y"), a step whose `files`/`creates` span unrelated areas, an implied mix of refactor + feature `change_type`. Merge smells: two `depends_on`-adjacent steps that touch identical file sets; a refactor step with trivial scope feeding exactly one feature step; a step whose only dependent is the immediate next step and both are below a size floor.

**Semantic signal (behind the invoker seam).** The `detail` MIXED-STEP purity judgment (behavior-preserving vs behavior-changing) is relocated/wrapped behind the advisor rather than re-implemented.

**Stage adapters.** `create` — evidence = proposed step titles, `change_type`, `depends_on`, `files`/`creates` (no authored prose yet); decompose-time advice surfaced in the change-type review loop where `_SPLIT` already lives. `detail` — evidence = authored implementation prose; move the existing `_parse_purity_findings` MIXED-STEP detection behind the advisor's `granularity-split` source, and `detail --split` Phase B keeps consuming the same findings. `completeness` — evidence = whole-plan structure + all detail files; adds the cross-step granularity audit (fragmentation / bloat across the plan) that completeness does not do today, emitted as advisory findings.

## Out of scope

- Any structural mutation — split execution lives in the `escalate-structural-findings-to-split.md` bridge; merge execution lives in `merge-steps-executor.md`.
- A merge command/engine/safety-gate (`plan-tool merge`, a `_merge_is_safe` gate, a merge mirror of `_apply_step_split`) — explicitly built elsewhere.
- A new decomposition *algorithm* in `create` — the advisor advises; Claude still decomposes.

## Risks

- **Purity logic forking into two code paths** — if `detail-purity` were duplicated rather than folded into the advisor, `detail --split` Phase B and the escalation bridge could diverge. Mitigation: route today's `detail-purity` finding through the advisor as a single `granularity-split` path, not two.
- **Leaf acquiring a cycle** — `granularity.py` gaining a CLI or orchestrator import would break its position below `create`/`detail`/`completeness`. Mitigation: constrain its imports to `schema` + the `Recommendation` shape.
- **Merge findings with no executor** — `granularity-merge` is advisory only until `merge-steps-executor.md` lands; the operator must resolve fragmentation by hand or re-plan, so these findings can accumulate unactioned.
- **Findings flipping exit codes** — granularity findings are findings, not failure-to-complete; treating them as failures would violate the exit-code convention. Mitigation: rc stays 0 unless `--fail-on-findings`.

## Acceptance criteria

- `plan_tool/granularity.py` imports only `schema` and `review.Recommendation` (no CLI, no orchestrator imports), and `create`/`detail`/`completeness` import it — verifiable by an import-graph/acyclicity check.
- `assess_granularity` returns `list[Recommendation]` for each `stage` value (`"create"`, `"detail"`, `"completeness"`).
- A step with a title conjunction, an unrelated `files`/`creates` span, or a mixed refactor+feature `change_type` yields a `source="granularity-split"` recommendation with no Claude invocation.
- Two `depends_on`-adjacent steps touching identical file sets (or a trivial refactor feeding exactly one feature step) yield a `source="granularity-merge"` recommendation.
- The former `detail-purity` MIXED-STEP finding is emitted as `source="granularity-split"` through the advisor, and `detail --split` Phase B still consumes it unchanged (single code path, not forked from `_parse_purity_findings`).
- Granularity findings (split or merge) leave the subcommand exit code at 0 unless `--fail-on-findings` is passed.
- The advisor never mutates plan structure: `granularity-merge` findings remain recommend-only regardless of mode, and splits execute only via the bridge's existing gates (`_split_is_safe`, TTY, opt-in).

## Deferred

- The MERGE half stays advisory-only until `merge-steps-executor.md` (the merge executor — a mirror of split's `_apply_step_split`, downstream-detail migration, a `_merge_is_safe` gate, and a `plan-tool merge` command) lands; `granularity-merge` findings are emitted now but cannot be actuated until that dependency ships.
