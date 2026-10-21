# Handoff-content continuity: read-only trace

The existing base plans now require actual successor-input production and consumption, but the exact input package and content-availability responsibility remain unresolved. This trace supplies the pickup for one producer-side test; it does not establish a new tool defect or choose a storage design.

## What the business route requires

A handoff passes the completed step's actual output, at the intended revision, to the next runtime as usable input. A ready flag, an output-event history or retained revision metadata alone does not prove that the content is available to that runtime.

The scope is availability through the ordinary handoff. It does not require retaining worker credentials or live checkouts in the application database, recovering sessions after worker loss, or guaranteeing availability across failures the accepted source excludes.

## Evidence inspected

Frozen upstream artifacts and current mapping: `integration-business-logic-loop2`, version `41c1e9369d922888946f93d9f76b31bd42cc2e798909053372abbfbeec770e49`, in `/private/tmp/roadmap-plan-derivation-comparison-20261016/business-logic-loop2-seed-integration`. These are the accepted inputs from the [corrected-evidence iteration](roadmap-corrected-evidence-iteration.md). The earlier worker plan comes from the initial `f373` candidate mapping, so it is historical comparison output, not a producer plan derived from the newer mapping.

| Evidence | Established responsibility | Remaining limit |
| --- | --- | --- |
| Brief, completed revision's outputs versus next connector inputs; `rule-handoff-check` and `constraint-connector-only-handoff` | Both boundaries must use revision-applicable output and supported connector declarations. | The exact production input package is not settled. |
| `decision-session-store-split`, `03-components.md:160` | Session metadata and attributed output survive in the shared store; live processes, repository checkout and credentials stay inside the worker. | Output-history retention does not demonstrate preservation or delivery of the artifacts a successor needs. Do not silently change this settled boundary. |
| Initial `integration-isolated-sessions` base steps 2, 4 and 5 | Execution preserves checkout artifacts, persists attributed replies/raw output and supplies engine evidence. | These are different responsibilities. None alone proves that an independently executed successor receives the required content. |
| New mapping `runtime-contract-proof` and `assumption-successor-input-production` | Runtime-contract proof establishes actual required input packages, source identities and supported production operations at both boundaries. | It explicitly retains unknown production semantics; a roadmap file alone is not assumed to be sufficient for Construction. |
| New mapping `isolated-step-execution` | Worker performs supported operations producing initial/corrected output and evidence. | Its seed and base plan are not generated in this mapping yet, so producer-side retention/delivery cannot be assessed from them. |
| New `revision-safe-step-handoffs` base steps 3 and 6, raw capture `9211d7e` | Request supported input production and prove actual successor consumption at both boundaries. | This is a stronger business acceptance contract, not a selected content-preservation mechanism or runtime feasibility proof. |

The original retrospective seam study identifies consumed readiness-evidence and report-revision contracts. It is declared review context, not authorization to inject its repaired tables or storage choices into generation inputs.

## Judgment and next bounded test

The current consumer contract requires real consumption rather than readiness alone. The source remains open about the actual package, and the newer producer row has no generated seed/base plan. Therefore the first unresolved point is a combination of source-contract uncertainty and unobserved producer decomposition, not a confirmed loss during materialization or create.

The bounded producer test ran on 2026-10-16; its result is under "Producer seed result" below. A tool change needs a demonstrated first gap, and an unspecified internal mechanism belongs to detail.

Do not regenerate the mapping or full plan set by default. Make another general tool adjustment only if a demonstrated first gap justifies it. An unspecified internal mechanism belongs later; absence of details is not evidence that the base-plan generator fails.

## Producer seed result (2026-10-16)

Native `roadmap integration-business-logic-loop2 --materialize isolated-step-execution -y` ran once in a new independent copy of `E/business-logic-loop2-seed-integration` at `9211d7e` (`E/business-logic-loop3-producer-integration`; stores verified byte-identical, no remote), with the tool at `586255721` and Codex `gpt-6.1-sol`. It exited 0; the tee'd log carries no `run_end` line, so completion rests on the exit code and the created file. Raw seed capture: `ffe10a6`, SHA-256 `6fecb9125c98ba776455da41811552352fbafb35870e52be914639eff613cfc7`. Log: `E/business-logic-loop3-producer-materialize.log`. No base plan was created.

| Seed carries | Seed does not assign |
| --- | --- |
| Operations producing successor inputs at both approved boundaries, completed-revision correction and renewed evidence; "checking supplied artifacts does not satisfy" production; readiness authority stays with `revision-safe-step-handoffs`; `assumption-successor-input-production` and pending `decision-provisional-runtime-native-handoff` kept as risks | Any owner for making the produced output available to the successor runtime through the ordinary handoff. The accepted `isolated-step-execution` row and `assumption-successor-input-production` assign production only, so the seed preserves the mapping faithfully. |

First gap: the accepted source and mapping, not materialization or create. A base plan would restate the same open question, so none is created.

## Integration implementation check (2026-10-16)

Integration (`implement/integration-aidlc-mvp`, `44c22cc`) already owns the availability responsibility, from plans built before this benchmark:

- `engine_worker/session_runtime.py` releases credential-scrubbed declared handoff files before the terminal report; a failed release stops the report.
- `integration/engine_handoff_store.py` and migration `0010_engine_output.sql` keep an immutable whole file set per (session, revision); a differing retry is refused (`handoff_conflict`).
- `read_for_launch` returns only the immediate predecessor's closing revision with a passing handoff check for the next connector. `engine_session_launch.py` refuses launch with `predecessor_handoff_missing` otherwise, and `checkout_store.materialize_handoff` writes the files into the successor checkout.
- This stays inside `decision-session-store-split`: only released content reaches the database.

Still open in Integration: the three drivers refuse to start unless `fixture_only`, so the real CLIs have not yet produced handoff files through this path. That is `assumption-successor-input-production` unproven, not a missing owner.

Disposition: no Integration roadmap feedback item. The plan-tool question stands separately (below).

## Was it identifiable from bare plans?

- **In Integration: no.** `2-isolated-engine-worker.md` contains no "handoff material" wording at `da657b8`, `d3c787a` or `03b4e23` (the bare-stage Gate 1 rounds). The paragraph "Handoff material crosses sessions through Aurora" first appears at `8dcdb8b` ("close Gate 2 findings"), after detail authoring introduced the append-only handoff table (step 3) and the pre-report release (step 4); the Gate 2 audit then flagged only its idempotency. The answer came from detail, not from a bare-plan audit.
- **In this benchmark: as a question, not an answer.** The bare producer seed and the `9211d7e` handoff plan carry the consumer requirement (prove actual successor consumption) and the open assumption, so the gap is visible to a reader who traces producer to consumer. No audit asked who makes the content available, and nothing in the artifacts assigns it. The detail-grounded audit remains the stage that resolves mechanism.

Plan-tool finding (unfiled): when a consumer must receive a producer's actual output, mapping guidance could require an explicit owner for availability to the consumer, without choosing a mechanism. The Integration evidence shows the responsibility is real and gets owned eventually, so this concerns when it is surfaced. Any change needs a sibling-site enumeration and an intent-fit check before editing; it is not a confirmed defect.

## Guidance change and mapping reruns (2026-10-16)

The unfiled finding became a bounded change in `plan_tool/prompts/roadmap-plans.md`, in the implementation checkout. It went through a site sweep (the reasons each other site stays are in the checkout's business-logic-sites scratch file), mutation-verified focused tests, and two `/code-review` rounds at high effort.

| Step | Result |
| --- | --- |
| Interim clause (`eb9ba5cb2`): add the operation that makes actual output available to the consumer | Mapping `99f331f` assigned availability to two plans. The producing worker side stayed unowned, and the `integration-ready-handoffs` seed (`79fbada`) inherited that gap. |
| Whole-chain rewrite (`0d8d7ca95`): trace each source-required transition from origin to consumer, name a plan that owns each hop even when support is unresolved, keep distinct source identities distinct | Full suite 14,637 passed / 67 skipped. Both review rounds flipped at the same lines, so the invariant was stated and patching stopped. |
| Fresh stage-4 mapping on the frozen upstream with `0d8d7ca95` (`E/business-logic-loop5-hoptrace-integration`, version `b121a94c…`, ten rows, one attempt, no violations) | Every hop has a named plan. `isolated-step-execution` owns worker-side output and evidence delivery. `revision-review-and-correction` owns corrected content. `revision-bound-handoffs` owns supplying accepted content to the next runtime. |
| Seeds `isolated-step-execution` and `revision-bound-handoffs` from that mapping (raw capture `c1a0f22`) | The producer seed delivers output and evidence to consumers and stops on unavailable actual output. The consumer seed carries successor delivery and reevaluation. |

Remaining limit: the producer seed does not state that the worker releases handoff content for the successor. That responsibility rests on `revision-backed-repository` and `revision-bound-handoffs` plus the stop condition for unavailable output. Owner decision 2026-10-16: accepted as a known limit at seed altitude, not fixed by another guidance change. The mechanism (what the worker releases, when, and where it is kept) belongs to detail authoring, and the detail-grounded audit is the stage expected to catch an unimplemented successor path. The evidence is one sample; mapping runs vary (nine versus ten rows), so it shows the wording can yield full ownership, not that it reliably does.

Variation check (2026-10-16): two more stage-4 samples on the same frozen upstream and tool (`E/business-logic-loop6-hoptrace-integration`, 10 rows; `E/business-logic-loop7-hoptrace-integration`, 9 rows), scored against a rubric fixed before reading them (`E/hoptrace-validation-rubric.md`). All three mappings name an owner for worker-side output production, corrected-content availability and successor delivery, and keep review, corrected, engine-session and completed-step identities distinct with unresolved support as assumptions. Qualifications: loop6 words successor delivery as connecting outputs to the next connector's declared intake and adds a separate `roadmap-to-construction` plan for plan production; loop7 states worker production but not worker-side delivery, and puts "making the actual completed outputs available to each next runtime" on its handoff plan. No sample leaves a hop unowned. The check shows the wording yields full ownership across three runs with a stable qualification; there is no control arm, so it does not show the wording caused it.

Step-level granularity was out of scope: no base plan or detail was created from these seeds.

## Seed-altitude correctness audit pilot (2026-10-16)

No tool command audits a seed. The repo rule is a session procedure: check the seed's claims against the live code and the source, fix material correctness problems, and raise completeness only for a HIGH or CRITICAL omission. Pilot: two independent read-only audits (fresh Sonnet agents) of the loop-5 seeds `isolated-step-execution` and `revision-bound-handoffs` against accepted version `b121a94c…` and the clone as the live repository, with fidelity to the mapping row, dropped obligations, repository claims, cited ids and contradictions as the checks.

| Result | Detail |
| --- | --- |
| Yield | No CRITICAL, HIGH or MEDIUM finding in either seed. Four LOW, all confirmed against the sources: a non-goal borrowed from `revision-review-and-correction`; "replacement lineage distinct from step-run identity" not stated; wording of `rule-completion-vs-transition` filed under `decision-engine-session-scope`; a process line ("use existing roadmap review") that comes from the seed prompt, not the row. |
| Repository claims | "No implemented application API, session layer, worker or transition service" verified true in the clone. |
| Sensitivity | A scratch copy of `revision-bound-handoffs` with three planted defects, audited blind with the same brief: a false repository claim (CRITICAL), an invented infrastructure-provisioning assignment (HIGH), and a nonexistent cited decision id (HIGH). All three were caught with correct category and evidence. The audit also re-raised the existing `decision-engine-session-scope` attribution, at MEDIUM this time against LOW before: stable finding, unstable severity. |

Limits: the planted defects were blatant, so the check shows the audit sees fabricated claims, invented assignments and bad ids, not subtle weakening of an obligation. Two seeds from one mapping is a small sample. The audit did not flag the accepted producer-seed limit, as intended, because the roadmap does not require it.

Disposition: keep the audit as a session procedure after `--materialize`; no tool verb. A verb would need a named observable and an enumerated list of what it may not check before any backlog entry.

## Checkpoint

The read-only trace predates the producer-seed run and the loop-4 and loop-5 mapping and seed runs. No detail authoring or application work occurs, and no process remains active. The [testing handoff](../../handoffs/2026-10-16-roadmap-business-logic-base-plan-loop.md) records the pickup. Production code is `0d8d7ca95` in the implementation checkout.
