"""Authoring command module — the plan-writing verbs.

Holds the ``create`` handler (``cmd_create``) and its helpers
(``_cmd_create_reprocess``, ``_read_seed_body``,
``_render_split_proposal_markdown``, ``_emit_split_proposal``) plus the
``detail`` handler (``cmd_detail``), and a :func:`register` that
contributes the ``create`` / ``detail`` subparsers to the shared
``add_subparsers`` action (see :mod:`plan_tool.cli.parser`).

Like every per-intent command module, this imports only the cycle-free
leaves (:mod:`plan_tool.cli.console`, :mod:`plan_tool.cli.context`,
:mod:`plan_tool.cli.parser`) and the domain packages — never
:mod:`plan_tool.cli.app` at module top. ``app`` imports *this* module to
build ``COMMAND_MODULES``, so the dependency edge runs ``app → authoring``;
the two functions ``cmd_detail`` still needs from ``app``
(``_cmd_detail_reconcile`` / ``cmd_completeness``, both bound for later
carves) are reached via a function-body ``from plan_tool.cli import app``
so the edge stays one-directional and cycle-free. ``app`` re-imports the
moved names back into its own namespace so the package surface stays
intact.

``create_plan`` and ``generate_detail`` are module globals here: the
handlers read them as bare names, dispatch routes the handlers from this
module's namespace, so the legacy create/detail test suites patch
``plan_tool.cli.authoring.create_plan`` / ``.generate_detail`` to
intercept the claude-invoking orchestrators.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Optional


_TRACKED_SEED_MARKER_RE = re.compile(
    r"<!-- plan-tool-roadmap-seed-state: [^\n]* -->"
)


def _experiment_arm_overrides(args=None) -> dict:
    """Parse repeated ``--experiment-arm NAME=ARM`` flags into ``{name: arm}``.

    The generic, future-proof selector: a new experiment is selectable with no
    new flag. Malformed entries (no ``=``) are ignored.
    """
    overrides: dict = {}
    for entry in getattr(args, "experiment_arm", None) or []:
        name, sep, arm = str(entry).partition("=")
        if sep and name.strip():
            overrides[name.strip()] = arm.strip()
    return overrides


def resolve_experiment_arm(experiment, args=None) -> str:
    """Resolve the active arm of a registered :class:`Experiment`.

    Precedence: a dedicated flag (e.g. ``--prompt-mode``) > the generic
    ``--experiment-arm <name>=<arm>`` override > the experiment's env var >
    its default arm. The experiment owns the env/default + arm validation.
    """
    overrides = _experiment_arm_overrides(args)
    # Dedicated flags by experiment name (back-compat ergonomics).
    dedicated = {"prompt-mode": getattr(args, "prompt_mode", None)}
    flag = dedicated.get(experiment.name) or overrides.get(experiment.name)
    return experiment.resolve_arm(flag)


def _resolve_prompt_mode(args=None) -> str:
    """Resolve the prompt-mode arm (``combined`` default | ``split``).

    Thin wrapper over the generic experiment resolver for the prompt-mode
    experiment. Precedence: ``--prompt-mode`` > ``--experiment-arm
    prompt-mode=…`` > ``PLAN_TOOL_PROMPT_MODE`` > ``combined``.
    """
    from plan_tool.scenario_capture import PROMPT_MODE_EXPERIMENT

    return resolve_experiment_arm(PROMPT_MODE_EXPERIMENT, args)

from plan_tool.canonical import read_canonical_provenance
from plan_tool.cli.console import (
    _print_detail_summary,
    _print_next_steps,
    _repo_rel,
    _report_archive_result,
    _short_path,
)
from plan_tool.cli.context import (
    _load_context,
    _resolve_cmd_repo_root,
    _resolve_iterative_budget,
)
from plan_tool.cli.parser import Handler, make_yes_parent
from plan_tool.completeness_report import (
    ABSENT_BLOCKING_VERDICT,
    BLOCKING_STATE_ABSENT,
    UNTRUSTED_STALE_REVISION,
    BlockingVerdict,
    _reaudit_command,
    blocking_verdict_from_gate,
    next_stage_command,
)
from plan_tool.convergence import (
    DEFAULT_ITERATION_BUDGET_SECONDS,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_STALL_ROUNDS,
)
from plan_tool.create import (
    DEFAULT_OUTPUT_DIR,
    ArchiveResult,
    CreateError,
    FileBackedSourceRoute,
    SplitProposal,
    SplitProposalEntry,
    archive_existing_source,
    create_plan,
    extract_file_path_candidates,
    read_existing_description,
    resolve_create_slug,
    resolve_output_dir,
    reject_unmatched_create_sources,
    select_file_backed_source,
    shell_claude_invoker,
    file_backed_route_lifecycle,
    validate_from_existing_seed,
)
from plan_tool.fileio import durable_create_text
from plan_tool.detail import (
    DetailError,
    _confirm_merge,
    generate_detail,
    merge_steps,
    shell_detail_invoker,
    split_step,
)
from plan_tool.detail_artifacts import DetailFormatError
from plan_tool.scope_fence import _fenced_code_spans, _strip_frontmatter
from plan_tool.fingerprint import compute_code_fingerprint
from plan_tool.grounding import write_grounding
from plan_tool.locator import (
    find_umbrella_root,
    load_manifest_plan_paths,
    record_known_root,
    resolve_plan_for_context,
    resolve_repo_root,
    slug_from_filename,
)
from plan_tool.pathutil import literal_path
from plan_tool.roadmap_artifacts import (
    RoadmapArtifactError,
    parse_plans_artifact,
)
from plan_tool.roadmap_seed_manifest import (
    DRAFT_SEED_STATE_CURRENT,
    DRAFT_SEED_STATE_STALE,
    NoPublishedRoadmapVersionError,
    classify_draft_seeds,
    no_published_version_message,
)
from plan_tool.roadmap_versions import (
    VERSION_ARTIFACT_KEYS,
    RoadmapVersionError,
    load_accepted_version,
)
from plan_tool.roadmap_seed_state import (
    RoadmapSeedStateError,
    TrackedSeedLocation,
    load_seed_state,
    locate_tracked_seed,
)
from plan_tool.parser import UnsupportedPlanFormatVersionError, parse_plan
from plan_tool.reprocess import (
    ReprocessError,
    find_archive_for_slug,
    reprocess_plan,
)
from plan_tool.review_persistence import (
    AuditInputSnapshot,
    compute_plan_fingerprint,
    normalize_qualified_result,
)
from plan_tool.run_log import RunLogWriter, _bounded_violations
from plan_tool.style import detail, error, info, success, warn


# --- ``detail --commit`` git helpers --------------------------------------
#
# Generic git plumbing lives in the cycle-free ``gitcommit`` leaf (shared
# with the completeness verbs); only the detail-specific subject is local.
# ``_working_tree_dirty`` is re-exported under its historical name so the
# test suite's ``authoring._working_tree_dirty`` import keeps resolving.

from plan_tool.cli.gitcommit import commit_all as _commit_all
from plan_tool.cli.gitcommit import working_tree_dirty as _working_tree_dirty

# Branch-awareness preflight (the create-time namespace-collision gate). These
# compose step 1's config readers, step 2's git branch reads/mutators, step 3's
# ad-hoc binding store, and step 4's ownership lookup — all cycle-free leaves
# below this module.
from plan_tool.branch_binding import clear_binding, set_binding
from plan_tool.branch_ownership import branch_owner
from plan_tool.cli.gitcommit import (
    branch_exists,
    checkout_existing_branch,
    create_and_checkout_branch,
    current_branch,
    default_branch,
    list_branches,
    remote_collisions,
    warn_recommended_paths_ignored,
)
from plan_tool.project_config import (
    branch_awareness_enabled,
    branch_prefixes,
    derive_branch,
)


def _detail_step_commit_subject(slug: str, step_id: int, title: str) -> str:
    """Commit subject for one converged step of a ``detail --commit`` run
    (pure, so a test can assert the exact format without shelling out)."""
    short = " ".join(title.split())
    if len(short) > 60:
        short = short[:57].rstrip() + "…"
    return f"plan({slug}): detail step {step_id} — {short}"


def _detail_batch_commit_subject(slug: str, n_steps: int) -> str:
    """Commit subject for a single end-of-run batch commit — the concurrent
    (``--jobs>1``) path, which authors in parallel and cannot commit per step."""
    plural = "step" if n_steps == 1 else "steps"
    return f"plan({slug}): detail — authored {n_steps} {plural}"


def _detail_residual_commit_subject(slug: str) -> str:
    """Commit subject for the residual sweep after a per-step ``detail --commit``
    run — lessons / plan edits not tied to a single step's completion."""
    return f"plan({slug}): detail — residual authoring edits"


def _commit_if_dirty(
    repo_root: Path, subject: str
) -> "Optional[tuple[int, str]]":
    """Commit all changes under ``subject`` when the tree is dirty; ``None`` on a
    clean tree. **Never raises** — a git subprocess failure (``OSError``: missing
    binary, removed cwd, EMFILE) or a ``ValueError`` / ``UnicodeDecodeError`` from
    ``subprocess.run(text=True)`` decoding non-UTF-8 git/hook output degrades to a
    non-zero ``(rc, tail)`` so every caller flags the run rather than crashing.
    Shared by the per-step commit and the end-of-run sweep so both are guarded
    identically.
    """
    try:
        if not _working_tree_dirty(repo_root):
            return None
        return _commit_all(repo_root, subject)
    except (OSError, ValueError) as exc:
        return 1, f"git subprocess error: {exc}"


def _commit_detail_step(
    repo_root: Path, *, slug: str, step_id: int, title: str
) -> "Optional[tuple[int, str]]":
    """Commit one converged step's changes (#122) via :func:`_commit_if_dirty`,
    so an interrupted batch keeps completed steps. ``None`` on a clean tree."""
    return _commit_if_dirty(
        repo_root, _detail_step_commit_subject(slug, step_id, title)
    )


def _confirm_repo_root(
    repo_root: Path,
    *,
    yes: bool,
    input_fn=input,
) -> Optional[Path]:
    """Resolve which directory to use as the plan root when it isn't the cwd.

    Returns the directory to use, or ``None`` to abort. When the discovered
    root already equals the cwd there is nothing to confirm — it is returned
    unchanged with no warning. Otherwise warns that the root differs and
    offers three choices: keep the discovered ``[r]oot``, switch to the
    ``[c]urrent`` directory, or ``[a]bort`` (the default, so a
    wrong-directory invocation doesn't silently scatter plan files into an
    ancestor or sibling repo).

    Non-interactive callers (``-y`` or a non-TTY stdin, e.g. CI / piped) get
    the warning and then keep the discovered root without blocking —
    re-prompting there would deadlock, and ``-y`` means "take the offered
    choice".
    """
    cwd = Path.cwd().resolve()
    root = repo_root.resolve()
    if root == cwd:
        return root
    warn(f"discovered plan root {root} is not the current directory {cwd}")
    if yes or not sys.stdin.isatty():
        return root
    raw = input_fn(
        f"Use the discovered [r]oot ({root}), the [c]urrent directory "
        f"({cwd}), or [a]bort? [r/c/A] "
    ).strip().lower()
    if raw in {"r", "root", "y", "yes"}:
        return root
    if raw in {"c", "cur", "current"}:
        return cwd
    return None


def _confirm_invalidated_roadmap_seed(
    location: TrackedSeedLocation | None, *, yes: bool, input_fn=input
) -> bool:
    """Require an explicit assent before ``create`` consumes an unsafe seed.

    A promoted ``plan-seeds/`` copy (``location.via_marker``) is validated
    against the sidecar's persisted lifecycle status rather than
    ``classify_draft_seeds``: that classifier's states all describe the
    *draft* file's live on-disk condition, but a promoted copy's own bytes —
    not the draft's — are what a consumer is about to read, and the draft is
    routinely archived or deleted once its promotion lands. Gating a promoted
    copy on the draft's liveness would spuriously refuse an intact promotion
    the moment its source draft is archived.
    """
    if location is None:
        return True
    try:
        plans_dir = location.state_path.parent.parent.parent
        accepted = load_accepted_version(plans_dir=plans_dir, slug=location.roadmap_slug)
        if accepted is None:
            raise NoPublishedRoadmapVersionError(
                no_published_version_message(plans_dir, location.roadmap_slug)
            )
        members = dict(zip(VERSION_ARTIFACT_KEYS, accepted.artifact_bytes, strict=True))
        artifact = parse_plans_artifact(members["plans"].decode("utf-8"))
        plan_row = next(
            (row for row in artifact.plans if row.id == location.plan_id), None
        )
        if plan_row is None:
            error(
                f"roadmap seed '{location.plan_id}' from '{location.roadmap_slug}' "
                "is no longer present in its roadmap"
            )
            return False
        if location.via_marker:
            entry = load_seed_state(location.state_path)["seeds"].get(
                location.plan_id
            )
            is_stale = entry is not None and entry.get("status") == "invalidated"
            classification_detail = ""
            non_current_state = DRAFT_SEED_STATE_STALE if is_stale else None
        else:
            classification = classify_draft_seeds(
                artifact, plans_dir=plans_dir, slug=location.roadmap_slug
            ).get(location.plan_id)
            if classification is None:
                error(
                    f"roadmap seed '{location.plan_id}' from "
                    f"'{location.roadmap_slug}' is no longer present in its roadmap"
                )
                return False
            non_current_state = (
                None
                if classification.state == DRAFT_SEED_STATE_CURRENT
                else classification.state
            )
            classification_detail = classification.detail
    except (
        RoadmapArtifactError,
        RoadmapSeedStateError,
        RoadmapVersionError,
        UnicodeDecodeError,
    ) as exc:
        error(str(exc))
        return False
    if non_current_state is None:
        return True
    if non_current_state == DRAFT_SEED_STATE_STALE:
        message = (
            f"roadmap seed '{location.plan_id}' from '{location.roadmap_slug}' "
            "is invalidated by a roadmap revision"
        )
        non_tty_description = "the stale seed"
        prompt_description = "this stale seed"
    else:
        message = (
            f"draft seed for plan '{location.plan_id}' in roadmap "
            f"'{location.roadmap_slug}' classifies as '{non_current_state}'"
        )
        if classification_detail:
            message = f"{message}: {classification_detail}"
        non_tty_description = "this seed"
        prompt_description = "this seed"
    if yes:
        detail(f"{message}; continuing because -y explicitly confirmed it")
        return True
    if not sys.stdin.isatty():
        error(
            f"{message}; re-run with -y to explicitly continue with {non_tty_description}, "
            "or run `plan-tool roadmap "
            f"{location.roadmap_slug} --refresh-seeds` first"
        )
        return False
    try:
        answer = input_fn(
            f"{message}. Continue with {prompt_description}? [y/N]: "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in {"y", "yes"}


def _create_branch_collision_gate(
    args: argparse.Namespace,
    *,
    repo_root: Path,
    slug: str,
    registered_slugs: set[str],
    input_fn=input,
) -> Optional[int]:
    """Disambiguate an unowned ``plan/<slug>`` collision before authoring.

    A flag-check-first preflight for :func:`cmd_create`. Return contract:
    ``None`` proceeds with the create (possibly after switching to a freshly
    created disambiguated branch and ad-hoc-binding the plan to it); an ``int``
    is the rc ``cmd_create`` returns immediately (``2`` decline / dirty-tree
    refusal, ``1`` git failure).

    Inert when branch awareness is off (every repo today): returns ``None``
    before any git I/O. Also a no-op on a non-git / detached-HEAD tree
    (``current_branch`` -> ``None``), so the restore-on-failure path always has
    a real invocation branch to return to. Only an existing ``plan/<slug>``
    that **no registered plan owns** is the foreign collision this warns on; an
    owned branch is left to the slug-uniqueness path / run guard.

    On collision-and-consent over a clean tree with a resolvable default
    branch, it creates the first-free ``plan/<slug>-N`` (N>=2) **from the
    default branch**, ad-hoc-binds ``slug`` to it, and records a rollback
    context on ``args`` so ``cmd_create`` can undo the switch+bind if the
    downstream author fails.
    """
    if not branch_awareness_enabled(repo_root):
        return None

    # Read once; the restore path below needs a real branch to return to.
    invocation = current_branch(repo_root)
    if invocation is None:
        return None

    prefixes = branch_prefixes(repo_root)
    derived = derive_branch(slug, prefixes)
    if not branch_exists(repo_root, derived):
        # No local branch to act on — but the derived name may already be
        # claimed only as a pushed remote-tracking ref. Read the offline ref
        # list once (no network) and warn-and-proceed if so; this is a pure
        # advisory tier — no disambiguation, bind, or checkout.
        collisions = remote_collisions(list_branches(repo_root), derived, prefixes)
        if collisions:
            warn(
                f"branch '{derived}' already exists on the remote as "
                f"{', '.join(collisions)} (as of your last fetch — no network "
                f"performed). The create proceeds on '{invocation}'; run "
                f"'git fetch' to refresh, or pick a distinct slug if that "
                f"remote work is unrelated."
            )
        return None
    if branch_owner(repo_root, derived, registered_slugs, prefixes) is not None:
        # A registered plan owns it (convention or ad-hoc) — not a foreign
        # collision; defer to the slug-uniqueness path / run guard.
        return None

    warn(
        f"branch '{derived}' already exists but no registered plan owns it "
        f"(likely unrelated local work or another developer's plan)."
    )
    proceed = getattr(args, "yes", False) or not sys.stdin.isatty()
    if not proceed:
        raw = input_fn(
            f"branch {derived} already exists and is unowned; [c]reate a "
            f"disambiguated branch from the default branch, or [a]bort? [c/A] "
        ).strip().lower()
        proceed = raw in {"c", "create", "y", "yes"}
    if not proceed:
        return 2

    # Anchor the disambiguated branch on the default branch. ``default_branch``
    # returns a ``PLAN_TOOL_DEFAULT_BRANCH`` value verbatim even when it does
    # not resolve, so an env-named default that is not a real local branch is
    # undeterminable exactly like the ``None`` case.
    base = default_branch(repo_root)
    if base is None or not branch_exists(repo_root, base):
        warn(
            f"the default branch is undeterminable, so '{derived}' cannot be "
            f"disambiguated — protection skipped; the foreign branch "
            f"'{derived}' is now silently convention-owned by plan '{slug}', "
            f"re-exposing the run-on-foreign-work hazard. Set "
            f"PLAN_TOOL_DEFAULT_BRANCH or configure origin/HEAD to restore it."
        )
        return None

    if _working_tree_dirty(repo_root):
        error(
            f"branch '{derived}' collides with unrelated work; disambiguating "
            f"needs a clean working tree (commit or stash your changes first)."
        )
        return 2

    # First-free suffix off the *branch* name (preserves the configured prefix).
    candidate: Optional[str] = None
    for n in range(2, 101):
        probe = f"{derived}-{n}"
        if not branch_exists(repo_root, probe):
            candidate = probe
            break
    if candidate is None:
        error(
            f"could not find a free disambiguated branch name for '{derived}' "
            f"(tried -2 through -100); resolve the collision manually."
        )
        return 1

    # Create FROM the default branch: ``gitcommit`` exposes only switch +
    # create-from-HEAD, so switch to ``base`` then ``switch -c`` the candidate.
    rc, tail = checkout_existing_branch(repo_root, base)
    if rc != 0:
        error(tail or f"failed to switch to default branch '{base}'.")
        return 1
    rc2, tail2 = create_and_checkout_branch(repo_root, candidate)
    if rc2 != 0:
        # The first switch already left ``invocation`` for ``base`` — restore
        # it so a failed create never strands the developer on the default
        # branch with no plan.
        checkout_existing_branch(repo_root, invocation)  # best-effort
        error(
            f"{tail2 or f'failed to create branch {candidate}'}; "
            f"restored branch {invocation}"
        )
        return 1

    # Bind the new plan to its disambiguated branch so ``expected_branch`` /
    # the run guard recognize ``candidate`` as Tier-1 owned (not the foreign
    # derived name the disambiguation existed to avoid).
    set_binding(repo_root, slug, candidate)
    # Only the disambiguation path sets this; every no-op/refusal return leaves
    # it unset so ``cmd_create`` rolls back exactly this case.
    args._branch_collision_rollback = (invocation, slug, candidate)
    success(
        f"created disambiguated branch {candidate} from {base} and bound "
        f"{slug} to it"
    )
    return None


def _rollback_branch_collision(args: argparse.Namespace, repo_root: Path) -> None:
    """Undo a disambiguation gate's switch+bind when create leaves no plan.

    Best-effort and idempotent: clears the ad-hoc binding (so the orphaned
    candidate branch is no longer Tier-1 owned), restores the invocation branch
    (so the developer is not stranded on the candidate), and names the leftover
    ``candidate`` branch — the tool never deletes branches, so it is left in
    place but reported. A no-op unless the gate recorded a rollback context.
    """
    ctx = getattr(args, "_branch_collision_rollback", None)
    if ctx is None:
        return
    invocation, slug, candidate = ctx
    clear_binding(repo_root, slug)
    if invocation:
        checkout_existing_branch(repo_root, invocation)  # best-effort
    warn(
        f"no plan was created; cleared binding {slug} and restored branch "
        f"{invocation}; left empty branch {candidate} — remove it manually "
        f"if unwanted."
    )
    # Consume the context so a retry / later path doesn't double-roll-back.
    args._branch_collision_rollback = None


def _report_retained_create_artifact(artifact: object) -> None:
    """Print recovery guidance without rolling back the artifact's branch binding."""
    path = getattr(artifact, "path", None)
    registered = getattr(artifact, "registered", False)
    parse_valid = getattr(artifact, "parse_valid", False)
    if registered:
        error(
            f"create retained registered plan {path}; finalization is incomplete, "
            "so inspect and repair it in place before continuing"
        )
    elif parse_valid:
        error(
            f"create retained parse-valid unregistered plan {path}; preserve it, "
            "explicitly adopt it after review, or use it as --from-existing "
            "for a separate conversion"
        )
    else:
        error(
            f"create retained invalid unregistered plan {path}; preserve it for "
            "repair or remove it deliberately before retrying"
        )


def _archive_normalized_artifact(
    source_path: Path,
    plan_path: Path,
    normalized_payload: str,
    *,
    repo_root: Path,
    archived_sink: Optional[list[str]] = None,
) -> bool:
    """Archive one normalized artifact after one bounded collision recovery.

    ``archived_sink`` receives each archive destination written, for ``run_end``.
    """
    normalized_path = source_path.parent / f"{source_path.stem}.distilled.md"
    recovered_collision = False
    try:
        durable_create_text(normalized_path, normalized_payload)
    except FileExistsError:
        recovered_collision = True
        if normalized_path.is_symlink() and not normalized_path.exists():
            try:
                normalized_path.unlink()
            except OSError as exc:
                warn(
                    f"could not clear dangling normalized artifact link "
                    f"{literal_path(normalized_path, repo_root)}: {exc}; "
                    "retained source"
                )
                return False
        else:
            archive = archive_existing_source(
                normalized_path, plan_path, repo_root=repo_root
            )
            _report_archive_result(archive, repo_root=repo_root)
            if archived_sink is not None:
                archived_sink.extend(_archive_targets(archive.archived, repo_root))
            if not any(
                original == normalized_path for original, _ in archive.archived
            ):
                return False
    except OSError as exc:
        _warn_normalized_artifact_write_failure(normalized_path, repo_root, exc)
        return False

    if recovered_collision:
        try:
            durable_create_text(normalized_path, normalized_payload)
        except FileExistsError:
            warn(
                f"normalized artifact collision persisted at "
                f"{literal_path(normalized_path, repo_root)}; retained source"
            )
            return False
        except OSError as exc:
            _warn_normalized_artifact_write_failure(normalized_path, repo_root, exc)
            return False

    archive = archive_existing_source(
        normalized_path, plan_path, repo_root=repo_root
    )
    _report_archive_result(archive, repo_root=repo_root)
    if archived_sink is not None:
        archived_sink.extend(_archive_targets(archive.archived, repo_root))
    return any(original == normalized_path for original, _ in archive.archived)


def _warn_normalized_artifact_write_failure(
    normalized_path: Path, repo_root: Path, exc: OSError
) -> None:
    """Keep the matching first-write and retry failure guidance identical."""
    warn(
        f"could not create normalized artifact "
        f"{literal_path(normalized_path, repo_root)}: {exc}; retained source"
    )


def cmd_create(args: argparse.Namespace) -> int:
    """Author a new plan file end-to-end (authoring).

    Intent: take the user from "I have an idea / notes / a structured
    doc" to a registered plan-tool plan with YAML frontmatter, a
    body skeleton, and an entry in ``structured_plans.json``. Two
    seed shapes are supported:

    - ``--from <description>`` — inline prose; claude proposes steps.
    - ``--from-existing <path>`` — a file. If the file matches the
      canonical layout, steps are lifted deterministically — no claude
      call. Otherwise claude proposes steps from the prose.

    Sits at the head of the authoring chain — :func:`cmd_detail`
    fills in per-step specs after. Resumable via the checkpoint
    cache (see :func:`cmd_checkpoint`); pass ``--no-resume`` to force
    fresh claude calls.

    Exit codes: ``0`` for a published plan or a file-backed split proposal;
    ``2`` for input, collision, and file-backed preparation refusals; ``1``
    for a hard authoring error.

    A free-form or oversize seed is first run through the distill
    first-pass (``propose_distilled_seed_from_claude``), which either
    reorganizes it into a compact canonical body or — when it spans
    multiple independent efforts — returns a multi-plan split proposal
    that ``create`` saves and surfaces instead of writing a plan. For
    ``--from-existing`` input this route always runs; ``--no-distill`` keeps
    its raw-seed bypass only for inline ``--from`` input.

    Note that :func:`cmd_create` is the *only* subcommand that
    writes new plan frontmatter or registers a plan in the
    manifest.
    """
    try:
        repo_root = _resolve_cmd_repo_root(args)
    except FileNotFoundError as exc:
        # No run log — we don't know where to put it yet.
        error(str(exc))
        return 2

    if getattr(args, "reprocess", False):
        return _cmd_create_reprocess(args)

    description: Optional[str] = args.from_description
    source_path: Optional[Path] = None
    seed_body: Optional[str] = None
    tracked_seed_location: TrackedSeedLocation | None = None
    if args.from_existing is not None:
        source_path = args.from_existing.resolve()
        try:
            description = read_existing_description(source_path)
        except CreateError as exc:
            error(str(exc))
            return 2
        seed_body = _read_seed_body(source_path, description)
        try:
            validate_from_existing_seed(
                select_file_backed_source(seed_body, description), source=source_path
            )
        except CreateError as exc:
            error(str(exc))
            return 2
        try:
            tracked_seed_location = locate_tracked_seed(
                source_path, repo_root=repo_root
            )
        except (RoadmapArtifactError, RoadmapSeedStateError) as exc:
            error(str(exc))
            return 2
        if not _confirm_invalidated_roadmap_seed(
            tracked_seed_location, yes=args.yes
        ):
            return 2

    if seed_body is not None or description is not None:
        try:
            reject_unmatched_create_sources(
                seed_body=seed_body,
                from_description=description,
                source=source_path if source_path is not None else "create seed",
            )
        except CreateError as exc:
            error(str(exc))
            return 2

    # Slug resolution. ``slug`` is now an optional positional: when the
    # user omits it we suggest one from the seed/description (claude, with
    # a deterministic slugify fallback) and let them confirm or edit at
    # the prompt. Must run before RunLogWriter.start below so the run log
    # lands under the resolved slug rather than ``None``.
    try:
        args.slug = resolve_create_slug(
            args.slug,
            seed_body or description,
            shell_claude_invoker,
            yes=args.yes,
        )
    except CreateError as exc:
        error(str(exc))
        return 2

    # Whether the operator pinned the root explicitly (--repo-root flag or
    # PLAN_TOOL_REPO_ROOT). When set, the operator owns the choice: we skip
    # both the seed-derived umbrella override and the cwd-mismatch confirm.
    explicit_root = (
        getattr(args, "repo_root", None) is not None
        or resolve_repo_root(None) is not None
    )

    # Repo-root selection from seed: scan the seed for file references
    # and use the ``.git`` ancestor that "controls" the files as the
    # plan root. When all files share one owning repo we use it (even
    # when narrower than the cwd-derived root — a ``.agents/``-only
    # plan invoked from the outer project picks up the inner repo).
    # When files span multiple owning repos we use the deepest common
    # ancestor as the umbrella, even if that ancestor isn't itself a
    # ``.git`` directory. Override-aware: if --repo-root /
    # PLAN_TOOL_REPO_ROOT is set, the operator owns the choice and
    # we don't second-guess them.
    if not explicit_root and (seed_body or description):
        seed_text = _TRACKED_SEED_MARKER_RE.sub(
            "", "\n".join(s for s in (seed_body, description) if s)
        )
        file_candidates = extract_file_path_candidates(seed_text)
        if file_candidates:
            umbrella = find_umbrella_root(
                file_candidates,
                search_from=repo_root,
                fallback=repo_root,
            )
            if (
                umbrella is not None
                and umbrella.resolve() != repo_root.resolve()
            ):
                relation = (
                    "narrower (inside)"
                    if str(umbrella.resolve()).startswith(str(repo_root.resolve()))
                    else "broader (outside)"
                )
                info(
                    f"seed file references resolve under {umbrella} "
                    f"({relation} the cwd-derived root {repo_root}); using "
                    f"the seed-derived root. Override with --repo-root if undesired."
                )
                repo_root = umbrella.resolve()
                record_known_root(repo_root)

    # The discovered root drives where the plan, its detail files, and the
    # manifest entry land — and the launcher later runs steps from it. When
    # it isn't the cwd (commonly: invoked from a subdirectory, so the root is
    # an ancestor; or a seed-derived umbrella jumped to a sibling repo), warn
    # and let the operator keep that root, switch to the current directory,
    # or abort. Skipped when the root was pinned explicitly — they named it.
    if not explicit_root:
        chosen = _confirm_repo_root(repo_root, yes=args.yes)
        if chosen is None:
            error(
                "aborted: plan root not confirmed; re-run from the intended "
                "directory or pass --repo-root <path> to pin it"
            )
            return 2
        repo_root = chosen

    # Branch-awareness preflight: when the new plan's derived branch already
    # exists with no local owner, strong-warn and (on consent) move the plan
    # onto a fresh disambiguated branch cut from the default. Built here (not in
    # the gate) so the gate stays pure of manifest I/O; placed before
    # ``RunLogWriter.start`` so a declined collision opens no run log.
    registered = {
        s
        for p in load_manifest_plan_paths(repo_root, manifest_path=args.manifest)
        if (s := slug_from_filename(p))
    }
    gate_rc = _create_branch_collision_gate(
        args, repo_root=repo_root, slug=args.slug, registered_slugs=registered
    )
    if gate_rc is not None:
        return gate_rc

    logger = RunLogWriter.start(
        repo_root=repo_root,
        slug=args.slug,
        command="create",
        argv=list(sys.argv),
    )
    rc = 1
    outcome = "error"
    # Explicit empties: a run that writes nothing (split, refusal, error)
    # records "nothing written" rather than omitting the fields.
    end_result: dict[str, Any] = {
        "plan_path": None,
        "manifest_updated": None,
        "archived_paths": [],
    }

    def _record_retained_artifact(exc: BaseException) -> None:
        # A plan retained on disk by a failed or interrupted create is still
        # a written artifact; a driver must not read the run as "nothing written".
        retained = getattr(exc, "artifact", None)
        if retained is not None:
            end_result["plan_path"] = _repo_rel(retained.path, repo_root)
            end_result["manifest_updated"] = bool(retained.registered)

    try:
        budget = _resolve_iterative_budget(args)
    except CreateError as exc:
        error(str(exc))
        _rollback_branch_collision(args, repo_root)
        logger.run_end(
            outcome="error", rc=1, result=_create_end_result(end_result)
        )
        return 1
    # A/B prompt mode: ``split`` wires the lifted-out foundational-logic call
    # (and the lean prompt); ``combined`` (default) leaves it off so
    # ``create`` runs the single legacy proposal call.
    arm = _resolve_prompt_mode(args)
    split = arm == "split"
    split_invoker = shell_claude_invoker if split else None
    try:
        try:
            result = create_plan(
                args.slug,
                repo_root=repo_root,
                output_dir_override=args.output_dir,
                manifest_path=args.manifest,
                from_description=description,
                from_existing_path=source_path,
                tracked_seed_location=tracked_seed_location,
                seed_body=seed_body,
                yes=args.yes,
                resume=not getattr(args, "no_resume", False),
                budget=budget,
                allow_drift=getattr(args, "allow_drift", False),
                auto_reconcile_on_drift=getattr(
                    args, "auto_reconcile_on_drift", True,
                ),
                collision_sidecar=getattr(
                    args, "collision_sidecar", True,
                ),
                triage=getattr(args, "triage", True),
                include_info=getattr(args, "include_info", False),
                synthesize_body=not getattr(args, "no_synthesize_body", False),
                fetch_docs=not getattr(args, "no_fetch_docs", False),
                # File-backed inputs classify before consulting this legacy
                # inline control. ``_prepare_create_plan`` owns that route;
                # keep the flag's raw-seed bypass only for ``--from``.
                distill=(
                    source_path is None
                    and not getattr(args, "no_distill", False)
                ),
                skip_prose_reproposal=not getattr(
                    args, "no_skip_prose_reproposal", False
                ),
                foundational_invoker=split_invoker,
                capture_scenarios=True,
                arm=arm,
                run_logger=logger,
            )
        except FileExistsError as exc:
            error(str(exc))
            _rollback_branch_collision(args, repo_root)
            return 1
        except CreateError as exc:
            error(str(exc))
            _record_retained_artifact(exc)
            artifact = getattr(exc, "artifact", None)
            if artifact is None:
                _rollback_branch_collision(args, repo_root)
            return 1

        # Record the written plan before any reporting, so an interrupt during
        # the reporting below still leaves a run_end that names it.
        if result.plan_path is not None:
            end_result["plan_path"] = _repo_rel(result.plan_path, repo_root)
            end_result["manifest_updated"] = bool(result.manifest_updated)
            end_result["archived_paths"].extend(
                _archive_targets(result.replaced_archives, repo_root)
            )

        if result.file_backed_route is FileBackedSourceRoute.REFUSED:
            # A post-preflight refusal selected an explicit no-plan route.
            # Restore any collision-created binding before reporting it.
            _rollback_branch_collision(args, repo_root)
            error(
                "route: refused — file-backed source: "
                f"{result.refusal_reason or 'preparation refused'}"
            )
            rc = 2
            outcome = "refused"
            return 2

        # An inline ``--from`` caller retains its historical split proposal
        # without gaining a file-backed route. Keep that compatibility case
        # explicit instead of inferring a file-backed route from the proposal.
        selected_split_route = (
            result.file_backed_route is FileBackedSourceRoute.SPLIT
        )
        inline_split_compatibility = (
            result.file_backed_route is None and result.split_proposal is not None
        )
        # A split leaves no plan. Restore any collision-created binding before
        # its worksheet/output branch, then exit 0 so the operator can carve.
        if selected_split_route or inline_split_compatibility:
            if result.split_proposal is None:
                error("file-backed split route returned without a proposal")
                _rollback_branch_collision(args, repo_root)
                return 1
            _rollback_branch_collision(args, repo_root)
            if selected_split_route:
                print("route: split")
            _emit_split_proposal(
                result.split_proposal,
                slug=args.slug,
                source_path=source_path,
                output_dir_override=args.output_dir,
                repo_root=repo_root,
                yes=args.yes,
            )
            rc = 0
            outcome = "ok"
            return 0

        if result.plan_path is None:
            error("create returned no plan without a selected file-backed route")
            _rollback_branch_collision(args, repo_root)
            return 1

        # Styled summary: the ``created`` line is the headline (green ✓);
        # every other action (archives, manifest, plan-details) is a dim,
        # bulleted detail line under it so the eye lands on the result
        # first. Warnings keep a yellow prefix on stderr. Plain mode (no
        # TTY / NO_COLOR) drops the color but keeps the same words.
        _report_archive_result(
            ArchiveResult(
                archived=result.replaced_archives,
                skipped=result.replaced_skipped,
            ),
            repo_root=repo_root,
        )
        for stale in result.replaced_manifest_entries:
            detail(f"removed stale manifest entry: {stale}")

        route_note = (
            f" (route: {result.file_backed_route.value})"
            if result.file_backed_route is not None
            else ""
        )
        success(f"created {_short_path(result.plan_path, repo_root)}{route_note}")
        _report_saved_risk_profile(result.plan_path, repo_root)
        if result.manifest_updated:
            detail(
                f"added to manifest {_short_path(result.manifest_path, repo_root)}"
            )
        else:
            detail(
                f"path already listed in manifest "
                f"{_short_path(result.manifest_path, repo_root)} (no change)"
            )
        warn_recommended_paths_ignored(repo_root, warn)

        if result.plan_details_renamed_to is not None:
            detail(
                f"reused plan-details -> "
                f"{_short_path(result.plan_details_renamed_to, repo_root)}"
            )
        if result.plan_details_skip_reason is not None:
            warn(result.plan_details_skip_reason)

        lifecycle = file_backed_route_lifecycle(
            result.file_backed_route,
            source_identity=source_path,
            finalization_complete=result.iteration_stage_failure is None,
            normalized_payload=result.distilled_seed,
        )
        archive_source_chain = lifecycle.archive_source_chain
        if lifecycle.materialize_normalized_artifact and source_path is not None:
            assert result.distilled_seed is not None
            archive_source_chain = _archive_normalized_artifact(
                source_path,
                result.plan_path,
                result.distilled_seed,
                repo_root=repo_root,
                archived_sink=end_result["archived_paths"],
            )

        source_archived = False
        if archive_source_chain and source_path is not None:
            archive = archive_existing_source(
                source_path,
                result.plan_path,
                repo_root=repo_root,
            )
            source_archived = any(
                original.resolve() == source_path.resolve()
                for original, _target in archive.archived
            )
            end_result["archived_paths"].extend(
                _archive_targets(archive.archived, repo_root)
            )
            _report_archive_result(archive, repo_root=repo_root)

        # When the source carries provenance, also archive the original seed
        # file (the one the canonical's provenance points back to). Without
        # this, the seed remains on disk after its content has been
        # superseded by the new plan, contradicting the canonical's archival
        # notice and leaving stale references to the (now renamed)
        # plan-details directory.
        if (
            source_archived
            and result.provenance is not None
        ):
            seed_path = (source_path.parent / result.provenance.source).resolve()
            if seed_path != source_path and seed_path.is_file():
                seed_archive = archive_existing_source(
                    seed_path,
                    result.plan_path,
                    repo_root=repo_root,
                )
                end_result["archived_paths"].extend(
                    _archive_targets(seed_archive.archived, repo_root)
                )
                _report_archive_result(seed_archive, repo_root=repo_root)

        # Stamp the grounding baseline now the plan is on disk: this is
        # the *first* grounding a plan ever gets (the refresh gate reads
        # ``None`` as "needs grounding" until something stamps one).
        # Fail-soft — a stamp hiccup leaves rc unchanged. Both terminal-0
        # returns below (clean ``ok`` and ``iteration_incomplete``) fall
        # after this line, so a written-but-unconverged plan still gets a
        # baseline; the split-proposal branch returns earlier and never
        # reaches here, so a no-plan proposal stamps nothing.
        _stamp_grounding(result.plan_path, repo_root)

        # Next-step hints: the plan exists but is still skeletal.
        # ``detail`` is the natural next authoring command; ``status``
        # and ``run`` are the natural execution-side follow-ups. The
        # plan-tool create iteration loop may have left open findings —
        # the loop-stop banner already surfaces that case with its own
        # follow-up suggestions, so this block is the happy-path hint.
        next_steps = _authoring_audit_follow_up(
            args.slug,
            bare_plan=True,
        )
        next_steps.extend(
            [
                (
                    f"plan-tool detail {args.slug}",
                    "author per-step detail files",
                ),
            ]
        )
        next_steps.extend(
            [
                (
                    f"plan-tool status {args.slug}",
                    "inspect current plan state",
                ),
                (
                    f"plan-tool run {args.slug}",
                    "execute the first runnable step",
                ),
            ]
        )
        if (
            result.file_backed_route is FileBackedSourceRoute.NORMALIZED
            and result.iteration_stage_failure is not None
        ):
            next_steps.insert(
                0,
                (
                    f"plan-tool completeness-audit {args.slug} --iterate",
                    "continue the published normalized plan in place",
                ),
            )
        _print_next_steps("Next steps:", next_steps)

        # The plan is on disk and usable even when the post-write
        # convergence loop aborted on a failed iteration stage -- create's
        # job (write a registered plan) completed, so it exits 0. The
        # incomplete polish is a result the operator addresses (re-run
        # resumes from the preserved round-0 checkpoints); the loop's
        # FAILURE banner on stderr and the ``iteration_incomplete`` run-log
        # outcome carry that signal, not the exit code. (main()'s
        # unexpected-exception crash handler still returns 1 — that path is
        # a genuine error.)
        if result.iteration_stage_failure is not None:
            rc = 0
            outcome = "iteration_incomplete"
            return 0

        rc = 0
        outcome = "ok"
        return 0
    except KeyboardInterrupt as exc:
        # The ``finally`` records the interrupt before this exits 130.
        rc = 130
        outcome = "interrupted"
        _record_retained_artifact(exc)
        artifact = getattr(exc, "artifact", None)
        if artifact is None:
            _rollback_branch_collision(args, repo_root)
        else:
            _report_retained_create_artifact(artifact)
        raise SystemExit(130)
    except Exception:
        # An unexpected author failure after a disambiguating switch must not
        # strand the developer on the candidate branch with an orphan binding;
        # roll back best-effort, then re-raise so the original failure (and rc)
        # is surfaced unchanged.
        _rollback_branch_collision(args, repo_root)
        raise
    finally:
        # ``run_end`` computes duration from the writer's own monotonic
        # start time; we don't have to track ``started`` here.
        logger.run_end(outcome=outcome, rc=rc, result=_create_end_result(end_result))


def _archive_targets(pairs: Iterable[tuple[Path, Path]], repo_root: Path) -> list[str]:
    """Repo-relative POSIX destinations of ``(original, archived)`` move pairs."""
    return [_repo_rel(target, repo_root) for _original, target in pairs]


def _bounded_paths(paths: list[str]) -> tuple[list[str], bool]:
    """Leading ``paths`` that fit the run log's shared list budget, and whether
    any were cut. Delegates to the one serialized-byte helper in ``run_log``."""
    kept, dropped = _bounded_violations(paths)
    return kept, dropped > 0


def _create_end_result(result: dict[str, Any]) -> dict[str, Any]:
    archived, truncated = _bounded_paths(result["archived_paths"])
    return {
        **result,
        "archived_paths": archived,
        "archived_paths_truncated": truncated,
    }


def _detail_end_result(written: Optional[list[str]]) -> dict[str, Any]:
    """``detail``'s ``run_end`` record. ``None`` means the files written are
    unknown because the authoring call raised before returning its results."""
    if written is None:
        return {
            "detail_files_written": None,
            "detail_files_written_count": None,
            "detail_files_truncated": None,
        }
    kept, truncated = _bounded_paths(written)
    return {
        "detail_files_written": kept,
        "detail_files_written_count": len(written),
        "detail_files_truncated": truncated,
    }


def _report_saved_risk_profile(plan_path: Path, repo_root: Path) -> None:
    """Show the declaration persisted by a completed single-plan create."""
    try:
        plan = parse_plan(plan_path)
    except Exception as exc:  # noqa: BLE001 -- display confirmation is fail-soft
        warn(
            f"could not confirm saved risk tier for "
            f"{_short_path(plan_path, repo_root)}: {exc}"
        )
        return

    if plan.risk_profile is None:
        warn(
            f"could not confirm saved risk tier for "
            f"{_short_path(plan_path, repo_root)}: declaration is missing"
        )
        return

    detail(f"saved risk tier: {plan.risk_profile.value}")


def _stamp_grounding(
    plan_path: Path,
    repo_root: Path,
    *,
    touched_step_ids: Optional[set[int]] = None,
) -> Optional[Path]:
    """Record the grounding sidecar for a just-authored plan; fail-soft.

    Parses the on-disk plan, computes its current code/plan fingerprints and
    per-step authoring fingerprints (BACKLOG #165), and persists them via
    :func:`write_grounding`. See ``DATA_CONTRACT.md``'s "Grounding sidecar"
    section for the field contract and ``touched_step_ids``' anti-laundering
    rationale. Returns the sidecar ``Path`` on success, ``None`` on any
    failure (parse/hash/write hiccups must never flip an otherwise-green
    authoring run to a failure).
    """
    try:
        from plan_tool.grounding import (
            compute_step_authoring_fingerprint,
            extract_scope_bearing_sections,
            read_grounding,
        )

        plan = parse_plan(plan_path)
        code_fp = compute_code_fingerprint(plan, plan_path, repo_root)
        plan_fp = compute_plan_fingerprint(plan_path)
        out_of_scope, deferred = extract_scope_bearing_sections(plan_path)

        def _fingerprint(step) -> str:
            return compute_step_authoring_fingerprint(
                step, out_of_scope=out_of_scope, deferred=deferred
            )

        if touched_step_ids is None:
            # ``create``'s call site: no prior baseline to disturb, so a
            # blanket first-bootstrap stamp of every currently-detailed step
            # is correct here (contrast the merge branch below).
            step_fps = {
                str(step.id): _fingerprint(step)
                for step in plan.steps
                if step.detail and (repo_root / step.detail).is_file()
            }
        else:
            # ``detail``'s call site. Must NOT blanket-recompute every
            # detailed step — that would silently re-baseline steps this
            # run never touched against the plan's *current* shape, erasing
            # the staleness a prior plan edit already introduced for them
            # (DATA_CONTRACT.md's Grounding section spells out why). Merge:
            # start from the existing map, overwrite only the touched ids.
            existing = read_grounding(plan_path)
            step_fps = dict(
                existing.step_authoring_fingerprints if existing else {}
            )
            for step in plan.steps:
                if step.id not in touched_step_ids:
                    continue
                if step.detail and (repo_root / step.detail).is_file():
                    step_fps[str(step.id)] = _fingerprint(step)
                else:
                    step_fps.pop(str(step.id), None)

        return write_grounding(
            plan_path,
            plan_fingerprint=plan_fp,
            code_fingerprint=code_fp,
            step_authoring_fingerprints=step_fps,
        )
    except Exception as exc:
        warn(
            f"could not stamp grounding for "
            f"{_short_path(plan_path, repo_root)}: {exc}"
        )
        return None


def _read_seed_body(canonical_path: Path, canonical_text: str) -> Optional[str]:
    """Read the original seed file referenced by ``canonical_text``'s provenance.

    Returns ``None`` when the canonical carries no provenance
    frontmatter, when the resolved seed path matches the canonical
    itself (no separate source), when the seed is missing on disk, or
    when the read fails. ``None`` means "no *separate* seed file", not
    "no body source": ``create_plan`` falls back to ``canonical_text``
    itself, so the first two branches are the ordinary path (nothing has
    written provenance since ``reformat`` was removed in BACKLOG #40)
    and stay quiet. The two failure branches warn on stderr — the
    canonical text still populates the body, but the richer prose the
    provenance promised is silently missing otherwise.
    """
    provenance = read_canonical_provenance(canonical_text)
    if provenance is None:
        return None
    seed_path = (canonical_path.parent / provenance.source).resolve()
    if seed_path == canonical_path:
        return None
    if not seed_path.is_file():
        warn(
            f"canonical provenance points at {seed_path}, "
            "which is not on disk; falling back to the canonical text "
            "for body sections."
        )
        return None
    try:
        return seed_path.read_text(encoding="utf-8")
    except OSError as exc:
        warn(
            f"could not read seed {seed_path}: {exc}; falling back to "
            "the canonical text for body sections."
        )
        return None


_SPLIT_PROPOSAL_ROADMAP_GUIDANCE = (
    "For a project-sized concept, consider **`plan-tool roadmap`** with a "
    "concept brief to derive an ordered plan list and draft seeds before "
    "creating each plan individually."
)


def _render_split_proposal_markdown(
    slug: str, entries: list[SplitProposalEntry], seed_display: str
) -> str:
    """Render a multi-plan split proposal as a markdown worksheet.

    One H2 per proposed plan with its slug, rationale, and (when the distill
    pass returned a usable range) the seed line range plus a ``sed`` carve
    command. Ranges are advisory — entries whose range was unusable simply
    omit the carve line.
    """
    lines = [
        f"# Split proposal for `{slug}`",
        "",
        f"`plan-tool create` determined this seed describes {len(entries)} "
        "independent plans, so no plan was created. Create each below as its "
        "own plan: carve the seed using the line ranges, then run "
        "`plan-tool create <slug> --from-existing <file>` for each.",
        "",
        _SPLIT_PROPOSAL_ROADMAP_GUIDANCE,
        "",
    ]
    for i, e in enumerate(entries, start=1):
        lines.append(f"## {i}. {e.title}")
        lines.append("")
        lines.append(f"- **Suggested slug:** `{e.suggested_slug}`")
        if e.rationale:
            lines.append(f"- **Why its own plan:** {e.rationale}")
        if e.start_line is not None and e.end_line is not None:
            lines.append(f"- **Seed lines:** {e.start_line}–{e.end_line}")
            lines.append(
                f"- **Carve:** `sed -n '{e.start_line},{e.end_line}p' "
                f"{seed_display} > {e.suggested_slug}.md`"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _emit_split_proposal(
    proposal: SplitProposal,
    *,
    slug: str,
    source_path: Optional[Path],
    output_dir_override: Optional[Path],
    repo_root: Path,
    yes: bool,
) -> None:
    """Surface a multi-plan split proposal, save it, and print next steps.

    The distill first-pass determined the seed describes several independent
    plans, so ``create`` wrote nothing. This prints the proposed plans, offers
    to save a worksheet (auto-saving under ``--yes`` / non-TTY so headless runs
    don't lose it), and explains how to carve the seed. The seed is left in
    place. ``create`` exits 0 — a split proposal is a successful outcome, not
    an error.
    """
    entries = proposal.entries
    seed_display = str(source_path) if source_path is not None else "<seed-file>"

    # Headline + per-plan list on stdout (the useful output; parallels the
    # "created <path>" line of a normal create so scripts can branch on it).
    print(f"no plan created — the seed describes {len(entries)} independent plans:")
    for i, e in enumerate(entries, start=1):
        rng = (
            f"  (seed lines {e.start_line}-{e.end_line})"
            if e.start_line is not None and e.end_line is not None
            else ""
        )
        print(f"  {i}. {e.title}  [slug: {e.suggested_slug}]{rng}")
        if e.rationale:
            print(f"     {e.rationale}")

    markdown = _render_split_proposal_markdown(slug, entries, seed_display)

    try:
        output_dir = resolve_output_dir(
            repo_root, output_dir_override or DEFAULT_OUTPUT_DIR
        )
    except Exception:
        output_dir = repo_root
    save_path = output_dir / f"{slug}-split-proposal.md"

    do_save = yes or not sys.stdin.isatty()
    if not do_save:
        import builtins

        answer = (
            builtins.input(f"\nSave split proposal to {save_path}? [Y/n] ")
            .strip()
            .lower()
        )
        do_save = answer in ("", "y", "yes")

    if do_save:
        try:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_text(markdown, encoding="utf-8")
        except OSError as exc:
            warn(f"could not save split proposal to {save_path}: {exc}")
        else:
            print(f"saved split proposal to {save_path}")

    print(
        "next: carve the seed into one file per plan using the ranges above, "
        "then run `plan-tool create <slug> --from-existing <file>` for each. "
        "No plan or manifest entry was written."
    )
    print(_SPLIT_PROPOSAL_ROADMAP_GUIDANCE)


def _cmd_create_reprocess(args: argparse.Namespace) -> int:
    """Dispatch for ``create <slug> --reprocess``.

    Looks up the registered plan for ``slug``, finds the matching
    archive under ``<plan-dir>/archive/``, and fills `_(TODO)_`
    section bodies in place. No claude call, no manifest mutation —
    explicitly the cheap counterpart to a full ``create --iterate``
    pass when a prior create left placeholders behind.

    Exit codes: 0 on success (even if some sections couldn't be
    filled — those land in ``unfilled``), 1 on missing plan / archive
    / no TODOs.
    """
    if args.slug is None:
        error(
            "create --reprocess needs an explicit slug naming the "
            "plan to reprocess (no description to suggest one from)"
        )
        return 2
    ctx = _load_context(args)
    try:
        plan_path = resolve_plan_for_context(ctx, args.slug)
    except FileNotFoundError as exc:
        error(str(exc))
        return 1
    archive_path = find_archive_for_slug(plan_path, args.slug)
    if archive_path is None:
        error(
            f"no archive matching slug {args.slug!r} under "
            f"{plan_path.parent / 'archive'}. Reprocess needs a "
            "predecessor file to lift sections from — author the body "
            "manually or re-run `create --from-existing <draft>` so the "
            "draft is archived and available next time."
        )
        return 1
    try:
        result = reprocess_plan(plan_path, archive_path)
    except ReprocessError as exc:
        error(str(exc))
        return 1
    print(f"reprocessed {result.plan_path}")
    print(f"  archive: {result.archive_path}")
    if result.filled:
        print(f"  filled ({len(result.filled)}):")
        for title in result.filled:
            print(f"    - {title}")
    if result.unfilled:
        print(f"  still TODO ({len(result.unfilled)}, no match in archive):")
        for title in result.unfilled:
            print(f"    - {title}")
    if result.skipped:
        print(
            f"  left as-is ({len(result.skipped)}, already populated "
            "or Steps section):"
        )
        for title in result.skipped:
            print(f"    - {title}")
    return 0


def cmd_detail(args: argparse.Namespace) -> int:
    """Draft developer-actionable per-step detail markdown (authoring).

    Intent: fill in the per-step spec a developer needs to execute
    the step — Why / Files / Implementation / Tests / Acceptance
    criteria / Deferred — and wire the plan's ``step.detail``
    pointer to the new file automatically. Downstream subcommands
    (:func:`cmd_run`, :func:`cmd_review`, :func:`cmd_jira`,
    :func:`cmd_verify`) load the detail body into their prompts when
    present, so detail authoring up-front improves every later
    claude call.

    Idempotent per step: a step whose detail file already exists is
    skipped unless ``--force``. Resumable via the checkpoint cache
    (see :func:`cmd_checkpoint`); pass ``--no-resume`` to force
    fresh claude calls.

    Distinguish from :func:`cmd_create`: ``create`` writes the
    *plan* (frontmatter + body skeleton + manifest entry), ``detail``
    writes *per-step specs*. New "author content for a plan"
    subcommands belong in this category.

    See ``docs/reference/contracts/process.md`` for the detail-grade authority boundary.
    """

    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)

    # ``--reconcile`` switches detail into a read-only audit path. It
    # has no authoring semantics, so reject combinations that only
    # apply to the write path before any run log opens — and, for the
    # same reason, before the unmatched-fence gate below: that gate is
    # specifically about not *authoring onto* a malformed plan, which
    # doesn't apply to a read-only reconcile (`run_step`'s own mode-gated
    # guard already covers the mutating "run" mode this dispatches to).
    if getattr(args, "reconcile", False):
        if args.dry_run:
            error(
                "--dry-run has no meaning on the --reconcile audit "
                "path (use plan-tool run --dry-run to render the prompt "
                "without invoking claude)"
            )
            return 2
        # ``_cmd_detail_reconcile`` still lives in ``app`` (its own carve
        # comes later). Resolve it lazily — by call time ``app`` is fully
        # loaded, so this is a cheap attribute bind with no import cycle.
        from plan_tool.cli import app
        return app._cmd_detail_reconcile(args, ctx=ctx, plan_path=path)

    # ``--all`` is a reconcile-sweep flag. The authoring path already
    # covers every step lacking detail by default, so a bare
    # ``detail <name> --all`` is either a misremembered sweep (wants
    # --reconcile) or a redundant no-op alias — reject it instead of
    # guessing.
    if getattr(args, "all", False):
        error(
            "--all requires --reconcile (the authoring path already "
            "covers every step lacking detail by default; --all sweeps "
            "the per-step reconcile audit)."
        )
        return 2

    try:
        plan_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        error(f"{path}: could not read plan file: {exc}")
        return 2
    if _fenced_code_spans(_strip_frontmatter(plan_text)).unmatched_opening is not None:
        error(
            f"{path}: unmatched opening code fence; add a matching closing fence "
            "before authoring detail."
        )
        return 2

    if getattr(args, "detail_only", False) and not getattr(
        args, "auto_completeness", True
    ):
        error(
            "--detail-only requires the completeness tail; use --no-iterate "
            "for one-shot detail authoring without any auto-update pass."
        )
        return 2

    # ``--detail-only`` means "skip the per-step loop, but run the
    # completeness tail *with* auto-update" — its whole point over a plain
    # (now default --no-iterate) detail run. Pin the tail ON here so the
    # OFF --iterate default the mutex group hands it doesn't silently strip
    # its auto-update; the per-step loop still stays off via ``detail_budget``
    # (enabled=False for detail_only below).
    if getattr(args, "detail_only", False):
        args.iterate = True

    # Recovery is one forced, targeted, no-tail write; see DETAIL_FORMAT.md.
    recover_refused = getattr(args, "recover_refused", False)
    if recover_refused and (
        args.step is None
        or not args.force
        or getattr(args, "auto_completeness", True)
    ):
        error(
            "--recover-refused requires the exact companion shape --step N "
            "--force --no-completeness (it recovers exactly one refused or "
            "carrier-less detail file, without reading the bundle's other "
            "detail files or running the completeness tail)."
        )
        return 2

    # ``--commit`` requires a clean tree up front: the post-run commit does
    # ``git add -A``, so any pre-existing edit would fold into it. Reject
    # before any run log opens (consistent with run's --commit gate).
    # Skipped under --dry-run (no files written, so nothing to commit).
    if getattr(args, "commit", False) and not args.dry_run:
        if _working_tree_dirty(ctx.repo_root):
            error(
                "--commit requires a clean working tree (commit or stash "
                "your changes first)."
            )
            return 2

    # ``--jobs > 1`` drives parallel detail authoring, which is only safe on a
    # frozen step set. Refuse it under a plan-structure-mutating mode:
    # ``--iterate`` re-reads the live plan each convergence pass, and ``--split``
    # renumbers steps after the loop — either would mutate numbering out from
    # under workers holding step snapshots. Name the conflicting flag(s) and the
    # way out; fire before the run log opens (like the sibling guards). This is
    # the operator-facing front door in front of generate_detail's deep guard.
    jobs = getattr(args, "jobs", 1)
    if jobs > 1:
        iterate_on = getattr(args, "iterate", True)
        split_on = getattr(args, "split", False)
        lessons_on = getattr(args, "lessons", False)
        if iterate_on or split_on:
            conflicting = " and ".join(
                flag
                for flag, on in (("--iterate", iterate_on), ("--split", split_on))
                if on
            )
            error(
                f"--jobs > 1 cannot combine with {conflicting} (parallel "
                "authoring needs a frozen step set); re-run with --no-iterate "
                "--no-split, or drop --jobs."
            )
            return 2
        if lessons_on:
            error(
                "--jobs > 1 cannot combine with --lessons (lesson capture "
                "requires a clean detail-quality converge under --iterate, "
                "which is serial-only); drop --jobs or --lessons."
            )
            return 2

    # ``--jobs > 1 --step N`` targets exactly one step, so there is no
    # parallelism to gain — degrade to serial with a warning rather than
    # spinning up a pool of one. Softer than the refuse above (a pointless
    # combination, not an incompatible mode). Runs after the refuse guard so
    # ``--jobs 4 --step 2`` (iterate on) errors rather than degrading. A local
    # keeps the requested value (run-log flags) distinct from the effective one.
    effective_jobs = jobs
    if jobs > 1 and args.step is not None:
        warn(
            "--jobs > 1 with --step authors a single step; running serially "
            "(jobs=1)."
        )
        effective_jobs = 1

    # Open the run log AFTER resolve_plan_for_context succeeds. A bad
    # plan name bubbles a FileNotFoundError/ManifestError up to the
    # dispatcher (rc=2) before any log is created — we don't want a
    # ghost JSONL under .plan-tool/runs/<unknown>/ for an invocation
    # that never matched a plan.
    #
    # Slug the run log under ``detail._plan_slug(path)`` (the canonical
    # derivation that strips a leading ``<digit>-`` from the filename
    # stem) so the run log lands alongside detail's other artifacts
    # under the same key. Local import keeps this module's top-level
    # imports stable.
    from plan_tool.detail import _plan_slug as _detail_plan_slug
    run_logger = RunLogWriter.start(
        repo_root=ctx.repo_root,
        slug=_detail_plan_slug(path),
        command="detail",
        argv=list(sys.argv[1:]),
        plan_path=path,
        step_filter=args.step,
        flags={
            "force": args.force,
            "dry_run": args.dry_run,
            "lessons": getattr(args, "lessons", False),
            "no_resume": getattr(args, "no_resume", False),
            "commit": getattr(args, "commit", False),
            "detail_only": getattr(args, "detail_only", False),
            "jobs": jobs,
            "recover_refused": recover_refused,
        },
    )
    # Default rc/err defensively so an unexpected escape path still
    # records a sensible terminal event.
    rc = 1
    err_msg: Optional[str] = None
    # ``None`` = unknown: set to a list once ``generate_detail`` returns.
    detail_written: Optional[list[str]] = None
    try:
        budget = _resolve_iterative_budget(args)
    except CreateError as exc:
        err_msg = str(exc)
        error(str(exc))
        run_logger.run_end(
            outcome="error",
            rc=2,
            error=err_msg,
            result=_detail_end_result([]),
        )
        return 2
    detail_budget = (
        # replace() so every field (hard_budget_seconds / op_started_at, #123)
        # survives; only ``enabled`` is overridden for the detail-only pass.
        replace(budget, enabled=False)
        if getattr(args, "detail_only", False)
        else budget
    )
    # A/B prompt mode: ``split`` wires the lifted-out foundational-logic sweep
    # (and drops the inline grep directive + always-on self-check); ``combined``
    # (default) keeps the single legacy authoring call.
    detail_arm = _resolve_prompt_mode(args)
    detail_split_invoker = (
        shell_detail_invoker if detail_arm == "split" else None
    )
    # ``--commit``: commit each step as it converges (#122) so an interrupted
    # batch keeps completed steps (and the tree stays clean between steps,
    # avoiding the test-gate masking). A residual sweep after the run (below)
    # catches lessons / plan edits not tied to a single step's completion.
    _commit_slug = _detail_plan_slug(path)
    _committed_steps: list[int] = []  # step ids that produced a commit
    _commit_failed_steps: list[int] = []
    _commit_step_ran: list[bool] = []  # the serial per-step path fired at all
    _commit_step_cb: Optional[Callable[[int, str], None]] = None
    if getattr(args, "commit", False) and not args.dry_run:
        def _commit_step_cb(step_id: int, title: str) -> None:
            # The serial per-step path fired (generate_detail only calls this
            # from the serial loop, never the concurrent tail), so the end-of-run
            # commit knows to use the residual — not batch — subject even if every
            # per-step commit was a clean no-op (--force byte-identical bodies).
            _commit_step_ran.append(True)
            # Stop after the first failure: a failed ``git commit`` (e.g. a
            # pre-commit hook rejection) leaves that step's files *staged*, and
            # a later step's ``git add -A`` would fold them into the wrong
            # commit. Once one step's commit fails, leave the rest on disk
            # uncommitted for the operator rather than misattribute history.
            if _commit_failed_steps:
                return
            res = _commit_detail_step(
                ctx.repo_root, slug=_commit_slug, step_id=step_id, title=title
            )
            if res is None:
                return  # clean tree — nothing to commit for this step
            crc, ctail = res
            if crc == 0:
                _committed_steps.append(step_id)
            else:
                _commit_failed_steps.append(step_id)
                error(
                    f"git commit failed for step {step_id} (rc={crc})"
                    + (f": {ctail}" if ctail else "")
                )
    try:
        try:
            results = generate_detail(
                path,
                repo_root=ctx.repo_root,
                step_id=args.step,
                force=args.force,
                dry_run=args.dry_run,
                extract_lessons=getattr(args, "lessons", False),
                foundational_invoker=detail_split_invoker,
                capture_scenarios=True,
                arm=detail_arm,
                resume=not getattr(args, "no_resume", False),
                yes=getattr(args, "yes", False),
                prompt_fn=input,
                run_logger=run_logger,
                budget=detail_budget,
                allow_drift=getattr(args, "allow_drift", False),
                auto_reconcile_on_drift=getattr(
                    args, "auto_reconcile_on_drift", True,
                ),
                collision_sidecar=getattr(
                    args, "collision_sidecar", True,
                ),
                triage=getattr(args, "triage", True),
                include_info=getattr(args, "include_info", False),
                allow_split=getattr(args, "split", False),
                jobs=effective_jobs,
                commit_step=_commit_step_cb,
                recovery_only=recover_refused,
            )
        except DetailFormatError as exc:
            err_msg = str(exc)
            raise
        except DetailError as exc:
            err_msg = str(exc)
            error(str(exc))
            rc = 2
            return rc

        rc = 0
        detail_written = []
        sep = "=" * 64
        # Accumulate per-step outcomes so the final block can render as a
        # single grouped summary instead of one long path per line
        # interleaved with status text. Dry-run still streams its prompt
        # previews inline (each preview is megabytes — buffering it would
        # blow the terminal).
        wrote: list[tuple[int, Path]] = []
        skipped: list[tuple[int, str]] = []
        for r in results:
            if args.dry_run:
                print(sep)
                print(
                    f"Step {r.step_id} → would write "
                    f"{_short_path(Path(r.output_path), ctx.repo_root)}"
                )
                print(sep)
                print(r.prompt or "")
                print()
            elif r.written:
                wrote.append((r.step_id, Path(r.output_path)))
                detail_written.append(_repo_rel(Path(r.output_path), ctx.repo_root))
            else:
                reason = r.skipped_reason or "(no reason recorded)"
                skipped.append((r.step_id, reason))
                # Real failures (claude / write / frontmatter) flag the run;
                # idempotent "already exists" skips don't.
                if "already exists" not in reason:
                    rc = 1

        # A per-step commit failed during generate_detail (e.g. a hook
        # rejection). Bump rc BEFORE the summary + tail so the summary banner
        # reflects the failure and the tail / grounding stamp / next-steps /
        # end-of-run commit all short-circuit on ``rc == 0`` — no wasted tokens,
        # tree left for the operator. Already reported per step by the callback.
        if _commit_failed_steps:
            rc = 1

        # Render the grouped summary AFTER the per-step loop so the
        # final block isn't interleaved with progress noise from
        # detail-quality / lessons capture lines that were emitted
        # mid-run.
        if not args.dry_run and (wrote or skipped):
            _print_detail_summary(
                slug=args.name,
                wrote=wrote,
                skipped=skipped,
                rc=rc,
                repo_root=ctx.repo_root,
            )

        # After a clean authoring run, auto-run the conceptual
        # completeness pass as a tail step (default on; opt out with
        # ``--no-completeness``). It reads the whole plan as a
        # self-contained design and — when iteration is enabled —
        # applies the deterministic well-formedness findings and writes the
        # completeness report; the conceptual correctness/completeness gaps
        # are persisted for the reader to hand-edit in plan/detail files (#85). This closes
        # the coverage gap the per-step detail-quality loop structurally
        # can't see: detail-quality reviews one step's prose in
        # isolation, so cross-step contradictions and orphaned concepts
        # only surface here, against the full plan.
        #
        # ``args.iterate`` is propagated rather than forced: a default
        # detail run (iterate ON) gets the full auto-update, while
        # ``--no-iterate`` (a cost-sensitive run) downgrades this to an
        # audit-only report with no apply calls. ``json`` is forced off
        # because ``detail`` has no ``--json`` surface of its own and the
        # tail is meant for human eyes. Gated on the same
        # rc==0/wrote/not-dry-run condition as the next-steps block.
        completeness_tail: _CompletenessTailOutcome | None = None
        if (
            rc == 0
            and wrote
            and not args.dry_run
            and getattr(args, "auto_completeness", True)
        ):
            completeness_tail = _coerce_completeness_tail_outcome(
                _run_completeness_tail(args, what="detail")
            )

        # Suggest the next command only when detail actually wrote
        # something and the run is clean. Dry-run is purely informational
        # (prompt preview); skipped-only runs ("already exists" idempotent
        # path) didn't change state so a "next step" would be misleading.
        if rc == 0 and wrote and not args.dry_run:
            # Stamp the grounding baseline after the completeness tail has
            # applied its blocking findings, so the stored plan digest
            # reflects the converged markdown. Same clean/productive gate
            # as the next-steps block — a dry-run or skipped-only run never
            # reaches here, so neither writes a sidecar. Fail-soft.
            # ``touched_step_ids`` scopes the per-step authoring fingerprint
            # (BACKLOG #165) to the steps this run actually wrote, so an
            # untouched sibling step's existing fingerprint — and the
            # staleness it may already be recording — survives the restamp.
            _stamp_grounding(
                path,
                ctx.repo_root,
                touched_step_ids={step_id for step_id, _ in wrote},
            )
            # One merged block: the completeness tail's disposition actions
            # (apply / split / re-audit) lead — they're the most likely next
            # command when the audit found gaps — then the standing pipeline
            # steps. The tail prints its own counts + report path but no
            # next-steps of its own, so this is the single list the reader
            # acts on.
            _follow_up, _stage = _authoring_guidance(
                args.name,
                path=path,
                repo_root=ctx.repo_root,
                tail_outcome=completeness_tail,
            )
            _print_next_steps(
                "Next steps:",
                [
                    *_follow_up,
                    (
                        f"plan-tool reconcile-plan {args.name}",
                        "re-audit the new detail files against the current code",
                    ),
                    *_stage,
                ],
            )
            # A parallel run is by construction ``--no-iterate --no-split`` (the
            # only runnable form), so it skips the convergence loop. Flag the
            # bodies as an intentional un-converged first pass and print the
            # exact follow-up, so the always-``--iterate`` mandate isn't left
            # unmet. Gated on the *effective* jobs value so a degraded
            # single-step run (which ran serial) stays silent. Advisory only —
            # never changes rc.
            if effective_jobs > 1:
                warn(
                    "Parallel authoring wrote an un-converged first pass "
                    "(no convergence loop under --no-iterate --no-split). "
                    f"Re-run `plan-tool detail {args.name} --iterate` to "
                    "converge the authored bodies."
                )
        # Skipped-only run: every targeted step already had a detail file and
        # the user declined to replace it, so nothing changed. Without a word
        # this reads as a dead end — especially when a completeness BLOCKED
        # finding sent the user here expecting `detail` to author a *new*
        # step's file (there isn't one yet). Spell out the no-op and the two
        # real levers.
        elif rc == 0 and not wrote and not args.dry_run:
            next_steps = _authoring_audit_follow_up(
                args.name,
            )
            if skipped and all("already exists" in reason for _, reason in skipped):
                info(
                    "Nothing to author — every targeted step already has a detail "
                    "file. To regenerate one, pass --force; to break a step into "
                    "new sub-steps (e.g. to resolve a completeness BLOCKED "
                    f"finding), run `plan-tool split {args.name} --step N --into "
                    '"…" --into "…"`.'
                )
                next_steps.extend(
                    [
                        (
                            f"plan-tool detail {args.name} --force",
                            "regenerate the selected detail file(s)",
                        ),
                        (
                            f"plan-tool split {args.name} --step N --into \"…\" "
                            '--into "…"',
                            "replace one oversized step with new sub-steps",
                        ),
                    ]
                )
            else:
                info(
                    "No detail files were written, so no current qualified "
                    "audit result exists."
                )
            _print_next_steps(
                "Next steps:",
                next_steps,
            )

        # ``--commit`` (#122): in the serial path each converged step was
        # already committed by ``_commit_step_cb`` during ``generate_detail``
        # (so an interrupted batch keeps its completed steps). Runs only on a
        # productive (``wrote``), non-dry, non-failed run — a skipped-only run
        # authored nothing, so there is nothing to commit and we must NOT sweep
        # unrelated tracked churn (e.g. run-log writes) into a bogus commit. A
        # per-step commit failure already set ``rc = 1`` above, so this whole
        # block is skipped and the dirty tree is left for the operator.
        if getattr(args, "commit", False) and rc == 0 and not args.dry_run:
            if wrote:
                slug = _commit_slug
                # Serial iff the per-step callback ran (see `_commit_step_ran`) —
                # robust to clean-no-op commits and to a --jobs>1 run that
                # generate_detail executed serially. Only a truly-concurrent run
                # (callback never fired) takes the batch `else`.
                if _commit_step_ran:
                    # Serial path: per-step commits already landed each step.
                    # Report the tally and residual-sweep only what they didn't
                    # capture (the post-authoring completeness tail's edits).
                    if _committed_steps:
                        success(f"committed {len(_committed_steps)} step(s)")
                    subject = _detail_residual_commit_subject(slug)
                    label = "residual authoring edits"
                else:
                    # Concurrent (``--jobs>1``) path: no per-step commits fired,
                    # so this is the one batch commit of everything authored.
                    subject = _detail_batch_commit_subject(slug, len(wrote))
                    label = f"{len(wrote)} detail file(s)"
                res = _commit_if_dirty(ctx.repo_root, subject)
                if res is not None:
                    commit_rc, tail = res
                    if commit_rc == 0:
                        success(f"committed {label}")
                    else:
                        error(
                            f"git commit failed (rc={commit_rc})"
                            + (f": {tail}" if tail else "")
                        )
                        rc = 1
        return rc
    except KeyboardInterrupt:
        # The ``finally`` records the interrupt before this exits 130.
        rc = 130
        err_msg = "interrupted"
        raise SystemExit(130)
    finally:
        run_logger.run_end(
            outcome=("success" if rc == 0 else "error"),
            rc=rc,
            error=err_msg,
            result=_detail_end_result(detail_written),
        )


@dataclass(frozen=True)
class _CompletenessTailOutcome:
    """Disposition commands plus the one final audit result from a tail."""

    next_steps: list[tuple[str, str]]
    final_result: object = None
    blocking_verdict: BlockingVerdict = ABSENT_BLOCKING_VERDICT
    # The audit's own bundle status, so the stage row never re-scans the bundle.
    bundle_status: object = None


def _coerce_completeness_tail_outcome(value: object) -> _CompletenessTailOutcome:
    """Accept legacy test doubles while production tails return full evidence."""
    if isinstance(value, _CompletenessTailOutcome):
        return value
    if isinstance(value, list):
        return _CompletenessTailOutcome(value)
    return _CompletenessTailOutcome([])


def _fresh_completeness_audit_follow_up(
    plan_name: str,
    *,
    bare_plan: bool = False,
    verdict: BlockingVerdict = ABSENT_BLOCKING_VERDICT,
    artifacts_moved: bool = False,
) -> tuple[str, str]:
    """Return the safe audit route when authoring has no current evidence.

    A verdict with gaps or an untrusted cause lends its count and reason;
    ``artifacts_moved`` makes it read ``stale-revision``. See
    docs/how-to/pipeline/audit.md § "Authoring follow-up after a tail audit"."""
    audit_kind = "bare-plan " if bare_plan else ""
    result_name = "audit result"
    if verdict.state == BLOCKING_STATE_ABSENT or (
        not artifacts_moved and verdict.is_completed_empty_set
    ):
        command, _why = _reaudit_command(
            plan_name, ABSENT_BLOCKING_VERDICT
        )
        return (
            command,
            f"no current qualified {result_name} exists; run a fresh "
            f"{audit_kind}audit",
        )
    if artifacts_moved:
        # Deterministic blockers were computed on text that has since moved.
        verdict = blocking_verdict_from_gate(
            (), (), untrusted_cause=UNTRUSTED_STALE_REVISION
        )
    command, why = _reaudit_command(plan_name, verdict)
    kind = f" ({audit_kind.strip()} audit)" if audit_kind else ""
    return command, f"no current qualified {result_name} exists; {why}{kind}"


def _tail_result_freshness(
    result: object,
    *,
    path: Path,
    repo_root: Path,
) -> str:
    """Classify a final tail result against the bundle on disk, with at most
    one capture: ``"current"`` (proves it), ``"moved"`` (its run-grade revision
    differs from the files now), or ``"unproven"``.

    A missing or malformed result, another detail grade, or a capture that
    fails is ``"unproven"``, never ``"moved"``: that is
    ``project_saved_completeness_result``'s ``unknown``, so the tail agrees with
    ``status`` and ``list`` for the same result."""
    payload = result.as_dict() if hasattr(result, "as_dict") else result
    normalized = normalize_qualified_result(payload)
    if normalized is None:
        return _FRESHNESS_UNPROVEN
    revision = normalized["audit_revision"]
    if revision is None or revision["detail_grade"] != "run":
        return _FRESHNESS_UNPROVEN
    try:
        current = AuditInputSnapshot.capture(
            path, repo_root
        ).revision
    except Exception:  # noqa: BLE001 -- authoring guidance must fail closed
        return _FRESHNESS_UNPROVEN
    if current != revision:
        return _FRESHNESS_MOVED
    qualified = (
        normalized["headline"]
        in {"awaiting-human-action", "advisory-only", "clean"}
        and normalized["coverage"] == "confirmed"
        and normalized["revision_status"] == "current"
    )
    return _FRESHNESS_CURRENT if qualified else _FRESHNESS_UNPROVEN


_FRESHNESS_CURRENT = "current"
_FRESHNESS_MOVED = "moved"
_FRESHNESS_UNPROVEN = "unproven"


def _authoring_audit_follow_up(
    plan_name: str,
    *,
    path: Path | None = None,
    repo_root: Path | None = None,
    tail_outcome: _CompletenessTailOutcome | None = None,
    bare_plan: bool = False,
) -> list[tuple[str, str]]:
    """Keep only current final tail guidance; otherwise lead with fresh audit."""
    return _authoring_guidance(
        plan_name,
        path=path,
        repo_root=repo_root,
        tail_outcome=tail_outcome,
        bare_plan=bare_plan,
    )[0]


def _authoring_guidance(
    plan_name: str,
    *,
    path: Path | None = None,
    repo_root: Path | None = None,
    tail_outcome: _CompletenessTailOutcome | None = None,
    bare_plan: bool = False,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """``(follow_up_rows, stage_rows)`` from one freshness check of the tail.

    The stage row exists only for a completed empty set whose final result
    still matches the artifacts on disk; otherwise the fresh-audit follow-up
    stands alone."""
    freshness = (
        _tail_result_freshness(
            tail_outcome.final_result,
            path=path,
            repo_root=repo_root,
        )
        if tail_outcome is not None and path is not None and repo_root is not None
        else _FRESHNESS_UNPROVEN
    )
    if freshness != _FRESHNESS_CURRENT:
        moved = freshness == _FRESHNESS_MOVED
        return (
            [
                _fresh_completeness_audit_follow_up(
                    plan_name,
                    bare_plan=bare_plan,
                    verdict=(
                        tail_outcome.blocking_verdict
                        if tail_outcome is not None
                        else ABSENT_BLOCKING_VERDICT
                    ),
                    artifacts_moved=moved,
                )
            ],
            [],
        )
    follow_up = list(tail_outcome.next_steps)
    if not tail_outcome.blocking_verdict.is_completed_empty_set:
        return follow_up, []
    bundle_status = tail_outcome.bundle_status
    if bundle_status is None:
        return follow_up, []
    return follow_up, [
        next_stage_command(
            plan_name,
            bundle_status,
            verdict=tail_outcome.blocking_verdict,
        )
    ]


def _run_completeness_tail(
    args: argparse.Namespace, *, what: str
) -> _CompletenessTailOutcome:
    """Audit the authored bundle; iteration repairs deterministic findings only.

    Conceptual findings remain for judged edits. Ordinary tail failures do not
    change the authoring rc; unsupported detail formats deliberately refuse.

    Returns the audit's disposition next-step ``(command, description)``
    tuples plus its one final qualified result. The parent folds current
    disposition commands into its single pipeline ``Next steps:`` block;
    missing or unqualified final evidence instead leads to a fresh audit.

    ``cmd_completeness`` still lives in ``app`` (its own carve comes later);
    resolve it lazily — by call time ``app`` is fully loaded, so this is a
    cheap attribute bind with no import cycle.
    """
    print(
        f"\nplan-tool: {what} done — running conceptual completeness audit"
        + (" + auto-update" if getattr(args, "iterate", True) else "")
        + " (pass --no-completeness to skip)…",
        file=sys.stderr,
    )
    completeness_args = argparse.Namespace(**vars(args))
    completeness_args.json = False
    # Nested tail: the parent (detail/split) owns the run log, so the
    # completeness iterate loop must NOT open a second one under the same
    # slug (the run/detail "exactly one JSONL per run" contract). Its
    # apply/audit phases stay unlogged here, as before this instrumentation.
    completeness_args._suppress_run_log = True
    # The caller (detail/split) owns the single end-of-run commit when
    # ``--commit`` is set; the tail must not commit too or the run would
    # produce two commits and the caller's would capture nothing.
    completeness_args.commit = False
    # Sink for the audit's disposition next-steps: the finalize step fills
    # this instead of printing its own block, so the caller renders one
    # merged list. A list (not None) is the signal to suppress + hand back.
    next_steps: list[tuple[str, str]] = []
    completeness_args._next_steps_sink = next_steps
    final_results: list[object] = []
    completeness_args._final_qualified_result_sink = final_results
    verdicts: list[BlockingVerdict] = []
    completeness_args._blocking_verdict_sink = verdicts
    bundle_statuses: list[object] = []
    completeness_args._bundle_status_sink = bundle_statuses
    from plan_tool.cli import app
    try:
        app.cmd_completeness(completeness_args)
    except DetailFormatError:
        # A refused sibling detail is a hard, named refusal — never the
        # ordinary audit failure this warning-only tail exists for. A
        # successful authoring write must not conceal it.
        raise
    except UnsupportedPlanFormatVersionError:
        raise
    except Exception as exc:  # noqa: BLE001
        print(
            f"plan-tool: warning: auto-completeness pass failed ({exc}); "
            "detail files were written successfully",
            file=sys.stderr,
        )
    return _CompletenessTailOutcome(
        next_steps,
        final_results[0] if len(final_results) == 1 else None,
        verdicts[0] if len(verdicts) == 1 else ABSENT_BLOCKING_VERDICT,
        bundle_statuses[0] if len(bundle_statuses) == 1 else None,
    )


def cmd_split(args: argparse.Namespace) -> int:
    """Split and renumber steps, author details, then audit the bundle.

    Iteration repairs deterministic findings; conceptual gaps need judged edits.
    Code-canonical reconciliation remains a separate pre-execution action.
    """
    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)

    titles = list(getattr(args, "into", None) or [])
    if sum(1 for t in titles if t.strip()) < 2:
        error(
            'split needs at least two replacement step titles — pass '
            '--into "Title A" --into "Title B" (repeat --into for more).'
        )
        return 2
    author_details = getattr(args, "author_details", True)

    from plan_tool.detail import _plan_slug as _detail_plan_slug
    run_logger = RunLogWriter.start(
        repo_root=ctx.repo_root,
        slug=_detail_plan_slug(path),
        command="split",
        argv=list(sys.argv[1:]),
        plan_path=path,
        step_filter=args.step,
        flags={"into": titles, "author_details": author_details},
    )
    rc = 1
    err_msg: Optional[str] = None
    try:
        try:
            budget = _resolve_iterative_budget(args)
        except CreateError as exc:
            err_msg = str(exc)
            error(str(exc))
            run_logger.run_end(outcome="error", rc=2, error=err_msg)
            return 2

        dry_run = getattr(args, "dry_run", False)
        try:
            result = split_step(
                path,
                target_id=args.step,
                new_titles=titles,
                repo_root=ctx.repo_root,
                author_details=author_details,
                dry_run=dry_run,
                run_logger=run_logger,
                budget=budget,
            )
        except DetailFormatError as exc:
            err_msg = str(exc)
            raise
        except DetailError as exc:
            err_msg = str(exc)
            error(str(exc))
            rc = 2
            return rc

        if result.dry_run:
            # Preview: the renumber map + post-split plan, no disk mutation.
            info(
                f"[dry-run] would split step {result.target_id} "
                f"({result.original_title!r}) into {len(result.new_ids)} "
                f"step(s); no changes written."
            )
            shifted = [
                (old, new) for old, new in result.renumber if old != new
            ]
            if shifted:
                info("  renumber:")
                for old, new in shifted:
                    info(f"    step {old} → {new}")
            info("  resulting plan:")
            for sid, title, deps in result.new_plan:
                dep_txt = f"  (depends_on {deps})" if deps else ""
                info(f"    {sid:>2}. {title}{dep_txt}")
            rc = 0
            return rc

        new_ids_txt = ", ".join(str(i) for i in result.new_ids)
        success(
            f"split step {result.target_id} into {len(result.new_ids)} "
            f"step(s) {new_ids_txt}"
        )
        info(f"  was: {result.original_title}")
        for sid, title in zip(result.new_ids, result.new_titles):
            info(f"  {sid:>2}. {title}")

        # Authoring outcome for the new halves, grouped like a detail run.
        rc = 0
        if author_details and result.detail_results:
            wrote: list[tuple[int, Path]] = []
            skipped: list[tuple[int, str]] = []
            for r in result.detail_results:
                if r.written:
                    wrote.append((r.step_id, Path(r.output_path)))
                else:
                    reason = r.skipped_reason or "(no reason recorded)"
                    skipped.append((r.step_id, reason))
                    if "already exists" not in reason:
                        rc = 1
            _print_detail_summary(
                slug=args.name,
                wrote=wrote,
                skipped=skipped,
                rc=rc,
                repo_root=ctx.repo_root,
            )

        # Loop on correctness + completeness audit updates to convergence
        # (same tail detail runs), so a split that resolved a BLOCKED finding
        # leaves the plan re-audited rather than in a half-finished state.
        completeness_tail: _CompletenessTailOutcome | None = None
        if rc == 0 and author_details and getattr(args, "auto_completeness", True):
            completeness_tail = _coerce_completeness_tail_outcome(
                _run_completeness_tail(args, what="split")
            )

        if rc == 0 and not author_details:
            # --no-detail left the new halves without detail bodies; the
            # immediate next step is to author them (which also runs the
            # completeness tail this run skipped).
            _print_next_steps(
                "Next steps:",
                [
                    (
                        f"plan-tool detail {args.name}",
                        "author the new sub-steps' detail files",
                    ),
                    *_authoring_audit_follow_up(
                        args.name,
                    ),
                ],
            )
        elif rc == 0:
            # Merge the completeness tail's disposition actions (urgent
            # first) with the standing pipeline steps into one block.
            _follow_up, _stage = _authoring_guidance(
                args.name,
                path=path,
                repo_root=ctx.repo_root,
                tail_outcome=completeness_tail,
            )
            _print_next_steps(
                "Next steps:",
                [
                    *_follow_up,
                    (
                        f"plan-tool reconcile-plan {args.name}",
                        "check the new steps against the current code",
                    ),
                    *_stage,
                ],
            )
        return rc
    except KeyboardInterrupt:
        rc = 130
        err_msg = "interrupted"
        raise SystemExit(130)
    finally:
        run_logger.run_end(
            outcome=("success" if rc == 0 else "error"),
            rc=rc,
            error=err_msg,
        )


def cmd_merge(args: argparse.Namespace) -> int:
    """Merge and renumber steps, re-author detail, then audit the bundle.

    Iteration repairs deterministic findings; conceptual gaps need judged edits.
    Code-canonical reconciliation remains a separate pre-execution action.
    """
    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)

    ids = list(getattr(args, "steps", None) or [])
    # ``len(set(...)) < 2`` rejects both a single id and a duplicated one
    # (``--steps 3 --steps 3``) before any orchestrator call or disk mutation.
    if len(set(ids)) < 2:
        error(
            "merge needs at least two step ids — pass --steps 3 --steps 4 "
            "(repeat --steps for more)."
        )
        return 2
    author_details = getattr(args, "author_details", True)
    title = getattr(args, "title", None)

    from plan_tool.detail import _plan_slug as _detail_plan_slug
    run_logger = RunLogWriter.start(
        repo_root=ctx.repo_root,
        slug=_detail_plan_slug(path),
        command="merge",
        argv=list(sys.argv[1:]),
        plan_path=path,
        step_filter=None,
        flags={"steps": ids, "title": title, "author_details": author_details},
    )
    rc = 1
    err_msg: Optional[str] = None
    try:
        try:
            budget = _resolve_iterative_budget(args)
        except CreateError as exc:
            err_msg = str(exc)
            error(str(exc))
            run_logger.run_end(outcome="error", rc=2, error=err_msg)
            return 2

        dry_run = getattr(args, "dry_run", False)

        # Confirm at the TTY before mutating. ``cmd_split`` defers confirmation
        # to ``generate_detail``'s Phase-B; merge has no Phase-B and re-authors
        # over the members' existing bodies, so the CLI owns the gate.
        # ``--yes`` / non-TTY bypass it (an assented merge runs headlessly,
        # mirroring split's no-gate posture); ``--dry-run`` mutates nothing so
        # there is nothing to confirm. ``merge_steps`` itself never prompts.
        if not dry_run and not (
            getattr(args, "yes", False) or not sys.stdin.isatty()
        ):
            plan = parse_plan(path)
            members = set(ids)
            member_steps = [s for s in plan.steps if s.id in members]
            preview_title = title or (
                member_steps[0].title if member_steps else ""
            )
            confirmed = _confirm_merge(
                input, steps_to_merge=member_steps, merged_title=preview_title
            )
            if not confirmed:
                err_msg = "merge aborted — no steps were changed"
                error(err_msg)
                rc = 2
                return rc

        try:
            result = merge_steps(
                path,
                merge_ids=ids,
                title=title,
                repo_root=ctx.repo_root,
                author_details=author_details,
                dry_run=dry_run,
                run_logger=run_logger,
                budget=budget,
            )
        except DetailFormatError as exc:
            err_msg = str(exc)
            raise
        except DetailError as exc:
            err_msg = str(exc)
            error(str(exc))
            rc = 2
            return rc

        if result.dry_run:
            # Preview: the renumber map + post-merge plan, no disk mutation.
            info(
                f"[dry-run] would merge step(s) {result.folded_ids} into step "
                f"{result.merged_id}; no changes written."
            )
            shifted = [
                (old, new) for old, new in result.renumber if old != new
            ]
            if shifted:
                info("  renumber:")
                for old, new in shifted:
                    info(f"    step {old} → {new}")
            info("  resulting plan:")
            for sid, title_, deps in result.new_plan:
                dep_txt = f"  (depends_on {deps})" if deps else ""
                info(f"    {sid:>2}. {title_}{dep_txt}")
            rc = 0
            return rc

        folded_txt = ", ".join(str(i) for i in result.folded_ids)
        success(f"merged step(s) {folded_txt} into step {result.merged_id}")
        info(f"  now: {result.merged_title}")

        # Authoring outcome for the merged step, grouped like a detail run.
        rc = 0
        if author_details and result.detail_results:
            wrote: list[tuple[int, Path]] = []
            skipped: list[tuple[int, str]] = []
            for r in result.detail_results:
                if r.written:
                    wrote.append((r.step_id, Path(r.output_path)))
                else:
                    reason = r.skipped_reason or "(no reason recorded)"
                    skipped.append((r.step_id, reason))
                    if "already exists" not in reason:
                        rc = 1
            _print_detail_summary(
                slug=args.name,
                wrote=wrote,
                skipped=skipped,
                rc=rc,
                repo_root=ctx.repo_root,
            )

        # Loop on correctness + completeness audit updates to convergence, so a
        # merge leaves the plan re-audited rather than in a half-finished state.
        completeness_tail: _CompletenessTailOutcome | None = None
        if rc == 0 and author_details and getattr(args, "auto_completeness", True):
            completeness_tail = _coerce_completeness_tail_outcome(
                _run_completeness_tail(args, what="merge")
            )

        if rc == 0 and not author_details:
            # --no-detail left the merged step without a re-authored body; the
            # immediate next step is to author it (which also runs the
            # completeness tail this run skipped).
            _print_next_steps(
                "Next steps:",
                [
                    (
                        f"plan-tool detail {args.name}",
                        "author the merged step's detail file",
                    ),
                    *_authoring_audit_follow_up(
                        args.name,
                    ),
                ],
            )
        elif rc == 0:
            # Merge the completeness tail's disposition actions (urgent
            # first) with the standing pipeline steps into one block.
            _follow_up, _stage = _authoring_guidance(
                args.name,
                path=path,
                repo_root=ctx.repo_root,
                tail_outcome=completeness_tail,
            )
            _print_next_steps(
                "Next steps:",
                [
                    *_follow_up,
                    (
                        f"plan-tool reconcile-plan {args.name}",
                        "check the merged step against the current code",
                    ),
                    *_stage,
                ],
            )
        return rc
    except KeyboardInterrupt:
        rc = 130
        err_msg = "interrupted"
        raise SystemExit(130)
    finally:
        run_logger.run_end(
            outcome=("success" if rc == 0 else "error"),
            rc=rc,
            error=err_msg,
        )


def _positive_int(raw: str) -> int:
    """Parse an ``argparse`` value as an integer ``>= 1``.

    Rejects ``< 1`` (and non-numeric) via ``ArgumentTypeError`` so the message
    renders through argparse's standard ``prog: error: argument ...`` format.
    The ``--jobs`` flag has no ``0``/auto mode — the operator names an explicit
    worker count, so the tool never silently derives one.
    """
    try:
        value = int(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{raw!r} is not an integer")
    if value < 1:
        raise argparse.ArgumentTypeError(
            f"must be an integer >= 1 (got {value})"
        )
    return value


def register(subparsers) -> dict[str, Handler]:
    """Add the ``create`` / ``detail`` subparsers and return their dispatch map.

    Takes ``-y/--yes`` from :func:`plan_tool.cli.parser.make_yes_parent`
    and builds the iteration-flag parent locally. ``argparse``'s
    ``parents=`` copies actions by reference, so identical parent objects
    yield byte-identical per-subcommand help.
    """
    sub = subparsers

    yes_parent = make_yes_parent()

    # Shared iteration-loop flags inherited by the
    # create/completeness/detail/run subparsers. The loops themselves
    # live in steps 2–4 of the iterative-correctness plan; this parent
    # is just the CLI surface.
    #
    # NOTE: ``--iterate`` / ``--no-iterate`` is *intentionally* NOT
    # added here. Argparse's ``parents=`` mechanism copies actions by
    # reference, and ``set_defaults`` mutates the shared action's
    # ``default`` attribute -- so a single ``parent`` entry can't
    # express "default ON for create, default OFF for the others."
    # Each subparser adds its own ``--iterate`` action below with the
    # subcommand-appropriate default. The remaining iteration flags
    # (--max-iterations, --iteration-budget, etc.) share
    # the same defaults across subcommands and stay here.
    iterate_parent = argparse.ArgumentParser(add_help=False)
    iterate_parent.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        dest="max_iterations",
        metavar="N",
        help=(
            f"cap the convergence loop at N iterations even if findings "
            f"keep changing (default: {DEFAULT_MAX_ITERATIONS}). Ignored "
            f"when --no-iterate is set."
        ),
    )
    iterate_parent.add_argument(
        "--iteration-budget",
        type=int,
        default=DEFAULT_ITERATION_BUDGET_SECONDS,
        dest="iteration_budget",
        metavar="SECONDS",
        help=(
            f"debounced no-progress deadline in seconds: stop the "
            f"convergence loop only once SECONDS pass with no forward "
            f"progress at all (default: {DEFAULT_ITERATION_BUDGET_SECONDS}). "
            f"Resets on every round and every apply_finding call, so one "
            f"long claude call — even 15-20+ minutes — never trips it on "
            f"its own; see --time-budget for a true total-elapsed cap. "
            f"Ignored when --no-iterate is set."
        ),
    )
    iterate_parent.add_argument(
        "--time-budget",
        type=int,
        default=None,
        dest="time_budget",
        metavar="SECONDS",
        help=(
            "cooperative wall-clock cap (#123): stop the convergence loop "
            "cleanly at the next round boundary once SECONDS of total elapsed "
            "time pass — even while still converging — so a long op lands "
            "before an external execution ceiling instead of being killed "
            "mid-call. Exits 0 with a resume hint. Unlike --iteration-budget "
            "(a no-progress stall deadline), this is a hard total-elapsed cap. "
            "Falls back to PLAN_TOOL_TIME_BUDGET; default off. Ignored under "
            "--no-iterate."
        ),
    )
    iterate_parent.add_argument(
        "--max-stall-rounds",
        type=int,
        default=DEFAULT_MAX_STALL_ROUNDS,
        dest="max_stall_rounds",
        metavar="N",
        help=(
            f"stop the convergence loop after N consecutive rounds whose "
            f"open-finding count fails to shrink (default: "
            f"{DEFAULT_MAX_STALL_ROUNDS}). This is the ID-agnostic "
            f"backstop for a subjective claude audit that re-phrases the "
            f"same findings each round (fresh ids defeat the marginal / "
            f"converged checks). Pass 0 to disable. Ignored when "
            f"--no-iterate is set."
        ),
    )
    iterate_parent.add_argument(
        "--allow-drift",
        action="store_true",
        dest="allow_drift",
        help=(
            "opt back into the legacy 'warn but proceed' behavior when a "
            "watched file's content changes mid-iteration. Default: the "
            "loop checks drift BEFORE each apply (halts without spending "
            "claude tokens if drift detected) AND AFTER (keeps the "
            "apply's edits but halts subsequent applies if drift "
            "happened during the apply call). Token-preserving by "
            "design -- no revert, just halt + flag for `git diff` "
            "review (task #30). Pass --allow-drift only when you're "
            "sure the drift is expected (e.g. an automated formatter "
            "touching files in step.files during iteration)."
        ),
    )
    iterate_parent.add_argument(
        "--no-auto-reconcile-on-drift",
        action="store_false",
        dest="auto_reconcile_on_drift",
        default=True,
        help=(
            "skip the auto-reconcile pass that fires when drift halts "
            "the iteration loop. Default: when drift is detected, "
            "plan-tool runs `reconcile` against the step(s) that own "
            "the drifted file(s), saves the findings, and prints a "
            "structured summary inline with the halt (Lesson 13: "
            "audit beats observe). Pass this flag to suppress that "
            "extra claude call -- useful in CI runs that prefer a "
            "minimal stderr footprint, or when you'll inspect drift "
            "manually via `git diff` and `plan-tool run --mode "
            "reconcile`."
        ),
    )
    iterate_parent.add_argument(
        "--no-triage",
        action="store_false",
        dest="triage",
        default=True,
        help=(
            "skip the impact-weighted triage gate on findings. "
            "Default: when a finding carries impact/complexity tags "
            "(the plan-audit prompt's trailing "
            "``(impact=…, complexity=…)`` on conceptual findings; the "
            "reconcile prompt's ``Impact:`` / ``Complexity:`` fields), "
            "the iteration loop skips applies whose complexity "
            "strictly exceeds their impact (low+medium, low+high, "
            "medium+high) -- those findings are reported on stderr "
            "and dropped from the open-set so convergence "
            "short-circuits when only triaged findings remain. "
            "Findings without triage tags (deterministic checks, "
            "untagged output) default to apply. Pass this flag to "
            "force-apply every finding regardless of triage tags -- "
            "useful for completeness sweeps where you want to land "
            "every applicable edit."
        ),
    )
    iterate_parent.add_argument(
        "--include-info",
        action="store_true",
        dest="include_info",
        default=False,
        help=(
            "apply info-severity findings too. Default: info findings "
            "are advisory (a concept too vague to audit, a heuristic "
            "hit, a detail-only path) and are excluded from the apply "
            "loop -- they're still reported in the deferred summary, "
            "just not auto-applied. Pass this to spend claude tokens "
            "applying them as well."
        ),
    )
    iterate_parent.add_argument(
        "--no-collision-sidecar",
        action="store_false",
        dest="collision_sidecar",
        default=True,
        help=(
            "skip the change-collision sidecar pause when drift fires "
            "during apply_finding. Default: when drift is detected "
            "post-apply, plan-tool saves claude's edits to "
            "`<stem>-change-collision<ext>` next to each modified "
            "original, restores originals to pre-apply state, and "
            "pauses interactively for the user to merge with their "
            "preferred tool (vimdiff, `code --diff`, meld, etc.). "
            "Pressing Enter at the prompt continues the iteration "
            "loop against the merged state; Ctrl-D / typing 'abort' "
            "halts as today. Pass this flag to revert to the legacy "
            "'keep claude's edits on disk, review via git diff' "
            "behavior -- useful when scripting or piping to a CI "
            "consumer that doesn't expect sidecar files. Headless "
            "runs (-y or non-TTY) auto-skip the pause and fall "
            "through to halt regardless of this flag, since there's "
            "no human to merge."
        ),
    )

    p_create = sub.add_parser(
        "create",
        help="interactively author a new plan",
        parents=[yes_parent, iterate_parent],
    )
    # ``create`` opts INTO the post-write convergence loop by default
    # -- the loop is the primary value of the subcommand (auto-fill
    # ``_(TODO)_`` placeholders + close completeness gaps). Pass
    # ``--no-iterate`` to author a plan without the loop.
    p_create.add_argument(
        "--iterate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "run the post-write convergence loop until findings "
            "stabilize (completeness primitives + apply-finding). "
            "Default ON for create -- pass --no-iterate to opt out "
            "and emit the one-shot historical write only."
        ),
    )
    p_create.add_argument(
        "slug",
        nargs="?",
        default=None,
        help=(
            "canonical plan slug for the new plan — lowercase, dashes, "
            "no priority prefix, no .md suffix. Optional: when omitted "
            "alongside --from/--from-existing, a slug is suggested from "
            "the description (confirm or edit at the prompt; taken as-is "
            "under --yes)"
        ),
    )
    p_create_source = p_create.add_mutually_exclusive_group()
    p_create_source.add_argument(
        "--from",
        dest="from_description",
        default=None,
        metavar="DESCRIPTION",
        help="ask claude for initial steps given this inline description",
    )
    p_create_source.add_argument(
        "--from-existing",
        dest="from_existing",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "read an existing plan or notes file and use its contents as the "
            "description fed to claude for initial-step proposal. Its "
            "file-backed route publishes direct/normalized plans and exits "
            "0, returns a no-plan split with exit 0, or refuses with exit 2 "
            "(mutually exclusive with --from)"
        ),
    )
    p_create_source.add_argument(
        "--reprocess",
        action="store_true",
        dest="reprocess",
        help=(
            "fill `_(TODO)_` placeholders in the existing plan for "
            "this slug from its archived predecessor under "
            "<plan-dir>/archive/. Deterministic merge — no claude "
            "call, no manifest mutation, no step/reference "
            "regeneration. Mutually exclusive with --from / "
            "--from-existing. This refreshes placeholder *text* only, "
            "not stale-against-code content — to re-ground a plan "
            "against changed code use `reconcile-plan --refresh`."
        ),
    )
    p_create.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "directory to write the new plan into (default: "
            "docs/implementation-plans/ under the repo root)"
        ),
    )
    p_create.add_argument(
        "--no-distill",
        action="store_true",
        dest="no_distill",
        help=(
            "for inline --from input only, skip the distill first-pass and "
            "feed the raw seed to the steps/references/body round-trips. "
            "--from-existing still selects its file-backed route."
        ),
    )
    p_create.add_argument(
        "--no-synthesize-body",
        action="store_true",
        dest="no_synthesize_body",
        help=(
            "skip the third Claude round-trip that synthesizes body "
            "sections (Overview, Problem statement, Architecture, Out of "
            "scope, Risks, Testing, Acceptance criteria, Deferred) from "
            "the seed prose. Without synthesis, the body falls back to "
            "deterministic H2-name extraction from the seed; sections "
            "with no matching H2 land as _(TODO)_ and trip the fail-loud "
            "pre-write gate (unless --iterate is also set, in which case "
            "the convergence loop fills them via apply_finding). Useful "
            "for cost-sensitive runs, recording-test fixtures, or when "
            "the seed is known to be canonical and the canonical-skip "
            "optimization should be the only path to skipping synthesis."
        ),
    )
    p_create.add_argument(
        "--no-fetch-docs",
        action="store_true",
        dest="no_fetch_docs",
        help=(
            "skip fetching the content of the reference URLs gathered by "
            "the references round-trip. By default create fetches each "
            "reference, strips it to readable text, and folds that text "
            "into the body-synthesis prompt so the generated body is "
            "grounded in real documentation. The fetch only runs when "
            "synthesis runs (it has nowhere else to feed) and never blocks "
            "a create — a dead link or timeout just drops that doc. Pass "
            "this for offline / air-gapped runs, cost-sensitive runs, or "
            "recording-test fixtures where network access is undesirable. "
            "The References section still renders the links either way."
        ),
    )
    p_create.add_argument(
        "--no-skip-prose-reproposal",
        action="store_true",
        dest="no_skip_prose_reproposal",
        help=(
            "opt back into re-proposing steps + references on EVERY "
            "convergence iteration. By default (--iterate), a round that "
            "applied only body-prose findings (e.g. a _(TODO)_ section fill) "
            "skips the steps/references re-proposal: that re-proposal takes "
            "title + description as input, which the prose edit never "
            "changes, so it is non-deterministic churn (A/B-validated to "
            "~halve create's Claude cost with no quality regression). Pass "
            "this to force the re-proposal every round (e.g. to reproduce "
            "the legacy behavior or debug step drift)."
        ),
    )
    p_create.add_argument(
        "--no-resume",
        action="store_true",
        dest="no_resume",
        help=(
            "ignore any saved checkpoint under "
            "<repo_root>/.plan-tool/checkpoints/<slug>/ and re-invoke "
            "claude for both create phases (initial-steps proposal and "
            "references research). By default, when a checkpoint's input "
            "hash matches the current slug/description/output dir, the "
            "cached body is reused (and confirmed interactively on a "
            "TTY). Pass this to force fresh generation, e.g. after an "
            "out-of-band template/prompt change that doesn't alter the "
            "create inputs."
        ),
    )

    p_detail = sub.add_parser(
        "detail",
        help="draft developer-actionable per-step detail markdown files",
        parents=[yes_parent, iterate_parent],
    )
    # ``detail`` opts OUT of the per-step convergence loop by default --
    # a plain ``detail`` run emits the one-shot write only. Pass
    # ``--iterate`` to opt INTO the loop, which tightens each
    # freshly-written detail body via detail-quality review +
    # apply_finding until findings stabilize.
    #
    # ``--iterate`` and ``--reconcile`` go in a mutually-exclusive
    # group: ``--reconcile`` switches detail into an audit-only path
    # (renders prompts/detail-reconcile.md against the code on disk,
    # treats code as canonical, walks findings via apply_finding).
    # The authoring convergence loop is meaningless on that path.
    p_detail_mode = p_detail.add_mutually_exclusive_group()
    p_detail_mode.add_argument(
        "--iterate",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "run the per-step detail-quality review + apply loop after "
            "each detail-file write. Default OFF for detail -- pass "
            "--iterate to opt in (the default emits the one-shot write "
            "only). With the default max-iterations cap, detail scales "
            "the effective per-step iteration cap by complexity: "
            "low=1, medium=2, high/unknown=3."
        ),
    )
    p_detail_mode.add_argument(
        "--detail-only",
        action="store_true",
        dest="detail_only",
        help=(
            "write detail files without the per-step detail-quality loop, "
            "then run the whole-plan completeness tail with auto-update. "
            "Use this explicit bulk-speed mode when you want to defer "
            "grounding to the final pass; incompatible with --no-completeness."
        ),
    )
    p_detail_mode.add_argument(
        "--reconcile",
        action="store_true",
        help=(
            "audit the plan's per-step detail markdown against the "
            "code on disk (treats code as canonical). Mutually "
            "exclusive with the authoring path; renders "
            "prompts/detail-reconcile.md and walks findings via the "
            "apply-finding handler. Requires --step or --all."
        ),
    )
    p_detail.add_argument(
        "name",
        help="plan name — slug, filename stem (e.g. 1-my-feature), or filename.md",
    )
    p_detail.add_argument(
        "--step",
        type=int,
        default=None,
        help="generate for one step by id (default: every step lacking detail)",
    )
    p_detail.add_argument(
        "--jobs",
        type=_positive_int,
        default=1,
        dest="jobs",
        metavar="N",
        help=(
            "run up to N per-step authoring calls concurrently (explicit "
            "integer >= 1; default 1 = serial; there is no 0/auto mode). "
            "N>1 requires --no-iterate --no-split and is incompatible with "
            "--lessons (lesson capture needs a clean --iterate converge, "
            "which is serial-only). Ignored on the --reconcile audit path."
        ),
    )
    # ``--all`` only means something on the audit path: the authoring
    # path already covers every step lacking detail by default, so
    # ``detail <name> --all`` without ``--reconcile`` is rejected in
    # ``cmd_detail`` rather than silently treated as a no-op alias.
    p_detail.add_argument(
        "--all",
        action="store_true",
        dest="all",
        help=(
            "with --reconcile: sweep the per-step audit across every "
            "step not yet done (done steps are skipped — their detail "
            "is a historical record of delivered work). One claude "
            "call per step; halts on the first per-step failure. "
            "Mutually exclusive with --step."
        ),
    )
    p_detail.add_argument(
        "--force",
        action="store_true",
        help=(
            "overwrite an existing detail file and replace its `detail:` "
            "pointer (default: skip steps that already have a detail file)"
        ),
    )
    p_detail.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "render the prompt(s) and print them; do not invoke claude or "
            "write anything"
        ),
    )
    p_detail.add_argument(
        "--recover-refused",
        action="store_true",
        dest="recover_refused",
        help=(
            "targeted recovery for one detail file the shared format-version "
            "reader gate refuses (an unsupported/malformed marker) or that "
            "has no valid carrier H1. Requires the exact companion shape "
            "--step N --force --no-completeness: archives and replaces only "
            "the named step's file, without reading any other detail file in "
            "the bundle (sibling, already-implemented, or deterministic-"
            "grounding) and without running the post-write convergence loop "
            "or the whole-bundle completeness tail. Re-run per refused "
            "target, then a fresh `completeness-audit` once every target is "
            "repaired. Ordinary --force re-authoring, merge, and forced "
            "review regeneration are unaffected — none of them set this."
        ),
    )
    p_detail.add_argument(
        "--split",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "after authoring, offer to split any step the purity self-check "
            "flags as mixed (refactor + feature) into a refactor-then-feature "
            "pair and re-author both halves (default: on). Interactive only "
            "(each split is confirmed y/N) and skipped for any step whose "
            "downstream is done. Pass --no-split to only "
            "surface mixed steps as a warning."
        ),
    )
    p_detail.add_argument(
        "--lessons",
        action=argparse.BooleanOptionalAction,
        default=False,
        dest="lessons",
        help=(
            "capture lessons learned (default: off). When on, after a "
            "step's detail-quality iterate loop exits with 0 open "
            "findings, a second claude call distills new general "
            "lessons into ~/.plan-tool/lessons/general.md and "
            "project-specific lessons into "
            "<repo_root>/.plan-tool/lessons/project.md. Requires "
            "--iterate (capture never runs from an unaudited first "
            "write). Off by default because it costs an extra claude "
            "call per step; pass --lessons to opt in. --no-lessons is "
            "the explicit form of the default."
        ),
    )
    p_detail.add_argument(
        "--no-resume",
        action="store_true",
        dest="no_resume",
        help=(
            "ignore any saved checkpoint under "
            "<repo_root>/.plan-tool/checkpoints/<slug>/ and re-invoke "
            "claude for every step. By default, when a checkpoint's "
            "input hash matches the current step's title/files/depends_on, "
            "the cached body is reused (and confirmed interactively on a "
            "TTY). Pass this to force fresh generation, e.g. after an "
            "out-of-band template/prompt change that doesn't alter the "
            "step's frontmatter."
        ),
    )
    p_detail.add_argument(
        "--no-completeness",
        action="store_false",
        dest="auto_completeness",
        default=True,
        help=(
            "skip the conceptual completeness pass that runs after a "
            "clean authoring run. Default: once the detail files are "
            "written, plan-tool runs `completeness` against the whole "
            "plan — a single plan-audit claude call plus deterministic "
            "well-formedness checks — surfacing cross-step contradictions, "
            "material ambiguities, and orphaned concepts the per-step "
            "detail-quality loop can't see, and (when --iterate is "
            "passed) applying the deterministic well-formedness "
            "findings. Conceptual ambiguity is reported with correctness, "
            "and both it and completeness gaps are persisted unapplied for "
            "the human or orchestrating session to read and hand-edit the relevant "
            "plan or detail files (#85). "
            "Pass this flag to suppress the tail entirely; without "
            "--iterate (the default) the tail is an audit-only report "
            "with no apply calls."
        ),
    )
    p_detail.add_argument(
        "--commit",
        action="store_true",
        dest="commit",
        help=(
            "after a clean authoring run (and the completeness tail), stage "
            "all changes (git add -A) and create one commit with subject "
            "'plan(<slug>): detail — authored N step(s)'. Requires a clean "
            "working tree up front; off by default; ignored under --dry-run "
            "or when nothing was authored."
        ),
    )
    p_detail.add_argument(
        "--reuse",
        action=argparse.BooleanOptionalAction,
        default=None,
        dest="reuse",
        help=(
            "for --reconcile: reuse a saved detail-reconcile's findings "
            "instead of running a fresh claude audit, when the save is "
            "fresh (plan AND code fingerprints still match). Default "
            "(unset): prompt interactively, auto-accepting under --yes / "
            "non-TTY stdin. --reuse always reuses a fresh save; --no-reuse "
            "always re-audits. A stale save is never reused — it declines "
            "to a fresh audit with a staleness note."
        ),
    )
    p_detail.add_argument(
        "--reuse-id",
        default=None,
        dest="reuse_id",
        metavar="STEM",
        help=(
            "pin reuse to a specific saved detail-reconcile by filename "
            "stem (the bare `<ts>` or full `<ts>-detail-reconcile` form); "
            "default: newest matching save for this step. An unresolved id "
            "prints a note and falls back to a fresh audit. Not compatible "
            "with --all (a pinned save can't mean anything sensible across "
            "every step)."
        ),
    )

    p_split = sub.add_parser(
        "split",
        help=(
            "split a step into named sub-steps on demand, author their "
            "detail files, then loop on the completeness audit"
        ),
        parents=[yes_parent, iterate_parent],
    )
    p_split.add_argument(
        "name",
        help="plan name — slug, filename stem (e.g. 1-my-feature), or filename.md",
    )
    p_split.add_argument(
        "--step",
        type=int,
        required=True,
        help=(
            "id of the step to split. The split renumbers the plan to a "
            "contiguous 1..N and repoints downstream detail files; the "
            "first new half inherits the target's dependencies and each "
            "subsequent half depends on the previous one."
        ),
    )
    p_split.add_argument(
        "--into",
        action="append",
        dest="into",
        metavar="TITLE",
        help=(
            "title for one replacement step; pass --into at least twice "
            '(e.g. --into "Extract the validator" --into "Wire it into '
            'the handler"). The target step is replaced in place by these '
            "sub-steps, authored top to bottom."
        ),
    )
    # ``split`` opts INTO the convergence loop by default, mirroring
    # ``detail``: after the new halves are authored, the completeness tail
    # loops on the conceptual audit's correctness + completeness findings
    # and applies blocking ones. ``--no-iterate`` downgrades the tail to an
    # audit-only report.
    p_split.add_argument(
        "--iterate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "run the per-step detail-quality loop on each new half and the "
            "iterate convergence loop in the completeness tail. Default ON "
            "-- pass --no-iterate for one-shot authoring + an audit-only "
            "completeness report."
        ),
    )
    p_split.add_argument(
        "--no-detail",
        action="store_false",
        dest="author_details",
        default=True,
        help=(
            "split only: renumber the plan and rename downstream detail "
            "files, but don't author the new halves' detail bodies or run "
            "the completeness tail (author them later with "
            "`plan-tool detail <name>`)."
        ),
    )
    p_split.add_argument(
        "--no-completeness",
        action="store_false",
        dest="auto_completeness",
        default=True,
        help=(
            "skip the conceptual completeness audit that otherwise runs "
            "after the new halves are authored cleanly. Pass --no-iterate "
            "instead to keep it as an audit-only report with no apply calls."
        ),
    )
    p_split.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "preview the split — print the old→new step renumber map and the "
            "resulting plan — without writing the plan, renaming detail "
            "files, or authoring/auditing anything."
        ),
    )

    p_merge = sub.add_parser(
        "merge",
        help=(
            "merge a contiguous set of steps into one on demand, combine + "
            "re-author their detail file, then loop on the completeness audit"
        ),
        parents=[yes_parent, iterate_parent],
    )
    p_merge.add_argument(
        "name",
        help="plan name — slug, filename stem (e.g. 1-my-feature), or filename.md",
    )
    # ``--steps`` is the repeatable id flag — the set-valued merge analog of
    # split's single ``--step`` (the singular/plural inversion is deliberate).
    p_merge.add_argument(
        "--steps",
        type=int,
        action="append",
        dest="steps",
        metavar="ID",
        required=True,
        help=(
            "id of a step to fold into the merge; pass --steps at least twice "
            "for a contiguous dependency chain (e.g. --steps 3 --steps 4). The "
            "set collapses to a single step at the lowest id and the plan "
            "renumbers to a contiguous 1..N."
        ),
    )
    p_merge.add_argument(
        "--title",
        dest="title",
        metavar="TITLE",
        default=None,
        help=(
            "optional title for the merged step; omit to let the orchestrator "
            "derive one from the folded members' titles."
        ),
    )
    # ``merge`` opts INTO the convergence loop by default, mirroring
    # ``detail``/``split``: after the merged step is authored, the completeness
    # tail loops on the conceptual audit's correctness + completeness findings
    # and applies blocking ones. ``--no-iterate`` downgrades the tail to an
    # audit-only report.
    p_merge.add_argument(
        "--iterate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "run the per-step detail-quality loop on the merged step and the "
            "iterate convergence loop in the completeness tail. Default ON "
            "-- pass --no-iterate for one-shot authoring + an audit-only "
            "completeness report."
        ),
    )
    p_merge.add_argument(
        "--no-detail",
        action="store_false",
        dest="author_details",
        default=True,
        help=(
            "merge only: renumber + combine-and-archive detail files, but "
            "don't re-author the merged step's body or run the completeness "
            "tail (author it later with `plan-tool detail <name>`)."
        ),
    )
    p_merge.add_argument(
        "--no-completeness",
        action="store_false",
        dest="auto_completeness",
        default=True,
        help=(
            "skip the conceptual completeness audit that otherwise runs "
            "after the merged step is authored cleanly. Pass --no-iterate "
            "instead to keep it as an audit-only report with no apply calls."
        ),
    )
    p_merge.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "preview the merge — print the old→new step renumber map and the "
            "resulting plan — without writing the plan, renaming/archiving "
            "detail files, or authoring/auditing anything."
        ),
    )

    return {
        "create": cmd_create,
        "detail": cmd_detail,
        "split": cmd_split,
        "merge": cmd_merge,
    }
