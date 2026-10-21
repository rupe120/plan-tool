# Withdrawn 2026-08-21: jira-grade 02 consumer probe

> **Historical record, not a `plan-tool create` input.** The probe,
> quality-ledger, materiality, and canonical-inversion route is cut. #293 now
> owns the selected implementation-grade bundle's terminal projection into
> concise Jira stories and a developer-handoff companion. The plan remains the
> authority for non-negotiable outcomes; the companion presents grounded
> implementation guidance as suggestions.

> **BLOCKED — the verdict-arm design needs re-deriving (2026-08-08, BACKLOG
> #251).** "### The `probe` verdict arm" below designs `probe` as a third
> state "beside `converged` and `spinning`". `convergence_diagnosis.py` no
> longer has that two-state model — #251 retired `spinning` and the
> region-trending layer behind it; the shipped model is now three states
> (`no-history`/`insufficient-history`/`converging`). The probe **command**
> and its report/persistence design are unaffected; only the verdict-arm
> trigger ("neither the fingerprint-stable converging certificate nor the
> recurrence/no-shrinkage spinning verdict") needs re-deriving against the
> current shape before authoring a plan from this seed. See BACKLOG #169.

The former proposal is retained below only to document the cut route.

```
plan-tool create jira-grade-02-consumer-probe --from-existing plan-seeds/jira-grade-02-consumer-probe.md --iterate
```

> **Source and lifecycle.** Implements BACKLOG **#169** — stage **02 of 05**
> in the ordered `jira-grade` group (full arc lives in #169, the group
> anchor; naming per the "Ordered efforts" directive in `BACKLOG.md`) — and
> inherits #169's full scope contract. **Hard dependency:** stage 01
> (`docs/implementation-plans/2-jira-grade-01-detail-instrument.md`, **shipped**) must ship first — the
> probe selects bundles through 01's grade-selection machinery and must be
> able to probe either grade. The final docs/status step must reconcile
> `BACKLOG.md` #169: mark it plan-authored while execution is pending and
> remove it only after this stage ships; out-of-scope findings route to the
> backlog files, never into this plan.

---

## Intent

Replace unbounded auditor critique with bounded consumer evidence at the
point where convergence is decided. An auditor-role invocation is rewarded
for producing findings and so never returns empty; a consumer-role
invocation is rewarded for completing the task and reports only what
actually stopped it. This stage makes that second signal available as a
read-only probe, and adds the decomposition cross-check that recovers the
structural collision the jira-grade audit lane sheds. Success is a probe
whose blockers are anchored, verifiable, and cheap enough to prefer over
another round of judging.

## Stage and audit scope fence

**Tool state when this plan starts:** stage 01 has shipped — both detail
grades are authorable, selectable, consumable, and independently auditable;
run-grade is still the default and canonical grade. There is no consumer
probe, no probe-based materiality, no inversion. **Tool state this plan
leaves behind:** exactly one read-only consumer surface (`plan-tool probe`)
and one recommend-only convergence verdict arm — audit behavior, defaults,
and every mutating surface are unchanged.

Completeness audits of this plan must judge it against that stage's tool
state only. Route later-stage concerns as `[out-of-scope-deferred]` to their
owning stage instead of expanding this plan: cross-probe counting, blocker
recurrence, or any evidence-based demotion of audit findings (stage 04,
BACKLOG #170); the quality ledger's metrics, floors, or roll-up (stage
03, `plan-seeds/jira-grade-03-quality-ledger.md`); canonical inversion or
any default change (stage 05, #171); and any `run` integration beyond what
already exists (`run` is the tier-2 evidence source *as it stands* — this
plan does not touch it). Per the #125 convention, deferred-tagged findings
neither reset low-yield streaks nor justify raising pass caps; prefer
`--audit-passes 1` for audits of this plan.

## Overview

Add `plan-tool probe <name> [--grade <g>]`: a consumer-role dry run in which
a fresh implementer-role invocation — with no plan-authoring context —
consumes a selected detail bundle plus repository grounding and returns a
plan-of-attack and a **blockers-only report**, each blocker anchored at its
point of use. The report persists as a saved sidecar, and `plan-tool
convergence` gains a third verdict arm — **`probe`** — that recommends
running one when the completeness trajectory is indeterminate: cheaper to
test the artifact than to keep judging it.

## First principles: role asymmetry is the determinism lever

An auditor-role invocation is rewarded for producing findings; unbounded
generative critique of a detailed artifact never returns empty, which is why
"audit until clean" is structurally divergent against a strong model. A
consumer-role invocation is rewarded for **completing the task from the
brief** and reports only what actually stopped it. That objective difference
— not a better model or a smarter classifier — is what changes the
false-positive rate. An anchored blocker is verifiable and dedupable in a
way free-form critique is not: it must name where in the bundle the consumer
was stopped and what it could not resolve there.

This answers "would implementation resolve this finding?" operationally
instead of predictively — the question the judged-impact family
(`impact-recurrence-structural-stop`) tried to answer with a classifier and
spun on. The tool's primary value is the communication artifact, so the
arbiter of its convergence is a consumer of that artifact; the existing
`run` command is the highest-fidelity tier of the same idea and is not
modified here.

## Design

### The probe invocation

A fresh implementer-role Claude call (through the standard `invoker=` seam)
receives: the selected detail bundle (chosen through stage 01's explicit
grade selection, defaulting to the plan's canonical grade), the plan body,
and normal repository grounding. It is instructed to produce a plan-of-attack
— the concrete edits it would make, organized per plan step so each attack
item names the step it serves — and to report **only** blockers. The
probe is strictly read-only: no tree mutation, no plan mutation, no worktree
provisioning; enforced and tested, so a probe can never drift into
implementing. A plan with no detail bundle at the selected grade is a clear
error, not an empty report.

### The blocker contract and report gates

Each blocker carries: an **anchor** (the step/section/file citation at the
point of use), a **kind** — `unanswerable-decision` (a choice the brief
forces the consumer to make without the information to make it),
`contradiction` (two parts of the bundle/plan that cannot both be followed),
or `missing-constraint` (a boundary the consumer needed and could not find)
— the question the consumer could not answer, and what it tried first.
Deterministic report gates (loopable under `--iterate`) reject
critique-style entries: an unanchored blocker, a "this could be better"
observation, or a blocker whose anchor does not resolve in the bundle fails
the gate and re-prompts with the violation named. The gates keep the
consumer honest to its role — improvements are not blockers.

### The decomposition cross-check (advisory structural signal)

The plan-of-attack is a second signal, not just context. Because it is
organized per plan step, a deterministic post-pass compares its shape
against the plan's step decomposition: one step whose attack splits into
divergent tracks (disjoint file sets, or a behavior-preserving track beside
a new-behavior track) is a fused-step signal; a step group whose attacks
collapse into one indivisible edit sequence is a fragmentation signal. Both
emit through the existing advisory vocabulary — `granularity-split` /
`granularity-merge` at `severity="info"`, recommend-only, outside
`APPLY_ELIGIBLE_SOURCES`, never dispatched to any structural bridge (the
reconcile lane's code-grounded split finding is the precedent for an `info`
reuse of the literal). This is the structural middle ground for jira-grade
bundles: run-grade authoring surfaces a mis-decomposed plan by colliding
with implementation facts (the purity and coherence checks the jira-grade
audit lane deliberately sheds); outcome-altitude prose can sit coherently
on the same bad structure, so the consumer's derived attack plan stands in
as the collision surface. The cross-check reads only the plan-of-attack
section — the blockers-only fence is untouched, and a structure signal is
never rendered as a blocker.

### Persistence

The probe report persists as a saved sidecar under the plan's reports
directory (schema added to `DATA_CONTRACT.md`, drift-guarded), carrying the
plan fingerprint, selected grade, backend/model settings, and timestamp so
later consumers (stage 03's ledger, stage 04's recurrence counting) can
correlate probes without this plan building any of that correlation.

### The `probe` verdict arm

`convergence_diagnosis` gains a third verdict beside `converged` and
`spinning`: **`probe`** — emitted only when the trajectory is genuinely
indeterminate (neither the fingerprint-stable converging certificate nor the
recurrence/no-shrinkage spinning verdict), recommending the runnable
`plan-tool probe <name> --grade <g>` line. Recommend-only, spends no Claude,
writes nothing, always exits 0 — the same posture as the existing verdicts.
It never overrides `converged` or `spinning`; it fills the gap where today
the diagnostic can only shrug.

## Suggested decomposition

Keep these as separate concerns:

- **Blocker schema and report gates step:** the blocker/report data shapes,
  the deterministic anchor-resolution and role-honesty gates, and the
  `DATA_CONTRACT.md` addition — no Claude call, fixture-tested.
- **Probe invocation step:** the prompt file, the consumer-role invocation
  through the invoker seam, read-only enforcement, and the grade-selection
  wiring against stage 01's machinery, tested with stub invokers.
- **Decomposition cross-check step:** the per-step plan-of-attack shape in
  the report schema and the deterministic comparison emitting advisory
  `granularity-split` / `granularity-merge` signals at `info` — no Claude
  call of its own, fixture-tested with seeded fused-step and
  fragmented-group attack plans.
- **CLI and persistence step:** `plan-tool probe` command wiring, sidecar
  persistence, `docs/cli/` regeneration.
- **Verdict arm step:** the `probe` arm in `convergence_diagnosis.py` /
  `convergence_cmd.py` with its indeterminate-only trigger, plus its
  rendered recommendation line.
- **Docs/status step:** `RUNBOOK.md` / `CAPABILITIES.md` / `USE_CASES.md`
  coverage and `BACKLOG.md` #169 reconciliation.

## Out of scope

- Counting blockers across probes, blocker recurrence, or demoting any audit
  finding on probe evidence (stage 04, #170).
- Any change to audit findings, severities, prompts, sampling, or stopping
  predicates — this stage adds evidence beside the audit, not inside it.
- Any change to `run`, including consumer-mode integration or execution-tier
  capture (tier-2 evidence remains the existing `run` as-is).
- Canonical inversion or any default change (stage 05, #171).
- Blocker-driven auto-fixes or auto-chaining a probe into apply/reconcile
  surfaces.
- Auto-dispatching a cross-check signal to `escalate_to_split`,
  `merge_bridge`, or any structural bridge — the signals are advisory
  `info` recommendations only, and `info` is what keeps them out of every
  auto-dispatch gate.
- The quality ledger's use of probe reports (stage 03 consumes; this stage
  only produces).

## Risks and mitigations

- **The probe is still nondeterministic:** mitigated structurally — the
  anchor requirement makes each blocker checkable, the role-honesty gates
  strip critique, and single-probe trust is never load-bearing (recurrence
  counting is stage 04; here a probe only informs the operator and the
  indeterminate verdict).
- **Role drift into implementation:** read-only invocation with enforcement
  and tests; a probe that attempts mutation is a failure, not a feature.
- **Verdict-arm creep:** the `probe` arm triggers only on the indeterminate
  trajectory and never outranks `converged`/`spinning`; pinned by tests.
- **Report rot:** the sidecar carries fingerprints and settings so stale
  probes are detectable by later stages without this plan adding staleness
  logic.

## Acceptance criteria

- `plan-tool probe <name>` produces a persisted, fingerprint-stamped,
  blockers-only report for the selected grade; every blocker carries a
  resolving anchor, a kind, the unanswerable question, and what was tried.
- The report gates demonstrably reject unanchored and critique-style
  entries, and the iterate loop re-prompts with the violation named.
- The probe provably leaves the working tree and plan state untouched, and
  probing a plan with no bundle at the selected grade fails clearly.
- The plan-of-attack is organized per plan step, and the deterministic
  cross-check emits advisory `granularity-split` / `granularity-merge`
  signals at `info` for seeded fused-step and fragmented-group fixtures —
  recommend-only, never blocking, never auto-dispatched, never rendered as
  blockers.
- Both grades are probeable through stage 01's explicit selection; the
  canonical grade is the default.
- `convergence` emits the `probe` verdict only on the indeterminate
  trajectory, renders the runnable probe command, and continues to exit 0.
- No audit, `run`, or default behavior changed; tests pin this.
- `DATA_CONTRACT.md` documents the sidecar; docs cover the probe and the
  verdict arm; `BACKLOG.md` #169 is reconciled by the final step.

## Deferred

- Blocker-recurrence materiality and evidence-cited demotion (stage 04,
  #170).
- Canonical inversion (stage 05, #171).
- Consumer-mode `run` capture as structured tier-2 evidence.
- Cross-probe analytics, probe scheduling, and any statistical treatment of
  blocker history.
