> **Archived:** this completed plan moved here on 2026-08-20 after all steps reached `done`.

---
title: Roadmap Feedback Revision Bounded Operations
intent: A feedback-driven roadmap stage revision returns only a closed, typed JSON
  operation set, and deterministic code applies those operations to the canonical
  artifact before the existing stage gates judge the result. The model does not re-emit
  untouched artifact content or the authoring contract, so a large artifact's untouched
  rows cannot drift during a revision.
status: completed
priority: medium
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-feedback-revision-bounded-operations.md
steps:
- id: 1
  title: Define closed stage-envelope operations, explicit add-row types, their local
    compatibility profile, isolated row-prose amendments, and plan-ordering companions
  intent: Bind every stage-envelope operation to its feedback target, explicit row
    collection where it adds a row, and deterministic row-owned prose effect, while
    preserving the selector-bound local profile and the required ordering relation
    for plan-row additions and removals.
  files:
  - plan_tool/roadmap_artifacts.py
  - plan_tool/data_contract.py
  - plan_tool/project_config.py
  - plan_tool/roadmap_revision.py
  - tests/test_roadmap_artifacts.py
  - tests/test_data_contract.py
  - tests/test_project_config.py
  - tests/test_roadmap_revision.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-feedback-revision-bounded-operations/01-define-closed-stage-envelope-operations.md
  status: done
- id: 2
  title: Build bounded stage-envelope feedback context from the authority matrix,
    selected isolated row-prose spans, declared relations, and plan ordering
  intent: Keep prompt size tied to authorized changes while supplying the row and
    relation facts and exact row-owned body spans each permitted operation needs.
  files:
  - plan_tool/roadmap_revision.py
  - plan_tool/roadmap_relations.py
  - tests/test_roadmap_gates.py
  - tests/test_roadmap_revision.py
  - tests/test_roadmap_relations.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Defines the operation targets, reviewer authority, and combinations that determine
      which context each operation needs.
  detail: docs/implementation-plans/plan-details/roadmap-feedback-revision-bounded-operations/02-build-bounded-stage-envelope-feedback.md
  status: done
- id: 3
  title: Atomically apply authorized row, prose, and ordering operations; preserve
    the local profile and unselected prose and content; and retain removal continuity
    evidence
  intent: Make code own only feedback-authorized canonical changes while retaining
    the existing local revision path as a compatible subset.
  files:
  - plan_tool/roadmap_artifacts.py
  - plan_tool/roadmap_gates.py
  - plan_tool/roadmap_revision_patch.py
  - tests/test_roadmap_artifacts.py
  - tests/test_roadmap_gates.py
  - tests/test_roadmap_revision_patch.py
  - tests/test_roadmap_revision_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: Supplies the validated operation records and authorization rules the merger
      enforces.
    2: Supplies the context-issued row, prose, relation, and ordering authority the
      merger must re-check before it creates a candidate.
  detail: docs/implementation-plans/plan-details/roadmap-feedback-revision-bounded-operations/03-atomically-apply-authorized-row-prose.md
  status: done
- id: 4
  title: Enroll a trusted canonical baseline and publish it atomically with every
    semantic roadmap change and its dependent seed state
  intent: Give the normal and local revision routes one trusted comparison value that
    distinguishes presentation-only source drift from an unauthorized construct or
    prose change, while never leaving a bounded feedback revision paired with seeds
    that still claim its earlier roadmap semantics are current.
  files:
  - plan_tool/roadmap.py
  - plan_tool/cli/roadmap_cmd.py
  - docs/cli/roadmap.md
  - plan_tool/roadmap_revision_publish.py
  - plan_tool/roadmap_revision_run.py
  - plan_tool/roadmap_seed_state.py
  - plan_tool/roadmap_source_identity.py
  - plan_tool/roadmap_structural_revision_run.py
  - tests/test_roadmap.py
  - tests/cli/test_cli_reference.py
  - tests/cli/test_roadmap_cmd.py
  - tests/test_roadmap_revision_publish.py
  - tests/test_roadmap_revision_run.py
  - tests/test_roadmap_seed_state.py
  - tests/test_roadmap_source_identity.py
  - tests/test_roadmap_structural_revision_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: Supplies the canonical merge result whose non-feedback projection the writer
      publishes as the next trusted baseline.
  detail: docs/implementation-plans/plan-details/roadmap-feedback-revision-bounded-operations/04-enroll-trusted-canonical-baseline.md
  status: done
- id: 5
  title: Route every re-entered stage by active feedback, refuse unauthorized non-feedback
    changes, and re-gate feedback-free stages without writes
  intent: Prevent large revisions from re-emitting untouched content while making
    baseline-checked source admission, bounded merges, no-op re-gates, backend calls,
    artifact writes, seed invalidation, and the feedback-free terminal outcome follow
    one observable precedence rule.
  files:
  - plan_tool/roadmap.py
  - plan_tool/roadmap_revision_publish.py
  - plan_tool/roadmap_revision_run.py
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/prompts/roadmap-revision.md
  - tests/test_roadmap.py
  - tests/test_roadmap_revision_publish.py
  - tests/test_roadmap_revision_run.py
  - tests/cli/test_roadmap_cmd.py
  - TESTING.md
  creates:
  - plan_tool/prompts/roadmap-stage-feedback-revision.md
  - tests/fixtures/roadmap/integration-scale-domain.md
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  - 4
  depends_on_notes:
    2: Supplies the bounded feedback and relation payload rendered into the new prompt.
    3: Supplies the deterministic merge candidate that the existing stage gates judge.
    4: Supplies the trusted baseline and canonical working artifact the routes must
      use before selecting feedback work or re-gating a no-op.
  detail: docs/implementation-plans/plan-details/roadmap-feedback-revision-bounded-operations/05-route-every-re-entered-stage-active.md
  status: done
- id: 6
  title: Document bounded stage feedback and its feedback-free re-gate boundary across
    roadmap references
  intent: Keep operator guidance, architecture boundaries, examples, CLI reference,
    and run-log semantics aligned with the shipped per-stage selection rule.
  files:
  - ROADMAP_FORMAT.md
  - DATA_CONTRACT.md
  - README.md
  - RUNBOOK.md
  - CAPABILITIES.md
  - docs/ARCHITECTURE.md
  - docs/ROADMAP_WALKTHROUGH.md
  - docs/ROADMAP_DEMO_ORCHESTRATION.md
  - docs/cli/roadmap.md
  - tests/test_data_contract.py
  - tests/test_roadmap_format.py
  complexity: high
  change_type: non-code
  depends_on:
  - 5
  depends_on_notes:
    5: Settles the prompt, baseline admission, per-stage selection, no-op, overwrite,
      invalidation, failure, and CLI behavior the references describe.
  detail: docs/implementation-plans/plan-details/roadmap-feedback-revision-bounded-operations/06-document-bounded-stage-feedback-its.md
  status: done
- id: 7
  title: 'Close #297 and its whole-artifact revision bug record, mark the roadmap
    arc gate shipped, and re-scope the remaining source-identity work'
  intent: Stop presenting the shipped failure as active work while preserving a distinct
    later plan for receipt and evidence freshness beyond this route's baseline.
  files:
  - BACKLOG.md
  - BUG_BACKLOG.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md
  - docs/implementation-plans/2-roadmap-canonical-source-identity.md
  complexity: low
  change_type: non-code
  depends_on:
  - 5
  - 6
  depends_on_notes:
    5: 'Provides the verified bounded stage-revision and source-admission behavior
      that closes #297.'
    6: Ensures the durable contract documentation is current before the tracking records
      and remaining source-identity scope are updated.
  detail: docs/implementation-plans/plan-details/roadmap-feedback-revision-bounded-operations/07-close-297-its-whole-artifact-revision.md
  status: done
---
# Roadmap Feedback Revision Bounded Operations

## Overview

`roadmap.py:_render_revision_prompt` currently gives a model the predecessor
artifact, active feedback, and the full authoring prompt, then asks it to
re-emit the entire artifact. A 2026-08-12 first-use run on the `integration`
roadmap exposed the design at real artifact scale: a stage-1 revision made a
roughly 70 KB prompt and exhausted attempts through an invocation timeout, a
YAML parse failure, and a gate rejection caused by an altered
`awaiting-review` response.

Two sibling routes already use the intended shape. `--revise-feedback`
parses a closed JSON operation envelope and
`roadmap_revision_patch.merge_feedback_revision` merges it into one
canonical artifact. Structural revision similarly constrains model output to
typed operations and applies them in code. This effort generalizes that
bounded, code-owned pattern to the ordinary feedback route rather than adding
more defenses around whole-artifact regeneration.

## Problem statement

The current route makes output fidelity proportional to the size of the
artifact it asks the model to reproduce. Its deterministic gates correctly
refuse parse errors and changes to retained review content, but they do so
only after a long model call has reconstructed content that the feedback did
not authorize changing. Retrying repeats the same oversized reproduction
task.

The local feedback route cannot substitute directly: it selects one open
row, permits one presentation replacement, and requires one response. A
stage-level revision must carry the broader set of reviewer-authorized
changes the existing stage gates accept. The shared typed merge contract is
therefore widened compatibly instead of creating a second, stage-only patch
language.

## Architecture

The revision response remains one ordered, closed JSON envelope. Each
operation has a typed discriminator, a narrowly defined target, and only the
values needed for that operation. An `add-row` also carries an explicit typed
row-collection discriminator; code never infers a collection from its
payload. Every material row operation has its coupled row-prose amendment.
Code validates the complete envelope against the current predecessor and
active reviewer feedback, applies the approved operations atomically to the
canonical parsed artifact, renders the candidate, and runs the existing three
revision gates — `check_design_row_continuity`, `check_feedback_integrity`,
and `check_settled_decisions` — on that result. The completed-revision
contract remains the gates' current contract; only the model's input and reply
format change.

The following matrix governs only the multi-feedback **stage envelope**. Every
stage material operation names one active feedback id; no operation may touch
an id, collection, row, or review state the matrix does not admit. Detail fixes
the concrete JSON fields and row-type validation, but it cannot widen this
authority.

| Operation | Eligible feedback target | Deterministic effect and rejection boundary |
| --- | --- | --- |
| `respond-feedback` | Every `open` row: `artifact`, a live `row`, or a `row` id retained only by a removal record. | Carries one non-blank response and moves only that feedback row to `awaiting-review`. It changes no design row. Exactly one is required for every active row; `deferred`, reopening, and any future `closed` move remain reviewer-only. |
| `add-row` | An `artifact` target. | Carries an explicit `row_type` collection discriminator and one matching typed row with a new valid id; code rejects an omitted, unknown, or payload-mismatched type rather than inferring it. The admitted collections are `entities`, `business_rules`, `workflows`, and `decisions` on `DomainArtifact`; `dispositions`, `constraints`, and `decisions` on `ConstraintsArtifact`; `system_patterns`, `component_patterns`, `components`, `decisions`, and `stores` on `ComponentsArtifact`; and `plans`, `assumptions`, and `decisions` on `PlansArtifact`. `hosting` is not admitted: its three fixed facets already have exactly one row each, so feedback revises an existing facet rather than adds or removes one. An addition appends its required isolated prose fragment naming that id, except an identity-only `stores` addition has no prose field; in both cases it names the authorizing feedback. Every relationship-bearing field in every added row may name only a live predecessor id from the frozen context inventory — never an id introduced by another operation in the same envelope. Only a `plans` addition also appends its one matching `ordering` entry, whose `depends_on` and `assumption_targets` follow that same predecessor-only rule. A row-targeted request, another review row, or a removal record cannot authorize an addition. |
| `edit-row` | A `row` target that resolves to one live design row. | Replaces values only on that same typed row in the same collection while retaining its id. A prose-inventory row replaces only its supplied preflight, row-owned prose span: the span must contain no other row's prose, and the replacement may change no unselected row's wording. Identity-only `hosting` and `stores` rows carry no prose span, and code rejects one. A hosting edit preserves its id and facet, so it can revise only that fixed facet's values. It preserves every existing relation-bearing field: reference `FieldRow.entity_id`; business-rule and workflow entity ids; constraint anchors; component entity, pattern, constraint, and Store ids; plan component ids; ordering links; assumption consumers; and decision anchors. This vocabulary does not rewrite an existing relation, its membership, or its order regardless of decision state. An artifact target or a target resolved only by a removal record may receive a response but cannot edit a row. |
| `remove-row-with-record` | A `row` target that resolves to one live design row other than a fixed `hosting` facet. | Removes only that row, replaces or removes only its supplied preflight, row-owned prose span when it has one, and creates the current-format removal record with its rationale and citation to the authorizing feedback. The span must contain no other row's prose. An identity-only `stores` removal carries no prose span. A removal rejects before a candidate when a surviving current-stage or upstream declared relation names that row, including a component's `store_ids`; selected context intentionally excludes downstream artifacts, whose later re-gate detects any resulting break. For a plan row, it also removes that row's one ordering entry only after that general check passes. It cannot remove an added row, a fixed hosting facet, alter a carried record, or introduce #242's future snapshot or decision-reference fields. |

Material operations may not repeat a live-row target, operate on a row newly
added in the same envelope, or target a carried removal. They run in envelope
order before the required feedback responses, which then run in the predecessor
feedback order. An invalid target, feedback id, duplicate target, missing
response, or disallowed combination rejects the complete envelope without a
partial merge. This is a closed vocabulary, not an extensible operation
registry; the current presentation replacement and feedback-response pair
remain the backward-compatible subset. No standalone ordering operation,
reordering of an existing plan, or retargeting of an existing plan-internal
relation is admitted.

The stage envelope has four fixed v1 hard limits: at most one material
operation for each active feedback item, at most 32 active feedback items, at
most 32 KiB of UTF-8 JSON for the complete reply, and at most 4 KiB of UTF-8
text for each prose amendment. The context builder rejects an over-limit active
set before a backend call. The response reader measures reply and amendment
bytes before binding or merging, then rejects any excess as `invalid`, with the
feedback id where one applies, the measured value, the limit, and a request to
split the feedback. A limit violation is neither partially applied nor sent
through the model correction or retry path. The prompt renders these same
limits from the typed response contract so its instructions cannot drift from
validation. The artifact renderer's feedback-structure comments repeat this
concise limit and split-feedback guidance for reviewers who create or edit a
feedback row.

`.plan-tool/config.json` may set stricter project-only numeric limits under
`roadmap_feedback.stage_limits`: `max_active_feedback_items`,
`max_response_bytes`, and `max_prose_amendment_bytes`. Each is a positive JSON
integer no greater than its 32-item, 32 KiB, or 4 KiB hard ceiling; the prose
limit must not exceed the response limit. The material-operation cardinality is
a semantic rule and is not configurable. The resolver reads this block once at
command start, ignores user-level configuration, and passes one immutable
effective-limit value to context construction, prompt rendering, and reply
validation. An absent block uses the hard limits. A malformed, unknown, or
out-of-range project block fails command preflight before any backend call or
write instead of silently broadening a project policy. The artifact comments
state the non-bypassable ceilings and tell reviewers that their project may use
stricter limits; they do not make canonical rendering depend on local config.
`plan_tool/data_contract.py:json_object_contracts` registers this project-only
object and its three leaves so generated contract documentation and its drift
test cover the same schema as the resolver.

The prose amendment is coupled to its material row operation, not a general
body-edit operation. Context supplies exact, bounded, row-owned preflight spans
only for prose-inventory rows; `hosting` and `stores` are identity-only and have
no body-prose surface. A row-owned span contains that one row's prose and no
other row's prose. An edit or removal names that source span and its
replacement; code rejects an unmatched, ambiguous, overlapping, shared, or
cross-target span, and verifies that every unselected row's prose remains
byte-for-byte unchanged. An addition appends one isolated fragment that names
its new prose-inventory row id. The model neither receives nor returns any
other body text, and all body bytes outside its selected row-owned amendment
remain unchanged. Detail sets the concrete JSON fields without permitting a
whole-body replacement.

The existing `--revise-feedback` route is a separate selector-bound profile
over the shared merge leaf: it selects one open feedback row, may replace that
selected row's presentation, and requires only that selected row's response.
Its replacement has no feedback id and another open row may remain unchanged.
Stage-envelope rules never reinterpret that profile as a multi-feedback
envelope. Structural revision likewise retains its current selection and
publication contract. Backward-compatible callers may continue using the
presentation-only local profile of the shared merge contract.
The vocabulary does not introduce #242's retention semantics: any future
`closed` feedback state, retained closed feedback, removal snapshot policy,
or decision-reference policy remains #242 work after this merge layer ships.

Every semantic artifact publisher — ordinary stage authoring or revision,
selector-bound local revision, and structural revision — creates or updates a
writer-owned baseline for that stage. The baseline stores the canonical parsed
projection
of every construct, removal, ordering entry, and body-prose value **except**
`feedback`, plus a digest of that projection, the roadmap slug, stage key, and
format version. It is a trusted canonical copy, not a copy of raw artifact
bytes: comments and schema-unrecognized fields are absent, while every
semantic construct and its prose remain available for a precise difference
message. The hash is a quick equality check; retained baseline content lets a
refusal name the changed field, added or removed row, or altered body span.

Before any baseline exists, an operator must explicitly run
`plan-tool roadmap <slug> --enroll-baselines`. This one-time enrollment checks
an exact-canonical, contiguous prefix beginning at stage 1, records a baseline
for each member, makes no model call or artifact rewrite, and logs that the
operator established the trust boundary. Enrollment of a Plans artifact also
marks every existing derived seed invalidated: trusting current roadmap content
does not prove an older seed was derived from it. It refuses a gap, a
noncanonical artifact, a later-stage-only suffix, or a fully enrolled prefix.
Exact canonicality proves only that the current text is renderable; it cannot
prove who last changed it. The enrollment action therefore deliberately trusts
the content present at that moment. A direct edit before enrollment is not
retroactively detectable; every direct semantic edit after enrollment is.
Normal, local, and structural writers never initialize a missing baseline from
the source they are about to consume.

Enrollment is one recoverable bootstrap generation for the whole requested
prefix, not one generation per stage. Its recorded old and new sets contain
every prefix baseline and, when the prefix reaches Plans, the invalidated
seed-state sidecar. Under the writer guard, recover this pending set before
testing whether a stage is already enrolled: a partially written prefix restores
the known old set, and a fully written new prefix completes and clears its
record. A retry therefore sees either no enrolled prefix or one fully enrolled
prefix, never an accepted prefix followed by an impossible suffix. Enrollment
still never rewrites an artifact itself.

Every semantic publisher updates a semantic artifact change and its next
baseline as one recoverable publication set under the existing roadmap writer
guard. Only a brand-new stage with no predecessor, baseline, or derived-seed
state publishes an artifact/baseline pair without seed invalidation. A missing
artifact paired with a baseline or derived-seed sidecar is an invalid direct
deletion, not fresh authoring. An
accepted bounded feedback merge at **any** stage also includes the next
invalidated seed-state sidecar in its recorded generation before any member
becomes current: a Domain, Constraints, or Components merge can stale seeds
derived from the later Plans artifact just as a Plans merge can. This preserves
the current conservative behavior of invalidating all known derived seeds after
a feedback-bearing merge. A feedback-free no-op changes neither the artifact
nor its seed state. A reader never silently repairs a pending or mismatched
set. A failed publication either recovers a fully recorded old or new set on
the next writer entry, or refuses an unknown mixed state without replacing any
member. Recovery must never leave a new artifact or baseline from a bounded
feedback merge paired with a seed-state sidecar that still marks a seed derived
from that roadmap current. A feedback-only publication outside Plans need not
replace an unchanged non-feedback projection, but its reader still compares the
projection to the current trusted baseline and invalidates the affected seed
state as part of its bounded merge. This is the bounded revision route's
source-admission contract; receipt, impact, and structural-evidence freshness
remain later `roadmap-canonical-source-identity` scope.

Before a stage-envelope operation, local selector authorization, upstream
gate, or feedback-free re-gate, the route parses the current artifact and
compares its non-feedback projection to that baseline. On `--from-stage N`, it
does this for every lower existing artifact before it lets that artifact enter
the upstream gate envelope. Feedback rows are excluded because reviewer-written
feedback is the normal input path — the separate raw-YAML-scalar corruption
risk is tracked in `BUG_BACKLOG.md`, not fixed by this check. Equal projections
admit the source: the current parsed artifact, rendered canonically in memory,
becomes the working artifact. A comment, formatting change, or schema-
unrecognized field therefore never changes a construct; the route logs what
canonicalization does not retain and uses canonical text downstream without
writing it back merely for formatting.

Admission retains an immutable baseline binding beside every file-backed
working artifact. The normal route rechecks every such selected predecessor or
upstream artifact immediately before every gate or route use, including a
correction/retry prompt and selected feedback-free re-gate, and immediately
before a candidate publishes. A semantic mismatch at either point is
`OUTCOME_STAGE_INVALID` with no write; a prior in-memory merge from this run
may remain upstream only after its own successful guarded publication. The
advisory writer guard is not treated as proof that a reviewer did not edit a
file between admission and use.

Feedback has a separate, non-baseline snapshot because reviewer feedback is
normal mutable input. After source admission and row preflight, both bounded
routes freeze the selected artifact's ordered canonical feedback projection.
Before a correction/retry prompt and immediately before publishing, they reread
and compare that projection; an added, changed, reopened, reordered, or removed
feedback row rejects without a write, retry, correction request, baseline
replacement, or seed-state change. The permitted candidate responses are
compared only after this source snapshot check, so a reviewer change observed by
the protocol is never lost.

Artifact publication is atomic replacement, not an optimistic compare-and-swap
against an editor that ignores `roadmap_writer_guard`. An uncoordinated raw file
edit that lands after the final check and during replacement is unsupported; the
supported way to change an artifact is feedback, and a future hand-edit review
process will use its own coordinated input boundary. The route guarantees a
fail-closed refusal for changes it observes, not an impossible preservation
guarantee for that exact uncoordinated write race.

An unequal projection is an unauthorized direct construct or prose change,
including an add, edit, delete, or rename outside `feedback`. The normal stage
records `OUTCOME_STAGE_INVALID` with a message that identifies the affected
row, field, or prose span when the stored baseline permits it, then makes no
backend call, write, retry, seed action, or change to `loaded`. The local
route returns its equivalent `semantic-source-drift` preflight refusal before
it invokes or publishes. In particular, deleting or renaming a row an open
feedback item targets is invalid rather than a reason to retry the model. No
direct construct change becomes an accepted artifact merely because ordinary
gates would pass.

The selector-bound `--revise-feedback` route uses this same baseline-checked
preflight before it checks its selected row, and baseline-admits every earlier
artifact that its publication gate needs before it invokes the backend. It
passes that fixed canonical upstream map to the publisher; the publisher does
not reread raw upstream files. Before every retry/correction prompt and before
the atomic write, it checks that each admitted source and its selected feedback
snapshot still match, so an observed later hand edit fails without a write. Both
entry paths therefore use the same
canonical working artifacts for harmless presentation drift and refuse semantic
non-feedback drift. They remain distinct in authorization: the local route can
make only its selected row's presentation replacement and response, while the
stage route can apply the wider envelope.

Every re-entered stage follows one selection rule, independently of the other
stages selected by `--from-stage`: a baseline-equal artifact with one or more
`open` feedback rows takes the bounded feedback route; one with none is a
feedback-free no-op. Baseline admission precedes that selection, so a direct
semantic edit never reaches the no-op path or leaves a changed Plans artifact
with apparently current seeds. The no-op makes no backend request, artifact
write, artifact reload, seed-state invalidation, or downstream rewrite merely
because an earlier selected stage existed. It creates an in-memory canonical
loaded artifact from the baseline-equal parse and appends that canonical text,
not raw on-disk bytes, to the same upstream set that a write-then-reread
normally populates for later stages. A later selected stage therefore receives
the same canonical upstream text after a harmless comment or unknown-field
edit, despite no disk rewrite. The no-op first re-gates that artifact against
every current upstream value. A re-gate failure gives that stage state
`invalid`, reports a specific message containing its gate violations, halts
the run as `OUTCOME_STAGE_INVALID`, and makes no backend call, write, retry,
seed action, or rollback of an earlier accepted bounded merge. A passing
re-gate gives the stage state `completed-no-change`, with zero attempts. The
run-level vocabulary becomes
four closed outcomes: `OUTCOME_COMPLETED`, `OUTCOME_COMPLETED_NO_CHANGE`,
`OUTCOME_STAGE_EXHAUSTED`, and `OUTCOME_STAGE_INVALID`. Every current
exhaustive two-way branch must update for that vocabulary: `roadmap.py`'s
`OUTCOMES` tuple, `cli/roadmap_cmd.py`'s success, exhausted, and invalid
rendering, `roadmap.py:_run_roadmap`'s
`lifecycle.complete(outcome=..., rc=...)` call, and any other closed-outcome
consumer. `OUTCOME_COMPLETED` and `OUTCOME_COMPLETED_NO_CHANGE` record and
return success; the exhausted and invalid outcomes record and return failure.
A run whose every selected stage is feedback-free reports
`OUTCOME_COMPLETED_NO_CHANGE`, so an operator or CI watching only the top-line
result knows no artifact was merged. A run mixing a feedback-free stage with
at least one bounded merge reports `OUTCOME_COMPLETED`; the per-stage
distinction remains in the run log. A later selected stage with its own `open`
feedback still takes the bounded route. A successful bounded merge is the
only path in this plan that writes its artifact or invalidates derived seeds.
The CLI's write summary reports only the actual members of
`RoadmapResult.overwritten_stages`. It names feedback as the route for a
further construct or prose change and says that a later re-entry invokes only
stages with active feedback; it does not offer copy-aside or `--from-stage`
guidance for direct semantic hand edits, because source admission rejects them.

This plan introduces no broad-recovery selector, fallback, or feedback-free
whole-artifact regeneration. A generic rebuild after an upstream manual edit
needs a distinct future route and is not inferred from `--from-stage`; this
work keeps the existing re-entry entrypoint only for the per-stage selection
above. The stage gates remain the sole judge of a merged candidate.

## References

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259) — Defines JSON syntax and interoperability rules relevant to parsing a single closed operation envelope and rejecting duplicate members.
- [Python 3.13 json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Documents JSONDecoder, raw_decode, object_pairs_hook, and parse_constant for strict bounded-response parsing.
- [Pydantic: Unions](https://docs.pydantic.dev/latest/concepts/unions/) — Explains discriminated unions for validating a closed vocabulary of operations selected by an op field.
- [Pydantic: Configuration](https://docs.pydantic.dev/latest/api/config/) — Documents ConfigDict options such as extra='forbid', strict validation, and frozen models for closed operation records.
- [Pydantic: Validators](https://docs.pydantic.dev/latest/concepts/validators/) — Covers field and model validators useful for enforcing cross-field and whole-envelope ordering and combination rules.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Documents safe_load, safe_dump, representers, and emitter controls used when merging operations into canonical YAML artifacts.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Documents SHA-256 for the canonical non-feedback baseline identity.
- [os.replace — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html#os.replace) — Documents atomic replacement used with the roadmap writer guard to publish a recoverable artifact and baseline generation.
- [pytest: How to Monkeypatch/Mock Modules and Environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Shows how to stub invokers and assert that feedback-free revisions make no backend request.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- A general-purpose patch or diff language for arbitrary artifact edits.
- A general body-prose editor or a whole-body replacement; row-associated
  amendments are the only prose surface in this route.
- Changes to what the existing stage gates check, their retry behavior, or
  their completed-result contract, except that continuity enumerates `stores`
  for a removal record without widening the local design-row selector.
- Widening `--revise-feedback` beyond its one selected row or changing
  structural revision's selection, evidence, or operation authority; the
  local route retains its selector-bound presentation-and-response authority,
  and structural revision only shares baseline publication.
- Retargeting any existing declared relation, including reference-field entity
  ids, business-rule/workflow entity ids, constraint anchors, component links,
  plan component ids, ordering, assumption consumers, or decision anchors; a
  future effort can introduce a distinct, reviewable relation operation if it
  needs that authority.
- A broad recovery or feedback-free regeneration selector. A later effort may
  design one with an explicit operator input; #297 does not infer recovery
  from `--from-stage`.
- #242's retention semantics, including `closed` feedback, retained closed
  rows, removal snapshots, and removal-to-decision references.
- The independent hand-authored YAML-scalar corruption defect recorded in
  `BUG_BACKLOG.md`; the bounded model reply is JSON, but it does not mediate
  a reviewer editing raw YAML.
- Baseline use by receipt, impact, escalation, or structural-evidence readers;
  their raw-evidence and freshness contracts remain the later, re-scoped
  `roadmap-canonical-source-identity` work.
- Receipt freshness, evidence retention, framework lenses, or any new roadmap
  stage.

## Risks

- **Vocabulary creep.** A convenient catch-all operation would recreate the
  unbounded surface under another name. Every operation must express a
  currently reviewer-authorized stage change; if a real case needs arbitrary
  patching, stop and re-scope it as separate design work.
- **Baseline authority creep.** The baseline owns source admission for normal
  and local feedback revision only. It must compare the whole non-feedback
  semantic projection, never a selected row or raw bytes; never update from a
  direct edit; and never compare feedback rows, which would misfire on normal
  reviewer input. Receipt, impact, escalation, and structural readers retain
  their current source contracts until the remaining source-identity plan
  deliberately adopts the shared baseline.
- **Enrollment trust boundary.** Exact canonicality cannot establish who last
  changed a legacy artifact. `--enroll-baselines` is therefore an explicit
  operator declaration of trust, not an automatic migration and not evidence
  that a pre-enrollment hand edit did not occur. Once enrolled, no writer or
  reader may silently replace the baseline from current source.
- **Derived-seed freshness.** A bounded feedback merge at any stage cannot
  become current before every affected derived seed is marked invalidated. Its
  publication or enrollment journaled set must include the seed-state sidecar
  whenever the current route would invalidate it, and recovery must choose one
  whole old or new set rather than independently repairing its members.
- **Outcome-vocabulary widening.** Adding `OUTCOME_COMPLETED_NO_CHANGE` and
  `OUTCOME_STAGE_INVALID` widens the current two-member `OUTCOMES` tuple to
  four members. Update every exhaustive two-way branch: the tuple itself,
  `cli/roadmap_cmd.py`'s completed, exhausted, and invalid rendering, and
  `roadmap.py:_run_roadmap`'s `lifecycle.complete` run-log `rc` mapping.
  Missing the last would log the successful no-change outcome as a failure.
  Enumerate every remaining consumer of the closed vocabulary before declaring
  the widening complete.
- **Shared-leaf regression.** Structural revision and `--revise-feedback`
  consume neighboring bounded machinery. The selector-bound local profile,
  stage-envelope profile, and structural path need explicit compatibility
  coverage as the common contract expands.
- **Incomplete feedback context.** A prompt that omits a relation needed to
  choose a valid operation can produce a deterministic rejection loop. The
  detail phase must derive the minimum context from the existing gate
  obligations, not reintroduce whole-artifact or whole-authoring-prompt
  payloads as a shortcut.
- **Recovery demand after this cut.** A rejected direct source edit may reveal
  a real need for a deliberate broad rebuild or a feedback proposal. It does
  not authorize a fallback in this route; capture the request for #298's
  review bridge or a separately selected recovery effort.
- **Plan-ordering leakage.** A plan-row mutation can leave a dangling,
  duplicated, or out-of-order entry without changing any row id. Plan addition
  and removal own only their deterministic companion ordering effects, while
  existing assumption consumers and decision anchors cannot retarget around a
  removal; any broader relation change stays out of this vocabulary.
- **Same-envelope reference leakage.** An operation order must not make a new
  id look like predecessor state. The frozen predecessor inventory applies to
  every relationship-bearing field in every `add-row`, not just Plan ordering,
  assumptions, and decisions.
- **Store-continuity split.** Store rows are intentionally outside the local
  presentation selector but are valid stage removal targets. The continuity
  gate therefore needs a gate-specific Components row enumeration that includes
  stores; reusing the selector's narrower view would reject an authorized
  store removal.
- **Prose-patch escape.** A body-edit field could recreate whole-artifact
  regeneration. It is valid only as an exact, bounded amendment coupled to
  the selected row. Its span may not contain another row's prose, and it must
  preserve every unselected row's prose, references, and body bytes.
- **False confidence from unit scale.** The reported defect appears on a
  large artifact and must be checked at that scale, not inferred from a small
  fixture alone.

## Testing

Use hermetic fixture-driven tests with stubbed invokers. A integration-scale
artifact (tens of KB) with multiple feedback rows demonstrates that a
stage-level feedback revision receives and returns bounded JSON operations,
changes only operations' named rows, and preserves an untargeted
`awaiting-review` row's response exactly. Mutating an operation target,
lifecycle transition, or removal evidence must fail through the existing
validation or gate boundary; mutating unaffected canonical content must be
impossible because it is absent from the model reply.

Test every stage-envelope authority-matrix row: an artifact target may add a
typed row and its bounded target-ID prose fragment but cannot edit or remove
one; a live row target may edit or remove only itself and its supplied prose
span; a target retained only by a removal record may receive only its response;
and every active feedback row receives exactly one response and the only model
state move is `open` → `awaiting-review`. Assert the invalid complements by
mutation, including a missing target-ID fragment, an unmatched, ambiguous,
overlapping, shared, or cross-target prose span; a replacement that changes an
unselected row's prose while retaining its id; an altered untargeted body byte
or row id; duplicate targets; and a partial envelope, so code proves atomic
refusal rather than only happy-path parsing. Cover `edit-row`'s no-retarget
protection on `DecisionRow.anchor` across every artifact type that declares
`decisions` (domain, constraints, components, and plans), against both a
settled and a still-pending decision, mutating to retarget a pending anchor on
each artifact type and asserting the same rejection as a settled one — the
existing settled-decision gate does not itself cover pending rows. Separately
cover `AssumptionRow.consuming_plan_ids` protection on `PlansArtifact`, the one
artifact type that declares assumptions. Separately prove the selector-bound
local profile still accepts its optional presentation replacement followed by
exactly one selected-feedback response and leaves an unselected open row
unchanged.

Treat every existing relation field as one immutable set. Mutate a reference
field's entity id; business-rule and workflow entity ids; constraint anchors;
component entity, pattern, constraint, and Store ids; plan component ids;
ordering dependencies and assumption targets; assumption consumers; and
decision anchors. Each edit must reject before merge, including membership,
order, and replacement changes. Existing relation records are context facts for
rejection, never edit authority.

Exercise each effective limit independently. With the default configuration,
more than 32 active feedback items must return `invalid` before a backend call.
A response over 32 KiB, a prose amendment over 4 KiB, or more than one material
operation for one feedback id must return `invalid` without a correction prompt,
retry, partial merge, or write. Assert that the message identifies the relevant
feedback id when there is one, the measured value, the effective limit, and the
instruction to split the feedback. Assert that both rendered feedback-structure
comments give reviewers the same hard ceilings and split-feedback action.

Exercise configuration separately: an absent `roadmap_feedback.stage_limits`
uses the four hard limits; a project block may lower each numeric limit but
cannot raise one; and a boolean, non-integer, unknown key, malformed block, or
prose limit above the response limit rejects before a backend call. Prove a
user-level config never changes this project-owned contract, and changing the
project file while a run is active cannot change the limit snapshot already
chosen for that run.

Register `roadmap_feedback`, `stage_limits`, and its three numeric leaves in
`plan_tool/data_contract.py:json_object_contracts`. Regenerate or verify the
project-configuration contract from that registry so the documented JSON keys
cannot drift from the resolver, while retaining the existing user-config path
only for its unrelated configuration keys.

Exercise the identity-only exceptions as their own set. `hosting` is never an
`add-row` or removal target, but a feedback-authorized edit may change only a
live fixed facet's values while retaining its id and facet. `stores` remains
admitted for add, edit, and removal but carries no prose span. A supplied
identity-only prose span, an omitted prose span for a prose-inventory row, an
attempt to add a hosting facet, or an attempt to remove one rejects the whole
envelope.

For every relationship-bearing field on every admitted added row, try a target
id introduced by another operation in the same envelope. Binding must reject
it regardless of operation order; the only usable references are in the frozen
live predecessor-id inventory. Separately, remove a Components `stores` row
with a cited current-format removal record. The continuity gate accepts that
record while `design_row_collections` remains the narrower local presentation
view and still excludes stores.

Project `ComponentRow.store_ids` through the same ordered declared-relation
context as the other component references. A Store removal with any incoming
component Store reference exposes that fact to the prompt before the backend
call and rejects before a candidate if the response still attempts removal,
while an unreferenced Store removal reaches the bounded merger and retains its
continuity record. For a removal whose reference lives only in a downstream
artifact, prove the selected stage may publish and the later feedback-free
re-gate reports the downstream violation without rolling back that accepted
merge.

For each selected stage with no `open` feedback, use a fail-on-call invoker,
pre/post artifact, baseline, and seed-state digests to prove no backend
request, artifact write, artifact reload, baseline replacement, downstream
rewrite, or seed-state change occurs, and assert that a passing re-gate reports
`completed-no-change` at the stage level — zero attempts, a successful exit,
and run-log/CLI rendering never mistaken for a merged completion or a
retry-exhausted stage. Prove the four-member run-level vocabulary: a run whose
every selected stage is a feedback-free skip reports
`OUTCOME_COMPLETED_NO_CHANGE`, with successful CLI and run-log `rc`; a run
mixing a feedback-free stage with at least one bounded merge reports
`OUTCOME_COMPLETED`; and a failed skipped-stage re-gate reports
`OUTCOME_STAGE_INVALID`, non-zero CLI and run-log `rc`, the stage, and its
specific gate-violation message. The invalid path makes no backend call or
write and never retries. In a multi-stage re-entry, prove that such a skipped
stage does re-gate against the bounded result from an earlier stage. Test both
an upstream add and removal that make an unchanged components artifact fail;
each stops before a call or write for the skipped stage, names its gate
violation, and retains the earlier accepted merge. Also prove that a green
skipped stage appends its canonical in-memory loaded artifact to `loaded`, so
a later stage carrying `open` feedback takes the bounded route with that
artifact as upstream input and invalidates seeds only after its merge applies.

For every artifact type, add one row to every collection the authority matrix
admits, always with an explicit matching `row_type`; assert that an omitted,
unknown, payload-mismatched, or fixed-hosting `row_type` rejects the complete
envelope. At stage 4, prove that only a `plans` addition appends exactly one
matching ordering entry whose references are earlier predecessor plan ids.
Removing an unreferenced plan removes its one matching entry. Mutate those
cases to leave a duplicate, missing, dangling, or out-of-order ordering
reference; add a new assumption or decision that points at a newly added row;
or retarget an existing assumption consumer or decision anchor before removing
the plan it formerly named. Each must reject the whole envelope without
changing any canonical artifact.

Prove shared baseline admission runs before stage-envelope or local selector
authorization, with a call-order assertion (a spy or an operation-
authorization stub that fails the test if invoked first). Before that admission,
only `roadmap --enroll-baselines` can create legacy baselines: it requires an
explicit operator action, an exact-canonical contiguous prefix from stage 1,
records no artifact write, invalidates any existing Plans-derived seeds, and
refuses a noncanonical, gapped, later-only, or fully enrolled source. Treat the
whole requested prefix as one pending bootstrap generation, recover it before
the fully-enrolled check, and interrupt it between every pair of prefix
baseline writes as well as the Plans seed-state write. The test documents the
bootstrap boundary: enrollment trusts the current
exact-canonical source and therefore cannot retrospectively identify an earlier
direct edit. Every later semantic artifact publication creates a stage-keyed
baseline containing its canonical non-feedback projection and digest. A
baseline-equal predecessor, including
one whose only changes are inside feedback rows, proceeds with canonical
working text. A YAML comment or schema-unrecognized field is presentation-only:
both paths use rendered canonical text rather than raw bytes, log what was
normalized away, and do not write merely to normalize it. A semantic row add,
edit, delete, rename, body-prose edit, missing baseline, or pending/mismatched
artifact-baseline pair refuses before authorization, invocation, publication,
retry, seed invalidation, or mutation of `loaded`. Cover an open feedback
target whose row is deleted or renamed and assert the resulting `invalid`
message identifies the affected feedback target. A direct semantic edit to a
lower stage during `--from-stage N` is invalid before upstream re-gating, while
a presentation-only lower-stage difference supplies canonical in-memory text.
For Plans artifacts, assert that a semantic direct edit or a missing Plans
artifact paired with current derived seeds cannot reach the no-op or fresh-
authoring path or leave seed state current. For a bounded merge at Domain,
Constraints, Components, and Plans,
assert every existing derived seed is invalidated and simulate interruption
between every artifact, baseline, and seed-state replacement. Recovery returns
a recorded whole old or new set, never a new artifact or baseline from a
bounded merge paired with current seeds. Assert a Plans enrollment interrupted
between its baseline and seed-state replacement also recovers the whole old or
new bootstrap set. A feedback-row-only difference never produces a
semantic-drift refusal, while a direct non-feedback edit never becomes an
accepted artifact merely because the ordinary gates pass.

Keep every admitted file-backed normal-route source binding until the stage that
uses it finishes. Mutate a selected predecessor or upstream artifact after its
initial admission, both before a later stage sees it and while its stage awaits
the backend, including a terminal feedback-free re-gate. The normal route must
recheck before every gate or route use and immediately before publication,
return `OUTCOME_STAGE_INVALID`, and preserve all files, baselines, and seed
state. A prior accepted generation remains valid only as the guarded in-memory
result, never as permission to ignore a later direct file edit.

For both bounded publication paths, mutate the selected artifact's valid
feedback after context or selector preflight: add a row, change a request or
target, reopen a response, reorder rows, and remove a row. A frozen ordered
feedback snapshot must make every case refuse before write without classifying
the normal reviewer edit as semantic baseline drift or sending a correction or
retry. Repeat those mutations after a failed parse, merge, or gate attempt and
before the next correction prompt; the next backend call must be unreachable.

Test the supported boundary rather than claiming a raw-editor compare-and-swap
the filesystem cannot provide: observed source or feedback changes before the
final replacement refuse without a write. An editor that writes in the exact
interval after that check and during atomic replacement is outside the raw
hand-edit contract and must not be represented as a guaranteed-preserved case.

For the selector-bound local route, baseline-admit every earlier upstream
artifact before the selector preflight or backend call and pass only those
canonical admitted values to publication gates. Change an upstream artifact
after admission but before publication and assert a pre-write refusal with no
artifact, baseline, or seed-state change. The publisher must never mask either
case by rereading raw upstream text.

For a mixed re-entry, assert the CLI lists only actually replaced artifacts and
keeps no-op re-gates out of `overwritten_stages`. Its follow-up guidance sends
the reviewer to feedback, states that feedback-free stages only re-gate, and
does not recommend preserving direct semantic hand edits that source admission
will reject.

Run compatibility tests for the existing presentation-only local revision
and structural revision routes. Replay a stage-1 revision against the actual
`integration`-scale artifact or an equivalent captured fixture: it completes without
the whole-artifact `invoke`, YAML `parse`, or untouched-row `gates` failure
shape and preserves the untargeted awaiting-review response.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (non-code) — verification appropriate to the artifacts rather than unit tests.
- step 7 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A feedback-driven stage revision's model reply is a closed typed JSON
  operation envelope, never a complete roadmap artifact.
- The bounded prompt does not embed a whole predecessor artifact or a nested
  whole authoring prompt; its revision payload grows with selected feedback
  context rather than unrelated artifact text.
- `roadmap --enroll-baselines` is the only legacy-baseline initializer. It
  requires an explicit operator declaration that the current
  exact-canonical contiguous stage prefix is trusted, writes no artifact, and
  invalidates existing Plans-derived seeds because it cannot prove they came
  from the enrolled source. The whole requested prefix, including Plans seed
  invalidation when present, journals as one recoverable bootstrap set and
  recovers before the fully-enrolled check. It never claims to detect direct
  edits that predate enrollment.
  Every semantic roadmap writer-owned artifact then has a corresponding
  canonical non-feedback baseline copy and digest. The ordinary stage and
  local selector routes compare their parsed non-feedback projection to that
  baseline before authorization, upstream gating, or publication; structural
  revision updates it on a proved publication.
- A feedback-free authoring publication recovers its artifact/baseline pair as
  one recorded set. Every accepted bounded feedback merge, whether it publishes
  Domain, Constraints, Components, or Plans, recovers its artifact, baseline,
  and invalidated derived-seed state as one recorded set. It never leaves new
  roadmap semantics paired with seeds that still claim the earlier roadmap is
  current.
- A baseline-equal source with a comment, formatting change, or
  schema-unrecognized field uses canonical in-memory text and logs what the
  parser cannot retain, without a formatting write. A direct non-feedback
  construct or body-prose add, edit, delete, or rename, a missing baseline,
  or a mismatched pair is never accepted: the stage reports `invalid` with a
  specific reason and the local route refuses as `semantic-source-drift`.
  Neither invokes, writes, retries, changes `loaded`, nor alters seed state.
  A feedback-row-only difference remains normal reviewer input.
- Deterministic code applies only the operations named in the response before
  the existing stage gates judge the candidate.
- The stage-envelope authority matrix rejects an artifact-target edit/removal,
  a non-live-row edit/removal, an unowned add, a duplicate material target,
  any non-reviewer feedback-state move, any retarget of an existing decision
  anchor, reference-field entity, business-rule or workflow entity,
  constraint anchor, component entity/pattern/constraint/Store, plan component,
  ordering, or assumption-consumer relation, regardless of decision state, an
  unbounded or cross-target prose amendment, and any envelope that would
  partially merge;
  it also rejects every relationship-bearing field of a new row that names a
  same-envelope addition rather than the frozen predecessor inventory; the
  selector-bound local profile remains separately valid.
- Every prose-inventory material row operation carries its bounded row-prose
  amendment: an addition makes the new id appear in the body, while an edit or
  removal changes only an exact, row-owned target span that contains no other
  row's prose. Identity-only `hosting` and `stores` rows have no prose span;
  hosting is a fixed facet set and is never admitted to `add-row` or removal.
  Every unselected row's prose, all untargeted body bytes, and row references
  remain byte-for-byte unchanged.
- A baseline-equal feedback-free selected stage makes no backend request,
  artifact write, artifact reload, baseline replacement, downstream rewrite,
  or seed-state change only after its current-upstream re-gate passes. A
  passing stage reports `completed-no-change`, contributes its canonical
  in-memory loaded artifact to `loaded` for later stages, and makes no write.
  An upstream addition or removal that makes it invalid reports `invalid` with
  the specific gate violations, then stops as `OUTCOME_STAGE_INVALID` before a
  skipped-stage call or write while retaining an earlier accepted merge.
- Every existing lower artifact read for `--from-stage N` passes the same
  baseline admission before it becomes upstream gate input. A semantic lower-
  stage change or a missing artifact with residual baseline or derived-seed
  state is `invalid`; presentation-only drift is canonicalized in memory. The
  normal route retains and rechecks every file-backed selected or upstream
  binding before every gate or route use, including a feedback-free re-gate,
  and immediately before publication.
- `stores` remains outside the local presentation selector, but a cited Store
  removal record is valid continuity evidence for the Components gate. The
  bounded relation context includes `ComponentRow.store_ids`, so a referenced
  Store removal is visible to the prompt before backend work and an attempted
  removal fails before a candidate reaches the gates. A downstream-only
  reference remains outside selected context and is reported by that later
  stage's re-gate without rolling back an earlier accepted merge.
- A run whose every selected stage re-gates without a merge reports
  `OUTCOME_COMPLETED_NO_CHANGE`, including a successful CLI and run-log `rc`.
  A run with any bounded merge reports `OUTCOME_COMPLETED`. Both outcomes are
  distinct from `OUTCOME_STAGE_EXHAUSTED` and `OUTCOME_STAGE_INVALID`.
- Every `add-row` names an explicit row-type collection admitted for its
  artifact; an omitted, unknown, or payload-mismatched type rejects the whole
  envelope. On `PlansArtifact`, only a `plans` addition appends one valid
  matching ordering entry. Plan removal deletes that one entry only when no
  surviving ordering, assumption, or decision reference names it; every
  invalid companion relation rejects the whole envelope.
- The stage route admits no more than its effective active-feedback limit
  (32 by default), accepts a reply no larger than its effective UTF-8 JSON
  limit (32 KiB by default), and accepts no prose amendment larger than its
  effective limit (4 KiB by default). It permits at most one material operation
  per active feedback item. An excess is `invalid`, names its measured limit
  failure and split action, and makes no model retry, partial merge, or write.
  Both artifact feedback-structure comments state the same hard ceilings.
- A project may lower the numeric stage-feedback caps through
  `.plan-tool/config.json`'s `roadmap_feedback.stage_limits` block. It cannot
  raise the hard ceilings, change the one-material-operation rule, or inherit a
  user-level override. The command snapshots valid limits once; an invalid
  project block fails preflight before a backend call or write. The
  `json_object_contracts` registry names this project-only block and its three
  leaves, and its generated-contract test remains green.
- A later selected stage with open feedback still follows the bounded route
  using a green skipped predecessor as upstream input.
- A tens-of-KB fixture proves a named change lands while an untargeted
  `awaiting-review` response remains byte-for-byte unchanged.
- Existing `--revise-feedback` selector-bound presentation replacements keep
  their existing authorization scope while baseline-admitting every upstream
  gate input and publishing only against that admitted canonical map;
  structural revision keeps its current contract under the widened shared
  machinery.
- Both bounded publication paths freeze the selected artifact's ordered
  reviewer-feedback snapshot after preflight and recheck it before any
  correction/retry prompt and immediately before writing. An observed
  concurrent added, changed, reopened, reordered, or removed row refuses
  without a write, retry, baseline update, or seed-state change.
- The published concurrency boundary promises refusal for source and feedback
  changes the protocol observes before replacement. It does not promise to
  preserve an uncoordinated raw hand edit that races after the final check and
  during atomic replacement; feedback remains the supported edit path.
- CLI output lists only actual artifact writes. It identifies feedback as the
  supported path for a further change, distinguishes feedback-free re-gates,
  and gives no copy-aside or overwrite guidance for semantic hand edits.
- A real-size stage-1 replay completes without re-emitting untouched content
  and without the production failure shape that motivated #297.
- `ROADMAP_FORMAT.md` states the bounded stage-revision response and merge
  contract, and `BACKLOG.md` #297 is updated only when the work ships.

## Deferred

- Extending this baseline to receipt, impact, escalation, and structural
  evidence freshness; re-scope `roadmap-canonical-source-identity` after this
  outcome is verified.
- Redesigning #242 around the shipped merge layer.
- A safe interface for reviewers who manually add or edit YAML feedback rows.
- A deliberate broad-recovery route for feedback-free `--from-stage` work.
