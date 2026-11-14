# History

*Past decisions and retired contracts that remain useful for correct action.*

- [Historical backlog decisions](backlog-decisions.md)
- [Roadmap evidence version-1 retirement](roadmap-evidence-v1-retirement.md)

## Find the decisions for an area

Before designing, changing or reviewing behavior in an area, read its contract
first, then the settled decisions and evidence below. A decision recorded here is
settled unless new evidence reopens it; the records name the evidence that would.
Headings below are sections of [`backlog-decisions.md`](backlog-decisions.md).

| Area | Contract or owner | Settled decisions (`backlog-decisions.md` §) | Design and evidence |
| --- | --- | --- | --- |
| Roadmap stages, versions and feedback | [`ROADMAP_FORMAT.md`](../../ROADMAP_FORMAT.md), [`ROADMAP_FEEDBACK_FORMAT.md`](../../ROADMAP_FEEDBACK_FORMAT.md) | "#328 — Accepted-head versions and reader migration"; "#367 and non-stage routes — Brief rebind authority"; "#208 — The `roadmap` arc, positions 01–04"; "#215"; "#232"; "#289"; "#298"; "Roadmap evidence-storage hardening" | [Roadmap evidence v1 retirement](roadmap-evidence-v1-retirement.md); [run measurements](../evidence/roadmap-run-measurements.md); [layering measurement](../evidence/roadmap-layering-measurement.md) |
| Roadmap to plans | [`docs/how-to/roadmap.md`](../how-to/roadmap.md) | "#496 — Roadmap mapping and seed-to-plan derivation in the existing pipeline" | [plan-set benchmark](../evidence/roadmap-plan-set-benchmark.md); [derivation comparison](../evidence/roadmap-plan-derivation-comparison.md); [handoff investigation](../evidence/integration-roadmap-to-plan-handoff.md) |
| AI-DLC seam | [`aidlc-seam.md`](../reference/contracts/aidlc-seam.md), [`aidlc-integration.md`](../integrations/aidlc-integration.md) | "#384 — Carried settled decisions"; "#442 — AI-DLC errors with the plan-tool skill installed" | [fit design](../design-plans/roadmap-aidlc-inception-fit.md); [intake comparison](../evidence/roadmap-aidlc-intake-comparison-20260916.md) |
| Audit, gates and convergence | [`audit.md`](../how-to/pipeline/audit.md), [`GATES.md`](../GATES.md), [`ITERATION.md`](../ITERATION.md) | "#125 — Severity-aware low-yield audit convergence"; "#290 — Bare-plan audit altitude policy"; "#299"; "#251"; "#261"; "#231"; "#153 / #158"; "#91 / #248"; "#123" | [measured incidents behind `CLAUDE.md`](../evidence/claude-md-measured-incidents.md); [nondeterministic plan design](../explanations/nondeterministic-plan-design.md) |
| Run and executor | [`run.md`](../how-to/pipeline/run.md) | "#147"; "#178 — Run phase attribution"; "#122 — Per-step detail commits" | [overengineering checkpoints](../evidence/overengineering-checkpoints-test.md) |
| Create, detail and seeds | [`PLAN_FORMAT.md`](../../PLAN_FORMAT.md), [`DETAIL_FORMAT.md`](../../DETAIL_FORMAT.md), [`SEED_FORMAT.md`](../../SEED_FORMAT.md) | "#331 and #333 — Seed-to-create source boundary"; "#161 — Seed guardrail sections survive `create`"; "#121 — Deferred-concept sign-off"; "#211"; "#250 — Plan withdrawal" | [authored-artifact versioning](../evidence/authored-artifact-structure-versioning.md) |
| Models, backends and prompt budget | [`BACKENDS.md`](../BACKENDS.md), [`model-window-sources.md`](../reference/contracts/model-window-sources.md), [`ARCHITECTURE.md`](../ARCHITECTURE.md) § "Prompt-budget window" | "#390 — The skill routers do not set `model:`"; "#392 — No durable per-repo codebase profile" | [backend selection design](../design-plans/BACKEND_SELECTION.md); [backend recommendations](../evidence/backend-recommendations.md); [Integration context budget](../evidence/integration-context-budget-2026-10-09/sizing.md) |
| Tracking and Jira | [`TRACKING.md`](../TRACKING.md), [`jira-management.md`](../how-to/jira-management.md) | "#205 — Jira-grade renumber migration withdrawn"; "#293 — The former opt-in Jira handoff is superseded"; "#233 — Duplicate `BACKLOG.md` ids fail a test"; "#92 — Plan lineage with model-authored summaries" | none |
| Onboarding and documentation | [`docs/README.md`](../README.md), [`documentation-style.md`](../reference/documentation-style.md) | "#521 — A short core path for newcomers"; "#522 — One-command repository setup" | [skill-led demo verification](../evidence/skill-led-demo-examples-verification.md) |
| Release and public distribution | [`RELEASING.md`](../RELEASING.md) | none | [content snapshot](../evidence/public-release-content-snapshot.md); [ref disposition](../evidence/public-release-ref-disposition-20261021.md) |

This index routes by area. It does not restate decisions: open the record, which
carries the reason and the evidence. When a decision is added to
`backlog-decisions.md`, an evidence page or a design plan, add its heading to the
matching row so the area stays discoverable.
