# Step 5 — Update docs and close BACKLOG #121 for the lazy concept-materialization change

## Summary

This is a docs-only closure step: it changes no production code. It updates three surfaces so the written record matches the lazy behavior steps 1–4 shipped. `CLAUDE.md`'s "Concept sign-off and ownership" paragraph is rewritten to describe lazy materialization (a `concepts.json` record only when a plan actually defers something, un-deferred plans get none, proposed deferrals recorded unconfirmed under `-y`, `concept-unsigned-deferral` now surfaced in status and the completeness report). `BACKLOG.md`'s `#121` entry is reconciled from "lazy is the forward direction" to "lazy shipped," flipping future-tense language, fixing the now-stale live-seed reference (the seed was archived by `create`), and confirming `#126`–`#128` residue and `#129` still stand. The seed at `plan-seeds/lazy-deferral-confirmation.md` needs no live edit — `create` already archived it. On green: the docs no longer describe eager enrichment as current, and `#121` reads as delivered with its supersession of the eager-hardening path stated.

## Table of Contents

- [Why](#why) — why the docs now contradict the shipped behavior
- [Input](#input) — the shipped steps and backlog entries this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the two docs edited and the seed left as-is
- [Implementation](#implementation) — what each doc must say after the edit
- [Tests](#tests) — the doc-accuracy and link checks that stand in for unit tests
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes a reviewer can verify
- [References](#references) — the docs and entries this step touches
- [Deferred](#deferred) — what this step does not touch

## Why

Steps 1–4 changed how `create` and `detail` materialize concept decisions, but the project docs still describe the old eager behavior. `CLAUDE.md`'s concept paragraph says "Create records operator-approved owners" and calls `concept-unsigned-deferral` an "advisory reminder" — both now wrong: create no longer eagerly enriches, records deferrals unconfirmed under `-y`, and step 3 gave that finding a visible home in `status` and the completeness report. `BACKLOG.md`'s `#121` frames lazy-deferral as the *forward direction* to build and points at a live seed path that `create` has since archived — a dead reference and a stale tense. The seed itself asked for exactly this closure step: "When this work ships, its final docs/status step must update `BACKLOG.md`." Left unreconciled, the docs read as if the eager machinery is still the current design, which misleads the next agent doing a reconcile or a new plan.

## Input

- **Steps 1–4's shipped behavior** — this step describes, not re-implements, what those steps delivered. Read them by outcome, not mechanism:
  - Step 1 stopped eager enrichment: `create` no longer calls `emit_concept_tree`, which stays defined but dormant for the create path.
  - Step 2 made `create`'s gate deferral-only: an un-deferred plan writes no `concepts.json`; a proposed `defer`/`wont_do` under `-y` is recorded `review_state="unreviewed"`, not signed off.
  - Step 3 surfaced the unreviewed deferral in `plan_tool/cli/inspect.py:_print_status` and `plan_tool/completeness_report.py`, still non-blocking (kept out of `SELF_CONSISTENCY_SOURCES`).
  - Step 4 let `detail` materialize a new deferral at its shared-find routing **pending** (`review_state="unreviewed"`, not signed off), written directly via `save_concepts`, deriving a bootstrap tree when the plan has no record yet — never rendered into `## Deferred` until an operator confirms it via `scope-review`.
- **The archived seed** — `plan-seeds/archive/lazy-deferral-confirmation.replaced.md` carries the reconciliation obligation this step discharges (update `BACKLOG.md`, note supersession of the eager-hardening path, reconcile `#121`). Its live path `plan-seeds/lazy-deferral-confirmation.md` no longer exists.
- **`BACKLOG.md` entries** — `#121` (the entry being reconciled, with its `2026-07-15` "Altitude reframe" note and the seed reference), `#126`/`#127`/`#128` (the eager-hardening residue lazy supersedes for the common flow), and `#129` (decomposition monitoring). Verify each entry's current wording at HEAD before editing — line positions drift.

Verification limit: `CLAUDE.md` and `BACKLOG.md` are not drift-guarded by any test, so accuracy is checked by reading, not by a suite. Cross-check every claim against the shipped code in steps 1–4's files before writing it.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `CLAUDE.md` — rewrite the "Concept sign-off and ownership" paragraph (line 58 today) so it describes lazy materialization. Touch only that paragraph.
  - `BACKLOG.md` — reconcile the `#121` entry: flip future-tense "forward direction / this seed" language to shipped past tense, fix the stale live-seed reference, and state the lazy path's supersession of `#126`–`#128`/`concept-write-integrity` for the common flow. File a new entry only if the absent-record gap below is genuinely untracked.
- **Declared but not edited:**
  - `plan-seeds/lazy-deferral-confirmation.md` — **no live edit.** `create` already archived it to `plan-seeds/archive/lazy-deferral-confirmation.replaced.md` (with a replacement notice) during plan creation. Do not resurrect the live path or edit the archived copy. The reconciliation the seed asked for lands in `BACKLOG.md`, not in the seed. It appears in this step's `files:` from plan-authoring time; note it as a verified no-op.

## Implementation

- **Rewrite CLAUDE.md's concept paragraph to the lazy forward state.** Keep the still-true opening (the `concepts.json` record is the authority; prose is a synchronized rendering; `scope-review` reviews the supplied `--concept` IDs and binds approval to source state; the exact-ID ownership-accounting rule; legacy empty-ownership plans stay parseable; the split/merge/re-ground/scope-out conservation tail). Change the parts steps 1–4 made wrong:
  - **Materialization is lazy.** `create` no longer enriches a full tree up front; it writes a `concepts.json` record only when a plan actually proposes a `defer`/`wont_do` decision. An un-deferred plan gets no record at all.
  - **Unconfirmed under `-y`.** A proposed deferral authored non-interactively is recorded `review_state="unreviewed"` (decision intact), never silently signed off; the operator confirms it later via `scope-review`.
  - **The finding is surfaced, not just advisory.** `concept-unsigned-deferral` now shows in `plan-tool status` and under its own completeness-report heading, while staying non-blocking (only a `scope-review` decision resolves it).
  - **Detail materializes deferrals (pending).** `detail` can turn a concept its shared-find routing proposes deferring into a **pending** `defer` decision (unreviewed) via `save_concepts`, deriving a bootstrap tree if the plan has no record; it is confirmed and rendered later via `scope-review`, never auto-signed under `-y`.
  - **The tree machinery stays dormant, not removed.** `emit_concept_tree` and `Step.concept_ids` remain in place for reuse; lazy changes *when and how much* materializes, not the record format.
  - One way to phrase the create/detail sentence: replace "Create records operator-approved owners, detail persists structured deferrals, …" with wording that says create materializes a record only at a deferral (unconfirmed under `-y`) and detail signs off the deferrals it proposes. Keep it to the paragraph's existing terse density.
- **Reconcile BACKLOG #121 by tense-flip, not deletion.** The entry stays (residue in `#126`–`#128`/`#129` is still open), so this is the tense-flip reconciliation, not a retirement:
  - Flip the `2026-07-15` "Altitude reframe" note's forward-looking language ("The forward direction is `plan-seeds/lazy-deferral-confirmation.md`", "make materialization **lazy**") to shipped past tense, naming the delivering plan `docs/implementation-plans/2-lazy-deferral-confirmation.md` and its steps 1–4.
  - Fix the dead reference: the live seed path `plan-seeds/lazy-deferral-confirmation.md` (line 1931 today) no longer exists — point instead at the shipped plan (and, if a history pointer is wanted, the archived seed under `plan-seeds/archive/`).
  - State plainly that the lazy path delivers `#121`'s original desire (confirm what the tool defers) and **supersedes the eager-machinery hardening path** (`concept-write-integrity` / `#126`–`#128`) for the common flow — the seed's stated obligation.
  - **Cross-check the residue before touching it.** `#126`–`#128` describe hardening the lazy path makes largely moot but does not formally close; confirm none of their retained work was actually shipped by steps 1–4, then leave those entries open. `#129` (decomposition monitoring) is untouched by this plan — verify it still stands and leave it.
- **Confirm the absent-record path is covered (no longer a routed gap).** An earlier draft routed the absent-record detail-materialization path to `BACKLOG.md`; step 4 now **handles** it directly (derives a bootstrap tree when the plan has no `concepts.json`, as `scope_review_cmd.py` does), so there is no open gap to file here. Verify step 4 shipped that derive-on-absent path before writing the docs; if it did not, that is a step-4 defect to route back, not a docs entry.
- **Do not change the seed.** The live seed is gone (archived by `create`); the archived copy is history and carries a "do not edit" notice. Making the reconciliation land in `BACKLOG.md` satisfies the seed's forward-carry rule without touching either path.

Constraints that must hold:
- **Edit only the one CLAUDE.md paragraph.** The surrounding architecture map is accurate; a wider rewrite risks introducing new drift.
- **No new field-shaped rows or headings that a drift guard keys on** — neither file is drift-guarded, but keep additions as prose so this stays true if a guard is added later.
- **Every claim traces to shipped code.** Verify each rewritten sentence against steps 1–4's files at HEAD (`plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/review.py`, `plan_tool/completeness_report.py`, `plan_tool/cli/inspect.py`) before writing it — `depends_on` ordering is not proof the code matches the claim.

## Tests

### Verification (non-code step)

This step changes no production code, so verification is doc-accuracy and reference checks, not unit tests:

- **CLAUDE.md accuracy** — each rewritten sentence matches a shipped behavior: no `emit_concept_tree` on the create path (grep `plan_tool/create.py`), un-deferred plan writes no `concepts.json` (step 2), `-y` records `review_state="unreviewed"` (step 2), `concept-unsigned-deferral` appears in `_print_status` and the completeness report and is out of `SELF_CONSISTENCY_SOURCES` (step 3), detail materializes a **pending** deferral via `save_concepts` (step 4).
- **CLAUDE.md no dead reference** — the paragraph names no removed symbol or behavior as current; the still-true tail (scope-review, ownership accounting, split/merge/reground/scope-out) is unchanged.
- **BACKLOG #121 tense** — no remaining future-tense "forward direction / will ship / this seed" phrasing for the lazy work; the entry reads as delivered.
- **BACKLOG #121 no dead link** — no reference to the live seed path `plan-seeds/lazy-deferral-confirmation.md`; references resolve to `docs/implementation-plans/2-lazy-deferral-confirmation.md` (and the archived seed if cited).
- **Residue intact** — `#126`, `#127`, `#128`, `#129` still exist and their retained-work descriptions are accurate (none silently closed or over-swept).
- **Routed gap resolved** — the absent-record detail-materialization gap is either already tracked or filed as a new `BACKLOG.md` entry.
- **Seed untouched** — `plan-seeds/lazy-deferral-confirmation.md` is not recreated; `plan-seeds/archive/lazy-deferral-confirmation.replaced.md` is unchanged.

## Acceptance criteria

- `CLAUDE.md`'s concept paragraph states materialization is lazy: `create` writes `concepts.json` only when a plan defers something, and un-deferred plans get no record.
- `CLAUDE.md` describes `concept-unsigned-deferral` as surfaced in `status` and the completeness report and non-blocking — not as an "advisory reminder."
- `CLAUDE.md` describes `detail` materializing a proposed deferral **pending** (unreviewed, via `save_concepts`), confirmed later via `scope-review` — not auto-signed under `-y`.
- `CLAUDE.md`'s still-true claims (scope-review scope, exact-ID ownership accounting, legacy parseability, split/merge/reground/scope-out conservation) are preserved unchanged.
- `BACKLOG.md` `#121` reads as shipped (no future-tense lazy-work language) and cites `docs/implementation-plans/2-lazy-deferral-confirmation.md`.
- `BACKLOG.md` `#121` contains no reference to the non-existent live seed path `plan-seeds/lazy-deferral-confirmation.md`.
- `BACKLOG.md` `#121` states the lazy path supersedes `concept-write-integrity` / `#126`–`#128` for the common flow.
- `BACKLOG.md` entries `#126`, `#127`, `#128`, `#129` still exist with accurate retained-work descriptions.
- The absent-record detail-materialization gap is tracked in `BACKLOG.md` (existing or newly filed).
- `plan-seeds/lazy-deferral-confirmation.md` is not present as a live file; the archived `.replaced.md` copy is unmodified.

## References

- [json — JSON encoder and decoder (Python 3.13)](https://docs.python.org/3/library/json.html) — background for the `concepts.json` record whose lazy write this step documents; useful when verifying step 1/2 behavior against the docs.
- `docs/implementation-plans/2-lazy-deferral-confirmation.md` — the plan this step closes; its Overview and Out-of-scope sections are the source of truth for the supersession wording.
- `plan-seeds/archive/lazy-deferral-confirmation.replaced.md` — the archived seed stating the exact reconciliation obligation this step discharges.

## Deferred

- Removing or migrating the hierarchical tree, `parent_path`/`depth`, or `Step.concept_ids` — the plan leaves the machinery dormant; deletion is a separate decision, not this docs step.
- Consolidating the remaining direct `save_concepts` writers (`create`, `detail`'s pending-deferral tail, `scope_out.py`) onto one writer — the parked concept-write-integrity single-writer goal, reconcile-owned (noted in step 4's Deferred), not this step.
- Retiring `#126`–`#128`/`#129` — those track residue the lazy path does not formally close; this step reconciles `#121`'s tense and disposition only, leaving the residue entries open.
- Implementing the absent-record detail-materialization path — this step only *files/verifies* the tracking entry; building the bootstrap-on-absent-record path is future work.
