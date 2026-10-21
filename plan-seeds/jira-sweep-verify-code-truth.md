# Plan seed: `jira-sweep verify` — adjudicate story status against code, not Jira

This file is a `plan-tool create` input. Use it via:

```
plan-tool create jira-sweep-verify-code-truth --from-existing plan-seeds/jira-sweep-verify-code-truth.md --iterate
```

> **Source and lifecycle.** Implements BACKLOG **#143** and inherits its full
> scope contract, including its hard boundary: this pass **produces a third
> verdict and never resolves divergence by writing either side**.
> **Hard dependency — do not `create` before it ships:** #142
> (`plan-seeds/jira-sweep-deterministic.md`) supplies the divergence list this
> consumes *and* the token-collision disambiguation that keeps the wrong Jira
> issue's claims from being checked against the wrong plan's code. **Tool state
> this assumes:** `jira-sweep collect|check|report` exist, `Story.jira_issue_key`
> and `export_state` exist, and the persisted `.plan-tool/jira-sweep/` mapping
> is stable. The final docs/status step must reconcile `BACKLOG.md` #143 — mark
> it plan-authored while execution is pending, remove it only after this ships.
> Out-of-scope findings route to the backlog files, never into this plan.

---

## Overview

`jira-sweep report` can say two records disagree. It cannot say which is
right. This adds `plan-tool jira-sweep verify`: an opt-in, expensive,
read-only pass that reads each story's acceptance criteria and files-in-scope
against the **actual working tree** and returns an independent verdict.

When it ships: a divergence list plus an optional sample of agreements goes
in; a report comes out naming, per story, whether the code supports the claim
— with regression-suspected and superseded-elsewhere called out separately so
neither reads as generic "todo."

A new subcommand, not `reconcile-code --deep`. `reconcile-code` is
plan-canonical and **mutates code**; this is read-only and mutates nothing.
Folding a read-only report into a mutating verb blurs the one distinction
`CLAUDE.md` spends the most words protecting.

## Problem statement

Jira status is not ground truth, and neither is the local marker. Measured:
a code-blind sync that trusted Jira's `Done` and flipped 29 local statuses to
match was **wrong for 24 of them**.

Two failure classes make the obvious implementation actively harmful, both
observed rather than theorized:

**Existence is not evidence.** An eligibility flag hardcoded to `true` behind
a `// Temporarily disable …` comment, and an eligibility gate commented out
entirely — in both cases with the **test suite rewritten to assert the
disabled behavior**. A file/symbol shape check calls both "done," and so does
a green test run.

**Absence is not evidence either.** A plan group's files-in-scope can be
genuinely missing under *that plan's* story IDs while the identical feature
shipped under a *different* plan's IDs. Uncaught, the report reads "32
stories not started" when the honest read is "shipped elsewhere, nothing to
do here."

## Architecture

**Determinism ladder (Rule 3) — why the judge is the last resort, not the
first.** Each rung is taken as far as it goes before the next:

- **Mechanical check resolves `absent` outright.** Path and symbol
  resolution over files-in-scope is deterministic. Every story it settles
  leaves the judged set permanently — this is the work-cutting lever, not an
  optimization.
- **Observation is compromised here, which is why it can't finish the job.**
  Normally a real test run answers "does it work." Not on this evidence: the
  suites were *rewritten to assert the disabled behavior*, so a green run is
  consistent with the regression. Test results are input to the judge, never
  the verdict.
- **Counting doesn't apply** — this is a one-shot verdict per story, not a
  recurrence signal across passes.
- **So a judged classifier is genuinely last**, and only for the residue:
  separating `done` from `partial` among stories whose surfaces exist.

**Four layers (Rule 1).** Only layer 2 is non-deterministic:

1. **Deterministic assembly** — load #142's divergence list, the story's
   criteria and files, resolve paths/symbols, run the mechanical filter,
   gather `git log -- <file>` history for the superseded classifier.
2. **One directed judged call per story-group** — forced output contract,
   never an open-ended ask. Groups mirror `completeness-audit`'s sampled
   pass rather than one mega-prompt.
3. **Deterministic response gates** — see below; a failing reply re-prompts
   with the violation named (`--iterate` pattern).
4. **Deterministic consumption** — merge, count, render, persist. No
   mutation anywhere.

**Closed vocabulary (Rule 4).** `verdict` is exactly one of `done` /
`partial` / `absent`. Two orthogonal boolean classifiers ride alongside
rather than inflating the enum, because each is true *of* a verdict rather
than instead of one: `regression_suspected` (a surface exists but its logic
is disabled) and `superseded_elsewhere` (absent here, shipped under another
story's IDs). An unknown token is a gate failure, not a new category.

**Anchoring.** Every verdict and every classifier flag cites a resolvable
anchor — file plus symbol for a verdict or a regression, the commit or story
ID for a supersession. An unanchored claim is rejected and re-prompted. This
is the gate against the risk #143 names directly: an agent asserting
"confirmed" without having read what it claims to.

**Totality.** Every story in a group's input maps to exactly one verdict in
its output. Missing and extra stories are both gate failures.

**Three-way contradiction is its own output class.** Where the code verdict
contradicts *both* the local state and Jira, the report says so distinctly —
this occurred in the reference run and reads as noise if merged into ordinary
divergence.

**Stale criteria stay visible as ambiguity.** When code and criterion
disagree, the honest reading is sometimes that the *criterion* is stale, not
the code. The report renders this as a disagreement between two records, and
never silently picks a side. Same discipline as the sweep: surface, don't
arbitrate.

**Serial by default.** The reference run used ~10 parallel agents over 12
groups / 99 stories, 5–70 tool calls and 20k–110k output tokens per group.
The fan-out is read-only with no shared mutable state and no merge-back, so
it is not the shape `CLAUDE.md § Architecture` discourages — but adopting
in-process concurrency is still a structural decision requiring **explicit
user sign-off** there, and the mechanical `absent` filter is the cut-work
lever to exhaust first. Ship serial; concurrency is a separately justified
follow-up, not part of this plan.

## Out of scope

- **Writing anything.** No local `export_state` change, no Jira write-back,
  no plan mutation, no code edit. #143's boundary, inherited verbatim.
- **Deciding which side wins.** The verdict is a third record, not a
  resolution.
- **In-process parallel fan-out** — see above; needs its own sign-off.
- **Running by default.** Opt-in subcommand only; never fires on
  `reconcile` / `status` / `sweep`.
- **Changing `reconcile-code`**, `verify`, or the criteria-fulfillment
  prompt's existing plan-scoped behavior.
- **Rebuilding the sweep.** #142 owns collection, matching, and the mapping
  artifact; this consumes them unchanged.
- **Tuning the two classifiers** beyond shipping them behind gates — they
  were discovered by reading agent output, so calibration is follow-up work.

## Risks

- **False confidence** — an agent claiming "confirmed" without reading what
  it cites. The anchor gate is the mitigation; an unresolvable anchor fails
  rather than downgrades.
- **Cost and variance** — inherently large and per-plan variable. Mitigated
  by the mechanical filter shrinking the judged set, and by the pass being
  opt-in.
- **Compromised observers** — tests asserting disabled behavior. Test output
  informs the judge; it never *is* the verdict.
- **Stale acceptance criteria** read as code defects. Mitigated by rendering
  disagreement as two-sided.

## Testing

Fixture repos with seeded, known-shape defects; the judged call stubbed
through its invoker seam per `TESTING.md`. Every gate gets a
contract-conformance test: illegal vocabulary, unresolvable anchor, a story
missing from the reply, an extra story in the reply. Criteria assert the
**contract**, never what a judge concludes.

## Acceptance criteria

- A story whose files-in-scope do not resolve is classified `absent`
  mechanically, with **no judged call made** for it.
- A reply using a token outside `done` / `partial` / `absent` fails the gate
  and re-prompts naming the violation.
- A reply asserting `regression_suspected` without a resolvable file+symbol
  anchor fails the gate and re-prompts naming the violation.
- A reply omitting a story present in the group's input, or adding one that
  was not, fails the totality gate.
- A fixture where the code verdict opposes both records is rendered in the
  three-way-contradiction section, not merged into ordinary divergence.
- The command completes without mutating any plan, export, working-tree
  file, or Jira issue — asserted, not assumed.
- Exit is non-zero only on failure-to-complete; verdicts never flip the code.
- `BACKLOG.md` #143 is reconciled.

## Deferred

- Calibrating the two classifiers against a labeled corpus.
- Parallel fan-out, pending the architecture sign-off above.
- Any write-back path, local or to Jira.
- Extending the pass to plan steps outside the jira-story lane.

## References

- `BACKLOG.md` #143 — Jira-sweep verification scope and lifecycle contract.
- `BACKLOG.md` #142 — divergence collection dependency that this seed consumes
  without rebuilding.
- `TESTING.md` — fixture and stub-invoker convention for judged verification.
