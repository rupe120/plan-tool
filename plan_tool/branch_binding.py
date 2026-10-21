"""Git-config-backed ad-hoc plan→branch override store.

Persists the optional plan→branch override in untracked local git config
(``git config --local plan-tool.binding.<slug>``) — nothing tracked, nothing in
``plans.json`` or frontmatter. The store is branch-independent, lost on a
machine switch (falling back to the slug-derived branch name), and never
diverges between two devs. Stdlib-only leaf — imports nothing from
``create``/``launcher``/``locator``/``cli.*`` so ``branch_ownership.py`` (the
reverse-lookup consumer) and the run guard can depend on it without a cycle,
mirroring ``plan_tool/cli/gitcommit.py``'s leaf contract.

Error posture is set-loud / clear-quiet: ``set_binding`` raises
``BranchBindingError`` on empty input or any git-write failure (a desync the
user must see), while ``clear_binding`` treats an absent binding as a satisfied
no-op (the desired end-state already holds). Slug/ref validity is the caller's
concern; this store does not re-validate the slug shape.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class BranchBindingError(Exception):
    """Failed to write/clear an ad-hoc branch binding in local git config."""


def _binding_key(slug: str) -> str:
    """Config key for ``slug``'s override: ``plan-tool.binding.<slug>``.

    Git parses this as the ``plan-tool`` section, ``binding`` subsection,
    ``<slug>`` key and lowercases the key tail — canonical slugs are already
    lowercase kebab-case, so they round-trip unchanged.
    """
    return f"plan-tool.binding.{slug}"


def get_binding(repo_root: Path, slug: str) -> str | None:
    """The branch bound to ``slug``, or ``None`` when unset.

    Folds key-absent (rc 1) and non-repo (rc 128) into one ``None`` — only an
    rc-0 read is a positive answer, matching ``path_is_gitignored``'s posture.
    """
    proc = subprocess.run(
        ["git", "config", "--local", "--get", _binding_key(slug)],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def set_binding(repo_root: Path, slug: str, branch: str) -> None:
    """Bind ``slug`` to ``branch`` in local git config — loud on failure.

    Raises ``BranchBindingError`` when ``slug`` or ``branch`` is empty after
    ``.strip()``, or on any non-zero git rc (a bad ``--local`` write, including
    outside a work tree → rc 128) — a desync the caller must surface, not
    swallow. Stays a thin primitive: registration / uniqueness / clean-tree
    preconditions are the ``attach-branch`` handler's policy, enforced before
    this call.
    """
    if not slug.strip():
        raise BranchBindingError("Cannot bind an empty slug.")
    if not branch.strip():
        raise BranchBindingError(f"Cannot bind slug {slug!r} to an empty branch.")
    proc = subprocess.run(
        ["git", "config", "--local", _binding_key(slug), branch],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise BranchBindingError(
            f"Failed to bind slug {slug!r} to branch {branch!r}: "
            f"{proc.stderr.strip()}"
        )


def clear_binding(repo_root: Path, slug: str) -> bool:
    """Remove ``slug``'s binding — quiet, idempotent, never raises.

    Returns ``True`` when a binding existed and was unset (rc 0); ``False`` on
    any non-zero rc (no binding to unset → rc 5, non-repo → rc 128). An absent
    binding is a satisfied no-op, so a ``detach-branch`` retry never errors.
    """
    proc = subprocess.run(
        ["git", "config", "--local", "--unset", _binding_key(slug)],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def all_bindings(repo_root: Path) -> dict[str, str]:
    """Every ``{slug: branch}`` override pair in local git config.

    Returns ``{}`` on any non-zero rc (no matches → rc 1, non-repo → rc 128).
    Each ``git config --get-regexp`` line is ``plan-tool.binding.<slug> <branch>``;
    split key from value on the first whitespace and strip the section prefix.
    """
    proc = subprocess.run(
        ["git", "config", "--local", "--get-regexp", r"^plan-tool\.binding\."],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return {}
    prefix = "plan-tool.binding."
    bindings: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        key, _, value = line.partition(" ")
        if not key.startswith(prefix):
            continue
        slug = key[len(prefix):]
        bindings[slug] = value.strip()
    return bindings


def reverse_binding(repo_root: Path, branch: str) -> str | None:
    """The slug bound to ``branch``, or ``None`` when none is.

    Derived from ``all_bindings`` (one parse path) so the forward and reverse
    views can never disagree. Iterates in sorted-slug order for deterministic
    results if the caller-enforced one-branch-per-plan invariant is ever
    violated.
    """
    target = branch.strip()
    bindings = all_bindings(repo_root)
    for slug in sorted(bindings):
        if bindings[slug].strip() == target:
            return slug
    return None
