# Glossary

*Back to the [README task routes](../README.md#start-here).*

These are the short meanings of terms that carry a particular meaning in
`plan-tool`. Each entry links to the guide that supplies the working rules.

## Apply / `apply-finding`

The edit that addresses an audit or review finding. Applying a finding means
checking its evidence, finding every matching site, making the smallest change
that delivers the required property, and checking the result again. It does
not mean accepting a suggestion without judgment. See
[the development model](explanations/development-model.md#two-jobs-guardian-and-mentor).

## Audit

A check of an artifact against a stated source of truth. An audit produces
findings and evidence; it is not itself a verdict that the work is ready. The
bare-plan and detail-grounded `completeness-audit` gates ask whether a plan is
sound and covered, while reconcile checks compare a plan and the code. See
[Gates and reconcile](GATES.md).

## Bare plan

A plan with one or more steps that have no detail file yet. Its early audit
can still catch plan-level correctness gaps, but cannot make detail-grounded
claims until the detail bundle is complete. See
[the audit workflow](how-to/common-workflows.md#3-audit-a-plans-quality).

## Convergence and converged

**Convergence** is the repeated loop of checking an artifact, fixing the
findings that are real and in scope, and checking it again. It asks whether a
new pass still exposes a material problem.

**Converged** is one possible human exit: the appropriate check is clean, or
two low-severity passes are quiet. The other exits are useful signals too: a
review may be describing the last edit rather than the artifact, or a repeated
finding may call for a redesign. A falling count alone proves neither.

An automated `--iterate` result is narrower. For example,
`no_blocking_findings` means no `medium`-or-above finding remains; it does not
certify that a plan is sound. Read the report and
handle conceptual findings deliberately. See
[Iterating to convergence](ITERATION.md) and
[the development model's loop exits](explanations/development-model.md#the-loops-and-how-they-end).

## Convergence diagnostic

`plan-tool convergence <name>` is a read-only report on saved audit history.
It does not run a new audit, change the plan, or choose a structural remedy.
Use it as one signal when deciding whether the loop is healthy. See
[Iterating to convergence](ITERATION.md).

## Detail and detail bundle

A **detail** is the implementation-grade file for one plan step. A **detail
bundle** is the collection of those files for the plan. The bundle grounds the
second completeness audit in the proposed implementation and current code.
See [the detail workflow](how-to/common-workflows.md#2-detail--draft-per-step-detail-files).

## Direct route and plan route

The **direct route** is a small, clear change made directly: edit, test,
review, fix, and review again. The **plan route** adds an authored plan, two
audit gates, step execution, and post-run reconciliation for work whose scope
or acceptance criteria need more structure. See
[Contributing](../CONTRIBUTING.md#direct-edit-or-plan).

## Session-directed edit

A **session-directed edit** is a deliberate change after the driving developer
has read the evidence, chosen what is real and in scope, and asked the coding
assistant to write a bounded change. The developer owns the judgment; the
assistant may write, search, test, and review the edit. A **direct edit** is the broader term for any
artifact change outside a `plan-tool` automatic-apply path, whether a person
or an assistant writes it.

## Pull request (PR) review

The team's review of a bounded branch before it merges. It shares the
change's intent, evidence, and settled decisions with people beyond the
author, and gives every substantive comment a recorded disposition. It adds a
team checkpoint after the local loops; it does not replace them. See
[Pull-request review](../CONTRIBUTING.md#pull-request-review-team-checkpoint).

## Finding

A specific claim that an artifact has a defect, a gap, or a risk. It needs a
severity, evidence, and a disposition such as fixed, refuted, declined, or
tracked. A finding is a hypothesis to check, not an instruction to obey. See
[the code-review guidance](../CONTRIBUTING.md#code-review-where-the-craft-gets-taught).

## Gate

A deterministic check that blocks an unsafe or malformed action before it can
continue. Gates and audits complement each other: a gate checks known rules;
an audit looks for relevant problems the known rules may not cover. See
[Correctness gates](GATES.md#correctness-gates).

## Grounding

Evidence that a plan or detail refers to the code that exists now: the real
files, call sites, contracts, and tests it will affect. Grounding keeps a
plausible plan from describing a repository that is no longer there. See
[the workflow](how-to/common-workflows.md).

## Reconcile

A comparison between a plan and the code after one of them has changed. The
direction matters: `reconcile-plan` treats code as the truth and updates an
unexecuted plan; `reconcile-code` treats the plan as the truth and checks or
updates delivered code. See [Per-subcommand reconcile](GATES.md#per-subcommand-reconcile).

## Scope and scope-out

**Scope** is the work and acceptance criteria the current plan promises.
**Scope-out** removes an over-packed step or contiguous range from that plan,
first saving it as a forward seed for later work. It is a structural decision,
not another way to hide an unresolved finding. See
[scope-out](ITERATION.md#carve-an-over-packed-step-out-plan-tool-scope-out).

## Seed and forward seed

A **seed** is the starting brief passed to `create`. A **forward seed** is a
new brief that preserves deferred or carved-out work for the next plan; it
does not silently expand the plan in hand. See
[the create workflow](how-to/common-workflows.md#1-create--author-a-new-plan).
