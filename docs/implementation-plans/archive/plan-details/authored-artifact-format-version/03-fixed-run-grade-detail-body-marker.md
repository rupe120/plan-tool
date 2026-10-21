> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add the fixed run-grade detail body marker and shared parser to detail_artifacts.py, then route every semantic run-grade detail read and apply boundary through its refusal

## Summary

`plan_tool/detail_artifacts.py` gains the run-grade detail class's format-version contract: `DETAIL_FORMAT_VERSION`, `SUPPORTED_DETAIL_FORMAT_VERSIONS`, `DetailFormatError`, a fixed-marker renderer, and `require_supported_detail_format_version(text, *, path=None)`. Every semantic run-grade reader in `plan_tool/renderer.py`, `plan_tool/review.py`, `plan_tool/launcher.py`, `plan_tool/detail.py`, `plan_tool/scope_out.py`, `plan_tool/annotate.py`, `plan_tool/completeness_report.py`, `plan_tool/cli/reconcile.py`, `plan_tool/jira.py`, `plan_tool/gates.py`, and `plan_tool/split_criteria.py` gates its read before using the body. `apply_finding` preflights every editable on-disk detail before snapshot or mutation. The parallel completeness dispatcher and each review-walk action handler re-raise a `DetailFormatError` rather than turn it into an isolated per-item result or continue to a sibling. Named command wrappers preserve the format diagnosis; otherwise `DetailFormatError` reaches `plan_tool/cli/app.py:main()`'s new typed handler. `plan_tool/cli/authoring.py:_run_completeness_tail` keeps its ordinary audit warning but re-raises this typed refusal, so a successful authoring write cannot conceal an unsupported sibling during its automatic audit. Broad best-effort boundaries above a semantic reader re-raise this error rather than degrade a prompt, report, audit budget, or apply transaction. Byte-only and same-invocation freshly-authored reads remain untouched. On green, an unsupported or malformed marker stops every command that would interpret the body, with its declared-and-supported diagnosis and no traceback, blank prompt section, partial report, or sibling apply.

## Table of Contents

- [Why](#why) — the read-side half of the detail carrier this step delivers, and why the gate has to be one shared function
- [Files (creates vs edits)](#files-creates-vs-edits) — every file this step touches
- [Implementation](#implementation) — the marker/parser/exception, the routing principle, and the per-file call sites
- [Tests](#tests) — the test cases this step adds, by file
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — the plan-level docs and code seams this step's design follows
- [Applicable guardrails](#applicable-guardrails) — which plan-level fences bind this step
- [Deferred](#deferred) — what steps 4, 5, and 6 own instead

## Why

A detail file has no YAML frontmatter — `DETAIL_FORMAT.md` § Format is explicit that it's pure markdown, a fixed set of H2 sections beneath one H1 — so it has nowhere to put a version declaration the way `Plan.format_version` (step 1) does. The plan's Architecture settles the carrier: a fixed HTML comment, `<!-- plan-tool:detail-format-version: N -->`, on the first non-blank line after the H1, with `## Summary` as the next H2. `plan_tool/roadmap_seed_state.py`'s `_MARKER_PREFIX`/`_MARKER_RE` pair is the in-repo precedent for exactly this shape — a machine-read marker embedded in an otherwise-human markdown body — though it's a different subsystem and not imported here.

Recognizing the marker is only half the job. The plan's Architecture names a long, specific list of consumers that must refuse an unsupported body before using it: run prompt assembly, review and audit prompt construction, deep reconcile, detail quality and every regeneration path that reuses an existing body, scope-out, annotation grounding, completeness reporting, the selected run-reconcile preflight, Jira export, gate suggestion, and split criteria. Each of these today just calls `path.read_text(...)` (sometimes via `resolve_detail_artifact`, sometimes via `derive_detail_path` directly) and hands the string straight to a prompt template, a heuristic, or a deterministic check — there's no shared choke point that could catch a bad marker even if one existed. Putting the parser and the raising logic in one place in `detail_artifacts.py` — the leaf every one of those files already imports from for path resolution — means every consumer adds one line rather than reimplementing the marker grammar a dozen times, and it's the only way `detail_artifacts.py` (the module the plan's Architecture names as owning "the marker parser and the unsupported-version error") can actually be the single source of truth.

The refusal has to be genuinely fail-closed, not a best-effort skip: the plan's Architecture is explicit that "there is no per-step fallback, partial report, or best-effort omission for that error," in contrast to the *existing* missing-file/unreadable-file handling every one of these sites already has, which stays exactly as lenient as it is today. That distinction — an absent or OS-unreadable file degrades gracefully; a present-but-unsupported-version file refuses hard — is the main thing this step's routing has to get right at every site, and it's the opposite of the instinct a reader gets from skimming any of these functions' existing `except OSError: return None`/`continue` blocks.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/detail_artifacts.py` — add `DETAIL_FORMAT_VERSION`, `SUPPORTED_DETAIL_FORMAT_VERSIONS`, `DetailFormatError`, `render_detail_format_version_marker`, `locate_detail_format_carrier`, `require_supported_detail_format_version`, and their private regex/parsing helpers. The named locator is this step's delivered shared surface for the reader, writer, upgrader, and archive-snapshot tests.
- `plan_tool/renderer.py` — gate `_load_detail`'s two `read_text` branches; catch `DetailFormatError`, re-raise `DetailGradeError`, mirroring the function's own jira-grade sibling a few lines above it.
- `plan_tool/review.py` — gate `_resolve_detail_body` (the shared resolver `_read_detail_body`, `check_files_coherence`, `check_detail_body_completeness`, `build_plan_footprint`, `tree_provider`, `detect_suppression_shape`, and `_deliverable_deferred` all route through), `_filter_symbols_by_detail`, `_render_step_detail_block` (feeds `render_review_prompt`), and `_format_audit_detail_bundle`'s run-grade branch (feeds `render_plan_audit_prompt` / `check_plan_audit`). Let `DetailFormatError` propagate uncaught from all four, including through the audit-budget estimator around `render_plan_audit_prompt`.
- `plan_tool/launcher.py` — gate `_run_deep_for_step`'s read; catch `DetailFormatError`, raise `LauncherError` directly (no existing local wrap to mirror here, unlike the render-prompt path, which needs no launcher.py change at all since `renderer.py`'s `DetailGradeError` already funnels through the existing `isinstance(exc, DetailGradeError)` check). Also preflight every extant run-grade detail `apply_finding` can edit before its `_snapshot_text_files` call, so review walks, completeness `--iterate`, and direct apply stop before a snapshot, prompt, model call, or mutation. After an apply, `_compute_findings_delta` also re-raises `DetailFormatError` before its generic synthetic plan-parse-failure fallback can misdiagnose a corrupted detail carrier.
- `plan_tool/detail.py` — gate `collect_detail_quality_findings`'s own read, `_cached_purity_findings`' two `_read_step_detail_body` reads, `merge_steps`' `prior_bodies` read loop, and `_format_sibling_details_block` (sibling-reference authoring context). `DetailFormatError` also escapes `_format_already_implemented_block` and `collect_step_grounding_findings` rather than their ordinary best-effort fallbacks; unrelated exceptions keep those fallbacks. `DetailError` remains reserved for the authoring pipeline's own failures, not a pre-existing artifact's refusal.
- `plan_tool/scope_out.py` — gate `scope_out_step`'s two content reads (the carved step's own detail body, and — for a region carve — each additional carved step's detail body feeding `render_carved_region_seed`). Let `DetailFormatError` propagate uncaught.
- `plan_tool/annotate.py` — gate `_load_step_specs`'s detail-body read; catch `DetailFormatError`, re-raise `AnnotateError`, mirroring step 1's `_try_parse_plan` conversion of `UnsupportedPlanFormatVersionError` so a batch continues past one source's unsupported detail exactly as it continues past one source's unsupported plan version.
- `plan_tool/completeness_report.py` — gate `_read_detail_bodies_for_mass`. `compute_plan_mass_best_effort` re-raises `DetailFormatError` while retaining its ordinary-failure `None` result.
- `plan_tool/cli/reconcile.py` — gate `_read_selected_run_reconcile_detail`; catch `DetailFormatError`, raise `LauncherError`, mirroring its own adjacent `except (OSError, UnicodeDecodeError)` wrap two lines above.
- `plan_tool/jira.py` — gate `_capture_run_grade_step_detail`; catch `DetailFormatError`, raise `JiraError`, mirroring its own adjacent OSError/fence/missing-section `JiraError` raises in the same function.
- `plan_tool/gates.py` — gate `load_step_details` (covers `load_done_details`, which is a thin wrapper over it). Let `DetailFormatError` propagate uncaught.
- `plan_tool/split_criteria.py` — gate `_read_detail_bodies`. Let `DetailFormatError` propagate uncaught — `granularity.py` receives only the already-gated `detail_bodies` this function returns, per the plan's Architecture, and needs no change.
- `plan_tool/cli/gates_cmd.py` — no code change expected (`cmd_suggest_gates` has no broad `except` around its `suggest_gates`/`load_step_details` call chain, so the propagated error already reaches `plan_tool/cli/app.py`'s new handler). Listed here so `tests/test_gates.py`'s command-level addition has a declared home; confirm the no-broad-except claim still holds before treating this as test-only.
- `plan_tool/cli/split_criteria_cmd.py` — no code change expected, same reasoning (`cmd_split_criteria` has no broad `except` around `evaluate_split_criteria`). Listed here so `tests/test_split_criteria.py`'s command-level addition has a declared home.
- `plan_tool/cli/inspect.py` — after step 1 establishes the plan-format `validate` refusal, run `cmd_validate`'s pointer-backed suppression scan before it prints `OK:` and extend that local branch for `DetailFormatError` only. The detail arm prints exactly one `INVALID:` verdict with the named diagnosis and returns exit `1`; the plan arm and ordinary schema-invalid behavior remain step 1's responsibility.
- `plan_tool/cli/authoring.py` — preserve `_run_completeness_tail`'s existing ordinary-exception warning, but re-raise `DetailFormatError` so direct `detail`, `split`, and `merge` commands cannot report success after their automatic audit refuses a bundle detail. The explicit direct-recovery command carries `--recover-refused --no-completeness`, so it skips this whole-bundle tail while it replaces refused targets one at a time.
- `plan_tool/cli/completeness_apply_parallel.py` — preserve worker isolation only for ordinary apply failures. Its guarded worker re-raises `DetailFormatError` so the main dispatcher aborts before it records a failed finding or permits a sibling apply.
- `plan_tool/review_walk.py` — each of its three action handlers re-raises `DetailFormatError` before the generic action-failed display-and-continue branch. Other action exceptions retain the existing interactive continuation behavior.
- `plan_tool/auto_reconcile.py` — preserve its best-effort continuation for ordinary `LauncherError`, but re-raise an error whose cause chain contains `DetailFormatError` instead of logging a per-step skip.
- `plan_tool/cli/app.py` — add `from plan_tool.detail_artifacts import DetailFormatError` and one new `except DetailFormatError as exc:` clause in `main()`, positioned with the other typed command errors (`NarrowError`, `HumanInputError`) ahead of the generic `except Exception` crash handler.
- `tests/test_detail_artifacts.py`, `tests/test_renderer.py`, `tests/test_review.py`, `tests/test_launcher.py`, `tests/test_detail.py`, `tests/test_scope_out.py`, `tests/test_annotate.py`, `tests/test_completeness_report.py`, `tests/cli/test_reconcile_engine.py`, `tests/test_jira.py`, `tests/test_gates.py`, `tests/test_split_criteria.py`, `tests/test_auto_reconcile.py`, `tests/cli/test_inspect_cmds.py`, `tests/cli/test_review_actions.py`, `tests/cli/test_completeness_apply_parallel.py`, `tests/cli/test_completeness_cmd.py`, `tests/cli/test_app.py`, `tests/cli/test_authoring_cmds.py`, `tests/test_review_walk.py` — new test cases per file, enumerated in [Tests](#tests).

## Implementation

### 1. The marker, the parser, and the exception — `plan_tool/detail_artifacts.py`

This is the step's one genuinely new piece of logic; everything else is routing. Add, near the existing path-derivation functions:

```python
DETAIL_FORMAT_VERSION = 1
SUPPORTED_DETAIL_FORMAT_VERSIONS = frozenset({DETAIL_FORMAT_VERSION})

_H1_RE = re.compile(r"^#[ \t]+\S")
_DETAIL_FORMAT_VERSION_MARKER_RE = re.compile(
    r"^<!--\s*plan-tool:detail-format-version:\s*(?P<value>.*?)\s*-->\s*$"
)


class DetailFormatError(Exception):
    """A run-grade detail body declares an unsupported or malformed
    format version at its fixed post-H1 marker slot."""

    def __init__(self, message: str, *, path: Optional[Path] = None) -> None:
        super().__init__(message)
        self.path = path


def render_detail_format_version_marker(version: int = DETAIL_FORMAT_VERSION) -> str:
    """The exact carrier line a run-grade detail writer stamps."""
    return f"<!-- plan-tool:detail-format-version: {version} -->"


def locate_detail_format_carrier(text: str) -> tuple[int, int] | None:
    """Return the H1 and fixed marker-slot line indexes, or None."""


def require_supported_detail_format_version(
    text: str, *, path: Optional[Path] = None
) -> None:
    """Raise DetailFormatError when text's marker declares a version this
    build doesn't support. Resolve a missing marker (including no valid carrier
    H1 or ordinary prose in the slot) to legacy version 1, then check that
    value against ``SUPPORTED_DETAIL_FORMAT_VERSIONS``. It returns None only
    when that effective version is supported.
    """
```

This is a starting point on naming and decomposition, not a mandate — what has to hold:

- **Locate the slot, don't scan the whole body.** `locate_detail_format_carrier(text)` is the one named implementation: it skips leading blank lines, requires the document's first non-blank line to match `_H1_RE` at column 0 (exactly one `#`, whitespace, and content), and returns the H1 plus the first non-blank line strictly after it as the fixed slot (including an insertion position when that later line is absent). `require_supported_detail_format_version`, step 4's parser/stamp, step 6's upgrader, and the archive-snapshot tests all call this helper rather than copying its predicate or slot scan. A non-blank preamble or indented H1 has no valid carrier H1, so marker-shaped text in it is ordinary prose and reads as absent (version 1). Leading blank lines alone do not erase a declared newer marker. Only a line matching the exact `plan-tool:detail-format-version:` prefix in that specific slot is an attempted declaration.
- **A matched marker with a non-integer payload is malformed, not absent.** Reject anything that isn't a bare `-?\d+` string (`re.fullmatch(r"-?\d+", value)` is one way) the same way step 1 rejects a non-`int` `format_version` — refuse, don't default to 1. This is the direct analog of step 1's `type(declared) is not int` guard, adapted for text: there's no YAML type coercion at play here (the marker is always a string), so the check is "does it look like an integer literal," not a type check.
- **The message names both the declared value and the supported set**, matching step 1's `UnsupportedPlanFormatVersionError` message shape and the plan's stated requirement — `str(exc)` is what every wrapping call site (`DetailGradeError`, `LauncherError`, `JiraError`, `AnnotateError`, and `plan_tool/cli/app.py`'s new handler) will surface verbatim or nearly so, so it has to be self-sufficient without the caller adding context beyond a step/path label.
- **Resolve absent then check support.** A missing marker is effective legacy version 1, not an unconditional bypass. Check that value against `SUPPORTED_DETAIL_FORMAT_VERSIONS` just as step 1's plan gate does, so an absent detail retires with version 1 rather than staying readable after a declared `1` refuses. While 1 is supported, absence remains silent — no warning, advisory, or finding — and every existing detail file keeps parsing exactly as it does now.
- **This function validates; it does not read files.** Every call site already has its own `path.read_text(...)` with its own encoding/`errors=`/truncation/missing-file policy — this function takes the text those sites already have in hand and either returns or raises. Don't fold file I/O into it; that would force every call site to change its existing read shape for no benefit, and several sites truncate (`[:max_bytes]`) or use `errors="replace"` differently from each other on purpose.
- **Validate before any truncation is applied.** The marker sits on line 2, well inside any realistic byte budget, but call it on the full text a site just read, before that site's own `[:max_bytes]` slice — not after.

`render_detail_format_version_marker` has one caller in this step's own scope: none — no production code calls it yet, since nothing writes a marker until step 4. It's added here because step 4's `depends_on_notes` says explicitly that step 3 "owns the marker's spelling and its parser, so the writer stamps exactly what the reader accepts rather than restating the recipe" — ship the renderer now so step 4 imports it instead of re-deriving the exact string.

`detail_artifacts.py` stays a leaf: everything above uses only `re`, `dataclasses`-adjacent stdlib, and the module's existing `Path`/`Optional` imports. No new first-party import.

### 2. The routing principle: semantic vs. byte-only, and the fail-closed rule

Not every `path.read_text(...)` near a detail file is a call this step touches. The plan's Architecture draws the line explicitly and this step's audit confirms it holds at every site in scope:

- **Gate a read when the caller interprets the body's content** — feeds it to a prompt template, a heuristic string search, a symbol filter, a section parser, or an acceptance-bullet extractor.
- **Don't gate a read that only touches bytes without interpreting them** — a fingerprint hash, a file-existence/`is_file()` check (`resolve_detail_artifact`, `_resolve_detail_source`, `audit_detail_bundle_status`, `derive_detail_path` used to compute an *output* path before writing), or a path string used only as a label.
- **Don't gate a read of a different artifact class** — a step's declared *source* files (`step.files`/`step.all_files`, read by `_format_files_contents_block`, `_capture_step_file_excerpts`, `heuristic_already_done`, `_collect_done_step_file_contents`), the plan file itself, an existing Jira story/handoff export, or a jira-*grade* detail body (`_capture_jira_grade_step_detail`, `check_jira_grade_bundle`, `_read_detail_body`'s jira-grade branch) — all explicitly out of this plan's scope.
- **Don't gate in-flight or freshly-drafted content that never round-tripped through disk** — `plan_tool/detail.py`'s mixed-step parser (`parse_mixed_step_findings`) receives a model's in-progress response or a candidate body under authoring; `plan_tool/bench.py`'s post-write re-read and lesson distillation receive the body the current writer just stamped in the same invocation, not an independent artifact-input boundary. Neither is in this step's file list, and neither should gain a call.

**The one rule every routed site must preserve: `DetailFormatError` is not the same failure class as "missing," "unreadable," or an ordinary per-item apply failure, and must not be caught by the same clause that handles those.** Place the gate immediately after each read's narrow `OSError` handling. Then trace its error boundary: `plan_tool/detail.py:_format_already_implemented_block`, `plan_tool/detail.py:collect_step_grounding_findings`, `plan_tool/review.py`'s audit-budget estimator, `plan_tool/completeness_report.py:compute_plan_mass_best_effort`, `plan_tool/launcher.py:_compute_findings_delta`, `plan_tool/cli/authoring.py:_run_completeness_tail`, `plan_tool/cli/completeness_apply_parallel.py:dispatch_parallel`'s guarded worker, and `plan_tool/review_walk.py`'s three action handlers each re-raise `DetailFormatError` while retaining their ordinary best-effort or per-item fallback for unrelated failures. The post-edit delta must not replace the typed refusal with its synthetic plan-parse failure. The tail receives the refusal from its direct `cmd_completeness` call and lets it reach `main()`; it does not convert it to a successful-authoring warning. The parallel dispatcher cancels the apply rather than recording a failed worker result, and every review-walk action lets the typed refusal pass its generic display-and-continue branch. The one function this bites hardest is `plan_tool/review.py:_filter_symbols_by_detail`, whose existing docstring says an unreadable detail file "falls through" to return the caller's symbols *unfiltered* — that fallback is correct for `OSError` and would be wrong for `DetailFormatError`: this function reads and interprets the body's prose (a symbol substring search), so it's a semantic reader under the plan's Architecture and must raise, not silently drop the cross-check the way it does for a genuinely absent or unreadable file.

### 3. `renderer.py` — the run-prompt path (mirror the existing jira-grade sibling)

`_load_detail` has two `return detail_path.read_text(...)` / `return resolution.path.read_text(...)` branches. `renderer.py` already has the exact idiom to copy a few lines above `_load_detail`, in the jira-grade loader: it wraps `load_jira_grade_detail`'s `JiraGradeContractError` into `DetailGradeError` with a step-scoped message. Do the same here — after each `read_text`, call `require_supported_detail_format_version`, catch `DetailFormatError`, and raise `DetailGradeError(f"step {step.id} ({step.title}): {exc}")` (or similar) from it.

**No change is needed in `launcher.py` for this path.** `launcher.py`'s `run_step` already has `if isinstance(exc, DetailGradeError): raise LauncherError(str(exc)) from exc` around its `render_prompt(...)` call, reached before the invoker and before the `dry_run` branch — so once `renderer.py` raises `DetailGradeError`, `run` already stops before touching a backend, with no launcher.py edit. `launcher.py`'s own edit is `_run_deep_for_step` only (§4 below), which reads a detail body directly rather than through `render_prompt`.

### 4. `launcher.py` — deep reconcile

`_run_deep_for_step` reads a done step's detail body directly to extract acceptance bullets for the deep-reconcile pass, with `except OSError: return None` as its existing "skip this step's deep pass" fallback. Add the gate call right after the read, outside that `except OSError` block, and on `DetailFormatError` raise `LauncherError` directly — this function has no domain error of its own to wrap into for other reasons, so a direct raise (rather than returning `None`, which would make the caller silently fall back to the reconcile-derived verdict) is the correct fail-closed behavior. Contrast this explicitly with the existing `if step.detail is None: return None` / `if not detail_path.is_file(): return None` lines immediately above it, which are the missing-file best-effort path and stay untouched.

### 5. `review.py` — four independent choke points

- **`_resolve_detail_body`** is already the shared resolver `check_files_coherence` calls, and `_read_detail_body` (its own thin wrapper) is what `build_plan_footprint`, `check_detail_body_completeness`, `tree_provider`, `detect_suppression_shape`, and `_deliverable_deferred` all call for run grade. Gate once, inside `_resolve_detail_body`, right after its `text = path.read_text(...)` line — every one of those callers inherits the refusal for free. `_read_detail_body`'s separate jira-grade branch (guarded by `_is_jira_grade_bundle(detail_grade)`) is untouched.
- **`_filter_symbols_by_detail`** reads a detail body independently of the resolver above (it's a lighter already-implemented-heuristic helper, not routed through `_resolve_detail_body`). Gate it directly, and see the fail-closed note in §2 — don't let it fall into the existing "unreadable → return symbols unchanged" branch.
- **`_render_step_detail_block`** (feeds `render_review_prompt`, i.e. `reconcile-plan`'s prompt) reads `path.read_text(...)` inside its own `try/except OSError`. Gate right after, before the body is truncated and embedded.
- **`_format_audit_detail_bundle`** (feeds `render_plan_audit_prompt` / `check_plan_audit`, i.e. the bare-plan and detail-grounded completeness audit) has two ways to obtain `text` for a given step — a freshly-read `path.read_text(...)`, or an already-captured `audit_input_snapshot.detail_for_step(step.id)` value when an `AuditInputSnapshot` was supplied — and both converge into one `text` variable before the function branches on `jira_grade`. Gate right where that branch happens: in the `else` arm that handles run grade (immediately before the existing `candidates = _derive_symbols(...)` / `build_prompt_excerpt(...)` tail, i.e. the code that runs when `jira_grade` is `False`), so both the fresh-read and the captured-snapshot paths are covered by one call, and the jira-grade arm (which does its own `validate_jira_grade_body` check and is out of scope) is untouched.

All four let `DetailFormatError` propagate uncaught — `plan_tool/review.py` has no existing domain error for this failure class, and `check_plan_audit`/`review_plan_full` have no per-step continuation of their own to preserve (unlike annotate's batch loop). It reaches `plan_tool/cli/app.py`'s new handler.

### 6. `plan_tool/detail.py` — quality, merge, sibling reference

- **Quality**: `collect_detail_quality_findings` reads a step's own detail body directly. `_cached_purity_findings`, a separate module-level cache/reuse helper, makes the two `_read_step_detail_body` calls that feed its reuse decision and cached verdict. Gate `_read_step_detail_body` once — it does `derive_detail_path` then `read_text`, with no existing exception handling to work around — and gate `collect_detail_quality_findings`'s own direct read at its call site.
- **Merge**: `merge_steps` itself collects `prior_bodies` in its `for s in member_steps:` loop, reading each existing member path before it joins the bodies into the explicit `prior_body` input for re-authoring. Gate each of those reads. `_old_to_new` is the dry-run id-arithmetic closure and reads no body; leave it untouched. The merge refusal test calls `merge_steps` (parametrized over either member carrying the marker), not `_old_to_new`.
- **Sibling reference**: `_format_sibling_details_block` renders existing sibling detail files as tone/structure context for a fresh authoring prompt — this is literally the same mechanism that produced the "Existing sibling detail files" section you're reading right now in this very prompt. Gate its read, inside the existing `try/except OSError`'s surrounding scope, same as the other sites.

Leave `_format_files_contents_block` (declared source files, not detail) and `_prepare_run_grade_detail`'s own `plan_path.read_text(...)` (the plan file, not a detail file) untouched. `_generate_detail_concurrent` and `_run_grade_detail_lifecycle` assemble sibling path lists for the prompt; step 4's recovery-only mode suppresses their body context before the already-gated formatter can read it. `parse_mixed_step_findings` receives in-flight model text or a freshly drafted candidate, never an on-disk read — no change.

All three gated spots let `DetailFormatError` propagate uncaught to `plan_tool/cli/app.py`; `plan_tool/detail.py`'s own `DetailError` is reserved for the authoring pipeline's failures (bad response, unparseable output), not a pre-existing artifact's version refusal, and reusing it here would blur that distinction for anyone reading a `DetailError` traceback later.

### 7. `scope_out.py` — the carved-region seed

`scope_out_step` reads the carved step's detail body (and, for a region carve of several steps, each additional carved step's body) to pass as `render_carved_seed`'s / `render_carved_region_seed`'s `detail_body` argument — this is the pure no-Claude seed emitter reading real content for the first time in the pipeline. Gate both reads. `_resolve_detail_source` / `_resolve_carved_detail_path` (path resolution only, no content) are untouched. Let `DetailFormatError` propagate uncaught — `scope_out_step` already returns a `ScopeOutResult`/raises `NarrowError` for its own structural blockers, and adding a raw propagation path here is consistent with those failures already reaching the operator through `plan_tool/cli/app.py`.

### 8. `annotate.py` — batch-preserving conversion

`_load_step_specs` reads a step's detail body while grounding a source's classification. Gate the read, and convert `DetailFormatError` to `AnnotateError` the same way `_try_parse_plan` (step 1) converts `UnsupportedPlanFormatVersionError`:

```python
except DetailFormatError as exc:
    raise AnnotateError(str(exc)) from exc
```

This is the one gated site outside `plan_tool/renderer.py`/`plan_tool/launcher.py`/`plan_tool/jira.py`/`plan_tool/cli/reconcile.py` that needs an explicit wrap rather than raw propagation, because `classify_plan_implementation` is called per-source inside `cmd_annotate`'s batch loop, and that loop already catches `AnnotateError` to record one source's failure and continue independent sources — exactly the behavior the plan's Testing section describes for a detail-level refusal ("batch annotate records the rejected source then continues its independent inputs"). Import `DetailFormatError` alongside the existing `plan_tool.detail_artifacts` usage already present in this module.

### 9. `completeness_report.py`, `gates.py`, `split_criteria.py` — single-site gates, raw propagation

Each of these has exactly one read site in scope, none has a domain error of its own for this failure class, and none runs a per-item continuation loop the way annotate's batch does — a completeness report, a gate-suggestion run, and a split-criteria evaluation are each single-plan operations. Gate the read, let `DetailFormatError` propagate:

- `completeness_report.py:_read_detail_bodies_for_mass`.
- `gates.py:load_step_details` — covers `load_done_details`, a two-line wrapper that calls it directly.
- `split_criteria.py:_read_detail_bodies` — its output already feeds `granularity.py` as `detail_bodies`, which the plan's Architecture names as receiving only already-gated bodies; no change needed in `granularity.py`.

`compute_plan_mass_best_effort` is the common wrapper for both the saved markdown audit report and `completeness-audit --json`. Its previous `except Exception: return None` would erase the newly raised `DetailFormatError` after `_read_detail_bodies_for_mass` correctly detected it. Narrow that wrapper to its stated best-effort domain — missing or unreadable I/O — and explicitly re-raise `DetailFormatError`; an unsupported readable body must reach the command boundary rather than disappear from a mass result. Test the private read and both report and JSON command paths, not only the helper.

### 10. `plan_tool/cli/reconcile.py` and `plan_tool/jira.py` — mirror an adjacent existing wrap

- **`plan_tool/cli/reconcile.py:_read_selected_run_reconcile_detail`** already discards the text it reads (its return type is `None` — it's a pure preflight gate) and already wraps `OSError`/`UnicodeDecodeError` into `LauncherError` two lines below the read. Add the format-version call right after the read, in the same style, raising `LauncherError` on `DetailFormatError`.
- **`jira.py:_capture_run_grade_step_detail`** already wraps `OSError`/`UnicodeDecodeError` into `JiraError`, then separately checks for an unmatched fence and missing required sections, each raising its own `JiraError`. Add the format-version check as a fourth check in that same sequence (after the read, before or alongside the fence check — order between these three checks doesn't matter, since each is an independent hard refusal), raising `JiraError` the same way its siblings do. This is the concrete site the plan's Architecture means by "Jira already uses its `JiraError` route for an invalid run-grade body; it receives the same named format diagnosis there." `_capture_jira_grade_step_detail` (the jira-grade sibling function) is untouched.

### 11. `plan_tool/cli/inspect.py` — validate before it endorses a pointer-backed bundle

`cmd_validate` prints `OK:` and then calls `collect_smell_findings`. Its run-grade `detect_suppression_shape` detector calls `_read_detail_body`; even though `cmd_validate` passes no `plan_path`, every detailed step has a `detail:` pointer and the resolver's pointer-only branch reads that body. Gate that read through step 3's existing `_resolve_detail_body` change and move the smell pass before `OK:`. Step 1 has already added the local `UnsupportedPlanFormatVersionError` handling and its unconditional exit-1 test; extend that branch only for `DetailFormatError`. The detail refusal prints exactly one `INVALID: <path>` verdict followed by the declared-and-supported diagnosis and returns exit `1`; it does not use `--fail-on-findings` to turn an unsafe declared format into a successful validation. Other schema-invalid and advisory-smell behavior stay otherwise unchanged.

### 12. `auto_reconcile.py` — preserve ordinary recovery, not a format refusal

`run_auto_reconcile_on_drift` intentionally catches ordinary `LauncherError` per step and continues its best-effort drift analysis. A detail-format refusal travels there as `DetailFormatError` → `DetailGradeError` → `LauncherError`; continuing on that specific cause would turn the new hard refusal into the per-step skip the plan forbids. Add a small cause-chain predicate local to `auto_reconcile.py` (or equivalent narrow check) and re-raise only a `LauncherError` caused by `DetailFormatError`; leave every unrelated launcher failure on the existing note-and-continue route. This is not another reader gate — `renderer.py` owns the read — it is the failure boundary that keeps the reader's result fail-closed.

### 13. `launcher.py` apply surfaces — reject before the first snapshot

`apply_finding` can target the plan or any detail file, so checking only the selected step during prompt rendering is both too narrow and too late: its existing `_snapshot_text_files(tracked)` runs first. After it has resolved the plan and every current on-disk run-grade detail path it may edit, but before it takes that snapshot, read and gate each body. Missing or non-file paths preserve the existing tracking behavior; a readable unsupported or malformed body raises `DetailFormatError` directly. This one preflight covers the interactive review/reconcile action dispatcher, serial and parallel completeness-apply, and completeness `--iterate`, all of which funnel through `apply_finding`.

The matching post-edit boundary is `plan_tool/launcher.py:_compute_findings_delta`. Its deterministic re-check can first see a malformed marker written by the model after the preflight. Add `except DetailFormatError: raise` ahead of its generic `except Exception` branch; otherwise it manufactures `POST_EDIT_PARSE_FAILURE_ID` and tells the operator the plan frontmatter failed to parse. That synthetic result remains correct for an actual plan parse failure. It must not be moved into a generic post-snapshot deterministic check or converted to a model finding.

### 14. `plan_tool/cli/authoring.py` — an automatic audit cannot conceal a refusal

`_run_completeness_tail` invokes `app.cmd_completeness(...)` directly after
`detail`, `split`, or `merge` writes its body. Keep its existing broad warning
for ordinary audit failures — authoring succeeded and the follow-up remains
best-effort in that case — but add a specific `except DetailFormatError: raise`
ahead of it. The tail does not inspect or replace the typed error and does not
discard the resulting command failure; the surrounding direct command reaches
the app handler in §15. This applies when the tail runs: the direct forced
recovery command carries `--recover-refused --no-completeness`, so it bypasses the tail while it
replaces refused targets sequentially and re-audits only after the last one.
Test a refused sibling during the tail for all three callers through their
shared helper, the no-tail recovery control, then retain an unrelated exception
as the warning-only control.

### 15. `plan_tool/cli/app.py` — the top-level safety net

Add `from plan_tool.detail_artifacts import DetailFormatError` and one new `except DetailFormatError as exc:` clause in `main()`, positioned alongside the other typed command-boundary errors (`NarrowError`, `HumanInputError`) and ahead of the final `except Exception as exc:` crash-traceback handler. This is what actually delivers the plan's stated guarantee for every command that doesn't already wrap the error into its own domain type: `completeness-audit`, `reconcile-plan`, `detail --reconcile`, `scope-out`, `suggest-gates`, `split-criteria`, and the apply surfaces all reach this clause on an unsupported detail body. Print the message (`str(exc)` already names the declared and supported versions), print the recovery direction, and return exit `1`, matching malformed plan input. A `_print_next_steps` pointer at the plan's stated recovery route (`plan-tool detail <slug> --step N --force --recover-refused --commit --no-completeness`) is required here, since recovery must not re-read refused siblings through the automatic tail.

## Tests

For every invariant named above with a reason it must hold this way, name the test after the invariant, not the code path — per this repo's testing convention, already followed by steps 1 and 2's test rosters.

### Tests for this step

`tests/test_detail_artifacts.py` (new `TestDetailFormatVersion` class):

- `test_body_with_no_marker_resolves_to_supported_legacy_and_is_unchanged` — a body with an H1 and `## Summary` immediately after (no marker line at all, matching every existing detail file in this repo) resolves to legacy version 1 and raises nothing while 1 is supported.
- `test_marker_free_body_refuses_when_legacy_version_is_retired` — patch the supported set to exclude 1 and prove a marker-free body raises `DetailFormatError`, matching a body that declares 1.
- `test_body_with_current_version_marker_parses_identically` — a body carrying `<!-- plan-tool:detail-format-version: 1 -->` as the first line after the H1 raises nothing.
- `test_leading_blank_lines_preserve_the_h1_carrier_slot` — a current marker beneath an H1 preceded only by blank lines still parses as current, and an unsupported marker in the same slot refuses; pins that leading whitespace cannot silently downgrade a newer body to absent legacy version.
- `test_body_declaring_unsupported_version_is_refused_by_name` — a marker declaring `999` raises `DetailFormatError`; the message contains `"999"` and the supported-set value.
- `test_malformed_marker_payload_fails_closed` (parametrized over a non-integer payload: empty, `"one"`, `"1.5"`, `"true"`) — each raises `DetailFormatError` rather than being treated as absent.
- `test_body_with_no_valid_carrier_h1_has_no_marker_slot` — text that is empty, starts directly with `## Summary`, or has non-blank preamble before an H1 resolves as absent legacy version 1 even when it contains marker-shaped text elsewhere; it raises nothing while 1 is supported.
- `test_carrier_locator_accepts_only_a_column_zero_h1` — `locate_detail_format_carrier` returns the fixed slot for a blank-prefixed column-0 H1, and returns `None` for an H2-first body, an indented H1, or a non-blank preamble; the reader, writer, upgrader, and archive tests therefore share one H1 decision.
- `test_marker_shaped_text_outside_the_fixed_slot_is_ordinary_prose` — a body whose H1 is followed by ordinary prose (no marker), with a `<!-- plan-tool:detail-format-version: 999 -->`-shaped line appearing later in the body (e.g. inside `## Implementation`), parses as absent (version 1) rather than refusing — pins that only the fixed slot carries meaning.
- `test_unrelated_html_comment_in_the_slot_is_treated_as_absent` — an ordinary `<!-- note to self -->` comment (not matching the `plan-tool:detail-format-version:` prefix) as the first non-blank line after the H1 parses as absent, not malformed.
- `test_render_detail_format_version_marker_round_trips` — `require_supported_detail_format_version` raises nothing on a body built by inserting `render_detail_format_version_marker()` as the first line after the H1 — pins that the renderer and the parser agree on the exact string.
- `test_default_version_is_a_supported_version` — `DETAIL_FORMAT_VERSION in SUPPORTED_DETAIL_FORMAT_VERSIONS`.

`tests/test_renderer.py` (extend `TestCanonicalDetailFallback` or a sibling class):

- `test_run_render_refuses_an_unsupported_detail_marker` — a canonical detail file declaring an unsupported version raises `DetailGradeError` from `render_prompt(mode="run", ...)`, with a message naming the step and the declared version.
- `test_run_render_with_no_marker_reads_the_body_unchanged` — a canonical detail file with no marker (today's shape) still renders its body into the prompt exactly as before this step.

`tests/test_launcher.py`:

- `test_deep_reconcile_refuses_an_unsupported_detail_marker` — `_run_deep_for_step` (or its public caller) raises `LauncherError` rather than falling back to the reconcile-derived verdict, for a done step whose detail declares an unsupported version.
- `test_deep_reconcile_still_falls_back_on_a_missing_detail_file` — the existing "no detail file → return None" behavior is unchanged (a regression guard distinguishing the new hard refusal from the old soft fallback).
- `test_post_edit_delta_reraises_detail_format_error` — after the ordinary preflight succeeds, a fixture writes a malformed fixed-slot marker and `_compute_findings_delta` raises `DetailFormatError` instead of returning `POST_EDIT_PARSE_FAILURE_ID`; a broken plan-frontmatter fixture remains the synthetic-parse-failure control.

`tests/test_review.py`:

- `test_files_coherence_refuses_an_unsupported_detail_marker` — `check_files_coherence` (or `_resolve_detail_body` directly) raises `DetailFormatError` for a step whose detail declares an unsupported version, rather than silently skipping the step's coherence check.
- `test_symbol_filter_refuses_rather_than_falls_through_on_an_unsupported_marker` — `_filter_symbols_by_detail` raises `DetailFormatError`, explicitly distinguished by name from its existing `test_*_falls_through_on_unreadable_detail`-style case for OSError, so the fail-closed-vs-best-effort split is pinned rather than left to be inferred.
- `test_review_prompt_refuses_an_unsupported_detail_marker` — `render_review_prompt` raises `DetailFormatError` when a step's detail declares an unsupported version.
- `test_audit_bundle_refuses_an_unsupported_detail_marker_from_a_fresh_read` — `_format_audit_detail_bundle` raises `DetailFormatError` at run grade when reading directly from disk.
- `test_audit_bundle_refuses_an_unsupported_detail_marker_from_a_captured_snapshot` — the same, but with an `AuditInputSnapshot` supplying the captured text instead of a fresh read — the case naming the two-source gotcha explicitly.
- `test_audit_budget_estimator_reraises_detail_format_error` — a format refusal from `render_plan_audit_prompt` escapes the estimator rather than becoming a silently missing budget advisory.
- `test_audit_bundle_at_jira_grade_ignores_the_run_grade_marker` — a jira-grade artifact whose content happens to be run-grade prose with a version marker in it is judged only by `validate_jira_grade_body`, never by the new run-grade gate — pins that the two grades stay independent.

`tests/test_detail.py`:

- `test_quality_check_refuses_an_unsupported_detail_marker` — `collect_detail_quality_findings` raises `DetailFormatError` for the step under judgment.
- `test_authoring_prompt_boundaries_reraise_detail_format_error` — `_format_already_implemented_block` and `collect_step_grounding_findings` preserve their fallback for an unrelated exception but re-raise a real `DetailFormatError`; pins the error boundaries above their gated review readers.
- `test_merge_refuses_an_unsupported_detail_marker_on_either_side` (parametrized over which of the two merged steps carries the bad marker) — `merge_steps` raises before it constructs `prior_body` or re-authors.
- `test_sibling_reference_block_refuses_an_unsupported_detail_marker` — `_format_sibling_details_block` raises when one sibling detail file declares an unsupported version, rather than silently rendering `"_no sibling detail files yet_"` or skipping just that sibling.
- `test_files_contents_block_ignores_detail_format_version_entirely` — `_format_files_contents_block` (declared source files, not detail) is unaffected by a marker-shaped line inside one of those source files — a negative control proving this step didn't over-gate.

`tests/test_scope_out.py`:

- `test_scope_out_refuses_an_unsupported_detail_marker_on_the_carved_step` — `scope_out_step` raises `DetailFormatError` rather than emitting a `ScopeOutResult` with a truncated or missing carved body.
- `test_region_carve_refuses_an_unsupported_detail_marker_on_any_carved_step` — same, for a multi-step region carve where a non-first carved step carries the bad marker.

`tests/test_annotate.py`:

- `test_unsupported_detail_format_version_is_reported_as_annotate_error` — `classify_plan_implementation` raises `AnnotateError` (converted from `DetailFormatError`) whose message names the declared version, mirroring step 1's equivalent plan-version test.
- `test_batch_continues_past_one_sources_unsupported_detail_marker` (in `tests/cli/test_annotate_cmd.py` if that's where step 1's equivalent batch test landed, else here) — a batch of sources where one source's cited detail file declares an unsupported version fails only that source; sibling sources still annotate.

`tests/test_completeness_report.py`:

- `test_mass_detail_read_refuses_an_unsupported_detail_marker` — `_read_detail_bodies_for_mass` raises `DetailFormatError` for a plan with one step declaring an unsupported version.
- `test_plan_mass_wrapper_propagates_detail_format_error` — `compute_plan_mass_best_effort` re-raises the format refusal while preserving its existing `None` result for a missing or unreadable detail file.

`tests/cli/test_completeness_cmd.py`:

- `test_completeness_report_and_json_refuse_an_unsupported_detail_marker` — the ordinary report path and `--json` both return the typed exit-1 diagnosis rather than persisting or rendering a partial mass result.

`tests/cli/test_inspect_cmds.py`:

- `test_validate_refuses_an_unsupported_pointer_backed_detail_before_printing_ok` — a detailed plan whose suppression scan reaches an unsupported marker returns `1`, prints one `INVALID:` verdict and the diagnosis, and contains no `OK:`.

`tests/test_auto_reconcile.py`:

- `test_auto_reconcile_reraises_a_detail_format_caused_launcher_error` — a `LauncherError` with the real `DetailFormatError` cause chain escapes the per-step loop, while an unrelated launcher failure retains the existing note-and-continue behavior.

`tests/cli/test_reconcile_engine.py`:

- `test_selected_run_reconcile_preflight_refuses_an_unsupported_detail_marker` — `_read_selected_run_reconcile_detail` raises `LauncherError` (not `DetailFormatError` directly) naming the step and the declared version.

`tests/test_jira.py`:

- `test_run_grade_export_refuses_an_unsupported_detail_marker` — `_capture_run_grade_step_detail` (or `export_jira` end to end) raises `JiraError` for a step whose selected run-grade detail declares an unsupported version.
- `test_jira_grade_export_ignores_the_run_grade_marker` — `_capture_jira_grade_step_detail` is unaffected by this step's change (negative control, since jira-grade artifacts are out of scope).

`tests/test_gates.py`:

- `test_gate_suggestion_refuses_an_unsupported_detail_marker` — `load_step_details` (and, by the same code path, `suggest_gates`/`cmd_suggest_gates` end to end) raises `DetailFormatError` rather than silently omitting the step's detail from the prompt the way it does for a missing file.

`tests/test_split_criteria.py`:

- `test_split_criteria_refuses_an_unsupported_detail_marker` — `_read_detail_bodies` (and `evaluate_split_criteria`/`cmd_split_criteria` end to end) raises `DetailFormatError`.

`tests/cli/test_app.py`:

- `test_detail_format_error_is_reported_as_a_known_command_error` — driving `cli.main(...)` through a command that lets `DetailFormatError` propagate uncaught (e.g. `completeness-audit` or `split-criteria` against a plan whose selected step's detail declares an unsupported version) returns exit `1`, prints the declared-and-supported message plus the forced-regeneration recovery on stderr, and prints no `Traceback` — mirrors the existing `test_unmatched_fence_is_reported_as_a_known_command_error` in the same file almost line for line.

`tests/cli/test_authoring_cmds.py`:

- `test_auto_completeness_tail_reraises_detail_format_error` — patch the direct `cmd_completeness` seam to raise `DetailFormatError` and prove the shared tail raises for `detail`, `split`, and `merge` callers rather than printing a successful-authoring warning.
- `test_direct_recovery_skips_the_auto_completeness_tail` — only direct `detail --step N --force --recover-refused --no-completeness` does not invoke the tail while it replaces one refused target; ordinary forced and force-plus-no-completeness routes remain the tail/context-preserving controls.
- `test_auto_completeness_tail_keeps_ordinary_failure_as_warning` — an unrelated exception still prints the existing warning and leaves the authoring result successful; pins the narrow failure split.

`tests/test_launcher.py` and `tests/cli/test_review_actions.py`:

- `test_apply_refuses_unsupported_detail_before_snapshot_or_mutation` — use the direct launcher seam to prove an unsupported sibling stops before `_snapshot_text_files`, then drive one interactive review action to prove the shared preflight reaches its operator boundary without invoking an apply model or editing any file.

`tests/cli/test_completeness_apply_parallel.py`:

- `test_parallel_apply_reraises_detail_format_error_without_recording_a_worker_result` — make the apply seam raise `DetailFormatError` after preflight and prove `dispatch_parallel` aborts rather than returning a failed finding result, emitting a partial report, or applying a queued sibling. An unrelated worker exception remains the negative control that records an isolated failure.

`tests/test_review_walk.py`:

- `test_each_review_walk_action_reraises_detail_format_error` — parameterize the three action modes over an action function that raises `DetailFormatError`; each lets the typed refusal leave the walk instead of printing the generic action-failed message and continuing.
- `test_review_walk_keeps_generic_action_failure_continuation` — an ordinary exception still renders the existing failure message and continues, proving the typed re-raise is narrow.

Every test above must be green before this step is considered finished. They cover exactly the behavior this step changes — the marker/parser/exception in `detail_artifacts.py`, and the refusal reaching every named semantic reader without disturbing the existing missing-file/unreadable-file best-effort paths — and deliberately don't pad the roster with cases (the detail *writer*, `DETAIL_FORMAT.md`'s documentation, the data-contract registry entry, the upgrade entry point) that steps 4, 5, and 6 own.

## Acceptance criteria

- `plan_tool.detail_artifacts` exposes `DETAIL_FORMAT_VERSION`, `SUPPORTED_DETAIL_FORMAT_VERSIONS`, `DetailFormatError`, `render_detail_format_version_marker`, `locate_detail_format_carrier`, and `require_supported_detail_format_version`.
- A run-grade detail body with no marker (every existing detail file in this repo today) is treated as declaring version 1 and parses identically to before this step.
- A marker-free or no-valid-carrier detail body follows the same resolve-then-support-check as a plan with an absent key: it stays silent while legacy 1 is supported and refuses once 1 retires.
- A body declaring the current version parses identically; a body declaring any other value, or a non-integer value, in the fixed marker slot raises `DetailFormatError` naming the declared value and the complete supported-version set.
- A body with no valid carrier H1 has no marker slot and is treated as absent legacy version 1; leading blank lines before a column-0 H1 preserve the slot, while an indented H1, a non-blank preamble, or marker-shaped text anywhere other than the fixed post-H1 slot is ordinary prose and does not independently refuse.
- Every reader named in the plan's Architecture as a semantic run-grade detail consumer — run prompt assembly, review/audit prompt construction, deep reconcile, detail quality, merge, sibling-reference reads, scope-out, annotation grounding, completeness-report mass reads, the selected run-reconcile preflight, Jira export, gate suggestion, and split criteria — refuses an unsupported or malformed marker before using that body's content.
- The broad best-effort boundaries above semantic readers re-raise `DetailFormatError`; no prompt, audit budget estimate, mass report, or post-edit delta silently downgrades the refusal. The guarded parallel-apply worker and each review-walk action handler do the same before their ordinary per-item continuation. An automatic authoring tail re-raises whenever it runs; only direct `--recover-refused --no-completeness` recovery explicitly skips it.
- `apply_finding` preflights every current on-disk run-grade detail it can edit before `_snapshot_text_files`, covering review actions and every completeness apply route; no unsupported body reaches a snapshot, model call, or mutation. A typed refusal from the parallel dispatcher or any review-walk action reaches the command without a partial apply report or sibling application. A post-edit marker corruption re-raises its named error from `_compute_findings_delta`, not a synthetic plan-parse failure.
- `validate` runs its pointer-backed suppression scan before it prints `OK:`; after step 1's plan-format arm is in place, an unsupported marker instead produces exactly one detail-format `INVALID:` verdict and exit `1`.
- The drift-halt auto-reconcile path propagates a detail-format-caused `LauncherError` rather than turning it into a per-step best-effort skip, while unrelated launcher failures retain their existing recovery behavior.
- `run` never invokes its backend on a step whose selected detail carries an unsupported marker; `suggest-gates` and `split-criteria` return their existing non-zero command-error outcome with no partial recommendation or criterion report.
- Every refusal reaches its operator as the declared-and-supported diagnosis through an established command error (`DetailGradeError`/`LauncherError`, `LauncherError`, `JiraError`, `AnnotateError`) or `plan_tool/cli/app.py`'s new typed handler — never as an unexpected-error traceback; the app handler returns exit `1` and names forced regeneration as recovery.
- Missing and unreadable detail files keep their exact existing best-effort behavior at every gated site; only a *present, readable, unsupported-or-malformed* body newly refuses.
- Batch `annotate` continues past one source's unsupported detail marker exactly as it continues past one source's unsupported plan version (step 1), recording a named per-source failure.
- `granularity.py`, jira-grade readers (`_capture_jira_grade_step_detail`, `check_jira_grade_bundle`, `_read_detail_body`'s jira-grade branch), source-file excerpt renderers, fingerprint/path-only consumers, and in-flight/freshly-drafted body consumers (`parse_mixed_step_findings`, `bench.py`'s post-write re-read) are unaffected by this step.

## References

- `plan_tool/roadmap_seed_state.py:render_seed_state_marker` (and its `_MARKER_RE`) — the in-repo precedent for a machine-read marker embedded in a markdown body; a different subsystem, not imported here.
- `DETAIL_FORMAT.md` § Format, § Path convention — the pure-markdown, no-frontmatter contract the new carrier must respect without altering.
- `plan_tool/jira_grade.py` — the sibling artifact-class contract this step's `DetailFormatError`/`require_supported_detail_format_version` shape mirrors (`JiraGradeContractError`, `load_jira_grade_detail`), and the module every consumer of a run-grade body already imports alongside for grade selection.
- `docs/implementation-plans/plan-details/authored-artifact-format-version/01-accept-fixed-plan-format-version-field.md` — the plan-class precedent for the gate-then-refuse shape (`UnsupportedPlanFormatVersionError`, `_require_supported_plan_format_version`, the `_try_parse_plan` conversion this step's `annotate.py` change mirrors for the detail class).
- `DATA_CONTRACT.md` § "Version-evolution policy" — the fail-closed reading rule ("readers fail closed; they never guess a version") this step's gate follows for the detail class.

## Applicable guardrails

- **The plan's "## Scope guardrails" binary-observable rule.** `require_supported_detail_format_version` checks exactly one thing — is the declared marker value one this build supports — and every routed call site must not grow into a check of whether the rest of the body's content matches what that version implies.
- **The plan's "## Scope guardrails" not-allowed list.** No advisory or warning for a *supported* declaration; no inferring, repairing, or upgrading a version at read time (a malformed or unsupported value always refuses, never defaults); no fallback that feeds an unsupported body to a command — every routed site raises before the body reaches a prompt, heuristic, or report, with `run` and Jira preserving their own named error results rather than gaining a generic fallback.
- **The plan's "## Out of scope" carve-outs.** This step must not touch jira-grade readers, the four staged roadmap artifacts, or `roadmap_source_identity.py`'s unrelated `CanonicalSourceIdentity.format_version`; must not add any version other than 1 to the supported set; must not add a migration engine or a concrete upgrade mechanism (step 6); and must not declare the detail *grade* in the marker.

## Deferred

- Making `plan_tool/detail.py` the sole writer of the marker, and stamping it into every freshly authored detail file — step 4, which depends on this step's marker spelling and parser.
- `DETAIL_FORMAT.md`'s description of the marker and its refusal — step 4.
- The `data_contract.py` version-only registry entry and the class-specific rules in `DATA_CONTRACT.md` for the detail class — step 5, which names this step's `DETAIL_FORMAT_VERSION`/`SUPPORTED_DETAIL_FORMAT_VERSIONS` constants.
- The explicit absent-to-1 raw-body upgrade entry point and its coverage test — step 6, including the refusal for a raw body with no valid carrier H1 (this step's reader treats that document as absent/version-1 for *reading* purposes; step 6's upgrader is a separate, explicitly invoked action that refuses that shape rather than synthesizing a carrier).
- Content-conformance checking (whether a body's actual shape matches its declared version), any warning on a supported version, and any repair-on-read behavior — permanently out of scope per the plan's Scope guardrails, not a later step's work.
- Removing `BACKLOG.md` #356 and updating `CLAUDE.md`'s format-doc bullets — step 7.
