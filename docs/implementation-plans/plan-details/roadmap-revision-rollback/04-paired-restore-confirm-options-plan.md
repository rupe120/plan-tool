# Step 4 — Add the paired restore and confirm options to `plan-tool roadmap`, exclusive with every other roadmap option, and map the runner's outcomes to exit codes

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step wires step 3's `restore_roadmap_revision` into `plan_tool/cli/roadmap_cmd.py` as a new explicit, confirmed CLI action — `--restore-revision` paired with `--confirm-restore-revision` — following the exact shape `--reopen-feedback`/`--confirm-feedback-reopen` already established in this file: both flags register through `_TrackExclusiveOption`, a new `_has_restore_revision`/`_restore_revision_has_conflict` predicate pair requires exactly one of each with no companion roadmap option (`-y` included — it is not confirmation), and a new dispatch branch in `cmd_roadmap` calls the runner and maps its closed `RevisionRestoreResult` to an exit code. Because the pair is a new exclusive mode, every existing sibling conflict predicate (nine of them, enumerated below) needs the same one-line addition `--reopen-feedback` got when it was added, so that every other roadmap option correctly rejects `--restore-revision`/`--confirm-restore-revision` as a companion and vice versa. The step closes with `python -m plan_tool.cli_reference --write` regenerating `docs/cli/roadmap.md` from the updated parser. On green, the restore route is reachable from the command line and returns a correct exit code for every outcome step 3 can produce, but nothing yet tells an operator it exists at the point a run stops short — that is step 5's job.

## Table of Contents

- [Summary](#summary) — what this step delivers and where the line is drawn
- [Why](#why) — the gap this step closes
- [Input](#input) — the contract step 3 hands this step
- [Files (creates vs edits)](#files-creates-vs-edits) — what changes, file by file
- [Implementation](#implementation) — the flag pair, the conflict sweep, dispatch, and exit-code mapping
- [Tests](#tests) — test roster
- [Acceptance criteria](#acceptance-criteria)
- [References](#references)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

Step 3 leaves `restore_roadmap_revision` with no caller. An operator whose run stopped partway has no way to invoke it — the plan's own settled decision is that restore only ever runs on an explicit, confirmed command, mirroring `--reopen-feedback`/`--confirm-feedback-reopen` rather than an automatic recovery path. `plan_tool/cli/roadmap_cmd.py` already has a working template for exactly this shape (a paired action/confirm flag, tracked as an exclusive mode, rejected everywhere else and rejecting everything else), so this step is mostly disciplined repetition of that template rather than new design — the main risk is an incomplete sweep of the nine existing conflict predicates, not getting any one of them wrong.

## Input

- **Step 3's closed result contract** (`plan_tool/roadmap_revision_rollback.py`, not yet built when this step lands — treat `docs/implementation-plans/plan-details/roadmap-revision-rollback/03-revision-restore-runner-under-writer.md` as authoritative): `restore_roadmap_revision(slug: str, *, plans_dir: Path) -> RevisionRestoreResult`, where `RevisionRestoreResult` carries `outcome: Literal["restored", "already-restored", "refused"]` and `reason: Literal["no-checkpoint", "enrolled", "changed-since-failed-run"] | None` (non-`None` exactly when `outcome == "refused"`), exposed as `RESTORE_OUTCOME_RESTORED` / `RESTORE_OUTCOME_ALREADY_RESTORED` / `RESTORE_OUTCOME_REFUSED`. The function takes no `mode_rejected` kwarg (unlike `run_confirmed_feedback_reopen`) and does not compute its own exit status (unlike `FeedbackReopenRunResult.status`) — step 3's own Implementation section states both are deliberately left to this step.
- **What step 3 raises rather than returns** — `restore_roadmap_revision` lets four things propagate uncaught: `RoadmapWriterGuardError` (`plan_tool/roadmap_revision_publish.py`, a bad writer token or an unavailable lock), `RoadmapPublicationRecoveryError` (`plan_tool/roadmap_revision_publish.py`, subclass of `RoadmapRevisionPublishError(ValueError)`, an unrecoverable dangling journal or a publish that didn't commit), `RoadmapRevisionCheckpointError` (`plan_tool/roadmap_revision_checkpoint.py`, also a `ValueError` subclass per step 1's Implementation, a corrupted on-disk checkpoint file), and plain `OSError` from the filesystem reads/writes underneath. This step's dispatch wrapper is the first place any of these are caught.
- **The existing `--reopen-feedback`/`--confirm-feedback-reopen` shape** (`plan_tool/cli/roadmap_cmd.py`) — the flag registration (`_TrackExclusiveOption`, `nargs=0, const=True` for the confirm half), `_has_feedback_reopen`, `_feedback_reopen_has_conflict`, the `has_feedback_reopen` dispatch block inside `cmd_roadmap`, `_cmd_roadmap_feedback_reopen`, and `_render_feedback_reopen_result` are the template every piece of this step's CLI wiring mirrors.
- **The exit-code vocabulary already established for this file** — `_RC_USAGE = 2` (pre-flight / rejected-by-current-state), `_RC_INCOMPLETE = 1` (ran but did not finish, or an environmental failure). `_RC_PARTIAL = 3` does not apply here — restore is a single all-or-nothing operation, not a batch.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/cli/roadmap_cmd.py` — two new `--restore-revision`/`--confirm-restore-revision` parser flags, their default occurrence tuples in `register()`'s `p.set_defaults(...)`, `_has_restore_revision`, `_restore_revision_has_conflict`, a new `has_restore_revision` dispatch block in `cmd_roadmap`, `_cmd_roadmap_restore_revision`, `_render_restore_revision_result`, a one-line addition to each of the nine existing conflict predicates named in Implementation, a new import of `restore_roadmap_revision` / `RevisionRestoreResult` / the three `RESTORE_OUTCOME_*` constants from `plan_tool.roadmap_revision_rollback`, and a new module-docstring paragraph describing the pair (matching the existing per-flag paragraphs at the top of the file).
- `tests/cli/test_roadmap_cmd.py` — the new test roster below, plus `restore_revision=None`, `confirm_restore_revision=None`, `_restore_revision_occurrences=()`, `_confirm_restore_revision_occurrences=()` added to the shared `_ns(...)` fixture and a new `_restore_revision_args(...)` helper mirroring `_feedback_reopen_args`.
- `docs/cli/roadmap.md` — regenerated output of `python -m plan_tool.cli_reference --write`; no hand edits.

## Implementation

**The flag pair.** Register both through `_TrackExclusiveOption` exactly as `--reopen-feedback`/`--confirm-feedback-reopen` are registered — but both take no value, closer to `--enroll-version`'s shape, since restore has no selector (the target is the whole roadmap for `args.slug`, not one feedback row):

- `--restore-revision` — `action=_TrackExclusiveOption, nargs=0, const=True, default=None`. One reasonable name, chosen to match `restore_roadmap_revision`/`plan_tool/roadmap_revision_rollback.py`; adjust if a clearer one presents itself, but keep the confirm flag's name derived from it so the pair reads as one unit.
- `--confirm-restore-revision` — same shape, its help text stating "Required exactly once; -y is not confirmation" verbatim, matching `--confirm-feedback-reopen`'s help text (this is also what `test_restore_revision_help_documents_the_exact_confirmed_pair`, below, checks for literally).

Add both to `p.set_defaults(...)`'s occurrence-tuple block (`_restore_revision_occurrences=(), _confirm_restore_revision_occurrences=()`), beside the existing `_reopen_feedback_occurrences=()` / `_confirm_feedback_reopen_occurrences=()` lines.

**`_has_restore_revision` and `_restore_revision_has_conflict`.** Copy `_has_feedback_reopen` and `_feedback_reopen_has_conflict` verbatim, substituting the new option names:

```python
def _has_restore_revision(args: argparse.Namespace) -> bool:
    return bool(
        _option_occurrences(args, "restore_revision")
        or _option_occurrences(args, "confirm_restore_revision")
    )


def _restore_revision_has_conflict(args: argparse.Namespace) -> bool:
    return any(
        (
            len(_option_occurrences(args, "restore_revision")) != 1,
            len(_option_occurrences(args, "confirm_restore_revision")) != 1,
            bool(_view_occurrences(args)),
            _has_receipt_creation(args),
            _has_impact_analysis_creation(args),
            _has_structural_rewrite(args),
            _has_feedback_reopen(args),
            _has_candidate_lifecycle_action(args),
            getattr(args, "revise_feedback", None) is not None,
            *_broad_mode_companions_present(args),
        )
    )
```

`_broad_mode_companions_present(args)` already covers `-y`/`--yes` as a rejected companion, which is what makes "`-y` is not confirmation" true without any special-case code: supplying `-y` instead of `--confirm-restore-revision` fails this predicate on the companion check, and supplying `-y` *and* `--confirm-restore-revision` still fails on it, so `-y` can never substitute for the confirm flag.

**The nine-site sweep — the part most likely to be under-scoped.** `--reopen-feedback`/`--confirm-feedback-reopen` is not just a template for the two functions above; every *other* exclusive mode's own conflict predicate had to learn about it too, so that mode is symmetrically excluded on both sides. Add `_has_restore_revision(args)` to the `any(...)` tuple in each of these existing functions (all in `plan_tool/cli/roadmap_cmd.py`), alongside the existing `_has_feedback_reopen(args)` line each one already carries:

1. `_enrollment_has_conflict`
2. `_escalation_creation_has_conflict`
3. `_escalation_view_has_conflict`
4. `_impact_analysis_creation_has_conflict`
5. `_impact_analysis_view_has_conflict`
6. `_structural_rewrite_has_conflict`
7. `_feedback_reopen_has_conflict` (the reverse direction — reject restore as a companion to reopen-feedback too)
8. `_revise_feedback_has_conflict`
9. `_candidate_lifecycle_has_conflict`

And one more site outside that group: `_selects_non_stage_roadmap_route` — add `_has_restore_revision(args)` to its `any(...)` tuple too. This function feeds the existing top-of-`cmd_roadmap` guard (`if getattr(args, "confirm_brief_rebind", False) and _selects_non_stage_roadmap_route(args): error(...)`), and without this addition `--confirm-brief-rebind` combined with `--restore-revision` would silently skip that guard instead of being rejected as "valid only for stage runs."

Grep `_has_feedback_reopen(args)` across the file before finishing this step — every hit is a site this sweep must also touch, and that grep is the check that the sweep is actually complete rather than assumed complete.

**Dispatch.** Add `has_restore_revision = _has_restore_revision(args)` alongside the other `has_*` bindings at the top of `cmd_roadmap`, and a new block shaped like the `has_feedback_reopen` block — placed near it, since both are paired-confirm actions, though exact placement among the mutually-exclusive early-dispatch blocks doesn't otherwise matter:

```python
if has_restore_revision:
    if _restore_revision_has_conflict(args):
        error(
            "--restore-revision requires exactly one --confirm-restore-revision "
            "and no companion roadmap options"
        )
        return _RC_USAGE
    repo_root = _resolve_cmd_repo_root(args)
    plans_dir = resolve_explicit_plans_dir(args.plans_dir)
    if plans_dir is None:
        plans_dir = resolve_output_dir(repo_root)
    try:
        roadmap_dir(plans_dir, args.slug)
    except (TypeError, ValueError) as exc:
        error(str(exc))
        return _RC_USAGE
    try:
        return _cmd_roadmap_restore_revision(args, plans_dir=plans_dir)
    except KeyboardInterrupt:
        error("interrupted")
        return 130
```

The `roadmap_dir(plans_dir, args.slug)` preflight matters here specifically: unlike `run_confirmed_feedback_reopen` (which validates the slug internally and folds a bad one into its own `"mode-rejected"` outcome), `restore_roadmap_revision` has no such internal check per step 3's Input section — a malformed slug would otherwise propagate as a raw `TypeError`/`ValueError` from deep inside `roadmap_writer_guard`/`load_checkpoint` instead of a clean usage error. This mirrors the same preflight the candidate-lifecycle and receipt-creation dispatch blocks already do before their own handlers.

**`_cmd_roadmap_restore_revision` and the exit-code mapping.** `RevisionRestoreResult` carries no status field, so this function owns the mapping — the runner's outcomes on one side, its propagated exceptions on the other:

```python
def _cmd_roadmap_restore_revision(args: argparse.Namespace, *, plans_dir: Path) -> int:
    try:
        result = restore_roadmap_revision(args.slug, plans_dir=plans_dir)
    except OSError as exc:
        error(str(exc))
        return _RC_INCOMPLETE
    except (RoadmapWriterGuardError, ValueError) as exc:
        error(str(exc))
        return _RC_USAGE
    _render_restore_revision_result(result)
    if result.outcome == RESTORE_OUTCOME_REFUSED:
        return _RC_USAGE
    return 0
```

`RoadmapPublicationRecoveryError` and `RoadmapRevisionCheckpointError` are both `ValueError` subclasses (per step 3's Input and step 1's Implementation), so a plain `except (RoadmapWriterGuardError, ValueError)` catches every propagated failure step 3 names without importing either narrow type — the same shape `_cmd_roadmap_promote_review_seal`'s own `except (..., RoadmapWriterGuardError, ..., ValueError)` already uses for an analogous "the tool's own state won't allow this write" case. This is a recommendation, not a hard requirement: catching the two narrow types by name instead is equally correct if a reviewer prefers explicit imports over relying on the `ValueError` hierarchy.

For the closed `RevisionRestoreResult.outcome` values: `"restored"` and `"already-restored"` both map to `0` (the operation the operator asked for succeeded, whether or not it changed anything — matching how `OUTCOME_COMPLETED_NO_CHANGE` also maps to `0` for an ordinary stage run). `"refused"` maps to `_RC_USAGE` uniformly across all three `reason` values (`"no-checkpoint"`, `"enrolled"`, `"changed-since-failed-run"`) rather than splitting them — this mirrors `_reopen_result`'s own outcome→status table in `plan_tool/roadmap_feedback_reopen.py`, where every `"preflight-rejected"` verdict maps to `2` regardless of *which* business rule rejected it, `"changed-since-failed-run"` included as the direct analog of that table's own `"source-changed"` entry (both are "the state moved under us since we started" refusals). If a reviewer wants the three refusal reasons to map to different codes, that's a deliberate deviation from this precedent and should be called out, not made silently.

**`_render_restore_revision_result`.** Two lines, matching `_render_feedback_reopen_result`'s shape:

```python
def _render_restore_revision_result(result: RevisionRestoreResult) -> None:
    print(f"revision restore: {result.outcome}")
    if result.reason is not None:
        print(f"reason: {result.reason}")
```

No redaction is needed here (unlike the feedback/candidate/escalation renderers, which withhold selector or response content) — `reason` is a closed three-member enum, not user- or model-supplied content.

**Imports.** Add to the existing `from plan_tool.roadmap_revision_rollback import (...)` — a new import block, since this module doesn't exist yet at HEAD — `RESTORE_OUTCOME_REFUSED`, `RevisionRestoreResult`, `restore_roadmap_revision`. No new import is needed for `RoadmapWriterGuardError` (already imported from `plan_tool.roadmap_revision_publish` at the top of the file).

**Module docstring.** Add one paragraph describing `--restore-revision`/`--confirm-restore-revision`, in the same style and roughly the same position as the existing `--reopen-feedback`/`--confirm-feedback-reopen` paragraph (after it reads naturally, since both are paired-confirm exceptions to an ordinary flow).

**Regenerate the reference doc.** Once the parser changes land, run `python -m plan_tool.cli_reference --write` and commit the resulting diff to `docs/cli/roadmap.md`. Do not hand-edit that file — it is fully generated from the argparse parser (usage line, arguments table, options table, help text verbatim), confirmed by reading its current contents against `register()`'s `add_argument` calls.

## Tests

### Tests for this step

All cases live in `tests/cli/test_roadmap_cmd.py`. Every one must be green before this step is done.

- `test_restore_revision_options_preserve_absent_single_and_repeated_occurrences` — mirrors `test_feedback_reopen_options_preserve_absent_single_and_repeated_occurrences`: absent, single, and repeated `--restore-revision`/`--confirm-restore-revision` each leave the right `_restore_revision_occurrences` / `_confirm_restore_revision_occurrences` tuples and final values.
- `test_restore_revision_pair_is_not_a_broad_mode` — `args._roadmap_mode_occurrences == ()` when only the restore pair is supplied, proving it is tracked as an exclusive option, not a broad mode.
- `test_restore_revision_help_documents_the_exact_confirmed_pair` — help text contains both flag names, `"Required exactly once"`, and `"-y is not confirmation"`.
- `test_restore_revision_dispatches_only_the_confirmed_operation` — monkeypatches `restore_roadmap_revision` and every other roadmap entrypoint (`run_roadmap`, `run_confirmed_feedback_reopen`, `run_roadmap_escalation_receipt`, `run_roadmap_impact_analysis`, `run_structural_revision`, `run_local_feedback_revision`, `_cmd_roadmap_view`) to `pytest.fail` if called; asserts only the restore runner ran, with `slug` and `plans_dir` forwarded and no `repo_root` (matching step 3's stated signature).
- `test_restore_revision_incomplete_or_repeated_pair_returns_usage_without_calling_the_runner` — parametrized over missing/repeated `--restore-revision` and missing/repeated `--confirm-restore-revision`; asserts `cmd_roadmap(...) == 2` and that `restore_roadmap_revision` is never called at all — the stronger claim than the feedback-reopen analog, since `restore_roadmap_revision` has no `mode_rejected` kwarg to short-circuit internally, so an incomplete pair must never reach it.
- `test_restore_revision_rejects_every_companion_mode_without_calling_the_runner` — parametrized over every other roadmap option (`--revise-feedback`, receipt creation, impact-analysis creation, structural rewrite, `--reopen-feedback`/`--confirm-feedback-reopen`, `--view`, `--enroll-baselines`, `-y`, `--from-existing`, `--from-stage`, `--apply`, `--mode`, `--id`, and a candidate-lifecycle action); asserts `cmd_roadmap(...) == 2` and `restore_roadmap_revision` never called for each.
- `test_existing_exclusive_mode_predicates_reject_the_restore_revision_pair` — the sweep test, mirroring `test_existing_exclusive_mode_predicates_reject_the_feedback_reopen_pair`: with the restore/confirm pair present, asserts `_enrollment_has_conflict`, `_escalation_creation_has_conflict`, `_escalation_view_has_conflict`, `_impact_analysis_creation_has_conflict`, `_impact_analysis_view_has_conflict`, `_structural_rewrite_has_conflict`, `_feedback_reopen_has_conflict`, `_revise_feedback_has_conflict`, and `_candidate_lifecycle_has_conflict` all return `True` — covering `_candidate_lifecycle_has_conflict` explicitly, which the existing feedback-reopen sibling test does not exercise even though `_has_feedback_reopen` is already in that predicate's tuple.
- `test_restore_revision_confirm_brief_rebind_is_rejected_as_a_non_stage_route` — `--confirm-brief-rebind` together with the restore/confirm pair returns `2` with the existing `"--confirm-brief-rebind is valid only for stage runs"` message, proving `_selects_non_stage_roadmap_route` was swept.
- `test_restore_revision_does_not_treat_yes_as_confirmation` — `--restore-revision -y` with no `--confirm-restore-revision` returns `2` and never calls the runner.
- `test_restore_revision_preflight_validates_the_slug_before_calling_the_runner` — an invalid slug (e.g. containing `/`) with the restore/confirm pair returns `2` from the `roadmap_dir` preflight, and `restore_roadmap_revision` is never called.
- `test_restore_revision_renders_only_redacted_terminal_facts` — parametrized over `RevisionRestoreResult("restored", None)`, `RevisionRestoreResult("already-restored", None)`, and `RevisionRestoreResult("refused", "no-checkpoint")` / `"enrolled"` / `"changed-since-failed-run"`; asserts stdout equals `revision restore: {outcome}` (plus a `reason: {reason}` line when refused) and the return code matches `0` / `0` / `2` / `2` / `2`.
- `test_restore_revision_maps_checkpoint_and_publish_errors_to_usage` — monkeypatches `restore_roadmap_revision` to raise `RoadmapRevisionCheckpointError` and, separately, `RoadmapPublicationRecoveryError`; asserts `cmd_roadmap(...) == 2` for each and the exception message is printed.
- `test_restore_revision_maps_writer_guard_error_to_usage` — same, raising `RoadmapWriterGuardError`; asserts `2`.
- `test_restore_revision_maps_os_error_to_incomplete` — same, raising `OSError`; asserts `1`.
- `test_restore_revision_keyboard_interrupt_returns_130_from_the_shared_wrap` — monkeypatches `restore_roadmap_revision` to raise `KeyboardInterrupt`; asserts `cmd_roadmap(...) == 130` and `"interrupted"` is printed — names explicitly that this dispatch block's own `try`/`except KeyboardInterrupt` is what supplies this, since step 3 deliberately leaves `KeyboardInterrupt` unhandled inside the runner itself.

`tests/cli/test_cli_reference.py::TestCliReferenceDrift::test_every_generated_file_matches_disk` (pre-existing, not modified by this step) is what enforces `docs/cli/roadmap.md` staying in sync with the two new flags — no new bespoke doc test is needed in `test_roadmap_cmd.py`.

## Acceptance criteria

- `plan-tool roadmap <slug> --restore-revision --confirm-restore-revision` calls `restore_roadmap_revision(slug, plans_dir=...)` and exits `0` on `"restored"` or `"already-restored"`, `2` on `"refused"` (any reason).
- `--restore-revision` or `--confirm-restore-revision` supplied fewer or more than once, or supplied with any other roadmap option (including `-y`, `--view`, `--enroll-baselines`, `--confirm-brief-rebind`, `--revise-feedback`, a candidate-lifecycle action, receipt creation, impact-analysis creation, structural rewrite, or `--reopen-feedback`/`--confirm-feedback-reopen`), exits `2` without calling `restore_roadmap_revision`.
- Every other exclusive roadmap mode's own conflict predicate rejects the restore/confirm pair as a companion: `_enrollment_has_conflict`, `_escalation_creation_has_conflict`, `_escalation_view_has_conflict`, `_impact_analysis_creation_has_conflict`, `_impact_analysis_view_has_conflict`, `_structural_rewrite_has_conflict`, `_feedback_reopen_has_conflict`, `_revise_feedback_has_conflict`, and `_candidate_lifecycle_has_conflict` all return `True` when it is present.
- An invalid slug with the restore/confirm pair exits `2` from a `roadmap_dir` preflight check, without calling `restore_roadmap_revision`.
- `RoadmapWriterGuardError`, `RoadmapPublicationRecoveryError`, and `RoadmapRevisionCheckpointError` raised by `restore_roadmap_revision` each exit `2`; `OSError` exits `1`; `KeyboardInterrupt` exits `130` and prints `"interrupted"`.
- `docs/cli/roadmap.md` is byte-identical to `python -m plan_tool.cli_reference --write`'s output.
- `uv run pytest tests/cli/test_roadmap_cmd.py tests/cli/test_cli_reference.py -q` passes, and the full suite (`uv run pytest tests/ -q -n auto`) passes.

## References

- `plan_tool/cli/roadmap_cmd.py`: `--reopen-feedback`/`--confirm-feedback-reopen` (registration, `_has_feedback_reopen`, `_feedback_reopen_has_conflict`, the `has_feedback_reopen` dispatch block, `_cmd_roadmap_feedback_reopen`, `_render_feedback_reopen_result`) — the CLI shape this step mirrors throughout. `_cmd_roadmap_promote_review_seal` — the precedent for catching `RoadmapWriterGuardError` and `ValueError` broadly rather than importing every narrow subclass by name.
- `plan_tool/roadmap_revision_publish.py`: `RoadmapWriterGuardError`, `RoadmapRevisionPublishError`, `RoadmapPublicationRecoveryError` — the exception hierarchy this step's dispatch wrapper catches.
- `docs/implementation-plans/plan-details/roadmap-revision-rollback/01-roadmap-revision-checkpoint-file-that.md`, `03-revision-restore-runner-under-writer.md` — `RoadmapRevisionCheckpointError`'s base class and `restore_roadmap_revision`'s full contract, not yet landed in code when this step is authored.
- `plan_tool/cli_reference.py`, `tests/cli/test_cli_reference.py` — the generator and its drift guard for `docs/cli/roadmap.md`.

## Applicable guardrails

- The plan's `## Scope guardrails`, "No automatic restore, and no restore offered on anything but an explicit command" — this step's only entry point is the explicit, confirmed `--restore-revision --confirm-restore-revision` pair; nothing in `cmd_roadmap`'s ordinary stage-run path or any other branch calls `restore_roadmap_revision`.
- The same guardrails, "No new persisted state except the checkpoint" — this step writes no new file; it only adds CLI parsing, dispatch, and rendering.
- The same guardrails, "No change to `--revise-feedback`, `--materialize`, `--enroll-baselines`, or `--enroll-version`" — the nine-site sweep adds a line to each of those flags' own *conflict predicate* (so they correctly reject the new pair as a companion) but changes none of their own behavior, semantics, or output.
- The same guardrails, "No change to enrollment, candidates, review seals, promotion, or the `.roadmap-versions/` namespace" and "Eligibility never reads run logs" — this step's dispatch code reads no run log and calls no enrollment, candidate, or promotion function; it only calls `restore_roadmap_revision` and renders its closed result.

## Deferred

- Naming the restore command at `cmd_roadmap`'s four non-completion paths (the `RoadmapResult`-based invalid/exhausted branch, the `except (OSError, RoadmapEnvironmentalError)` branch, the `except (RoadmapError, RoadmapArtifactError, RoadmapWriterGuardError)` branch, and the `except KeyboardInterrupt` branch) — step 5, which depends on this step's flag names.
- Operator documentation (`ROADMAP_FORMAT.md`, `docs/how-to/roadmap.md`, `RUNBOOK.md`, `CAPABILITIES.md`, `docs/ARCHITECTURE.md`) and closing `BACKLOG.md` #394 — step 6.
- Splitting the `"refused"` outcome's three reasons into different exit codes — not requested by the plan; this step maps all three to `_RC_USAGE`, matching `run_confirmed_feedback_reopen`'s own precedent of one status per outcome category rather than per reason.
