---
title: Lazy Deferral Confirmation
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Stop eager concept enrichment in create and reconcile the create-writes-a-tree
    tests
  files:
  - plan_tool/create.py
  - tests/test_create.py
  - tests/test_concept_emit.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/01-stop-eager-concept-enrichment-create.md
  status: current
- id: 2
  title: Replace the whole-tree confirm walk with a deferral-only gate that records
    unconfirmed deferrals under -y and persists only defer/wont_do decisions
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/02-replace-whole-tree-confirm-walk.md
- id: 3
  title: Make an unconfirmed proposed deferral a surfaced (non-blocking) signal instead
    of info-only
  files:
  - plan_tool/review.py
  - plan_tool/completeness_report.py
  - plan_tool/cli/inspect.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/03-make-unconfirmed-proposed-deferral.md
- id: 4
  title: Materialize a new deferral at detail's shared-find routing via review_concept_scope
    and synchronize_concepts
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/04-materialize-new-deferral-detail-shared.md
- id: 5
  title: 'Update docs and close BACKLOG #121 for the lazy concept-materialization
    change'
  files:
  - BACKLOG.md
  - CLAUDE.md
  - plan-seeds/lazy-deferral-confirmation.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/05-update-docs-close-backlog-121-lazy.md
---
# Lazy Deferral Confirmation

> **Superseded — parked 2026-07-15.** This 5-step plan reused the whole-bundle concept
> fingerprint, which a 2-pass audit showed goes stale before the operator can confirm a
> pending deferral (breaking the core confirm loop). Superseded by a re-seed on a lazy
> foundation (bucket-tagged guide posts + concept-scoped fingerprints) —
> `plan-seeds/lazy-deferral-confirmation.md`. Its 4 convergence rounds fed that seed. Kept
> in `archive/` as reference.

## Overview

Make concept materialization **lazy** so `create` stops decomposing every plan into a full concept tree up front, and instead surfaces — for operator confirmation — only the concepts the tool proposes to **defer** or mark **won't-do**. This is the MVP of the original desire ("confirm the list of deferred concepts"): materialize a concept record entry only at a deferral decision, surface those (and only those) for confirmation, and leave un-deferred plans with no concept record at all. The shipped hierarchical machinery (the tree, `Step.concept_ids`, `synchronize_concepts`) stays in place but dormant-by-default — this does not rip it out. Expected decomposition ~5–7 steps; if convergence pressure grows it past that, defer to the backlog (BACKLOG #129) rather than growing the plan.

## Problem statement

Today `create` **eagerly** builds a concept tree for every plan whether or not anything is deferred. `bootstrap_concepts` (`plan_tool/concept_bootstrap.py:55`, called unconditionally at `plan_tool/create.py:5932`) emits one node per body section (~8), and `emit_concept_tree` (`plan_tool/concept_tree.py:330`, invoked at `plan_tool/create.py:5956` when no saved tree exists) enriches that to ~20 more speculative sub-concepts — 28 nodes in the shipped `concept-write-integrity` example, all `review_state="unreviewed"`, `decision="include"`. Almost none are ever deferred; they are the plan's prose re-encoded as a second structure that must be kept in sync — the coupling that produced the write-integrity bugs and the whole-bundle-fingerprint staleness that broke that plan's audit twice during authoring. Three specific problems, grounded: (1) **Eager over-decomposition** — `emit_concept_tree` at `create.py:5956` adds ~20 speculative sub-concepts nobody signs off on; that enrichment is the bloat, the sync surface, and (via the whole-bundle `compute_plan_fingerprint` on `load_concepts`, `plan_tool/concept_tree.py:234`) the staleness coupling, so any plan/detail edit invalidates the record even when no deferral decision changed. (2) **The confirm gate reviews the wrong thing and is silent under `-y`** — `_review_create_concepts` (`plan_tool/create.py:4506-4537`) walks the whole tree (include/defer/wont_do per node) and is skipped non-interactively (`create.py:4516-4517`), silently accepting the tool's suggestions — the exact founding-incident failure (BACKLOG #121), since these plans are authored with `-y`. (3) **The deferral producers don't gate a new concept decision.** Note the *concept record* has only two producers that can introduce a new deferral on the create/detail path: detail's shared-find routing (`detail.py:399-427`, today bounded to a pre-approved `decision="defer"` node by `detail.py:1683-1691` — step 4 relaxes this) and a carried-in `--from-existing`/resume record. The other two historical "defer points" are **not** concept-record producers: create-synthesis writes plan `## Deferred` *prose* and is already told to abstain on those sections (`prompts/synthesize-body.md:88-94` — it never reads the concept record nor emits a `decision="defer"` node), and the decomposition "a branch with no namable live scenario is NOT a step — defer it" instruction (`create.py:1983-1984`) silently omits the branch from the step array with no concept at all (its wiring is out of MVP scope). So the confirm gate (change B/C) governs the concept-record producers; the raw prose/omit paths are separate.

## Architecture

Keep the shipped record format and its writer; change *when and how much* gets materialized. Most of the lazy behavior is already latent: `scope-review` (`plan_tool/cli/scope_review_cmd.py:41-119`) already re-derives the tree from live plan text every run and tolerates an absent record (`original_tree is None` → bootstrap directly, `scope_review_cmd.py:57-64`), making it the natural materialize+sign-off hook; and the coverage findings (`check_concept_coverage`, `plan_tool/review.py:2290-2380`) are already inert on an absent/`None`/all-unreviewed tree (`review.py:2312, 2317`), firing only on `review_state=="approved"` nodes — so an empty-until-deferred record produces zero findings until an operator signs off. Five changes: **A. Stop eager enrichment** — do not call `emit_concept_tree` at create. Resolved record shape (settled by steps 1–2, not left open): an **un-deferred plan gets no `concepts.json` at all** — step 1 stops enrichment (keeping a thin section bootstrap only as an interim), and step 2 gates every persistence write on has-a-deferral, so the common plan is record-absent. This is the main breakage surface: the `create`-writes-a-tree tests (`create.py:5932-5974`; tests assert `concepts.json` exists post-create) must be reconciled to "absent record is valid." Enrichment becomes dead code for the create path; leave the function for possible reuse but stop invoking it eagerly. **B. Deferral-focused confirmation** — replace the whole-tree walk with a gate that surfaces only proposed `defer` / `wont_do` decisions; an included concept needs no confirmation and no record (a committed step is its own proof; coverage is already inert on unreviewed). **C. Safe under `-y` — pending, never auto-signed** (closes the founding incident) — non-interactively, a proposed deferral is recorded as **pending** (`review_state="unreviewed"`, `decision="defer"`/`"wont_do"`), **never signed off automatically**, and surfaced with its concept id so the operator can act on it; raise the existing `concept-unsigned-deferral` source (`review.py:2235`, today info-only) off the silent floor into a **surfaced but non-blocking** signal (completeness report + `status` + a `create` run-summary line) so it cannot ship unseen — non-blocking because only an operator `scope-review` decision, never `apply_finding` or the `--iterate` loop, can resolve it, so blocking would wedge the audit. A pending deferral is **not rendered into `## Deferred`** — the existing `render_scope_decisions` path emits only signed-off (`approved`) nodes, so a pending decision stays out of plan prose until confirmed. The operator confirms later via `scope-review` (already lazy), which signs it off and *then* renders it. This is the load-bearing decision: sign-off is an operator act, never a `-y` side effect. **D. Materialize at the defer points as pending** — at each defer decision (create's confirm gate in B/C, and detail's shared-find routing), materialize the one concept + its proposed `defer`/`wont_do` decision through `scope-review`'s derive path (`bootstrap_concepts` on an absent tree, exactly as `scope_review_cmd.py:57-64` does when `original_tree is None`) — but stop at recording it **pending**, without `sign_off=True`. This deliberately relaxes detail's current precondition that a deferral reference an *already-approved* node (`detail.py:1683-1691`): under lazy there is no pre-approval, so detail records a pending proposal instead. The safety net for a *mis-proposed* deferral is that a pending decision is **inert until confirmed** — it never renders and never counts, so a wrong one left unconfirmed is harmless. Actively confirming means `scope-review defer`/`wont_do`; deciding the concept should instead be *implemented* is a re-plan (add a step), out of this MVP — and note `scope-review include` on a lazy plan is not the dismissal path, because an approved `include` node with no committed owner trips a blocking `concept-coverage` finding (lazy plans carry no `Step.concept_ids`); a dedicated dismiss/remove verb is deferred (see Deferred). So the confirm surfaces offer `defer`/`wont_do`, not `include`. **E. Drop the enrichment, absent-when-un-deferred** — stop the ~20-node `emit_concept_tree` enrichment and write **no record at all** for an un-deferred plan (which is what breaks the whole-bundle-fingerprint staleness for the common case — no record, nothing to go stale). A plan that *does* defer carries at most the **thin section bootstrap** (create narrows its persisted tree to the decision nodes; detail and the reused `scope-review` derive+write the section nodes) — an order smaller than today's 28-node tree, though not strictly decision-only on every path; a fully decision-only record would require changing the reused `scope-review` writer, which is out of scope.

## Input

This plan reads existing contracts before it writes: the shipped `plan-details/<slug>/concepts.json` record format (its `review_state` and `decision` fields, e.g. `review_state="unreviewed"`/`"approved"`, `decision="include"`/`"defer"`/`"wont_do"`), whose writer it keeps unchanged; `scope-review`'s derive+sign-off path (`plan_tool/cli/scope_review_cmd.py:41-119`), which re-derives the tree from live plan text and tolerates an absent record (`original_tree is None`, `scope_review_cmd.py:57-64`); `check_concept_coverage` (`plan_tool/review.py:2290-2380`), inert on an absent/`None`/all-unreviewed tree (`review.py:2312, 2317`) and firing only on `review_state=="approved"` nodes; the existing `concept-unsigned-deferral` source (`review.py:2235`, today info-only); detail's precondition that a deferral references a signed-off `decision="defer"` node (`detail.py:1683-1691`); and the whole-bundle `compute_plan_fingerprint` on `load_concepts` (`plan_tool/concept_tree.py:234`) whose coupling change E breaks for the common case. Verification limit: legacy plans with empty ownership must remain parseable, so an absent or empty record is a valid input state, not an error.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — Official reference for frozen dataclasses and field() — needed to build the immutable, decision-keyed concept-record result objects this plan materializes.
- [json — JSON encoder and decoder (Python 3.13)](https://docs.python.org/3/library/json.html) — Primary docs for json.load/dump used to read and write the thin lazy concepts.json record without eager tree enrichment.
- [argparse — Parser for command-line options (Python 3.13)](https://docs.python.org/3/library/argparse.html) — Official argparse subparsers/add_argument reference for wiring the scope-review defer gate and the confirmation flags this plan touches.
- [How to use temporary directories and files in tests (pytest)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — The tmp_path fixture reference an implementer opens to reconcile the create-writes-a-tree tests to an absent-record-is-valid world (change A's main breakage surface).

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Removing the hierarchical tree, `parent_path`/`depth`, or `Step.concept_ids` — leave the shipped machinery in place but dormant; migration/deletion is a separate decision. `split` / `merge` / `reground` / `scope-out` conservation of `concept_ids` keeps working on whatever ids exist (empty is the valid default).
- The `concept-write-integrity` transactional hardening and BACKLOG #126–#128 — largely moot for the lazy path (fewer/smaller writers, no big record to diverge from prose); this seed supersedes that path for the common flow rather than completing it.
- New schema, commands, or a rewrite of `concept_sync` — reuse `scope-review`'s derive+sign-off.

## Risks

- The `create`-writes-a-tree test coupling is the main breakage surface (change A); budget a step to reconcile those tests to "absent record is valid."
- The unsigned-deferral surface is **settled non-blocking** (change C, step 3): only an operator `scope-review` decision can resolve it, and a blocking finding would wedge the `--iterate` loop (which has no path to approve a concept decision). It is raised off the silent info floor and given dedicated surfaces, but kept out of `SELF_CONSISTENCY_SOURCES` — surfaced, never exit-code-flipping. (This is a foreclosed decision, not an open blocking-vs-surface trade-off.)
- **Residual staleness on deferred plans — and its reach into step 3's surface.** Change E breaks the whole-bundle-fingerprint staleness coupling only for the *un-deferred* common case. A plan that *does* defer still writes a `concepts.json` whose `plan_fingerprint` is bundle-wide, so `load_concepts` raises `StaleConceptTreeError` on any unrelated prose/detail edit to exactly the plans the concept machinery serves. Critically, step 3's surfacing runs through `check_concept_coverage` → `load_concepts`, so a stale record would make `status`/the completeness report **raise instead of surfacing** the very pending deferral they exist to show — defeating "cannot ship unseen." Step 3 therefore must treat a stale record as "re-derive," catching `StaleConceptTreeError` in the surfacing path and still surfacing (best-effort, with a staleness note) rather than raising. Per-decision (not bundle-wide) fingerprint keying — the durable fix — is deferred (see Deferred).
- Relaxing detail's already-approved precondition (change D) lets detail record a pending deferral for any concept; a mis-proposed one (e.g. a section a committed step implements) is caught at the operator's `scope-review` confirmation rather than by an ownership guard, since lazy plans carry no `Step.concept_ids`. Tight ownership-bounding is deferred.

## Testing

- **Un-deferred plan:** `create -y` produces no blocking findings, writes **no `concepts.json`**, and makes no `emit_concept_tree` call.
- **Founding-incident regression:** a `create -y` whose **confirm gate** proposes a deferral leaves a **pending** (unreviewed, un-signed) deferral that the completeness report + `status` + `create` run-summary surface **with its concept id** — non-blocking — never a silently-accepted one, and that pending deferral does **not** appear in the plan's `## Deferred` prose until confirmed.
- **Lazy materialization:** a `scope-review` defer on a plan with no prior record creates exactly the one deferred concept, signs it off, and renders it into `## Deferred` (reuses the existing `render_scope_decisions` path).
- **Detail pending deferral:** detail's shared-find routing on a record-absent plan derives a bootstrap tree on the fly, records the proposed deferral **pending** (no `sign_off`), and leaves `## Deferred` unrendered until confirmed.
- **Staleness:** editing an un-deferred plan's prose does not raise `StaleConceptTreeError` anywhere (there is no record to invalidate).

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `create -y` on an un-deferred plan produces no blocking findings, does not invoke `emit_concept_tree`, and leaves **no `concepts.json`** (record-absent — settled by change A).
- A `create -y` whose **confirm gate** proposes a deferral records it **pending** (`review_state="unreviewed"`, not signed off) and surfaces it (non-blocking) — with its concept id — in the completeness report, `plan-tool status`, and a `create` run-summary line, never silently accepting the tool's suggestion. The surface stays non-blocking (out of `SELF_CONSISTENCY_SOURCES`, never flips an exit code), because only an operator `scope-review` decision can resolve it. (The raw decomposition-omit producer — the "no namable scenario → defer it" instruction that today only drops a branch from the step array — is **out of MVP scope**; see Deferred.)
- A pending (unconfirmed) deferral is **not** rendered into `## Deferred`: `render_scope_decisions` emits only `approved` nodes, so a pending decision stays out of plan prose until an operator confirms it.
- The pending-deferral surfaces print the exact token `scope-review --concept` consumes — the **bare `node.id`**, not the finding's `concept-<id>` anchor form — so a surfaced pending deferral is actionable, not seen-but-stuck. (Verify the token against `scope_review_cmd.py`'s `--concept` parsing when wiring the surface.)
- A `scope-review defer` on a plan with no prior `concepts.json` signs off exactly the one named concept and renders it into `## Deferred` via the existing `render_scope_decisions` path. (The persisted record holds the derived section nodes — `scope-review`'s existing bootstrap-the-whole-tree behavior, reused unchanged — not a single node.)
- Editing an un-deferred plan's prose raises no `StaleConceptTreeError` anywhere, because no record exists to invalidate. (A plan that *has* deferred still carries a bundle-wide fingerprint — that residual is named in Risks/Deferred, not closed here.)
- An `include` decision requires no record entry and no confirmation, and `check_concept_coverage` stays inert until an operator signs off a `review_state=="approved"` node.

## Deferred

- Wiring the raw create **decomposition-omit** producer (the "a branch with no namable live scenario is NOT a step — defer it" instruction, `create.py:1983-1984`) to emit a pending concept — today it silently drops the branch from the step array with no concept. The MVP closes the founding incident for the **confirm-gate** path (proposed `defer`/`wont_do` decisions the tool surfaces); the raw-omit path is a separate producer needing its own wiring — file it to `BACKLOG.md` under #121 residue rather than growing this plan.
- Tight ownership-bounding of a detail-time pending deferral to concepts genuinely lacking a committed owner — under lazy there is no `Step.concept_ids` to check, so a mis-proposed pending deferral is inert (never confirmed → never rendered) rather than guarded; a structural owner check is deferred.
- A **dismiss/remove** verb for a pending deferral the operator judges wrong (drop the node from the record) — `scope-review` today only does `include`/`defer`/`wont_do`, and `include` on a lazy plan trips a blocking `concept-coverage` finding (approved-include with no owner), so it is not a dismissal path. The MVP leaves a wrong pending deferral inert-until-confirmed; a dedicated dismiss action is deferred to `BACKLOG.md`.
- Deciding a proposed-deferral concept should instead be **implemented** (a re-plan that adds a step for it) — out of the confirmation MVP; the operator re-plans rather than resolving it through `scope-review`.
- Per-decision (not whole-bundle) fingerprint keying so a plan that *does* defer stops going stale on unrelated edits (the residual named in Risks) — deferred; relates to the staleness coupling in #126–#128 territory.
- Enforcing a seed-declared step ceiling and the program-scale monitoring that would have caught the original blowup — BACKLOG #129.

(Change A's record-shape question — thin bootstrap vs fully record-absent — is **resolved**, not deferred: un-deferred plans are record-absent. See Architecture A.)
