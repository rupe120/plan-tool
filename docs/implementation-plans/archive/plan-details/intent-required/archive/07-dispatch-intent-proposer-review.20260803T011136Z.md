> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

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

- [Run Claude Code programmatically (headless mode)](https://docs.claude.com/en/docs/claude-code/headless) — The non-interactive invocation and result envelope behind the `shell_claude_invoker` seam this dispatcher resolves and hands to the bridge.
- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference) — Flag list for the `claude` binary the invoker shells out to, for reading what a real dispatch would spend.
- [dataclasses — Data Classes — Python 3 documentation](https://docs.python.org/3/library/dataclasses.html) — `frozen=True` semantics for the `IntentAction` this step consumes and the `StructuralOutcomeEffects` records it constructs.

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
