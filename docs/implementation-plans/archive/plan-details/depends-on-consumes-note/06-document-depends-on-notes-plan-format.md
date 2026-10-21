> **Auto-archived**: this plan was swept on 2026-08-10 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Document `depends_on_notes` in PLAN_FORMAT.md and mark BACKLOG #253 shipped

## Summary

This step documents the shipped `depends_on_notes` field in `PLAN_FORMAT.md` — the human-facing contract for plan frontmatter — and removes BACKLOG #253 now that the feature is complete. The doc addition follows the existing `depends_on` / `intent` pattern: a schema-block entry, a field-semantics section naming the enforcing code symbols, a defaults-table row, a parse-time validation rule, and (likely) a short mutation table mirroring the plan Architecture fan-out/fan-in table. The key design choice is **structural-membership documentation**: the doc states what is checked (every note key is in `depends_on`) and explicitly fences what is never checked (whether an edge carries a note; note wording, plausibility, completeness). No production code changes. On green, a reader can learn the field contract from `PLAN_FORMAT.md` alone, and BACKLOG #253 is gone with dependent entries updated.

## Table of Contents

- [Summary](#summary) — what ships, where, and the green outcome
- [Why](#why) — the gap after steps 1–5
- [Input](#input) — landed contracts this step documents
- [Files (creates vs edits)](#files-creates-vs-edits) — footprint per file
- [Implementation](#implementation) — doc shape, backlog close-out, and boundaries
- [Tests](#tests) — exemption note and substitute verification
- [Verification (non-code step)](#verification-non-code-step) — reviewer-runnable checks
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — docs worth reading for this step
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — explicitly not this step

## Why

Steps 1–5 land the schema field, transform threading, create authoring, interactive review display, and the withdrawn-#172 proof fixture — but `PLAN_FORMAT.md` still describes `depends_on` as a bare id list with no place for per-edge consumption notes. That leaves the durable contract only in code and plan prose, which is exactly the gap BACKLOG #253 opened. This step closes the loop in the one doc operators and agents are directed to for frontmatter shape, and removes the backlog entry per `BACKLOG.md`'s own rule: forward-looking entries delete on ship.

## Input

- **Landed names win.** Open `plan_tool/schema.py` at HEAD when authoring — field name, type, default, and validator symbol must match what step 1 shipped, not whatever this plan's earlier detail files proposed. On disagreement, the module wins.
- **Step 1 outcome** — `plan_tool/schema.py:Step` carries `depends_on_notes: dict[int, str]` (default `{}`) with a step-level `@model_validator(mode="after")` rejecting any key not in that step's `depends_on`. Note content is never validated; partial edge coverage and empty string values parse; `{}` drops on rewrite via `plan_tool/parser.py:write_plan`'s `exclude_defaults` path.
- **Step 2 outcome** — split, merge, and scope-out narrow remap note keys through the same old-id→new-id map as `depends_on`; carved-seed upstream rendering threads notes through `plan_tool/scope_out.py:_resolve_upstream_context` / `_upstream_block`. Fan-out/fan-in rules live in the plan Architecture table — document them, do not re-derive.
- **Steps 3–4 outcome** — `plan_tool/create.py` collects notes in proposal and manual wizard paths and displays them read-only in interactive review. Silence stays valid everywhere.
- **Step 5 outcome** — `tests/fixtures/withdrawn_audit_trajectory_depends_on_notes.md` is the worked example for pointer-style notes on bridging edges; cite it as a fixture path, not as something this step creates.
- **Purity-cache exclusion** — `plan_tool/fingerprint.py:compute_purity_cache_key` deliberately excludes `depends_on_notes` (same class as `title`/`complexity`); step 1's test pins this.
- **No automated PLAN_FORMAT drift guard** — unlike `DATA_CONTRACT.md`'s registry-driven checks, this doc is verified by hand in this step's verification list.
- **`PLAN_FORMAT.md` family shape** — the source-of-truth banner is present; there is no `## See also` tail (that exists only in `DETAIL_FORMAT.md` and `JIRA_FORMAT.md`). Match the sibling's fenced ```yaml schema block, field-semantics prose, defaults table, and validation-rules list — do not copy elements from siblings that `PLAN_FORMAT.md` lacks.

## Files (creates vs edits)

- **New files:** none

- **Existing files (edits only):**
  - **`PLAN_FORMAT.md`** — add `depends_on_notes` to the frontmatter schema block (immediately after `depends_on`); add a **`steps[].depends_on_notes`** field-semantics section after **`steps[].depends_on`**; add a mutation subsection (table form, parallel to the existing intent-under-mutation table); add a defaults-table row; add a parse-time validation rule; optionally extend the worked example with a note on one edge. Every enforcing symbol cited must exist at HEAD.
  - **`BACKLOG.md`** — delete the **`#253 — Require a depends_on edge to say what it consumes`** entry; sweep inbound references to `#253` in the same file and update them to reflect shipped state (notably **`#252`**, **`#257`**, **`#258`**, **`#259`**, and any "Stop / defer: #253's schema work" lines); record the landing commit hash in the plan's own status note or in the removal's surrounding context per the plan acceptance criterion.

## Implementation

### Design stance

- **Document the binary observable, not a quality bar.** The field answers "did anyone name what this edge delivers?" — same framing as the plan intent. The doc must state plainly that note text is **never** graded, scored, or gated on at parse time or anywhere else in the pipeline.
- **Rejected alternative:** restating the full fan-out/fan-in table from the plan body inside `PLAN_FORMAT.md`'s Architecture — out of scope; a compact mutation table keyed to real symbols (like the existing `intent` table) is enough, with the plan as depth reference.
- **Rejected alternative:** requiring a note on every `depends_on` edge in the doc — contradicts the plan fence; silence on an edge stays valid and must be documented as such.

### `PLAN_FORMAT.md` — schema block

- Add **`depends_on_notes`** immediately after **`depends_on`** in the fenced ```yaml schema under `## Frontmatter schema`.
- **Shape to document:** optional mapping from antecedent step id (integer key) to short string value; default empty; left out of rewritten frontmatter when empty (same elision story as other empty collections).
- Use inline `# required` / `# default` comments consistent with neighboring fields — one way:

```yaml
    depends_on_notes: # optional. int → str; each key must be in depends_on. default {}.
      <antecedent_step_id>: string
```

### `PLAN_FORMAT.md` — field semantics (`steps[].depends_on_notes`)

Place this section **immediately after** the existing **`steps[].depends_on`** section. Cover at minimum:

- **Purpose** — optional per-edge note naming what the dependent step consumes from the antecedent (a lookup pointer, not a claim the tool scores).
- **Relationship to `depends_on`** — sibling field; does not replace, reorder, or reinterpret `depends_on`. Keys are antecedent ids; values are free-form strings.
- **Parse-time contract (structural only)** — every key must appear in that same step's `depends_on` list; enforced by the `Step`-level validator in `plan_tool/schema.py` (name the landed symbol). **`Plan._validate_graph`** does not inspect notes — say so explicitly so readers do not expect id-existence checking twice.
- **Content is never checked** — wording, length, plausibility, truth, and placeholder text all parse. No requirement to annotate every edge; partial coverage is valid.
- **Not checked at parse time** — note presence, completeness across edges, and semantic correctness (bullets mirroring step 1's deliberate non-checks).
- **Serialization** — empty `{}` omitted on rewrite via `plan_tool/parser.py:write_plan` / `render_plan_text` and `exclude_defaults=True`; cite that path.
- **Purity cache** — excluded from `plan_tool/fingerprint.py:compute_purity_cache_key` (metadata about rationale, not a verdict input).
- **Authoring surfaces** — one short paragraph: `plan-tool create`'s Claude proposal and manual wizard may populate notes; interactive review displays them read-only (steps 3–4). **`plan_tool/canonical.py:extract_canonical_steps`**, **`plan_tool/foundational_logic.py:merge_sweep_into_steps`**, and **`plan_tool/reground.py:render_rebaseline_seed`** stay note-less by design — name all three so readers do not expect backfill.
- **Distinction from `SoftEdge`** — one sentence: `plan_tool/completeness_report.py`'s soft-edge heuristic scans detail prose for ordering-only markers; it is separate, reporting-only, and does not read `depends_on_notes` (BACKLOG #238 territory). Do not imply overlap or replacement.

### `PLAN_FORMAT.md` — mutation table

Add a subsection **`depends_on_notes` under structural edits** (or fold into the existing intent mutation area if a separate heading reads cleaner — grep `#intent-under-structural-edits` inbound links before renaming). Mirror the plan Architecture table in table form:

| Verb / surface | Rule | Enforced by |
|---|---|---|
| split | never copy a note onto the surviving repointed edge; always set `depends_on_notes={}` on both replacement halves; forbid the field in `_propose_step_split` | `plan_tool/create.py:_apply_step_split`, `_propose_step_split` |
| merge (outbound) | keep note only when every merging member that depended on that antecedent had identical text; members without that edge are out of the vote; else clear | `plan_tool/create.py:_apply_step_merge` |
| merge (inbound collapse) | same identical-text rule when external dependents collapse multiple edges onto one survivor | `plan_tool/create.py:_apply_step_merge` |
| scope-out narrow | remap note keys through the same old-id→new-id map as `depends_on` | `plan_tool/scope_out.py:compute_narrow` |
| carved-seed upstream | render each upstream prerequisite's note when present (done and external sections); when several carved steps share one dep, first-seen carved step wins for title and note | `plan_tool/scope_out.py:_resolve_upstream_context`, `_upstream_block` |

State the governing rule in one line: **prefer absent over a quietly false carry-over** (same spirit as the intent mutation prose).

**Explicit exclusions** (one line each): carved region's internal graph (re-synthesized); **canonical extraction** (`extract_canonical_steps` / `extract_steps_from_canonical` — note-less by construction); foundational-logic consolidation steps (`merge_sweep_into_steps`); `reground` rebaseline seeds (no `depends_on` edges rendered today).

### `PLAN_FORMAT.md` — defaults, validation, example

- **Defaults table** — add `steps[].depends_on_notes` → `{}` (elided on rewrite when empty).
- **Validation rules** — add an numbered item: a note key not in the step's `depends_on` is rejected (structural error, same class as unknown id in `depends_on`).
- **Example block** (recommended, not mandatory if it overcrowds) — add a `depends_on_notes` entry on one step in the existing `## Example` frontmatter, e.g. step 2 depending on step 1 with `depends_on_notes: {1: "consumes the schema types from step 1"}`. Keep the example minimal.

### Traceability checks to satisfy while editing

- **Forward:** every rule the doc states names the code symbol that enforces or implements it.
- **Reverse:** every public behavior step 1–5 added for `depends_on_notes` that belongs in a format reference appears in the doc — at minimum the field, the key-in-`depends_on` validator, elision, purity exclusion, and the mutation rows above. Authoring/display behavior can be one summarized paragraph rather than duplicating `docs/CREATE_FROM_EXISTING_FLOW.md`.
- **No line-number anchors** in the doc body.

### `BACKLOG.md` — close out #253

- **Delete** the full `#253` entry (lines under `**#253 — Require a depends_on edge to say what it consumes**`).
- **Do not** move it to `docs/HISTORICAL_BACKLOG_DECISIONS.md` — shipped features leave via git log and the implementation plan; the plan acceptance criterion asks for a commit citation, not a historical stub.
- **Sweep `#253` references** in the same file. At HEAD these include at least:
  - **`#252`** — update "composes with **#253**" and remove "Stop / defer: #253's schema work" now that the schema work shipped.
  - **`#257`**, **`#258`**, **`#259`** — change "requires BACKLOG #253 shipped first" to "builds on shipped `depends_on_notes`" (or drop the dependency line if redundant once #253 is gone).
  - Any other "BACKLOG #253" prose that reads as pending work.
- **Landing commit** — when marking shipped, cite the commit that landed steps 1–6 (or the merge commit for the plan) in the plan file's status/handoff; the backlog removal itself needs no tombstone paragraph.

### Boundaries

- **No `DATA_CONTRACT.md` edit** — plan frontmatter is outside that doc's scope (`PLAN_FORMAT.md` owns it); do not add a registry row.
- **No example-driven test file** — `change_type: non-code`; verification is the numbered checklist below.
- **Do not** add `## See also` to `PLAN_FORMAT.md` — not part of this doc's family shape.

## Tests

This step is **`change_type: non-code`** in a plan with **`enforce_step_tests: true`**. The test-authoring gate keys on `feature`/`refactor` only — it does **not** apply here. Verification is the explicit checklist in the next section, not a new pytest module.

## Verification (non-code step)

Run these before marking the step done:

1. **Schema block** — `rg 'depends_on_notes' PLAN_FORMAT.md` shows the field in the ```yaml schema block immediately after `depends_on`.
2. **Semantics section** — a `**steps[].depends_on_notes**` heading exists with the structural key-membership fence (and explicit "note-on-edge presence never required; content never checked") statement.
3. **Symbol existence** — every `plan_tool/...` symbol cited in the new prose exists at HEAD (`rg` or import check per symbol).
4. **Validator name match** — the cited `Step` validator name matches `plan_tool/schema.py` exactly.
5. **Validation rule** — `## Validation rules` includes key-not-in-`depends_on` rejection.
6. **Defaults row** — the defaults table lists `steps[].depends_on_notes`.
7. **Example parse** — if the worked example includes `depends_on_notes`, run `uv run python -c "from plan_tool.parser import parse_plan; parse_plan(open('PLAN_FORMAT.md').read())"` **only on extracted example YAML**, or copy the example frontmatter to a temp file and parse it — the full doc is not a plan file. Prefer extracting the example block into a scratch plan under `.tmp/` and parsing that.
8. **Example round-trip** — parse the scratch example → `write_plan` → re-parse; `depends_on_notes` survives and empty notes stay elided.
9. **No line-number citations** — `rg -n 'PLAN_FORMAT.md:[0-9]' PLAN_FORMAT.md` returns nothing (primary anchors are symbols, not lines).
10. **Heading anchors** — if any new heading text duplicates an existing slug, grep inbound `#`-links; rename if needed.
11. **Backlog removal** — `rg '#253' BACKLOG.md` returns no standalone pending-work entry (origin/history mentions inside other entries may remain if rewritten to past tense).
12. **Cross-ref sweep** — no `BACKLOG #253` or "requires #253 shipped" reads as blocking future work.
13. **Fence restatement** — new prose contains no language implying notes are required on all edges, graded, or gated.
14. **Clean tree** — only `PLAN_FORMAT.md` and `BACKLOG.md` changed for this step's commit scope.

## Acceptance criteria

- `PLAN_FORMAT.md` documents `steps[].depends_on_notes` with type, default, elision behavior, parse-time key-in-`depends_on` rule, and an explicit never-graded content fence.
- The doc names `plan_tool/schema.py:Step` and the landed step-level validator as the structural enforcer; it states `Plan._validate_graph` does not inspect notes.
- The mutation table lists split, merge, scope-out narrow, and carved-seed upstream rules with real module symbols from steps 2–5.
- The defaults table and validation-rules list include the new field.
- BACKLOG `#253` entry is removed from `BACKLOG.md`.
- Inbound `#253` references in `BACKLOG.md` no longer read as pending work.
- The plan's acceptance criterion is met: BACKLOG #253 marked shipped with a cited landing commit recorded in the plan handoff or commit message.
- All verification checklist items above pass.

## References

- [Pydantic v2 — Fields](https://docs.pydantic.dev/latest/concepts/fields/) — optional `dict` fields, `default_factory=dict`, and default elision semantics the doc should describe accurately.
- [Pydantic v2 — Validators](https://docs.pydantic.dev/latest/concepts/validators/) — documents `@model_validator(mode="after")`, the mechanism behind the key-in-`depends_on` rule.
- [Pydantic v2 — Serialization](https://docs.pydantic.dev/latest/concepts/serialization/) — `exclude_defaults` behavior referenced for empty-map elision.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — int-key mapping in YAML frontmatter the example must demonstrate correctly.
- [YAML 1.2.2 Specification](https://yaml.org/spec/1.2.2/) — mapping-key rules for bare integer keys in the schema example.

## Applicable guardrails

- **Plan fence (structural key membership only)** — this step documents that fence; the doc must not describe content grading, scoring, note-on-edge requirements, or completeness requirements for notes.
- **Plan "## Out of scope", existing plans** — document that omission stays valid forever; do not instruct backfill of corpus plans.
- **Plan "## Out of scope", gates and grading** — no doc language suggesting future gates on note presence or wording; the trap prose from BACKLOG #253 belongs as a one-line warning, not a spec for checks.
- **Plan "## Out of scope", `depends_on` semantics** — document `depends_on_notes` as a sibling; do not change how `depends_on` ordering, cycles, or self-reference are described.

## Deferred

- **`DATA_CONTRACT.md`** — deliberately out of scope for this plan (runtime sidecars only); no follow-up row.
- **`CLAUDE.md` reference-docs sweep** — if the field warrants a bullet in the injected reference list, that is a separate hygiene edit; not required to close #253.
- **`JIRA_FORMAT.md` / `DETAIL_FORMAT.md` note rendering** — BACKLOG #258 and #259; display-only consumers documented in their own entries.
- **Threading notes into `#252` cohesion grounding (`_render_dependency_cohesion_block`)** — BACKLOG #257.
- **`SoftEdge` / detail-prose heuristic integration** — BACKLOG #238; explicitly separate from `depends_on_notes` in the doc, not merged here.
- **Automated PLAN_FORMAT ↔ code drift guard** — no shipped checker at HEAD; hand verification remains the contract for this doc family.
