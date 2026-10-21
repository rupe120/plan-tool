> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Completeness Apply Split Bridge
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Produce the mixed refactor+feature split finding in the completeness audit
  files:
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/completeness-apply-split-bridge/01-produce-mixed-refactor-feature-split.md
  status: done
- id: 2
  title: Persist the medium mixed-step split finding to the completeness sidecar
  files:
  - plan_tool/cli/completeness_phases.py
  - DATA_CONTRACT.md
  - tests/cli/test_completeness_cmd.py
  - tests/test_data_contract.py
  allowed_mentions:
  - plan_tool/cli/completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/completeness-apply-split-bridge/02-persist-medium-mixed-step-split-finding.md
  status: done
- id: 3
  title: Route the split finding to the escalate-to-split bridge in the apply walk
  files:
  - plan_tool/review_walk.py
  - plan_tool/cli/review_actions.py
  - tests/test_review_walk.py
  - tests/cli/test_review_actions.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/completeness-apply-split-bridge/03-route-split-finding-escalate-split.md
  status: done
- id: 4
  title: Add --apply-structural to completeness-apply and gate the split dispatch
  files:
  - plan_tool/cli/completeness_cmd.py
  - tests/cli/test_completeness_cmd.py
  allowed_mentions:
  - plan_tool/cli/completeness_phases.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/completeness-apply-split-bridge/04-apply-structural-completeness-apply.md
  status: done
- id: 5
  title: Update docs and backlog for the completeness-apply split bridge
  files:
  - CLAUDE.md
  - RUNBOOK.md
  - docs/cli/completeness-apply.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 4
  detail: docs/implementation-plans/plan-details/completeness-apply-split-bridge/05-update-docs-backlog-completeness-apply.md
  status: done
---
# Completeness Apply Split Bridge

## Overview

Wires the `completeness-apply` walk to dispatch a `granularity-split` MIXED-STEP finding to the already-shipped `escalate_to_split` bridge, closing the convergence gap between "the audit knows a step must split" and "the plan structure is actually split". Today that finding lands as triage prose and the operator must split/renumber/re-author by hand; this plan routes it through the same opt-in + TTY-confirm gate the merge/re-ground bridges use. The bridge itself is unchanged — this is the wiring into the completeness-apply lane, plus **producing** the `medium` MIXED-STEP finding (a new per-step Claude purity pass, since the completeness lane mints no `medium` finding today) and persisting it to the saved sidecar so the apply walk can see it. Builds the "Completeness-apply split bridge" arm of BACKLOG #70.

## Problem statement

When `completeness-apply` (serial `--jobs 1` interactive walk) replays a saved conceptual gap map, a `granularity-split` MIXED-STEP finding ("step mixes refactor + feature") is left as **triage prose** — the operator must split / renumber / re-author the plan by hand, even though `escalate_to_split` already owns the whole split mechanism. Worse, today the completeness lane produces no `medium` MIXED-STEP finding at all: in `cli/completeness_phases.py`, the only granularity pass is `assess_granularity(stage="completeness", invoker=None)` (≈547), which runs just the deterministic `info` title/area detectors — the Claude-judged `parse_mixed_step_findings` kernel fires only under `stage=="detail"` (`granularity.py:132`), so no `medium` rec is minted here. Even the `info` recs only reach report prose: they fold into `smell_recs` (≈550–552) while the persisted `sidecar_recs = correctness + conceptual + data_contract` (≈1371–1375) **exclude** them, and the apply walk replays `saved.recommendations` (= `sidecar_recs`). So the apply walk sees no granularity-split finding — the `medium` one because it is never produced, the `info` ones because they are never persisted. This surfaced while hardening `parallel-rate-limit-switch-scope` (2026-07-08): detail/completeness correctly found step 1 mixed a refactor with a feature, but the apply path did not route that structural finding to split. The review/reconcile walk already routes a `BLOCKED-STRUCTURAL` verdict through `cli/review_actions.py:_dispatch_structural_escalation` → `escalate_to_split`; the completeness lane lacks the equivalent wiring.

## Architecture

Three coordinated changes, no new bridge logic. **(1) Produce the finding.** Today the completeness lane runs only `assess_granularity(stage="completeness", invoker=None)`, which mints the deterministic `info` title/area detectors — the Claude-judged `medium` MIXED-STEP `granularity-split` rec (`granularity.parse_mixed_step_findings`, ≈439–498, `step_id=step.id`) is **never produced** in this lane today; it fires only under `stage=="detail"`. Step 1 adds a per-step Claude purity pass to `cli/completeness_phases.py` that runs that judgment and folds the resulting `medium` rec into `smell_recs`. This is a real behavior/cost change — a Claude call inside the previously no-Claude deterministic phase — gated to fire once per audit. **(2) Persist the finding.** Add this `medium`+ signal to `sidecar_recs` so the apply walk replays it. The `info` deterministic title/area detectors (`_split_findings`) stay advisory/report-only in the `Smells (advisory)` bucket — dispatching only the higher-confidence Claude-judged `medium` signal avoids firing a structural mutation off a low-confidence title heuristic. Because the sidecar shape is drift-guarded, `DATA_CONTRACT.md` is updated in the same plan and `tests/test_data_contract.py` stays green.

**(3) Dispatch the finding.** Add a structural-dispatch path so `review_walk.is_dispatchable` (≈238–276, four qualifying paths today, none matching `granularity-split`) routes the finding, and reuse `cli/review_actions.py:_dispatch_structural_escalation` (≈788–868) rather than forking a second escalation body — it already takes a `rec` with `step_id`, wires `shell_claude_invoker`, `allow_split`, `prompt_fn=None`, guards `rec.step_id is None` (plan-level → "re-decompose by hand"), and maps all five `EscalateResult.outcome` values to a one-line walk status. The completeness lane calls it, threading `allow_split` from the structural opt-in. The apply walk seams are `cli/completeness_cmd.py`: `_SAVED_SERIAL_APPLY_SOURCE_RANK` (≈266–268), `_build_review_action_fn(..., extra_apply_sources=_walk_apply_sources)` (≈484–495), and `review_walk.walk_recommendations(..., extra_apply_sources=...)` (≈521–528).

This mirrors merge/re-ground: `granularity-split` stays **out** of `review.py`'s `APPLY_ELIGIBLE_SOURCES` and **in** `STRUCTURAL_SOURCES` (it is not an `apply_finding` edit); it is a structural dispatch, not an apply edit. Safety keys entirely on the shipped `split_safety.split_is_safe(plan, target_id)` — the single choke point that blocks when any `s.id >= target_id and s.status != StepStatus.PENDING` (both CURRENT and DONE; parked deferred/wont_do stay PENDING → safe) — no second safety notion is forked in the completeness lane. Gate = the new `--apply-structural` opt-in on `completeness-apply` (step 4), gated only by `and not -y` (`allow_split = bool(args.apply_structural) and not args.yes`) — **not** `--include-info`, which governs info-severity gaps, not the `medium` split — plus `escalate_to_split`'s `allow_split` + interactive `_confirm_split`; with the flag absent, or under `-y`/`yes_to_all`, or in the parallel `--jobs > 1` lane, the walk recommends only (prints the runnable `plan-tool split <plan> --step N --into ... --into ...`), spends no Claude, and mutates nothing — mirroring `escalate_to_split`'s `allow_split=(allow_split and not yes_to_all)` invariant so structural mutation never happens unattended. On an `applied` outcome the 1→2 split renumbers every step from the target onward, invalidating every other saved finding's `step_id`/anchor, so the walk **halts** and instructs a re-audit rather than applying subsequent findings against stale ids (analogous to the review walk short-circuiting on `BLOCKED-STRUCTURAL`); `recommended`/`unsafe`/other outcomes record a one-line status and continue.

## References

- [concurrent.futures — Launching parallel tasks (Python docs)](https://docs.python.org/3/library/concurrent.futures.html) — Official ThreadPoolExecutor / submit / map reference, needed for the `--jobs > 1` parallel-apply lane that fans applies out with B1-style failure isolation.
- [git-worktree Documentation (git-scm)](https://git-scm.com/docs/git-worktree) — Canonical reference for `worktree add/list/remove/prune`, the mechanism behind each parallel apply worker running in its own isolated worktree off HEAD.
- [git-status Documentation (git-scm)](https://git-scm.com/docs/git-status) — Documents `--porcelain` v1/v2 machine-readable output, the format an implementer would parse for the deferred run-evidence hardening of `split_is_safe` and the clean-tree gate.
- [argparse — Parser for command-line options (Python docs)](https://docs.python.org/3/library/argparse.html) — Reference for add_argument/subparsers/flags, needed to wire the `--apply-structural` / `--include-info` opt-in and recommend-only defaults into the completeness-apply CLI.
- [pytest — Working with custom markers](https://docs.pytest.org/en/stable/how-to/mark.html) — Explains registering and using custom markers like `@pytest.mark.integration` and the `allow_real_claude` opt-out that the plan's unit-first tests rely on.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **The other three #70 arms** — multi-step/region carve, per-remedy `--merge`/`--reground` walk flags + dispatcher consolidation, and the code-reveals-a-split reconcile producer — stay open under #70; this plan is the completeness-apply split bridge arm only.
- **`create`-side structural dispatch** — `create.py`'s convergence loop still does not route through `escalate_to_split` (the create-side trigger is separately deferred per CLAUDE.md); this plan is completeness-apply only.
- **The `info` deterministic granularity detectors** (`_split_findings`) — they remain report-only advisory in the `Smells (advisory)` bucket; only the `medium` MIXED-STEP signal becomes dispatchable.

## Risks

- **Data-contract drift:** adding `granularity-split` to `sidecar_recs` changes what the persisted gap map can contain and is drift-guarded by `DATA_CONTRACT.md` + `tests/test_data_contract.py`; mitigation is updating the contract doc in the same plan and keeping the guard green.
- **Stale gap map after a split (post-apply window):** a 1→2 split renumbers every step from the target onward, so applying later saved findings against the old ids would target wrong steps; mitigated by halting the walk on an `applied` outcome and instructing a re-audit. This halt is also what handles a plan carrying **two** `granularity-split` findings: the first applied split renumbers the second's `step_id`, so the walk halts after the first and the second mixed step is deferred to the post-split re-audit rather than split against a stale id.
- **Stale `step_id` before the split (pre-apply window) — do NOT use a whole-plan fingerprint guard:** the dispatch routes through `_dispatch_structural_escalation` → `escalate_to_split(step_id=rec.step_id)` using the `step_id` persisted at audit time. A tempting guard is a whole-plan fingerprint check (`saved_plan_fingerprint != compute_plan_fingerprint(plan_path)`, as `_dispatch_reground_remedy` uses) — but that is **wrong here** and must not be added: in the normal serial walk the earlier rank-0/1/2 conceptual applies edit plan/detail **bytes without renumbering steps**, so the fingerprint changes while `step_id` stays valid; a fingerprint guard would then downgrade the split to recommend-only on *every* walk that applied any prior finding, making the headline "applies the 1→2 split" path unreachable in the common case. The real invariant is narrower: **no same-walk apply renumbers steps** (only the split does, and it is ranked last and halts the walk), so the `step_id` cannot go stale *within* a walk. The only residual risk is an **external** edit between audit and apply that renumbers steps to a different valid id; `escalate_to_split` re-parses the plan from disk and returns `step-missing` if the id is gone, which covers the delete case. The rare "renumbered to a *different valid* step" case is precisely BACKLOG **#93** (precise per-step-id staleness, replacing the coarse whole-plan fingerprint) — **deferred to #93**, not solved with a coarse guard that breaks the common path. This is distinct from the post-apply window above.
- **Unattended structural mutation:** a blanket `-y` fast-forward or a `--jobs > 1` worktree worker must never reshape the plan spine; mitigated by recommending-only under `-y`/`yes_to_all` and by **excluding** `granularity-split` from the parallel `_CONCEPTUAL_APPLY_SOURCE_RANK` entirely (step 4), so the `--jobs > 1` lane never processes it — mirroring `escalate_to_split`'s `allow_split=(allow_split and not yes_to_all)` invariant. **But the exclusion must not be silent** (see the parallel-lane skip risk below).
- **Parallel lane silently drops the split:** step 4 keeps `granularity-split` out of `_CONCEPTUAL_APPLY_SOURCE_RANK`, and `completeness-apply` degrades to serial only when `not conceptual_walk_recs and walk_recs` — so a **mixed** sidecar (conceptual gaps + a split finding) runs `_apply_walk_recs_parallel(conceptual_walk_recs, …)` under `--jobs > 1` and reports "done" while the split **vanishes with no notice**, violating the codebase's "no silent caps" rule. Mitigation (step 4): when a `medium` `granularity-split` is present but the parallel lane will not process it, **emit an operator-facing breadcrumb** — a one-line "N mixed-step split(s) pending; re-run the serial walk (`--jobs 1`) with `--apply-structural` to act on them" notice — so the pending split is never dropped silently.
- **Low-confidence trigger — dispatch must also gate on `severity == "medium"`:** the `medium`-only guarantee cannot rest on step 2's persistence filter alone, because the dispatch predicate keys on the `source` literal, and the deterministic `info` detectors emit the **same** `source="granularity-split"`. So **both** the `is_dispatchable` recognizer (step 3) **and** the `action(rec)` router branch (step 3) must gate on `rec.severity == "medium"`, not `source` alone — otherwise any future path that persisted an `info` granularity-split would dispatch it to `escalate_to_split` and split off a low-confidence title heuristic, the exact outcome this risk prevents. Keeping `info` detectors advisory is necessary but not sufficient; the severity gate on dispatch is the load-bearing guard.
- **Added Claude cost on a previously no-Claude phase:** step 1's MIXED-STEP purity pass adds a Claude call **per pending code step, per audit round** to the phase-1 deterministic well-formedness battery (formerly no-Claude). "Once per audit" means once per step *per round* (a dedicated call site, not the per-checkpoint path) — so under `--iterate` the total is **(pending-code-steps × iterate-rounds)** detail-quality calls, not a single call. The spend is real and scales with plan size × audit depth; operators tuning audit depth should account for it.
- **Bare/partial-plan gate skips the split too:** `completeness-apply`'s `is_bare` gate `return 0`s the entire saved walk when *any* step lacks a detail bundle (`review.py:DetailBundleStatus.is_bare` is True for a partially-detailed plan), yet step 1's purity pass fires per *detailed* step — so a partial plan can persist a `medium` `granularity-split` against a fully-detailed mixed step that the apply walk then skips with the generic "conceptual apply requires a complete detail bundle" warning, neither dispatching nor printing the recommend-only `plan-tool split …`. This is a **known limitation**: on a partial plan the split finding is not actionable until every sibling step is detailed (the same "an action can only target what exists" gate the completeness surface already enforces). Name it so an operator isn't surprised the AC's "recommends only" is inert on partial plans; a finer gate (skip only the undetailed steps' findings) is out of scope here.

## Testing

Unit-first, with the conftest autouse gate never seeing a real backend spawn — stub `escalate_to_split` / the split proposer throughout.
- `tests/cli/test_completeness_cmd.py` — sidecar now carries a `medium` granularity-split (extend/counter the existing folds-into-smells test at ≈699); the apply walk dispatches it to a **stubbed** `escalate_to_split`; assert recommend-only under no-flag / `-y` / unsafe.
- `tests/cli/test_review_actions.py` — `TestStructuralEscalation` is the template for the outcome→status mapping if a completeness-side wrapper is added.
- `tests/test_review_walk.py` — add a new dispatchable path for `granularity-split` (the merge/re-ground dispatchability tests ≈2748–2812 are the analog).
- `tests/test_data_contract.py` — the sidecar-shape drift guard must stay green with the new source persisted.
- Seam discipline: stub `escalate_to_split` / the split proposer; do not spawn real Claude.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- A saved conceptual gap map containing a `medium` `granularity-split` MIXED-STEP finding (resolvable `step_id`), walked by `completeness-apply` **with the structural opt-in + an interactive confirm on a safe plan**, dispatches to `escalate_to_split` and **applies** the 1→2 split (plan renumbered, downstream detail files migrated) — the operator does not hand-edit the plan.
- In the **serial** walk, **without** the opt-in, under `-y`, on an **unsafe** plan (a non-PENDING step at/after the target), or a declined/non-TTY confirm → the walk **recommends only**: it prints the runnable `plan-tool split … --step N --into …`, spends **no Claude on mutation**, and leaves plan + detail files byte-unchanged (only `applied` mutated).
- In the **parallel** lane (`--jobs > 1`), `granularity-split` is **excluded from `_CONCEPTUAL_APPLY_SOURCE_RANK`**, so the finding is **not processed** — no split. This is the deliberate parallel-lane safety mechanism (never mutate the spine unattended), not a recommend-only surface. To honor "no silent caps," when a `medium` `granularity-split` is present the parallel lane **emits a one-line breadcrumb** naming the pending split(s) and directing the operator to re-run the **serial** walk (`--jobs 1`) with `--apply-structural`. (Documented limitation, mirrored in Deferred.)
- A `granularity-split` `medium` finding is now **persisted to the saved sidecar** (not report-prose only), `DATA_CONTRACT.md` documents the addition, and its drift guard stays green; the `info` deterministic granularity detectors remain report-only advisory.
- On an **applied** split the walk **halts and instructs a re-audit** (stale gap map), and does not apply any later saved finding against the now-renumbered ids.
- `granularity-split` stays **out** of `APPLY_ELIGIBLE_SOURCES` and does **not** flip an exit code; the new path is a structural dispatch, not an `apply_finding` edit.
- Docs updated: `CLAUDE.md` (the escalate-to-split bridge *callers* list gains the completeness-apply lane), `RUNBOOK.md` (operator walkthrough), `docs/cli/completeness-apply.md` (the new opt-in + recommend-only default), and **`BACKLOG.md` #70** (remove the completeness-apply split bridge bullet from *Remaining*, note the ship date).

## Deferred

- **Run-evidence hardening of `split_is_safe`** beyond the `status` field (consulting run-log `run-started` markers or `git status --porcelain`) — a separate change to the single choke point, affecting every `escalate_to_split` caller, not just this bridge. Note it; do not bundle it.
- **Parallel-lane structural mutation** — the `--jobs > 1` worktree lane stays recommend-only for structural findings (decision 3); building safe parallel structural apply is future design.
- **`create`-side structural dispatch** — deferred per CLAUDE.md; this plan is completeness-apply only.
- **The other three #70 arms** — multi-step/region carve, per-remedy `--merge`/`--reground` walk flags + dispatcher consolidation, and the code-reveals-a-split reconcile producer — stay open under #70.
