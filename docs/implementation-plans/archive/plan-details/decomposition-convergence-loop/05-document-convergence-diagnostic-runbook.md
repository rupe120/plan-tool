# Step 5 — Document the convergence diagnostic (RUNBOOK workflow, CLAUDE architecture, BACKLOG #57)

## Summary

- Documents the read-only `plan-tool convergence <plan>` command that steps 1–4 build, across the three operator/agent docs in scope: a RUNBOOK workflow subsection, one CLAUDE architecture paragraph, and a BACKLOG #57 reframe.
- **No production code changes** — this step edits `RUNBOOK.md`, `CLAUDE.md`, and `BACKLOG.md` only. It depends on step 4 (the CLI seam) so the command it documents actually exists.
- Most important decision: the new RUNBOOK content goes in as a `###` subsection under `## Workflow: completeness checks`, directly after the existing `### When repeated audit/apply doesn't converge` block — the command automates the manual re-split-vs-re-seed fork that block describes, so it belongs beside it (and a `###` needs no `## Table of contents` edit).
- The step also reframes the two stale forward-looking cross-references the feature obsoletes: RUNBOOK's "the manual version of what BACKLOG #57 proposes to surface automatically" line and BACKLOG #57's "proposes to surface" framing — both now describe a landed command, not future work.
- On green: an operator reading any of the three docs learns the command exists, what it prints (spinning/converging verdict + the forked copy-paste repair command), and that it spends zero Claude and never mutates.

## Table of Contents

- [Why](#why) — the engine + CLI land in steps 1–4 but no operator doc names them
- [Files (creates vs edits)](#files-creates-vs-edits) — three doc edits, no new files
- [Implementation](#implementation) — the RUNBOOK subsection, the CLAUDE paragraph, the BACKLOG reframe
- [Tests](#tests) — verification of a non-code step (link + accuracy checks)
- [Acceptance criteria](#acceptance-criteria) — checkable doc states
- [References](#references) — the sibling step details that define the documented surface
- [Deferred](#deferred) — README/SKILL edits and generated CLI reference left out

## Why

- Steps 1–4 build the whole diagnostic — reader (`plan_tool/convergence_diagnosis.py: load_report_history`), detector (`diagnose_convergence`), classifier/renderer (`classify_fork`, `render_diagnosis`), and the `plan-tool convergence` CLI seam — but **no operator-facing doc tells anyone the command exists or when to run it.** An operator who suspects a plan's audit/apply loop is spinning still only has the manual `### When repeated audit/apply doesn't converge` RUNBOOK recipe; nothing points them at the command that confirms it and prints the matched repair.
- Two existing cross-references now lie. RUNBOOK's re-decompose subsection ends with "this fork … is the manual version of what BACKLOG #57 proposes to surface automatically," and BACKLOG #57 itself is written as a not-yet-built candidate ("Build the missing edge", "proposes to surface"). The feature landing across steps 1–4 makes both stale — they describe shipped behavior as future work.

## Files (creates vs edits)

**New files:**
- None.

**Existing files (edits only):**
- `RUNBOOK.md`:
  - Add a new `###` subsection under `## Workflow: completeness checks`, placed immediately after the `### When repeated audit/apply doesn't converge — re-decompose, don't keep patching` subsection and before `### Suppressing a body-section finding`.
  - Reframe the trailing parenthetical of the re-decompose subsection ("This fork — re-split vs. re-seed — is the manual version of what BACKLOG #57 proposes to surface automatically.") to point at the landed `plan-tool convergence` command.
  - No `## Table of contents` edit — the addition is a `###`, and the TOC lists only `##` workflow headings.
- `CLAUDE.md`:
  - Add one bolded paragraph to `## Architecture` describing `plan_tool/convergence_diagnosis.py` + the `plan-tool convergence` command, placed after the **Granularity advisor (`granularity.py`).** paragraph and before the **Exit-code convention:** line.
- `BACKLOG.md`:
  - Reframe the `#57` entry (heading `**#57 — A decomposition convergence loop: …**`) so its shipped v1 (read-only advisory diagnostic) is described as landed and the entry is trimmed to its still-deferred remainder, per BACKLOG's "Remove a feature's entry when it ships" rule.

## Implementation

### `RUNBOOK.md`

- **New `###` subsection** under `## Workflow: completeness checks`, after `### When repeated audit/apply doesn't converge — re-decompose, don't keep patching`. Suggested heading: `### Confirm non-convergence with `plan-tool convergence``. Content (keep it short — the re-decompose subsection already carries the conceptual signature; this subsection is the command's operator recipe):
  - State what it does: reads the plan's saved completeness/reconcile report history and prints a **spinning** or **converging** verdict, and when spinning, the recurring region plus a pre-filled repair command.
  - Show the invocation and that it is read-only / zero-Claude:
    ```bash
    plan-tool convergence my-feature   # read-only; prints verdict + forked repair command
    ```
  - State the fork it prints, tied back to the manual fork in the sibling subsection:
    - **localized over-pack** → a `plan-tool split <plan> --step N --into "…" --into "…"` command.
    - **structural / cross-step** → a `plan-tool create --from-existing <seed> --iterate` re-seed command.
  - State the exit-code behavior, matching the repo convention: exits `0` regardless of verdict; `--fail-on-findings` is the only lever that flips rc to `1` on a `spinning` verdict (mirror the wording in `CLAUDE.md`'s **Exit-code convention:** line and `04-wire-plan-tool-convergence-plan-cli.md`).
  - Note that the command needs **saved report history** to read — it relies on prior `completeness-audit` / reconcile runs having persisted reports under the plan's `reports/` dir; with no history it reports `converging` (too little signal), not an error.
- **Reframe the stale cross-reference.** In the `### When repeated audit/apply doesn't converge` subsection, the closing sentence currently reads "(This fork — re-split vs. re-seed — is the manual version of what BACKLOG #57 proposes to surface automatically.)". Rewrite it to past/present tense pointing at the landed command, e.g. "(`plan-tool convergence <plan>` now detects this signature and prints the matched fork automatically — see [the subsection below].)" Do not delete the manual recipe; the command confirms and recommends, the operator still runs the repair.
- **Do not touch** the `## Table of contents` block, the `> Convergence is the plan's correctness signal` callout under `## Workflow: drive an authoring task to convergence`, or any other section.

### `CLAUDE.md`

- **Add one `## Architecture` paragraph** after the **Granularity advisor (`granularity.py`).** paragraph and before the **Exit-code convention:** line. The convergence diagnostic is a read-only analysis leaf and a sibling of the gates/advisor surfaces, not a `## What this is` pipeline stage — keep `## What this is` unchanged.
- Content for the paragraph (mirror the density of the surrounding architecture bullets):
  - Name the module and command: **Convergence diagnostic (`convergence_diagnosis.py`, `plan-tool convergence`).**
  - State it is a cycle-free leaf whose only `plan_tool` imports are `review_persistence`, `review`, `locator`, `convergence`, `granularity` — it imports no `plan_tool.cli`.
  - State the read-only chain: `load_report_history` (reads saved completeness/reconcile reports via `review_persistence`) → `diagnose_convergence` (spinning/converging verdict from recurrence + no-shrinkage; `report_bytes` growth is recorded as a corroborating signal but never gates the verdict) → `classify_fork` (localized over-pack vs structural) → `render_diagnosis` (the printed verdict + forked copy-paste command).
  - State it spends zero Claude, never mutates, and honors the exit-code convention (exit 0 even on `spinning`; `--fail-on-findings` flips rc).
  - Note it is the **cross-run** counterpart to `granularity.py`'s advisory sources: the granularity advisor flags a per-step `granularity-split` / `granularity-merge` smell within a single audit; this reads the saved report history to surface a region that keeps re-flagging *across* runs (recurrence + no-shrinkage) — and like the advisor, it only recommends, with no actuating bridge.

### `BACKLOG.md`

- **Reframe `#57`** (heading `**#57 — A decomposition convergence loop: …**`). The v1 read-only advisory diagnostic ships in this plan, so per BACKLOG's "Remove a feature's entry when it ships," the shipped scope must leave the forward-looking list. Two acceptable forms — pick the one that matches what actually landed:
  - **If only the deferred items remain** (auto-execution behind opt-in, report-section surfacing — see the plan seed's Deferred): trim `#57` down to those remainder items, retitle it to name the remaining work (e.g. "auto-execute the localized split / surface the diagnosis in the completeness report"), and add a one-line note that the read-only `plan-tool convergence` diagnostic shipped.
  - **If nothing meaningful remains in BACKLOG scope:** remove the `#57` entry entirely and let git history / the plan file carry the record, per the "Remove a feature's entry when it ships" instruction.
  - Default to the **trim-to-remainder** form — the plan seed explicitly parks auto-execution and report-section surfacing in Deferred, so the backlog should retain a triageable entry for them rather than dropping them.
- **Fix or drop the stale `Seed:` line.** `#57`'s `Seed:` line (`BACKLOG.md:712`) still points at `plan-seeds/decomposition-convergence-loop.md`, now archived to `plan-seeds/archive/decomposition-convergence-loop.replaced.md`. In the same trim pass, repoint it to the archived path or drop the line — don't leave it citing the moved seed.
- **Reframe the stale `Origin` future-tense self-reference.** `#57`'s `Origin` paragraph says the manual re-decompose move is "exactly the structural path #57 would surface automatically" — a second future-tense self-reference that survives the trim-to-remainder form unless explicitly edited. In the same trim pass, rewrite it to describe the landed `plan-tool convergence` diagnostic (present tense, "now surfaces"), so it doesn't fail the body's "every surviving #57 hit describes the landed command, not future work" acceptance grep.
- **Leave `#59`'s reference to `#57` intact.** `#59 — Make the conceptual audit's sampling exhaustion-aware` says it "Blocks/de-risks #57 (signal trust)" — that is still true (the diagnostic's recurrence signal is only trustworthy once a single audit pass is exhaustive), so do not rewrite it. If `#57` is removed entirely, change `#59`'s "#57" references to name the shipped `plan-tool convergence` diagnostic instead of a dangling backlog number.
- **Do not** edit BACKLOG's `## Which file does my entry go in?` rules, the architecture map, or any unrelated entry.

## Tests

### Verification (non-code step)

This step changes no production code — no unit tests. Verify the artifacts instead:

- **RUNBOOK link integrity** — the reframed cross-reference's anchor (and any new in-doc link to the new subsection) resolves to a real heading; the GitHub-style slug matches.
- **RUNBOOK command accuracy** — the documented invocation (`plan-tool convergence <plan>`), the `--fail-on-findings` flag, and the exit-0-on-spinning behavior match the landed `plan_tool/cli/convergence_cmd.py` handler and `docs/cli/convergence.md` from step 4. Confirm the flag exists before citing it.
- **RUNBOOK fork accuracy** — the two printed repair commands (`plan-tool split …` and `plan-tool create --from-existing … --iterate`) match what `plan_tool/convergence_diagnosis.py: render_diagnosis` actually prints (per step 3).
- **CLAUDE import claim** — grep `plan_tool/convergence_diagnosis.py` to confirm its `plan_tool` imports are exactly `review_persistence`, `review`, `locator`, `convergence`, `granularity` and that it imports no `plan_tool.cli`, so the architecture paragraph's leaf claim is true at HEAD.
- **No stale forward references remain** — grep `RUNBOOK.md` and `BACKLOG.md` for "proposes to surface" / "#57" / "the manual version of what BACKLOG #57"; confirm every surviving hit describes the landed command, not future work.
- **No accidental TOC churn** — `RUNBOOK.md`'s `## Table of contents` is unchanged (the addition is a `###`).

## Acceptance criteria

- `RUNBOOK.md` has a `###` subsection under `## Workflow: completeness checks` documenting `plan-tool convergence <plan>`: read-only, prints spinning/converging verdict + the forked repair command, exits 0 (with `--fail-on-findings` flipping rc on spinning).
- `RUNBOOK.md`'s `### When repeated audit/apply doesn't converge` subsection no longer says BACKLOG #57 "proposes to surface automatically"; it points at the landed `plan-tool convergence` command.
- `RUNBOOK.md`'s `## Table of contents` is unchanged.
- `CLAUDE.md`'s `## Architecture` contains one paragraph naming `convergence_diagnosis.py` + `plan-tool convergence`, placed after the Granularity advisor paragraph and before the Exit-code convention line; `## What this is` is unchanged.
- `BACKLOG.md`'s `#57` is either trimmed to its still-deferred remainder (with a note that the read-only diagnostic shipped) or removed; no surviving text describes the read-only diagnostic as unbuilt.
- A grep for "proposes to surface" across `RUNBOOK.md` and `BACKLOG.md` returns no hit that describes the shipped read-only diagnostic as future work.

## References

- `docs/implementation-plans/plan-details/decomposition-convergence-loop/04-wire-plan-tool-convergence-plan-cli.md` — the exact CLI surface (flags, exit-code behavior, `--fail-on-findings`) the RUNBOOK subsection and CLAUDE paragraph must match.
- `docs/implementation-plans/plan-details/decomposition-convergence-loop/03-localized-vs-structural-fork-classifier.md` — the printed verdict text and the two forked copy-paste commands `render_diagnosis` emits, which the RUNBOOK fork bullets describe.
- `docs/implementation-plans/plan-details/decomposition-convergence-loop/01-convergence-diagnosis-report-history.md` — the reader's source (saved report history) and the zero-Claude / read-only posture the docs claim.
- `plan-seeds/archive/decomposition-convergence-loop.replaced.md` — the v1 scope boundary (read-only diagnostic, advisory only) vs. the Deferred items (auto-execution, report-section surfacing) that the BACKLOG #57 reframe must preserve.

## Deferred

- **README.md / `integrations/claude/SKILL.md` edits** — out of this step's `files:` list. If the convergence command warrants a mention in the conceptual docs or the agent skill, route it to a follow-up; this step covers only RUNBOOK/CLAUDE/BACKLOG.
- **`docs/cli/convergence.md` and the `docs/cli/README.md` row** — generated by `python -m plan_tool.cli_reference --write` in step 4, not hand-authored here.
- **Auto-execution and completeness-report surfacing of the diagnosis** — parked in the plan seed's Deferred; this step documents the read-only v1 only and (in the BACKLOG reframe) keeps a triageable entry for them.
