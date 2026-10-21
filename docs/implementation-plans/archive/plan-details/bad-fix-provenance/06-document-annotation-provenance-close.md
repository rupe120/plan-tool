> **Withdrawn 2026-08-11** — Withdrawn after the detail-stage audit exposed an unresolved high-severity provenance-ordering defect and non-convergent correctness contracts; re-seed the capability from the audited invariants before implementation.
> Preserved here for history; do not edit.

# Step 6 — Document annotation provenance and close backlog #231

## Summary

Document the landed annotation-provenance contract in `DATA_CONTRACT.md`, including every annotation producer and the conditions that make a note usable remedy evidence. Update `CLAUDE.md` and `integrations/shared/DIRECTIVES.md` so operators use the new hand-record route after a manual completeness fix. Close `BACKLOG.md` entry #231 and remove its stale active-work references. Extend `tests/test_data_contract.py` so the contract text stays aligned with the persisted `Annotation` shape and producer rules.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the documentation and backlog update.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why the existing annotation and hand-apply guidance is incomplete.
- [Input](#input) — Landed provenance, command, and advisory contracts this step documents.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation, backlog, and drift-test edits.
- [Implementation](#implementation) — Contract ownership, producer mapping, guidance, and closure rules.
- [Tests](#tests) — Documentation-drift coverage and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completion.
- [References](#references) — Primary references for persisted dataclass and JSON contracts.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain the documentation.
- [Deferred](#deferred) — Work that remains outside this final documentation step.

## Why

`DATA_CONTRACT.md` still says that only the interactive walk populates annotations, while the completed provenance work also records serial, parallel, and hand-applied dispositions. Without a clear producer map and hand-record instructions, an operator can fix a saved completeness finding without the evidence that `plan-tool convergence` needs to issue its recommend-only advisory. Closing #231 also requires the backlog’s active priority and readiness views to stop presenting shipped work as pending.

## Input

- **Step 2 provenance contract:** Read the landed `plan_tool/review_persistence.py:Annotation`, `plan_tool/review_persistence.py:SavedReview`, `plan_tool/review_persistence.py:load_review`, and `plan_tool/review_persistence.py:update_annotation` shapes. The landed code names the provenance fields and supported sidecar version; it wins over this plan and sibling detail proposals.

- **Step 3 recording route:** Document the landed `plan-tool completeness-record` command and its selected-report, finding-selector, and applied-note requirements. It is the hand-applied producer of operator remedy evidence.

- **Step 5 advisory contract:** Document the final recommend-only interpretation from `plan_tool/convergence_diagnosis.py:diagnose_convergence` and `plan_tool/convergence_diagnosis.py:render_diagnosis`: qualified provenance supports a re-check prompt, not a causal conclusion or a control-flow change.

- **Contract drift guard:** `plan_tool/data_contract.py:persisted_dataclass_contracts` and `tests/test_data_contract.py:test_every_persisted_field_is_documented_in_own_section` define the existing field-to-document check that this step extends.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `DATA_CONTRACT.md` — update the `SavedReview` and `Annotation` sections with the landed provenance fields, compatibility behavior, evidence rules, and complete producer map.
  - `CLAUDE.md` — update the `Driving the convergence loops` guidance with the hand-applied recording route and its operator-note requirement.
  - `integrations/shared/DIRECTIVES.md` — update the provenance check in the convergence guidance so manual remedies are recorded before recurrence is interpreted.
  - `BACKLOG.md` — close #231 with a dated completion record and remove or update its active-work references throughout the backlog.
  - `tests/test_data_contract.py` — add focused assertions for annotation provenance documentation and producer coverage while retaining the registry-driven checks.

## Implementation

- **Foundational logic: traceable annotation documentation.** Make the documentation explain how an annotation becomes qualified evidence, who can produce it, and how an operator records a manual remedy.

- **Keep one contract owner.** Put persisted field names, allowed source values, source-report identity, timestamp semantics, legacy handling, and qualification rules in `DATA_CONTRACT.md` under `Annotation` and, where needed, `SavedReview`. List the field names exactly as the landed `plan_tool/review_persistence.py:Annotation` dataclass exposes them.

- **Distinguish event time from report time.** State that annotation recording time and the immutable saved-report time have different jobs. The later advisory uses the recorded event time for ordering and retains report identity for attribution.

- **Fail closed in the documentation.** State that a qualifying remedy needs the landed applied disposition, empty halt reason, non-empty stripped operator text, recognized operator source, complete source identity, and valid earlier recording time. Generated text, decline or failure outcomes, safety halts, malformed fields, and legacy annotations without provenance remain non-qualifying.

- **Document every producer once.** Use a compact producer map in `DATA_CONTRACT.md`; do not leave the old interactive-walk-only statement in place.

  | Producer | Evidence classification to document |
  |---|---|
  | `plan_tool/review_walk.py:walk_recommendations` | Explicit operator-entered text is operator evidence; action output is generated; absent or whitespace-only text is non-evidence. |
  | `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply` | The serial path keeps the shared walk’s classification; it does not promote generated apply output to operator evidence. |
  | `plan_tool/cli/completeness_apply_parallel.py:annotation_status` and `plan_tool/cli/completeness_apply_parallel.py:replay_results` | Final parallel verdict and status text is generated evidence. |
  | Step 3’s `plan-tool completeness-record` route | An applied hand record requires explicit remedy text and records operator evidence; a deliberate decline remains a recorded disposition but not an applied remedy. |

- **Keep guidance procedural.** In `CLAUDE.md` and `integrations/shared/DIRECTIVES.md`, tell an operator who fixes a saved completeness finding by hand to use the record command against that saved finding, provide the required applied-remedy note, then re-audit. Point readers to the command help for selector syntax instead of duplicating its parser contract.

- **Do not overstate the advisory.** Guidance must say that the result asks an operator to re-check an earlier remedy. It must not describe the signal as proof that the remedy caused the recurrence or as a reason to stop, mutate a plan, or change an exit code.

- **Close #231 as shipped work.** Replace the central `BACKLOG.md` #231 proposal with a short, dated completion record that names the delivered recommend-only provenance advisory and its documentation. Remove #231 from active priority, readiness, and cluster lists; update nearby references that describe it as future or active work. Retain a reference only where it is genuinely historical, and frame that reference as history rather than an active backlog item.

- **Sweep identifier and vocabulary references together.** Use the `BACKLOG.md` #231 entry and its cross-reference search results as the review set. In particular, update references that still describe missing provenance, a pending decision, or an upcoming hard-exit behavior; do not leave the former problem statement as current design.

## Tests

- `tests/test_data_contract.py:test_every_persisted_field_is_documented_in_own_section` — confirms every landed `Annotation` provenance field appears in its contract section.

- `tests/test_data_contract.py:test_documented_fields_are_registered_or_aliases` — rejects stale or guessed provenance field names in the `Annotation` table.

- `tests/test_data_contract.py:test_annotation_provenance_contract_documented` — asserts the contract distinguishes event time, report identity, source categories, qualification, and fail-closed legacy behavior.

- `tests/test_data_contract.py:test_annotation_producer_map_documented` — asserts the documentation names the shared walk, serial apply, parallel apply, and hand-record producer rules.

### Verification (non-code step)

This step is `change_type: non-code`, so the plan’s production-code test-authoring gate does not apply.

1. Run `pytest tests/test_data_contract.py` and confirm the registry-driven and targeted documentation checks pass.

2. Compare the `DATA_CONTRACT.md` `Annotation` and `SavedReview` sections with the landed `plan_tool/review_persistence.py:Annotation`, `plan_tool/review_persistence.py:SavedReview`, and `plan_tool/review_persistence.py:SCHEMA_VERSION` values.

3. Check the registered `plan-tool completeness-record` help and its generated command reference before finalizing the guidance wording.

4. Review `rg -n '#231' BACKLOG.md` results: no active priority, readiness, or pending-work reference may describe #231 as unfinished.

## Acceptance criteria

- `DATA_CONTRACT.md` documents every persisted `Annotation` field that the landed contract registry exposes, with no stale field rows.

- The annotation documentation names all four producer paths and accurately separates operator, generated, and non-evidence notes.

- The provenance documentation states the complete qualifying-remedy rule and explicitly fails closed for legacy or malformed provenance.

- `CLAUDE.md` and `integrations/shared/DIRECTIVES.md` direct hand-applied completeness fixes through `plan-tool completeness-record` with an explicit applied-remedy note.

- Guidance describes the bad-fix result as recommend-only and does not claim causation or a convergence-control effect.

- `BACKLOG.md` records #231 as completed with a completion date, and its active backlog references no longer present it as planned, theoretical, or pending.

- `pytest tests/test_data_contract.py` passes.

## References

- [Python dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Defines the field shape that `DATA_CONTRACT.md` documents for persisted dataclasses.

- [Python json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Covers the saved-sidecar representation and compatibility language in the contract.

## Applicable guardrails

- **The plan’s “## Plan intent”, causal-evidence boundary** — document qualified evidence and the advisory’s limited meaning without turning it into proof of causation.

- **The plan’s “## Step intent”, producer and recording boundary** — explain every annotation producer and the hand-apply route; do not add new producer behavior.

- **The plan’s “## Out of scope”, loop-control and mutation boundaries** — do not document a stop rule, exit-code change, plan mutation, or automatic remedy as part of this signal.

- **The plan’s “## Out of scope”, matcher and storage boundaries** — keep the documented evidence in annotations and do not extend `_matches` semantics or introduce another provenance store.

- **The plan’s “## Out of scope”, separate-work boundary** — leave the unrelated work named by the plan’s fence out of these documentation and backlog edits.

## Deferred

- **Hard enforcement based on the advisory** — remains outside this documentation step and requires separate tracking if the recommend-only policy changes.

- **Other convergence backlog work** — this step closes #231 and its stale references only; unrelated backlog entries retain their own scope and status.
