> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Judge a revision against its predecessor: row continuity, feedback integrity, and settled-choice finality

## Summary

Add three gates to `plan_tool/roadmap_gates.py` that judge a re-run artifact against the version it replaces: every predecessor design row survives or is dropped by a removal record that cites reviewer feedback; every predecessor feedback row survives with its source text untouched and only moves `open` → `awaiting-review`; and a predecessor decision still marked `settled` keeps its id, status, chosen option, and anchor. The predecessor arrives as a third, defaulted field on `ArtifactEnvelope`, so `plan_tool/roadmap.py:_build_envelope` keeps compiling untouched and step 5 fills it later. The key design decision: **every predecessor-derived rule is inert when `predecessor is None`**, which is what keeps a first run and the below-stage re-gating pass in `plan_tool/roadmap.py:_load_and_regate_below` behaving exactly as they do today. On green, a revision that silently deletes a row, edits the reviewer's words, or re-decides a settled question comes back as a violation message the retry loop quotes to the model, and an envelope with no predecessor produces the same violation list it produces at HEAD.

## Table of Contents

- [Summary](#summary) — what the three gates add and what stays unchanged.
- [Why](#why) — a re-run today may rewrite anything, and nothing notices.
- [Input](#input) — the position-01 gate contract and step 1's new row types.
- [Files (creates vs edits)](#files-creates-vs-edits) — two edits, no new files.
- [Implementation](#implementation) — the envelope change, the three gates, the rules that are not free to vary.
- [Tests](#tests) — the new roster, the four existing cases this step rewrites, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the docs that bear on retry text and stable schemas.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step's code.
- [Deferred](#deferred) — everything the later steps own.

## Why

A `--from-stage N` re-entry rewrites that stage's artifact from scratch, and the eight gates at HEAD judge only the file in front of them. They cannot tell a considered revision from a fresh regeneration that happens to be shaped right: a model may drop an entity the reviewer never mentioned, reword the reviewer's own request into something it prefers to answer, or flip a decision the operator already settled — and every one of those clears `run_domain_gates` and `run_constraints_gates` today. Step 1 gives the artifact somewhere to record feedback and declared removals; without a gate reading them, a removal record is decoration and the reviewer's text is a suggestion. This step is where "the model may not quietly overwrite the human's contribution" becomes a deterministic check instead of a prompt instruction.

## Input

This step consumes position 01's shipped gate contract and step 1's new rows. Each of these must stay true:

- **The gate signature.** `Gate = Callable[[ArtifactEnvelope], list[Violation]]`. All three new gates take that one type and return that one list, because `plan_tool/roadmap.py`'s `RoadmapStage.gates` holds a gate set as data and a differing signature would put per-gate knowledge back into the run loop.
- **Violations are retry text, never a report.** See the module docstring's "**Violations are retry text, not a report**" paragraph. Each message is quoted straight into the next attempt's prompt as a bare `- {message}` bullet by `plan_tool/roadmap.py:_corrections_block`, with no surrounding context — so it names every identifier involved, names the file by its filename constant, and anchors on ids only. **No violation message may contain a feedback `request` or `proposed_response` substring, and this is a persistence rule, not a style one:** `plan_tool/roadmap.py:_run_stage` passes these messages straight into `run_logger.gate_violations(messages=...)`, so any message quoting the reviewer's prose writes it into `.plan-tool/runs/` — defeating the plan's own criterion that the run log omits feedback and response text. The natural mistake is `VIOLATION_ALTERED_FEEDBACK_SOURCE` quoting the expected request so the model can restore it; name the id and the field instead. Pin it with a sentinel test that seeds a recognizable request string and asserts it appears in no emitted message, alongside step 6's whole-log check.
- **`_rows_of` is the design-row inventory.** `_domain_rows` and `_constraints_rows` spell out the design row kinds one by one and deliberately do **not** derive them from the artifact's dataclass fields. Step 1's `feedback` and `removals` are therefore already outside the prose gate and the duplicate-id gate. Continuity's "predecessor design row" set is `_rows_of(predecessor)` for free.
- **Step 1's row types**, by owning step rather than by mechanism: step 1 produces `FeedbackRow` (id, target, request, state, optional `proposed_response`), `FeedbackTarget` / `FeedbackTargetKind`, `FeedbackState` (`open` / `awaiting-review` / `deferred`), and `RemovalRecord` (`removed_id`, `rationale`, `feedback_ids`), plus `feedback` and `removals` collections defaulting to `()` on both artifacts.
- **Shape rules step 1 already enforces, which this step must not re-check.** An `awaiting-review` row with a blank or absent `proposed_response` raises at parse time, as does a `row` target with no `row_id` and an `artifact` target carrying one. Nothing here re-reports them; a defect reported twice spends two corrections on one problem, the same rule `test_a_targetless_reference_is_reported_once_not_by_both_gates` already pins.
- **Two envelope consumers this step must not disturb.** `plan_tool/roadmap.py:_build_envelope` constructs `ArtifactEnvelope(**{artifact_key: artifact})` from the stage table's `artifact_key`, and `_load_and_regate_below` runs a stage's full gate set over every artifact below the re-entry point. Neither knows what a predecessor is until step 5.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/roadmap_gates.py` — add the `predecessor` field to `ArtifactEnvelope`, 14 new `VIOLATION_*` constants (the invented-feedback defect is step 6's, not a gate rule — see gate 2), the three `check_*` gates, and their entries at the end of `DOMAIN_GATES` and `CONSTRAINTS_GATES`. Update the module docstring's and the section comment's gate counts, and add a clause to `Violation.row_id`'s docstring.
- `tests/test_roadmap_gates.py` — add the cases listed in [Tests](#tests); extend `make_domain` / `make_constraints` / `domain_envelope` / `constraints_envelope` with the new keywords; rewrite the four existing cases named there.

## Implementation

### What must be true when this is done

- Three gates read `envelope.predecessor` and emit nothing at all when it is `None`, except the three rules named below that need no predecessor.
- `ArtifactEnvelope(domain=…)` and `ArtifactEnvelope(domain=…, constraints=…)` still work, so `plan_tool/roadmap.py` and `tests/test_roadmap.py` compile and pass **unedited**.
- A revision that keeps every row, every feedback row's source text, and every settled decision's commitment produces an empty violation list.
- Nothing outside `plan_tool/roadmap_gates.py` and `tests/test_roadmap_gates.py` changes.

### The envelope grows one defaulted field

Add `predecessor: Optional[StageArtifact] = None` to `ArtifactEnvelope`, after `constraints`. It holds **the prior version of the artifact under check** — the domain stage's predecessor is a `DomainArtifact`, the constraints stage's is a `ConstraintsArtifact`.

- **The default is what keeps this step additive.** `_build_envelope` fills only `artifact_key`-named slots; a defaulted third field is invisible to it.
- **Do not validate that the predecessor's type matches the artifact under check.** Step 5 builds the pair from one stage row, so they agree by the way it is built, and this module returns violations rather than raising — a `__post_init__` raise would be the first exception the gate layer ever threw. Say so in the field's docstring.
- **Rejected alternative:** a separate `RevisionEnvelope` type passed to a second gate set. It doubles the stage-table field the run loop reads and gives the two sets different signatures, which is the exact thing `test_both_gate_sets_share_one_call_shape` exists to prevent.

### Gate 1 — `check_design_row_continuity`

Three rules run **always** (they judge only the artifact under check, so they are decidable on a first run and on a below-stage artifact):

- A removal's `rationale` is non-blank → `VIOLATION_BLANK_REMOVAL_RATIONALE`.
- A removal cites at least one feedback id → `VIOLATION_UNCITED_REMOVAL`.
- A removal does not name a row the same artifact still declares → `VIOLATION_REMOVAL_NAMES_A_PRESENT_ROW`.

Three rules need the predecessor:

- Every id in `_rows_of(predecessor)` appears in `_rows_of(artifact_under_check)` or is some removal's `removed_id` → `VIOLATION_DROPPED_DESIGN_ROW`. Report every dropped row, not the first.
- A **new** removal's `feedback_ids` each name a predecessor feedback row **that was `open`** → `VIOLATION_UNRESOLVED_REMOVAL_CITATION`. Only an `open` row is active guidance: a `deferred` row is one the reviewer explicitly parked, and an `awaiting-review` row is one the model already answered. Neither may authorize dropping a design row — otherwise the hole step 6's fourth rejection kind closes is reachable through a real id instead of a fabricated one. The revision prompt states the same restriction, so the model is told the rule rather than discovering it through a retry.
- A **new** removal names a row the predecessor declared → `VIOLATION_REMOVAL_WITHOUT_A_PREDECESSOR_ROW`.

**"New" means the whole record is not already in the predecessor.** Compute `carried = set(predecessor.removals)` — `RemovalRecord` is a frozen dataclass whose fields are all hashable — and judge only removals outside it against the predecessor.

- **The reason this scoping is not optional:** feedback is deliberately transient (the human closes it by deleting the row), so judging a carried-forward removal's citation would make an ordinary human close turn a clean revision into a violation nobody can fix, and the retry loop would spend its whole budget on it.
- **A removal record's lifetime, decided here rather than left open:** a carried removal record survives a revision by default and **the model may never drop one** — dropping a removal is not a move the revision prompt offers, and `VIOLATION_DROPPED_DESIGN_ROW` would not catch it because a removal is not a design row. But it is **the reviewer's to prune**, deleted in the editor like any other frontmatter row. Model-permanent, reviewer-prunable — state it exactly that way, because the two halves are what make the next bullet work.
- **Restoring a removed design row is a supported move, and it needs the pruning half.** Once `entity-3` is dropped by a cited removal, any later revision that re-declares it trips the always-on `VIOLATION_REMOVAL_NAMES_A_PRESENT_ROW`, and `_load_and_regate_below` turns that into a hard pre-flight `RoadmapError` on a `--from-stage` run above it. The escape is the reviewer deleting the carried removal record before asking for the row back — there is no model-side move, and without this bullet the reviewer meets a violation with no documented answer. **Pruning is not sufficient on its own:** the prune drops that id from the set step 5's pre-flight target check resolves against, so every feedback row still naming it must be closed or retargeted in the same edit, or the next run fails pre-flight. The simpler move, and the one the docs should lead with, is an `artifact`-level target for the restore request. Step 4's revision contract states the same inverse so the model does not attempt it.
- Use the whole record as the identity rather than `removed_id` alone, so a hand-edited carried removal is re-judged.

### Gate 2 — `check_feedback_integrity`

Two rules run **always**:

- Feedback ids are unique within the artifact under check → `VIOLATION_DUPLICATE_FEEDBACK_ID`, one violation per duplicated id (matching `check_duplicate_row_ids`' cardinality, which `test_duplicate_id_reported_once_per_id` pins).
- **A predecessor holding duplicate feedback ids has no defined join, so it never reaches a gate.** Every predecessor-joining rule below keys on id; two rows sharing one id make "the predecessor's row for this id" ambiguous, and parse time deliberately lets the duplicate through. The reviewer wrote it and only the reviewer can fix it, so it is a pre-flight error naming the duplicated id, raised beside step 5's predecessor load — not a violation the retry loop can act on.
- Nothing else. A `row` target's resolution needs the predecessor — see below.

The rest joins the predecessor's feedback rows to the revision's by id:

- A predecessor feedback id absent from the revision → `VIOLATION_DROPPED_FEEDBACK`.
- **No `VIOLATION_INVENTED_FEEDBACK` rule here — step 6 owns this defect.** A model inventing `feedback-99` and citing it in a removal manufactures the reviewer-originated reason gate 1 demands, so it must be caught; but step 6's fourth rejection kind runs on the parsed reply *before* `stage.gates(envelope)` in `plan_tool/roadmap.py:_run_stage`, and it covers this case plus the predecessor-free one no gate can see. A rule here would therefore be unreachable, and ordering it first is worse: the same defect would draw two corrections, which is exactly what `test_a_targetless_reference_is_reported_once_not_by_both_gates` exists to prevent. Say so in the gate's docstring so a later author does not "restore" it.
- A surviving row whose `target` or `request` differs from the predecessor's → `VIOLATION_ALTERED_FEEDBACK_SOURCE`. The reviewer's words are source input, not model-authored prose. **Compare `request` after normalizing trailing whitespace** — `rstrip()` the whole value and each line before the equality test — because a reviewer's `request: |` block round-trips through `yaml.safe_dump` as a quoted scalar carrying a trailing newline, and a model re-emitting the same visible words without that newline would trip a violation on a request nobody changed. This is the plan's headline flow, so a false positive here is expensive. Step 1's rejection of a *global* literal-block representer stands: the normalization lives in this comparison, not in the renderer.
- State transitions → `VIOLATION_DISALLOWED_FEEDBACK_STATE`. Exactly one move is allowed: `open` → `awaiting-review`. An `open` row left `open` is a violation (the model owes a response to every active item), `awaiting-review` → anything is a violation, and `deferred` → anything is a violation. Deferring and reopening are the human's, done in the editor before the run.
- An `awaiting-review` or `deferred` row whose `proposed_response` differs from the predecessor's → `VIOLATION_ALTERED_CARRIED_RESPONSE`. Those rows are not sent as active guidance, so any change to them is an unrequested edit.
- A `row` target whose `row_id` is neither an id in `_rows_of(predecessor)` **nor an id named by one of the predecessor's removal records** → `VIOLATION_UNRESOLVED_FEEDBACK_TARGET`. **Resolve against the predecessor, never the revision** — that is what lets feedback ask for the removal of the row it names — and include the predecessor's `removed_id`s, or the design's own sanctioned flow deadlocks: feedback targets `entity-3`, the model drops it with a cited removal, and on the next run (before the reviewer has closed the row) carrying the row unchanged trips this rule, changing the target trips `VIOLATION_ALTERED_FEEDBACK_SOURCE`, and dropping it trips `VIOLATION_DROPPED_FEEDBACK`. A row carried unchanged from the predecessor must never be re-reported here.
- **A target that resolves against neither, in a row the *reviewer* wrote, is a pre-flight error naming the row — not a retry.** Only the reviewer can fix their own typo, so spending three attempts on it writes nothing and pressures the model toward the one edit `VIOLATION_ALTERED_FEEDBACK_SOURCE` forbids. Step 5 loads the predecessor; this check belongs beside that load, before any invoke.

Two deliberate non-checks, each worth a test and a docstring line:

- **The response text is never judged.** Whether it answers the request, how long it is, whether it repeats a prior response — none of that is observable here, and judging it is outside the plan's fence.
- **Feedback ids and design-row ids are separate namespaces.** Do **not** fold feedback ids into `check_duplicate_row_ids`. No consumer resolves against the union: a removal's `feedback_ids` resolve against feedback rows only, and an anchor or a `target.row_id` resolves against design rows only. The scope of a uniqueness check is set by the widest namespace something resolves against, and here that is two separate ones.

### Gate 3 — `check_settled_decisions`

Predecessor-only. For each predecessor decision whose `status` is `DecisionStatus.SETTLED`:

- The revision carries a decision with the same id → otherwise `VIOLATION_DROPPED_SETTLED_DECISION`. **A cited removal does not excuse this** — a settled decision is pinned until the human un-settles it.
- Its `status`, `chosen_option`, and `anchor` are unchanged → otherwise `VIOLATION_ALTERED_SETTLED_DECISION`.

Deliberately **not** compared: `rationale` and `rejected_alternatives`. The revision prompt (step 4) asks the model to keep them; the gate does not pretend it can decide whether a reworded rationale means the same thing. Say this in the docstring — an unused equality check here is exactly the field a later author "completes".

**Both settled messages must name the human action**: keep the decision as it stands, and say in `proposed_response` that the operator has to change the predecessor's status to `pending` first. The model cannot perform the un-settle itself, so a message that only states the rule leaves it with no move and spends the whole retry budget.

**The transitive block, which is the sharpest case in this step.** A design row that a `settled` decision anchors to cannot be removed *at all* while that decision stays settled — not even with a valid cited removal. Gate 1 would allow the drop, gate 3 pins the decision's `anchor`, and the shipped `check_decision_records` then reports the dangling anchor with a message telling the model to re-anchor to an id `01-domain.md` declares — the one move gate 3 forbids. Left unstated, the stage oscillates between those two messages until its budget is gone, and this fires *within* `01-domain.md` alone, so "place feedback in each affected artifact" is not even a candidate answer. The only legal move is to refuse the removal and say in `proposed_response` that the reviewer must set that decision to `pending` first. State it in the continuity message for a removal whose `removed_id` is a settled decision's anchor, and in gate 3's messages; step 4's revision contract states the same block so the model does not attempt the drop.

### Two cascade cases to expect, and the answer this step ships

A `--from-stage 1` re-entry re-runs stage 2 as well. If the domain revision drops an entity, `02-constraints.md` must lose the constraint anchored to it — but a removal needs a citation to feedback **in `02-constraints.md`**, and the reviewer wrote their request in `01-domain.md`. Same shape for a settled constraints decision anchored to a dropped domain row: `check_decision_records` wants the anchor to resolve, and gate 3 pins the anchor.

- **The two cases have different answers, and conflating them ships advice that cannot work.**
  - *An anchored **constraint** whose domain row was dropped* — answered by the plan's locality rule: the reviewer places a matching request in `02-constraints.md` too, and the constraints revision drops the constraint with its own cited removal. The gate message names that action.
  - *A **settled decision** anchored to a dropped row* — **not** answered by it. Gate 3's own rule says a cited removal does not excuse a settled decision, so no amount of feedback in either artifact unlocks it; the only move is the reviewer setting that decision to `pending` first. A message telling this operator to "place feedback in each artifact" prints advice that does nothing. Name the un-settle action instead.
- **Rejected alternative:** exempt a removal from the citation rule when the removed row's anchors no longer resolve. It turns "the anchor is gone" into a self-authorizing escape — a model that also proposes dropping the anchor unlocks the whole chain — and the check stops meaning anything.
- This cost is real and is worth naming in the gate docstrings rather than discovering during the real-run exercise.

### Gate-set wiring and the constraints that are not free to vary

- **Append the three gates to the end of both `DOMAIN_GATES` and `CONSTRAINTS_GATES`.** Declared order is violation order, so appending leaves the existing kind sequence in `test_violation_order_is_stable` intact.
- **Do not extend `_domain_rows` / `_constraints_rows` with feedback or removal rows.** They feed `check_inventory_has_prose` and `check_duplicate_row_ids`; adding review rows there would demand prose for a reviewer's feedback and fold feedback ids into the design-row namespace, both of which the plan's "excluded from the design-row prose-inventory gate" forbids. Reach the new collections through `artifact.feedback` / `artifact.removals` directly — both artifacts carry the same field names, so no kind dispatch is needed.
- **Every predecessor-derived rule short-circuits on `predecessor is None`.** `_load_and_regate_below` treats a below-stage violation as a hard pre-flight `RoadmapError`, and a first run has no predecessor at all — so a rule that fired without one would break re-entry outright. The three always-on rules were chosen because a settled, already-written artifact satisfies them: its removals carry model-written rationales and citations, and its feedback ids are unique.
- **Update the counts in this module.** The docstring's "The eight gates here" and the `# The eight gates` section comment both become eleven. `ROADMAP_FORMAT.md` and `CLAUDE.md` carry the same claim and belong to steps 8 and 10.
- **Add a clause to `Violation.row_id`'s docstring.** A dropped design row and a removal's `removed_id` are real row ids, so they populate `row_id`; the existing "`None` only when the defect is an *absent* row" reading covers a missing quality attribute, which has no row id at all. Keep `row_id` set wherever there is an id, so `test_every_violation_names_its_row_id` extends to the new gates.
- **Watch two token bans.** `test_module_touches_no_filesystem_and_no_subprocess` asserts the source contains none of `invoker`, `subprocess`, `open(`, `read_text`, `Path`. Two traps here: a message or comment written as `open(...)` trips the third, and a `Path`-typed hint or a capitalized "Path" in prose trips the fifth. The word `open` on its own — the feedback state — is fine.

## Tests

All new cases go in `tests/test_roadmap_gates.py`, in the file's existing section-comment layout, and follow its rule of building step 1's dataclasses directly rather than parsing text. Extend the builders first: `make_domain` / `make_constraints` gain `feedback=()` and `removals=()`; `domain_envelope` / `constraints_envelope` gain `predecessor=None`; add `feedback_row(...)` and `removal(...)` helpers beside the existing `disposition_row`.

### Tests for this step

Approx. 49 cases — about 45 new and 4 rewritten. Every one must be green before this step is done, and `tests/test_roadmap.py`, `tests/test_roadmap_artifacts.py`, and `tests/cli/test_roadmap_cmd.py` must stay green **without being edited**.

Continuity gate:

- `test_unchanged_revision_passes_continuity` — every predecessor id present, no removals.
- `test_dropped_design_row_violates` — names the dropped id and the artifact.
- `test_every_dropped_row_is_reported_not_just_the_first` — two dropped rows, two violations.
- `test_dropped_row_with_a_cited_removal_passes` — the sanctioned path.
- `test_removal_with_a_blank_rationale_violates` — fires with no predecessor too.
- `test_removal_citing_no_feedback_violates` — fires with no predecessor too.
- `test_removal_naming_a_row_the_revision_still_declares_violates` — fires with no predecessor too.
- `test_removal_citing_an_unknown_feedback_id_violates` — resolution is against the predecessor's feedback.
- `test_new_removal_naming_a_row_the_predecessor_never_had_violates`.
- `test_a_removal_carried_from_the_predecessor_is_not_rejudged` — the rule that stops a human close from spinning the loop.
- `test_a_hand_edited_carried_removal_is_rejudged` — identity is the whole record, not `removed_id`.
- `test_predecessor_derived_continuity_is_inert_without_a_predecessor`.

Feedback integrity:

- `test_carried_feedback_answered_with_a_response_passes`.
- `test_deleted_feedback_row_violates` — the model may not close feedback.
- `test_altered_request_violates` and `test_altered_target_violates` — one case each.
- `test_open_feedback_left_open_violates` — every active item owes a response.
- `test_open_becoming_awaiting_review_passes` — the one allowed move.
- `test_open_becoming_deferred_violates` — deferring is the human's.
- `test_awaiting_review_reverted_to_open_violates` — reopening is the human's.
- `test_awaiting_review_response_rewritten_violates`.
- `test_deferred_row_carried_unchanged_passes` and `test_deferred_row_altered_violates`.
- *(no `test_model_added_feedback_row_violates` — the fabricated-feedback defect is step 6's fourth rejection kind, and its cases live there.)*
- `test_duplicate_feedback_ids_violate_once_per_id` — fires with no predecessor.
- `test_a_feedback_id_may_equal_a_design_row_id` — the two namespaces stay separate.
- `test_row_target_naming_a_predecessor_row_resolves`.
- `test_row_target_may_name_a_row_the_revision_removed` — the case predecessor-scoped resolution exists for.
- `test_row_target_naming_an_id_the_predecessor_never_had_violates`.
- `test_artifact_target_needs_no_row_id`.
- `test_response_text_is_never_judged` — an odd or repeated response passes.
- `test_feedback_integrity_is_inert_without_a_predecessor`.

Settled-choice gate:

- `test_settled_decision_carried_unchanged_passes`.
- `test_changed_chosen_option_on_a_settled_decision_violates`.
- `test_changed_anchor_on_a_settled_decision_violates`.
- `test_settled_becoming_pending_violates` — un-settling is the human's.
- `test_settled_decision_removed_violates_even_with_a_cited_removal`.
- `test_settled_decision_rationale_may_change` and `test_settled_decision_alternatives_may_change` — the two deliberate non-checks.
- `test_pending_predecessor_decision_is_unpinned` — a `pending` decision may change freely.
- `test_settled_message_names_the_un_settle_action` — the message gives the model a move it can make.
- `test_settled_finality_is_inert_without_a_predecessor`.

Gate sets, ordering, and the seam:

- `test_new_gates_are_inert_on_a_first_run` — both gate sets over a no-predecessor envelope return exactly the violations they return at HEAD. The main regression guard.
- `test_clean_revision_yields_no_violations` — both gate sets over a conforming revision envelope.
- `test_predecessor_defaults_to_none` — `ArtifactEnvelope(domain=…)` still constructs, which is what keeps `plan_tool/roadmap.py:_build_envelope` compiling.
- `test_feedback_and_removal_rows_stay_out_of_the_prose_and_duplicate_id_gates` — a body naming no feedback id passes `check_inventory_has_prose`, and a feedback id colliding with a design-row id passes `check_duplicate_row_ids`.
- `test_gates_accept_a_parsed_conforming_revision` — the second module-boundary case: parse feedback-bearing predecessor and revision text with step 1's parser, run both gate sets, expect empty.
- Rewritten: `test_domain_gate_set_runs_every_domain_gate` — extend `_domain_breaking_every_gate` with a predecessor that trips each new gate once, so the `len(violations) == len(DOMAIN_GATES)` assertion keeps its meaning instead of being loosened.
- Rewritten: `test_constraints_gate_set_runs_every_constraints_gate` — same treatment for `_constraints_breaking_every_gate_but_non_empty`.
- Rewritten: `test_violation_order_is_stable` — the expected kind list grows by the three new gates' kinds, in tuple order.
- Rewritten: `test_every_violation_names_its_row_id` — add one parametrized case per new gate, all with `expects_row_ids=True`.
- The two layering cases, `test_module_imports_only_the_artifact_leaf` and `test_module_touches_no_filesystem_and_no_subprocess`, stay green unchanged.

## Acceptance criteria

- `ArtifactEnvelope(domain=d)` and `ArtifactEnvelope(domain=d, constraints=c)` both construct, and `envelope.predecessor` is `None`.
- With `predecessor=None`, `run_domain_gates` and `run_constraints_gates` return the same violation lists they return at HEAD for the same inputs.
- `check_design_row_continuity` returns a `dropped-design-row` violation naming the missing id when a predecessor row is absent, and returns `[]` when the same row is covered by a removal carrying a non-blank rationale and a predecessor feedback id.
- `check_feedback_integrity` returns a violation when a predecessor feedback row is missing, when its `request` or `target` differs, when an `open` row is still `open`, and when an `awaiting-review` or `deferred` row changed in any field.
- `check_settled_decisions` returns a violation when a predecessor `settled` decision is absent or when its `status`, `chosen_option`, or `anchor` differs, and returns `[]` when only its `rationale` or `rejected_alternatives` differ.
- Every violation the three gates emit names its `artifact` and its `row_id` inside `message`.
- `DOMAIN_GATES` and `CONSTRAINTS_GATES` each hold 9 gates; `rg -c 'def check_' plan_tool/roadmap_gates.py` reports 11.
- `rg -n 'eight gates' plan_tool/roadmap_gates.py` returns nothing.
- `rg -n 'feedback|removals' plan_tool/roadmap.py plan_tool/cli/roadmap_cmd.py plan_tool/roadmap_artifacts.py` shows no new consumer edit outside step 1's contract work.
- `uv run pytest tests/test_roadmap_gates.py tests/test_roadmap.py tests/test_roadmap_artifacts.py tests/cli/test_roadmap_cmd.py -q` is green, with the last three files unmodified, **except** for one named, bounded exception: `tests/test_roadmap.py:test_domain_prompt_states_every_domain_gate_rule` and its constraints sibling are parametrized over the gate tables, so appending three gates with no `_GATE_PROMPT_SUBJECTS` entry leaves those two parametrized **tests** red across **all six of their cases** — three gates × two templates (`check_design_row_continuity`, `check_feedback_integrity`, `check_settled_decisions`, each in the domain and constraints sibling). Verified on the landed step: `6 failed, 421 passed` across the roadmap suites. Step 4 adds the prompt rules and owns that repair; this step must not be judged against those cases, and must not silence them by editing the test.
- `uv run pytest tests/test_duplication.py -q` is green with no new `ALLOWED_DUPLICATE_GROUPS` entry.
- `git diff --name-only` lists exactly `plan_tool/roadmap_gates.py` and `tests/test_roadmap_gates.py`.

## References

- [Increase output consistency — Claude Docs](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency) — a stable schema and a closed state vocabulary are what make the lifecycle transitions this step checks reproducible enough to gate on.
- [Long context prompting tips — Claude Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips) — read for why each violation message must stand alone: it arrives in the retried prompt as one bullet with no surrounding document.
- [Prompting best practices (Claude 4) — Claude Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices) — the scoped-edit framing these gates enforce from the outside; useful for judging whether a violation message states a move the model can actually make.

## Applicable guardrails

- **The plan's "## Out of scope", no judging whether a revision honored feedback.** This binds this step hardest, because a feedback gate is exactly where a "did the response actually answer it" check feels natural. These gates compare ids, states, and stored strings for equality and never rate a response. `proposed_response` is compared only for the carried rows that must not change at all.
- **The plan's "## Out of scope", no automatic transition out of awaiting-review.** The gate permits one transition and forbids the rest; it never rewrites a state, because it returns violations and mutates nothing.
- **The plan's "## Out of scope", no cap or rejection based on feedback length, shape, count, or semantics.** Nothing here counts feedback rows, bounds a request, or reads what a request says.
- **The plan's "## Out of scope", general value stability for non-settled rows.** Continuity checks that a row's *id* survives or its disappearance is declared. It never compares a surviving row's fields, and only a `settled` decision has any field pinned.
- **The plan's "## Out of scope", cross-artifact feedback propagation.** Feedback and removal rules read the artifact under check and its own predecessor. Never the other artifact's feedback.
- **The plan's "## Architecture", the one-way dependency line and the pure relation-gate layer.** `plan_tool/roadmap_gates.py` keeps `plan_tool.roadmap_artifacts` as its only first-party import, returns violations, and raises nothing. The two layering tests are the guard.
- **The plan's "## Architecture", a stage is data.** The three gates join the existing gate-set tuples and take the same one envelope, so `plan_tool/roadmap.py`'s stage table gains nothing and its loop gains no branch.

## Deferred

- **Loading the predecessor off disk and filling `envelope.predecessor`** — step 5, which owns the predecessor envelope. Until it lands, the field is always `None` in production and the three gates are inert.
- **The revision prompt and the active-feedback block** — step 4. This step decides what an acceptable revision *is*; nothing here renders a prompt or tells the model anything.
- **Performing the `open` → `awaiting-review` transition on a write** — step 6. The gate checks that the transition happened; it never applies one.
- **The run-log delivery event** — step 3.
- **The operator summary counting feedback awaiting review** — step 7.
- **Updating `ROADMAP_FORMAT.md`'s gate table, its "eight gates" claims, and the per-stage gate counts** — step 8, which reads whatever actually landed here. `CLAUDE.md`'s "eight relation gates" clause is step 10's.
- **Softening the cascade cost** — an exemption for a removal forced by an upstream change is not taken here; the plan's answer is that the reviewer places feedback in each affected artifact. File a `BACKLOG.md` entry if the real-run exercise in step 9 shows the duplication is unworkable.
- **Comparing a settled decision's `rationale` or `rejected_alternatives`** — not taken. Whether a rewording means the same thing is not decidable here, and an equality check on prose would fail on formatting alone.
- **Requiring a reopened row's new response to differ from its stale one** — not taken. It is a judgment about whether the model re-engaged, which the plan's fence puts outside this position.
- **Folding the id-uniqueness and dangling-reference rules shared with `plan_tool/review.py:validate_feature_refs` into one helper** — declined, not left open. Three data types and three result types share a rule and a message shape, not code worth moving, and importing `review.py` would end this module's leaf status.
