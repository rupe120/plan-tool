# Integration plan derivation review

The new base plans provide clearer responsibility boundaries and stronger acceptance language. They do not yet demonstrate complete coverage of the original Integration gaps: the eight captured candidate plans have no per-step detail files. This is a review of raw creation output, before manual repairs, bare-plan audits, or detail authoring.

## Review scope

The [benchmark](roadmap-plan-set-benchmark.md) defines the original failure corpus. The experiment lives at `/private/tmp/roadmap-plan-derivation-comparison-20261016`. Baseline tool `f1cba286a` and candidate `5433b3a53` use Codex `gpt-6.1-sol` against Integration application baseline `998a78706a22bcf8b64be7ce382608fff1f8189a`. Native upstream gates receive identical frozen stages 1–3; only stage four uses fresh model generation. Baseline mapping contains five plans; candidate mapping contains ten. Five baseline and eight candidate base plans are available for this review. Candidate AWS delivery and end-to-end proof are available as seeds, not yet published base plans.

The earlier nine-plan, 53-detail replay includes session corrections and retrospective context. It is a failure corpus, not an unmodified matched baseline. Existing `workspace-membership-selection` reports in the experiment clones are unrelated; `grounding.json` files are not step detail files. None establishes detail coverage for the new plans.

## Observable improvements

| Area | Baseline output | Candidate output | Assessment |
| --- | --- | --- | --- |
| Responsibility boundaries | `integration-live-step` combines worker execution, conversation, references, revision review and browser integration in eight steps. | Separate isolated-session, conversation, repository-reference, revision-review and browser plans identify prerequisites and downstream consumers. | Clearer routes for independent implementation and integration review. More plans alone does not prove optimal granularity. |
| Handoff delivery | `integration-ready-handoffs` has one non-code prerequisite-verification step and no handoff implementation steps. | Six steps own evidence recognition, readiness checks, persistence/observation, correction reevaluation, continuation and observed proof. | A concrete implementation omission is addressed in the new base plan. |
| Durable output | The live-step plan groups durable observation with the other live capabilities. | Isolated sessions step 4 owns persisted attributed output; conversation consumes worker-owned output. | The producer and observer responsibilities are more explicit. Disconnected operation still needs detail and tests. |
| Reference integrity | Repository behavior shares the live-step plan. | A six-step route owns worker reads, catalog metadata, durable references, binding before dependent action and integrated observation. | A clearer route preserves exact path/revision and refuses substitution. |
| Browser integration | Browser proof is the last step of the broad live-step plan. | Eight browser steps consume named producers and finish with observed integrated behavior. | Integration has its own owner and does not absorb sibling capabilities. |
| Local source context | Identical-seed control publishes a References section containing only an external-research note. | The control retains all four local artifact References alongside that note. | A directly observed information-retention improvement; not semantic agreement certification. |
| Acceptance strength | The original failure corpus allows local/document checks to substitute for deployed proof. | Captured candidate plans explicitly require observed runtime or browser integration and preserve downstream deployed proof. | Stronger base-plan contracts; selected detail mechanics and final delivery plans remain unverified. |

## Original gap coverage

Plan intent: derive a complete, appropriately granular implementation plan set from roadmap artifacts, with coherent outcomes, dependencies, integration ownership and observable completion.

| Witnessed gap | Relevant candidate responsibility | What the raw output establishes | What remains to assess |
| --- | --- | --- | --- |
| Readiness-correction intake | `integration-ready-handoffs`, especially steps 2–4: correct-revision checks, persistence and requested reevaluation. | Corrected content cannot reuse evidence for different content; reevaluation requires applicable evidence. | The concrete producer and intake path for corrected evidence are not established by these base steps. |
| Session-lifetime cleanup | `integration-isolated-sessions`: durable lifecycle and replacement lineage, worker-only volatile resources. | Durable versus live state ownership and explicit replacement are named. | Terminal cleanup of processes, credentials and checkout access needs an explicit detail route and verification. |
| Safe output release | `integration-isolated-sessions` output producer and `integration-observable-conversation` consumers. | Output ownership and credential isolation are stated. | The release policy and withholding before unsafe exposure are not demonstrated. Credential isolation alone is insufficient evidence. |
| Handoff content continuity | Worker output producer, registry contracts and readiness consumers. | Named producers and checks make the boundary easier to inspect. | No demonstrated end-to-end durable handoff-content contract connects emitted content to the successor session and revision. |
| Catalog revision identity | `integration-repository-references` steps 2–4. | Catalog-owned revision-backed metadata feeds retained path/revision references and dependent reads. | Immutable workflow-configuration revision identity is not separately established; repository revision identity must not substitute for it. |
| Disconnected output indexing | Worker step 4 produces durable attributed output; conversation steps 1, 4 and 5 consume and replay it. | Production is assigned outside the browser observer. | Detail must show that output is persisted/indexed with no connected observer and replay does not execute the engine. |
| Submission reference binding | Repository-reference steps 3–5. | Selected path/revision remains attached through history; the worker reads it before dependent action. | Binding across the actual submission/dispatch boundary and failure handling need detail and tests. |
| Local References retention | Native create, identical-seed control. | Four local artifact References survive candidate creation and disappear from baseline creation. | This binary observation is complete for the selected control, not every possible input. |
| Observed deployment proof | Captured browser plan; AWS and end-to-end seeds. | Browser acceptance rejects document-only or simulated proof; final deployed acceptance has a named downstream owner. | The two pending base plans and all resulting details must retain observed dev deployment, independent target deployment and complete deployed journey proof. |

These responsibilities span multiple consumers rather than one accidental extra feature arm. This review does not count material audit findings or substitute for the native completeness gates. Several unresolved items are detail questions; missing shared producer contracts may require plan-level corrections before detail. Do not add implementation mechanics to seeds to force a favorable review.

## Current testing direction

Owner decision, 2026-10-16: stop at base plans and focus further testing on application business logic. Do not create detail files or spend this loop redesigning infrastructure decomposition.

Review shared producer operations using the captured application plans. Preserve scope and distinguish source omissions from mapping omissions, seed losses and create losses. Use bounded reruns of affected routes before proposing another tool adjustment. Keep unresolved implementation mechanics explicitly unassessed at base-plan altitude.

The present evidence supports improved decomposition and input retention. It does not support a claim that all initial gaps are closed or that the new detail bundles are more complete: those bundles do not exist. This single sample measures neither implementation efficiency nor a success rate.
