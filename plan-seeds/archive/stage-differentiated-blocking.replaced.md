> **Replaced**: this file has been superseded by `docs/implementation-plans/2-stage-differentiated-blocking.md`.
> Preserved here for history; do not edit.

# Plan seed: stage-differentiated blocking (#248 bare + #91 detail)

```
plan-tool create stage-differentiated-blocking \
  --from-existing plan-seeds/stage-differentiated-blocking.md --iterate
```

Backlog sources: **#248** (bare-plan gate) and **#91** (detail-grounded
domain-aware medium demotion). Land as **one** stage-branching change to the
shared blocking predicate — not two sequential rewrites. When this ships,
update those backlog entries (remove or mark plan-authored while execution
pending) in the final docs/status step.

---

## Outcome

`completeness-audit --iterate` (and the shared convergence `no_blocking_findings`
stop) applies **different blocking bars by audit stage**: a **bare-plan** gate
stops when the plan is correctness-clean and has no HIGH completeness; a
**detail-grounded** gate keeps iterating on medium **code-logic** findings while
treating medium **docs/unit-test** findings as advisory for the stop decision.
One discriminator; stage selects which axis applies. Reports name which bar
fired and, on a bare exit, name the deferred completeness set handed to gate 2.

## Settled composition (do not re-litigate)

| Stage | Owner | Blocking bar |
| --- | --- | --- |
| Bare plan (`bundle_status.is_bare`) | #248 | Zero `plan-correctness` at any severity **and** zero HIGH completeness. Prefer a **clean streak** (consecutive clean samples) over a single clean round. |
| Detail-grounded | #91 | Severity + **domain**: `high`/`critical` always block; `nit`/`info` never; `medium` blocks iff domain is **code-logic** (or **unknown**). Docs/unit-test mediums are advisory for *stop only*. |

- Domain-aware demotion is **detail-gate only** — never applied on bare plans.
- Deferred completeness at gate 2 is **re-derived** (fresh audit after detail),
  not replayed as still-open evidence. The bare handoff **names** that deferred
  set so operators know what was postponed; gate 2 does not treat those ids as
  unpaid debt.
- Coupling rule (#91): when a round already has **any** blocking finding, fix
  **all** open mediums that round (docs/test included). Advisory matters only
  when nothing blocks — then the loop stops even with docs/test mediums left.

## Why one discriminator

`plan_tool/convergence.py` today keys `is_blocking` / `BLOCKING_SEVERITIES` on
severity alone (`medium+` blocks; only `nit`/`info` advisory). Callers
(`completeness_cmd._completeness_has_blocking_findings`, reconcile loops,
create/detail iterate wiring) all feed `has_blocking_findings` →
`should_continue`'s `no_blocking_findings`. #248 and #91 both rewrite that
predicate on independent axes; land them together as
`is_blocking_finding(rec, *, stage=…)`.

Measured warning (#248 sample, `app-mode-server-side-enforcement`, 2026-08-07):
severity alone is badly calibrated (one MEDIUM said the core mechanism might
not work; another asked to rename a phrase). Axis-keyed bare bar is the
settled answer; the sample also showed **every round still carried HIGH
correctness**, so the bare bar must **not** be sold as early-exit wall-clock —
verification must confirm it would **not** have exited early on that fixture.

## In scope

- Stage-aware blocking predicate in `convergence.py` (+ keep a pure severity
  helper for callers that still want it).
- Bare vs detail branch selection from existing bundle/stage signal
  (`is_bare` / detail coverage) — no new CLI flag required for the default path.
- Completeness **advisory conceptual bucket**: HIGH or code-logic-medium
  completeness must still **block** the stop decision under the detail bar
  (today severity/domain-blind advisory can hide them — #91 scope).
- Report/console: which bar applied; bare exit names deferred completeness set
  for gate 2 handoff.
- Caller sweep of `has_blocking_findings` / `is_blocking(...)` sites that drive
  iterate stop (completeness, reconcile, create/detail as applicable).
- Docs that describe `no_blocking_findings` / the two audit gates
  (CLAUDE.md / DIRECTIVES gate sections, `should_continue` docstring,
  DATA_CONTRACT / telemetry if they record stop reason).
- Tests: bare matrix (correctness residual → continue; HIGH completeness →
  continue; correctness-clean + medium/low completeness only → stop after
  streak policy); detail matrix (medium-docs/test → advisory stop;
  medium-code → block; unknown → block; high/critical always block);
  fixture honesty on the four-round bare sample (no early exit while HIGH
  correctness present); plan-level no-target-file code-logic medium still
  blocks (path-only classifiers are insufficient — #91
  `merge-bridge-reauthor-context` pin).

## Out of scope / Non-goals

- Edit-drift / self-seeded-finding as **machinery** (judgment-only today;
  Stage 3 / #158 family — re-derive after #251).
- Changing which findings bare audits **withhold** from `completeness-apply`
  (#241 half is correct today).
- Pass-count defaults, `arm-clustering`, audit prompt wording, severity
  reassignment.
- Reintroducing region-trending / `spinning` / `FORK_*` (#251 retired).
- Impact-recurrence / reseed-advisor dependents (#158/#168) — blocked pending
  Stage 3 re-derive.
- Interactive chat / #255 recorder.

## Allowed behavior changes

- Bare iterate can stop with medium/low completeness still open (named deferred).
- Detail iterate can stop with only docs/unit-test mediums open.
- Stop-reason / report fields may gain stage-bar identity and deferred-set
  naming; exit-code convention unchanged (completed audit still exits 0 unless
  `--fail-on-findings`).

## Allowed reorganization

- Smallest move that keeps one discriminator owning both axes (helper extract
  inside `convergence.py` / shared leaf). No new parallel policy modules unless
  a cycle or ownership boundary forces it — cite the blocker if so.

## Verification

- Predicate unit matrix above; mutation-proven caller tests where policy
  previously severity-only.
- Replay honesty check against the #248 four-round fixture: bare bar reports
  distinctly and does **not** claim an early exit while HIGH correctness
  remained.
- After ship: BACKLOG #91 and #248 updated (remove shipped, or mark
  plan-authored while execution pending) in the final step.

## Stop / defer

Out-of-scope discoveries → `BACKLOG.md` / `BUG_BACKLOG.md`. If the correctness
axis proves as mislabeled as severity was in the #248 sample, close the bare
rule as a measured no — record labels; do not tune until the number looks right.
