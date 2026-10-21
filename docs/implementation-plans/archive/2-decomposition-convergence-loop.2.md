> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Decomposition Convergence Loop
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add convergence_diagnosis.py reader + normalized history model (ReportHistory/RunSnapshot/RunFinding)
    with committed fixture
  creates:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  - tests/fixtures/convergence/sample-report-history.json
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/decomposition-convergence-loop/01-convergence-diagnosis-py-reader.md
  status: done
- id: 2
  title: Region model & matching (tiered key + closed-state + per-region trend)
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/decomposition-convergence-loop/02-region-model-matching-tiered-key-closed.md
  status: done
- id: 3
  title: Signature & verdict (M-of-N recurrence + no-shrinkage + four-state)
  complexity: high
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/decomposition-convergence-loop/03-signature-verdict-recurrence-no.md
  status: done
- id: 4
  title: Add localized-vs-structural fork classifier + render_diagnosis output (four-state,
    severity trend, pre-filled command, fill-in --into placeholders, ambiguous→cautious
    re-seed, step<N>-anchor-only caveat)
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/decomposition-convergence-loop/04-localized-vs-structural-fork-classifier.md
  status: done
- id: 5
  title: Register read-only `plan-tool convergence` subcommand across app.py/parser.py/__init__.py
    + generated docs (cmd_status pattern, zero Claude, exits 0; no --fail-on-findings/--min-runs)
  files:
  - plan_tool/cli/app.py
  - plan_tool/cli/parser.py
  - plan_tool/cli/__init__.py
  - docs/cli/README.md
  - tests/cli/package_surface_help.golden.txt
  creates:
  - plan_tool/cli/convergence_cmd.py
  - tests/cli/test_convergence_cmd.py
  - docs/cli/convergence.md
  complexity: medium
  change_type: feature
  gate:
  - uv run plan-tool convergence --help >/dev/null && uv run plan-tool --help | grep
    -q convergence
  - test -z "$(uv run plan-tool convergence --help 2>&1 | grep -E -- '--fail-on-findings|--min-runs')"
  depends_on:
  - 4
  detail: docs/implementation-plans/plan-details/decomposition-convergence-loop/05-register-read-only-plan-tool.md
  status: done
- id: 6
  title: 'Document the convergence diagnostic in RUNBOOK (### under completeness-checks
    workflow) + one CLAUDE architecture paragraph, and trim BACKLOG #57 to its deferred
    remainder'
  files:
  - RUNBOOK.md
  - CLAUDE.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  gate:
  - grep -q 'plan-tool convergence' RUNBOOK.md && grep -q convergence CLAUDE.md
  depends_on:
  - 5
  detail: docs/implementation-plans/plan-details/decomposition-convergence-loop/06-document-convergence-diagnostic-runbook.md
  status: done
---
# Decomposition Convergence Loop

## Overview

Add a read-only command — **`plan-tool convergence <plan>`** — that reads a plan's saved completeness/reconcile report history, detects when the audit/apply loop is **spinning instead of converging**, and prints a recommendation **forked by the failure's shape**: a *localized* over-pack (one step doing too much) recommends an in-place re-split; a *structural* / cross-step problem (the decomposition itself is wrong) recommends authoring a fresh `create` seed and re-decomposing. v1 is the lean form: a read-only diagnostic that mutates nothing, writes no files, and spends **zero Claude** (it analyzes report JSON already on disk). It prints a four-state verdict and a forked recommendation; completion exits 0 regardless of verdict (exit-code convention). The producer-side changes that would unlock stronger signals are parked in `## Deferred`. (BACKLOG #57.)

> **Why this re-seed exists.** The prior plan (`docs/implementation-plans/2-decomposition-convergence-loop.md`) was authored against an *imagined* report schema. A completeness audit surfaced 14 gaps that nearly all reduce to one root cause — the persisted `SavedReview` does **not** carry granularity findings, a BLOCKED flag, plan/detail body size, reliable step ids, or guaranteed-stable anchor slugs. This seed pins v1 to **what the present schema actually supports** and files the write-side changes the stronger signals need as named v2 prerequisites. The design analysis is in `docs/implementation-plans/plan-details/decomposition-convergence-loop/decomposition-convergence-loop.schema-contract.md`.

## Problem statement

**The pipeline converges on content, never on structure.** Every convergence loop the tool has — `create --iterate`, `detail --iterate`, `completeness --iterate` — closes over plan/detail **content**. **None closes over step boundaries.** Decomposition is decided once, by `create`, in a single round-trip, at the moment of *least* information in the pipeline (before any detail file exists, before the audit has read code at HEAD), and then frozen.

The audit later *acquires* that information and *detects* boundary problems — purity findings, size findings, a branch with no live scenario. But its only repair move is `apply_finding`, which edits **prose**: it cannot delete a concern, move it to another step, drop dead wiring, or re-split. So it patches *around* the mis-decomposition by adding prose, which grows the plan and feeds the next audit more surface — it re-finds the same problem under a new anchor every pass and never converges, all while reporting `no_blocking_findings`/converged and overstating soundness.

Today the only thing that closes this gap is a **human** noticing the non-convergence, diagnosing it, and re-running `create` with a hand-tuned seed (see the "When repeated audit/apply doesn't converge" workflow in `RUNBOOK.md`, and the worked re-seed at `plan-seeds/archive/escalate-structural-findings-to-split-redecomposed.replaced.md`). That human step is the missing pipeline edge: **audit-detects-bad-decomposition → re-decompose.** v1 automates the *detection and recommendation* half of it.

## Architecture

**One module + a thin CLI seam.**

- **`plan_tool/convergence_diagnosis.py`** (orchestrator leaf): read report history → detect signature → classify localized vs. structural → render the forked recommendation. Pure logic, no `invoker` (v1 spends no Claude). Keep it a leaf below the CLI; lazy-import report parsing if it would close a cycle.
- **`plan_tool/cli/convergence_cmd.py`** (thin handler, registered in `parser.py`).

**Input contract — what a saved report actually carries.** v1 is a reader designed against the real persisted schema, not an assumed one. A saved completeness/reconcile sidecar (`SavedReview`, `kind="completeness"` | `"detail-reconcile"` | `"run-reconcile"`) carries at top level: `plan_slug`, `plan_path`, `created_at` (ISO-8601 UTC), `kind`, `step_id` (None for completeness; set for reconcile kinds), `plan_fingerprint`, `code_fingerprint`, `code_fingerprint_present`, `report_md`, `recommendations[]`, and `annotations{}` (the operator's per-finding walk decisions). Per `Recommendation`: `id` (content-addressed, stable only for an *unchanged* finding), `source`, `severity`, `step_id` (**None** for `plan-completeness` / `plan-correctness`), `title`, `body`, `suggested_action`, `impact`, `complexity`, `redirect`, `file_path`, `anchor` (Claude-minted slug; may be None; only *encouraged* stable across re-audits, never guaranteed). The default `"review"` kind that `reconcile-plan` persists (a suffixless `<ts>.json`) exists but is **intentionally outside the convergence window** — only completeness/reconcile kinds are read, and the `*-completeness.json` / `*-reconcile.json` glob and the contract list above deliberately exclude plain-review sidecars.

What is **not** present, and therefore cannot back a v1 signal: granularity / `smell_recs` findings, a per-finding BLOCKED marker, plan-body or detail-body byte size (the only size available is `len(report_md)`, which measures the *report*, not the plan), and a reliable per-finding step id for audit findings.

**The non-convergence signature — two deterministic signals.** Both signals and the rendered severity trend are scoped to **apply-eligible sources** (`plan-correctness` and the reconcile findings): advisory `plan-completeness` recs are excluded from recurrence counting, from no-shrinkage counting, and from the trend display alike. The persisted sidecar concatenates `correctness_recs + conceptual_recs`, but the `--iterate` loop only applies `plan-correctness` — advisory `plan-completeness` gaps are *never* applied by design, so they reappear in every sidecar and never shrink; counting them would make any plan with a stable advisory gap read `spinning` regardless of structural health. On top of that source filter, both signals apply **one shared `medium+` severity floor**: sub-`medium` (`nit` / `info`) findings are excluded from recurrence counting, from no-shrinkage counting, and from the trend display alike. A region recurring only at `nit` / `info` (or only via an advisory `plan-completeness` rec) thus contributes to none of the three, keeping the recurrence count, the shrinkage signal, and the displayed trend mutually consistent. **The floor reads persisted severity, in which `medium` already subsumes operator-`LOW`:** `review.py`'s `_CLAUDE_SEVERITY_MAP` folds Claude's authored `LOW` → `"medium"` at save time (matching the launcher's verdict line), so by the time the detector applies the `medium+` floor a `LOW`-authored finding has already cleared it — the floor's real cut is between `nit`/`info` and everything Claude authored at `LOW` or above. v1 **accepts folded-`LOW` recurrence** rather than raising to a `high+` floor: the fold is lossy and irreversible at the sidecar, so a `high+` floor cannot recover operator-`LOW` without also discarding genuine operator-`MEDIUM` structural findings, and the cautious-default principle (a read-only advisory leaning toward `spinning`) tolerates the residual risk of a recurring cosmetic-but-`LOW` finding contributing to a verdict over the larger risk of suppressing a real medium structural spin.

- **Region recurrence** (primary) — the same *region* re-flagged at **medium+** (the shared floor) without being **closed** across an **M-of-N trailing window** (recurs in at least M of the last N runs, rather than requiring a strict consecutive streak). The M-of-N window applies a **uniform** one-missed-run tolerance to every v1 series (`recurrence_min = max(1, window - RECURRENCE_TOLERANCE)`, default N=3 → M=2), not a per-`kind` gate. Although each `completeness`-kind run is a *full* audit (one sidecar written after the iterate loop converges), the audit is Claude-driven and non-deterministic, so a region's absence in a single run is **not** conclusive evidence it was resolved — the audit may simply have failed to re-surface it that pass. Tolerating one missed run guards against a flaky-absent run masking a genuine spin, leaning toward `spinning` per the cautious-default principle; the rarer cost is briefly flagging a just-resolved region, acceptable for a read-only advisory verdict.
- **No shrinkage** — open medium+ finding count fails to trend down across the window, evaluated over the region's **sampled runs** (the runs in which the region actually appears) — or a monotone-trend test across those runs — **not** the two raw endpoints. An endpoint rule (`counts[-1] >= counts[0]`) misreads a region absent from the *final* run as shrinkage (`counts[-1] == 0 < counts[0]` → `converging`) exactly when **Region recurrence** (which tolerates one missed run) still trips, silently flipping the verdict to healthy on a missed final audit; it also ignores the trajectory it claims to measure (both `2,3,3,2` and `1,3,3,1` read no-shrink despite their differing trajectories). Sampling the region's own appearances (or testing the trend across them) keeps the two `spinning` signals consistent (stated on its own terms, *not* claimed equivalent to `convergence.py`'s consecutive-stall semantics). Evaluate shrinkage on **the recurring region's own** open-count, not only the global count: a plan genuinely stuck on one over-packed step while resolving unrelated peripheral findings (global count trending down) must still read as `spinning` on that region. A region's **per-run open-count is the number of distinct open medium+ findings sharing its region key in that run** (deduped by finding id) — a count that can vary only when more than one finding maps to the same region. For a single-identity title-tier region — which the canonical-region-key design names the *primary* matcher for the `step_id=None` `plan-correctness` findings that drive `spinning` — exactly one finding identity maps to the region, so its per-run count is `1` in every sampled run and can never trend down; **no-shrinkage is vacuously true there and adds independent signal only for multi-finding step-focused regions** (where several distinct findings cluster on one step id). For single-identity regions the verdict therefore rests on **recurrence alone**, and the output must not claim no-shrinkage separately corroborated it.

**Canonical region key.** `region_key = (kind, normalized_focus)` where `normalized_focus` is, in priority order: the finding's `step_id` if present, else a `step<N>` token parsed from `anchor`, else the full concept-slug `anchor` itself, else a truncated slug of `title`. Recurrence matching is **tiered**: an exact `step_id` / `step<N>` match is authoritative; full concept-slug `anchor` equality is **also authoritative** (the audit prompt re-uses a concept-slug anchor verbatim across re-audits, so a stable anchor — not only a `step<N>` token — anchors recurrence, and a re-slugged gap must not silently break the streak); title-similarity is the last resort. **For the `step_id=None` audit findings (`plan-correctness`) the Problem statement says drive spinning, the title tier is in practice the *primary* matcher, not a fallback:** tier 1 (step focus) is unavailable because those findings carry no `step_id`, and tier 2 (anchor equality) holds only when Claude re-mints an identical anchor — which the Problem statement's "re-finds the same problem under a **new anchor** every pass" warns it often does not. The title tier therefore carries the recurrence load for completeness findings whenever the anchor drifts. The title tier is a fuzzy `difflib.SequenceMatcher.ratio()` comparison (not exact-slug equality): two findings share a title-tier region when `ratio()` between their normalized title slugs is `>= 0.85`. The `0.85` cutoff is chosen because a re-worded *anchor* (slug churn) leaves the human-readable `title` largely intact — the audit re-describes the *same* structural defect, so the title slug typically differs by a few tokens (re-ordering, a dropped article), well above `0.85`; the cutoff tolerates that incidental drift while rejecting two genuinely distinct findings (whose titles share far less). Because both anchor and title *can* drift together, the cutoff is a calibration knob, not a guarantee: the fixture tests bound the false-negative rate when both fields drift by pinning a re-worded-title pair that must still match (`ratio() >= 0.85`) and a genuinely-distinct-finding pair that must not. A new finding is matched greedily against the representative (first-seen) title slug of each existing title-tier region in run order, joining the first region that clears the cutoff and seeding a new region otherwise — pairwise against representatives, not all-pairs clustering — so the rule is deterministic and reproducible. **No cross-`kind` region match in v1** — completeness anchors and reconcile step ids draw from different spaces, so the series is partitioned by `kind`. **Reconcile-kind series partition by `(kind, step_id)`, not `kind` alone** — each `detail-reconcile` / `run-reconcile` sidecar carries a `step_id` for a *single* audited step, so a window of reconcile runs is a sequence of per-step audits; partitioning on `kind` alone would let the M-of-N window compare findings on different steps and fabricate recurrence. Partitioning each reconcile series by `(kind, step_id)` keeps the window comparing audits of the same step. (`completeness`-kind sidecars carry `step_id=None`, so their partition key is simply `kind`.)

**Closed-state.** A finding is **closed** only when `annotations[id].status == "skip"` **and** `annotations[id].halt_reason == ""` (a deliberate operator decline). Anything else — absent, `open`, or `applied` — counts as unresolved, because an `applied` finding that *reappears* in a later run is the spin signature itself (the audit re-finds what `apply_finding` only patched around) and must keep accumulating recurrence; a genuinely-fixed finding self-suppresses by not reappearing. Only a deliberate `skip` (WONTFIX / acknowledged-and-deferred) suppresses recurrence and must not drive a `spinning` verdict. **Closed-state is sticky at the region-key level and scoped series-wide, not per-run per-`id` and not trailing-window:** because ids/anchors drift across re-audits (the very reason recurrence keys on the fuzzy region key), once *any* run in the **whole series** carries a deliberate `skip` for a finding that maps to a region, that **region** is treated as closed for the entire series — the operator's WONTFIX need not be re-skipped on every subsequent run. A region the operator skipped once stays suppressed even when it reappears later with a fresh `id` and no annotation. **Contract split between steps 2 and 3:** step 2 (`Region model & matching`) owns and computes this series-wide sticky `closed` flag over the full series it is passed (a `skip` anywhere in history suppresses the region permanently — the intended "WONTFIX stays" semantics); the **trailing-window** scope belongs solely to step 3 (`Signature & verdict`), which applies the M-of-N window to the *recurrence* signal alone. Closed-state is deliberately broader than the recurrence window, so a WONTFIX recorded before the window still suppresses a region the window would otherwise read as spinning. A `skip` carrying `halt_reason == "drift"` is **not** closed — it is a pre-apply safety halt where no apply landed and no choice was made, so the region stays unresolved for recurrence and a region that keeps tripping the drift guard run after run must still read as `spinning`. **Closed-state suppression depends on walk-produced annotations.** Only the separate interactive `completeness-apply` walk populates `annotations{}` (via `update_annotation`); `write_completeness_report` → `save_review` persists the sidecar with **empty** annotations, so under the mandated `--iterate` workflow nothing records a `skip`. v1's closed-state suppression therefore applies only to history that has been through an interactive apply-walk; on iterate-only history every region reads as unresolved and a deliberately-deferred region can still drive a `spinning` verdict. Persisting the iterate disposition as annotations is the producer-side fix (see `## Deferred`).

**How history accrues.** `write_completeness_report` writes **one** sidecar per `completeness` invocation, after the `--iterate` loop converges; the intra-invocation re-audit rounds are **discarded**. The `skip_sidecar_write` reuse-skip (`reused_audit_recs is not None and not budget.enabled`) fires **only under `--no-iterate`** audit-reuse; under the mandated `--iterate` workflow `budget.enabled` is True, so every invocation rewrites a fresh post-apply sidecar regardless of whether the plan changed. So the N-run window counts **distinct `completeness`/reconcile invocations** — not iterate rounds. A single `completeness --iterate` leaves history length 1, and the diagnostic only has signal after ≥N separate invocations.

**Verdict — four-state, not binary,** so "no data" is never mistaken for "healthy": `no-history` (reports dir missing/empty), `insufficient-history` (1…N-1 saved runs that are *not* yet a converged-and-stable streak; below threshold and still churning, reads as "not enough data", *not* a reassuring `converging`), `converging` (the signature does not trip and the plan reads converged-and-stable), `spinning` (≥N runs and recurrence + no-shrinkage both trip). **`converging` does not require ≥N saved runs.** Under `--iterate` a converged plan keeps rewriting a fresh post-apply sidecar each invocation (the `skip_sidecar_write` reuse-skip fires only under `--no-iterate`), so a hard ≥N floor is unnecessary for liveness — but path (b) still earns the positive verdict **one invocation sooner**, certifying a fingerprint-stable, recurrence-free streak as `converging` without waiting for the Nth separate run. So `converging` is certified by either path: (a) ≥N runs and the signature does not trip, **or** (b) a **fingerprint-stable streak with no recurrence** — the trailing runs share an identical `plan_fingerprint` (and `code_fingerprint`, when present) with no medium+ region recurring across them, evidencing a plan the audit/apply loop has stopped changing. Path (b) is what distinguishes converged-and-stable (`converging`) from genuinely-too-little-data (`insufficient-history`): a sub-threshold history whose latest runs are fingerprint-stable and recurrence-free reads `converging`, while a sub-threshold history still mutating run-to-run reads `insufficient-history`.

**Combining per-kind verdicts.** Because the series is partitioned by `kind` (no cross-`kind` region match), each `kind` is diagnosed independently and yields its own four-state verdict. The plan's single headline verdict is the **least-confident** verdict across its per-kind series, ordered `spinning` > `insufficient-history` > `converging` > `no-history`. A `converging` kind may **not** override an `insufficient-history` kind in the headline: `insufficient-history` deliberately outranks `converging` so a sub-threshold, still-churning kind is never masked by a healthy one, honoring the no-overstatement acceptance criterion. `no-history` ranks lowest because a kind with no reports is mere absence, not churn, and so cannot drag down a genuine signal (and a kind with no/sub-threshold history still cannot mask a `spinning` kind). The render shows the headline verdict followed by the per-kind breakdown beneath it, so a `completeness` series reading `converging` while `detail-reconcile` reads `spinning` reports headline `spinning` with both kinds named.

**The fork.** On `spinning`, classify the recurring region and recommend the matching repair: a **localized over-pack** (recurrence concentrates on a single step focus, the rest of the plan quiet) recommends an in-place re-split `plan-tool split <plan> --step N --into "<a>" --into "<b>"` (or interactive `detail --split`) — surgical, 1→2, preserves the other detail files and run state, the path `plan-tool split` (`cmd_split`, registered in `cli/authoring.py`) executes; a **structural / cross-step** problem (recurrence spans ≥2 distinct step foci) recommends authoring a fresh seed and re-decomposing `create --from-existing <seed> --iterate`. A 1→2 split can't fix the structural case; it's N-way.

> **v1 caveat — localization fires only on a `step<N>` anchor.** Because audit findings carry `step_id=None` and granularity (`step_id`-bearing) findings aren't persisted, the only reliable step focus in v1 comes from a Claude-minted `step<N>`-prefixed anchor. A genuine single-step over-pack slugged by concept (e.g. `over-packed-step`) yields no focus → ambiguous → cautious structural re-seed. v1 must **state this limitation honestly**. The localized branch fires only when **every** recurring region resolves to one concrete step number; any anchor-unresolvable (concept-only) region — even a single one in the minority — forces the cautious structural re-seed. When genuinely ambiguous, v1 says so and recommends the more cautious re-seed (mirroring the `direct`-vs-`plan-tool` heuristic's "when unsure, author a plan").

**Read the report history.** Glob `docs/implementation-plans/plan-details/<slug>/reports/*-completeness.json` (and `*-reconcile.json` if present), ordered by `created_at`, breaking ties on equal `created_at` by filename lexical order (the second-precision timestamp filename is already lexically sortable) so two sidecars written in the same second order deterministically at a trailing-window boundary. Partition per `kind`, and split each reconcile-`kind` series further by `step_id` so the window compares audits of the same step. For each run collect: open findings with their `anchor`, `step_id`, `severity`, the canonical region key, and the run's `annotations`. Build a per-region recurrence-and-severity trend across runs.

**Output.** Print to stdout: the four-state verdict, the recurring region(s) with their run-count **and severity trend** (`max_severity` / first→last seen — computed over the same **medium+** findings the two signals count, never sub-`medium` ones, and **must be rendered**, not just computed), and the matched recommendation with the command pre-filled, e.g.:

```
spinning — step 5 re-flagged in 4 of the last 4 audits, no shrinkage (severity medium→high)
  shape: localized over-pack (recurrence on a single step)
  → plan-tool split escalate-structural-findings-to-split --step 5 \
        --into "<first concern>" --into "<second concern>"
```

or, for the cross-step shape:

```
spinning — recurrence spans 3 distinct step foci (steps 4,5,7)
  shape: structural (the decomposition itself is wrong)
  → re-decompose: author a fresh seed and run
        create --from-existing <seed> --iterate
```

The localized `--into "<…>"` titles are **fill-in placeholders** (the diagnosis knows *which* step is over-packed, not the two concern titles to split into); the output must frame them as such, not as fully copy-paste-ready.

**Flags.** Preserve the exit-code convention: a completed diagnosis exits 0 regardless of verdict. **v1 ships no `--fail-on-findings` and no `--min-runs` flag** — the spin threshold N is a detector keyword (default 3) used for testing, not an operator-facing flag, and "tunable" is not advertised. Both flags are in `## Deferred`.

**Open question — standalone command vs. completeness-report section.** v1 assumes a standalone `plan-tool convergence <plan>`. The signature is most useful surfaced *exactly when it trips* — as a short "Convergence diagnosis" section the completeness report prints after K stalled runs. The report-JSON history reader and recurrence logic are the same either way. v1 leans standalone (smaller surface, no completeness coupling), with the report section as the first Deferred follow-up.

## References

- [argparse — Parser for command-line options, arguments and sub-commands (Python docs)](https://docs.python.org/3/library/argparse.html) — The stdlib subcommand-parser reference for wiring the new `plan-tool convergence <plan>` handler into `parser.py` via add_subparsers/set_defaults.
- [glob — Unix style pathname pattern expansion (Python docs)](https://docs.python.org/3/library/glob.html) — Reference for globbing the `reports/*-completeness.json` / `*-reconcile.json` report history that the diagnostic reads off disk.
- [json — JSON encoder and decoder (Python docs)](https://docs.python.org/3/library/json.html) — Reference for defensively parsing the persisted `SavedReview` sidecars (recommendations[], annotations{}) the detector analyzes.
- [datetime — Basic date and time types (Python docs)](https://docs.python.org/3/library/datetime.html) — Covers `datetime.fromisoformat()` and its ISO-8601 limitations, needed to order the report history by `created_at` for the M-of-N trailing window.
- [difflib — Helpers for computing deltas (Python docs)](https://docs.python.org/3/library/difflib.html) — SequenceMatcher.ratio() reference backing the title-similarity last-resort tier of the canonical region-key matching.
- [How to use temporary directories and files in tests (pytest docs)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — The `tmp_path` fixture and marker usage an implementer needs to write the hermetic unit and `@pytest.mark.integration` fixture tests against the real schema.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Auto-executing any repair.** v1 diagnoses and recommends; it never splits a step, edits a plan, or authors a seed. (Auto-split behind an opt-in is Deferred and must obey the never-mutate-structure-unattended invariant.)
- **Re-running the audit.** v1 reads *saved* reports; it spends no Claude and triggers no new audit.
- **A new code checker or a new finding source.** This analyzes the *history of findings the audit already produced*; it adds no new audit of plan or code.
- **Any producer-side (write) change.** v1 is a pure reader of the schema as it exists today. Every change to *what gets persisted* is a v2 prerequisite (see `## Deferred`).

## Risks

- **False "spinning" on a plan that's legitimately mid-authoring.** Severity: UX. Mitigation: require N≥3 runs and an M-of-N-within-window recurrence rule before declaring spinning (a uniform one-missed-run tolerance absorbs the audit's non-determinism — a Claude-driven full audit may drop a real finding for a single pass — leaning toward `spinning` per the cautious-default principle), plus the `insufficient-history` verdict for sub-threshold histories.
- **Claude-authored anchor-slug instability.** Severity: medium. Anchors are only *encouraged* stable across re-audits, so a re-slugged gap could scatter recurrence across keys and suppress a true `spinning`. For the `step_id=None` `plan-correctness` findings that drive spinning, tier 1 (step focus) is unavailable and tier 2 (anchor equality) fails on exactly this re-slug, so the fuzzy **title tier becomes the primary matcher**, not a fallback. Mitigation: the `0.85` `SequenceMatcher.ratio()` cutoff tolerates a re-worded anchor because the human-readable `title` re-describes the same defect and drifts far less than the slug; the residual risk is both anchor *and* title drifting together, bounded by fixture tests that pin a re-worded-title pair (must still match) against a distinct-finding pair (must not).
- **Skip-deferred regions read as spinning.** Severity: medium. Mitigation **(apply-walk history only):** the closed-state rule counts only `skip` as closed via each run's `annotations` (an `applied`-yet-recurring finding stays open, as it must). This guard is **inert on iterate-only history** — under the mandated `--iterate` workflow `write_completeness_report`→`save_review` persists empty annotations (only the interactive `completeness-apply` walk records a `skip`), so no region is ever closed and a deliberately-WONTFIX'd recurring region can still read `spinning`; closing that gap awaits the deferred "persist iterate disposition as annotations" producer-change.
- **Mis-forked recommendation.** Severity: wasted work. Mitigation: on an ambiguous classification, default to the cautious re-seed and *say it's ambiguous* — recommend-only keeps the operator in the loop.
- **Report-schema drift.** Severity: low. Mitigation: read defensively (tolerate missing fields) and pin the fields the detector depends on with a fixture test.
- **Never-applied advisory recs faking `spinning`.** Severity: high. The sidecar concatenates `correctness_recs + conceptual_recs`, but `--iterate` only applies `plan-correctness`, so a stable advisory `plan-completeness` gap recurs and never shrinks. Mitigation: scope both signals and the trend to apply-eligible sources (`plan-correctness` / reconcile findings), excluding advisory `plan-completeness` recs from driving the verdict.
- **Import-cycle pressure.** Mitigation: keep `convergence_diagnosis.py` a leaf below the CLI; lazy-import report parsing if needed.

## Testing

Pin the detector against the **real persisted `SavedReview` schema** with fixture tests (not an assumed shape), so report-schema drift is caught — read defensively and assert on the specific fields the detector depends on (`recommendations[].anchor`/`step_id`/`severity`, `annotations[id].status`, `kind`, `created_at`). Default to unit tests on `convergence_diagnosis.py`: the four-state verdict logic, the M-of-N recurrence window (including the one-missed-run tolerance), the no-shrinkage rule evaluated over a recurring region's own sampled runs (a region absent from the final run must not fake convergence; a plan with global count trending down but one region stuck must still read `spinning`), the canonical `(kind, step_id || step<N> || title-slug)` region key with tiered matching and no cross-kind folding, the closed-state rule (only `skip` closes a region; an `applied`-yet-recurring finding stays open and drives `spinning`; a skipped region does not), and the localized-vs-structural fork including the ambiguous→cautious-re-seed default and the `step<N>`-anchor-only localization caveat. Cover the history-accrual boundary cases: `no-history` (empty/missing reports dir), `insufficient-history` (1…N-1 runs). Add an `@pytest.mark.integration` test only for the CLI wiring — driving `plan-tool convergence <plan>` through `main([...])` to assert it reads the globbed report history, prints the rendered verdict + severity trend + pre-filled recommendation, spends zero Claude, writes no files, and exits 0 regardless of verdict.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan-tool convergence <plan>` reads the saved completeness report history and prints a **four-state** verdict (`no-history` / `insufficient-history` / `converging` / `spinning`) — never reporting a *still-churning* sub-threshold or never-audited plan as a positive `converging`, while certifying a converged-and-stable plan (a fingerprint-stable, recurrence-free streak) as `converging` even when it has fewer than N saved runs (a genuinely converged plan stops accruing history, so the positive verdict must not require ≥N runs).
- The signature is **recurrence + no-shrinkage** only; the output renders each recurring region's run-count **and** its cross-run severity trend.
- Recurrence keys on the canonical `(kind, step_id || step<N> || anchor-slug || title-slug)` region key, treats full concept-slug anchor equality as authoritative (above title-similarity), and does not match across kinds.
- On **apply-walk history**, a region the operator **skipped** (`annotations[id].status == "skip"` **and** `annotations[id].halt_reason == ""`, a deliberate decline) is treated as closed and does not drive `spinning`; a `skip` carrying `halt_reason == "drift"` (a pre-apply safety halt where no choice was made) is **not** closed. On iterate-only history (the mandated `--iterate` workflow persists empty annotations) this suppression is inert — no region is closed — until the deferred "persist iterate disposition as annotations" producer-change lands.
- On `spinning`, it classifies the shape (localized vs. structural) from the report data and prints the matched recommendation; the localized `split` command's `--into` concern titles are presented as fill-in placeholders, not as fully copy-pasteable.
- An ambiguous classification recommends the cautious re-seed and labels itself ambiguous (never a confident wrong split).
- The command spends **zero Claude calls** and writes no files (read-only).
- v1 ships **no** `--fail-on-findings` and **no** `--min-runs` flag; completion exits 0 regardless of verdict (exit-code convention).
- `convergence_diagnosis.py` adds no import cycle.

## Deferred

- **Persist `smell_recs` (granularity-split / -merge) into the completeness sidecar** (producer-change) — v2 prerequisite that unlocks a reliable per-step focus and the granularity-backed localized path, broadening the localized fork beyond `step<N>`-prefixed anchors.
- **Persist a per-finding BLOCKED marker** (producer-change) — v2 prerequisite that restores the structural-`[BLOCKED]` signature component (the strongest structural signal), cut from v1 because it isn't readable today.
- **Capture plan/detail body size at save time** (producer-change) — v2 prerequisite that restores the *intended* monotone-growth signal (plan grows run over run), which the current `report_md`-only size cannot honestly serve.
- **`--min-runs` flag** — expose the spin threshold N as an operator-tunable flag (the detector already takes it as a keyword); out of v1's minimal surface.
- **`--fail-on-findings`-style CI gate** — flip rc non-zero when a plan has been spinning for ≥N runs, so CI can block "this plan isn't converging." Out of v1 (exit-code convention; advisory only).
- **Persist iterate disposition as annotations** (producer-change) — v2 prerequisite that records each `--iterate` round's applied/skipped findings into the sidecar's `annotations{}` (today only the interactive `completeness-apply` walk does), so closed-state suppression works on iterate-only history and a deliberately-deferred region under the mandated `--iterate` workflow stops driving a false `spinning`.
- **Per-iteration sidecar persistence** — optionally persist each iterate round's report so a single `completeness --iterate` run is diagnosable, rather than requiring ≥N separate invocations to accrue history.
- **Surface the diagnosis as a "Convergence diagnosis" section of the completeness report** after K stalled runs (the open-question follow-up).
- **Opt-in auto-execution of the *localized* split** — wire the recommendation into `plan-tool split` (`cmd_split`) behind an explicit flag + TTY gate. Never the structural/re-seed path, and never unattended.
- **Cross-plan sweep** — run the diagnosis over every registered plan (a backlog-health view).
- **Claude-assisted classification** for genuinely ambiguous localized-vs-structural cases — only if the deterministic classifier proves insufficient in practice.
