> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add the jira-grade schema authority module: required H2s, read-time validator, plain-English gate, and collision-safe artifact paths

## Summary

Create `plan_tool/jira_grade.py` as the single authority for the jira-grade detail contract: the five required H2 sections (`Intent`, `Change`, `Constraints`, `Done when`, `Out of scope`), a deterministic validator that accepts a conforming body and loudly rejects a run-grade body stored at a jira-grade path, and a deterministic plain-English gate for the prose between the anchors. Alongside it, extend step 1's `plan_tool/detail_artifacts.py` leaf with jira-grade artifact path derivation that cannot collide with any run-grade file or with the run-grade orphan sweep. The key design decision: jira-grade artifacts live in a `jira/` subdirectory of the plan's detail directory — a same-directory `.jira.md` suffix is rejected because `plan_tool/detail.py:_archive_orphan_details` globs `{NN}-*.md` and would archive the jira artifact every time the run-grade file for the same step is re-authored. On green, both modules import cleanly from anywhere, ~16 new tests pass in `tests/test_jira_grade.py`, and no existing command behaves differently — nothing consumes the new module yet.

## Table of Contents

- [Summary](#summary) — what the step ships and the one path decision
- [Why](#why) — why the contract needs one durable authority before any consumer exists
- [Input](#input) — the step 1 leaf contract and run-grade conventions this step builds on
- [Files (creates vs edits)](#files-creates-vs-edits) — new module + tests, and the one leaf edit
- [Implementation](#implementation) — tokens, validator, prose gate, path routing, and the constraints on each
- [Tests](#tests) — contract, rejection, prose-gate, collision, and import-safety cases
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the specs the H2 contract and tests lean on
- [Deferred](#deferred) — consumer wiring and lifecycle gaps owned elsewhere

## Why

The plan's `artifact-ambiguity` blocker (HIGH, recurring across three audit snapshots) came from consumers validating only path existence: a run-grade body at a jira-grade path would be read and executed under the jira-grade prompt with nothing red. The fix the plan commits to is contract validation on read — and that needs one module that owns the contract, because steps 4 (detail authoring mode), 5 (`jira` export), 6 (run renderer), and 9 (the audit's jira bundle check) all validate the same five H2s. Declared once here, they import it; declared per-consumer, the copies drift. This step is also where the user-confirmed authority decision lands in code: this module — not BACKLOG #149's compact run-grade schema — is the single compact-schema authority, and step 10 later re-scopes #149 to alias these tokens. Nothing else in the codebase changes: with no consumer wired, every existing command's behavior is unchanged, which keeps this step small and independently green.

## Input

- **Step 1's leaf** (plan_tool/detail_artifacts.py — **step 1 is `done` and the module is merged; verify signatures against it**): it ships the shared path leaf — `derive_detail_path` (convention `<plan_dir>/plan-details/<plan_slug>/<NN>-<step_slug>.md`), `derive_step_slug`, `_plan_slug`, `find_unreferenced_detail_for_step`, and the state-carrying run-grade resolver (`DetailArtifactResolution` / `resolve_detail_artifact`) — with a pinned import discipline: module-level imports limited to stdlib, `plan_tool.schema`, and `plan_tool.locator`, enforced by a fresh-interpreter test. This step's path additions go into that leaf and must keep that discipline; step 1's characterization suite (tests/test_detail_artifacts.py, merged) must pass unmodified.
- **Run-grade H2 matching convention** (`plan_tool/detail.py`): `_H2_HEADING_RE` matches an H2 line and captures the first word, lowercased; `_REQUIRED_H2_TOKENS` checks membership on that first token, so `## Files (creates vs edits)` satisfies `files`. The jira-grade matcher mirrors this convention so the two contracts read alike — but does not import or touch `plan_tool/detail.py`.
- **Run-grade lifecycle behaviors the paths must dodge** (all in `plan_tool/detail.py`): `_archive_orphan_details` sweeps `{step_id:02d}-*.md` siblings of a just-written run-grade file into `archive/`; `find_unreferenced_detail_for_step` adopts only the exact canonical run-grade name; `_migrate_downstream_details_after_split` renames only files reachable through `Step.detail` pointers. Jira-grade artifacts must be invisible to all three.
- **Plain-English rubric** (BACKLOG #167, applied at birth per the plan's Architecture): descriptions are short, direct, said once; code anchors, paths, symbols, examples, and stated constraints are immutable facts the gate never counts against the prose.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/jira_grade.py` — the schema authority: required-H2 names and matcher tokens, the body validator, the plain-English gate, and the contract error type.
  - `tests/test_jira_grade.py` — contract, rejection, prose-gate, path-collision, and import-safety tests (the path tests live here even though the path functions land in `detail_artifacts.py`, since `tests/test_detail_artifacts.py` is step 1's file and must stay unmodified).

- **Existing files (edits only):**
  - `plan_tool/detail_artifacts.py` — add jira-grade path derivation (e.g. `derive_jira_detail_path`) and, if useful to consumers, a small existence-carrying resolve helper; no change to any run-grade function or to the leaf's import discipline.

## Implementation

**What must be true when done:** one module declares the jira-grade contract; a deterministic function validates any body string against it and rejects the wrong schema loudly; a deterministic prose gate flags filler and buried outcomes without ever flagging a code anchor; and a jira-grade artifact path exists for every step that no run-grade code path can adopt, archive, or overwrite. No Claude call anywhere in this step — both modules are pure leaves with no `invoker=` seam.

- **The token authority.** Declare the five required sections once, in display order: `Intent`, `Change`, `Constraints`, `Done when`, `Out of scope` (one way: a `JIRA_GRADE_REQUIRED_H2S` tuple of display names plus a derived first-token set — `intent`, `change`, `constraints`, `done`, `out` — mirroring `detail.py:_REQUIRED_H2_TOKENS`'s first-token, case-insensitive, trailing-words-allowed convention, so `## Done when` and `## Done when (acceptance)` both match). These names are the durable authority the plan's schema decision names; steps 4–9 import them and never re-declare them. **Mint the grade axis values here too** — the `run` / `jira` tokens themselves (one way: a `GRADE_RUN` / `GRADE_JIRA` pair plus a `JIRA_GRADE_VALUES` tuple for argparse `choices=`). Four later steps each add a grade flag (`jira --grade`, `run --detail-grade`, `completeness-audit --grade`, `detail --grade`) and every one of them must read the spelling from here rather than from a sibling: this step runs before all four, so it is the only common ancestor that has landed at each of their turns. A consumer that pins its flag to another consumer's flag is asserting a step that has not shipped. Do not import from or edit `plan_tool/detail.py` — the run-grade tokens stay where they are, and consolidating the two matchers is a refactor this step must not fold in (see Deferred).

- **The read-time validator.** A pure function — likely `validate_jira_grade_body(text) -> list[<finding>]` with a frozen finding dataclass (`kind`, `blocking`, `message`) — that checks, in one pass:
  - all five required H2s present (each missing one is its own blocking finding, named by display name);
  - each required section has a non-empty body;
  - no unknown H2s. This strictness is a deliberate decision, not a default: the compact schema is "the smallest shared schema", and rejecting extra H2s is what makes a hybrid or wrong-schema body fail structurally instead of passing on a five-heading subset. H3s inside sections are free.
  - **wrong-schema detection with a targeted message:** when the body carries run-grade tokens (`summary`, `implementation`, `acceptance`, …) instead, say so plainly — "run-grade body at a jira-grade path" beats five "missing section" lines. Per the captured lesson, rejecting a *complete, valid* body from the other schema is a first-class requirement, not a nice error message.

  Also provide the loud-failure form consumers need — e.g. a `JiraGradeContractError` and a helper that reads a path, validates, and raises on any blocking finding. Steps 5 and 6 wire it; this step only ships it.

- **The plain-English gate.** A second pure function (e.g. `check_plain_english(text)`) returning the same finding shape. Constraints that are not free to vary:
  - **Deterministic only.** No Claude judgment in this leaf; #167's model-reviewed clarity half stays out (Deferred).
  - **Anchors are exempt.** Strip fenced code blocks, backtick spans, links, and path/identifier-shaped tokens (the `create.py:_looks_like_code` shape is the precedent) before measuring anything. A long backticked symbol must never trip a sentence-length or jargon check.
  - **Two finding classes.** Blocking findings are the high-precision mechanical signals — a filler-phrase denylist ("it is worth noting", "in order to", "it should be noted", "this means that", …) and sentences past a hard word cap (recommend ~35 words after anchor-stripping; pick one number and constant-ize it). Softer signals (long sections, dense clause stacking heuristics) stay advisory. This resolves the tension between the plan's "gates reject padding" and #167's "keep heuristic signals advisory": the model-facing response gate (step 4) treats blocking findings as reject-and-retry, while nothing at read time judges style — read-time consumption validates the H2 contract only, so an operator's hand-edited artifact can't start failing `jira` export over prose taste.
  - The gate reports; it never rewrites. No finding mutates or truncates text.

- **Collision-safe paths (the `detail_artifacts.py` edit).** Add `derive_jira_detail_path(plan_path, plan, step)` returning `<plan_dir>/plan-details/<plan_slug>/jira/<NN>-<step_slug>.md`, built from the same `_plan_slug` / `derive_step_slug` helpers already in the leaf. The subdirectory is the decision, and the rejected alternative matters: a same-directory suffix (`<NN>-<step_slug>.jira.md`) matches `_archive_orphan_details`' non-recursive `{NN}-*.md` glob, so every run-grade re-author of the same step would archive the jira artifact as an orphan. The `jira/` subdirectory is structurally outside that glob, outside `find_unreferenced_detail_for_step`'s exact-canonical-name adoption, outside split migration (which walks `Step.detail` pointers), and can never equal a run-grade path. It also can't collide with the existing `archive/` sibling directory. There is no pointer axis for jira-grade — `Step.detail` stays run-grade-only per the plan, and no new frontmatter field is added — so resolution is canonical-derivation plus at most an `is_file()` check; hard-failure-on-missing semantics belong to the consumers (step 5/6), not the leaf.

- **Keep both modules leaves.** `plan_tool/jira_grade.py` should be stdlib-only (the validator takes strings and paths; it needs no first-party import — `backend.py` and `telemetry.py` are the precedent). `detail_artifacts.py` keeps step 1's pinned import set. Pin both with fresh-interpreter import tests, not by reading the import block.

- **Foundational logic and its other homes.** The rule this step adds is "required-H2 presence validation over a markdown body." It already exists twice: `detail.py`'s run-grade gate (`_REQUIRED_H2_TOKENS` / `_H2_HEADING_RE` / the stub-synthesis path) and `create.py:extract_h2_sections` / `detail.py:parse_detail_file_sections` for section splitting. This step deliberately mirrors the convention without consolidating — a shared H2-matching helper is a refactor across three modules that this feature step must not carry; route it to reconcile (see Deferred).

## Tests

All in `tests/test_jira_grade.py` (new). Existing suites — `tests/test_detail_artifacts.py`, `tests/test_detail.py`, `tests/test_review.py` — are part of the gate and must pass unmodified.

Contract and validator:

- `test_required_h2_names_and_order` — the authority tuple is exactly (`Intent`, `Change`, `Constraints`, `Done when`, `Out of scope`), in that order.
- `test_validate_accepts_minimal_conforming_body` — a five-section body with plain prose returns no blocking findings.
- `test_validate_accepts_heading_variants` — case-insensitive and trailing-words H2 forms match (`## done when`, `## Out of scope (v1)`).
- `test_validate_flags_each_missing_section` — dropping any one required H2 yields a blocking finding naming it (parametrized over the five).
- `test_validate_flags_empty_section_body` — a present heading with a blank body is blocking.
- `test_validate_rejects_unknown_h2` — a valid body plus `## Implementation` is blocking; H3s inside sections are not.
- `test_validate_rejects_complete_run_grade_body` — a full, valid run-grade body (all seven run-grade H2s) fails with the wrong-schema finding, not just five missing-section lines.
- `test_contract_error_raised_on_load` — the load-and-validate helper raises `JiraGradeContractError` (or chosen name) on a blocking body, returns the text on a clean one.

Plain-English gate:

- `test_prose_gate_flags_filler_phrase` — a denylisted phrase yields a blocking finding.
- `test_prose_gate_flags_over_long_sentence` — a sentence past the cap is blocking.
- `test_prose_gate_exempts_code_anchors` — a sentence long only because of backticked paths/symbols passes; a fenced block is never measured.
- `test_prose_gate_clean_body_no_findings` — a short, plain body returns `[]`.

Paths and collision safety:

- `test_derive_jira_detail_path_format` — `plan-details/<plan_slug>/jira/<NN>-<step_slug>.md` under the plan's parent.
- `test_jira_path_never_equals_run_grade_path` — for the same step, `derive_jira_detail_path` ≠ `derive_detail_path`.
- `test_orphan_sweep_leaves_jira_artifact` — with a jira artifact on disk, `detail.py:_archive_orphan_details` for the same step id moves nothing from `jira/`.
- `test_run_grade_adoption_ignores_jira_artifact` — `find_unreferenced_detail_for_step` returns `None` when only the jira artifact exists.

Import safety:

- `test_jira_grade_is_stdlib_only_leaf` — importing `plan_tool.jira_grade` in a subprocess leaves `plan_tool.detail`, `plan_tool.review`, and `plan_tool.jira` out of `sys.modules`.

(Approx. 17 new tests.)

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add the tests above with the implementation, each pinning the behavior named on its line. Gate: every new test green, and the full suite (`uv run pytest tests/ -q`) green with zero edits to any pre-existing test file, before this step is considered finished.

## Acceptance criteria

- `plan_tool/jira_grade.py` exists and is the only module that declares the five section names *as the jira-grade contract* (one declaration site, no second validator or token list elsewhere). Independent uses of the same phrases in other modules' vocabularies — e.g. `plan_tool/create.py`'s plan-body optional-section names, `plan_tool/parser.py`, `plan_tool/review.py` — are out of this uniqueness claim's scope (a bare repo-wide grep for `"Out of scope"` will legitimately hit them).
- `validate_jira_grade_body` (or chosen name) returns no blocking findings for a conforming body; returns blocking findings for each missing required H2, an empty section, an unknown H2, and a complete run-grade body — the last with a wrong-schema message.
- The plain-English gate flags a denylisted filler phrase and an over-cap sentence as blocking, returns advisory-or-nothing otherwise, and never flags text inside backticks or fences.
- `derive_jira_detail_path` returns `<plan_dir>/plan-details/<plan_slug>/jira/<NN>-<step_slug>.md`, never equal to the run-grade path for any step.
- With both grades on disk for one step, re-running the run-grade orphan sweep (`_archive_orphan_details`) leaves the jira artifact in place, and `find_unreferenced_detail_for_step` does not adopt it.
- The subprocess import test proves `plan_tool.jira_grade` imports without pulling `plan_tool.detail`, `plan_tool.review`, or `plan_tool.jira`; `tests/test_detail_artifacts.py`'s leaf import test still passes.
- `uv run pytest tests/ -q` passes with no edits to `tests/test_detail_artifacts.py`, `tests/test_detail.py`, or `tests/test_review.py`; no CLI flag, prompt, or output of any existing command changes.

## References

- [CommonMark Spec 0.30 — ATX headings](https://spec.commonmark.org/0.30/) — ground truth for what counts as an H2 line when the validator and matcher tokens parse heading syntax.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — for the `tmp_path` fixtures backing the path-collision and load-time tests.

## Deferred

- Wiring the validator, prose gate, and paths into consumers — step 4 owns the authoring mode and response gate, step 5 the `jira` export's hard read-time failure, step 6 the run renderer, and steps 7–9 the grade-aware audit. This step ships the authority with zero call sites; that is the intended end state here.
- Consolidating jira-grade H2 matching with `detail.py`'s run-grade matcher into one shared helper — a three-module refactor; route to reconcile rather than folding into this feature step.
- Split-renumbering and scope-out migration of jira-grade artifacts — `_migrate_downstream_details_after_split` and scope-out's detail migration walk `Step.detail` pointers, so unpointed `jira/` artifacts keep stale `NN-` prefixes after a renumber. The failure is loud (consumers hard-fail on the missing selected artifact, step 5's contract), not silent; a durable migration belongs with the consumer steps or a backlog entry once jira artifacts exist in a real corpus — surface it at reconcile.
- Claude-judged clarity review — #167's model-review half; this leaf is deterministic by design, no `invoker=` seam.
- A `Step` frontmatter field for a jira-grade pointer — the plan keeps `Step.detail` run-grade-only; any pointer field is a plan-level schema decision this step must not make.
- `DETAIL_FORMAT.md` / `JIRA_FORMAT.md` contract documentation and the #149 re-scope — step 10 owns docs and backlog close-out.
