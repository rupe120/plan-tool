> **Auto-archived**: this plan was swept on 2026-06-25 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Document the shipped `plan-tool scope-out` actuator across operator docs (RUNBOOK recipe, CLAUDE paragraph, README section, BACKLOG remainder, SKILL routers)

## Summary

Flip every operator-facing doc that mentions scope-out from "prose-only, executor ships later" to "runnable verb", now that steps 4–5 shipped `plan-tool scope-out <name> --step N` and the convergence diagnostic's `FORK_SCOPE_OUT` arm prints it. Edits six files: `RUNBOOK.md` (a dedicated scope-out recipe plus the runnable command in the re-decompose fork's 2c arm and the convergence-diagnosing section), `CLAUDE.md` (amend the one `## Architecture` paragraph that names the structural remedy vocabulary so it records the shipped executor module + command), `README.md` (a short scope-out subsection under *Iterating to convergence*), `BACKLOG.md` (mark #70's convergence-recommendation and executor halves shipped, trim the entry to its un-built convenience remainder), and the `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md` router pair (add the `## Subcommands at a glance` and `## Decision tree for common user asks` rows so an agent can surface the verb — the repo's mandatory six-file operator-command convention). The key decision: this step **inverts** the advisory plan's docs-side guard — the negative grep that required `plan-tool scope-out` to appear *only* inside "executor ships later" phrasing must be replaced by the runnable-command guard, because making the verb runnable in prose is the whole point. On green, every doc shows `plan-tool scope-out` as a real command, no doc still calls it not-yet-shipped, and the `#57`-attribution lines stay unchanged.

## Table of Contents

- [Why](#why) — the executor shipped; the docs still describe it as prose-only
- [Files (creates vs edits)](#files-creates-vs-edits) — six file edits, no new files
- [Implementation](#implementation) — per-doc edits, the SKILL router rows, placement anchors, and the advisory-handoff inversion
- [Tests](#tests) — verification appropriate to a docs-only step
- [Acceptance criteria](#acceptance-criteria) — checkable doc facts a reviewer can grep
- [References](#references) — the surfaces this step edits and the sibling-plan handoff
- [Deferred](#deferred) — multi-step carve, reconcile-side routing, the auto-bridge

## Why

Steps 1–5 built and wired the whole scope-out actuator — `plan_tool/scope_out.py` (renderer + narrow primitive + `scope_out_step` orchestrator), the `plan-tool scope-out` CLI (step 4), and the convergence diagnostic's runnable `FORK_SCOPE_OUT` line (step 5) — but the operator docs still describe scope-out as a *concept* the advisory plan (`structural-remedy-vocabulary`) documented prose-only, with the command deliberately not advertised as runnable. A command an operator can't find in the docs is effectively unshipped. This step closes the handoff the advisory plan left open: it turns the prose-only mentions into runnable references and trims the backlog entry that tracked the un-built executor, so the docs match the code at HEAD.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `RUNBOOK.md` — add a dedicated scope-out recipe (`### Carve a spinning region out of a plan (`plan-tool scope-out`)`) under the *re-decompose* workflow; add the runnable `plan-tool scope-out <slug> --step N` line into the re-decompose fork's scope-out (2c) arm and the *Diagnosing convergence* section; add the new heading to the `## Table of contents`. Leave the `#57`-attribution lines and the escalate-to-split prose unchanged.
  - `CLAUDE.md` — amend the single `## Architecture` paragraph naming the structural remedy vocabulary (added by the advisory plan, sits between **Convergence diagnostic** and **Decision telemetry**) so it records the shipped executor: module `plan_tool/scope_out.py`, command module `plan_tool/cli/scope_out_cmd.py`, the `scope_out_step` orchestrator and frozen `ScopeOutResult`, the seed-first apply-or-recommend gate, and that it spends no Claude. Leave `## What this is` unchanged (scope-out is an off-spine restructure verb, not a pipeline stage).
  - `README.md` — add a short scope-out subsection inside `## Iterating to convergence (`--iterate`)`, beside the existing re-split / re-seed re-decompose discussion, naming the runnable `plan-tool scope-out <name> --step N` carve-and-defer remedy. Add the subsection anchor to README's `## Table of contents`. Leave the `Two verbs sit off the main spine:` list and its count unchanged — scope-out is a restructure verb (like `split`/`merge`), not an off-spine verb.
  - `BACKLOG.md` — edit **#70** (`Unify the structural-remedy vocabulary as split/merge-by-altitude; add scope-out…`): mark scope (a) (the convergence scope-out/defer recommendation) and the executor half shipped, and trim the entry to its un-built convenience remainder (multi-step carve, reconcile-side routing, the auto-bridge from a spinning-region finding to the command), repointing its leftover to **#67**. Leave **#67** itself as the still-open reconcile-side code-grounded structural check.
  - `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md` — add the `plan-tool scope-out <name> --step N` rows to both routers in lockstep: a `## Decision tree for common user asks` row (beside the existing `split`/`merge` rows) for "a plan region keeps spinning / carve it out and defer it", and a `## Subcommands at a glance` row under the same grouping as `split`/`merge`. Leave each file's parallel-step out-of-scope sentence and the rest of the table unchanged.

## Implementation

**Drift-guard ordering (realizes the Risks "Doc double-write" mitigation).** `RUNBOOK.md` and `CLAUDE.md` are co-edited by the advisory plan (`structural-remedy-vocabulary`) and this step. Two ordering rules keep a watched-file drift guard from halting a `plan-tool run` of this plan mid-run: (1) run step 6 only after the advisory plan has fully landed at HEAD — it is an external precondition on top of the frontmatter `depends_on: [4, 5]`, and the per-doc "Defensive posture on the handoff" notes assume that baseline; (2) apply all six doc edits as one batch within this single step, never interleaved with a concurrent advisory-plan run, so the guard never observes a half-applied co-owned doc between sub-edits. If a pre-flight read shows the advisory paragraphs absent (advisory not yet landed), prefer halting and landing the advisory plan first over force-adding them here.

### `RUNBOOK.md`

- **Add the runnable line in the re-decompose fork's scope-out arm.** The advisory plan adds a scope-out (2c) arm beside the localized (2a, `plan-tool split`) and structural (2b, `create --from-existing`) arms under `### When repeated audit/apply doesn't converge — re-decompose, don't keep patching`. **Defensive posture on the handoff:** if a pre-flight read shows the 2c arm present (advisory at HEAD), replace its prose-only "executor ships later" phrasing with the runnable form; if it is absent (advisory not yet landed — at HEAD the fork has only 2a/2b arms), add the scope-out (2c) arm in that same slot beside 2a/2b rather than assuming a replacement target. Either way the arm names the runnable form: `plan-tool scope-out <plan> --step N` (carve the spinning region out of the plan, seed-first, then narrow). Keep the carve/defer rationale that distinguishes scope-out (reduce scope) from re-split (bisect one step) and re-seed (restart).
- **Add the runnable command to the convergence-diagnosing section.** `### Diagnosing convergence with `plan-tool convergence`` already lists the localized → `plan-tool split …` and structural → `plan-tool create … --from-existing` pre-filled commands. Add the scope-out fork: when `plan-tool convergence` reports `spinning` on a single severe, non-shrinking region, it now also prints `plan-tool scope-out <slug> --step N`. State that the diagnostic prints the **recommend-only / preview** form (no `--apply`, no `-y`) — the operator adds `--apply` consciously — so the printed line mirrors the executor's recommend-only default rather than a copy-paste mutation.
- **Add a dedicated recipe** under the re-decompose workflow: `### Carve a spinning region out of a plan (`plan-tool scope-out`)`. Cover the gate exactly as `scope_out_step` encodes it: recommend-only by default; mutates only when `--apply` (the opt-in) plus a TTY confirm hold; refuses with no write on any blocker (inbound dependent on the carved step, a downstream non-PENDING step that would renumber, an empty-plan result, a missing step); and is seed-first — the `create --from-existing` forward-seed is written to `plan-seeds/` before the plan is narrowed, so the carved work survives even if the narrow rolls back. Note it spends no Claude. Add a post-carve caveat: the saved completeness/reconcile report sidecars keep their pre-carve numbering after a narrow, so a `plan-tool convergence` read taken immediately after a carve can mis-attribute the carved step's spin trend to the survivor now holding its renumbered id and spuriously re-recommend scope-out — operators should run a fresh completeness/reconcile pass over the narrowed plan to re-ground history before trusting a post-carve `convergence` verdict.
- **Add the new recipe heading to `## Table of contents`.** Place its bullet adjacent to the re-decompose / convergence-diagnosing entries.
- **Do not touch** the `### The escalate-to-split bridge` prose or the `## Workflow: per-subcommand reconcile` table — reconcile-side scope-out routing is deferred (see Deferred). If any `#57`-attribution lines are present (they belong to the convergence-loop plan; at HEAD RUNBOOK carries no `#57` string), leave them unchanged too.

### `CLAUDE.md`

- **Amend the one structural-remedy `## Architecture` paragraph** (added by the advisory plan, between the **Convergence diagnostic** and **Decision telemetry** paragraphs). The advisory version describes the altitude × disposition model and notes the scope-out executor ships later; this step rewrites that forward-reference to record the shipped surface:
  - the leaf `plan_tool/scope_out.py` — `render_carved_seed` (deterministic seed renderer), `compute_narrow`/`apply_narrow` (drop-renumber + `depends_on` repair + detail migrate/archive, all-or-nothing with rollback), and `scope_out_step` (the apply-or-recommend orchestrator returning a frozen `ScopeOutResult`);
  - the command `plan-tool scope-out <name> --step N` wired by `plan_tool/cli/scope_out_cmd.py` (`cmd_scope_out` + `register`);
  - that scope-out is the **actuator** for the convergence diagnostic's `FORK_SCOPE_OUT` arm, spends **no Claude** (both halves deterministic, no `invoker=`), and is recommend-only unless `--apply` + confirm hold — the second instance of the apply-or-recommend gate shape after `launcher.py:escalate_to_split`.
- **Keep it to one paragraph** (the operator-command CLAUDE tier is a single summary paragraph); push the full operator walkthrough to RUNBOOK. Leave `## What this is` byte-for-byte unchanged.
- **Defensive posture on the handoff.** The structural-remedy paragraph is co-owned with the advisory plan. Assume the advisory paragraph is at HEAD and amend it in place; if a pre-flight read shows it absent (advisory not yet landed), add the paragraph in the same Convergence-diagnostic → Decision-telemetry slot rather than minting a second one elsewhere.

### `README.md`

- **Add a scope-out subsection under `## Iterating to convergence (`--iterate`)`,** next to the existing "re-decompose — re-split … or re-seed" discussion (the section already frames convergence failure as a mis-shaped plan). Keep it to a few bullets: when a region keeps spinning at high severity and won't converge, carve it out with `plan-tool scope-out <name> --step N` — recommend-only by default, mutating only under `--apply` + confirm; it writes a `create --from-existing` forward-seed to `plan-seeds/` first, then narrows the plan. Link to the RUNBOOK recipe for the full gate.
- **Add the subsection anchor to README's `## Table of contents`.**
- **Do not extend** the `Two verbs sit off the main spine:` list — scope-out is a restructure verb alongside `split`/`merge`, not an off-spine bridge like `annotate` / branch-awareness; touching that list would misfile the verb and risk the hardcoded "Two verbs" count.

### `BACKLOG.md`

- **Edit #70** (`#70 — Unify the structural-remedy vocabulary as split/merge-by-altitude; add scope-out…`):
  - mark its scope (a) (the convergence diagnostic emits a scope-out/defer recommendation) **shipped** — done by the advisory plan + step 5;
  - mark its scope (b) (the executor that narrows the plan and routes the carved part to a forward-seed) **shipped** — done by this plan's steps 1–4;
  - trim the entry to its un-built remainder so it isn't re-proposed whole: multi-step carve (today `scope-out` takes a single `--step N`), reconcile-side scope-out routing, and the auto-bridge that would wire a spinning-region finding straight to the command rather than printing it. Repoint the trimmed entry's Dependencies/Approach at **#67** (the code-grounded reconcile structural check that would feed reconcile-side routing).
- **Leave #67 open and unchanged** — its reconcile-side, code-grounded structural-decomposition check is not shipped by this plan.
- **Follow BACKLOG's own rule:** the entry stays in `BACKLOG.md` (forward-looking remainder), not `BUG_BACKLOG.md`; nothing here is broken behavior.

### `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md`

- **Add the scope-out rows to both routers in lockstep** — the repo's six-file operator-command convention requires a new verb to land in both SKILL routers, or an agent won't surface it (the gap the body's own Deferred section flagged as "do not ship the command undiscoverable in the routers"; resolved here by extending the footprint, not parking it).
- **`## Decision tree for common user asks`** — add a row for the spinning-region ask (e.g. "a plan region keeps spinning / carve it out and defer it") mapping to `plan-tool scope-out <name> --step N` (recommend-only by default; `--apply` + confirm to mutate; seed-first). Place it beside the existing `split`/`merge` rows.
- **`## Subcommands at a glance`** — add `scope-out <name> --step N` (carve a spinning region out, seed-first, then narrow) under the same grouping as `split`/`merge`.
- **Edit both files identically** (the pair is maintained in lockstep) and **leave the parallel-step out-of-scope sentence and the rest of each table unchanged** — add only the two scope-out rows.

## Tests

### Verification (non-code step)

This step changes no production code — verification is doc-accuracy and link checks, run after steps 4–5 (and the advisory plan) are at HEAD:

- **Runnable-command presence** — `grep -n "plan-tool scope-out" RUNBOOK.md README.md CLAUDE.md integrations/claude/SKILL.md integrations/codex/SKILL.md` returns the new runnable references in each file; the recipe heading is reachable from the RUNBOOK `## Table of contents`.
- **SKILL router rows (lockstep)** — both `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md` gain a `scope-out` row under `## Subcommands at a glance` and a `## Decision tree for common user asks` row; the two files' scope-out additions match, and each file's parallel-step out-of-scope sentence is unchanged.
- **Inversion of the advisory guard** — `grep -rn "scope-out" RUNBOOK.md CLAUDE.md README.md` shows **no** remaining "executor ships later", "prose-only", "not yet runnable", or "ships in a later plan" qualifier on a `plan-tool scope-out` mention. This supersedes the advisory plan's negative grep guard, which required the verb to appear *only* inside such phrasing.
- **Symbol accuracy** — every code symbol cited in the CLAUDE paragraph resolves at HEAD: `plan_tool/scope_out.py`, `plan_tool/cli/scope_out_cmd.py`, `scope_out_step`, `ScopeOutResult`, `cmd_scope_out`. Confirm with `grep`.
- **Diagnostic command form** — the RUNBOOK convergence-diagnosing line shows the recommend-only form (`plan-tool scope-out <slug> --step N`) with no `--apply`/`-y`, matching step 5's `_scope_out_command` output.
- **Untouched anchors** — `git diff` shows README's `Two verbs sit off the main spine:` list unchanged and CLAUDE's `## What this is` unchanged; any `#57`-attribution lines present in RUNBOOK are unchanged (at HEAD RUNBOOK carries no `#57` string, so this is vacuous unless the advisory plan landed them).
- **Internal links resolve** — the new README → RUNBOOK recipe link and any in-doc TOC anchors point at real headings (GitHub-slug match).
- **Backlog coherence** — `#70` no longer lists shipped scope (a)/(b) as pending; `#67` remains open; both stay in `BACKLOG.md`.

## Acceptance criteria

- `plan-tool scope-out` appears as a runnable command in `RUNBOOK.md`, `README.md`, and `CLAUDE.md`.
- No `plan-tool scope-out` mention in any of the six edited files still carries a "not yet shipped / executor ships later / prose-only" qualifier.
- Both `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md` carry a `scope-out` row under `## Subcommands at a glance` and a `## Decision tree for common user asks` row, added in lockstep, with each file's parallel-step out-of-scope sentence unchanged.
- `RUNBOOK.md`'s `## Table of contents` includes the new scope-out recipe heading, and the recipe documents the recommend-only default, the `--apply` + confirm gate, the four refusal blockers, and seed-first ordering.
- `CLAUDE.md` has exactly one `## Architecture` paragraph covering scope-out, placed between **Convergence diagnostic** and **Decision telemetry**, naming `plan_tool/scope_out.py`, `plan_tool/cli/scope_out_cmd.py`, `scope_out_step`, and `ScopeOutResult`; `## What this is` is unchanged.
- `README.md` has a scope-out subsection under `## Iterating to convergence` with a matching `## Table of contents` entry; the off-spine verbs list is unchanged.
- `BACKLOG.md` #70 marks the convergence recommendation and executor shipped and is trimmed to the multi-step-carve / reconcile-routing / auto-bridge remainder pointing at #67; #67 is unchanged.
- Any `#57`-attribution lines present in `RUNBOOK.md` are unchanged (vacuous at HEAD, where RUNBOOK carries no `#57` string — checkable only if the advisory plan landed them).

## References

- [argparse — subcommands](https://docs.python.org/3/library/argparse.html) — confirms the `scope-out --step N` flag surface this step documents matches the parser steps 4–5 wired.
- [dataclasses — frozen instances](https://docs.python.org/3/library/dataclasses.html) — the frozen `ScopeOutResult` (outcome ∈ applied / recommended / unsafe / empty-plan / step-missing) the CLAUDE paragraph summarizes.
- [GitHub Flavored Markdown — autolinked headings](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax) — heading-slug rules for the new TOC anchors and the README → RUNBOOK link.
- `plan-seeds/scope-out-executor.md` — the seed documenting the advisory-vs-executor split this step closes; read it for which surfaces the advisory plan deferred to this plan.

## Deferred

- **`docs/cli/scope-out.md`** — already generated and drift-guarded by step 4 (`python -m plan_tool.cli_reference --write`); not re-derived here.
- **Multi-step carve** — `plan-tool scope-out` carves one `--step N`; carving a contiguous multi-step region is left to #70's trimmed remainder.
- **Reconcile-side scope-out routing** — wiring scope-out into the reconcile path's code-grounded structural check is #67, still open; this step documents only the convergence-driven (audit-history) trigger.
- **Auto-bridge from a spinning-region finding to the command** — the diagnostic prints the runnable line; auto-applying it stays out of scope (mutation-gated), tracked in #70's remainder.
