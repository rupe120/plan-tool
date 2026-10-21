# Roadmap candidate envelope diagnostics — post-run review ledger

## Summary

| Field | Value |
| --- | --- |
| Plan | `roadmap-candidate-envelope-diagnostics` (`docs/implementation-plans/2-roadmap-candidate-envelope-diagnostics.md`), 7 steps (5 code, 6 and 7 non-code). Source: `BUG_BACKLOG.md` § "Candidate proposal retries still emit incompatible row-operation envelopes…" (`PLAN-AUTHORED`). |
| Branch | `impl/roadmap-candidate-envelope-diagnostics`, based on `main` at `24b32aff`, pushed to `origin`. |
| Review range | `24b32aff..HEAD`; `plan_tool/` and `tests/` only. |
| Run | Steps 1–5 green, each through the full-suite gate; step 6 green (tests only). Step 7 is marked done without its edit; the closure is a direct edit (see "Decisions"). |
| Checks run | Bare and detail-grounded `completeness-audit --iterate` gates, both converged. `reconcile-code --all`: sweep 1 found 2 medium (fixed `48af5acb`, `205b3878`), sweep 2 found 0. Full suite after the last fix: 14022 passed, 190 skipped. |
| `/code-review` | Three independent `high` report-only passes. Pass 1 (`24b32aff..183b8d2b`): 1 high, 1 medium, 3 low, 2 nit, plus owner-note discrepancy P1.0. Pass 2 (`..7c52de70`): 2 low. Pass 3 (`..e59e5336`): 2 low. |
| Current disposition | **Converged (2026-09-27).** Passes 2 and 3 returned only low findings; see "Convergence status". |

## Settled decisions (hand these to every reviewer)

A finding that proposes the opposite is invalid, not deferrable.

- **The strict parser stays strict.** A known class name selects a row schema for diagnosis only; the response is still rejected. No parse-time coercion, dropping, or repair of unknown fields, class names, or `source`.
- **The hint is reshaped, never removed.** `PatternRow` maps to `system_patterns` and `component_patterns`; the hint's `collection` is the only disambiguator. No hint record carries `artifact_key`, `row_type`, `row_id`, or `collection` at its top level.
- **One correction names every defect.** The retry has one correction, so operation-field defects and an invalid `row_type` are reported together. An unknown field is named when the tool defines the name: operation keys, row and nested-record keys, `DecisionRow` fields (so `source`), and the discovery keys (`collection`, `source_collection`, `issued_row`, `row_digest`). Any other name is `other`, so a correction never repeats arbitrary model text. Names of one kind share a clause.
- **Unchanged on purpose.** The two-attempt bound, the capsule's class-name `identity` records, receipts and digests, replay identity, the run-log schema. Rejected responses keep their exact bytes.
- **Prompt shapes come from the parser's own key sets** (shared constants).
- **Existing value-echoing messages are not reworded** (unknown `op`, duplicate JSON key).
- **Per-row-type example bodies beyond `entities` are out of scope.** `DecisionRow.source` is the only mismatch between a row dataclass and the parser's accepted keys.
- **Deliberately not:** a run-log schema change, receipt redaction, a third attempt, any check of model content beyond the closed wire vocabulary.

## Decisions (owner)

- **Step 7 and the Integration re-run — closed on deterministic proof (2026-09-27).** The `PLAN-AUTHORED` entry is removed from `BUG_BACKLOG.md`. Evidence: steps 1–6, both `reconcile-code` sweeps, and three review passes, all committed, suite green. The Integration `--propose-candidate` re-run is deliberately not run: it needs a build containing this branch in the canonical checkout, calls a live model, and writes into Integration's files, so it stays a separate, unrecorded acceptance check. If a later Integration run still emits `collection` or a class-name `row_type`, file a new entry with that run's stored responses and do not add parse-time repair.

## Findings

### Reconcile-code sweeps

- **RC1 — `PatternRow` correction named one collection** (medium): the `invalid-row-type` correction for `PatternRow` named only `system_patterns`. **Disposition:** fixed `48af5acb` — the new test fails when reverted.
- **RC2 — stored `add-row` shape unproven end to end** (medium): the only run-level retry fixture malformed a `replace-row`, where `row_id` is legitimate. **Disposition:** fixed `205b3878` — new test beside the existing one.
- Sweep 2: 0 findings on steps 1–5; a third sweep is not run (it would resample unchanged code).

### Pass 1

- **P1.0 — `collection` reported as `other`** (owner-note discrepancy): the plan says tool-defined names, `collection` included, are named; the settled wording (this ledger's own) was wrong and the code reported the stored Integration defect as `other`. **Disposition:** fixed `2c993f91` — `_DISCOVERY_FIELD_NAMES` joins the reportable names at all six operation-level sites (naming only, accepted keys unchanged); two tests that pinned `other` changed, and a parametrized test pins each name plus the invented-names-stay-`other` carve-out.
- **P1.1 — corrected `decisions` row cannot be stored** (high, CONFIRMED): dropping `source` parses as `DecisionRow(source=None)`, but evidence re-serialization writes `"source": null`, which the strict parser refuses, so a compliant reply never stores (the stored-evidence replay had the same defect). **Disposition:** fixed `2c993f91` — `_operations_wire_for_reparse` drops only a null `source` at all three re-parse sites; identity and digest wire form unchanged, a supplied `source` stays refused; the retry test now stores the corrected row.
- **P1.2 — class-name `row_type` on a relationless collection hides the reached-anchor defect** (medium, CONFIRMED): `HostingRow`, `PatternRow`, `AttributeDispositionRow` were checked as raw class names, so the retry was spent on the anchor rule. **Disposition:** fixed `2c993f91` — the check reads the resolved schema; parametrized test, red when reverted.
- **P1.3 — some operation defects surface one at a time** (low, PLAUSIBLE): malformed `ordering`, `replace-row` `row.id` differing from `row_id`, or a non-string id are checked only by `_parse_operation`. **Disposition:** tracked `BUG_BACKLOG.md` (`a7fd01dc`, "The single candidate correction still names only the first of several operation defects…") — outside the plan's three-reason vocabulary and absent from stored Integration replies.
- **P1.4 — no operation index; identical clauses repeat** (low, PLAUSIBLE): **Disposition:** declined — the plan requires naming every defect, not locating each; no stored reply or test shows a retry failing for want of an index.
- **P1.5 — examples show `"ordering": null` while prose says omit** (low, PLAUSIBLE): **Disposition:** fixed `2c993f91` — prose says to keep `ordering` `null` unless changing the plans ordering entry (superseded in part by P3.1).
- **P1.6 — dead `if "op" not in record` guard; each valid row parsed twice** (nit, CONFIRMED): **Disposition:** guard fixed `2c993f91` (deleted); double parse declined — merging the pre-pass and `_parse_operation` is a refactor the plan does not ask for.
- **P1.7 — `_ROW_TYPE_BY_CLASS_NAME` restates the inverse of the canonical collection map** (nit, CONFIRMED): **Disposition:** fixed `2c993f91` as a test (table keys equal the canonical class names, each maps to a collection assigned to that class), not a derivation, which would change `PatternRow`'s two-collection handling.
- **P1.R — `remove-row` with a non-collection `row_type` now fails at parse time** (reviewer-rejected candidate): **Disposition:** refuted by the reviewer — materialization already refuses such a `row_type`, so stored evidence cannot hold one.

### Pass 2

- **P2.1 — a `remove-row`'s forbidden `row` body diagnosed as an intended row** (low, CONFIRMED): a stray malformed `row: {}` drew both `unknown-field row` and `entities row has missing-field …`, so acting on the second clause wastes the retry. **Disposition:** fixed `931b6625` — the row-body check runs only for operations whose parser key sets include `row`; test asserts `unknown-field row` and no `entities row has …` clause, red when reverted.
- **P2.2 — root-level key defect hides operation defects** (low, CONFIRMED behavior): root checks raise before the operation pre-pass, so both cannot appear in one correction. **Disposition:** tracked `BUG_BACKLOG.md` (the entry filed for P1.3, extended; the source gives no separate commit for the extension) — collecting root diagnostics changes `parse_candidate_delta` control flow for a defect with no observed instance.
- Re-checked: P1.0, P1.1, P1.2, P1.5 verified complete; the reviewer rejected two of its own candidates as contradicting settled decisions or already dispositioned.

### Pass 3

- **P3.1 — prompt calls `ordering` optional, but a `plans` row requires it** (low, CONFIRMED): materialization requires a matching `ordering` on a `plans` `add-row` and `remove-row` (removal equals the predecessor entry exactly) and refuses it elsewhere. Partly self-seeded by P1.5. **Disposition:** fixed `5a59ae7e` — the prose says `ordering` is `null` except for `plans`, where an add or removal requires an `ordering` object naming the plan and a removal repeats the existing entry; a prompt test pins the three claims, red on the old prose.
- **P3.2 — `_render_batch_operation_shapes` raises a bare `KeyError` if a parser key set grows** (low, PLAUSIBLE): **Disposition:** declined — the trigger is a developer editing shared key sets, not model or operator input, and `test_batch_prompt_renders_parser_owned_operation_shapes` fails loudly first; moving the call under the `try` would turn that drift signal into a quiet run-time refusal.
- Considered and not reported: row-level unknown fields other than `DecisionRow` fields report as `other` (the rule names discovery names only at operation level); the selector-shaped prompt gets no operation shapes since only the batch route retries.

## Out-of-range findings

_(none)_

## Convergence status

**Converged after three passes (2026-09-27).** Pass 1 returned a high and a medium finding, so the streak begins at pass 2. Passes 2 and 3 each returned two low findings and nothing material, with no sibling regression in earlier fixes: the stopping rule's two consecutive low-only passes. This is low-yield convergence, not a clean audit. The advisory tail is the tracked `BUG_BACKLOG.md` entry (P1.3, P2.2) and the declined P1.4, P1.6 (double parse), and P3.2. P3.1 was partly seeded by the P1.5 edit, so its fix is prose plus a test, and no further pass is run. The last full suite ran after the P3.1 fix: 14022 passed, 190 skipped.
