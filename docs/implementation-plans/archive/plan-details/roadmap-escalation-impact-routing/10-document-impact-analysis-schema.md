> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 10 — Document impact-analysis schema, freshness routes, and the noncanonical write boundary

## Summary

Document the impact-analysis contract across the roadmap format reference, operator guides, architecture reference, testing guide, and concise authoring guidance. Extend `ROADMAP_FORMAT.md` and `tests/test_roadmap_format.py` as the schema source and drift guard; keep each other document focused on its audience. The key decision is that immutable analysis evidence can report a current route but never becomes a canonical roadmap writer. Green means operators can find the exact commands, understand freshness and no-route results, and see precisely which writes creation may perform.

## Table of Contents

- [Summary](#summary) — The completed documentation outcome.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why receipt-only guidance no longer covers the operator path.
- [Input](#input) — The landed contracts this documentation step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The existing documentation and drift-guard files to update.
- [Implementation](#implementation) — Documentation ownership, schema, freshness, and write-boundary rules.
- [Tests](#tests) — Drift-guard cases and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary schema, JSON, hashing, and locking references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this documentation step.
- [Deferred](#deferred) — Follow-on work this step names but does not implement.

## Why

Current roadmap guidance ends at a structural-escalation receipt and manual scope review, while the landed analysis path will validate that exact receipt against current evidence before naming a follow-on workflow or deliberately returning no route. Without one clear documentation chain, operators can mistake a receipt reason for proven impact, treat immutable evidence as current forever, or assume analysis may start broad re-entry or mutate a roadmap.

## Input

- **Step 2 planned output (dependency):** After step 2 lands, use its ordered declared-relation closure from `plan_tool/roadmap_impact_relations.py`. Document its meaning as selected declared evidence only; do not describe reviewer prose or receipt reasons as closure inputs. This module does not exist at the current baseline.

- **Step 4 planned output (dependency):** After step 4 lands, use its coherent current-state snapshot and recheck outcome from `plan_tool/roadmap_impact_snapshot.py`. Describe the current-state guarantee, including distinct raw-source-record and decoded-brief digests, not its internal read sequence. This module does not exist at the current baseline.

- **Step 5 planned output (dependency):** After step 5 lands, read the closed schema, canonical renderer, parser, semantic-id rule, route classifier, and workflow mapping in `plan_tool/roadmap_impact_analysis.py` before documenting field names or examples. The landed code wins over this plan’s wording. This module does not exist at the current baseline.

- **Step 7 planned output (dependency):** Use the event vocabulary that step 7 adds to `plan_tool/run_log.py`: `RoadmapImpactPreflight`, `RoadmapImpactResult`, and `RunLogWriter.roadmap_impact_result`. Keep stored route class, immutable publication outcome, terminal lifecycle outcome, and return-only telemetry failure separate.

- **Step 9 planned output (dependency):** Use the final parser and dispatch behavior that step 9 adds to `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`, including `--analyze-escalation` and `--view impact-analyses`. Treat `docs/cli/roadmap.md` as step 9’s detailed flag reference; this step does not edit it.

- **Existing receipt baseline:** Preserve the distinction already enforced by `plan_tool/roadmap_escalation.py:EscalationReceipt`, `parse_receipt`, and `render_receipt`: a receipt stays separate immutable evidence and does not itself select a route.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — Add the code-backed impact-analysis reference, canonical example, route table, freshness meaning, command forms, and noncanonical boundary.
  - `tests/test_roadmap_format.py` — Extend the format drift guard for the landed analysis schema, example, command forms, route precedence, and write boundary.
  - `README.md` — Add concise analysis commands and route-boundary guidance to `## CLI usage` and `### 0. roadmap`.
  - `CLAUDE.md` — Update the concise roadmap description in `## What this is` so future authors know receipts can feed a separate analysis without becoming canonical writes.
  - `docs/ARCHITECTURE.md` — Extend `### Immutable roadmap evidence` with the analysis layer, current-state validation, separate namespace, reader coordination, and permitted writes.
  - `docs/ROADMAP_WALKTHROUGH.md` — Add the explicit receipt-to-analysis sequence to `## Command sequence at a glance` and `### Record structural feedback for explicit scope review`.
  - `RUNBOOK.md` — Add the analysis forms to the roadmap command table and revise the structural-feedback and `scope-review` workflows to distinguish a receipt from an analysis route.
  - `TESTING.md` — Add an impact-analysis test-layer map and the no-backend, no-canonical-mutation expectations.

## Implementation

- **Foundational logic — document one evidence-to-route path without granting write authority.** Describe an analysis as a separate immutable record built from one named receipt and current declared evidence. A reason requests review; it never expands the impact set or proves a route.

- **Make `ROADMAP_FORMAT.md` the schema owner.** Extend its source-of-truth banner and add a dedicated analysis reference beside `## Structural escalation receipts`. Read the exact field inventory from the landed `plan_tool/roadmap_impact_analysis.py:ImpactAnalysis` contract, then show the closed field set, canonical JSON rules, semantic-id/final-name relationship, redaction limits, and one parseable canonical example. Use marker-delimited blocks where `tests/test_roadmap_format.py` can compare copied values with code.

- **Document route precedence and command outcome exactly once.** In the format reference, show that invalid input is transient and creates no analysis; an uncorroborated one-artifact `cross-artifact-impact` result is durable `requires-scope-review` with `next_workflow: null`; a multi-artifact closure names `roadmap-cross-artifact-revision-transaction`; and every other valid one-artifact closure names `roadmap-same-artifact-structural-revision`. State that append-confirmed terminal event, stored route class, immutable `created`/`reused` creation outcome, and return-only `telemetry-unavailable` are separate facts. A completed `requires-scope-review` creation is successful status `0`, has a null workflow, and is neither a refusal nor an alias for a broad command.

- **Explain freshness as a route condition.** State that creation validates and rechecks current evidence before publication, so an immutable record is not permanent proof that its route is still current. Explain that `--view impact-analyses` strictly parses stored evidence and requires its entry name plus exact canonical bytes to match a recomputed current candidate under step 9’s reader coordination; stale, unavailable, invalid, or uncoordinated records display no route or workflow.

- **Document the two operator status maps.** Creation returns `0` only for durable current route records (including no-workflow `requires-scope-review`), `1` for accepted post-admission invalid/storage-rejected/collision/write/telemetry failures, `2` for invalid usage/preflight rejection, and `130` for interruption. A completed pure inspection returns `0` for current and every no-route evidence state; only its usage conflict returns `2`. `created`/`reused` belongs only to creation output, never to inspection.

- **Keep receipt, analysis, and broad re-entry distinct.** Update every affected guide so a current receipt can be supplied only through `plan-tool roadmap <slug> --analyze-escalation RECEIPT_FINAL`; the command never selects a receipt from a scan. Keep `plan-tool roadmap <slug> --view impact-analyses` as inspection only. Do not describe either form as an alias for `--from-stage`, `scope-review`, a patch, or a follow-on writer.

- **State the exact write boundary.** Document that analysis creation may write only its coordination lock, one immutable impact-analysis final, and its redacted lifecycle telemetry. It must not change a canonical artifact, receipt, feedback state, seed state, or Git state, call a backend, or start broad re-entry. Document that the impact-analysis view is log-free and creates neither evidence nor a lock.

- **Give each document one job.** Keep detailed fields, JSON, and route vocabulary in `ROADMAP_FORMAT.md`; keep the execution order in `docs/ROADMAP_WALKTHROUGH.md` and `RUNBOOK.md`; keep layer ownership in `docs/ARCHITECTURE.md`; keep the command cheat sheet in `README.md`; keep `CLAUDE.md` terse; and keep test seams in `TESTING.md`. Cross-link instead of restating tables in several places.

- **Preserve the existing receipt wording where it remains true.** The receipt still does not derive impact or authorize a writer. Update language that presents manual scope review as the only post-receipt path so it directs an operator to explicit analysis first when current declared evidence is needed.

## Tests

- `tests/test_roadmap_format.py:test_impact_analysis_reference_matches_landed_contract` — The documented field inventory, schema version, closed route vocabulary, workflow mapping, and command forms match the landed schema and parser.

- `tests/test_roadmap_format.py:test_impact_analysis_example_is_valid_canonical_and_identity_bound` — The copied JSON example parses through the landed analysis parser, re-renders unchanged, and has a semantic id equal to its final name.

- `tests/test_roadmap_format.py:test_impact_analysis_route_reference_preserves_precedence_and_no_route_cases` — `invalid`, `requires-scope-review`, `cross-artifact`, and `same-artifact` retain their documented order; only the two routable classes name workflows.

- `tests/test_roadmap_format.py:test_impact_analysis_reference_separates_route_publication_event_and_status` — The reference shows `created`/`reused` as creation-only publication facts for every durable route, including scope review; distinguishes append-confirmed events from return-only telemetry failure; and shows the closed creation and view status maps.

- `tests/test_roadmap_format.py:test_impact_analysis_reference_keeps_receipt_analysis_and_broad_reentry_distinct` — The reference states that an exact receipt final starts analysis and that neither analysis form authorizes broad generation or canonical mutation.

- `tests/test_roadmap_format.py:test_impact_analysis_documentation_names_the_permitted_writes_and_log_free_view` — Creation lists only the allowed noncanonical writes, while the view is documented as read-only, lock-noncreating, and telemetry-free.

### Verification (non-code step)

1. **Non-code exemption:** This step has `change_type: non-code`; the production test-authoring gate does not require a new production test module. The format drift guard and documentation checks are the required verification.

2. **Format drift guard:** Run `uv run pytest tests/test_roadmap_format.py -q`.

3. **Command alignment:** Run `uv run pytest tests/cli/test_roadmap_cmd.py tests/cli/test_cli_reference.py -q` to confirm the documented forms still match step 9’s parser and generated CLI reference.

4. **Link and terminology sweep:** Check links among `README.md`, `ROADMAP_FORMAT.md`, `docs/ROADMAP_WALKTHROUGH.md`, and `RUNBOOK.md`; then search the declared documentation files for receipt-only wording and confirm each remaining receipt boundary distinguishes receipt behavior from the separate analysis path.

## Acceptance criteria

- `ROADMAP_FORMAT.md` identifies the landed analysis schema owner and contains a complete code-checked field inventory, route vocabulary, raw-source-record versus decoded-brief digest meanings, canonical JSON example, and semantic-id/final-name rule.

- The format example parses and renders through the landed analysis contract without changing bytes.

- Documentation names exactly these operator forms: `plan-tool roadmap <slug> --analyze-escalation RECEIPT_FINAL` and `plan-tool roadmap <slug> --view impact-analyses`.

- Every operator-facing document distinguishes creation from inspection, describes stale or invalid records as no-route results, requires exact recomputed candidate identity before a route renders, and does not present immutable evidence as permanent current authority.

- Only `roadmap-cross-artifact-revision-transaction` and `roadmap-same-artifact-structural-revision` are documented as named workflows; `requires-scope-review` has no workflow or printed command.

- Documentation states that every durable creation route, including `requires-scope-review`, exits `0`; it distinguishes that route from the creation-only `created`/`reused` publication fact, documents append-confirmed versus return-only telemetry outcomes, the creation `1`/`2`/`130` statuses, and the completed-view `0`/usage-error `2` statuses.

- The documentation names only the permitted creation writes and states that inspection creates no evidence, telemetry, or lock state.

- `README.md`, `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP_WALKTHROUGH.md`, `RUNBOOK.md`, and `TESTING.md` direct readers to the format reference for schema detail instead of copying it.

- `uv run pytest tests/test_roadmap_format.py tests/cli/test_roadmap_cmd.py tests/cli/test_cli_reference.py -q` passes.

## References

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Use this for the strict JSON and duplicate-member expectations stated in the schema reference.

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use this for canonical serialization and duplicate-aware decoding terminology.

- [Configuration — Pydantic](https://docs.pydantic.dev/latest/api/config/) — Use this for the strict, frozen, extra-forbidden schema guarantees the reference describes.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Use this for the SHA-256 semantic identity and immutable final-name explanation.

- [fcntl — The fcntl and ioctl system calls](https://docs.python.org/3.13/library/fcntl.html) — Use this for the advisory coordination context behind current-record inspection.

## Applicable guardrails

- **The plan’s “## Plan intent,” separate evidence route** — Describe analysis as evidence-backed routing only; do not imply canonical mutation, backend work, broad re-entry, or patch selection.

- **The plan’s “## Step intent,” discoverable contract** — Keep this step limited to documenting the schema, workflows, no-route cases, command forms, freshness meaning, and write boundary supplied by its dependencies.

- **The plan’s “## Architecture,” route precedence and current-state validation** — Preserve the code-owned route order and current-record distinction; do not infer impact from a receipt reason or prose.

- **The plan’s “## Out of scope,” follow-on execution** — Name later same-artifact and cross-artifact workflows only as handoffs. Do not document them as actions this analysis performs.

## Deferred

- Follow-on same-artifact and cross-artifact mutation — `roadmap-same-artifact-structural-revision` and `roadmap-cross-artifact-revision-transaction` own their separate admission checks and any canonical write.

- Receipt creation and receipt-only inspection — The existing escalation contract remains separate; this step documents its relationship to analysis but does not revise it.

- Changes to the analysis schema, evidence protocol, telemetry, or CLI behavior — Steps 2, 4, 5, 7, and 9 own those contracts; any later change requires code and a renewed documentation sweep.
