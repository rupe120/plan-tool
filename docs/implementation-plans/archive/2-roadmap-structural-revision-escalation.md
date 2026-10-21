> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap Structural Escalation Receipt
intent: '`plan-tool roadmap` will provide an explicit, receipt-only record for one
  selected feedback row that cannot safely use bounded local revision. Given an artifact-qualified
  open row and an operator-selected structural reason, it will persist immutable noncanonical
  evidence of the selected artifact, target, reason, and current raw selected-artifact
  digest, then direct the operator to scope review. It will not infer a relation closure,
  select a broad route, invoke a backend, or rewrite a roadmap artifact, seed, feedback
  row, or Git state.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Extract behavior-preserving shared feedback selector primitives
  intent: Move existing selector parsing and lookup rules behind a shared boundary,
    including typed internal syntax-versus-stage outcomes and its colon-free feedback-id
    grammar, while preserving local revision eligibility, public verdicts, and writes.
  files:
  - plan_tool/roadmap_revision.py
  - tests/test_roadmap_revision.py
  creates:
  - plan_tool/roadmap_feedback.py
  - tests/test_roadmap_feedback.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/roadmap-structural-revision-escalation/01-extract-behavior-preserving-shared.md
  status: done
- id: 2
  title: Define strict receipt selection, canonicality, and reason capture
  intent: Define one total, selected-artifact-only receipt-selection predicate through
    the extracted selector boundary, enforce receipt-safe routing identifiers and
    one raw-byte render-canonical snapshot, and record one closed reason without changing
    the roadmap-wide identifier or local revision grammar.
  files:
  - plan_tool/roadmap_feedback.py
  - tests/test_roadmap_feedback.py
  creates:
  - plan_tool/roadmap_escalation_selection.py
  - tests/test_roadmap_escalation_selection.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Supplies shared selector parsing, typed syntax-versus-stage facts, and lookup
      facts.
  detail: docs/implementation-plans/plan-details/roadmap-structural-revision-escalation/02-define-strict-receipt-selection.md
  status: done
- id: 3
  title: Define versioned, redacted immutable receipts for one selected artifact
  intent: Bind a duplicate-member-free schema version 1 and one deterministic receipt
    identity and final name to roadmap-root-relative selector-derived artifact facts
    without trusting a stored path or inferring wider impact.
  files:
  - plan_tool/roadmap_artifacts.py
  - tests/test_roadmap_artifacts.py
  creates:
  - plan_tool/roadmap_escalation.py
  - tests/test_roadmap_escalation.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: Supplies the live, canonical selected-row and reason facts the receipt records.
  detail: docs/implementation-plans/plan-details/roadmap-structural-revision-escalation/03-define-versioned-redacted-immutable.md
  status: done
- id: 4
  title: Map immutable-evidence storage results to redacted receipt lifecycle evidence
  intent: Use the prerequisite's opaque immutable-evidence API to publish or validate
    one receipt and make every receipt-specific outcome observable without recording
    reviewer content, with one explicit process-status map and a fixed retryable result
    when telemetry itself is unavailable.
  files:
  - plan_tool/run_log.py
  - tests/test_run_log.py
  - DATA_CONTRACT.md
  creates:
  - plan_tool/roadmap_escalation_run.py
  - tests/test_roadmap_escalation_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: Supplies the receipt identity, schema, roadmap-root-relative selector-derived
      path, and redaction boundary; the implemented immutable-evidence-storage prerequisite
      supplies the opaque durable-storage API.
  detail: docs/implementation-plans/plan-details/roadmap-structural-revision-escalation/04-map-immutable-evidence-storage-results.md
  status: done
- id: 5
  title: Extract behavior-preserving roadmap command-mode parsing
  intent: Replace parser-level broad-mode exclusion with one explicit compatibility
    boundary that preserves well-formed non-receipt usage output and status while
    retaining receipt-option occurrences for the following receipt wiring step.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/roadmap-structural-revision-escalation/05-extract-behavior-preserving-roadmap.md
  status: done
- id: 6
  title: Wire exclusive escalation creation and log-free receipt views
  intent: Let operators create and inspect receipts while rejecting partial, repeated,
    or well-formed conflicting modes and every receipt-view modifier before any broad
    roadmap dispatch or receipt view, then re-run the total receipt-selection predicate
    before any handoff.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/cli/__init__.py
  - tests/cli/test_roadmap_cmd.py
  - tests/cli/package_surface_help.golden.txt
  - docs/cli/roadmap.md
  - CAPABILITIES.md
  complexity: high
  change_type: feature
  depends_on:
  - 4
  - 5
  depends_on_notes:
    4: Supplies the receipt runner and typed lifecycle result used by CLI integration.
    5: Supplies compatible raw broad-mode and receipt-option occurrence state.
  detail: docs/implementation-plans/plan-details/roadmap-structural-revision-escalation/06-wire-exclusive-escalation-creation-log.md
  status: done
- id: 7
  title: Document escalation receipts, scope-review handoff, and the no-write boundary
  intent: Make the receipt schema and deferred impact-routing boundary discoverable
    without presenting supporting evidence as a fifth canonical roadmap artifact.
  files:
  - ROADMAP_FORMAT.md
  - tests/test_roadmap_format.py
  - README.md
  - CLAUDE.md
  - docs/ARCHITECTURE.md
  - docs/ROADMAP_WALKTHROUGH.md
  - RUNBOOK.md
  - TESTING.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 3
  - 4
  - 6
  depends_on_notes:
    3: Provides the persisted receipt fields, schema version, and identity rule.
    4: Provides the redacted creation lifecycle and immutable-publication contract.
    6: Provides the final command forms, view outcomes, and log-free behavior.
  detail: docs/implementation-plans/plan-details/roadmap-structural-revision-escalation/07-document-escalation-receipts-scope.md
  status: done
---
# Roadmap Structural Escalation Receipt

## Overview

`plan-tool roadmap` adds an explicit, receipt-only escalation record for one artifact-qualified feedback row that cannot safely use bounded local revision. It records a schema-versioned selected-row identity and state, canonical target, operator-selected reason, selector-derived artifact path and raw-byte digest, and a `requires-scope-review` handoff. It uses the prerequisite `roadmap-immutable-evidence-storage` for immutable noncanonical storage rather than defining filesystem safety inside the receipt command. Creation writes only the declared immutable receipt and creation-command telemetry. Pure inspection is read-only, including an empty evidence namespace: it never creates storage or telemetry, rewrites a roadmap artifact, seed, feedback lifecycle state, draft, or Git state, invokes a backend, or starts broad revision.

The `roadmap-immutable-evidence-storage` prerequisite supplies that closed API.
This plan's seven-step detail bundle has executed to completion; the receipt
runner consumes the prerequisite API and does not recreate its filesystem
protocol.

## Problem statement

The narrowed `roadmap-incremental-revision` path is safe because it has a closed write set: one existing artifact, one target row, a few scalar presentation fields, and one proposed feedback response. Structural requests can affect prose, row membership, relations, decisions, or multiple artifacts, so silently widening the local command would remove its central safety guarantee. A receipt makes that boundary visible without pretending an operator-selected reason proves a complete impact set or safe broad route.

## Architecture

Step 1 extracts the existing local-revision selector parsing and lookup behavior and exposes typed internal outcomes for malformed selector syntax and an unknown configured stage; its local-revision adapter preserves the existing public `RevisionContractError` surface and messages. Step 2 adds receipt-only selection on that boundary: creation accepts exactly one `<artifact>:<feedback-id>` selector in that shared grammar plus one `--escalation-reason`. The artifact key is one configured stage key and the feedback id is its original, nonblank-after-trimming, colon-free identifier. Receipt admission additionally requires every persisted or logged routing identifier—the selector artifact key and feedback id, and any selected row-target id—to be a `receipt-safe-id`: ASCII `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`. That closed receipt-only grammar prevents reviewer prose from becoming evidence; it does not change the roadmap-wide row-id grammar or local-revision behavior. The receipt runner maps the two step-1 types to `malformed-selector` and `unknown-artifact` without inspecting error text. After both succeed, receipt-safe selector admission is an outer preflight: an unsafe selector reaches `identifier-rejected` before reason validation, source access, feedback cardinality, or any resolved field is logged. An unsafe parsed row-target id reaches the same redacted rejection only within the later selected-artifact predicate, before the target is recorded. Creation, receipt parsing, reuse, and views reject a stored value outside the receipt-safe grammar. It reads the selector-derived artifact once as raw bytes, decodes those bytes as strict UTF-8, parses that exact text, and compares the renderer's UTF-8 bytes with the same raw snapshot.

Receipt selection is one total predicate over that selected artifact alone; it never reads another canonical artifact to decide whether the target exists. It runs only after outer selector admission and source readability/canonicality, then checks the selected feedback id's cardinality, reuses the established local-revision order of state before response, and validates the parsed target. A missing or malformed target is an artifact-shape failure and reaches `artifact-unparsable` before this predicate. Its ordered rejection vocabulary is `missing-feedback`, `duplicate-feedback`, `not-open`, `already-responded`, `identifier-rejected`, `missing-or-ambiguous-target`, and `target-not-live-in-selected-artifact`; within this predicate, `identifier-rejected` means only an unsafe parsed row target. A valid row is `open`, unanswered, and targets either the selected artifact or exactly one live row in it. An artifact target has `target_id` equal to the selector artifact key. A parsed row target whose id is not receipt-safe is `identifier-rejected`; one that is receipt-safe but resolves zero times in the selected artifact, including a removed or unknown row, is `target-not-live-in-selected-artifact`. The predicate does not determine whether another artifact contains the id. A parsed receipt-safe row target that resolves more than once is `missing-or-ambiguous-target`. It may be ineligible for local revision because local field allowlists never govern receipt creation.

The closed reason vocabulary is `prose`, `row-structure`, `collection-structure`, `relationship-semantics`, `decision-semantics`, and `cross-artifact-impact`. A receipt records that reason exactly as chosen; it does not classify feedback prose, infer relations, or choose another workflow. Every reason exits through `requires-scope-review`, whose consumer is the operator or the separate `roadmap-escalation-impact-routing` analysis. Receipt creation does not treat a stale receipt as a selector error: live freshness is an inspection result.

Version 1 has one exact, closed JSON object schema. Before schema or semantic-id validation, its JSON decoder rejects a duplicate member name at every object level, including `selector`, `target`, and `source`; it never silently retains a last duplicate value. Every listed object is also closed: it admits no extra key, no omitted required key, no floating-point value, and no alternate representation.

| Key | Type and closed value | Semantic preimage |
| --- | --- | --- |
| `schema_version` | JSON integer `1` | Included |
| `selector` | Object `{artifact_key, feedback_id}`: both satisfy `receipt-safe-id`; `artifact_key` is one fixed stage key and `feedback_id` also satisfies the extracted shared grammar | Included |
| `feedback_state` | String `open` | Included |
| `target` | Object `{kind, id}`; `kind` is `artifact` or `row`; `id` satisfies `receipt-safe-id`, using the selector artifact key for `artifact` | Included |
| `reason` | One member of the closed reason vocabulary | Included |
| `source` | Object `{relative_stage_path, sha256}`; `relative_stage_path` is the selected configured stage's `artifact_path`, relative to `roadmap_dir(plans_dir, slug)` (`<plans-dir>/roadmaps/<slug>`), rendered as normalized POSIX with no leading slash or dot component; `sha256` is 64 lowercase hex over the raw selected-artifact bytes | Included |
| `handoff` | String `requires-scope-review` | Included |
| `semantic_id` | 64 lowercase hex equal to the preimage digest | Excluded; derived |
| `created_at` | UTC RFC 3339 timestamp to whole seconds, rendered as `YYYY-MM-DDTHH:MM:SSZ` | Excluded; observational |

The semantic id is the lowercase SHA-256 hex digest of UTF-8 canonical JSON over exactly the seven Included keys above. Canonical JSON sorts object keys lexicographically, preserves recorded array order, uses `separators=(",", ":")`, emits strings as their original Unicode code points with `ensure_ascii=False` and no Unicode normalization, and admits no floating-point values. It is computed only from duplicate-member-free decoded values. The receipt and redacted telemetry may carry only resolved `receipt-safe-id` selector and target identifiers because routing requires them. They never record raw selector or reason input, feedback request, target-row prose, artifact body, relation information, source brief, seed content, or repository code. Creation derives `relative_stage_path` by taking the selector's configured stage `artifact_path` relative to `roadmap_dir(plans_dir, slug)` and rendering its POSIX form before recording it; inspection recomputes that same value first and never lets stored content select a filesystem path.

The prerequisite owns the fixed `<roadmap-dir>/.plan-tool/evidence/escalations` namespace, private temporary publication, durable exclusive final creation, matching final-name enumeration, and opaque existing bytes. The receipt runner supplies only the sealed `ESCALATIONS` namespace, the candidate's 64-lowercase-hex semantic-id final name, and a complete schema-valid payload. Candidate validation binds the computed semantic digest, the stored `semantic_id`, and the requested final name to one exact value before publication. It maps prerequisite `created`, `existing`, `invalid-input`, and `write-failed` results to receipt lifecycle outcomes. `invalid-input` produces redacted `storage-rejected`; `write-failed` retains its same-named terminal outcome. An `existing` result is `reused` only when its storage final name, stored semantic id, exact v1 semantic preimage, and selector-recomputed roadmap-root-relative path all match the candidate; a valid different preimage with the same semantic id is `collision`; and an unreadable, duplicate-member, schema/id/path-invalid, or final-name-mismatched existing payload is `invalid-existing-receipt`. The runner never redefines or bypasses the prerequisite's storage protocol.

`--view escalations` receives matching final-name enumeration and opaque bytes only from the prerequisite. A missing namespace is an empty read and creates no directory. An enumeration `write-failed` renders the log-free `storage-unavailable` result with no receipt, handoff, or trusted field, and exits through the normal completed-view path. For each returned opaque record, the view accepts only duplicate-member-free closed schema version 1 bytes, including `receipt-safe-id` selector and target identifiers, then validates that the enumerated final name, stored semantic id, recomputed semantic id, and selector-recomputed path relative to `roadmap_dir(plans_dir, slug)` agree. A malformed, duplicate-member, unsupported, identifier-invalid, semantic/final-name-mismatched, or path-substituted receipt remains visible as `invalid` evidence with no handoff; an invalid view exposes only safe status and escaped relative storage-location metadata, never any stored receipt field. A missing or otherwise unreadable selector-derived source is the distinct `source-unavailable` result; it keeps the receipt visible but suppresses the handoff. Once the source's bytes can be read (whether or not they decode or parse), every other way the escalation has moved on — non-UTF-8 or unparsable current bytes, a parseable but noncanonical current source, a render-canonical source whose raw digest has changed, a rejection from the complete receipt-selection predicate, or a stored target that no longer matches the re-derived target — collapses into one `resolved` result: no handoff, and only the receipt's identity, selector, reason, and creation time are shown. Receipt views, including `storage-unavailable`, `invalid`, `resolved`, `source-unavailable`, and `fresh` views, create no run log.

Before a receipt may be reused or displayed as valid, its selected feedback target is re-derived from the current selector-derived source; a stored target that differs from that re-derived target is `resolved`, with no handoff. A current source must be render-canonical before its digest can establish freshness: a changed canonical source, or a parseable noncanonical source, is likewise `resolved`. Source unavailability remains distinct and never grants a handoff.

Creation is exclusively one `--escalate-feedback SELECTOR` and one `--escalation-reason REASON`; inspection is exclusively one `--view escalations`. Any receipt entry—either creation flag or a receipt view—first calls `roadmap_dir(plans_dir, slug)` as a pure root validation. An invalid slug is a standard log-free usage error with status `2`; it creates no lifecycle event or run log and touches no source or evidence storage. This root-eligibility check outranks every creation-preflight row, including a mode conflict, because no safe lifecycle or evidence namespace exists otherwise.

Step 5 removes parser-level broad-mode exclusion while preserving receipt-option and `--view` occurrence state, then reproduces the current well-formed non-receipt usage output and status before any dispatch. It leaves `argparse` closed validation for `--view`, `--mode`, and integer `--from-stage` intact. Step 6 receives that compatible parser state and treats one or more well-formed `--apply`, `--refresh-seeds`, `--accept-seed`, `--materialize`, `--from-stage`, or `--view` companions beside either creation flag as row-1 `mode-rejected`. A companion value rejected by its own `argparse` `choices` or `type=int` validation is instead a standard log-free usage error with status `2`, even beside a creation flag: it never reaches root validation, receipt preflight, a run log, or storage. If neither creation flag appears, command dispatch preserves the current broad-mode mutual-exclusion usage rejection before any side effect.

A repeated creation option is a row-1 `mode-rejected` creation preflight with one redacted event pair. With no creation flag, repeated existing view values that contain no `escalations` preserve the current final-value behavior; a repeated `--view` whose occurrences include `escalations` is instead a standard log-free usage error before storage, so receipt inspection remains singular. A pure receipt inspection also rejects `--mode`, `--id`, `--from-existing`, `-y`, `--revise-feedback`, `--apply`, `--refresh-seeds`, `--accept-seed`, `--materialize`, and `--from-stage` before it loads storage. Existing non-receipt views retain their own `--mode` and `--id` rules. If either creation flag appears beside any well-formed `--view`, creation preflight owns the command: row 1 returns `mode-rejected`, records its one redacted preflight and `preflight-rejected` terminal event, and neither loads storage nor renders a view. The following ordered creation-preflight table decides the one result for every overlapping well-formed invalid creation input after root eligibility succeeds. Each rejected row emits one `preflight-rejected` terminal result; fields not resolved before its row remain null, raw input is never logged, and a reason is logged only after it is a closed value.

| Precedence | Decisive condition | Preflight verdict | Permitted resolved fields |
| --- | --- | --- | --- |
| 1 | The creation pair is incomplete or repeated, either creation flag appears with any well-formed `--view`, or either appears with `--revise-feedback`, well-formed `--from-stage`, `--apply`, `--refresh-seeds`, `--accept-seed`, `--materialize`, `--from-existing`, `-y`, well-formed `--mode`, or `--id` | `mode-rejected` | None |
| 2 | The mode is valid but the selector is malformed or names an unknown fixed stage key | `malformed-selector` or `unknown-artifact` | None |
| 2b | The parsed selector contains an artifact key or feedback id outside `receipt-safe-id` | `identifier-rejected` | None |
| 3 | The receipt-safe selector is valid but the reason is not closed | `reason-rejected` | Selector artifact key and feedback id only |
| 4 | The reason is valid but the raw selected-artifact snapshot is missing, unreadable, or non-UTF-8 | `artifact-unreadable` | Selector and closed reason only |
| 5 | The raw snapshot is readable but parser or render-byte canonicality fails | `artifact-unparsable` or `artifact-not-canonical` | Selector, closed reason, raw digest; target is null |
| 6a | The canonical selected artifact has no row with the feedback id | `missing-feedback` | Selector, closed reason, raw digest |
| 6b | The canonical selected artifact has more than one row with the feedback id | `duplicate-feedback` | Selector, closed reason, raw digest |
| 6c | The unique selected row is not `open` | `not-open` | Selector, closed reason, raw digest |
| 6d | The unique open selected row has a non-null proposed response | `already-responded` | Selector, closed reason, raw digest |
| 6e | The selected row's parsed row target is outside `receipt-safe-id` | `identifier-rejected` | Selector, closed reason, raw digest; target is null |
| 6f | The selected row's parsed receipt-safe row target resolves more than once in the selected artifact | `missing-or-ambiguous-target` | Selector, closed reason, raw digest |
| 6g | The selected row's parsed receipt-safe row target resolves zero times in the selected artifact | `target-not-live-in-selected-artifact` | Selector, closed reason, raw digest |
| 7 | Every preceding check succeeds | `accepted` | Selector, closed reason, raw digest, and re-derived target |

Telemetry availability gates receipt publication. The runner must successfully open the redacted `RunLogWriter` and append the preflight event before it calls the immutable-evidence helper; a setup or preflight-append failure blocks publication and returns the fixed redacted `telemetry-unavailable` process failure. An interruption before `RunLogWriter.start` returns produces status `130`, no receipt publication, and no promised receipt preflight/result/run-end lifecycle. The existing generic writer may already have persisted its `run_start` or in-flight bookkeeping before that return; receipt creation neither treats that partial startup as a receipt lifecycle nor cleans it up. After startup returns, an interruption between successfully returned receipt lifecycle appends emits an all-null `interrupted` preflight before selection resolves, or preserves an earlier preflight verdict, then appends an `interrupted` terminal result and `run_end`. An interruption delivered inside a preflight or result append returns status `130` with null identity and handoff, emits no compensating receipt result or retry, and makes no exact-pair claim because the interrupted append may already have persisted its line; it still makes a best-effort generic `run_end` cleanup. An interruption delivered inside the trailing `run_end` append is different: the result event already durably logged the real outcome, identity, and handoff immediately before `run_end` runs, so the runner returns that already-logged result unchanged — its real status and, for `created` or `reused`, its real identity and handoff — instead of fabricating a `130` `interrupted` outcome the operator never received. If a helper call or later post-preflight work may have made the final durable, a preflight- or result-phase interrupted result still has null identity and handoff; retrying the identical request either creates a final or validates the existing final and records a complete `reused` lifecycle. A receipt-result or `run_end` append failure after a helper call can make the final durable, or any sink failure while recording an interruption, returns the fixed `telemetry-unavailable` failure without exception text, receipt identity, or handoff. The final may then exist, but the command never claims a completed lifecycle. `telemetry-unavailable` is a process result, not a persisted receipt terminal outcome, because its defining condition prevents reliable persistence.

After `RunLogWriter.start` returns, every root-valid creation whose sink persists its lifecycle and whose receipt event appends return normally records exactly one redacted preflight event, one terminal result event, and one matching `run_end`. `interrupted` is a closed preflight verdict for an interruption between lifecycle phases before selection resolves and a runner-owned terminal outcome in every interruption phase. Terminal outcomes are `preflight-rejected`, `storage-rejected`, `created`, `reused`, `collision`, `invalid-existing-receipt`, `write-failed`, and `interrupted`. Receipt id/digest are null until a durable `created` or validated `reused` result; every preflight- or result-phase interrupted invocation records null id/digest even when a final may require later reuse validation, while a `run_end`-phase interruption instead returns the already-logged terminal result's own id/digest whenever that result was `created` or `reused`. The full creation-log envelope—including `run_start` argv, flags, preflight, terminal event, run end, and failure paths—records only command/mode names, validated closed values, and resolved `receipt-safe-id` selector facts. It never records raw selector or reason input, exception prose, feedback request text, receipt rendering, target prose, or other reviewer content.

| Command result | Process exit status |
| --- | --- |
| Durable `created` or validated `reused` creation | `0` |
| Any `preflight-rejected` creation, including malformed, unsafe, repeated, or conflicting input | `2` |
| `storage-rejected`, `collision`, `invalid-existing-receipt`, or `write-failed` creation | `1` |
| `telemetry-unavailable` creation, whether or not its immutable final became durable | `1` |
| Runner-owned `interrupted` creation | `130` |
| Any completed `--view escalations` rendering, including empty, `storage-unavailable`, `resolved`, `invalid`, or `source-unavailable` evidence | `0` |
| Any receipt-entry usage error, including an invalid slug, a repeated `--view` containing `escalations`, or a prohibited modifier | `2` |

## Input

This plan consumes one selected feedback row, its selected canonical artifact, its receipt-safe target identifier, lifecycle state, and response-presence eligibility, one closed operator-selected reason, and one raw selected-artifact byte snapshot. The fixed stage map used to derive a selector's path and `roadmap_dir(plans_dir, slug)`, the named root for that relative path, are program configuration, not receipt input. Receipt entry validates that named root before any lifecycle, source, or storage action. The plan does not consume other canonical artifacts, relation graphs, source briefs, feedback prose, plan-seed drafts, repository code as receipt data, or backend output.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Covers paired and exclusive command modes.
- [Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/) — Covers strict versioned receipt validation and serialization.
- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Documents stable serialization for receipt identity.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Defines digest binding for selected-artifact freshness.
- [pytest: How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Supports no-backend and failure-path tests.
- [pytest: How to use temporary directories and files in tests](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — Supports receipt persistence and no-write boundary fixtures.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Relation closure, cross-artifact impact analysis, coherent four-artifact or source-brief snapshots, route selection, and broad-command recommendations; `roadmap-escalation-impact-routing` owns those decisions.
- Backend-generated patches, model-selected impact sets, automatic broad revision, same-artifact structural patching, multi-artifact writers, and transaction or publication protocols.
- Editing roadmap prose; adding, removing, or reordering rows; changing relations or decisions; responding to or closing feedback; and updating reviewer-owned state.
- Changes to the local `--revise-feedback` allowlist, one-artifact atomic replacement behavior, conservative seed invalidation policy, or failure and recovery semantics.
- Changes to `--from-stage` prompt construction, full-stage output schema, retry behavior, timeouts, or broad-stage publication.
- Seed materialization, refresh, promotion, acceptance, Git commits, branches, pull requests, external tickets, or a general workflow system.
- Immutable-evidence publication internals, matching-final enumeration, durability, and private-temporary cleanup; `roadmap-immutable-evidence-storage` owns that fixed prerequisite boundary.
- A roadmap-wide row-identifier grammar or a local-revision compatibility change; receipt-safe identifier admission narrows only the persisted and logged receipt boundary.

## Risks

- **Silent widening of local revision:** structural work could escape the closed write set. The mitigation is a distinct receipt command that never invokes or changes the local writer.
- **A receipt becomes impact approval:** a reason or selected artifact could be mistaken for a complete scope. The mitigation is the sole `requires-scope-review` handoff and the explicit deferred analysis boundary.
- **Receipt substitution reads an arbitrary artifact or accepts invalid opaque evidence:** a self-consistent receipt could name a different source path, or an existing final could fail the closed receipt contract. The mitigation is a selector-recomputed POSIX path relative to `roadmap_dir(plans_dir, slug)`, exact computed/stored/final-name binding, receipt-side schema validation, and the implemented `roadmap-immutable-evidence-storage` fixed namespace boundary; every mismatch has no handoff.
- **Reviewer content leaks into evidence:** receipt or telemetry could expose feedback request or roadmap prose through an unrestricted id. The mitigation requires `receipt-safe-id` before any routing identifier is persisted or logged, then uses the closed redacted receipt schema, safe-metadata-only invalid views, and the complete run-log envelope—including startup argv and failure paths—with absence tests.
- **An invocation is silently reinterpreted or misclassified by automation:** argparse could collapse repeated receipt options, or lifecycle results could have no process status. The mitigation retains receipt-option cardinality before dispatch, rejects repeats at the receipt boundary, and maps every creation and view result to one exit status.
- **A parser refactor changes established roadmap behavior:** replacing the broad-mode group could alter a non-receipt command while adding no receipt value. The mitigation isolates compatibility parsing in step 5 and pins the existing well-formed non-receipt usage bytes and statuses before step 6 adds receipt dispatch.
- **An unvalidated slug escapes the telemetry root:** a receipt runner could open a run log before the roadmap path helper rejects a separator or parent component. The mitigation validates `roadmap_dir(plans_dir, slug)` in both CLI and runner before any log, source, or storage action; invalid receipt entries are log-free usage errors.
- **Telemetry failure or interruption leaves a durable receipt without trustworthy lifecycle evidence:** a log setup or append can fail, or an interruption can arrive during generic startup, between receipt lifecycle phases, inside a receipt-event append, during storage, or after publication. The mitigation blocks publication until startup and preflight telemetry succeed, treats pre-return generic startup bookkeeping as neither a receipt lifecycle nor a receipt-cleanup responsibility, gives between-phase interruption its precise redacted terminal sequence, makes an append-interrupted line incomplete rather than retrying or duplicating it, returns the fixed redacted `telemetry-unavailable` status when the sink cannot record a later sequence, and makes retry validate an existing final before a complete `reused` lifecycle.
- **Concurrent creation or host failure falsifies immutable evidence:** two creators could observe an absent name, or a crash could acknowledge receipt bytes before they are persistent. The mitigation is the prerequisite's immutable-evidence result contract; this runner maps only its completed storage results and never publishes files itself.
- **Freshness evidence becomes unusable:** a selected artifact can disappear, become unreadable, fail to decode or parse, or remain parseable but cease to be render-canonical after receipt creation. The mitigation is the visible `source-unavailable` no-handoff result when the source's bytes cannot be read at all, distinct from the `resolved` no-handoff result covering every readable source that no longer matches — undecodable, unparsable, noncanonical, stale, selection-ineligible, or target-mismatched.
- **A pure inspection writes state or hides a storage failure:** a first view could create an empty namespace, or a failed enumeration could look like no receipts. The mitigation is the helper's read-only empty listing and the visible, log-free `storage-unavailable` result with no trusted receipt or handoff.

## Testing

Use unit, CLI, and fixture tests for shared-selector extraction that preserves local revision while exposing typed malformed-syntax and unknown-stage outcomes; one strict-UTF-8 raw-byte snapshot through parse, canonical render comparison, digest, receipt, and freshness view (including CRLF); every receipt-only selector, artifact-unreadable/unparsable/canonicality, and paired-option verdict; parser-invalid target shape before any parsed-target verdict; receipt-safe identifier acceptance and rejection for selector, artifact target, and row target, including selector rejection before reason or source access; the total selected-artifact-only feedback/target order for a safe selector, including state-before-response and every overlap; every reason value; exact schema version 1 key/type/value validation, including stored colon-bearing or receipt-unsafe selector/target rejection, duplicate-member rejection at every nested object level, unknown-field rejection, and every unsupported shape; canonical-JSON semantic-id preimage validation including unescaped Unicode, exact computed/stored/final-name binding, and a selector-recomputed POSIX source path relative to `roadmap_dir(plans_dir, slug)`; artifact-target and row-target identity; selector-derived path mismatch; identity/reuse/collision/invalid-existing-receipt; live selected-artifact freshness and target re-binding; `source-unavailable`; `resolved`; `storage-unavailable`; redaction; receipt-aware preflight precedence for every well-formed broad-mode combination; byte-for-byte and exit-status-compatible non-receipt broad-mode usage errors; malformed companion usage before root validation; repeated creation options, repeated ordinary views that retain their final value, and repeated views containing `escalations` that reject; receipt-view modifier rejection; slug rejection before any log, source, or storage access; telemetry setup/preflight/terminal failure recovery; interruption during generic startup with no promised receipt lifecycle, between lifecycle phases, and inside each receipt-event append; telemetry nullability; and every process exit-status row. Tests prove a locally ineligible but live row can obtain a receipt; absolute, relative, and dot-normalized representations of the same `plans_dir` yield the same source path and semantic id; malformed, colon-bearing, receipt-unsafe, duplicate-member, noncanonical, semantic/final-name-mismatched, path-substituted, target-mismatched, unsupported, or unknown-field evidence is `invalid`, while stale or selection-ineligible readable evidence is `resolved`; source-unavailable or storage-unavailable evidence never hands off. Accepted evidence and telemetry retain only resolved receipt-safe selector/target identifiers, never feedback request or target prose; invalid receipt slugs and malformed companion values leave no run-log or evidence path at any location; pure views remain log-free and leave a missing namespace absent; and no normal or error path invokes a backend or changes canonical, reviewer-owned, seed, draft, or Git state.

Creation fixtures exercise one accepted event pair and one `preflight-rejected` pair for every precedence row and every existing well-formed `--view` value, including overlapping invalid mode, selector, and reason inputs. They cover every pair and higher-cardinality combination of well-formed broad modes with a creation flag, asserting one event pair rather than parser rejection, and the same broad combinations without a creation flag, asserting the unchanged log-free mutual-exclusion usage error. A frozen compatibility fixture compares parser output and status for well-formed non-receipt commands before and after step 5. The shared selector fixture distinguishes malformed syntax and unknown stage through typed internal outcomes while the local-revision adapter preserves its existing error surface; receipt creation maps those outcomes to rows 2 and 2b without reading error text. Malformed `--view`, `--mode`, and `--from-stage` companions beside creation prove argparse's own standard log-free usage rejection before root validation, the runner, or storage. A syntactically valid but receipt-unsafe selector proves row 2b wins before reason validation, source access, candidate cardinality, or row state; only a receipt-safe selector enters the selected-artifact predicate. Repeated creation options prove that receipt preflight wins, writes one redacted event pair, and reaches neither storage nor a view renderer; repeated ordinary views without `escalations` preserve their current final value, while any repeated view containing `escalations` is a standard log-free usage rejection before storage. CLI and direct-runner fixtures use separator and parent-component slugs, asserting status `2` with no run log, source read, or storage access. Pure receipt-view fixtures reject every listed modifier and action option before storage access and prove that existing non-receipt view modifiers remain unchanged. Sink-failure fixtures inject `RunLogWriter.start`, preflight append, receipt-result append, and `run_end` failures: the first two block publication, the latter two return only redacted `telemetry-unavailable` status `1`, and retrying a durable final produces one complete validated `reused` lifecycle. Interruption fixtures distinguish generic writer startup bookkeeping from receipt telemetry: an interruption before `start()` returns publishes no receipt and has no promised receipt event pair; an interruption between successfully returned lifecycle appends records the all-null or preserved-preflight `interrupted` sequence; and an interruption inside a preflight or result append returns status `130` with null identity/handoff, emits no compensating receipt result, and makes no exact-pair claim while still completing generic writer cleanup. An interruption inside the trailing `run_end` append instead returns the already-logged terminal result unchanged. They assert `run_start` and every later receipt event omit raw selector/reason input, exception prose, feedback request text, target prose, receipt rendering, and repository content, while accepted events carry only resolved receipt-safe fields. Integration tests supply every prerequisite storage result: `existing` becomes `reused`, `collision`, or `invalid-existing-receipt` only after receipt validation and final-name binding; `invalid-input` becomes `storage-rejected`; `write-failed` never reports `created`; and a runner interruption emits the redacted `interrupted` outcome with null id/digest. Failed prerequisite enumeration renders only the log-free `storage-unavailable` view result. Duplicate-member existing payloads—including a suppressed first `reason` or a nested-object duplicate—and semantic/final-name-mismatched payloads are invalid on reuse and view and disclose no receipt field. The prerequisite owns filesystem interleavings, durable publication, read-only empty enumeration, and matching-final enumeration tests; invalid receipt views disclose only safe metadata.

## Acceptance criteria

- Unchanged local-revision selector behavior survives step 1 extraction. After closed selector syntax and fixed-stage recognition, a receipt-safe selector check rejects an unsafe selector as `identifier-rejected` before reason validation, source access, feedback cardinality, or row state; its unsafe values are never recorded. A receipt then uses one strict-UTF-8 raw selected-artifact snapshot for parse, render-byte canonicality, digest, persistence, and freshness. Parser-invalid target shape is `artifact-unparsable`; for a receipt-safe selector, the total receipt-selection predicate then reads only that artifact and chooses its one parsed-target verdict in order, checks state before response, and never looks in another artifact for a row target. An unsafe parsed row target is `identifier-rejected` without recording that target identifier. A live render-canonical selected feedback row and one closed reason produce one deterministic, schema-version-1, redacted receipt whose semantic id excludes itself and creation time and includes the selected stage path relative to `roadmap_dir(plans_dir, slug)` as normalized POSIX, raw-byte selected-artifact digest, receipt-safe selector/target identifiers (selector artifact key for artifact targets, row id for row targets), and `requires-scope-review`; its canonical JSON sorts keys, uses compact separators, and emits unescaped Unicode code points.
- Every receipt entry validates `roadmap_dir(plans_dir, slug)` before it opens a log, reads a source, publishes, or scans. An invalid slug returns log-free usage status `2`, with no lifecycle event, run log, source read, or storage access; the runner repeats the pure check so direct callers cannot bypass the CLI.
- Every closed selector verdict, reason, repeated creation option, creation flag beside any well-formed `--view`, and partial/conflicting well-formed command-mode rejection occurs before receipt publication, backend invocation, or broad dispatch, and emits exactly one redacted preflight plus one `preflight-rejected` terminal result. The parser compatibility step keeps well-formed broad-mode combinations available for that precedence decision and preserves the current non-receipt usage bytes and status; a malformed `--view`, `--mode`, or `--from-stage` value remains argparse's standard log-free usage error, even beside creation. Repeated non-receipt views that contain no `escalations` retain their current final value; a repeated view containing `escalations` is the standard log-free usage error before storage.
- A pure `--view escalations` accepts no modifier or action option: `--mode`, `--id`, `--from-existing`, `-y`, `--revise-feedback`, `--apply`, `--refresh-seeds`, `--accept-seed`, `--materialize`, and `--from-stage` fail before storage access with a usage error and no receipt event or run log. A missing evidence namespace is an empty read that creates neither evidence nor telemetry. When either creation flag appears beside any `--view`, the creation preflight instead emits exactly one redacted event pair and neither stores nor views a receipt. Existing non-receipt views preserve their documented modifier rules.
- The runner uses only completed results and opaque matching-final bytes from the implemented immutable-evidence-storage prerequisite; `invalid-input` is `storage-rejected`, and it cannot publish, overwrite, or enumerate a receipt file itself. Candidate computed semantic id, stored semantic id, and final name bind exactly. Identity reuses only a validated, durable final receipt, reports valid semantic-hash collisions separately from semantic/final-name-mismatched or otherwise invalid existing payloads, and never reports `created` after a storage failure. A preflight- or result-phase runner interruption is `interrupted` with null id/digest, not a helper storage result; a `run_end`-phase interruption instead returns the already-logged terminal result unchanged.
- A receipt runner publishes only after its redacted startup and preflight telemetry have persisted. An interruption before startup returns publishes no receipt and promises no receipt lifecycle; generic `RunLogWriter.start()` bookkeeping that may already persist remains outside the receipt contract. After startup, an interruption between successfully returned lifecycle appends records an all-null `interrupted` preflight/result/run-end sequence before selection or preserves the resolved preflight and records the same terminal pair. An interruption inside a preflight or result append returns status `130` with null identity/handoff, emits no compensating receipt result, and makes no exact-pair claim while it completes generic writer cleanup; an interruption inside the trailing `run_end` append instead returns the already-logged terminal result unchanged, since its outcome, identity, and handoff were durably recorded by the preceding result append. A setup or preflight-append failure returns fixed redacted `telemetry-unavailable` status `1` and blocks publication; a receipt-result or `run_end` append failure after publication, or any sink failure while recording interruption, returns the same status without a receipt identity, handoff, or exception text. A retry validates a durable final and records a complete `reused` lifecycle; the exact event-pair invariant applies only when the sink is available and each receipt-event append returns normally.
- A stored path that differs from the selector-recomputed stage path relative to `roadmap_dir(plans_dir, slug)` is invalid before any artifact read. A missing or otherwise unreadable selected source is the distinct `source-unavailable` result. Once the source's bytes can be read, every other way the escalation is no longer live — non-UTF-8 or unparsable current bytes, a changed render-canonical source, a parseable but noncanonical source, a selection-predicate rejection, or a target mismatch — is `resolved`, with no handoff. Malformed, unsupported, unknown-field, or path-mismatched receipt evidence has no handoff and an invalid view exposes only safe status and escaped relative storage-location metadata. A failed prerequisite enumeration is the log-free `storage-unavailable` view result with no trusted receipt or handoff.
- The closed receipt field set rejects duplicate JSON members before its schema or semantic-id checks. Its complete creation-log envelope permits only resolved receipt-safe selector/target identifiers and contains no raw selector/reason input, exception prose, feedback request, target-row prose, artifact body, relation data, source brief, seed content, or repository code. Pure receipt views create no run log.
- Created/reused receipt creation and every completed view exit `0`; all preflight and usage rejections exit `2`; `storage-rejected`, collision, invalid existing evidence, write failure, and `telemetry-unavailable` exit `1`; and an interrupted creation exits `130`.
- The command changes no canonical artifact, feedback state, seed state, draft, or Git file beyond the declared receipt and creation-command telemetry, and invokes no backend in normal or error paths.
- Documentation names the receipt schema, identity/freshness rule, exact command forms, `requires-scope-review` handoff, and deferred impact-routing boundary.

## Deferred

- `roadmap-escalation-impact-routing` owns relation closure, coherent roadmap/brief snapshots, impact route classes, and admission evidence for the same-artifact and cross-artifact workflows.
- `roadmap-same-artifact-structural-revision` owns one-artifact structural patching after a current receipt or later impact analysis is admissible.
- `roadmap-cross-artifact-revision-transaction` owns a recoverable multi-file writer after a current cross-artifact impact analysis is admissible.
