> **Replaced**: this file has been superseded by `docs/implementation-plans/2-intent-structural-propagation.md`.
> Preserved here for history; do not edit.

# Plan seed: intent structural propagation (split / merge / forward-seeds / conceptual audit)

This file is a `plan-tool create` input. Use it via:

```
plan-tool create intent-structural-propagation --from-existing plan-seeds/intent-structural-propagation.md --iterate
```

> **Provenance.** Residual of the 2026-08-01 carve from
> `2-intent-scope-fence` (archived). The original carve dump lived at
> `plan-seeds/archive/intent-scope-fence-carved-fill-the-plan-s-intent-from-through-11.md`
> and mixed shipped work with open work. **Already shipped** (do not re-plan):
> `Plan.intent` / `Step.intent` schema + advisory presence
> (`2-intent-scope-fence`); `create` Outcome→intent mapping, step-proposal
> intent, docs, and BACKLOG #206 close-out (`2-intent-required`); fence
> rendering into `detail` / `run` via `plan_tool/scope_fence.py`. **This seed
> covers only what remains:** propagation through the four structural verbs
> and delivery into the conceptual-audit prompt.
>
> No numbered BACKLOG entry owns this residual yet. The plan's final
> docs/status step must either file one and mark it plan-authored, or update
> `2-intent-scope-fence`'s `## Deferred` to point here and note discharge on
> ship. Do not invent a second intent program.

---

## Outcome

After every structural mutation and every conceptual-audit call, every
surviving step's `intent` is either **true of that step** or **absent** —
never a quietly false carry-over — and the conceptual audit **receives** the
plan/step intents its "stay inside the declared scope contract" rule already
assumes.

## In scope

1. **`split` / `merge` intent rules** on the step transforms
   (`detail.py:split_step` / `merge_steps` and their create-side ownership
   helpers). Settled contracts (do not re-litigate):
   - **Split never copies** the target's intent onto either half.
   - **Merge keeps** an intent only when every folded member states the
     *same* non-blank intent; otherwise clears it.
2. **Forward-seed renderers** for `scope-out` and `reground`
   (`render_carved_seed`, `render_carved_region_seed`,
   `render_rebaseline_seed`). Settled contracts:
   - An intent renders **attached to the thing it describes** — a carved
     step's intent rides its own scope block; the source plan's intent is
     labeled as the *source* plan's, never rewritten as the new effort's
     `## Outcome`.
   - Blank / whitespace / multi-line values are collapsed to one line or
     dropped before seed text (no forged headings).
   - `compute_narrow` / `mark_steps_done` need no production edit if they
     already copy step fields through — pin with tests.
3. **Conceptual-audit prompt delivery** (`review.py` +
   `prompts/plan-audit.md`): a dynamic intent block; **all new prompt text
   lives inside the block**. A plan with no intents renders
   **byte-identical** audit prompts to today.

## Out of scope / Non-goals

- Re-authoring schema, presence check, `create` Outcome mapping, wizard
  proposal, or fence rendering into `detail`/`run` — shipped.
- **Any validation of intent content** — quality, agreement with `## Why`,
  length caps, gates, exit-code flips. Permanently refused (same fence as
  `2-intent-scope-fence` / CLAUDE.md intent record).
- **BACKLOG #212** (`apply_finding` leaving a stale intent) — deliberately
  fenced out of the structural-verb set; file/keep separate.
- #161/#162 seed/backlog scope-contract prompt work.
- New CLI verbs, migrations, backfills, or requiring intent on existing plans.
- Changing required detail H2s at either grade.

## Allowed behavior changes

- Split/merge frontmatter after a structural edit: surviving steps carry a
  defensible intent or none.
- Carved / re-baseline seeds may gain labeled intent lines when source
  intents exist; intent-free plans produce **identical** seed text to today.
- Conceptual-audit prompts gain an intent block only when at least one
  intent is present.

## Allowed reorganization

None. Edits stay in the existing transform and renderer owners.

## Verification

- Intent-free plans: byte-identical split/merge frontmatter paths (no new
  `intent:` keys), byte-identical forward seeds, byte-identical audit
  prompts.
- Split of an intent-bearing step → neither half carries the parent's
  intent.
- Merge of matching intents → survivor keeps it; mixed/blank → cleared.
- Carve/re-baseline of an intent-bearing plan → source plan intent labeled
  as source; per-step intents attached to their blocks; newlines cannot
  forge headings.
- Intent-bearing plan's audit prompt contains the intents; bodyless plan
  still returns `None` from the renderer (existing contract).
- No test asserts intent *quality* or length beyond one-line collapse.

## Stop / defer

- #212 and any non-structural stale-intent path → `BACKLOG.md`.
- Intent content validation proposals → reject; cite the permanent fence.
- Further audit consumers beyond conceptual audit → new backlog entry.

---

## Overview

`Plan.intent` and `Step.intent` exist and reach `detail`/`run`, but the four
structural verbs either leave intent unspecified (so the next edit copies it
blindly) or drop it on the floor when writing the next `create
--from-existing` seed. The conceptual audit still strips frontmatter, so the
prompt rule that says "honor the Outcome" never sees the Outcome. This plan
closes that residual only.

## Problem statement

A stale or missing why is worst exactly where structure changes: split can
duplicate a parent's purpose onto two half-steps; merge can keep a member's
why over a survivor that now does more; carve/re-baseline seeds hand the next
`create` every field except the why; the conceptual audit is the creep
detector and is the one consumer a frontmatter field cannot reach by accident.

## Architecture

**One invariant.** Every surviving step ends with an intent that is true of
it, or with none. Prefer absent over false.

**Settled verb rules** (from the carve; load-bearing — do not reopen):

| Verb | Rule |
|---|---|
| split | never copy target intent onto halves |
| merge | keep only if every member's intent is the same non-blank value; else clear |
| scope-out / reground seeds | attach intent to its owner; source plan intent ≠ new `## Outcome`; collapse/drop unsafe values |
| conceptual audit | dynamic `${intent_block}` only; empty → byte-identical prompt |

**Ordering.** Pin split/merge first (in-plan structure), then forward-seed
renderers (handoff), then audit delivery (consumer). Each layer is
independently shippable and testable.

**Reuse.** Collapse/one-line helpers already used by the fence renderer —
call them; do not invent a third normalization copy (see closed #225).

## Out of scope

See the scope contract above. Explicitly: shipped intent authoring/fence
work; #212; content validation; #161/#162.

## Risks

- Someone "helpfully" copies intent on split by analogy with `change_type` —
  the tests are the contract.
- Forward-seed parameter gaps (`render_carved_seed` takes `plan_title: str`,
  not `Plan`) — plan intent needs an explicit new parameter, not a silent
  omission.
- Putting static intent prose in `plan-audit.md` would change every prompt
  even for intent-free plans — keep all new text inside the dynamic block.

## Testing

Green-before-done on the three surfaces. Intent-free fixtures must stay
byte-identical. Table-drive the five legal intent shapes (`None`, `""`,
whitespace, one-liner, embedded newline) on merge and on seed render.
No content-quality assertions.

## Acceptance criteria

- Split/merge obey the settled rules; pinned by tests.
- The three forward-seed renderers carry plan/step intent per the attach-to-
  owner rule; intent-free output unchanged.
- Conceptual audit prompt receives intents when present and is unchanged
  when absent.
- Permanent no-validation fence holds in code and tests.
- Docs: `PLAN_FORMAT.md` / structural-verb notes name the four rules; the
  parent plan's Deferred / any new backlog entry is reconciled on ship.

## Deferred

- BACKLOG #212 (`apply_finding` stale intent).
- #161/#162 scope-contract audit block.
- Any further prompt consumers.
