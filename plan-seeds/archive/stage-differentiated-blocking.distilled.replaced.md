> **Replaced**: this file has been superseded by `docs/implementation-plans/2-stage-differentiated-blocking.md`.
> Preserved here for history; do not edit.

## Overview

Make the shared blocking predicate in `plan_tool/convergence.py` stage-aware so `completeness-audit --iterate` (and the shared convergence `no_blocking_findings` stop) applies a different bar depending on the audit stage. A **bare-plan** gate stops when the plan is correctness-clean and carries no HIGH completeness; a **detail-grounded** gate keeps iterating on medium **code-logic** findings while treating medium **docs/unit-test** findings as advisory for the stop decision only. There is **one** discriminator — `is_blocking_finding(rec, *, stage=…)` — and the stage selects which axis applies; this lands as a single stage-branching change, not two sequential rewrites. Reports and console output name which bar fired, and a bare exit names the deferred completeness set handed to gate 2. Branch selection comes from the existing bundle/stage signal (`is_bare` / detail coverage), so the default path needs no new CLI flag, and the exit-code convention is unchanged.

## Problem statement

`plan_tool/convergence.py` today keys `is_blocking` / `BLOCKING_SEVERITIES` on severity alone: `medium` and above blocks, only `nit`/`info` are advisory. Every caller that drives an iterate stop — `completeness_cmd._completeness_has_blocking_findings`, the reconcile loops, and the create/detail iterate wiring — feeds `has_blocking_findings` into `should_continue`'s `no_blocking_findings`, so that one severity-only rule governs the stop decision at every audit stage.

Severity alone is badly calibrated. Measured on the #248 sample (`app-mode-server-side-enforcement`, 2026-08-07): one MEDIUM said the core mechanism might not work while another asked to rename a phrase, and both blocked identically. On the detail side (#91), a severity/domain-blind advisory bucket can hide HIGH or code-logic-medium completeness findings from the stop decision. Backlog **#248** (bare-plan gate) and **#91** (detail-grounded domain-aware medium demotion) both rewrite this same predicate on independent axes, so shipping them separately would mean rewriting it twice.

The same sample carries a warning about what this is *not*: every round still carried HIGH correctness, so the bare bar must not be sold as an early-exit wall-clock win — verification has to confirm it would not have exited early on that fixture.

## Architecture

One discriminator owns both axes: replace the severity-only `is_blocking` with `is_blocking_finding(rec, *, stage=…)` in `convergence.py`, keeping a pure severity helper for callers that still want severity-only classification. Stage is selected from the existing bundle/stage signal (`bundle_status.is_bare` / detail coverage) rather than a new CLI flag on the default path.

The two bars, settled and not to be re-litigated:

| Stage | Owner | Blocking bar |
| --- | --- | --- |
| Bare plan (`bundle_status.is_bare`) | #248 | Zero `plan-correctness` at any severity **and** zero HIGH completeness. Prefer a **clean streak** (consecutive clean samples) over a single clean round. |
| Detail-grounded | #91 | Severity + **domain**: `high`/`critical` always block; `nit`/`info` never; `medium` blocks iff domain is **code-logic** (or **unknown**). Docs/unit-test mediums are advisory for *stop only*. |

Three rules constrain how the branches interact:

- Domain-aware demotion is **detail-gate only** — it is never applied on bare plans.
- Deferred completeness at gate 2 is **re-derived** by a fresh audit after detail, not replayed as still-open evidence. The bare handoff **names** the deferred set so operators know what was postponed, but gate 2 does not treat those ids as unpaid debt.
- Coupling rule (#91): when a round already has **any** blocking finding, fix **all** open mediums that round, docs/test included. The advisory demotion matters only when nothing else blocks — then the loop stops even with docs/test mediums left.

The completeness **advisory conceptual bucket** changes accordingly: HIGH or code-logic-medium completeness must still block the stop decision under the detail bar (#91 scope). Reporting and console output gain the identity of which bar applied, and the bare exit names the deferred completeness set for the gate 2 handoff.

The change sweeps the `has_blocking_findings` / `is_blocking(...)` call sites that drive iterate stop (completeness, reconcile, create/detail as applicable) plus the docs describing `no_blocking_findings` and the two audit gates: the CLAUDE.md / DIRECTIVES gate sections, the `should_continue` docstring, and DATA_CONTRACT / telemetry where they record a stop reason.

Placement is the smallest move that keeps one discriminator owning both axes — a helper extracted inside `convergence.py` or a shared leaf. No new parallel policy modules unless a cycle or ownership boundary forces it, and the blocker must be cited if so.

This is a backlog-derived plan: when it ships, the final docs/status step updates BACKLOG **#91** and **#248** — removing the shipped entries, or marking them plan-authored while execution remains pending.

## Out of scope

- Edit-drift / self-seeded-finding as **machinery** — judgment-only today; Stage 3 / #158 family, re-derive after #251.
- Changing which findings bare audits **withhold** from `completeness-apply` — the #241 half is correct today.
- Pass-count defaults, `arm-clustering`, audit prompt wording, severity reassignment.
- Reintroducing region-trending / `spinning` / `FORK_*` — #251 retired.
- Impact-recurrence / reseed-advisor dependents (#158/#168) — blocked pending Stage 3 re-derive.
- Interactive chat / #255 recorder.

## Risks

- The correctness axis may prove as mislabeled as severity was in the #248 sample. If it does, close the bare rule as a measured no — record the labels and do not tune until the number looks right.
- The bare bar could be mistaken for an early-exit wall-clock win. On the #248 four-round sample every round still carried HIGH correctness, so no early exit was available; verification must confirm the bar does not claim one on that fixture.
- Path-only domain classifiers are insufficient: a plan-level code-logic medium with no target file must still block (the #91 `merge-bridge-reauthor-context` pin).

## Testing

- Bare matrix: correctness residual → continue; HIGH completeness → continue; correctness-clean with only medium/low completeness → stop after the streak policy.
- Detail matrix: medium docs/test → advisory stop; medium code-logic → block; unknown domain → block; `high`/`critical` always block.
- Fixture honesty on the four-round bare sample: no early exit while HIGH correctness is present.
- Plan-level no-target-file code-logic medium still blocks (path-only classifiers are insufficient — #91 `merge-bridge-reauthor-context` pin).
- Predicate unit matrix as above, plus mutation-proven caller tests wherever policy was previously severity-only.
- Replay honesty check against the #248 four-round fixture: the bare bar reports distinctly and does not claim an early exit while HIGH correctness remained.

## Acceptance criteria

- `convergence.py` exposes a stage-aware blocking predicate (`is_blocking_finding(rec, *, stage=…)`) alongside a pure severity helper that callers can still use.
- Under the bare-plan bar (`bundle_status.is_bare`), the iterate loop continues while any `plan-correctness` finding at any severity remains, and while any HIGH completeness finding remains; it stops once correctness is clean and no HIGH completeness remains, subject to the clean-streak policy.
- Under the detail-grounded bar, `high`/`critical` always block, `nit`/`info` never block, and `medium` blocks iff its domain is code-logic or unknown; docs/unit-test mediums are advisory for the stop decision only.
- Domain-aware demotion never applies on a bare plan.
- When a round has any blocking finding, all open mediums that round (docs/test included) are treated as to-fix; the advisory demotion applies only when nothing else blocks.
- HIGH or code-logic-medium completeness findings block the stop decision under the detail bar rather than being hidden in the advisory conceptual bucket.
- A plan-level code-logic medium with no target file still blocks (the #91 `merge-bridge-reauthor-context` pin).
- Report and console output name which stage bar applied; a bare exit names the deferred completeness set handed to gate 2.
- Gate 2 re-derives completeness from a fresh post-detail audit and does not treat the named deferred ids as still-open evidence.
- Stage branch selection uses the existing bundle/detail-coverage signal; the default path requires no new CLI flag.
- The exit-code convention is unchanged: a completed audit still exits 0 unless `--fail-on-findings`.
- Replay against the #248 four-round fixture (`app-mode-server-side-enforcement`) shows no early exit while HIGH correctness findings remain.
- BACKLOG #91 and #248 are updated in the final step — shipped entries removed, or marked plan-authored while execution remains pending.
