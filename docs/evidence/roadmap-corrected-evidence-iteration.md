# Corrected-evidence business-logic iteration

This review tests one application route through roadmap mapping, selected-row seed materialization and base-plan creation. It asks whether corrected-content reevaluation has an assigned evidence producer and an integrating consumer. It does not create detail files, implement Integration, probe live engines or redesign infrastructure.

## Source trace and first incomplete assignment

The accepted candidate version is `f373ddd13c76d8dd46791f69d9dd75cf69b604da9f054298e9813b2dca8653fb` under `integration-granularity-comparison`. Its business requirement survives seed and base-plan creation. The missing element is an explicit assignment for the production/update operation needed by the consumer.

| Layer | Source anchor | What it establishes | What remains implicit |
| --- | --- | --- | --- |
| Domain | `01-domain.md:190`, `rule-handoff-check` | Corrected content cannot reuse evidence for different content; the owner can request reevaluation; completed-but-blocked state remains until applicable evidence and checks establish readiness. | No selected internal refresh mechanism. A mechanism is not required at this altitude. |
| Constraints | `02-constraints.md:62`, `constraint-connector-only-handoff`; `:69`, `constraint-engine-reported-done`; `:119`, `constraint-transition-blocker-detail` | Supported declarations, owning-engine completion and exact supplied blockers constrain the route. | Runtime support is a proof obligation rather than an established capability. |
| Components | `03-components.md:70`, `component-step-transition`; `:90`, `component-engine-worker`; `:152`, `decision-step-transition-scope` | The worker owns engine sessions; one transition authority owns completion/readiness facts and handoff results. | These role assignments do not establish which supported operation supplies fresh evidence for corrected completed content. |
| Mapping | `04-roadmap.md:243`, `integration-isolated-sessions`; `:247`, `integration-ready-handoffs`; `:164`, `assumption-supported-runtime-evidence` | Execution produces lifecycle evidence; transitions consume it and offer reevaluation; runtime contracts must establish supported behavior. | No explicit operation assignment connects corrected-content production and renewed evidence to the reevaluation consumer. |
| Original seed | `integration-ready-handoffs`, raw SHA-256 `a581b491829829d1c6335c88a5a98f7b7c886b864d33c8755c9d09761c88f3ab` | Preserves the readiness rule, four prerequisites and owner reevaluation. | Does not invent an assignment missing from the accepted mapping. |
| Original base plans | Worker step 5; handoff step 4 | Worker supplies attributed completion/gate/output/revision evidence; handoff requests fresh worker evidence after correction. | Requesting fresh evidence does not establish a delivered production/update operation in the prerequisite plan. |

The first incomplete responsibility assignment is therefore at mapping altitude, not disappearance of the domain rule in materialization. This does not prove that a particular API, schema, report counter or new session is required. Unsupported runtime behavior remains a separate source limitation.

## Controlled inputs

Experiment root `E` is `/private/tmp/roadmap-plan-derivation-comparison-20261016`. The new independent full clone is `E/business-logic-loop2-seed-integration`, without a remote, shared Git store or live merge. Application baseline remains `998a78706a22bcf8b64be7ce382608fff1f8189a`; inputs and outputs change planning state only.

Tool checkout: `/private/tmp/plan-tool-roadmap-plan-set-20261016`, invocation snapshot `cacea5aa3`, production change `586255721`. Every model call explicitly selects Codex `gpt-6.1-sol`. No additional production change is made for this iteration: it tests the guidance already implemented and reviewed.

### Selected materialization from the existing mapping

Starting from raw mapping/seed checkpoint `5e72651`, remove only the selected handoff draft in the new clone and commit that recoverable missing-draft state as `f5ab5a4`. Keep the original elsewhere unchanged. Other nine seeds remain visible; this differs from the corpus available during the original serial all-row materialization, so wording differences are not a causal estimate.

Native command, with explicit tool PYTHONPATH and the implementation checkout's `.venv/bin/python` as host:

```sh
roadmap integration-granularity-comparison --materialize integration-ready-handoffs -y < /dev/null
```

The result preserves the accepted outcome, dependencies, corrected-revision readiness, observed proof and all four local References. Its Stop/defer explicitly keeps implementation work behind unavailable prerequisites. It does not invent the missing production-operation assignment. Raw seed SHA-256: `3733a2cc908516442c37e4dae93d99d9bc78251b64a107ae7deef1290ee3f1f8`; capture `8006a29`. Native run `2026-10-16T19-30-37+00-00-447e57` completes rc 0 in 63.545 seconds, first attempt; original shell session 80433 exits 0. Both original immutable stores and accepted heads remain byte-identical.

### Fresh mapping with the existing improved guidance

Scratch harness `E/roadmap-plan-derivation-business-loop2.py` calls native `roadmap.run_roadmap` for new slug `integration-business-logic-loop2`. It replays frozen stages 1–3 through native gates and generates stage four with the real backend. The runner reports four stages; only stage four is model-generated. Accepted stages 1–3 and the brief are byte-identical to the initial candidate's accepted inputs. Native publication normalizes trailing newlines, so compare accepted artifacts to accepted artifacts rather than unnormalized source responses.

One stage-four attempt publishes version `41c1e9369d922888946f93d9f76b31bd42cc2e798909053372abbfbeec770e49`, capture `555bb07`. Native run `2026-10-16T19-32-35+00-00-078566` completes rc 0 in 110.341 seconds; original shell session 64508 exits 0. The mapping still has ten rows: this result improves explicit responsibility assignment without increasing the count.

| Responsibility | Earlier mapping | New mapping |
| --- | --- | --- |
| Runtime contract proof | Usable completion/gate/output/revision evidence. | `runtime-contract-proof` also establishes supported operations producing actual successor inputs. |
| Evidence production/update | Worker reports engine lifecycle evidence. | `isolated-step-execution` performs supported operations producing initial or corrected outputs and renewed evidence. |
| Request and integration | Handoff consumes evidence and offers reevaluation. | `revision-safe-step-handoffs` requests the supply operations and evaluates the resulting revision; a check alone is explicitly insufficient. |
| Correction after completion | Generic runtime-evidence assumption. | `assumption-completed-revision-correction` names the unresolved capability and requires an explicit scope decision if unsupported; it forbids treating a completed step as eligible for unfinished-step replacement. |
| Identity | Revision applicability required. | Review, file-reference and completed-handoff revisions remain distinct identities. |

The new mapping exposes an actual uncertainty instead of asserting that the supported engines provide the operation. This is useful planning output, not proof of runtime feasibility or execution readiness.

### Selected seed from the new mapping

Native `roadmap integration-business-logic-loop2 --materialize revision-safe-step-handoffs -y` materializes only that row. Raw capture `7e1a172`; selected seed SHA-256 `d6b659741d4c73dae933735ae8cf85be3f438a727c557fd2e3dd28f26c97a7bb`.

The seed preserves production by `isolated-step-execution`, requesting/evaluation by the readiness owner, all five prerequisites, distinct identities and the explicit unsupported-correction stop condition. Testing and acceptance require observed supported correction and fresh applicable evidence. All four local References survive. Seed-altitude review finds no material correctness issue or serious omission preventing decomposition; no manual repair is applied.

Native run `2026-10-16T19-35-41+00-00-8ffde6` completes rc 0 in 97.064 seconds, first attempt; original shell session 31565 exits 0.

## Final base-plan check

Native `create revision-safe-step-handoffs --from-existing <selected-seed> --iterate -y` completes without manual repairs. Original shell session 87128 exits 0; native run `2026-10-16T19-37-42+00-00-64bdb4` records `run_end`, outcome `ok`, rc 0 and duration 301.134 seconds. Raw capture: **`9211d7e`**. Raw plan SHA-256: `c35cb2d0f0f1a6b05bf446efe41b59fc9a3884c2261cef28b995d2729b0a52a7`.

| Step | Delivered responsibility |
| --- | --- |
| 1 | Revision-bound readiness checks and required dependencies. |
| 2 | Worker-confirmed completion, persisted progress and exact blockers; completion remains distinct from updated readiness. |
| 3 | Request supported worker production of successor inputs and refreshed evidence for both handoffs. |
| 4 | Request completed-content correction and fresh evidence without reopening the step or consuming replacement. |
| 5 | Authorize successor opening against current revision-applicable readiness. |
| 6 | Integrate owner commands and durable observations; prove input production, successor consumption and correction/reevaluation at both real boundaries. |

The plan body retains execution ownership with `isolated-step-execution`, the contract-proof prerequisite and all five named plan dependencies. Risks and Stop/defer retain `assumption-completed-revision-correction`: unsupported correction requires a scope decision rather than an invented engine capability. All four local References survive. This is raw base output, not a completed bare-plan audit or execution-ready implementation.

No detail files or application-code changes occur. Both original immutable stores and accepted heads remain byte-identical. Verification records at `E/business-logic-loop2-{input-hashes,materialize-verification,mapping-verification,create-verification}.json` retain input/output hashes and boundary checks. Model calls and original shells all complete; no command remains active.


## Interpretation

The mapping, seed and base-plan observations support the existing bounded guidance: assign source-required production/update operations, their consumers and integration, and retain explicit uncertainty about external support. They do not establish complete coverage of the original Integration corpus, optimal decomposition, causal improvement from one phrase or implementation efficiency. Earlier and newer mappings are single samples. No additional prompt change is justified by this result; it supplies evidence for the existing business-operation guidance. The next independent business case is durable handoff-content continuity, tracing emitted content and revision identity through successor consumption. Do not prescribe its storage mechanism.

BACKLOG #496 remains open; no shipment or semantic certification follows from this experiment.
