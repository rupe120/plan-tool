> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Have the intent-presence finding carry the missing step ids in a parseable directive

## Summary

Append a machine-readable directive marker to the tail of each `check_intent_presence` finding's `suggested_action` in `plan_tool/review.py` — `→ intent plan` on the plan-level finding, `→ intent steps: 1, 3` on the step roll-up — and add the frozen `IntentAction` record plus a `render_intent_action` / `parse_intent_action` writer-reader pair beside the shipped merge grammar. The design decision is to **mirror** `render_merge_action` / `parse_merge_action` / `MergeAction` rather than generalize them into one shared parser: the plan's fence allows no reorganization, and folding a shipped grammar into a new one inside a feature step is exactly the mixed change the repo splits. Nothing else about the finding moves — same two findings per plan, same `info` severity, same `step_id=None`, same recommendation ids, same never-echo-the-value property. On green, a consumer holding only the `Recommendation` recovers the exact target set without a plan file, a re-parse, or a second run of the check.

## Table of Contents

- [Summary](#summary) — what the step does and what is true on green.
- [Why](#why) — why the ids are unreachable today and why prose-scraping is the wrong recovery.
- [Input](#input) — the four contracts this step reads, and what the directive cannot tell a consumer.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched and the per-file edits.
- [Implementation](#implementation) — the grammar, the constraints that are not free to vary, and the alternatives rejected.
- [Tests](#tests) — the cases this step adds and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checks a reviewer or CI can run.
- [References](#references) — the docs bearing on a frozen record and a marker regex.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step's code.
- [Deferred](#deferred) — the walk-side wiring and later steps this one leaves alone.

## Why

The roll-up finding names the steps it flagged **only in human prose** — `Step(s) 1, 3 carry no usable intent:` in `body`, repeated in `suggested_action`. Both findings also carry `step_id=None`, because they are plan-wide by design. So a consumer holding the finding has no supported way to learn which steps it meant. Step 7 dispatches step 4's proposer, whose bridge takes an explicit `step_ids` set; its only options today are to regex the sentence, or to re-run `check_intent_presence` against a freshly parsed plan and hope the answer matches the finding the operator is looking at. The second is the real hazard: the operator confirms one target set and the bridge writes another.

`plan_tool/review.py` already hit this exact shape once. The comment above `MERGE_ACTION_MERGE` records it — the `granularity-merge` source has two producers, the plan-wide finding sets `step_id=None`, and its id set is buried inside a fingerprint that `_make_rec_id` hashes away. The answer there was a single machine marker on `suggested_action` with one writer and one reader. `intent-presence` matches that shape point for point, so it gets the same answer.

## Input

This step reads four contracts and changes only the first.

- **`plan_tool/review.py:check_intent_presence`** — emits at most two findings per plan, both `source=INTENT_PRESENCE_SOURCE`, both `severity="info"`, both `step_id=None`. The roll-up's target set is the local `missing_ids` list, already sorted. Its docstring records the two properties this step must not disturb: the at-most-two roll-up shape, and that the finding never echoes the value it read.
- **`plan_tool/review.py:_make_rec_id`** — hashes an explicit `fingerprint` string, never `suggested_action`. The plan-level finding passes `"plan-intent"`; the roll-up passes `"step-intent:" + ids`. Appending a marker therefore leaves both recommendation ids unchanged, which is what keeps a saved sidecar from re-reporting the same finding as new.
- **`plan_tool/review.py:render_merge_action` / `parse_merge_action` / `MergeAction`** — the shipped instance of this pattern, read as the model. `MergeAction`'s docstring states the stance to copy: an in-memory classification result only, never serialized, so `suggested_action`'s field shape is unchanged. `parse_merge_action` source-guards internally before touching the regex; that guard is what lets a caller treat a non-`None` parse as "this is a routable directive".
- **Step 4's proposer bridge** — step 4 produces `plan_tool/intent_proposal.py`, whose bridge takes an explicit `step_ids` set and re-parses the plan itself. That signature is what fixes the directive's payload: an ordered set of step ids, plus a way to say "the plan-level field" with no ids at all.

**What the directive cannot tell a consumer.** It records which targets the finding named *when it fired* — nothing more. It does not assert those targets still lack an intent (step 4's bridge re-parses and re-checks that), and it carries no intent text, no quality signal, and no ordering preference. A directive is a pointer to gaps, not a judgment about them.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — add the two target constants, the marker regex, the frozen `IntentAction`, and the `render_intent_action` / `parse_intent_action` pair; append the rendered marker to the tail of both findings' `suggested_action` inside `check_intent_presence`.
  - `tests/test_review.py` — add a grammar test class beside `TestMergeActionGrammar`, and extend `TestCheckIntentPresence` with the directive cases.

## Implementation

**What must be true when the step is done.** Given only a `Recommendation` produced by `check_intent_presence`, a consumer can decide (a) whether it is an intent-presence directive at all and (b) exactly which targets it names — the plan-level field, or an ordered tuple of step ids — with no plan file open and no second run of the detector.

**The grammar — two arms, one marker.** One way, and the one that matches the sibling:

- `→ intent plan` on the plan-level finding.
- `→ intent steps: 1, 3` on the roll-up.
- Constants for the two target tokens (something like `INTENT_TARGET_PLAN` / `INTENT_TARGET_STEPS`) so the renderer, the parser, and step 7's dispatcher key on one symbol — the same single-sourcing `INTENT_PRESENCE_SOURCE` already does for the source token.
- A frozen `IntentAction` carrying the target token and a `step_ids` tuple that is **empty** for the plan arm.
- One regex with two arms; the plan arm matches no id list. Keep it module-private, like `_MERGE_ACTION_MARKER_RE`.

**Sole writer, sole reader.** `render_intent_action` is the only place that formats the marker and `parse_intent_action` the only place that reads it, so the two cannot fork. `check_intent_presence` calls the renderer rather than building the string inline.

**Source-guard the parse first.** Return `None` for any rec whose `source` is not `INTENT_PRESENCE_SOURCE`, before the regex runs — mirroring `parse_merge_action`'s guard on `_GRANULARITY_MERGE_SOURCE`. Step 7's dispatcher will branch on a non-`None` parse, so the guard is what stops another source whose prose happens to contain the marker text from routing to the intent bridge.

**Constraints that are not free to vary:**

- **The marker goes at the tail**, after the human sentence, the way `_reground_already_built_recommendation` places its own. `plan_tool/completeness_report.py:_fmt_fix_line` renders `suggested_action` verbatim as a `- Fix:` sub-bullet, and the per-source remedy-line loop in the same module's next-actions builder appends it verbatim too. An operator reads the sentence first either way.
- **Recommendation ids must not move.** Feed the ids to `_make_rec_id` through the existing `fingerprint` string exactly as today. Do not relocate the id set into the marker only.
- **The anti-echo property survives.** The marker is derived from step ids, never from the value read, so `test_finding_text_is_identical_whatever_the_non_value_was` stays green. The marker must also contain **no `#`** — `test_finding_never_carries_a_forged_heading` asserts that over `title`, `body`, *and* `suggested_action`. `→` is safe; a `#`-bearing separator is not.
- **Only missing ids appear.** `test_rollup_omits_steps_that_have_an_intent` asserts a step with a usable intent does not appear anywhere in `suggested_action`. Render `missing_ids`, nothing wider.
- **The plan arm carries no id list.** Do not render `→ intent steps:` with an empty list — an empty set is ambiguous with "the roll-up matched nothing", and the roll-up is never emitted when `missing_ids` is empty.
- **Parse returns ids sorted and deduped**, matching the sorted `missing_ids` the renderer receives, so writer and reader can never disagree about order. `parse_merge_action` already sorts on the way out; do the same.
- **Nothing about routing changes.** `INTENT_PRESENCE_SOURCE` stays out of `APPLY_ELIGIBLE_SOURCES` and `STRUCTURAL_SOURCES` (`test_source_is_in_no_routing_set` pins this), the severity stays `info`, and the finding count stays at most two per plan.

**Alternatives rejected:**

1. **Generalize the merge grammar into one shared marker parser.** Rejected. It restructures a shipped grammar and adds new behavior in the same step — a mixed change — and the plan's "Allowed reorganization: none" fence rules out the module churn. Mirroring is the repo's standing call for a second instance of a shape.
2. **Add a typed field to `Recommendation` (e.g. `target_step_ids`).** Rejected. `Recommendation` is a persisted schema guarded by `tests/test_data_contract.py`, so a new field is a `DATA_CONTRACT.md` decision the plan's frontmatter does not carry. `MergeAction`'s docstring already records the in-memory-only stance for exactly this reason.
3. **Have step 7 re-run `check_intent_presence` against a fresh parse.** Rejected. Two answers that can disagree, with the operator confirming one and the bridge writing the other.

**Watch `tests/test_duplication.py`.** `render_merge_action`'s body is two lines — below the guard's four-line floor — so a near-identical `render_intent_action` cannot trip it. `parse_intent_action` differs from `parse_merge_action` in its source constant and its regex, so the normalized bodies are not identical either. If some helper you write does collide, `ALLOWED_DUPLICATE_GROUPS` with a stated reason is the supported answer; folding the two grammars together is rejected alternative 1, not a fix.

**Shared locations for the same rule.** The core logic here is "carry a finding's target step ids in a machine-readable marker on `suggested_action`". Four other places touch it and **none** is edited by this step: `plan_tool/review.py:render_merge_action` / `parse_merge_action` (the shipped instance, read as the model); `plan_tool/granularity.py:split_predicate_key` (the split side's key-carrying analog); `plan_tool/review_walk.py:merge_remedy_target` and `directive_target_ids` (the walk-side recovery seam, owned by step 7 — see [Deferred](#deferred)); and the two `suggested_action` renderers in `plan_tool/completeness_report.py` named above, which pick the marker up for free.

## Tests

All cases live in `tests/test_review.py`.

### Tests for this step

New class `TestIntentActionGrammar`, placed beside `TestMergeActionGrammar`:

- `test_intent_target_constants_pin_values` — the two target tokens are the literals the parser matches.
- `test_render_plan_target_marker` — the plan arm renders the marker with no id list.
- `test_render_steps_marker_lists_ids_in_order` — the steps arm renders the ids in the order given.
- `test_parse_round_trips_the_plan_target` — rendering then parsing the plan arm yields the plan target with an empty id tuple.
- `test_parse_round_trips_a_step_id_set` — rendering then parsing an id set yields that exact tuple.
- `test_parse_returns_none_for_a_non_intent_source` — a `granularity-merge` rec whose `suggested_action` carries an intent-shaped marker parses to `None`.
- `test_parse_returns_none_without_a_marker` — an intent-presence rec with plain prose parses to `None`.
- `test_parse_returns_none_for_a_malformed_marker` — a truncated or misspelled marker parses to `None`, not to a partial result.
- `test_parse_sorts_and_dedupes_ids` — a marker written with unsorted or repeated ids parses to a sorted, deduped tuple.
- `test_parse_ignores_ids_in_the_human_prose` — a rec whose sentence lists ids but carries no marker parses to `None`, so prose can never be mistaken for a directive.

Added to the existing `TestCheckIntentPresence`:

- `test_plan_finding_carries_the_plan_directive` — the plan-level finding parses to the plan target.
- `test_plan_finding_carries_no_step_ids` — that parse's id tuple is empty.
- `test_rollup_carries_every_missing_step_id_in_its_directive` — a plan missing intents on steps 1 and 3 parses to `(1, 3)`.
- `test_rollup_directive_omits_steps_that_have_an_intent` — a step with a usable intent is absent from the parsed tuple.
- `test_marker_is_at_the_tail_of_the_suggested_action` — the human sentence precedes the marker.
- `test_rec_ids_are_unchanged_by_the_directive` — both ids equal `_make_rec_id(None, INTENT_PRESENCE_SOURCE, …)` over the same fingerprints used today, pinning the id's independence from `suggested_action`.

**Green-before-done gate.** Every case above, **plus the whole existing `TestCheckIntentPresence` class green untouched** — in particular `test_finding_never_carries_a_forged_heading`, `test_finding_text_is_identical_whatever_the_non_value_was`, `test_cap_holds_as_step_count_grows`, `test_rollup_omits_steps_that_have_an_intent`, `test_source_is_in_no_routing_set`, and `test_rec_ids_are_stable_across_two_runs`. Also run `tests/test_duplication.py` and `tests/test_data_contract.py`, which are the two repo-wide guards this change could trip.

## Acceptance criteria

- `parse_intent_action` on the roll-up finding for a plan whose steps 1 and 3 lack an intent returns the steps target with `step_ids == (1, 3)`.
- `parse_intent_action` on the plan-level finding returns the plan target with `step_ids == ()`.
- `parse_intent_action` returns `None` for a recommendation whose `source` is not `INTENT_PRESENCE_SOURCE`, whatever its `suggested_action` says.
- `check_intent_presence` still returns at most two findings for any plan; both carry `severity == "info"` and `step_id is None`.
- Both findings' `id` values equal `_make_rec_id(None, INTENT_PRESENCE_SOURCE, "plan-intent")` and `_make_rec_id(None, INTENT_PRESENCE_SOURCE, "step-intent:<ids>")` respectively — unchanged from HEAD.
- No `#` appears in either finding's `title`, `body`, or `suggested_action`.
- `rg '→ intent' plan_tool/` shows the literal only inside `render_intent_action`; the marker regex constant appears only at its definition and inside `parse_intent_action`.
- `INTENT_PRESENCE_SOURCE` is still absent from `APPLY_ELIGIBLE_SOURCES` and `STRUCTURAL_SOURCES`.
- `Recommendation` gains no field; `tests/test_data_contract.py` and `tests/test_duplication.py` pass unchanged.
- `uv run pytest tests/test_review.py tests/test_duplication.py tests/test_data_contract.py -q` is green, and `git status` shows changes only in the two declared files.

## References

- [dataclasses — Data Classes — Python 3 documentation](https://docs.python.org/3/library/dataclasses.html) — Field defaults and `frozen=True` semantics for the `IntentAction` record, matching how `MergeAction` is declared.
- [re — Regular expression operations — Python 3 documentation](https://docs.python.org/3/library/re.html) — Group and alternation semantics for the two-arm marker pattern, including how an unmatched group reads back as `None`.

## Applicable guardrails

- **The plan's "## Out of scope", any validation past presence.** The directive carries step ids and a target token — never intent text, a length, a shape check, or a quality signal. This is permanently refused, so a later finding asking the directive to grade an intent is invalid rather than deferrable.
- **The plan's "## Architecture", the roll-up shape survives.** The marker rides on the two findings that already exist. This step adds no third finding, no per-step fan-out, and no change to the count.
- **The plan's "## Architecture", allowed reorganization: none.** No module moves and no renderer changes. This is the specific reason the step mirrors the shipped merge grammar instead of generalizing it.
- **The plan's "## Architecture", produce before require.** Severity stays `info` and the finding stays off the blocking bucket here; the promotion is a later step's work.
- **The plan's "## Architecture", the proposer is a remedy on the existing finding, not a new verb.** The directive routes to a gated bridge, never to `apply_finding` — `intent-presence` stays out of the apply-eligible set.
- **The plan's "## Out of scope", propagation through `split` / `merge` / `scope-out` / `reground`.** The new grammar is not wired into any of those verbs, and it does not extend the shipped merge/re-ground directive.
- **The step's own intent** — let the proposer act on the finding directly. Carrying the target set is the whole job; anything past that is widening.

## Deferred

- **The walk-side resolver and the dispatcher** (`plan_tool/review_walk.py`, `plan_tool/cli/review_actions.py`) — step 7 owns both files and produces the dispatch behind an operator confirm. This step ships the grammar only.
- **Whether the intent directive joins `review_walk.py:directive_target_ids` and the `target_signature` stamping** — step 7's call, and its bridge already re-parses the plan and re-checks each id, so a stale saved directive is caught there rather than by a signature.
- **`triage_reason`'s `intent-presence` branch wording** — it stays accurate while no dispatcher exists. Revisit it with the step that changes the finding's routing (step 8 declares `plan_tool/review.py`).
- **The severity promotion and the move onto the blocking self-consistency bucket** — step 8.
- **Folding the merge and intent marker grammars into one shared parser** — a cross-module refactor a feature step cannot mint. File it in `BACKLOG.md` if a third grammar ever arrives.
- **Persisting the directive as a typed `Recommendation` field** — a `DATA_CONTRACT.md` schema decision outside this plan's frontmatter.
- **Documenting the directive in a format doc** — step 9 owns the documentation sweep.
