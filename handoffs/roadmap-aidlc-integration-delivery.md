# Handoff: deliver AI-DLC-compatible roadmap integration

## Status

**Delivery handoff.** This is the Plan-tool pickup record for making Roadmap
consume connector-provided, framework-grounded inputs without learning AI-DLC
runtime paths, artifact kinds, or stage names. The changed-brief rebind
confirmation slice (#367) and the corpus comparison are complete. The #384
implementation and post-run review tail are complete. #383
stays held without a comparison-proven per-stage source gap.

The generic stage-run source-admission boundary completes independent review on
2026-09-14. It is a prerequisite and evidence, not permission to spread
stage-run admission, lifecycle events, or same-path rebind semantics into
other writers.

This handoff does not run AI-DLC, mutate Integration, start a Roadmap run against the
Integration corpus, or select an unfiled Plan-tool capability. Integration owns the AI-DLC
runtime, corpus, approval receipt, and connector mapping. Plan-tool owns its
generic reader, source identity, prompts, gates, and stored artifacts.

## Outcome

The completed integration provides a narrow, durable seam:

1. A connector supplies a committed, approval-bound source set using
   Plan-tool's generic input vocabulary.
2. Roadmap records and verifies that source identity before any route makes a
   claim that depends on it.
3. Each stage receives only declared grounding; judgment and approval evidence
   never become stage-prompt authority.
4. Carried decisions, questions, constraints, obligations, and rules stay
   visibly distinct from Roadmap-derived claims and retain resolvable
   citations.
5. Existing deterministic gates remain the only publication authority. Wider
   reader context never grants wider write authority.
6. Integration validates connector-to-framework mapping outside Plan-tool. Plan-tool
   does not parse AI-DLC names or layouts.

This is an outcome, not one oversized implementation. Every selected slice
needs its own seed, plan, two audit gates, execution, reconciliation, and
independent review. The first production integration admits only the roles and
capabilities the frozen corpus and a controlled comparison show are needed.

## Authorities and current boundary

| Record | Authority |
| --- | --- |
| handoffs/roadmap-aidlc-inception-fit.md | Framework-fit design, settled decisions, open choices, and the eight possible engine changes. |
| handoffs/integration-seam-resume-order.md | Cross-repository checkpoint and Integration execution fence. |
| handoffs/roadmap-brief-source-drift-code-review.md | Converged evidence for the delivered stage-run source-admission boundary. |
| BACKLOG.md closed route-local brief-drift record | Delivered policy for non-stage writers. |
| BACKLOG.md closed #367 record | Delivered changed-brief stage-run rebind operator-intent policy. |
| BACKLOG.md #384 | Narrow compatibility capability: carried settled decisions with citations. |
| BACKLOG.md #383 | General compatibility capability: per-stage sources with enforced grounding and judgment roles. |
| BACKLOG.md #385 | Read-only status projection; it waits for a Integration connector consumer. |
| docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md | Canonical order: corpus comparison, #384, #383; #367 and the route-local brief-drift record are closed, and #385 remains independent and evidence-gated. |

Stage-run source admission, the route-local brief-drift policy, and #367 are
delivered. Stage runs bind one recorded brief path and decoded-text digest.
Changed or legacy content at that path refuses before a stage writes unless the
operator supplies both the recorded `--from-existing` path and
`--confirm-brief-rebind`; that acceptance replaces only the source baseline.
Matching and initial stage runs retain their ordinary behavior, a different
path remains refused, and non-stage routes reject the confirmation flag. The
closed route-local policy keeps that acceptance separate: analysis creation and
immutable-root enrollment refuse `changed-brief` and `legacy-brief` redacted
with status `1`, impact inspection returns a log-free status-`0` no-route state, and
structural rewrite refuses only after evaluator admission and guarded recovery.
#384 is implemented and review-converged; #383 remains unstarted. No Roadmap
run has used the AI-DLC corpus.

## Seam contract

Keep these three owners separate in plans, detail, code, tests, and operator
documentation.

| Layer | Owner | Contract |
| --- | --- | --- |
| Framework semantics | AI-DLC workflow profile and Integration connector | Maps framework artifacts and approved records to generic roles, selected rule sections, and provenance. |
| Runtime layout | Integration and AI-DLC runtime | Owns repository paths, intent directories, stage slugs, hooks, audit shards, and approval receipt storage. |
| Engine contract | Plan-tool Roadmap | Owns generic roles, identity, citations, prompt routing, artifact rows, gates, and results. |

Plan-tool receives generic roles, not a directory tree. A connector mapping can
change with a Integration workflow profile without a Plan-tool parser release. A
Plan-tool role can also serve a non-AI-DLC producer.

| Source material | Plan-tool treatment |
| --- | --- |
| Confirmed intent, scope, constraints, selected experience context, and selected rules | Grounding; it reaches only declared stage requests. |
| Confirmed upstream answer | Inherited decision with a source citation; Roadmap does not re-decide it. |
| Unresolved item | Open question or assumption; it never silently becomes a requirement or scope boundary. |
| Accepted-risk finding with a named later action | Obligation with one visible disposition when that capability is selected. |
| Approval handoff, decision-log repetition, runtime metadata | Provenance only; never prompt authority. |
| Prioritized backlog, stakeholder-map body, unselected alternatives, proto-decomposition | Judgment material; it is excluded from prompts so it cannot become a plan-row count. |

Only a confirmed answer may ground a scope boundary. Workflow configuration,
including framework scope and execution lists, never widens product scope.

## Ordered delivery path

### 0. Preserve the source-admission boundary

Treat the delivered source-admission boundary as fixed behavior:

- unconfirmed stage-run reads refuse changed or legacy recorded content before
  admission;
- a changed or legacy same-path rebind requires explicit
  `--confirm-brief-rebind` with `--from-existing`, and replaces only the source
  baseline, not artifacts, feedback, or seeds;
- semantic changes remain owning-artifact feedback or a successor lineage.

Do not refactor this boundary into a generic admission framework. A later
route reuses a demonstrated helper only after its own authority and result
semantics are selected and tested.

### 1. Delivered route-local brief-drift policy: non-stage writers

The closed route-local brief-drift record gives each route an explicit, tested policy without creating a generic
admission layer. A matching recorded decoded-text baseline retains existing
behavior. `--analyze-escalation` refuses `changed-brief` and `legacy-brief`
redacted with status `1` and no immutable analysis publication; log-free
`--view impact-analyses` returns those states with status `0` and no route or
workflow. `--rewrite-structural` preserves evaluator admission and guarded
recovery before its redacted status-`1` refusal and makes no artifact,
baseline, or seed publication. Backend-free, exclusive `--enroll-version`
returns the same redacted status-`1` refusal without an immutable version or
accepted-head claim. No non-stage route receives stage lifecycle or same-path
`--from-existing` baseline-acceptance authority.

Delivery evidence: [plan](../docs/implementation-plans/archive/2-roadmap-non-stage-brief-drift.md),
[final detail-grounded audit — retained historical summary](../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions),
and guide-review evidence from the [guide-contract review guard](../tests/test_roadmap_format.py).

**Convergence record (2026-09-15).** The route-local brief-drift delivery completes its post-run
`reconcile-code --all` tail and logic-focused review convergence. The full suite
passes with `12357 passed, 190 skipped`. Two independent Sonnet reviews of
`597e7068f05d75b00650e832bf275d6ab3c18cb1..8769c51b` find no current
production-logic defect; the second returns `CLEAN`. The documentation-only
closeouts `8875f9f8` and `01b3929a` correct structural-rewrite guidance and
state the logic-focused convergence rule; they do not change the reviewed
runtime behavior. It has no remaining implementation or review-tail action.

### 2. Delivered #367: changed-brief rebind intent

#367 follows the closed route-local brief-drift policy. **Decision
(2026-09-15, user-confirmed):** repeating the same-path `--from-existing`
argument is not sufficient deliberate acceptance. Changed or legacy brief
content requires a distinct explicit confirmation before it can replace the
recorded baseline.

Delivered on 2026-09-16: `--confirm-brief-rebind` supplies that stage-run-only,
headless signal. It admits only changed or legacy content at the recorded path
with explicit `--from-existing`; matching and initial runs are no-ops, a
different path remains refused, and non-stage routes reject the flag before a
handler or writer runs. An accepted rebind still writes only `source.json`
before ordinary processing and retains the existing `accepted-rebind`
lifecycle fact.

The plan is [Roadmap Brief Rebind Confirmation](../docs/implementation-plans/archive/2-roadmap-brief-rebind-confirmation.md).
Three complete `reconcile-code --all` sweeps reach zero findings in the saved
reports. The review tail confirms two live preflight normalization gaps and
fixes them in `a56683a9` and `48b0957c`, with regression coverage. The last
production-logic change is `48b0957c`; two independent Sonnet 5 reviews after
it find no further live logic/property failure. The later commits
`ed5be0e6` and `6d0a71cc` improve coverage and documentation only, so they do
not reset that logic-convergence window. The final full suite passes with
`12633 passed, 190 skipped`; the final documentation-contract suite passes
with `63 passed`.

The final two review records are
`.tmp/roadmap-brief-rebind-confirmation.code-review-4.ndjson` and
`.tmp/roadmap-brief-rebind-confirmation.code-review-5.ndjson`. Their remaining
items are triaged as non-live: an unsupported partial CLI namespace, localized
refactor opportunities, a prospective scenario test, and a docstring omission.
They neither require a production change nor reopen the convergence loop.

### 3. Establish corpus-ready evidence before selecting intake machinery

The AI-DLC owner supplies a fresh approval-bound, committed corpus and
connector-side provenance. Plan-tool does not start, stop, or alter that
workflow. Once a Roadmap experiment is separately authorized, compare:

1. the approved initiative brief as the current one-file input; and
2. a deterministic, role-sectioned composition of selected Inception inputs.

Change one arm only. Exclude the intent-backlog body and stakeholder-map body.
For each arm record:

- pending rows per distinct open question;
- output contradicting a confirmed upstream answer;
- dispositions for the three accepted-risk obligations;
- whether the domain stays a generic workflow surface with runtime selection
  per step;
- revision drift after equivalent feedback through routes that do not see the
  source today.

This comparison selects the minimum first source carrier and role set. If one
composed file closes the observed gap, do not add a manifest or broad role
reader because it is more general. If it cannot safely close the gap, record
the exact failure and choose the smallest generic reader that can.

**Provisional sequencing decision (2026-09-16, user-confirmed):** #384 is the
presumed next compatibility slice; #383 remains held. The comparison is a
confirmation gate, not permission to start #383 by default. It confirms #384
when the observed failure is a Roadmap row that re-decides, loses, or
contradicts a confirmed upstream answer. It selects #383 only when a named
stage lacks essential grounded facts that cannot safely fit in the approved
one-file brief, with the stage, facts, and failed safe representation recorded.
No general source carrier, manifest, or role reader ships merely because the
composed comparison arm contains more material.

After the corpus is frozen and the experiment is authorized:

1. Run the two arms against the same Roadmap input and revision scenario.
2. Record the measures above with citations to the approval-bound corpus.
3. If #384 is confirmed, write only its seed and bare plan; carry confirmed
   decisions as cited inherited facts, not stage-prompt authority.
4. Hold #383 unless the report names its essential per-stage grounding gap and
   proves why the approved brief cannot carry it safely.

### 4. Delivered #384: carried settled decisions

**Comparison record (2026-09-16).** The separately authorized, approval-bound
Integration Gate 1 comparison is recorded in
[`docs/evidence/roadmap-aidlc-intake-comparison-20260916.md`](../docs/evidence/roadmap-aidlc-intake-comparison-20260916.md).
Both the approved one-file brief and a deterministic role-sectioned composition
produce four accepted Roadmap artifacts and preserve the generic configured-
runtime surface. Both nevertheless re-author confirmed upstream choices as
Roadmap `settled` decisions, add model-authored rejected alternatives, and omit
resolvable source citations. That observed provenance failure confirms #384.
No composed-only essential stage fact proves a need for #383, so #383 remains
held; the accepted-risk obligation gap remains separately gated.

#384 is the narrow first compatibility capability. Its implementation plan is
`docs/implementation-plans/2-roadmap-carried-settled-decisions.md`; the
source-carrier and citation shape are plan inputs.

The delivered capability:

- accepts a closed block of confirmed upstream decisions;
- emits settled Roadmap decisions with source citations;
- distinguishes inherited from Roadmap-derived decisions;
- requires each carried decision to anchor a live row and resolve its citation
  inside the recorded source;
- retains rejected-alternative and rationale requirements for Roadmap-derived
  decisions only;
- refuses a carried decision with no anchor or resolvable confirmed source.

A source citation is the proof of a carried decision. Never manufacture
rejected alternatives from the other options in an upstream question.

**Convergence record (2026-09-16).** All five implementation steps, both plan
audit gates, and three complete `reconcile-code --all` sweeps are complete.
The post-run reviews use the project-root `.tmp/` findings documents
`roadmap-carried-settled-decisions.code-review-{findings,round2,round3,round4,round5,round6,round7,round8}.md`.
Confirmed local-revision authority and brief-admission gaps are fixed through
`acbb63f8`; `6fe325f4` makes inherited citations visible in HTML and text
views, and test-only `93d058ff` pins each brief-recheck refusal. The final
full suite passes with `12715 passed, 190 skipped`.

The two independent reviews of the final runtime snapshot (`6fe325f4`),
rounds 7 and 8, are **low-yield after session triage, not clean reports**.
Round 7's branch-specific test finding is closed by `93d058ff`, which round 8
verifies. Round 8 names prospective coverage of later TOCTOU checkpoints,
blank-source display for an already gate-rejected artifact, test-fixture
duplication, and retrospective commit scope; it finds no live authority or
publication defect. The earlier recurring alternate-fence suggestion is
closed as an explicit three-backtick, column-zero format contract with tests.
Per the post-run stop rule, do not resample this unchanged logic snapshot to
turn those non-blocking findings into a nominally clean label. #383 remains
held pending a separate comparison-proven per-stage grounding gap.

### 5. Deliver #383: role-routed supplementary grounding

#383 generalizes only the comparison-proven gap after #384. Its first surface
is an optional per-stage supplementary source with an explicit role. The
identity digest covers each admitted supplement and its role declaration.

The implementation must prove the prompt boundary:

- grounding reaches only its named stage prompt and is fenced as data;
- judgment reaches no stage prompt, including the plans stage;
- reader context does not change write authority; existing gates remain in
  force unless a separately selected contract adds a gate;
- schema values never use AI-DLC artifact names, paths, or runtime stage slugs;
- projects with only a hand-written brief preserve current behavior.

Hosting facets and quality dispositions are candidates only if the selected
carrier states them safely. Do not position-parse free-form upstream prose by
default. The first release does not add an enumerable backlog or stakeholder
channel.

### 6. Select broader framework fit only with named evidence

None of these capabilities belongs opportunistically in #383:

| Capability | Selection condition | Separate contract |
| --- | --- | --- |
| Settle-once questions | The comparison finds a load-bearing unresolved item that current rows re-decide. | Question identity, stop or provisional policy, dependent-row invalidation. |
| Obligations | An approved accepted-risk finding needs Roadmap disposition. | Exactly-one disposition and its gate. |
| Selected workflow rules | A named rule affects Roadmap meaning and fits generic grounding. | Section selection, citations, runtime-conduct exclusion. |
| Shared seam frame | A revision route changes artifact meaning outside the proven box. | Deterministic frame bytes, request reach, ceilings, prompt authority. |
| Coverage projection | A real phase check needs machine-readable source-item coverage. | Stable IDs, coverage states, boundary summary. |
| #385 JSON status | Integration has a connector consumer needing Roadmap state between runs. | Versioned read-only view, never execution authority. |

Create a focused backlog entry and seed before selecting one. The
Inception-step coverage decision remains shared: Plan-tool decides whether
Roadmap grows a capability, while Integration decides whether its workflow profile
explicitly skips that step.

## Open decisions

`roadmap-aidlc-inception-fit.md` § "Open design choices" owns the
list of undecided choices. This table records only the evidence that would
decide each one. These choices do not belong hidden in a detail file or
implementation patch.

| Decision | Required evidence or owner |
| --- | --- |
| Source carrier: role-tagged sources, a named manifest, or typed frontmatter on one composed brief | Decided for now (2026-09-16 comparison): #384 ships on the single brief and #383 stays held. Reopens only if a per-stage grounding gap is proven. |
| Hosting and quality ingestion | Safe source representation; no default position-based free-prose parser. |
| Roadmap-raised question default | A planned stop versus provisional decision; source-change behavior does not decide it. |
| RAID risks, issues, and dependencies | Existing-concept destination or separately justified row type; malformed upstream Markdown must fail clearly or be connector-normalized. |
| Scope-list rendering | Proof it cannot preselect plan rows, or an alternate coverage check. |
| Requirement IDs and Inception coverage | Selected requirements-analysis coverage decision. |
| Frame reach, size, and fit review | Revision-pass evidence and measured request ceilings. |

If one becomes necessary, add a BACKLOG.md entry with outcome, scope,
non-goals, stop condition, route assignment, and evidence. Do not enlarge
#383 or #384 silently.

## Required planning and verification loop

Every selected Plan-tool slice starts from a clean committed checkpoint.
Commit a hand-applied audit correction before the next tool invocation.

1. Write a seed from the selected backlog contract. It names only the smallest
   proven capability, affected routes, persisted contracts, non-goals, and
   focused acceptance cases.
2. Create the bare plan with the conceptual model, then commit it.

       plan-tool create <slug> --from-existing <seed> --iterate --model gpt-5.6-sol -y < /dev/null

3. Audit the bare plan with the implementation model. Read the saved report,
   enumerate identifier and vocabulary sites before each correction, hand-apply
   only in-scope conceptual plan changes, commit, and re-audit.

       plan-tool completeness-audit <slug> --iterate --commit --model gpt-5.6-terra -y < /dev/null

4. Author detail without forcing detail iteration, then run the
   detail-grounded audit with the same site enumeration and goal check.

       plan-tool detail <slug> --commit --model gpt-5.6-terra -y < /dev/null
       plan-tool completeness-audit <slug> --iterate --commit --model gpt-5.6-terra -y < /dev/null

5. Run the approved plan with per-step commits. Do not terminate a quiet
   long-running command; monitor it and ask before stopping it.

       plan-tool run <slug> --all --commit --model gpt-5.6-terra -y < /dev/null

6. Reconcile the implementation against its plan and complete independent
   code-review convergence. Update this handoff, BACKLOG.md, BUG_BACKLOG.md,
   and the roadmap and Integration backlog arcs with every in-scope or deferred
   finding.

       plan-tool reconcile-code <slug> --all --model gpt-5.6-terra -y < /dev/null

For every finding, record the defect class, identifier sweep, vocabulary sweep,
smallest correction, observable test, and why the mechanic delivers the
property on the ordinary input.

## Stop and escalation conditions

Stop the selected slice and record a new decision rather than widening it when:

- Plan-tool needs an AI-DLC path, artifact kind, or runtime stage name; move
  mapping to Integration's connector.
- A source has no committed, approval-bound identity; do not create an
  implicit current baseline.
- Judgment or enumeration needs to reach a stage prompt; prove a
  non-enumerating contract first or keep it outside.
- A role reader changes stored source shape without a compatible read/write
  transition and legacy-record tests.
- A route needs changed-brief acceptance beyond #367's confirmed same-recorded-
  path stage-run policy.
- The comparison shows no gap over the one-file brief; retain the smaller
  carrier instead of building a general intake system.
- A capability affects an uncovered Inception step before Integration selects
  Roadmap coverage versus an explicit workflow-profile skip.
- Integration requests status projection before it has a concrete consumer; keep
  #385 evidence-gated.

## Next pickup

No slice is selected. The corpus comparison finished 2026-09-16
(`docs/evidence/roadmap-aidlc-intake-comparison-20260916.md`), #384 shipped,
and #383 and #385 stay held on their selection conditions in § 6. Select the
next capability only when one of those conditions is met, through a focused
backlog entry and seed. Do not build an AI-DLC-specific parser or a broad
source manifest.

## Scope fence

- No Plan-tool code learns AI-DLC paths, stage slugs, runtime protocol names,
  or artifact-kind names.
- No Integration source, connector, application code, workflow state, or AI-DLC
  process changes through this handoff.
- No generic source manifest, multi-source intake, question subsystem,
  obligations subsystem, rules reader, frame, coverage projection, or status
  view ships until its selection condition is met and its plan converges.
- Hand-written-brief projects retain current behavior unless a selected plan
  explicitly supplies and tests a compatible transition.
