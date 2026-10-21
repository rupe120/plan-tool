> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add an advisory check that flags a missing, placeholder, or over-long intent

## Summary

This step adds one deterministic, no-Claude check to `plan_tool/review.py` that reads step 1's `Plan.intent` and `Step.intent` fields and reports when an intent is absent, is a `TODO`/`TBD` placeholder, or runs past one line. It ships as a new `check_intent_presence` function plus a `SMELL_DETECTORS` registry entry, so the findings ride the advisory smell bucket that is documented as "never block the run" — the one channel that keeps a check firing on every plan on disk from flipping `has_blocking_findings`. The main design decision is cardinality: **absent** intents roll up into a single plan-wide finding naming every carrier, while a **placeholder** or **over-long** value gets its own finding, so a legacy plan produces exactly one advisory bullet instead of one per step. On green, `plan-tool validate` and `plan-tool completeness-audit` both surface the intent state of a plan advisorily, no exit code moves, and nothing anywhere judges whether an intent is any *good*.

## Table of Contents

- [Summary](#summary) — what the step ships and the cardinality decision behind it.
- [Why](#why) — why a field nothing reads is a field nobody fills.
- [Input](#input) — the four contracts this step reads and does not own, and what the tests cannot prove.
- [Files (creates vs edits)](#files-creates-vs-edits) — two declared files plus one noted addition.
- [Implementation](#implementation) — the check, the channel it must land in, the placeholder rule it reuses, and the rejected alternative.
- [Tests](#tests) — ~25 new cases plus two existing assertions this step rewrites.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the YAML, `re`, and pytest docs behind the one-line rule and the table-driven cases.
- [Applicable guardrails](#applicable-guardrails) — the fence entries that bind this step, and the exact line where breaking them is tempting.
- [Deferred](#deferred) — what the other eight steps own, and the one prose sweep routed to reconcile.

## Why

Step 1 makes `intent` parseable, and nothing else. A field that no surface ever mentions is a field nobody fills: `create` will not propose one until step 7, the prompts will not render one until steps 4–5, and an author reading a plan file has no signal that the key exists. This step is the only place in the plan where a human or an audit is *told* about intent, so it is what turns two optional fields from dead schema into something operators actually adopt. It also has to earn that without becoming noise — every plan in this repo lacks both fields today, so the check fires on all of them the first time it runs, and a finding class that fires everywhere and blocks is exactly the channel operators learn to ignore.

## Input

This step reads four contracts it does not own.

- **Step 1's two schema fields.** `Plan.intent` and `Step.intent` land as `Optional[str] = None` on `plan_tool/schema.py`, storing whatever YAML handed over with no stripping or normalizing. That is the load-bearing part: this check has to tell `None` from `""` from `"   "` from `"TODO"` from a `|` literal block, and step 1 deliberately preserves all five so it can. Read the landed field names off `plan_tool/schema.py`; if they differ from the names above, the landed name wins.
- **The `Recommendation` record** (`plan_tool/review.py`). Findings are built with `_make_rec_id(step_id, source, fingerprint)` for a stable content-addressed id, a `source` token, a `severity` string, and `step_id` set for a step-scoped finding or `None` for a plan-scoped one.
- **The detector-registry contract** (`plan_tool/review.py`: `DetectorEntry`, `DetectorRegistry`, `SMELL_DETECTORS`). An entry is `(key, call, consumes, finding_sources, grade)`; `DetectorRegistry.for_grade` **raises** on an entry with no grade class, so the new entry must declare one explicitly rather than letting it default.
- **How the smell bucket renders.** `plan_tool/cli/completeness_phases.py` prints each smell as `- {SEVERITY}: {body}` under `### Smells (advisory)` and puts `severity / source / id / title / body` in the `--json` payload; `plan_tool/cli/inspect.py:cmd_validate` prints `- {title} [{source}]: {body}`. **Neither surface renders `suggested_action` for a smell**, so the remedy has to live in `body` to reach a reader.

**What this step cannot verify.** The check sees frontmatter only. It can prove an intent is present, is not a placeholder, and fits on a line — it cannot prove the intent is *true*, *useful*, or *agrees with anything*, and the plan's fence forbids trying. The tests therefore assert shape, cardinality, severity, and routing; nothing asserts quality.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/review.py` — add the `INTENT_PRESENCE_SOURCE` token and the `_INTENT_MAX_CHARS` cap beside the other smell source constants; add `check_intent_presence(plan)`; add one `DetectorEntry` to `SMELL_DETECTORS`.
  - `tests/test_review.py` — add a `TestIntentPresence` class next to `TestValidateFeatureRefs`; extend the `_smell_plan_text` fixture helper with an optional plan-level `intent`; update `TestDeterministicFanoutCharacterization._SMELLS` and the `_fanout_corpus` docstring.
  - `tests/cli/test_completeness_cmd.py` — **an addition beyond the plan's declared `files:` list, noted deliberately.** One assertion (`assert report.smell_recs == []` at the end of `TestRunDeterministicChecks::test_run_deterministic_checks_collects_concept_findings`) runs `_run_deterministic_checks` against a real fixture with the smell collector *unpatched*, so a real intent finding reddens it. Every other smell assertion in that file and in `tests/test_completeness_report.py` / `tests/cli/test_inspect_cmds.py` monkeypatches `collect_smell_findings` or passes synthetic recs, so this is the only line outside the declared set that has to move.

## Implementation

**The behavior: one pure function over the parsed plan, wired into the advisory smell fan-out.**

### The check

Add `check_intent_presence(plan: Plan) -> list[Recommendation]` to `plan_tool/review.py`, modeled on `validate_feature_refs` — the closest sibling: pure, plan-only, never raises, emits `info` findings at both plan and step scope.

**The signature is the guardrail.** Take `plan: Plan` and nothing else. No `repo_root`, no `plan_path`, no `invoker`. A function that cannot open a file cannot compare an intent to plan prose, to a detail's `## Why`, or to a diff — which is the thing the plan's fence bans outright. Anything that would need a second parameter is out of scope by construction.

Classify each carrier into exactly one of four states, in this precedence order:

- **missing** — the value is `None`, or `_body_section_is_empty(value)` is true (empty or whitespace-only).
- **placeholder** — `_body_section_is_placeholder(value)` is true.
- **over-long** — the value contains a newline, or its length exceeds `_INTENT_MAX_CHARS`.
- **ok** — everything else.

Precedence matters and is not free to vary: a 400-character whitespace-only value is **missing**, not over-long, because a reader needs to be told the field is empty, not that it is long. Each carrier yields at most one finding.

**Reuse the placeholder vocabulary, do not mint a second one.** `_body_section_is_placeholder` and `_body_section_is_empty` already exist in `plan_tool/review.py` for the plan-body completeness check, and `_BODY_PLACEHOLDER_RE` already covers `_(TODO)_`, bare `TODO`/`TBD`, and `(TODO)`. That regex is applied with `fullmatch` against the stripped text, which is exactly the property this check wants — an intent that *mentions* a TODO ("Fix the TODO handling in the parser") is real prose, not a placeholder. This is the same rule at two altitudes; a second copy would drift.

**The carrier set skips `done` steps.** Intent's job is to brief work that has not happened yet, and `check_detail_coverage` and `check_jira_grade_bundle` already skip `done` steps for the same reason ("the artifact briefs a step before it runs"). The plan-level intent is always checked regardless of step states.

### Cardinality — the key decision

- **Missing → one rolled-up finding per plan, at most.** `step_id=None`; the body names the plan (when its own intent is absent) and every step id that lacks one. On any plan on disk today that is exactly one bullet instead of eleven.
- **Placeholder → one finding per offending carrier.** Somebody typed a value; the fix is per-carrier.
- **Over-long → one finding per offending carrier**, with the actual measurement and the cap in the body ("312 characters, cap 200" / "spans 3 lines").

The asymmetry is deliberate and worth a comment in the code: absence is the state every existing plan is in, so it gets the volume control; a bad *value* is a thing one person typed, so it gets its own line. The rejected alternative — one finding per carrier for all three kinds — is simpler to write and produces N+1 near-identical bullets on the first run of every plan in the repo, which is the failure the plan's Risks section names.

**Stable ids.** Fingerprint on the kind plus the carrier set, never on the intent text. Two different over-long values on the same step are the same unresolved finding and must share an id; a roll-up whose step set changed is a different finding and should mint a new one.

**Self-contained bodies.** Put the remedy sentence in `body` (see [Input](#input)). Set `suggested_action` too, matching `validate_feature_refs`, but do not rely on it being displayed.

### The channel — this is where the step can go wrong

Register the check in `SMELL_DETECTORS`, **not** in `collect_deterministic_findings`.

```
DetectorEntry(
    "intent-presence",
    lambda ctx, results: check_intent_presence(ctx.plan),
    finding_sources=(INTENT_PRESENCE_SOURCE,),
    grade=DETECTOR_GRADE_INDEPENDENT,
)
```

Placement is a readability choice — the registry's `__post_init__` constrains only `consumes` ordering — and next to `feature-refs` reads best, since both are plan-frontmatter hygiene with no file I/O. `DETECTOR_GRADE_INDEPENDENT` because the check reads frontmatter and opens no detail body, so it is right at both grades.

Four properties must hold, and three of them are satisfied by *not* editing something:

- **Severity is `info` on every finding.** Same as `feature-ref`, `self-referential`, and `claim-vs-delivery`.
- **`INTENT_PRESENCE_SOURCE` stays out of `SELF_CONSISTENCY_SOURCES`.** Adding it there would route the finding onto the blocking-capable bucket, and `_completeness_has_blocking_findings` (`plan_tool/cli/completeness_cmd.py`) blocks that bucket at medium+.
- **It stays out of `APPLY_ELIGIBLE_SOURCES` and `STRUCTURAL_SOURCES`.** Both are opt-in frozensets, so this is a non-edit — but it is the non-edit that keeps `apply_finding` from being asked to write an `intent:` into every plan in the repo.
- **It stays out of `collect_deterministic_findings`.** That fan-out feeds the `--iterate` apply loop's pre/post delta. Smells are deliberately excluded from it already; keep it that way.

Two more consequences that need no edit and should be confirmed rather than assumed:

- **Not persisted to the sidecar.** `plan_tool/cli/completeness_phases.py` builds `sidecar_recs` from the correctness, conceptual, data-contract, concept-link, and `medium` `granularity-split` recs only. An `info` smell is none of those, so it never reaches the saved report — which is what keeps a finding that recurs on every audit from feeding `convergence_diagnosis`'s spinning verdict.
- **`DATA_CONTRACT.md` needs no entry.** Its `source` row is an open-ended example list (`file-check`, `heuristic`, `deps`, `claude`, `granularity-split`, …), not a closed vocabulary, so the drift guard in `tests/test_data_contract.py` does not fire on a new token.

### Names and the cap

Settle these here — step 11 documents them and can only describe what got typed:

- `INTENT_PRESENCE_SOURCE = "intent-presence"` — public, single-sourced like `CLAIM_VS_DELIVERY_SOURCE` and `SUPPRESSION_SHAPE_SOURCE`. It takes the plan's own vocabulary ("presence is advisory, and only presence"); an unusable value is an intent that is present but not usably so.
- `_INTENT_MAX_CHARS = 200` — private, matching the file's cap convention (`_MAX_HEURISTIC_BYTES`, `_CARRIED_BODY_EXCERPT_CHARS`). 200 is roughly three times a git subject line and comfortably one terminal line; the plan-level intent in this plan's own `## Scope guardrails` is about 135 characters, so the cap is generous rather than tight. The finding body must print the number so a reader never has to open the source to learn it.

## Tests

All cases live in `tests/test_review.py` unless noted. Add a `TestIntentPresence` class beside `TestValidateFeatureRefs` and reuse the existing `_smell_plan_text` / `parse_plan_text` helpers; extend `_smell_plan_text` with an optional plan-level `intent` argument rather than hand-writing frontmatter in each case.

### Tests for this step

**Classification and precedence**

- `test_fully_populated_plan_yields_no_findings` — plan and every step carry a short one-line intent → `[]`.
- `test_legacy_plan_with_no_intent_anywhere_yields_one_finding` — a three-step plan with no `intent:` anywhere produces exactly one finding, `step_id is None`.
- `test_rolled_up_missing_finding_names_the_plan_and_every_step_id` — the body names the plan and ids 1, 2, 3.
- `test_empty_string_intent_counts_as_missing` — `intent: ''`.
- `test_whitespace_only_intent_counts_as_missing` — `intent: '   '`.
- `test_placeholder_vocabulary_matches_the_body_completeness_marker` — parametrized over `_(TODO)_`, `TODO`, `TBD`, `(TBD)`; each classifies as placeholder. Pins the shared `_BODY_PLACEHOLDER_RE`.
- `test_prose_mentioning_todo_is_not_a_placeholder` — "Fix the TODO handling in the parser" is a fine intent. Guards the `fullmatch` semantics.
- `test_over_long_intent_reports_its_length_and_the_cap` — body contains both numbers.
- `test_intent_exactly_at_the_cap_is_not_flagged` — boundary case, reading `_INTENT_MAX_CHARS` rather than the literal.
- `test_cap_constant_value` — pins `_INTENT_MAX_CHARS == 200` so a silent change is caught.
- `test_multi_line_intent_is_flagged_as_over_long` — a `|` literal-block value with real newlines.
- `test_missing_takes_precedence_over_over_long` — a 400-character whitespace-only value yields one missing finding and no over-long one.
- `test_each_carrier_yields_at_most_one_finding` — no carrier appears twice in the result set.

**Cardinality and scope**

- `test_placeholder_fires_once_per_carrier` — two placeholder steps → two findings, each with its own `step_id`.
- `test_done_steps_are_skipped` — a `done` step with no intent is absent from the roll-up and mints no finding of its own.
- `test_plan_level_finding_has_step_id_none` — an over-long plan intent carries `step_id is None`.
- `test_ids_are_stable_across_repeat_calls` — same plan, same ids.
- `test_id_changes_when_the_missing_carrier_set_changes` — adding a step without an intent mints a new roll-up id.
- `test_id_is_unchanged_when_only_the_intent_text_changes` — two different over-long values on the same step share an id.
- `test_every_finding_is_info_severity_and_carries_the_source_token`.
- `test_body_states_the_remedy_without_suggested_action` — the body alone tells a reader what to do, because neither renderer shows `suggested_action` for a smell.

**Wiring and routing**

- `test_detector_is_registered_in_the_smell_table` — `"intent-presence"` is in `SMELL_DETECTORS.keys`, its `finding_sources` names `INTENT_PRESENCE_SOURCE`, and its grade is `DETECTOR_GRADE_INDEPENDENT`.
- `test_detector_runs_at_both_detail_grades` — the key survives `SMELL_DETECTORS.for_grade(GRADE_RUN)` and `.for_grade(GRADE_JIRA)`.
- `test_source_is_not_apply_eligible_structural_or_self_consistent` — absent from `APPLY_ELIGIBLE_SOURCES`, `STRUCTURAL_SOURCES`, and `SELF_CONSISTENCY_SOURCES`.
- `test_collect_smell_findings_surfaces_the_intent_finding` — end-to-end through the fan-out.
- `test_collect_deterministic_findings_omits_intent` — the apply-loop fan-out never carries it; mirrors `TestCollectDeterministicOmitsCodeSplit`.

**Existing assertions this step rewrites** (each is correct-by-design at HEAD and necessarily reddens — a failure here is the new detector working, not a regression):

- `TestDeterministicFanoutCharacterization._SMELLS` — all four `_fanout_corpus` fixtures lack `intent:`, so each gains one `intent-presence` row and the `"clean"` entry goes from `[]` to one row. Add the rows rather than giving the fixtures intents: the corpus exists to trip every detector, and silencing the new one there would make its own docstring false.
- `_fanout_corpus`'s docstring — "`collect_smell_findings`' five" becomes six.
- `tests/cli/test_completeness_cmd.py::TestRunDeterministicChecks::test_run_deterministic_checks_collects_concept_findings` — its trailing `assert report.smell_recs == []` becomes an assertion that the bucket holds exactly the intent finding.

**Green-before-done gate.** Step 1 must be landed and green first — the check reads `Plan.intent` / `Step.intent`. Then every case above, plus `uv run pytest tests/ -q` with no other test edited and no plan fixture given an `intent:` value. A green full suite with untouched fixtures is the proof that adding this check migrates nothing.

## Acceptance criteria

- `plan_tool/review.py` defines `INTENT_PRESENCE_SOURCE == "intent-presence"` and `_INTENT_MAX_CHARS == 200`.
- `check_intent_presence` takes exactly one parameter, the parsed plan: `rg 'def check_intent_presence' plan_tool/review.py` shows no `repo_root`, no `plan_path`, no `invoker`.
- The function body opens no file and reads no prose: `rg 'read_text|split_body_sections|Path\(' ` over the function returns nothing.
- Calling it on a plan whose plan-level and every step-level `intent` is a short one-line string returns `[]`.
- Calling it on a three-step plan with no `intent` anywhere returns exactly one `Recommendation`, with `step_id is None`, `severity == "info"`, `source == "intent-presence"`, and a body naming the plan and all three step ids.
- An intent of `_INTENT_MAX_CHARS + 1` characters produces one finding whose body contains both that length and `200`; an intent of exactly `_INTENT_MAX_CHARS` characters produces none.
- An `intent: |` literal block with two lines produces one over-long finding.
- A `done` step with no intent contributes nothing to the result set.
- `"intent-presence" in SMELL_DETECTORS.keys`, and that entry's `grade` is `DETECTOR_GRADE_INDEPENDENT`.
- `INTENT_PRESENCE_SOURCE` is in none of `APPLY_ELIGIBLE_SOURCES`, `STRUCTURAL_SOURCES`, `SELF_CONSISTENCY_SOURCES`.
- `collect_deterministic_findings` over a plan with no intent returns no `intent-presence` finding.
- `plan-tool completeness-audit` on a plan with no intent reports `has_blocking_findings: false` when nothing else is wrong, and prints the finding under `### Smells (advisory)`.
- `plan-tool validate <name> --fail-on-findings` on an otherwise valid plan with no intent still exits 0.
- `uv run pytest tests/ -q` is green with no edit to any plan fixture under `tests/fixtures/`.

## References

- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — scalar styles and line folding: why a plain multi-line scalar arrives as one space-joined line and a `|` literal block is the only way a newline reaches the field, which is what the over-long check has to detect.
- [`re` — Regular expression operations (Python 3 documentation)](https://docs.python.org/3/library/re.html) — `fullmatch` versus `search`, the distinction that lets the reused placeholder pattern flag a bare `TODO` while leaving prose that mentions one alone.
- [How to parametrize fixtures and test functions — pytest](https://docs.pytest.org/en/stable/how-to/parametrize.html) — the table-driven form for the placeholder-vocabulary and missing-shape cases.

## Applicable guardrails

- **No check comparing an intent against prose or against a diff.** This is the guardrail that binds this step hardest, because this is the one step that writes code which *reads* an intent — adding `plan_path` to the signature and glancing at `## Why`, or comparing the intent to the step title, is a two-line change from here. The fence is enforced structurally: the function takes only the parsed plan. Criterion: `rg 'read_text|split_body_sections' ` over the new function returns nothing.
- **Nothing becomes required at parse time, and no plan on disk is migrated.** The check never raises, never edits a plan, and never reaches `apply_finding`. Criterion: the full suite is green with every existing plan fixture untouched.
- **Presence is advisory, and only presence.** Every finding is `info`, rides the smell bucket, and cannot flip `has_blocking_findings` or an exit code. Nothing judges whether an intent is any good.
- **Findings asking that intent be made required, that an agreement check be added, or that propagation widen past the four structural verbs go to `BACKLOG.md`.** They are outside the plan's fence; do not apply them as expansion of this step.

## Deferred

- **Naming the intent family in the `### Smells (advisory)` blurb** in `plan_tool/cli/completeness_phases.py` — the blurb is an example list rather than a contract, and touching it pulls a CLI renderer plus `tests/test_completeness_report.py` into a two-file step for one sentence. Route it to reconcile.
- **Documenting the fields, the cap, the source token, and the four propagation rules** — step 11 owns `PLAN_FORMAT.md`, `SEED_FORMAT.md`, `CLAUDE.md`, the flow docs, and closing `BACKLOG #206`.
- **Rendering intent into any prompt** — steps 3, 4, and 5 own the shared fence renderer and the `detail` / `run` prompt seams. This step surfaces intent to a *reader*, never to a model.
- **`create` filling a plan's intent from the seed's `## Outcome`, and proposing a per-step intent** — steps 6 and 7 own `plan_tool/create.py`.
- **What `split` and `merge` do with a step's intent** — step 8 owns the rule in `plan_tool/detail.py`.
- **Carrying intent into the scope-out and reground forward seeds** — step 9 owns `plan_tool/scope_out.py` and `plan_tool/reground.py`.
- **Giving this plan and its own steps an `intent` value** — step 11, the plan's stated first use of the feature.
- **Making the finding apply-eligible or auto-fillable** — deliberately not shipped. `apply_finding` would be asked to invent an intent for every step of every plan in the repo, which is authoring by machine of exactly the field the plan wants a human to settle.
- **An intent-vs-work agreement check at any altitude** — refused by the plan's fence, not merely deferred. If it is ever revisited it is its own backlog entry and must first answer what makes it different from the withdrawn `change_type` test-ordering contract.
