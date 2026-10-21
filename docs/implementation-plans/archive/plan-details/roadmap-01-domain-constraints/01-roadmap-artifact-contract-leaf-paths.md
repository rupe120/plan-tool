> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a roadmap artifact contract leaf with paths, enums, and frontmatter parsing

## Summary

This step creates `plan_tool/roadmap_artifacts.py`, the one module that answers "where does a roadmap's files live, what do their frontmatter rows hold, and which words are allowed in them" — plus `tests/test_roadmap_artifacts.py`. It ships path helpers for `<plans_dir>/roadmaps/<slug>/01-domain.md` and `02-constraints.md`, frozen row types for entities / rules / workflows / quality-attribute dispositions / constraints / decisions, three closed vocabularies, a parser that raises on a malformed artifact, and a renderer so a written artifact re-parses. The main design decision is that the leaf imports **no first-party module** — not even `plan_tool.parser._split_frontmatter` — so it mirrors the repo's frontmatter fence rules instead of reusing them, and takes the resolved plans directory as an argument instead of re-deriving it. On green, a roadmap artifact loads into typed rows and dumps back to the same bytes, with no gate, no orchestrator, and no Claude call anywhere in the module.

## Table of Contents

- [Summary](#summary) — what the step ships and the one design decision behind it.
- [Why](#why) — why the contract has to exist before any gate or stage can be written.
- [Input](#input) — the two existing contracts this leaf has to match without importing them.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files; no edits anywhere.
- [Implementation](#implementation) — paths, vocabularies, row types, the parse/render pair, and the rules that are not free to vary.
- [Tests](#tests) — the 28 cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the docs worth reading for the YAML and enum decisions.
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences that bind this step.
- [Deferred](#deferred) — what other steps own, and the one consolidation routed to reconcile.

## Why

Nothing in the repo knows what a roadmap artifact is. Steps 2, 4, 5, and 6 all need the same three facts — the file paths, the frontmatter row shapes, and the closed word lists — and each would otherwise mint its own copy. The layering makes this sharp: `plan_tool/roadmap_gates.py` (step 2) is allowed exactly one first-party import, this leaf, so anything a gate reads has to be defined here or duplicated in the gate module. The repo already has the pattern to copy — `plan_tool/jira_grade.py` is the single authority for the jira-grade section tokens precisely so its four consumers cannot drift — and the same reasoning applies here with more consumers. Writing the contract first also makes the gates unit-testable: a gate is a pure function over a parsed artifact, which needs the parsed type to exist before it can be written.

## Input

Two existing contracts constrain this leaf even though it must not import either one.

- **The plan-side frontmatter fence rule** — `plan_tool/parser.py:_split_frontmatter` defines it: the file's first line must be exactly `---` (`_FENCE`), and the next line equal to `---` closes the block; anything after is the prose body. Roadmap artifacts carry "the same dual contract as plans" (BACKLOG #208), so the leaf's own splitter must accept and reject the same inputs. It cannot call that function: `plan_tool/parser.py` imports `plan_tool.schema` and pydantic, which would make this module a non-leaf. `plan_tool/reprocess.py:_split_frontmatter_for_rewrite` is the only existing second copy of that scan — this leaf becomes the third.
- **The plans-directory contract** — `plan_tool/locator.py:PLANS_SUBPATH` is `docs/implementation-plans`, but it is overridable by `--plans-dir` and `PLAN_TOOL_PLANS_DIR` (`plan_tool/locator.py:resolve_explicit_plans_dir`), and skill/agent-scoped repos resolve elsewhere (`plan_tool/scope_guard.py`). The leaf therefore accepts an already-resolved plans directory and never re-derives one. Verifying the default location end-to-end needs a caller that resolves it — that is step 4/step 7 work, so this step's tests pass a `tmp_path` directory directly.

Also worth knowing while writing the parser: PyYAML's `SafeDumper` raises `RepresenterError` on an `Enum` subclass even when it inherits from `str` — `plan_tool/parser.py:_coerce_enums` documents this and exists only to work around it. The renderer here hits the same wall.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_artifacts.py` — the contract leaf: path helpers, closed vocabularies, row types, parser, renderer, error type.
  - `tests/test_roadmap_artifacts.py` — the suite listed under [Tests](#tests).
- **Existing files (edits only):** none. No call sites exist yet, and no orchestrator, CLI handler, or doc changes belong here.

## Implementation

### Paths

- **Take the plans directory as a parameter; never derive it.** One function per artifact reading `(plans_dir: Path, slug: str) -> Path`, plus a `roadmap_dir(plans_dir, slug)` the two share. `plan_tool/detail_artifacts.py:derive_detail_path` is the shape to follow — a pure path function with no filesystem access.
- **Name the two artifacts as constants**, not literals repeated at call sites — something like `DOMAIN_FILENAME = "01-domain.md"` and `CONSTRAINTS_FILENAME = "02-constraints.md"`, under a `ROADMAP_DIRNAME = "roadmaps"` subdirectory. Step 3's `ROADMAP_FORMAT.md` and step 4's stage table both read these.
- **Validate the slug before joining it.** Copy the checks in `plan_tool/worktree.py:_validate_slug` — reject a non-string, an empty or whitespace-only value, a `/` or `\` component, and a `..` traversal part — since this is the only place a caller-supplied slug becomes a path. `plan_tool/create.py:SLUG_RE` (`^[a-z0-9][a-z0-9-]*[a-z0-9]$`) is the repo's stricter plan-slug shape; matching it is reasonable but the path-safety checks are the part that must hold.
- **A `roadmaps/` subdirectory is already invisible to plan discovery.** `plan_tool/locator.py:list_plans` globs `plans_dir.glob("*.md")` — top level only, not recursive — and the manifest lists explicit paths. Nothing needs changing to satisfy the plan's "plan discovery untouched" criterion; a test that asserts it is still worth having as a guard.

### Closed vocabularies

- **Two parser-enforced vocabularies, plus one shared constant that the parser does *not* police** — all defined here because `roadmap_gates.py` can import only this module. The split matters: an unknown *status* or *disposition* is a parse error, while an unknown *attribute* is a gate violation, and if the parser rejected attributes too, step 2's totality-gate arm for "a row naming something outside the list" could never fire.
  - **Decision status (parser-enforced)** — two members: a settled-by-guess value and `pending`. Nothing consumes a third "confirmed" value in this plan (see [Deferred](#deferred)).
  - **Constraint disposition (parser-enforced)** — must include a value meaning *this attribute is deliberately optimized for*, one meaning *deliberately traded away*, and the honest-answer value the plan's Risks section names, spelled `not-load-bearing`. That third member is what keeps the totality gate (step 2) satisfiable without filler.
  - **The quality-attribute list (a shared constant, not a parser check)** — an ordered, fixed tuple of the seven BACKLOG #208 names: performance, scalability, security, availability, maintainability, fault tolerance, reliability. The parser carries the tuple and coerces nothing against it; **step 2's totality gate is the sole owner of membership**, so it can report an unknown attribute as a violation with the row id rather than dying at parse time.
- **The seven are deliberately a flat *operational* list, not a conformance taxonomy.** In ISO/IEC 25010, availability and fault tolerance are subcharacteristics *of* reliability, so a hierarchy-faithful list would not let a roadmap dispose all three independently. This plan wants exactly that: each name is a concern an operator ranks on its own, and "exactly one disposition per attribute" is a prompt for seven separate judgments, not a claim about a standard. The consequence is real and accepted — nothing stops `reliability: not-load-bearing` sitting beside `availability: prioritized`, and that combination is *coherent under this reading* (the system need not survive component failure, but must stay reachable). Do **not** cite ISO/IEC 25010 as the source of the taxonomy; it is at most a spelling reference. A nesting-aware disposition model is [Deferred](#deferred).
- **Use plain `str, Enum` from the stdlib**, matching `plan_tool/schema.py:ChangeType`'s style. Pydantic is a real dependency and would validate members for you, but its error text needs the flattening helper in `plan_tool/parser.py:format_validation_errors` to name the offending value cleanly — and that file is off-limits here. A hand-written coercion that raises with the bad value in the message is smaller and gives the message the acceptance criteria ask for.
- **The attribute list belongs here rather than in the gate module** because both the step-2 gate and step 6's constraints prompt need one source. This is the `jira_grade.py` doctrine: consumers import the tokens, never re-declare them.

### Row types and the parsed artifacts

- **Frozen dataclasses, one per row kind**, and two artifact types holding them plus the prose body. A workable inventory (field names are this step's to mint, but step 3 documents them, so settle them here):
  - domain — entities, business rules (**each rule carrying the entity ids it governs**), workflows (each workflow carrying the entity ids it touches), decisions. Rules carry entity ids for the same reason workflows do: step 6 lets a constraint anchor to the union of entity, rule and workflow ids, so a rule that connects to no entity would be a valid anchor target that breaks the entity→constraint traceability chain this artifact exists to create;
  - constraints — one disposition row per quality attribute, constraint rows each carrying **the attribute they serve** plus the upstream ids they anchor to, decisions. The `attribute` field is minted here rather than assumed downstream: step 6's prompt asks for it, and without it nothing links a constraint to the attribute it discharges;
  - a decision row — id, the chosen option, a list of rejected alternatives each with its reason, a rationale, **an anchor naming the element the decision bears on**, and a status from the closed vocabulary. The anchor is what makes a `pending` decision actionable: the operator confirming it by hand — this plan's whole review channel — must be able to see what it constrains, and a later stage inheriting it as a fence needs the same.
- **An anchor is always a row *id*, and the resolvable set differs by artifact.** In `01-domain.md` it is an entity, business-rule, or workflow id. In `02-constraints.md` it is a disposition, constraint, or other row id in that artifact, **or** an `01-domain.md` id, which is why step 2's decision gate reads the envelope rather than one artifact. **A quality attribute is addressed by its disposition row's id, never by its plain name** — attribute names are a constant, not rows, so a name resolves nowhere and only the disposition row puts the attribute in the id space. Step 1 mints the field; step 2 resolves it; steps 5 and 6 state the same set in their prompts. State it identically in all four places, because an anchor target the parser accepts and the gate can never resolve is a rule that fails only at run time, on the operator's budget.
- **Keep rows as an ordered tuple, never a dict keyed by id.** A duplicate id must survive parsing so the step-2 gate can report it; collapsing to a map at parse time silently drops one row and makes that gate unwritable.
- **Preserve the prose body exactly.** Whatever follows the closing fence is carried through untouched, so a render after a load returns the original bytes.

### Parsing and rendering

- **Split the text form from the path form**, following `plan_tool/jira_grade.py`: a `parse_*(text)` pair for the two artifacts and a `load_*(path)` pair that reads the file and adds the path to any error. Most tests then need no temp files.
- **Raise, don't return findings.** The plan's Risks section says a malformed upstream artifact "surfaces as a parse error at re-entry rather than silently". Add one exception type carrying the offending path, modeled on `plan_tool/jira_grade.py:JiraGradeContractError`. Gate *violations* — which return, not raise — are step 2's separate channel.
- **Check shape here, relations there.** The loader checks: fences present, YAML parses (`yaml.safe_load`, catching `yaml.YAMLError`), required keys present on each row, values of the right type, and every closed-vocabulary value a known member. It does **not** check that a workflow's entity id exists, that ids are unique, that every attribute appears once, or that a constraint's anchor points at something real. `plan_tool/schema.py:Feature`'s docstring states this split for the plan side — types at parse time, "unique/kebab ids, refs resolving to the registry" as advisory checks elsewhere — and it is the line to hold.
- **Every raised message names the offending thing**: the row id where there is one, and the bad value for a vocabulary rejection. Gates in step 2 inherit this expectation.
- **Pair the parser with a renderer.** `render_*(artifact) -> str` dumps the frontmatter through `yaml.safe_dump` and re-attaches the body, so `parse(render(a)) == a` is testable in this step and step 4's writer does no YAML shaping of its own. Convert enum members to their `.value` before dumping — see the `RepresenterError` note in [Input](#input). Writing bytes to disk (which path, when, atomically via `plan_tool/fileio.py:atomic_write_text`) stays with step 4.

### Constraints that are not free to vary

- **No first-party import, at column 0 or inside a function.** This is asserted by test, and it is what lets `roadmap_gates.py` stay a leaf too. `yaml` is the only third-party import the plan sanctions.
- **No `invoker=` seam and no subprocess.** The leaf is pure functions of its inputs; only `plan_tool/roadmap.py` (step 4) shells out.
- **No reads of config or the environment.** The quality-attribute list is a constant, and per-project configuration of it is fenced out by the plan.
- **Nothing here touches the plan schema, the manifest, or plan discovery** — see [Applicable guardrails](#applicable-guardrails).

## Tests

All cases live in `tests/test_roadmap_artifacts.py`. They are plain unit tests (unmarked, no `@pytest.mark.integration`) — the module drives no orchestrator and crosses no module boundary. The leaf has no backend seam, so the suite passes under `tests/conftest.py`'s autouse gate with no `@pytest.mark.allow_real_claude` opt-out.

### Tests for this step

28 cases. Every one must be green before this step is finished.

**Paths and slugs**

- `test_roadmap_dir_sits_under_the_given_plans_dir` — `roadmap_dir` returns `<plans_dir>/roadmaps/<slug>`.
- `test_domain_and_constraints_paths_share_the_roadmap_dir` — both artifact paths have the same parent and the constant filenames.
- `test_paths_follow_an_arbitrary_plans_dir` — passing a non-default directory moves both paths; no `docs/implementation-plans` is hardcoded.
- `test_slug_with_a_path_separator_is_rejected` — `/` or `\` raises rather than escaping the directory.
- `test_slug_with_a_parent_traversal_component_is_rejected` — a `..` part raises.
- `test_empty_or_whitespace_slug_is_rejected` — raises with the bad value in the message.
- `test_roadmap_subdir_is_not_matched_by_a_top_level_md_glob` — an artifact under `roadmaps/<slug>/` is absent from `plans_dir.glob("*.md")`, guarding the plan-discovery fence.

**Closed vocabularies**

- `test_decision_status_members` — exactly the settled-by-guess and `pending` values, spelled as documented.
- `test_constraint_disposition_includes_not_load_bearing` — the honest-answer member exists alongside the prioritized and traded-away members.
- `test_quality_attribute_list_is_ordered_and_has_no_duplicates` — the shipped tuple's contents and order are pinned.
- `test_unknown_decision_status_raises_naming_the_value` — the message contains the rejected string.
- `test_unknown_disposition_raises_naming_the_value` — same for the disposition vocabulary.

**Domain artifact parsing**

- `test_conforming_domain_body_parses_every_row_kind` — entities, rules, workflows, and decisions all land as typed rows.
- `test_missing_opening_fence_raises` — a body that does not start with `---` is a contract error.
- `test_unclosed_frontmatter_fence_raises` — an opening fence with no closer raises.
- `test_malformed_yaml_raises_and_names_the_path` — a `yaml.YAMLError` becomes the leaf's error type carrying the path.
- `test_missing_required_row_key_raises_naming_the_row` — a workflow row with no id (or no entity references) names the row in the message.
- `test_wrong_type_for_a_row_collection_raises` — a scalar where a list of rows is required is rejected, not coerced.
- `test_duplicate_row_ids_survive_as_separate_rows` — two rows sharing an id both appear in the parsed tuple, so step 2's gate can see them.
- `test_prose_body_is_preserved_unchanged` — the text after the closing fence round-trips exactly, including blank lines.

**Constraints artifact parsing**

- `test_conforming_constraints_body_parses_attributes_and_constraints` — disposition rows and constraint rows both land typed.
- `test_constraint_anchor_ids_parse_without_being_resolved` — an anchor pointing at an id no artifact defines parses fine; resolution is a gate.
- `test_attribute_missing_from_the_body_still_parses` — an incomplete disposition set is a gate finding, not a parse error.
- `test_decision_with_no_rejected_alternative_still_parses` — the "names its alternatives" rule is a gate, not a shape check.

**Round-trip**

- `test_domain_artifact_round_trips_through_render_and_parse` — parse → render → parse returns an equal artifact.
- `test_constraints_artifact_round_trips_through_render_and_parse` — same for the constraints artifact.
- `test_rendered_enum_values_are_plain_strings` — the rendered YAML carries `pending`, not a Python enum repr, and re-parses.

**Layering**

- `test_leaf_imports_no_first_party_module` — importing the module in a subprocess under a stub `plan_tool` package leaves no other `plan_tool.*` entry in `sys.modules`, following `tests/test_jira_grade.py:TestLeafImportDiscipline` and `tests/test_detail_artifacts.py:TestLeafAndReexports::test_leaf_does_not_import_detail`. Pair it with the source grep in `tests/test_rate_limit_loop.py:test_leaf_has_no_first_party_runtime_import`, which also catches a lazy import inside a function.
- `test_leaf_declares_no_invoker_seam` — no `invoker`/`claude_invoker` parameter and no `subprocess` import anywhere in the module.

## Acceptance criteria

- `plan_tool/roadmap_artifacts.py` and `tests/test_roadmap_artifacts.py` exist; no other file in the repo changes.
- `rg '^(from|import) plan_tool' plan_tool/roadmap_artifacts.py` returns nothing, and importing the module under a stub `plan_tool` package leaves no other `plan_tool.*` module in `sys.modules`.
- `rg 'invoker|subprocess' plan_tool/roadmap_artifacts.py` returns nothing.
- The path helpers return `<plans_dir>/roadmaps/<slug>/01-domain.md` and `<plans_dir>/roadmaps/<slug>/02-constraints.md` for any plans directory passed in; a slug containing `/`, `\`, `..`, or only whitespace raises.
- Parsing a conforming `01-domain.md` yields typed entity, rule, workflow, and decision rows; parsing a conforming `02-constraints.md` yields one disposition row per attribute present plus constraint and decision rows.
- Parsing raises the module's contract error — carrying the path — for: no opening `---`, an unclosed fence, invalid YAML, a missing required row key, a wrong-typed row collection, and an unknown decision-status or disposition value. The vocabulary messages contain the rejected string.
- Parsing does **not** raise for a workflow naming an undefined entity, a constraint anchored to an unknown id, a missing quality attribute, a duplicate row id, or a decision with no alternatives — every one of those parses into rows.
- `parse(render(artifact))` equals `artifact` for both artifact types, and the rendered YAML contains the vocabulary values as plain strings.
- The 28 cases in `tests/test_roadmap_artifacts.py` pass under `uv run pytest tests/test_roadmap_artifacts.py -q`, and the full suite (`uv run pytest tests/ -q`) stays green.
- `<plans_dir>/.plan-tool/plans.json` is unchanged after the suite runs, and `plan_tool/schema.py`, `plan_tool/parser.py`, and `plan_tool/locator.py` carry no diff.

## References

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — `safe_load`, `YAMLError`, and `safe_dump` options; read it for the loader's error handling and the renderer's dump settings.
- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — type-resolution rules, needed so an id list, an enum value, and a nested row have one defined serialization for step 3 to document.
- [Standard Library Types — Pydantic Docs](https://docs.pydantic.dev/latest/api/standard_library_types/) — how Pydantic validates `Enum` fields and what it raises on an unknown member; read it to judge the hand-written-coercion choice made here.
- [ISO/IEC 25010 — Product quality model (characteristics and subcharacteristics)](https://iso25000.com/index.php/en/iso-25000-standards/iso-25010) — a **spelling reference only**, not the source of this list's structure. Its hierarchy nests availability and fault tolerance under reliability; the shipped list deliberately keeps all seven flat and independently disposable (see Implementation). Do not "fix" the list toward the standard without also revisiting the totality gate.
- [MADR — Markdown Architectural Decision Records](https://adr.github.io/madr/) — the established decision-record field set (status, considered options with why each lost, outcome, consequences); the model for the decision row's shape.

## Applicable guardrails

- **No change to plan discovery, the plan schema, or the manifest.** Roadmap artifacts are a separate artifact type on purpose. This step adds no field to `plan_tool/schema.py`, changes nothing in `plan_tool/parser.py` or `plan_tool/locator.py`, and writes nothing to `plans.json`. The `roadmaps/<slug>/` subdirectory is chosen partly because `plan_tool/locator.py:list_plans`' top-level `*.md` glob already cannot see it.
- **No standalone audit or reconcile surface over roadmap artifacts.** The leaf exposes parse, render, and path helpers only — no report, no findings roll-up, no `--fail-on-findings`-style verdict.
- **No per-project configuration of the quality-attribute list.** It is a constant in this module. Do not read `plan_tool/project_config.py` or any config file — the no-first-party-import rule blocks that anyway.
- **No interactive or TTY surface.** Pure functions, no prompts, no `input()`, no confirm gate.
- **Nothing for the later stages.** No `03-components.md` / `04-roadmap.md` paths or row types, and no seed rendering for the `FORK_STRUCTURAL` arm.

## Deferred

- **Every relation check over parsed rows** (workflow→entity references, duplicate ids, attribute totality, constraint anchors, decisions naming alternatives and a rationale) — step 2 owns them in `plan_tool/roadmap_gates.py`. This step deliberately parses such artifacts without complaint so those gates have something to be given.
- **Writing artifacts to disk, the run log, the retry loop, and `--from-stage` re-entry** — step 4's orchestrator. This leaf renders text; it never opens a file for writing.
- **`ROADMAP_FORMAT.md`** — step 3 documents the row inventory this step mints and names the code enforcing each rule.
- **The stage prompts and the CLI verb** — steps 5–7. Nothing here knows a stage or an argparse parser exists.
- **Consolidating the repo's three frontmatter fence scanners** — `plan_tool/parser.py:_split_frontmatter`, `plan_tool/reprocess.py:_split_frontmatter_for_rewrite`, and this leaf's own. A shared splitter would have to be a new leaf below `parser.py`, which is a cross-module refactor this step cannot mint; route it to reconcile or a BACKLOG entry.
- **A "confirmed" decision status** — nothing consumes one. Under the shipped two-member vocabulary an operator records acceptance of a `pending` decision by **editing its status to the settled value**, which reads as *this is the decision of record* rather than *a machine guessed it*; that is what keeps the reported `pending` count a queue that can be worked to zero instead of a tally that only rises. A third value would distinguish an accepted guess from an original one, but nothing downstream reads that difference yet, so two members is the honest set today. The plan defers pinning a confirmed decision across `--from-stage` re-entry to the sign-off surface it also defers.
- **Extending `tests/test_data_contract.py` to the roadmap frontmatter** — the plan defers this while the contract is still being established; this suite is the only check for now.
- **Restating the quality-attribute list in step 6's `roadmap-constraints.md` prompt** — a static prompt file cannot import a constant, so that restatement is a real drift risk the prompt's owning step has to handle.
