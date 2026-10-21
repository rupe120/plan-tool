# Plan seed: synthesize plan body from `--from-existing` seed via a Claude round-trip

This file is a `plan-tool create` input. Uses the canonical H2 names from `PLAN_BODY_SECTIONS` in `plan_tool/create.py` so the body sections populate cleanly — which is exactly the gap this plan closes.

---

## Overview

`plan-tool create --from-existing` is meant to take an existing seed, conceptualize it via Claude, and develop a plan from it. Today the *step decomposition* and *references* round-trips do that — but the *body sections* (Overview, Problem statement, Architecture, Out of scope, Risks, Testing, Acceptance criteria, Deferred) are populated by a mechanical regex H2-name match, falling back to `_(TODO)_` when names don't line up. This plan adds a third Claude round-trip (`create-body-sections`) that synthesizes each canonical body section from the full seed prose regardless of how the seed is structured. H2-extraction stays as a deterministic fallback so canonical seeds keep working.

## Problem statement

Verified from `plan_tool/create.py:_render_plan_body` (around line 1533): the function iterates `PLAN_BODY_SECTIONS` and does `seed_sections.get(section.lower())` — case-insensitive exact name match against H2s. Seeds with names like `## Goal`, `## Non-goals`, `## Acceptance criteria (plan-level)` silently fall through to `_(TODO)_` even though they contain the right content. A real run against `per-user-agent-cost-tracking.md` produced TODOs in every body section except `## Risks` (which only matched because the seed used that exact name).

The `--iterate` convergence loop cannot recover from this because `apply_finding` does not have the original seed text in its prompt context. The user-stated intent — "the existing would be taken, conceptualized, and the plan developed from it, not that it would need to be well formed" — is implemented for steps and references but skipped for body sections.

## Architecture

**Existing flow (verified):** `create --from-existing` makes two Claude round-trips: `create-initial-steps` (`_INITIAL_STEPS_CHECKPOINT_NAME` at create.py:198) proposes the step graph; `create-references` (line 199) proposes external doc links. Then `_render_plan_body()` at line 1533 builds the body deterministically — no Claude involvement, body sections come from `seed_sections.get(section.lower())` or fall back to literal `_(TODO)_`.

**Proposed flow:** add a third round-trip `create-body-sections` between steps and `_render_plan_body`. Claude reads the full seed prose + `PLAN_BODY_SECTIONS` + the `PLAN_BODY_SECTION_SHAPES` guidance (already declared at create.py:110) and returns `{section_name: body_markdown | null}` covering every canonical section that has content derivable from the seed.

**Precedence at render time:** synthesized (non-null) → H2-extracted (current behavior, preserved) → `_(TODO)_`.

**Empty-section semantics:** when the seed has no risk-shaped content, synthesis returns `null` for `Risks` — not invented risks. Invention looks authoritative but is hallucinatory; a visible TODO flags the gap honestly. The prompt enforces this explicitly.

**One Claude call, not one-per-section:** cross-section context matters (Risks shouldn't restate Architecture; `Out of scope` shouldn't contradict `Deferred`). Single call preserves coherence and costs less than parallel per-section calls.

**Canonical-seed optimization:** if every section in `PLAN_BODY_SECTIONS` (minus `Steps` and `References` which are handled separately) has a matching H2 in the seed with non-empty body, skip the synthesis round-trip entirely. H2-extraction already covers it. Detection: one set intersection against `extract_h2_sections` keys plus an empty-body check.

**Iteration-loop interaction (unchanged):** `--iterate` continues to use `apply_finding` as today. If synthesis returns `null` and the renderer drops a TODO, the next iterate pass's `completeness` primitive flags it and `apply_finding` tries to fill it (still without seed context — that's a separate follow-on).

**Token-cost shape:** synthesis prompt is full seed + 10 section shapes + JSON instructions + 1-2 worked examples. For a 16KB seed that's ~20KB of prompt input, cache-friendly. The existing `_MAX_EXISTING_BYTES = 16384` cap (create.py:192) stays for v1 with a code-comment update naming this plan as motivation.

## Scope of work

1. **Lock design decisions; write the synthesis prompt.** Commit: one-call-not-per-section, `null` for empty sections (no inventing), H2 fallback preserved, canonical-seed detection skips synthesis, cap stays at 16KB. Prompt file `prompts/synthesize-body.md` — inputs: seed prose, section list, section shapes; output: strict JSON `{section_name: body_markdown | null}` with one key per canonical section; 1-2 worked examples included for shape guidance.

2. **Add `propose_body_sections` helper in `create.py`.** Mirrors `propose_initial_steps` and `propose_references` patterns: read checkpoint, call Claude, validate JSON shape, persist checkpoint, return typed dict. Validation: every key in `PLAN_BODY_SECTIONS`, every value `str | None`, no extra keys. On JSON-parse or shape failure: retry once via the same pattern other proposes use, then fall back to all-`null`.

3. **Wire the third round-trip into `create_plan()`.** Add `_BODY_SECTIONS_CHECKPOINT_NAME = "create-body-sections"`. Call `propose_body_sections` between the steps round-trip and `_render_plan_body`. Implement the canonical-seed optimization: if `extract_h2_sections(seed)` keys cover the canonical set (and bodies are non-empty), skip the round-trip and pass `None`.

4. **Update `_render_plan_body` precedence.** Add `synthesized_sections: Optional[dict[str, str | None]]` parameter. New precedence: synthesized (non-null) → H2-extracted → `_(TODO)_`. Preserve `Steps` (always-pointer) and `References` (separate path). Update the fail-loud TODO-body gate at create.py:2077 to count a section as populated if it lands from EITHER synthesis OR H2-extraction.

5. **Add `--no-synthesize-body` CLI flag.** Default off (synthesis on). When set: skip the third round-trip, fall back to H2-extraction-only behavior. The escape hatch for canonical seeds or offline runs. Wire through `plan_tool/cli.py` → `create_plan()`.

6. **Update `_MAX_EXISTING_BYTES` comment.** Cap stays at 16384 for v1; add a code comment cross-referencing this plan and naming the prompt-cache TTL motivation so future readers understand the choice.

7. **Unit tests for `propose_body_sections`.** Happy-path JSON parse + shape validation; null values render TODO downstream; extra-key rejection; malformed JSON triggers single retry; second-failure falls back to all-null without raising; checkpoint resume reproduces the same output. Use the recording-fake `ClaudeInvoker` pattern.

8. **Integration tests end-to-end.** (a) Free-form seed (`## Goal`, `## Non-goals`, `## Acceptance criteria (plan-level)`) produces a plan body populated from synthesis. (b) Canonical seed produces a plan body via H2-extraction with synthesis skipped — byte-identical to a `--no-synthesize-body` run on the same seed (regression guard). (c) `--no-synthesize-body` flag skips the round-trip and falls back to H2-extraction.

9. **Documentation update.** `README.md` "Common workflows" and `RUNBOOK.md` "Workflow: create a plan from an existing seed" describe: (a) seed is now conceptualized via Claude — non-canonical names are fine; (b) `--no-synthesize-body` escape hatch; (c) canonical H2 names still work and skip the synthesis call as an optimization.

10. **Lessons capture.** One-bullet entry in `lessons/general.md` under `create-heuristic`: "seed names no longer have to be canonical; choosing canonical saves one Claude call." Prevents future `create` prompts that inject lessons from misinforming authors.

## Out of scope

- **Reformatting the seed on disk.** Synthesis reads the seed and produces plan body content; seed file is unchanged. `plan-tool reformat` remains the separate path for restructuring sources.
- **Web-search-driven content for body sections.** `## References` has its own round-trip. Synthesis is constrained to seed prose; no external sources.
- **Per-step detail file population.** `plan-tool detail` is the dedicated path. Synthesis touches only top-level plan body sections.
- **Removing the H2-extraction path.** Canonical seeds keep working via the existing extractor. Synthesis is additive.
- **Iteration-loop synthesis.** `--iterate` is not modified to use the new primitive. Threading seed text into `apply_finding` is a plausible follow-on with its own scope-guard and drift-detection questions.
- **Per-section parallel synthesis.** Single-call design is intentional for cross-section coherence.
- **Bumping `_MAX_EXISTING_BYTES` past 16KB.** Separate decision tied to prompt-cache cost analysis.

## Risks

- **Synthesis quality / hallucination.** Claude may produce body content that looks coherent but misrepresents the seed (e.g., invent risks the seed never raised). Mitigations: prompt forbids invention and requires `null` for empty content; iteration loop's `completeness` + `apply_finding` remains a downstream correction surface; integration-test fixtures pin "free-form seed → expected body shape" against SDK version drift. Residual risk: wrong-but-plausible synthesis lands and a hurried author ships it. Docs deliverable must say "read the synthesized body before running `plan-tool detail`."

- **JSON parse / shape failures from Claude.** Synthesis output is structured JSON; occasionally Claude produces invalid JSON or extra keys. Retry-once-then-fall-back-to-null pattern handles this gracefully (failure mode is "plan body has TODOs," not "create fails"). Risk: repeated synthesis failures silently regress the feature. Mitigation: log a structured warning to stderr on retry; record a `runs` log event so `plan-tool runs show` surfaces the regression.

- **Canonical-seed detection false positives.** A seed with all the right H2 names but empty bodies would incorrectly skip synthesis and produce blank sections. Mitigation: detection requires both H2 name presence AND non-empty extracted body (whitespace-stripped). Falsely-canonical seeds trigger synthesis as expected.

- **Backward compatibility with existing canonical seeds.** `lessons-store-restructure.md` and any other canonical seeds in `plan-seeds/` must continue producing the same plan. Mitigation: precedence order means canonical seeds work via either path; integration test in step 8(b) pins this.

- **Iteration loop drift in effective coverage.** Today iterate fills TODOs via `apply_finding`. With synthesis pre-filling most sections, the loop has less to do — but if synthesis lands wrong content, the loop's `completeness` primitive (which checks for TODOs, not synthesis quality) will NOT flag it. Effective coverage shifts. Document in the docs deliverable.

- **Checkpoint resume semantics.** The new `create-body-sections` checkpoint must survive interrupted runs cleanly. The existing checkpoint plumbing handles this, but the new helper must store the JSON output verbatim. Mitigation: round-trip resume test in step 7.

## Testing

Follow the project's unit-first convention. Tests under `.agents/skills/plan-tool/tests/`; existing patterns use Pydantic models for fixtures and recording-fake `ClaudeInvoker`s.

- **Unit: `propose_body_sections` happy path** — recording fake returns valid JSON; helper returns the same dict; checkpoint file is written.
- **Unit: shape validation** — extra keys rejected, non-string non-null values rejected, missing canonical keys default to `null`.
- **Unit: retry + exhaustion** — first call malformed → retry → second succeeds → parsed result returned; both fail → all-null returned without raising.
- **Unit: `_render_plan_body` precedence** — given synthesized + H2-extracted + canonical → synthesized wins; null synthesized → H2-extracted wins; both empty → TODO wins.
- **Unit: canonical-seed detection** — all canonical H2s with non-empty bodies → synthesis skipped (no Claude call); canonical H2 names with empty bodies → synthesis still runs.
- **Integration: free-form seed end-to-end** — fixture with `## Goal`, `## Non-goals`, `## Acceptance criteria (plan-level)`; drive `create_plan()`; assert written plan body has populated canonical sections matching synthesized content.
- **Integration: canonical seed end-to-end** — fixture with canonical H2s; assert synthesis NOT invoked; plan body matches H2-extraction output (regression guard).
- **Integration: `--no-synthesize-body` flag** — same free-form fixture; flag set; assert synthesis skipped and body falls back to H2-extraction.
- **Integration: checkpoint resume** — interrupt after the steps round-trip writes its checkpoint but before body-sections runs; re-invoke; assert resumed run reads the steps checkpoint and only calls Claude for body sections + references.

## Acceptance criteria

- A seed with non-canonical H2 names drives `plan-tool create --from-existing` to produce a plan whose canonical body sections are populated with content synthesized from the seed prose — no `_(TODO)_` for sections that had derivable source content.
- A canonical seed (every `PLAN_BODY_SECTIONS` H2 present and non-empty) drives `create --from-existing` without invoking the synthesis round-trip; the resulting plan body is byte-identical to a run on the same seed with `--no-synthesize-body`.
- `--no-synthesize-body` skips the synthesis round-trip and falls back to H2-extraction-only behavior — regression test pins this against current pre-this-plan output bytes.
- When the seed has no risk-shaped content, synthesis returns `null` for `## Risks` and the plan renders `_(TODO)_` — unit test asserts Claude is not asked to invent.
- A malformed-JSON response from Claude triggers exactly one retry; if both attempts fail, the plan still writes with `_(TODO)_` body sections and exits 0.
- A `runs` log entry records the synthesis-retry event; `plan-tool runs show <slug>` surfaces synthesis quality regressions across runs.
- The `_MAX_EXISTING_BYTES = 16384` site at create.py:192 carries a code comment naming this plan and the prompt-cache TTL motivation.
- Integration tests pass for both fixture shapes (canonical, free-form) and the `--no-synthesize-body` combination, end-to-end through `create_plan()`.

## Deferred

- **Iteration-loop synthesis.** Threading the seed text into `apply_finding` so the iterate loop can re-synthesize sections that landed as TODO from a v1 synthesis miss. Plausible follow-on; introduces scope-guard and drift-detection questions iterate isn't currently shaped for. Revisit if synthesis-miss rate is observably high.
- **Per-section parallel synthesis.** Higher latency/token cost; may improve quality on dense seeds. Defer until single-call coherence problems show up on real data.
- **Synthesis output caching across reruns.** Resumable checkpoints cover the happy path; cross-run caching of "seed hash → synthesized body" is separate. Defer until rerun frequency justifies it.
- **Bumping `_MAX_EXISTING_BYTES` past 16KB.** Worth flagging — larger seeds get more value from synthesis. Future change with explicit prompt-cache cost analysis can raise it.
- **Synonym mapping for non-canonical H2 names** (`Goal → Overview`, `Non-goals → Out of scope`) as a deterministic alternative to synthesis. Cheap and Claude-call-free but brittle. Synthesis subsumes this; the synonym map only matters if synthesis is unavailable (`--no-synthesize-body` path) — defer unless requested.
