# Step 4 — Document the draft seed's `## Stack` section and its carry through create, detail, and the audit, and reconcile BACKLOG.md #460

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step is documentation only. `ROADMAP_FORMAT.md` gains a subsection under "Draft seeds under the roadmap slug" that describes the tool-rendered `## Stack` section, and `docs/how-to/roadmap.md` § 7 gains a short note on how it travels. `PLAN_FORMAT.md` adds `Stack` to the scope-fence guardrail list. `BACKLOG.md` loses the #460 entry, since this is the plan's last step. The #461 and #462 entries keep accurate dependency notes. On green, each doc matches the code that steps 1–3 landed, and no live backlog text depends on an entry that no longer exists.

## Table of Contents

- [Why](#why) — what the docs say today versus what ships
- [Input](#input) — the landed code the docs must be read from
- [Files (creates vs edits)](#files-creates-vs-edits) — the footprint
- [Implementation](#implementation) — what each doc states, and the backlog reconciliation
- [Tests](#tests) — verification for a non-code step
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [Applicable guardrails](#applicable-guardrails) — the plan fence as it binds this step
- [Deferred](#deferred) — items left out

## Why

After steps 1–3, a draft seed carries a tool-written `## Stack` section, `create` preserves it, the `detail` fence carries it, and the plan audit treats it as authoritative. The format docs still describe draft seeds without it, and `PLAN_FORMAT.md` still lists three author-supplied guardrail sections. Operators who hand-edit a draft would not know the section is rewritten on rematerialization. BACKLOG.md #460 would still read as pending work after it ships, and #461 and #462 would depend on an entry that is gone.

## Input

- **Landed code wins.** Read the exact heading text, field names, version-id wording, and open-product wording off the landed code and tests, not off steps 1–3's detail files. If they disagree, the code wins and the doc follows it.
  - Step 1 owns the renderer and replacement helper in `plan_tool/roadmap.py`, and the `plan_tool/prompts/roadmap-seed.md` edit.
  - Step 2 owns `GUARDRAIL_BODY_SECTIONS` in `plan_tool/scope_fence.py` and `OPTIONAL_PLAN_BODY_SECTION_SHAPES` in `plan_tool/create.py`.
  - Step 3 owns the `plan_tool/prompts/plan-audit.md` edits.
- **Doc conventions** (from the sibling FORMAT docs):
  - `ROADMAP_FORMAT.md` cites enforcing symbols by name, with no line numbers.
  - `PLAN_FORMAT.md` states the guardrail order as contract.
  - `docs/how-to/roadmap.md` is a task-ordered walkthrough that routes to the format docs for contracts. Follow `docs/reference/documentation-style.md`.
- **Backlog rule:** #460 is an unpromoted, plan-authored entry. It is removed only after full shipment. This step is the plan's last, so removal belongs here. If any earlier step is not green at the time, leave the entry and mark it still pending instead.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — add a `### Stack section` subsection to "Draft seeds under the roadmap slug"; adjust the neighboring prose that says the model writes the whole draft and the "Seed body" gate list.
  - `docs/how-to/roadmap.md` — add a short note in § 7 on the section's behavior.
  - `PLAN_FORMAT.md` — update the scope-fence list and the sentence about author-supplied sections.
  - `BACKLOG.md` — remove #460; reword the #461 and #462 dependency lines.
- **Possible additions:** if the sweep below finds live references to #460 in other files (for example `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md`), add those files to this step's edit set and note the addition. Do not leave dangling references.

## Implementation

**`ROADMAP_FORMAT.md`: the stack subsection**

- State the section's purpose first: it carries the accepted hosting and store choices into the draft so `create` and `detail` do not choose a technology of their own.
- Describe the section in a small table or list, by row kind:
  - the accepted version id;
  - every hosting row, with its id, facet, value, and product;
  - the stores reached through the plan row's component ids, each once, with id, category, sharing, and product.
- State the open-product wording exactly as the code renders it, and say a missing product is never printed as `None` or left blank.
- State that the section is always emitted, including the explicit empty form when the roadmap has no hosting rows and no stores.
- State the ownership rule:
  - The tool writes the section from the accepted bytes.
  - Any model-authored `## Stack` is replaced.
  - A hand edit to the section is overwritten on the next materialization or `--refresh-seeds`.
  - A reviewer who edits the draft by hand and keeps the edit uses `--accept-seed`, which keeps that edit only until the next rematerialization.
- Name the enforcing symbols (the renderer and replacement helper in `plan_tool/roadmap.py`) with the doc's usual "Enforced by" style. Cite only symbols that exist at HEAD.
- Add the deliberate non-checks, under the existing "No gate checks" list in "Seed body":
  - no comparison of technology names;
  - no notes or conflict surfacing in `create` or `detail`;
  - the plan audit is the contradiction check, and it is advisory.
- State that drafts materialized before this change lack the section until rematerialized (`--materialize` or `--refresh-seeds`). Frame this as a current fact, not history.
- The existing promoted-seed paragraph ("After `--apply`") needs one clause: the promoted copy carries the section, and a rematerialization rewrites it too.

**`docs/how-to/roadmap.md` § 7**

- Add a short paragraph after the `--accept-seed` explanation:
  - The draft includes a tool-written `## Stack`.
  - `create --from-existing` preserves it in the plan, and `detail` and the audit read it.
  - Do not hand-edit it; change the roadmap through feedback and rematerialize.
- Link to `ROADMAP_FORMAT.md` for the contract. Do not restate the row fields here.
- Keep the sentence "preserve those fences when you amend a seed" accurate. The stack section sits beside the fences and follows the same rule.

**`PLAN_FORMAT.md`: scope fence**

- Change the guardrail half from three to four author-supplied sections, and list them in the contract order: `## Scope guardrails`, `## Audit guardrails`, `## Expected placement`, `## Stack`, then `## Out of scope`. Confirm the order against `GUARDRAIL_BODY_SECTIONS` as landed in step 2.
- Update the heading text "four body sections" to match what is listed, and the "first three guardrail sections are author-supplied" sentence to name the new set. `## Out of scope` stays the skeleton section.
- Add one sentence: `## Stack` is absent from the plan unless the seed carried it, and the plan audit treats it as authoritative.
- Keep the paragraph about what the guardrail half excludes. `## Stack` carries settled technology decisions, not delivery claims, and the paragraph should still read true. Check this wording against the code.

**`BACKLOG.md` reconciliation**

- **Remove #460 entirely** (heading through its command block). Leave no stub: it was never promoted.
- **#461** — its Dependencies line cites `#460 (its seed renderer gains the stack collection)`. Reword it to name the shipped `## Stack` seed renderer in `plan_tool/roadmap.py` instead of the removed entry id. Sweep the same entry's In scope, Origin, and Stop lines for `#460` and fix each.
- **#462** — same treatment for its Dependencies line, "Do-not-reopen decisions", "Stop / defer", "Evidence gate", and the SQLite note ("within #460's reach"). Each phrase that argues from #460 is reworded to refer to the shipped section.
- **Sweep, identifier half:** `rg -n "#460|roadmap-stack-propagation" BACKLOG.md BUG_BACKLOG.md docs/ plan-seeds/ CLAUDE.md` and decide each hit: reword, delete, or keep because it is a plan file or seed that legitimately carries its own slug.
- **Sweep, vocabulary half:** `rg -n "cite store rows by id only|stack propagation|carry the .*stack" BACKLOG.md docs/` for prose that still describes the pending gap in the present tense.
- **Arc listing:** if `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` lists #460, remove it there too.
- **Do not renumber** other backlog entries.

**Constraints**

- **Forward-looking only:** write what the section is and does. Drop "previously", "used to", and "was changed because". A dated don't-reopen decision is allowed, such as "conflict surfacing deliberately not built, decided 2026-10-08".
- **State what is deliberately not built**, with the reason, in `ROADMAP_FORMAT.md`. Do not leave it to be inferred.
- **No restating owner mechanics:** `ROADMAP_FORMAT.md` owns the section contract. The how-to and `PLAN_FORMAT.md` point to it.
- **Terse code-adjacent prose:** no new long comment blocks in code; this step edits no code.

## Tests

### Verification (non-code step)

This step changes no production code, so the test-authoring gate does not apply. Run these checks instead:

1. **Heading and field names:** `rg -n "## Stack" ROADMAP_FORMAT.md PLAN_FORMAT.md docs/how-to/roadmap.md` — each doc's wording matches a rendered draft from `tests/test_roadmap.py` (compare against the landed renderer output).
2. **Open-product wording:** the string in `ROADMAP_FORMAT.md` equals the one in the landed renderer and its test.
3. **Symbol check:** `rg -n "<each symbol cited>" plan_tool/` — every symbol named in the new subsection exists at HEAD.
4. **Guardrail order:** the list in `PLAN_FORMAT.md` equals `GUARDRAIL_BODY_SECTIONS` plus `## Out of scope`, in `plan_tool/scope_fence.py`.
5. **Doc-drift tests:** `uv run pytest tests/test_roadmap_format.py tests/test_data_contract.py -q` stays green. Run `uv run pytest tests/ -q -n auto -k "format or docs or capability or backlog"` for any doc-checking test that reads the edited files.
6. **Backlog sweep:** `rg -n "#460" BACKLOG.md BUG_BACKLOG.md docs/ CLAUDE.md plan-seeds/` returns only hits deliberately kept (state each).
7. **Links:** every relative link added resolves to a real file and anchor.
8. **Clean tree:** `git status` shows only the files named above (plus any sweep additions noted in the commit).

## Acceptance criteria

- `ROADMAP_FORMAT.md` describes the `## Stack` section: the version id, hosting row fields, store row fields, the always-emitted empty form, and the open-product wording, matching the landed renderer.
- `ROADMAP_FORMAT.md` states that the tool replaces any model-authored or hand-edited `## Stack` on rematerialization, and lists the deliberate non-checks.
- `docs/how-to/roadmap.md` § 7 tells the operator not to hand-edit the section and links to the format doc.
- `PLAN_FORMAT.md` lists `Stack` in the contract order and its "author-supplied" sentence matches `GUARDRAIL_BODY_SECTIONS`.
- BACKLOG.md has no #460 entry, and #461 and #462 contain no reference to #460 as a live dependency.
- `rg -n "#460"` over the checked-in docs returns no dangling reference.
- Existing doc-drift tests pass.
- Only the four declared files change, plus any sweep additions named in the commit message.

## Applicable guardrails

- **The plan's "## Out of scope"** limits this step to documenting what steps 1–3 shipped. It adds no stack collection (#461), no cross-plan audit (#462), and no Jira-handoff text. The docs state those as not built, with their reasons.
- **The same section** bars documenting conflict surfacing, hosting questions, or provenance as features. State them only as deliberately not built.
- **The plan's step intent** requires #460 removal only on full shipment, and the #461 and #462 dependency notes to stay accurate. This step edits those two entries' wording only, not their scope contracts.

## Deferred

- Correcting existing Integration drafts or plans — outside the plan's fence; they pick up the section on rematerialization.
- Marking the Integration HTML review aid current — belongs to #461 per its Origin line.
- Consolidating the guardrail-heading lists across docs into one source — a cross-module refactor; file it in `BACKLOG.md` if the sweep shows real duplication.
