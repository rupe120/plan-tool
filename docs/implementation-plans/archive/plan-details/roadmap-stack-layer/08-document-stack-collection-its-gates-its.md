> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Document the stack collection, its gates, its feedback operations, and its callouts, record the summary module in the architecture doc, and keep BACKLOG #461 plan-authored

<!-- plan-tool:detail-format-version: 1 -->

## Summary

- Documents the `stack` collection where operators and reviewers read the schema: `ROADMAP_FORMAT.md` (the `02-constraints.md` schema, gates, closed vocabulary, callouts, and a runnable example) and `ROADMAP_FEEDBACK_FORMAT.md` (stack rows as feedback and candidate targets).
- Adds `plan_tool/roadmap_stack_summary.py` to `docs/ARCHITECTURE.md` as the single producer behind the first-run output, `INDEX.md`, candidate review, and seed rendering, with its import boundary.
- Key decision: **names come from the landed code, not from steps 1–7's detail files.** Every field, constant, gate, and function this step cites is read off the modules those steps landed; the landed name wins on disagreement.
- Keeps BACKLOG #461 marked `PLAN-AUTHORED` and removes it only at full shipment, not in this step.
- On green: the doc's new `02-constraints.md` example parses, round-trips, and clears the gates; every stack gate and constant in the code appears in the doc; and `tests/test_roadmap_format.py` pins the backlog state.

## Table of Contents

- [Summary](#summary) — what the step does and the result on green
- [Why](#why) — the documentation gap and the drift risk
- [Input](#input) — what steps 1–7 hand this step, and what cannot be checked yet
- [Files (creates vs edits)](#files-creates-vs-edits) — the five files touched
- [Implementation](#implementation) — content per file, citation rules, and what must not change
- [Tests](#tests) — drift-guard cases and verification checks
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — work that belongs elsewhere

## Why

- `ROADMAP_FORMAT.md` is the schema contract an operator reads before hand-editing `02-constraints.md`. Its `02-constraints.md` schema block lists `hosting`, `dispositions`, `constraints`, and `decisions` only. After steps 1–7, a hand edit that adds, drops, or mistypes a `stack` row has no documented rules.
- `ROADMAP_FEEDBACK_FORMAT.md` describes the ledger-to-candidate workflow without saying that stack rows are legal targets, or that a candidate introducing the collection must add all required concerns at once.
- `docs/ARCHITECTURE.md` describes the roadmap leaves and their one-way import edges. A new module that four surfaces share needs its boundary written down, or a later change adds an import edge nobody meant.
- `tests/test_roadmap_format.py` already guards this doc's examples and its printed vocabularies. A stack section with no guard is the one part that can go stale silently.
- The backlog entry must stay accurate to what is true: planned, not shipped.

## Input

- **Steps 1–7 output.** The landed code defines the stack row type, its concern vocabulary constant, the `ConstraintsArtifact.stack` field (`None` = not recorded, `()` = present and empty), the stack gate and its violation kinds, the feedback and candidate row-operation policy, the constraints prompt, and `plan_tool/roadmap_stack_summary.py`.
- **Names come from the landed modules.** Step 1 proposed `StackRow`, `STACK_CONCERNS`, and fields `id`, `concern`, `choice`, `open`; step 2 proposed `check_stack_totality`. These are proposals. Read `plan_tool/roadmap_artifacts.py`, `plan_tool/roadmap_gates.py`, `plan_tool/roadmap_stack_summary.py`, and `plan_tool/cli/roadmap_cmd.py`, document what shipped, and say so in the edit where a name differs.
- **Citation depth.** All seven earlier steps are dependencies, so symbol-level citations are allowed for every module they landed. If an earlier step is found missing at HEAD, stop and surface it; do not document a symbol that does not exist.
- **#460 dependency.** Step 7 renders the stack into #460's `## Stack` seed section. Cite that section by the heading and function #460 landed, not by a guess.
- **Limit.** The doc example proves the schema is satisfiable and the gates accept it. It does not show a real model follows the prompt.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md`:
    - extend the `02-constraints.md` schema block with the `stack` collection and its parsed type;
    - add a short subsection on stack semantics and the first-run versus existing-lineage rule;
    - add the stack gate(s) to the relation-gates section and the "what parse time deliberately lets through" section;
    - add the concern vocabulary to `## Closed vocabularies` (update its count word);
    - add the stack callout surfaces to the review and `INDEX.md` prose;
    - add a stack-bearing `02-constraints.md` example under `## Examples`;
    - add "deliberately not defined" lines for the plan's non-goals.
  - `ROADMAP_FEEDBACK_FORMAT.md`: add stack rows to the target description and the candidate workflow (one short paragraph, not a restatement of the format doc).
  - `docs/ARCHITECTURE.md`: add `plan_tool/roadmap_stack_summary.py` to the roadmap module list and import-edge paragraph, and mention it beside the `roadmap_index.py` entry.
  - `BACKLOG.md`: confirm #461 stays `PLAN-AUTHORED (roadmap-stack-layer)`; correct only facts that are now wrong.
  - `tests/test_roadmap_format.py`: add the guards under Tests.

## Implementation

**Order of work.** Read the landed code first, then write `ROADMAP_FORMAT.md`, then the two shorter docs, then the tests. `ROADMAP_FORMAT.md` is the home doc; the other two link to it and restate nothing.

**`ROADMAP_FORMAT.md` content.**
- **Schema block.** Add the `stack` key to the `02-constraints.md` yaml block in the same annotated style as `hosting` (`# required`, `# optional` comments). State plainly that the key is optional on the file.
- **Missing versus empty.** Document that an absent `stack` key means "stack not recorded" and a present `stack: []` means "recorded, and empty", and that an absent key re-renders with no key. This is the compatibility rule the gates and callouts depend on.
- **Row states.** Document that each row is either chosen (non-blank text) or `open`, as the landed row type defines and the `stack-row-state` gate enforces, and that pending-ness is derived from decisions anchored to the row id and is never stored on the row.
- **Gate rules.** For each landed stack gate, state the rule, the code symbol that enforces it, and when it binds: on an artifact that carries the collection, and on a first run, never on absence alone in an existing lineage. Pair every rule with its enforcer by name, so the doc's both-directions traceability holds.
- **Anchors and feedback.** State that stack row ids join the anchor union (a decision can anchor to a stack row) and the global duplicate-id check, and that stack rows are not ledger feedback targets (the ledger addresses design rows only) but a candidate can add, replace, and revise them, never retype or remove them (the `concern` field is fixed on edit and `allow_remove` is false, as the landed policy says), so a recorded stack never reverts to "stack not recorded".
- **Authority.** State that stack rows are authoritative over hosting and store `product` fields and that no gate compares them; candidate review shows them side by side.
- **Callouts.** Describe where the stack is shown: first-run completion output, `INDEX.md`, and every candidate review print site, as display only. Say that the callout is not part of narrative evidence, is not a defect class, and never blocks approval. Cite the landed producer functions.
- **Draft seeds.** One sentence that the stack renders into the tool-owned `## Stack` seed section; link to the existing `## Draft seeds` heading instead of re-describing it.
- **Example.** Add a stack-bearing `02-constraints.md` under `## Examples` with placeholder-style ids, one chosen concern and one `open` concern. It must be a ```markdown block opening on `---`, so the existing example guards pick it up automatically. Keep it consistent with the existing `01-domain.md` example so the cross-artifact gates pass.
- **Not defined.** Add lines under "What is deliberately not enforced" for: judging whether a choice is good, comparing a stack choice with a hosting or store `product`, a closed vendor vocabulary, concerns beyond the named three, and a fifth artifact.
- **Do not change.** Do not edit the existing hosting, store, or disposition rules; do not add line numbers; do not reproduce the plan's wording where a link will do.

**`ROADMAP_FEEDBACK_FORMAT.md` content.**
- Add one sentence to the lifecycle section that a target row may be a stack row.
- Add one paragraph to the candidate workflow: a candidate that introduces the collection on a lineage that lacks it must carry every required concern in one candidate, because totality binds once the collection is present; stack changes appear in the candidate's stack callout. Link to `ROADMAP_FORMAT.md` for the schema.
- The ledger example block between the `ledger-example` markers must stay unchanged.

**`docs/ARCHITECTURE.md` content.**
- Name `plan_tool/roadmap_stack_summary.py` as the one producer of stack summary lines for first-run output, `INDEX.md`, candidate review, and seed rendering.
- State its edges from the landed imports: it imports `roadmap_artifacts.py` (and whatever the landed code imports for pending decisions) and nothing above it; `roadmap_index.py`, `cli/roadmap_cmd.py`, and `roadmap.py` import it, never the reverse. It must not import `roadmap.py` or `cli`.
- Say it is read-only and returns plain text lines.

**`BACKLOG.md` content.**
- Keep the heading marker and the `**Seed:**` and plan pointers. Do not remove the entry and do not turn it into a promotion stub.
- Verify each stated path in the entry (`plan-seeds/archive/roadmap-stack-layer.replaced.md`, `docs/implementation-plans/2-roadmap-stack-layer.md`) still exists; fix only a path that is wrong.
- Removal at full shipment is a separate act after the post-run tail (see Deferred).

**Sweep.** Name the class: "a doc or test that enumerates the `02-constraints.md` collections or the roadmap leaf modules." Search by identifier (`hosting`, `dispositions`, `roadmap_index.py`) and by vocabulary (`four collections`, `exactly four`, `Nine closed vocabularies`) across `ROADMAP_FORMAT.md`, `docs/how-to/roadmap.md`, `CAPABILITIES.md`, `docs/ARCHITECTURE.md`, and `tests/test_roadmap_format.py`. Update any count word that the new collection or vocabulary invalidates. Per-site, state why a site stays if it does.

## Tests

All in `tests/test_roadmap_format.py` (approx. 5 new cases). The existing example guards (`test_every_artifact_example_parses`, `test_standalone_examples_clear_their_own_gates`, `test_every_artifact_example_round_trips`) pick up the new example without edits; confirm they ran against it.

- `test_stack_example_records_a_chosen_and_an_open_concern` — the doc's stack-bearing `02-constraints.md` parses to a `stack` tuple holding at least one chosen and one open row, so the example exercises both states.
- `test_stack_schema_documents_the_complete_concern_vocabulary` — every member of the landed concern constant appears in the doc's stack section, and the doc prints no concern the constant lacks (same shape as the hosting and store vocabulary guards).
- `test_every_stack_gate_the_code_ships_is_named_in_the_doc` — each landed stack gate function and violation kind constant in `plan_tool/roadmap_gates.py` appears in the doc, and each `check_*` the doc names exists. Catches an undocumented enforcer.
- `test_doc_states_absent_stack_is_not_recorded_and_empty_stack_is_recorded` — the doc contains both distinguishing statements, and a parse of the example with the key removed yields `None` while `stack: []` yields `()`. Pins the compatibility rule the doc claims.
- `test_backlog_461_stays_plan_authored_until_full_shipment` — `BACKLOG.md` still carries the `#461` heading with `PLAN-AUTHORED`, and the entry's plan and seed paths exist on disk. Name and message say that removal belongs to full shipment, so a later removal updates this test deliberately.

### Verification (docs)

- Run `rg -n 'stack' ROADMAP_FORMAT.md ROADMAP_FEEDBACK_FORMAT.md docs/ARCHITECTURE.md` and confirm every cited symbol exists with `rg -n '<symbol>' plan_tool/`.
- Confirm no line numbers were added to the three docs.
- Confirm every relative link added resolves to a real file or heading.
- Run `uv run pytest tests/test_roadmap_format.py tests/test_roadmap_artifacts.py tests/test_roadmap_gates.py -q` and then the full suite with `-n auto`.

## Acceptance criteria

- `ROADMAP_FORMAT.md` documents the `stack` key, the missing-versus-empty rule, chosen versus `open` rows, each stack gate with its enforcing symbol, and the callout surfaces.
- Every stack gate and violation kind in `plan_tool/roadmap_gates.py` appears in the doc, and every `check_*` name the doc cites exists.
- The new stack-bearing example parses, round-trips through `render_constraints_artifact`, and returns no violations from `run_constraints_gates`.
- `ROADMAP_FEEDBACK_FORMAT.md` names stack rows as legal targets and states the all-concerns-in-one-candidate rule; its ledger example block is unchanged and still parses.
- `docs/ARCHITECTURE.md` names `plan_tool/roadmap_stack_summary.py`, its consumers, and the edges it must not add.
- `BACKLOG.md` #461 is still present and marked `PLAN-AUTHORED (roadmap-stack-layer)`; its cited paths exist.
- `tests/test_roadmap_format.py` passes with the five new cases, and a mutation check holds: deleting one concern name from the doc, or one gate name, turns the matching case red.
- The full suite passes with `uv run pytest tests/ -q -n auto`.

## Applicable guardrails

- **The plan's "## Out of scope" (fifth artifact, extra concerns, vendor vocabulary, narrative-evidence class, approval block, quality judgment, Integration's review aid, regeneration).** The docs state these as deliberately not built and add no text implying any of them exists or is planned in this plan. Documentation of stack content as display only is the boundary.
- **The plan's step intent for this step.** Docs and the backlog only: no production code change, and no widening into the how-to, CAPABILITIES, or README beyond a count-word fix found by the sweep.
- **The plan's intent line.** Doc wording must keep the property the plan serves — a stack choice or open question reaching acceptance by a first run or a candidate is never unseen, with hand enrollment excluded — and must not claim the tool judges the choice.
- **Documentation is forward-looking.** Write the stack in present tense as shipped behavior; do not narrate how the docs changed. Dated history appears only for the don't-reopen decisions already dated 2026-10-08.

## Deferred

- Removing BACKLOG #461 — happens after the whole plan has shipped and the post-run reconcile and review tail has converged; a separate act, tracked by the entry's own backlog-reconciliation rule.
- Updates to `docs/how-to/roadmap.md`, `CAPABILITIES.md`, and `README.md` beyond count words found by the sweep — not in this step's file list; route to the backlog if the sweep finds real drift.
- Integration's HTML review aid showing the stack — follows separately in Integration, per the plan's out-of-scope list.
- The cross-plan audit that reads stack rows (#462) — separate backlog item.
- Consolidating the three FORMAT-doc banner or example conventions — cross-module refactor, not a feature step.
