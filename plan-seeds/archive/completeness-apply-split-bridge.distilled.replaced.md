> **Replaced**: this file has been superseded by `docs/implementation-plans/2-completeness-apply-split-bridge.md`.
> Preserved here for history; do not edit.

## Overview

Wires the `completeness-apply` walk to dispatch a `granularity-split` MIXED-STEP finding to the already-shipped `escalate_to_split` bridge, closing the convergence gap between "the audit knows a step must split" and "the plan structure is actually split". Today that finding lands as triage prose and the operator must split/renumber/re-author by hand; this plan routes it through the same opt-in + TTY-confirm gate the merge/re-ground bridges use. The bridge itself is unchanged — this is the wiring into the completeness-apply lane, plus persisting the finding to the saved sidecar so the apply walk can see it. Builds the "Completeness-apply split bridge" arm of BACKLOG #70.

## Problem statement

When `completeness-apply` (serial `--jobs 1` interactive walk) replays a saved conceptual gap map, a `granularity-split` MIXED-STEP finding ("step mixes refactor + feature") is left as **triage prose** — the operator must split / renumber / re-author the plan by hand, even though `escalate_to_split` already owns the whole split mechanism. Worse, the finding never even reaches the apply walk: in `cli/completeness_phases.py`, `granularity_recs` fold into `smell_recs` (≈550–552) and the persisted `sidecar_recs = correctness + conceptual + data_contract` (≈1371–1375) **exclude** them, so they reach report prose only; the apply walk replays `saved.recommendations` (= `sidecar_recs`) and never sees a granularity-split finding. This surfaced while hardening `parallel-rate-limit-switch-scope` (2026-07-08): detail/completeness correctly found step 1 mixed a refactor with a feature, but the apply path did not route that structural finding to split. The review/reconcile walk already routes a `BLOCKED-STRUCTURAL` verdict through `cli/review_actions.py:_dispatch_structural_escalation` → `escalate_to_split`; the completeness lane lacks the equivalent wiring.

## Architecture

Two coordinated changes, no new bridge logic. **(1) Persist the finding.** `granularity.parse_mixed_step_findings` (≈439–498) emits the `medium` MIXED-STEP `granularity-split` rec with `step_id=step.id`; add this `medium`+ signal to `sidecar_recs` so the apply walk replays it. The `info` deterministic title/area detectors (`_split_findings`) stay advisory/report-only in the `Smells (advisory)` bucket — dispatching only the higher-confidence Claude-judged `medium` signal avoids firing a structural mutation off a low-confidence title heuristic. Because the sidecar shape is drift-guarded, `DATA_CONTRACT.md` is updated in the same plan and `tests/test_data_contract.py` stays green.

**(2) Dispatch the finding.** Add a structural-dispatch path so `review_walk.is_dispatchable` (≈238–276, four qualifying paths today, none matching `granularity-split`) routes the finding, and reuse `cli/review_actions.py:_dispatch_structural_escalation` (≈788–868) rather than forking a second escalation body — it already takes a `rec` with `step_id`, wires `shell_claude_invoker`, `allow_split`, `prompt_fn=None`, guards `rec.step_id is None` (plan-level → "re-decompose by hand"), and maps all five `EscalateResult.outcome` values to a one-line walk status. The completeness lane calls it, threading `allow_split` from the structural opt-in. The apply walk seams are `cli/completeness_cmd.py`: `_SAVED_SERIAL_APPLY_SOURCE_RANK` (≈266–268), `_build_review_action_fn(..., extra_apply_sources=_walk_apply_sources)` (≈484–495), and `review_walk.walk_recommendations(..., extra_apply_sources=...)` (≈521–528).

This mirrors merge/re-ground: `granularity-split` stays **out** of `review.py`'s `APPLY_ELIGIBLE_SOURCES` and **in** `STRUCTURAL_SOURCES` (it is not an `apply_finding` edit); it is a structural dispatch, not an apply edit. Safety keys entirely on the shipped `split_safety.split_is_safe(plan, target_id)` — the single choke point that blocks when any `s.id >= target_id and s.status != StepStatus.PENDING` (both CURRENT and DONE; parked deferred/wont_do stay PENDING → safe) — no second safety notion is forked in the completeness lane. Gate = the existing `--apply-structural`/`--include-info` opt-in + `escalate_to_split`'s `allow_split` + interactive `_confirm_split`; with the flag absent, or under `-y`/`yes_to_all`, or in the parallel `--jobs > 1` lane, the walk recommends only (prints the runnable `plan-tool split <plan> --step N --into ... --into ...`), spends no Claude, and mutates nothing — mirroring `escalate_to_split`'s `allow_split=(allow_split and not yes_to_all)` invariant so structural mutation never happens unattended. On an `applied` outcome the 1→2 split renumbers every step from the target onward, invalidating every other saved finding's `step_id`/anchor, so the walk **halts** and instructs a re-audit rather than applying subsequent findings against stale ids (analogous to the review walk short-circuiting on `BLOCKED-STRUCTURAL`); `recommended`/`unsafe`/other outcomes record a one-line status and continue.

## Out of scope

- **The other three #70 arms** — multi-step/region carve, per-remedy `--merge`/`--reground` walk flags + dispatcher consolidation, and the code-reveals-a-split reconcile producer — stay open under #70; this plan is the completeness-apply split bridge arm only.
- **`create`-side structural dispatch** — `create.py`'s convergence loop still does not route through `escalate_to_split` (the create-side trigger is separately deferred per CLAUDE.md); this plan is completeness-apply only.
- **The `info` deterministic granularity detectors** (`_split_findings`) — they remain report-only advisory in the `Smells (advisory)` bucket; only the `medium` MIXED-STEP signal becomes dispatchable.

## Risks

- **Data-contract drift:** adding `granularity-split` to `sidecar_recs` changes what the persisted gap map can contain and is drift-guarded by `DATA_CONTRACT.md` + `tests/test_data_contract.py`; mitigation is updating the contract doc in the same plan and keeping the guard green.
- **Stale gap map after a split:** a 1→2 split renumbers every step from the target onward, so applying later saved findings against the old ids would target wrong steps; mitigated by halting the walk on an `applied` outcome and instructing a re-audit.
- **Unattended structural mutation:** a blanket `-y` fast-forward or a `--jobs > 1` worktree worker must never reshape the plan spine; mitigated by recommending-only under `-y`/`yes_to_all` and in the parallel lane, mirroring `escalate_to_split`'s `allow_split=(allow_split and not yes_to_all)` invariant.
- **Low-confidence trigger:** firing a structural mutation off a heuristic title/area detector would be unsafe; mitigated by dispatching only the `medium` Claude-judged signal and keeping `info` detectors advisory.

## Testing

Unit-first, with the conftest autouse gate never seeing a real backend spawn — stub `escalate_to_split` / the split proposer throughout.
- `tests/cli/test_completeness_cmd.py` — sidecar now carries a `medium` granularity-split (extend/counter the existing folds-into-smells test at ≈699); the apply walk dispatches it to a **stubbed** `escalate_to_split`; assert recommend-only under no-flag / `-y` / unsafe.
- `tests/cli/test_review_actions.py` — `TestStructuralEscalation` is the template for the outcome→status mapping if a completeness-side wrapper is added.
- `tests/test_review_walk.py` — add a new dispatchable path for `granularity-split` (the merge/re-ground dispatchability tests ≈2748–2812 are the analog).
- `tests/test_data_contract.py` — the sidecar-shape drift guard must stay green with the new source persisted.
- Seam discipline: stub `escalate_to_split` / the split proposer; do not spawn real Claude.

## Acceptance criteria

- A saved conceptual gap map containing a `medium` `granularity-split` MIXED-STEP finding (resolvable `step_id`), walked by `completeness-apply` **with the structural opt-in + an interactive confirm on a safe plan**, dispatches to `escalate_to_split` and **applies** the 1→2 split (plan renumbered, downstream detail files migrated) — the operator does not hand-edit the plan.
- **Without** the opt-in, under `-y`, in the parallel lane, on an **unsafe** plan (a non-PENDING step at/after the target), or a declined/non-TTY confirm → the walk **recommends only**: it prints the runnable `plan-tool split … --step N --into …`, spends **no Claude on mutation**, and leaves plan + detail files byte-unchanged (only `applied` mutated).
- A `granularity-split` `medium` finding is now **persisted to the saved sidecar** (not report-prose only), `DATA_CONTRACT.md` documents the addition, and its drift guard stays green; the `info` deterministic granularity detectors remain report-only advisory.
- On an **applied** split the walk **halts and instructs a re-audit** (stale gap map), and does not apply any later saved finding against the now-renumbered ids.
- `granularity-split` stays **out** of `APPLY_ELIGIBLE_SOURCES` and does **not** flip an exit code; the new path is a structural dispatch, not an `apply_finding` edit.
- Docs updated: `CLAUDE.md` (the escalate-to-split bridge *callers* list gains the completeness-apply lane), `RUNBOOK.md` (operator walkthrough), `docs/cli/completeness-apply.md` (the new opt-in + recommend-only default), and **`BACKLOG.md` #70** (remove the completeness-apply split bridge bullet from *Remaining*, note the ship date).

## Deferred

- **Run-evidence hardening of `split_is_safe`** beyond the `status` field (consulting run-log `run-started` markers or `git status --porcelain`) — a separate change to the single choke point, affecting every `escalate_to_split` caller, not just this bridge. Note it; do not bundle it.
- **Parallel-lane structural mutation** — the `--jobs > 1` worktree lane stays recommend-only for structural findings (decision 3); building safe parallel structural apply is future design.
- **`create`-side structural dispatch** — deferred per CLAUDE.md; this plan is completeness-apply only.
- **The other three #70 arms** — multi-step/region carve, per-remedy `--merge`/`--reground` walk flags + dispatcher consolidation, and the code-reveals-a-split reconcile producer — stay open under #70.
