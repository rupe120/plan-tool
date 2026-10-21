# Step 2 — Add the removed-id-in-live-prose check to roadmap_gates.py

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds one deterministic check to `plan_tool/roadmap_gates.py`. It finds removed design-row ids that the candidate's live prose still names, and it reports each hit with its artifact, row id and span. The check classifies each hit as `removed-id-in-live-prose` or `removed-id-ambiguous-reference`, using the contract step 1 wrote in `ROADMAP_FORMAT.md`. The check stays out of the `run_*_gates` stage tuples, so no existing gate behavior changes. The check is pinned on the Integration Decisions paragraph fixture that IPPT-18 checks in. Today `tests/fixtures/roadmap/` holds only `integration-scale-domain.md`, so that precondition is unmet. On green, the check returns the findings for a candidate, and step 3 can wrap it in a pure evidence function.

## Table of Contents

- [Why](#why) — what no gate does today
- [Input](#input) — step 1's contract and the fixture precondition
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files
- [Implementation](#implementation) — the check's shape, the removed-id set, marker handling, result type
- [Tests](#tests) — cases and the green gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — fence rules and parametrization
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — what other steps own

## Why

`plan_tool/roadmap_gates.py:check_inventory_has_prose` only confirms that each present row is named in the body. `check_design_row_continuity` requires a removal record for a dropped row. No gate asks whether the live prose still names a row that was removed. The Integration Decisions paragraph shows the symptom: it still refers to a removed decision, and the reviewer cannot see that before approval. This step adds the one machine-checkable fact the plan builds on. Steps 3 to 5 consume it.

## Input

- **Step 1** owns the contract in `ROADMAP_FORMAT.md` § "Narrative review evidence". It fixes:
  - the two class names (`removed-id-in-live-prose`, `removed-id-ambiguous-reference`)
  - the marker spelling, the fence rule, and the unclosed-start and nested-start rules
  - the removed-id source rule
  
  Read the final spelling from that section. The section wins over any spelling in this file.
- **Landed code this step builds on:**
  - `ArtifactEnvelope` carries `artifact_under_check`, `filename_under_check` and `predecessor`.
  - `RemovalRecord.removed_id`.
  - `_prose_names_id` and `_ID_CHARACTER` are the whole-token matcher.
  - `_continuity_rows` lists the design rows present in an artifact.
  - `_fenced_code_spans` is already imported from `plan_tool.scope_fence`. It returns a scan with a `.spans` list, and an unclosed fence runs to end of text.
- **Fixture precondition:** this step needs `tests/fixtures/roadmap/integration-decisions-paragraph.md` from IPPT-18, as the plan's "Ordering with IPPT-18" section requires. If the file is absent when work starts, stop and go to the user. Do not recreate the fixture and do not substitute `tests/fixtures/roadmap/integration-scale-domain.md`.
- **Limit on verification:** the fixture's exact removed id is not known until IPPT-18 lands. Read it from the fixture, not from this file.

## Files (creates vs edits)

- **New files:** none. The fixture is IPPT-18's, and this step only reads it.
- **Existing files (edits only):**
  - `plan_tool/roadmap_gates.py`
    - Add the two kind constants beside the other `VIOLATION_*` constants.
    - Add the result dataclass.
    - Add the check and its private helpers.
  - `tests/test_roadmap_gates.py`
    - Add a test class for the check.

## Implementation

**The behavior that must hold**

- **The check:** one public function, for example `check_removed_ids_in_live_prose(envelope, *, feedback_free=False)`. It returns a list and never raises.
- **Removed-id source:** follow step 1's rule.
  - Default: the `removed_id` of every record in `envelope.artifact_under_check.removals`. That covers records carried forward and records the candidate adds. A pruned record is absent, so it is not checked.
  - With `feedback_free=True`: also include `envelope.predecessor.removals`, when the predecessor is present.
  - Step 3 knows whether a candidate is feedback-free and passes the flag. The check does not guess it.
  - Step 1 asks the implementer to confirm how `materialize_candidate` carries `removals`. If it already carries them, the flag changes nothing. Keep the flag only if that confirmation shows it is needed. Otherwise drop it and note the result in the step's handoff.
- **Scan region:** only `artifact.body`.
  - Frontmatter rows, including decision `alternatives`, are not scanned.
  - A token inside a fenced span is not live prose.
  - Reuse `_fenced_code_spans` for fences. Do not write a second fence scanner.
  - Step 1 cites `jira_grade.fenced_spans`. Before reusing the already-imported scanner, check that both treat tilde fences, CRLF and an unclosed fence the same way. Say in the handoff which one you used.
- **Marker handling:**
  - A marker line counts only when it stands alone on its own line and sits outside a fenced span.
  - Text between a start line and the next end line is excluded.
  - An unclosed start excludes nothing.
  - A start inside an open region does not reopen it.
  - Keep the two marker spellings as module constants. Tests import them, so they are spelled once in code.
  - One way to do this: walk the body line by line, keep a running offset, and build the excluded spans from the marker lines. Then match ids with the existing whole-token rule and drop any match whose offset falls in a fenced or marked span.
- **Classification:** a removed id that is also a present design row in the candidate (per `_continuity_rows`) is reported as `removed-id-ambiguous-reference`. Any other hit is `removed-id-in-live-prose`. The ambiguous kind never blocks. This step does not decide blocking. Steps 3 and 4 key on the kind.
- **Cardinality:** report every occurrence, one finding per occurrence. Each finding carries the exact span so step 5 can display it. A repeated id in two paragraphs produces two findings.
- **Result type:**
  - Use a small frozen dataclass, for example `NarrativeReference`, with `kind`, `artifact` (a filename constant), `row_id`, the span (body character offsets plus a 1-based body line), and a short excerpt of the matched line.
  - Rejected alternative: reuse `Violation`. It has no span field, and widening a frozen type shared by every gate touches all of them.
  - Like `Violation`, the type has no `blocking` field. Blocking is policy owned by steps 1, 3 and 4.
  - The kind constants follow the existing `VIOLATION_*` naming and spelling style.
- **Not wired into stage gates:** do not add the check to `DOMAIN_GATES`, `CONSTRAINTS_GATES`, `COMPONENTS_GATES`, `PLANS_GATES`, or any `run_*_gates` function. Add a test that pins that.
- **Leaf discipline:** add no first-party import beyond those already in the module. The module is not `plan_tool/gates.py`, the shell-command suggester. The check takes no invoker and makes no model call.

## Tests

All tests go in `tests/test_roadmap_gates.py`. Build artifacts by constructing the row dataclasses directly, as the suite's header requires. Only the fixture case reads text from disk.

### Tests for this step

Every one of these must be green before the step is done. The first case is the plan's Integration pin. It needs the IPPT-18 fixture, so it cannot be written until the fixture exists.

- `test_integration_decisions_paragraph_reports_the_removed_decision_reference` — the fixture text as the body, plus a removal record for the id the paragraph names, yields one `removed-id-in-live-prose` finding with the artifact, row id and span.
- `test_removed_id_in_plain_prose_is_reported_with_artifact_id_and_span` — the finding names the filename, the id, and the offsets and line of the match.
- `test_every_occurrence_is_reported_once_each` — two mentions yield two findings.
- `test_whole_token_match_ignores_longer_ids` — a removed `entity-1` is not found in `entity-1-extra`.
- `test_reference_between_history_markers_is_not_reported` — text between the start and end marker lines is excluded.
- `test_reference_after_the_end_marker_is_reported` — the exclusion stops at the end line.
- `test_unclosed_history_start_excludes_nothing` — fails safe: all references are reported.
- `test_nested_history_start_does_not_reopen_the_region` — a second start inside an open region changes nothing, and the first end closes it.
- `test_marker_inside_a_fenced_span_is_quoted_text_not_a_marker` — a fenced marker line excludes nothing.
- `test_reference_inside_a_fenced_span_is_not_live_prose` — a fenced token is not reported.
- `test_marker_must_stand_alone_on_its_line` — a marker string embedded in a sentence is not a marker.
- `test_frontmatter_alternatives_are_not_scanned` — a removed id named only in a decision's `alternatives` produces nothing.
- `test_removed_id_that_is_also_a_present_row_is_ambiguous_not_live` — the kind is `removed-id-ambiguous-reference`.
- `test_removed_ids_are_checked_per_artifact` — an id removed in one artifact's records is checked against that artifact's prose only; the same id in another artifact's prose is not a finding for it (it is ambiguous only when it is a present row).
- `test_pruned_removal_record_is_no_longer_checked` — the predecessor carries a removal, the candidate drops the record, and the check reports nothing. The name states that the bypass is deliberate.
- `test_candidate_added_removal_is_checked` — a record the candidate adds is in the set.
- `test_feedback_free_candidate_is_checked_against_predecessor_removals` — with `feedback_free=True` and no candidate removals, the predecessor's removal ids are checked. Keep this case only if the flag stays (see Implementation).
- `test_default_does_not_read_predecessor_removals` — without the flag, a predecessor-only removal is not checked. This guards the pruned-record rule against the feedback-free arm.
- `test_check_is_not_in_any_stage_gate_tuple` — the function is absent from the four `*_GATES` tuples and from the `run_*_gates` source. This pins the "no existing gate behavior changes" carve-out.
- `test_valid_no_change_reconciliation_reports_nothing` — a candidate whose body names no removed id returns an empty list.

Parametrize the marker and fence variants with `pytest.mark.parametrize`. Verify the carve-out and marker tests by mutation: break the marker exclusion and the fence exclusion in turn, and watch the matching cases go red.

## Acceptance criteria

- The check returns the findings listed above for each input class, and an empty list for a clean candidate.
- Every finding names the artifact filename, the removed id, and a body span.
- A reference inside a marked region or a fenced span is not reported.
- An unclosed start marker excludes nothing.
- A removed id that is also a present row is reported as `removed-id-ambiguous-reference` only.
- A pruned record is not checked.
- No `run_*_gates` function or `*_GATES` tuple references the new check, and the existing gate tests pass unchanged.
- `rg 'invoker|subprocess' plan_tool/roadmap_gates.py` shows no new hit. The module gains no first-party import.
- The IPPT-18 fixture test passes, or the step stops before code and goes to the user.
- `uv run pytest tests/test_roadmap_gates.py -q` is green.

## References

- [CommonMark Spec 0.31.2: Fenced code blocks](https://spec.commonmark.org/0.31.2/#fenced-code-blocks) — read for the opening and closing fence rules that decide which body spans are quoted.
- [pytest: How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — read for the marker, fence and ambiguity case tables.

## Applicable guardrails

- The plan's "## Scope guardrails" bars any model call and any meaning-level judgment here. The check matches whole-token ids against structurally marked spans and never reads the prose for meaning. Keyword matching does not decide anything.
- The plan's "## Scope guardrails" bars any stored evidence. The function reads the candidate and returns a list. It writes nothing.
- The plan's "## Out of scope" leaves feedback eligibility, authority limits and refusal behavior alone. This step adds no refusal. Blocking is applied by steps 3 and 4.
- The plan's "## Scope guardrails" bars a prose check on ids that were never rows. The check looks up only ids from removal records.

## Deferred

- The pure function that gathers the candidate's evidence, and the choice of `feedback_free` — step 3 owns both.
- Approval refusal, the exit text, and the answer-path seal — step 4.
- The CLI and review display of findings — step 5.
- The `ROADMAP_FORMAT.md` contract, including the marker spelling — step 1.
- Meaning-level review of pending versus settled prose — BACKLOG #435.
- Checking the stated basis of a reconciliation response — BACKLOG #437.
- Merging the two fence scanners (`plan_tool/jira_grade.py:fenced_spans` and `plan_tool/scope_fence.py:_fenced_code_spans`) — a cross-module consolidation, so it goes to BACKLOG.md and not into this step.
