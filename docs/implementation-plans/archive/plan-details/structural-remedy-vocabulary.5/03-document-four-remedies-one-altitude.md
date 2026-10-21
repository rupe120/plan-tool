> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Document the four remedies as one altitude × disposition model and trim BACKLOG #70 plus its was-#67 subsection

## Summary

- Documents the tool's four structural remedies — **re-split**, **scope-out**, **merge / re-ground**, **re-seed** — as one **altitude × disposition model** across `CLAUDE.md` and `RUNBOOK.md`, and trims `BACKLOG.md` **#70** plus its **was-#67** subsection so #70 keeps only the un-shipped scope-out actuator while the former-#67 subsection keeps its split-detection advisory remainder and auto-bridge remainder.
- No production code changes. Steps 1 and 2 (deps) added the advisory arms in code — the scope-out fork-arm (`plan_tool/convergence_diagnosis.py: FORK_SCOPE_OUT`) and the reconcile re-ground finding (`plan_tool/review.py`). This step makes the docs describe those arms and the shared model.
- Key decision: frame the four remedies as one model rather than four primitives — **scope-out is a plan-scope split with the carved side deferred to a forward-seed; merge / re-ground is the inverse of split; re-seed is the limit (split everything / restart)**. State the **advisory-now / actuator-later** split everywhere: detection and recommendation ship in this plan, the `plan-tool scope-out` executor ships in the follow-up `scope-out-executor` plan.
- On green: `CLAUDE.md`'s Architecture section names the model and the scope-out fork-arm; `RUNBOOK.md`'s convergence and reconcile workflows list scope-out and re-ground beside re-split and re-seed; `BACKLOG.md` #70 points only its scope-out actuator at the follow-up plan, and #70's was-#67 subsection keeps the un-shipped split-detection advisory and auto-bridge remainders.

## Table of Contents

- [Why](#why) — the remedy vocabulary is real in code but undocumented as one model
- [Files (creates vs edits)](#files-creates-vs-edits) — three in-scope docs, all edits
- [Implementation](#implementation) — the per-file edits and the altitude × disposition framing
- [Tests](#tests) — none; see Verification
- [Verification (non-code step)](#verification-non-code-step) — doc-accuracy and grep checks
- [Acceptance criteria](#acceptance-criteria) — checkable doc states
- [References](#references) — the plan-level docs relevant to this step
- [Deferred](#deferred) — surfaces this step deliberately leaves alone

## Why

- The four structural remedies now **exist in code but are scattered and undocumented as one idea.** `granularity.py` owns split/merge, `convergence_diagnosis.py` owns re-seed and (after step 1) scope-out, and (after step 2) `review.py` emits a reconcile re-ground finding. A reader has no single place that says these are one `split`/`merge` axis parameterized by altitude and disposition.
- The current docs are **stale against steps 1 and 2.** `CLAUDE.md`'s **Convergence diagnostic** paragraph says the loop "forks localized over-pack (re-split one step) vs structural (re-seed)" — it never mentions the new scope-out sub-arm. `RUNBOOK.md`'s convergence diagnosis lists only two spinning arms (split, re-seed). Reconcile's new code-grounded re-ground finding has no operator note.
- `BACKLOG.md` **#70** still describes its **whole** scope, including the absorbed former **#67** work, as forward work, but this plan ships the scope-out advisory arm and the re-ground / merge advisory arm. Leaving it unedited would re-propose work already done and hide which remainders are still unshipped.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `CLAUDE.md` — update the **Convergence diagnostic (`convergence_diagnosis.py`)** Architecture paragraph to name the scope-out sub-arm; update the **Granularity advisor (`granularity.py`)** paragraph to name reconcile's second `granularity-merge` producer; add one new Architecture paragraph stating the altitude × disposition model.
  - `RUNBOOK.md` — extend `### Diagnosing convergence with `plan-tool convergence`` with the scope-out spinning arm and the four-remedy model; add a scope-out repair path to `### When repeated audit/apply doesn't converge — re-decompose, don't keep patching`; add a re-ground note under `## Workflow: per-subcommand reconcile`.
  - `BACKLOG.md` — rewrite **#70** and its **was-#67** subsection: mark the shipped advisory arms done, point only #70's scope-out actuator at `plan-seeds/scope-out-executor.md`, and keep the former-#67 split-detection advisory and auto-bridge remainders open.

## Implementation

### `CLAUDE.md`

- **Update the Convergence diagnostic paragraph.** In the sentence "then forks **localized over-pack** (re-split one step) vs **structural** (re-seed and re-decompose)", split the localized arm into two sub-arms: **re-split** vs **scope-out / defer**. State that scope-out (`FORK_SCOPE_OUT`) fires when a co-located region on the resolved step is **severe and not improving** (`last_severity ≥ high` AND non-decreasing first→last trend), renders **prose-only** (no runnable command), and waits on the follow-up executor plan. Keep the structural re-seed arm unchanged.
- **Update the Granularity advisor paragraph.** The line "`granularity-merge` is recommend-only" stays true. Add that `granularity-merge` now has a **second producer**: reconcile's code-grounded re-ground finding (`review.py`, fired on **≥2 distinct already-built steps**, scoped to the reconcile lane), which reuses the `granularity-merge` **literal** so it routes to the neutral `triage_reason` branch — never the split bridge. Do not claim a new source token; scope-out introduces none.
- **Add one new Architecture paragraph, the unified model.** Place it **after the Convergence diagnostic paragraph and before the Decision telemetry paragraph** (it ties together the escalate-to-split bridge, the granularity advisor, and the convergence diagnostic, all above it). Title it **Structural remedy vocabulary** and state, terse and bulleted-in-prose:
  - The four remedies are one `split`/`merge` axis parameterized by **altitude** (a **step** → two siblings, vs the **plan's scope** → narrowed plan + carved-out remainder) and **disposition of the carved side** (kept as a sibling step, vs carved out to a **forward-seed**).
  - **re-split** = step-altitude split, both halves kept (`granularity-split` → `escalate_to_split` / `plan-tool split`; also the `convergence` localized fork `FORK_LOCALIZED` / `_split_command`, which emits the same `plan-tool split` recommendation).
  - **scope-out** = plan-scope split, carved side deferred to a forward-seed (`convergence` localized fork-arm `FORK_SCOPE_OUT`, prose-only; executor in `scope-out-executor`). It is **triggered local** (one resolved step) but **acts at plan scope** (carves that step out) — state both halves.
  - **merge / re-ground** = the inverse of split (`granularity-merge` → `plan-tool merge`; reconcile's already-built re-ground finding re-baselines a ≥2-step set).
  - **re-seed** = the limit, split everything / restart (`convergence` structural fork `FORK_STRUCTURAL` → `create --from-existing`).
  - One closing clause: **detection and recommendation are unconditional; mutation stays gated** — scope-out's executor is the follow-up plan, not this one.
- **Leave `## What this is` unchanged.** These remedies are off-spine diagnostics, not a pipeline stage — the pipeline line does not change.

### `RUNBOOK.md`

- **Extend `### Diagnosing convergence with `plan-tool convergence``.** The spinning bullet list currently has two arms (localized over-pack → `plan-tool split …`; structural → `create --from-existing …`). Add a **third** bullet: **localized + severe-and-not-improving → scope-out / defer** — `plan-tool convergence` prints a **prose-only** scope-out recommendation (carve the over-packed step out and defer it), **renders no runnable command yet**, and the executor ships in the `scope-out-executor` plan. Note the always-exit-0, zero-Claude contract is unchanged.
- **Add a short four-remedy framing.** Near the same convergence subsection, add one tight paragraph or bullet block naming the altitude × disposition model so the operator doc carries the full version (the operator-facing home for the model, vs `CLAUDE.md`'s one-paragraph summary). Map each remedy to its operator command exactly as `CLAUDE.md` does.
- **Add a scope-out repair path to `### When repeated audit/apply doesn't converge — re-decompose, don't keep patching`.** The fork lists 2a (localized re-split) and 2b (structural re-seed). Add **2c — severe-and-not-improving region → scope-out / defer**: when a region stays `high`+ and stops shrinking (in-place patching is backfiring, the PPW `prune`/clone-lifecycle case), the right move is to **carve that step out of the plan and defer it**, not re-split a third time. State the actuator is not yet a command (`plan-tool convergence` recommends it in prose; the executor ships later).
- **Add a re-ground note under `## Workflow: per-subcommand reconcile`.** State that `reconcile-plan` now surfaces a **code-grounded re-ground finding** when **≥2 distinct steps** are already implemented in the code — advisory, sourced `granularity-merge`, tallied in the `Findings:` banner, **never flips the exit code**. The remedy is **re-ground / re-baseline** (mark done or re-decompose), not a blind `merge`, because the flagged steps may be non-adjacent or non-`PENDING`.
- **Keep the "manual reading of the same signal" pointer (the re-decompose subsection's link to `plan-tool convergence`) intact, but apply one narrow wording fix to it.** That line calls the command's output a "re-split-vs-re-seed fork"; after step 1 added `FORK_SCOPE_OUT` to `render_diagnosis`, `plan-tool convergence` computes a three-way fork (re-split / scope-out / re-seed), so the two-way phrasing now undercounts and disagrees with the 2a/2b/2c list it sits beside. Widen only that "re-split-vs-re-seed" phrasing to name the three-way fork; leave the pointer and the rest of the line otherwise unchanged (it belongs to the convergence-loop plan).

### `BACKLOG.md`

- **Trim #70 to its actuator remainder.** The advisory arm (the `convergence` scope-out / defer recommendation) **ships in this plan** — drop it from #70's open scope and mark it done. Keep only **(b) the executor**: the `plan-tool scope-out` command that **narrows the plan and routes the carved side to a forward-seed**. Repoint Dependencies/Approach at `plan-seeds/scope-out-executor.md` and state the model framing now lives in `CLAUDE.md`/`RUNBOOK.md`. Keep the entry (the actuator is unbuilt), do not delete it.
- **Update #70's was-#67 subsection to its un-shipped remainders.** Step 2 ships only the code-grounded **re-ground / merge** detection (≥2 already-built steps) — mark *that arm* done, not the former #67's whole detection scope. Keep two un-built remainders in the subsection: (a) the **code-reality-reveals-a-split** detection the former #67's "re-seed / merge / split" title also scopes (no producer lands in this plan), and (b) an **automatic bridge** from the re-ground finding to an actuating command (today it is recommend-only, like `granularity-merge`). State the re-ground finding itself is advisory and shipped; the split-detection and wired actuator may return later. Do **not** make this subsection point at `plan-seeds/scope-out-executor.md`; only #70's scope-out actuator uses that follow-up plan.
- **Touch only #70 and its was-#67 subsection.** Leave the triage framework, the `T2` cluster line that names `#70`/`#67`, and every other entry unchanged in substance — a stale cross-reference fix is allowed only where it now misstates shipped state.

## Tests

No automated tests — this step changes only Markdown docs and adds no code path.

### Verification (non-code step)

- **`git status` scope** — only `CLAUDE.md`, `RUNBOOK.md`, `BACKLOG.md` change; no `plan_tool/**` or `tests/**` files in the diff.
- **Symbol accuracy vs HEAD** — every code symbol cited in the new prose returns a hit. Already resolvable at HEAD: `grep -n "FORK_STRUCTURAL\|FORK_LOCALIZED" plan_tool/convergence_diagnosis.py` and the `granularity-split` / `granularity-merge` literals in `plan_tool/granularity.py`. Step-gated (resolve only after steps 1/2 land): `grep -n "FORK_SCOPE_OUT" plan_tool/convergence_diagnosis.py` (step 1) and `grep -n "_GRANULARITY_MERGE_SOURCE\|reconcile_lane" plan_tool/review.py` (step 2).
- **Cross-doc consistency** — the four remedy names and their producer/actuator mappings read identically in `CLAUDE.md`'s new paragraph and `RUNBOOK.md`'s convergence subsection (same four labels, same commands).
- **Forward-ref guard** — no doc renders a runnable `plan-tool scope-out …` line; `grep -rn "plan-tool scope-out" CLAUDE.md RUNBOOK.md` shows it only inside prose-only / "executor ships later" phrasing, never as a copy-paste command.
- **Re-decompose pointer preserved** — `git diff RUNBOOK.md` shows the "manual reading of the same signal" line still points at `plan-tool convergence`, with only its "re-split-vs-re-seed fork" phrasing widened to the three-way (re-split / scope-out / re-seed) fork and no other edit to the line; `git diff BACKLOG.md` shows none.
- **Markdown links resolve** — any in-doc anchor links added (e.g. to the convergence subsection) point at real headings; `plan-tool validate` and the docs drift guards that already run in the suite stay green.
- **No drift-guarded generated doc edited** — `docs/cli/**` is untouched (this step documents concepts, not a new CLI surface).

## Acceptance criteria

- `CLAUDE.md` contains a new `## Architecture` paragraph naming the **altitude × disposition** model and all four remedies (re-split, scope-out, merge / re-ground, re-seed) with their producers; it sits between the Convergence diagnostic and Decision telemetry paragraphs.
- `CLAUDE.md`'s Convergence diagnostic paragraph names the **scope-out** sub-arm (`FORK_SCOPE_OUT`, prose-only) of the localized fork.
- `CLAUDE.md`'s Granularity advisor paragraph names reconcile's **second `granularity-merge` producer** (the ≥2-already-built-step re-ground finding) and still says merge is recommend-only.
- `RUNBOOK.md`'s `### Diagnosing convergence` spinning list has **three** arms (split, scope-out, re-seed); the scope-out arm states it renders no runnable command yet.
- `RUNBOOK.md`'s re-decompose fork has a **scope-out (2c)** path, and `## Workflow: per-subcommand reconcile` notes the advisory re-ground finding (≥2 steps, never flips rc).
- `BACKLOG.md` **#70** describes only the **scope-out actuator** remainder, marks the scope-out advisory arm shipped, and points that actuator at `plan-seeds/scope-out-executor.md`; #70's **was-#67** subsection marks the re-ground / merge detection shipped and retains its two un-built remainders (the code-reality-reveals-a-split detection and the auto-bridge).
- No `plan-tool scope-out …` line is rendered as a runnable command in any doc; the re-decompose subsection's "manual reading of the same signal" line keeps its `plan-tool convergence` pointer, with only its two-way "re-split-vs-re-seed fork" phrasing widened to name the three-way fork; `git status` shows only the three in-scope files changed.

## References

- `BACKLOG.md` #70 and its was-#67 subsection — the entry this step trims to the advisory/actuator split; read for the original full scope and the origin/dependencies you keep only for the scope-out actuator.
- `plan-seeds/scope-out-executor.md` — the follow-up executor plan that flips the prose-only scope-out recommendation into a runnable `plan-tool scope-out` command; only #70's scope-out actuator points here.
- `plan_tool/convergence_diagnosis.py` — `FORK_LOCALIZED` / `FORK_STRUCTURAL` / `FORK_SCOPE_OUT`, `_split_command` / `_reseed_command`, `render_diagnosis`; the convergence-side producers the docs describe (scope-out added by step 1).
- `plan_tool/review.py` — `heuristic_already_done`, `_heuristic_recommendation`, `STRUCTURAL_SOURCES`, `triage_reason`; the reconcile re-ground finding (step 2) the docs describe.
- `plan_tool/granularity.py` — the `granularity-split` / `granularity-merge` source-token literals named in the model and their exclusion from `APPLY_ELIGIBLE_SOURCES`.
- `MISSION.md` — the *always surface the more-correct plan* principle (detection unconditional, mutation gated) the docs cite as the reason scope-out is advisory-now / actuator-later.

## Deferred

- **README.md and the `integrations/{claude,codex}/SKILL.md` router rows** — not edited here, on two distinct grounds. (a) The **operator-command surface** (README's command tables + the SKILL router rows) belongs to the `scope-out-executor` plan when `plan-tool scope-out` ships — this step adds no operator command. (b) README's **`## Iterating to convergence` concept passage** (the "re-decompose — re-split one step, or re-seed the plan" enumeration) *is* concept-level remedy guidance, not a command surface, and scope-out now applies to it (after step 1 `plan-tool convergence` recommends scope-out in prose). It stays a **two-way** enumeration here deliberately: README is the operator-command home, so naming scope-out in its prose before the `plan-tool scope-out` command exists would forward-ref a runnable remedy README cannot yet point at — the same forward-ref the plan avoids elsewhere. It widens to three arms in the `scope-out-executor` plan that ships the command. The three-way framing lands now only in `CLAUDE.md`/`RUNBOOK.md`, the concept docs.
- **`docs/cli/**` regeneration** — no new CLI flag or subcommand lands in this plan, so the generated flag reference is untouched.
- **Flipping the scope-out prose to a runnable command line in the docs** — held until the executor exists (`scope-out-executor` plan); the docs say "executor ships later," not a copy-paste command.
- **An auto-bridge from the reconcile re-ground finding to a `plan-tool merge` / re-plan command** — the #67 actuator remainder; kept recommend-only here, may return as its own plan.
- **Consolidating the four remedies' command builders into one shared renderer** — a behavior-preserving cross-module refactor (`_split_command` / `_reseed_command` and the `granularity` builders), out of a docs step's scope; route to reconcile.
