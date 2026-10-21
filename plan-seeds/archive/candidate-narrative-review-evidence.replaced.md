> **Replaced**: this file has been superseded by `docs/implementation-plans/2-candidate-narrative-review-evidence.md`.
> Preserved here for history; do not edit.

# Plan seed: candidate review shows unresolved narrative contradictions before approval

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/candidate-narrative-review-evidence.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per
step.

Source: BUG_BACKLOG "Candidate review can present prose reconciliation as handled
while contradictions remain" → promoted to IPPT-19 (2026-10-01). This seed carries that entry's scope
contract; the ticket holds the working brief.

## Outcome

Before approval, a candidate reviewer sees unresolved narrative defects and the
evidence behind each claimed reconciliation outcome, bound to that candidate.

## In scope

- A deterministic check that identifies references, in live prose, to design
  rows removed by the candidate or its accepted lineage, retaining explicit
  historical and rejected-alternative exceptions.
- A requirement that a reconciliation response either identifies its corrective
  operations or gives a checkable no-change justification against the relevant
  source spans and settled rows.
- Candidate diagnostics and review surfaces (`roadmap_gates.py`, candidate
  run/review modules, prompts) showing exact artifact, row/span, defect, and
  correction path.
- A bounded semantic review distinguishing current assertions from history and
  rejected alternatives, whose uncertain findings reach an explicit reviewer
  disposition.
- Review evidence bound to candidate identity and invalidated when the candidate
  changes.

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

## Out of scope

- Silently rewriting prose, automatically closing feedback, requiring every
  feedback item to change a typed row, or an unbounded semantic audit loop.
- The remedy itself: the prose-correction operation (IPPT-18). This effort
  supplies evidence and dispositions only.
- Changing feedback eligibility, existing authority limits, or refusal/recovery
  behavior.

## Allowed behavior changes

Candidate diagnostics and review gain new evidence and disposition surfaces,
and one new deterministic check for the binary observable above.
Which deterministic defects block approval is a decision `create` makes the
first step's deliverable. No other gate behavior changes.

## Allowed reorganization

None.

## Architecture

- **Binary observable:** a live prose block names an id that the candidate or
  its accepted lineage removed (the `removed_id` records on `artifact.removals`,
  read through the predecessor chain), outside a retained historical or
  rejected-alternative context. An id that was never a row is not this
  observable: today's gates do not resolve prose references
  (`check_inventory_has_prose` only checks that inventoried rows are named), and
  this effort adds no such check. This is the only machine-checked fact;
  everything past it is delivered to the reviewer, not verified.
- Deterministic defects and semantic findings are separate classes: the
  deterministic class may block approval by decision; the semantic class never
  blocks and requires a reviewer disposition.
- Review evidence names the candidate identity it was produced for; any
  candidate change invalidates it and triggers fresh review. The mechanism is
  an identity stamp on the evidence checked by the approval path before it
  accepts the evidence; the owning destination is candidate review, and the
  stamp lands before any surface presents the evidence.
- The defect classes, the reconciliation-response outcomes, and the reviewer
  disposition values are closed vocabularies. `create` derives each value's
  definition, producer, consumers, and (for a state an operator can land in) its
  exit path in the first step, before surfaces depend on them.

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

## Stop / defer

Stop and surface to the user if blocking policy cannot be separated from
semantic judgment. File anything else in `BUG_BACKLOG.md` or `BACKLOG.md`, never
as plan expansion.

## References

- `plan_tool/roadmap_gates.py` — existing gates (typed-row validity,
  identifier-presence coverage) this adds evidence beside.
- `plan_tool/roadmap_candidate_run.py`, `plan_tool/roadmap_candidate_review.py`,
  `plan_tool/roadmap_compare_run.py` — candidate run/review and comparison
  surfaces.
- `CLAUDE.md` § "Validating a semantic property you cannot observe" — the rule
  the Not-allowed list applies.
- `ROADMAP_FORMAT.md`, `ROADMAP_FEEDBACK_FORMAT.md`.

## Backlog reconciliation

The `BUG_BACKLOG.md` entry is a promotion stub (IPPT-19). The plan's final step
removes it in the shipping pull request, per `docs/TRACKING.md` § "Promotion
stubs".
