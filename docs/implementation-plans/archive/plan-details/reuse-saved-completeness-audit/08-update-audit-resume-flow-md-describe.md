> **Auto-archived**: this plan was swept on 2026-06-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Document fingerprinted conceptual-audit reuse in `AUDIT_RESUME_FLOW.md` and the reuse flags + code-drift warning in `RUNBOOK.md`

## Summary

- Update `docs/AUDIT_RESUME_FLOW.md` to correct its now-stale central claim ("no resume *cache* here"): the **conceptual** axis of `completeness-audit` now reuses a fingerprinted saved sidecar when both the **plan fingerprint** and **code fingerprint** still match current disk, while the **deterministic** well-formedness battery is still re-derived from disk on every run. Revise the TL;DR, the "Why there's no resume cache" framing, the ASCII loop diagram, and the Source-map table.
- Update `RUNBOOK.md` to document the three new `completeness-audit` flags landed by step 6 — `--reuse-audit` / `--no-reuse-audit` (tri-state, unset = prompt) and `--reuse-audit-id STEM` — plus the attributed code-drift staleness warning, with a Quick-reference row and a new H3 under `## Workflow: completeness checks`.
- **Load-bearing decision:** docs only — this step changes no production code and adds no test. The forward symbols it describes (`resolve_reusable_audit`, `_resolve_audit_reuse`, `_warn_code_drift`, `compute_plan_fingerprint`, `compute_code_fingerprint`) are delivered by steps 1–6; this step's job is to make the operator-facing docs describe their behavior accurately, not to introduce them.
- **Observable result on green:** both docs describe reuse consistently — `AUDIT_RESUME_FLOW.md` no longer asserts the conceptual axis is uncached, and `RUNBOOK.md` tells an operator how to force/skip/pin reuse and how to read the code-drift decline. Every cross-doc link and CLI flag spelling resolves and matches the code landed in step 6.

## Table of Contents

- [Why](#why) — why the resume doc is now wrong and the runbook is silent on reuse.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two docs edited, with the edits per file.
- [Implementation](#implementation) — the section-by-section doc edits and the exact flag/symbol facts to state.
- [Tests](#tests) — n/a (non-code); see Verification.
- [Verification (non-code step)](#verification-non-code-step) — link, spelling, and accuracy checks for the prose.
- [Acceptance criteria](#acceptance-criteria) — checkable doc states a reviewer can confirm.
- [References](#references) — argparse `BooleanOptionalAction` and the in-repo surfaces these docs describe.
- [Deferred](#deferred) — `README.md` / `SKILL.md` mirrors and the `--json` reuse field left out of scope.

## Why

`docs/AUDIT_RESUME_FLOW.md` opens with "**No checkpoints — and that's the point**" and devotes a whole `## Why there's no resume *cache* here` section to the claim that `completeness` / `reconcile` re-derive **every** finding from disk and memoize nothing. Step 6 makes that claim half-wrong: the expensive conceptual audit (`audit_plan_until_stable`) is now substituted from a saved `-completeness.json` sidecar when both fingerprints match, so the conceptual axis **is** reused across runs while only the deterministic layer stays cache-free. A reader trusting the current doc would conclude a second `completeness-audit` always re-samples Claude — the opposite of the new behavior. Separately, `RUNBOOK.md`'s `## Workflow: completeness checks` documents `--iterate`, `--json`, `--audit-samples`, and `completeness-apply`, but says nothing about the new reuse flags or the code-drift staleness warning an operator will hit. This step closes both doc gaps; per the project convention that `completeness-audit` flags are a RUNBOOK surface (not `PLAN_FORMAT.md`, which is frontmatter-only), all runbook edits land in `RUNBOOK.md`.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `docs/AUDIT_RESUME_FLOW.md` — rewrite the TL;DR conceptual-cache bullet, reframe the `## Why there's no resume *cache* here` section to split the deterministic (uncached) layer from the conceptual (fingerprint-gated reuse) layer, redraw the ASCII loop diagram to show the reuse branch, and extend the `## Source map` table with the fingerprint/reuse symbols.
  - `RUNBOOK.md` — add Quick-reference rows for the three reuse flags; add a new H3 `### Reusing a saved conceptual audit (--reuse-audit)` under `## Workflow: completeness checks`; cross-link it from the `### Completeness with iteration` recipe in `## Workflow: drive an authoring task to convergence (--iterate)`.

## Implementation

### `docs/AUDIT_RESUME_FLOW.md`

**TL;DR (`## TL;DR`).** The current first bullet — "**No checkpoints — and that's the point.** These loops re-derive deterministic findings from the **on-disk plan** every run." — is correct for the deterministic layer but omits conceptual reuse. Edit it to keep the deterministic-re-derive claim and **add** a sibling bullet stating:
- The **conceptual** audit is reused across runs when a saved `-completeness.json` sidecar's **plan fingerprint AND code fingerprint** both still match current disk; otherwise it re-samples Claude fresh.
- Reuse is operator-gated by `--reuse-audit` / `--no-reuse-audit` / `--reuse-audit-id`; the **deterministic well-formedness battery runs on every invocation regardless** (reuse never gates it).
- Keep the "a crash loses nothing durable" bullet unchanged.

**Reframe `## Why there's no resume *cache* here`.** Retitle to `## What's reused vs re-derived` (or similar) so the heading no longer asserts a blanket no-cache. Replace the single-paragraph claim with a two-bullet split:
- **Deterministic findings — re-derived from disk every run, no cache.** file-check, deps, body/detail coverage (`plan_tool/review.py: collect_deterministic_findings`, CLI `_run_deterministic_checks`). The on-disk plan is the source of truth; a re-run sees only the findings still open.
- **Conceptual audit — fingerprint-gated reuse from the saved sidecar.** The single-Claude-call audit (`plan_tool/review.py: check_plan_audit`, driven by `audit_plan_until_stable`) is now the reusable axis. `plan_tool/completeness_report.py: resolve_reusable_audit` locates the newest `-completeness.json`, recomputes `compute_plan_fingerprint` (`plan_tool/review_persistence.py`) and `compute_code_fingerprint` (`plan_tool/completeness_report.py`), and returns a `ReusableAudit` whose `fresh` is true only when **both** fingerprints match. On `fresh`, the CLI substitutes the saved conceptual recs for a fresh `audit_plan_until_stable` call; on any mismatch it declines and re-audits.

**Redraw the ASCII loop diagram.** The current diagram shows `re-derive deterministic findings + conceptual audit` as one box. Split the conceptual step into a reuse branch — show `fresh sidecar? ──yes──► reuse saved conceptual recs` / `──no──► sample conceptual audit (Claude)`, with the deterministic box still unconditional above it. Keep it ASCII, keep it under ~20 lines.

**Extend `## Source map`.** Add rows (the table is `| Concern | File |`):
- `Conceptual-audit reuse verdict` → `plan_tool/completeness_report.py` (`resolve_reusable_audit`, `ReusableAudit`)
- `Plan / code fingerprints` → `plan_tool/review_persistence.py` (`compute_plan_fingerprint`), `plan_tool/completeness_report.py` (`compute_code_fingerprint`)
- `Reuse decision + code-drift warning (CLI)` → `plan_tool/cli/completeness_cmd.py` (`_resolve_audit_reuse`, `_warn_code_drift`)
- Fix the existing `Finding re-derivation (no cache)` row — it currently lists `plan_tool/review.py` (`collect_deterministic_findings`, `check_plan_audit`), but `check_plan_audit` is the conceptual single-call audit that is now reusable, not a deterministic no-cache source. Drop `check_plan_audit` from that row (leave `collect_deterministic_findings`); the conceptual `check_plan_audit` belongs to the new reuse rows above.
- Keep the existing `cmd_completeness` / `apply_finding` / `iteration_session` rows.

Do **not** touch the `## Crash / interrupt recovery` or `## Relationship to create / detail recovery` sections — reuse changes neither the crash posture nor the create/detail continuation story.

### `RUNBOOK.md`

**Quick-reference rows (`## Quick reference` table).** Insert three rows adjacent to the existing `completeness-audit` rows (after the `Machine-readable completeness for CI gating` row near `--json`):
- `Reuse a saved conceptual audit when plan+code are unchanged (skip the expensive re-sample)` → `plan-tool completeness-audit <name> --reuse-audit`
- `Always re-audit; never reuse a saved conceptual audit` → `plan-tool completeness-audit <name> --no-reuse-audit`
- `Reuse a specific saved audit by its sidecar stem` → `plan-tool completeness-audit <name> --reuse-audit-id <stem>`

**New H3 under `## Workflow: completeness checks`.** Add `### Reusing a saved conceptual audit (--reuse-audit)`, placed after the `### Test-strategy alignment checks` H3 and before `### Address conceptual gaps (completeness-apply)`. State, as bullets:
- **What's reused.** Only the conceptual axis (`audit_plan_until_stable`, the minutes-each Claude sampling). The deterministic battery (`_run_deterministic_checks`) runs every time — reuse never weakens a run.
- **When reuse is offered.** Only when the newest saved `-completeness.json` is **fresh** — its captured **plan fingerprint AND code fingerprint** both match current disk. Any plan edit or in-scope code change declines and re-audits.
- **The tri-state flag.** `--reuse-audit` / `--no-reuse-audit` is a `BooleanOptionalAction` whose **unset default prompts** (interactive TTY) or auto-decides (non-TTY / `--yes`): `--reuse-audit` forces reuse-when-fresh, `--no-reuse-audit` always re-audits, unset = ask. Pin the tri-state explicitly so an operator knows unset ≠ off.
- **`--reuse-audit-id STEM`.** Pins a specific saved sidecar by its filename stem (e.g. `20260611-123456-completeness`) instead of newest-wins.
- **Plan-stale decline.** A plan edit declines with a one-line note on stderr; no warning detail (the plan change is the operator's own edit).
- **Code-drift decline + attributed warning.** An in-scope **code** change (or a deleted/newly-landed in-scope file) declines and emits a per-file warning naming each drifted path with its owning step as `path (step N: title)`, closed by the `detail --reconcile` recovery hint. State that this warning shares the byte-for-byte shape of the live-edit drift warnings (single-sourced through `render_attributed_path_line` / `reconcile_drift_hint`).
- **Stream split.** The reuse line, plan-stale note, and code-drift attribution all go to **stderr**; the grouped report goes to **stdout** — so `2>/dev/null` hides the reuse chatter but keeps the report.
- **Exit code unchanged.** A staleness decline is never a failure — it falls back to a fresh audit and exits 0 (the failure-to-complete-only exit convention). The warning is informational.

Add a worked example block:
```bash
plan-tool completeness-audit my-feature                      # prompt (TTY) / auto-decide (non-TTY)
plan-tool completeness-audit my-feature --reuse-audit        # reuse when fresh, no prompt
plan-tool completeness-audit my-feature --no-reuse-audit     # always re-audit
plan-tool completeness-audit my-feature --reuse-audit-id 20260611-123456-completeness
```

**Cross-link from the iterate recipe.** In `## Workflow: drive an authoring task to convergence (--iterate)` → `### Completeness with iteration`, add one sentence noting that `--reuse-audit` substitutes the up-front `audit_plan_until_stable` call with saved findings when fresh — so a second `--iterate` run on an unchanged plan+code skips the conceptual re-sample — and link to the new `### Reusing a saved conceptual audit (--reuse-audit)` H3.

**No other RUNBOOK edits.** Do **not** add reuse text to the `## Backends` section or the `## Quick reference` backend rows — reuse is orthogonal to backend selection. Do **not** edit `PLAN_FORMAT.md` (frontmatter-only; reuse adds no frontmatter field).

## Tests

Non-code step — no unit tests. See [Verification (non-code step)](#verification-non-code-step).

### Verification (non-code step)

Changes only Markdown prose; verify by inspection and tooling rather than pytest:

- **Flag spellings match step-5 argparse.** Grep `plan_tool/cli/completeness_cmd.py` for `--reuse-audit`, `--no-reuse-audit`, `--reuse-audit-id` (the `register` function's `p_completeness.add_argument` calls) and confirm every flag spelled in both docs matches a real argument `dest`/option string. A doc flag with no code match is the failure to catch.
- **Symbol citations resolve** (verify after step 6 is merged)**.** Each symbol named in `AUDIT_RESUME_FLOW.md`'s Source map (`resolve_reusable_audit`, `compute_plan_fingerprint`, `compute_code_fingerprint`, `_resolve_audit_reuse`, `_warn_code_drift`) resolves via `grep -rn <symbol> plan_tool/` to the cited file. These symbols are delivered by steps 1–6; run this check only once `depends_on: 6` has landed, as none exist on the branch before then.
- **Internal anchors resolve.** The new `RUNBOOK.md` `### Reusing a saved conceptual audit (--reuse-audit)` H3 and the iterate-section cross-link use matching GitHub-slug anchors (`#reusing-a-saved-conceptual-audit---reuse-audit`); the `AUDIT_RESUME_FLOW.md` intra-doc links to `RESUME_FLOW.md` / `AUDIT_FLOW.md` still resolve to real files under `docs/`.
- **No contradiction survives.** `grep -n "no resume" docs/AUDIT_RESUME_FLOW.md` returns no bullet still asserting the conceptual axis is uncached; the TL;DR and the reframed section agree that conceptual = fingerprint-gated reuse, deterministic = re-derived.
- **Stream-split claim is accurate.** Confirm against step-5 wiring that the reuse/stale/drift lines route to `sys.stderr` (the `error`/`warn`/`tool(..., stream=sys.stderr)` calls in `_warn_code_drift` / the reuse path) before documenting the `2>/dev/null` tip.

## Acceptance criteria

- `docs/AUDIT_RESUME_FLOW.md` TL;DR contains a bullet stating the conceptual audit is reused when **both** plan and code fingerprints match, and that the deterministic battery runs every run regardless.
- `docs/AUDIT_RESUME_FLOW.md` has no remaining sentence asserting `completeness-audit` memoizes nothing / always re-samples the conceptual axis.
- `docs/AUDIT_RESUME_FLOW.md` `## Source map` table includes rows for `resolve_reusable_audit`, the two fingerprint helpers, and the `_resolve_audit_reuse` / `_warn_code_drift` CLI helpers, each with a correct file path.
- `RUNBOOK.md` `## Quick reference` table has rows for `--reuse-audit`, `--no-reuse-audit`, and `--reuse-audit-id`.
- `RUNBOOK.md` contains an H3 `### Reusing a saved conceptual audit (--reuse-audit)` documenting the tri-state default, the both-fingerprints freshness gate, the attributed code-drift warning with `path (step N: title)` shape, the stderr/stdout stream split, and the exit-0-on-decline behavior.
- `RUNBOOK.md` `### Completeness with iteration` cross-links the new reuse H3.
- Every flag and symbol named in both docs resolves against `plan_tool/` at HEAD (verify after step 6 is merged — the cited symbols don't exist on the branch before `depends_on: 6` lands); all intra-doc anchors and file links resolve.

## References

- [argparse — BooleanOptionalAction](https://docs.python.org/3/library/argparse.html#argparse.BooleanOptionalAction) — confirms the `--reuse-audit` / `--no-reuse-audit` tri-state (unset default ≠ explicit off) the runbook documents.
- `plan_tool/cli/completeness_cmd.py` (in-repo) — the `register` function (flag spellings) and the step-5 `_resolve_audit_reuse` / `_warn_code_drift` helpers whose behavior the runbook H3 narrates.
- `plan_tool/drift_detection.py` (in-repo) — `render_attributed_path_line` and `reconcile_drift_hint`, the single-sourced renderers behind the `path (step N: title)` code-drift warning the docs describe as byte-identical to live-edit drift warnings.
- `plan_tool/completeness_report.py` (in-repo) — `resolve_reusable_audit` / `ReusableAudit` and `compute_code_fingerprint`, the reuse verdict and code-fingerprint surfaces the Source map cites.

## Deferred

- `README.md` and `integrations/claude/SKILL.md` reuse mentions — these docs carry conceptual overviews; mirroring the reuse story there is a separate sweep, not part of this RUNBOOK/flow-doc step. Track if the conceptual overview drifts.
- Documenting any `--json` reuse field (e.g. a `reused: true` marker in the machine-readable completeness output) — only if step 6 actually added one; if it didn't, there's nothing to document and no `--json` schema row changes here.
- `PLAN_FORMAT.md` — intentionally untouched; reuse adds no frontmatter field, so the frontmatter spec has no reuse surface.
