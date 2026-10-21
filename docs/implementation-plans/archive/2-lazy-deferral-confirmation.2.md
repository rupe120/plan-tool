> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Lazy Deferral Confirmation
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add a flat decision-record kind to concepts.json and skip fingerprint validation
    when loading it
  files:
  - plan_tool/concept_tree.py
  - DATA_CONTRACT.md
  - tests/test_concept_tree.py
  - tests/test_data_contract.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/01-flat-decision-record-kind-concepts-json.md
  status: done
- id: 2
  title: Replace create's whole-tree confirm walk with a deferral-only gate that stays
    pending under -y, and stop calling emit_concept_tree
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/02-replace-create-whole-tree-confirm-walk.md
  status: done
- id: 3
  title: Make check_concept_coverage total and surface a record whose bucket no longer
    exists for re-review
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/03-make-check-concept-coverage-total.md
  status: done
- id: 4
  title: Let scope-review confirm a flat decision record after unrelated edits, checking
    bucket existence instead of the plan fingerprint
  files:
  - plan_tool/cli/scope_review_cmd.py
  - tests/cli/test_scope_review_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 3
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/04-let-scope-review-confirm-flat-decision.md
  status: done
- id: 5
  title: Surface pending decisions as a flat, bucket-grouped, non-blocking list (with
    on-demand bucket section context in status) across status, the completeness report,
    and a create run-summary line
  files:
  - plan_tool/cli/inspect.py
  - plan_tool/completeness_report.py
  - plan_tool/create.py
  - tests/cli/test_inspect_cmds.py
  - tests/test_completeness_report.py
  - tests/test_create.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/05-surface-pending-decisions-flat-bucket.md
  status: done
- id: 6
  title: Have detail's deferral routing record a flat pending decision on a record-absent
    plan, never auto-signed under -y
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/06-have-detail-shared-find-routing-record.md
  status: done
- id: 7
  title: 'Update BACKLOG.md, CLAUDE.md, and DATA_CONTRACT.md to close #121 and reconcile
    the lazy-deferral disposition'
  files:
  - BACKLOG.md
  - CLAUDE.md
  - DATA_CONTRACT.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/07-update-docs-close-backlog-121.md
  status: done
---
# Lazy Deferral Confirmation

## Overview

Ship the leanest MVP of "confirm the deferred concepts": a deferred concept becomes a **flat decision record** `{bucket, title, rationale, decision, review_state}` — an operator/tool decision, not a derived cache. The key move is that a decision record is **not fingerprint-validated against plan text at all**, so a recorded decision no longer goes stale when unrelated prose changes (the real staleness fix); its only validity check is whether its `bucket` still exists. There is **no concept hierarchy and no drill** in this MVP — the `bucket` (a coarse section-level tag) is the leaf, and the pending list is grouped by bucket. This supersedes the two prior lazy attempts and stops using the shipped hierarchical machinery without ripping it out. Expected ~5–7 steps.

## Problem statement

BACKLOG #121's goal was to **confirm the concepts the tool defers** so none is silently dropped, but the shipped machinery over-solved it. `create` eagerly decomposes every plan into a ~28-node concept tree kept in sync with prose via a whole-bundle fingerprint (`compute_plan_fingerprint` on `load_concepts`, `concept_tree.py:234`). A pending deferral must survive until the operator confirms it *later* — after more edits — so any whole-bundle fingerprint on that record is stale by confirm time, and `scope-review` (`scope_review_cmd.py:cmd_scope_review`, which returns `SCOPE_REVIEW_INVALID_STATE_EXIT` on `StaleConceptTreeError`) then refuses to confirm it. Specifically: (1) `load_concepts` raises `StaleConceptTreeError` on a `plan_fingerprint` mismatch (`concept_tree.py:234`), cascading through `scope-review` (dead-ends confirm) and `check_concept_coverage` → `load_concepts` (crashes `status`, the completeness audit, and the `--iterate` gate via `collect_smell_findings` / `collect_self_consistency_findings`) — but a pending deferral is confirmed after edits by design, so the guard is simply wrong for this record. (2) Eager decomposition plus a hierarchy is unneeded: `bootstrap_concepts` (`concept_bootstrap.py:55`, `create.py:5932`) emits a node per body section and `emit_concept_tree` (`concept_tree.py:330`, `create.py:5956`) enriches ~20 more that nobody signs off on, when a deferral only needs its coarse bucket. (3) The confirm gate `_review_create_concepts` (`create.py:4506-4537`) walks every node and is skipped non-interactively (`create.py:4516`), silently accepting the tool's suggestions — the founding incident.

## Architecture

Keep what is already lazy; remove the fingerprint guard and the pre-computed tree.

- **A. Flat decision record.** A deferred concept is `{bucket, title, rationale, decision (defer|wont_do), review_state}`. `bucket` is a coarse section-level tag; `rationale` is the short reason the proposer (detail, step 6) gives for the deferral — populated from the deferral envelope so a confirmed decision renders as `- {title} — {rationale}` and the record captures *what/why*, not just the section name. No `parent_path`/`depth`, no hierarchy, no per-record hash. An un-deferred plan has **no record at all**.
- **B. Not fingerprint-validated (the staleness fix — the whole point), for FLAT records only.** A **flat decision record** skips the whole-bundle `plan_fingerprint` guard on load: a decision record is not a cache of plan text, so it does not go stale when the plan is edited. Every read/confirm path (`scope-review`, `status`, `check_concept_coverage` and its `collect_*` callers) loads and acts on a *flat* record **without** a `StaleConceptTreeError` gate; its only validity question is C. A **legacy full-tree** record keeps its fingerprint guard (it *is* a derived cache) and its existing behavior — see **H** (dual-mode); the fingerprint-skip is scoped to the flat kind so a legacy record's staleness still means "re-derive," not "ignore."
- **H. Dual-mode — the legacy full-tree path stays live (no regression).** This repo already holds full-tree `concepts.json` records (the shipped concept plans; archived `concept-write-integrity` / `concept-remediation-*`). v3 must **not** break their ability to confirm deferrals. So every touchpoint branches on `record_kind`: a **flat** record takes the new lazy path (B/C above); a **legacy full-tree** record keeps the existing path — `scope-review` still bootstraps+re-derives+confirms it (not a hard refusal), `check_concept_coverage` still surfaces its findings under the fingerprint guard (a stale legacy record means re-sync, not swallowed-to-`[]`), and `detail` on a legacy record keeps its old behavior and **warns** rather than silently dropping a proposed deferral. Both modes coexist until the #131 migration retires the legacy shape.
- **C. Bucket-existence check, not a content hash.** The one thing that can invalidate a deferral is its `bucket` no longer existing (the section it referred to was deleted/renamed). Read/confirm paths check whether the record's `bucket` still resolves to a current body section (a **name lookup**, no hash). A missing bucket **surfaces the record for operator re-review** (not a silent stand, not a hard crash). Crucially, `scope-review` must still be able to **resolve** such a record — the whole point of surfacing it — so a missing bucket must **not** hard-refuse the confirm: the operator can sign it off `wont_do` (the deferred thing's home is gone, so it is out of scope) or `defer` it as-is. Signing off is what **clears** the finding: `check_concept_coverage` surfaces `concept-bucket-missing` only for an *unreviewed* node, so `wont_do` (which sets `review_state="approved"`) stops it re-surfacing — it is the clear-it path (a full **dismiss/remove** verb that drops the record is deferred to BACKLOG #132). Refusing a missing-bucket record outright would strand it as a non-clearable standing finding. **Rename case:** when a section is *renamed* (not deleted) the concept is still live under the new name — the documented workflow is `wont_do` the now-stale record (clearing it) and let `detail` re-propose the concept under the new bucket; a first-class "re-home to a new bucket" verb is out of MVP scope (a #132-adjacent follow-up).
- **D. Deferral-only confirm gate, safe under `-y`.** Replace the whole-tree walk with a gate that records only proposed `defer`/`wont_do` decisions. Under `-y` a proposal is recorded **pending** (never auto-signed); interactively the operator may confirm (`defer`/`wont_do`) or **decline** (the declined proposal is dropped — no record). Included concepts get nothing (a committed step is proof).
- **E. Surface pending decisions with the actionable id, non-blocking.** Surface each pending decision with its title + the **bare `node.id`** token `scope-review --concept` consumes, across three surfaces: `status`, the completeness report, and a `create` run-summary line — all **non-blocking** (only an operator `scope-review` decision resolves it; blocking would wedge the `--iterate` loop). The `status` surface is the flat MVP's navigation: it **groups by section `bucket`** (it can load the record). The completeness report renders from findings only (no disk access), so it groups by pending **kind** (unsigned vs missing-bucket); the `create` line names the id(s). No drilling — the status bucket grouping *is* the navigation. Confirming signs it off and renders it into `## Deferred` via the existing `render_scope_decisions` path.
- **G. Lazy context — show the bucket's section text on demand, don't store a catalog.** To situate a deferred concept without cataloging every concept (the eager decomposition this MVP removes), the `status` surface renders, under each bucket group, a **short excerpt of that bucket's current body-section text**, read on demand from the plan (`parse_body_sections`), so the operator sees *what the deferral relates to* without a second stored structure. The plan prose is the concept catalog; a decision record is a thin pointer into it, and the section excerpt is that pointer resolved lazily at display time. This deliberately stops short of a browsable sub-concept hierarchy (that would need an on-demand sub-concept producer — deferred to BACKLOG #130); the section excerpt is the flat MVP's contextualization.
- **F. Detail records — or merges — a flat pending decision.** Detail's **deferral routing** (the `parse_structured_detail_response` deferral gate) records a new deferral as a flat pending decision (bucket-tagged), with no dependency on a pre-materialized tree. On a **record-absent plan** (the lazy common case) it writes a fresh flat record; on a plan that **already carries a flat `decision-record`** it **merges** the new deferral in idempotently — a new bucket is added and prior pending nodes are left untouched, a re-deferral of an already-`unreviewed` bucket is a no-op (no duplicate), and a bucket already signed off (`review_state="approved"`, e.g. a prior `wont_do`) is **preserved**, never re-opened to pending (`[detail-merge-into-existing-node]`). A **legacy full-tree** record is *not* extended or clobbered here — detail-time deferral on a legacy record depends on the record-kind coexistence tracked in BACKLOG #131. Never auto-signed under `-y`.

## Input

This plan consumes the existing persisted `plan-details/<slug>/concepts.json` record contract. Two shapes must remain loadable through the same load path: the new **flat decision record** `{bucket, title, rationale, decision (defer|wont_do), review_state}` and the **legacy full-tree** hierarchical record produced by `bootstrap_concepts` / `emit_concept_tree` (with `parent_path`/`depth` and per-bundle `plan_fingerprint`). `load_concepts` (`concept_tree.py:234`) is the read seam; the change removes the `StaleConceptTreeError` `plan_fingerprint` guard for the flat-record path and adds a record-kind branch. The bucket-existence check reads the plan's current body-section names as its lookup target, so the notion of a stable section name is a depended-on contract. Legacy records are left dormant and loadable, not migrated (migration is deferred).

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — Official reference for defining the flat decision record ({bucket, title, rationale, decision, review_state}) as a typed dataclass, including field defaults and frozen/immutability options.
- [json — JSON encoder and decoder (Python 3.13)](https://docs.python.org/3/library/json.html) — Primary reference for serializing/deserializing the decision record and adding the record-kind load branch that keeps both flat and legacy concepts.json loadable.
- [argparse — Parser for command-line options (Python 3.13)](https://docs.python.org/3/library/argparse.html) — Canonical guide for wiring the scope-review/status/create flags (e.g. --concept, -y) an implementer touches when surfacing and confirming pending deferrals.
- [typing — Support for type hints (Python 3.13)](https://docs.python.org/3/library/typing.html) — Reference for the Literal/Optional/enum-style annotations used to constrain decision (defer|wont_do) and review_state fields on the record.
- [pytest — full documentation](https://docs.pytest.org/en/stable/) — Testing framework used across the suite; consulted for authoring the staleness, bucket-gone, founding-incident, and confirm-loop tests the plan's Testing section requires.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Any concept hierarchy / drill / sub-concepts** — the bucket is the leaf. On-demand sub-concept derivation (the drill vision) is a deliberate non-goal here; if wanted it is a separate feature that re-introduces a scoped producer. Flat bucket-level deferrals fully solve the founding incident.
- **Per-record content fingerprints** — decisions are not caches; validity is bucket-existence only.
- Removing the shipped hierarchical tree / `Step.concept_ids` — left dormant, not deleted.
- The `concept-write-integrity` transactional hardening / #126–#128 — moot for the lazy path.
- A dismiss/remove verb for a wrong pending decision — inert until confirmed; active dismissal deferred.

## Risks

- **Dual-mode maintenance cost (accepted, Architecture H).** Every touchpoint (`load_concepts`, `scope-review`, `check_concept_coverage`, `detail`) branches on `record_kind`: flat records take the new lazy path, legacy full-tree records keep the existing path. This is more code than a flat-only MVP, but it is the deliberate cost of **not regressing** the existing full-tree records (shipped concept plans, archived `concept-write-integrity`/`concept-remediation-*`). The legacy path is *unchanged existing behavior*, so the risk is limited to the branch wiring; both modes retire when #131 migrates legacy records to flat.
- "Bucket still exists" needs a stable notion of a body-section name; a renamed section reads as a missing bucket and surfaces the record for re-review — intended, but validate it isn't noisy on ordinary section edits (an edit to a section's *body* must not read as a missing bucket).

## Testing

- **Staleness (the root):** a plan with a pending decision, then any unrelated edit, leaves the decision fully usable — `scope-review defer` confirms it, `status`/`check_concept_coverage` act on it, no `StaleConceptTreeError` anywhere.
- **Bucket gone:** deleting/renaming the decision's bucket surfaces it for re-review (not a silent stand, not a crash).
- **Founding incident:** a `detail`-proposed deferral (step 6, the sole operationalized proposer) leaves a pending decision surfaced with its bare id in `status` and the completeness report, never silently signed. (A fresh `create -y` proposes nothing under the lazy model; carried-in flat records via resume are out of scope — see Deferred.) Separately, `create`'s interactive concept gate (step 2) **drops** a proposed deferral the operator declines — that decline-drop is exercised there, not on the detail proposer. **Coverage boundary (BACKLOG #134):** the shipped tests verify this as two agreeing halves — step 6 pins the record the producer writes, step 5 pins the surfaces rendering that record shape — not a single producer→surface integration test; a real `detail`→`status`/report e2e test is tracked in #134 as a coverage-strength backfill.
- **Confirm loop end-to-end:** surface → `scope-review defer` → rendered in `## Deferred`, on a plan edited since the deferral was recorded.
- **Detail:** deferral routing records a flat pending decision on a **record-absent** plan and **merges** a new deferral into an **already-present flat `decision-record`** (new bucket added; re-deferral of a pending bucket a no-op; an already-signed-off bucket preserved); on a legacy full-tree record it keeps legacy behavior and warns (rather than silently dropping) a new proposal it can't record there.
- **Legacy dual-mode:** a plan with an existing full-tree record can still `scope-review`-confirm its deferrals (legacy path), and its stale record reports "needs re-sync" rather than vanishing — no regression vs. today (Architecture H).
- **Un-deferred plan:** no `concepts.json`, no `emit_concept_tree` call, no staleness anywhere.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.

## Acceptance criteria

- A plan with a pending decision remains fully usable after any unrelated prose edit: `scope-review defer` confirms it and `status` / `check_concept_coverage` act on it with no `StaleConceptTreeError` raised on any read/confirm path.
- Deleting or renaming a decision record's `bucket` surfaces that record for operator re-review — neither a silent stand nor a crash — while an edit to a section's *body* (not its name) leaves the record valid. `scope-review` can still resolve a missing-bucket record (at minimum `wont_do`); it does not hard-refuse it, so the surfaced finding is clearable (full dismiss verb → BACKLOG #132).
- A `detail`-proposed deferral is recorded pending and surfaced with its bare `node.id` token in the **two live surfaces** (`status` and the completeness report), never auto-signed under `-y`. (The `create` run-summary surface exists too but is **dormant** in this MVP — it fires only when `create` sees a flat record *already present*, i.e. a carried-in `--from-existing`/resume record, which is Deferred; a fresh `create` mints none.) The separate **interactive decline → drop** path lives in `create`'s deferral-only gate (step 2), not in `detail` (which always records `unreviewed`). **The sole operationalized proposer is `detail`'s deferral routing (step 6).** Under the lazy model `create` does *not* propose a deferral (removing `emit_concept_tree` left the bootstrap all-`include`), and a carried-in flat record via `create` resume is **not** wired here — the resume path's `rederive_concepts` merges against a full-section tree and is not specified for flat records (deferred; see Deferred). The create-decomposition "defer a branch with no live scenario" instruction still only omits from the step array (no concept) and also stays out of scope. So "confirm what the tool defers" is delivered at *detail* time; `create`'s pending-surface + run-summary exist to display any flat record already present, not because fresh `create` mints one.
- A surfaced pending decision confirmed via `scope-review defer` is rendered into `## Deferred` through the existing `render_scope_decisions` path, including on a plan edited since the deferral was recorded.
- Detail's deferral routing records a flat, bucket-tagged pending decision on a **record-absent** plan and never auto-signs it under `-y`. On a plan **already carrying a flat `decision-record`** it **merges** the new deferral in idempotently — adding a new bucket while leaving prior pending nodes untouched, treating a re-deferral of an already-`unreviewed` bucket as a no-op, and **preserving** a bucket already signed off (`approved`) rather than re-opening it to pending. On a **legacy full-tree** record it keeps the legacy behavior and, if the model proposes a *new* deferral it cannot record there, **warns** the operator that the plan's legacy record must be migrated (#131) to capture it — it does **not** silently discard the deferral.
- A **legacy full-tree** record retains full deferral-confirmation ability: `scope-review` still bootstraps + re-derives + confirms it (no hard refusal), and `check_concept_coverage` still surfaces its findings under the fingerprint guard (a stale legacy record reports "needs re-sync", not swallowed to `[]`). No existing full-tree record loses functionality (dual-mode, Architecture H).
- An un-deferred plan produces no `concepts.json`, invokes no `emit_concept_tree`, and raises no staleness on any path.
- Pending decisions surface as a flat, bucket-grouped list and are non-blocking, so an unresolved deferral does not wedge the `--iterate` convergence loop.
- The `status` surface renders, under each bucket group, a short excerpt of that bucket's current body-section text (read on demand via `parse_body_sections`), so a deferred concept is contextualized without a stored concept catalog; no sub-concept hierarchy is built (that is BACKLOG #130).

## Deferred

- Sub-concept drill / on-demand per-bucket derivation — a separate feature; the MVP is flat. **This also bounds granularity:** identity is the section name, so the MVP tracks **at most one deferral decision per body section** — two distinct concepts deferred into the same section collapse to one record (the founding-incident "none silently dropped" holds at *bucket* granularity). **Rationale on re-deferral is first-write-wins by intent:** re-proposing an already-`unreviewed` bucket is a no-op, so the first proposal's `rationale` is what renders in `## Deferred`; a later proposal's differing/richer reason is not merged in (the operator can still edit the rationale at confirm time via `scope-review`). Capturing multiple distinct concepts under one section, or merging a richer re-proposed rationale, needs finer-than-section identity — exactly the sub-concept producer of BACKLOG **#130**.
- **Carried-in flat records through `create` resume / `--from-existing`.** `create`'s resume path merges a saved record via `rederive_concepts`, which is built for full-section trees; carrying a *flat* decision record through it (preserving `record_kind`/`decision`/`bucket`, and `node.id` stability across the re-persist) is not specified here. The MVP's proposer is `detail`; a flat record recorded by an earlier run is confirmed via `scope-review` (which handles flat records directly), not re-processed through resume. Wiring resume to preserve a carried-in flat record — including the `node.id`-stability contract — is a follow-up (relates to #131's legacy-coexistence work).
- Migrating existing eager full-tree records to the flat shape — legacy stays loadable; migration is separate.
- Program-scale / authoring-time decomposition monitoring — BACKLOG #129.
