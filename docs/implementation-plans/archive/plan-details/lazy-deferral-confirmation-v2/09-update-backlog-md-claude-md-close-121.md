# Step 9 — Reconcile BACKLOG.md and CLAUDE.md to the lazy guide-post model: close #121, mark #126–#128 residue superseded, and flip #129's reframe to shipped

## Summary

This is a docs-only closure step. It updates two unguarded docs — `BACKLOG.md` and `CLAUDE.md` — so they describe the lazy deferral-confirmation model this plan ships instead of the eager whole-tree concept model. In `BACKLOG.md`: flip **#121** from "completed/parked, lazy is the forward direction, concept-write-integrity is the fallback if lazy is rejected" to "the lazy path shipped and delivers #121's original MVP"; add a note to **#126/#127/#128** that the lazy path supersedes most of the eager write-integrity residue they were designed around; and flip **#129**'s "the real remedy *was* a wrong-altitude reframe" to "that reframe shipped," keeping its forward-looking monitoring work (a/b/c/d) open. In `CLAUDE.md`: rewrite the **Concept sign-off and ownership** paragraph so it states the guide-post rules (create/detail record only proposed deferrals as unreviewed pending guide posts, never signed under `-y`; scope-review confirms each against its own scoped bucket anchor and re-derives on a bucket change instead of dead-ending on whole-bundle staleness). Neither doc has a drift-guard test, so on green the observable result is that every claim in both edited regions matches the behavior steps 3–8 actually shipped at HEAD.

## Table of Contents

- [Why](#why) — why the two docs go stale the moment the lazy path ships
- [Input](#input) — the shipped behaviors and backlog entries this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the two docs this step edits
- [Implementation](#implementation) — the BACKLOG entry edits and the CLAUDE.md paragraph rewrite
- [Tests](#tests) — verification for a non-code step
- [Acceptance criteria](#acceptance-criteria) — checkable states on green
- [References](#references) — the docs and code surfaces to cross-check against
- [Deferred](#deferred) — what this step deliberately leaves open

## Why

`BACKLOG.md` and `CLAUDE.md` still describe the eager model this plan replaces, and both are read on every reconcile, review, and run. In `CLAUDE.md` the **Concept sign-off and ownership** paragraph says create "records operator-approved owners" and scope-review "binds approval to the current plan source state" — both whole-tree, whole-bundle claims that steps 3–8 make false. In `BACKLOG.md`, **#121**'s "Altitude reframe" bullet still frames lazy materialization as an unbuilt "forward direction" and parks `concept-write-integrity` as "the ready-to-run fallback if the lazy approach is rejected"; once this plan ships, lazy is not a proposal but the delivered MVP of #121's founding desire ("confirm the deferred concepts"). The eager-hardening residue in **#126/#127/#128** was scoped to the write-integrity surface the lazy path largely removes, and **#129**'s origin note calls the eager→lazy reframe "the real remedy" in past tense as an insight, not as shipped work. This step is where the docs catch up. The backlog-derived seed (`plan-seeds/lazy-deferral-confirmation.md`, sourced from #121) was consumed and archived by `create`, and its forward-carry obligation — update the originating backlog entry when the work ships — lands here in #121.

## Input

This step consumes shipped behavior and existing backlog text; it writes no code, so its correctness rests entirely on reading both accurately at HEAD.

- **Steps 3–8's shipped behavior (verify against code at HEAD, not sibling detail prose).** Detail files are authored before their steps run and can drift during implementation, so confirm each claim this step writes against the actual code:
  - step 3/4 (`plan_tool/create.py`) — create no longer calls `emit_concept_tree`, records only proposed `defer`/`wont_do` as **unreviewed** pending guide posts (never signed under `-y`), and writes no `concepts.json` for an un-deferred plan.
  - step 5 (`plan_tool/cli/scope_review_cmd.py:cmd_scope_review`) — scope-review confirms a pending guide post against its own scoped **bucket anchor**, re-deriving on a bucket-level change and no longer dead-ending on whole-bundle staleness.
  - step 6 (`plan_tool/review.py:check_concept_coverage`) — the coverage audit validates a guide post against its bucket anchor and never crashes on a stale/renamed bucket.
  - step 7 (`plan_tool/cli/inspect.py`, `plan_tool/completeness_report.py`, `plan_tool/create.py`) — pending guide posts surface as a drillable list, non-blocking.
  - step 8 (`plan_tool/detail.py`) — detail is a second producer of unreviewed pending guide posts.
- **The `BACKLOG.md` entries edited** — the H3-ish headers `**#121 — …**`, `**#126 — …**`, `**#127 — …**`, `**#128 — …**`, and `**#129 — …**`, plus the `- **convergence:**` and `- **gate-signal:**` rollup bullets in the Quality/accuracy lens that name #129 and #127. Read each entry's retained-residue list before touching it — the tense-flip must not delete residue that is still genuinely open.
- **The `CLAUDE.md` target** — the single **Concept sign-off and ownership** paragraph (the `concept_tree.py`, `concept_bootstrap.py`, `concept_review.py`, `concept_sync.py` line). It is the only paragraph making eager-model claims; the Correctness-gates and other paragraphs are unaffected.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — edit **#121** (close as delivered-via-lazy; flip the "Altitude reframe" bullet and drop the "fallback if rejected" framing), **#126/#127/#128** (add a superseded-by-lazy note to each), and **#129** (flip the reframe from "the real remedy was" to "shipped," keep a/b/c/d open). Verify the `convergence:` / `gate-signal:` lens rollups that name #129/#127 are still accurate; leave them unless a claim went stale.
  - `CLAUDE.md` — rewrite the **Concept sign-off and ownership** paragraph to state the guide-post rules. No other paragraph changes.

## Implementation

Describe forward state; keep each edit inside its named region.

- **`CLAUDE.md` — rewrite the Concept sign-off and ownership paragraph to the guide-post model.** Replace the eager claims with the lazy ones; keep the durable, still-true parts.
  - **Keep true and unchanged:** the `concepts.json` record is the authority and plan prose is a synchronized rendering; a signed-off concept is accounted for only by its exact ID in a committed `Step.concept_ids`, an approved `wont_do`, or a valid structured deferral; titles/tags/files/prose don't confer ownership; legacy plans stay parseable; `concept-coverage` blocks and `concept-unsigned-deferral` reminds.
  - **Replace "Create records operator-approved owners" and "detail persists structured deferrals":** state that create and detail record only **proposed** `defer`/`wont_do` concepts as **unreviewed pending guide posts** (never signed under `-y`), that an un-deferred plan writes no `concepts.json` at all, and that `plan-tool scope-review` is the sole signer.
  - **Replace "binds approval to the current plan source state":** state that scope-review confirms each pending guide post against its own **scoped bucket anchor** (a hash over just that concept's plan section), re-deriving on a bucket-level change and no longer dead-ending on whole-bundle staleness.
  - **Keep the lifecycle tail** (split conserves, merge unions, re-grounding carries forward, scope-out signs off carved deferrals) — those still hold; only the create/detail/scope-review clauses change.
  - **Gotcha — stay terse and one paragraph.** Match the surrounding architecture-section density (a long single paragraph). Don't add a new subsection or a bullet list; this section is prose by convention.
- **`BACKLOG.md` #121 — close as delivered by the lazy path.** Flip the **Altitude reframe (2026-07-15)** bullet from "the forward direction is `plan-seeds/lazy-deferral-confirmation.md`" (unbuilt) to "shipped via the lazy-deferral-confirmation plan," and drop the "`concept-write-integrity` … parked as superseded … ready-to-run fallback if the lazy approach is rejected" framing — lazy landed, so the archived plan is superseded outright, not a contingency. State that this discharges the backlog-derived seed's forward-carry obligation. Keep the shipped-capability / coverage-contract / maintainers content that still describes real behavior; do not resurrect the archived seed path.
- **`BACKLOG.md` #126/#127/#128 — add a superseded-by-lazy note to each.** These residue entries were scoped to the eager write-integrity surface (publication transactions, authoring-boundary validation, non-delivery ledger). The lazy path writes a record only when something is deferred and validates per-bucket, removing most of that surface. Add one line per entry noting the lazy path supersedes most of its motivation and to revisit only if a real incident survives the lazy model's nets. **Cross-check before writing:** read each entry's retained-residue list and only supersede what the lazy path actually removes — e.g. #127's Markdown-fallback / include-regeneration items and #128's ledger may retain a genuinely-open sliver; if so, say "largely superseded" and name what stands, rather than blanket-closing. Follow the tense-flip-not-retirement rule: change the future-tense "would ship / revisit" language, keep still-accurate residue pointers.
- **`BACKLOG.md` #129 — flip the reframe to shipped, keep the monitoring work open.** #129's **Status** stays "not started" for its own sub-changes (a/b/c/d monitoring), but its **Origin**/summary calls the eager→lazy reframe "the real remedy … no re-decomposition would have produced." Update that to state the reframe shipped (via this plan) while its forward-looking decomposition-monitoring work remains open — the two are distinct: the reframe was the one-off remedy, the monitoring that would have *caught the fragmentation earlier* is the unbuilt entry. Do not mark #129 done.
- **Rejected alternative — deleting #126/#127/#128 outright.** Tempting since the lazy path removes their surface, but each may retain a sliver of genuinely-open residue and deletion loses the archived-design pointers. Prefer a superseded note over retirement; retire only an entry whose every retained item the lazy path provably removes.
- **Constraint — no drift-guard net.** Neither doc is covered by a drift-guard test (unlike `DATA_CONTRACT.md`, `docs/cli/*`, `CAPABILITIES.md`). Accuracy is checked only by reading against HEAD code. Every behavioral sentence this step writes must be confirmed against the shipped code from steps 3–8, not transcribed from their detail files.

## Tests

### Verification (non-code step)

This step changes no production code; verify the docs by reading, since neither file has a drift guard.

- **CLAUDE.md claim-by-claim cross-check** — each rewritten sentence in the Concept sign-off paragraph matches HEAD behavior: create/detail record unreviewed pending guide posts (grep `plan_tool/create.py`, `plan_tool/detail.py` for the guide-post write and `review_state="unreviewed"`); scope-review confirms against a bucket anchor (grep `plan_tool/cli/scope_review_cmd.py` for the anchor comparison, and that `rederive_concepts` is gone).
- **BACKLOG #121 accuracy** — the entry no longer calls lazy an unbuilt "forward direction" and no longer frames `concept-write-integrity` as a fallback-if-rejected; it names the shipped lazy plan and states the seed's forward-carry is discharged.
- **BACKLOG #126/#127/#128 residue integrity** — each entry carries a superseded-by-lazy note; any residue left open is one the lazy path does *not* remove (no still-open item silently dropped, no already-removed surface still described as pending).
- **BACKLOG #129 reframe tense** — the reframe reads as shipped; the a/b/c/d monitoring sub-changes still read as open and the entry is not marked done.
- **Rollup consistency** — the `convergence:` and `gate-signal:` lens bullets that name #129/#127 still describe the entries accurately after the edits.
- **Link/anchor safety** — no heading text changed in either file, so any internal table-of-contents / anchor links stay intact (edits are inside entry bodies and the one CLAUDE.md paragraph, not headings).

## Acceptance criteria

- `CLAUDE.md`'s Concept sign-off and ownership paragraph states create/detail record **unreviewed pending guide posts**, never sign under `-y`, and scope-review confirms against a **scoped bucket anchor** — and contains no surviving "records operator-approved owners" or "binds approval to the current plan source state" wording.
- `BACKLOG.md` #121 no longer describes lazy materialization as an unbuilt forward direction, no longer lists `concept-write-integrity` as a ready-to-run fallback, and states the backlog-derived seed's forward-carry obligation is discharged.
- `BACKLOG.md` #126, #127, and #128 each carry a note that the lazy path supersedes most of their motivation, with any retained residue explicitly named.
- `BACKLOG.md` #129's reframe reads as shipped while its (a)/(b)/(c)/(d) monitoring work remains open; the entry is not marked done.
- The full test suite still passes (`uv run pytest -m "not integration" tests/ -q`) — this step touches no code, so no test changes; a green suite confirms the doc edits introduced no accidental code change.
- No heading text changed in either file (internal anchors intact).

## References

- `MISSION.md` — the grounding principles the reconciled CLAUDE.md paragraph must stay faithful to (concepts.json as the single decision store; deterministically driven non-determinism).
- `BACKLOG.md` — this file's own "Which file does my entry go in?" and Quality/accuracy lens sections, to keep the edited entries consistent with the doc's own conventions.
- `plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/cli/scope_review_cmd.py`, `plan_tool/review.py` — the HEAD code surfaces whose shipped behavior every rewritten sentence must match.

## Deferred

- Editing any doc other than `BACKLOG.md` and `CLAUDE.md` (e.g. `USE_CASES.md`, `RUNBOOK.md`, `docs/*_FLOW.md`) — out of this step's declared files; if the lazy model changed operator-facing walkthroughs, that reconciliation belongs to its own step or a follow-up, not here.
- Implementing #129's decomposition-monitoring sub-changes (a/b/c/d) — this step only flips #129's reframe tense; the monitoring work stays a separate not-started backlog entry.
- Retiring #126/#127/#128 entirely — deliberately left as superseded-annotated entries (with their archived-design pointers) rather than deleted, in case a real incident revives them.
