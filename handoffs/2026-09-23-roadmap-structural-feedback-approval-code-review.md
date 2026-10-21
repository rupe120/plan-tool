# Roadmap structural feedback approval — post-run review ledger

> **2026-09-24:** the interim refusal of a `--propose-candidate` batch under a structural candidate (`ae3fb0bc`) was superseded by `roadmap-stack-aware-approval`. Passes 2–4 below record that refusal as it stood.

## Summary

| Field | Value |
| --- | --- |
| Plan | `roadmap-structural-feedback-approval` (`docs/implementation-plans/2-roadmap-structural-feedback-approval.md`), 7 steps (6 code, step 7 non-code), all green |
| Branch | `codex/roadmap-structural-approval-handoff` (base `main` at `30484873`, PR #18 merged) |
| Run head (all steps green) | `471aa057` |
| Checks run | Detail-grounded `completeness-audit --iterate` clean at 7/7 detail coverage (`20260923-220408-completeness.md`); three complete `reconcile-code --all` sweeps over the six code steps (commits `6fa71bfa`, `e15ac3e1`, `d1d2921a`); final full suite green at `75664e74` (13,730 passed, 190 skipped; log `.tmp/roadmap-structural-approval-review.p4-fixes.pytest.log`) |
| `/code-review` | Pass 1 (`high`, `eb68ba19..d1d2921a`): 8 findings (7 reviewed, P1.8 found during P1.1 class enumeration), 2 high. Pass 2 (`high`, `d1d2921a..65802426`): 3 findings, 1 high. Pass 3 (`high`, `65802426..4561ff6e`): logic and coverage clean, 4 low documentation findings. Pass 4 (`high`, `65802426..b3685c47`): no correctness defect after 51,000 executed transitions, 1 medium coverage and 2 low documentation findings. All findings dispositioned. |
| Current disposition | Closed by owner decision (2026-09-24), not by the two-consecutive-pass stopping rule: the strict count against the latest logic commit `ae3fb0bc` is one (pass 3), because pass 4 returned a medium finding. See § "Convergence status". The stack direction shipped as `roadmap-stack-aware-approval`; wider run-log coverage stays open (§ "Open owner directions"). |

## Settled decisions (hand these to every reviewer)

From the plan, BACKLOG #423's closure, and the revision-approval handoff. A finding that proposes the opposite is
invalid, not deferrable.

- **One intake, no user-chosen type.** Validated typed operations select the presentation-only or structural route.
- **Approval binds the top candidate and covers its whole stack.** `approve` is two invocations: the first prints
  every unpromoted hop, the cumulative diff, and a digest and writes nothing; the second, with
  `--confirm-stack-digest`, seals the top candidate only when the recomputed digest matches. `edit` creates an
  unsealed replacement; `reject` releases the active candidate and drops every unpromoted hop; promotion alone
  advances `AcceptedRoadmapHead`.
- **Reuse, do not duplicate** the candidate store, review seal, promotion writer, publication journal,
  checkpoint/recovery, feedback-state and seed-invalidation owners. No second chain, store, head writer, or
  transaction system.
- **Fence.** No workflow authoring, automatic approval, feedback grouping, multi-user approval, or general
  transaction system. Selector-shaped escalation, settlement, analysis, and exact-pair rewrite routes stay outside
  ordinary proposal approval; structural operations outside current stage authority stay deferred.
- **Legacy batch evidence.** Route-less evidence written before this plan is readable and ineligible for every
  structural decision; checks key on a stored STRUCTURAL route, never on absence.
- **Answered chain.** `--review-candidate` / `--answer-question` / `--promote-review-seal` is the nonstructural
  route; a candidate whose stack carries a structural hop is refused there and named `--decide-candidate`
  (`bf3c7fda`); a replacement whose own computed classification is structural is refused before storage
  (`41a1ae44`). Rejection stays available on both routes. Answered replacements stored before this plan keep
  their pre-plan behavior (live legacy contract).
- **Stacks are allowed and approved as a whole.** A `--propose-candidate` batch takes the active candidate as its
  source. A stack is structural iff any hop above the recorded root stores a STRUCTURAL route (derived at use, no
  persisted field; a hop with no stored route contributes nothing). Every guard asks that one derivation.
  Structural content reaches the head, or changes enrolled seed state, only through a confirmed structural
  approval of the whole unpromoted stack (`roadmap-stack-aware-approval`, 2026-09-24).
- **Run-log coverage.** Every model-calling candidate lifecycle command writes a run-log lifecycle under its own
  phase and mode (propose, question, replacement, and — since `85177a89` — structural edit); reviewer prose stays
  out of the log (owner direction, 2026-09-24). Decision commands are not covered; see § "Open owner directions".
- **Deliberately not** a semantic or quality check on candidate content, a second structural gate on the answered
  route, or a check needing a new persisted field without a consumer the finding breaks.
- **Documentation-only corrections** are tested for accuracy but do not reset the logic-convergence window.
- **Project rule edits** need architect-tier review in the PR; this loop does not edit rules.

## Findings

Ids: P1.x pass 1 (`eb68ba19..d1d2921a`), P2.x pass 2, P3.x pass 3, P4.x pass 4. Each pass was an independent
headless `high` review.

### Pass 1

- **P1.1 — Answered route promotes a structural candidate** (high, correctness): only `--decide-candidate`
  consulted the stored route, so the answered chain advanced the head with no decision or seed invalidation.
  **Disposition:** fixed `bf3c7fda` — guards at `generate_candidate_question`, the shared admitted-initial loader,
  and the answered-seal branch of `_load_complete_sealed_candidate`; `reject_candidate_review` deliberately
  unguarded; tests in `tests/test_roadmap_candidate_review.py`, `tests/test_roadmap_version_promotion.py`.
- **P1.2 — Structural edit refusal and failure branches unpinned** (medium, coverage): deleting the
  non-structural-replacement check stayed green. **Disposition:** fixed `03bc3f49` — tests only, mutation-verified;
  the expansion-request branch is unreachable (`allow_expansion=False` raises first) and deliberately not pinned.
- **P1.3 — Prior candidate's lost eligibility unpinned on the decision surface** (medium, coverage).
  **Disposition:** fixed `03bc3f49` — tests only; the claim is partly refuted (the publication recheck
  `_require_active_structural_candidate` also refuses unsealed superseded candidates), but the loader is the sole
  guard for a sealed-then-superseded candidate (`approved-then-superseded-by-edit` cell). The edit-path loader
  mutant is equivalent by design.
- **P1.4 — Legacy route-less evidence pinned as ineligible for approve only** (low, coverage). **Disposition:**
  fixed `03bc3f49` (library) and `3722f7a6` (CLI) — tests only, mutation-verified.
- **P1.5 — CLI prints the full approval disclosure before eligibility is checked** (low, correctness).
  **Disposition:** fixed `3722f7a6` — the handler compares the id with `admission.candidate_version_id` before
  rendering; the library still re-checks, so the CLI check is presentation only. Deliberately not a new public
  eligibility function.
- **P1.6 — Structural edit has no run-log lifecycle and requires an argument it discards** (low, coverage /
  consistency). **Disposition:** fixed `85177a89` — declined at first (no criterion required a trail), reversed by
  the owner 2026-09-24 (comprehensive log coverage); phase `roadmap-candidate-structural-edit`, mode
  `candidate-structural-edit`, logged invoker, interrupt and terminal records, rejected reply kept in the
  parse-failure sidecar, reviewer text out of the log; six outcomes tested, mutation-verified.
- **P1.7 — Two claims wider than the code** (low, documentation): the `DATA_CONTRACT.md` retention sentence and the
  `--promote-review-seal` help. **Disposition:** fixed `bf3c7fda` — narrowed, `docs/cli/roadmap.md` regenerated
  (`tests/cli/test_cli_reference.py`).
- **P1.8 — Presentation-only candidate takes a structural replacement through the answered route** (high,
  correctness; class completion of P1.1, found during its enumeration): `_store_batch_replacement` never
  consulted the replacement's computed classification. **Disposition:** fixed `41a1ae44` — refusal reads that
  classification (no persisted field); regression test and mutation verified. Deliberately not: a persisted
  classification on replacements, or a promotion-side re-check of stored answered replacements. The selector-era
  `_store_replacement` stays outside the plan (BACKLOG #429).

### Pass 2

- **P2.1 — Structural content reaches the head as ancestry of a stacked presentation-only candidate** (high,
  correctness): a batch sourced from an active structural C1 classifies presentation-only relative to C1 and the
  answered chain promotes it with C1's changes. **Disposition:** fixed `ae3fb0bc` — reproduced by probe first; the
  batch source in `roadmap_candidate_run.py` (the only producer of a descendant of an active candidate's content)
  refuses when the active candidate's stored route is STRUCTURAL, keyed on the value, after `no eligible work` and
  before the first model call. Owner-flagged reversible call narrowing the prerequisite plan's stacking rule;
  smaller than cumulative classification or a promotion-side ancestor refusal (which strands the chain). Refusal
  later superseded by `roadmap-stack-aware-approval`.
- **P2.2 — Legacy route-less carve-out pinned only on the decision side** (medium, coverage). **Disposition:**
  fixed `ffceb1e8` — test only; mutation executed (entry and promotion guards keyed on absence go red).
- **P2.3 — Retention sentence says prompts are not retained** (low, documentation): the capsule persists the
  model-facing payload. **Disposition:** fixed `19682e8f` — sentence corrected; batch block and answered-route
  refusal stated in `docs/how-to/roadmap.md`, `ROADMAP_FEEDBACK_FORMAT.md`, `docs/ARCHITECTURE.md`.

### Pass 3 (logic and coverage clean against `ae3fb0bc`)

- **P3.1 — Ledger named the review tooling and tier** (low, documentation). **Disposition:** fixed (pass-3
  documentation commit; hash not recorded in the source) — four sites reworded.
- **P3.2 — "No raw model reply is retained" contradicted by the failure sidecar** (low, documentation).
  **Disposition:** fixed (pass-3 documentation commit; hash not recorded) — claim scoped to evidence and seals; the
  sidecar is named.
- **P3.3 — "approve, edit, or reject ends it" misstates edit** (low, documentation): an edit stores another
  structural candidate. **Disposition:** fixed (pass-3 documentation commit; hash not recorded) — approval with
  promotion or rejection ends the block; an edit continues it.
- **P3.4 — Ordering rationale rests on a re-entry return that cannot fire** (low, documentation): the batch receipt
  binds `source`, so the same-receipt return never matches while a candidate is active. **Disposition:** fixed
  (ledger text only); the never-firing branch is tracked as BACKLOG #430 (evidence-gated, may be no action).

### Pass 4 (no correctness defect; 51,000 transitions, 0 violations)

- **P4.1 — States that keep the batch block pinned by no test** (medium, coverage): a guard narrowed to ignore an
  approved-unpromoted or edit-produced structural candidate kept 830 tests green. **Disposition:** fixed
  `68a3749f` — tests only; refusal test parametrized over initial, approved-not-promoted, and edit-produced
  states; each narrowed-guard mutant fails its own cell. The pass-3 triage had wrongly judged this redundant.
- **P4.2 — Seed-state member described as journaled for every promotion** (low, documentation). **Disposition:**
  fixed `75664e74` — `DATA_CONTRACT.md` and `docs/ARCHITECTURE.md` corrected.
- **P4.3 — Route-less batch evidence described as legacy only** (low, documentation): answered-review replacements
  also persist neither field. **Disposition:** fixed `75664e74` — paragraph corrected.

## Reconcile-code sweeps

Three complete `reconcile-code --all` sweeps over the six code steps ran before review (commits `6fa71bfa`,
`e15ac3e1`, `d1d2921a`). The source records no per-sweep finding triage beyond these commits.

## Out-of-range findings

_(none)_ — weighed and dropped: an unreachable `assert` in `_classify_validated_operations`; consolidation
candidates (belong in `BACKLOG.md` with machine-verified evidence); an edit reproducing an existing candidate is
refused as an identity collision (fails closed); pre-plan structural answered replacements and route-less
candidates (settled live legacy contract); a hand-edited stored route (outside the threat model); the same-receipt
return (P3.4, #430); a promotion-generation crash window (interrupted enrolled generations refuse recovery by
design).

## Open owner directions

**Whole-stack presentation and confirmed approval — shipped as `roadmap-stack-aware-approval` (decided
2026-09-24; do not reopen).** The interim batch refusal is gone; a structural approval covers everything built on
the approved candidate. Every approval or confirmation presents the entire unpromoted stack (supersedes the
last-hop-only disclosure weighed in passes 3 and 4). Approve is confirmed in a separate invocation with a
stateless stack digest. There is deliberately no read-only show command: an unconfirmed approve prints the stack
and writes nothing; `--propose-candidate` cannot re-show a candidate because a re-run builds on the active one
(see #430).

One owner direction remains open.

**Wider run-log coverage (owner aim, 2026-09-24; not done).** Only propose, question, replacement, and now
structural edit write run logs. The decision commands that change state — approve, reject, discard, and promote —
write none. Whether and how to log them is undecided.

**Tracked 2026-09-29:** `BACKLOG.md` #434 records the decision and its fence.

## Convergence status

Closed by owner decision, not by the strict stopping rule (see the decision below). Passes 1 and 2 were not clean and needed four
logic-changing commits (`bf3c7fda`, `41a1ae44`, `3722f7a6`, `ae3fb0bc`). Against the newest, `ae3fb0bc`, pass 3
was low-yield (logic and coverage clean, four low documentation findings). Pass 4 found no correctness defect,
and its executed evidence is the strongest yet (51,000 transitions, an oracle independent of the stored route,
guard mutants detected), but it returned one medium coverage finding on the central guard. A medium finding is
not advisory-severity, so under `integrations/shared/DIRECTIVES.md` § "After `run` finishes a plan" and the
severity-aware stopping rule the streak restarts after its fix. The fixes are test-only and documentation-only
and leave the logic head unchanged.

**Owner decision (2026-09-24): stop here and accept convergence.** This deliberately does **not** satisfy the
two-consecutive-clean-or-low-yield-pass rule: the strict count against `ae3fb0bc` is one (pass 3), because pass 4
returned a medium finding. The owner judged the executed evidence sufficient instead of spending passes 5 and 6:
no correctness defect in passes 3 or 4; a randomized state-machine search over the real library functions
(51,000 transitions, an oracle that judges structural change from artifact content and never from the stored
route, guard mutants detected) with 0 violations; the full suite green at `75664e74` (13,730 passed, 190
skipped); and every finding across the four passes dispositioned. Deliberately not done: passes 5 and 6, and any
mutation or crash-window testing beyond what pass 4 executed. The closure did not cover the two owner directions
open at the time, which were follow-on work: the stack direction shipped as `roadmap-stack-aware-approval`, and
wider run-log coverage remains open. That plan's logic commits (steps 1–7) post-date this closure, and this ledger
records no review pass over them. A later logic-changing commit reopens the window,
and a new finding of the recurring class (structural content reaching the head without a decision) should be
treated as a non-converging signal and surfaced rather than patched by another per-route guard; the alternative
recorded for that case is to enforce the property once at promotion by measuring what the promoted version
changes against the accepted head.

Trajectory across the four passes, by identity and severity: the high correctness finding recurred in the same
class twice more (P1.8, P2.1) and did not recur in passes 3 or 4; the non-documentation tail went from three
coverage findings and three low findings (pass 1), to one coverage finding (pass 2), to none (pass 3), to one
coverage finding (pass 4) that pass 3 had explicitly dropped; the documentation tail is the retention and
publication-contract wording, corrected four times, each time narrower.
