# Step 8 — Document the single-writer invariant in DATA_CONTRACT.md and reconcile BACKLOG #121/#126-#128 and RUNBOOK.md

## Summary

Close out the plan's docs and bookkeeping: document the concepts.json single-writer invariant in `DATA_CONTRACT.md`'s "Concept sidecar" section, flip BACKLOG #121/#126/#127/#128 from "these fixes ship via the `concept-write-integrity` plan" to shipped (naming `docs/implementation-plans/2-concept-write-integrity.md`), file the routed deferral-link staleness gap as its own `BACKLOG.md` entry, and reconcile the `RUNBOOK.md` workflows whose operator-facing behavior steps 2, 4, 5, and 6 changed (create-collision recovery, the detail-flow signed owned-section re-render, scope-out deferral rendering, detail-replacement recovery). The key rule for this step: verify each claim against the code and tests at HEAD before writing it — `depends_on` says steps 2–7 ran, not that their guarantees hold — and route any gap found back to the owning step instead of papering over it in prose. On green, the docs describe the shipped state, the four backlog entries carry no stale "should land first" language, and the data-contract drift guard (`tests/test_data_contract.py`) still passes.

## Table of Contents

- [Summary](#summary) — what the step does and the main rule it follows
- [Table of Contents](#table-of-contents) — this list
- [Why](#why) — why the docs and backlog go stale the moment steps 2–7 land
- [Input](#input) — the dependency outcomes and drift-guard contract this step consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — the three files touched and the edits per file
- [Implementation](#implementation) — the invariant text, the backlog tense sweep, the RUNBOOK reconciliation, and the parts that must not vary
- [Tests](#tests) — verification appropriate to a non-code step
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer or CI can run
- [Deferred](#deferred) — doc surfaces deliberately left to other owners

## Why

This is the plan's fifth work item ("update the concept-workflow docs the fixes touch … and perform the `BACKLOG.md` bookkeeping"). Steps 3–5 made `concept_sync.py:synchronize_concepts` the only production writer of `concepts.json` and step 5 pinned it with a guard test, but `DATA_CONTRACT.md`'s "Concept sidecar" section still describes only the save primitive ("Saves validate the complete record and atomically replace one `concepts.json` file") — the invariant a future plan author most needs is undocumented. `BACKLOG.md` #121's follow-up disposition and the #126/#127 entries all say the write-integrity bugs "ship via" this plan in the future tense; once steps 2–7 are green those lines misread as work still pending, which is exactly the stale-prose smell the accumulated lessons flag. And `RUNBOOK.md` describes recovery and scope-out behavior from before the fixes: an operator following it would hand-restore an archived colliding plan that step 2 now restores automatically, and would not expect a scope-out to render its signed-off deferrals into the narrowed plan's `## Deferred` section (step 5's deliberate behavior change).

## Input

- **Step 5's guard test** (created by step 5 in `tests/test_concept_sync.py` as `test_no_concept_sidecar_writer_outside_concept_sync` — a step-5 deliverable, so it resolves at HEAD only after step 5 lands, not in the pre-plan tree): a plain text scan over `plan_tool/**/*.py` asserting the `save_concepts`/`write_concepts` tokens appear only in `plan_tool/concept_tree.py` and `plan_tool/concept_sync.py`. The DATA_CONTRACT prose names this test as the invariant's guard, so its name and allowlist must be read from the test file at HEAD (after step 5), not from this plan.
- **Step 2's outcome**: a create that fails between archiving a colliding plan and manifest registration restores the archived original (plan, detail bundle, manifest entries) and re-raises. The RUNBOOK recovery note describes this observable behavior only; the mechanism belongs to step 2's detail.
- **Step 4's outcome**: running `plan-tool detail` on a **signed** plan now re-renders the plan's owned `## Deferred` / `## Out of scope` sections from the concept record (the routed signed sync arm), where the prior direct write left any hand-authored prose in those sections untouched. This is an operator-visible behavior change on the detail flow — an operator who hand-edits those sections on a signed plan and then re-details will see them overwritten by the record's rendering. The RUNBOOK note describes this observable behavior only.
- **Step 5's outcome**: a scope-out that defers a carved ownerless concept signs it off and takes the signed sync arm, so the deferral renders into the narrowed plan's `## Deferred` section; a scope-out never creates a sidecar that didn't exist.
- **Step 6's outcome**: a failed detail replacement leaves the prior body at the canonical path (validate-then-swap plus restore), and the authored replacement survives in the checkpoint cache for the next run.
- **Drift-guard contract** (`tests/test_data_contract.py`): section-scoped tests assert documented fields match the runtime dataclasses (e.g. `test_concept_contract_is_documented` requires `concepts.json` in the Concept sidecar section). New prose is safe; new field-shaped table rows are not — don't add tables for the invariant, write it as prose in the existing section.
- **BACKLOG entry state at HEAD**: #121's "Follow-up disposition (2026-07-13)" bullet, #126's Dependencies/Status bullets, #127's Effort/Dependencies/Status bullets, and #128's Status bullet are the four regions carrying "ship via / should land first" language (found via `grep -n "concept-write-integrity" BACKLOG.md`).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `DATA_CONTRACT.md` — in the `## Concept sidecar` section, add the single-writer invariant: `synchronize_concepts` is the sole production writer, `save_concepts` is the serialization primitive confined to `concept_tree.py`/`concept_sync.py`, plan `## Deferred`/`## Out of scope` prose is a synchronized rendering of the record (unsigned trees publish sidecar-only), and the guard test that pins it.
  - `BACKLOG.md` — flip #121/#126/#127 from "ship via" to shipped with the plan path; confirm #128 needs no change (or adjust if verification shows residue was absorbed); sweep for any other stale `concept-write-integrity` future-tense reference.
  - `RUNBOOK.md` — reconcile the scope-review workflow, the scope-out workflow, the detail workflow, and the interrupted-run recovery material with steps 2, 4, 5, and 6's shipped behavior.

## Implementation

**Verify before writing (the one hard ordering).** Before editing any doc, confirm each claim at HEAD: the guard test exists and passes, `grep -rn "save_concepts" plan_tool/` matches only `concept_tree.py` and `concept_sync.py`, and the step 2/5/6 behaviors have their owning tests green. If any check fails, the gap belongs to the owning implementation step — stop and route it there rather than describing unshipped behavior as shipped.

**DATA_CONTRACT.md — the invariant text.** Extend the existing `## Concept sidecar (<plan-dir>/plan-details/<slug>/concepts.json)` section (keep its current prose; the invariant builds on the "Saves validate … atomically replace" sentence). Cover, in prose:

- **Single writer**: every production write of `concepts.json` flows through `plan_tool/concept_sync.py:synchronize_concepts`; `plan_tool/concept_tree.py:save_concepts` is the serialization primitive and is called only from `concept_tree.py` and `concept_sync.py`.
- **What the writer guarantees**: validation and compare-and-swap guards on every write, and — for a signed tree — re-rendering of the plan's owned `## Deferred` / `## Out of scope` sections from the record, so plan prose is a synchronized rendering of the record, never a second decision store. An unsigned tree (no approved node) publishes the sidecar only and leaves the plan file untouched (step 1's arm).
- **The guard**: name the token-scan test in `tests/test_concept_sync.py` and state the rule for future work: route new concept persistence through `synchronize_concepts`; never extend the allowlist.

One way to keep the drift guard trivially green: pure prose (no new tables, no field-shaped rows), since `tests/test_data_contract.py` keys documented fields per section against the runtime registry. Run that suite after the edit either way.

**BACKLOG.md — the tense sweep.** Four regions, found by `grep -n "concept-write-integrity" BACKLOG.md`:

- **#121 "Follow-up disposition"** — state the write-integrity fixes shipped via `docs/implementation-plans/2-concept-write-integrity.md` (name the plan file; the seed pointer can stay as provenance). Keep the #126/#127/#128 residue pointers — they remain deferred.
- **#126** — Dependencies says the plan "should land first"; Status rationale says the bugs "ship in the distilled plan". Flip both to shipped/landed. The entry itself stays open (publication-transaction machinery remains deferred).
- **#127** — the Effort bullet's parenthetical says three of the archived plan's six steps "ship in `concept-write-integrity`" (evidence-provenance tightening, fail-soft concept parse, detail replacement safety — steps 6–7 and 2 here). Flip to shipped. Verify the three items #127 retains (envelope tightening, legacy-Markdown fallback removal, include-regeneration bounding) were genuinely untouched by this plan; they were not in any step's scope, so the entry's residue list should stand unchanged.
- **#128** — expected no-op: nothing in steps 1–7 absorbed ledger/accounting residue. Confirm and leave it; adjust only if verification finds otherwise.

Also check whether the deferral-link staleness gap steps 4–5 routed to the backlog (`detail_deferral_step_ids` links going stale when a narrow renumbers steps — see step 5's Deferred) already has an entry; if no step filed it, add one under the section BACKLOG.md's decision rule picks, so the routed gap doesn't evaporate. Per the retirement lesson, don't touch the #127 mention in the triage framework's `gate-signal` list — it describes still-deferred residue and stays accurate.

**RUNBOOK.md — three reconciliations**, matching each section's existing voice:

- **`## Workflow: review concept decisions and ownership (scope-review)`** — the paragraph on structural remedies already says `scope-out --apply` "signs off a structured `defer` decision for each carved concept that has no committed surviving owner"; extend it to say the signed-off deferral is rendered into the narrowed plan's `## Deferred` section, so record and prose stay aligned.
- **`### Carve a spinning region out of a plan (plan-tool scope-out)`** — add the same operator-visible facts to the bullet list: a carve with signed-off deferrals republishes the narrowed plan's `## Deferred` section from the record, and a scope-out never creates a `concepts.json` that didn't exist.
- **`## Workflow: author per-step detail (plan-tool detail)`** (or wherever the detail flow is described; the implementer picks the exact section) — add the step-4 operator-visible fact: running `plan-tool detail` on a **signed** plan re-renders the plan's owned `## Deferred` / `## Out of scope` sections from the concept record, so hand-authored prose in those two sections on a signed plan is replaced by the record's rendering (edit the record via `scope-review`, not the prose). An unsigned plan's detail run leaves the plan file untouched (sidecar-only).
- **Recovery material** — two notes, placed where an operator would look (likely `## Workflow: recover from an interrupted create/detail run` and/or `## Recovery: common failures`; the implementer picks the exact spot): a create that fails mid-collision-replacement restores the archived original plan and its manifest entries automatically (no hand un-archive), and a failed detail regeneration leaves the prior detail body at the canonical path with the authored replacement recoverable from the checkpoint cache on re-run.

**Parts that must not vary:**

- The invariant lands in `DATA_CONTRACT.md`'s concepts section — the plan's problem statement pins the location; don't move it to a new top-level section or another doc.
- Docs state the forward invariant, not history: no "previously three writers bypassed…" narration (git history owns that).
- BACKLOG entries #126/#127/#128 stay open — this step reconciles their language; it retires nothing.
- Every symbol and test name cited in the new prose is copied from HEAD, not from this plan's details.

## Tests

### Verification (non-code step)

This step changes no production code. Verify the artifacts:

- `uv run pytest tests/test_data_contract.py -q` — green after the DATA_CONTRACT edit (drift guard tolerates the new prose; `test_concept_contract_is_documented` still finds `concepts.json` in the section).
- `uv run pytest tests/test_concept_sync.py -q` — green, and the guard test named in the new DATA_CONTRACT prose exists under the exact cited name.
- `grep -rn "save_concepts" plan_tool/` — matches only `plan_tool/concept_tree.py` and `plan_tool/concept_sync.py`, confirming the invariant is true before it is documented.
- `grep -n "concept-write-integrity" BACKLOG.md` — every hit reads as shipped/deferred-residue; no "ship via" / "should land first" future tense remains on #121/#126/#127.
- Path check — every file path cited in the new prose (`plan_tool/concept_sync.py`, `tests/test_concept_sync.py`, `docs/implementation-plans/2-concept-write-integrity.md`, archived-plan paths kept in #126–#128) exists at HEAD.
- RUNBOOK anchor check — the scope-review and scope-out sections' edits don't break the `## Table of contents` links (no heading text changed).

## Acceptance criteria

- `DATA_CONTRACT.md`'s Concept sidecar section names `synchronize_concepts` as the sole production writer, names the guard test in `tests/test_concept_sync.py`, and states the unsigned sidecar-only vs signed re-render split.
- `uv run pytest tests/test_data_contract.py tests/test_concept_sync.py -q` passes.
- BACKLOG #121's follow-up disposition says the write-integrity fixes shipped and names `docs/implementation-plans/2-concept-write-integrity.md`.
- BACKLOG #126 and #127 carry no future-tense "ship in / should land first" language about this plan; both entries remain open with their deferred residue intact.
- The deferral-link staleness gap steps 4 and 5 routed to the backlog (`detail_deferral_step_ids` links going stale when a narrow or auto-split renumbers steps) has a concrete `BACKLOG.md` entry under the section BACKLOG.md's decision rule picks; the routed "file it later" note does not evaporate on ship.
- `grep -rn "save_concepts" plan_tool/` returns hits only in `concept_tree.py` and `concept_sync.py`.
- `RUNBOOK.md`'s scope-review and scope-out sections state that signed-off carved deferrals render into the narrowed plan's `## Deferred` section, and the recovery material describes the automatic create-collision restore and the prior-detail-body-preserved outcome of a failed replacement.

## Deferred

- CLAUDE.md / CAPABILITIES.md touch-ups — outside this step's declared file list; the plan ships no new leaf, command, or schema, so no registration surface changed.
- Consolidating `plan_tool/review.py:_structured_concept_deferral_is_valid` onto concept_sync's public deferral reader — reconcile-owned follow-up pinned by step 4; not a docs concern.
- Retiring BACKLOG #126/#127/#128 — their residue is untouched by this plan; this step only reconciles their language.
- Documenting the publication-transaction recovery model beyond git + fingerprint — BACKLOG #126 owns that design.
