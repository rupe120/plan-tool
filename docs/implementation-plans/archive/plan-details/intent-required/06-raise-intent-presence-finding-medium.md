> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Raise the intent-presence finding to `medium` and move it onto the blocking self-consistency bucket

## Summary

Flip both `check_intent_presence` findings in `plan_tool/review.py` from `severity="info"` to `severity="medium"` and add `INTENT_PRESENCE_SOURCE` to the `SELF_CONSISTENCY_SOURCES` frozenset. Those two edits are the whole routing change: `SELF_CONSISTENCY_SMELL_DETECTORS` is *derived* from that frozenset by intersecting each `DetectorEntry.finding_sources`, and both the finalize gate (`_self_consistency_from_smells`) and the `--iterate` loop's blocking signal (`collect_self_consistency_findings`) key on the same set — so nothing gets hand-listed in a second place. The rest of the step is honesty repair in `plan_tool/cli/completeness_phases.py`: the report's `### Self-consistency` blurb and the partition comment still name only `suppression-shape`, and the `### Suggested next steps` tail falls through to "Remaining finding(s) above are advisory (info/nit)" for a report whose only blocking finding is a self-consistency one — which after this step is the common case. On green, a plan carrying no usable intent reports two `medium` findings on the blocking bucket, `has_blocking_findings` is `true` in `--json`, `completeness-audit --iterate` halts with the manual-fix message instead of "converged", and a completed audit still exits 0 unless `--fail-on-findings` was passed.

## Table of Contents

- [Summary](#summary) — what the step changes and what is true on green.
- [Why](#why) — why the advisory can be promoted now and not before.
- [Input](#input) — the sibling-step outcomes and the shipped partition contract this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — the four files touched and the per-file edits.
- [Implementation](#implementation) — the two production edits, the report repair, the constraints, and the alternatives rejected.
- [Tests](#tests) — the cases this step adds or re-pins, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checks a reviewer or CI can run.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step's code.
- [Deferred](#deferred) — the surfaces outside this step's files and the work routed elsewhere.

## Why

`check_intent_presence` fires on essentially every plan in the repo and does nothing. It is `info`, so `_completeness_has_blocking_findings` never sees it (advisory smells are not even a parameter of that gate), the `--iterate` loop reports "converged" beside it, and `triage_reason` explicitly calls it advisory. A finding that fires everywhere and stops nothing is the shape that trains an operator to skim past the whole channel.

Promoting it was unsafe until now for one concrete reason: there was nowhere to send an operator who hit it. Steps 3 and 5 close that gap for plans created from now on. For a plan already on disk the remedy is a one-line frontmatter edit, which needs no machinery — so with authoring landed, the promotion converts noise into a gate instead of into a dead end.

## Input

This step reads three sibling outcomes and one shipped contract, and changes none of them.

- **Step 3's outcome** — `create`'s step-proposal JSON carries `intent`, so a newly created plan's steps land with a value. Without it, every plan `create` writes would block on the round it is created.
- **Step 5's outcome** — the create wizard offers a proposed intent for the seed / `--from` / interactive / canonical paths that supply none, so the plan-level field is filled too.
- **The shipped self-consistency partition contract** in `plan_tool/review.py`. Three parts, and all three key on one frozenset:
  - `SELF_CONSISTENCY_SOURCES` — the membership.
  - `SELF_CONSISTENCY_SMELL_DETECTORS` — built by filtering `SMELL_DETECTORS` for entries whose `finding_sources` intersect that frozenset. Adding a source to the frozenset therefore pulls its detector into this registry with no second edit.
  - `_self_consistency_from_smells` (the finalize gate's partition, called from `plan_tool/cli/completeness_phases.py:_run_deterministic_checks`) and `collect_self_consistency_findings` (the `--iterate` loop's independent collector, called from `plan_tool/cli/completeness_cmd.py`). Both filter on the same frozenset and both preserve the smell fan-out's relative order, which is what keeps `TestCollectSelfConsistencyFindings`' parity assertion true.

**What this step cannot verify.** Presence, and nothing else. Raising the severity does not make the check smarter — a one-word intent still clears it. The promotion changes only whether the *absence* of a value stops the loop.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — flip both `Recommendation` literals in `check_intent_presence` to `severity="medium"` and refresh its docstring; add `INTENT_PRESENCE_SOURCE` to `SELF_CONSISTENCY_SOURCES`; reword the `INTENT_PRESENCE_SOURCE` branch in `triage_reason`, which currently calls the finding advisory; sweep the semantic-smell header comment above `SUPPRESSION_SHAPE_SOURCE` and the `collect_smell_findings` docstring, both of which name `suppression-shape` as the one elevated source.
  - `plan_tool/cli/completeness_phases.py` — update the `_DeterministicReport` bucket docstring and the partition comment in `_run_deterministic_checks`; extend the `### Self-consistency` blurb in `_render_grouped_report`; fix that function's `### Suggested next steps` tail so a blocking self-consistency finding is not described as advisory and gets a remedy bullet.
  - `tests/test_review.py` — re-pin the intent-presence severity and routing cases, the derived-registry key tuple, the self-consistency collector cases, and the fan-out characterization maps.
  - `tests/cli/test_completeness_cmd.py` — re-pin the blocking-gate case, the bucket-placement case, the deterministic-report corpus counts and digests, and add next-steps coverage.

## Implementation

### The two production edits in `plan_tool/review.py`

- **Severity.** Both `Recommendation(...)` literals inside `check_intent_presence` go from `severity="info"` to `severity="medium"`. Nothing else about either finding moves: same two findings per plan, same `step_id=None`, same titles and bodies, same `suggested_action` (including step 6's directive marker), same never-echo-the-value property.
- **Membership.** Add `INTENT_PRESENCE_SOURCE` to the `SELF_CONSISTENCY_SOURCES` frozenset, beside `SUPPRESSION_SHAPE_SOURCE`, `ORPHANED_DELIVERABLE_SOURCE`, and `CONCEPT_COVERAGE_SOURCE`. **Do not** hand-add the detector anywhere else — `SELF_CONSISTENCY_SMELL_DETECTORS` derives itself from this frozenset, and a hand-listed second copy is exactly the drift its comment says the derivation exists to prevent.
- **Recommendation ids do not move.** `_make_rec_id` hashes only the fingerprint string (`"plan-intent"` / `"step-intent:<ids>"`), never the severity — so a saved sidecar does not re-report the promoted finding as a new one. The literal ids pinned in the fan-out characterization map are the proof; if they change, something else was edited.

### What stays exactly where it is

- **The `intent-presence` entry stays in `SMELL_DETECTORS`.** This is the `suppression-shape` shape: the detector fans out through `collect_smell_findings` (so `plan-tool validate`'s advisory listing keeps printing it, as it already does for the `medium` `suppression-shape` rec), and `_run_deterministic_checks` partitions it off `smell_recs` onto `self_consistency_recs`. Moving the entry into `SELF_CONSISTENCY_DETECTORS` would be wrong — that registry holds the one detector that is *never* a smell.
- **The grade class stays `DETECTOR_GRADE_INDEPENDENT`.** `intent` is a frontmatter field, readable at both grades, so the finding blocks at jira grade too — matching `concept-coverage` and `orphaned-deliverable`. Do not reclassify it to `DETECTOR_GRADE_RUN_ONLY` to spare the jira lane; the reason `suppression-shape` is run-grade-only (it reads run-grade detail bodies) does not apply here.
- **The source stays out of `APPLY_ELIGIBLE_SOURCES`, `STRUCTURAL_SOURCES`, `AUDIT_FIX_SOURCES`, and `collect_deterministic_findings`.** `apply_finding` is a prose editor; feeding it a frontmatter-field finding would corrupt its pre/post delta. `partition_findings_for_triage` gates on apply-eligibility *before* it looks at severity, so the promoted finding is still deferred at every call site (no caller passes `apply_eligible_only=False`).
- **The roll-up shape survives.** At most two findings per plan, whatever the step count. A blocking finding fanned out per step on a corpus where nearly every plan predates the field is worse than the advisory it replaces. `test_cap_holds_as_step_count_grows` must stay green untouched.

### `triage_reason` and the two stale comments

`triage_reason`'s `INTENT_PRESENCE_SOURCE` branch currently reads "advisory — add a one-line `intent:` …". That word is now false. Reword it to say the finding blocks completeness convergence, and name the remedy: add a one-line `intent:` to the plan or the named steps. Keep it clear that it is not an `apply_finding` edit — that is why the branch exists at all.

Three comments in the same file are made false by this step, and the third is the one an `intent` grep cannot find:

1. the semantic-smell layer's header comment above `SUPPRESSION_SHAPE_SOURCE`, which names `suppression-shape` as the lone elevated smell;
2. `collect_smell_findings`' docstring, which lists "``intent`` presence" among the advisory detectors;
3. **the comment on `SELF_CONSISTENCY_SOURCES` itself**, which describes every member as *"NOT auto-appliable (`apply_finding`, a prose editor, can't rewire a plan) — the fix is a manual plan edit."* That stays true for the member this step adds — an intent is fixed by hand, one line. Leave the rule intact and only widen the sentence naming which sources are in the bucket.

Sweep all three — this is the vocabulary half of the change, and it is the half that gets skipped. Note that (3) contains no occurrence of the word "intent", so this step's `rg 'intent' …` acceptance grep cannot catch it; the acceptance check below is widened accordingly.

### The report repair in `plan_tool/cli/completeness_phases.py`

Three of these are prose; the last is a real behavior fix.

- `_DeterministicReport`'s docstring describes `self_consistency_recs` as the bucket the gate reads at `medium`+. It is still correct, but its membership sentence should mention the missing-intent case so a reader of the dataclass knows what lands there.
- The partition comment in `_run_deterministic_checks` says "the elevated `medium` `suppression-shape` recs partitioned off `smell_recs`". Generalize it — the partition keys on the source set, not on one detector.
- `_render_grouped_report`'s `### Self-consistency` blurb lists what the bucket contains (claims no step delivers, deliverables no step consumes, unaccounted signed-off concepts). Add the missing plan/step intent.
- **The next-steps tail is the behavior fix.** `_structural` — the condition that decides whether the tail names a follow-up command — does not include `det.self_consistency_recs`. So a report whose only blocking finding is a self-consistency one produces an empty `_next_steps`, falls through to the `has_any` branch, and prints *"Remaining finding(s) above are advisory (info/nit) — review them by eye; no follow-up command needed."* That is already wrong for `suppression-shape` and `orphaned-deliverable`; after this step it is wrong on nearly every audit, and it directly contradicts what this step is for.

  What must be true: when the bucket carries a `medium`+ finding, the tail names a remedy and never calls it advisory. One way to get there — compute a blocking-self-consistency flag beside the existing `_structural` / `_missing_detail` / `_detail_level` flags, append a bullet for it, and let the existing `if not _next_steps:` fallback stay untouched (a non-empty `_next_steps` already suppresses it). For the bullet's text, follow the tail's established split:
  - otherwise say the fix is a manual plan edit, since neither `apply_finding` nor `completeness-apply` targets these;
  - under `--grade jira`, mirror the arm already there and name **no** apply verb.

  Keep every suggestion a `plan-tool` command. This tail ships to operators and must never point at a Claude Code session activity.

### What needs no change at all

- `_completeness_has_blocking_findings` in `plan_tool/cli/completeness_cmd.py` already reads `self_consistency_recs` at `medium`+. The promoted finding flips `has_blocking_findings` for free.
- The `--iterate` loop needs no new mechanics. `collect_self_consistency_findings` picks the finding up from the derived registry; the loop's `not open_apply` branch already halts with `_loop_stop_reason = "manual_fix_blocking_findings"` and the honest manual-fix message. Because the finding is never apply-eligible, the loop cannot spin on it — it halts on the first round with no apply-eligible work left.
- The exit-code convention is unchanged. A completed audit exits 0 however many intent findings it prints; only `--fail-on-findings` flips the rc, via the same gate.

### Alternatives rejected

- **Mint a second, blocking intent detector and leave the advisory one.** Two findings for one fact, two ids in the sidecar, and two places to keep in step with `is_usable_intent`.
- **Hand-list the entry in `SELF_CONSISTENCY_SMELL_DETECTORS`.** Reintroduces the exact drift the derivation removed.
- **Add the source to `APPLY_ELIGIBLE_SOURCES` so `--iterate` can close it.** `apply_finding` edits prose; a frontmatter field is not its target, and routing it there would poison the pre/post delta the apply loop measures.

## Tests

### Tests for this step

Existing cases that must be re-pinned (each currently asserts the pre-promotion state):

- `tests/test_review.py` `TestCheckIntentPresence::test_findings_are_info_severity` → `test_findings_are_medium_severity` — both findings come back `medium`.
- `tests/test_review.py` `TestCheckIntentPresence::test_source_is_in_no_routing_set` → reworked — `INTENT_PRESENCE_SOURCE` is now **in** `SELF_CONSISTENCY_SOURCES` and still out of `APPLY_ELIGIBLE_SOURCES`, `STRUCTURAL_SOURCES`, and `AUDIT_FIX_SOURCES`.
- `tests/test_review.py` `TestCheckIntentPresence::test_triage_reason_is_intent_specific` — the reason names the remedy and no longer calls the finding advisory.
- `tests/test_review.py` `TestDetectorRegistry::test_self_consistency_smell_subset_is_derived_from_sources` — the expected key tuple becomes `("suppression-shape", "concept-coverage", "intent-presence")`, in `SMELL_DETECTORS` declaration order.
- `tests/test_review.py` `TestCollectSelfConsistencyFindings::test_includes_orphaned_deliverable` — the fixture declares no intent, so the collector now returns the two intent recs alongside the orphan rec; assert the source list, not a single-element list.
- `tests/test_review.py` `TestCollectSelfConsistencyFindings::test_clean_plan_yields_no_self_consistency_findings` — a "clean" plan with no intent is no longer clean. Thread an optional intent (and per-step intents) through the `_write_orphan_plan` helper — `_smell_plan_text` already takes an `intent` argument, which `_intent_plan` uses — so the fixture can be genuinely clean, and keep the assertion as an empty list.
- `tests/test_review.py` `TestDeterministicFanoutCharacterization` — `_INTENT_RECS` severity becomes `medium` (the pinned id strings must not move); `_SMELLS` keeps the intent entries, because `collect_smell_findings` still produces them; `_SELF_CONSISTENCY` gains them for all four fixtures, ordered smell-derived first and `orphaned-deliverable` last.
- `tests/cli/test_completeness_cmd.py` `test_intent_presence_on_smell_recs_never_blocks` → `test_intent_presence_blocks_at_medium` — a `medium` intent rec on `self_consistency_recs` returns `True`; an `info` one still returns `False`.
- `tests/cli/test_completeness_cmd.py` `test_intent_presence_lands_on_smell_recs` → `test_intent_presence_lands_on_self_consistency_recs` — two `medium` recs on the blocking bucket, none on `smell_recs`, still capped at two across a three-step plan.
- `tests/cli/test_completeness_cmd.py` `test_run_deterministic_checks_yields_empty_self_consistency_bucket` — the `_CLEAN_STEPS` fixture declares no intent, so the bucket now carries the two intent recs; re-pin it and add an intent-bearing fixture that still yields an empty bucket.
- `tests/cli/test_completeness_cmd.py` `test_run_deterministic_checks_collects_concept_findings` — the source list gains `intent-presence`, and `smell_recs` becomes empty (its only member had been the intent advisories).
- `tests/cli/test_completeness_cmd.py` `_CORPUS_BUCKET_COUNTS` and `_CORPUS_DIGESTS` — every fixture moves two findings from `smell_recs` to `self_consistency_recs`, so all seven digests re-pin. Take the digests from the failing assertion's own output (it prints the full rendering); do not hand-compute them. Update the comment above the counts map, which currently says every fixture "gains the same two `intent-presence` smells".

New cases:

- `test_intent_presence_reaches_the_blocking_bucket_from_both_paths` (`tests/test_review.py`) — the `--iterate` collector and the finalize partition return the same intent recs in the same order for a plan with no intent.
- `test_plan_with_intent_yields_no_self_consistency_findings` (`tests/test_review.py`) — the positive control: a plan and steps carrying real intents produce an empty bucket.
- `test_intent_finding_ids_are_unchanged_by_the_promotion` (`tests/test_review.py`) — the two rec ids are the exact strings the fan-out map pins, so a saved sidecar does not treat the promoted finding as new.
- `test_blocking_self_consistency_next_step_is_not_called_advisory` (`tests/cli/test_completeness_cmd.py`) — a report whose only finding is a `medium` intent rec does not print the "advisory (info/nit)" line and names the manual one-line fix.
- `test_blocking_self_consistency_next_step_names_no_apply_verb_at_jira_grade` (`tests/cli/test_completeness_cmd.py`) — under `--grade jira` the bullet says fix by hand and names no verb.
- `test_non_intent_self_consistency_next_step_says_manual_edit` (`tests/cli/test_completeness_cmd.py`) — an `orphaned-deliverable`-only report also gets the manual-edit bullet.

Cases that must stay green **untouched** — they are the guard on what this step must not change:

- `TestCheckIntentPresence::test_cap_holds_as_step_count_grows`, `test_finding_text_is_identical_whatever_the_non_value_was`, `test_finding_never_carries_a_forged_heading`, `test_is_apply_eligible_and_is_structural_are_false`, and every presence case (`test_empty_string_intent_counts_as_missing`, the placeholder parametrization, `test_long_or_vague_intent_yields_nothing`).
- `test_intent_presence_reaches_the_smell_battery` — the detector stays in the smell fan-out.
- `TestCollectSelfConsistencyFindings::test_parity_with_deterministic_checks_battery` and `test_collect_self_consistency_findings_parity_preserved`.
- `test_suppression_routes_to_self_consistency_not_smells`, `test_orphaned_deliverable_lands_on_self_consistency_recs`, and `test_claim_vs_delivery_lands_on_smell_recs`.

**Green-before-done gate.** Every case above must be green, and — because this promotion reaches the `--iterate` loop, the `--json` gate, and the report tail — the **full** suite must be green too (`uv run pytest tests/ -q`), not just the two declared test files. `tests/test_cli.py`'s `TestIterate` self-consistency cases assert the manual-fix message and `rc == 1`, both of which the promotion only reinforces; if any assertion outside the four declared files does flip, add that file to the step and say so in the commit rather than weakening the assertion.

## Acceptance criteria

- `check_intent_presence` returns findings with `severity == "medium"` for a plan and steps declaring no intent, and still returns at most two findings whatever the step count.
- `INTENT_PRESENCE_SOURCE in SELF_CONSISTENCY_SOURCES` is `True`; membership in `APPLY_ELIGIBLE_SOURCES`, `STRUCTURAL_SOURCES`, and `AUDIT_FIX_SOURCES` is `False`.
- `SELF_CONSISTENCY_SMELL_DETECTORS.keys == ("suppression-shape", "concept-coverage", "intent-presence")` — and `plan_tool/review.py` contains no hand-written second list of self-consistency detector keys.
- `_run_deterministic_checks` over a plan with no intent puts the two intent recs in `self_consistency_recs` and none in `smell_recs`.
- `collect_smell_findings` over the same plan still returns the two intent recs (the detector stays in the fan-out).
- `_completeness_has_blocking_findings(self_consistency_recs=[<medium intent rec>], …)` returns `True`; the same call with an `info` rec returns `False`.
- `completeness-audit --json` on a plan with no intent reports `has_blocking_findings: true` and lists the two recs under `checks.self_consistency`.
- `completeness-audit` on that plan exits 0; the same command with `--fail-on-findings` exits 1.
- The two rec ids produced by `check_intent_presence` are the same strings pinned in `tests/test_review.py`'s fan-out characterization map.
- `triage_reason` for an intent finding contains no form of the word "advisory" and names a remedy.
- The `### Suggested next steps` block of a report whose only finding is a `medium` intent rec does not contain "advisory (info/nit)" and names the one-line manual fix; under `--grade jira` it names no apply verb.
- The finding names the plan and the exact step ids lacking an intent, so the one-line fix needs no further diagnosis.
- `rg 'intent' plan_tool/review.py plan_tool/cli/completeness_phases.py` shows no comment or docstring still describing the intent finding as advisory or as riding `smell_recs`.
- **Read the comment on `SELF_CONSISTENCY_SOURCES` directly** — it contains no occurrence of "intent", so the grep above cannot reach it. Its "not auto-appliable … the fix is a manual plan edit" claim must no longer read as true of every member.
- `uv run pytest tests/ -q` is green.

## Applicable guardrails

- **The plan's "## Out of scope", validation-past-presence refusal.** This step changes only *whether* an absent value stops the loop. It must add no quality judgment, no comparison against `## Why` / the plan body / detail / acceptance criteria, no length cap, and no shape rule. A finding proposing one against this step is invalid, not deferrable.
- **The plan's "## Out of scope", no migration or backfill.** Do not sweep the existing plans to add intents, and do not add a grandfather clause, allowlist, or age check that exempts them. They start blocking; a one-line `intent:` added by hand is the remedy.
- **The plan's Architecture, roll-up shape survives the promotion.** The finding count stays per plan, never per step. This binds the severity edit directly — the temptation on promotion is to make a blocking finding more precise by fanning it out.
- **The exit-code convention** (`CLAUDE.md`, and the plan's Overview restating it for this step). Blocking here means blocking *convergence* and the `--json` flag. Do not change any subcommand's exit code; only `--fail-on-findings` flips the rc, through the gate that already exists.
- **The plan's "## Out of scope", no new `--jobs` or parallel surfaces.** Nothing in this step needs one.
- **`CLAUDE.md`'s rule that a tool's `Next steps:` block names only `plan-tool` commands.** The next-steps bullet this step adds ships to operators; it must not name a Claude Code session activity.

## Deferred

- **`plan_tool/cli/completeness_cmd.py:_sc_manual_fix_note`'s wording** — it tells the operator every blocking self-consistency finding "require[s] a manual plan edit (not auto-appliable)". That stays true for the intent finding too, so no change is needed — recorded here because an earlier decomposition wired a walk remedy that would have falsified it, and that arm was carved out 2026-08-03.
- **`plan_tool/cli/inspect.py`'s `plan-tool validate` listing** — it keeps printing the intent finding under "smells (advisory):" at `MEDIUM`. Left as is: `validate` has no gate, and `suppression-shape` has printed there at `medium` since it was elevated. No change needed.
- **`docs/AUDIT_FLOW.md`** — the audit flow's gate documentation should record that a missing intent now blocks. Step 7 owns that file; leave it for step 7.
- **`RUNBOOK.md`'s self-consistency walkthrough** — it names `concept-coverage` as the blocking example and is in neither this step's nor step 7's file list. File a `BACKLOG.md` entry.
- **Backfilling intents into the plans already on disk** — the plan's "## Out of scope" rules it out; a hand edit per plan is the path.
- **BACKLOG #109 (threading one plan footprint across the two self-consistency detectors)** — an unrelated over-work item that happens to touch this bucket. Do not fold it in.
