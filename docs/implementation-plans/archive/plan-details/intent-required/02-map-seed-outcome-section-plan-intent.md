> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Map the seed's `## Outcome` section to the plan's `intent` in create.py

## Summary

Add a deterministic map in `plan_tool/create.py` from the seed's `## Outcome` H2 to `Plan.intent`, and pass the result into the one `Plan(...)` construction inside `create_plan`. The value is read from the **raw seed**, before the distill first-pass rebinds the seed text — `## Outcome` is not a canonical plan-body section, so distillation drops it. Whether a candidate counts as an intent is decided by step 1's public `plan_tool/review.py:is_usable_intent`, never by a second local check. No Claude call is added. On green, `plan-tool create --from-existing <seed with ## Outcome>` writes an `intent:` line into the new plan's frontmatter that round-trips through `parse_plan`; a seed with no usable Outcome leaves `intent` unset for step 5's proposer.

## Table of Contents

- [Summary](#summary) — what the step does and what is true when it lands.
- [Why](#why) — why the seed's Outcome is the right source and why nothing authors an intent today.
- [Input](#input) — the four contracts this step reads and what it cannot verify about them.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched and the per-file edits.
- [Implementation](#implementation) — where the read happens, the helper's shape, and the two alternatives rejected.
- [Tests](#tests) — the cases this step adds and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checks a reviewer or CI can run.
- [References](#references) — the docs that bear on this step's surfaces.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step's code.
- [Deferred](#deferred) — the sibling seed sources and later steps this one leaves alone.

## Why

`create` cannot author a plan intent today. The field exists (`plan_tool/schema.py`, `Plan.intent`), the fence renders it (`plan_tool/scope_fence.py:render_scope_fence`), and `review.py:check_intent_presence` flags its absence — but no authoring path writes one, so the finding fires on every plan with no fix behind it. The seed already states the why exactly once: `SEED_FORMAT.md` requires `## Outcome` ("one measurable result") as part of the scope contract. Reading that value costs nothing — no round-trip, no prompt change — and it is the one source that cannot drift from the seed, because it *is* the seed. Asking a model for a second sentence at plan altitude would create two prose fields that can disagree, which is the duplication the plan's Architecture rules out.

## Input

This step reads four contracts and changes none of them.

- **`plan_tool/review.py:is_usable_intent`** — step 1 makes this predicate public. Its plain-string signature (`Optional[str] -> bool`) is what this step needs: the candidate line is judged before any `Plan` object exists. Its three non-values are `None`, empty after `.strip()`, and a bare TODO/TBD marker.
- **`plan_tool/scope_fence.py:extract_h2_sections`** — already imported by `create.py`. Returns `{lowered heading: body}`, keeps the **first** occurrence of a duplicate heading, strips the CommonMark closing `##` sequence, and drops sections with an empty body. It does **not** strip YAML frontmatter; the sibling `extract_plan_guardrails` does, and its docstring states why (a `##`-prefixed YAML comment is legal at column 0 and would shadow the real section).
- **`plan_tool/schema.py`, `Plan.intent`** — `Optional[str] = None`. It stays optional; nothing about parse-time behavior changes.
- **The seed's `## Outcome` heading**, required by `SEED_FORMAT.md`'s scope-contract list. That same doc records the fact this step turns on: `Outcome` has **no canonical-H2 counterpart**, so a seed shaped for the canonical plan body omits it unless the author adds it deliberately.

**What this step cannot verify.** Only presence. Nothing here judges whether an `## Outcome` is a *good* intent, compares it against the plan body or `## Why`, or checks its length. A seed whose Outcome is vague still maps; a seed with none maps nothing.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — add `is_usable_intent` to the existing module-level `from plan_tool.review import (...)` block; add one private helper beside `_extract_supplied_guardrails`; capture the mapped value where `create_plan` already resolves `raw_seed` / `supplied_guardrails`; pass `intent=` into the single `Plan(...)` construction in `create_plan`.
  - `tests/test_create.py` — add a test class covering the map, the read-order guard, and the boundary with steps 3 and 5.

## Implementation

**Read the raw seed, not the distilled one — this is the constraint, not a preference.**

- `create_plan` resolves `raw_seed = seed_body if seed_body is not None else from_description` immediately above `supplied_guardrails = _extract_supplied_guardrails(raw_seed)`, in the block introduced by the `# --- Distill first-pass ---` comment. That is *before* the pass rebinds `from_description` and `seed_body` to the cleaned text. Capture the intent on the same raw value, right beside `supplied_guardrails` — same input, same reason (original-seed-only).
- Reading later is wrong because distillation drops the heading. `_render_distilled_markdown` emits only `_BODY_SECTIONS_CANONICAL_KEYS` plus `_OPTIONAL_PLAN_BODY_SECTIONS`, and `Outcome` is in neither set.
- This is the common path, not an edge case: `plan_tool/cli/authoring.py` passes `distill=not --no-distill`, so distillation runs unless the operator opts out. A map placed after `create_plan`'s `body_source` ladder would fire only under `--no-distill` while still passing a unit test that skips the pass.

**The helper.** One module-level private function beside `_extract_supplied_guardrails` — likely `_intent_from_seed_outcome(seed_text: Optional[str]) -> Optional[str]`. Recommended shape:

- Run `extract_h2_sections` over the seed text and take `sections.get("outcome")` (keys are lowercased, so `## Outcome` and `## outcome` both hit).
- Collapse runs of whitespace to single spaces. Real Outcome bodies are wrapped prose — see the multi-line `## Outcome` in `docs/implementation-plans/plan-seeds/impact-recurrence-01-classifier.md`. `scope_fence.py:_render_intent_section` already collapses `\s+` before rendering, so collapsing here makes the stored frontmatter the same string the fence emits rather than merely equivalent to it.
- **Never truncate.** The plan's fence bans a length cap; the collapse changes whitespace only.
- Return the value only when `is_usable_intent` says yes; otherwise return `None`. An `## Outcome` whose body is `_(TODO)_` maps to nothing. Do not write a second emptiness or placeholder test in `create.py` — that duplicate is exactly what step 1 published the predicate to prevent.
- Keep it deterministic: no `invoker=` parameter, no subprocess, no prompt.

**Where the value lands.** `create_plan` builds the plan once — the `Plan(...)` inside the `try:` that converts a `PydanticValidationError` into `CreateError`. Add `intent=` there and nothing else needs threading:

- `parser.write_plan` serializes whatever the model carries, so `intent:` reaches the frontmatter and survives the post-write `parse_plan` reparse.
- The `plan.model_copy(update={"steps": reviewed_steps})` right after the concept review replaces only the named field, so the intent survives it. No second assignment.

**Constraints a developer must respect.**

- **No substitute value when the Outcome is missing.** Do not fall back to the plan title, the seed's first line, or a synthesized sentence. Step 5 owns the no-Outcome path, and a silent stand-in would make the finding step 6 promotes unable to fire on a plan with no stated why — the check would pass on exactly the plans it exists to catch.
- **Plan altitude only.** `Step.intent` belongs to step 3, which adds `intent` to the step-proposal JSON contract. Every step in a plan produced by this step still carries `intent is None`.
- **No new plan-body section.** The Outcome becomes frontmatter, not body prose. Leave `PLAN_BODY_SECTIONS`, `_BODY_SECTIONS_CANONICAL_KEYS`, `_OPTIONAL_PLAN_BODY_SECTIONS`, `_render_plan_body`, and the distill vocabulary alone — widening any of them changes every plan body renderer and the synthesis prompt's key list.
- **Existing plans keep parsing unchanged.** The field stays `Optional`; nothing backfills or sweeps the plans on disk.

**Decide the frontmatter case deliberately.** `create --from-existing` can be pointed at a canonical plan file that carries YAML frontmatter, and `extract_h2_sections` matches headings across the whole text. The leaf's `extract_plan_guardrails` strips a leading frontmatter block first for a stated reason; `_extract_supplied_guardrails` does not. Recommendation: strip the leading block before extracting, so a `##`-prefixed YAML comment can never put a frontmatter blob into `intent:`. `create.py` already imports a private name from that leaf (`_H2_HEADING_RE`) with a recorded reason, so reusing `scope_fence._strip_frontmatter` is the cheapest route inside this step's file list; publishing it is routed to [Deferred](#deferred). If the implementer instead matches `_extract_supplied_guardrails`'s current behavior, say so in the helper's docstring rather than leaving it unstated.

**Alternatives rejected.**

- **Read the Outcome after distillation** (off `body_source`). Rejected: the heading is gone by then, so the map would work only under `--no-distill`.
- **Teach the distill prompt to preserve `## Outcome`.** Rejected twice over: it puts a frontmatter value behind a Claude round-trip the plan's Architecture makes deterministic, and it needs the distill section vocabulary widened — reorganization the plan's fence disallows.

**Shared locations for the same rule.** The foundational logic here is "pull a named H2 out of the seed and decide whether the string counts as an intent." Three other places touch it and none is edited by this step: `review.py:check_intent_presence` already calls the same predicate; `scope_fence.py:_render_intent_section` runs its own whitespace collapse and placeholder check against a mirrored regex (step 1's detail routes that split); and the two tool-generated forward-seed renderers emit no Outcome at all — both are in [Deferred](#deferred).

## Tests

All cases land in `tests/test_create.py`, in a new class alongside `TestCreatePlanFromDescription` and reusing its helpers (`_queue_input`, `_basic_metadata_answers`, a canned-JSON `claude_invoker`).

### Tests for this step

- `test_outcome_section_becomes_plan_intent` — a seed with `## Outcome` produces a plan whose `intent` is that text.
- `test_outcome_is_read_before_distillation` — with distill on and a distill response that returns canonical sections without `## Outcome`, the written plan still carries the intent. The regression guard for the read-order decision.
- `test_wrapped_outcome_collapses_to_one_line` — a multi-line Outcome body maps to a single-line intent with nothing dropped from the end.
- `test_placeholder_outcome_leaves_intent_unset` — an `## Outcome` whose body is `_(TODO)_` maps to `None`, not to the marker.
- `test_seed_without_outcome_leaves_intent_unset` — no heading means `intent is None`; nothing substitutes the title or the seed's first line.
- `test_outcome_heading_matches_case_insensitively` — `## outcome` maps the same as `## Outcome`.
- `test_first_outcome_wins_on_duplicate_heading` — two `## Outcome` headings keep the first, matching `extract_h2_sections`.
- `test_intent_round_trips_through_the_written_plan` — `parse_plan(result.plan_path).intent` equals the mapped value and the raw file contains an `intent:` key.
- `test_frontmatter_comment_does_not_shadow_the_real_outcome` — a source whose leading YAML frontmatter contains a `## Outcome` comment still maps the body's real section. Emit only if the strip recommendation is taken; drop it if the implementer matches `_extract_supplied_guardrails` instead, and say which in the helper's docstring.
- `test_mapping_adds_no_claude_call` — a recording invoker makes the same number of calls for a seed with an `## Outcome` and one without.
- `test_step_intents_stay_unset` — every step in the produced plan has `intent is None`, pinning the boundary with step 3.

**Green-before-done gate:** every case above must be green before this step is finished, along with `uv run pytest tests/test_create.py -q`. The plan sets `enforce_step_tests: true` and this step is `change_type: feature`, so the test-authoring gate applies; the edits to `tests/test_create.py` satisfy it.

## Acceptance criteria

- `create_plan(..., from_description="## Outcome\n\nShip the thing")` writes a plan whose `parse_plan(path).intent == "Ship the thing"`.
- With distill on and a distill response that omits `## Outcome`, the written plan still carries the mapped intent.
- A seed whose `## Outcome` body is `_(TODO)_`, and a seed with no `## Outcome`, both produce `parse_plan(path).intent is None` — and no `intent:` key holding a placeholder value appears in the frontmatter.
- `plan_tool/create.py` imports `is_usable_intent` from `plan_tool.review`; `rg -n 'strip\(\)|TODO|TBD' ` over the new helper shows no second emptiness or placeholder test.
- The mapping helper takes no `invoker` / `claude_invoker` parameter, and the recorded call count is unchanged between a seed with an Outcome and one without.
- Every step of a plan created by this step has `step.intent is None`.
- `git diff --stat` touches only `plan_tool/create.py` and `tests/test_create.py`.
- `uv run pytest tests/test_create.py -q` is green, and the full suite is green.
- Every plan already under `docs/implementation-plans/` still parses — no file is rewritten by this step.

## References

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Loader/dumper reference for the frontmatter round-trip; read it for how a long single-line scalar is emitted and re-read, since the mapped Outcome becomes an `intent:` value in every new plan.
- [Models — Pydantic](https://docs.pydantic.dev/latest/concepts/models/) — Field defaults and `model_copy` semantics, for confirming that the `model_copy(update={"steps": ...})` after the concept review leaves `intent` intact.
- [ATX headings — CommonMark Spec](https://spec.commonmark.org/0.31.2/#atx-headings) — Defines the optional closing `##` sequence that `extract_h2_sections` normalizes, which is why `## Outcome ##` matches the same key.

## Applicable guardrails

- **The plan's "## Plan intent"** — every part of this step serves making the intent field reachable. Here that is the authoring half at plan altitude, nothing further downstream.
- **The plan's "## Step intent"** — carry the seed's stated value forward rather than asking a model for a second one. This is what forbids a synthesized fallback and any Claude call on this path.
- **The plan's "## Out of scope", validation past presence** — the map checks only that a value is there and is not a placeholder. No quality judgment, no length cap, no comparison against any other prose. The plan marks this permanently refused, so a finding proposing one against this step is invalid rather than deferrable.
- **The plan's "## Out of scope", parse-time requirement and migration** — `Plan.intent` stays optional here and no existing plan is touched.
- **The plan's "## Out of scope", propagation through the structural verbs** — this step does not teach any other seed renderer to emit an `## Outcome`.
- **The plan's "## Out of scope", delivery to further consumers** — nothing beyond the plan file is threaded; the templates already rendering the fence pick the value up unchanged.
- **The plan's "Allowed reorganization: none"** — `plan_tool/scope_fence.py` is consumed exactly as shipped, no module moves, and `_extract_supplied_guardrails` / `_render_plan_body` / the distill vocabulary are left alone.

## Deferred

- **Step-level `intent`** — step 3 adds it to the step-proposal JSON and retries a proposal that omits it.
- **The `--from` one-liner, the interactive path, and a seed with no usable `## Outcome`** — step 5 offers a proposed intent on those paths.
- **A canonical source's own frontmatter `intent:`** — `create --from-existing <existing plan>` does not carry it forward here; this step's contract is the seed's `## Outcome`. Route the decision to step 5's fall-through or the backlog.
- **Tool-generated forward seeds carry no `## Outcome`** — `plan_tool/scope_out.py:render_carved_seed` and `plan_tool/reground.py:render_rebaseline_seed` emit `## Provenance` / `## Scope to re-plan` / `## Done-context` and no Outcome, so a plan created from a carve or re-baseline maps no intent and falls to step 5. Adding the heading to either renderer is outside this step's files; route it to reconcile or `BACKLOG.md`.
- **The mirrored placeholder vocabulary in `plan_tool/scope_fence.py`** (`_SECTION_PLACEHOLDER_RE` against `review._BODY_PLACEHOLDER_RE`) — step 1's detail already routes this; this step must not add a third copy, and consolidating the existing two needs a refactor step `detail` cannot mint.
- **Publishing `scope_fence._strip_frontmatter` as a public helper** — `plan_tool/scope_fence.py` is not in this step's file list; the private import is the in-scope route and the tidy-up is a follow-up.
- **Documenting the `## Outcome` → `intent` map** in `SEED_FORMAT.md` and `PLAN_FORMAT.md` — step 7 owns both format docs.
