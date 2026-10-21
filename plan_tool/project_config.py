"""Branch-awareness config leaf: read the flag, prefixes, and derive branches.

Answers the three questions any branch-aware code path needs without
importing ``create`` / ``launcher`` / ``locator``:

- *is branch-awareness on?* — :func:`branch_awareness_enabled`
- *what branch prefixes are configured?* — :func:`branch_prefixes`
- *what branch(es) correspond to a slug?* — :func:`derive_branch` /
  :func:`convention_names`

The branch-awareness readers use **per-level tolerance**: each config level
(env → project → user) is an independent fallback, so a malformed user file
never crashes an otherwise-fine project. :func:`_read_level` swallows every
malformed shape and returns ``None`` ("level unset").

Stage-feedback limits are a separate strict project-only contract. They never
read user configuration and reject a present malformed block before invocation.

Off by default: with no config, :func:`branch_awareness_enabled` returns
``False`` for every repo, so callers gate on the flag *first* and
short-circuit before deriving or reading any branch.

Configuration leaf: it imports stdlib modules only — nothing from
:mod:`plan_tool.create` / ``launcher`` / ``locator`` / ``scenario_capture`` —
so any command can depend on it without a cycle. ``repo_root`` is a parameter
(never calls ``locator``) so the leaf stays hermetic and testable against a
``tmp_path``.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

# Truthy/falsy env tokens. ``_TRUTHY`` is copied verbatim from
# ``plan_tool.scenario_capture`` (an orchestrator-tier module) to preserve
# the leaf contract — depending on it would invert the import direction.
# A shared truthy-env helper is a deferred refactor.
_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSY = frozenset({"0", "false", "no", "off"})

# The canonical default prefix list. Accessors return a fresh ``list`` so
# callers can't mutate this constant.
DEFAULT_BRANCH_PREFIXES = ("plan/",)

# Env override controlling only the enabled flag (never the prefixes).
BRANCH_AWARENESS_ENV = "PLAN_TOOL_BRANCH_AWARENESS"

# Repo-relative project config location.
PROJECT_CONFIG_SUBPATH = Path(".plan-tool") / "config.json"


# Stage-feedback limits are repository behavior, never a user preference.
ROADMAP_FEEDBACK_CONFIG_BLOCK = "roadmap_feedback"
STAGE_LIMITS_CONFIG_BLOCK = "stage_limits"
MAX_ACTIVE_FEEDBACK_ITEMS_KEY = "max_active_feedback_items"
MAX_RESPONSE_BYTES_KEY = "max_response_bytes"
MAX_PROSE_AMENDMENT_BYTES_KEY = "max_prose_amendment_bytes"

# Hard ceilings remain project behavior even when no config file exists.
HARD_MAX_ACTIVE_FEEDBACK_ITEMS = 32
HARD_MAX_RESPONSE_BYTES = 32 * 1024
HARD_MAX_PROSE_AMENDMENT_BYTES = 4 * 1024


@dataclass(frozen=True)
class StageFeedbackLimits:
    """The effective non-expandable budget for one stage feedback reply."""

    max_active_feedback_items: int = HARD_MAX_ACTIVE_FEEDBACK_ITEMS
    max_response_bytes: int = HARD_MAX_RESPONSE_BYTES
    max_prose_amendment_bytes: int = HARD_MAX_PROSE_AMENDMENT_BYTES


class ProjectConfigError(Exception):
    """A strict project-owned configuration block is malformed."""


def project_config_path(repo_root: Path) -> Path:
    """Path to ``.plan-tool/config.json`` under ``repo_root``."""
    return (repo_root / PROJECT_CONFIG_SUBPATH).resolve()


def user_config_path() -> Path:
    """Path to ``~/.plan-tool/config.json``.

    ``Path.home()`` is evaluated **in-body**, never captured at import:
    the test suite patches ``Path.home()`` and ``$HOME`` per test, so a
    module-level capture would freeze the real home and break hermetic
    user-level tests. Mirrors :func:`plan_tool.lessons.general_lessons_dir`.
    """
    return Path.home() / ".plan-tool" / "config.json"


def stage_feedback_limits(repo_root: Path) -> StageFeedbackLimits:
    """Resolve strict stage-feedback caps from the project config only."""
    path = project_config_path(repo_root)
    if not path.is_file():
        return StageFeedbackLimits()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectConfigError(
            f"stage feedback configuration in {path} must be valid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise ProjectConfigError(f"stage feedback configuration in {path} must be a JSON object")
    if ROADMAP_FEEDBACK_CONFIG_BLOCK not in payload:
        return StageFeedbackLimits()

    feedback = payload[ROADMAP_FEEDBACK_CONFIG_BLOCK]
    if not isinstance(feedback, dict):
        raise ProjectConfigError(f"{ROADMAP_FEEDBACK_CONFIG_BLOCK} in {path} must be a JSON object")
    if set(feedback) != {STAGE_LIMITS_CONFIG_BLOCK}:
        raise ProjectConfigError(
            f"{ROADMAP_FEEDBACK_CONFIG_BLOCK} in {path} must contain exactly "
            f"{STAGE_LIMITS_CONFIG_BLOCK!r}"
        )
    limits = feedback[STAGE_LIMITS_CONFIG_BLOCK]
    if not isinstance(limits, dict):
        raise ProjectConfigError(
            f"{ROADMAP_FEEDBACK_CONFIG_BLOCK}.{STAGE_LIMITS_CONFIG_BLOCK} in "
            f"{path} must be a JSON object"
        )

    defaults = StageFeedbackLimits()
    allowed = {
        MAX_ACTIVE_FEEDBACK_ITEMS_KEY,
        MAX_RESPONSE_BYTES_KEY,
        MAX_PROSE_AMENDMENT_BYTES_KEY,
    }
    unknown = sorted(set(limits) - allowed)
    if unknown:
        raise ProjectConfigError(
            f"{ROADMAP_FEEDBACK_CONFIG_BLOCK}.{STAGE_LIMITS_CONFIG_BLOCK} in "
            f"{path} has unknown key(s): {', '.join(unknown)}"
        )

    values = {
        key: _strict_stage_limit(
            limits.get(key, default),
            key=key,
            hard_ceiling=default,
            path=path,
        )
        for key, default in (
            (MAX_ACTIVE_FEEDBACK_ITEMS_KEY, defaults.max_active_feedback_items),
            (MAX_RESPONSE_BYTES_KEY, defaults.max_response_bytes),
            (MAX_PROSE_AMENDMENT_BYTES_KEY, defaults.max_prose_amendment_bytes),
        )
    }
    if values[MAX_PROSE_AMENDMENT_BYTES_KEY] > values[MAX_RESPONSE_BYTES_KEY]:
        raise ProjectConfigError(
            f"{MAX_PROSE_AMENDMENT_BYTES_KEY} in {path} must not exceed {MAX_RESPONSE_BYTES_KEY}"
        )
    return StageFeedbackLimits(**values)


def _strict_stage_limit(value: object, *, key: str, hard_ceiling: int, path: Path) -> int:
    """Return one positive integer at or below its immutable hard ceiling."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProjectConfigError(f"{key} in {path} must be a positive JSON integer")
    if not 0 < value <= hard_ceiling:
        raise ProjectConfigError(f"{key} in {path} must be between 1 and {hard_ceiling}")
    return value


def _read_level(path: Path) -> Optional[dict]:
    """Return the ``branch_awareness`` mapping for one config file, or ``None``.

    ``None`` ("level unset") on any malformed shape: file absent,
    ``json.JSONDecodeError``, top-level value not a ``dict``, or
    ``branch_awareness`` missing / not a ``dict``. **Never raises** — one
    broken fallback level must not crash a consumer that only needed a
    lower-priority level, so the sentinel is a legitimate domain value.

    Per-key type validation lives in the accessors, not here: this returns
    the raw block and ``branch_awareness_enabled`` / ``branch_prefixes``
    each validate their own key independently.
    """
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    block = data.get("branch_awareness")
    if not isinstance(block, dict):
        return None
    return block


def branch_awareness_enabled(repo_root: Path) -> bool:
    """Resolve the branch-awareness flag: env → project → user → ``False``.

    First explicitly-set level wins:

    1. Env (``PLAN_TOOL_BRANCH_AWARENESS``): ``.strip().lower()`` matched
       against the truthy/falsy token sets; unrecognized/empty falls
       through ("not set"). Env values are strings, so they need token
       coercion.
    2. Project ``enabled``: used only when ``isinstance(bool)`` — a JSON
       ``"true"`` string or ``1`` int is malformed and falls through. The
       typed field is **not** routed through ``_TRUTHY`` (that would let
       ``"enabled": "yes"`` silently flip behavior).
    3. User ``enabled``: same ``isinstance(bool)`` check.
    4. Default ``False``.
    """
    raw_env = os.environ.get(BRANCH_AWARENESS_ENV)
    if raw_env is not None:
        token = raw_env.strip().lower()
        if token in _TRUTHY:
            return True
        if token in _FALSY:
            return False
        # Unrecognized / empty: fall through to the file levels.

    for block in (
        _read_level(project_config_path(repo_root)),
        _read_level(user_config_path()),
    ):
        if block is not None:
            enabled = block.get("enabled")
            if isinstance(enabled, bool):
                return enabled

    return False


def branch_prefixes(repo_root: Path) -> list[str]:
    """Resolve the branch prefix list: project → user → default (no env axis).

    Takes the first level whose ``branch_awareness.branch_prefixes`` is
    present. Validates the resolved list; on a bad/empty list, warns once
    to stderr (naming the offending file) and returns a fresh copy of
    :data:`DEFAULT_BRANCH_PREFIXES` — never crashes.

    "Bad" = not a ``list``, empty, or any element that is not a non-empty
    ``str`` or fails :func:`_is_valid_branch_prefix`.
    """
    for path in (project_config_path(repo_root), user_config_path()):
        block = _read_level(path)
        if block is None or "branch_prefixes" not in block:
            continue
        raw = block.get("branch_prefixes")
        if _is_valid_prefix_list(raw):
            return list(raw)
        print(
            f"branch_awareness.branch_prefixes in {path} is invalid; "
            f"using {list(DEFAULT_BRANCH_PREFIXES)}",
            file=sys.stderr,
        )
        return list(DEFAULT_BRANCH_PREFIXES)

    return list(DEFAULT_BRANCH_PREFIXES)


REQUIRE_MERGED_PLAN_ENV = "PLAN_TOOL_REQUIRE_MERGED_PLAN"
RUN_CONFIG_BLOCK = "run"
REQUIRE_MERGED_PLAN_KEY = "require_merged_plan"


def _read_run_block(path: Path) -> Optional[dict]:
    """Return the ``run`` mapping for one config file, or ``None``.

    A small reader parallel to :func:`_read_level`, for the same reason
    :func:`_read_smell_block` is. ``None`` on any malformed shape; never raises.
    """
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    block = data.get(RUN_CONFIG_BLOCK)
    if not isinstance(block, dict):
        return None
    return block


def require_merged_plan(repo_root: Path) -> bool:
    """Resolve the pre-run merged-plan check: env → project → user → ``True``.

    ``run.require_merged_plan`` must be a JSON bool at the file levels; any
    other value falls through. On by default: a merged plan is the review
    that precedes ``run`` (docs/how-to/pipeline/run.md).
    """
    raw_env = os.environ.get(REQUIRE_MERGED_PLAN_ENV)
    if raw_env is not None:
        token = raw_env.strip().lower()
        if token in _TRUTHY:
            return True
        if token in _FALSY:
            return False
    for path in (project_config_path(repo_root), user_config_path()):
        block = _read_run_block(path)
        if block is not None and isinstance(block.get(REQUIRE_MERGED_PLAN_KEY), bool):
            return block[REQUIRE_MERGED_PLAN_KEY]
    return True


def _is_valid_prefix_list(raw: object) -> bool:
    """True when ``raw`` is a non-empty list of valid branch prefixes."""
    if not isinstance(raw, list) or not raw:
        return False
    return all(_is_valid_branch_prefix(p) for p in raw)


# Config block + key for the advisory smell checks. The
# ``validation_machinery_paths`` list names the tool's own audit-machinery
# files, against which ``review.detect_self_referential_features`` compares a
# feature's footprint. Repo-structural, not an operator toggle — so, unlike
# ``branch_awareness.enabled``, it gets no ``PLAN_TOOL_*`` env axis.
SMELL_CONFIG_BLOCK = "smell_checks"
VALIDATION_MACHINERY_PATHS_KEY = "validation_machinery_paths"


def _read_smell_block(path: Path) -> Optional[dict]:
    """Return the ``smell_checks`` mapping for one config file, or ``None``.

    A second small reader parallel to :func:`_read_level` (keyed on
    :data:`SMELL_CONFIG_BLOCK`) rather than a shared ``_read_block`` — the
    branch-awareness path is byte-pinned and a behavior-preserving
    consolidation is deferred. ``None`` on any malformed shape; never raises.
    """
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    block = data.get(SMELL_CONFIG_BLOCK)
    if not isinstance(block, dict):
        return None
    return block


def _is_valid_path_list(raw: object) -> bool:
    """True when ``raw`` is a non-empty ``list`` of non-empty ``str``.

    Not :func:`_is_valid_branch_prefix` — that applies git-ref validation
    which wrongly rejects ordinary file paths.
    """
    if not isinstance(raw, list) or not raw:
        return False
    return all(isinstance(p, str) and p for p in raw)


def validation_machinery_paths(repo_root: Path) -> list[str]:
    """Resolve the audit-machinery path set: project → user → ``[]`` (no env).

    Takes the first level whose ``smell_checks.validation_machinery_paths`` is
    present and valid. On a present-but-invalid list, warns once to stderr
    (naming the offending file) and returns ``[]``. Defaults to ``[]`` when
    unconfigured — empty means "no check", so
    :func:`plan_tool.review.detect_self_referential_features` stays inert.
    """
    for path in (project_config_path(repo_root), user_config_path()):
        block = _read_smell_block(path)
        if block is None or VALIDATION_MACHINERY_PATHS_KEY not in block:
            continue
        raw = block.get(VALIDATION_MACHINERY_PATHS_KEY)
        if _is_valid_path_list(raw):
            return list(raw)
        print(
            f"smell_checks.validation_machinery_paths in {path} is invalid; using []",
            file=sys.stderr,
        )
        return []

    return []


def _is_valid_ref(ref: str) -> bool:
    """Pure-Python ``git check-ref-format`` predicate (no shelling out).

    Rejects, per the git rules so every ``<prefix><slug>`` is a valid
    branch: any ASCII control char or space; any of ``~ ^ : ? * [ \\``; a
    ``..`` sequence; an ``@{`` sequence; a trailing ``.lock``; a leading
    or trailing ``/``; and a ``//`` run. Requires at least one ``/`` so a
    degenerate single-component prefix can't yield a single-component ref.
    """
    if not isinstance(ref, str) or not ref:
        return False
    if "/" not in ref:
        return False
    if ref.startswith("/") or ref.endswith("/"):
        return False
    if "//" in ref or ".." in ref or "@{" in ref:
        return False
    if ref.endswith(".lock"):
        return False
    for ch in ref:
        if ord(ch) < 0x20 or ord(ch) == 0x7F or ch == " ":
            return False
        if ch in "~^:?*[\\":
            return False
    return True


def _is_valid_branch_prefix(prefix: object) -> bool:
    """True when ``prefix`` is a non-empty ``str`` yielding a valid ref.

    Proves ``<prefix><slug>`` is a valid ref by probing with a
    representative slug token.
    """
    if not isinstance(prefix, str) or not prefix:
        return False
    return _is_valid_ref(prefix + "probe-slug")


def derive_branch(slug: str, prefixes: Sequence[str]) -> str:
    """Return the single canonical branch name: ``prefixes[0] + slug``.

    Pure: the prefix list is a parameter (callers compute it once via
    :func:`branch_prefixes` and pass it in). Uses the **primary (first)**
    prefix — the name ``create`` and the run guard's "expected branch"
    derive. ``slug`` is trusted as an already-sanitized identifier; this
    concatenates only.
    """
    return prefixes[0] + slug


def convention_names(slug: str, prefixes: Sequence[str]) -> list[str]:
    """Return every conventional branch name: ``[p + slug for p in prefixes]``.

    The full match set used by enforcement/matching so a dev who used a
    secondary prefix is still recognized. Pure; ``slug`` is trusted as
    already-sanitized (concatenation only).
    """
    return [p + slug for p in prefixes]
