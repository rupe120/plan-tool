"""The direct-pipeline CLI leaf: the ``direct-jira`` / ``direct-run`` verbs plus
the deterministic size gate they add on top of the reused stage handlers.

Both verbs chain the pipeline in one process, threading ``create``'s result to
the next stage in memory. See ``docs/implementation-plans/2-direct-pipeline-commands.md``.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from plan_tool.cli.authoring import cmd_create, cmd_detail
from plan_tool.cli.completeness_cmd import cmd_completeness_apply
from plan_tool.cli.context import _resolve_cmd_repo_root
from plan_tool.cli.gitcommit import (
    commit_all,
    unexpected_dirty_paths,
    working_tree_dirty,
)
from plan_tool.cli.jira_cmd import cmd_jira
from plan_tool.cli.parser import Handler
from plan_tool.cli.run_cmd import cmd_reconcile_code, cmd_run
from plan_tool.concept_tree import concepts_path
from plan_tool.create import CreateResult
from plan_tool.grounding import grounding_path
from plan_tool.locator import find_repo_root_from_cwd
from plan_tool.parser import parse_plan
from plan_tool.schema import ChangeType
from plan_tool.style import error, warn

# Worker count for the mid-chain ``completeness-apply`` stage. Must be > 1 to
# select the non-interactive parallel apply path (``--jobs 1`` is the
# interactive walk, which would block a chained run on stdin); each worker
# isolates in its own git worktree off HEAD, which is why the verb requires a
# clean tree up front and commits the authoring artifacts before this stage.
COMPLETENESS_APPLY_JOBS = 4

# Largest finished-plan step count the direct verbs chain onward in one process;
# a bigger plan is better driven step-by-step via ``plan-tool run``. Measured in
# *steps*, not bytes (byte size tracks prose, not work). Tuning deferred — see
# the plan's ``## Out of scope``.
MAX_CHAINABLE_STEPS = 10


@dataclass(frozen=True)
class SizeGateResult:
    """Verdict from :func:`gate_create_result_size`: ``may_proceed`` gates the
    chain (``False`` → stop, print ``reason``). ``step_count`` (``-1`` on a
    split, where no single plan exists) and ``threshold`` build the message;
    ``split_short_circuit`` picks the stop shape (multi-plan split vs over-large).
    """

    may_proceed: bool
    step_count: int
    threshold: int
    reason: str
    split_short_circuit: bool = False


def gate_create_result_size(result: CreateResult) -> SizeGateResult:
    """Decide whether ``result`` is small enough to chain onward.

    Deterministic and Claude-free: re-parses the created plan from disk and
    compares its step count against :data:`MAX_CHAINABLE_STEPS`. Takes no
    ``invoker=`` seam — there is no judgment to delegate to a backend.

    The multi-plan split short-circuit (``result.plan_path is None``) is its own
    stop outcome: there is no single plan to size, so the chain cannot proceed
    and we must not ``parse_plan(None)``.
    """
    if result.plan_path is None:
        # Split short-circuit: create proposed multiple plans instead of
        # writing one, so there is nothing to chain onward.
        return SizeGateResult(
            may_proceed=False,
            step_count=-1,
            threshold=MAX_CHAINABLE_STEPS,
            reason=(
                "create produced a multi-plan split proposal, not a single "
                "plan — nothing to chain onward"
            ),
            split_short_circuit=True,
        )

    plan = parse_plan(result.plan_path)
    step_count = len(plan.steps)
    if step_count > MAX_CHAINABLE_STEPS:
        return SizeGateResult(
            may_proceed=False,
            step_count=step_count,
            threshold=MAX_CHAINABLE_STEPS,
            reason=(
                f"plan has {step_count} steps, over the {MAX_CHAINABLE_STEPS}-step "
                "limit for a single chained run — drive it step-by-step with "
                "plan-tool run"
            ),
        )

    return SizeGateResult(
        may_proceed=True,
        step_count=step_count,
        threshold=MAX_CHAINABLE_STEPS,
        reason=(
            f"plan has {step_count} steps, within the {MAX_CHAINABLE_STEPS}-step "
            "chain limit"
        ),
    )


def derive_created_repo_root(result: CreateResult) -> Path:
    """Return the repo root ``create`` actually wrote the plan under.

    Walks up from ``result.plan_path``'s own directory to the nearest
    ``.git`` / ``.plan-tool/plans.json`` ancestor via
    :func:`plan_tool.locator.find_repo_root_from_cwd` — the same primitive
    ``cmd_create``'s root confirmation and ``find_umbrella_root`` are built on,
    so a relocated ``--from-existing`` run's downstream stages resolve the plan
    and commit against the root it actually landed in.

    Deliberately NOT ``result.manifest_path.parent.parent``: that shortcut
    silently assumes the ``<root>/.plan-tool/plans.json`` layout and breaks
    under an explicit ``--manifest`` override pointing outside it (plan
    Architecture decision 2). ``result.plan_path`` is guaranteed non-``None``
    here — the multi-plan-split short-circuit already returned upstream.
    """
    assert result.plan_path is not None
    return find_repo_root_from_cwd(start=result.plan_path.parent)


def _resolve_created_repo_root(
    result: CreateResult,
    repo_root: Path,
    *,
    verb: str,
    plan_name: str,
) -> tuple[Path | None, int]:
    """Derive the root ``create`` used, refuse a nested/ancestor relocation, and
    sweep the original root's own relocation dirt before downstream stages
    repoint at the new root.

    Returns ``(created_repo_root, 0)`` on success — the caller threads
    ``created_repo_root`` into every post-create stage namespace and git-op.
    Returns ``(None, rc)`` when the chain must stop: ``rc=2`` on a refused
    non-disjoint (nested/ancestor) relocation, or the commit's rc when the
    original-root sweep commit fails.

    Order matters (plan Architecture decision 7): derive → refuse-if-non-disjoint
    → commit-original-root-dirt. The refuse precedes the commit so a rejected
    chain never leaves a half-committed original root, and it guarantees the two
    roots are disjoint trees before the ``git add -A`` sweep — so the sweep can
    never stage one root as an embedded gitlink inside the other.
    """
    created_repo_root = derive_created_repo_root(result)
    if created_repo_root == repo_root:
        # No relocation: the common case. Skip the disjointness check
        # (``is_relative_to`` self-returns True) and the original-root sweep
        # entirely — there is no second root to reconcile against.
        return created_repo_root, 0

    original = repo_root.resolve()
    relocated = created_repo_root.resolve()
    if relocated.is_relative_to(original) or original.is_relative_to(relocated):
        # One tree is nested inside the other. git's embedded-repository
        # semantics make a cross-root ``git add -A`` hazardous (a nested .git
        # stages as a mode-160000 gitlink), so refuse rather than corrupt.
        # Full nested-repo support is deferred to BACKLOG #146.
        error(
            f"{verb}: create relocated the plan to a repo nested within (or "
            f"containing) the current one ({created_repo_root}); nested-repo "
            "relocation is unsupported — run plan-tool create/detail/run from "
            "that repo directly"
        )
        return None, 2

    # Disjoint relocation: commit whatever dirt ``create`` left in the ORIGINAL
    # root (the archived --from-existing seed, up to three seed-adjacent writes)
    # before every later stage repoints at ``created_repo_root`` — otherwise it
    # is orphaned uncommitted and trips a later run's step-0 clean-tree
    # precondition. Guaranteed-disjoint here, so this ``git add -A`` cannot stage
    # ``created_repo_root`` as an embedded gitlink. A no-op (``--from``, or an
    # idempotent re-run) leaves the original root clean and skips the commit.
    if working_tree_dirty(repo_root):
        commit_rc, tail = commit_all(
            repo_root,
            f"{verb}({plan_name}): archive superseded seed after relocation",
        )
        if commit_rc != 0:
            error(
                f"{verb}: committing superseded seed in original root "
                f"failed: {tail}"
            )
            return None, commit_rc
    return created_repo_root, 0


def _relocated_root_unexpected_dirt(
    created_repo_root: Path, result: CreateResult
) -> "list[str] | None":
    """Dirty paths in the relocated root not covered by ``create``'s own writes.

    Builds the expected-path set from every write ``cmd_create`` is known to make
    under the relocated root — the plan file, manifest, concepts sidecar, and
    grounding-baseline sidecar always (``_stamp_grounding`` writes the last after
    every create, not just a deferred-concept one), plus a same-slug
    collision-replace's archived copies and renamed detail directory — then asks
    :func:`plan_tool.cli.gitcommit.unexpected_dirty_paths` what's dirty beyond
    them. ``None`` (git unreadable) or a non-empty list is the caller's signal to
    abort: the relocated root carries uncommitted work ``create`` didn't author.

    Best-effort by design (plan Implementation / BACKLOG #150): ``CreateResult``
    doesn't enumerate every ``create`` write, so a missed one costs a *spurious
    abort* (operator inspects and re-runs), never a corrupted commit.
    """
    assert result.plan_path is not None
    expected: list[Path] = [
        result.plan_path,
        result.manifest_path,
        concepts_path(result.plan_path),
        grounding_path(result.plan_path),
        # create's own tool-state scratch — telemetry (decisions.jsonl), the
        # initial-steps checkpoint, run logs — is written under .plan-tool/ on
        # essentially every create, and the relocated root (never subject to
        # step 0's clean-tree check) may not gitignore it. A directory entry
        # covers everything beneath it (see unexpected_dirty_paths), so one
        # path here accounts for all of it rather than enumerating each file —
        # and it's tool state, never a stranger's source work.
        created_repo_root / ".plan-tool",
    ]
    # Collision-replace: both sides are create's own writes, not a stranger's
    # dirt — the archived copy AND the *deleted* original (archive_existing_source
    # unlinks the superseded plan, so git reports a ` D old-plan.md` the archived
    # copy alone doesn't cover). Include both ends of each pair. The renamed
    # detail directory is likewise create's; manifest-entry removals edit
    # result.manifest_path (already in the always-set).
    for original, archived in result.replaced_archives:
        expected.append(original)
        expected.append(archived)
    if result.plan_details_renamed_to is not None:
        expected.append(result.plan_details_renamed_to)
    return unexpected_dirty_paths(created_repo_root, expected)


def _guard_relocated_root_clean(
    created_repo_root: Path,
    repo_root: Path,
    result: CreateResult,
    *,
    verb: str,
) -> int:
    """Abort (rc 2) when a relocated root carries dirt beyond create's own writes.

    A no-op (rc 0) when there's no relocation: the pre-create root already
    passed step 0's clean-tree precondition, so only a *disjoint* relocated root
    (step 2 already refused the nested/ancestor case) needs this second look,
    fired before ``detail`` so the chain fails fast rather than spending a
    detail round-trip on a run that would abort at the stage-4 commit anyway.
    """
    if created_repo_root.resolve() == repo_root.resolve():
        return 0
    unexpected = _relocated_root_unexpected_dirt(created_repo_root, result)
    if unexpected is None:
        error(
            f"{verb}: could not read git status in the relocated repo "
            f"{created_repo_root}; refusing to fold possibly-unrelated work "
            "into an auto-commit — commit or stash there and re-run"
        )
        return 2
    if unexpected:
        names = ", ".join(unexpected)
        error(
            f"{verb} requires a clean relocated repo: create wrote the plan to "
            f"{created_repo_root}, which has uncommitted changes unrelated to "
            f"this run ({names}); commit or stash them and re-run"
        )
        return 2
    return 0


def _stage_namespace(
    args: argparse.Namespace, **overrides: object
) -> argparse.Namespace:
    """Copy ``args`` and apply ``overrides``.

    Starting from ``argparse.Namespace(**vars(args))`` copies every
    cross-cutting flag (``backend``, ``model``, ``on_rate_limit``,
    ``fallback_backend``, ``yes``, …) through unchanged — that is what makes
    flag propagation free. The overrides then set the stage-specific fields the
    downstream handler reads *directly* (missing ones raise ``AttributeError``
    mid-chain), so the built namespace stays field-complete against the handler.
    """
    ns = argparse.Namespace(**vars(args))
    for key, value in overrides.items():
        setattr(ns, key, value)
    return ns


def cmd_direct_jira(args: argparse.Namespace) -> int:
    """Chain ``create → detail → completeness-apply → jira`` in one process.

    Reuses the standalone stage handlers (holds no stage logic of its own) and
    threads one args namespace into each. Requires a clean tree up front and
    commits mid-chain because ``completeness-apply --jobs N`` isolates its
    workers in worktrees cut off HEAD. A stage's non-zero exit stops the chain
    and is returned as-is; the size-gate and multi-plan-split stops are
    deliberate halts on a usable, re-runnable plan and exit 0.
    """
    warn(
        "direct-jira is going away (BACKLOG #376): it exists only to chain "
        "completeness-apply's gap-by-gap apply, which is retiring for the "
        "same reason (slower than a whole-report review, and the slow pace "
        "obscures the convergence signal) -- drive create / detail / jira "
        "as separate, hand-reviewed steps instead."
    )
    repo_root = _resolve_cmd_repo_root(args)

    # 0. Clean-tree precondition. The completeness-apply stage below isolates
    #    its workers in worktrees off HEAD, and the mid-chain ``git add -A``
    #    commits are only safe if the tree started clean. Don't name --commit:
    #    this verb commits on its own, it doesn't take a --commit flag.
    if working_tree_dirty(repo_root):
        error(
            "direct-jira requires a clean working tree (it commits the plan it "
            "authors before applying completeness gaps; commit or stash first)"
        )
        return 2

    # 1. Create. Deposit-sink hand-off: set a fresh list so cmd_create leaves
    #    its CreateResult here for the chain to read back in-process.
    args._create_result_sink = []
    rc = cmd_create(args)
    if rc != 0:
        return rc
    sink = args._create_result_sink
    if not sink:
        # cmd_create returned 0 but deposited nothing (no create ran). Nothing
        # to chain onward — surface it rather than crash on an empty sink.
        error("direct-jira: create produced no plan to chain onward")
        return 2
    result: CreateResult = sink[-1]

    # 2. Guard the hand-off before chaining forward.
    if result.split_proposal is not None or result.plan_path is None:
        # Multi-plan split: cmd_create already printed the proposal and exited
        # 0. There is no single plan to detail/export, so stop here (success,
        # not a hard failure — the seed is left for the operator to carve).
        print(
            "direct-jira: create produced a multi-plan split proposal, not a "
            "single plan — nothing to chain onward. Carve the seed and re-run."
        )
        return 0
    if result.iteration_stage_failure is not None:
        # cmd_create returns 0 here, so read the field, not the rc. An
        # unconverged plan must not be chained forward — stop unconditionally.
        error(
            "direct-jira: create's convergence loop did not converge "
            f"({result.iteration_stage_failure}); the plan is on disk but "
            "unconverged — resolve it before chaining to detail/jira"
        )
        return 2
    gate = gate_create_result_size(result)
    if not gate.may_proceed:
        print(f"direct-jira: {gate.reason}")
        return 0

    # The created plan's handle: cmd_create has registered it in the manifest,
    # so the downstream handlers' resolve_plan_for_context lookups resolve
    # against its stem — no disk round-trip to re-derive it from the seed.
    plan_name = result.plan_path.stem

    # Resolve the root ``create`` actually wrote to (it may differ from the
    # pre-create ``repo_root`` under a --from-existing relocation). Refuses a
    # nested/ancestor relocation and sweeps the original root's own dirt before
    # every later stage repoints at ``created_repo_root``. Keep ``repo_root``
    # intact for step 3's cleanliness check.
    created_repo_root, rc = _resolve_created_repo_root(
        result, repo_root, verb="direct-jira", plan_name=plan_name
    )
    if created_repo_root is None:
        return rc

    # Safety check: on a relocated (disjoint) root, abort before ``detail`` if
    # that root holds uncommitted work beyond ``create``'s own writes, rather
    # than fold a stranger's changes into the stage-4 authoring commit. Inert
    # when there was no relocation.
    rc = _guard_relocated_root_clean(
        created_repo_root, repo_root, result, verb="direct-jira"
    )
    if rc != 0:
        return rc

    # 3. Detail. ``detail_only=True`` pins the completeness tail's --iterate ON
    #    (deterministic well-formedness convergence + a saved conceptual gap
    #    map) while keeping the costly per-step detail-quality loop off. The
    #    tail does NOT apply conceptual gaps (#85) — step 5 below does.
    detail_args = _stage_namespace(
        args,
        name=plan_name,
        step=None,
        force=False,
        dry_run=False,
        detail_only=True,
        reconcile=False,
        all=False,
        commit=False,
        repo_root=created_repo_root,
    )
    rc = cmd_detail(detail_args)
    if rc != 0:
        return rc

    # 4. Commit the authoring artifacts so completeness-apply's worktree
    #    isolation has a clean HEAD to cut from. Gate on dirty (like direct-run):
    #    a resumed/idempotent run whose plan+detail are byte-identical to HEAD
    #    stages nothing, and an empty commit would fail and wrongly halt — the
    #    tree is already clean, which is all completeness-apply needs. Targets
    #    ``created_repo_root`` — the root the plan was actually written to.
    if working_tree_dirty(created_repo_root):
        commit_rc, tail = commit_all(
            created_repo_root, f"direct-jira({plan_name}): author plan and detail"
        )
        if commit_rc != 0:
            error(f"direct-jira: committing authoring artifacts failed: {tail}")
            return commit_rc

    # 5. Completeness-apply. Reuses detail's newest saved audit (no re-audit)
    #    and applies the conceptual plan-correctness / plan-completeness gaps in
    #    one parallel replay pass. ``jobs > 1`` selects that path; ``yes=True``
    #    is required (a bare non-interactive -y would otherwise skip the walk).
    apply_args = _stage_namespace(
        args,
        name=plan_name,
        jobs=COMPLETENESS_APPLY_JOBS,
        yes=True,
        id=None,
        anchor=None,
        rewalk=False,
        include_info=False,
        apply_structural=False,
        commit=False,
        repo_root=created_repo_root,
    )
    rc = cmd_completeness_apply(apply_args)
    if rc != 0:
        return rc
    # Commit the applied gaps only if any landed: a no-op apply (no conceptual
    # gaps — the common small-work case) leaves nothing staged, and an
    # unconditional commit_all would fail on the empty commit and wrongly halt.
    if working_tree_dirty(created_repo_root):
        commit_rc, tail = commit_all(
            created_repo_root, f"direct-jira({plan_name}): apply completeness gaps"
        )
        if commit_rc != 0:
            error(f"direct-jira: committing applied gaps failed: {tail}")
            return commit_rc

    # 6. Jira. Export the converged plan as the paired Jira stories and
    # developer handoff. ``jira_tag``
    #    mirrors the ``epic`` getattr-default: direct-jira's own subparser
    #    doesn't define --jira-tag, and cmd_jira reads args.jira_tag
    #    directly (not via getattr), so it must be pre-populated here or
    #    the call below raises AttributeError. Unset is fine — off a TTY
    #    (the unattended-run case this verb is for) cmd_jira auto-derives
    #    and persists a tag rather than blocking, so no flag is required.
    jira_args = _stage_namespace(
        args,
        name=plan_name,
        lint=False,
        output=None,
        epic=getattr(args, "epic", None),
        jira_tag=getattr(args, "jira_tag", None),
        max_hours=getattr(args, "max_hours", 8),
        format=getattr(args, "format", "markdown"),
        no_write=False,
        stdout=False,
        repo_root=created_repo_root,
    )
    return cmd_jira(jira_args)


def _is_code_step(step) -> bool:
    """A step reconcile-code should touch: anything but an explicit ``non-code``.

    Mirrors ``review.py``'s non-code-footprint gate (``change_type !=
    ChangeType.NON_CODE``): docs/test steps declared ``non-code`` have no code to
    reconcile, so a full Claude reconcile pass on them is wasted work. Unclassified
    (``None``) steps are treated as code — the conservative choice.
    """
    return step.change_type != ChangeType.NON_CODE


def cmd_direct_run(args: argparse.Namespace) -> int:
    """Chain ``create → detail → completeness-apply → run --all --commit →
    reconcile-code`` in one process.

    The run-side sibling of :func:`cmd_direct_jira`: same sink hand-off, size
    gate, and namespace-copy idiom, plus the two tail stages ``direct-jira``
    lacks — an ``--all --commit`` execution sweep and a per-code-step
    ``reconcile-code`` loop. Because the run stage's ``--commit`` path refuses a
    dirty tree, the verb commits the authoring artifacts (which ``create`` /
    ``detail`` leave uncommitted) before the run — the same clean HEAD that
    ``completeness-apply``'s worktree isolation needs. A stage's non-zero exit
    stops the chain and is returned as-is; the size-gate and multi-plan-split
    stops are deliberate halts on a usable, re-runnable plan and exit 0.
    """
    warn(
        "direct-run is going away (BACKLOG #376): it exists only to chain "
        "completeness-apply's gap-by-gap apply, which is retiring for the "
        "same reason (slower than a whole-report review, and the slow pace "
        "obscures the convergence signal) -- drive create / detail / run / "
        "reconcile-code as separate, hand-reviewed steps instead."
    )
    repo_root = _resolve_cmd_repo_root(args)

    # 0. Clean-tree precondition. Both the mid-chain ``git add -A`` commits and
    #    completeness-apply's worktree isolation need a clean starting HEAD.
    #    Name the verb, not --commit: the operator ran plain ``direct-run``.
    if working_tree_dirty(repo_root):
        error(
            "direct-run requires a clean working tree (it commits the plan it "
            "authors before running; commit or stash your changes first)"
        )
        return 2

    # 1. Create. Deposit-sink hand-off: cmd_create leaves its CreateResult here.
    args._create_result_sink = []
    rc = cmd_create(args)
    if rc != 0:
        return rc
    sink = args._create_result_sink
    if not sink:
        error("direct-run: create produced no plan to chain onward")
        return 2
    result: CreateResult = sink[-1]

    # 2. Guard the hand-off before chaining forward.
    if result.split_proposal is not None or result.plan_path is None:
        # Multi-plan split: cmd_create already printed the proposal and exited
        # 0. No single plan to run, so stop here (success, not a hard failure).
        print(
            "direct-run: create produced a multi-plan split proposal, not a "
            "single plan — nothing to chain onward. Carve the seed and re-run."
        )
        return 0
    if result.iteration_stage_failure is not None:
        # cmd_create returns 0 here, so read the field, not the rc. An
        # unconverged plan must not be chained forward — stop unconditionally.
        error(
            "direct-run: create's convergence loop did not converge "
            f"({result.iteration_stage_failure}); the plan is on disk but "
            "unconverged — resolve it before chaining to detail/run"
        )
        return 2
    gate = gate_create_result_size(result)
    if not gate.may_proceed:
        print(f"direct-run: {gate.reason}")
        return 0

    plan_name = result.plan_path.stem

    # Resolve the root ``create`` actually wrote to (it may differ from the
    # pre-create ``repo_root`` under a --from-existing relocation). Refuses a
    # nested/ancestor relocation and sweeps the original root's own dirt before
    # every later stage repoints at ``created_repo_root``. Keep ``repo_root``
    # intact for step 3's cleanliness check.
    created_repo_root, rc = _resolve_created_repo_root(
        result, repo_root, verb="direct-run", plan_name=plan_name
    )
    if created_repo_root is None:
        return rc

    # Safety check: on a relocated (disjoint) root, abort before ``detail`` if
    # that root holds uncommitted work beyond ``create``'s own writes, rather
    # than fold a stranger's changes into the stage-4 authoring commit. Inert
    # when there was no relocation.
    rc = _guard_relocated_root_clean(
        created_repo_root, repo_root, result, verb="direct-run"
    )
    if rc != 0:
        return rc

    # 3. Detail. ``detail_only=True`` pins the completeness tail's --iterate ON
    #    (deterministic well-formedness convergence + a saved conceptual gap
    #    map) while keeping the costly per-step detail-quality loop off. The
    #    tail saves conceptual gaps unapplied (#85) — stage 5 below applies them.
    detail_args = _stage_namespace(
        args,
        name=plan_name,
        step=None,
        force=False,
        dry_run=False,
        detail_only=True,
        reconcile=False,
        all=False,
        commit=False,
        repo_root=created_repo_root,
    )
    rc = cmd_detail(detail_args)
    if rc != 0:
        return rc

    # 4. Commit the authoring artifacts. create/detail leave the plan file,
    #    detail bundle, and manifest uncommitted; the run stage's --commit gate
    #    refuses a dirty tree, so clear it here. Gate on dirty: a no-op leaves
    #    nothing staged and an empty commit would fail and wrongly halt. Targets
    #    ``created_repo_root`` — the root the plan was actually written to.
    if working_tree_dirty(created_repo_root):
        commit_rc, tail = commit_all(
            created_repo_root, f"direct-run({plan_name}): author plan and detail"
        )
        if commit_rc != 0:
            error(f"direct-run: committing authoring artifacts failed: {tail}")
            return commit_rc

    # 5. Completeness-apply. Reuses detail's newest saved audit (no re-audit)
    #    and applies the conceptual gaps in one parallel replay pass in
    #    worktrees off the clean HEAD from stage 4. ``jobs > 1`` selects that
    #    path; ``yes=True`` is required (a bare non-interactive -y skips the walk).
    apply_args = _stage_namespace(
        args,
        name=plan_name,
        jobs=COMPLETENESS_APPLY_JOBS,
        yes=True,
        id=None,
        anchor=None,
        rewalk=False,
        include_info=False,
        apply_structural=False,
        commit=False,
        repo_root=created_repo_root,
    )
    rc = cmd_completeness_apply(apply_args)
    if rc != 0:
        return rc
    # Commit the applied gaps only if any landed, so the run stage's clean-tree
    # gate passes; a no-op apply (no conceptual gaps) leaves nothing to commit.
    if working_tree_dirty(created_repo_root):
        commit_rc, tail = commit_all(
            created_repo_root, f"direct-run({plan_name}): apply completeness gaps"
        )
        if commit_rc != 0:
            error(f"direct-run: committing applied gaps failed: {tail}")
            return commit_rc

    # 6. Run. ``--all --commit`` sweeps every runnable step, committing each
    #    green step (keeps the tree clean between steps for the test-authoring
    #    gate). Reset ``iterate=False`` so cmd_run's non-reconcile path doesn't
    #    warn about --iterate inherited from create's default.
    run_args = _stage_namespace(
        args,
        name=plan_name,
        mode="run",
        step=None,
        dry_run=False,
        # ``yes=True`` forced: direct-run is an unattended one-shot pipeline
        # (like its completeness-apply stage), so its internal run stage must not
        # block mid-chain on cmd_run's missing-detail confirm. Matches the -y
        # help string; the operator's review point is the post-run /code-review.
        yes=True,
        allow_missing_parent=False,
        no_walk=False,
        no_save=False,
        max_steps=None,
        reconcile=False,
        archive=False,
        all=True,
        commit=True,
        iterate=False,
        repo_root=created_repo_root,
    )
    rc = cmd_run(run_args)
    if rc != 0:
        return rc

    # 7. Preserve direct-run's per-code-step scope and non-code skip.
    plan = parse_plan(result.plan_path)
    for step in plan.steps:
        if not _is_code_step(step):
            continue
        reconcile_args = _stage_namespace(
            args,
            name=plan_name,
            step=step.id,
            dry_run=False,
            # ``yes=True`` forced: direct-run is unattended by design, so the
            # reconcile stage auto-applies inline like completeness-apply rather
            # than blocking on a per-finding walk. This is the documented
            # reconcile-auto-apply known limit; review happens post-run via
            # /code-review. (Do not copy the operator's ``yes`` through here.)
            yes=True,
            allow_missing_parent=False,
            no_walk=False,
            no_save=False,
            reuse=False,
            reuse_id=None,
            repo_root=created_repo_root,
        )
        rc = cmd_reconcile_code(reconcile_args)
        if rc != 0:
            error(
                f"direct-run: reconcile-code failed on step {step.id} "
                f"(rc {rc}); steps before it are reconciled (uncommitted), "
                f"steps after it are not — resume with "
                f"plan-tool reconcile-code {plan_name} --step {step.id}"
            )
            return rc

    return 0


def register(subparsers) -> dict[str, Handler]:
    """Add the ``direct-jira`` / ``direct-run`` subparsers and return their map.

    Both verbs open with a ``create`` stage, then copy that namespace and
    override per stage, so the parser must supply every create-side field the
    create stage reads directly (``from_description`` / ``from_existing`` /
    ``slug`` / ``output_dir`` / ``yes``) plus the ``--iterate`` toggle — a
    missing one raises ``AttributeError`` mid-chain. Those live on a shared
    ``add_help=False`` create-side parent, mirroring the ``yes`` / seed-source
    subset of :func:`plan_tool.cli.authoring.register`. The stage-specific
    fields (detail's ``force``, jira's ``lint``, run's ``mode`` / ``all`` /
    ``commit``, …) are set by the verbs, not the parser; the global flags
    (``--backend`` / ``--model`` / ``--on-rate-limit`` / ``--fallback-backend``
    / verbosity) come from ``make_base_parser`` and are already on every
    namespace. Keeps the module a thin leaf: imports only the cycle-free
    ``plan_tool.cli.parser`` for ``Handler``, never ``plan_tool.cli.app``.
    """
    create_parent = argparse.ArgumentParser(add_help=False)
    create_parent.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=(
            "auto-accept Y/N confirmation prompts across every chained stage "
            "(the completeness-apply and run stages already run non-interactive)."
        ),
    )
    create_parent.add_argument(
        "slug",
        nargs="?",
        default=None,
        help=(
            "canonical slug for the plan the create stage authors — lowercase, "
            "dashes, no priority prefix, no .md suffix. Optional: suggested from "
            "the seed when omitted (taken as-is under --yes)."
        ),
    )
    source = create_parent.add_mutually_exclusive_group()
    source.add_argument(
        "--from",
        dest="from_description",
        default=None,
        metavar="DESCRIPTION",
        help="ask claude for initial steps given this inline description",
    )
    source.add_argument(
        "--from-existing",
        dest="from_existing",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "read an existing plan or notes file and use its contents as the "
            "create seed (mutually exclusive with --from)"
        ),
    )
    create_parent.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "directory to write the new plan into (default: "
            "docs/implementation-plans/ under the repo root)"
        ),
    )
    create_parent.add_argument(
        "--iterate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "run the create stage's post-write convergence loop until findings "
            "stabilize (default ON; pass --no-iterate for a one-shot write)"
        ),
    )

    subparsers.add_parser(
        "direct-jira",
        help=(
            "DEPRECATED, going away (BACKLOG #376) — exists only to chain "
            "completeness-apply's gap-by-gap apply, retiring for the same "
            "reason (slow, and obscures the convergence signal); drive "
            "create / detail / jira as separate, hand-reviewed steps instead. "
            "chain create → detail → completeness-apply → jira in one process "
            "and publish paired Jira stories plus a developer handoff (small "
            "plans only)"
        ),
        parents=[create_parent],
    )
    subparsers.add_parser(
        "direct-run",
        help=(
            "DEPRECATED, going away (BACKLOG #376) — exists only to chain "
            "completeness-apply's gap-by-gap apply, retiring for the same "
            "reason (slow, and obscures the convergence signal); drive "
            "create / detail / run / reconcile-code as separate, "
            "hand-reviewed steps instead. "
            "chain create → detail → completeness-apply → run → reconcile-code "
            "in one process (small plans only)"
        ),
        parents=[create_parent],
    )
    return {"direct-jira": cmd_direct_jira, "direct-run": cmd_direct_run}
