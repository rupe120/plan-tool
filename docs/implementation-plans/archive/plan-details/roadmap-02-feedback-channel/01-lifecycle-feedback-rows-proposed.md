> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Carry feedback rows, model responses, and cited removals in the roadmap artifact contract

## Summary

Teach `plan_tool/roadmap_artifacts.py` two new frontmatter collections that both staged artifacts may carry: `feedback` (a reviewer's natural-language request, its target, its lifecycle state, and the model's optional proposed response) and `removals` (a record naming a design row that was dropped, why, and which feedback asked for it). Parse and render land together, so a revision that comes back through `roadmap.py:_write_artifact` keeps the reviewer's text instead of losing it to the renderer. The key design decision: both collections are **omitted entirely when empty**, and the two existing key constants `DOMAIN_ROW_KEYS` / `CONSTRAINTS_ROW_KEYS` keep naming only design rows — that is what keeps a first run's bytes and the stage prompts' pinning test unchanged. On green, an artifact with no feedback renders exactly as it does today, and an artifact with feedback round-trips every field through `parse(render(x)) == x`.

## Table of Contents

- [Summary](#summary) — what changes and what is observable on green.
- [Why](#why) — the channel cannot exist while the contract silently drops it.
- [Input](#input) — the position-01 contracts this step builds on.
- [Files (creates vs edits)](#files-creates-vs-edits) — two edits, no new files.
- [Implementation](#implementation) — the new types, the shape rules, and the rules that are deliberately *not* shape rules.
- [Tests](#tests) — the roster in `tests/test_roadmap_artifacts.py` and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — YAML grammar and PyYAML behavior this step depends on.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step's code.
- [Deferred](#deferred) — everything the later steps own.

## Why

Today a reviewer who writes a `feedback:` block into `01-domain.md` loses it on the next write. The frontmatter schema is open, so `parse_domain_artifact` ignores the unknown key; `render_domain_artifact` emits only the contract's keys; and `plan_tool/roadmap.py:_write_artifact` persists the renderer's output rather than the model's raw reply. The reviewer's text is dropped between those two facts with nothing reporting it. Every later step in this plan reads or writes feedback — the gates in step 2, the revision prompt in step 4, the predecessor envelope in step 5, the write path in step 6 — and none of them can hold a row the contract does not know about. This step is the one that makes the row exist.

## Input

This step consumes only what position 01 already ships in `plan_tool/roadmap_artifacts.py`, and must keep each of these true:

- **The open-schema rule.** An unnamed frontmatter key is ignored, not rejected (see the module docstring's "The frontmatter schema is **open**" paragraph). The new keys stop being ignored; nothing else changes.
- **The round-trip property.** `parse(render(x)) == x` for both artifacts, pinned by `test_domain_artifact_round_trips_through_render_and_parse` and its constraints sibling. The new collections must satisfy it too.
- **The shape/relation split.** Parsing raises `RoadmapArtifactError`; relations return violations from `plan_tool/roadmap_gates.py`. The module docstring's "**Shape is checked here; relations are not**" paragraph is the contract this step extends, not rewrites.
- **The existing row helpers** — `_row_id`, `_text_at`, `_row_text`, `_id_list`, `_require_key`, `_iter_rows`, and the `_coerce_status` / `_coerce_disposition` shape for a closed vocabulary. Reuse them; they already produce the message wording the retry loop expects.
- **The renderer is the writer.** `plan_tool/roadmap.py:_write_artifact` writes `stage.render(artifact)`, so a field the renderer drops is gone from disk. This is why the serializer lands in the same step as the parser.
- **Downstream consumers, named by owning step, not by mechanism.** Step 2 judges the new rows against a predecessor (continuity, feedback integrity, settled choice). Step 4 renders active feedback into the revision prompt. Step 5 loads the predecessor. Step 6 writes the allowed state transition. Step 8 documents the names this step mints — so the names settle **here**, and step 8 records whatever actually landed.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/roadmap_artifacts.py` — add the two closed vocabularies (`FeedbackState`, `FeedbackTargetKind`), the three row types (`FeedbackTarget`, `FeedbackRow`, `RemovalRecord`), the `REVIEW_ROW_KEYS` constant, two defaulted fields on each of `DomainArtifact` and `ConstraintsArtifact`, the parse helpers, and the render mappings.
- `tests/test_roadmap_artifacts.py` — add the cases listed in [Tests](#tests), plus feedback-bearing fixtures kept **separate** from `DOMAIN_TEXT` / `CONSTRAINTS_TEXT`.

## Implementation

### What must be true when this is done

- Both `DomainArtifact` and `ConstraintsArtifact` carry `feedback: tuple[FeedbackRow, ...]` and `removals: tuple[RemovalRecord, ...]`, each defaulting to `()`.
- An artifact with neither collection renders **exactly the bytes it renders today**.
- An artifact with either collection round-trips every field.
- Nothing outside `plan_tool/roadmap_artifacts.py` and `tests/test_roadmap_artifacts.py` changes, and the other three roadmap suites stay green **unedited**.

### The new names (settle them here — step 8 documents whatever lands)

- `FeedbackState` — `OPEN = "open"`, `AWAITING_REVIEW = "awaiting-review"`, `DEFERRED = "deferred"`. Follow `DecisionStatus`' `(str, enum.Enum)` shape.
- `FeedbackTargetKind` — `ARTIFACT = "artifact"`, `ROW = "row"`.
- `FeedbackTarget` — frozen dataclass, `kind: FeedbackTargetKind` and `row_id: Optional[str] = None`.
- `FeedbackRow` — `id`, `target: FeedbackTarget`, `request: str`, `state: FeedbackState`, `proposed_response: Optional[str] = None`.
- `RemovalRecord` — `removed_id: str`, `rationale: str`, `feedback_ids: tuple[str, ...]`. It mints **no `id` of its own**: nothing references a removal, and `removed_id` is the anchor every violation message will name. `feedback_ids` is spelled to match the module's existing `entity_ids` / `anchor_ids` so it can reuse `_id_list` unchanged.
- `REVIEW_ROW_KEYS = ("feedback", "removals")` — one constant shared by both artifacts, alongside the two existing per-artifact design-key tuples.

### The target is a nested mapping

Recommended shape:

```yaml
feedback:
- id: feedback-1
  target:
    kind: row
    row_id: entity-1
  request: Split the cart out of the order entity.
  state: open
```

- **Keep the tag and its payload together.** An `artifact` target then simply has no `row_id` key, instead of a sibling key that must be absent.
- **Rejected alternative:** flat `target: row` + `target_row_id: entity-1`. Fewer nested levels, but it puts two keys in a co-dependency the reader has to infer.
- Parse the nested mapping with a small helper in the shape of `_parse_alternatives` (present, a mapping, then per-key checks).

### Where the line between shape and relations falls

This is the part that is not free to vary. Put these in the **parser** (raise `RoadmapArtifactError`):

- `state` and `target.kind` are known members. Mirror `_coerce_status`' message: name the offending value, the row id, and the known members.
- **Tag and payload agree.** `kind: row` requires a non-blank `row_id`; `kind: artifact` must not carry one. A tag that disagrees with its payload has no defensible reading, so there is nothing for a gate to report against.
- **`awaiting-review` carries a non-blank `proposed_response`.** The state is *defined* by carrying a response; a blank one claims a review exists that does not. This is a deliberate exception to the module's "emptiness of prose fields is a gate's judgment" rule in `_text_at` — say so in the docstring.
- Required keys present and typed: `id` (non-blank, via `_row_id`), `request`, `state`, `target` on a feedback row; `removed_id`, `rationale`, `feedback_ids` on a removal.
- A present collection is a list of mappings — `_iter_rows` already gives this.

Leave these to the **gates in step 2** (they must parse without raising, and each gets a test saying so):

- a `row` target naming an id no artifact defines;
- a removal citing no feedback ids, or a feedback id nothing declares;
- a removal naming a row the artifact still contains;
- a blank `rationale` or a blank `request`;
- two feedback rows sharing an id;
- an `open` or `deferred` row that still carries a `proposed_response`.

That last one is a **deliberate allowance**, not an oversight: the plan's reopen path has the reviewer flip an `awaiting-review` row back to `open` and clear or replace its response, so the prior response stays readable beside the request while they decide.

### Rules that keep the change additive

- **Append the two fields after `body`, with `()` defaults.** Every out-of-step construction of these dataclasses uses keywords — `tests/test_roadmap.py`'s `_domain` / `_constraints` helpers, `tests/test_roadmap_gates.py`'s `make_domain` / `make_constraints`, and `tests/cli/test_roadmap_cmd.py`'s `_e2e_domain_text` — so defaulted fields keep all three compiling untouched.
- **Do not add the new keys to `DOMAIN_ROW_KEYS` / `CONSTRAINTS_ROW_KEYS`.** Those two constants feed `tests/test_roadmap.py`'s `_required_domain_row_keys` / `_required_constraints_row_keys`, which assert the stage prompts' frontmatter-inventory section names every declared key. Adding `feedback` there would redden a test in a file this step does not own, and would demand a prompt edit this step does not scope. Mint `REVIEW_ROW_KEYS` instead.
- **Render the review keys after the design keys, and only when non-empty.** An always-emitted `feedback: []` would put a new key in every first-run artifact, which the plan's "first-run behavior unchanged" criterion forbids. It also keeps `test_row_key_constants_match_the_rendered_frontmatter` green as written.
- **Omit `row_id` and `proposed_response` when absent** rather than rendering `null` — the same rule `_field_mapping` already applies to a non-reference field's `entity_id`.
- **Dump `.value`, never the enum member.** PyYAML's `SafeDumper` raises `RepresenterError` on an `Enum` subclass even when it inherits from `str`; `_decision_mapping` already carries the comment explaining it. Follow the local convention — do **not** import `plan_tool/parser.py:_coerce_enums`, which would end this module's leaf status.
- **Keep rows an ordered tuple with duplicates intact.** Do not key `feedback` by id: step 2's duplicate check needs both rows to exist.

### What this step does *not* have to touch, and why that is worth knowing

`plan_tool/roadmap_gates.py` enumerates rows through `_domain_rows` and `_constraints_rows`, which spell out the row kinds one by one rather than deriving them from the artifact's dataclass fields. So the new collections are invisible to `check_inventory_has_prose` and `check_duplicate_row_ids` for free — the plan's "feedback and removal records are excluded from the design-row prose-inventory gate" holds with **no edit to a file outside this step's list**. Confirm it with a grep rather than assuming (see [Acceptance criteria](#acceptance-criteria)).

### Two gotchas

- **A multi-line request keeps its value but loses its formatting.** `yaml.safe_dump` re-emits a reviewer's `request: |` literal block as a single-quoted continuation. The value round-trips exactly — which is what step 2's immutability check compares — but the file the reviewer reads back is re-styled. Do **not** fix this here with a literal-block representer: it would also re-style existing prose fields and change first-run bytes. Pin the value-level survival with a test and leave the styling alone.
- **Do not fold `_coerce_status` and `_coerce_disposition` into a shared helper while adding the two new coercers.** That is a behavior-preserving refactor of existing code, and mixing it into this feature step is exactly the split the purity check exists to catch. The new helpers will not trip `tests/test_duplication.py`: it normalizes past docstrings, function names, and parameter names only, and these bodies differ in enum class and message literals.

## Tests

All new cases go in `tests/test_roadmap_artifacts.py`, in the file's existing section-comment layout. Keep `DOMAIN_TEXT` and `CONSTRAINTS_TEXT` **feedback-free** — they are what proves the unchanged first-run rendering — and splice feedback in through new helpers built on `_domain_frontmatter()` / `_constraints_frontmatter()`.

### Tests for this step

Approx. 31 new cases. Every one must be green before this step is done, and the existing cases in this file plus `tests/test_roadmap.py`, `tests/test_roadmap_gates.py`, and `tests/cli/test_roadmap_cmd.py` must stay green **without being edited** — that is the real proof the change is additive.

Closed vocabularies:

- `test_feedback_state_members` — the three values, in declared order.
- `test_feedback_target_kind_members` — `artifact` and `row`, nothing else.
- `test_unknown_feedback_state_raises_naming_the_value` — the bad value, the feedback id, and the known members all appear in the message.
- `test_unknown_target_kind_raises_naming_the_value` — same message shape.

Shape rules that raise:

- `test_row_target_without_a_row_id_raises` — names the feedback id and `row_id`.
- `test_artifact_target_with_a_row_id_raises` — a tag disagreeing with its payload is a parse error.
- `test_blank_target_row_id_raises` — `row_id` is identifier-like, not prose.
- `test_target_that_is_not_a_mapping_raises` — names the feedback id and the type it got.
- `test_awaiting_review_without_a_response_raises` — names the feedback id and `proposed_response`.
- `test_awaiting_review_with_a_blank_response_raises` — blank is the same defect as absent for this state.
- `test_feedback_missing_a_required_key_raises` — parametrized over `id`, `request`, `state`, `target`.
- `test_non_list_feedback_collection_raises` — matches the existing `'entities' must be a list of rows` wording.
- `test_removal_missing_a_required_key_raises` — parametrized over `removed_id`, `rationale`, `feedback_ids`.
- `test_removal_feedback_ids_must_hold_non_empty_strings` — reuses `_id_list`'s message.

Deliberate non-checks (each asserts parsing succeeds — these are what make the step-1/step-2 ownership split real):

- `test_row_target_naming_an_undefined_id_parses` — resolution is a step-2 gate.
- `test_open_feedback_may_carry_a_stale_response` — a reopened row keeps the prior response readable.
- `test_deferred_feedback_may_carry_a_response` — same allowance.
- `test_duplicate_feedback_ids_survive_as_separate_rows` — the duplicate gate needs both rows.
- `test_blank_request_and_blank_rationale_parse` — prose emptiness stays a gate's judgment.
- `test_removal_citing_no_feedback_parses` — "cites at least one" is step 2's continuity gate.
- `test_removal_naming_a_row_the_artifact_still_declares_parses` — a relation, not a shape.

Rendering and round-trip:

- `test_domain_feedback_and_removals_round_trip` — `parse(render(x)) == x` with both collections populated.
- `test_constraints_feedback_and_removals_round_trip` — the constraints artifact carries both too.
- `test_absent_review_collections_render_no_new_key` — neither `feedback:` nor `removals:` appears when both are empty.
- `test_review_keys_render_after_the_design_keys` — rendered key order is the design tuple followed by `REVIEW_ROW_KEYS`.
- `test_artifact_target_renders_without_a_row_id_key` — no `row_id: null`.
- `test_absent_proposed_response_renders_no_key` — no `proposed_response: null`.
- `test_rendered_feedback_enum_values_are_plain_strings` — `state: open` present; no `FeedbackState`, no `!!python`.
- `test_a_multi_line_request_round_trips_by_value` — the reviewer's block scalar survives as a value, quoting style aside.

Constants and layering:

- `test_review_row_keys_match_the_rendered_frontmatter` — the constant is the wire truth, not a hand-copied list.
- `test_design_row_key_constants_exclude_the_review_keys` — `DOMAIN_ROW_KEYS` and `CONSTRAINTS_ROW_KEYS` still name design rows only.
- The existing `test_leaf_imports_no_first_party_module` and `test_leaf_declares_no_invoker_seam` stay green unchanged — the new code adds no first-party import and none of the words those tests ban.

## Acceptance criteria

- `parse_domain_artifact` and `parse_constraints_artifact` return `feedback` and `removals` as tuples; an absent collection parses to `()`.
- `render_domain_artifact(parse_domain_artifact(DOMAIN_TEXT))` produces frontmatter whose keys are exactly `DOMAIN_ROW_KEYS` — no `feedback` key, no `removals` key.
- For an artifact carrying both collections, `parse(render(x)) == x` holds for domain and constraints alike.
- Feeding an `awaiting-review` row with no `proposed_response`, a `row` target with no `row_id`, or an `artifact` target with a `row_id` each raises `RoadmapArtifactError` whose message names the feedback row's id.
- Feeding a `row` target that names an undefined id, a removal citing zero feedback ids, or two feedback rows sharing an id parses without raising.
- `rg 'feedback|removals|FeedbackRow|RemovalRecord' plan_tool/roadmap_gates.py plan_tool/roadmap.py plan_tool/cli/roadmap_cmd.py` returns nothing — the contract landed with no consumer edit.
- `uv run pytest tests/test_roadmap_artifacts.py tests/test_roadmap.py tests/test_roadmap_gates.py tests/cli/test_roadmap_cmd.py -q` is green, with the last three files unmodified.
- `uv run pytest tests/test_duplication.py -q` is green with no new `ALLOWED_DUPLICATE_GROUPS` entry.
- `git diff --name-only` lists exactly `plan_tool/roadmap_artifacts.py` and `tests/test_roadmap_artifacts.py`.

## References

- [YAML 1.2.2](https://yaml.org/spec/1.2.2/) — the normative grammar for the nested target mapping, the lifecycle rows, and the removal records this step adds to the frontmatter.
- [PyYAML documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — read for `safe_dump`'s scalar-style selection (why a multi-line request comes back single-quoted) and for why `SafeDumper` has no representer for an `Enum` subclass.
- [Increase output consistency — Claude Docs](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency) — the schema minted here is what a later stage prompt asks the model to emit; stable field names and a closed vocabulary are what make that reproducible.

## Applicable guardrails

- **The plan's "## Out of scope", no cap or rejection on feedback length, shape, count, or semantics.** This step validates a feedback *row's structure* — its keys and its lifecycle vocabulary — and must not cap request length, cap the number of rows, or judge what a request says. The fence bans judging the reviewer's content, not requiring the row to carry an id.
- **The plan's "## Out of scope", no second store, sidecar, or hidden feedback state.** Everything this step adds lives in the artifact's frontmatter. Add no file, no `.plan-tool/` state, and no cache.
- **The plan's "## Out of scope", no automatic transition out of awaiting-review.** The parser reads `state` as written and never defaults, normalizes, or advances it. An absent `state` is an error, not a defaulted `open` — a defaulted lifecycle state would be the tool deciding a row's review status.
- **The plan's "## Out of scope", no judging whether a revision honored feedback.** `proposed_response` is stored as text and compared to nothing.
- **The plan's "## Out of scope", cross-artifact feedback propagation.** Each artifact carries its own collections; nothing here reads the other artifact.
- **The plan's "## Architecture", the one-way dependency line.** `plan_tool/roadmap_artifacts.py` stays a stdlib-plus-YAML leaf — no first-party import, including the tempting `plan_tool/parser.py:_coerce_enums`. The two existing layering tests are the guard.
- **The plan's "## Acceptance criteria", first-run behavior unchanged.** This is the fence that binds this step hardest, because the natural renderer is one that always emits every contract key. Omit-when-empty is what satisfies it.

## Deferred

- **Every gate over the new rows** — predecessor continuity, feedback integrity, cited-removal validity, settled-choice finality, feedback-id uniqueness, "a removal cites at least one feedback id", "a rationale is non-blank", and target resolution against the predecessor inventory. Step 2 owns all of them, in `plan_tool/roadmap_gates.py`.
- **Deciding whether feedback ids share the design-row id namespace** — nothing this step ships resolves an id across both spaces, so `check_duplicate_row_ids` keeps its current scope. Step 2 decides whether a separate feedback-id uniqueness check is warranted.
- **The run-log delivery event** — step 3.
- **The revision prompt and its active-feedback block** — step 4.
- **Loading the predecessor artifact and building the predecessor envelope** — step 5.
- **Performing the `open` → `awaiting-review` transition on a write** — step 6.
- **The operator summary naming feedback awaiting review** — step 7.
- **Documenting these names in `ROADMAP_FORMAT.md`** — step 8, which reads whatever actually landed here rather than transcribing this file.
- **A literal-block YAML dumper for multi-line prose fields** — not taken. It would re-style existing fields and change first-run bytes. File a `BACKLOG.md` entry if reviewer experience later demands it.
- **Folding `_coerce_status`, `_coerce_disposition`, and the two new coercers into one shared helper** — a behavior-preserving refactor of existing code, out of place in a feature step. Route to `BACKLOG.md` or a reconcile pass.
