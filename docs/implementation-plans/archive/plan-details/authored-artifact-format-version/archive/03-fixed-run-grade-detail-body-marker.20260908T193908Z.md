> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add the fixed run-grade detail body marker and shared parser to detail_artifacts.py, then route every semantic run-grade detail read through its refusal

## Summary

`plan_tool/detail_artifacts.py` gains the run-grade detail class's format-version contract: the fixed marker text `<!-- plan-tool:detail-format-version: N -->` (the first non-blank line after a body's H1, `## Summary` next), a parser that reads it, and a `DetailFormatError` a caller raises when the effective version is unsupported. No writer exists yet — that's step 4 — so every detail file on disk today is unmarked and reads as absent, which this step's gate treats as version 1. The bulk of the work is routing: fourteen other production files (`renderer.py`, `review.py`, `launcher.py`, `detail.py`, `scope_out.py`, `annotate.py`, `completeness_report.py`, `cli/reconcile.py`, `jira.py`, `gates.py`, `split_criteria.py`, `cli/gates_cmd.py`, `cli/split_criteria_cmd.py`, `cli/app.py`) each call the new gate immediately after a successful read of a run-grade body, at every site that *interprets* that body rather than merely hashing or path-deriving it. On green, nothing observable changes for the existing, unmarked detail bundle: every current plan's `run`, `reconcile-plan`, `completeness-audit`, `detail`, `scope-out`, `annotate`, `jira`, `suggest-gates`, and `split-criteria` behave exactly as today. The new behavior is dormant until a hand-edited or future-built detail file declares a version this build doesn't support, at which point the operation that would have read it stops before using the body and the operator sees a named diagnosis instead of a crash or a silently wrong result.

## Table of Contents

- [Why](#why) — the gap this step closes and why the gate has to be shared rather than reimplemented per file
- [Input](#input) — the plan-level Architecture contract this step must implement exactly, not redesign
- [Files (creates vs edits)](#files-creates-vs-edits) — every file this step touches
- [Implementation](#implementation) — the marker/parser/error shape, the fail-closed rule, and the per-file routing
- [Tests](#tests) — the test cases this step adds, file by file
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — plan-level docs and the in-repo precedents this step follows
- [Applicable guardrails](#applicable-guardrails) — the plan-level scope fence bound to this step
- [Deferred](#deferred) — what this step deliberately does not do

## Why

`DETAIL_FORMAT.md` fixes a detail file's shape as pure markdown, no frontmatter, with the H1 required as the first non-blank line. That leaves no field to carry a format-version declaration the way `Plan.format_version` (step 1) does for the plan class — the detail class needs an in-band marker instead, and it needs one parser and one error type that every consumer shares, or the same recognition rule (and the same bugs) get reimplemented fifteen times. Right now, fifteen production files read a run-grade detail body's text and interpret it — for a run prompt, a review/audit prompt, a merge combine input, a carved seed, an annotation spec, a mass-completeness scan, a Jira export, a suggested gate, a split-criteria evaluation — and none of them has anywhere to ask "is this a version I understand?" before trusting the bytes. `plan_tool/detail_artifacts.py` is the existing shared leaf for "where is this step's detail file, and is it there" (`resolve_detail_artifact`); this step extends it to also answer "and is its declared version one this build supports," so every reader asks the same question the same way.

## Input

The plan's `## Architecture` section (`docs/implementation-plans/2-authored-artifact-format-version.md`) fixes the carrier's spelling and placement as a **plan-level, not step-level, decision**: exactly `<!-- plan-tool:detail-format-version: N -->` as the first non-blank line after the H1, with `## Summary` as the next H2, and states that "a later version may change other structure but must leave the carrier where an older reader looks." This step implements that exact spelling and position — it does not choose or redesign it. The Architecture section also fixes:

- **absent → 1**, by an explicit default the gate itself applies (not a `Step`/schema default, since detail files have no schema);
- **the gate runs on body text after a successful read**, never inside the existing missing/unreadable handling each consumer already has;
- **the reader list** this step routes: run prompt assembly, review/audit prompt construction, deep reconcile, semantic detail regeneration/quality/merge/sibling-reference/lesson-distillation reads, scope-out, annotation grounding, completeness-report mass reads, the selected run-reconcile preflight, Jira export, gate suggestion, and split criteria — with `granularity.py` explicitly named as *not* a reader (it only receives bodies `split_criteria.py` already gated) and `bench.py` explicitly named as *not* gated (post-write self-verification of the same-invocation body, not an independent artifact-input boundary — and `bench.py` isn't in this step's file list either).

The in-repo precedent for a machine-read marker embedded in a markdown/text body is `plan_tool/roadmap_seed_state.py`'s `render_seed_state_marker` / `_marker_payload` pair (an HTML-comment-wrapped JSON payload, found and validated by regex). This step's marker differs from that precedent in one deliberate way worth calling out: `roadmap_seed_state._MARKER_RE.search(text)` finds its marker *anywhere* in the text, because a roadmap seed's lifecycle comment can legitimately sit anywhere in a promoted file. This step's marker must instead be recognized *only* at the fixed post-H1 position — the plan's `## Scope guardrails` says a marker-shaped line anywhere else "is ordinary prose" — so the parser here is positional-by-design (anchored to the H1), not a document-wide search, which is what keeps a detail body's own prose (including a body that *discusses* this format-version feature, as this repo's own detail files sometimes discuss code strings) from accidentally tripping the gate.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/detail_artifacts.py` — add the marker constant/regex, `DETAIL_FORMAT_VERSION`, `SUPPORTED_DETAIL_FORMAT_VERSIONS`, `DetailFormatError`, the marker parser, and the shared gate function.
- `plan_tool/renderer.py` — gate `_load_detail`'s two run-grade `read_text` returns.
- `plan_tool/review.py` — gate `_resolve_detail_body`, `_format_audit_detail_bundle`, and `_filter_symbols_by_detail`.
- `plan_tool/launcher.py` — gate `_run_deep_for_step`'s direct read; extend `run_step`'s existing `DetailGradeError` conversion to also catch the new error.
- `plan_tool/detail.py` — gate `collect_detail_quality_findings`, `_read_step_detail_body` (covers `_cached_purity_findings`), `_format_sibling_details_block`, the inline `merge_steps` prior-body read, and `_capture_detail_lessons_after_validation`'s re-read.
- `plan_tool/scope_out.py` — gate the two inline `detail_path.read_text(...)` sites in `scope_out_step` (single-step and multi-step carve).
- `plan_tool/annotate.py` — gate `_load_step_specs`'s read, converted to the existing `AnnotateError` boundary.
- `plan_tool/completeness_report.py` — gate `_read_detail_bodies_for_mass`.
- `plan_tool/cli/reconcile.py` — gate `_read_selected_run_reconcile_detail`, converted to `LauncherError`.
- `plan_tool/jira.py` — gate `_capture_run_grade_step_detail`, converted to `JiraError`.
- `plan_tool/gates.py` — gate `load_step_details` (covers `load_done_details`), propagated (not swallowed like a missing file).
- `plan_tool/split_criteria.py` — gate `_read_detail_bodies`, propagated; update its docstring's "never a raise" claim.
- `plan_tool/cli/gates_cmd.py` — no new `except`; confirm `DetailFormatError` propagates uncaught to `cli/app.py` (document the expectation with a test, since this file currently has no `except` clause around its domain call at all).
- `plan_tool/cli/split_criteria_cmd.py` — same as above, no local catch.
- `plan_tool/cli/app.py` — add one new `except DetailFormatError as exc:` clause in `main()`'s dispatch chain, mirroring the existing `except NarrowError as exc:` clause immediately before it.

## Implementation

### The marker, the parser, and the error — `detail_artifacts.py`

Add, alongside the existing leaf's constants:

- `DETAIL_FORMAT_VERSION = 1` — the current version this build's (future, step-4) writer stamps.
- `SUPPORTED_DETAIL_FORMAT_VERSIONS` — a `frozenset` a reader accepts; at version 1 this holds only `{DETAIL_FORMAT_VERSION}`. Shape it as a set now (not a bare `int ==` check) so a later version's "current and current-minus-one" window (the plan's stated support-window rule) is a one-line change here, not a signature change at every call site — but do not implement that window now; there is no version 2.
- The fixed marker text, exactly `<!-- plan-tool:detail-format-version: N -->` — a constant prefix (`<!-- plan-tool:detail-format-version:`) plus a regex anchored to the whole stripped line, matching the plan's literal spelling verbatim. This spelling is not this step's to choose; it's already fixed by the plan's Architecture section, and step 4's writer will import it from here rather than restating it.
- `DetailFormatError(Exception)` — carries the message plus enough structure (e.g. `declared`, and an optional `path` for a friendlier default message) that a caller building its own contextual message (as `jira.py` and `cli/reconcile.py` already do for their own read failures) has what it needs without re-deriving it. This is a new, independent exception type — it is not a subclass of `DetailGradeError` (renderer.py's existing grade-selection/fence error) or of anything else. The two names are easy to confuse; they mean different things (grade = run vs. jira; format = version) and this step must not merge or subclass one into the other.
- A marker parser, something like `declared_detail_format_version(body: str) -> Optional[int]`: find the H1 line (mirror, don't import, the H1-recognition regex — `detail_artifacts.py` cannot import `detail.py`, the same "mirror the fence/heading scan rather than pull in a heavier module" pattern `plan_tool/reprocess.py`'s `_split_frontmatter_for_rewrite` already uses against `parser.py`); if there is none, return `None` (no carrier slot — the plan's guardrail: "a body with no H1 has no carrier slot"). Otherwise take the next non-blank line after the H1. If it fully matches the marker regex, return the parsed integer. If it starts with the marker's literal prefix but does not fully match (extra text, a non-integer value, a missing `-->`), raise `DetailFormatError` — a malformed declaration refuses rather than defaulting, per the plan's guardrail. If the slot line doesn't start with the prefix at all, it's ordinary prose in the marker's position (e.g. a body that goes straight from the H1 to `## Summary`); return `None`.
- A shared gate, something like `require_supported_detail_format_version(body: str) -> None`: call the parser above (which may raise for a malformed slot), default `None` to `DETAIL_FORMAT_VERSION`, and raise `DetailFormatError` naming the declared value and `SUPPORTED_DETAIL_FORMAT_VERSIONS` when the effective version isn't in the supported set. This is the one function every one of the fourteen other files calls; nothing else in this step needs to touch the parser directly.

The check does not validate anything about the body's *content* beyond the marker line itself — no schema check, no agreement check between the declared version and the body's actual shape (the plan's `## Scope guardrails` explicitly forbids that).

### The governing rule: fail-closed refusal, not another missing-file case

Every one of the fourteen call sites below already has an established policy for "the file is missing" or "the file is unreadable" — some render a placeholder ("_No detail file for this step…_"), some silently omit the step from a dict, some skip a quiet-probe function back to an empty result. **None of those policies change.** The new gate call sits *after* a read has already succeeded (so it never fires for missing/unreadable — those still short-circuit exactly as they do today) and its failure is never folded into any of those existing graceful paths. A `DetailFormatError` must propagate out of the function that read the body, aborting the operation that function is part of, exactly as the plan's `## Scope guardrails` states: "there is no per-step fallback, partial report, or best-effort omission for that error."

This matters most at the sites whose existing missing-file behavior is a *quiet, non-raising* fallback, because those are the ones where the natural-looking edit — catching the new error the same way the surrounding code already catches `OSError` — would be wrong:

- `detail.py:collect_detail_quality_findings` — today, no pointer or a missing file returns `[]` (a legitimate "nothing to check yet" signal the caller uses as a quiet probe). An unsupported-version body must **not** also return `[]`: that would read as "zero findings, this body is clean," which is actively misleading for a body this build refuses to interpret. It must raise.
- `detail.py:_format_sibling_details_block` — today, an unreadable sibling renders `"### `name` _(unreadable: {exc})_"` inline and the render continues with the other siblings. An unsupported-version sibling must not render as one more inline "unreadable" note among otherwise-fine siblings; the whole `render_detail_prompt` call must fail, because a tone/structure reference the tool can't actually interpret is not a degraded-but-usable reference.
- `gates.py:load_step_details` — today, `continue`s past a missing/unreadable file (best-effort; the prompt still carries title/files/change_type). An unsupported-version body must instead abort `load_step_details` (and therefore `suggest_gates`) entirely — the plan calls `suggest-gates` a "command-boundary refusal" explicitly.
- `split_criteria.py:_read_detail_bodies` — same shape as `gates.py`, plus its own docstring currently says "never a raise"; update that line, since it stops being true.
- `annotate.py:_load_step_specs` — today, a missing/unreadable spec becomes `spec_body = ""`. An unsupported-version spec must raise instead.
- `completeness_report.py:_read_detail_bodies_for_mass` — today, `except OSError: continue`. An unsupported-version body must abort `compute_plan_mass` for the whole plan, not just drop one step's contribution.
- `launcher.py:_run_deep_for_step` — today, no pointer / missing file / `OSError` on read all return `None`, and the caller falls back to the reconcile-derived verdict. An unsupported-version body must not fall back the same way — deep verification would silently substitute a weaker verdict for a body it never actually read.

Because `DetailFormatError` is not an `OSError` subclass, most of these sites need no change to their existing `except OSError:` clause at all — placing the gate call right after the successful `read_text(...)` (inside or immediately after the existing `try`) means an `OSError` still takes the old path and a `DetailFormatError` naturally escapes uncaught. The two places that need an explicit, deliberate distinction are `collect_detail_quality_findings` and `_format_sibling_details_block`, where the *existing* missing/unreadable handling is not exception-based (it's an early `if`/inline check), so the gate's raise has to be added as new code, not just left to fall through an existing `except`.

### Command-boundary conversion — where a raw `DetailFormatError` becomes a command result

Three sites already convert a lower-level read failure into their own command-specific error type, using a pattern this step's gate slots into directly rather than needing a new mechanism:

- **`launcher.py:run_step`** already special-cases `DetailGradeError` inside its `prompt_build` phase's `except Exception as exc:` block (`isinstance(exc, DetailGradeError): raise LauncherError(str(exc)) from exc`) — reached before the `dry_run` branch and before any invoker call, per the project's own accumulated lesson on this exact code path. Extend that `isinstance` check to also match `DetailFormatError` (either a second branch or a tuple check), so a gate failure inside `renderer.render_prompt` → `_load_detail` becomes a `LauncherError` the same way, and `run` never reaches the backend on this refusal. `_run_deep_for_step`'s own direct read needs the same conversion at its own call site (it isn't inside `run_step`'s `prompt_build` try) — whatever wraps its call must convert an escaping `DetailFormatError` to `LauncherError` rather than letting it surface as an unrelated Python traceback.
- **`jira.py:_capture_run_grade_step_detail`** already raises `JiraError` for an unreadable, fence-broken, or section-incomplete selected detail ("a *present* selected detail must always be usable," per its own docstring). Add the gate call right after the successful `text = path.read_text(...)`, before the fence check, and convert a `DetailFormatError` there into the same kind of `JiraError` the function already raises for its other present-but-broken cases.
- **`cli/reconcile.py:_read_selected_run_reconcile_detail`** already wraps `resolution.path.read_text(...)` in a `try`/`except (OSError, UnicodeDecodeError)` that raises `LauncherError`. Today the read result is discarded (assigned to nothing) — capture it, run the gate against it, and convert a `DetailFormatError` into `LauncherError` the same way its sibling `except` clause already does.

Every other site (`review.py`'s three, `detail.py`'s remaining four, `scope_out.py`, `annotate.py`, `completeness_report.py`, `gates.py`, `split_criteria.py`) lets `DetailFormatError` propagate raw, uncaught by any local `except Exception` (verify this at each site — `authoring.py`, `review_cmd.py`, `reconcile.py`, and others carry narrow, commented `except Exception:` blocks for unrelated fail-soft purposes; none should sit between a gated read and its caller's command boundary, but confirm rather than assume at HEAD) up to `cli/app.py`'s `main()`. Add one new clause there:

```
except DetailFormatError as exc:
    ...
    return 2
```

placed immediately beside the existing `except NarrowError as exc:` clause (same position in the dispatch chain, same shape: print the diagnosis, return the standard command-error exit) — before the final `except Exception as exc:` catch-all that saves a crash traceback and prints "unexpected error: …". This is what makes `suggest-gates` and `split-criteria` — whose CLI wrappers (`cli/gates_cmd.py`, `cli/split_criteria_cmd.py`) have no `except` clause of their own around the domain call at all — surface the refusal as a clean command error rather than a crash-file traceback, without either wrapper needing new code.

### Explicitly not gated

- **Fingerprints and path metadata** — `review_persistence.compute_plan_fingerprint`, `fingerprint.compute_detail_bundle_fingerprint`, and anything that only hashes bytes or derives a path never reads for meaning and does not gate.
- **`detail.py:_archive_orphan_details`** — pure filename-pattern `Path.rename`, no content read.
- **`detail.py:_detail_step_input_hash`** — already documented as excluding file contents from its cache key.
- **`detail.py:parse_mixed_step_findings`** — both call sites pass it the in-flight Claude response (`raw`) or a freshly drafted candidate body, never an on-disk artifact. It is a downstream evaluator of text this step's own authoring flow just produced, not a reader of a possibly-unsupported on-disk file.
- **`launcher.py:apply_finding`**'s pre/post detail-body snapshot (`_snapshot_text_files`) — read for byte-level diff/revert bookkeeping only, the same "byte-only, not interpreting" carve-out the plan gives fingerprints.
- **`split_criteria.py` → `granularity.py`** — `granularity.GranularityEvidence(detail_bodies=...)` receives bodies `split_criteria._read_detail_bodies` already gated; `granularity.py` itself needs no changes and is not in this step's file list.
- **`review.py:audit_detail_bundle_status`** — presence-only (`resolution.on_disk`), no content read; unchanged.

## Tests

### Tests for this step

`tests/test_detail_artifacts.py`:
- `test_absent_marker_defaults_to_current_version` — a body with an H1 and `## Summary` immediately after it (no marker line) reads as `DETAIL_FORMAT_VERSION`.
- `test_supported_declared_version_passes_silently` — a body with a well-formed marker declaring `DETAIL_FORMAT_VERSION` passes the gate with no exception.
- `test_unsupported_declared_version_raises_naming_declared_and_supported` — a hand-built body declaring a version outside `SUPPORTED_DETAIL_FORMAT_VERSIONS` raises `DetailFormatError` whose message names both the declared value and the supported set.
- `test_malformed_marker_in_slot_refuses_rather_than_defaulting` — a line starting with the marker's literal prefix but failing to parse (non-integer value, missing closing `-->`) in the fixed slot raises, and does *not* silently resolve to version 1.
- `test_marker_shaped_text_outside_the_slot_is_ordinary_prose` — a marker-shaped line appearing later in the body (not immediately after the H1) is not read as a declaration; the gate passes as absent.
- `test_body_with_no_h1_has_no_carrier_slot` — a body with no H1 line at all never raises for a "malformed marker," even if some line elsewhere happens to start with the marker prefix; it reads as absent.
- `test_marker_slot_is_the_first_non_blank_line_after_h1_not_the_immediately_next_line` — a body with one or more blank lines between the H1 and the marker still recognizes the marker (skips blank lines, doesn't require zero gap).

`tests/test_renderer.py`:
- `test_run_render_raises_on_unsupported_pointer_detail_version` — a pointer-set detail file declaring an unsupported version raises (not the "_No detail file…_" placeholder path).
- `test_run_render_raises_on_unsupported_canonical_detail_version` — same, for the pointer-unset/canonical-resolution branch.
- Existing missing/absent tests (`test_absent_canonical_file_still_reports_no_detail`, `test_set_pointer_never_falls_back_to_canonical`, etc.) stay green unmodified — pin that the new gate never fires on a missing file.

`tests/test_review.py`:
- `test_resolve_detail_body_raises_on_unsupported_version` — `_resolve_detail_body` propagates rather than returning a body for a check to silently judge.
- `test_format_audit_detail_bundle_raises_on_unsupported_version` — the plan-audit prompt build stops rather than embedding an unreadable-by-version body.
- `test_filter_symbols_by_detail_raises_rather_than_falling_through_unfiltered` — the bare-vs-detailed heuristic does not fall back to its existing "no detail" unfiltered behavior for an unsupported version.

`tests/test_launcher.py`:
- `test_run_step_converts_detail_format_error_to_launcher_error_before_invoker` — mirrors the existing `DetailGradeError` conversion test; assert the fake invoker is never called (invariant: a format refusal never reaches the backend).
- `test_run_deep_for_step_raises_on_unsupported_version_rather_than_falling_back` — asserts this is distinct from the missing-detail case, which still returns `None` and falls back to the reconcile-derived verdict.

`tests/test_detail.py`:
- `test_collect_detail_quality_findings_raises_rather_than_returning_empty_for_unsupported_version` — named to state the invariant directly: an unsupported version is not the same outcome as "nothing to check yet."
- `test_format_sibling_details_block_raises_rather_than_rendering_unreadable_note` — an unsupported sibling is not folded into the existing per-sibling "_(unreadable: …)_" tolerance.
- `test_merge_steps_raises_on_unsupported_folded_member_detail` — the prior-body combine read propagates.
- `test_capture_detail_lessons_after_validation_raises_on_unsupported_reread` — defense-in-depth for the post-write re-read (low practical likelihood since this reads back what the current build just wrote, but explicitly covered per the plan's reader list).

`tests/test_scope_out.py`:
- `test_scope_out_step_raises_on_unsupported_single_carve_detail`
- `test_scope_out_step_raises_on_unsupported_region_carve_detail` — the multi-step carve loop.

`tests/test_annotate.py`:
- `test_load_step_specs_raises_on_unsupported_version`
- `test_classify_plan_implementation_surfaces_unsupported_detail_as_annotate_error` — the conversion boundary, mirroring how step 1's `UnsupportedPlanFormatVersionError` → `AnnotateError` conversion already works for the plan's own version.

`tests/test_completeness_report.py`:
- `test_read_detail_bodies_for_mass_raises_on_unsupported_version` — `compute_plan_mass` aborts rather than omitting the one step.

`tests/cli/test_reconcile_engine.py`:
- `test_read_selected_run_reconcile_detail_raises_launcher_error_on_unsupported_version` — mirrors the existing unreadable-detail `LauncherError` case for this same function.

`tests/test_jira.py`:
- `test_capture_run_grade_step_detail_raises_jira_error_on_unsupported_version` — mirrors the existing unreadable/fence/missing-section `JiraError` cases in the same function.

`tests/test_gates.py`:
- `test_load_step_details_raises_rather_than_omitting_unsupported_step` — contrast with the existing best-effort omission for a missing file.
- `test_suggest_gates_propagates_unsupported_version_without_partial_recommendations` — no gate suggestions are emitted for the plan when one done step's detail is unsupported.

`tests/test_split_criteria.py`:
- `test_read_detail_bodies_raises_rather_than_omitting_unsupported_step`
- `test_evaluate_split_criteria_propagates_unsupported_version` — end-to-end through `evaluate_split_criteria`.

`tests/cli/test_app.py`:
- `test_detail_format_error_prints_diagnosis_and_returns_command_error_exit` — mirrors the existing unmatched-fence test (`test_unmatched_fence_is_reported_as_a_known_command_error`): drive a command whose domain call raises `DetailFormatError` (e.g. via `suggest-gates` or `split-criteria` against a hand-built unsupported detail fixture) through `cli.main`, assert the exit code, the printed diagnosis, and `"Traceback" not in captured.err`.

Every test listed above must be green before this step is considered done; run `uv run pytest tests/ -q -n auto` (or the affected subset during iteration) per `test_command` in the plan frontmatter.

## Acceptance criteria

- `detail_artifacts.py` exposes the fixed marker text `<!-- plan-tool:detail-format-version: N -->`, `DETAIL_FORMAT_VERSION`, `SUPPORTED_DETAIL_FORMAT_VERSIONS`, `DetailFormatError`, a marker parser, and a shared gate function.
- A body with no marker (every detail file in this repo today) reads as `DETAIL_FORMAT_VERSION` and every currently-existing plan's `run`, `reconcile-plan`, `completeness-audit`, `detail`, `scope-out`, `annotate`, `jira`, `suggest-gates`, and `split-criteria` behave exactly as before this step, since no writer exists yet to declare anything else.
- A body with no H1 has no carrier slot; a marker-shaped line anywhere in such a body is ordinary prose and never raises.
- A marker-shaped line outside the fixed post-H1 slot (H1 present, but the marker isn't the first non-blank line after it) is ordinary prose and never raises.
- A well-formed marker declaring a supported version passes the gate with no exception.
- A malformed marker occupying the fixed slot (prefix present, parse fails) raises `DetailFormatError` rather than defaulting to version 1.
- A well-formed marker declaring an unsupported version raises `DetailFormatError` naming both the declared value and the supported set.
- Every listed site in `renderer.py`, `review.py`, `launcher.py`, `detail.py`, `scope_out.py`, `annotate.py`, `completeness_report.py`, `cli/reconcile.py`, `jira.py`, `gates.py`, and `split_criteria.py` calls the shared gate immediately after a successful read and before using the body for anything semantic; each site's existing missing-file/unreadable-file behavior is unchanged.
- `run` never invokes the backend when the selected step's detail fails the gate; the refusal surfaces as `LauncherError`.
- Jira export surfaces the refusal as `JiraError`; the selected run-reconcile preflight surfaces it as `LauncherError`.
- `suggest-gates` and `split-criteria` emit no partial recommendation/criterion output when a relevant step's detail fails the gate; the refusal propagates uncaught through their CLI wrappers to `cli/app.py`.
- `cli/app.py`'s `main()` gains a `DetailFormatError` handler, positioned like the existing `NarrowError` handler, that prints the named diagnosis and returns the standard command-error exit with no crash traceback and no "unexpected error" fallback text.
- Fingerprint/path-metadata reads, `apply_finding`'s snapshot diffing, `detail.py`'s in-flight-response consumers (`parse_mixed_step_findings`), and `granularity.py` remain ungated, unchanged.

## References

- `docs/implementation-plans/2-authored-artifact-format-version.md` — this plan's own `## Architecture` and `## Scope guardrails`, the authoritative source for the marker's exact spelling, position, and the fail-closed/no-fallback rules this step implements.
- `DETAIL_FORMAT.md` § Format — the pure-markdown, H1-first contract the marker's fixed post-H1 slot sits inside.
- `DATA_CONTRACT.md` § "Version-evolution policy" — the fail-closed reader rule this step's gate follows (a later step registers the constant here; this step just obeys the policy).
- `plan_tool/roadmap_seed_state.py:render_seed_state_marker` / `_marker_payload` — the in-repo precedent for an HTML-comment marker embedded in a markdown body, and the deliberate contrast (search-anywhere there vs. fixed-position here).
- `plan_tool/jira_grade.py` — this repo's template for a deterministic contract-violation type (a frozen finding/error carrying enough context to render a message, a never-raising low-level check paired with a raising `load_*` wrapper) that this step's `DetailFormatError` + gate follow the shape of.

## Applicable guardrails

- The plan's `## Scope guardrails` bind this step's whole surface: the check is exactly one binary observable (declared version supported or not), never a content-schema check, never a warning on a supported version, and never a read-time upgrade or repair. Every routing change in this step exists only to reach that one refusal at every semantic read site — nothing here should grow into validating what a body *says*, only what it *declares*.
- The plan's `## Out of scope` excludes "declaring the detail grade in the artifact" — the marker this step parses carries only a version integer; do not widen it to also carry `GRADE_RUN`/`GRADE_JIRA` even though the temptation exists right next to it in `renderer.py`/`jira.py`, both of which already have a separate grade axis.
- The plan's `## Out of scope` also excludes rewriting or upgrading artifacts on read, any version 2, and a migration engine — this step's gate only ever refuses or passes; it never repairs, upgrades, or infers.

## Deferred

- Stamping the marker into any detail file this build writes — `plan_tool/detail.py`'s writer, `DETAIL_FORMAT.md`'s description of the resulting position, and `plan_tool/prompts/detail.md`'s reserved-but-version-free slot are step 4, which depends on this step's marker spelling and parser.
- Registering `DETAIL_FORMAT_VERSION` / `SUPPORTED_DETAIL_FORMAT_VERSIONS` in `plan_tool/data_contract.py`'s version-only record and the class-specific evolution/writer-eligibility/support-window/retirement rules in `DATA_CONTRACT.md` — step 5.
- The explicit absent-to-1 raw upgrade entry point and its coverage test over every absent-or-supported state — step 6.
- `BACKLOG.md` #356 removal and `CLAUDE.md`'s format-doc bullet updates — step 7.
- Any version 2 of the detail format, a migration engine, or a `plan-tool migrate` verb — out of scope for the whole plan; there is nothing to migrate to yet.
- The four staged roadmap artifacts' own version declaration — carved into `BACKLOG.md` #362, tracked separately.
