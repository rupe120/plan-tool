# Step 5 — Update the docs for the cross-round advisory and settle the backlog entries

## Summary

This step is a documentation-only pass over four files — `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/AUDIT_FLOW.md`, `BACKLOG.md` — that corrects claims steps 1–4 make false or incomplete and documents the cross-round `arm-clustering` advisory those steps ship. It fixes `convergence_diagnosis.py`'s import set as described in two places (`CLAUDE.md`'s "Cycle-free import constraints" bullet and `docs/ARCHITECTURE.md`'s "Convergence diagnostic" entry), corrects `CLAUDE.md`'s claim that `--audit-passes 1` leaves `arm-clustering` fully dark, adds the new advisory to `CLAUDE.md`'s "Recommend-only convergence advisories" catalog and to `docs/AUDIT_FLOW.md`'s prose and source map, and removes `BACKLOG.md`'s `#264` entry, which steps 1–4 fully deliver. The main design decision: describe the cross-round mechanism once, in `docs/AUDIT_FLOW.md` (the descriptive home for how the completeness/convergence surfaces behave) and in `CLAUDE.md`'s advisory catalog (the normative home for the recommend-only stance), and have every other touched spot *point* at those descriptions rather than restate them — matching this repo's own doc-ownership convention. On green, no doc still asserts that `--audit-passes 1` and `arm-clustering` are mutually exclusive by construction, no doc still lists a stale import set for `convergence_diagnosis.py`, and `BACKLOG.md` no longer carries a `#264` entry describing work that has already shipped.

## Table of Contents

- [Summary](#summary) — what this step delivers and where the line is drawn
- [Why](#why) — the gap this step closes
- [Input](#input) — what steps 2 and 4 actually landed, which this step's prose must match
- [Files (creates vs edits)](#files-creates-vs-edits) — what changes, file by file
- [Implementation](#implementation) — the specific edit to each of the four files
- [Tests](#tests) — verification appropriate to a docs-only step
- [Acceptance criteria](#acceptance-criteria)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

`CLAUDE.md` is injected into every session working on this repo, so a stale claim there does not just sit unread — it actively misleads the next audit, plan, or review. Three of its claims go stale the moment steps 1–4 land: the "Cycle-free import constraints" bullet for `convergence_diagnosis.py` (already wrong before this plan, since it omits `granularity`; wrong again after step 2 adds `audit_shapes`), the "What the shipped advisory cannot see" section's claim that `--audit-passes 1` and `arm-clustering` are "mutually exclusive by construction" (true only of the same-execution path; false once the cross-round path ships), and the "Recommend-only convergence advisories" catalog, which after step 2 lands a third signal onto `ConvergenceDiagnosis` that it doesn't name. `docs/ARCHITECTURE.md`'s "Convergence diagnostic" entry restates the same stale import set independently. `BACKLOG.md`'s `#264` entry proposes exactly the mechanism steps 1–4 build; leaving it open after they ship makes the backlog claim outstanding work is still needed. This step is the one that reconciles all four documents with what actually shipped, so a future session reading any of them gets the current, true picture rather than re-discovering or re-litigating a settled fact.

## Input

This step's prose must match what steps 1, 2, and 4 actually land — cite their outcomes, don't re-derive them:

- **Step 1** (`plan_tool/convergence_diagnosis.py`) lands `CROSS_ROUND_CONSENSUS_WINDOW`, `ArmClusteringConsensusEvidence`, and `classify_arm_clustering_consensus(history, *, declared_step_ids, step_statuses, window=..., classify_domain=None)` — a pure function over already-loaded history, with no `audit_shapes` import and no call into `evaluate_arm_clustering`.
- **Step 2** (same file) lands the consumer: a new top-level `from plan_tool.audit_shapes import (...)` import, an `ArmClusteringAdvisory` dataclass (`window_audit_stage`, `rounds_used`, `shape: AuditShapeAdvisory`), a `classify_arm_clustering(history, *, declared_step_ids=(), step_statuses=None, repo_root=None, window=..., classify_domain=None)` classifier that calls step 1's function and then `evaluate_arm_clustering`, a new `arm_clustering` field on `ConvergenceDiagnosis`, and a `_arm_clustering_lines(advisory) -> list[str]` render function wired into `render_diagnosis` beside `_impact_recurrence_lines` / `_edit_drift_lines`. Step 2's own Implementation states the render "names the round count and audit stage explicitly (e.g. 'across N saved `<stage>` rounds')" so it reads distinctly from the pre-existing same-execution advisory — this step's docs must describe that distinguishing behavior, not invent different wording for it. Step 2 also fixes this module's own "cycle-free leaf" docstring paragraph in the same edit — this step's `CLAUDE.md`/`docs/ARCHITECTURE.md` edits describe the same corrected import set but do not touch the module docstring itself (that file isn't in this step's declared `files:` list).
- **Step 4** (`plan_tool/cli/convergence_cmd.py`, `plan_tool/cli/completeness_cmd.py`) is what actually threads real `declared_step_ids` / `step_statuses` / `repo_root` into `diagnose_convergence` from `cmd_convergence` and from the completeness-audit stderr tail (`_convergence_loop_advisory_lines` → `_emit_convergence_loop_advisories` → `finalize_completeness_run`), so the advisory fires for a real operator on both `plan-tool convergence <name>` and `completeness-audit`'s stderr output once ≥2 qualifying same-stage rounds exist. Before step 4, the classifier exists but nothing calls it with real data — this step's docs describe the shipped, wired-up state, not an intermediate one.
- **The plan's own Architecture point 8** (frontmatter body) — the render stays silent when nothing fires, including when a previously-firing arm's consensus becomes unresolvable; this is a stated decision, not an open question, and the plan's Risks section requires this step's docs to say so "in those words rather than leaving it to be inferred from the absence of a line."
- **`BACKLOG.md`'s `#264` entry** (current text, to be removed) — proposes exactly the mechanism steps 1–4 build: a new caller wiring `consensus_targets` from `build_collapsed_completeness_passes(history)`-derived cross-round data instead of same-invocation passes. Its own "This is a different signal, not just a substitute" note speculates the cross-round question might be "does this arm keep generating findings despite genuine remediation attempts between rounds" — the plan's actual Overview and Out of scope settle this differently: the shipped mechanism "checks recurrence only... does not check whether a fix was attempted between rounds." This step's docs must use the plan's actual, narrower framing, not `#264`'s original speculative one.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `CLAUDE.md` — three separate edits (see Implementation): the "Cycle-free import constraints" bullet for `convergence_diagnosis.py`; the "What the shipped advisory cannot see" section under the `arm-clustering` audit-shape row; the "Recommend-only convergence advisories" catalog.
- `docs/ARCHITECTURE.md` — one edit to the "Convergence diagnostic" paragraph: the import-set clause and a new sentence naming the cross-round advisory.
- `docs/AUDIT_FLOW.md` — one new paragraph after the existing "Arm-clustering advisory" paragraph (inside the `` `completeness` `` section), and one new row in the "Source map" table.
- `BACKLOG.md` — remove the `#264` entry in full.

No code, test, or prompt file is touched — this step's `change_type` is `non-code`.

## Implementation

### 1. `CLAUDE.md` — "Cycle-free import constraints" bullet

Find the bullet for `convergence_diagnosis.py` under "Cycle-free import constraints, in one place." (§ "Architecture"). It currently lists `review_persistence`, `review`, `locator`, `convergence` and omits `granularity` — already wrong before this plan, per the plan's own Step intent. Update it to name the module's complete import set as it exists once steps 1–2 land: `review_persistence`, `review`, `locator`, `convergence`, `granularity`, `audit_shapes`, keeping the "never `plan_tool.cli`" clause. Don't just append `audit_shapes` onto the existing four-name list — fix the omission too, in the same edit, per the plan's explicit instruction ("not only append the one new edge onto an already-wrong baseline").

Leave the neighboring `audit_shapes.py` bullet ("a leaf; audit-flow and persistence consumers import it, never the reverse") unchanged — it's a category description of `audit_shapes.py`'s existing consumer set (`review_persistence.py`, `data_contract.py`, `completeness_report.py`, `review.py`, two `cli/` modules), and `convergence_diagnosis.py` becoming one more consumer of a leaf still fits "consumers import it, never the reverse" without needing a name added.

### 2. `CLAUDE.md` — "What the shipped advisory cannot see"

This section (under the `arm-clustering` row of the audit-shapes table, § "Audit the why, not the what") describes the *same-execution* detector only (`evaluate_arm_clustering` as called from `review.py`'s same-invocation multi-pass path) — that path is unmodified by this plan (Out of scope). Once the cross-round path ships, two of its three stated consequences are no longer absolute:

- The `--audit-passes 1` bullet currently says this setting "disables it outright" and that "the recommended setting and the only shipped detector are mutually exclusive by construction." After this plan, there are two shipped detectors, and the second one — `arm_clustering` on `ConvergenceDiagnosis` — can fire under `--audit-passes 1` once ≥2 qualifying same-`audit_stage` rounds are already saved in history. Keep the same-execution fact (still true: one same-invocation sample can never yield a same-execution consensus target), drop the "only shipped detector" / "mutually exclusive by construction" framing, and point at the cross-round advisory (described in full under "Recommend-only convergence advisories" — see edit 3) as the thing that closes this gap.
- The "`detail` completeness tail computes none either" bullet is the same shape: true of the same-execution path (no multi-sample evidence within one invocation at any stage), not true of the cross-round path once ≥2 saved `detail`-stage rounds exist.
- The "one-step concentration can never fire it" bullet needs no change — `evaluate_arm_clustering`'s own step-majority arm math is shared and unmodified by this plan (Out of scope), so this limit applies identically to both detectors.

One reasonable way to keep the section coherent: qualify the section's own header/lead so "the shipped advisory" clearly means the same-execution one (there are now two shipped advisories, so the bare phrase is ambiguous), and add a short pointer sentence after the bullet list naming the cross-round advisory as the thing that closes the first and third gaps once qualifying history exists — without re-describing its mechanism here (that description lives in edit 3).

### 3. `CLAUDE.md` — "Recommend-only convergence advisories"

This list (§ "Convergence policy boundary") currently names two signals, `impact_recurrence` and `edit_drift`, each with its classifying function, firing condition, and render function. Add a third bullet for `arm_clustering`, in the same shape:

- Name the classifier (`classify_arm_clustering`, built on step 1's `classify_arm_clustering_consensus`) and what it feeds (`evaluate_arm_clustering`, `plan_tool/audit_shapes.py`).
- State the firing condition: a material finding's `[audit-step:N]` target (persisted as `audit_step_target` on `Recommendation`/`RunFinding` by step 1) agrees across ≥2 same-`audit_stage` saved rounds, forming the same gap-free proper-majority arm the same-execution detector requires — `evaluate_arm_clustering`'s own math is shared and unmodified.
- State what makes it distinct: it reads persisted `completeness-audit` history instead of same-invocation passes, so it can fire under `--audit-passes 1` — this is the sentence edit 2's pointer should land on.
- Name the render function (`_arm_clustering_lines`) and both surfaces (`plan-tool convergence`, completeness stderr), and that its printed line names its round count and audit stage so it reads distinctly from the same-execution advisory when both fire together (Input, step 2's stated requirement).
- State it checks recurrence only — not whether a fix was attempted between matched rounds (the plan's Overview and Out of scope; this is the point where `#264`'s original, more speculative framing does **not** apply — see Input).

Update the closing paragraph ("Neither advisory feeds `should_continue`...") to cover all three: it should still state that none of the three feeds `should_continue` / `ConvergenceState.has_blocking_findings` / `_completeness_has_blocking_findings` / `--fail-on-findings` / exit codes, and none revives `spinning` / `FORK_*` / `recurring_regions`. Consider adding one clause noting that cross-round `arm_clustering`'s materiality (`is_blocking_finding`, per step 1's Architecture point 2) is deliberately not required to agree with the same-execution advisory's own `is_blocking_impact`-based materiality — the same "deliberately different rule for a different consumer" pattern the plan's Architecture and Acceptance criteria state repeatedly.

### 4. `docs/ARCHITECTURE.md` — "Convergence diagnostic"

This paragraph (§ "Convergence diagnostic") states the module's import set inline ("whose only `plan_tool` imports are `review_persistence`, `review`, `locator`, and `convergence`") — apply the same fix as edit 1: add `granularity` and `audit_shapes`.

The same paragraph also says "plus three newest-run advisories" and names exactly three (`latest_blocking`, `code_drift`, `finding_churn`) — this was already an undercount before this plan (the module's actual docstring, per step 2's own Files section, separately lists `structural_recurrence`, `impact_recurrence`, and `edit_drift` too). Fully reconciling that pre-existing gap is out of this step's scope (see Deferred), but adding a new sentence for `arm_clustering` right after a claim of "three" would make the paragraph read as internally contradictory. Recommended fix: drop the specific count ("three newest-run advisories" → "several newest-run advisories", keeping the same three as illustrative examples), then add one new sentence naming `arm_clustering` as a newer signal in the same family that reads round-over-round history and can fire under `--audit-passes 1`, pointing at `CLAUDE.md`'s "Recommend-only convergence advisories" for the full catalog rather than re-describing the mechanism here.

### 5. `docs/AUDIT_FLOW.md` — new paragraph + source map row

The existing "**Arm-clustering advisory.**" paragraph (§ "`completeness` — conceptual audit") describes only the same-execution, sidecar-persisted `AuditShapeAdvisory`. Add a new paragraph immediately after it — recommended heading "**Cross-round arm-clustering advisory.**" — that:

- States it's a second, independent signal living on `ConvergenceDiagnosis`, not in the completeness report/sidecar the preceding paragraph describes.
- Names the mechanism: `classify_arm_clustering` (`plan_tool/convergence_diagnosis.py`) feeds `evaluate_arm_clustering` with consensus built from saved `completeness-audit` history (via step 1's `classify_arm_clustering_consensus`, matching on each round's persisted `audit_step_target`) instead of same-invocation passes.
- States the firing condition (≥2 same-`audit_stage` saved rounds agreeing on a finding's target) and that this includes `--audit-passes 1`, where the same-execution advisory above cannot fire at all.
- States it is computed fresh on every read and is **never persisted** to the completeness sidecar — unlike the same-execution advisory the preceding paragraph describes.
- Names both rendering surfaces (`plan-tool convergence <name>`, completeness-audit's stderr tail) and that the printed line names its round count and audit stage, distinguishing it from the same-execution advisory when both fire together.
- States, in explicit terms, that a previously-firing arm losing consensus renders silently — **"this is a decision, not a gap"** or equivalent explicit phrasing — matching the plan's Risks-section requirement and this step's own guardrail (see Applicable guardrails).
- States it checks recurrence only, not whether a fix was attempted between matched rounds.

Add one new row to the "Source map" table (end of the file) naming the real symbols, e.g. next to the existing "Standalone convergence diagnostic" row:

```
| Cross-round arm-clustering advisory | `plan_tool/convergence_diagnosis.py` (`classify_arm_clustering_consensus`, `classify_arm_clustering`, `ArmClusteringAdvisory`, `_arm_clustering_lines`) |
```

### 6. `BACKLOG.md` — remove `#264`

Delete the entire `#264` entry (currently the last entry before the `## Adding a new entry` section) — title line through its closing `- **Status:** not started.` line, leaving exactly one blank line before the following `---`. This matches the repo's own settled convention for a discharged entry: `CLAUDE.md`'s "Withdrawn" section already records that `#203` and `#204` were "closed and deleted once discharged" and that the durable record moved into `CLAUDE.md` prose itself rather than staying as a completed backlog line item. `#264` needs no equivalent durable-record move — its content is fully superseded by this plan's own frontmatter `intent`/Overview, which already serves as the durable record of why the cross-round path exists.

Grep confirms `#264` is cited only inside this plan's own frontmatter/body/detail files (expected — a plan legitimately references its own originating backlog entry) and its archived seed under `plan-seeds/archive/`; no other doc treats it as still open, so no other file needs a cross-reference cleanup.

## Tests

### Verification (non-code step)

This step edits only documentation; `enforce_step_tests` does not apply because no production code, test, or prompt file changes (`change_type: non-code`). Verify instead with the following reviewer-runnable checks, run **after** steps 1–4 have actually landed in the working tree (this step's prose describes their shipped state):

1. `grep -n "convergence_diagnosis.py" CLAUDE.md` and `head -70 plan_tool/convergence_diagnosis.py | grep '^from plan_tool'` — confirm `CLAUDE.md`'s cycle-free bullet names exactly the module's real top-level `plan_tool` imports.
2. `grep -n "Convergence diagnostic" -A3 docs/ARCHITECTURE.md` — confirm the same six-name import set appears there too.
3. `grep -n "disables it outright\|mutually exclusive by construction" CLAUDE.md` — confirm no remaining sentence asserts `--audit-passes 1` and `arm-clustering` are unconditionally exclusive.
4. `grep -n "arm_clustering\|arm-clustering" CLAUDE.md` — confirm the "Recommend-only convergence advisories" section now names `arm_clustering` alongside `impact_recurrence` / `edit_drift`, and that `classify_arm_clustering` / `_arm_clustering_lines` are both cited by their real names (cross-check against `plan_tool/convergence_diagnosis.py`).
5. `grep -n "Cross-round arm-clustering" docs/AUDIT_FLOW.md` — confirm the new paragraph exists and sits after the existing "Arm-clustering advisory" paragraph, and that it contains the phrase "decision, not a gap" (or an equally explicit equivalent) rather than leaving the silent-non-fire behavior to be inferred.
6. `grep -n "Cross-round arm-clustering advisory" docs/AUDIT_FLOW.md` in the "Source map" table — confirm the new row exists and its four cited symbols (`classify_arm_clustering_consensus`, `classify_arm_clustering`, `ArmClusteringAdvisory`, `_arm_clustering_lines`) all exist in `plan_tool/convergence_diagnosis.py` (`grep -n "^def classify_arm_clustering\|^class ArmClusteringAdvisory\|^def _arm_clustering_lines" plan_tool/convergence_diagnosis.py`).
7. `grep -n "#264" BACKLOG.md` — confirm zero hits.
8. `grep -rn "#264" . --include=*.md | grep -v "docs/implementation-plans/2-arm-clustering-cross-round-consensus.md\|plan-details/arm-clustering-cross-round-consensus\|plan-seeds/archive"` — confirm no other live (non-plan, non-archived-seed) doc still cites `#264` as open work.
9. `grep -n "spinning\|FORK_\|recurring_regions" CLAUDE.md docs/ARCHITECTURE.md docs/AUDIT_FLOW.md BACKLOG.md` — diff against this step's own edits and confirm none of that retired vocabulary was introduced by this step (pre-existing hits elsewhere in these files, if any, are out of scope).
10. `git diff --stat` — confirm only `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/AUDIT_FLOW.md`, and `BACKLOG.md` changed.

## Acceptance criteria

- `CLAUDE.md`'s "Cycle-free import constraints" bullet for `convergence_diagnosis.py` names `review_persistence`, `review`, `locator`, `convergence`, `granularity`, `audit_shapes` — not the previous four-name list with `audit_shapes` merely appended.
- `docs/ARCHITECTURE.md`'s "Convergence diagnostic" entry names the same six-name import set.
- `CLAUDE.md`'s "What the shipped advisory cannot see" section no longer states that `--audit-passes 1` and `arm-clustering` are mutually exclusive by construction; it distinguishes the same-execution limitation (still true) from the cross-round path's coverage of that gap.
- `CLAUDE.md`'s "Recommend-only convergence advisories" list names `arm_clustering` as a third signal, with its classifier, firing condition, render function, both rendering surfaces, and its recurrence-only (not remediation-attempt-aware) scope — matching the plan's actual Overview/Out of scope framing, not `#264`'s original speculative framing.
- `docs/AUDIT_FLOW.md` documents the cross-round advisory in a paragraph distinct from the existing same-execution "Arm-clustering advisory" paragraph, states it is computed fresh and never persisted to the completeness sidecar, names both rendering surfaces, and states the silent-non-fire behavior as an explicit decision, not an inferred gap.
- `docs/AUDIT_FLOW.md`'s Source map table gains a row naming the cross-round advisory's real symbols.
- `BACKLOG.md` no longer contains a `#264` entry.
- No file outside `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/AUDIT_FLOW.md`, `BACKLOG.md` is touched by this step's diff.
- No vocabulary from the retired `spinning` / `FORK_*` / `recurring_regions` diagnostic is introduced anywhere in this step's edits.

## Applicable guardrails

The plan's `## Out of scope` section binds this step on several points:

- No new blocking gate, exit-code flip, or apply-dispatch keyed on the advisory — every description this step writes must state `arm_clustering` (both the same-execution and cross-round signals) as recommend-only, never as something that blocks or gates.
- No reviving the retired `spinning` / `FORK_*` / `recurring_regions` region-trending diagnostic or its vocabulary — this step's new prose must not resemble it.
- No changing `--audit-passes 1`'s actual behavior, the stopping-rule recommendation, or any other convergence-policy-boundary caller class — this step only documents that a second, independent detector now also exists and can fire in that setting; it does not describe or imply any change to `--audit-passes 1` itself.
- Rendering an explicit "insufficient evidence" signal when a previously-firing arm's cross-round consensus becomes unresolvable is out of scope for the *code* (plan Architecture point 8) — this step's docs must describe that silence as the accepted, documented behavior rather than proposing or implying such a signal should exist.

## Deferred

- Editing `plan_tool/convergence_diagnosis.py`'s own module docstring paragraph — step 2's job, landed where the import lands, not this step's (this step's declared `files:` list does not include it).
- Adding `Recommendation.audit_step_target`'s `DATA_CONTRACT.md` row — step 1's job.
- Fully reconciling `docs/ARCHITECTURE.md`'s "newest-run advisories" list against `convergence_diagnosis.py`'s complete current signal set (`structural_recurrence`, `impact_recurrence`, `edit_drift` are all missing from that paragraph today, independent of this plan) — this step removes the false "three" count and adds `arm_clustering` without reintroducing a contradiction, but a full re-enumeration of the pre-existing gap is a separate docs sweep this plan does not scope.
- Adding a dedicated top-level "`plan-tool convergence`" section to `docs/AUDIT_FLOW.md` — the standalone diagnostic (including `impact_recurrence` / `edit_drift`) has never had its own prose section, only a "Source map" row; this step adds the cross-round paragraph inline near the existing arm-clustering content rather than creating that missing section.
- Touching any `BACKLOG.md` entry other than `#264` — the other mentions of "arm-clustering" in the file (e.g. the bare-plan prompt-cost entry's aside that `--audit-passes 1` "disables `arm-clustering` outright") describe the same-execution path's own, still-true ≥2-samples requirement and are unrelated topics; none asserts the "mutually exclusive by construction" claim this plan invalidates.
- Any change to `plan_tool/audit_shapes.py`, `plan_tool/convergence_diagnosis.py`, `plan_tool/review.py`, or their tests — all landed by steps 1–4 and consumed here only as citation targets for accurate documentation.

<!-- plan-tool-detail-deferrals
{"deferrals":[]}
-->
