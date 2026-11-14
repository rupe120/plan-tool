# AI-DLC seam contract

The boundary between an orchestration layer that runs the AI-DLC workflow framework and
`plan-tool`'s `roadmap` verb: who owns what, which source material is grounding and which
is not, and how a brief is admitted. The integration overview is
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

Source identity belongs to the accepted version, and no separate source baseline exists.

- A first stage run reads the brief named by `--from-existing`. The published version
  stores the brief's raw bytes as `brief.md` and records its digest beside the four stage
  artifacts. Every later command reads that stored brief and never the original path.
- A stage run refuses once an accepted head exists. A roadmap with a head changes only
  through feedback and candidate review.
- Before the head exists, held stages sit in a resume directory beside a `brief.digest`.
  A brief whose text differs from that digest refuses before any backend call; the
  operator restores the brief, deletes the directory by hand, or starts a successor slug.
- A semantic change to the product definition goes through owning-artifact feedback or a
  successor lineage. Nothing rebinds a changed brief to an existing roadmap.
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

Each further capability needs named evidence and its own contract, and none rides in #383:

| Capability | Selected when | Needs |
| --- | --- | --- |
| Settle-once questions | A load-bearing unresolved item is re-decided by current rows | Question identity, a stop or provisional policy, dependent-row invalidation |
| Obligations | An approved accepted-risk finding needs a disposition | Exactly one disposition per obligation, and a gate |
| Selected workflow rules | A named rule changes roadmap meaning and fits generic grounding | Section selection, citations, exclusion of runtime conduct |
| Shared seam frame | A revision route changes artifact meaning outside the proven box | Deterministic frame bytes, request reach, ceilings, prompt authority |
| Coverage projection | A real phase check needs machine-readable source-item coverage | Stable ids, coverage states, a boundary summary |
| `--view status --json` (#385) | A connector consumer needs state between runs | A versioned read-only view, never execution authority |

Stop and record a new decision when a role reader would change the stored source shape
without a compatible read/write transition and legacy-record tests, or when a capability
touches an Inception step that the orchestration layer has neither assigned to `roadmap`
nor skipped in its workflow profile.
