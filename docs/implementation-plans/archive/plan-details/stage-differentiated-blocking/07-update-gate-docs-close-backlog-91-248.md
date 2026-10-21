> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Update the gate docs and close BACKLOG 91 and 248

## Summary

Document the shipped two-bar completeness policy and mid-run steering so operators and assistants can find it beside the existing severity-aware stopping rule and `is_blocking_impact` boundary. Touch five docs only: `integrations/shared/DIRECTIVES.md` (operator canonical), `CLAUDE.md` (assistant dev repo), `docs/AUDIT_FLOW.md` (flow + source map), `RUNBOOK.md` (recipes and CI wording), and `BACKLOG.md` (partial closure + follow-up filing). The main design choice is **split ownership**: predicate semantics and gate bars live in DIRECTIVES and AUDIT_FLOW; the three-predicate boundary (`is_blocking` / `is_blocking_finding` / `is_blocking_impact`) lives in CLAUDE.md; RUNBOOK updates operator commands without restating the full bar table. Green means stale “flat medium+” completeness-gate prose is gone from those files, the bars are discoverable next to the stopping rule, and #91/#248 are **partially closed** with remaining work routed to new/existing backlog entries (#260 reporting polish, new four-loop consistency entry).

## Table of Contents

- [Why](#why) — docs still describe severity-only completeness blocking after steps 1–6 land.
- [Input](#input) — symbols and behavior steps 1–6 ship that this step must describe accurately.
- [Files (creates vs edits)](#files-creates-vs-edits) — the five declared paths and what each gains.
- [Implementation](#implementation) — per-file edit shape, ownership, and vocabulary sweeps.
- [Tests](#tests) — non-code verification checklist.
- [Acceptance criteria](#acceptance-criteria) — grep-able doc and backlog outcomes.
- [References](#references) — typing docs (plan-level carryover).
- [Applicable guardrails](#applicable-guardrails) — scope fence for this docs-only step.
- [Deferred](#deferred) — reporting polish and out-of-plan follow-ups this step only points at.

## Why

Steps 1–6 add `classify_finding_domain`, stage-aware `is_blocking_finding`, hoisted `audit_stage`, pass-conformance + `conceptual_bar_blocking_ids`, mid-run `terminal_hand_apply` steering, and bar-aware finalize/`--json`/`--fail-on-findings` — but HEAD gate docs still read as if completeness blocking is severity-only (`medium+` everywhere) and both audit gates share one bar. `integrations/shared/DIRECTIVES.md` documents Gate 1/Gate 2 and the manual loop but not the stage discriminator; `RUNBOOK.md` still tells CI to use `--fail-on-findings` for “medium+ findings”; BACKLOG #91 and #248 remain **not started / blocked together** even though this plan ships their coupled predicate. Without this step, operators keep misreading a clean bare gate, assistants conflate `is_blocking_impact` with the stage bar, and backlog triage still blocks on work that core execution discharges.

## Input

**From steps 1–2** (land before this step runs; cite modules that exist at HEAD — symbols below are step deliverables, not pre-existing anchors):

- `plan_tool/review.py` — delivers `classify_finding_domain` and `FINDING_DOMAIN_*` (step 1); detail-stage domain demotion input.
- `plan_tool/convergence.py` — delivers `is_blocking_finding`, `STAGE_BARE`, `STAGE_DETAIL` (step 2); bare bar = source axis + severity (no domain call); detail bar = domain on conceptual mediums via injected `classify_domain`. Keep existing `is_blocking` / `is_blocking_impact` **unchanged**; docs must keep them separate from the stage bar.

**From step 3:**

- `plan_tool/cli/completeness_phases.py` — delivers `derive_audit_stage` (`total == 0 → bare` before `is_bare`); stage hoisted once per invocation in `plan_tool/cli/completeness_cmd.py`.

**From steps 4–6:**

- `compute_conceptual_bar_blocking_ids`, `audit_coverage_qualifies_sample`, `conforming_pass_count` / `failed_or_malformed_pass_count` (step 4).
- Mid-run remap to `terminal_hand_apply` in `plan_tool/cli/completeness_phases.py` (`_run_iterate_convergence_loop`).
- `_completeness_has_blocking_findings` conceptual arm uses `is_blocking_finding` under hoisted `audit_stage` (step 6).
- `--json` fields: `stage`, `conceptual_bar_blocking_ids`, `audit_incomplete`, bar-aware `has_blocking_findings`.
- `ConvergenceState.has_blocking_findings` stays **deterministic-only** (dual-use split from the plan Architecture).

**Backlog state to reconcile:**

- **#248** — bare-plan bar; status already notes `stage-differentiated-blocking`; core ships here; edit-drift exit and reporting polish stay open.
- **#91** — detail-grounded domain demotion; settled 2026-08-09 to land with #248; original scope also named create/detail/reconcile loops and `plan_tool/completeness_report.py` advisory bucket — **not** in this plan’s scope.

**Already-implemented signal:** `integrations/shared/DIRECTIVES.md` has `## Gate 1` / `## Gate 2` headings only — structurally uninformative; confirm option-level (no stage-bar / `terminal_hand_apply` vocabulary) before scoping remaining work.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `integrations/shared/DIRECTIVES.md` — add **stage-differentiated conceptual bar** subsection beside Gate 1/Gate 2 and the stopping rule: bare vs detail tables, mid-run `terminal_hand_apply`, pass-conformance / `audit_incomplete` one-liner, three-predicate boundary (stage bar vs `is_blocking_impact` vs severity helper), pointer to BACKLOG #260 for reporting polish. Do **not** duplicate the full manual convergence loop or audit-shapes registry.
  - `CLAUDE.md` — extend **Convergence policy boundary** and, if needed, one terse clause under **Plan audit gate**: three predicates, dual `has_blocking_findings` roles, completeness-only scope of `is_blocking_finding`.
  - `docs/AUDIT_FLOW.md` — new **`completeness-audit` stage bar** subsection in `[BLOCK]` idiom; update **Source map** rows for symbols this step cites (`derive_audit_stage`, `is_blocking_finding`, `classify_finding_domain`, `compute_conceptual_bar_blocking_ids`, `_completeness_has_blocking_findings`, `_run_iterate_convergence_loop` bar remap). Cross-link DIRECTIVES for operator narrative; do not paste the bar table twice.
  - `RUNBOOK.md` — fix **completeness-audit** / **How the loop terminates** / `--json` / `--fail-on-findings` passages that still say flat `medium+`; add bare vs detail operator notes and JSON field names; optional one-line note on recipe step 3 (bare gate) if it still implies severity-only clean.
  - `BACKLOG.md` — **partially close** #91 and #248; add **#261** (four-loop blocking consistency); update **Blocked** index row that lists `#248 with #91`; add `stage-differentiated-blocking` to executed-plan disposition when the plan ships (or mark plan-authored pending execution per backlog hygiene — prefer **Status: partially closed — core in `stage-differentiated-blocking`** until the plan’s final step clears the entry).

## Implementation

### Doc ownership (do not duplicate; link instead)

| Fact class | Home doc | Others |
| --- | --- | --- |
| Bare vs detail bar rules, mid-run steering, operator “when is gate 1 clean” | `integrations/shared/DIRECTIVES.md` | AUDIT_FLOW links; RUNBOOK one-paragraph + commands |
| Three-predicate boundary, assistant-facing scope fences | `CLAUDE.md` | DIRECTIVES one-sentence pointer |
| Symbol → module map, iterate/finalize sequence | `docs/AUDIT_FLOW.md` | RUNBOOK points here for gate sequence |
| Copy-paste commands, CI `--json` / `--fail-on-findings` | `RUNBOOK.md` | cite bar-aware fields, not full predicate |
| What shipped vs what remains | `BACKLOG.md` | #260, new #261 |

**Rejected alternative:** pasting the plan Architecture table verbatim into all five files — it will drift; each home doc gets the minimum table or bullet set its audience needs.

### `integrations/shared/DIRECTIVES.md`

Insert a new subsection **after Gate 2 (before or within “The manual convergence loop”)** — suggested title: **Stage-differentiated conceptual bar (`completeness-audit`)**. Cover:

- **Closed stage vocabulary:** `bare` | `detail`, derived once per invocation (`derive_audit_stage`; `total == 0 → bare` even when `DetailBundleStatus.is_bare` is false).
- **Bare bar (Gate 1):** medium+ `plan-correctness` blocks; `plan-completeness` blocks only at high/critical; nit/info never; **no** `classify_domain` call.
- **Detail bar (Gate 2):** `is_blocking_finding(..., stage="detail", classify_domain=classify_finding_domain)` demotes medium **docs** / **unit-test** conceptual findings; medium **code-logic** (and unknown domain) stay blocking.
- **Mid-run:** when only conceptual bar blockers remain, iterate loop stop kind becomes **`terminal_hand_apply`** (not “converged”); remedies by finding class on existing surfaces — do not claim `completeness-apply` auto-closes conceptual gaps in assistant-driven mode.
- **Finalize / CI:** clean eligibility uses qualifying pass-conformance sample ∧ bar-aware `has_blocking_findings` ∧ eligible `outcome.stop_reason`; `audit_incomplete` means re-run with a live sample — not “raise `--audit-passes` first.”
- **Boundary:** `is_blocking_impact` remains for reconcile refresh and conceptual `material_new` only — **not** the completeness stage bar. Severity-aware **stopping rule** (#125) is orthogonal (audit pass budget), not the bar.
- **Deferred reporting:** one line pointing at BACKLOG **#260** (set-aside lists, full stop-reason vocabulary, gate-2 tail copy).

Keep Gate 1/Gate 2 withhold prose intact; clarify that **withhold** (`bundle_status.is_bare`) is separate from **audit stage** for the bar.

### `CLAUDE.md`

Extend **Convergence policy boundary** with a short **three-predicate** bullet list:

- `is_blocking(severity)` — pure severity floor; unchanged callers.
- `is_blocking_finding(rec, *, stage, classify_domain=...)` — **completeness-audit** conceptual bar only (steps 1–6 wiring).
- `is_blocking_impact(rec)` — reconcile + `material_new`; explicitly **out of scope** to widen for stage/domain.

Add one bullet on **`has_blocking_findings` dual use:** `ConvergenceState.has_blocking_findings` deterministic-only; finalize/`--json`/`--fail-on-findings` use `_completeness_has_blocking_findings` with the stage bar.

**Superseded 2026-08-14:** the "out of scope to widen for stage/domain" line
above no longer holds as stated — `is_blocking_impact`'s `material_new` use
gained an optional `classify_domain` param (still stage-agnostic, still not
the stage bar; reconcile calls still omit it). See BACKLOG #91's current
status and CLAUDE.md's live "Convergence policy boundary" section.

Under **Plan audit gate**, at most **one sentence** that bare and detail gates use different conceptual bars via `is_blocking_finding` — detail in DIRECTIVES/AUDIT_FLOW.

### `docs/AUDIT_FLOW.md`

Under **`completeness` — conceptual audit**, add a subsection (suggested: **Stage bar and mid-run steering**) using existing `[BLOCK]` / advisory idioms:

1. **[BLOCK] Stage hoisting** — `cmd_completeness` → `derive_audit_stage(bundle_status)` before iterate vs audit-only branch.
2. **[BLOCK] Pass-conformance** — `conforming_pass_count` / `failed_or_malformed_pass_count`; `audit_incomplete` when sample does not qualify (including reuse without conformance).
3. **[BLOCK] Conceptual bar set** — `compute_conceptual_bar_blocking_ids` + `is_blocking_finding` (detail: `classify_domain=classify_finding_domain`).
4. **[BLOCK] Mid-run steering** — `_run_iterate_convergence_loop` remaps `converged` / `no_blocking_findings` / `all_auto_apply_findings_deferred` when bar blockers remain → `terminal_hand_apply`.
5. **[BLOCK] Finalize / JSON** — `_completeness_has_blocking_findings` bar-aware arm; JSON keys `stage`, `conceptual_bar_blocking_ids`, `audit_incomplete`.

Update **Source map** table: add rows for the symbols above; keep `is_blocking_impact` row but add a note “not completeness stage bar.”

**Heading rename guard:** if any new heading text changes, `rg` inbound `#anchor` links across `docs/` before merging.

### `RUNBOOK.md`

Target passages that still equate CI gating with flat **medium+**:

- **How the loop terminates** (`--fail-on-findings` bullet ~line 1238) — stage-aware wording: bare vs detail differ; incomplete audit fails; point at `--json` `stage` + `conceptual_bar_blocking_ids`.
- **Completeness with iteration** / **Address conceptual gaps** — note mid-run `terminal_hand_apply` when conceptual bar blockers remain after deterministic convergence.
- **`plan-tool completeness-audit … --json`** block (~2448) — document bar-aware `has_blocking_findings` and new JSON fields; link `DATA_CONTRACT.md` for schema (do not duplicate field tables here).
- **Non-convergent signature** (~2716) — qualify that `no_blocking_findings` / “converged” on **deterministic** iterate state does not override the **conceptual stage bar** (cross-link DIRECTIVES).

Optional: recipe comment at **# 3. Early design gate** — bare bar is correctness-focused (not “zero findings of any kind”).

### `BACKLOG.md` — partial closure and re-filing

**#248 — Partially closed**

- Update **Status** to: **Partially closed — core shipped in `stage-differentiated-blocking` (2026-08-10).** Bare bar via `is_blocking_finding` at `stage="bare"`; mid-run + finalize/JSON wired in that plan.
- **Remaining / follow-up:** edit-drift exit (plan Out of scope); reporting polish → **#260**; do not delete the measurement table (provenance).
- Remove or rewrite **Blocked** table coupling “#248 with #91” — replace with “partially closed; see #261 for loop propagation.”

**#91 — Partially closed**

- Update **Status** to: **Partially closed — detail-grounded domain demotion shipped for `completeness-audit` only** (`classify_finding_domain` + `is_blocking_finding` at `stage="detail"`).
- **Remaining:** four convergence loops (create / detail / completeness / reconcile) still on old predicates; `completeness_report.py` completeness-advisory bucket; reconcile `convergence_diagnosis` severity-only filter — route to **#261**, not left implicit in #91 body.
- Trim or strike the “Hard coupling with #248” blocker language; replace with pointer to shipped plan.

**New entry #261 — Four-loop blocking policy consistency (follow-up to stage-differentiated-blocking)**

- **What:** propagate documented stage/domain blocking expectations to create, detail, and reconcile iterate loops (and decide explicitly for `completeness_report.py` advisory bucket + `convergence_diagnosis.py` recurring regions) so all four loops do not disagree with completeness-audit’s bar.
- **Why:** #91’s original acceptance named four loops; this plan intentionally scoped bars to completeness-audit only.
- **Depends on:** `stage-differentiated-blocking` executed.
- **Out of scope:** changing the completeness bar itself; persisted `Recommendation.domain`.
- **Origin:** step 7 partial closure of #91 (2026-08-10).

**Index hygiene:** update trust-core / blocked lists that still list #91 and #248 as fully open coupled work.

### Vocabulary sweep (required before calling the step done)

Run over the five edited files only:

| Stale phrase / claim | Replace with |
| --- | --- |
| completeness `--fail-on-findings` / CI gates on **medium+** (flat) | stage-aware bar; `audit_incomplete`; JSON `conceptual_bar_blocking_ids` |
| `no_blocking_findings` means fully clean for completeness | deterministic iterate state; conceptual bar may still block via `terminal_hand_apply` |
| `is_blocking` is the completeness conceptual gate | `is_blocking_finding` for conceptual recs at completeness finalize/mid-run |
| domain-aware blocking **everywhere** | **detail-grounded completeness-audit** only unless #261 ships |
| Gate 1 and Gate 2 share one blocking bar | distinct bare vs detail bars (same manual loop, different bar) |

Also `rg 'is_blocking_finding|terminal_hand_apply|conceptual_bar_blocking' integrations/shared/DIRECTIVES.md docs/AUDIT_FLOW.md` — expect matches after edit.

### Constraints and gotchas

- **No production code** in this step — if docs describe behavior steps 1–6 have not landed, that is a plan execution ordering bug, not something to fix by editing code here.
- **Do not** document reporting polish as shipped — point at #260 and the plan Deferred section.
- **Do not** expand `is_blocking_impact` scope in prose — reconcile only.
- **Do not** cite line numbers as anchors; use symbol names from Input.
- **DIRECTIVES.md** is symlinked into consuming repos — keep operator-facing tone; depth stays in AUDIT_FLOW source map.

## Tests

### Verification (non-code step)

The test-authoring gate does not apply (`change_type: non-code`). Run this numbered checklist before marking the step done:

1. `rg -n 'medium\+' integrations/shared/DIRECTIVES.md CLAUDE.md docs/AUDIT_FLOW.md RUNBOOK.md` — no flat completeness-gate CI claims remain (matches may exist only in historical BACKLOG quotes or explicitly qualified context).
2. `rg -n 'is_blocking_finding|derive_audit_stage|terminal_hand_apply|conceptual_bar_blocking_ids|audit_incomplete' integrations/shared/DIRECTIVES.md docs/AUDIT_FLOW.md` — each symbol appears at least once where the bar is explained.
3. `rg -n 'is_blocking_impact' CLAUDE.md integrations/shared/DIRECTIVES.md` — prose states it is **not** the completeness stage bar.
4. `rg -n 'is_blocking_finding' docs/AUDIT_FLOW.md` — source map row exists for `plan_tool/convergence.py`.
5. `rg -n '#248 with #91|#248 with #91' BACKLOG.md` — blocked coupling row updated.
6. `rg -n 'Partially closed' BACKLOG.md` — both #91 and #248 statuses updated.
7. `rg -n '^\*\*#261' BACKLOG.md` — four-loop follow-up entry present.
8. `rg -n '#260' integrations/shared/DIRECTIVES.md` — reporting polish deferred pointer present.
9. Markdown link spot-check: DIRECTIVES → CLAUDE audit-shapes pointer still valid; new AUDIT_FLOW anchors resolve (no broken `#` links from heading edits).
10. `git diff --stat` — only the five declared files (plus no accidental `DATA_CONTRACT.md` / generated CLI reference edits in this step).

## Acceptance criteria

- `integrations/shared/DIRECTIVES.md` documents bare vs detail conceptual bars, mid-run `terminal_hand_apply`, and separates stage bar from `is_blocking_impact` and the #125 stopping rule.
- `CLAUDE.md` Convergence policy boundary names all three predicates and the `has_blocking_findings` dual-use split without widening `is_blocking_impact`.
- `docs/AUDIT_FLOW.md` adds stage-bar `[BLOCK]` sequence and source-map rows for `derive_audit_stage`, `is_blocking_finding`, `classify_finding_domain`, `compute_conceptual_bar_blocking_ids`, and completeness finalize/mid-run wiring.
- `RUNBOOK.md` no longer tells operators that `--fail-on-findings` is a flat medium+ gate; documents bar-aware JSON fields at a high level.
- BACKLOG **#248** and **#91** statuses read **Partially closed** with explicit remaining work (#260, edit-drift, #261).
- BACKLOG **#261** filed for four-loop blocking consistency; blocked index no longer lists #248/#91 as an unshipped coupled blocker.
- Verification checklist items 1–10 pass.
- No edits outside the five declared `files:` paths.

## References

- [typing](https://docs.python.org/3/library/typing.html) — when citing `classify_domain` callback typing in AUDIT_FLOW prose.
- [PEP 3102](https://peps.python.org/pep-3102/) — keyword-only `audit_stage` / `classify_domain` parameters in symbol mentions.
- [pytest parametrize](https://docs.pytest.org/en/stable/how-to/parametrize.html) — pointer only if RUNBOOK mentions the #248 fixture’s test location (`tests/test_convergence.py`).

## Applicable guardrails

- **Plan intent** — docs make stage-differentiated blocking and mid-run steering discoverable; they do not implement bars or reporting polish.
- **Plan Out of scope** — do not document edit-drift exit, bare withhold (#241), multi-pass streak changes, arm-clustering, audit prompt changes, reconcile/create/detail loop bars as shipped, persisted `Recommendation.domain`, or `is_blocking_impact` expansion; route those to Deferred/backlog.
- **Plan Deferred** — reporting polish stays BACKLOG #260; this step only points operators there.
- **Step intent** — BACKLOG partial closure only for what steps 1–6 ship; re-file four-loop gap as #261.

## Deferred

- Reporting polish (full stop-reason vocabulary, set-aside handoff, gate-2 tails, jira next-steps) — BACKLOG #260; not this step.
- Edit-drift exit from #248 measurement — plan Out of scope; remains a backlog follow-up, not deleted with partial closure.
- Four-loop blocking consistency (create / detail / reconcile + advisory bucket / diagnosis) — BACKLOG #261 filed by this step.
- Domain classifier live-rate corpus gate — plan Deferred.
- Stage bars in reconcile / create / detail loops — plan Out of scope; cite #261 instead of implying future work is done.
