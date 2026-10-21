> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Write ROADMAP_FORMAT.md specifying both artifacts and naming the code that enforces them

## Summary

This step creates `ROADMAP_FORMAT.md` at the repo root — the schema reference for the two roadmap artifacts, `01-domain.md` and `02-constraints.md`. It documents where they live, every frontmatter row and field, the three closed vocabularies, and — the part the plan's acceptance criteria turn on — a rule table that names the code enforcing each rule, so every gate in `plan_tool/roadmap_gates.py` traces back to a stated clause and every clause traces forward to a symbol. The main design decision is that the doc splits enforcement into **two channels and says which one each rule is in**: shape failures raise at parse time in `plan_tool/roadmap_artifacts.py`, relation failures return violations from `plan_tool/roadmap_gates.py`. On green the repo has one new markdown file, no code changes, and a reader can predict from the doc alone whether a given broken artifact raises or produces a violation.

## Table of Contents

- [Summary](#summary) — what the step ships and the one design decision behind it.
- [Why](#why) — why the contract needs a written home now, not after the stages land.
- [Input](#input) — the names steps 1 and 2 mint that this doc records.
- [Files (creates vs edits)](#files-creates-vs-edits) — the one new file; no edits anywhere.
- [Implementation](#implementation) — the doc's outline, the rule table, and the rules that are not free to vary.
- [Tests](#tests) — no unit tests; the checks that stand in for them.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the specs behind the YAML and decision-record wording.
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences that bind this step.
- [Deferred](#deferred) — which doc owns what, and what other steps write.

## Why

Steps 1 and 2 put the roadmap contract in code, spread across two modules and split by channel: shape rules raise, relation rules return violations. Nothing tells a reader that split exists. An operator staring at a gate violation, or an author writing the stage prompts, has to read both modules to learn which rule lives where — and the person most affected is the one hand-editing an artifact before `--from-stage N` re-entry, who needs to know what will be checked and what will not. The repo already answers this for its other artifact types: `PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, and `JIRA_FORMAT.md` each pair a written schema with a source-of-truth banner naming the enforcing code. Roadmap artifacts are the fourth artifact type and the only one without that pairing. Writing it now — before the stage prompts (steps 5 and 6) exist — also gives the person *authoring* those prompts one settled reference to write from, instead of each prompt's author re-deriving the row inventory out of two modules. **It does not give the prompts a doc to point at.** `plan-tool` is installed as a tool and the verb runs in whatever repo the operator is in, which has no copy of `ROADMAP_FORMAT.md`; `rg -l 'FORMAT\.md' plan_tool/prompts/` returns nothing across all templates at HEAD, and that is the rule, not an oversight. Each prompt still restates the full inventory in its own text, pinned by a containment test against step 1's constants (steps 5 and 6). The benefit here is a correct, reviewable source for the author — not shared text at run time.

## Input

This step consumes the outcomes of steps 1 and 2 and records them. It reads the landed modules, not this plan's prose.

- **Step 1 produces the artifact contract** — `plan_tool/roadmap_artifacts.py`: path helpers for `<plans_dir>/roadmaps/<slug>/01-domain.md` and `02-constraints.md`, the filename and directory constants, frozen row types for entities / business rules / workflows / quality-attribute dispositions / constraints / decisions, the three closed vocabularies, the parse/load pair, the renderer, and one contract error carrying the offending path.
- **Step 2 produces the seven gates** — `plan_tool/roadmap_gates.py`: the violation type with its kind constants, the seven relation checks, and the two stage gate sets.
- **The landed names win over any name suggested in this plan.** Steps 1 and 2 mint the field names, constants, and function names; their detail files call them out as suggestions. Open both modules and write down what actually shipped. Where the doc and the code disagree, the code is right — that is the same rule the banner states.
- **Two modules the doc names are not on disk yet.** `plan_tool/roadmap.py` writes the artifacts and `plan_tool/cli/roadmap_cmd.py` wires the verb; both land later in this plan (steps 4 and 7), and the stage prompts under `plan_tool/prompts/` land in steps 5 and 6. See [Implementation](#implementation) for how the doc refers to them without citing symbols that do not exist.
- **What cannot be verified here:** nothing runs a roadmap end to end yet, so the doc's examples are checked by feeding them to step 1's parser and step 2's gate sets directly, not by running the verb.

## Files (creates vs edits)

- **New files:**
  - `ROADMAP_FORMAT.md` — the artifact schema reference described under [Implementation](#implementation).
- **Existing files (edits only):** none. Cross-links *into* this doc from `README.md`, `CLAUDE.md`, `USE_CASES.md`, and `RUNBOOK.md` belong to other owners — see [Deferred](#deferred).

## Implementation

### Follow the FORMAT-doc family contract

`PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, and `JIRA_FORMAT.md` share a shape. Match it rather than inventing one:

- **Open with the source-of-truth banner.** A blockquote naming the enforcing code — `plan_tool/roadmap_artifacts.py` for shape and vocabularies, `plan_tool/roadmap_gates.py` for relations — and closing with the family's exact stance: the tool does not load this doc at runtime, and if the doc and the code disagree, the code wins and the doc gets fixed.
- **Show schemas as fenced `yaml` blocks with inline comments**, the way `PLAN_FORMAT.md`'s frontmatter schema does — one block per artifact, every row kind and field named, `# required` / `# default` markers inline.
- **Close with a `## See also` list** of the sibling docs, following `DETAIL_FORMAT.md` and `JIRA_FORMAT.md` (`PLAN_FORMAT.md` has no such tail — the banner is the only element all three share).

### The outline

Roughly ten H2 sections, in this order. Adjust the split if something reads better, but keep every subject below present:

- **What a roadmap is, and that it is not a plan.** Two artifacts, one per stage, under one directory. Plan discovery never resolves them: `plan_tool/locator.py:list_plans` globs `plans_dir.glob("*.md")` at the top level only, so a file inside `roadmaps/<slug>/` is invisible to it, and nothing is added to `plans.json`.
- **What writes them.** The `roadmap` verb, with the orchestrator and CLI module named by path (see the citation rule below). Artifacts are committed docs; only the run log lands under `.plan-tool/runs/<slug>/`, with every other verb's.
- **Path convention.** `<plans_dir>/roadmaps/<slug>/01-domain.md` and `02-constraints.md`, computed by step 1's path helpers, with the directory and filename constants named. State that `plans_dir` is resolved by the caller — the default is `plan_tool/locator.py:PLANS_SUBPATH`, overridable by `--plans-dir` and `PLAN_TOOL_PLANS_DIR` (`plan_tool/locator.py:resolve_explicit_plans_dir`) — and that the slug is rejected when it is empty, whitespace-only, or carries a path separator or a `..` part.
- **The frontmatter schema of `01-domain.md`** — entities, business rules, workflows with the entity ids each touches, and decision rows.
- **The frontmatter schema of `02-constraints.md`** — one disposition row per quality attribute, constraint rows with the upstream ids they anchor to, and decision rows.
- **The closed vocabularies** — decision status, constraint disposition (including the *not load-bearing* member), and the quality-attribute list. Restate the members for readability *and* name the constant in `plan_tool/roadmap_artifacts.py` as canonical. That is the `DETAIL_FORMAT.md` move: it prints the five jira-grade headings and then says the canonical list is `JIRA_GRADE_REQUIRED_H2S` in `plan_tool/jira_grade.py`.
- **The prose body.** Everything after the closing `---` is preserved byte for byte through a load-and-render cycle and is written for humans. **One gate reads it:** `check_inventory_has_prose` requires every frontmatter row id to appear somewhere in the body, so an inventoried row the narrative never describes is a violation. Say what that gate does *not* do — it never judges whether the prose is good, only whether the row was mentioned at all — so a reader does not mistake it for the prose gate the architecture bans.
- **The two enforcement channels** — the rule table below.
- **What is deliberately not enforced.** A `pending` decision is never a violation; it is the review channel. Advisory residue on a written artifact never flips an exit code — the verb exits non-zero only when it fails to finish. Say plainly that a hand edit is re-read from disk at `--from-stage N` re-entry and judged by the same gates as model output.
- **An abridged example** of each artifact, short enough to keep current, that really parses and really passes both gate sets — see [Tests](#tests).

### The rule table is the deliverable

The plan's acceptance criterion is that every gate is traceable to a stated contract clause. A table makes that checkable in both directions, so build the enforcement section around one:

- **One row per rule**, with three columns: the rule in plain words, the symbol that enforces it, and what failing it looks like.
- **Split the table (or tag each row) by channel**, because the two behave differently for a reader:
  - **Shape — raises.** Opening fence present, fence closed, YAML parses, required row keys present, row collections of the right type, and every vocabulary value a known member. Enforced by step 1's parse/load functions, which raise the module's contract error carrying the path; a vocabulary rejection names the bad value.
  - **Relations — return violations.** The seven gates in `plan_tool/roadmap_gates.py`, each named with what it demands and what its message names: workflows **and business rules** reference defined entities (both ids in the message); ids unique across all row kinds in one artifact, one violation per duplicated id; exactly one disposition per quality attribute (the attribute name when the row is missing), every constraint row's `attribute` a member of the same list, and no constraint serving an attribute disposed `not-load-bearing`; every constraint anchored to an id `01-domain.md` defines; every decision carrying a rejected alternative with its reason, a non-empty rationale, and an anchor resolving to a row id in its own artifact (or, for a constraints decision, an `01-domain.md` id) — a quality attribute being reachable only through its disposition row's id, never its bare name; each artifact non-empty (a domain declares at least one entity and one workflow, a constraints artifact at least one constraint row — dispositions alone do not count); and every frontmatter row id described in the prose below the fence.
- **State what parse-time deliberately lets through** — an undefined entity reference, a duplicate id, a missing attribute, an unresolvable anchor, a decision with no alternatives. Otherwise a reader hunts for anchor resolution in the parser and concludes it is missing.
- **Say what a violation is for.** Violations are correction text fed back into a retry of the same stage, not report lines. That is why they name ids and never line numbers.

The alternative — prose paragraphs describing each rule without naming a symbol — is rejected: it makes the doc impossible to check against the code, which is the one property the plan asks for.

### Rules that are not free to vary

- **Every rule the doc states names the code that enforces it, and every gate the code ships appears in the doc.** Both directions. An unenforced rule and an undocumented gate are the two defects this doc exists to prevent.
- **Cite symbols only in modules that exist when you write; cite the not-yet-built modules as paths, and know those are forward references.** `plan_tool/roadmap_artifacts.py` and `plan_tool/roadmap_gates.py` are on disk by now, so name their functions and constants. For `plan_tool/roadmap.py`, `plan_tool/cli/roadmap_cmd.py`, and the stage prompt files, name the **module path only** — no function names. Be honest about what that buys: those paths do **not** resolve when this step runs (steps 4, 5, 6 and 7 create them), so the doc is not fully resolvable at step 3 and this step's verification cannot claim otherwise. A path is the smallest forward reference that survives — it needs no update when the module lands, while a function name would be a guess at an API that does not exist yet. **Re-check these paths once the plan closes**, which step 8's verification owns; step 3's own grep covers cited *symbols* against `plan_tool/` and by construction cannot cover a path to an unwritten file.
- **No line numbers, in any citation.** Symbol names only. They survive edits; offsets do not.
- **No plan step ids in the shipped doc.** Write it in the present and future tense, describing what the artifacts are and what the code does. A doc that says "step 4 adds the writer" rots the moment the plan closes.
- **Do not restate another doc's contract.** Cross-link `PLAN_FORMAT.md` for plan frontmatter, `DETAIL_FORMAT.md` for detail grades, `SEED_FORMAT.md` for seeds. A copied fact drifts.
- **No flag or CLI reference.** `docs/cli/` is generated from the argparse parser; a hand-written flag list here would be a second, drifting copy.
- **Nothing here is loaded at runtime.** Do not describe the doc as parsed, validated, or consumed by any command.

## Tests

This is a **non-code** step: it adds no production code and no unit tests. The plan's per-step strategy calls for verification appropriate to the artifact.

### Verification (non-code step)

Eight checks, all runnable by a reviewer:

- **The example `01-domain.md` parses.** Feed it to step 1's domain parser; expect a typed artifact and no raise.
- **The example `02-constraints.md` parses.** Same, through the constraints parser.
- **The examples round-trip.** Render each parsed artifact and re-parse it; the result equals the original, so the doc's YAML shows a shape the writer really produces.
- **The examples pass both gate sets.** Run step 2's domain and constraints aggregates over the parsed pair; expect an empty violation list. An example that would fail its own gates is the worst thing this doc could ship.
- **Every gate is documented.** Every public `check_*` function in `plan_tool/roadmap_gates.py` appears by name in the doc — compare the module's function list against `rg 'check_' ROADMAP_FORMAT.md`.
- **Every cited symbol exists.** `rg` each constant, class, and function name the doc cites against `plan_tool/`; zero misses. **Scope:** this covers symbols only. The four forward-referenced module *paths* (`plan_tool/roadmap.py`, `plan_tool/cli/roadmap_cmd.py`, and the two stage prompt files) do not exist yet and are deliberately not checked here — step 8 re-checks them once the plan closes.
- **No line numbers and no plan step ids.** `rg '\.py:[0-9]' ROADMAP_FORMAT.md` and a scan for "step 1"/"step 4"-style references both come back empty.
- **Links resolve and the tree is otherwise untouched.** Every relative link in `## See also` points at a file that exists; `git status` shows exactly one new file; `uv run pytest tests/ -q` stays green.

## Acceptance criteria

- `ROADMAP_FORMAT.md` exists at the repo root and is the only file this step adds or changes.
- It opens with the family's source-of-truth banner naming both `plan_tool/roadmap_artifacts.py` and `plan_tool/roadmap_gates.py`, and stating that the code wins on disagreement.
- It documents the path convention `<plans_dir>/roadmaps/<slug>/01-domain.md` and `02-constraints.md`, names the constants and path helpers that compute it, and states that `plans_dir` is passed in rather than hardcoded.
- It documents the full frontmatter inventory of both artifacts — every row kind and every field — using the names that actually shipped in `plan_tool/roadmap_artifacts.py`.
- It lists all three closed vocabularies with their members, including the *not load-bearing* disposition, and names the canonical constant for each.
- It carries a rule table in which every one of the seven gates in `plan_tool/roadmap_gates.py` appears by function name, alongside what it demands and what its message names.
- It states which rules raise at parse time and which return violations, and lists the relation defects that parse cleanly on purpose.
- It states that a `pending` decision is never a violation and that advisory residue never flips the exit code.
- Both abridged examples parse through step 1's parsers, round-trip through render-and-re-parse unchanged, and produce zero violations from both of step 2's gate sets.
- `rg '\.py:[0-9]' ROADMAP_FORMAT.md` returns nothing, and every symbol the doc cites is found by `rg` in `plan_tool/`. The four module paths the doc forward-references are not yet on disk at this step and are re-checked by step 8.
- Every relative link in the doc points at a file that exists.
- `uv run pytest tests/ -q` stays green and `git status` shows one new untracked file and no modified files.

## References

- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — the normative grammar and type-resolution rules; read it so the documented serialization of id lists, enum values, and nested rows is precise rather than approximate.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — the loader and dumper behind the artifacts; read it when describing how values are quoted and how a malformed document surfaces.
- [ISO/IEC 25010 — Product quality model (characteristics and subcharacteristics)](https://iso25000.com/index.php/en/iso-25000-standards/iso-25010) — the canonical quality-attribute names; check the doc's spelling of the shipped list against it.
- [MADR — Markdown Architectural Decision Records](https://adr.github.io/madr/) — the established decision-record fields (status, considered options with why each lost, outcome); useful wording for the decision-row section.

## Applicable guardrails

- **No change to plan discovery, the plan schema, or the manifest.** This step writes one doc. The doc must also say plainly that roadmap artifacts are a separate artifact type and that no plan-pipeline surface resolves them.
- **No standalone audit or reconcile surface over roadmap artifacts.** Describe the in-run gates only. Do not describe, propose, or imply a `completeness`-style verb over these artifacts.
- **No per-project configuration of the quality-attribute list.** Document the list as a constant shipped in `plan_tool/roadmap_artifacts.py`. Do not document a config key, an override, or a way to extend it.
- **No sign-off command for `pending` decisions.** The review channel is a hand edit plus `--from-stage N` re-entry; document that and nothing more.
- **No interactive or TTY surface.** Describe the verb as non-interactive by design, not as missing an interview.
- **Nothing for the later stages.** No `03-components.md` or `04-roadmap.md` paths, row types, or gates, and no seed-emission contract.

## Deferred

- **`README.md`'s code-layout tree and its doc index** — outside this step's file list. Route the one-line entry to the operator-docs step that closes this plan, or to reconcile.
- **`CLAUDE.md`'s reference-docs list, `USE_CASES.md`, `RUNBOOK.md`, and `integrations/claude/SKILL.md`** — the plan's final docs step owns all four, and it owns the operator loop narrative that goes with them.
- **The flag reference for the verb** — `docs/cli/roadmap.md` is generated from the argparse parser and is written by the CLI-wiring step; a hand-written flag list here would drift from it.
- **`CAPABILITIES.md`'s entry for the verb** — added by the CLI-wiring step, since `plan-tool validate`'s catalog check requires the subcommand to exist first.
- **The run-log schema and the stage table's shape** — the orchestrator step owns both. This doc says only that artifacts are committed under the plans directory while run state lands in `.plan-tool/runs/<slug>/`.
- **The retry budget and what an exhausted budget does** — orchestrator behavior, not artifact schema. The doc states that a violation is retry input and stops there.
- **A checked-in test that re-parses the doc's examples** — this step adds no test file, and the plan defers extending `tests/test_data_contract.py` to the roadmap contract while it is still settling. The manual re-parse under [Verification](#verification-non-code-step) is the check for now.
- **Documenting stage prompt contents** — the prompt files are written by their own steps and are prompts, not artifacts; this doc describes what a stage must produce, never how it is asked.
