> **Auto-archived**: this plan was swept on 2026-06-14 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Document fingerprinted reconcile-family reuse across RESUME_FLOW.md, AUDIT_FLOW.md, and RUNBOOK.md

## Summary

- **Documents the reconcile-family reuse feature** (steps 1–5) across three docs: `docs/RESUME_FLOW.md` (split a now-half-false blanket claim), `docs/AUDIT_FLOW.md` (revise the `reconcile` "Reuse check" + Source map), and `RUNBOOK.md` (add the `--reuse` / `--no-reuse` / `--reuse-id` flag surface + the code-drift staleness warning).
- **Docs only — zero production code, zero tests.** Every symbol and flag named here is *delivered by steps 1–5*; this step describes upstream behavior accurately so a reader understands it, and must not "complete" any prose into an implementation.
- **Load-bearing decision:** treat the `RESUME_FLOW.md` and `AUDIT_FLOW.md` edits as **corrections, not additions** — both carry a standing blanket claim (reconcile "re-derives findings from the on-disk plan"; reconcile reuse is "default no") that the fingerprint-gated reuse silently invalidated. An append-only edit leaves the false claim standing.
- **On green:** the two flow docs split the **still-re-derived deterministic layer** from the **fingerprint-gated reused conceptual/claude axis** for the reconcile family; `RUNBOOK.md` carries a "Reusing a saved reconcile" subsection mirroring the existing `--reuse-audit` one, plus the attributed `path (step N: title)` code-drift warning; every CLI flag and symbol named resolves at HEAD (after steps 1–5 land).

## Table of Contents

- [Why](#why) — the standing claims the reuse feature invalidated
- [Files (creates vs edits)](#files-creates-vs-edits) — the three docs and the per-file edits
- [Implementation](#implementation) — the exact claims to revise in each doc
- [Verification](#verification) — flag/symbol grep battery + negative checks
- [Tests](#tests) — docs-only: no test file; the grep/inspection battery is the check
- [Acceptance criteria](#acceptance-criteria) — observable doc-content checks
- [References](#references) — the completeness-plan doc template + the argparse/symbol sources
- [Deferred](#deferred) — AUDIT_RESUME_FLOW.md and other out-of-footprint surfaces

## Why

- **The reconcile family now reuses saved sidecar findings, but three docs still claim it always re-derives or always re-runs.** Steps 1–2 made every reconcile sidecar carry `plan_fingerprint` + `code_fingerprint`; step 3 added `resolve_reusable_reconcile` to verdict them; step 4 gated the reuse prompts on fingerprint freshness; step 5 exposed `--reuse` / `--no-reuse` / `--reuse-id`. A reader trusting `docs/RESUME_FLOW.md`'s "`completeness` / `reconcile` ... re-derive findings from the on-disk plan", or `docs/AUDIT_FLOW.md`'s "`reconcile` ... offers to walk a previously saved review ... (default no)", concludes the opposite of the shipped behavior.
- **The operator-facing flags have no home.** `RUNBOOK.md` documents the completeness analog (`--reuse-audit` family) in full but says nothing about the reconcile family's `--reuse` / `--no-reuse` / `--reuse-id` or the code-drift staleness warning — so the feature is invisible to anyone reading the runbook.
- **Fixing it now closes the feature.** Step 5 is the last machinery/CLI piece; step 7 is the doc pass that makes the feature discoverable and stops the standing docs from contradicting it.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `docs/RESUME_FLOW.md` — revise the checkpoint-contract blanket claim that lumps `completeness` / `reconcile` as "re-derive findings from the on-disk plan" (the sentence under `## The checkpoint contract` beginning "Only `create` and `detail` write checkpoints"). Split the deterministic (re-derived) axis from the fingerprint-gated reused conceptual/claude axis; keep the still-true "do not write checkpoints" half and the pointer to `AUDIT_RESUME_FLOW.md`.
  - `docs/AUDIT_FLOW.md` — revise the `## `reconcile` — plan-vs-code fit (one claude call)` section's **step 1 "Reuse check"** bullet to describe fingerprint-gated reuse (plan **AND** code fingerprints), the still-re-derived deterministic primitives, and the tri-state flags; add Source-map rows for `resolve_reusable_reconcile` + the two fingerprint producers + the code-drift warning.
  - `RUNBOOK.md` — add a `### Reusing a saved reconcile (--reuse)` subsection under `## Workflow: per-subcommand reconcile`; revise the two reuse-prompt callouts under `## Workflow: review before running` (**Reuse-last-review prompt** / **Reuse-last-reconcile prompt**) to note the freshness gate; add the reconcile flags to the Quick-reference niche-flags parenthetical.

## Implementation

### `docs/RESUME_FLOW.md` — split the re-derive blanket claim

- **Target the sentence under `## The checkpoint contract`:** "Only `create` and `detail` write checkpoints; `completeness` / `reconcile` do not (they re-derive findings from the on-disk plan — see `AUDIT_RESUME_FLOW.md`)."
- **Keep true:** `completeness` / `reconcile` write **no checkpoints**. The checkpoint mechanism (`compute_input_hash` / `save_checkpoint` / `load_if_valid`) remains create/detail-only — do not claim reconcile uses checkpoints.
- **Correct the parenthetical reason.** The audit verbs re-derive only the **deterministic** layer from disk every run; their **single-claude-call conceptual axis** is reused from a **fingerprint-fresh saved sidecar** (a separate memoization from checkpoints, gated on `plan_fingerprint` **AND** `code_fingerprint`, not on a 30-day TTL). State this for **both** completeness and reconcile, and keep the `→ AUDIT_RESUME_FLOW.md` pointer where the reuse mechanics live.
- **Do not re-explain the fingerprint verdict here** — `RESUME_FLOW.md` is the shared-engine doc (checkpoints, `iteration_session`, crash handler); the sidecar-reuse verdict belongs to `AUDIT_RESUME_FLOW.md`. One corrected sentence + the cross-link is the whole edit.

### `docs/AUDIT_FLOW.md` — revise the reconcile Reuse check + Source map

- **Revise step 1 of `## `reconcile` — plan-vs-code fit (one claude call)`** (currently "**Reuse check:** offers to walk a previously saved review instead of spending a fresh claude call (default no, so unattended runs get a fresh review).") to state:
  - **Reuse is offered only on a fingerprint-fresh save** — the saved sidecar's captured **plan fingerprint AND code fingerprint** must both still match current disk; any plan edit or in-scope code change (including a deleted / newly-landed in-scope file) declines and re-audits.
  - **The deterministic primitives are never gated** — file-existence / deps / path-style / the looks-already-done heuristic run on every invocation, reuse or not (the cheap-correctness-always-runs invariant the completeness reuse path already documents).
  - **Tri-state flags drive it:** `--reuse` reuses when fresh (no prompt), `--no-reuse` always re-audits, `--reuse-id STEM` pins a specific saved sidecar; **unset prompts on a TTY and auto-decides under `--yes` / non-TTY**. Point to the `RUNBOOK.md` "Reusing a saved reconcile" subsection for the operator recipe (flag surface lives in the runbook, per the flag-vs-flow doc-home split).
  - **Note the two verdict paths:** `reconcile-plan` (kind `review`) recomputes the freshness verdict **inline** in `review_cmd.py`'s `_prompt_reuse_saved_review` (there is no `resolve_reusable_review`); `reconcile-code` and `detail --reconcile` route through the shared `resolve_reusable_reconcile` helper. Both apply the same plan-AND-code fingerprint gate.
- **Add rows to the `## Source map` table** (after "Save / load artifacts" / "Walk + apply"):
  - `Reconcile-sidecar reuse verdict` → `plan_tool/cli/reconcile.py` (`resolve_reusable_reconcile`, `ReusableReconcile`) for `reconcile-code` / `detail --reconcile`; `reconcile-plan` (kind `review`) recomputes the verdict inline in `plan_tool/cli/review_cmd.py` (`_prompt_reuse_saved_review`, no `resolve_reusable_review`) — delivered by step 3.
  - `Plan / code fingerprints` → `plan_tool/review_persistence.py` (`compute_plan_fingerprint`), `plan_tool/fingerprint.py` (`compute_code_fingerprint`) — note `compute_code_fingerprint` now lives in the `plan_tool/fingerprint.py` leaf (step 1's move), **not** `completeness_report.py`.
  - `Reuse gate + code-drift warning (CLI)` → `plan_tool/cli/reconcile.py` (`_prompt_reuse_saved`, `_warn_reuse_code_drift`), `plan_tool/cli/review_cmd.py` (`_prompt_reuse_saved_review`) — delivered by step 4.
- **Do not touch the `completeness` section** — its conceptual-reuse story is already correct (documented by the completeness plan's step 7). The reconcile section is the only stale one in this file.

### `RUNBOOK.md` — flags + code-drift warning

- **Add `### Reusing a saved reconcile (--reuse)` under `## Workflow: per-subcommand reconcile`**, mirroring the existing `### Reusing a saved conceptual audit (--reuse-audit)` subsection member-for-member, swapping the completeness specifics for the reconcile family:
  - **Applies to all three reconcile commands** — `reconcile-plan`, `reconcile-code`, and `detail --reconcile` (the `--reuse` family attaches to `p_run`/`p_reconcile_code`/`p_detail`/`p_review`, per step 5).
  - **What's reused.** Only the single-claude-call reconcile axis; the deterministic primitives run every invocation.
  - **When reuse is offered.** Only when the newest saved reconcile sidecar for that kind is **fresh** — its captured **plan fingerprint AND code fingerprint** both match current disk. Note the per-kind suffix: `reconcile-plan` writes a bare `<ts>.json` (kind `review`), `reconcile-code` writes `<ts>-run-reconcile.json`, `detail --reconcile` writes `<ts>-detail-reconcile.json`.
  - **The tri-state flag.** `--reuse` / `--no-reuse` is a `BooleanOptionalAction` whose **unset default prompts** on a TTY and auto-decides under `--yes` / non-TTY; `--reuse` forces reuse-when-fresh, `--no-reuse` always re-audits, unset = ask. Unset is **not** off.
  - **`--reuse-id STEM`.** Pins a specific saved sidecar by filename stem instead of newest-wins; an unresolved id prints a note and falls back to a fresh audit.
  - **Plan-stale decline.** A plan edit declines with a one-line staleness note on stderr (no per-file detail — the plan change is the operator's own edit).
  - **Code-drift decline + attributed warning.** An in-scope **code** change (or a deleted / newly-landed in-scope file) declines and emits a per-file warning naming each drifted path with its owning step as `path (step N: title)`, closed by the `detail --reconcile` recovery hint — the byte-for-byte shape of the live-edit drift warnings (both render through `render_attributed_path_line` / `reconcile_drift_hint` in `plan_tool/drift_detection.py`).
  - **Exit code unchanged.** A staleness decline is never a failure — it falls back to a fresh audit and exits 0 (the failure-to-complete-only exit convention).
  - **Example block:** `plan-tool reconcile-plan my-feature --reuse` / `--no-reuse` / `--reuse-id <stem>`, and the same for `reconcile-code` / `detail --reconcile --step N`.
- **Revise the two reuse-prompt callouts under `## Workflow: review before running`** (**Reuse-last-review prompt** and **Reuse-last-reconcile prompt**): the offer now fires **only when the saved sidecar is fingerprint-fresh**, and `--reuse` / `--no-reuse` / `--reuse-id` script the decision. Replace the standalone "default is **no** — saved reviews go stale as code moves" framing with "the freshness gate now catches that staleness directly; unset still defaults to a prompt." Link forward to the new `### Reusing a saved reconcile (--reuse)` subsection.
- **Update the Quick-reference niche-flags parenthetical** (currently "`--no-iterate`, `--reuse-audit`, `--dry-run`, gating, backends, …") to add `--reuse` so the reconcile reuse flag is discoverable alongside `--reuse-audit`.

### Foundational logic + shared locations

- **Foundational rule of this step:** "reconcile sidecar reuse is fingerprint-gated (plan AND code), the deterministic layer is always re-derived." That same rule already lives in prose for the completeness family in `docs/AUDIT_RESUME_FLOW.md` (the `## What's reused vs re-derived` section) and `RUNBOOK.md`'s `### Reusing a saved conceptual audit (--reuse-audit)`. Mirror that prose shape rather than inventing new framing — both families are deliberate structural siblings.
- **`docs/AUDIT_RESUME_FLOW.md` exercises the same rule for `detail --reconcile`** but is **out of this step's `files:` footprint** — see Deferred. Do not edit it here.

## Verification

This step changes **no production code** and adds **no test** — its deliverable is prose edits to three existing `.md` files. Verify with an inspection/tooling battery, not a unit suite:

- **Flag-spelling grep** — every CLI flag named in the new RUNBOOK prose resolves to an `add_argument` declaration at HEAD (after step 5 lands): grep `--reuse` / `--no-reuse` / `--reuse-id` against `plan_tool/cli/run_cmd.py`, `plan_tool/cli/authoring.py`, `plan_tool/cli/review_cmd.py`.
- **Symbol-resolution grep** — every symbol cited resolves to its named file: `resolve_reusable_reconcile` / `ReusableReconcile` / `_prompt_reuse_saved` / `_warn_reuse_code_drift` in `plan_tool/cli/reconcile.py`; `_prompt_reuse_saved_review` in `plan_tool/cli/review_cmd.py`; `compute_plan_fingerprint` in `plan_tool/review_persistence.py`; `compute_code_fingerprint` in `plan_tool/fingerprint.py`; `render_attributed_path_line` / `reconcile_drift_hint` in `plan_tool/drift_detection.py`.
- **Intra-doc link/anchor check** — the new RUNBOOK cross-links (`### Reusing a saved reconcile` anchor `#reusing-a-saved-reconcile---reuse`, the AUDIT_FLOW → RUNBOOK pointer, the RESUME_FLOW → AUDIT_RESUME_FLOW pointer) resolve as GitHub-style slugs; the `AUDIT_RESUME_FLOW.md` / `RESUME_FLOW.md` relative file links exist.
- **Negative "no surviving contradiction" greps:**
  - `grep -n "default no" docs/AUDIT_FLOW.md` returns no surviving "reuse ... default no" claim in the reconcile section.
  - `grep -n "re-derive findings from the on-disk plan" docs/RESUME_FLOW.md` returns no surviving blanket claim that lumps reconcile as re-derive-only (the corrected sentence splits the two axes).
- **Fingerprint-home accuracy** — confirm the Source-map row points `compute_code_fingerprint` at `plan_tool/fingerprint.py` (step 1's leaf), not `completeness_report.py`; grep `def compute_code_fingerprint` resolves to `plan_tool/fingerprint.py` only.

## Tests

- **No test file is added or modified** (`change_type: non-code`). The deliverable is prose edits to three existing `.md` files; there is no production behavior to assert, so no unit/component/integration test is authored, and the existing suite stays green untouched.
- **The "test" for this step is the [Verification](#verification) grep/inspection battery** run by hand (or in review): flag-spelling grep, symbol-resolution grep, intra-doc anchor/link check, the two negative "no surviving contradiction" greps, and the fingerprint-home accuracy grep. Each must pass against HEAD after steps 1–5 land.
- **Test-ordering directive:** none — a non-code doc step carries no green-before-completion test gate. The acceptance criteria below are the doc-content checks that stand in for assertions.

## Acceptance criteria

- `docs/RESUME_FLOW.md`'s checkpoint-contract sentence no longer asserts reconcile "re-derive[s] findings from the on-disk plan" as a blanket claim; it splits the re-derived deterministic axis from the fingerprint-gated reused conceptual axis and keeps the `AUDIT_RESUME_FLOW.md` pointer.
- `docs/AUDIT_FLOW.md`'s `reconcile` step-1 "Reuse check" describes plan **AND** code fingerprint gating, the ungated deterministic primitives, and the `--reuse` / `--no-reuse` / `--reuse-id` tri-state; the Source map has rows for `resolve_reusable_reconcile`, `compute_plan_fingerprint` (`review_persistence.py`), `compute_code_fingerprint` (`fingerprint.py`), and the code-drift warning.
- `RUNBOOK.md` has a `### Reusing a saved reconcile (--reuse)` subsection covering all three reconcile commands, the per-kind sidecar suffixes, the tri-state flag semantics, the `path (step N: title)` code-drift warning, and the exit-0-on-decline invariant; the two reuse-prompt callouts note the freshness gate; the Quick-reference niche-flags list includes `--reuse`.
- Every flag and symbol named in the three docs resolves at HEAD (verification greps return a hit in the cited file); no negative-grep contradiction survives.
- No production `.py` file and no test file is modified by this step.

## References

- `docs/implementation-plans/archive/2-reuse-saved-completeness-audit.md` (in-repo) — the template plan; its step 7 performed the analogous doc pass for the completeness family (`AUDIT_RESUME_FLOW.md` + `RUNBOOK.md`'s `--reuse-audit` subsection), the structure this step mirrors for reconcile.
- `RUNBOOK.md` (in-repo) — the existing `### Reusing a saved conceptual audit (--reuse-audit)` subsection is the section-for-section template for the new reconcile subsection.
- `plan_tool/drift_detection.py` (in-repo) — `render_attributed_path_line` / `reconcile_drift_hint`, the renderers the code-drift warning prose must name accurately.
- [argparse — BooleanOptionalAction](https://docs.python.org/3/library/argparse.html#argparse.BooleanOptionalAction) — the unset-default sentinel behavior the `--reuse` / `--no-reuse` prose describes (unset ≠ off).

## Deferred

- **`docs/AUDIT_RESUME_FLOW.md`** — out of this step's declared `files:`, but its `## What's reused vs re-derived` / `## Source map` cover `detail --reconcile` and currently describe only the completeness sidecar (`-completeness.json`, `resolve_reusable_audit`). After this plan, `detail --reconcile` also reuses a reconcile sidecar via `resolve_reusable_reconcile`. Add a reconcile-sidecar-reuse paragraph + Source-map rows there as a follow-up (or fold it into this step's footprint if the plan author prefers a single doc pass) — flagged for reconcile to catch.
- **`README.md` / `integrations/claude/SKILL.md`** — conceptual/overview docs; the reuse flags are operational and land in `RUNBOOK.md` per the flag-vs-concept doc-home convention. Not touched here.
- **`docs/RUN_FLOW.md`** — the run-gate gauntlet map; the reuse gate is a pre-claude reuse decision, not a run gate, so it stays out of that doc.
- **`tests/cli/package_surface_help.golden.txt`** — the `--reuse` flags attach to subcommand parsers (not `make_base_parser`), so the top-level `--help` golden is byte-unchanged; step 5 owns that assertion, and this docs step neither regenerates nor depends on it.

