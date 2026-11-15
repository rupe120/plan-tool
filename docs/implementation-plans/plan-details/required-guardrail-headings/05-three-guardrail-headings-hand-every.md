# Step 5 — Add the three guardrail headings by hand to every live seed that lacks one

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step edits the live seed files in `docs/implementation-plans/plan-seeds/` and `plan-seeds/` by hand, adding `## Scope guardrails`, `## Audit guardrails` and `## Expected placement` wherever step 1's check reports an offence. Each body comes from the seed's own scope fence, `Out of scope` and `Allowed reorganization` text, and is `None` when the seed states no such boundary. Existing sections stay untouched, and `archive/` is not edited. No code changes. The key decision is that step 1's predicate decides which headings are missing, not a grep or a hand count. On green, the predicate reports nothing for every seed in both directories.

## Table of Contents

- [Input](#input) — what step 1 provides and the state of both directories
- [Why](#why) — why live seeds must change before the refusal turns on
- [Files (creates vs edits)](#files-creates-vs-edits) — the files touched
- [Implementation](#implementation) — how to choose each heading's body and what must hold
- [Verification (non-code step)](#verification-non-code-step) — checks to run
- [Acceptance criteria](#acceptance-criteria) — observable results
- [References](#references) — docs to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work left out

## Input

- **Step 1's check.** Step 1 adds a constant naming the three headings and a pure function in `plan_tool/scope_fence.py`. The function reports each heading that is missing, duplicated, empty or a placeholder. At HEAD of this drafting neither exists (`rg missing_required_guardrail_headings plan_tool` returns nothing). Read the landed names off the module at implementation time. The landed names win over any spelling here.
- **State of both directories at HEAD (a count by `^## <heading>` match, not the predicate).**
  - `docs/implementation-plans/plan-seeds/` holds six seed files plus `README.md`.
  - `plan-seeds/` holds 22 seed files plus `README.md`.
  - Only `docs/implementation-plans/plan-seeds/commit-scoped-to-verb-footprint.md` and `plan-seeds/convergence-handoff-guide.md` match any of the three headings, one match each.
  - The other 26 seed files match none.
  - The predicate may also flag a heading that is present but empty, duplicated or a placeholder. Treat its output as the authority and the count above as orientation.
- **The two `README.md` files are not seeds.** They have no guardrail headings and are never inputs to `create --from-existing`. The step does not add headings to them. If the predicate is run over every file in the directory and flags a README, run it over the seed files only (every `.md` except `README.md` and `archive/`) and say so in the handoff.
- **Limit on verification.** The predicate proves presence only. It cannot show that a body is a faithful reading of the seed, so that needs a human read of each insertion.

## Why

Step 1's check is wired into `create --from-existing` by a later step, and that refusal happens before any model call. Without this step, every live seed that lacks a heading would be refused the next time someone runs `create` on it. The plan's intent for this step is that live seeds keep working after the refusal turns on. Seeds are prose written by people, so the headings are added by hand rather than by a tool that would need a new model call, which the plan forbids.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):** every seed file under `docs/implementation-plans/plan-seeds/` and `plan-seeds/` that step 1's predicate reports.
  - At HEAD that is expected to be the 26 files with no matching heading, plus anything the predicate flags among the 2 that have one (a duplicate, empty or placeholder body).
  - Each edit is an insertion of one to three `## ...` sections with a body. No existing line is changed or removed.
- **Not touched:** `README.md` in either directory, and everything under either `archive/` directory.

## Implementation

- **Run the predicate first and list the offenders.**
  - Use step 1's function over each seed file's text and record per file which headings it reports.
  - Edit only reported headings. A heading the predicate accepts stays as written.
- **Write each body from the seed itself.**
  - `## Scope guardrails`: take the seed's scope fence, meaning what the seed says the work may and may not do. Look at its `Scope contract`, `Not allowed`, `Allowed behavior changes` and similar sections.
  - `## Audit guardrails`: take what the seed says audits or reviewers must not widen into or must treat as settled. Often that is its `Out of scope` or `Stop / defer` content.
  - `## Expected placement`: take where the seed says the work lands, from its `Allowed reorganization` or an explicit destination. Name destinations, not construction steps.
  - Condense and cite rather than invent. A body may restate a boundary the seed already states in fewer words.
- **Write `None` where the seed states no such boundary.**
  - Use the exact word `None` on its own line. The step 1 rule accepts it as content and the plan forbids adding `None` to the placeholder pattern.
  - Do not write `N/A`, `TBD` or `_(TODO)_`; the check refuses those.
  - Do not write `None` for a heading whose content the seed does state. Read the seed fully first.
- **Placement and order.**
  - Insert the three headings together, in the constant's order, after `Out of scope` or the last content section and before `## References` when one exists. One way: follow `commit-scoped-to-verb-footprint.md` or `convergence-handoff-guide.md` as the local example of the shape.
  - Keep each as its own H2 that starts its own line. Never put one inside a fenced block.
- **Constraints that must hold.**
  - Do not add new scope, a new requirement, or a new non-goal. A body only restates what is already in the seed.
  - Leave every existing section's text unchanged, including whitespace.
  - Do not delete or overwrite anything; every change is an insertion.
  - Do not touch frontmatter. A seed with frontmatter keeps it, and the headings go in the body.
- **Commit.** Land the insertions as one commit that touches only these seed files, separate from any code change.
- **Rejected alternative.** A script that inserts `None` into every offender would be quick, but it would write `None` for seeds that do state a fence and hide that boundary. The plan names this step as a by-hand edit for that reason.

## Verification (non-code step)

This is a **non-code** step; it changes no production code, so no unit tests apply. The test-authoring gate keys on `change_type` and does not fire for it. Verify with these checks:

1. Run step 1's predicate over every seed file in both directories. It must report nothing.
2. Run `git diff --stat` and confirm only seed `.md` files under the two directories changed, with none under either `archive/` and neither `README.md`.
3. Run `git diff` and confirm every hunk is a pure addition: no `-` lines other than file headers.
4. For each edited seed, read its inserted bodies against that seed's own sections. Confirm each body restates something already there, or is `None` because the seed states nothing.
5. Run `rg -c '^## (Scope guardrails|Audit guardrails|Expected placement)$'` over each seed and confirm each file has exactly one match per heading.
6. Run `plan-tool validate` and confirm it reports nothing new for the seeds.

## Acceptance criteria

- Step 1's predicate reports no offence for any seed file in `docs/implementation-plans/plan-seeds/` or `plan-seeds/`.
- Every heading each seed gained appears exactly once, as an H2 outside any fenced block, with a non-empty body.
- `git diff` over the two directories shows additions only, and no change under either `archive/`.
- Neither `README.md` is edited.
- Every `None` body is on a seed that states no such boundary, confirmed by the human read in verification check 4.
- The commit touches no file outside the two seed directories.

## References

- `plan_tool/scope_fence.py` (step 1's constant and function, `GUARDRAIL_BODY_SECTIONS`, `_is_placeholder_section`) — the rule that defines a missing heading.
- `SEED_FORMAT.md` — what a seed's scope fence is and how to name destinations.
- `docs/how-to/pipeline/create-from-existing.md` — what the `create --from-existing` intake reads from a seed.
- `docs/implementation-plans/plan-seeds/commit-scoped-to-verb-footprint.md` and `plan-seeds/convergence-handoff-guide.md` — the two seeds that already carry a guardrail heading.

## Applicable guardrails

- The plan's "## Scope guardrails", the presence-only bullet: this step adds headings and judges no guardrail content, so it must not compare, grade or cap what any seed says.
- The plan's "## Scope guardrails", the `None` bullet: `None` must pass as written, so this step uses it and must not introduce any other placeholder spelling.
- The plan's "## Scope guardrails", the bullet naming what is not required or touched: this step must not add `## Stack`, `## Outcome` or `## In scope`, and must not touch archived seeds.
- The plan's "## Scope guardrails", the bullet on seed-writing tools: no tool or model call is added here, since this is a hand edit.
- The plan's "## Out of scope", archived seeds and any check beyond presence: nothing in either `archive/` changes, and no seed text is rewritten.

## Deferred

- Requiring `## Outcome` or `## In scope` in live seeds — separate decision named in the plan's "## Out of scope".
- Reviewing whether each seed's fence is good, or agrees with its `Out of scope` — the plan refuses any check past presence.
- Adding guardrail headings to the two `README.md` files — they are not seeds and `create` never reads them.
- Seeds created after this step — covered by steps 2 to 4, which make the seed-writing tools emit all three headings.

## Tests

_(stub: model omitted this section — fill in manually)_

