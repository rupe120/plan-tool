# Roadmap-to-plan handoff

*Part of the plan-tool developer docs. Start at [Contributing](../../CONTRIBUTING.md).*

Use a short, source-linked composition record before deriving a plan when an
accepted outcome spans a harness, methodology tool and application adapter.
For the selected Integration owner-answer journey, existing seed and plan prose can
carry that record. This investigation recommends `use-existing` for `create`,
`detail` and `completeness-audit`; it does not select a new tool input or claim
that project context alone contains the necessary evidence.

## Ownership and authority

### Selected source and accepted outcome

The inspected Integration checkout is `<integration-consumer-root>` at
`25d6517dd47949040b94904669128a5f0ba9aa06`. The layer map, probe record and
collaborative proposal are clean at that revision. The earlier
[Integration evidence summary](../evidence/integration-roadmap-to-plan-handoff.md) retains
its `2cb1e7283f9d23363b0ff185d223eecf76fc5036` observation provenance; it is
supporting evidence, not the accepted-content selector.

The Git revision identifies the code and cited documents. The accepted roadmap
is a separate local immutable store: its selector and content-addressed version,
not Git HEAD alone, identify the accepted content observed here.

A read-only call to
[`load_accepted_version`](../../plan_tool/roadmap_versions.py) with the Integration
`docs/implementation-plans` directory and slug `integration-aidlc-mvp` resolves version
`c7743c56d7b3da8450d5c4c060dc4a407414fbb77e3967813000a4538f9a4987`.
Within that version, `01-domain.md:rule-answer-engine-acceptance` requires
owning-engine confirmation before Integration treats an answer as accepted; otherwise
Integration shows uncertainty. Sending an answer or selecting a suggestion does not
approve a candidate or advance the workflow. The `04-roadmap.md` plan row
`chat-output-streaming` carries that acceptance obligation through the existing
`isolated-engine-worker` dependency.

Those immutable rows supply the selected approved outcome. The proposal's
transport composition and observed code supply evidence about delivering it;
they cannot change the accepted rows. The full outcome coverage remains in
that version's `04-roadmap.md` and the layer map's “Outcome coverage pointer”:
three runtimes, both adjacent handoffs and revision review remain outside this
one-answer trace. Mid-run feedback is a separately recorded departure in the
Integration proposal and BACKLOG #12, not silently satisfied by a transactional answer.

### Selected owner-answer journey

| Move | Responsible layer | Contract and evidence |
| --- | --- | --- |
| Receive the owner's answer to the current question | Integration application | `integration/chat_input.py:ChatInput.submit` checks the current question before forwarding; stale, absent or mismatched questions are refused. |
| Carry the answer in a resumed invocation | Harness transport in Integration's worker | Collaborative decisions O03/O09 separate carriage from methodology acceptance. The composition proposal requires resuming the session that asked the question. |
| Establish acceptance | AI-DLC 2.9.0 methodology | Probe run E records `HUMAN_TURN` and `QUESTION_ANSWERED`; harness turn completion alone proves neither acceptance nor approval. |
| Attribute the result to the answer | Integration adapter/evidence reader | Compare native ledger positions before and after the invocation and bind the result to the current question, message and session. A scan of old ledger rows cannot establish acceptance of this answer. |
| Present the result | Existing driver-event consumer | Emit the native-confirmed `answer_acceptance` outcome; preserve uncertainty when confirmation cannot be established. Message receipt is a separate event. |

The probe also accepts an answer from a different Codex session. That is a
provider limitation, not permission for Integration to accept a foreign session.
The proposal's “New obligations” requires resuming the asking session and
retaining the current-question guard. This record does not reopen that policy.

## Critical contracts and evidence

### Existing-interface extension and bounded increment

At the inspected Integration revision,
`engine_worker/runtime_contract.py:RuntimeDriver.deliver_chat` takes a
`ChatCommand` with `message_id`, `kind`, `text`, `question_id` and reference ids.
An answer requires a question id. Its `DriverEvent` already represents
`chat_receipt` and `answer_acceptance` separately and carries
`in_reply_to_message_id`, `question_id` and `acceptance` (`accepted`/`rejected`).
`integration/chat_input.py` validates the returned receipt's message and session ids;
that receipt establishes delivery, not owning-engine acceptance.

The selected extension is to the existing driver's behavior: a shared harness
transport carries the `ChatCommand`, and an AI-DLC evidence reader maps fresh
native acceptance evidence into the existing `DriverEvent` contract. This is
an extension to an existing operation and event vocabulary, not a missing
CLI name or proof that a new schema is needed. The producer is the
transport/evidence-reader adapter; the consumer is Integration's existing owner-input
and output path. Methodology evidence remains the authority for acceptance.
Current consumer shapes constrain the later implementation; this record does
not choose a new field, event encoding or migration.

A bounded proposed increment implements one AI-DLC current-question answer
through that seam with same-session resume, before/after ledger attribution
and retained stale-question refusal. It is part of the Integration successor scope
selected by O14, not work implemented here. The source plan's full three-runtime
and handoff obligations remain intact. Existing fixture tests
`test_answer_with_the_current_question_goes_through_answer_with_the_same_guard_and_states`
and `test_stale_absent_or_mismatched_question_is_refused_and_never_forwarded_or_sent_as_chat`
in `tests/unit/test_chat_input.py`, plus the question API tests, pin consumer
behavior. They do not verify a deployed provider. No Integration test or live probe
is run by this investigation.

### Evidence strength and remaining provider question

| Evidence | What it establishes | What remains unknown |
| --- | --- | --- |
| Accepted version and `rule-answer-engine-acceptance` | The obligation and its approval boundary | Whether a particular adapter delivers it |
| Layer map and current runtime contract | Ownership assignments and existing consumer fields | Unimplemented transactional behavior |
| AI-DLC 2.9.0 / Codex 0.162.1 probe runs E/F | A resumed answer can produce native acceptance; AI-DLC also permits foreign-session answers | Deployed worker behavior, an in-workflow refusal, Claude Code behavior and terminal completion |
| Existing consumer tests | Current-question refusal and receipt/session separation are asserted by fixtures | Provider-side acceptance and deployed integration |
| Collaborative O03/O09 and next-plan composition | Accepted pilot direction and same-session integration requirement | They do not promote a roadmap change or prove runtime behavior |

The remaining provider question for this journey is: at the selected worker
pins, how does an **in-workflow answer refusal** appear and remain distinguishable
from a successful answer when delivered through the deployed harness? The probe
exercises a pre-intent command refusal, but explicitly does not exercise an
in-workflow refusal. The Integration runtime integration owner must obtain that evidence
before claiming the refusal path delivered. It does not prevent the tool-side
input decision below. No new probe is authorized by this record.

Owner product decisions remain with the owner. O07 excludes app-server mode,
O09 selects transactional invocations, O11 withdraws queueing/cancellation for
now, and O14–O16 select the successor, pin direction and feedback route. Read
those explicit decisions alongside earlier proposal prose. A pending departure
or feedback id never replaces accepted-head authority; #485 owns that question.

## Minimum handoff and existing input delivery

The minimum record has the two sections above: ownership/authority and critical
contracts/evidence, with pointers to full outcomes and remaining questions.
For this journey it must identify the accepted slug/version/row, selected outcome,
source revision, provider/consumer boundary and fields, evidence limits,
settled session requirement and bounded increment. A project profile's intent,
non-goals and decisions cannot stand in for those source facts.

Use source references and explicit evidence prose in the seed and resulting
plan. Keep a compact provenance and responsibility statement in the plan
References block itself: accepted slug/version/row, Integration source commit, the
methodology acceptance versus harness-carriage distinction, and the linked
composition record. A bare path alone does not deliver that statement. Paths identify evidence for the driving session to read; they do not
snapshot source contents, prove agreement or enforce revision admission.

| Consumer | Existing delivery route | Need decision and limit |
| --- | --- | --- |
| `create` | Put the selected version/row, source revision and compact composition record into `--from-existing` seed Architecture, with exact source pointers in References. `create.py:propose_steps_from_claude` supplies the selected description to `_render_from_prompt`; file-backed preparation carries canonical body sections into the plan. | `use-existing`: the selected evidence can be explicit seed prose. Inspect the published plan: this investigation's normalized creation replaced local references with generic web references, so the session restores and verifies them before auditing. This is not automatic provenance preservation. |
| `detail` | The plan's Architecture holds the bounded evidence/authority contract; `detail.py:render_detail_prompt` receives the owning plan, scope fence and plan References block lifted from the plan body. | `use-existing`: retain the exact accepted version/row and responsibility statement in References for detail authors; Architecture alone is insufficient for this prompt route. Linked source bodies are not automatically admitted or frozen; the author verifies the selected revision. |
| `completeness-audit` | `review.py:render_plan_audit_prompt` embeds the plan body and grade-selected detail bundle; `_collect_plan_body` includes the plan's evidence prose and References. Seed scope-contract extraction carries the fence, not every external source body. | `use-existing`: inspectable version/row and evidence statements live in the audited bundle. The driving session checks cited sources. Report silence does not verify them, and the audit does not automatically resolve the accepted roadmap or compare sibling plans. |

`project_profile.py:render_project_profile_context` explicitly calls confirmed
project context scope guidance, not repository evidence. The recommendation
therefore depends on authoring and reviewing the small record through existing
prose/reference routes, not on pretending the profile delivers native evidence.
The code paths above establish that these inputs can be presented; they do not
establish that a model reads them correctly or that this process saves effort.

Projects without selected context keep existing prompt and status behavior.
No persisted input, revision-admission policy, automatic refresh, new schema or
additional consumer is selected. If later work needs machine-bound shared-source
admission rather than session-verified references, that is a demonstrated new
contract to settle before an implementation seed, not implied by this result.

## Follow-on dispositions and boundaries

| Follow-on | Recommendation | Evidence and prerequisites |
| --- | --- | --- |
| #493 shared context | `no-action` for this selected journey | Existing seed/plan prose and References can deliver the minimum record to the three consumers. Source verification stays session-owned. No additional machine-bound shared input requirement is established; this does not claim that existing delivery guarantees provenance or semantic use. Retain the gated entry for a separately demonstrated delivery need. |
| #462 cross-plan advisory | Conditional `build` | Coordinated shared-contract findings remain distinct from this layer-premise case. Preserve #462's own evidence gate; this study does not settle whether its prior one-sided detection/churn evidence meets that gate. A conditional recommendation neither promotes #462 nor makes #492 wait for it. |
| #494 prerequisite status | `no-action` for this selected journey | `cli/inspect.py:_print_status` already shows progress/dependencies, stale-detail advice and pending concept decisions. The remaining provider question can be cited in the record/plan; this study does not show a distinct requirement for a new status projection or select its input contract. Keep its entry gated. |

#490 retains finding-disposition ownership; #485 retains departure authority;
#262 retains the bare/detail advisory; #403 retains installation-readiness work.
No follow-on is implemented, closed or promoted by this document. #492's stage
arc stays the routing authority. This is a bounded use-existing result, not a
certification of decomposition quality, full outcome coverage or execution readiness.

## References

Integration code/document paths below are relative to the inspected checkout at the
source commit above. Roadmap-store paths identify the separately observed local
accepted store and require that store to resolve; Git checkout alone is not
claimed to reproduce it.

- `docs/implementation-plans/roadmaps/integration-aidlc-mvp/.roadmap-versions/accepted-head.json` and `.roadmap-versions/c7743c56d7b3da8450d5c4c060dc4a407414fbb77e3967813000a4538f9a4987/{01-domain,04-roadmap}.md` — immutable accepted source; resolve through the accepted-head reader.
- `docs/engine-sessions/signal-layer-map.md` — ownership map and full-outcome pointer.
- `docs/engine-sessions/2026-10-15-aidlc-probe-record.md`, runs E/F, question 3 and “Not shown by this probe” — provider evidence and limits.
- `docs/proposals/2026-10-15-roadmap-to-plan-collaborative-approach.md`, O03/O07/O09/O11/O14–O16 — owner decisions, distinct from accepted artifacts.
- `docs/proposals/2026-10-15-live-runtime-next-plan-composition.md`, “New obligations” and successor scope — settled same-session requirement and proposed increment.
- `engine_worker/runtime_contract.py:ChatCommand`, `DriverEvent`, `RuntimeDriver`; `integration/chat_input.py:ChatInput` — existing seam and guards.
- [BACKLOG #492 and its staged arc](../../BACKLOG.md)
- [Bounded Integration evidence summary](../evidence/integration-roadmap-to-plan-handoff.md)
- [Roadmap authority contract](../../ROADMAP_FORMAT.md)
- [Create](../../plan_tool/create.py), [detail](../../plan_tool/detail.py), [audit](../../plan_tool/review.py), [project context](../../plan_tool/project_profile.py) and [status](../../plan_tool/cli/inspect.py) — inspected consumer paths.
