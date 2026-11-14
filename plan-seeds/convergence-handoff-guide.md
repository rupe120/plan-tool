# Convergence handoff guide

## Outcome

A developer taking over an audited plan or a hand-applied code correction can
reconstruct the current evidence, decide whether the next action is a bounded
fix, execution, or a user-owned structural decision, and leave the same
decision record for the next developer without mistaking repeated review output
for proof of progress.

## In scope

- Publish `docs/CONVERGENCE_HANDOFF.md` as the durable, developer-facing guide
  for the manual loop that follows either `completeness-audit` or
  `/code-review`.
- Cover the two authority directions separately: plan-canonical authoring
  audits before execution and plan-canonical code reconciliation/review after
  execution or after a direct code change.
- Give a copyable per-round handoff record: clean/pinned baseline, authority,
  reports and command scope, finding dispositions, class-wide site enumeration,
  stated property, tests or reproduction, commit, and the exact next decision.
- Explain how an assistant-driven hand-apply differs from an interactive human
  walk, including why a headless session supplies review judgment rather than
  blindly invokes `completeness-apply`.
- Teach the three exits: clean or low-yield convergence; findings caused by the
  previous edit, which must be completed then executed and tested; and genuine
  non-convergence, which requires a user-owned split, carve, re-seed, backlog,
  or other bounded structural decision.
- Include concise, dated evidence cases: the false premise withdrawal of
  `audit-trajectory-instrumentation`; class-wide versus cited-site-only plan
  corrections; the post-run `roadmap-brief-source-drift` reconcile/review tail;
  and a recurrence whose provenance is insufficient to claim causation.
- Add navigation from the existing developer entry points without turning the
  `handoffs/` directory into a second backlog or duplicating the canonical
  directive in full.

## Scope guardrails

- This is process and handoff documentation only. Do not change audit prompts,
  findings, convergence predicates, CLI behavior, report schemas, or automatic
  structural remediation.
- `integrations/shared/DIRECTIVES.md` remains the canonical policy for driving
  plan-tool. The new guide explains how to carry out and hand off that policy;
  it links to policy sections instead of creating competing rules.
- Reports, logs, and commit order show a trajectory but do not prove that a
  manual edit caused a later model finding. The guide must require an explicit
  human disposition based on retained reports or conclusion summaries, decisions,
  current code and tests before treating recurrence as a decomposition signal.
  Use `git log -S` when relevant history exists; otherwise report insufficient
  provenance explicitly rather than infer a structural defect.
- A count trend, a model label, or a green suite alone never decides a structural
  action. Preserve plan intent, the governing property, existing tests, and
  user ownership of scope changes.
- Do not revive retired `spinning`, `FORK_*`, or automatic causal-classifier
  mechanisms. Mention the withdrawn work only as dated provenance explaining
  why judgment stays with the operator.

## Design decisions

- The guide starts with an evidence hierarchy: source plan/detail and explicit
  acceptance property; saved reports; focused tests or reproduction; the
  committed diff; run logs. It labels raw `.plan-tool/runs/` records as useful
  chronology and scope evidence, not a causal apply ledger.
- A receiver begins every round from a clean committed snapshot. They identify
  whether the plan or code is canonical, collect the applicable reports, and
  classify each material finding before editing: confirmed in-scope,
  refuted by code/test, out of scope with a destination, self-seeded, or a
  scope/architecture decision for the user.
- A confirmed correction is applied as a defect class, not only at the cited
  line: enumerate identifier and vocabulary sites before editing; read the
  suggested action; check set membership and implied tests/docs; then trace the
  chosen mechanism against the stated property on the common case.
- The guide records the minimum three completed snapshots for a trajectory and
  compares stable findings and material severity, rather than using raw count
  as a verdict. It distinguishes a genuine recurring plan/code defect from a
  new symptom created by the prior correction.
- For a plan, the guide preserves the bare-plan versus detail-grounded audit
  boundary and the fact that conceptual corrections are judgment-owned. For
  code, it preserves the post-run three-sweep stop rule and uses focused
  correction/test work rather than an unbounded fourth sweep.
- A multi-developer handoff names one evidence recorder and assigns each open
  finding a single disposition owner; parallel investigation may be read-only,
  but only the owner lands a correction after the shared ledger is reconciled.

## Verification

- A new maintainer can use the guide's handoff record to reconstruct the
  authority direction, latest clean commit, reports, tests, prior dispositions,
  site enumeration, governing property, and next bounded action without
  reading an unstructured chat transcript.
- The guide gives a distinct example and next action for a confirmed fix,
  refuted finding, self-seeded round, low-yield convergence, and genuine
  non-convergence.
- Every operational rule in the guide links to its current canonical source;
  the guide introduces no runnable command that conflicts with the shared
  directives or the post-run reconciliation flow.
- A documentation review checks the example dates, archive status, report and
  handoff paths, retired vocabulary, and links against HEAD.

## Out of scope

- A new convergence command, telemetry field, causal-provenance store,
  automatic split/scope-out/re-seed route, or automated multi-agent workflow.
- Rewriting historical plans, run logs, reports, or existing handoffs.
- Changing `RUNBOOK.md`'s older command reference beyond a narrowly necessary
  link or stale-pointer correction discovered while adding the new navigation.

## Risks

- Repeating all of the canonical policy in a new document will drift. Keep the
  guide decision-oriented and link to the policy for precise command semantics.
- Treating model recurrence as causal proof would repeat the retired
  provenance-classifier error. Keep source limits and the human disposition
  record visible in the template.
- A broad collaboration prescription could imply unsafe concurrent writes.
  Limit multi-developer guidance to shared evidence, a single correction owner,
  and serialized committed rounds.

## Deferred

- Productizing the handoff record as a plan-tool command or persisted schema.
- Measuring whether the guide reduces audit rounds; such a claim needs a
  separate, bounded evidence plan.

## References

- `integrations/shared/DIRECTIVES.md` — canonical manual convergence loop,
  authority direction, three exits, and post-run stop rule.
- `CLAUDE.md` — repository-specific measurements for class-wide hand-applies,
  premise checks, test verification, and recurring code-review symptoms.
- `docs/how-to/pipeline/audit.md` and `docs/how-to/pipeline/run.md` — persisted audit evidence and
  post-run reconciliation lifecycle.
- `docs/implementation-plans/archive/2-audit-trajectory-instrumentation.withdrawn.md`
  — dated false-premise example.
- `docs/evidence/claude-md-measured-incidents.md` — retained class-wide-application
  and remedy-verification evidence for the domain-constraints trajectory.
