> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

<!--
  ┌─────────────────────────────────────────────────────────────────────────┐
  │ LABEL: SCHEMA CONTRACT — design note (spike output), NOT a plan/detail    │
  │        file. Do not run plan-tool commands against it; it carries no      │
  │        frontmatter and is not in the plan manifest.                       │
  ├─────────────────────────────────────────────────────────────────────────┤
  │ doc-type   : schema-contract / design-note                               │
  │ feature    : decomposition-convergence-loop (v1)                          │
  │ derived-from: docs/implementation-plans/plan-details/                     │
  │               decomposition-convergence-loop/reports/                     │
  │               20260620-235917-completeness.json (14 conceptual gaps)      │
  │ feeds      : plan-seeds/decomposition-convergence-loop.md                 │
  │ authored   : 2026-06-20                                                   │
  └─────────────────────────────────────────────────────────────────────────┘
-->

# SCHEMA CONTRACT (design note) — Decomposition Convergence Loop

> **What this is:** a one-off **schema-contract design note** (spike output), not
> a plan or a numbered step-detail file. It pins the real persisted report schema
> the `convergence` command must read, and feeds
> `plan-seeds/decomposition-convergence-loop.md`. It is intentionally outside the
> plan manifest and is never executed by plan-tool.

_Spike output feeding a re-seed of `decomposition-convergence-loop`. Resolves the
foundational mismatch the 20260620-235917 completeness audit surfaced: the plan
designed its signals first and assumed the persisted report would carry whatever
each signal needed. It doesn't. This note pins **what a saved report actually
carries**, derives the **canonical region key** and **resolved-state** rules from
those real fields, and routes each of the 14 conceptual gaps to one of four
dispositions: **consume** (use a field that exists), **derive** (compute in the
reader from fields that exist), **producer-change** (needs a write-side edit —
explicitly in or out of v1), or **cut** (drop the claim from the plan)._

## 1. Ground truth — what is actually persisted

Verified at HEAD against the source, not the prose.

### Sidecar JSON top level (`save_review`, `kind="completeness"`)
`version`, `plan_slug`, `plan_path`, `created_at` (ISO-8601 UTC),
`kind`, `step_id` (None for completeness; set only for reconcile kinds),
`plan_fingerprint`, `code_fingerprint` (opaque path→hash map),
`code_fingerprint_present`, `report_md`, `recommendations[]`, `annotations{}`.

`SavedReview` (`review_persistence.py:141`) adds `schema_version` and `path`
in-memory. **There is no `report_bytes`, no plan/detail body size, and no
per-finding BLOCKED marker.**

### `Recommendation` (`review.py:279`) — the per-finding shape
`id` (content-addressed, stable for an *unchanged* finding), `source`,
`severity`, `step_id` (**None** for `plan-completeness`/`plan-correctness`),
`title`, `body`, `suggested_action`, `impact`, `complexity`, `redirect`,
`file_path`, `anchor` (Claude-minted slug; None for deterministic/sluggless).

### What the producer drops on the floor
`cli/completeness_cmd.py:501` persists `correctness_recs + conceptual_recs`
only (`source` ∈ {`plan-correctness`, `plan-completeness`}). `det.smell_recs`
— including every `granularity-split` / `granularity-merge` finding — is passed
to presentation/markdown **only**, never to `save_review`. So the granularity
advisor's structured findings **never reach the JSON this command reads.**

### Accrual cadence
`write_completeness_report` writes **one** sidecar per `completeness`
invocation, after the `--iterate` loop converges. Intra-invocation re-audit
rounds (where spinning manifests as `--max-stall-rounds`) are **discarded**.
`skip_sidecar_write` suppresses the write entirely on an unchanged-plan reuse.

## 2. The two foundational decisions

Everything downstream hangs on these. Decide them first; the 14 gaps fall out.

### D1 — Canonical region key
A "region" is the thing recurrence counts. It must be derivable from fields that
exist and must be **stable across runs** and **comparable across kinds**.

> **Decision:** `region_key = (kind, normalized_focus)` where
> `normalized_focus = step_id` if present, else a `step<N>` token parsed from
> `anchor`, else `slugify(title)` truncated. Recurrence matching is
> **tiered**: exact `step_id`/`step<N>` match is authoritative; `anchor`
> equality is corroborating; title-similarity is the last resort.
> **No cross-`kind` region match in v1** (completeness anchors and reconcile
> `step_id`s draw from different spaces — folding them invites collisions).

This is pure **derive** — no producer change. It directly resolves
`anchor-slug-stability` (anchor demoted from authoritative to corroborating)
and `mixed-kind-region-keying` (key is `(kind, …)`, partitioned).

### D2 — What "resolved / closed" means
Recurrence counts a region only while it stays *unresolved*. The plan defined
`resolved = annotation.status == "applied"` and never consulted skips.

> **Decision (revised 2026-06-21):** a finding is **closed** only when its
> `annotations[id].status == "skip"` **and** `annotations[id].halt_reason == ""`
> (a deliberate operator WONTFIX/decline). Everything else — absent, `open`, or
> **`applied`** — counts as unresolved.
>
> **`applied` does NOT close.** The original D2 closed on `{applied, skip}`; that
> was wrong. An `applied`-yet-reappearing finding *is* the spin signature itself
> (the audit re-finds what `apply_finding` only patched around), so closing on
> `applied` would blind the detector to the exact apply→reappear loop it exists to
> catch. A genuinely-fixed finding self-suppresses by not reappearing.
>
> **A `skip` with `halt_reason == "drift"` does NOT close** — it's a pre-apply
> safety halt where no choice was made, so a region that keeps tripping the drift
> guard must stay `spinning`.
>
> Closed-state is **sticky at the region-key level, series-wide** (one deliberate
> skip suppresses the region for the whole series; the operator's WONTFIX is not
> re-asked each run).

Pure **consume** — `annotations` is already persisted per run. Resolves
`skipped-finding-recurrence`. (This decision is operationalized in step 2
`Region model & matching` and stated in the plan body's **Closed-state**
paragraph — the three are now in sync.)

## 3. Gap dispositions (all 14)

| Anchor | Disposition | Resolution grounded in §1 |
|---|---|---|
| `anchor-slug-stability` | **derive** | D1 tiered key; anchor is corroborating, not authoritative. Add the Risks entry naming Claude-authored slug instability. |
| `mixed-kind-region-keying` | **derive** | D1 keys on `(kind, …)`; no cross-kind match in v1. |
| `skipped-finding-recurrence` | **consume** | D2: `skip` is a closed state via `annotations`. |
| `history-accrual` | **document** | One sidecar per invocation after iterate converges; intra-iterate rounds not persisted. State that the N-run window counts **distinct invocations across which the plan changed** (fingerprint-gated), not iterate rounds. |
| `zero-history-case` | **derive** | New explicit `no-history` output when the reports dir is empty. |
| `insufficient-history-verdict` | **derive** | Third verdict `insufficient-history` for 1…N-1 runs — distinct from a positive `converging`. Verdict enum becomes {`insufficient-history`, `converging`, `spinning`}. |
| `monotone-growth-proxy` | **defer (v2)** | Only size in the sidecar is `len(report_md)` — measures the *report*, not the plan, so it can't honestly serve the intended "plan grows" semantics. **Decision: defer the whole monotone-growth signal to v2**, gated on a producer-change that captures plan/detail body size at save time. Not in the v1 signature. |
| `structural-blocked-signal` | **cut** | No BLOCKED marker persisted. **Decision: cut the 4th signature component** — v1 ships a recurrence + no-shrinkage signature. File "persist a per-finding BLOCKED flag" as a v2 prerequisite. |
| `granularity-split-signal` | **cut/restate** | Overview asserts granularity findings flow into history; false at HEAD (`smell_recs` dropped). Restate as forward-wired/inert in v1, matching step 3. |
| `localized-step-focus-signal` | **scope** | Step focus is reliable only from a `step<N>` anchor (recs carry `step_id=None`; `granularity-split` inert). Either mandate `step<N>`-prefixed anchors for step-scoped findings, or scope the localized claim to the granularity-backed path (post-producer-change). |
| `split-command-placeholders` | **cut** | Diagnosis knows the step, not the two concern titles. Soften the criterion to "step-targeted command with concern-title placeholders." |
| `severity-trend-output` | **derive** | `severity` is per-rec and present every run → `max_severity`/`first_seen`/`last_seen` are computable in the reader. Render them, or narrow the criterion to the run-count signal. |
| `fail-on-findings-scope` | **decide (scope)** | Pick one: pull `--fail-on-findings` into v1 body+Output (and out of Deferred), or strike it from step 4. Step 4 currently builds+tests it. |
| `min-runs-cli-tunable` | **decide (scope)** | Either add `--min-runs` in step 4, or drop the "tunable" claim from Risks/step 2. |

## 4. The producer-change fork (the real v1-scope question)

Three gaps — `monotone-growth-proxy`, `structural-blocked-signal`,
`localized-step-focus-signal`/`granularity-split-signal` — cannot be honestly
resolved by a reader-only command. Each needs the **write side** to persist data
it currently drops. The clean v1 boundary is:

- **v1 = consume + derive only.** Build the reader against the schema as it
  exists today. The v1 signature is **two signals: recurrence + no-shrinkage**
  (monotone-growth and structural-`[BLOCKED]` are both cut/deferred per §3). The
  localized fork fires only on `step<N>` anchors; granularity is described as
  forward-wired/inert.
- **Deferred (needs producer-changes), each a prerequisite, not a nice-to-have:**
  1. persist `det.smell_recs` (or just `granularity-*`) into the sidecar →
     unlocks reliable step focus + the granularity-backed localized path;
  2. persist a per-finding BLOCKED flag → unlocks the structural-`[BLOCKED]`
     signature component (v2);
  3. capture plan/detail body size at save time → unlocks the *intended*
     monotone-growth proxy (v2).

The audit's own "spinning" frame applies recursively: closing these 14 by
softening prose is patch-around-a-stuck-region. The honest cut is to **shrink v1
to what the present schema supports** and file the three producer-changes as
named prerequisites for v2's stronger signals.

## 5. Re-seed checklist

When authoring the next seed (`create --from-existing`):

1. State the **real** `SavedReview`/`Recommendation` field set (§1) as the
   command's input contract — verbatim, not aspirational.
2. Adopt D1 (canonical region key) and D2 (closed-state) as named invariants.
3. Make the verdict **ternary** (`insufficient-history` / `converging` /
   `spinning`) and define the `no-history` and sub-threshold outputs.
4. Scope v1 to consume+derive; list the three producer-changes (§4) as Deferred
   prerequisites with the signals each unlocks.
5. Resolve the two pure-scope toggles (`--fail-on-findings`, `--min-runs`) one
   way and keep body, Output, Deferred, and step 4 in agreement.
