> **Auto-archived**: this plan was swept on 2026-06-20 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Step Granularity Advisor
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: 'Add cycle-free granularity leaf: assess_granularity contract, GranularityEvidence,
    and deterministic split/merge signals'
  creates:
  - plan_tool/granularity.py
  - tests/test_granularity.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/step-granularity-advisor/01-cycle-free-granularity-leaf-assess.md
  status: done
- id: 2
  title: Fold detail's MIXED-STEP purity judgment behind the advisor as granularity-split
    (single path), keeping detail --split Phase B consuming it
  files:
  - plan_tool/detail.py
  - plan_tool/granularity.py
  - tests/test_detail.py
  - tests/test_granularity.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/step-granularity-advisor/02-fold-detail-mixed-step-purity-judgment.md
  status: done
- id: 3
  title: Wire create's change-type review loop to call assess_granularity(stage="create")
    for decompose-time granularity-split advice
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/step-granularity-advisor/03-wire-create-change-type-review-loop.md
  status: done
- id: 4
  title: Add completeness cross-step granularity audit via assess_granularity(stage="completeness"),
    emitted as advisory findings (rc stays 0 unless --fail-on-findings)
  files:
  - plan_tool/completeness_report.py
  - plan_tool/cli/completeness_phases.py
  - tests/test_completeness_report.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/step-granularity-advisor/04-completeness-cross-step-granularity.md
  status: done
- id: 5
  title: Document the granularity advisor leaf, the granularity-split/granularity-merge
    sources, and the merge-is-advisory-only deferral
  files:
  - CLAUDE.md
  - RUNBOOK.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/step-granularity-advisor/05-document-granularity-advisor-leaf.md
  status: done
---
# Step Granularity Advisor

## Overview

Adds a stage-agnostic step-granularity advisor: a new cycle-free leaf `plan_tool/granularity.py` exposing a stateless `assess_granularity` contract that emits split/merge *recommendations* through the existing `review.Recommendation` model, plus thin per-stage adapters (`create`, `detail`, `completeness`) that feed it whatever evidence each stage holds. The advisor is **advisory only** — it produces findings and never mutates plan structure. Only detail's MIXED-STEP kernel actuates today, through `detail --split` Phase B (preserved in step 2); the deterministic `granularity-split` recs surfaced at `create` and `completeness` are recommend-only because the `escalate-structural-findings-to-split.md` bridge is still `status: planning` (unwired). The `granularity-merge` recs are likewise recommend-only — the `plan-tool merge` executor has landed, but no automatic bridge routes a merge finding to it, so the operator hand-runs `plan-tool merge`. Load-bearing constraints: granularity findings obey the exit-code convention (rc stays 0 unless `--fail-on-findings`), and `granularity.py` imports only `schema` and `review`'s finding primitives (`Recommendation`, `_make_rec_id`, `Invoker`) so it remains an acyclic leaf below `create`/`detail`/`completeness`.

## Problem statement

Step-granularity reasoning is scattered and lopsided today. `create` leaves step count entirely to Claude's decomposition prompt, `detail` runs a purity MIXED-STEP self-check (split-only) buried in its prompt template, and `completeness` does no granularity reasoning at all. There is no merge reasoning anywhere, and no shared contract for "this step should be split / these steps should be merged." The result is ad-hoc, per-stage judgments with no single reusable place to decide granularity from each stage's own evidence.

## Architecture

A new leaf `plan_tool/granularity.py` imports only `schema` (Plan, Step, ChangeType) and `review` (`Recommendation`, `_make_rec_id`, `Invoker`); it has **no CLI and no orchestrator imports**, staying a cycle-free leaf below `create`/`detail`/`completeness` (same discipline as `backend.py`), which import *it*. It exposes a stateless contract:

```python
def assess_granularity(
    plan: Plan,
    *,
    stage: str,                 # "create" | "detail" | "completeness"
    evidence: GranularityEvidence,
    invoker: Optional[Invoker] = None,  # reserved-but-unused forward surface; no step calls it
) -> list[Recommendation]:
    ...
```

Output is always `Recommendation`s so the iteration loop and the split escalation bridge consume them uniformly. New sources: `source="granularity-split"` (step too big / mixes concerns — generalizes today's `detail-purity`, folded in, not forked) and `source="granularity-merge"` (adjacent dependent steps artificially fragmented — advisory only). The `granularity-split` source carries two severities under one source string: step 1's deterministic detectors emit `severity="info"`, while step 2's relocated MIXED-STEP kernel keeps `severity="medium"`. Both are non-apply-eligible, so a consumer isolating the kernel's recs filters on `severity == "medium"`.

The split between reusable and stage-specific work:

| Reusable (the leaf) | Stage-specific (the adapter) |
| --- | --- |
| The decision contract / function signature | What evidence is passed in |
| The `Recommendation` output shape + sources | The "is this mixed / too small?" determination from each stage's own evidence |
| Deterministic signals (file-set overlap, title conjunctions, mixed `change_type`, depends_on shape) | The deterministic lift of already-authored prose (only `detail` has prose, parsed — not live-judged); the `invoker` seam stays reserved-but-unused |

**Deterministic signals (in the leaf, no Claude).** Split smells: title conjunctions ("X **and** Y"), a step whose `files`/`creates` span unrelated areas, a title implying both refactor and feature verbs. Merge smells: two `depends_on`-adjacent steps that touch identical file sets; a refactor step with trivial scope feeding exactly one feature step; a step whose only dependent is the immediate next step and both are below a size floor.

**MIXED-STEP signal (deterministic parsing of Claude-authored prose).** The `detail` MIXED-STEP purity judgment (behavior-preserving vs behavior-changing) is relocated/wrapped behind the advisor rather than re-implemented — its kernel is deterministic regex parsing of the structural-findings prose Claude already authored during `detail`, not a fresh live judgment. The `invoker` seam is a reserved-but-unused forward surface (default `None`); no step calls it, and `test_*_never_calls_invoker` pins it unused.

**Stage adapters.** `create` — evidence = proposed step titles, `change_type`, `depends_on`, `files`/`creates` (no authored prose yet); decompose-time advice surfaced in the change-type review loop where `_SPLIT` already lives. `detail` — evidence = authored implementation prose; move the existing `_parse_purity_findings` MIXED-STEP detection behind the advisor's `granularity-split` source, and `detail --split` Phase B keeps consuming the same findings. `detail` intentionally calls that relocated kernel directly (via `collect_detail_quality_findings`/`generate_detail`); `assess_granularity(stage="detail")` and `GranularityEvidence.detail_bodies` are a forward-contract surface no orchestrator routes through, so the detail "adapter" is single-kernel reuse rather than a routed advisor call. `completeness` — evidence = whole-plan structure + all detail files; adds the cross-step granularity audit (fragmentation / bloat across the plan) that completeness does not do today, emitted as advisory findings.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3.13/library/dataclasses.html) — Reference for the @dataclass decorator, fields, and the 3.13 per-field __eq__ change — consulted when defining/extending the Recommendation model and the GranularityEvidence container.
- [typing — Support for type hints (Python 3.13)](https://docs.python.org/3.13/library/typing.html) — Authoritative spec for type hints used in the stateless assess_granularity contract, including keyword-only argument annotations and the Invoker callable shape.
- [subprocess — Subprocess management (Python 3.13)](https://docs.python.org/3.13/library/subprocess.html) — Reference for the shell-out mechanics behind the reserved-but-unused invoker seam; no step wires the detail-purity judgment through Claude — the kernel parses already-authored prose deterministically.
- [Python Language Reference — The import system (Python 3.13)](https://docs.python.org/3.13/reference/import.html) — Defines module import resolution and dependency semantics — relevant for keeping granularity.py a cycle-free leaf importing only schema and review's finding primitives (Recommendation, _make_rec_id, Invoker).
- [Claude Code — Headless mode](https://docs.anthropic.com/en/docs/claude-code/headless) — Official Anthropic guide to running the claude CLI non-interactively (-p / stdout, session resume) — the contract the real-CLI invoker defaults shell out against.
- [Claude Code — CLI reference](https://docs.anthropic.com/en/docs/claude-code/cli-reference) — Canonical list of claude CLI flags and defaults — relevant only to the reserved-but-unused invoker seam, which no step in this plan invokes for a granularity signal.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Any structural mutation — split execution lives in the `escalate-structural-findings-to-split.md` bridge; merge execution lives in `merge-steps-executor.md`.
- A merge command/engine/safety-gate (`plan-tool merge`, a `_merge_is_safe` gate, a merge mirror of `_apply_step_split`) — explicitly built elsewhere.
- A new decomposition *algorithm* in `create` — the advisor advises; Claude still decomposes.

## Risks

- **Purity logic forking into two code paths** — if `detail-purity` were duplicated rather than folded into the advisor, `detail --split` Phase B and the escalation bridge could diverge. Mitigation: route today's `detail-purity` finding through the advisor as a single `granularity-split` path, not two.
- **Leaf acquiring a cycle** — `granularity.py` gaining a CLI or orchestrator import would break its position below `create`/`detail`/`completeness`. Mitigation: constrain its imports to `schema` and `review`'s finding primitives (`Recommendation`, `_make_rec_id`, `Invoker`).
- **Merge findings with no auto-escalation bridge** — `granularity-merge` is recommend-only: the `plan-tool merge` executor has landed, but no automatic bridge routes a merge finding to it, so the operator must resolve fragmentation by hand-running `plan-tool merge` (or re-planning), and these findings can accumulate unactioned.
- **Findings flipping exit codes** — granularity findings are findings, not failure-to-complete; treating them as failures would violate the exit-code convention. Mitigation: rc stays 0 unless `--fail-on-findings`.
- **Rename desyncs the split-escalation bridge** — step 2 renames `source="detail-purity"` to `"granularity-split"`, but the `escalate-structural-findings-to-split.md` bridge (`status: planning`) is seeded entirely on the `detail-purity` literal — its `review.is_structural` predicate, its convergence-loop routing, and its acceptance criteria all key on that string, and that plan's own Deferred postpones the rename until this advisor lands. Landing step 2 silently invalidates the bridge's seed: its classifier would match nothing the advisor emits. Mitigation: landing step 2 obligates re-seeding that bridge on `granularity-split`, cross-referencing its postponed-rename deferral.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan_tool/granularity.py` imports only `schema` and `review` (`Recommendation`, `_make_rec_id`, `Invoker`) (no CLI, no orchestrator imports), and `create`/`detail`/`completeness` import it — verifiable by an import-graph/acyclicity check.
- `assess_granularity` returns `list[Recommendation]` for each `stage` value (`"create"`, `"detail"`, `"completeness"`).
- A step with a title conjunction, an unrelated `files`/`creates` span, or a title implying both refactor and feature verbs yields a `source="granularity-split"` recommendation with no Claude invocation.
- Two `depends_on`-adjacent steps touching identical file sets (or a trivial refactor feeding exactly one feature step) yield a `source="granularity-merge"` recommendation.
- The former `detail-purity` MIXED-STEP finding is emitted as `source="granularity-split"` through the advisor, and `detail --split` Phase B still consumes it unchanged (single code path, not forked from `_parse_purity_findings`).
- `source="granularity-split"` carries two severities under one source string: step 1's deterministic detectors emit `severity="info"` and step 2's relocated MIXED-STEP kernel keeps `severity="medium"`; both are non-apply-eligible, and a consumer isolating the kernel's recs filters on `severity == "medium"`.
- Granularity findings (split or merge) never flip the subcommand exit code: they are structurally excluded from the blocking gate, so rc stays 0 in both default and `--fail-on-findings` mode and the flag has no effect on them.
- The advisor never mutates plan structure: `granularity-merge` findings remain recommend-only regardless of mode, and the `create`/`completeness` `granularity-split` recs are likewise recommend-only — actuation via the `escalate-structural-findings-to-split.md` bridge is not-yet-landed (the bridge is `status: planning`). Only detail's MIXED-STEP kernel actuates today, through `detail --split` Phase B under its existing gates (`_split_is_safe`, TTY, opt-in).

## Deferred

- The MERGE half stays recommend-only because no automatic bridge wires a `granularity-merge` finding to an actuating command. The `plan-tool merge` executor (split's `_apply_step_split` mirror, downstream-detail migration, the `_merge_is_safe` gate, and the `plan-tool merge` command) has already landed; `granularity-merge` findings are emitted now, but actuation waits on that auto-escalation bridge — until it ships the operator hand-runs `plan-tool merge`.
