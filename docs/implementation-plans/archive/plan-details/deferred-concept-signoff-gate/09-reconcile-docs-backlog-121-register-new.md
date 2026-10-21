# Step 9 — Reconcile the docs and close BACKLOG #121: register the concept sign-off gate leaf in CLAUDE.md, add the RUNBOOK walkthrough, and retire #121

## Summary

This step brings the durable docs into line with the shipped concept sign-off gate (steps 1–8) and closes its backlog entry. It edits three files, all in the declared list: `CLAUDE.md` gains a new Architecture paragraph registering the `plan_tool/concept_tree.py` leaf, its `scope-review` command, the two completeness checks, and the scope-out concept-flip; `RUNBOOK.md` gains an operator walkthrough (plus a ToC entry) for signing off a plan's deferred-concept tree and for `plan-tool scope-review`; and `BACKLOG.md` retires `#121` now that the plan fully ships it. The key rule: this is a **non-code** step — it changes no production code and must describe only surfaces that already exist at HEAD, so its "shipped" claims (the leaf, the command, the checks) get the same verify-before-write grep gate a whole-entry backlog deletion gets. On green, CLAUDE.md and RUNBOOK describe the concept gate accurately, `grep -n '#121' BACKLOG.md` returns nothing, and no doc names a symbol that isn't in the tree.

## Table of Contents

- [Why](#why) — the docs still describe a world with no concept gate
- [Input](#input) — the shipped surfaces this step documents
- [Files (creates vs edits)](#files-creates-vs-edits) — three doc edits, no new files
- [Implementation](#implementation) — the CLAUDE.md paragraph, the RUNBOOK walkthrough, the #121 retirement, and the verify-before-write gate
- [Tests](#tests) — points to the verification block
- [Verification (non-code step)](#verification-non-code-step) — grep/anchor/accuracy checks
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — the plan seed and the doc-owner conventions
- [Deferred](#deferred) — code, tests, and other-doc registration owned by earlier steps

## Why

Steps 1–8 built the concept sign-off gate — a `concepts.json` sidecar, a producer, an interactive walker, three wiring surfaces (`create`, `detail`, `scope-review`), two completeness checks, and a scope-out concept-flip — but the durable docs still describe a world where deferral is decided silently. `CLAUDE.md`'s Architecture section names every other leaf (`granularity.py`, `convergence_diagnosis.py`, `telemetry.py`, the branch-awareness leaves) but not `concept_tree.py`, so the next reconcile audit reads the feature as undocumented drift. `RUNBOOK.md` has no operator recipe for signing off concepts or for the new `scope-review` verb. And `BACKLOG.md` #121 still reads "not started — backlog entry + seed authored" even though this plan implements it end-to-end. This step is the plan's closing docs/status step: it makes the durable docs match the code and removes the shipped backlog entry, per the backlog-reconciliation rule the seed carried forward.

## Input

This step **documents** contracts other steps own — reference them, do not re-specify their mechanics. It reads these shipped surfaces to describe them accurately:

- **Step 1 — the leaf and sidecar.** `plan_tool/concept_tree.py` ships `ConceptNode`, `ConceptTree`, `CONCEPTS_FILENAME`, `CONCEPTS_SCHEMA_VERSION`, `concepts_path`, `compute_node_id`, `save_concepts`, `read_concepts`; the sidecar lives at `plan-details/<slug>/concepts.json` beside `grounding.json` and is drift-guarded through `plan_tool/data_contract.py` + `DATA_CONTRACT.md`.
- **Step 2 — the producer.** `emit_concept_tree` behind the `shell_concept_invoker` seam.
- **Step 3 — the walker.** `navigate_concepts`, its frozen `ConceptDecision`, and the operator-only sign-off gate (`yes → non-TTY → interactive`; only the `c` keystroke sets `signed_off`).
- **Steps 4 / 5 / 8 — the three wiring surfaces.** `plan_tool/create.py:create_plan`, `plan_tool/detail.py:generate_detail`, and `plan-tool scope-review` (`plan_tool/cli/scope_review_cmd.py`).
- **Step 6 — the two checks.** `check_concept_coverage` (source `concept-coverage`, blocking) and `check_concept_signoff` (source `concept-unsigned-deferral`, advisory) in `plan_tool/review.py`; both stay out of `APPLY_ELIGIBLE_SOURCES`.
- **Step 7 — the scope-out concept-flip.** `plan_tool/scope_out.py:scope_out_step` flips a carved step's sole-covered `include` concepts to `defer` and lists them in the rendered seed.

If a name above differs from what actually shipped, follow HEAD — the code is the owner, and the verify gate below is how you catch the difference before writing prose about it.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `CLAUDE.md` — add one Architecture paragraph registering the concept sign-off gate leaf and its surfaces. One-line touch-ups where an existing paragraph now understates scope (the scope-out bullet in **Structural remedy vocabulary**, and optionally a cross-reference in **Correctness gates** for the two new checks).
  - `RUNBOOK.md` — add an operator walkthrough for the concept sign-off gate and `plan-tool scope-review`, plus its Table-of-contents entry. Add a one-line note to the existing scope-out walkthrough that a carve defers the step's sole-covered concepts.
  - `BACKLOG.md` — retire `#121` (delete the entry block).

## Implementation

**Add a new CLAUDE.md Architecture paragraph for the concept sign-off gate.** Model it on the sibling leaf paragraphs — **Granularity advisor**, **Convergence diagnostic**, **Decision telemetry**, and the **Branch-awareness** block — a bold lead like `**Concept sign-off gate (`concept_tree.py`).**` followed by the leaf's shape and its wiring. Place it near the other advisory/gate leaves (a sensible spot is right after **Structural remedy vocabulary** or beside **Correctness gates**; the implementer picks by flow). Cover, grounded in the shipped names:

- **The leaf.** `plan_tool/concept_tree.py` is a stdlib-only leaf modeled on `plan_tool/grounding.py` — the sidecar dataclasses (`ConceptNode` / `ConceptTree`), `concepts_path` / `save_concepts` / `read_concepts`, the content-hash `compute_node_id`, the `emit_concept_tree` producer behind the `shell_concept_invoker` seam, and the interactive `navigate_concepts` walker returning a frozen `ConceptDecision`. Note it keeps every first-party import function-local so it stays cycle-free.
- **The sidecar.** `plan-details/<slug>/concepts.json` beside `grounding.json`, drift-guarded via `plan_tool/data_contract.py` (both dataclasses registered separately) and `DATA_CONTRACT.md`.
- **The operator-only sign-off rule.** Only the interactive `c` keystroke sets `signed_off`; `--yes` and non-TTY runs accept the suggested states but leave every node unsigned — the same `yes → non-TTY → interactive` gate `scope_out.py` uses.
- **The three wiring surfaces.** `create_plan` (step 4) and `generate_detail` (step 5) run the gate once per authoring run, and `## Out of scope` / `## Deferred` become a one-directional render of the tree; the standalone `plan-tool scope-review` (step 8) re-runs the gate on any plan, emitting a fresh tree if none exists.
- **The two completeness checks.** `check_concept_coverage` (source `concept-coverage`, `medium`/blocking — an `include` concept with no covering step) and `check_concept_signoff` (source `concept-unsigned-deferral`, `info`/advisory — a deferred concept never signed). State the key invariant: **both stay out of `APPLY_ELIGIBLE_SOURCES`** (apply can't add a step or sign off a deferral), and coverage is **recomputed by slug every run** — never read from a persisted `covered_by` — so the parallel `completeness-apply` worktree path can't lose it.
- **The scope-out concept-flip.** A carve flips a step's sole-covered `include` concepts to `defer` and carries them into the forward-seed (step 7), so a just-deferred concept never re-raises `concept-coverage`.

**Touch the existing scope-out bullet.** The **Structural remedy vocabulary** paragraph's scope-out bullet describes the carve as a plan-scope split to a forward-seed but predates the concept-flip. Add a short clause that the carve also defers the carved step's sole-covered concepts and lists them in the seed. Keep it to one clause — the full mechanism lives in the new gate paragraph.

**Add the RUNBOOK walkthrough.** Add an operator-facing section — one clear option is a new `### ` subsection, e.g. **`### Sign off a plan's deferred concepts (`plan-tool scope-review`)`**, placed near the completeness workflow (beside the scope-out walkthrough) or under the create/detail workflows. It should explain, in plain steps:

- **What the tree is** and where it lives (`plan-details/<slug>/concepts.json`).
- **The keystrokes** — mark include / defer, drill into a concept's children, and confirm sign-off with `c`; per-selection save means an interrupt mid-walk never loses the session.
- **The unattended rule** — `-y` / non-TTY accept the suggested states and persist them but leave everything unsigned, so a real sign-off needs an interactive run.
- **When it fires automatically** — once per `create` and once per `detail` run — and when to reach for `scope-review` (a plan created under `-y`, a plan created before the feature, or changing your mind later).
- **The enforcement** — a signed `include` concept with no covering step raises a blocking `concept-coverage` finding in `completeness-audit`; an unsigned deferral raises the advisory `concept-unsigned-deferral` nudge.

Add the matching bullet to RUNBOOK's **Table of contents** with the correct GitHub-slug anchor. Also add a one-line note to the existing scope-out walkthrough (the **Carve a spinning region out of a plan** subsection) that carving a covering step defers that step's sole-covered concepts and records them in the seed.

**Retire BACKLOG #121.** Delete the `**#121 — Operator sign-off of a hierarchical deferred-concept tree**` entry block in full — this plan ships it end to end, so it is no longer open work. Constraints:

- **Verify before you delete.** #121 is only referenced at its own entry (confirmed: no T-tier list, `Highest open by tier`, or `Next concrete pick` line names it), so no priority-steering line needs re-pointing. Still grep first to be sure nothing else cites `#121`; if a cross-citation exists, keep it (a shipped-origin reference survives a whole-entry deletion) rather than scrubbing every mention.
- **Gate the "shipped" claim on HEAD.** Before deleting, grep that the surfaces #121 promised actually exist at HEAD — the `plan_tool/concept_tree.py` leaf, the `scope-review` command, and the `concept-coverage` / `concept-unsigned-deferral` checks. If any is missing, the owning code step (1–8) is incomplete: stop and route back to it, do not edit code in this docs step.
- **Sweep the plan's own deferred work.** Read this plan's `## Out of scope` / `## Deferred` and each step's Deferred section. Any genuinely forward follow-up that is not reconcile-owned (for example a `covered_by` persistence enrichment, if the plan left one open) gets filed as a new `BACKLOG.md` entry so it isn't lost; items already marked reconcile-owned (atomic-write extraction, seed-renderer consolidation) need no new entry. Do not invent forward work the plan didn't defer.

## Tests

This step changes no production code, so it has no unit tests. See the verification block below for the checks that stand in for tests.

### Verification (non-code step)

- `grep -n 'concept_tree\|scope-review\|concept-coverage' CLAUDE.md` — the new paragraph names the leaf, the command, and the checks.
- Every symbol the new CLAUDE.md paragraph names (`ConceptNode`, `ConceptTree`, `concepts_path`, `emit_concept_tree`, `navigate_concepts`, `check_concept_coverage`, `check_concept_signoff`, `scope_out_step`) resolves to a real definition at HEAD via `grep -rn` in `plan_tool/` — no invented names.
- `grep -n 'scope-review' RUNBOOK.md` — the walkthrough exists; its heading matches the new Table-of-contents anchor exactly (slug check: lowercase, spaces → hyphens, punctuation dropped).
- RUNBOOK's scope-out walkthrough carries the concept-defer note.
- `grep -n '#121' BACKLOG.md` returns nothing — the entry is gone and no dangling citation remains.
- The shipped-surface grep gate passed before the #121 deletion (the leaf, command, and both checks exist at HEAD).
- No plan-tool `Next steps:` output or tool-printed text was added — the new prose is operator/maintainer docs only, and any command it names is a `plan-tool …` command, never a session activity.

## Acceptance criteria

- `CLAUDE.md` Architecture section contains a concept-sign-off-gate paragraph that names `plan_tool/concept_tree.py`, `scope-review`, `concept-coverage`, and `concept-unsigned-deferral`, and states that both check sources stay out of `APPLY_ELIGIBLE_SOURCES` and coverage is recomputed by slug.
- The CLAUDE.md scope-out bullet mentions the concept-flip.
- `RUNBOOK.md` has a concept sign-off / `scope-review` walkthrough plus a matching Table-of-contents entry whose anchor resolves to the new heading.
- Every symbol cited in the new doc prose exists in `plan_tool/` at HEAD.
- `grep -n '#121' BACKLOG.md` is empty; no other backlog entry lost a legitimate cross-citation.
- Any remaining non-reconcile-owned forward follow-up from this plan is filed as a new `BACKLOG.md` entry, or confirmed reconcile-owned and left untracked.

## References

- `plan-seeds/deferred-concept-signoff.md` — the plan seed #121 points to; the source of the feature's intended shape and the backlog-reconciliation requirement this step fulfills.
- `CLAUDE.md` Architecture paragraphs — **Granularity advisor**, **Convergence diagnostic**, **Decision telemetry**, **Branch-awareness** — the format template for the new leaf paragraph.
- `plan_tool/grounding.py` — the sidecar leaf the concept leaf mirrors; read it to describe the persistence shape accurately.
- `BACKLOG.md` header — the BUG_BACKLOG-vs-BACKLOG decision rule and the entry-retirement conventions (delete whole entry; preserve shipped-origin cross-citations; re-point priority lines only when the retired item is named in one).

## Deferred

- The concept-gate code (leaf, producer, walker, wiring, checks, scope-out flip) — owned by steps 1–8; this step only documents it.
- Any code, unit tests, or `DATA_CONTRACT.md` edits — none belong here; this step edits only `CLAUDE.md`, `RUNBOOK.md`, `BACKLOG.md`.
- Registering `scope-review` in `CAPABILITIES.md`, the generated `docs/cli/` reference, and the `--help` golden — owned by step 8's registration work, not this step.
- Reconcile-owned consolidations the plan's steps flagged (extract a shared atomic-write-JSON; consolidate the three `create --from-existing` seed renderers; consolidate the leaf's local input helpers) — left for a reconcile pass, no new backlog entry needed.
