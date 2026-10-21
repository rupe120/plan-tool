# Step 8 — Document the new stop and close out BACKLOG item #158

## Summary

Write the shipped recurring-high-impact-seam stop into the three docs that describe it and close out BACKLOG item #158. `docs/AUDIT_FLOW.md` gains a short subsection plus a `Source map` row so an operator can find the classifier and the two loop call sites; `DATA_CONTRACT.md` gains prose (not a new table row) saying `Recommendation.impact` is now read back at runtime and that an absent value reads as unknown evidence; `CLAUDE.md` gains one architecture paragraph for `plan_tool/impact_recurrence.py` and keeps the convergence-policy-boundary section honest. The key decision: document only what steps 1–7 actually landed — read the shipped symbol and token names off the code, not off this plan's prose. On green, `#158` is gone from `BACKLOG.md`, every entry that referenced it names the shipped work by feature name instead of a dead number, and the full test suite (including the `DATA_CONTRACT.md` drift guard) still passes.

## Table of Contents

- [Summary](#summary) — what changes and the observable result.
- [Why](#why) — why the docs and the backlog have to move together.
- [Input](#input) — the landed code and doc contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — per-file edit list.
- [Implementation](#implementation) — what each of the four files gets, and the gotchas.
- [Tests](#tests) — verification for a non-code step.
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes.
- [References](#references) — the docs worth opening.
- [Deferred](#deferred) — what this step leaves alone.

## Why

Steps 1–7 add a live stop that ends a completeness or reconcile iteration with a non-successful outcome, but nothing in the docs tells an operator it exists, when it fires, or how it differs from the offline `plan-tool convergence` verdict. Two verdicts that answer a similar question from different evidence are exactly the pair a reader confuses, so the difference has to be written down where each is already described. `BACKLOG.md` also carries `#158` as open work plus four inbound references that treat it as future — leaving them makes shipped behavior read as unbuilt, and deleting the number without rewording the references leaves dangling `#158` tokens that resolve to nothing.

## Input

- **Steps 6 and 7's outcome** — the wired completeness and reconcile call sites. Read the landed code in `plan_tool/cli/completeness_cmd.py` and `plan_tool/cli/reconcile.py` for where in each loop the check runs and what the operator actually sees on a stop. Document that, not the plan's description of it.
- **Steps 3, 4 and 5's outcome** — the classifier module, the recommend-only action record, and the `structural_stop` reason. The tokens `recurring_high_impact_seam` and `structural_stop` are module constants; quote the names that exist at HEAD.
- **`DATA_CONTRACT.md`'s drift guard** — `tests/test_data_contract.py` parses the doc's field tables against a registry of persisted dataclasses. `test_documented_fields_are_registered_or_aliases` fails on a documented field that isn't registered, so anything from step 2 that lives only in memory must not become a table row.
- **`plan_tool/capability_catalog.py`'s honesty check** (`plan-tool validate`) — it fires only on unowned *subcommands* and missing module paths. This plan registers no subcommand, so `CAPABILITIES.md` is verify-only here and "no edit needed" is the correct outcome.
- **Verification limit:** none of this can be checked before steps 6 and 7 are green — the doc claims are only true once the code is on disk.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `docs/AUDIT_FLOW.md` — add a subsection describing the stop in the `completeness` section; add a sentence in the `reconcile` section naming where the check runs; add one `Source map` row.
  - `DATA_CONTRACT.md` — prose under `### Recommendation` (`review.py`) recording the new runtime reader of `impact` and the unknown-on-absent rule.
  - `CLAUDE.md` — one new architecture paragraph for `plan_tool/impact_recurrence.py`; a sentence in the trailing `# Convergence policy boundary` section stating the calibrated policy is unchanged.
  - `BACKLOG.md` — delete the `#158` entry; reword the four inbound references; add one follow-up entry for the deferred slices; refresh the `convergence.py` line in the `## Architectural map` block.

## Implementation

**Ground everything in the landed code first.** Before writing a sentence, grep for the module, the two outcome tokens, and the loop call sites. A doc that names a symbol that doesn't exist is worse than no doc, and reconcile flags it on every audit.

### `docs/AUDIT_FLOW.md`

- Add a bold-led subsection in the `## completeness — conceptual audit` section, placed after **Calibrated impact-aware convergence** and before the `(impact=…, complexity=…)` triage-tag paragraph — that puts the live stop next to the other impact prose without breaking the reader's path from severity policy to triage tags.
- Cover, in the same terse style as its neighbours: the classifier lives in `plan_tool/impact_recurrence.py` and is separate from the severity/decomposition diagnosis in `plan_tool/convergence_diagnosis.py`; the trigger is the same region present in the newest three consecutive compatible passes, carrying explicit high impact with recorded provenance in every one, not shrinking, and still open in the newest pass; missing or legacy impact is insufficient evidence, not a trigger; the loop ends with `should_continue`'s `structural_stop` reason and prints a recommend-only next action; nothing is mutated.
- **Say plainly that this is not a converged outcome.** The TL;DR already tells operators to label stops using the emitted coverage fields (`confirmed-dry`, `confirmed-low-yield`, `budget_limited`, `recommendation_kind=non-converging`). A structural stop is a different, non-successful ending — spell that out so nobody files it under one of those four.
- **Say plainly how it differs from `plan-tool convergence <name>`.** One sentence: this stop reads the live loop's own passes and ends the loop; the offline diagnostic reads saved sidecars after the fact and ends nothing. They can disagree.
- Add a sentence to the `## reconcile — plan-vs-code fit` numbered list (or immediately after it) naming that `_iterate_reconcile_loop` evaluates the classifier at the post-apply, pre-next-pass boundary, so a qualifying stop happens before another Claude call is spent.
- Add one `## Source map` row. Suggested concern label: `Recurring high-impact seam stop`. File column lists `plan_tool/impact_recurrence.py` (classifier + recommend-only action), `plan_tool/convergence.py` (`structural_stop` reason), and the two call sites `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/reconcile.py`. Keep it distinct from the existing `Impact-aware continuation` row — that row is the calibrated `is_blocking_impact` policy and does not change.

### `DATA_CONTRACT.md`

- Add prose to the `### Recommendation` (`review.py`) section, below the field table: `impact` is now read back at runtime by the live impact-recurrence stop through history normalization in `plan_tool/convergence_diagnosis.py`, and an absent or empty `impact` on a legacy row is treated as unknown evidence — never as low impact — so such a row can neither start nor extend a recurrence streak.
- **Do not add a table row for anything step 2 added to `RunFinding`.** `RunFinding` and its impact-provenance token are in-memory normalization, not a persisted schema. A new row for an unregistered field fails `tests/test_data_contract.py::test_documented_fields_are_registered_or_aliases`. This is the one constraint in this file that is not free to vary.
- Leave `## Intentional exclusions` alone — it states that no registered serialized field is undocumented, which stays true.
- Leave the `completeness-audit --json` `coverage` table alone unless step 6 actually added a key to that payload. Check the landed code; if it did, the row belongs here and the plan's frontmatter already lists this file.

### `CLAUDE.md`

- Add one architecture paragraph directly after the existing **Convergence diagnostic (`convergence_diagnosis.py`)** paragraph, in the same bold-lead style. Content: `plan_tool/impact_recurrence.py` is a cycle-free leaf sitting above `convergence_diagnosis.py` and below the CLI; it takes a history as an argument and never loads one; the three-pass window is a fixed module constant, not a flag; it spends no Claude; its verdict is recommend-only and it never mutates plan structure; the two wired callers are the completeness and reconcile iterate loops; `create` and `detail` are deliberately not wired.
- **Name the two-classifier boundary in that paragraph.** The severity/decomposition classifier keeps its current semantics; the impact classifier owns its own eligibility rule and its own tokens (`recurring_high_impact_seam` / `structural_stop`) precisely so the offline fork names are never mistaken for the live stop.
- In the trailing `# Convergence policy boundary` section, add one sentence: the impact-recurrence stop computes its own predicate and does **not** extend `convergence.is_blocking_impact` to a new caller. That section already forbids widening the calibrated policy; this makes clear the new work stayed inside the fence rather than quietly changing it.
- Keep both additions short. The surrounding paragraphs are dense already; three to five sentences each is the right size.

### `BACKLOG.md`

- **Delete the `#158` entry outright** — but only once steps 1–7 are green and committed. Authoring the plan is not shipment.
- **Reword every inbound reference to name the feature, not a replacement number.** A deleted number resolves to nothing and minting a substitute is worse. Four known sites, all found with `grep -n '#158' BACKLOG.md`:
  - the `convergence:` roll-up bullet in `## Priority (mission-grounded)` — drop the `#158` item from the list of open convergence work.
  - `#153` (superseded, stays) — its "#158 owns the replacement design" line becomes a reference to the shipped impact-recurrence classifier and structural stop.
  - `#156` (open, stays) — its Out-of-scope bullet "the impact-recurrence structural route (#158)" becomes the same by-name reference.
  - `#125`'s Follow-up line "Impact-recurrence structural stopping remains separate in #158" — reword to say it shipped separately and stays separate.
- **Add one follow-up entry** for the slices the plan deliberately left undone, so they survive the deletion: fuzzy identity matching for a drifting seam, measured region-size shrinkage, backfilling impact provenance onto older rows, wiring the stop into the `create` and `detail` iterate loops, unifying the live stop with the offline `convergence` verdict, and an operator-tunable pass threshold. Use the next free number (`#159` — `#158` is the current maximum) and follow `## Adding a new entry`'s scope-contract fields. Grouping all six under one entry is a judgment call worth surfacing to the user; splitting them into separate entries is the alternative if any one is likely to be picked up on its own.
- Refresh the `convergence.py` line in the `## Architectural map` code block so its listed public API includes the new `structural_stop` reason and the caller-supplied seam field from step 5. Adding an `impact_recurrence.py` block to that map is optional — the map is already partial (`convergence_diagnosis.py` is absent) — so skip it rather than half-filling the gap.
- Do not touch `#116`, `#129`, or `BUG_BACKLOG.md`. Nothing in this plan resolves them.

## Tests

This step writes no code and adds no test cases. Verification is by command and by reading.

### Verification (non-code step)

- `uv run pytest tests/test_data_contract.py -q` — the `DATA_CONTRACT.md` drift guard stays green, proving the prose edit added no unregistered field row.
- `uv run pytest tests/ -q` — full suite green, no new failures from the doc edits.
- `plan-tool validate <name>` — green with no `orphan-subcommand` or `absent-surface` finding, confirming `CAPABILITIES.md` needed no edit.
- `grep -rn '#158' BACKLOG.md docs/ CLAUDE.md DATA_CONTRACT.md` — returns nothing, or only text that names the work as shipped; no line frames it as open or as a prerequisite.
- Symbol check — every module path, function, and token named in the three docs exists at HEAD: `grep -rn 'recurring_high_impact_seam\|structural_stop' plan_tool/` and `ls plan_tool/impact_recurrence.py`.
- Link check — the relative links in `docs/AUDIT_FLOW.md` (including any added ones) point at files that exist.
- Read-through — the new `docs/AUDIT_FLOW.md` subsection and the new `CLAUDE.md` paragraph each state the live-vs-offline difference in one sentence a reader can repeat back.

## Acceptance criteria

- `docs/AUDIT_FLOW.md` contains a subsection describing the recurring-high-impact-seam stop, naming `plan_tool/impact_recurrence.py`, the three-pass window, the recommend-only outcome, and the difference from `plan-tool convergence <name>`.
- `docs/AUDIT_FLOW.md`'s `## Source map` table has a row for the stop listing the classifier module, `plan_tool/convergence.py`, and the two loop call sites.
- `docs/AUDIT_FLOW.md`'s `reconcile` section names where in `_iterate_reconcile_loop` the check runs.
- `DATA_CONTRACT.md`'s `### Recommendation` section states that `impact` is read back at runtime and that an absent value reads as unknown evidence, and its field table gained no new row.
- `uv run pytest tests/test_data_contract.py -q` passes.
- `CLAUDE.md` has an architecture paragraph naming `plan_tool/impact_recurrence.py`, its two wired callers, its fixed three-pass constant, and its recommend-only rule.
- `CLAUDE.md`'s `# Convergence policy boundary` section states that the new stop does not extend `convergence.is_blocking_impact`.
- `BACKLOG.md` no longer contains the `#158` entry, and `grep -n '#158' BACKLOG.md` returns nothing.
- `BACKLOG.md` contains one new entry covering the six deferred slices, with the scope-contract fields `## Adding a new entry` requires.
- `#153` and `#156` are still present and still open, with their `#158` references replaced by by-name references to the shipped work.
- `uv run pytest tests/ -q` shows no new failures and `plan-tool validate <name>` is green.

## References

- [JSON Lines (JSONL) format specification](https://jsonlines.org/) — the record shape behind the telemetry log `DATA_CONTRACT.md` documents, worth a glance before editing that file's persisted-schema prose.
- [RFC 8259 — The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259) — the spec the saved-review sidecar conforms to; use it if the `Recommendation` prose needs to be precise about absent versus null keys.

## Deferred

- **Updating `docs/RESUME_FLOW.md`'s "The check runs **last** in `should_continue`" sentence** — step 5 puts `structural_stop` after the hard wall-clock cap, so that sentence goes stale. The file is outside this step's declared `files:` list; route it to a reconcile pass or a `BACKLOG.md` follow-up rather than widening this step's footprint.
- **`CAPABILITIES.md`** — no subcommand is registered by this plan, so the honesty check has nothing to reconcile and no edit is correct.
- **`USE_CASES.md` and `RUNBOOK.md`** — an operator recipe for what to do after a structural stop would be useful, but neither file is in this step's list and the recommend-only action already prints its own next command. Follow-up.
- **`README.md` flag tables** — nothing user-facing gained a flag; the three-pass threshold stays a module constant.
- **Any code change** — this step is documentation and bookkeeping only; steps 1–7 own every behavior it describes.
- **Adding `impact_recurrence.py` to `BACKLOG.md`'s `## Architectural map`** — the map is already partial and filling it properly is its own cleanup.
- **`BUG_BACKLOG.md`** — nothing in this plan fixes an entry there.
