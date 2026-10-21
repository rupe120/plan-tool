> **Replaced**: this file has been superseded by `docs/implementation-plans/2-candidate-narrative-review-evidence.md`.
> Preserved here for history; do not edit.

## Overview

This plan makes a candidate review show a reviewer, before approval, the unresolved narrative defects in a candidate and the evidence behind each claimed reconciliation outcome, all tied to that specific candidate. It adds one deterministic check: whether live prose refers to a design row that the candidate or its accepted lineage removed. It also requires each reconciliation response to name its corrective operations or give a no-change justification that can be checked. A bounded semantic review is added too, and its uncertain findings go to an explicit reviewer disposition instead of a gate. This effort supplies evidence and dispositions only. It does not build the prose-correction remedy (IPPT-18), and it does not change feedback eligibility, authority limits, or refusal/recovery behavior.

## Problem statement

Candidate review can present prose reconciliation as handled while contradictions remain (BUG_BACKLOG entry, promoted to IPPT-19 on 2026-10-01). Today's gates in `plan_tool/roadmap_gates.py` check typed-row validity and identifier-presence coverage. They do not resolve prose references: `check_inventory_has_prose` only checks that inventoried rows are named. Live prose can therefore keep naming a design row that the candidate or its accepted lineage removed, and a reconciliation response can claim completion without saying which corrective operations it made or why no change was needed. The reviewer approves without seeing these defects or the evidence behind each claimed outcome. The Integration case shows the symptom: the Decisions paragraph of integration-aidlc-mvp's `01-domain.md` contains a removed-decision reference and a contradiction between pending and settled decisions.

## Architecture

- **Binary observable (the only machine-checked fact):** a live prose block names an id that the candidate or its accepted lineage removed. Removed ids are the `removed_id` records on `artifact.removals`, read through the predecessor chain. A reference inside a retained historical or rejected-alternative context does not count. An id that was never a row is not this observable. Today's gates do not resolve prose references (`check_inventory_has_prose` only checks that inventoried rows are named), and this effort adds no such check. Everything past this observable is delivered to the reviewer, not verified.
- **Two separate finding classes:** deterministic defects and semantic findings stay distinct. A deterministic defect may block approval if the plan decides it should. Which deterministic defects block approval is a decision `create` makes the first step's deliverable. The semantic class never blocks. It requires a reviewer disposition.
- **Reconciliation-response requirement:** a reconciliation response either names its corrective operations or gives a no-change justification that can be checked against the relevant source spans and settled rows.
- **Bounded semantic review:** this review separates current assertions from history and from rejected alternatives. Uncertain findings reach an explicit reviewer disposition. The review is bounded and is never an unbounded audit loop.
- **Candidate-bound evidence:** review evidence names the candidate identity it was produced for. Any change to the candidate invalidates the evidence and triggers a fresh review. The mechanism is an identity stamp on the evidence, which the approval path checks before accepting it. The owning destination is candidate review, and the stamp lands before any surface presents the evidence.
- **Closed vocabularies first:** the defect classes, the reconciliation-response outcomes, and the reviewer disposition values are closed vocabularies. The first step defines each value's definition, producer, consumers, and, for any state an operator can land in, its exit path, before any surface depends on them.
- **Surfaces:** candidate diagnostics and review surfaces (`roadmap_gates.py`, the candidate run/review modules `plan_tool/roadmap_candidate_run.py`, `plan_tool/roadmap_candidate_review.py`, `plan_tool/roadmap_compare_run.py`, and prompts) show the exact artifact, row/span, defect, and correction path. This evidence sits beside the existing typed-row validity and identifier-presence gates. No other gate behavior changes.

## Out of scope

- Silently rewriting prose, automatically closing feedback, requiring every
  feedback item to change a typed row, or an unbounded semantic audit loop.
- The remedy itself: the prose-correction operation (IPPT-18). This effort
  supplies evidence and dispositions only.
- Changing feedback eligibility, existing authority limits, or refusal/recovery
  behavior.

## Risks

Drift of the semantic half toward a gate. The Not-allowed list is the fence; a
finding proposing a semantic gate is invalid, not deferrable.

## Testing

- Pin the Integration case: a removed-decision reference, and a pending-versus-settled
  contradiction surfaced as a semantic finding rather than a block. The fixture
  is the Decisions paragraph of integration-aidlc-mvp's `01-domain.md` (1,288 bytes),
  checked in as a test fixture; the remedy effort (IPPT-18) uses the same text.
- Valid no-change reconciliation, historical references, rejected alternatives,
  ambiguous references, and unsupported claims of completion.
- Diagnostics expose unresolved findings before approval; a correction triggers
  fresh review.

## Acceptance criteria

- The Testing cases pass, feedback eligibility and authority limits are
  unchanged, and the Not-allowed list holds.
- The IPPT-19 promotion stub is removed from `BUG_BACKLOG.md`.

## Deferred

The prose-correction operation (separate seed).

## Scope guardrails

This effort does not:

- silently rewrite prose, automatically close feedback, require every
  feedback item to change a typed row, or run an unbounded semantic audit loop;
- build the remedy itself, the prose-correction operation (IPPT-18); this
  effort supplies evidence and dispositions only;
- change feedback eligibility, existing authority limits, or refusal/recovery
  behavior.

**Not allowed (deliberately not checked), each with its reason:**

- A semantic gate on "pending versus settled" or any other meaning judgment:
  the property is unobservable, and a proxy would measure vocabulary (a high
  false-positive rate means kill, not tune).
- An exit-code flip or refusal-to-advance keyed on a semantic finding; an
  uncertain finding reaches an explicit reviewer disposition only.
- Keyword matching as the deciding rule for consistency.
- Quality, length, or agreement checks between two prose artifacts.
