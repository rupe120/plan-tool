<!-- plan-tool scope-out carved-seed
source: docs/implementation-plans/2-intent-required.md
carved_steps: 6, 7
-->

# Plan seed: carved steps 6..7 from Intent Required

> **Severity note (2026-08-03):** this seed was written before step 6
> promoted `check_intent_presence`. At HEAD the finding emits **`medium`**
> and sits in `SELF_CONSISTENCY_SOURCES`, blocking completeness
> convergence. Every `info` / non-blocking / `test_source_is_in_no_routing_set`
> claim below describes the *pre-promotion* contract — read the code, and
> do not restore `info`.

> **Provenance (2026-08-03):** `propose_intent_bridge` was built and tested
> under the original decomposition and **deleted** when this arm was carved,
> because nothing called it. Rebuilding it is part of this seed's work; the
> gate order it had is specified below.


This is a `plan-tool create --from-existing` input. It re-plans **only the carved region** in the **Scope to re-plan** sections below (one per carved step). The **Done-context**, **Upstream prerequisites**, and **External prerequisites** sections are already-implemented context, not work to re-plan.

## Scope to re-plan (source step 6)

**Have the intent-presence finding carry the missing step ids in a parseable directive**

Files:
- plan_tool/review.py
- tests/test_review.py

Change type: feature

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

- [dataclasses — Data Classes — Python 3 documentationhttps: — Field defaults and `frozen=True` semantics for the `IntentAction` record, matching how `MergeAction` is declared.
- [re — Regular expression operations — Python 3 documentationhttps: — Group and alternation semantics for the two-arm marker pattern, including how an unmatched group reads back as `None`.

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


## Done-context (already done — do not re-plan; source step 6)

Everything in this section is **already implemented** done-context. Do **not** re-plan or re-implement it.

The carved step was left **attempted/partial** (status `pending`) — account for this in the re-plan, but treat its work (in **Scope to re-plan** above) as not yet complete.

## Scope to re-plan (source step 7)

**Dispatch the intent proposer from the review and reconcile apply walk behind an operator confirm**

Files:
- plan_tool/review_walk.py
- plan_tool/cli/review_actions.py
- tests/test_review_walk.py
- tests/cli/test_review_actions.py

Change type: feature

# Step 7 — Dispatch the intent proposer from the review and reconcile apply walk behind an operator confirm

## Summary

Wire step 6's intent directive into the apply walk so pressing `a` on an `intent-presence` finding runs step 4's proposer instead of just recording an annotation. Two files change: `plan_tool/review_walk.py` gains an `intent_remedy_target` resolver, an `is_dispatchable` arm, and the roll-up's ids in `directive_target_ids`; `plan_tool/cli/review_actions.py` gains a `_dispatch_intent_remedy` branch that guards directive staleness, calls `propose_intent_bridge`, and maps its outcome onto `WalkState`. The design decision is that **the confirm is the whole gate** — there is no new CLI flag, because this step's declared files cannot reach the parser and because an intent write adds one frontmatter line rather than renumbering the plan; a blanket `-y` fast-forward still degrades to recommend-only, matching the three sibling bridge dispatchers. On green, an operator walking a saved review that carries an intent finding gets drafts, accepts or declines each one, and a decline leaves the plan file's bytes unchanged.

## Table of Contents

- [Summary](#summary) — what the step wires and what is true on green.
- [Why](#why) — why the finding is the operator's only meeting point with the remedy.
- [Input](#input) — the contracts from steps 4 and 6, the shipped walk seams, and what none of them can tell this step.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two production files and the two suites, with the per-file edits.
- [Implementation](#implementation) — the resolver, the dispatch branch, the gate decision, the outcome map, and the alternatives rejected.
- [Tests](#tests) — the cases this step adds and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checks a reviewer or CI can run.
- [References](#references) — the docs bearing on the backend seam this dispatcher owns.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step's code.
- [Deferred](#deferred) — the persistence gap, the flag surface, and the later steps this one leaves alone.

## Why

Steps 2, 3, and 5 close the authoring paths, but they only reach plans created from now on. Every plan already on disk keeps its missing intent, and the plan's no-migration fence rules out a sweep. The one place an operator already meets an existing plan's missing intent is the finding — and today applying it does nothing but write `applied` into the sidecar, because `intent-presence` matches no dispatch arm in `plan_tool/review_walk.py:is_dispatchable`. Step 4 built the remedy and step 6 put the target ids on the finding; this step is the wire between them. Without it, step 8 promotes a finding whose fix an operator can reach only by hand-editing frontmatter.

## Input

This step consumes two sibling contracts and five shipped walk seams. **Neither sibling exists at HEAD** — `plan_tool/intent_proposal.py` is absent and `plan_tool/review.py` carries no `parse_intent_action` — so this step is blocked until steps 4 and 6 land, which is what `depends_on: 4, 6` records.

- **Step 4's `plan_tool/intent_proposal.py:propose_intent_bridge`** — the apply-or-recommend actuator. This step supplies the plan path, the target step ids, the opt-in token, and a backend invoker; the bridge owns the re-parse, the presence re-check, the confirm, and the write. Its outcome vocabulary is what this dispatcher maps onto `WalkState`: `applied` is the only outcome that mutates, and `noop` / `recommended` / `proposal-unusable` / `step-missing` all write nothing. Its `invoker` parameter has **no default** by step 4's decision, so this dispatcher is the seam owner.
- **Step 6's `plan_tool/review.py:parse_intent_action`** — the sole reader of the directive marker, with its frozen `IntentAction` carrying a target token plus a step-id tuple that is **empty on the plan arm**. It source-guards internally, so a non-`None` parse already means "this is a routable intent directive". This step never re-runs `check_intent_presence` and never scrapes the finding's prose for ids.
- **`plan_tool/review_walk.py:merge_remedy_target` and the `is_dispatchable` ladder** — the shape to mirror. `merge_remedy_target` is a one-line wrapper over `parse_merge_action` whose whole job is to give the walk a name to key on; `is_dispatchable` is a flat list of "does this resolver return something" arms.
- **`plan_tool/review_walk.py:directive_target_ids` and `stamp_target_signatures`** — the freshness seam. `directive_target_ids` is the single recovery both the stamp side and the guard side call, so they can never disagree about which ids a directive targets. `stamp_target_signatures` runs at the two save sites (`plan_tool/cli/review_cmd.py`'s save block and `plan_tool/completeness_report.py:write_completeness_report`), so a directive added to `directive_target_ids` gets stamped there with no edit to either file.
- **`plan_tool/review_walk.py:apply_structural_outcome` / `StructuralOutcomeEffects` / `structural_apply_allowed`** — the shared `WalkState` tail and fast-forward gate the four existing structural dispatchers route through. `structural_apply_allowed`'s one rule is that a `-y` fast-forward never auto-confirms; `apply_structural_outcome` owns `apply_skip`, the `applied_structural_finding_ids` record, and the halt pair.
- **`plan_tool/cli/review_actions.py:_saved_directive_is_stale`** — the freshness contract every mutating bridge dispatch gates on. It re-hashes the directive's own targets against the stamped `target_signature`, falls back to the whole-plan fingerprint for an unstamped rec, and returns **stale** when the plan is gone or unparseable so a bridge is never reached with a missing plan.

**What this step cannot verify, and one fact that changes what it can deliver today.** The dispatch is routing: nothing here checks that a draft is good, and the tests drive synthetic recommendations against a stubbed bridge, so they prove the wire, not that a real audit hands the walk one of these findings. That distinction is load-bearing right now, because **no saved review carries an `intent-presence` finding at HEAD**: `plan_tool/cli/completeness_phases.py` composes its sidecar recommendation list from the correctness, conceptual, data-contract, concept-link, and mixed-split buckets, and the advisory smell bucket that holds `intent-presence` is render-only. So this step ships walk-side wiring whose producer arrives later — the same forward-wiring shape `plan_tool/review.py`'s `STRUCTURAL_SOURCES` comment already records for `structural-split`. See [Deferred](#deferred) for where that gap is routed.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review_walk.py` — add `intent_remedy_target` beside `merge_remedy_target`; add its arm to `is_dispatchable`; add the roll-up's step ids to `directive_target_ids`; extend `structural_apply_allowed`'s docstring and `WalkState.applied_structural_finding_ids`' comment to cover the fourth dispatcher.
  - `plan_tool/cli/review_actions.py` — add `_dispatch_intent_remedy` beside the merge and re-ground dispatchers, and route to it from `action`.
  - `tests/test_review_walk.py` — new dispatch/resolver class plus cases added to the existing `TestDirectiveTargetIds` and `TestStampTargetSignatures`.
  - `tests/cli/test_review_actions.py` — new dispatch class modelled on `TestRegroundRemedyDispatch`.

## Implementation

**What must be true when the step is done.** Applying an `intent-presence` finding in the walk calls step 4's bridge with exactly the targets the finding named; every non-`applied` outcome leaves the plan file's bytes unchanged and records `skip`; and nothing about the finding's severity, count, ids, or routing-set membership moves.

### The resolver and the dispatch arm (`plan_tool/review_walk.py`)

- **Add `intent_remedy_target(rec)`**, a thin wrapper over step 6's `parse_intent_action` returning its `IntentAction` or `None`. Mirror `merge_remedy_target`'s stance in the docstring: key on the parsed *directive*, never the source string, because the parser already source-guards. One more name in the existing `from plan_tool.review import (…)` block at module top — no new module edge.
- **Add one arm to `is_dispatchable`.** It is a flat ladder of resolver calls; the intent arm reads like the merge arm. Both directive arms — plan and steps — qualify: the plan arm has no ids and still has a target.
- **Do not add `intent-presence` to `_APPLY_AS_FINDING_SOURCES`, `APPLY_ELIGIBLE_SOURCES`, or `STRUCTURAL_SOURCES.`** `tests/test_review.py:TestCheckIntentPresence::test_source_is_in_no_routing_set` pins all of that, and those sets live in a file this step does not declare. The dispatch reaches the bridge through its own branch, exactly as the merge and re-ground directives do.

**`directive_target_ids` takes the roll-up arm only.** Return the parsed step-id tuple for the steps arm and `None` for the plan arm. The reason the plan arm is excluded is concrete: `compute_target_signature` over an empty id set produces the same digest for every plan, so stamping the plan arm would hand `_saved_directive_is_stale` a signature that always matches and certify freshness it never checked. There is also nothing to guard — a plan has exactly one plan-level field, and a renumber cannot move it. Step 6 left this decision here; this is the answer, and the "empty tuple is not a target set" rule belongs in the function's docstring beside the shapes it already covers.

### The dispatch branch (`plan_tool/cli/review_actions.py`)

Add `_dispatch_intent_remedy(rec)` beside `_dispatch_reground_remedy` and `_dispatch_merge_remedy`, and route to it from `action`. Recommended order of work inside the dispatcher, which is the same order those two use:

1. **Re-parse the directive** with `parse_intent_action`. `None`, or a rec routed here by mistake, records `skip` through `apply_structural_outcome(state, rec, StructuralOutcomeEffects(resolved=False))` and returns the shared manual-run notice — the walk's `r`/run key can call `action` on a rec that never passed `is_dispatchable`, so this re-check is not defensive noise.
2. **Check `state.applied_structural_finding_ids`** for `rec.id` and return a resolved noop message if present. This is the r-then-a re-dispatch path the two sibling dispatchers already carry.
3. **Guard staleness** with `_saved_directive_is_stale(rec)` before any backend call, downgrading to recommend-only with a re-run-the-diagnosis message. On the plan arm this falls back to the coarse whole-plan check by construction, since step 1 above yields no ids to stamp.
4. **Call `propose_intent_bridge`** with the directive's step ids (an empty list on the plan arm), `allow_intent_write=structural_apply_allowed(True, state)`, and `yes=False`.
5. **Map the outcome** onto `WalkState` and a one-line status string.

**The gate decision, and why there is no new flag.** The three structural bridge dispatchers each take a CLI-supplied opt-in (`--apply-structural`, `--merge`, `--reground`) *on top of* a TTY confirm, because a fold, a split, or a mark-done renumbers or re-states the plan's structure. An intent write adds one frontmatter line to targets the operator explicitly asked about, and the bridge shows each draft before writing it. So the opt-in here is the operator pressing apply on the finding, and the confirm is the bridge's accept / edit / decline walk — which is precisely the gating the plan's Architecture names. This also keeps the step inside its declared files: `plan_tool/cli/parser.py` and the walk's callers are not in scope, so a new flag could not be registered or threaded anyway.

**A fast-forward still never writes.** Pass the opt-in through `structural_apply_allowed`, so `state.yes_to_all` forces `allow_intent_write=False` and the bridge returns `recommended` without a backend call. Model-drafted prose lands in the field that steers every downstream authoring and run prompt; a blanket `-y` is not a review of it. Say so in the recommend-only message rather than naming a flag that does not exist — something like "declined: `--yes` never auto-writes an intent; re-walk without it and confirm each draft." Reusing the helper needs one clause added to its docstring, which currently says "the three bridge dispatchers"; **do not rename it** — a rename plus a new dispatcher in one step is the mixed change the repo splits.

**The invoker seam.** Resolve `plan_tool/create.py:shell_claude_invoker` with a body-local import and pass it to the bridge, mirroring `_dispatch_structural_escalation`, which already owns exactly this seam in this module. Tests neutralize it by stubbing `plan_tool.intent_proposal.propose_intent_bridge` on its owning module — the `_stub_reground_bridge` idiom — so the invoker is never called and `tests/conftest.py`'s autouse gate never has to fire. One way if a case genuinely needs to reach the invoker: an optional `intent_invoker=None` builder kwarg resolving to the shell invoker when unset, the shape `plan_tool/cli/gates_cmd.py:cmd_suggest_gates` uses. Prefer the stub; it adds no public surface.

**The outcome map.** Every row but the first writes nothing:

- `applied` → `StructuralOutcomeEffects(resolved=True, record_finding_id=True)`. Record the id so an r-then-a re-dispatch resolves through the session signal. **No halt**: an intent write changes no step id, so later saved findings stay valid — the opposite of the merge dispatcher, which halts because its fold renumbers. `WalkState.applied_structural_finding_ids`' comment names merge and re-ground today and needs the intent write added; the field's own rule (a rec is one directive kind and `rec.id` is unique, so ids never collide) already covers a third writer.
- `noop` → `resolved=True`. The bridge re-checked and every target already carries a usable intent, so the desired end state holds.
- `recommended`, `proposal-unusable`, `step-missing` → `resolved=False`, each with its own message. Never mark a finding resolved without an edit.

**Where the branch goes in `action`.** Put it with the other marker-driven directive dispatches and **before** the `should_apply_as_finding` branch. `intent-presence` is in none of the apply-source sets today, so this is belt-and-suspenders — the same reason the `split_escalation_target` branch states for its own placement — but it is what stops a future caller widening `extra_apply_sources` from routing an intent finding into `apply_finding`, which the plan's Architecture rules out.

**Constraints that are not free to vary:**

- **The targets come from the directive, never from `rec.step_id`.** Both intent findings carry `step_id=None` by design; recovering ids any other way is what step 6 exists to prevent.
- **`yes=False` at the bridge, always.** The walk supplies the opt-in token; the bridge owns the confirm. Forwarding `yes=True` would make the confirm skippable from a surface that never asked for it.
- **Only `applied` may leave the plan file changed**, and this step adds no write of its own — every mutation goes through the bridge.
- **The two suites stay hermetic.** No case may reach a real backend; the conftest gate raises if one does.

**Alternatives rejected:**

1. **Add a `--apply-intent` flag and thread it through the walk callers.** Rejected on scope: the parser and the caller modules are outside this step's declared files, and the mutation is already gated by a per-draft confirm. If a reviewer wants a flag anyway, that is a plan-level decision, not something to smuggle in by widening the file list.
2. **Route the finding through `apply_finding` by opting `intent-presence` into the apply sources.** Rejected. `apply_finding` is a prose editor pointed at plan and detail bodies; the plan states this remedy is the finding's only mutator, and the routing-set test pins the source out of every apply set.
3. **Re-run `check_intent_presence` inside the dispatcher to recover the ids.** Rejected for the reason step 6 records — two answers that can disagree, with the operator confirming one set and the bridge writing another.
4. **Halt the walk after an applied write, the way the merge dispatcher does.** Rejected. Nothing renumbers, so later findings' step ids stay valid and halting would cost the operator the rest of the walk for no safety.

## Tests

Cases live in `tests/test_review_walk.py` (resolver, dispatchability, stamping) and `tests/cli/test_review_actions.py` (the dispatcher). Every dispatcher case stubs `plan_tool.intent_proposal.propose_intent_bridge` on its owning module and records the kwargs it received, mirroring `_stub_reground_bridge`; no case spawns a backend or blocks on stdin.

### Tests for this step

New class `TestIntentDirectiveDispatch` in `tests/test_review_walk.py`, placed beside `TestMergeDirectiveDispatch`:

- `test_rollup_directive_is_dispatchable` — the roll-up finding resolves to an `IntentAction` and `is_dispatchable` is True.
- `test_plan_arm_directive_is_dispatchable` — the plan-level finding qualifies with an empty id tuple.
- `test_intent_finding_without_a_marker_is_not_dispatchable` — plain prose resolves to `None`.
- `test_non_intent_source_carrying_the_marker_is_not_dispatchable` — the parser's source guard is what keeps another source out.
- `test_intent_rec_is_not_apply_as_finding` — `should_apply_as_finding` stays False for it, with and without extra sources.
- `test_info_intent_finding_is_hidden_under_skip_info` — the default hide still applies, pinning that `--include-info` is required until the severity moves.

Added to the existing `TestDirectiveTargetIds` and `TestStampTargetSignatures`:

- `test_rollup_directive_yields_its_step_ids` — the parsed tuple comes back in sorted order.
- `test_plan_arm_directive_yields_none` — the plan arm is not a target set.
- `test_rollup_directive_is_stamped` — a roll-up rec comes out of `stamp_target_signatures` with a signature over its own steps.
- `test_plan_arm_directive_passes_through_unstamped` — the plan arm's `target_signature` stays `None`.

New class `TestIntentRemedyDispatch` in `tests/cli/test_review_actions.py`, modelled on `TestRegroundRemedyDispatch`:

- `test_rollup_directive_routes_to_the_intent_bridge` — the bridge is called once.
- `test_step_ids_come_from_the_directive_not_rec_step_id` — `rec.step_id` is None and the forwarded ids are the directive's.
- `test_plan_arm_forwards_an_empty_step_id_set` — the plan-level ask reaches the bridge with no step targets.
- `test_applied_records_applied_and_does_not_halt` — `apply_skip` False, `halt_requested` False, id recorded.
- `test_noop_records_applied` — the already-satisfied case is resolved, not skipped.
- `test_recommended_records_skip` — no edit landed, so the annotation is `skip`.
- `test_proposal_unusable_records_skip` — an unusable backend response is not a resolution.
- `test_step_missing_records_skip` — an id absent from the plan is refused.
- `test_stale_rollup_directive_downgrades_before_any_call` — the bridge is never called and the message points at re-running the diagnosis.
- `test_missing_plan_file_downgrades_not_crashes` — a deleted plan with an empty saved fingerprint still refuses instead of raising.
- `test_fast_forward_never_auto_writes` — under `yes_to_all` the bridge receives `allow_intent_write=False`.
- `test_yes_is_always_false_at_the_bridge` — the confirm is never bypassed from here.
- `test_re_dispatch_after_an_applied_write_resolves` — the session signal short-circuits the stale guard.
- `test_directiveless_rec_records_skip_and_returns_the_manual_notice` — a stray `r`-key call actuates nothing.
- `test_plan_file_bytes_unchanged_on_every_non_applied_outcome` — one assertion over the four write-nothing outcomes.

Approx. 21 new cases. **Green-before-done gate:** the plan sets `enforce_step_tests: true` and this step is `change_type: feature`, so every case above must pass, **plus the existing `tests/test_review_walk.py` and `tests/cli/test_review_actions.py` suites green untouched** — in particular `TestMergeDirectiveDispatch`, `TestSplitEscalationTarget`, `TestStructuralApplyAllowedGate`, `TestDirectiveTargetIds`, `TestRegroundRemedyDispatch`, and `TestMergeRemedyDispatch`. Also run `tests/test_review.py` (for `test_source_is_in_no_routing_set`) and `tests/test_duplication.py`, the repo-wide guard a fourth near-identical dispatcher could trip.

## Acceptance criteria

- `plan_tool.review_walk.intent_remedy_target` returns an `IntentAction` for both intent findings and `None` for every other recommendation.
- `plan_tool.review_walk.is_dispatchable` returns True for both intent directive findings and False for an `intent-presence` recommendation with no marker.
- `plan_tool.review_walk.directive_target_ids` returns the roll-up's sorted step ids and `None` for the plan-level finding.
- Applying a roll-up finding calls `propose_intent_bridge` exactly once with the directive's step ids and `yes=False`.
- With `WalkState(yes_to_all=True)`, the bridge receives `allow_intent_write=False` and the plan file's bytes are unchanged.
- Every bridge outcome other than `applied` leaves the plan file's bytes unchanged and produces a `skip` annotation; `applied` and `noop` produce `applied`.
- An `applied` intent write leaves `state.halt_requested` False and adds `rec.id` to `state.applied_structural_finding_ids`.
- A stale roll-up directive (its targets' titles or change types changed on disk) makes zero bridge calls and returns a message naming the re-run.
- A deleted plan file makes zero bridge calls and raises nothing.
- `rg 'intent' plan_tool/review.py` shows `INTENT_PRESENCE_SOURCE` still absent from `APPLY_ELIGIBLE_SOURCES` and `STRUCTURAL_SOURCES`; `tests/test_review.py::TestCheckIntentPresence::test_source_is_in_no_routing_set` passes unchanged.
- `uv run pytest tests/test_review_walk.py tests/cli/test_review_actions.py tests/test_review.py tests/test_duplication.py -q` is green.
- `git status` shows changes only in the four declared files.

## References

- [Run Claude Code programmatically (headless mode)https: — The non-interactive invocation and result envelope behind the `shell_claude_invoker` seam this dispatcher resolves and hands to the bridge.
- [Claude Code CLI referencehttps: — Flag list for the `claude` binary the invoker shells out to, for reading what a real dispatch would spend.
- [dataclasses — Data Classes — Python 3 documentationhttps: — `frozen=True` semantics for the `IntentAction` this step consumes and the `StructuralOutcomeEffects` records it constructs.

## Applicable guardrails

- **The plan's "## Out of scope", any validation past presence.** The dispatcher forwards ids and reports an outcome. It must not inspect, score, cap, or compare a drafted intent — and it must not add a check the bridge deliberately omits. A finding asking this dispatcher to judge a draft is invalid, not deferrable.
- **The plan's "## Out of scope", no parse-time requirement and no migration.** This step touches one plan per apply, only through the bridge's confirm. No sweep, no backfill, no batch arm.
- **The plan's "## Out of scope", propagation through the structural verbs named there.** The intent directive is not wired into any of them and must not extend the shipped merge/re-ground directive grammar.
- **The plan's "## Out of scope", no new parallel surfaces.** Serial dispatch, one bridge call per applied finding.
- **The plan's "## Architecture", allowed reorganization: none.** Reuse `structural_apply_allowed`, `apply_structural_outcome`, and `_saved_directive_is_stale` as they ship. A docstring clause may be widened; no symbol is renamed, moved, or generalized.
- **The plan's "## Architecture", the proposer is a remedy on the existing finding, not a new verb.** This step registers no subcommand, mints no `Recommendation`, and adds no finding source. Detection stays unconditional; only the mutation is gated.
- **The plan's "## Architecture", produce before require.** Severity stays where step 6 left it and no blocking bucket changes here.
- **The step's stated intent.** Reaching existing plans is the job. Deciding *when* the finding fires, or how loud it is, belongs to step 8.

## Deferred

- **Getting the finding into a saved review at all** — `plan_tool/cli/completeness_phases.py` composes its sidecar list from the correctness, conceptual, data-contract, concept-link, and mixed-split buckets, and the advisory smell bucket holding `intent-presence` is render-only. That file is step 8's, not this step's; surface it as a scope question when step 8 is detailed rather than widening this file list. Until then the dispatch is forward-wiring exercised by synthetic recommendations, the shape `plan_tool/review.py`'s `STRUCTURAL_SOURCES` comment already records for `structural-split`.
- **A CLI opt-in flag for the intent write** — no flag is added, and the parser and walk callers are outside this step's files. The mutation is gated by the bridge's per-draft confirm plus the fast-forward refusal.
- **A `skip_info` carve-out so the finding is visible without `--include-info`** — step 8 raises the severity, which makes a carve-out dead on arrival. The pairwise merge carve-out exists because those findings stay `info` permanently; this one does not.
- **A `TESTING.md` neutralization-table row** for the backend default this dispatcher now resolves — `TESTING.md` is in no step's file list. File it in `BACKLOG.md` if a reviewer wants the row; the sibling `_dispatch_structural_escalation` owns the same seam without one today.
- **Telemetry on the accept / edit / decline choice** — a new decision kind is outside the plan's allowed behavior changes, and step 4 already routed it out for the same reason.
- **Raising the finding to `medium` and moving it onto the blocking bucket** — step 8.
- **`triage_reason`'s `intent-presence` wording**, which still says a frontmatter field is not an apply edit — true of `apply_finding`, and `plan_tool/review.py` is not in this step's files. Revisit it with the step that changes the finding's routing.
- **Documenting the dispatch in the flow docs** — step 9 owns the documentation sweep.


## Done-context (already done — do not re-plan; source step 7)

Everything in this section is **already implemented** done-context. Do **not** re-plan or re-implement it.

The carved step was left **attempted/partial** (status `pending`) — account for this in the re-plan, but treat its work (in **Scope to re-plan** above) as not yet complete.

## External prerequisites (not done yet)

- step 1 [current]: Make the usable-intent check in review.py public so create and the proposer share one predicate
- step 4 [pending]: Add an intent-proposal helper module that drafts a one-liner and takes accept, edit, or decline

## Provenance

- Source plan: docs/implementation-plans/2-intent-required.md
- Carved steps: 6, 7
