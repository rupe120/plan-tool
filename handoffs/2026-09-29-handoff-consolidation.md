# Handoff: handoff-doc cleanup and consolidation

`handoffs/` holds 33 dated records (1.1 MB) plus `README.md`. The directory
follows the `README.md` contract — a handoff records what a future session does
next; a review ledger records how one bounded change was judged — but the
records have outgrown it. This handoff queues the cleanup. Delete an item when
it closes.

Route: docs hygiene only. No code, plan, or backlog-entry semantics change.
Start with `BACKLOG.md`'s working board; this file does not override it.

## Scope contract

- **Outcome:** every file in `handoffs/` is either indexed in `README.md` with a
  live purpose, or retired with its durable content moved to its canonical home.
- **In scope:** `handoffs/*.md`, the `README.md` index, and the inbound
  references listed under "Inbound references".
- **Out of scope (deliberately not touched):**
  - Frozen plans, plan details, and saved `reports/` under
    `docs/implementation-plans/` — editing one makes its saved audit reports
    stale. Reports that cite a handoff are left as written.
  - Rewriting the substance of any ledger's findings or dispositions.
  - Deleting a record that is still the only home of a live decision.
- **Stop / defer:** if a record's live/retired status is unclear, leave it and
  ask the owner; do not guess.

## Findings (measured 2026-09-29)

| Finding | Evidence |
| --- | --- |
| **10 files are not indexed** in `README.md`'s "Current handoffs" | `authored-artifact-structure-versioning`, `integration-engagement-evidence`, `roadmap-aidlc-integration-delivery`, `roadmap-concept-comparison-code-review`, `unpushed-main-code-review`, `roadmap-model-failure-receipts-code-review`, `roadmap-versioned-feedback-revision-chain-code-review`, `roadmap-candidate-vocabulary-retry`, `roadmap-candidate-envelope-diagnostics-code-review`, `candidate-anchor-gate-correction-code-review` |
| **One file is 331 KB**, 30% of the directory | `2026-09-08-authored-artifact-structure-versioning.md` — 58 sections; its plan is `completed` (2026-09-09), all seven steps `done`; `BACKLOG.md` still cites it 4 times |
| **Nine ledgers are converged** but still sit beside live handoffs | see "Ledger triage" below; ~430 KB combined |
| **Dangling inbound references** to handoffs already retired (corrected 2026-09-29: only the second is a real gap; the first names Integration's own handoff) | `handoffs/2026-09-08-aidlc-authoring-route.md` (3 cites in `docs/implementation-plans/backlog-arcs/backlog-arc-integration-mvp.md`) and `handoffs/2026-08-27-integration-roadmap-evidence-preflight.md` (2 cites in `docs/implementation-plans/2-roadmap-source-baseline-recovery.md`) |
| **README index is stale in a second way** | "Current handoffs" mixes live handoffs and converged ledgers with no split, and the entry for `2026-09-12-…-drift-code-review` says the review "authorizes findings only" though that review closed with all 55 findings resolved |
| **Two `.tmp/` handoff scratch files** exist | `.tmp/2026-09-15-convergence-eval-experiment-handoff.md`, `.tmp/2026-09-22-roadmap-model-failure-receipts-handoff.md` — gitignored; check whether either is the only copy of anything before deleting |

## Ledger compression: done 2026-09-29

Compressed ledgers keep finding explanations, evidence, dispositions and closure
labels. Retain enough reasoning for a maintainer to understand each decision.
The 2026-09-29 compression preserves these deliberate omissions:

| Ledger | Dropped | Why |
| --- | --- | --- |
| `roadmap-brief-source-drift` | `40e76f91` | Documentation-only commit cited in a scope note, never for a finding |
| `roadmap-structural-feedback-approval` | `509cd49f`, `8dc2e9d0`, `df582bab`, `4561ff6e` | Documentation- or ledger-only commits in scope lines |
| `roadmap-concept-comparison` | `#1`, `#6` | Cross-references to finding numbers, not backlog ids |

Compressed files still over their size targets (kept, because a harder trim
cuts the reasoning behind `declined` and `refuted` findings): `versioned-chain`
25 KB, `concept-comparison` 18 KB, `structural-approval` 17 KB,
`brief-source-drift` 17 KB.

Agent-authored structure a later reader should know about: `unpushed-main`,
`model-failure-receipts`, `concept-comparison`, and `versioned-chain` have no
original "Settled decisions" list, so the one they carry was assembled from
each ledger's own declined and refuted findings. `unpushed-main` R4-8 ("noted,
not filed" in the source) is recorded `pending` (owner, 2026-09-29); it is
tracked nowhere.

Open items this leaves:
- `unpushed-main` R4-8 stays `pending` and unfiled until either function is next touched.
- `structural-approval` keeps the owner's run-log-coverage direction for
  approve, reject, discard, and promote; filed 2026-09-29 as `BACKLOG.md` #434.
- Remaining ledger with no compression: `backlog-id-guard` (11 KB, kept: finding E is open).

## Ledger triage (as decided before compression)

| File | Size | Status recorded in the file | Proposed action |
| --- | --- | --- | --- |
| `2026-09-12-roadmap-brief-source-drift-code-review.md` | 94 KB | 55 findings, all dispositioned | Compress to summary + settled decisions |
| `2026-09-21-roadmap-concept-comparison-code-review.md` | 88 KB | **Stopped by owner 2026-09-21** after 11 rounds, not converged; its file says so. Round commits `45fc73bf`..`92c96ef3`; 17 items remain as BACKLOG #406–#422 | Compress as a stopped loop; replace each "commit pending" with the round commit id; keep the #406–#422 list
| `2026-09-21-unpushed-main-code-review.md` | 53 KB | Converged after 4 rounds | Compress |
| `2026-09-22-roadmap-model-failure-receipts-code-review.md` | 42 KB | Converged, loop stopped | Compress |
| `2026-09-23-roadmap-versioned-feedback-revision-chain-code-review.md` | 98 KB | Converged (low-yield); follow-ups BACKLOG #427–#429 | Compress; keep the follow-up ids |
| `2026-09-23-roadmap-structural-feedback-approval-code-review.md` | 54 KB | **Closed by owner decision 2026-09-24**, not by the two-clean-pass rule (says so). Open: wider run-log coverage for approve/reject/discard/promote. Carries a non-converging warning for the recurring class | Compress; keep the closure paragraph and the open run-log direction verbatim
| `2026-09-24-roadmap-stack-aware-approval-code-review.md` | 26 KB | Converged 2026-09-25 | Compress |
| `2026-09-25-detail-deferrals-envelope-repair-code-review.md` | 17 KB | Converged 2026-09-25 | Compress |
| `2026-09-26-roadmap-candidate-envelope-diagnostics-code-review.md` | 20 KB | Converged 2026-09-27 | Compress |
| `2026-09-27-candidate-anchor-gate-correction-code-review.md` | 48 KB | **Converged, low-yield, after 8 passes (2026-09-27)**; passes 6–8 found no correctness defect | Compress; fix the top table, which still reads `_(in progress)_`
| `2026-09-23-backlog-id-guard-code-review.md` | 11 KB | Finding E `pending` (wider broken-link count) | **Keep**: E is open; tracked in `BACKLOG.md` #426 |

To compress a closed ledger, keep its summary table, settled decisions, every
`tracked <backlog id>` and `pending` disposition, and one line per finding with
its evidence and disposition. Remove narrative only when the remaining text
still explains the decision. Preserve the distinction between convergence,
owner-stopped work and closure by owner decision.

## Open design choices in the AI-DLC fit doc (read 2026-09-29)

`2026-09-11-roadmap-aidlc-inception-fit.md` § "Open design choices" lists 11
undecided items. Only one has been decided since: the source carrier, which the
2026-09-16 comparison (`docs/evidence/roadmap-aidlc-intake-comparison-20260916.md`)
settled for now by shipping #384 on the single brief and holding #383. The rest
wait on an evidence trigger, which is by design.

| Group | Choices | Waits on |
| --- | --- | --- |
| Decided for now | Source carrier | Reopens only if a per-stage grounding gap is proven (#383) |
| Open, low urgency | RAID mapping (lean: existing concepts); hosting and quality facts reaching stage 2; question-mode default | Obligations and settle-once questions are unbuilt; each needs a load-bearing case the comparison did not find |
| Blocked on Integration or the coverage decision | Framework requirement IDs; Inception-step coverage table; what Integration's first run needs | Integration's workflow profile and connector; no `roadmap` run has used the real corpus |
| Parked with the shared frame | Scope-list rendering; fit-to-box check; frame reach to wording-only and read-only requests; frame reach past `roadmap`; frame size against byte ceilings | A revision route shown to change meaning outside the proven box (delivery handoff § 6) |

Consolidation consequences:
- **Done 2026-09-29:** the stale "Next pickup" is replaced and the open-decisions list has one owner (the fit doc); the integration doc and the delivery handoff now point to it. `tests/test_roadmap_format.py` pinned the old pickup sentence, so its assertion moved with the text.
- **Was: stale "Next pickup".** `2026-09-14-roadmap-aidlc-integration-delivery.md`
  still says to request the corpus comparison, which finished 2026-09-16.
  Replace it with the current pickup: none selected; #383 and #385 held.
- **Was: one owner for the open list.** The fit doc, the delivery handoff's "Open
  decisions" table, and `docs/integrations/aidlc-integration.md` each keep a
  copy. Make the fit doc the owner; the other two link to it and keep only the
  status line. Sweep both halves (paths and the vocabulary "explicitly still
  open") when doing so.

## Proposed steps

1. **Verify before deleting anything.** For each candidate, read the file's
   tail (status, convergence, follow-ups), then grep inbound references
   (`grep -rIn "handoffs/<file>" . --exclude-dir=.git --exclude-dir=.tmp`).
   Record per file: live / converged / superseded.
2. **Resolve the two dangling references.** Repoint or drop the 5 cites above;
   these live in plan files, so decide per site whether editing is worth
   staling saved reports (default: leave, and note it in the README).
3. **Done 2026-09-29: `authored-artifact-structure-versioning` moved to
   `docs/evidence/`** (owner decision). Its links, the two `BACKLOG.md` cites,
   and the evidence index were updated. Known residue, left because the files
   are frozen: three code-span citations of the old `handoffs/` path in
   `docs/implementation-plans/archive/2-authored-artifact-format-version.md`
   and its step-7 detail, and historical mentions in the id-guard ledger.
4. **Compress converged ledgers** per the table, one commit each, keeping the
   `README.md` review-ledger contract (summary table, settled decisions,
   dispositions from the closed set).
5. **Rebuild the `README.md` index** in two labelled sections — *Live
   handoffs* and *Converged review ledgers* — each entry a one-line purpose.
   State the empty case explicitly if a section ends up empty.
6. **Add a retention rule to `README.md`**: a ledger compresses when its loop
   converges; a handoff is deleted (not archived in place) when its work ships.
   This follows `CLAUDE.md` § "Documentation is forward-looking".
7. **Sweep both halves** after each retirement: identifiers (paths, ids) and
   vocabulary (the retired record's terms) across `BACKLOG.md`,
   `BUG_BACKLOG.md`, `CONTRIBUTING.md`, `RUNBOOK.md`, and other handoffs.
8. **Re-run the broken-link scan** from
   [`2026-09-23-doc-cleanup.md`](2026-09-23-doc-cleanup.md) before and after; the
   count must not rise.

## Small 2026-09-08 handoffs: done 2026-09-29

Seven records are deleted. Each of six pointed at a backlog entry (#216, #242,
#322, #355/#361, #359) or superseded route that already carries the same
pickup and fence (checked entry by entry; #242's re-entry trigger is verbatim in
`backlog-arc-roadmap.md`). The seventh, `roadmap-lineage-disposition`, held the
only copy of the successor-slug rule, which now lives in `docs/how-to/roadmap.md`
§ "Reuse the slug, or start a successor". `backlog-arc-integration-mvp.md` and the
`authored-artifact` handoff were repointed. The README's "2026-09-08
consolidation record" stays as written; it names routes, not files.

## Also queued nearby

- `2026-09-23-doc-cleanup.md`, `2026-09-23-jira-management.md`, and
  `2026-09-29-branch-cleanup.md` are live and overlap in "general hygiene"; this
  handoff does not merge them, but the README should say how they differ.
- Integration seam set (`integration-ideation-roadmap-intake-review`,
  `roadmap-aidlc-inception-fit`, `integration-seam-resume-order`, and
  `roadmap-aidlc-integration-delivery`): ~115 KB.
  `docs/integrations/aidlc-integration.md` cites the fit doc, so retire only
  after repointing.
- **Done 2026-09-29 (committed `a9ef2fe3`):** `roadmap-intake-evolution-ideas` is retired. Its ideas
  are covered by #383/#384, the 2026-09-16 comparison in `docs/evidence/`, and
  the fit doc's re-ranking; its one uncaptured item (review-time aids) is now a
  note on `BACKLOG.md` #383.

## Verification

- `ls handoffs | wc -l` and `du -sh handoffs` before and after; report both.
- Every remaining `handoffs/*.md` (except `README.md`) appears in the index.
- `grep` for each deleted filename across tracked files returns only frozen
  reports, and those are listed in the README as known residue.
- Broken-link scan count does not increase.

## Verification result (2026-09-29)

| Check | Result |
| --- | --- |
| Size | 34 files, 1,134,313 bytes at `72f58f79` -> 26 files, 402,212 bytes (`du`: 1.2 MB -> 452 KB) |
| Index | Every `handoffs/*.md` except `README.md` is indexed; no README link targets a missing file |
| Deleted-name references | Only frozen archive plans and the id-guard ledger cite a moved or deleted handoff path; all are listed in the README under "Known dangling citations" |
| Broken relative links | 235 at `72f58f79` -> 234 now; none new (the one removed was in a deleted handoff) |
| Tests | Fast suite 13322 passed after the open-decisions edits; the docs, link, evidence and roadmap-format subset passed after each later change |

## Still open

- Deliberately not done (owner, 2026-09-29): the gitignored `.tmp/` scratch handoffs and logs are left as they are; nothing there is sorted or deleted.
- `unpushed-main` R4-8 stays `pending` until either function is next touched.
- The branch cleanup and doc cleanup handoffs are separate, live routes.
- Push is held by the owner (2026-09-29); every commit from this cleanup is local.

## Commits

One concern per commit: index rebuild, each retirement, each compression, and
the retention rule separately. Push is a separate decision; the branch-cleanup
handoff records that handoff PRs are held until review completes.
