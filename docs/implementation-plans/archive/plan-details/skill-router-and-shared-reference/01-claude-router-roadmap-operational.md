> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Relocate the Claude router's roadmap operational guidance into DIRECTIVES.md

<!-- plan-tool:detail-format-version: 1 -->

## Summary

`integrations/shared/DIRECTIVES.md` today has no operational content for the `roadmap` verb beyond one mention in "Which model to run a subcommand with." All of the roadmap flag semantics, refusal behavior, and exit-code detail live only in `integrations/claude/SKILL.md`'s decision-tree rows and Subcommands-at-a-glance table rows. This step copies that content into a new `# Roadmap` section in `DIRECTIVES.md` (with `## Roadmap non-stage routes` and `## Roadmap rewrite` subsections) without touching `integrations/claude/SKILL.md` itself — the router's trim to one-line pointers is step 3's job, which depends on this step landing first. It then extends `tests/test_roadmap_format.py`'s four existing guide-sweep dictionaries (`_SOURCE_ADMISSION_GUIDES`/`_SOURCE_ADMISSION_GUIDANCE`/`_SOURCE_ADMISSION_ISOLATION`, `_STRUCTURAL_ROUTE_GUIDES`/`_STRUCTURAL_ROUTE_GUIDE_BOUNDS`, and `_NON_STAGE_BRIEF_DRIFT_GUIDES`) with a new `"integrations/shared/DIRECTIVES.md"` entry in each, plus the two hardcoded expected-guide-name sets that gate them, so the same phrase-level assertions that watch the router today also watch the new copy. On green, `DIRECTIVES.md` is a self-sufficient reference for every roadmap flag the router currently documents, and nothing in the router has moved yet.

## Table of Contents

- [Why](#why) — why the reference has to hold this content before the router can be trimmed
- [Input](#input) — the guide-sweep dictionary shape and the router prose this step reads but does not edit
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step edits
- [Implementation](#implementation) — where the new section goes and which exact phrases the sweep tests require
- [Tests](#tests) — the extended pytest assertions and non-code verification
- [Acceptance criteria](#acceptance-criteria) — observable facts a reviewer can check
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences that bind this step
- [Deferred](#deferred) — work this step explicitly does not do

## Why

Step 3 trims `integrations/claude/SKILL.md`'s roadmap decision-tree rows and Subcommands-at-a-glance rows down to one-line pointers, and the plan's own Risks section says that trimming a router before the reference is complete "loses roadmap guidance that exists only in the Claude router today." `DIRECTIVES.md` is the file every backend (Claude, Codex, and — once step 4 lands — Cursor) actually reads for flag semantics, so the roadmap operational detail has to exist there first. Doing that copy without also widening the guide-sweep tests would leave `DIRECTIVES.md`'s new prose unverified — the existing tests only ever look at `integrations/claude/SKILL.md`, `README.md`, `RUNBOOK.md`, and the other named guides, so a new file needs an explicit new entry in each dictionary to be swept at all.

## Input

This step reads, but does not edit, two existing contracts:

- **`integrations/claude/SKILL.md`'s roadmap prose** — the decision-tree rows "I have a project-sized concept, not a single feature," "rewrite one proved structural roadmap request," "analyze or inspect structural roadmap evidence," and "enroll the immutable roadmap root," plus the Subcommands-at-a-glance rows "**Roadmap** (project-altitude, above the pipeline)," "**Roadmap non-stage routes**," and "**Roadmap rewrite**." This step's job is to carry that substance into `DIRECTIVES.md`, not to redesign it — see the guardrails below.
- **The guide-sweep dictionary shape in `tests/test_roadmap_format.py`.** Four families key a guide name (a display string, usually a repo-relative path) to a `Path` (or a `(Path, extra)` tuple) and a set of expected phrases or boundary anchors, then a sweep test iterates the dict and asserts the phrases/ordering against that file's flattened, lowercased text:
  - `_SOURCE_ADMISSION_GUIDES: dict[str, Path]` + `_SOURCE_ADMISSION_GUIDANCE: dict[str, tuple[str, str, str]]` + `_SOURCE_ADMISSION_ISOLATION: dict[str, str]` — all three dicts must share the same key set (`test_source_admission_guidance_sweep_matches_landed_contract` and `test_source_admission_guidance_keeps_artifact_and_seed_isolation` assert this directly).
  - `_STRUCTURAL_ROUTE_GUIDES: dict[str, Path]` + `_STRUCTURAL_ROUTE_GUIDE_BOUNDS: dict[str, tuple[str, str]]` (start anchor, end anchor) — `test_structural_rewrite_route_guidance_sweep_covers_every_named_public_guide` hardcodes the expected key set as a literal `{...}` and must be extended by hand; it isn't derived from the dict.
  - `_NON_STAGE_BRIEF_DRIFT_GUIDES: dict[str, tuple[Path, tuple[str, ...]]]` (path, subset of `("analysis", "inspection", "structural", "enrollment")`) — `test_non_stage_brief_drift_guidance_sweep_matches_landed_contract` also hardcodes its expected key set as a literal `{...}`. `_NON_STAGE_REBIND_GUIDES` is a dict comprehension derived from it (filters to guides whose routes are a superset of all four) — adding an entry with the full four-route tuple here means `_NON_STAGE_REBIND_GUIDES` picks it up automatically, no separate edit needed.
  - `_STAGE_FEEDBACK_GUIDES` does not reference `integrations/claude/SKILL.md` at all today (confirmed by `grep -n "integrations/claude/SKILL" tests/test_roadmap_format.py`, which returns no hit for this dict) — it needs no change.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `integrations/shared/DIRECTIVES.md` — add a new `# Roadmap` section (with `## Roadmap non-stage routes` and `## Roadmap rewrite` subsections) carrying the content described below.
  - `tests/test_roadmap_format.py` — add a `"integrations/shared/DIRECTIVES.md"` entry to `_SOURCE_ADMISSION_GUIDES`, `_SOURCE_ADMISSION_GUIDANCE`, `_SOURCE_ADMISSION_ISOLATION`, `_STRUCTURAL_ROUTE_GUIDES`, `_STRUCTURAL_ROUTE_GUIDE_BOUNDS`, and `_NON_STAGE_BRIEF_DRIFT_GUIDES`, and extend the two hardcoded expected-set literals in `test_non_stage_brief_drift_guidance_sweep_matches_landed_contract` and `test_structural_rewrite_route_guidance_sweep_covers_every_named_public_guide`.

## Implementation

### Where the new section goes

- Insert a new `---`-delimited `# Roadmap` section in `integrations/shared/DIRECTIVES.md`, positioned between the existing front-matter block (which ends with `## Which model to run a subcommand with`) and `# The two audit gates`. This matches the doc's existing pattern of major rule domains separated by `---`, rather than folding roadmap content into the short front-matter bullet list under `## Subcommands by intent`.
- Give it exactly two `##`-level subsections, in this order, with `## Roadmap rewrite` last: `## Roadmap non-stage routes` and `## Roadmap rewrite`. Nothing may sit between the `## Roadmap rewrite` heading and the following `# The two audit gates` heading — a sweep test bounds the rewrite content by scanning from one heading to the other (see below), so an inserted aside or example block there would silently widen or corrupt that bound.
- Optional, not test-driven: add a one-line pointer to the new section from `## Subcommands by intent`'s existing bullet list, which today has no `roadmap` entry at all (`Discovery`, `Authoring`, `Audit — completeness`, `Audit — reconcile/verify`, `Execution`, `Integration` — confirmed by reading the section). This is a discoverability nicety, not an acceptance criterion.

### What the section carries, relocated from `integrations/claude/SKILL.md`

**Relocate the prose; do not redesign it.** The router's existing sentences already satisfy the analogous sweep-test entries keyed on `integrations/claude/SKILL.md` today, so reusing them (or a close paraphrase that keeps every phrase below intact) is the lowest-risk path — this is explicitly not an invitation to reword the rules while moving them.

- **The section's general body** — mirrors the decision-tree row "I have a project-sized concept, not a single feature" and the Subcommands-at-a-glance row "**Roadmap** (project-altitude, above the pipeline)". Covers: `roadmap <slug> --from-existing <concept.md>`, the four gated artifacts and their write location under `docs/implementation-plans/roadmaps/<slug>/`, `source.json` provenance, re-entry via `--from-stage N` (re-gates everything below `N`, rewrites everything from `N` up), the two non-zero exit codes, `--apply`/`-y` seed promotion, `--refresh-seeds`, `--view {walk,ledger,index}`, and the `pending`-decision-edit vs. `feedback`-row-plus-re-entry distinction. Include the `--confirm-brief-rebind` semantics here (a stage-run-only flag that replaces only the accepted decoded-text baseline without touching artifacts, feedback, or seed state, unneeded for initial/matching-baseline runs) and its closing boundary that it **is not a non-stage recovery route** — that exact clause is what `_SOURCE_ADMISSION_GUIDANCE`'s new entry asserts.
- **`## Roadmap non-stage routes`** — mirrors the decision-tree rows "analyze or inspect structural roadmap evidence" and "enroll the immutable roadmap root," plus the table row "**Roadmap non-stage routes**". Covers `--analyze-escalation`, `--view impact-analyses`, and `--enroll-version`, each refusing `changed-brief`/`legacy-brief` states redacted with status `1` (enrollment) or `0`/log-free with no route or workflow (the `--view` inspection route), gated on "a matching recorded decoded-text baseline." Close it with the same disclaiming sentence the router uses: stage-run-only `--from-existing` plus `--confirm-brief-rebind` baseline acceptance **is not a recovery path** for any non-stage route (a distinct phrase from the general-body clause above — both are separately asserted, see Implementation constraints below).
- **`## Roadmap rewrite`** — mirrors the decision-tree row "rewrite one proved structural roadmap request" and the table row "**Roadmap rewrite**". Covers `--rewrite-structural RECEIPT_FINAL --rewrite-analysis ANALYSIS_FINAL`, admission by current `same-artifact` or `cross-artifact` evidence, and the fixed ordering: an unavailable evaluator rejects fact-free before evidence is read, then after evaluator admission and guarded recovery, structural preflight checks the current brief baseline before rebuilding and validating the exact pair. `changed-brief`/`legacy-brief` refuse redacted with status `1` and no artifact, baseline, or seed publication; every other failure — including a `requires-scope-review` route — also refuses. It publishes only the selected artifact and selected feedback row; cross-artifact evidence grants no transaction, second artifact update, or relation change. Point onward to `ROADMAP_FORMAT.md` for the closed schema, as the router does today.

### Exact-phrase constraints the sweep tests impose

These are not free to vary — each is checked as a literal (case-insensitive, whitespace-collapsed) substring or ordering, so dropping or reordering one fails a specific test. Group them by which dictionary you're adding the `"integrations/shared/DIRECTIVES.md"` entry to:

- **`_SOURCE_ADMISSION_GUIDANCE`** — pick a 3-tuple of phrases (they don't have to be word-for-word what `integrations/claude/SKILL.md`'s own tuple uses, but the ones below are the cheapest match since they're already in the source prose): something asserting `--confirm-brief-rebind` is required to repeat `--from-existing`, something asserting the rebind replaces only the decoded-text baseline, and something asserting it **is not a non-stage recovery route**. Whatever three phrases you pick, they must all appear literally in the rendered `DIRECTIVES.md` text.
- **`_SOURCE_ADMISSION_ISOLATION`** — a single phrase asserting the rebind changes no artifact, feedback, or seed state.
- **`_STRUCTURAL_ROUTE_GUIDES` / `_STRUCTURAL_ROUTE_GUIDE_BOUNDS`** — the bound tuple is `("## roadmap rewrite", "# the two audit gates")` if you use the heading names recommended above (the sweep test lowercases and collapses whitespace before searching, so the literal markdown heading syntax survives as a token). Inside that bounded slice, the test requires, **in this order**: "unavailable evaluator rejects fact-free before evidence is read" → "after evaluator admission" → "structural preflight" → "requires-scope-review"; between "structural preflight" and "requires-scope-review" it needs both "changed-brief" and "legacy-brief" (or the literal phrase "refuses on any failure"); and "same-artifact", "cross-artifact", "selected artifact", and "transaction" must all appear somewhere in the slice.
- **`_NON_STAGE_BRIEF_DRIFT_GUIDES`** — use the full four-route tuple `("analysis", "inspection", "structural", "enrollment")`, matching `integrations/claude/SKILL.md`'s own entry, since the new section documents all four routes. The whole-document text (not bounded) must contain: "matching recorded decoded-text baseline", "changed-brief", "legacy-brief", "--analyze-escalation", "status `1`", "no immutable analysis publication", "--view impact-analyses", "status `0`", "no route or workflow", "structural preflight", "no artifact, baseline, or seed publication", "--enroll-version", and "no immutable version or accepted-head claim". Two of these checks are positional rather than pure membership: the document's **last** occurrence of "--analyze-escalation" must come before its next occurrence of "--view impact-analyses", with "no immutable analysis publication" appearing between them and "status `0`"/"no route or workflow" appearing at or after the "--view impact-analyses" mention — writing the `## Roadmap non-stage routes` content as one paragraph in the order given above satisfies this naturally. The "structural" route's ordering is the same bounded slice as `_STRUCTURAL_ROUTE_GUIDE_BOUNDS` above, reused via that same dict — no separate bound to write.
- **Both hardcoded literal sets** — `test_non_stage_brief_drift_guidance_sweep_matches_landed_contract` and `test_structural_rewrite_route_guidance_sweep_covers_every_named_public_guide` each assert `set(<dict>) == {...}` against a literal set written in the test body. Add `"integrations/shared/DIRECTIVES.md"` to both literals; adding only the dict entries without updating these two literals leaves the sweep tests failing on the set-equality assertion, not silently skipping the new guide.

### What must not change

- `integrations/claude/SKILL.md` is untouched. Its existing entries in all four dictionaries stay exactly as they are — this step must not edit that file (`plan_tool/cli/roadmap_cmd.py`'s docstring and every other existing guide's entry are likewise out of scope).
- `_STAGE_FEEDBACK_GUIDES` is untouched — it never referenced `integrations/claude/SKILL.md`, so there is nothing for this step to relocate into it.
- `tests/cli/test_skill_cmd.py` and `tests/test_model_specs.py` also mention `integrations/claude/SKILL.md` (installer-copy and model-family-doc-coverage checks respectively — confirmed by `grep -rln "integrations/claude/SKILL" tests/`), but neither is a roadmap guide-sweep test; they belong to steps 2 and 4 and are untouched here.
- No new flag, exit code, or refusal behavior — every flag named in the new section (`--from-existing`, `--from-stage`, `--confirm-brief-rebind`, `--apply`, `--view`, `--analyze-escalation`, `--enroll-version`, `--rewrite-structural`, `--rewrite-analysis`) must match what `integrations/claude/SKILL.md` already documents today. This step relocates documentation; it does not touch `plan_tool/cli/roadmap_cmd.py` or any runtime behavior.

## Tests

This step's `change_type` is `non-code`, so `run`'s automatic test-authorship gate (which fires only for `feature`/`refactor` steps) does not apply here — but the step's real verification is not merely descriptive: it's the concrete pytest assertions below, all in `tests/test_roadmap_format.py`, extended (not newly authored) by this step.

- `test_source_admission_guidance_sweep_matches_landed_contract` — now also walks the new `"integrations/shared/DIRECTIVES.md"` triplet, confirming the confirm-brief-rebind, decoded-text-baseline, and non-stage-recovery phrases are present in the rendered doc.
- `test_source_admission_guidance_keeps_artifact_and_seed_isolation` — now also confirms `DIRECTIVES.md` states the rebind changes no artifact, feedback, or seed state.
- `test_structural_rewrite_route_guidance_sweep_covers_every_named_public_guide` — now also walks the `DIRECTIVES.md` `## Roadmap rewrite` bound, confirming same-artifact/cross-artifact evidence, the evaluator-admission-before-preflight-before-scope-review ordering, and the selected-artifact/transaction limits.
- `test_non_stage_brief_drift_guidance_sweep_matches_landed_contract` — now also confirms `DIRECTIVES.md` carries all four non-stage-route terms (analysis/inspection/structural/enrollment) with their status-code and no-publication phrases, and that its hardcoded expected-guide-name literal includes the new entry.
- `test_non_stage_brief_drift_guidance_keeps_analysis_creation_and_view_distinct` — now also confirms `DIRECTIVES.md`'s `--analyze-escalation` mention precedes its `--view impact-analyses` mention, with "no immutable analysis publication" between them.
- `test_non_stage_brief_drift_structural_guidance_preserves_evaluator_first_ordering` — now also walks the same `DIRECTIVES.md` bound as the structural-route test above, confirming the ordering holds there too.
- `test_non_stage_brief_drift_guidance_does_not_offer_stage_rebind_to_non_stage_routes` — now also confirms `DIRECTIVES.md`'s non-stage-routes content states the stage-run rebind "is not a recovery path" for non-stage routes.
- `test_non_stage_brief_drift_guidance_uses_supported_creation_commands` — now also confirms `DIRECTIVES.md` never mentions the retired `--impact-analysis`/`--structural-revision` flag names, and does carry `--analyze-escalation`/`--rewrite-structural`.
- `test_structural_rewrite_route_guidance_sweep_covers_every_named_public_guide`'s and `test_non_stage_brief_drift_guidance_sweep_matches_landed_contract`'s hardcoded expected-set literals — both must include `"integrations/shared/DIRECTIVES.md"` or the set-equality assertion fails outright rather than skipping the new guide.

### Verification (non-code step)

1. Run `uv run pytest tests/test_roadmap_format.py -q` and confirm every test above passes.
2. Confirm the commit's `git diff --stat` touches only `integrations/shared/DIRECTIVES.md` and `tests/test_roadmap_format.py` — `integrations/claude/SKILL.md` stays byte-for-byte unchanged (its trim is step 3's job, which depends on this step).
3. Grep the new `DIRECTIVES.md` content for the retired flag spellings `--impact-analysis` and `--structural-revision` and confirm zero matches.
4. Read the new `# Roadmap` section end-to-end and confirm every flag it names matches a flag `integrations/claude/SKILL.md`'s current text already documents — this step relocates existing semantics, it does not invent or change any.
5. Confirm no other content elsewhere in `DIRECTIVES.md` needed correction as a side effect (e.g., no other section already claimed "DIRECTIVES.md has no roadmap content" in a way this addition would now contradict).

## Acceptance criteria

- `integrations/shared/DIRECTIVES.md` has a `# Roadmap` section with `## Roadmap non-stage routes` and `## Roadmap rewrite` subsections carrying the flag semantics and refusal/exit-code behavior found today only in `integrations/claude/SKILL.md`'s roadmap decision-tree rows and Subcommands-at-a-glance rows.
- `integrations/claude/SKILL.md` is unchanged by this step.
- `_SOURCE_ADMISSION_GUIDES`, `_SOURCE_ADMISSION_GUIDANCE`, and `_SOURCE_ADMISSION_ISOLATION` each carry a new `"integrations/shared/DIRECTIVES.md"` key, and `test_source_admission_guidance_sweep_matches_landed_contract` / `test_source_admission_guidance_keeps_artifact_and_seed_isolation` pass.
- `_STRUCTURAL_ROUTE_GUIDES` and `_STRUCTURAL_ROUTE_GUIDE_BOUNDS` carry a new `"integrations/shared/DIRECTIVES.md"` entry, its hardcoded expected-set literal in `test_structural_rewrite_route_guidance_sweep_covers_every_named_public_guide` includes it, and that test passes.
- `_NON_STAGE_BRIEF_DRIFT_GUIDES` carries a new `"integrations/shared/DIRECTIVES.md"` entry with the full four-route tuple, its hardcoded expected-set literal in `test_non_stage_brief_drift_guidance_sweep_matches_landed_contract` includes it, and that test plus the other four `_NON_STAGE_BRIEF_DRIFT_GUIDES`-driven tests pass.
- `_STAGE_FEEDBACK_GUIDES` is unchanged.
- `uv run pytest tests/test_roadmap_format.py -q` passes in full.
- No occurrence of `--impact-analysis` or `--structural-revision` in the new `DIRECTIVES.md` content.

## Applicable guardrails

- The plan's "## Scope guardrails" first bullet (relocate roadmap guidance into `DIRECTIVES.md`, don't rewrite or re-derive it) binds this step's copy work directly: carry the router's existing roadmap prose across without changing its substance. The bullet's other half — moving router-shaped prose out of the routers — is step 3's, not this step's; this step must not touch `integrations/claude/SKILL.md` at all.
- The plan's "## Scope guardrails" second bullet (no drift check, lint, gate, or exit-code flip) means the new dictionary entries must assert `DIRECTIVES.md`'s own content on its own terms, never diff or cross-check it against `integrations/claude/SKILL.md`'s text — that comparison is exactly the mechanism this bullet forbids.
- The plan's "## Scope guardrails" fourth bullet (no change to backend selection, `backend.json`, or command runtime behavior) means every flag and refusal behavior described in the new section must match what already ships; this step documents, it does not redesign.

## Deferred

- Trimming `integrations/claude/SKILL.md`'s roadmap rows to one-line pointers — step 3, which depends on this step landing first.
- Adding roadmap pointer content to the Codex or Cursor routers — steps 3 and 4.
- A drift guard between `DIRECTIVES.md` and any router — the plan's own top-level `## Deferred` section routes this out permanently; one shared file is the anti-drift mechanism.
- Editing `tests/cli/test_skill_cmd.py`'s or `tests/test_model_specs.py`'s `integrations/claude/SKILL.md` references — neither is a roadmap guide-sweep test; they belong to steps 2 and 4.
- Any change to `plan_tool/cli/roadmap_cmd.py` or its docstring — that guide's dictionary entries are untouched by this step.
