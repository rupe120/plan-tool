> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Make the usable-intent check in `review.py` public so `create` and the proposer share one predicate

## Summary

Rename `plan_tool/review.py`'s private `_is_usable_intent` to a public `is_usable_intent` and leave its behavior exactly as it is. The only production call site is `check_intent_presence`, in the same module; nothing outside `review.py` reads the predicate today. The design decision is that the public symbol keeps its plain-string signature (`Optional[str] -> bool`) rather than taking a `Plan` or `Step`, because steps 2–5 need to judge a candidate line *before* any `Step` object exists. On green, `plan_tool.review.is_usable_intent` is importable, `_is_usable_intent` is gone, and every existing `check_intent_presence` test passes untouched.

## Table of Contents

- [Summary](#summary) — what the step does and what is true when it lands.
- [Why](#why) — why one shared predicate has to exist before steps 2–5 can be written.
- [Input](#input) — the contract this step reads: the shipped predicate and its placeholder helper.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched, and the per-file edits.
- [Implementation](#implementation) — the rename, the signature decision, and the alternatives rejected.
- [Tests](#tests) — the direct predicate cases this step adds and the gate they satisfy.
- [Acceptance criteria](#acceptance-criteria) — checks a reviewer or CI can run.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step's code.
- [Deferred](#deferred) — the placeholder-vocabulary split and the stale plan citations, both routed elsewhere.

## Why

`review.py:_is_usable_intent` already defines the whole observable this plan enforces — absent, empty after whitespace, or a bare placeholder means "no intent". It is private, so the four consumers this plan is about to add cannot reach it without either importing a private name across a module boundary or writing a second copy. A second copy is the real hazard: `create` would decide a seed's `## Outcome` is good enough while `check_intent_presence` still flags the plan, or the proposer would offer to fix an intent the finding never named. There is already one live example of exactly this drift in the repo — `plan_tool/scope_fence.py` mirrors the placeholder shapes rather than importing them, and the two vocabularies have diverged (see [Deferred](#deferred)). Publishing the one predicate now, before any consumer exists, is what keeps the rest of the plan from adding a third.

## Input

This step reads two shipped contracts and changes neither:

- **`plan_tool/review.py:_is_usable_intent`** — the predicate itself. Its three non-values are `None`, a string that is empty after `.strip()`, and a string that is entirely a TODO/TBD marker. The order matters and must survive the rename: emptiness is checked first because `_body_section_is_placeholder` returns `False` for `""`, so asking the placeholder helper first would pass an empty string off as usable. The existing docstring records this.
- **`plan_tool/review.py:_body_section_is_placeholder`** and its `_BODY_PLACEHOLDER_RE` — the placeholder vocabulary the predicate delegates to. Both stay **private**. This step publishes exactly one symbol; the placeholder helper is an implementation detail of it, and every consumer in steps 2–5 wants the intent-shaped question, not the section-shaped one.

**Limit on verifying this.** Nothing here checks that an intent is *good* — only that a value is there and is not a marker. The predicate returns a bool and never returns or echoes the value it read; that anti-echo property is what `check_intent_presence` relies on to avoid quoting a multi-line intent into a rendered report.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — rename `_is_usable_intent` to `is_usable_intent`; update its two call sites inside `check_intent_presence`; extend its docstring to say it is the shared predicate that `create`, the proposer, and this finding all use.
  - `tests/test_review.py` — add `is_usable_intent` to the advisory-smell-layer import block that already pulls `check_intent_presence` and `INTENT_PRESENCE_SOURCE` from `plan_tool.review`; add a test class covering the predicate directly.

## Implementation

**What changes:** one symbol's name and visibility. No behavior changes at all — same three non-values, same order of checks, same return type. `change_type: refactor` is accurate and should stay accurate: if any test in this step needs a new input shape to pass, the step has drifted.

**The rename.** `is_usable_intent` fits `review.py`'s existing public predicate family — `is_apply_eligible`, `is_structural`, `is_pairwise_merge_finding` — so a reader meeting it beside them reads it the same way. Leave the function where it sits, directly under `INTENT_PRESENCE_SOURCE` and above `check_intent_presence`; moving it up beside the other `is_*` predicates separates it from its only current caller for no gain.

**Keep the plain-string signature.** `is_usable_intent(value: Optional[str]) -> bool` is the constraint, not a preference:

- Step 2 judges a seed's `## Outcome` text before a `Plan` is constructed.
- Step 3 judges a model-proposed `intent` value while it is still a dict entry inside the step-proposal JSON, before `_parse_steps_json` builds a `Step`.
- Step 4's proposer judges an operator's edited one-liner, which belongs to no object at all.

A `Plan`/`Step`-shaped signature would force each of those to build a throwaway object or fall back to its own copy of the rule — the exact outcome this step exists to prevent.

**Update the docstring while renaming.** It should say two things a reader needs: presence is the entire contract (already there), and this is the single predicate `create`, the intent proposer, and `check_intent_presence` all share, so a change here changes what all three accept. That sentence is what stops the next author from adding a second "is this a real intent" helper somewhere convenient.

**No new export beyond the module.** Consumers import from `plan_tool.review` directly — `plan_tool/create.py` already does exactly that for `check_file_existence` and `collect_deterministic_findings`. Do not add the name to `plan_tool/__init__.py`'s `__all__`: that file is not in this step's `files:` list, and nothing in the plan needs the top-level path.

**Alternative rejected: keep `_is_usable_intent` and add a public alias.** It would leave the plan's existing citations of the private name valid, and it is wrong. Two names for one predicate is precisely what the step intent forbids, and an alias invites a future edit to one name that the other silently misses. Rename, and accept the small citation sweep noted in [Deferred](#deferred).

**Alternative rejected: publish `_body_section_is_placeholder` too.** A consumer with the placeholder helper in hand can rebuild the intent rule slightly differently — checking the marker but forgetting the empty-string ordering, say. Publishing only the composed predicate makes the wrong thing harder to write.

**Call sites to update:** both are inside `check_intent_presence` — the plan-level guard and the step roll-up's generator expression. `grep -rn '_is_usable_intent'` across `plan_tool/` should return nothing when the edit is complete. Nothing in `plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/scope_fence.py`, or any CLI handler reads it today, so the rename's blast radius is one module.

**Leave the finding's routing alone.** `INTENT_PRESENCE_SOURCE`, the `SMELL_DETECTORS` entry named `"intent-presence"`, `triage_reason`'s `INTENT_PRESENCE_SOURCE` branch, and the finding's `info` severity are all untouched here — the severity promotion is step 6's.

## Tests

All tests live in `tests/test_review.py`, in a new `TestIsUsableIntent` class placed immediately before the existing `TestCheckIntentPresence`. The module-level `_PLACEHOLDER_INTENTS` tuple sitting just above that class already lists the marker spellings and is reused rather than re-declared.

### Tests for this step

- `test_real_prose_is_usable` — a plain one-line why returns `True`.
- `test_none_is_not_usable` — `None` returns `False`.
- `test_empty_string_is_not_usable` — `""` returns `False`, pinning the emptiness-before-placeholder ordering the docstring records.
- `test_whitespace_only_is_not_usable` — `"   \t "` returns `False`.
- `test_placeholder_markers_are_not_usable` — parametrized over `_PLACEHOLDER_INTENTS`; each marker returns `False`.
- `test_marker_word_inside_real_prose_is_usable` — `"ship the TODO list view"` returns `True`; only a whole-body marker counts.
- `test_long_or_vague_values_are_usable` — a 500-character value and the word `"stuff"` both return `True`, pinning that the predicate makes no quality or length judgment.
- `test_private_name_is_gone` — `plan_tool.review` has no `_is_usable_intent` attribute; the guard against an alias or a leftover wrapper reintroducing a second name.

The 20 existing `TestCheckIntentPresence` cases are **not** edited — they call `check_intent_presence`, never the predicate, so they are the regression evidence that the rename changed no behavior.

**Green-before-done gate:** every test above, plus the whole of `tests/test_review.py`, must be green before this step is finished. The plan sets `enforce_step_tests: true` and this step is `change_type: refactor`, so the test-authoring gate fires and expects `tests/test_review.py` in the step's changed-file delta.

## Acceptance criteria

- `from plan_tool.review import is_usable_intent` succeeds.
- `grep -rn '_is_usable_intent' plan_tool/ tests/` returns no matches.
- `is_usable_intent` returns `False` for `None`, `""`, `"   "`, and every spelling in `tests/test_review.py`'s `_PLACEHOLDER_INTENTS`; `True` for `"ship the TODO list view"` and for a 500-character string.
- `uv run pytest tests/test_review.py -q` is green, with the 20 existing `TestCheckIntentPresence` cases unmodified.
- `git diff` for this step touches only `plan_tool/review.py` and `tests/test_review.py`.
- `plan_tool/review.py`'s diff is the rename, its two call sites, and the docstring sentence — no change to `INTENT_PRESENCE_SOURCE`, the `SMELL_DETECTORS` entry, the findings' `info` severity, or `triage_reason`.
- `uv run pytest tests/test_duplication.py -q` is green (no second copy of the predicate was introduced).

## Applicable guardrails

- **The plan's `## Out of scope`, "any validation past presence"** — the published predicate keeps exactly the three non-values it has today. This step adds no length cap, no shape rule, and no comparison against any other text. The temptation lands specifically on the docstring: describing what a *good* intent looks like there would seed the rule the fence permanently refuses.
- **The plan's `## Architecture`, "Allowed reorganization: none"** — no module moves and no renderer changes. In particular `plan_tool/scope_fence.py` is consumed as shipped, so the divergence found in [Deferred](#deferred) is filed, not fixed here.
- **The plan's `## Architecture`, "produce before require"** — this step is the shared predicate only. It does not touch the finding's severity or its routing sets; those belong to step 6, after authoring and the proposer land.
- **The plan's `## Out of scope`, the schema fence** — `Plan.intent` / `Step.intent` stay `Optional` in `plan_tool/schema.py`, and no plan on disk is migrated or backfilled.

## Deferred

- **`plan_tool/scope_fence.py`'s placeholder vocabulary disagrees with `review.py`'s, and this step does not reconcile them.** `scope_fence._SECTION_PLACEHOLDER_RE` recognizes only the TODO spellings, while `review._BODY_PLACEHOLDER_RE` also recognizes TBD — so an intent of `TBD`, `_(TBD)_`, or `(TBD)` is flagged missing by `check_intent_presence` and still rendered into the fence block by `render_scope_fence` (verified 2026-08-02 against HEAD; the three TODO spellings agree). The mirror is deliberate — `scope_fence.py` is a stdlib-only leaf that cannot import `review` — so closing this needs a shared vocabulary decision, not an import. File it in `BUG_BACKLOG.md`; the plan's "no renderer changes" fence keeps it out of this step.
- **The plan body's two citations of the private name go stale on rename.** `docs/implementation-plans/2-intent-required.md` names `review.py:_is_usable_intent` in its `## Architecture` and `## Input` sections. That file is not in this step's `files:` list; correct both by hand as a separate edit when this step lands rather than leaving a dangling identifier in the plan that drives the work. The archived seeds under `docs/implementation-plans/plan-seeds/archive/` are dated history and stay as they are.
- **Every consumer of the published predicate** — the seed `## Outcome` map (step 2), the step-proposal JSON key and its retry (step 3), the proposer module (step 4), and the wizard path (step 5). This step publishes the symbol and adds no caller.
- **The finding's severity, its blocking status, and the parseable step-id directive** — steps 8 and 6 respectively.
- **Documenting either `intent` field** — step 7 owns `PLAN_FORMAT.md`, `SEED_FORMAT.md`, and the two flow docs.
