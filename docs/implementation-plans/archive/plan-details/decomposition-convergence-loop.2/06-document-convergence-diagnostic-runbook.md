> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Document the `plan-tool convergence` diagnostic in RUNBOOK + CLAUDE, and trim BACKLOG #57 to its deferred remainder

## Summary

This is the **docs-only** close-out for the Decomposition Convergence Loop plan: it teaches operators the `plan-tool convergence <name>` command that steps 1–5 built, and it retires the now-shipped scope from the backlog. Three edits, no new files, no production code: a new `###` subsection in `RUNBOOK.md` under `## Workflow: completeness checks` (placed beside the existing re-decompose subsection, since the command automates that manual fork); one `## Architecture` paragraph in `CLAUDE.md` after the **Granularity advisor** paragraph; and a trim of `BACKLOG.md` **#57** to just its deferred remainder (opt-in auto-execution + report-section surfacing). The key decision: because `## Table of contents` in `RUNBOOK.md` lists only `##`-level headings, adding a `###` subsection needs **no** ToC edit. On green, an operator can read how to run the read-only diagnostic, the architecture map names the new leaf, and #57's text describes only what is still unbuilt — not the v1 that landed.

## Table of Contents

- [Why](#why) — what's undocumented today and why the docs close-out is its own step
- [Files (creates vs edits)](#files-creates-vs-edits) — the three edited docs, no new files
- [Implementation](#implementation) — the RUNBOOK subsection, the stale-line reframe, the CLAUDE paragraph, the #57 trim
- [Tests](#tests) — non-code; doc accuracy and link checks
- [Acceptance criteria](#acceptance-criteria) — checkable doc states
- [References](#references) — the source surfaces this docs step describes
- [Deferred](#deferred) — what stays in #57 and out of this step

## Why

- Steps 1–5 ship the whole `plan-tool convergence` command — `load_report_history` → `build_region_trends` → `diagnose_convergence` → `classify_fork` / `render_diagnosis` → the `plan_tool/cli/convergence_cmd.py` handler — but **no operator doc tells anyone it exists or when to run it**. An operator hitting a non-convergent audit/apply loop today reads `RUNBOOK.md`'s `### When repeated audit/apply doesn't converge` subsection and must run the re-split-vs-re-seed fork **by hand**; the command now computes that fork from saved report history, and the runbook must point at it.
- `CLAUDE.md`'s `## Architecture` map names every cross-cutting leaf (`review.py`, `granularity.py`, …) but not `convergence_diagnosis.py`, so a future agent can't place the new module.
- `BACKLOG.md` **#57** *is* this plan. Leaving its full text in place after the v1 ships tells a reader the read-only diagnostic is still unbuilt — the feature landing silently falsifies the entry. Trim it to the remainder that genuinely stays open.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `RUNBOOK.md` — add one `### …` subsection under `## Workflow: completeness checks`, placed right after the `### When repeated audit/apply doesn't converge — re-decompose, don't keep patching` subsection (after its closing **Rule of thumb** line, before `### Suppressing a body-section finding`). Reframe that subsection's stale closing parenthetical that names "BACKLOG #57 proposes to surface automatically." **No `## Table of contents` edit** (the addition is `###`-level).
  - `CLAUDE.md` — add one bolded `## Architecture` paragraph after the **Granularity advisor (`granularity.py`).** paragraph and before the **Exit-code convention:** line. Leave `## What this is` unchanged.
  - `BACKLOG.md` — trim entry **#57** to its deferred remainder; verify the two sibling cross-references to `#57` still read true.

## Implementation

### `RUNBOOK.md` — new `###` subsection under completeness-checks

- **Use a `###` heading.** Place it inside `## Workflow: completeness checks`, immediately after the re-decompose subsection that ends with the `Rule of thumb: **three audit/apply cycles in the same region with no shrinkage…**` line. The command is the automated form of that exact fork, so the two belong adjacent.
- **No `## Table of contents` line.** The ToC near the top of `RUNBOOK.md` lists only `##`-level workflow headings; a `###` subsection adds nothing to it. Do not touch the ToC.
- **Content to cover in the subsection (keep it short, operator-facing):**
  - **What it answers** — "is this plan's audit/apply loop converging, or spinning on a mis-decomposition I should re-split or re-seed?" — computed from the plan's saved completeness/reconcile report sidecars, **zero Claude**, read-only.
  - **How to run it** — `plan-tool convergence <name>`. It loads report history, runs the diagnostic, prints the verdict, and **always exits 0** (no `--fail-on-findings`, no `--min-runs` — it is purely informational).
  - **What it prints** — the four-state headline (`no-history` / `insufficient-history` / `converging` / `spinning`), a per-kind breakdown, and on `spinning` a **pre-filled** `plan-tool split <plan> --step N --into "…" --into "…"` (localized over-pack) or `plan-tool create <slug> --from-existing <seed.md>` (structural mis-decomposition) command the operator can run.
  - **When to reach for it** — instead of eyeballing whether findings keep recurring in one region; it replaces the manual "identify the hot region, read its spread" judgment in the sibling subsection.
  - **Frame it as the authoring-time analogue** of the execution-time `escalate_to_split` bridge — that bridge escalates from the *apply/run* path; this command diagnoses from the *audit* history. Do not conflate the two.
- **Reframe the stale forward-looking line.** The re-decompose subsection ends with: *"(This fork — re-split vs. re-seed — is the manual version of what BACKLOG #57 proposes to surface automatically.)"* The feature has landed, so rewrite it to point at the shipped command — e.g. *"`plan-tool convergence` now computes this fork from saved report history; this section is the manual reading of the same signal."* Match whatever exact replacement text the new subsection uses so the two don't contradict.
- **COLLISION CHECK — re-verify before editing.** The separate escalate-to-split plan's step 9 reframes the **same** parenthetical to point at the `escalate_to_split` bridge. Whichever lands second must first confirm the line still reads in its stale `proposes to surface automatically` form before rewriting:
  - If still stale → reframe to name `plan-tool convergence` (the read-only diagnostic is #57's true v1 fulfillment, not the bridge).
  - If already rewritten by the bridge plan → **dedupe**: the line must name the `plan-tool convergence` diagnostic as #57's fulfillment, since #57 *is* the convergence loop. Do not stack a second contradictory "X is what #57 proposed" claim.

### `CLAUDE.md` — one `## Architecture` paragraph

- **Placement:** after the **Granularity advisor (`granularity.py`).** paragraph, before the **Exit-code convention:** line. The convergence diagnostic is a cross-cutting read-only leaf (a sibling of `review.py` / `granularity.py`), **not** a `## What this is` pipeline stage — leave `## What this is` unchanged.
- **What the paragraph states (bold lead term, terse):**
  - `plan_tool/convergence_diagnosis.py` is a **cycle-free leaf** whose only `plan_tool` imports are `review_persistence`, `review`, `locator`, `convergence` — it imports no `plan_tool.cli`.
  - It reads a plan's **saved completeness/reconcile report sidecars** (cross-run history) and decides whether the audit/apply loop is **spinning** on a mis-decomposition or **converging**, then forks **localized over-pack** (re-split one step) vs **structural** (re-seed and re-decompose).
  - The five functions in layer order: `load_report_history` → `build_region_trends` → `diagnose_convergence` → `classify_fork` / `render_diagnosis`.
  - Surfaced by the **read-only** `plan-tool convergence <name>` command (`plan_tool/cli/convergence_cmd.py`), modeled on `cmd_status`: spends **no Claude**, no mutation, no run-log entry, and **always exits 0** for every verdict (no `--fail-on-findings`). It consumes only the persisted report subset (recommendations, walk annotations, and the per-run `plan_fingerprint` / `code_fingerprint`) — it cannot read per-finding apply verdicts or file byte sizes, so detection keys on **recurrence + no-shrinkage**, with a fingerprint-stable, recurrence-free streak as the sub-threshold `converging` certificate.

### `BACKLOG.md` — trim **#57** to its deferred remainder

- **#57 is this plan.** The v1 read-only diagnostic shipped as `plan-tool convergence`. Rewrite the entry so its **What** describes only what is still open, and add a one-line "Shipped:" note pointing at the landed command. The remainder to keep (already parked in the seed's Deferred):
  - **Opt-in auto-execution** of the localized re-split (wire the recommended `plan-tool split` to actually run behind an explicit flag) — the structural re-seed stays human-authored.
  - **Report-section surfacing** — fold the verdict into the completeness report output instead of a separate command invocation.
- **Drop the now-done scope:** the detector over saved report history, the region-recurrence + no-shrinkage signature, the one-step-vs-cross-step fork, and the advisory-only first cut — all landed. Do not leave them described as future work.
- **Preserve the entry (trim, don't remove).** Because #57 stays in the file (as its deferred remainder), the two sibling cross-references keep their `#57` pointers — verify each still reads true rather than rewriting:
  - The bare-plan-audit entry's **Dependencies** line *"Complements #57 (consumes these reports)"* — still true; the diagnostic consumes saved reports.
  - **#59**'s **Dependencies** line *"Blocks/de-risks #57 (signal trust)"* and its body *"The recurrence signal that #57 (the non-convergence detector) … rely on is polluted by [sampling artifacts]"* — still true; #59's exhaustive-sampling work de-risks the diagnostic's recurrence signal exactly as before. Leave both unchanged.

## Tests

### Verification (non-code step)

This step changes no production code — no unit tests. Verify the artifacts:

- **`RUNBOOK.md` heading level** — the new subsection is `###`, nests under `## Workflow: completeness checks`, and the top `## Table of contents` is unchanged (no new ToC line).
- **Stale-line reframe** — the re-decompose subsection no longer says BACKLOG #57 "proposes to surface automatically"; it names the landed `plan-tool convergence` command, and only one such claim exists (no duplicate/contradictory reframe from the bridge plan).
- **Command accuracy** — every flag/behavior the new subsection states matches step 5's handler: `plan-tool convergence <name>`, zero Claude, always exit 0, no `--fail-on-findings`/`--min-runs`, the four verdict states, and the two pre-filled commands. Cross-check against `plan_tool/cli/convergence_cmd.py` and `docs/cli/convergence.md`.
- **`CLAUDE.md` placement** — the new paragraph sits after **Granularity advisor** and before **Exit-code convention:**; `## What this is` is unchanged; the named imports/functions match `plan_tool/convergence_diagnosis.py` at HEAD.
- **`BACKLOG.md` #57 trim** — the entry describes only opt-in auto-execution + report-section surfacing as open; the shipped diagnostic is noted as landed; #59's and the bare-plan-audit entry's `#57` references still read true.
- **Link/anchor check** — any in-doc link to the new subsection (if added) resolves to the correct GitHub-style anchor; no dangling `#57` references introduced.

## Acceptance criteria

- `RUNBOOK.md` has a new `###` subsection under `## Workflow: completeness checks` documenting `plan-tool convergence <name>` (read-only, zero Claude, always exits 0, four-state verdict, pre-filled split/create command).
- `RUNBOOK.md`'s `## Table of contents` is unchanged.
- The re-decompose subsection's closing line points at the landed `plan-tool convergence` command, not at a "BACKLOG #57 proposes to surface automatically" future claim, and there is exactly one such reframe.
- `CLAUDE.md` has one `## Architecture` paragraph between the **Granularity advisor** paragraph and the **Exit-code convention:** line that names `convergence_diagnosis.py`, its five functions, and the `plan-tool convergence` command; `## What this is` is unchanged.
- `BACKLOG.md` **#57** text describes only the deferred remainder (opt-in auto-execution + report-section surfacing) and notes the read-only diagnostic shipped.
- `BACKLOG.md` **#59** and the bare-plan-audit entry still carry their `#57` cross-references, and each still reads true.
- `uv run pytest -m "not integration" tests/ -q` stays green (no production code changed; any doc-snapshot/golden tests, if present, are unaffected).

## References

- [`RUNBOOK.md`](RUNBOOK.md) — the operator runbook; this step edits its `## Workflow: completeness checks` section (and its `### When repeated audit/apply doesn't converge` subsection).
- [`CLAUDE.md`](CLAUDE.md) — the architecture map; this step adds one `## Architecture` paragraph after the granularity-advisor entry.
- [`BACKLOG.md`](BACKLOG.md) — forward-looking backlog; entry **#57** is this plan and gets trimmed to its remainder. See its "Which file does my entry go in?" rule for keeping the remainder forward-looking.
- `plan_tool/cli/convergence_cmd.py` and `docs/cli/convergence.md` — the step-5 handler and generated flag reference; the source of truth for every command behavior the new docs assert.

## Deferred

- **Opt-in auto-execution of the localized re-split** — wiring the recommended `plan-tool split` to actually run behind an explicit flag stays in #57's remainder; the structural re-seed stays human-authored (the never-mutate-structure-unattended invariant). Not built here.
- **Folding the verdict into the completeness report output** — surfacing the diagnosis inside the report instead of a separate `plan-tool convergence` invocation stays in #57's remainder.
- **Editing the escalate-to-split bridge's own docs** — that bridge's RUNBOOK subsection (under `## Workflow: drive an authoring task to convergence`) and its CLAUDE paragraph (after **Correctness gates**) are a different feature's docs; this step touches only the convergence-diagnostic homes.
- **Any production-code or test change** — out of scope; this is a docs-only step.
