# Step 7 — Document the required guardrail headings and remove BACKLOG #532

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This non-code step updates four docs to describe the shipped contract and removes BACKLOG #532. The contract: a `--from-existing` seed must carry `## Scope guardrails`, `## Audit guardrails` and `## Expected placement`. An explicit `None` body is valid. A missing, duplicated, empty or `_(TODO)_` heading is refused before any model call. The pages are `SEED_FORMAT.md`, `PLAN_FORMAT.md` § "Scope fence", `docs/how-to/pipeline/create-from-existing.md`, and `ROADMAP_FORMAT.md`'s "Draft seeds under the roadmap slug" section. The roadmap page also gains the draft-gate rule. Each page names what fills the headings for each seed-writing tool. The main decision is that every page states the contract once in its own terms and points to the code for the exact rule. On green, the docs match the code, and `BACKLOG.md` no longer lists #532.

## Table of Contents

- [Input](#input) — what steps 1–6 provide and the limits on verifying the docs
- [Why](#why) — why the docs and backlog change last
- [Files (creates vs edits)](#files-creates-vs-edits) — the five files touched
- [Implementation](#implementation) — contract wording, per-page edits, source table, backlog removal
- [Tests](#tests) — verification checks for this non-code step
- [Acceptance criteria](#acceptance-criteria) — observable results
- [References](#references) — code and docs to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work left out

## Input

- **Steps 1–6 own the code contract.**
  - Step 1 adds the shared check in `plan_tool/scope_fence.py`.
  - Steps 2–4 make `scope-out`, `reground`, `annotate` and `roadmap` write the headings.
  - Step 5 edits the live seeds.
  - Step 6 turns the refusal on in `plan_tool/create.py:classify_file_backed_source`.
- **Landed names win.** At the time of drafting, `rg "REQUIRED_GUARDRAIL|missing_required" plan_tool/scope_fence.py` returns nothing on this branch. Read the real constant, function and violation-kind names from the modules at implementation time. The names in this file are descriptions, not spellings. Cite a symbol only if `rg` finds it at HEAD. Otherwise cite the module path.
- **Where the docs live at HEAD.**
  - `SEED_FORMAT.md` has `## What a seed is`, `## Core directives` and `## Conventions`.
  - `PLAN_FORMAT.md` has `### Scope fence (reaches the detail and run prompts)` under `## Body sections (advisory-checked)`.
  - `docs/how-to/pipeline/create-from-existing.md` has `## Preparation and normalized publication`, `## Direct publication` and `## Source map`.
  - `ROADMAP_FORMAT.md` has `## Draft seeds under the roadmap slug` and `### Draft-seed manifest states`.
  - `BACKLOG.md` carries `**#532 — ...**` in bucket A. `#534` follows it.
- **Source of each writer's headings (what the docs must say).**
  - **`roadmap --materialize` and `--refresh-seeds`:** the model writes the headings from the accepted plan row, per `plan_tool/prompts/roadmap-seed.md`. It uses `None` where the row sets no fence.
  - **`annotate`:** it copies the source plan's guardrails when they pass the check. When the source has none, its existing single model call supplies them, limited to fences the source supports. A missing response renders `_(TODO)_`.
  - **`scope-out` and `reground`:** they copy the source plan's guardrails verbatim, and write `_(TODO)_` for any heading the source lacks.
  - **Confirm each statement against steps 2–4 as landed.**
- **Limit on verification.** Link and symbol checks show the docs are consistent with the code. They do not show an operator finds the wording clear.

## Why

The code now refuses a seed with a bad guardrail heading, but the docs still describe the headings as optional. `SEED_FORMAT.md` is the authoring directive, so an author following it today writes a seed that `create` refuses. The roadmap draft gate gained a rule in step 4 that `ROADMAP_FORMAT.md` does not yet state. BACKLOG #532 describes work that has shipped, and a stale entry is a defect under the repo's forward-looking rule. This step comes last because it documents what the earlier steps landed.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `SEED_FORMAT.md`: state the three-heading requirement, the `None` rule and the `_(TODO)_` refusal. Add the per-tool source summary.
  - `PLAN_FORMAT.md`: add the requirement and the per-tool source summary to `### Scope fence (reaches the detail and run prompts)`.
  - `docs/how-to/pipeline/create-from-existing.md`: add the guardrail check to the preflight description and the decision flow. Add the per-tool source summary.
  - `ROADMAP_FORMAT.md`: add the draft-gate rule to `## Draft seeds under the roadmap slug`. Add the per-tool source summary for the roadmap seed.
  - `BACKLOG.md`: delete the whole #532 entry.

## Implementation

- **State one contract, in plain words, on every page.**
  - The three headings are required in a `--from-existing` seed.
  - Each must appear exactly once, outside fenced code, with a non-empty body.
  - A body of `None` is valid and means "this seed deliberately sets no such fence".
  - A `_(TODO)_` body is refused, the same as an empty one.
  - The refusal happens before any model call and writes no run record.
  - Each page words this for its own audience. Do not copy one paragraph across four files.
- **`SEED_FORMAT.md`.**
  - Add the requirement to the directives for the guardrail headings. The existing directive says to state a scope fence, so extend that text rather than adding a new section.
  - Tell authors to write `None` rather than omit a heading, and to write a real fence otherwise.
  - Follow the user rule that an explicit marker beats absence: say why `None` is better than a missing heading (a reader cannot tell "no fence" from "forgot the fence").
  - Say that `## Stack`, `## Outcome` and `## In scope` are unchanged by this rule.
- **`PLAN_FORMAT.md` § "Scope fence".**
  - Keep the plan-body description as it is. Add the seed-side requirement and a pointer to `SEED_FORMAT.md`.
  - Say that the captured heading text reaches `detail` and `run` unchanged, and that `None` is carried unchanged like any other body.
- **`docs/how-to/pipeline/create-from-existing.md`.**
  - Add the guardrail check next to the unmatched-fence and `## References` preflights in the TL;DR bullet and the decision-flow diagram. Keep the diagram's shape. Edit the preflight line only.
  - Say the check sits in the same function as the `## References` check, so every route reaches it. A combined error names every failing heading, and the `## References` problem when both fail.
  - Keep the route table in `docs/reference/contracts/seed-ingestion.md` as the owner of the exact contract. Link to it. If that page also lists the preflights, add a one-line pointer there only if it states the old rule, and then list it under Files.
- **`ROADMAP_FORMAT.md` draft seed contract.**
  - Add the rule beside the existing draft-gate rules (`## References`, `## Risks`, fences, provenance): a draft missing or mis-filling a guardrail heading is a gate violation.
  - Say that this keeps a draft the roadmap accepts from being refused later by `create`.
  - Say what happens to a draft written before the rule: it is classified malformed, and `--refresh-seeds` regenerates it. Confirm the wording against step 4's landed message.
  - Name the gate by symbol only if `rg` finds it (`plan_tool/roadmap_gates.py:validate_draft_seed_content`).
- **Per-tool source table.**
  - Use a small table in the page that owns seed-writing most (`SEED_FORMAT.md`), with columns tool, source, fallback.
  - The other three pages carry a short bullet list or a link to that table, whichever fits the page. Avoid four full copies.
  - Do not cite step numbers in the shipped docs.
- **Docs style.** Follow `docs/reference/documentation-style.md`: purpose first, mappings as tables, normal path apart from exceptions. Write in present tense. Add no "previously optional" narration.
- **Remove #532 from `BACKLOG.md`.**
  - Delete the whole entry, from its `**#532 — ...**` line through its last scope-contract bullet. Stop before `**#534 —`.
  - Do not renumber other entries.
  - Sweep the identifier and the vocabulary: `rg "#532" BACKLOG.md BUG_BACKLOG.md docs CLAUDE.md`, and `rg -i "guardrail heading" BACKLOG.md BUG_BACKLOG.md`. Fix or remove each reference to the removed entry. Leave a reference that is a dated record, and say why in the handoff.
  - The BUG_BACKLOG entry "`--commit` stages the whole working tree…" says it waits for #532's ordering. Check whether it names #532. If it does, update that text.

## Tests

### Verification (non-code step)

This step is `non-code`. The test-authoring gate keys on `change_type` and does not apply. Run these checks instead.

1. **Symbols exist.** For every code symbol or path a page cites, run `rg` at HEAD. Every one must be found. Drop any that is not.
2. **Contract matches the code.** Feed a seed with each defect through `plan-tool create --from-existing` in a throwaway repo. Cover missing, duplicate, empty and `_(TODO)_` headings, and `None`. The refusal and acceptance must match the docs.
3. **Source statements match the writers.** For each tool in the source table, read its landed renderer or prompt. Confirm the source and the fallback the docs state.
4. **Links resolve.** Check every new relative link and heading anchor. If a heading text changes, grep the repo for inbound anchors first.
5. **No stale wording.** `rg -i "optional|conditional" SEED_FORMAT.md PLAN_FORMAT.md docs/how-to/pipeline/create-from-existing.md ROADMAP_FORMAT.md` near the guardrail headings finds no sentence that still calls them optional.
6. **Backlog is clean.** `rg "#532" BACKLOG.md` shows no entry. `#534` follows the previous entry unchanged.
7. **Repo checks stay green.** Run `plan-tool validate` and the doc-drift tests (`uv run pytest tests/ -q -n auto`, in the background). Doc-drift tests may pin the text of these pages. Read any failure before editing it.
8. **Scope of change.** `git diff --stat` lists only the five declared files, unless check 7 or the `docs/reference/contracts/seed-ingestion.md` case above requires one more, which must be named.

## Acceptance criteria

- Each of the four doc pages states that all three headings are required, that `None` is valid, and that `_(TODO)_` is refused.
- Each of the four pages names the source each seed-writing tool uses for the headings, or links to the one table that does.
- `ROADMAP_FORMAT.md` states the draft-gate rule and the handling of a draft written before it.
- Every cited symbol is found by `rg` at HEAD, and every new link resolves.
- Check 2 above passes: the observed refusals and the accepted `None` match the docs.
- `BACKLOG.md` has no #532 entry, and no remaining reference to it points at a removed entry.
- `uv run pytest tests/ -q -n auto` passes.

## References

- BACKLOG #532, the source of the contract and its scope fence.
- `plan_tool/create.py` (`classify_file_backed_source`) and `plan_tool/scope_fence.py`, for the landed check.
- `plan_tool/roadmap_gates.py` (`validate_draft_seed_content`) and `plan_tool/prompts/roadmap-seed.md`.
- `plan_tool/annotate_render.py`, `plan_tool/scope_out.py` and `plan_tool/reground.py`, for each tool's source.
- `docs/reference/documentation-style.md`, the style rules for live developer docs.
- `docs/reference/contracts/seed-ingestion.md`, the owner of the exact route contract.

## Applicable guardrails

- **The plan's "## Scope guardrails", presence only.** The docs describe a presence rule. They must not suggest the tool judges, compares or caps what a guardrail says.
- **The plan's "## Scope guardrails", `None` must pass.** The docs must not list `None`, `N/A` or similar as placeholders, and must not describe `None` as a weak answer.
- **The plan's "## Scope guardrails", headings not required.** The docs must not say `## Stack`, `## Outcome` or `## In scope` are now required, and must not extend the rule to inline `--from`, `--from-plan` or archived seeds.
- **The plan's "## Scope guardrails", no new model call.** The source statements must say tools fill the headings from a source they already read or a call they already make. No page may describe a new call.
- **The plan's "## Out of scope".** The step documents only the shipped contract. It adds no new behavior, no other backlog edits, and no changes to code.

## Deferred

- Requiring `## Outcome` or `## In scope` — a separate decision, kept out by the plan's "## Out of scope".
- Any change to `docs/reference/contracts/seed-ingestion.md` beyond a one-line pointer, if it states the old rule — that page owns the route table and is not in this step's file list. Add it to the footprint explicitly if the pointer is needed.
- Consolidating the per-tool source statements into one generated table — a refactor outside this step; file a `BACKLOG.md` entry if the copies drift.
