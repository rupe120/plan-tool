> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 9 — Document both intent fields and the `## Outcome` mapping in the format and flow docs

## Summary

Document `Plan.intent` and `Step.intent` across the four docs that own the contract a reader needs to comply with: `PLAN_FORMAT.md` gains the two frontmatter rows, their field semantics, the defaults entry, the fence's intent half, and the `intent-presence` smell entry; `SEED_FORMAT.md` states that the seed's `## Outcome` **is** the seed's intent and maps to `Plan.intent`; `docs/CREATE_FROM_EXISTING_FLOW.md` maps where each value comes from during a `create` run; `docs/AUDIT_FLOW.md` records that a missing intent now blocks completeness convergence and that the finding never reaches the apply walk — the remedy is a one-line frontmatter edit. The key design decision is a **fixed ownership split** — each fact class lives in exactly one of the four docs and the others cross-link — because the alternative (restating the field contract in all four) is the drift this repo has already paid for once. No production code changes. On green, a reader who has never opened `plan_tool/schema.py` can author both fields correctly, and every symbol the four docs newly cite resolves at HEAD.

## Table of Contents

- [Summary](#summary) — what the step documents and what is true on green.
- [Why](#why) — why a shipped, now-blocking field with no format-doc entry is a gap.
- [Input](#input) — the landed code and doc conventions this step reads, and how to read them.
- [Files (creates vs edits)](#files-creates-vs-edits) — the four docs touched and the per-file edits.
- [Implementation](#implementation) — the ownership split, the per-doc content, the constraints, and the alternatives rejected.
- [Tests](#tests) — why the test-authoring gate does not apply, and the verification list that replaces it.
- [Acceptance criteria](#acceptance-criteria) — checks a reviewer or CI can run.
- [References](#references) — the docs bearing on the contracts these files describe.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step's prose.
- [Deferred](#deferred) — the docs, sweeps, and decisions this step leaves alone.

## Why

`PLAN_FORMAT.md` is the one place a human or a coding agent looks up what may appear in a plan's frontmatter, and neither `intent` field is in it. Its `## Frontmatter schema` YAML block, its `### Field semantics` list, and its `### Defaults` table all read as complete, so a reader who follows the doc writes a plan with no intent — and after step 6 that plan blocks completeness convergence with nothing in the doc explaining why. `SEED_FORMAT.md` has the same shape of gap on the other side: it requires `## Outcome` as part of the scope contract but says nothing about the value being read into the plan, so an author has no reason to think the section is load-bearing past the fence. The two flow docs are where a reader goes to find out *when* a value is produced and *what happens to it later*, and both are silent. This step is the last one before closeout, so every symbol it needs to name is already on disk.

## Input

This step reads landed code and existing doc conventions. It changes neither.

- **The two schema fields** — `plan_tool/schema.py`, `Plan.intent` and `Step.intent`. Both are `Optional[str] = None`, both sit directly after `title` in their model, and both are left out of rewritten frontmatter when `None`. Their field comments state the rule the doc must carry: presence is checked in `review.py`, never at parse time, so empty, placeholder, and multi-line values all parse.
- **The presence predicate and the finding** — `plan_tool/review.py`. Step 1 makes the predicate public and step 6 changes the finding's severity. **Read the landed names off the module, not out of this plan or a sibling detail file** — the plan text proposed names before the code existed, and the landed name wins on any disagreement. The names to confirm before citing: the public presence predicate, `check_intent_presence`, `INTENT_PRESENCE_SOURCE`, and `SELF_CONSISTENCY_SOURCES`.
- **The fence renderer** — `plan_tool/scope_fence.py`. `render_scope_fence` renders the whole fence (intent half, then guardrail half) and `extract_plan_guardrails` renders the guardrail half alone. `PLAN_INTENT_HEADING` and `STEP_INTENT_HEADING` are the two headings. `_render_intent_section` collapses whitespace to single spaces and renders nothing for an empty or placeholder value. `plan_tool/renderer.py:_scope_fence_section` unwraps the two `Optional[str]` values for the run prompt; `plan_tool/detail.py` does the same for the detail prompt.
- **Where the finding lands in a report** — `plan_tool/cli/completeness_phases.py` partitions findings whose source is in `SELF_CONSISTENCY_SOURCES` off the advisory smell bucket onto `self_consistency_recs`, rendered under `### Self-consistency`. `plan_tool/cli/inspect.py`'s `validate` handler calls `collect_smell_findings` directly, without that partition, and its own comment records that its findings never touch the exit code.
- **The doc families' conventions.** `PLAN_FORMAT.md` carries the source-of-truth banner and fenced `yaml` schema blocks with inline `# required` / `# default` comments; it has **no** `## See also` tail (only `DETAIL_FORMAT.md` and `JIRA_FORMAT.md` do). The two flow docs each close with a `| Concern | File |` source map that must gain a row for any newly cited symbol.

**What this step cannot verify.** Nothing here checks that a documented rule is followed, that an authored intent is good, or that the four docs agree with each other in prose. The checkable claims are mechanical: a cited symbol exists, an anchor resolves, a fact class appears in one file. Everything past that is a reviewer's read.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `PLAN_FORMAT.md` — add `intent` to the `## Frontmatter schema` YAML block at both levels; add two `### Field semantics` entries; add the `steps[].intent` row to the `### Defaults` table and name plan-level `intent` in the prose beneath it; document the fence's intent half under `### Plan-level scope fence (reaches the `detail` prompt)`; add an intent-presence entry under `## Smell checks (advisory)` and correct that section's preamble; add an `intent:` line to the `## Example` block.
  - `SEED_FORMAT.md` — extend the `Outcome` bullet in the scope-contract list with the mapping; extend the "Canonical H2s pay for themselves" convention bullet with what an absent `## Outcome` costs; record the one-why-section decision.
  - `docs/CREATE_FROM_EXISTING_FLOW.md` — add a TL;DR bullet; place the `## Outcome` read in the high-level flow diagram above the distill box; add a short section covering the three intent sources; add source-map rows.
  - `docs/AUDIT_FLOW.md` — record the intent finding's blocking bucket in the `completeness` section, state in the `reconcile` walk section that the finding never reaches that walk, and add one clause to the jira-grade subsection; add source-map rows.

## Implementation

### The ownership split (the design decision)

Each fact class gets **one home doc**; the other three cross-link to it and never restate it. Change the home doc and let the links carry the change.

- **`PLAN_FORMAT.md` owns the field contract** — type, default, elision on rewrite, the three non-values, presence-not-quality, the fence's intent half, and the detector's severity.
- **`SEED_FORMAT.md` owns the seed side** — `## Outcome` is the seed's intent, and what an absent one costs.
- **`docs/CREATE_FROM_EXISTING_FLOW.md` owns the authoring flow** — which producer supplies which value, in what order, at what round-trip cost.
- **`docs/AUDIT_FLOW.md` owns the audit and walk behavior** — which report bucket the finding renders in, and that the walk has no remedy to dispatch for it.

The rejected alternative is the obvious one: restate the field's shape wherever it is mentioned, so each doc reads standalone. This repo has measured what that costs — the jira-grade five-section contract was deliberately pinned to one file for exactly this reason, and a contract restated in six documents drifts six ways. A one-line pointer is cheaper to keep true than a paragraph.

### `PLAN_FORMAT.md`

The doc's own banner says the code wins on disagreement, so mirror `plan_tool/schema.py` rather than paraphrasing it.

- **Frontmatter schema block.** Add `intent` at plan level directly after `title`, and inside `steps[]` directly after `title`. Field order matters: it should read the way `write_plan` emits a plan, so an author comparing the doc to a real file sees the same sequence. Both rows are `string # optional.` with a one-clause note.
- **Field semantics.** Two entries, one per level, each stating: what the line is for (one line on why this plan / this step exists — the positive half of the scope fence); that it is optional, defaults to `null`, and is left out of rewritten frontmatter when unset; that presence is checked in `plan_tool/review.py`, never at parse time, so empty, placeholder, and multi-line values all parse; that **presence is the whole contract** — nothing judges quality, shape, or length; and where the value comes from (`create` maps the seed's `## Outcome` to the plan field and reads the step field off the step-proposal JSON; the gated proposer supplies whatever is still missing). Keep the producer sentences short and point at `docs/CREATE_FROM_EXISTING_FLOW.md` for the flow.
- **Defaults.** Add `steps[].intent` → `null` to the table, and add plan-level `intent` to the sentence beneath it that lists the optional plan-level fields.
- **The scope-fence section — bridge its exclusion rationale in the same edit, or the doc contradicts itself.** The section currently states that the channel *"carries **fence** content only — what the step must *not* build. It deliberately excludes sections asserting what the plan delivers, so `detail` states the step's own claims independently and the audit can still detect a contradiction between the two."* Adding the positive intent half beside that sentence, untouched, leaves a reader meeting two adjacent rules that appear to disagree about whether the fence may carry positive claims. **Scope the exclusion to what it was always about — the plan's *delivery claims*, i.e. body sections asserting what gets built — and say why threading purpose leaves the independent-claims property intact:** an intent states why a unit exists, not what it delivers, so `detail` still authors its own claims and the audit still has two independently-written artifacts to compare. Both sentences must end up true at once; do not delete the exclusion rationale, and do not leave it unqualified.
- The fence now has two halves. Document that `plan_tool/scope_fence.py:render_scope_fence` renders both — the intent half first (plan intent, then step intent, order is contract, widest fence first), then the guardrail sections — and that `extract_plan_guardrails` is the guardrail half on its own. Two behaviors are worth stating because an author will otherwise be surprised: whitespace in an intent collapses to single spaces (a real newline could otherwise open a line with `##` and forge a heading inside a block the prompt labels authoritative), and an empty or `_(TODO)_`-style intent renders nothing at all. The section heading names only the `detail` prompt; all four templates carrying `${scope_fence_block}` render the fence, so widening the heading is a reasonable call — **grep for inbound links first** (`rg 'plan-level-scope-fence'`), since a heading rename silently changes the anchor. At the time of writing there are none, and the doc's own in-file links target `#body-sections-advisory-checked` and `#smell-checks-advisory`.
- **Smell checks.** Add an intent-presence entry naming `plan_tool/review.py:check_intent_presence`, what it flags (a plan or step whose intent is absent, empty, or a placeholder), and the roll-up shape — at most two findings per plan, one for the plan field and one naming every step id that lacks one, and it never echoes the value it read.

  The section's preamble currently says every smell emits a lowest-severity `info` finding, which the new entry contradicts. Correct it: **most** smells stay `info`; the ones on `SELF_CONSISTENCY_SOURCES` emit `medium` and the completeness battery partitions them onto its blocking-capable bucket. That same correction makes the shipped `suppression-shape` row accurate — it is one sentence covering both, not a second change. Two things must survive the edit unchanged: the statement that **none of these flips the exit code** (still true — see the guardrail note below), and the fact that `plan-tool validate` calls the smell fan-out directly, so it prints the finding as an advisory smell and never gates on it, while `completeness-audit` routes the same finding to the blocking bucket. **Do not rename the section** — three in-file links target `#smell-checks-advisory`.
- **Example.** Add an `intent:` line at plan level and on at least one step, so the example matches what `create` now writes.
- **Do not add a `## See also` tail.** `PLAN_FORMAT.md` does not have one and the family is not uniform on that point.

### `SEED_FORMAT.md`

- **The `Outcome` bullet** in the scope-contract list gains the mapping: `create` reads `## Outcome` off the seed and maps it to the new plan's `intent`, deterministically and with no Claude call. State the read order in one clause — it happens against the **raw seed**, before the distill first-pass, because `Outcome` has no canonical-body counterpart and distillation drops it — and point at `docs/CREATE_FROM_EXISTING_FLOW.md` for the rest.
- **The "Canonical H2s pay for themselves" bullet** already warns that `Outcome` and `In scope` have no canonical-H2 counterpart and get silently omitted by a canonical-shaped seed. Extend the consequence: a seed with no usable `## Outcome` maps no plan intent, so `create` falls back to offering a proposed one.
- **One why-section, not two.** Record as a dated, settled decision that the seed format gains **no** second why/intent section — `Outcome` is it. Two prose fields at the same level that can disagree is the duplication this was decided against. Frame it as history per the forward-looking rule ("decided 2026-08-02; do not re-open"), not as present-tense design prose.

### `docs/CREATE_FROM_EXISTING_FLOW.md`

- **TL;DR** gains one bullet: the seed's `## Outcome` becomes the new plan's intent, read from the raw seed before distillation.
- **High-level flow.** Place the `## Outcome` read **above** the distill box in the ASCII diagram — its position relative to distillation is the point, and the reason is visible in the doc's own distill output table (the `"single"` payload is the 8 canonical body keys, and `Outcome` is not one of them). Add the intent-proposal gate on the single-plan path, before the plan is written. Exact box wording is yours; the ordering is not.
- **A short new section** covering the three producers and what each costs:
  - the seed's `## Outcome` → the plan field, deterministic, no round-trip;
  - the step-proposal JSON's `intent` key → each step's field, riding the call `create` already makes, with the one existing repair retry re-used when a proposal omits it (so the call count does not move on the happy path);
  - the proposer, for whatever is still missing after those two — one round-trip, offered as accept / edit / decline, and skipped entirely on non-TTY stdin without `--yes`, so a headless run's recorded call count is unchanged.

  Keep this at flow altitude. The field's shape belongs to `PLAN_FORMAT.md`; link, don't restate.
- **Source map** gains a row for the `## Outcome` read and one for the proposer module, each naming the file and the landed symbol.

### `docs/AUDIT_FLOW.md`

- **In the `completeness` section**, record that a plan or step with no usable intent produces a finding on the blocking-capable self-consistency bucket, rendered under the report's `### Self-consistency` heading, and that **blocking means blocking convergence only** — a completed audit still exits 0 without `--fail-on-findings`. State that the finding is not auto-applied: it stays out of `APPLY_ELIGIBLE_SOURCES`, and its remedy is the gated proposer, not `apply_finding`.
- **In the `reconcile` walk section** (the numbered walk list), record that the `intent-presence` finding **never reaches this walk**: it is not in `APPLY_ELIGIBLE_SOURCES`, and `triage_reason` says so directly (a frontmatter field is not an apply edit). The remedy is a one-line hand edit naming the plan or the step ids the finding lists.
- **In the jira-grade subsection**, one clause: the intent check is frontmatter-only and grade-independent, so it runs and blocks at both grades. That grade withholds the sidecar, and the remedy is the same one-line hand edit — which is consistent with the subsection's existing "next steps name no verb this grade cannot serve" rule.
- **Source map** gains a row for the detector.

### Constraints that are not free to vary

- **Never write that a missing intent fails, errors, or flips an exit code.** The exit-code convention is unchanged. Use "blocks convergence" / "blocking bucket".
- **Never document a check past presence.** No quality claim, no comparison against `## Why` or the plan body or a detail file, no length or shape rule. If a sentence implies one, cut it.
- **Cite symbols by name, never with a line number.** The two flow docs and `PLAN_FORMAT.md` are re-read on every reconcile, and a line-number citation is the highest-churn thing you can put in them.
- **Read the landed names off the modules.** A name this plan or a sibling detail proposed is a proposal; what shipped is the contract.
- **Do not rename `## Smell checks (advisory)`.** Three in-file links depend on its anchor.
- **Keep each fact class in its home doc.** A restatement is a defect here, not redundancy.

## Tests

This is a **non-code** step: `change_type: non-code`, and the plan's `enforce_step_tests: true` does not reach it — the test-authoring gate keys on `change_type` and fires only for `feature` and `refactor` steps. No test file is authored and none is expected. The checks below replace it.

### Verification (non-code step)

1. **Suite unchanged** — `uv run pytest tests/ -q` is green. None of the four files is loaded at runtime; `PLAN_FORMAT.md`'s own banner states the tool does not read it.
2. **Diff shape** — `git status --porcelain` lists exactly the four declared `.md` paths and nothing else.
3. **Every newly cited symbol resolves** — one `rg -n '<symbol>' plan_tool/` per name added to the four docs, each returning at least one production hit. Cover the presence predicate, `check_intent_presence`, `INTENT_PRESENCE_SOURCE`, `SELF_CONSISTENCY_SOURCES`, `render_scope_fence`, `extract_plan_guardrails`, and the proposer entry point step 4 landed.
4. **No line-number anchors** — `rg -n '\.py:[0-9]+' PLAN_FORMAT.md SEED_FORMAT.md docs/CREATE_FROM_EXISTING_FLOW.md docs/AUDIT_FLOW.md` returns nothing.
5. **Anchors still resolve** — `rg -n '#smell-checks-advisory|#body-sections-advisory-checked' PLAN_FORMAT.md` still matches live headings; any heading renamed was first checked with `rg 'plan-level-scope-fence'` across the repo.
6. **Relative links resolve** — every `[...](...)` target added by this step points at a file that exists.
7. **Schema agreement** — the two new frontmatter rows match `plan_tool/schema.py` on name, type, optionality, default, and position relative to `title`.
8. **Elision claim holds** — parse a plan carrying no intent and rewrite it through `parse_plan` / `write_plan`; no `intent:` key appears in the output, matching what the defaults entry claims.
9. **No restatement** — the three non-values (absent, empty, placeholder) are enumerated in `PLAN_FORMAT.md` only; the literal severity token appears in `PLAN_FORMAT.md` only. `rg -l` over the four files returns one file for each.

## Acceptance criteria

- `PLAN_FORMAT.md`'s frontmatter schema block declares `intent` at plan level and inside `steps[]`, each directly after `title`, matching `plan_tool/schema.py` on type, optionality, and default.
- `PLAN_FORMAT.md` carries a field-semantics entry per level, each stating that presence is the entire contract and that the field is checked in `plan_tool/review.py`, never at parse time.
- `PLAN_FORMAT.md`'s defaults table has a `steps[].intent` → `null` row, and its following prose names plan-level `intent` among the optional fields.
- `PLAN_FORMAT.md`'s scope-fence section describes both halves and names `render_scope_fence` as the whole-fence renderer.
- `PLAN_FORMAT.md`'s smell-check section has an intent-presence entry, and its preamble no longer claims every smell is `info` while still stating that none flips the exit code.
- `SEED_FORMAT.md`'s `Outcome` bullet states the deterministic map to the plan's intent and that an absent `## Outcome` falls to the proposer.
- `docs/CREATE_FROM_EXISTING_FLOW.md` shows the `## Outcome` read above the distill box and names all three intent producers.
- `docs/AUDIT_FLOW.md` states that a missing intent blocks convergence while the command still exits 0 without `--fail-on-findings`, and that the walk's apply dispatches the proposer behind a confirm.
- Both flow docs' source maps carry a row for every symbol this step newly cites in them.
- All nine verification checks above pass.

## References

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Dumper behavior behind the "left out of rewritten frontmatter when unset" claim the field-semantics and defaults entries make.
- [Increase output consistency (JSON mode) — Claude Platform Docs](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency) — Background for the flow doc's description of the step-proposal contract and the re-prompt when a proposal omits `intent`.
- [Structured outputs — Claude API Docs](https://docs.claude.com/en/docs/build-with-claude/structured-outputs) — Required-key semantics, for describing `intent` as part of the proposal object rather than an optional extra.

## Applicable guardrails

- **The plan's "## Out of scope", any validation past presence.** No sentence in these four docs may describe or imply a quality judgment, a comparison between the intent and any other prose, a length cap, or a required phrasing. This binds hardest in the field-semantics entries, where "what makes a good intent" is the natural next paragraph to write. Do not write it.
- **The plan's "## Out of scope", required-at-parse-time and migration.** Document the field as optional and the check as an authoring/audit-time concern. No sentence may suggest existing plans need backfilling or that the parser rejects a plan with no intent.
- **The plan's "## Out of scope", delivery past the templates the fence names.** When documenting the fence, point at the plan's list of consuming templates rather than proposing or implying a new one.
- **The plan's "## Architecture", allowed reorganization: none.** These edits are additive prose plus the one preamble correction the new entry requires. No section is moved between docs and no doc gains a new structural convention its family does not have.
- **The plan's "## Architecture", the exit-code convention is unchanged.** Every place these docs describe blocking must scope it to convergence, never to a return code.

## Deferred

- `CLAUDE.md` and `BACKLOG.md` — owned by step 8, which closes out the backlog entry and preserves both reversal records.
- `docs/RUN_FLOW.md` and `docs/DETAIL_FLOW.md` — neither documents the scope fence at all today, so neither is made stale by the intent half, and both are outside this step's declared files. If a reader should be able to find the fence's delivery documented at the run and detail flow altitude, file it in `BACKLOG.md` rather than widening this step.
- `DETAIL_FORMAT.md`'s `## Applicable guardrails` guidance — it describes how a detail references the fence, which this step does not change.
- `DATA_CONTRACT.md` — the intent fields are plan frontmatter, not a persisted runtime schema, so no drift-guarded contract entry is owed.
- The `docs/cli/` generated flag reference — this step adds no flag; nothing to regenerate.
- Clearing a stale intent when a step is rewritten — BACKLOG #212, out of this plan's scope and not documented here.
