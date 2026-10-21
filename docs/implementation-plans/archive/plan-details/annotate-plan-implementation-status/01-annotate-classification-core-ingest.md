> **Auto-archived**: this plan was swept on 2026-06-15 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add the annotate classification core

## Summary

- Create `plan_tool/annotate.py`: a Claude-invoking orchestrator that ingests an arbitrary plan/notes file, code-grounds it against the current repo, and returns a structured per-section classification (IMPLEMENTED / PARTIAL / NOT-IMPLEMENTED with concrete code references).
- The deliverable is the **classification contract** — a frozen `PlanAnnotation` dataclass carrying the verbatim source text plus a `SectionAnnotation` list — that step 2's two renderers (report + seed) consume. This step renders nothing and wires no CLI.
- **Load-bearing decision:** reuse the verified existing anchors verbatim — `read_existing_description` for ingestion, `extract_file_path_candidates` + `find_umbrella_root` for grounding, `prompts_dir()` + `string.Template.safe_substitute` for the prompt — and author exactly one new Claude seam (`plan_tool/prompts/annotate.md`) plus its overridable `invoker=` default (`shell_annotate_invoker`).
- On green: `classify_plan_implementation(path, repo_root=root, invoker=stub)` returns a `PlanAnnotation` whose `sections` carry the stubbed verdicts, whose `source_text` equals the ingested file byte-for-byte, and which raises `AnnotateError` on an unparseable Claude response.

## Table of Contents

- [Why](#why) — what's missing and why the core lands first.
- [Files (creates vs edits)](#files-creates-vs-edits) — three new files, zero edits.
- [Implementation](#implementation) — the dataclass contract, the orchestrator flow, the prompt, the parser, the invoker seam.
- [Tests](#tests) — unit cases stubbing the invoker, with creation order.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — the step-relevant subset of the plan's links.
- [Deferred](#deferred) — renderers, CLI, archive, and the `verify_plan` consolidation left for later.

## Why

- **No code today judges an arbitrary plan file against the repo and returns a structured verdict.** `reconcile-plan --rollup` (`plan_tool/launcher.py:verify_plan`) does the analogous per-step judgement but takes a `plan_path` it parses internally, requiring a plan file with frontmatter `steps:` — the annotate input is free-form prose with no frontmatter guarantee, so that engine cannot be called directly.
- **The classification is the foundation the whole feature stands on.** Step 2's report and seed renderers, and step 3's CLI, are pure consumers of this step's `PlanAnnotation`. Landing the contract first lets the renderers be authored against a stable, testable shape with the Claude seam already neutralized.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/annotate.py` — the classification core: dataclasses, orchestrator, prompt renderer, response parser, and the shell invoker default.
  - `plan_tool/prompts/annotate.md` — the `string.Template` prompt that drives the section-level implemented-vs-spec judgement and pins the JSON output contract.
  - `tests/test_annotate.py` — unit tests stubbing the `invoker=` seam.
- **Existing files (edits only):** none. This step imports `read_existing_description`, `extract_file_path_candidates`, the existing plan frontmatter reader (`parse_plan`/`read_frontmatter`, for `_load_step_specs`), `CreateError` (for reference) from `plan_tool/create.py`, `find_umbrella_root` from `plan_tool/locator.py`, and `prompts_dir` from `plan_tool/renderer.py` — it adds no symbols to them.

## Implementation

### `plan_tool/annotate.py`

**Public classification contract (the step's deliverable — step 2 consumes it):**

- `class AnnotationStatus(str, Enum)` — three members with the wire strings the prompt emits: `IMPLEMENTED = "IMPLEMENTED"`, `PARTIAL = "PARTIAL"`, `NOT_IMPLEMENTED = "NOT-IMPLEMENTED"`. Subclass `str` so JSON round-trips and renderers can compare against the literal without `.value`.
- `@dataclass(frozen=True) class SectionAnnotation` — one judged section:
  - `heading: str` — the original section heading verbatim (the renderer anchors the status block under it).
  - `status: AnnotationStatus`.
  - `evidence: str` — one-to-three-sentence justification.
  - `code_refs: tuple[str, ...]` — concrete `path:line` / symbol references; **expected non-empty for IMPLEMENTED/PARTIAL, empty tuple for NOT-IMPLEMENTED** — but an IMPLEMENTED/PARTIAL section with empty refs is demoted to `low_confidence`, not rejected (see the parser below). Use `tuple` not `list` so the frozen dataclass stays hashable and the structural `__eq__` golden is stable. For PARTIAL these refs name the already-implemented portion.
  - `remaining_work: str = ""` — for a PARTIAL section, the not-yet-implemented remainder in one-to-two sentences; this is the only portion step 2's seed renderer scopes into the next plan, while `code_refs`/`evidence` (the implemented half) are carried as done-context. Empty for IMPLEMENTED and NOT-IMPLEMENTED (NOT-IMPLEMENTED carries the whole section forward; IMPLEMENTED carries nothing forward).
  - `low_confidence: bool = False` — set when the prompt flags an uncertain grounding, or when the parser demotes an IMPLEMENTED/PARTIAL verdict that arrived without `code_refs` (mitigates the "under-resolved files → false NOT-IMPLEMENTED" risk by surfacing doubt rather than asserting).
  - `is_step: bool = False` — `True` when this section is a frontmatter `steps:` entry, so its `heading` is the step's YAML `title:` (which has no matching markdown heading line in the body). This is the contract field step 2's report renderer keys on to anchor the verdict inside the `## Steps` region instead of the unmatched-sections addendum (a YAML `title:` would otherwise never heading-match and every per-step verdict would fall to the addendum). `sections` preserves frontmatter `steps:` order, so step 2 places per-step blocks in order without a separate index field.
- `@dataclass(frozen=True) class PlanAnnotation` — the whole result:
  - `source_path: Path` — provenance: the original file (the report renderer records original → report lineage from this).
  - `source_text: str` — **the ingested file verbatim.** Load-bearing: step 2's additive-guarantee test diffs original lines against the rendered report, so the original must travel inside the result, not be re-read. Mark `field(compare=False)` only if a test needs to exclude it; default keep it compared.
  - `repo_root: Path` — the resolved umbrella root the grounding actually used (may differ from the caller's `repo_root` when the plan spans repos).
  - `grounded_files: tuple[Path, ...]` — the candidate files that resolved and were fed to the prompt (empty when none resolved — itself a strong NOT-IMPLEMENTED signal).
  - `sections: tuple[SectionAnnotation, ...]`.

**Typed error:**

- `class AnnotateError(Exception)` — mirror `plan_tool/create.py:CreateError` (subclass `Exception`, message names the offending file/condition). Raised for an unparseable/empty Claude response and for a malformed section entry. Do **not** swallow-and-return-empty: this is a definitive resolver over a caller-supplied real path, so a bad response must surface (the CLI layer in step 3 owns the operator UX).

**Invoker seam (mirror `plan_tool/detail.py:shell_detail_invoker`):**

- `AnnotateInvoker = Callable[[str], str]` type alias (mirrors `DetailInvoker`).
- `def shell_annotate_invoker(prompt: str) -> str:` — `_, stdout = claude_invoke(prompt); return stdout`. Import `claude_invoke` from `plan_tool.shell`. This is the production default; the autouse gate in `tests/conftest.py` raises if a test forgets to override it.

**Prompt renderer (mirror `plan_tool/detail.py:render_detail_prompt`):**

- `def render_annotate_prompt(source_text: str, step_specs_block: str, grounded_files_block: str) -> str:`
  - `template_path = prompts_dir() / "annotate.md"` (import `prompts_dir` from `plan_tool.renderer`).
  - `return Template(template_path.read_text(encoding="utf-8")).safe_substitute(source_body=source_text, step_specs_block=step_specs_block, grounded_files_block=grounded_files_block)`.
  - Use `safe_substitute` (not `substitute`) so a stray `$` in the ingested prose, loaded spec, or grounded code does not raise — matches `render_detail_prompt`.
  - `step_specs_block` carries the loaded frontmatter-step spec bodies (see the step-spec loader below) and is rendered **distinct from** `grounded_files_block` so the prompt judges each step against its real `detail:` spec, not its one-line `title:`, and never mistakes a spec file for code evidence.

**Step-spec loader (private) — the spec the prompt judges against:**

- `def _load_step_specs(source_text: str, *, repo_root: Path) -> tuple[tuple[str, str], ...]:` — when the ingested file is a valid plan-tool plan, parse its frontmatter `steps:` (reuse the YAML frontmatter read the plan loader already uses — e.g. `parse_plan`/`read_frontmatter` from `plan_tool/create.py`; do **not** mint a second frontmatter parser) and, for each entry, return a `(title, spec_body)` pair where `spec_body` is the `detail:` file's text read from `(repo_root / entry["detail"])` (empty string when the entry has no `detail:` or the file is absent). Returns `()` when the input has no parseable `steps:` block (the rough-notes / non-plan path), so the prompt sees no spec block and falls back to section-by-heading judgement.
- `_format_step_specs_block` turns the pairs into a fenced, title-labelled block for `${step_specs_block}` — each step's `title:` as the section label and its loaded `detail:` body beneath. This is the spec the prompt judges each `is_step: true` section against; it is **not** code evidence and is presented separately from the grounded-code block. Apply the same `max_file_bytes` bound and truncation labelling as the grounding helper so a large `detail:` file is bounded, not dropped silently.

**Grounding helper (private):**

- `def _ground_source(source_text: str, *, repo_root: Path, max_file_bytes: int, exclude: frozenset[Path] = frozenset()) -> tuple[Path, tuple[tuple[Path, str], ...]]:` — returns the resolved umbrella root and the `(path, bounded_content)` pairs. Flow:
  1. `candidates = extract_file_path_candidates(source_text)` (from `plan_tool.create`).
  2. `umbrella = find_umbrella_root(candidates, search_from=repo_root, fallback=repo_root)` (from `plan_tool.locator`); treat a `None` return as `repo_root`. This is the same widening the CLI authoring flow does in `plan_tool/cli/authoring.py` (the `find_umbrella_root(... fallback=repo_root)` block).
  3. For each candidate, resolve `(umbrella / candidate)`; **skip silently** when it is not an existing file (permissive posture matching `extract_file_path_candidates`'s docstring — an unresolved ref is a NOT-IMPLEMENTED signal, not an error) **or when its resolved path is in `exclude`** — the plan's own `detail:` spec files are passed in `exclude` so they are judged as spec (via `_load_step_specs`), never injected into the grounded block as code evidence (which would bias every step toward IMPLEMENTED because the spec exists on disk). Read at most `max_file_bytes` bytes per file; when the on-disk file exceeds that bound, mark the pair **truncated** so the symbol past 4KB is not silently assumed absent.
- `_MAX_GROUND_FILE_BYTES = 4096` — mirror `plan_tool/detail.py:_MAX_PROMPT_FILE_BYTES` (same 4096 value, distinct name so the two prompts tune independently).
- `_format_grounded_block` turns the pairs into a fenced, path-labelled block for the prompt (mirror the shape of detail.py's `_format_files_contents_block`, but inline here — no need to share). **Label any truncated file in its block header** (e.g. `[truncated to first 4096 bytes]`) and instruct the prompt to set `confidence_low` for a verdict grounded on a truncated file — a relevant symbol may sit past the cut, so PARTIAL/NOT-IMPLEMENTED on a truncated file is surfaced as doubt, not asserted (same posture as the under-resolution mitigation).

**Orchestrator entry:**

- `def classify_plan_implementation(source_path: Path, *, repo_root: Path, invoker: AnnotateInvoker = shell_annotate_invoker, max_file_bytes: int = _MAX_GROUND_FILE_BYTES) -> PlanAnnotation:`
  1. `source_text = read_existing_description(source_path)` — reuse the `--from-existing` reader (`plan_tool/create.py:read_existing_description`); it raises `CreateError` if the path is not a file. Do **not** add a second tolerant parser.
  2. `step_specs = _load_step_specs(source_text, repo_root=repo_root)` — load each frontmatter step's `detail:` body as the spec to judge (empty tuple for non-plan input).
  3. `umbrella, grounded = _ground_source(source_text, repo_root=repo_root, max_file_bytes=max_file_bytes, exclude=<resolved detail: paths from step 2>)` — exclude the loaded `detail:` spec files so they are not double-counted as code evidence.
  4. `prompt = render_annotate_prompt(source_text, _format_step_specs_block(step_specs), _format_grounded_block(grounded))`.
  5. `raw = invoker(prompt)`.
  6. `sections = _parse_annotation_response(raw)` → raises `AnnotateError` on failure.
  7. Return `PlanAnnotation(source_path=source_path, source_text=source_text, repo_root=umbrella, grounded_files=tuple(p for p, _ in grounded), sections=sections)`.

**Response parser (mirror `plan_tool/create.py:_parse_steps_json` extraction):**

- `def _parse_annotation_response(raw: str) -> tuple[SectionAnnotation, ...]:`
  - Locate the JSON array with `text.find("[")` / `text.rfind("]")` and `json.loads` on the slice — identical extraction shape to `_parse_steps_json`, which already tolerates prose around the JSON and fenced blocks.
  - **On any of:** no array found, `JSONDecodeError`, empty list, a non-dict entry, a missing/blank `heading`, a `status` not in `AnnotationStatus` → raise `AnnotateError` naming the failure (unlike `_parse_steps_json`, which returns `None` for an interactive fallback that does not exist here).
  - Coerce `status` via `AnnotationStatus(value)`; normalise `code_refs` to a `tuple[str, ...]`. **Raise `AnnotateError` only for the contradictory `NOT_IMPLEMENTED`-with-`code_refs` case** (a genuinely impossible verdict). For an IMPLEMENTED/PARTIAL section with empty `code_refs`, **demote to `low_confidence=True`** rather than raise — the model could not pin a concrete symbol but the verdict is otherwise reasonable, and the `low_confidence` flag exists to surface exactly this doubt without aborting the whole annotate (consistent with the "under-resolved files → false NOT-IMPLEMENTED" mitigation).
  - Read `low_confidence` via `bool(item.get("confidence_low", False))` (absent key defaults `False`, matching the additive-optional-key posture).
  - Read `remaining_work` via `str(item.get("remaining", "")).strip()` (absent key defaults `""`, same additive-optional-key posture). It only carries meaning for PARTIAL — the seed renderer scopes exactly this remainder; for IMPLEMENTED/NOT-IMPLEMENTED a stray value is ignored downstream, so do not raise on it.
  - Read `is_step` via `bool(item.get("is_step", False))` (absent key defaults `False`, same additive-optional-key posture) — set by the prompt for each frontmatter `steps:` entry so step 2 can anchor its verdict in the `## Steps` region.

### `plan_tool/prompts/annotate.md`

- Author as a `string.Template` file with exactly three `${...}` placeholders: `${source_body}`, `${step_specs_block}`, and `${grounded_files_block}`. No other `$` should appear unescaped (write literal dollars as `$$`) — `safe_substitute` tolerates strays but keep the template clean.
- Mirror `plan_tool/prompts/detail.md`'s conventions: a role/intent preamble, a `## Plan spec` section (the loaded frontmatter-step `detail:` bodies — the spec each step is judged against), a `## Code grounding` section explaining the grounded files are the current repo state to judge against, and a strict `## What to produce` block. The `## Plan spec` section must state that these bodies are the **spec to satisfy, not evidence of implementation**, so their presence on disk never by itself implies IMPLEMENTED. The `## Code grounding` section must note that a file marked truncated shows only its first bytes, so any verdict grounded on it sets `confidence_low` rather than assuming a symbol past the cut is absent.
- **Output contract (pin it hard):** respond with **only** a JSON array, each element `{"heading": str, "status": "IMPLEMENTED"|"PARTIAL"|"NOT-IMPLEMENTED", "evidence": str, "code_refs": [str], "remaining": str, "confidence_low": bool, "is_step": bool}`. Require `code_refs` to be concrete `path:symbol` or `path:line` strings for IMPLEMENTED/PARTIAL and an empty array for NOT-IMPLEMENTED. For PARTIAL, `code_refs` names the already-implemented portion and `remaining` states the not-yet-implemented remainder (the only part the next plan should scope); set `remaining` to `""` for IMPLEMENTED and NOT-IMPLEMENTED. State the same anti-line-number guidance the repo favors (prefer symbol anchors over raw line numbers).
- **Plan-tool plan input (the primary case):** when the ingested file is a valid plan-tool plan, its substantive spec is the frontmatter `steps:` block (each entry's `title:`/`detail:`), and its `## Steps` prose body is a placeholder ("See the `steps:` block in the frontmatter"). Instruct the prompt to treat **each frontmatter `steps:` entry as its own classifiable section** — the entry's `title:` is the section `heading` and its `detail:` content (loaded into `${step_specs_block}` by `_load_step_specs` and matched to the step by `title:`) is the spec to judge against — rather than classifying only the `Overview`/`Architecture`/`Risks` prose and emitting a contentless NOT-IMPLEMENTED for the `## Steps` placeholder. Emit one array element per step entry (heading = the step `title:`, `is_step: true`), plus elements for any other substantive prose sections (`is_step: false`). The `is_step: true` flag is what lets step 2's report renderer anchor each per-step verdict inside the `## Steps` region rather than dumping it to the unmatched-sections addendum (the YAML `title:` heading never matches a markdown heading line). Because `read_existing_description` ingests the whole file verbatim (frontmatter included), the prompt sees the `steps:` YAML, and `_load_step_specs` reuses the existing plan frontmatter reader to load each step's `detail:` body into `${step_specs_block}`; no new frontmatter parser is added in this step.
- **Heading-less input (the rough-notes case):** when the ingested body has no parseable `steps:` block and no markdown headings, instruct the prompt to treat the entire file as a single section — emit exactly one array element whose `heading` is a synthesized label (`source_path.name`) and whose `status`/`evidence`/`code_refs` judge the whole document at once. This gives the `--from-existing` rough-notes path defined coverage (one classified section) rather than an empty result; because the synthesized `source_path.name` heading is not a line in the heading-less `source_text`, step 2's `_insert_status_blocks` finds no anchor and emits this single status block as an explicitly appended section (the unmatched-sections addendum), not inline under an in-body heading.
- Editing this `.md` needs **no Python change** as long as no new `${...}` placeholder is introduced — `safe_substitute` only resolves the two named keys (per the captured detail-prompt lesson about external `string.Template` prompt files).

## Tests

All tests live in `tests/test_annotate.py`. Every case passes a stub `invoker=` (lambda or recording closure) so the autouse `tests/conftest.py` gate never fires; no `@pytest.mark.allow_real_claude`.

### Test-creation order (feature step)

Author these unit tests **with** the implementation; each must be green before the step is done.

- `test_classify_returns_sections_from_stubbed_invoker` — stub returns a canned JSON array; assert `PlanAnnotation.sections` has the expected headings/statuses.
- `test_status_strings_map_to_enum` — canned `"IMPLEMENTED"/"PARTIAL"/"NOT-IMPLEMENTED"` coerce to the three `AnnotationStatus` members.
- `test_source_text_is_verbatim` — `PlanAnnotation.source_text` equals the on-disk file byte-for-byte (the additive-guarantee precondition step 2 relies on).
- `test_not_implemented_with_code_refs_raises` — a NOT-IMPLEMENTED entry with non-empty `code_refs` raises `AnnotateError` (contradictory verdict).
- `test_implemented_without_code_refs_demoted_to_low_confidence` — an IMPLEMENTED/PARTIAL entry with empty `code_refs` does not raise; the resulting `SectionAnnotation` has `low_confidence is True`.
- `test_unparseable_response_raises` — invoker returns `""` and returns prose-without-JSON; both raise `AnnotateError`.
- `test_malformed_status_raises` — a JSON entry with `status: "DONE"` raises `AnnotateError` naming the bad value.
- `test_missing_source_file_raises_create_error` — `classify_plan_implementation` on a non-file path surfaces `CreateError` from `read_existing_description` (not silently swallowed).
- `test_grounding_resolves_to_find_umbrella_root` — a source citing files spanning two repos resolves `PlanAnnotation.repo_root` to the `find_umbrella_root` result (the common ancestor that owns both); assert against a `tmp_path` two-repo layout.
- `test_unresolved_candidate_files_are_skipped` — a source citing a non-existent path produces a result with that path absent from `grounded_files` and no raise.
- `test_prompt_includes_source_and_grounded_block` — capture the prompt via a recording invoker; assert the ingested body and a grounded file's content both appear (mirrors `tests/test_detail.py`'s prompt-capture closure pattern).
- `test_prompt_includes_step_detail_spec` — over a plan input whose step has a `detail:` file, capture the prompt and assert the `detail:` body appears in the step-spec block (the step is judged against its real spec, not its one-line `title:`).
- `test_step_detail_files_excluded_from_grounding` — the plan's own `detail:` `.md` paths are not present in `grounded_files` (they are loaded as spec, not injected as code evidence).
- `test_render_annotate_prompt_substitutes_placeholders` — direct `render_annotate_prompt(...)` call; assert all three placeholders resolved and no literal `${` survives.
- `test_low_confidence_flag_parsed` — `confidence_low: true` yields `SectionAnnotation.low_confidence is True`; absent key defaults `False`.
- `test_partial_remaining_work_parsed` — a PARTIAL entry with `remaining: "resolver in step 6 still missing"` yields `SectionAnnotation.remaining_work` equal to that string; absent key defaults `""`.
- `test_is_step_flag_parsed` — an entry with `is_step: true` yields `SectionAnnotation.is_step is True`; absent key defaults `False` (the flag step 2 uses to anchor plan-step verdicts in the `## Steps` region).
- `test_heading_less_source_classified_as_one_section` — a source file with no markdown headings (stub invoker returns a single-element array whose `heading` is the file name) yields a `PlanAnnotation` with exactly one `SectionAnnotation`, not an empty `sections`.

**Green-before-done gate:** all of the above pass under `uv run pytest -m "not integration" tests/test_annotate.py -q` before this step is considered finished.

## Acceptance criteria

- `classify_plan_implementation(path, repo_root=root, invoker=stub)` returns a `PlanAnnotation` whose `sections` reflect the stubbed JSON verdicts.
- `PlanAnnotation.source_text` equals the ingested file's contents verbatim.
- An invoker returning empty string, non-JSON prose, an empty array, an unknown `status`, or a NOT-IMPLEMENTED entry carrying `code_refs` each raises `AnnotateError`. An IMPLEMENTED/PARTIAL entry with empty `code_refs` is demoted to `low_confidence`, not rejected.
- A PARTIAL entry's `remaining` value is parsed into `SectionAnnotation.remaining_work` (absent key defaults `""`), giving step 2's seed renderer the not-yet-implemented remainder to scope while the implemented `code_refs`/`evidence` carry as done-context.
- An entry's `is_step` value is parsed into `SectionAnnotation.is_step` (absent key defaults `False`), and `sections` preserves frontmatter `steps:` order, so step 2 can anchor each per-step verdict in the `## Steps` region instead of the unmatched addendum.
- A source path that is not a file raises `CreateError` (propagated from `read_existing_description`).
- A source citing files under a nested repo resolves `PlanAnnotation.repo_root` to the `find_umbrella_root` result; unresolved file references are skipped, not fatal.
- For a plan input, each frontmatter step's `detail:` body is loaded and presented to the prompt as the step's spec (in `${step_specs_block}`), and those `detail:` spec files are excluded from the grounded-code block so the spec's mere presence on disk does not bias the verdict toward IMPLEMENTED.
- `shell_annotate_invoker` is the production default for `invoker=`; every test overrides it and no test spawns the real backend.
- `render_annotate_prompt` substitutes exactly `${source_body}`, `${step_specs_block}`, and `${grounded_files_block}` via `safe_substitute`.

## References

- [pathlib — Object-oriented filesystem paths — Python docs](https://docs.python.org/3/library/pathlib.html) — Path resolution and bounded reads for grounding candidate files and deriving the umbrella root.
- [subprocess — Subprocess management — Python docs](https://docs.python.org/3/library/subprocess.html) — The contract behind `claude_invoke`/`shell_annotate_invoker` that the seam must keep overridable in tests.
- [Claude Code — Headless / Run programmatically](https://code.claude.com/docs/en/headless) — The `-p`/`--print` non-interactive contract the real shell invoker depends on for the implemented-vs-spec judgement.
- [json — JSON encoder and decoder — Python docs](https://docs.python.org/3/library/json.html) — `json.loads` and `JSONDecodeError` handling for the response parser (the gap the plan-level list does not cover for this step).
- [string — Common string operations (Template) — Python docs](https://docs.python.org/3/library/string.html#template-strings) — `Template.safe_substitute` semantics — the prompt-rendering mechanism mirrored from `render_detail_prompt`.

## Deferred

- **Report and seed renderers** — step 2 (`plan_tool/annotate_render.py`). This step deliberately ships zero rendering; it only produces the `PlanAnnotation` the renderers walk.
- **CLI wiring** (`annotate` subparser, `--output-dir`/`--report`/`--seed`/`--archive`, `--help` golden) — step 3 (`plan_tool/cli/annotate_cmd.py`). The orchestrator stays filesystem-/argparse-agnostic; only the CLI defaults `invoker=` to the shell seam in production.
- **`--archive` preservation/lineage** via `plan_tool/create.py:archive_existing_source` — step 3. The core never mutates the original.
- **Consolidating the judgement engine with `plan_tool/launcher.py:verify_plan`** — a shared "does code satisfy this spec" engine would be a refactor `detail` cannot mint. `verify_plan` judges per **parsed `Plan` step**; annotate judges per **free-form section of an un-parsed file**, so it authors its own `annotate.md` prompt rather than calling `verify_plan`. Route any future unification of the two judgement seams to a dedicated reconcile/refactor step.
- **Distill** (`plan_tool/create.py:propose_distilled_seed_from_claude`) — stays in `create` and is never invoked by annotate; the seed (step 2) bypasses distill via the documented `create --from-existing <name>.seed.md --no-distill` handoff (its `Carryover scope`/`Already implemented`/`Provenance` body does not meet `create`'s canonical-coverage skip condition, so compactness alone would not bypass distill).
