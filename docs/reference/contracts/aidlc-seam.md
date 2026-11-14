# AI-DLC seam contract

The boundary between an orchestration layer that runs the AI-DLC workflow framework and
`plan-tool`'s `roadmap` verb: who owns what, which source material is grounding and which
is not, and how a recorded source baseline is admitted. The integration overview is
[AI-DLC integration](../../integrations/aidlc-integration.md); the design behind this
contract is [roadmap fit to the AI-DLC workflow framework](../../design-plans/roadmap-aidlc-inception-fit.md).

## What the seam provides

1. A connector supplies a committed, approval-bound source set in `plan-tool`'s generic
   input vocabulary.
2. `roadmap` records and verifies that source identity before any route makes a claim
   that depends on it.
3. Each stage receives only declared grounding. Judgment and approval evidence never
   become stage-prompt authority.
4. Carried decisions, questions, constraints, obligations, and rules stay visibly distinct
   from `roadmap`-derived claims and keep resolvable citations.
5. The deterministic gates are the only publication authority. Wider reader context never
   grants wider write authority.
6. The orchestration layer validates the connector-to-framework mapping. `plan-tool` does
   not parse AI-DLC names or layouts.

## Owners

Keep these three owners separate in plans, detail, code, tests, and operator documentation.

| Layer | Owner | Contract |
| --- | --- | --- |
| Framework semantics | AI-DLC workflow profile and the orchestration layer's connector | Maps framework artifacts and approved records to generic roles, selected rule sections, and provenance. |
| Runtime layout | The orchestration layer and the AI-DLC runtime | Owns repository paths, intent directories, stage slugs, hooks, audit shards, and approval-receipt storage. |
| Engine contract | `plan-tool` `roadmap` | Owns generic roles, identity, citations, prompt routing, artifact rows, gates, and results. |

`plan-tool` receives generic roles, not a directory tree. A connector mapping can change
with a workflow profile without a `plan-tool` parser release, and a `plan-tool` role can
also serve a producer that is not AI-DLC.

## Treatment of source material

| Source material | `plan-tool` treatment |
| --- | --- |
| Confirmed intent, scope, constraints, selected experience context, and selected rules | Grounding. It reaches only the stage requests that declare it. |
| Confirmed upstream answer | Inherited decision with a source citation. `roadmap` does not re-decide it. |
| Unresolved item | Open question or assumption. It never silently becomes a requirement or scope boundary. |
| Accepted-risk finding with a named later action | Obligation with one visible disposition, when that capability is selected. |
| Approval handoff, decision-log repetition, runtime metadata | Provenance only. Never prompt authority. |
| Prioritized backlog, stakeholder-map body, unselected alternatives, proto-decomposition | Judgment material. It is excluded from prompts so it cannot become a plan-row count. |

Only a confirmed answer may ground a scope boundary. Workflow configuration, including
framework scope and execution lists, never widens product scope.

## Source admission

- A stage run binds one recorded brief path and decoded-text digest.
- Changed or legacy content at that path refuses before a stage writes, unless the operator
  supplies both the recorded `--from-existing` path and `--confirm-brief-rebind`. That
  acceptance replaces only the source baseline, never artifacts, feedback, or seeds.
- Matching and initial stage runs keep their ordinary behavior. A different path stays
  refused, and non-stage routes reject the confirmation flag.
- Semantic changes to a brief go through owning-artifact feedback or a successor lineage.
- Non-stage routes get no stage lifecycle and no same-path baseline-acceptance authority.
  `--analyze-escalation` and `--enroll-version` refuse `changed-brief` and `legacy-brief`
  with redacted status `1` and publish nothing; log-free `--view impact-analyses` returns
  those states with status `0` and no route; `--rewrite-structural` refuses after
  evaluator admission and guarded recovery, also with no publication.
- Admission is not a generic framework. A later route reuses a helper only after its own
  authority and result semantics are selected and tested.

## What `plan-tool` does not own

- Running AI-DLC, mutating the orchestration layer, or starting a `roadmap` run against its
  corpus.
- The connector mapping, rule selection, and question presentation.
- AI-DLC runtime paths, intent directories, stage slugs, hooks, audit shards, and
  approval-receipt storage.

## Capabilities beyond the seam

Per-stage supplementary sources with declared roles (`BACKLOG.md` #383) and a read-only
`roadmap --view status --json` projection (`BACKLOG.md` #385) are held until evidence
shows a concrete need. Each needs its own seed, plan, two audit gates, execution,
reconciliation, and independent review; a first production integration admits only the
roles and capabilities that the frozen corpus and a controlled comparison show are needed.
