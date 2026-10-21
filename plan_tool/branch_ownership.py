"""Branch-ownership decision layer: two lookups + a pure 4-tier classifier.

Sits above the config leaf (:mod:`plan_tool.project_config`, step 1) and the
override store (:mod:`plan_tool.branch_binding`, step 3) and answers the two
*deliberately-separate* questions every branch-aware call site needs:

- *where should plan P run?* — :func:`expected_branch` (override-else-derive)
- *who owns branch B?* — :func:`branch_owner` (reverse-binding-else-convention-owner)

Plus the pure :func:`classify_branch`, which grades a current branch B against a
plan P into one of four ordered tiers (1 strictest … 4 most permissive).

The load-bearing precedence rules:

- **ad-hoc-beats-convention** — :func:`branch_owner` consults ``reverse_binding``
  before convention ownership; an explicit binding is the strongest signal.
- **registered-locally** — convention ownership fires only when the
  convention-owning slug is in the caller-supplied ``registered_slugs``.
- **forfeit-when-bound-elsewhere** — a convention match whose slug is ad-hoc-bound
  to a *different* branch is dropped, so a plan bound away from its derived name
  no longer convention-owns it.

I/O is confined to the two lookups (they read git config via step 3);
:func:`classify_branch`, :func:`convention_owner`, and
:func:`matches_convention_pattern` are **pure** — the run guard (step 5) does the
git read once via :func:`branch_owner`, then classifies without re-reading.

Mid-tier leaf: imports only stdlib and the two upstream leaves
(:mod:`plan_tool.project_config`, :mod:`plan_tool.branch_binding`) — nothing from
``create`` / ``launcher`` / ``locator`` / ``cli.*`` / ``gitcommit`` — so the run
guard and the branch verbs can depend on it without a cycle. The registered-slug
set is a parameter, never read from ``locator`` here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Collection, Optional, Sequence

from plan_tool.branch_binding import get_binding, reverse_binding
from plan_tool.project_config import convention_names, derive_branch


class Tier(IntEnum):
    """Ownership tiers as an ordered severity ladder — 1 strictest, 4 loosest.

    ``IntEnum`` (not the ``(str, Enum)`` config-vocab pattern) because the
    guard's "block at ≤ Tier 2" predicate reads naturally off integer order.
    """

    AD_HOC_OWNED = 1
    CONVENTION_OWNED = 2
    ORPHAN_PATTERN = 3
    UNOWNED = 4


# The ownership kind a ``BranchOwner`` carries.
OWNER_AD_HOC = "ad-hoc"
OWNER_CONVENTION = "convention"


@dataclass(frozen=True)
class BranchOwner:
    """Who owns a branch and how. Returned by :func:`branch_owner`.

    ``kind`` is one of :data:`OWNER_AD_HOC` / :data:`OWNER_CONVENTION`; a
    ``None`` return from :func:`branch_owner` means no Tier-1/Tier-2 owner.
    """

    slug: str
    kind: str


@dataclass(frozen=True)
class BranchClassification:
    """A current branch graded against a plan. Returned by :func:`classify_branch`.

    ``owner`` is the owning slug for Tier 1/2, ``None`` for Tier 3/4.
    ``is_owned_by_plan`` is ``owner == plan_slug`` — the single field the run
    guard reads to decide block-unless-mine vs warn vs nudge.
    """

    tier: Tier
    owner: Optional[str]
    is_owned_by_plan: bool


def expected_branch(repo_root: Path, slug: str, prefixes: Sequence[str]) -> str:
    """Where plan ``slug`` should run: the ad-hoc override else the derived name.

    Override-else-derive: returns ``get_binding(repo_root, slug)`` when set,
    else ``derive_branch(slug, prefixes)`` (primary-prefix derivation). Powers
    the guard's Tier-4 nudge and ``--switch-branch``. ``prefixes`` is a
    parameter (caller computes ``branch_prefixes(repo_root)`` once).
    """
    override = get_binding(repo_root, slug)
    if override:
        return override
    return derive_branch(slug, prefixes)


def branch_owner(
    repo_root: Path,
    branch: str,
    registered_slugs: Collection[str],
    prefixes: Sequence[str],
) -> Optional[BranchOwner]:
    """Who owns ``branch``: reverse-binding-else-convention-owner (ad-hoc wins).

    1. ``reverse_binding(branch)`` set → ``BranchOwner(slug, OWNER_AD_HOC)`` —
       an ad-hoc owner need not be locally registered (the binding is itself
       the strongest signal).
    2. Else the convention owner, *unless* its slug is ad-hoc-bound to a
       different branch (forfeit-when-bound-elsewhere) → demoted to ``None``.
    3. Else ``None`` (the Tier-3-vs-Tier-4 split is the classifier's job).
    """
    rev = reverse_binding(repo_root, branch)
    if rev is not None:
        return BranchOwner(slug=rev, kind=OWNER_AD_HOC)

    co = convention_owner(branch, registered_slugs, prefixes)
    if co is not None:
        bound = get_binding(repo_root, co)
        # Forfeit the convention claim when this slug is ad-hoc-bound elsewhere:
        # a plan bound away from its derived name no longer convention-owns it.
        if bound is None or bound == branch:
            return BranchOwner(slug=co, kind=OWNER_CONVENTION)

    return None


def convention_owner(
    branch: str,
    registered_slugs: Collection[str],
    prefixes: Sequence[str],
) -> Optional[str]:
    """The registered slug whose convention names contain ``branch``, else ``None``.

    Pure (no I/O, no ``repo_root``): encodes the registered-locally condition —
    a slug not in ``registered_slugs`` is never returned, so an orphan
    pattern-match falls through to Tier 3. Reuses step 1's
    :func:`convention_names` as the single match rule (secondary prefixes still
    recognized). Scans ``sorted(registered_slugs)`` for a deterministic first
    match even if a caller passes a non-deduped, slug-colliding collection.
    """
    for slug in sorted(registered_slugs):
        if branch in convention_names(slug, prefixes):
            return slug
    return None


def matches_convention_pattern(branch: str, prefixes: Sequence[str]) -> bool:
    """True when ``branch`` has a configured prefix with a non-empty tail.

    Pure. Distinguishes Tier 3 (looks like a convention branch, nobody local
    owns it) from Tier 4 (matches no pattern). The non-empty-tail check stops a
    bare prefix string from counting as a match.
    """
    return any(
        branch.startswith(p) and len(branch) > len(p) for p in prefixes
    )


def classify_branch(
    branch: str,
    plan_slug: str,
    owner: Optional[BranchOwner],
    prefixes: Sequence[str],
) -> BranchClassification:
    """Grade ``branch`` against ``plan_slug`` into one of the four tiers.

    Pure: consumes the ``owner`` from :func:`branch_owner` as data and does
    zero I/O. The both-claimed edge is already resolved upstream (reverse-binding
    wins), so an ``OWNER_AD_HOC`` owner has already shadowed any convention claim.
    """
    if owner is not None and owner.kind == OWNER_AD_HOC:
        return BranchClassification(
            tier=Tier.AD_HOC_OWNED,
            owner=owner.slug,
            is_owned_by_plan=owner.slug == plan_slug,
        )
    if owner is not None and owner.kind == OWNER_CONVENTION:
        return BranchClassification(
            tier=Tier.CONVENTION_OWNED,
            owner=owner.slug,
            is_owned_by_plan=owner.slug == plan_slug,
        )
    if matches_convention_pattern(branch, prefixes):
        return BranchClassification(
            tier=Tier.ORPHAN_PATTERN, owner=None, is_owned_by_plan=False
        )
    return BranchClassification(
        tier=Tier.UNOWNED, owner=None, is_owned_by_plan=False
    )
