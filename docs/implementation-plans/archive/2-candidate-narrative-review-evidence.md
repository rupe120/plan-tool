> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
format_version: 1
title: Candidate Narrative Review Evidence
intent: Before approval, a candidate reviewer sees unresolved narrative defects, meaning
  live prose that names a design row the candidate removed, computed from that candidate.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/candidate-narrative-review-evidence.md
steps:
- id: 1
  title: 'Settle the narrative review-evidence contract in ROADMAP_FORMAT.md: the
    closed defect classes (each with definition, producer, consumers, and exit path);
    the structural marker that sets off historical and rejected-alternative context;
    the source of the removed ids; which deterministic defects block approval and,
    for each blocking class, the operator exit (the IPPT-18 correction operation or
    the structural historical marker; an ambiguous reference is a non-blocking evidence
    item, never a blocking defect; pruning a carried removal record is a deliberate
    reviewer bypass, not a listed exit); and that evidence is computed from the candidate
    each time it is needed, never stored, stamped, or regenerated'
  intent: Fixes the vocabulary, the blocking decision with its exits, and the compute-from-the-candidate
    rule before any code or surface depends on them, and is where work stops and goes
    to the user if blocking policy cannot be kept separate from meaning-level judgment.
  files:
  - ROADMAP_FORMAT.md
  complexity: high
  change_type: non-code
  detail: docs/implementation-plans/plan-details/candidate-narrative-review-evidence/01-settle-narrative-review-evidence.md
  status: done
- id: 2
  title: Add a deterministic check in roadmap_gates.py that finds live-prose references
    to ids in the candidate artifact's own carried removals (the predecessor's carried
    records, minus any the reviewer pruned in the candidate, plus any it adds; a feedback-free
    candidate carries none and is checked against its predecessor's removals) outside
    the structurally marked historical and rejected-alternative context (a removed
    id that is also a present row is reported as a distinct ambiguous-reference kind,
    never blocking), kept out of the run_*_gates stage tuples so no existing gate
    behavior changes, and pin it on the Integration Decisions paragraph by reusing the fixture
    IPPT-18 checks in at tests/fixtures/roadmap/integration-decisions-paragraph.md, which
    requires IPPT-18 to have landed and checked that fixture in, else work stops and
    goes to the user
  intent: Delivers the plan's one machine-checked fact, a removed design row still
    named in live prose, with exact artifact, row id, and span, and pins it on the
    real Integration case.
  files:
  - plan_tool/roadmap_gates.py
  - tests/test_roadmap_gates.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the defect class name and the structural marker for historical and rejected-alternative
      context
  detail: docs/implementation-plans/plan-details/candidate-narrative-review-evidence/02-deterministic-check-roadmap-gates-py.md
  status: done
- id: 3
  title: 'Add a pure function that computes a candidate''s narrative evidence from
    the candidate and its predecessor artifact, both supplied by the caller, with
    no model call, no storage, and no loading inside the function (an unreadable predecessor
    surfaces as the error the existing paths raise, never as an empty evidence list;
    a batch candidate is evaluated member by member, each with its own predecessor):
    the removed-id findings from step 2, each naming its artifact, row or span, defect
    class, and correction path, with the ambiguous reference as a non-blocking evidence
    item, and one adapter from stored candidate content so a stored candidate and
    its in-memory form yield identical evidence, shared by the approval paths and
    the CLI'
  intent: Makes the evidence bound to the candidate by construction, since it is recomputed
    from the candidate whenever it is needed, so a candidate change can never leave
    stale evidence and a legacy candidate with no stored evidence works the same way.
  creates:
  - plan_tool/roadmap_candidate_narrative.py
  - tests/test_roadmap_candidate_narrative.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: the deterministic removed-id finding function and its ambiguous kind
  detail: docs/implementation-plans/plan-details/candidate-narrative-review-evidence/03-pure-function-that-computes-candidate.md
  status: done
- id: 4
  title: Make the approval paths (seal_review and decide_structural_candidate approve)
    recompute the narrative evidence from the candidate and refuse only the deterministic
    defects step 1 selected as blocking, naming each defect and its operator exit
    in the refusal; non-blocking evidence is never a refusal, a candidate created
    before this ships is checked the same way, and existing create-only seal publishing,
    the answer path's sealing, and refusal and recovery behavior otherwise stay unchanged
  intent: Approval cannot pass a live reference to a removed row that step 1 made
    blocking, whatever the candidate's age or edit history, and the reviewer sees
    the defect and its exit in the refusal itself.
  files:
  - plan_tool/roadmap_candidate_review.py
  - tests/test_roadmap_candidate_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: the computed evidence and its blocking and non-blocking split
  detail: docs/implementation-plans/plan-details/candidate-narrative-review-evidence/04-make-approval-paths-seal-review-decide.md
  status: done
- id: 5
  title: Show the computed narrative evidence on the roadmap candidate CLI surfaces
    before approval (exact artifact, row or span, defect, and correction path), and
    regenerate docs/cli/roadmap.md
  intent: The reviewer sees the unresolved defects before approving, which is the
    plan's outcome.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  - docs/cli/roadmap.md
  complexity: medium
  change_type: feature
  depends_on:
  - 4
  depends_on_notes:
    4: the approval-time evidence the CLI presents
  detail: docs/implementation-plans/plan-details/candidate-narrative-review-evidence/05-show-computed-narrative-evidence-on.md
  status: done
- id: 6
  title: Update ROADMAP_FORMAT.md and docs/ARCHITECTURE.md with the shipped evidence,
    check, and approval symbols, and remove the IPPT-19 promotion stub from BUG_BACKLOG.md
  intent: Brings the format reference and module map in line with what shipped, and
    closes the backlog record once the full effort lands.
  files:
  - ROADMAP_FORMAT.md
  - docs/ARCHITECTURE.md
  - BUG_BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 5
  depends_on_notes:
    5: the finished, user-visible surface that the docs describe
  detail: docs/implementation-plans/plan-details/candidate-narrative-review-evidence/06-update-roadmap-format-md-docs.md
  status: done
---
# Candidate Narrative Review Evidence

## Overview

This plan makes a candidate review show a reviewer, before approval, the unresolved narrative defects in a candidate, computed from that specific candidate. It adds one deterministic check: whether live prose refers to a design row that the candidate or its accepted lineage removed. This effort supplies evidence only. It does not build the prose-correction remedy (IPPT-18), does not run any model-judged review, and does not change feedback eligibility, authority limits, or refusal and recovery behavior beyond refusing the deterministic defects step 1 selects as blocking. The meaning-level review (pending versus settled, current versus historical) is carved out to BACKLOG #435, and checking the stated basis of a reconciliation response is carved out to BACKLOG #437.

## Problem statement

Candidate review can present prose reconciliation as handled while contradictions remain (BUG_BACKLOG entry, promoted to IPPT-19 on 2026-10-01). Today's gates in `plan_tool/roadmap_gates.py` check typed-row validity and identifier-presence coverage. They do not resolve prose references: `check_inventory_has_prose` only checks that inventoried rows are named. Live prose can therefore keep naming a design row that the candidate or its accepted lineage removed, and the reviewer approves without seeing it. The Integration case shows the symptom: the Decisions paragraph of integration-aidlc-mvp's `01-domain.md` contains a removed-decision reference and a contradiction between pending and settled decisions.

## Architecture

- **Binary observable (the only machine-checked fact):** a live prose block names an id that the candidate or its accepted lineage removed. Removed ids are the `removed_id` records on the candidate artifact's own `artifact.removals`: the predecessor's carried records, minus any the reviewer pruned in the candidate, plus any the candidate adds. A feedback-free candidate carries none of its own and is checked against its predecessor's records. Each artifact's live prose is checked against that artifact's own removal set, and a batch candidate is checked member by member, each with its own predecessor. A record the reviewer pruned in the candidate is deliberately no longer checked; pruning is a deliberate bypass, not a listed operator exit, so refusals name only the correction operation and the historical marker. A reference inside a retained historical or rejected-alternative context, marked structurally, does not count. An id that was never a row is not this observable: today's gates do not resolve prose references (`check_inventory_has_prose` only checks that inventoried rows are named), and this effort adds no such check.
- **Evidence is computed, not stored:** the narrative evidence is a pure function of the candidate. It is recomputed whenever the review surface or an approval path needs it, so it is bound to the candidate by construction. There is no stored evidence record, no identity stamp, no staleness, and no regeneration. A candidate created before this ships gets the same evidence.
- **Deterministic defects and evidence items:** which deterministic defects block approval is decided in step 1, with an operator exit for each blocking class (the IPPT-18 correction operation or the structural historical marker). An ambiguous reference is a non-blocking evidence item shown to the reviewer.
- **Approval:** the approval paths recompute the deterministic check from the candidate and refuse only the blocking defects, naming the defect and its exit. The answer path seals through the same approval check. Everything else about approval, seal publishing, and recovery is unchanged.
- **Closed vocabulary first:** the defect classes are a closed vocabulary. The first step defines each value's definition, producer, consumers, and, for any state an operator can land in, its exit path, before any surface depends on them.
- **Ordering with IPPT-18:** this effort lands after the prose-correction plan (IPPT-18), which edits the same candidate modules, prompt, and `ROADMAP_FORMAT.md` and checks in the shared Integration fixture.
- **Surfaces:** candidate diagnostics and review surfaces (`roadmap_gates.py`, the candidate review module `plan_tool/roadmap_candidate_review.py`, and the CLI) show the exact artifact, row or span, defect, and correction path. This evidence sits beside the existing typed-row validity and identifier-presence gates. No other gate behavior changes.

## Scope guardrails

This effort does not:

- silently rewrite prose, automatically close feedback, require every
  feedback item to change a typed row, or run an unbounded semantic audit loop;
- build the remedy itself, the prose-correction operation (IPPT-18); this
  effort supplies evidence only;
- run any model-judged narrative review, store evidence, or record reviewer
  dispositions; that meaning-level half is carved out to BACKLOG #435;
- change feedback eligibility, existing authority limits, or refusal/recovery
  behavior beyond refusing the deterministic defects step 1 selects as blocking.

**Not allowed (deliberately not checked), each with its reason:**

- A semantic gate on "pending versus settled" or any other meaning judgment:
  the property is unobservable, and a proxy would measure vocabulary (a high
  false-positive rate means kill, not tune).
- An exit-code flip or refusal-to-advance keyed on a semantic finding; no
  semantic finding exists in this effort.
- Keyword matching as the deciding rule for consistency.
- Quality, length, or agreement checks between two prose artifacts.

## References

- [CommonMark Spec 0.31.2: Fenced code blocks](https://spec.commonmark.org/0.31.2/#fenced-code-blocks) — The exact rules for opening and closing fences, so the removed-id check can skip references inside fenced or quoted spans and find prose spans precisely.
- [pytest: How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — For writing one parametrized test over the Testing cases: the Integration fixture, historical and rejected-alternative references, ambiguous references, and approval refusal.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Silently rewriting prose, automatically closing feedback, requiring every
  feedback item to change a typed row, or an unbounded semantic audit loop.
- The remedy itself: the prose-correction operation (IPPT-18).
- The model-judged narrative review, the stored and identity-stamped evidence
  record, reviewer dispositions, and the semantic-review-unavailable state:
  carved out to BACKLOG #435.
- Letting a reconciliation response state its basis and checking that basis
  (the response field, the prompt change, and the missing-basis and
  unresolvable-citation notes): carved out to BACKLOG #437.
- Changing feedback eligibility, existing authority limits, or refusal/recovery
  behavior beyond the blocking defects step 1 selects.

## Risks

IPPT-18 must have landed, with its Integration fixture checked in, before any step of this plan runs: both plans edit the candidate review module, the CLI, and `ROADMAP_FORMAT.md`, and step 1 names IPPT-18's correction operation as an operator exit. If it has not landed, execution stops and goes to the user.

A blocking removed-id defect with no reachable operator exit would become a permanent refusal. Step 1 defines the exit for each blocking class, and an ambiguous reference stays non-blocking.

The Integration pending-versus-settled contradiction is a meaning-level defect and is not surfaced by this effort. A reviewer still sees the removed-decision reference, which is the deterministic half of the Integration case.

## Testing

- Pin the Integration case: a removed-decision reference surfaced as a deterministic finding. The fixture is the Decisions paragraph of integration-aidlc-mvp's `01-domain.md` (1,288 bytes), reused from the fixture IPPT-18 checks in at `tests/fixtures/roadmap/integration-decisions-paragraph.md`.
- A feedback-free candidate is checked against its predecessor's removals, and a pruned removal record is no longer checked.
- A batch candidate is checked member by member: a removed id in one member's removals is checked against that member's prose, using that member's predecessor.
- Historical references and rejected alternatives (structurally marked) are not findings; ambiguous references are non-blocking evidence items.
- Approval recomputes the check: a candidate with a live blocking removed-id reference is refused with the defect and its exit, including a candidate created before this ships and one edited after review; a candidate with only non-blocking items approves.
- The review surface shows the evidence before approval; the answer path's seal goes through the same check.
- A blocking removed-id defect has a defined operator exit.

## Acceptance criteria

- The Testing cases pass, feedback eligibility and authority limits are
  unchanged, and the Not-allowed list holds.
- No stored evidence record, identity stamp, disposition, or model call exists in this effort.
- The IPPT-19 promotion stub is removed from `BUG_BACKLOG.md`.

## Deferred

The meaning-level narrative review (current assertions versus history, pending versus settled), its stored and identity-stamped evidence, and reviewer dispositions: carved to BACKLOG #435. The reconciliation-response basis and its checks: carved to BACKLOG #437. The prose-correction operation (IPPT-18).
