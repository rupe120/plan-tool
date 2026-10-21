"""Locate plan markdown files and enumerate plan-tool–managed plans.

plan-tool is installed as a global binary, so each project keeps its own
plan manifest at ``<repo-root>/.plan-tool/plans.json`` (repo-relative plan
paths). Without ``--plans-dir`` / ``PLAN_TOOL_PLANS_DIR``, plan-tool reads
that per-project manifest; with an explicit directory it scans that
directory's top-level ``*.md`` instead (legacy escape hatch).

In manifest mode, :func:`build_plan_tool_context` enumerates *every*
project-root ancestor of cwd — any dir with a ``.git`` entry **or** a
``.plan-tool/plans.json`` manifest (so a project with nested ``.git``
folders — sub-repos, submodules — or a manifest-only checkout nested under
an unrelated git repo still resolves to the root that owns the plans) via
:func:`find_repo_root_candidates`, augments the list with the persistent
record at :data:`KNOWN_ROOTS_CACHE_SUBPATH` under ``$HOME/.plan-tool/``
(scoped to roots that contain cwd, so one project's cache never leaks into
another's), and picks the candidate whose own ``.plan-tool/plans.json``
resolves the most entries (innermost on tie). :func:`find_repo_root` is still used in directory
mode (anchored at the plans dir), and :func:`find_repo_root_from_cwd` remains
the single-root fallback for subcommands that have no manifest to score
against (e.g. ``checkpoint``, ``runs``).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional, Sequence

from plan_tool.parser import (
    ParseError,
    ValidationError,
    format_validation_errors,
    parse_plan,
)
from plan_tool.schema import Plan


PLANS_SUBPATH = Path("docs") / "implementation-plans"

# Per-project plan manifest, relative to the host repo root. plan-tool is
# installed as a global binary, so each project that uses it keeps its own
# manifest at ``<repo-root>/.plan-tool/plans.json``; the package ships no
# bundled manifest of its own.
DEFAULT_MANIFEST_SUBPATH = Path(".plan-tool") / "plans.json"


class ManifestError(Exception):
    """Raised when the plans manifest is malformed or has bad entries."""


def default_manifest_path(repo_root: Optional[Path] = None) -> Path:
    """Path to the host project's plan manifest.

    Returns ``<repo_root>/.plan-tool/plans.json``. When ``repo_root`` is
    omitted it is resolved by walking up from the current working directory
    to the nearest ``.git`` / ``.plan-tool`` ancestor (raising
    ``FileNotFoundError`` if neither marker is found).
    """
    root = repo_root if repo_root is not None else find_repo_root_from_cwd()
    return root / DEFAULT_MANIFEST_SUBPATH


def find_repo_root(plans_dir: Path) -> Path:
    """Return the git repository root containing `plans_dir`.

    Walks upward from `plans_dir` until a `.git` entry (file or directory) is
    found. If none is found (e.g. ephemeral test trees), falls back to the
    assumption that `plans_dir` is ``<root>/docs/implementation-plans``.
    """
    cursor = plans_dir.resolve()
    while True:
        if (cursor / ".git").exists():
            return cursor
        parent = cursor.parent
        if parent == cursor:
            break
        cursor = parent
    return plans_dir.parent.parent


def is_project_root(candidate: Path) -> bool:
    """True when ``candidate`` looks like a plan-tool project root.

    A project root is an ancestor with a ``.git`` entry **or** a per-project
    manifest at ``.plan-tool/plans.json``. The manifest — not the bare
    ``.plan-tool/`` directory — is the marker on purpose: ``.plan-tool/`` is
    also used as a *global state* directory (the ``~/.plan-tool``
    known-roots cache at :data:`KNOWN_ROOTS_CACHE_SUBPATH` plus shared
    lessons) and as a per-run work area (``.plan-tool/runs``,
    ``checkpoints``) that can exist under directories that are not plan
    roots — e.g. ``.agents/.plan-tool``. Anchoring on ``plans.json`` keeps
    the walk from mistaking ``$HOME`` (or a sibling work area) for the repo
    root, while still letting plan-tool resolve a root in a checkout with no
    git history once a manifest has been laid down there.
    """
    return (candidate / ".git").exists() or (
        candidate / DEFAULT_MANIFEST_SUBPATH
    ).is_file()


def collect_project_root_ancestors(start: Path) -> list[Path]:
    """Return every ancestor of ``start`` that is a plan-tool project root.

    A *project root* is an ancestor with a ``.git`` entry **or** a per-
    project manifest at ``.plan-tool/plans.json`` (see
    :func:`is_project_root`). Innermost (deepest) first.

    This is the enumerate-every-candidate twin of the stop-at-first walk in
    :func:`find_repo_root_from_cwd`: both decide "is this a project root?"
    through the same :func:`is_project_root` predicate, so manifest-mode
    candidate discovery (:func:`find_repo_root_candidates`) and the
    no-manifest walk-up can never disagree about which directories qualify.
    That parity is the fix for the failure mode where a manifest-only
    project dir (``.plan-tool/plans.json`` but no ``.git``) nested under an
    unrelated git repo was visible to ``plan-tool root`` but invisible to
    ``list`` / ``register`` — the latter only enumerated ``.git`` ancestors.

    Returns an empty list when no ancestor qualifies (no error — the caller
    may have other candidate sources, e.g. the known-roots cache).
    """
    out: list[Path] = []
    cursor = start.resolve()
    while True:
        if is_project_root(cursor):
            out.append(cursor)
        parent = cursor.parent
        if parent == cursor:
            return out
        cursor = parent


def find_repo_root_from_cwd(start: Optional[Path] = None) -> Path:
    """Walk upward from ``start`` (default cwd) to the nearest project root.

    A *project root* is an ancestor directory containing a ``.git`` entry
    **or** a per-project manifest at ``.plan-tool/plans.json`` (see
    :func:`is_project_root`). The latter lets plan-tool resolve a root in a
    checkout with no git history — or whose plan root sits below the git
    root — by anchoring on where the per-project manifest already lives.

    Delegates the walk to :func:`collect_project_root_ancestors` and takes
    the innermost result, so this stop-at-first resolution shares one
    implementation with the manifest-mode candidate enumeration.

    Raises ``FileNotFoundError`` when neither marker is found up to the
    filesystem root. Callers that want a current-directory fallback instead
    (the no-plan-name subcommands) catch that — see
    :func:`plan_tool.cli.context._resolve_cmd_repo_root`.
    """
    origin = start or Path.cwd()
    roots = collect_project_root_ancestors(origin)
    if roots:
        return roots[0]
    raise FileNotFoundError(
        "could not find a project root (.git or "
        ".plan-tool/plans.json) walking up from "
        f"{origin}; set PLAN_TOOL_PLANS_DIR or --plans-dir "
        "to use plan-tool without a repo-root manifest"
    )


def _is_ancestor_or_self(candidate: Path, cwd: Path) -> bool:
    """True when ``cwd`` is ``candidate`` or lives somewhere under it.

    Both paths must already be resolved. Used to scope the persistent
    known-roots cache to the current project tree: a cached root that
    doesn't contain ``cwd`` belongs to a *different* project and must
    never be selected as this invocation's repo root.
    """
    try:
        cwd.relative_to(candidate)
        return True
    except ValueError:
        return False


def collect_git_ancestors(start: Path) -> list[Path]:
    """Return every ancestor of ``start`` that contains a ``.git`` entry.

    Innermost (deepest) first. A strictly git-anchored enumeration, kept
    for callers that specifically mean "git repos" rather than "plan-tool
    project roots" — repo-root candidate discovery uses the broader
    :func:`collect_project_root_ancestors` (``.git`` *or*
    ``.plan-tool/plans.json``) instead. Returns an empty list when no
    ``.git`` ancestor exists (no error — the caller may have other
    candidate sources).
    """
    out: list[Path] = []
    cursor = start.resolve()
    while True:
        if (cursor / ".git").exists():
            out.append(cursor)
        parent = cursor.parent
        if parent == cursor:
            return out
        cursor = parent


KNOWN_ROOTS_CACHE_SUBPATH = Path(".plan-tool") / "git-roots.json"


def default_known_roots_path() -> Path:
    """Resolve the persistent cache path lazily so ``$HOME`` overrides
    (e.g. test monkeypatches) are honored on every call rather than
    being frozen at import time."""
    return Path.home() / KNOWN_ROOTS_CACHE_SUBPATH


def load_known_roots(cache_path: Optional[Path] = None) -> list[Path]:
    """Read the persistent record of previously-resolved repo roots.

    Silently returns ``[]`` for a missing or malformed cache — the cache
    is a hint, not a source of truth, and a corrupted entry must not
    block a fresh walk-up resolution.
    """
    cp = cache_path or default_known_roots_path()
    if not cp.is_file():
        return []
    try:
        data = json.loads(cp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    raw = data.get("roots", []) if isinstance(data, dict) else []
    if not isinstance(raw, list):
        return []
    out: list[Path] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            p = Path(item.strip())
            if p.is_dir():
                out.append(p.resolve())
    return out


def record_known_root(root: Path, cache_path: Optional[Path] = None) -> None:
    """Append ``root`` to the persistent record if not already present.

    Best-effort: any write error is swallowed. The cache is purely a
    performance/discovery hint; failing to update it never affects
    correctness of the current invocation.
    """
    cp = cache_path or default_known_roots_path()
    try:
        existing = load_known_roots(cp)
        resolved = root.resolve()
        if resolved in existing:
            return
        existing.append(resolved)
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(
            json.dumps({"roots": [str(p) for p in existing]}, indent=2),
            encoding="utf-8",
        )
    except OSError:
        return


def _controlling_git_repo(path: Path) -> Optional[Path]:
    """Return the deepest ``.git`` ancestor of ``path``, or ``None``.

    The deepest ``.git`` ancestor of a tracked file is the repo that
    "controls" the file in git's eyes — a sibling ``.git`` higher up
    is irrelevant because git's own resolution stops at the innermost
    ``.git``. Used by :func:`find_umbrella_root` to bucket files by
    their owning repo before computing a cross-repo umbrella.
    """
    cursor = path.resolve()
    while True:
        if (cursor / ".git").exists():
            return cursor
        parent = cursor.parent
        if parent == cursor:
            return None
        cursor = parent


def find_umbrella_root(
    file_paths: Sequence[Path],
    *,
    search_from: Path,
    fallback: Optional[Path] = None,
) -> Optional[Path]:
    """Return the repo root that "controls" every path in ``file_paths``.

    Resolves each path against ``search_from`` when relative, then
    asks :func:`_controlling_git_repo` which ``.git`` owns it. Three
    cases:

    1. **All files share one owning ``.git``** — return that repo.
       This is the dominant single-repo case; a plan whose files all
       live under ``.agents/`` returns ``.agents/`` (the inner repo)
       even when called from the outer project root.
    2. **Files span multiple owning ``.git`` repos** — return the
       deepest common ancestor of those repos. The umbrella may be a
       non-``.git`` directory (e.g. a parent that contains sibling
       repos like ``app-amplify/`` and ``app-infra/``); that's the
       whole point — the umbrella is the path that encapsulates every
       file even when no single ``.git`` does.
    3. **No file has an owning ``.git``** — return ``fallback``.

    Files whose path doesn't exist on disk (e.g. new files the plan
    will create) walk up from the path until an existing parent is
    found, then use that parent's owning ``.git``.
    """
    if not file_paths:
        return fallback
    owning_repos: list[Path] = []
    for p in file_paths:
        candidate = p if p.is_absolute() else (search_from / p)
        cursor = candidate
        while not cursor.exists() and cursor.parent != cursor:
            cursor = cursor.parent
        if not cursor.exists():
            continue
        repo = _controlling_git_repo(cursor)
        if repo is not None:
            owning_repos.append(repo)
    if not owning_repos:
        return fallback
    deduped = list(dict.fromkeys(owning_repos))
    if len(deduped) == 1:
        return deduped[0]
    return _deepest_common_ancestor(deduped)


def _deepest_common_ancestor(paths: Sequence[Path]) -> Path:
    """Return the deepest directory that is an ancestor of every path.

    All paths must be absolute. The result is the longest common prefix
    of their ``parts`` tuples, joined back into a ``Path``. When a
    single path is given, returns that path's nearest existing dir.
    """
    parts_list = [list(p.parts) for p in paths]
    common_parts: list[str] = []
    for tup in zip(*parts_list):
        first = tup[0]
        if all(p == first for p in tup):
            common_parts.append(first)
        else:
            break
    return Path(*common_parts) if common_parts else Path(paths[0].parts[0])


def find_repo_root_candidates(
    manifest_path: Optional[Path] = None,
    *,
    cwd: Optional[Path] = None,
    cache_path: Optional[Path] = None,
) -> list[Path]:
    """Return every plausible repo-root candidate, innermost first.

    Combines the *project-root* ancestors of ``cwd`` (default current
    working directory) and the persistent record at
    ``default_known_roots_path()``. When an explicit ``manifest_path`` is
    supplied, its parent directory's project-root ancestors are included
    too. A project root is any ancestor with a ``.git`` entry **or** a
    ``.plan-tool/plans.json`` manifest (see
    :func:`collect_project_root_ancestors` / :func:`is_project_root`) — the
    same predicate :func:`find_repo_root_from_cwd` walks, so a manifest-only
    project dir nested under an unrelated git repo is a candidate here just
    as it is the answer there. Enumerating *every* such ancestor — not just
    the innermost — is what lets a project with nested ``.git`` folders
    (sub-repos, submodules) resolve to the root that actually owns the plans.

    The persistent cache is filtered to roots that contain ``cwd`` (ancestor
    or self). Without this scoping, a root recorded while working in project
    A would be offered as a candidate when running plan-tool in project B —
    and because :func:`build_plan_tool_context` selects the candidate that
    resolves the most manifest entries, A's larger manifest could hijack B's
    ``plan-tool list``. The cache's remaining purpose is re-discovering a
    no-``.git`` umbrella ancestor of ``cwd`` that the ``.git`` walk can't see.

    The union is deduplicated and ordered innermost-first (deeper paths before
    shallower ones) so :func:`build_plan_tool_context` can tie-break by
    preferring the most specific candidate when multiple candidates resolve
    the same number of manifest entries.
    """
    cwd_origin = (cwd or Path.cwd()).resolve()
    cached_roots = [
        r for r in load_known_roots(cache_path) if _is_ancestor_or_self(r, cwd_origin)
    ]
    sources = [collect_project_root_ancestors(cwd_origin), cached_roots]
    if manifest_path is not None:
        sources.insert(0, collect_project_root_ancestors(manifest_path.parent))
    candidates: list[Path] = []
    seen: set[Path] = set()
    for source in sources:
        for c in source:
            if c not in seen:
                seen.add(c)
                candidates.append(c)
    candidates.sort(key=lambda p: len(p.parts), reverse=True)
    return candidates


def find_plans_dir(start: Optional[Path] = None) -> Path:
    """Walk up from `start` (default: cwd) looking for docs/implementation-plans.

    Raises FileNotFoundError if not found by the filesystem root.
    """
    cursor = (start or Path.cwd()).resolve()
    while True:
        candidate = cursor / PLANS_SUBPATH
        if candidate.is_dir():
            return candidate
        if cursor.parent == cursor:
            raise FileNotFoundError(
                f"could not find {PLANS_SUBPATH} walking up from {start or Path.cwd()}"
            )
        cursor = cursor.parent


def resolve_explicit_plans_dir(
    override: Optional[Path] = None,
    *,
    environ: Optional[Mapping[str, str]] = None,
) -> Optional[Path]:
    """Return a plans directory only when ``--plans-dir`` or env requests it."""
    if override is not None:
        p = override.expanduser().resolve()
        if not p.is_dir():
            raise FileNotFoundError(f"--plans-dir is not a directory: {p}")
        return p
    mapping = environ if environ is not None else os.environ
    raw = mapping.get("PLAN_TOOL_PLANS_DIR", "").strip()
    if raw:
        p = Path(raw).expanduser().resolve()
        if not p.is_dir():
            raise FileNotFoundError(
                f"PLAN_TOOL_PLANS_DIR is not a directory: {p}"
            )
        return p
    return None


def resolve_repo_root(
    override: Optional[Path] = None,
    *,
    environ: Optional[Mapping[str, str]] = None,
) -> Optional[Path]:
    """Return an explicit repo root only when a flag or env requests one.

    Precedence (highest first): ``override`` (CLI ``--repo-root``) →
    ``PLAN_TOOL_REPO_ROOT`` env var → ``None`` (callers fall back to
    a mode-dependent default — see :func:`build_plan_tool_context`).
    In manifest mode the caller's fallback is the candidate scoring
    in :func:`find_repo_root_candidates`; in directory mode it's
    :func:`find_repo_root` from the plans dir.

    Both sources are validated as existing directories. A path that doesn't
    exist or isn't a directory raises ``FileNotFoundError`` rather than
    silently falling through — surfacing the misconfiguration here is
    cheaper than chasing it through manifest resolution later.
    """
    if override is not None:
        p = override.expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"--repo-root does not exist: {p}")
        if not p.is_dir():
            raise FileNotFoundError(f"--repo-root is not a directory: {p}")
        return p
    mapping = environ if environ is not None else os.environ
    raw = mapping.get("PLAN_TOOL_REPO_ROOT", "").strip()
    if raw:
        p = Path(raw).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"PLAN_TOOL_REPO_ROOT does not exist: {p}")
        if not p.is_dir():
            raise FileNotFoundError(
                f"PLAN_TOOL_REPO_ROOT is not a directory: {p}"
            )
        return p
    return None


@dataclass
class PlanToolContext:
    """Resolved workspace for one CLI invocation.

    ``missing_paths`` lists manifest entries that resolved to a path that does
    not exist on disk. Only populated in manifest mode; always empty in
    directory mode. Callers (e.g. ``cmd_list``) surface this so a user whose
    cwd landed on the wrong repo root — making every manifest entry point at a
    nonexistent file — gets a diagnostic rather than an empty list.

    ``duplicate_paths`` lists plan files that exist under one of the non-
    selected candidate roots in addition to the selected root. Each entry
    is the full path of a duplicate file the user may want to archive
    (because it likely represents a stale copy from a forgotten checkout
    or a pre-move location). Only populated in manifest mode when
    candidate auto-discovery surfaces more than one viable root; always
    empty when ``--repo-root`` / ``PLAN_TOOL_REPO_ROOT`` is pinned.
    """

    repo_root: Path
    plans_dir: Optional[Path]
    entries: list["PlanEntry"]
    missing_paths: list[Path] = field(default_factory=list)
    duplicate_paths: list[Path] = field(default_factory=list)


def _score_candidate(
    candidate: Path, manifest_path: Optional[Path] = None
) -> tuple[int, list[Path], list[Path]]:
    """Count how many manifest entries resolve under ``candidate``.

    Returns ``(resolved_count, resolved_paths, missing_paths)``. Used by
    :func:`build_plan_tool_context` to pick the best candidate root when
    walk-up enumeration yields multiple ``.git`` ancestors. With no explicit
    ``manifest_path`` each candidate is scored against its own per-project
    manifest at ``<candidate>/.plan-tool/plans.json``.
    """
    mf = manifest_path if manifest_path is not None else default_manifest_path(candidate)
    declared = load_manifest_plan_paths(candidate, manifest_path=mf)
    resolved = [p for p in declared if p.is_file()]
    missing = [p for p in declared if not p.is_file()]
    return len(resolved), resolved, missing


def build_plan_tool_context(
    plans_dir_override: Optional[Path] = None,
    *,
    environ: Optional[Mapping[str, str]] = None,
    manifest_path: Optional[Path] = None,
    repo_root_override: Optional[Path] = None,
) -> PlanToolContext:
    """Resolve the plans dir, repo root, and plan entries for one CLI run.

    Repo-root precedence: ``repo_root_override`` (CLI ``--repo-root``) →
    ``PLAN_TOOL_REPO_ROOT`` env var → candidate auto-discovery. In
    directory mode auto-discovery is :func:`find_repo_root` from the
    plans dir. In manifest mode auto-discovery uses
    :func:`find_repo_root_candidates` (every project-root ancestor — by
    ``.git`` or ``.plan-tool/plans.json`` — of the manifest's parent dir,
    every project-root ancestor of the current working directory, and the
    roots in the persistent record at ``$HOME/.plan-tool/git-roots.json``
    that contain cwd); each candidate
    is scored by how many manifest entries resolve under it, and the
    highest-scoring candidate wins (innermost on ties). Cache entries that
    don't contain cwd are skipped, so a root recorded in one project can't
    hijack resolution in an unrelated one. Successful auto-resolution is
    written back to the cache so subsequent invocations from any
    subcommand pick up the same root without re-walking.

    In manifest mode, when no override is given and **no** candidate
    resolves a single manifest entry, this raises :class:`ManifestError`
    listing every candidate tried — the all-missing signature is the
    unambiguous "no plausible repo root reachable" footprint, and
    silently reporting "0 plans, N missing" is the silent-corruption
    path. Callers who explicitly pin ``--repo-root`` /
    ``PLAN_TOOL_REPO_ROOT`` opt out of this guard: they own the root and
    the report is their tool for debugging it.
    """
    explicit_root = resolve_repo_root(repo_root_override, environ=environ)
    explicit = resolve_explicit_plans_dir(plans_dir_override, environ=environ)
    if explicit is not None:
        repo_root = explicit_root or find_repo_root(explicit)
        entries = list_plans(explicit)
        return PlanToolContext(repo_root=repo_root, plans_dir=explicit, entries=entries)
    if explicit_root is not None:
        repo_root = explicit_root
        declared = load_manifest_plan_paths(repo_root, manifest_path=manifest_path)
        entries = collect_plan_entries(declared)
        missing = [p for p in declared if not p.is_file()]
        return PlanToolContext(
            repo_root=repo_root,
            plans_dir=None,
            entries=entries,
            missing_paths=missing,
        )
    candidates = find_repo_root_candidates(manifest_path)
    if not candidates:
        # No ``.git`` in any ancestor of manifest dir or cwd; raise the
        # familiar FileNotFoundError so the operator sees the same shape
        # they'd get if they pointed plan-tool at a directory with no
        # git history at all.
        find_repo_root_from_cwd()  # raises with a useful message
    best_root: Optional[Path] = None
    best_score = -1
    best_declared: list[Path] = []
    best_missing: list[Path] = []
    for c in candidates:
        score, resolved, missing = _score_candidate(c, manifest_path)
        declared = resolved + missing
        if score > best_score or (
            score == best_score
            and best_root is not None
            and len(c.parts) > len(best_root.parts)
        ):
            best_root = c
            best_score = score
            best_declared = declared
            best_missing = missing
    assert best_root is not None  # candidates was non-empty above
    if best_declared and best_score == 0:
        tried = "\n  - ".join(str(c) for c in candidates)
        raise ManifestError(
            f"every manifest entry ({len(best_declared)}) resolves to a "
            f"missing path under every candidate repo_root tried:\n  - {tried}\n"
            f"Pass --repo-root <repo> or set PLAN_TOOL_REPO_ROOT to override."
        )
    if best_declared and best_score > 0:
        record_known_root(best_root)
    entries = collect_plan_entries(best_declared)
    duplicates = _collect_duplicate_plan_paths(
        manifest_path=manifest_path,
        selected_root=best_root,
        all_candidates=candidates,
    )
    return PlanToolContext(
        repo_root=best_root,
        plans_dir=None,
        entries=entries,
        missing_paths=best_missing,
        duplicate_paths=duplicates,
    )


def _collect_duplicate_plan_paths(
    *,
    manifest_path: Optional[Path],
    selected_root: Path,
    all_candidates: Sequence[Path],
) -> list[Path]:
    """Find plan files that exist under non-selected candidate roots.

    For each non-selected candidate, resolve the manifest entries and
    collect every file that exists on disk. These represent duplicate
    copies (likely stale: a forgotten checkout, a pre-move location)
    that the user may want to archive. The list is deduplicated against
    the selected root's files so the operator's own canonical copies
    aren't reported back as duplicates. With no explicit ``manifest_path``
    each candidate is read from its own ``<candidate>/.plan-tool/plans.json``.
    """

    def _mf(root: Path) -> Path:
        return manifest_path if manifest_path is not None else default_manifest_path(root)

    selected_paths = {
        p.resolve()
        for p in load_manifest_plan_paths(selected_root, manifest_path=_mf(selected_root))
        if p.is_file()
    }
    seen: set[Path] = set()
    out: list[Path] = []
    for candidate in all_candidates:
        if candidate == selected_root:
            continue
        for p in load_manifest_plan_paths(candidate, manifest_path=_mf(candidate)):
            if not p.is_file():
                continue
            resolved = p.resolve()
            if resolved in selected_paths or resolved in seen:
                continue
            seen.add(resolved)
            out.append(resolved)
    return out


def resolve_plan_for_context(ctx: PlanToolContext, name: str) -> Path:
    if ctx.plans_dir is not None:
        return resolve_plan(ctx.plans_dir, name)
    return resolve_registered_plan(ctx.entries, name)


def slug_from_filename(
    name: str | Path, *, default_to_stem: bool = True
) -> Optional[str]:
    """``1-foo-bar.md`` → ``foo-bar``. Strips priority prefix and extension.

    Canonical implementation used by ``PlanEntry.slug`` and the
    per-module wrappers in ``create``/``detail``/``jira``/``split``.
    The fallback behaviour for files without a numeric
    prefix splits in two:

    - ``default_to_stem=True`` (default) returns the bare stem
      (``notes.md`` → ``notes``). Matches ``PlanEntry.slug`` and the
      ``str``-returning wrappers in ``detail``/``jira``/``split``.
    - ``default_to_stem=False`` returns ``None``. Matches the
      ``Optional[str]``-returning wrapper in ``create``
      that uses the slug as a uniqueness key and wants to reject
      unprefixed files explicitly.
    """
    stem = Path(name).stem
    parts = stem.split("-", 1)
    if len(parts) == 2 and parts[0].isdigit():
        return parts[1]
    return stem if default_to_stem else None


@dataclass
class PlanEntry:
    """One entry in `plan list` output."""

    path: Path
    plan: Optional[Plan]  # None when the file failed to parse/validate.
    error: Optional[str]  # Populated when `plan is None`.

    @property
    def slug(self) -> str:
        """`1-foo-bar.md` -> `foo-bar`. Strips priority prefix and extension."""
        result = slug_from_filename(self.path)
        assert result is not None  # default_to_stem=True guarantees non-None
        return result


def collect_plan_entries(paths: Sequence[Path]) -> list[PlanEntry]:
    """Parse each path that exists and is a file; same rules as :func:`list_plans`."""
    entries: list[PlanEntry] = []
    for path in sorted({p.resolve() for p in paths if p.is_file()}):
        if path.suffix.lower() != ".md":
            continue
        try:
            plan = parse_plan(path)
            entries.append(PlanEntry(path=path, plan=plan, error=None))
        except ParseError as exc:
            # Carry an unparseable plan as a malformed entry (plan=None) so it
            # surfaces as a MALFORMED row / INVALID verdict, exactly like a
            # schema-invalid plan. ParseError's message is already human-
            # readable, so attach it directly (no structured .errors list).
            entries.append(PlanEntry(path=path, plan=None, error=str(exc)))
        except ValidationError as exc:
            summary = "\n".join(format_validation_errors(exc.errors)) or str(exc)
            entries.append(PlanEntry(path=path, plan=None, error=summary))
    return entries


def list_plans(plans_dir: Path) -> list[PlanEntry]:
    """Return every top-level .md file under `plans_dir`, parsed where possible."""
    paths = plans_dir.glob("*.md")
    return collect_plan_entries(paths)


def load_manifest_plan_paths(
    repo_root: Path,
    manifest_path: Optional[Path] = None,
) -> list[Path]:
    """Read ``plans`` array from JSON; paths must be repo-relative."""
    mf = manifest_path or default_manifest_path(repo_root)
    if not mf.is_file():
        return []
    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"invalid JSON in {mf}: {exc}") from exc
    raw = data.get("plans", [])
    if not isinstance(raw, list):
        raise ManifestError(
            f'"plans" in {mf} must be a list, got {type(raw).__name__}'
        )
    out: list[Path] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            continue
        candidate = Path(item.strip())
        if candidate.is_absolute():
            raise ManifestError(
                f"manifest entries must be repo-relative; "
                f"got absolute path {candidate} in {mf}"
            )
        out.append((repo_root / candidate).resolve())
    return out


def list_plans_from_manifest(
    repo_root: Path,
    manifest_path: Optional[Path] = None,
) -> list[PlanEntry]:
    paths = load_manifest_plan_paths(repo_root, manifest_path=manifest_path)
    return collect_plan_entries(paths)


def resolve_plan(plans_dir: Path, name: str) -> Path:
    """Resolve a user-supplied plan name to a concrete .md path under ``plans_dir``."""
    cleaned = name.removesuffix(".md")
    candidates = [
        plans_dir / f"{cleaned}.md",
        plans_dir / f"1-{cleaned}.md",
        plans_dir / f"2-{cleaned}.md",
        plans_dir / f"3-{cleaned}.md",
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(
        f"no plan matching '{name}' under {plans_dir}. Tried: "
        + ", ".join(c.name for c in candidates)
    )


def resolve_registered_plan(entries: Sequence[PlanEntry], name: str) -> Path:
    """Resolve ``name`` to a path among manifest-registered plan entries.

    When no registered entry matches, scan the directories of existing
    entries for an orphan file with the same slug and, if one exists,
    append a hint to the error pointing at ``plan-tool register``. The
    scan is cheap (a handful of ``Path.is_file`` checks per directory)
    and resolves the long-standing "completeness says missing, create
    says exists" asymmetry by giving the user a concrete recovery step.
    """
    cleaned = name.removesuffix(".md")
    stems = {cleaned, f"1-{cleaned}", f"2-{cleaned}", f"3-{cleaned}"}
    for e in entries:
        if e.slug == cleaned or e.path.stem in stems or e.path.name == f"{cleaned}.md":
            return e.path
    orphan = _find_orphan_plan_file(entries, cleaned)
    if orphan is not None:
        raise FileNotFoundError(
            f"no plan matching '{name}' among registered plan entries\n"
            f"hint: file exists at {orphan} but isn't registered. "
            f"Run: plan-tool register {orphan}"
        )
    raise FileNotFoundError(
        f"no plan matching '{name}' among registered plan entries"
    )


def _find_orphan_plan_file(
    entries: Sequence[PlanEntry], cleaned_name: str
) -> Optional[Path]:
    """Scan known plan directories for an unregistered file matching ``cleaned_name``.

    Returns the first matching file found in any directory that already
    hosts at least one registered plan, or ``None``. We only scan dirs
    derived from ``entries`` (no hardcoded paths) so the heuristic adapts
    to whatever layout the repo uses.
    """
    candidate_dirs: list[Path] = []
    seen: set[Path] = set()
    for e in entries:
        parent = e.path.parent.resolve()
        if parent in seen:
            continue
        seen.add(parent)
        candidate_dirs.append(parent)
    filenames = [
        f"{cleaned_name}.md",
        f"1-{cleaned_name}.md",
        f"2-{cleaned_name}.md",
        f"3-{cleaned_name}.md",
    ]
    for d in candidate_dirs:
        for fn in filenames:
            candidate = d / fn
            if candidate.is_file():
                return candidate
    return None
