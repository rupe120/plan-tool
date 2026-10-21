> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap Escalation Impact Routing
intent: After a current structural-escalation receipt exists for one selected feedback
  row, `plan-tool roadmap` will produce a separate, immutable impact-routing analysis.
  It will validate the receipt, read a coherent current roadmap and recorded-brief
  snapshot, resolve the declared relation closure, and classify the evidence as same-artifact,
  cross-artifact, scope-review-required, or invalid. It will route only to a named
  follow-on workflow; it will not invoke `--from-stage`, write a canonical artifact,
  call a backend, or choose a patch.
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Extract typed roadmap relations without changing views or gates
  intent: Give impact analysis one ordered source for the closed design-only set of
    gate-validated roadmap relations, with a stable owner, endpoint, kind, and declared
    direction instead of copying field lists. Receipt-safe identifiers are enforced
    only after the selected closure is known.
  files:
  - plan_tool/roadmap_view.py
  - tests/test_roadmap_view.py
  - tests/test_roadmap_gates.py
  creates:
  - plan_tool/roadmap_relations.py
  - tests/test_roadmap_relations.py
  complexity: high
  change_type: refactor
  detail: docs/implementation-plans/plan-details/roadmap-escalation-impact-routing/01-extract-typed-roadmap-relations-without.md
  status: done
- id: 2
  title: Add deterministic bidirectional impact closure for one roadmap target
  intent: Expand one receipt target to a finite, ordered set of related rows and owning
    artifacts by following both directions of validated declared relations. Unrelated
    malformed or receipt-unsafe inventory entries cannot affect this selected closure.
  creates:
  - plan_tool/roadmap_impact_relations.py
  - tests/test_roadmap_impact_relations.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Supplies the complete typed relation inventory, including stable owners for
      nested references.
  detail: docs/implementation-plans/plan-details/roadmap-escalation-impact-routing/02-deterministic-bidirectional-impact.md
  status: done
- id: 3
  title: Extract recorded-brief readers and preserve source.json replacement
  intent: Let snapshot code read the same recorded brief path and decoded-text digest
    as broad roadmap execution, while separately binding exact raw `source.json` bytes
    for impact evidence without importing private orchestrator helpers.
  files:
  - plan_tool/roadmap.py
  creates:
  - plan_tool/roadmap_source.py
  - tests/test_roadmap_source.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/roadmap-escalation-impact-routing/03-extract-recorded-brief-readers-preserve.md
  status: done
- id: 4
  title: Capture, gate validate, and recheck one coherent roadmap and brief snapshot
  intent: Prevent impact analysis from combining roadmap artifacts, source metadata,
    or broad-equivalent brief content from different revisions, including an exact
    raw-byte source-record binding, or invalid full current-state gate tuples, including
    predecessor-independent integrity checks.
  creates:
  - plan_tool/roadmap_impact_snapshot.py
  - tests/test_roadmap_impact_snapshot.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: Supplies the established recorded-brief path and content-reading contract.
  detail: docs/implementation-plans/plan-details/roadmap-escalation-impact-routing/04-capture-gate-validate-recheck-one.md
  status: done
- id: 5
  title: Define closed impact identity, immutable analyses, and route precedence
  intent: Bind one selected receipt, coherent snapshot, and deterministic selected
    closure into a route class separately from its immutable publication outcome and
    process status.
  creates:
  - plan_tool/roadmap_impact_analysis.py
  - tests/test_roadmap_impact_analysis.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 4
  depends_on_notes:
    2: Supplies ordered closure nodes, edges, and artifact ownership evidence.
    4: Supplies the coherent artifact, source-record, and brief evidence bound into
      analysis identity and freshness.
  detail: docs/implementation-plans/plan-details/roadmap-escalation-impact-routing/05-define-closed-impact-identity-immutable.md
  status: done
- id: 6
  title: Add an impact-analysis evidence namespace while preserving immutable finals
    and temporary cleanup
  intent: Keep exact-name impact analyses separate from receipt records so each evidence
    view scans only its own closed record type.
  files:
  - plan_tool/roadmap_evidence_store.py
  - tests/test_roadmap_evidence_store.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-escalation-impact-routing/06-impact-analysis-evidence-namespace.md
  status: done
- id: 7
  title: Add closed redacted impact-analysis telemetry while preserving run-log appends,
    active-snapshot replacement, and guarded cleanup
  intent: Make analysis admission, route class, publication outcome, reuse, and failure
    observable as separate facts without recording reviewer prose or artifact contents.
  files:
  - plan_tool/run_log.py
  - tests/test_run_log.py
  - DATA_CONTRACT.md
  complexity: medium
  change_type: feature
  depends_on:
  - 5
  depends_on_notes:
    5: Supplies the route classes, identities, and validation outcomes that telemetry
      records.
  detail: docs/implementation-plans/plan-details/roadmap-escalation-impact-routing/07-closed-redacted-impact-analysis.md
  status: done
- id: 8
  title: Run guarded impact analysis with no-overwrite publication and temporary cleanup
  intent: Produce only fully bound analysis evidence under the roadmap writer guard,
    with a closed process-status map, without exposing mixed inputs, partial records,
    or canonical mutations.
  creates:
  - plan_tool/roadmap_impact_run.py
  - tests/test_roadmap_impact_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 4
  - 5
  - 6
  - 7
  depends_on_notes:
    2: Supplies deterministic closure computation.
    4: Supplies coherent capture and freshness rechecks.
    5: Supplies analysis construction and stored-record validation.
    6: Supplies isolated immutable storage for analysis records.
    7: Supplies the redacted lifecycle events emitted on terminal paths.
  detail: docs/implementation-plans/plan-details/roadmap-escalation-impact-routing/08-run-guarded-impact-analysis-no.md
  status: done
- id: 9
  title: Wire exact exclusive impact-analysis creation and coordinated log-free views
    while preserving canonical, seed, receipt, local-revision, and broad write paths
  intent: Let operators create and inspect one coherent current impact snapshot through
    one exact receipt selector and one log-free view, rendering separate route and
    publication facts with the runner's closed status, without invoking a backend,
    broad re-entry, or a canonical writer.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/cli/__init__.py
  - plan_tool/roadmap_revision_publish.py
  - tests/cli/test_roadmap_cmd.py
  - tests/test_roadmap_revision_publish.py
  - tests/cli/package_surface_help.golden.txt
  - docs/cli/roadmap.md
  - CAPABILITIES.md
  complexity: high
  change_type: feature
  depends_on:
  - 8
  depends_on_notes:
    8: Supplies the typed runner, status mapping, immutable results, and freshness-aware
      inspection contract.
  detail: docs/implementation-plans/plan-details/roadmap-escalation-impact-routing/09-wire-exact-exclusive-impact-analysis.md
  status: done
- id: 10
  title: Document impact-analysis schema, freshness routes, and the noncanonical write
    boundary
  intent: Make the analysis contract, named follow-on workflows, no-route cases, route
    and publication facts, command statuses, forms, and exact permitted writes discoverable
    to operators and future authors.
  files:
  - ROADMAP_FORMAT.md
  - tests/test_roadmap_format.py
  - README.md
  - CLAUDE.md
  - docs/ARCHITECTURE.md
  - docs/ROADMAP_WALKTHROUGH.md
  - RUNBOOK.md
  - TESTING.md
  complexity: high
  change_type: non-code
  depends_on:
  - 2
  - 4
  - 5
  - 7
  - 9
  depends_on_notes:
    2: Provides the landed relation and closure vocabulary.
    4: Provides the snapshot and freshness rules.
    5: Provides the final analysis schema, identity, and route precedence.
    7: Provides the telemetry event contract.
    9: Provides the final command forms, output behavior, and log-free view semantics.
  detail: docs/implementation-plans/plan-details/roadmap-escalation-impact-routing/10-document-impact-analysis-schema.md
  status: done
---
# Roadmap Escalation Impact Routing

## Overview

`plan-tool roadmap` adds a separate, immutable impact-routing analysis after a current structural-escalation receipt exists for one selected feedback row. It validates the receipt, reads a coherent current roadmap and recorded-brief snapshot, resolves the declared relation closure, and classifies the evidence as `same-artifact`, `cross-artifact`, `requires-scope-review`, or `invalid`. It routes only to a named follow-on workflow and never invokes `--from-stage`, writes a canonical artifact, calls a backend, or chooses a patch.

## Problem statement

A structural-escalation reason such as `cross-artifact-impact` signals that review is needed, but it does not prove that the current declared relations identify every affected artifact. Likewise, an apparent one-artifact closure cannot make broad stage re-entry safe. The tool needs a deterministic, current-source-grounded analysis that states exactly what the canonical model supports and refuses to turn incomplete evidence into a broad command or automatic writer.

## Architecture

Creation accepts exactly one opaque receipt final through `--analyze-escalation RECEIPT_FINAL`; it never scans receipts to choose one. It validates the receipt's closed version-1 schema, duplicate-member-free JSON, semantic identity, exact final-name binding, shared selector grammar, feedback state, target kind/id, selector-derived source path/digest, handoff, and redaction boundary. Receipt revalidation receives the selected artifact from the captured snapshot, re-runs the complete receipt-selection predicate against those exact bytes, and compares its selector, target, and digest with the receipt. Receipt creation remains owned by `roadmap-structural-revision-escalation`.

While `roadmap_revision_publish.py:roadmap_writer_guard` is held, the runner reads one raw `source.json` byte stream, the four canonical artifact byte streams, and the recorded brief. It treats a snapshot as admissible only when the source record parses under its closed reader contract and every artifact is UTF-8 and parse/render canonical. The source-record digest is SHA-256 of the exact raw `source.json` bytes; it is distinct from the recorded brief's broad-equivalent UTF-8 decoded-text `_artifact_digest(text)`. The runner records only those safe digests, never a path or content. It then runs every stage's full current gate tuple in stage order with an `ArtifactEnvelope` containing the captured upstream artifacts and `predecessor=None`. That disables only comparisons to an earlier artifact; it keeps predecessor-independent design/removal and feedback-integrity checks active. Analysis does not read a prior artifact version or treat review-owned feedback/removal history as a relation source. Immediately before immutable publication, the runner rereads and revalidates the exact raw source-record bytes, artifact-byte vector, full current-state gate result, and broad-equivalent brief digest. Any unreadable, changed, malformed, noncanonical, or gate-invalid input is `invalid` and never publishes an analysis.

The closed design relation inventory contains only: `FieldRow.entity_id` (owned by its entity); `BusinessRuleRow.entity_ids` and `WorkflowRow.entity_ids`; `DecisionRow.anchor` in every artifact; `ConstraintRow.anchor_ids`; `ComponentRow.entity_ids`, `pattern_ids`, and `constraint_ids`; `PlanRow.component_ids`; `OrderingEntry.depends_on` and `assumption_targets` (owned by that entry's `plan_id` row); and `AssumptionRow.consuming_plan_ids`. Each extractor emits its closed kind, declaring row, endpoint, stable owning artifact, declared direction, and deterministic order; nested fields and ordering entries use their containing stable design row as owner. `FeedbackTarget.row_id`, `RemovalRecord.feedback_ids`, feedback state, response prose, removal rationale, and every review-only citation are excluded except for the one selected receipt target that establishes the root. `PlanRow.draft_seed_path`, draft-seed provenance, and seed state are sidecar provenance, not design relations, and are excluded. A row target starts at its exact target row. An artifact target starts at every stable row owned by the selected artifact. From those roots, closure traverses both incoming and outgoing declared edges, while preserving each edge's stored direction, and projects owning artifacts in stage/key/row/relation order. Receipt-safe validation applies only to that selected closure and to facts that cross a persistence, telemetry, or view boundary: every selected node and selected relation owner/endpoint must satisfy `is_receipt_safe_id`, and a selected relation that cannot map to one stable endpoint is `invalid`. A receipt-unsafe or unmappable relation disconnected from the selected closure is ignored; it cannot block a safe route and its raw identifier never leaves the relation engine. This is the complete **declared** closure: no reviewer prose, receipt reason, or undeclared relationship can add a node.

For a gate-valid snapshot the selected declared closure is complete when every reached relation has one safe, stable owner and endpoint. The receipt reason does not add rows or artifacts. It only protects against a false narrowing: when reason `cross-artifact-impact` has a complete declared closure containing only the selected artifact, the analysis is `requires-scope-review` rather than `same-artifact`. That durable no-route result says that the stated cross-artifact concern is not corroborated by the current typed model; it does not infer a missing artifact. A complete closure containing more than one artifact is `cross-artifact` for every reason; any other complete one-artifact closure is `same-artifact`.

An immutable analysis has one closed versioned semantic preimage: the exact receipt final name and semantic id, receipt selector/target/reason/source digest, the ordered safe snapshot digest vector, the SHA-256 digest of exact raw source-record bytes, the recorded brief decoded-text digest, ordered safe selected-closure nodes and relation evidence, route class, and the nullable follow-on workflow. Its SHA-256 semantic id is also its opaque evidence final name. A creation input that fails receipt, snapshot, selected-closure safety, relation, or semantic validation is transient `invalid` and creates no record. When the expected final is occupied, exact canonical byte equality produces `reused`; every different, malformed, mismatched-final, or nonmatching semantic byte sequence is `collision`, creates no new record, and never reuses that final. A view treats an existing record as current only when strict parsing succeeds, its entry name equals its semantic final name, and a newly recomputed canonical candidate has both the same final name and exactly the supplied canonical bytes. A parser-valid but substituted or stale record is no-route `invalid` or `stale`, never a current route. A valid `requires-scope-review`, `same-artifact`, or `cross-artifact` analysis is durable. No-route classes store `next_workflow: null`, print no command, and have no workflow consumer. The immutable record stores a route class; the creation command separately reports immutable publication outcome (`created` or `reused`) so a valid scope-review result never loses either fact. Inspection never invents a publication outcome.

The analysis namespace is distinct from escalation receipts. Creation may write only the writer lock, one immutable analysis final, and lifecycle telemetry. It never changes canonical artifacts, feedback or seed state, Git state, or a receipt. `--view impact-analyses` first performs its existing read-only empty-namespace check. For a nonempty namespace it acquires a reader-only snapshot guard over the existing per-roadmap writer-lock file, with the same exclusive coordination semantics as writers but no writer token, persistence method, evidence creation, or telemetry. It rescans evidence, re-captures and current-state revalidates inputs, and renders while that guard remains held; failure to acquire the existing coordination boundary renders no current route. The view never chooses a receipt from a scan, never creates a lock or evidence record, and never routes from an invalid or noncurrent record.

Telemetry has one closed redacted lifecycle. `roadmap_impact_preflight` records the safe requested receipt final, validated selector/target/reason when available, digest/count facts, and exactly one verdict. Its verdict/fact matrix is: `mode-rejected`, `final-rejected`, `receipt-missing`, `receipt-unreadable`, `receipt-invalid`, and an early `interrupted` verdict expose only the safe requested final when one was established; `receipt-rejected` may also expose validated receipt selector/target/reason/source digest; `snapshot-rejected` may additionally expose raw-source-record and decoded-brief digests plus artifact count; `closure-rejected` may additionally expose selected-closure counts; and `accepted` has the same fully resolved safe fact set. A verdict never exposes facts from a later admission phase. After `RunLogWriter.start` succeeds, the runner emits exactly one preflight for every resolved admission path before publication; an unsuccessful `mode-rejected` or `final-rejected` path then returns terminal `preflight-rejected`, while receipt/snapshot/closure rejection returns terminal `invalid`.

`roadmap_impact_result` records only outcomes whose append completed: `completed`, `preflight-rejected`, `invalid`, `collision`, `write-failed`, or `interrupted`. `completed` carries exactly one route class and `created` or `reused`; it includes a safe analysis id, and includes a workflow only for routable classes. Thus a durable scope-review result carries `route_class: requires-scope-review`, `publication_outcome: created` or `reused`, a safe analysis id, and null workflow. `telemetry-unavailable` is a return-only process outcome, never an event outcome, because an event whose own append failed cannot truthfully claim it was recorded. An interrupted command may append `interrupted` only when that append succeeds; failure or interruption during any append returns a redacted process result and never fabricates a compensating event. It records no feedback prose, artifact or brief content, path, prompt, raw backend data, or unsafe relation id. A telemetry failure before immutable publication prevents it. A failure or interruption after `publish_evidence` returns cannot retract an immutable final: the command returns no route and a later exact retry validates and reports `reused`; telemetry is not treated as authority for the record. Normal event-pair and `run_end` guarantees apply only after each append returns.

`--analyze-escalation RECEIPT_FINAL` permits exactly one well-formed receipt-final argument and rejects `--escalate-feedback`, `--escalation-reason`, `--revise-feedback`, `--view`, `--from-stage`, `--from-existing`, `--apply`, `--refresh-seeds`, `--accept-seed`, `--materialize`, `--mode`, `--id`, and `-y`. When the analysis option itself is present, a well-formed companion reaches the redacted `mode-rejected` preflight and creates no analysis; malformed or duplicate analysis arguments are a redacted no-record rejection. `--view impact-analyses` permits no companion option or repeated view and remains a log-free, read-only usage error on conflict; a pure nonempty view coordinates with writers but creates neither evidence nor telemetry. A completed pure view returns `0` for every rendered empty, current, stale, unavailable, invalid, or guard-failed state because the read-only inspection itself completed; only its syntax/conflict usage errors return `2`. Existing receipt, local-revision, canonical view, seed, and broad-mode behavior stays byte-for-byte compatible.

The closed route class uses this precedence:

| Class | Producer condition | Durable record |
| --- | --- | --- |
| `invalid` | Creation input fails receipt, snapshot, brief, selected-closure safety, or semantic validation; an inspected stored record can separately render invalid | Transient no-record creation result and no-route view status; correct or regenerate evidence; no workflow begins. |
| `requires-scope-review` | A complete one-artifact declared closure does not corroborate receipt reason `cross-artifact-impact` | Durable record with `next_workflow: null`; an operator obtains narrower typed evidence; no broad command is printed. |
| `cross-artifact` | A current complete declared closure names more than one canonical artifact | Durable record naming `roadmap-cross-artifact-revision-transaction`; that plan still runs its own admission checks. |
| `same-artifact` | A current complete declared closure names one canonical artifact and no cross-artifact concern remains uncorroborated | Durable record naming `roadmap-same-artifact-structural-revision`; that plan may instead validate the receipt directly. |

Immutable publication remains a fact independent of the route class:

| Publication outcome | Expected final state | Command fact |
| --- | --- | --- |
| `created` | No final existed and canonical bytes were durably published | Report with the independently computed route class; record is current only after guarded revalidation. |
| `reused` | Existing final bytes exactly equal this canonical semantic record | Report with the independently recomputed route class; never rewrite the final. |

Terminal failures do not have a publication outcome: `preflight-rejected` is a
well-formed-command admission rejection, `invalid` is a post-admission
receipt/snapshot/closure/recheck failure, and `collision`, `write-failed`,
`telemetry-unavailable`, and `interrupted` report no route. Their immutable
facts, when any might already have been published, are recoverable only by a
later exact retry.

Creation process status is closed and independent of route and publication facts:

| Status | Terminal condition |
| --- | --- |
| `0` | A durable current analysis completed, including `same-artifact`, `cross-artifact`, or valid no-route `requires-scope-review`, whether its publication outcome is `created` or `reused`. |
| `1` | A syntactically accepted request cannot provide a durable route: `invalid` during admission or recheck, `collision`, `write-failed`, or `telemetry-unavailable`. |
| `2` | The request is malformed, repeated, or has an otherwise parseable incompatible companion and ends in `preflight-rejected` without an analysis. |
| `130` | The command is interrupted. |

Read-only inspection has its own closed status map:

| Status | `--view impact-analyses` condition |
| --- | --- |
| `0` | The view completes and renders an empty, current, stale, unavailable, invalid, or guard-failed no-route/current-route state. |
| `2` | The view has a malformed, repeated, or incompatible companion argument; it reads no evidence and creates no telemetry. |

Helper extraction is limited to relation-inventory, current-state snapshot, receipt/analysis-validation, route-class, immutable-evidence, telemetry, reader-snapshot, and CLI-conflict helpers that preserve the existing roadmap reader/writer boundary.

## References

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Defines interoperable JSON syntax and unique-member expectations needed for strict receipt and analysis validation.
- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Documents duplicate-aware decoding hooks and deterministic serialization controls for canonical analysis records.
- [Configuration — Pydantic](https://docs.pydantic.dev/latest/api/config/) — Covers strict models, forbidden extra fields, enum handling, and frozen instances for closed versioned schemas.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Documents SHA-256 and file-digest APIs used to bind receipts, snapshots, briefs, and closure evidence to exact content.
- [fcntl — The fcntl and ioctl system calls](https://docs.python.org/3.13/library/fcntl.html) — Documents advisory flock semantics underlying the durable roadmap writer guard and coherent snapshot boundary.
- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Covers exclusive file creation, hard links, fsync, and atomic replacement needed for immutable all-or-nothing evidence publication.
- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Explains scoped dependency replacement for interleaving, changed-snapshot, write-failure, and forbidden-side-effect tests.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Receipt creation, selector/reason capture, or changes to the receipt-only command; `roadmap-structural-revision-escalation` owns those.
- Invoking or changing broad `--from-stage` generation, prompts, retries, timeouts, or publication semantics.
- Same-artifact structural patching, cross-artifact patching, multi-file transactions, seed invalidation, or feedback-state transitions.
- Backend calls, model-selected scope, relation inference from prose, and a generic artifact graph unrelated to roadmap semantics.
- Replacing the existing writer boundary or extending it to arbitrary external filesystem readers and writers.
- Refactoring canonical artifact schemas, broad generation, seed machinery, or unrelated views for uniformity.

## Risks

- **A reason becomes inferred scope:** reviewer prose and reason never add relations. An uncorroborated `cross-artifact-impact` reason only prevents a same-artifact route and produces a durable no-route result.
- **Mixed evidence looks current:** the selected receipt predicate, full current-state `predecessor=None` gate tuples (including predecessor-independent integrity checks), exact raw source-record digest, and broad-equivalent brief digest consume the same captured bytes and are rechecked before publication; a changed snapshot is transient `invalid`.
- **A stored analysis becomes authority:** closed identity, exact final-byte equality between the supplied record and recomputed current candidate, selected-closure-safe relation identifiers, and live recomputation under the reader snapshot guard precede every rendered route. A parser-valid stale or substituted record cannot authorize a command.
- **A no-route result is mistaken for a failure:** route class, publication outcome, and process status remain separate. A durable `requires-scope-review` result is a successful (`0`) completed analysis with no workflow, not a collision, preflight rejection, or automatic broad fallback.
- **Telemetry is mistaken for evidence:** lifecycle records observe a durable final but do not validate it. An append failure after publication exits with no route and recovers only through exact retry/reuse validation; it never writes an event claiming its own failed append succeeded.
- **The writer boundary cannot provide a coherent snapshot:** if the existing writer boundary cannot support the full staged-gate snapshot without widening the noncanonical write set, stop and record that platform boundary rather than offering optimistic route advice.

## Testing

Use fixture and interleaving tests to prove the closed design-only relation inventory: entity field, business-rule/workflow, decision, constraint, component, plan, ordering, and assumption fields participate with the named owner/direction/order; feedback and removal citations cannot change closure. Prove artifact-root and row-root expansion, bidirectional declared closure, stable ordering, receipt-reason non-expansion, and each route class's exact precedence. Prove that an unsafe or unmappable relation reached by the selected closure rejects analysis without persistence, while a disconnected unsafe inventory relation is neither emitted nor route-blocking. Cover full `predecessor=None` current-state gate tuples: prior-version comparisons are inert, while predecessor-independent removal and feedback-integrity failures still reject the snapshot. Cover every current-gate failure, an exact raw `source.json` byte change (including whitespace-only change), changed brief/snapshot before publication, and the fact that receipt selection consumes the captured selected-artifact bytes rather than a second read. Prove the complete admission verdict/fact matrix and that every append failure returns a redacted process outcome without a compensating event; only successfully appended interruptions have an interruption event. Prove an interleaved writer cannot change the inputs or evidence list between pure-view validation and rendering, while the reader guard grants no writer token and creates no evidence or telemetry. Prove the analysis semantic id/final equality, exact reuse, collision for every occupied nonmatching final, transient-invalid versus durable-no-route distinction, null workflow behavior, independent route and publication facts for created and reused scope-review records, the closed creation `0`/`1`/`2`/`130` status map, the read-only view `0`/`2` map, exact-retry reuse after terminal telemetry failure or interruption, and that parsing plus exact recomputed canonical candidate bytes/final name precede every rendered route. CLI coverage proves both exact command forms, every rejected companion, unchanged existing-mode parsing, no backend or canonical write, and log-free inspection. The seed does not name test paths, test cases, or existing suites.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (refactor) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (feature) — tests covering the behavior this step changes; green before completion.
- step 8 (feature) — tests covering the behavior this step changes; green before completion.
- step 9 (feature) — tests covering the behavior this step changes; green before completion.
- step 10 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A current exact receipt and coherent roadmap/brief snapshot that passes every `predecessor=None` current-state gate tuple produce one deterministic declared closure and exactly one route class; its source-record digest is SHA-256 of the exact raw `source.json` bytes, while its brief digest remains broad-equivalent decoded text.
- Artifact targets root at every stable selected-artifact row, row targets root at their exact row, and closure follows both directions of the closed design-only field inventory without using reason, prose, feedback, or removals to add an artifact.
- Every route class has its documented producer, persistence, nullable workflow field, precedence, and no-route or named follow-on exit; `cross-artifact-impact` without a corroborating multi-artifact closure is durable `requires-scope-review`.
- Malformed, unsupported, mismatched, stale, substituted, unreadable, changed, noncanonical, gate-invalid, or selected-closure-unsafe receipt/snapshot/brief/analysis inputs never route or expose a partial analysis. Disconnected unsafe relation inventory cannot block a safe selected closure or escape the relation engine. Invalid creation is transient; valid no-route analysis is complete and immutable.
- Each stored analysis has one exact safe receipt/snapshot/closure semantic identity and opaque final name; exact final bytes reuse, every other occupied final collides, and a view renders a route only after recomputed canonical candidate bytes and semantic final exactly match the supplied record under reader coordination without logging or creating evidence.
- A durable route class and immutable publication outcome remain distinct creation facts; every durable `requires-scope-review` result returns status `0` with a null workflow, while invalid/recheck, collision, write, usage, and interruption creation paths follow the closed `1`/`2`/`130` status map. Completed read-only inspection returns `0` for every rendered evidence state and `2` only for usage conflicts.
- The command writes only the declared analysis, telemetry, and participating writer lock; it invokes no backend and changes no canonical or reviewer-owned state.
- `--analyze-escalation RECEIPT_FINAL` and `--view impact-analyses` have the closed exclusive behavior above, while all existing receipt, same-artifact, cross-artifact, seed, view, and broad workflows retain their contracts.
- Named follow-on workflows can require a current analysis as an additional admission artifact without changing existing writer or broad-command behavior.

## Deferred

- A safe broad-stage recommendation belongs to a later evidence-backed plan; this analysis routes to workflows rather than commands.
- `roadmap-cross-artifact-revision-transaction` owns a later multi-file writer and recovery journal after a `cross-artifact` analysis becomes admissible.
- If real receipts do not yield a relation-complete cross-artifact case, keep the transaction seed dormant.
