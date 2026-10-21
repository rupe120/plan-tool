# Step 2 — Add jira-grade detail authoring with separate files

## Summary

Add an explicit jira-grade authoring mode to `plan-tool detail` while keeping the current run-grade mode as the default. Update `plan_tool/cli/authoring.py` and `plan_tool/detail.py` to select the correct prompt, response contract, and separate artifact path for the requested depth. Create `plan_tool/prompts/detail-jira.md` for compact outcome-focused detail, and update `DETAIL_FORMAT.md` and `docs/DETAIL_FLOW.md` to describe both contracts. On green, one plan can hold independent run-grade and jira-grade detail files without changing `Step.detail` or reinterpreting legacy bundles.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the new authoring mode.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — Why separate authoring is needed before downstream consumers change.
- [Input](#input) — Existing run-grade and step-1 artifact-routing contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Prompt, authoring, documentation, and test footprint.
- [Implementation](#implementation) — Depth selection, compact contract, and compatibility rules.
- [Tests](#tests) — Unit and CLI coverage for both authoring paths.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for path and test behavior.
- [Deferred](#deferred) — Consumer changes and evaluation work owned by later steps.

## Why

`plan-tool detail` currently has one run-grade prompt, parser, and canonical write path, so it cannot produce a compact Jira-oriented artifact without overwriting or confusing the detail that `run` relies on. Step 1 supplies separate artifact routing; this step must use that routing to author a second contract while preserving the existing `Step.detail` pointer and legacy run-grade behavior. The already-present `### Authoring altitude and concept threads` section in `DETAIL_FORMAT.md` describes outcome-focused guidance, but it does not yet provide a distinct Jira-grade authoring contract or prompt.

## Input

- **Step 1 artifact routing:** This step is blocked until Step 1 supplies `plan_tool/detail_artifacts.py:derive_jira_detail_path()` for collision-safe Jira-grade path selection. Reuse that mechanism, whose result must be distinct from the run-grade path for the same step, rather than adding another path convention inside `plan_tool/detail.py`.
- **Run-grade control contract:** `plan_tool/detail.py:render_detail_prompt()`, `parse_detail_response()`, `derive_detail_path()`, and `update_step_detail_field()` define the current run-grade flow. `Step.detail` remains the stored run-grade pointer.
- **Authoring command boundary:** `plan_tool/cli/authoring.py:cmd_detail()` owns command dispatch and forwards authoring options into `plan_tool/detail.py:generate_detail()`.
- **Concept deferral transport:** `plan_tool/detail.py:parse_structured_detail_response()` must select the depth-specific parser and require the existing deferral envelope when the plan has candidate buckets or a concept record. Deferral evidence belongs under `## Deferred` for run-grade and `## Out of scope` for Jira-grade; the envelope remains transport metadata and is not written into either artifact body.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/prompts/detail-jira.md` — Define the compact jira-grade authoring prompt and its required markdown contract.

- **Existing files (edits only):**
  - `DETAIL_FORMAT.md` — Document run-grade and jira-grade detail as separate contracts, including their required sections, selection rules, and legacy compatibility.
  - `docs/DETAIL_FLOW.md` — Show the authoring branch that selects a depth, writes the matching artifact, and leaves run-grade as the default.
  - `docs/cli/README.md` — Regenerate the CLI reference index for the new `detail` depth option.
  - `docs/cli/detail.md` — Regenerate the `detail` command reference for the new depth selection.
  - `plan_tool/cli/authoring.py` — Add explicit depth selection to the `detail` parser and thread it through `cmd_detail()`.
  - `plan_tool/detail.py` — Render and parse the selected contract, write through step 1’s artifact routing, and preserve the existing run-grade path unchanged.
  - `tests/cli/test_authoring_cmds.py` — Cover CLI parsing, default selection, and forwarding at the `cmd_detail()` seam.
  - `tests/cli/test_cli_reference.py` — Cover generated CLI-reference drift for the new `detail` option.
  - `tests/test_detail.py` — Cover prompt rendering, parse gates, separate writes, idempotency, and legacy run-grade compatibility.

## Implementation

- **Make depth explicit.** Add one mutually exclusive authoring-mode selector near the `p_detail` setup in `plan_tool/cli/authoring.py:register()`. The default must select run-grade; Jira-grade must require an explicit opt-in. Prefer a named depth value over a boolean so the command can reject unknown or conflicting selections clearly.

- **Keep the existing run-grade path unchanged.** `cmd_detail()` must continue calling `generate_detail()` with the current behavior when no Jira-grade option is present. Read the new argument with a compatibility-safe `getattr(args, "depth", "run")` so namespaces constructed by `plan_tool/cli/direct_cmd.py:cmd_direct_jira()` and `cmd_direct_run()` remain run-grade without needing the new field. `render_detail_prompt()`, `parse_detail_response()`, the run-grade `derive_detail_path()` behavior, and `update_step_detail_field()` remain the control path for existing callers and legacy artifacts.

- **Add a compact, separate body contract.** `plan_tool/prompts/detail-jira.md` should direct the model to produce pure markdown with one H1 and the required H2 sections `Intent`, `Change`, `Constraints`, `Done when`, and `Out of scope`. The contract should state outcomes, boundaries, and acceptance conditions; it must not require file-by-file edits, test rosters, or algorithms unless the plan declares them as a constraint.

- **Use a separate parser for Jira-grade output.** Place the Jira-grade parse gate beside `plan_tool/detail.py:parse_detail_response()` and keep its required-section rules independent from `_REQUIRED_H2_TOKENS`. Accept the same harmless response cleanup that protects run-grade output where it is applicable, but reject a response that is incomplete for the selected contract rather than silently treating a run-grade body as Jira-grade.

- **Select retry guidance by depth.** Replace the run-grade-only `_REPROMPT_SUFFIX` with selected-depth retry text so a Jira-grade parse retry requests `Intent`, `Change`, `Constraints`, `Done when`, and `Out of scope`, while run-grade retries retain their existing seven-heading guidance.

- **Preserve the structured response envelope.** `parse_structured_detail_response()` must pass the selected depth to its parser and deferral-evidence check while still cooperating with `_strip_structural_findings_preserving_deferrals()`. Jira-grade markdown is compact, so required deferrals are evidenced under `## Out of scope` rather than the run-grade `## Deferred` section; the plan’s deferral envelope remains transport metadata and must not be written into the artifact body.

- **Route artifact lifecycle by depth, not by pointer mutation.** Extend `generate_detail()` and its `_author_step_detail()` call path so target selection, skip/force checks, checkpoint identity and input hash, plan mutation, and orphan archiving are all keyed by the selected depth, with Jira-grade writes using Step 1’s `plan_tool/detail_artifacts.py:derive_jira_detail_path()`. That helper’s Jira-grade result must be distinct from the run-grade path for the same step; do not add a parallel routing seam. Do not set, replace, or reinterpret `Step.detail` for Jira-grade output; it remains the run-grade pointer. A Jira-grade write must not skip because a same-step run-grade pointer exists, overwrite or archive that run-grade file, resume a run-grade checkpoint, or share its checkpoint cache, and an existing Jira-grade file must follow the selected mode’s normal `--force` and idempotent-skip behavior.

- **Keep run-grade-only processing out of the compact path.** `collect_detail_quality_findings()` and the existing detail-quality prompt assume the run-grade section schema. Do not apply that run-grade validator or its rewrite loop to Jira-grade bodies unless this step adds an explicit compatible check within its declared files. If an existing authoring option cannot safely apply to the compact mode, fail early with a clear mode-specific message rather than producing an artifact that the current validator will misread.

- **Gate the automatic completeness tail by depth.** After a successful write, `cmd_detail()` currently invokes `_run_completeness_tail()`, whose coverage check treats an unpointed same-step artifact as unreferenced. Do not invoke that run-grade tail for Jira-grade authoring unless it is made depth-aware to recognize the selected Jira-grade artifact; preserve the existing tail for run-grade so Jira-grade’s intentionally unchanged `Step.detail` pointer cannot produce a false coverage failure.

- **Share prompt context without duplicating routing policy.** One workable approach is to let `render_detail_prompt()` select the template and required parser from the requested depth while reusing the existing plan metadata, declared-file content, plan references, guardrails, lessons, output-path warning, and concept-scope inputs. Avoid creating a second independent authoring pipeline that can drift from checkpointing, retries, dry runs, and progress reporting.

- **Document the two contracts plainly.** In `DETAIL_FORMAT.md`, make the current seven-section schema explicitly run-grade and document the Jira-grade required sections and separate artifact selection. In `docs/DETAIL_FLOW.md`, show that explicit selection happens before prompt rendering and that only run-grade updates the legacy `Step.detail` pointer.

- **Keep downstream consumers out of this step.** `plan_tool/jira.py:render_jira_prompt()` and the run-side prompt/rendering paths are shared locations that will consume the new artifact later. Step 3 owns Jira consumption and step 4 owns opt-in run consumption; do not change them here.

## Tests

- `tests/cli/test_authoring_cmds.py::test_detail_defaults_to_run_grade` — Parsing and `cmd_detail()` forwarding select run-grade when no depth option is supplied.
- `tests/cli/test_authoring_cmds.py::test_detail_missing_depth_defaults_to_run_grade` — A compatibility namespace without `depth`, including direct-command callers, forwards run-grade without raising an attribute error.
- `tests/cli/test_authoring_cmds.py::test_detail_forwards_explicit_jira_grade` — The explicit Jira-grade option reaches the `generate_detail()` boundary.
- `tests/cli/test_authoring_cmds.py::test_detail_rejects_conflicting_depth_options` — Mutually exclusive depth selection fails before authoring begins.
- `tests/cli/test_authoring_cmds.py::test_detail_jira_grade_gates_run_grade_completeness_tail` — Jira-grade authoring does not run the pointer-based completeness tail, while run-grade retains it.
- `tests/cli/test_cli_reference.py` — Generated references remain in sync with the `detail` parser’s depth selection.
- `tests/test_detail.py::test_render_jira_detail_prompt_uses_compact_template` — The Jira-grade renderer includes the compact required sections and shared plan context without unresolved template placeholders.
- `tests/test_detail.py::test_parse_jira_detail_response_accepts_complete_compact_body` — A complete Jira-grade body passes the Jira-grade parse gate.
- `tests/test_detail.py::test_parse_jira_detail_response_rejects_missing_required_sections` — An incomplete or run-grade-shaped body cannot be published as Jira-grade.
- `tests/test_detail.py::test_generate_jira_detail_writes_separate_artifact` — Jira-grade authoring writes the distinct path returned by `plan_tool/detail_artifacts.py:derive_jira_detail_path()` while leaving an existing run-grade file and `Step.detail` unchanged.
- `tests/test_detail.py::test_generate_detail_default_remains_run_grade` — The existing invocation still writes the canonical run-grade path and updates `Step.detail`.
- `tests/test_detail.py::test_jira_detail_force_and_skip_are_scoped_to_jira_artifact` — Jira-grade idempotency and `--force` affect only the Jira-grade artifact.
- `tests/test_detail.py::test_jira_detail_retry_and_checkpoint_are_depth_specific` — Jira-grade parse retries request the compact headings, and Jira- and run-grade invocations use distinct checkpoint identities and input hashes.
- `tests/test_detail.py::test_jira_detail_preserves_structured_deferral_transport` — A Jira-grade response with required deferrals passes the depth-aware structured parse through `## Out of scope` and records valid envelope data without embedding the envelope in the written markdown.

### Test-creation order (feature step)

1. Add parser and prompt-rendering tests with the depth-selection interface; cover the default run-grade and explicit Jira-grade branches.
2. Add Jira-grade parse tests before wiring writes; cover a valid compact body and missing required sections.
3. Add orchestration tests for the distinct Jira-grade path from `plan_tool/detail_artifacts.py:derive_jira_detail_path()`, pointer preservation, and selected-mode skip/force behavior.
4. Add the CLI forwarding and invalid-combination tests at `cmd_detail()`.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan-tool detail <name>` without a depth option keeps the current run-grade prompt, parser, artifact path, and `Step.detail` update behavior.
- `cmd_detail()` treats a caller namespace that lacks `depth` as run-grade so direct Jira and run commands remain compatible.
- An explicit Jira-grade option renders `plan_tool/prompts/detail-jira.md` and validates `Intent`, `Change`, `Constraints`, `Done when`, and `Out of scope` before writing.
- A valid Jira-grade artifact and a valid run-grade artifact for the same plan step coexist at distinct paths, with the Jira-grade path selected by `plan_tool/detail_artifacts.py:derive_jira_detail_path()`.
- Authoring Jira-grade detail does not overwrite, repoint, or reinterpret the run-grade `Step.detail` value.
- A missing Jira-grade required section prevents publication after a Jira-grade-specific parse retry; a complete run-grade body is not accepted as Jira-grade by mistake.
- Jira- and run-grade invocations use depth-specific retry guidance, checkpoint identities, and checkpoint input hashes, so they cannot resume each other’s cached bodies.
- Required Jira-grade deferrals are accepted only when evidenced under `## Out of scope`; run-grade continues to use `## Deferred`.
- Jira-grade dry runs do not write either artifact or mutate the plan.
- Run-grade-only quality processing is not applied to a Jira-grade body without a compatible Jira-grade check.
- Jira-grade authoring gates or depth-adapts the automatic completeness tail so its intentionally unpointed artifact is not reported as unreferenced; run-grade retains the existing tail.
- `tests/test_detail.py`, `tests/cli/test_authoring_cmds.py`, and `tests/cli/test_cli_reference.py` cover both depth branches and generated-reference drift and pass.

## References

- [pytest API Reference](https://docs.pytest.org/en/stable/reference/reference.html) — Use temporary-path fixtures and parametrization for independent artifact and mode coverage.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — Use path operations for separate, collision-safe artifact locations.

## Deferred

- Jira consumption of jira-grade detail — Step 3 owns `plan_tool/cli/jira_cmd.py` and `plan_tool/jira.py`.
- Opt-in run consumption of jira-grade detail — Step 4 owns the run command and renderer changes.
- Paired evaluation, adoption threshold, and any default inversion — Steps 5 and 6 collect evidence; this step leaves run-grade as the default.
- Per-step mechanically prescriptive Jira supplements — The plan defers this until experiment failures show that the compact contract needs an escape hatch.
