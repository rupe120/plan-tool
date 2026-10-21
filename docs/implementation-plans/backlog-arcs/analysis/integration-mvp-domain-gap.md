# What the chat-centric inception phase needs that Integration's domain does not have

**Status (2026-09-08):** dated grounding for the retired 2026-08-28 definition. The inventory of the frozen `integration` domain and the two earlier feedback rows remain evidence; the conversation/mob entity gap it argues for is not a Integration requirement. Integration's product definition is in `integration/docs/concepts/integration-mvp-domain-disposition.md`.

Integration's current `01-domain.md` (16 entities) models the **construction half only**:
`user, initiative, roadmap, artifact, plan, plan-step, approval,
provider-configuration, repository-policy, workspace, agent-run, evidence,
execution-status-event, audit-record, platform-policy, pilot`.

There is **no conversation, message, session, group, mob, or document-draft
entity anywhere in the domain, and no phase concept.** Chat is not modelled at
all — the closest thing is `execution-status-event`, which is a one-way run
status feed, not a dialogue.

The 12 workflows are likewise all construction-side (`flow-create-initiative`
through `flow-run-pilot`); none covers exploration, elaboration, or synthesis.

## Already anticipated, and still unanswered

Two `awaiting-review` feedback rows on `01-domain.md` asked for exactly this
and were escalated rather than answered:

- `fb-pre-roadmap-ideation-lifecycle` — "Add an explicit, adaptive pre-roadmap
  lifecycle before plan-tool roadmap generation… idea → explore → shape →
  human ready-to-plan decision → plan-tool roadmap." Its response agreed and
  said delivering it needs "new domain entities (an idea, an exploration
  record, and a versioned planning brief, each with their own approvals and
  lineage links), at least one new rule… and a new workflow" — "more structure
  than a single bounded row change to this domain stage can safely express."
- `fb-adaptive-ideation-routing` — routing criteria (fast path vs. mandatory
  exploration), with advisory agent work that "may prepare evidence and a
  proposal, but cannot approve scope or make a planning decision."

Both were escalated for cross-artifact scope review that never happened,
because the receipt route closed. **The 2026-08-28 intent — AI-DLC inception
with mob conversations — is the answer those two rows were waiting for.**

## What carries forward unchanged

The construction-side authority rules are well-formed and reusable verbatim as
brief input; they already say precisely what the construction phase may do:

- `rule-plan-tool-roadmap-authority` — plan-tool generates and revises every
  roadmap; Integration only asks and displays.
- `rule-plan-tool-promotion-authority` — plan-tool alone turns an approved
  roadmap into a plan and its steps.
- `rule-plan-tool-story-traceability` — plan-tool's own story output is the
  only source of story artifacts; it is an internal artifact, **not** an
  external Jira integration.
- `rule-plan-tool-execution-orchestration` — plan-tool drives each bounded code
  change in a controlled workspace; Integration and any directly-invoked agent may
  only request, route, or advise.
- `rule-plan-tool-reconciliation-authority`, `rule-plan-tool-audit-handoff`.
- `rule-explicit-approval`, `rule-role-boundaries`, `rule-durable-artifacts`,
  `rule-durable-work`, `rule-execution-status-stream`.

## Conclusion

The MVP is roughly **half new domain, half retained**. Inception is entirely
new surface (conversation, group/mob, seed, response, synthesized brief, phase
state); construction is largely already modelled and can cite the existing
rules. That split is the strongest argument yet for a new roadmap slug rather
than revising `roadmaps/integration/`: a bounded per-row feedback route cannot add a
phase model and six entities, which is exactly what the escalated rows said.
