> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add an advisory check that flags a missing or placeholder intent

## Summary

This step adds one deterministic detector to `plan_tool/review.py` — `check_intent_presence` — that reports when a plan or its steps carry no usable `intent` (step 1's two optional fields). It registers as a new `SMELL_DETECTORS` entry, so it reaches the `completeness-audit` report and `plan-tool validate` with no other wiring. The main design decision is that the check emits **at most two findings per plan** — one for the plan-level field, one roll-up naming every step that lacks an intent — so advisory volume never grows with step count. On green, an intent-less plan gets two `info` findings in the advisory smell bucket, they never flip an exit code and never reach `apply_finding`, and a plan carrying an intent everywhere gets none.

## Table of Contents

- [Summary](#summary) — what ships, the two-findings cap, and the result on green.
- [Why](#why) — why the field needs a nudge that is not a gate.
- [Input](#input) — what this step reads from step 1 and from the detector table it joins.
- [Files (creates vs edits)](#files-creates-vs-edits) — three edited files, no new files.
- [Implementation](#implementation) — the detector, the registry entry, the routing rules, and six gotchas.
- [Tests](#tests) — ~19 cases in the review suite, 3 new plus 5 mechanical updates in the completeness-cmd suite, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — greps and assertions a reviewer can run.
- [References](#references) — the pytest doc this step's table-driven cases lean on.
- [Applicable guardrails](#applicable-guardrails) — the presence-only rule, and the two places breaking it is tempting.
- [Deferred](#deferred) — what steps 4–5 and the carved seed own, and the one refactor routed out.

## Why

Step 1 makes `intent` parseable and nothing more. A field nobody is ever asked for is a field nobody fills in, so without a nudge the two fields stay empty on every plan and steps 4 and 5 render an empty fence. This step supplies the nudge — and supplies it as the weakest signal the tool has, an `info` finding in the advisory smell bucket. That placement is the point, not a compromise: the plan's own Risks section names advisory volume as this feature's main hazard, because every plan on disk today lacks both fields, so the check fires on all of them at once. A finding that gated, or that fired once per step, would train operators to ignore the whole channel — the failure `CLAUDE.md` records for the withdrawn test-ordering contract.

## Input

Four contracts this step reads and does not own. Read each off HEAD before starting; where a landed name differs from a name below, the landed name wins.

- **Step 1's two schema fields.** `Plan.intent` and `Step.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD), each `Optional[str] = None`, storing whatever YAML handed over with no stripping. So this check sees `None`, `""`, `"   "`, `"TODO"`, a 500-character line, or a string with real newlines. It decides only which of those count as "no usable intent"; it judges nothing about the ones that do.
- **The smell detector table.** `plan_tool/review.py:SMELL_DETECTORS` is a `DetectorRegistry` of `DetectorEntry` rows — `(key, call, consumes, finding_sources, grade)`. `collect_smell_findings` is the only dispatcher; `DetectorRegistry.for_grade` refuses any entry with no `grade` class, so the new row must declare one.
- **The advisory bucket's contract.** `plan_tool/cli/completeness_phases.py:_run_deterministic_checks` puts `collect_smell_findings`' output on `_DeterministicReport.smell_recs`. That bucket is not a parameter of `plan_tool/cli/completeness_cmd.py:_completeness_has_blocking_findings` at all, and it is excluded from the deterministic finding count. Nothing this step does can change that — which is exactly why the finding belongs here.
- **`plan-tool validate`'s smell pass.** `plan_tool/cli/inspect.py:cmd_validate` calls `collect_smell_findings` on the valid path and prints each rec. It has no gate — only its `INVALID:` arm can flip the rc — so the new advisory reaches a second surface for free and still cannot fail CI.

**What this step cannot verify.** Nothing here proves an intent is *useful*. The suite can only show that a value is present, that four kinds of non-value (absent, empty, whitespace-only, placeholder) are treated alike, and that a long or vague intent produces nothing. That gap is deliberate and permanent — see [Applicable guardrails](#applicable-guardrails).

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/review.py` — add the `INTENT_PRESENCE_SOURCE` constant, the `check_intent_presence` detector, its `SMELL_DETECTORS` entry, and one branch in `triage_reason`.
- `tests/test_review.py` — add `TestCheckIntentPresence` (~18 cases) and one case in the existing `TestCollectSmellFindings`.
- `tests/cli/test_completeness_cmd.py` — add 3 cases; update `_REGISTRY_KEYS` and its count assertion, `_CORPUS_BUCKET_COUNTS`, `_CORPUS_DIGESTS`, and `_GRADE_INDEPENDENT_DETECTORS`.

## Implementation

### What must be true when the step is done

- A plan whose `intent` is missing, empty, whitespace-only, or a bare placeholder produces **one** `info` finding naming the plan.
- Steps in that same state produce **one** `info` roll-up finding naming every offending step id — not one finding per step.
- Both carry `source="intent-presence"`, and that source is in none of `APPLY_ELIGIBLE_SOURCES`, `STRUCTURAL_SOURCES`, `SELF_CONSISTENCY_SOURCES`, or `AUDIT_FIX_SOURCES`.
- A plan with an intent on the plan and on every step produces nothing.
- No finding echoes the intent's own text.

### The detector

Add `check_intent_presence(plan: Plan) -> list[Recommendation]` to `plan_tool/review.py`, next to the other advisory detectors. Model it on `plan_tool/review.py:validate_feature_refs` (advisory id-hygiene, `info`, never raises) and on the plan-level roll-up arm of `plan_tool/review.py:check_test_strategy_alignment`, whose "some steps declare `change_type`, others don't" finding already names a list of step ids in one message with `step_id=None`.

One helper decides everything: **"is this value a usable intent?"** — false when the value is `None`, false when `.strip()` is empty, false when it is a recognized placeholder, true otherwise. Reuse `plan_tool/review.py:_body_section_is_placeholder` for the third arm rather than writing a second placeholder rule; it already fullmatches `_BODY_PLACEHOLDER_RE`, which covers `TODO`, `TBD`, `_(TODO)_`, and `(TODO)`, case-insensitively.

Single-source the source token as a module constant, the way `plan_tool/review.py:SUPPRESSION_SHAPE_SOURCE` does, so the detector, the registry entry's `finding_sources`, and the `triage_reason` branch all key on one symbol.

### The registry entry

Append a `DetectorEntry` to `SMELL_DETECTORS`, **after** `concept-coverage`:

- `key="intent-presence"`, `finding_sources=(INTENT_PRESENCE_SOURCE,)`.
- `grade=DETECTOR_GRADE_INDEPENDENT` — the check reads frontmatter only, opens no detail file, and asks the same question at both grades.

Appending last (rather than inserting) keeps every existing finding's position in the rendered smell list, so the corpus digest diff in the completeness-cmd suite is a clean append per fixture instead of a reshuffle.

The entry does **not** go into `plan_tool/review.py:collect_deterministic_findings`. That table feeds `apply_finding`'s before/after delta and the `--iterate` apply loop; an advisory there would be dispatched to a prose editor that cannot add a frontmatter field.

### Routing text

`triage_reason`'s catch-all branch says "structural diagnostic — not auto-fixable … (fix the path / run `plan-tool detail` / author lessons)", which is wrong advice for a missing field. Add a branch keyed on the new source, in the style of the existing `DETAIL_ALTITUDE_SOURCE` branch, whose text points at the actual remedy — add a one-line `intent:` to the plan or the named steps. This is finding-routing prose, not validation.

### The key design decision, and the alternative rejected

**Two findings per plan, never more.** The rejected alternative is one finding per step lacking an intent, which is what `validate_feature_refs` does for dangling tags. It is rejected because volume then scales with step count: an eleven-step plan would open with eleven identical advisories on its first audit, and every plan on disk is in that state today. The roll-up says the same thing in one line and names the ids, so nothing is lost but the noise.

The cost is worth stating: the roll-up's stable id is computed from the id set (put the sorted ids in the `_make_rec_id` fingerprint, as `check_test_strategy_alignment` does), so filling in one step's intent mints a *different* id rather than shrinking the old one. That matters only to cross-run history, and `convergence_diagnosis` never treats an `info` finding as material — so the tradeoff is real but has no consequence here.

### Gotchas — the parts that are not free to vary

- **Order the two checks: empty first, placeholder second.** `_body_section_is_placeholder` returns `False` for an empty string, so testing placeholder-ness before emptiness silently lets `""` through as a usable intent.
- **Never put the intent's text in the finding.** A value with a real newline could otherwise start a line with `##` and forge a heading inside the rendered markdown report. Not echoing it also keeps step 2 out of the one-line collapse rule entirely — step 4 owns that, for rendering. The finding says *that* an intent is absent or a placeholder; it never quotes what was there.
- **`severity="info"`, not `medium`.** A `medium` rec on `smell_recs` still would not block (the granularity MIXED-STEP rec proves that), but `info` is the honest severity for a presence nudge and matches every other detector in the table.
- **Keep the source out of all four source sets.** That omission — not any code in the detector — is what makes `is_apply_eligible` and `is_structural` return `False` and keeps the finding off `_completeness_has_blocking_findings`.
- **Do not touch `SELF_CONSISTENCY_SOURCES`.** `SELF_CONSISTENCY_SMELL_DETECTORS` is derived from the smell table by intersecting `finding_sources` with that set, so adding the source there would silently promote the advisory onto the blocking-capable bucket.
- **A step with no `intent` and a plan with no `intent` are independent.** Report both when both are absent; the plan-level finding is not a substitute for the step roll-up.

### The one surface that changes without a code edit

`plan_tool/cli/inspect.py:cmd_validate` and the two report renderers pick the finding up automatically — the renderers loop over `smell_recs` with no per-source branching (`plan_tool/completeness_report.py:_fmt_finding_line` and the `### Smells (advisory)` block in `plan_tool/cli/completeness_phases.py`). Their intro blurbs do enumerate the bucket's detectors by name; refreshing that prose is out of this step's footprint — see [Deferred](#deferred).

## Tests

### Tests for this step

**`tests/test_review.py` — new `TestCheckIntentPresence`, beside `TestValidateFeatureRefs`.** Build fixtures with `plan_tool/parser.py:parse_plan_text`; the existing `_smell_plan_text` helper has no intent slot, so either extend it with an optional keyword or assemble the frontmatter inline.

- `test_plan_and_step_intents_present_yield_nothing` — a fully-filled plan produces `[]`.
- `test_missing_plan_intent_yields_one_finding` — plan intent absent → exactly one finding, `step_id is None`.
- `test_missing_step_intent_yields_one_rollup` — three steps all missing → exactly one step-level finding, not three.
- `test_rollup_names_every_missing_step_id` — the body names each offending id in ascending order.
- `test_rollup_omits_steps_that_have_an_intent` — a mixed plan names only the steps that lack one.
- `test_both_altitudes_report_independently` — plan and steps both missing → exactly two findings.
- `test_empty_string_intent_counts_as_missing` — `intent: ""`.
- `test_whitespace_only_intent_counts_as_missing` — `intent: "   "`.
- `test_placeholder_intents_count_as_missing` — table-driven over `TODO`, `TBD`, `_(TODO)_`, `(TODO)`, `todo`.
- `test_todo_inside_real_prose_is_not_a_placeholder` — `"ship the TODO list view"` is a usable intent.
- `test_findings_are_info_severity` — both findings.
- `test_findings_carry_the_intent_presence_source` — both findings.
- `test_finding_never_echoes_the_intent_text` — a newline-bearing placeholder-adjacent value never appears in `title`, `body`, or `suggested_action`, so no `##` can reach a rendered heading.
- `test_source_is_in_no_routing_set` — absent from `APPLY_ELIGIBLE_SOURCES`, `STRUCTURAL_SOURCES`, `SELF_CONSISTENCY_SOURCES`, `AUDIT_FIX_SOURCES`.
- `test_is_apply_eligible_and_is_structural_are_false` — both predicates.
- `test_triage_reason_is_intent_specific` — the reason names the intent remedy, not the generic "fix the path / run `plan-tool detail`" text.
- `test_rec_ids_are_stable_across_two_runs` — same plan, same ids.
- `test_long_or_vague_intent_yields_nothing` — a 500-character intent and the intent `"stuff"` each produce `[]`. This is the presence-only rule expressed as a test: no case in this class asserts anything about an intent's content or length.

**`tests/test_review.py` — existing `TestCollectSmellFindings`.**

- `test_intent_presence_reaches_the_smell_battery` — an intent-less plan's `collect_smell_findings` output contains the source. (The class's two existing cases assert membership, not equality, so they stay green.)

**`tests/cli/test_completeness_cmd.py` — 3 new cases.**

- `test_intent_presence_lands_on_smell_recs` (in `TestRunDeterministicChecks`) — an intent-less plan puts exactly two `intent-presence` recs on `smell_recs` and none on `self_consistency_recs`.
- `test_plan_with_intents_yields_no_intent_findings` (same class) — the negative control.
- `test_intent_presence_on_smell_recs_never_blocks` (in `TestCompletenessHasBlockingFindings`) — mirrors the existing `test_claim_vs_delivery_on_smell_recs_never_blocks`: the all-clear baseline stays non-blocking, and an `info` intent rec leaked onto the blocking bucket still sits below the medium+ threshold.

**`tests/cli/test_completeness_cmd.py` — 5 mechanical updates, all forced by the new registry entry.**

- `_REGISTRY_KEYS` gains `"intent-presence"` after `"concept-coverage"`, and its leading comment's counts change ("Eighteen entries" → nineteen; "the five inside `collect_smell_findings`" → six).
- `test_registry_covers_the_battery`'s `len(registry) == 18` → `19`. The sibling assertion in `test_grade_run_registry_is_the_full_battery` splices `"jira-grade-bundle"` at index 6, ahead of the smells, so it needs no change beyond the updated tuple.
- `_CORPUS_BUCKET_COUNTS` — every one of the seven fixtures gains `smell_recs: 2` (`clean` `{}` → `{"smell_recs": 2}`; `granularity-split` `2` → `4`; `footprint` `1` → `3`; the rest gain the key). The uniform `+2` across fixtures with different step counts is itself the readable proof that the cap is per plan, not per step.
- `_CORPUS_DIGESTS` — all seven re-pinned. Run the suite, read the failure's rendered JSON, and copy the new digest; do not hand-compute.
- `_GRADE_INDEPENDENT_DETECTORS` gains `"check_intent_presence"`, so the jira-grade dispatch case proves the detector still runs there.

**The alternative rejected on the corpus.** Seeding `_sectioned_plan_text` with plan and step intents would keep all seven digests unchanged and silence the new detector across the corpus. Rejected: `test_dropping_a_registry_entry_breaks_characterization` guards the table by *behavior*, and an entry that never fires in the corpus could be dropped from `SMELL_DETECTORS` with the characterization still green.

**Green-before-done gate.** Every case above must pass, plus the whole existing suite with no edits to any plan fixture other than the corpus counts and digests named here: `uv run pytest tests/test_review.py tests/cli/test_completeness_cmd.py -q`, then `uv run pytest tests/ -q`.

## Acceptance criteria

- `check_intent_presence` exists in `plan_tool/review.py` and takes a `Plan` only — no `repo_root`, no `plan_path`, no `invoker`.
- `rg 'intent-presence' plan_tool/review.py` shows the source spelled once as a constant and referenced by the detector, the registry entry, and the `triage_reason` branch.
- A plan with no intents produces exactly 2 findings from `check_intent_presence`, whether it has 1 step or 11.
- Every finding it produces has `severity == "info"`.
- `INTENT_PRESENCE_SOURCE` is in none of `APPLY_ELIGIBLE_SOURCES`, `STRUCTURAL_SOURCES`, `SELF_CONSISTENCY_SOURCES`, `AUDIT_FIX_SOURCES`; `is_apply_eligible` and `is_structural` both return `False` for such a rec.
- `deterministic_detector_registry()` reports 19 entries and its keys include `"intent-presence"`; `deterministic_detector_registry(GRADE_JIRA).keys` includes it too.
- `_completeness_has_blocking_findings` still accepts no `smell_recs` parameter, and a `completeness-audit` on an intent-less but otherwise clean plan exits 0 with and without `--fail-on-findings`.
- `plan-tool validate <name>` on an intent-less plan prints the advisory under `smells (advisory):` and exits 0.
- No finding's `title`, `body`, or `suggested_action` contains the intent value read off the plan — checkable by feeding a newline-bearing intent and asserting no `\n##` in any field.
- `rg -n 'len\(intent|len\(.*intent.*\) [<>]' plan_tool/review.py` returns nothing — no length rule shipped.

## References

- [How to parametrize fixtures and test functions — pytest](https://docs.pytest.org/en/stable/how-to/parametrize.html) — table-driven cases, used for the five placeholder spellings and the empty/whitespace variants.

## Applicable guardrails

- **Presence is the entire contract, and this step is where it is decided.** The check may ask only three things: is the field there, is it non-empty after whitespace collapse, is it a bare placeholder. No quality judgment, no comparison against `## Why` or any other prose, no comparison against a diff, no length cap, no required shape, no grammar rule.
- **This is the step where breaking that is tempting, in two specific places.** First, in `check_intent_presence` itself: once the value is in hand, a "too short to be useful" or "must contain a verb" test is one line away. Second, in the finding's body: quoting the intent back invites the next author to compare it to something. Neither is allowed, and the second is why the finding never echoes the text.
- **No gate, no exit-code flip, no refusal to advance.** The finding rides `smell_recs`, a bucket the blocking gate does not accept as a parameter. Do not add it to `SELF_CONSISTENCY_SOURCES`, to `collect_deterministic_findings`, or to any gate input.
- **Nothing becomes required at parse time.** This step adds no validator to `plan_tool/schema.py` and no parse-time check; every plan on disk keeps parsing exactly as it does today.
- **Delivery is not this step's job.** The check reports; it does not render an intent into any prompt. That is steps 4 and 5.

## Deferred

- **Any validation beyond presence** — permanently refused, not deferred and not tracked as a follow-up; see [Applicable guardrails](#applicable-guardrails).
- **Rendering the intent into the `detail` and `run` prompts** — steps 4 and 5 own it, through the shared leaf step 3 creates.
- **`create` authoring an intent, and propagation through `split` / `merge` / `scope-out` / `reground`** — carved out 2026-08-01 into `plan-seeds/intent-scope-fence-carved-fill-the-plan-s-intent-from-through-11.md`.
- **Refreshing the two smell-bucket intro blurbs** that enumerate the bucket's detectors, in `plan_tool/cli/completeness_phases.py` (the `### Smells (advisory)` block) and `plan_tool/completeness_report.py` (the `## Smells (advisory)` block) — both files are outside this step's declared footprint, and both renderers loop over the recs with no per-source branching, so the finding renders correctly without the edit. Route the prose refresh to reconcile.
- **Consolidating the two placeholder rules** — `plan_tool/review.py:_BODY_PLACEHOLDER_RE` and `plan_tool/detail.py:_SECTION_PLACEHOLDER_RE` encode overlapping vocabularies in two modules, deliberately, so `detail` does not import `review`. This step reuses the `review` one and adds no third copy; merging them is a cross-module refactor that belongs in `BACKLOG.md`, not in a feature step.
- **Delivering the intent to the conceptual-audit prompt** — carved out with the rest of the follow-up seed.
