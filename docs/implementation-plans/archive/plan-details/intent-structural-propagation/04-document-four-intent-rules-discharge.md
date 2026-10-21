> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

## Summary

This step writes the four settled intent-propagation rules into `PLAN_FORMAT.md` and closes the open carve note in `docs/implementation-plans/archive/2-intent-scope-fence.md`. It changes no production code. The main design decision is **one home for the four rules, cite steps 1–3 by outcome, do not restate their mechanisms** — operators and later audits find split, merge, forward-seed, and audit contracts in `PLAN_FORMAT.md`, and the parent Deferred no longer reads as unfinished work. On green, `PLAN_FORMAT.md` names all four rules with code anchors, and the parent archive's residual carve is marked discharged by this plan.

## Table of Contents

- [Summary](#summary) — docs-only close-out and the one-home rule.
- [Why](#why) — why the rules and the parent carve must land together.
- [Input](#input) — Architecture table and steps 1–3 outcomes this step documents.
- [Files (creates vs edits)](#files-creates-vs-edits) — two documentation edits.
- [Implementation](#implementation) — where to write the rules, how to discharge, what not to invent.
- [Tests](#tests) — doc verification checks (non-code).
- [Acceptance criteria](#acceptance-criteria) — checkable facts.
- [References](#references) — specs the documented contracts lean on.
- [Applicable guardrails](#applicable-guardrails) — plan fence entries that bind here.
- [Deferred](#deferred) — neighbors this step leaves alone.

## Why

`PLAN_FORMAT.md` already documents `Plan.intent` / `Step.intent` presence, the scope-fence thread into `detail`/`run`, and the author-time presence check — but it never names what happens to those fields when structure changes or when the conceptual audit runs. The four rules live only in this plan's Architecture table and in steps 1–3's detail files. After those steps ship, an operator reading the format doc still cannot find them. At the same time, the parent archive `docs/implementation-plans/archive/2-intent-scope-fence.md` `## Deferred` still says the structural-verb and conceptual-audit residual is **Still open**, and three other spots in that file still speak as if the carve is current. Closing the code without closing those docs leaves a second "intent program" story: shipped code, open history. This step is the bookkeeping half of the Outcome — one place for the rules, and the parent carve marked discharged.

## Input

Contracts this step reads and does not own. Confirm each at HEAD (after steps 1–3 are green) before writing.

- **This plan's Architecture "Settled verb rules" table** — the four rules to name. Do not reopen or rewrite them; document them.
- **Step 1 outcome** — `plan_tool/detail.py:split_step` / `merge_steps` obey the split-drop and merge-unanimous rules; cite those symbols as anchors, do not restate the fold recipe.
- **Step 2 outcome** — `plan_tool/scope_out.py:render_carved_seed` / `render_carved_region_seed` and `plan_tool/reground.py:render_rebaseline_seed` attach intent to its owner and never write `## Outcome`; cite those symbols.
- **Step 3 outcome** — `plan_tool/review.py:render_plan_audit_prompt` plus `plan_tool/prompts/plan-audit.md`'s `${intent_block}` deliver plan/step intents through the step-3 formatter; empty (including placeholders) → unchanged prompt. Cite those existing symbols (the formatter lands with step 3).
- **Existing `PLAN_FORMAT.md` intent prose** — `### Field semantics` for plan/step `intent`, `### Scope fence`, and `Intent-presence check`. Extend; do not duplicate the presence-is-the-entire-contract section as a fifth rule.
- **Parent archive Deferred carve bullet** — the "Partially discharged / Still open" entry naming `plan-seeds/intent-structural-propagation.md`. That is the discharge target.

**What verification cannot prove.** That a future author will find the subsection. The contract is: the four rules are written once in `PLAN_FORMAT.md`, and the parent archive no longer claims the residual is open.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `PLAN_FORMAT.md` — add one short subsection that names the four intent-propagation rules with code anchors; leave the existing presence / fence / smell prose in place (cross-link, do not copy).
  - `docs/implementation-plans/archive/2-intent-scope-fence.md` — discharge the structural-propagation carve in `## Deferred`; tense-flip the sibling "still carved out" / "Still open" sentences so they read as history pointing at this plan; leave permanently refused items and the #162 deferral alone.

Deliberate zero-diff (reviewer check): every `plan_tool/` module, every test file, `BACKLOG.md`, `CLAUDE.md`, `SEED_FORMAT.md`, `DETAIL_FORMAT.md`, and this plan's own body (except what landing the rules implies for readers of the format doc).

## Implementation

### Already-implemented check

The heuristic hit on `docs/implementation-plans/archive/2-intent-scope-fence.md` for `# Intent` is the plan title heading, not this step's work. `PLAN_FORMAT.md` has **no** structural-verb intent rules today (grep for never-copy / unanimous / `intent_block` / attach-to-owner returns nothing). Scope the step to the full remaining docs work.

### What must be true

- **`PLAN_FORMAT.md` is the single operator-facing home** for the four rules. Someone who knows frontmatter but not this plan can find split, merge, forward-seed, and conceptual-audit intent behavior without opening plan-details.
- **Each rule cites the enforcing symbol**, not a line number — so reconcile does not thrash on drift.
- **The parent archive Deferred no longer says the residual is open.** After this step, that carve reads as discharged by `docs/implementation-plans/2-intent-structural-propagation.md` (date the discharge). The archive banner's "do not edit" is ordinary-maintenance advice; this discharge is the intended exception.

### Recommended `PLAN_FORMAT.md` placement

One way: add a subsection under `### Field semantics`, immediately after the `**steps[].intent**` paragraph (before `**steps[].files**`), titled along the lines of **Intent under structural edits and the conceptual audit**.

Why there:

- Readers looking up `intent` / `steps[].intent` land on it.
- It stays next to the field that the rules govern.
- It is not a second Scope-fence rewrite — fence delivery into `detail`/`run` already has its own section; this subsection is the *mutation and audit-consumer* contract.

Rejected alternative: scattering one sentence into each of `steps[].id` (split/merge), Scope fence, and Smell checks. That splits the "one place" Outcome and drifts.

### What the subsection states (rules only — no mechanism restatement)

Name exactly the Architecture table's four rows. Prefer a compact list or table. For each row, give the rule in one line and the code anchor:

| Verb / surface | Rule to name | Anchor to cite (steps 1–3 outcomes) |
|---|---|---|
| split | never copy the target's intent onto either half | `plan_tool/detail.py:split_step` |
| merge | keep intent only when every member shares the same usable value (placeholders count as absent); else clear | `plan_tool/detail.py:merge_steps` |
| scope-out / reground seeds | attach intent to its owner; source plan intent is not the new `## Outcome`; drop absent / blank / whitespace / placeholders and collapse newlines before embed | `plan_tool/scope_out.py:render_carved_seed` / `render_carved_region_seed`, `plan_tool/reground.py:render_rebaseline_seed` |
| conceptual audit | dynamic `${intent_block}` only; empty (including placeholders) → same prompt as an intent-free plan | `plan_tool/review.py:render_plan_audit_prompt`, `plan_tool/prompts/plan-audit.md` |

Also name once, briefly:

- **Prefer absent over false** — the shared invariant behind split/merge/seeds.
- **Reuse `plan_tool/scope_fence.py:collapse_intent_to_one_line`** — do not invent a third normalizer (Architecture Reuse bullet).
- **Presence contract** — point at the existing "Presence is the entire contract" prose and the Smell-checks Intent-presence paragraph. **Correct that prose where it is wrong at HEAD:** today it says `is_usable_intent` recognizes exactly three non-values and omits naming `TBD`, but `is_usable_intent` / `_BODY_PLACEHOLDER_RE` already drop bare `TBD`. Update the Presence paragraph so the non-value list matches HEAD (include `TBD`) without adding quality/shape/length rules. Cross-link; do not re-argue content validation.
- **Fence presence set for structural surfaces** — in the four-rule subsection, name once that merge / forward-seed / conceptual-audit omit use the **fence** placeholder set (`TODO` / `_(TODO)_`), and that **`TBD` is outside that named set** (it still clears under `is_usable_intent` for the advisory presence smell). Do not unify the two predicates here (#227).

Do **not** add:

- quality / agreement / length rules;
- a claim that parse time rejects missing intent;
- CLI flag docs (`--intent` on split/merge) this plan does not ship;
- a restatement of step 1's merge comparison algorithm or step 3's formatter shape.

### Parent archive discharge

Edit `docs/implementation-plans/archive/2-intent-scope-fence.md` as history, not as a live redesign.

1. **`## Deferred` carve bullet** — flip **Still open** to **Discharged** (date it). Point at `docs/implementation-plans/2-intent-structural-propagation.md` as the plan that shipped the residual. Keep the "Partially discharged via `2-intent-required`" half as prior history. The old seed path may be noted as superseded; do not leave readers chasing `plan-seeds/intent-structural-propagation.md` as live work.
2. **Sweep present-tense "carve is open" siblings** in the same file so they cannot be read as current design:
   - `### The other two fences` — the bullet that still says other consumers and structural-verb propagation "are carved out";
   - `## Out of scope` — the bullet that still lists delivery past `detail`/`run` and `split`/`merge`/`scope-out`/`reground` as carved out;
   - `## Risks` — the "deliberately does not touch the structural verbs" hazard, if it still reads as an open gap rather than history (structural-verb stale-intent was the carve; `BACKLOG.md` #212 remains the `apply_finding` residue — say that plainly if you touch the Risk, without filing a new program).
3. **Leave alone** — permanent "Any validation beyond presence" refusal; the #162 Deferred bullet; Overview / Problem statement prose that describes *this* plan's shipped fence (not the carve residual).

### Foundational-logic sweep

Core rule: **document the four settled intent-propagation contracts in one format-doc home and mark the parent carve discharged.**

| Site | Disposition |
|---|---|
| `PLAN_FORMAT.md` four-rule subsection | **This step** |
| Parent archive Deferred + open-carve present-tense siblings | **This step** |
| Steps 1–3 production symbols | **Cite only** — already shipped by depends_on |
| Presence / fence / smell prose already in `PLAN_FORMAT.md` | **Cross-link** — do not duplicate |
| Live plan `## Deferred` (#212, #161/#162, further consumers) | **Zero-diff** — still this plan's Deferred, not the parent carve |
| `CLAUDE.md` intent reversal record | **Deferred** — not in `files:` |
| `BACKLOG.md` #212 | **Deferred** — stays open; do not invent a second entry for work this plan already owns |

### Constraints and gotchas

- **Archive "do not edit" banner** — ordinary maintenance stays off; this discharge is the planned exception. Do not remove the auto-archived banner.
- **Present and future tense in `PLAN_FORMAT.md`** — describe what the tool *does*. Past-tense carve narrative belongs only in the archive discharge notes.
- **Do not invent a second intent program** — no new schema field, no new smell, no new backlog id for the residual this plan already covers. Discharge is the seed's alternate bookkeeping path.
- **Symbol names must match HEAD after steps 1–3** — if a helper was renamed during implementation, cite the live name; the Architecture rule text stays the same.
- **Full repo-root paths** in the format doc when naming files (`plan_tool/detail.py`, not `detail.py`).

## Tests

### Verification (non-code step)

No unit tests. Check the two artifacts by hand (or with ripgrep) after the edit:

- `plan_format_names_all_four_rules` — `PLAN_FORMAT.md` states the split, merge, forward-seed, and conceptual-audit intent rules in one subsection.
- `plan_format_cites_enforcing_symbols` — that subsection names the step 1–3 symbols (or their HEAD equivalents), not bare line numbers.
- `plan_format_does_not_add_content_validation` — no new quality / agreement / length / gate claim under the new subsection; presence still points at the existing contract.
- `parent_deferred_no_longer_still_open` — the parent archive Deferred carve bullet does not say structural propagation / conceptual-audit delivery is still open; it names this plan as the discharge.
- `parent_open_carve_prose_swept` — the three present-tense carve siblings (`The other two fences`, Out of scope delivery bullet, and any Risks "does not touch structural verbs" claim that still reads as open) are marked history or pointed at the discharge.
- `permanent_refusals_intact` — "Any validation beyond presence" and the #162 Deferred bullet remain; this step did not pretend to close them.
- `no_production_diff` — `git diff --stat` for this step touches only the two declared paths.

## Acceptance criteria

- `PLAN_FORMAT.md` contains one subsection that names all four Architecture rules (split, merge, scope-out/reground seeds, conceptual audit).
- That subsection cites the enforcing symbols from steps 1–3 (or their HEAD names) with full repo-root paths.
- The subsection does not introduce content validation, parse-time required intent, or a fifth structural rule.
- Existing Presence / Scope fence / Intent-presence prose remains; the new subsection cross-links rather than copying it.
- `docs/implementation-plans/archive/2-intent-scope-fence.md` `## Deferred` carve entry is marked discharged by `docs/implementation-plans/2-intent-structural-propagation.md` and no longer says **Still open** for that residual.
- The archive's present-tense "carved out" / open-residual siblings listed in Implementation are updated so they cannot be read as current unfinished work.
- Permanently refused validation-beyond-presence and the #162 deferral are unchanged in substance.
- No `plan_tool/` or `tests/` file changes in this step's diff.

## References

- [CommonMark Spec — ATX headings](https://spec.commonmark.org/0.31.2/#atx-headings) — why the documented seed/audit rules require collapsing multi-line intents before embedding them in markdown.
- [string.Template — Python 3.13 Library Reference](https://docs.python.org/3.13/library/string.html#template-strings) — `${intent_block}` / `safe_substitute` behavior the conceptual-audit rule documents.
- [YAML 1.2.2 Specification](https://yaml.org/spec/1.2.2/) — optional `intent:` scalars and omit-when-unset rewrite behavior the format doc already assumes beside these rules.

## Applicable guardrails

- **The plan's "## Plan intent"** — documenting the rules must not invent a quietly false carry-over story; the format doc states true-or-absent after structural work, matching the plan Outcome.
- **The plan's "## Step intent"** — operators find the four contracts in one place; close the parent carve without inventing a second intent program.
- **The plan's "## Out of scope"** — do not reopen shipped intent authoring/fence work; do not add content validation; leave #212 and #161/#162 alone. Docs and Deferred discharge only.

## Deferred

- **`CLAUDE.md` reference-doc / intent-record sweep** — not in this step's `files:`; only if a cardinality claim there goes stale after the format subsection lands, fix by hand or a follow-up.
- **`BACKLOG.md` #212** — stays open; named in this plan's Deferred / Out of scope; do not discharge it here.
- **#161 / #162 full scope-contract audit block** — remains deferred on the parent archive and this plan; not this residual.
- **Further prompt consumers** (reconcile review prompt, annotate seeds, etc.) — this plan's Deferred; out of the four-rule set.
- **Filing a new BACKLOG id for structural propagation** — rejected; discharge via the parent Deferred is the chosen bookkeeping path.
- **Editing this plan's own `## Deferred` / Acceptance prose in the plan body** — outside the declared `files:`; landing the format rules is enough for the docs criterion.
