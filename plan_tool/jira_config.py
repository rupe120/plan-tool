"""Read / write JIRA configuration for plan-tool.

The config lives at ``docs/implementation-plans/jira-config.json`` (repo-
relative). Today it carries three things:

- **Epics** — each with a short uppercase ``key`` (2-10 letters), a
  human-readable ``name``, an optional real JIRA epic id, and an
  optional free-text description. The ``key`` is the letter pattern
  prefixed to story pseudo-ids in :mod:`plan_tool.jira` output
  (``AUTH-S1``, ``AUTH-S2``, ...). ``key`` must differ from the real
  JIRA project key parsed out of *any* epic's ``jira_epic_id`` (its own
  or a sibling's, when set) — reusing it would make plan-tool's own
  pseudo ids indistinguishable from real JIRA issue keys.

- **Plan assignments** — a map from repo-relative plan path to epic
  ``key``. ``jira`` export consults this to look up which epic prefix
  to use for the plan; plans without an assignment fall back to the
  legacy ``S<N>`` shape so the tool still works on unconfigured repos.

- **Plan tags** — a map from repo-relative plan path to a short,
  human-confirmed grouping tag rendered into every story title
  (``[<id>] [<tag>] [<layer>] <title>``) so tickets from the same plan
  stay visually/searchably grouped even when several plans share an
  epic. Resolved/confirmed once by :mod:`plan_tool.cli.jira_cmd`
  (``_resolve_plan_tag_for_plan`` / ``_assign_plan_tag_for_plan``,
  mirroring the epic-assignment flow) and persisted here so subsequent
  runs don't re-derive or re-ask.

All three pieces are intentionally direct-edit-friendly (JSON, sorted keys,
stable indentation) so reviewing a config diff in a PR is cheap. The
``jira config`` CLI subcommand offers an interactive wizard for users
who prefer not to edit directly; the wizard rewrites this same file.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Optional

from plan_tool.fileio import atomic_write_text


_EPIC_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")

# A real JIRA issue key: ``<PROJECT_KEY>-<NUMBER>`` (``PROJ-1234``). Used only
# to pull the project prefix out of ``jira_epic_id`` for the distinctness
# check below — lenient on purpose, since ``jira_epic_id`` is free-text
# input and an unparseable value should never itself be a validation error.
# ``re.ASCII`` keeps ``\d`` to plain ``0-9`` — a real JIRA id never carries
# a non-ASCII decimal digit, and without it a look-alike (full-width,
# Arabic-Indic, ...) would parse as one.
_JIRA_ISSUE_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]*)-\d+$", re.ASCII)

# Loose on case (a directly edited tag might be lowercase) but tight on length
# and characters — this renders straight into a title-line bracket, so a
# stray ``]`` or newline would corrupt it, and the whole point is "short".
_PLAN_TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,23}$")

DEFAULT_CONFIG_SUBPATH = Path("docs") / "implementation-plans" / "jira-config.json"


class JiraConfigError(Exception):
    """Raised when the config file is malformed or contains invalid entries.

    Surfaced verbatim by the CLI — message text is the user-facing
    diagnostic. Examples: invalid epic key shape, duplicate keys,
    assignment pointing at an unknown key, non-string fields, malformed
    JSON.
    """


@dataclass(frozen=True)
class Epic:
    """One epic record in the config.

    ``key`` is the short uppercase letter pattern prefixed to story
    pseudo-ids (``AUTH``, ``PAY``, ``PLAT``) — it must differ from any
    epic's real JIRA project key (see ``jira_epic_id`` below), enforced
    by :func:`validate_epic_key_distinct_from_jira_projects`.
    ``jira_epic_id`` is the optional real JIRA epic id (``PROJ-1234``)
    the stories will roll up to — recorded here so the export can
    include it for paste-time convenience. ``description`` is free-text
    context an author writes for themselves; the tool never parses it.
    """

    key: str
    name: str
    jira_epic_id: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> dict[str, str]:
        out: dict[str, str] = {"key": self.key, "name": self.name}
        if self.jira_epic_id:
            out["jira_epic_id"] = self.jira_epic_id
        if self.description:
            out["description"] = self.description
        return out


@dataclass
class JiraConfig:
    """Parsed representation of the config file.

    ``epics`` is kept as a list (preserves author-defined order in the
    file). ``plan_assignments`` maps repo-relative plan path string to
    epic ``key``, and ``plan_tags`` maps the same repo-relative plan path
    string to a short, human-confirmed grouping tag — both use strings
    (not :class:`Path`) so equality comparisons are platform-independent
    and the JSON round-trip stays lossless. The two maps are independent
    (a plan can have one, both, or neither).
    """

    epics: list[Epic] = field(default_factory=list)
    plan_assignments: dict[str, str] = field(default_factory=dict)
    plan_tags: dict[str, str] = field(default_factory=dict)

    def epic_by_key(self, key: str) -> Optional[Epic]:
        """Return the epic with ``key`` (case-insensitive lookup), or ``None``."""
        upper = key.upper()
        for e in self.epics:
            if e.key == upper:
                return e
        return None

    def epic_for_plan(self, plan_rel_path: str) -> Optional[Epic]:
        """Resolve the epic assigned to ``plan_rel_path`` (repo-relative)."""
        key = self.plan_assignments.get(plan_rel_path)
        if not key:
            return None
        return self.epic_by_key(key)

    def tag_for_plan(self, plan_rel_path: str) -> Optional[str]:
        """Resolve the confirmed jira tag for ``plan_rel_path`` (repo-relative).

        ``None`` means "not yet confirmed" — distinct from an empty
        string, which :meth:`load_jira_config` never produces (an empty
        tag fails :func:`validate_plan_tag` on load).
        """
        return self.plan_tags.get(plan_rel_path) or None


def default_config_path(repo_root: Path) -> Path:
    """Path to the conventional config file under ``repo_root``."""
    return (repo_root / DEFAULT_CONFIG_SUBPATH).resolve()


def validate_epic_key(key: str) -> None:
    """Raise :class:`JiraConfigError` when ``key`` is not a valid epic key.

    Rules: 2-10 chars, starts with an uppercase letter, remaining chars
    are uppercase letters or digits. Tight on purpose — these become
    story-id prefixes, so a typo'd or whitespace-laden key would
    silently produce malformed ids.
    """
    if not isinstance(key, str) or not _EPIC_KEY_RE.fullmatch(key):
        raise JiraConfigError(
            f"invalid epic key {key!r}: must match {_EPIC_KEY_RE.pattern} "
            "(2-10 chars, uppercase letter first, then uppercase letters / digits)"
        )


def jira_project_key(jira_epic_id: Optional[str]) -> Optional[str]:
    """Return the project-key prefix of a real JIRA id (``"PROJ-1234"`` →
    ``"PROJ"``), or ``None`` when ``jira_epic_id`` is unset/empty or
    doesn't parse as ``<KEY>-<NUMBER>``. A non-matching value is left to
    render as-is elsewhere; it is not itself a shape error.
    """
    if not jira_epic_id:
        return None
    m = _JIRA_ISSUE_KEY_RE.fullmatch(jira_epic_id.strip())
    return m.group(1).upper() if m else None


def jira_project_keys_in_use(epics: Iterable[Epic]) -> dict[str, str]:
    """Map every real JIRA project key parsed out of ``epics``' own
    ``jira_epic_id`` values to the ``jira_epic_id`` it came from (first
    one seen, when two epics happen to share a project).
    """
    in_use: dict[str, str] = {}
    for e in epics:
        project_key = jira_project_key(e.jira_epic_id)
        if project_key is not None and project_key not in in_use:
            assert e.jira_epic_id is not None  # jira_project_key requires it
            in_use[project_key] = e.jira_epic_id
    return in_use


def validate_epic_key_distinct_from_jira_projects(
    key: str, project_keys_in_use: Mapping[str, str]
) -> None:
    """Raise :class:`JiraConfigError` when ``key`` matches a real JIRA
    project key in ``project_keys_in_use`` (see
    :func:`jira_project_keys_in_use`). See JIRA_FORMAT.md's "Epic" entry
    for why. ``key`` need not be pre-uppercased — the message always
    renders the uppercased form.
    """
    upper = key.upper()
    source = project_keys_in_use.get(upper)
    if source is not None:
        raise JiraConfigError(
            f"epic key {key!r} matches the real JIRA project key "
            f"{upper!r} parsed from jira_epic_id {source!r} — "
            f"plan-tool's own {upper}-S<N> pseudo ids would then look "
            f"identical to real {upper}-<N> JIRA issue keys. Pick a "
            "different epic key."
        )


def validate_new_epic_key_distinct_from_jira_projects(
    key: str, jira_epic_id: Optional[str], other_epics: Iterable[Epic]
) -> None:
    """Raise :class:`JiraConfigError` when a candidate ``(key, jira_epic_id)``
    pair — not yet a full :class:`Epic`, checked against the rest of the
    config's ``other_epics`` — would collide with any epic once persisted
    (self checked first, then both directions against siblings: candidate
    key vs. a sibling's project, and candidate project vs. a sibling's
    key). See JIRA_FORMAT.md's "Epic" entry for why. Reused by
    :func:`load_jira_config` (one epic vs. the rest, per epic) and by
    every epic-creation/edit path in the CLI.
    """
    others = list(other_epics)
    own_project_key = jira_project_key(jira_epic_id)
    if own_project_key is not None:
        validate_epic_key_distinct_from_jira_projects(
            key, {own_project_key: jira_epic_id}
        )
    validate_epic_key_distinct_from_jira_projects(
        key, jira_project_keys_in_use(others)
    )
    if own_project_key is not None:
        colliding = next(
            (s for s in others if s.key.upper() == own_project_key), None
        )
        if colliding is not None:
            raise JiraConfigError(
                f"jira_epic_id {jira_epic_id!r} (real JIRA project "
                f"{own_project_key!r}) matches existing epic key "
                f"{colliding.key!r} — plan-tool's own {colliding.key}-S<N> "
                f"pseudo ids would then look identical to real "
                f"{own_project_key}-<N> JIRA issue keys. Pick a different "
                f"real JIRA epic id, or rename epic {colliding.key!r}."
            )


def epic_key_collision_warnings(epics: Iterable[Epic]) -> list[str]:
    """Return one human-readable line per epic whose key collides with a
    real JIRA project key in use (its own or a sibling's) — non-raising,
    for a caller (``jira config --show``) that must display a config
    :func:`load_jira_config` was asked to tolerate loading despite the
    collision (``enforce_key_distinct_from_jira_project=False``).
    """
    epics = list(epics)
    warnings: list[str] = []
    for e in epics:
        others = [x for x in epics if x is not e]
        try:
            validate_new_epic_key_distinct_from_jira_projects(
                e.key, e.jira_epic_id, others
            )
        except JiraConfigError as exc:
            warnings.append(str(exc))
    return warnings


def validate_plan_tag(tag: str) -> None:
    """Raise :class:`JiraConfigError` when ``tag`` is not a valid plan tag.

    Rules: 1-24 chars, letters/digits/``-``/``_`` only, alphanumeric
    first. Tight on characters (renders straight into a title-line
    bracket — a stray ``]`` or newline would corrupt it) and on length
    (the whole point of the tag is to be short).
    """
    if not isinstance(tag, str) or not _PLAN_TAG_RE.fullmatch(tag):
        raise JiraConfigError(
            f"invalid plan tag {tag!r}: must match {_PLAN_TAG_RE.pattern} "
            "(1-24 chars, letters/digits/-/_ only, alphanumeric first)"
        )


def load_jira_config(
    repo_root: Path,
    *,
    path: Optional[Path] = None,
    enforce_key_distinct_from_jira_project: bool = True,
) -> JiraConfig:
    """Read the config file under ``repo_root`` and parse it.

    Returns an empty :class:`JiraConfig` when the file doesn't exist —
    that's the legitimate "unconfigured repo" state. Raises
    :class:`JiraConfigError` when the file exists but is malformed,
    so the user sees a clear diagnostic rather than the tool silently
    falling back to defaults.

    Validation enforced on load:

    - Top-level value is a JSON object.
    - ``epics`` (when present) is a list of objects with valid ``key``
      and ``name`` strings; keys are unique across the list.
    - ``plan_assignments`` (when present) is a string-to-string map and
      every value references a defined epic key.
    - ``plan_tags`` (when present) is a string-to-string map and every
      value passes :func:`validate_plan_tag`.
    - Every epic ``key`` is distinct from every epic's real JIRA project
      key (see :func:`validate_new_epic_key_distinct_from_jira_projects`)
      — unless ``enforce_key_distinct_from_jira_project`` is ``False``.
      Pass ``False`` only to load a config that may already violate this
      rule so it can be inspected/fixed (``plan-tool jira config`` does
      this so a config broken by this rule can still open the wizard
      that repairs it); every other rule above still applies either way.
    """
    mf = path or default_config_path(repo_root)
    if not mf.is_file():
        return JiraConfig()

    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise JiraConfigError(f"invalid JSON in {mf}: {exc}") from exc
    if not isinstance(data, dict):
        raise JiraConfigError(
            f"{mf} top-level must be a JSON object, got {type(data).__name__}"
        )

    epics: list[Epic] = []
    seen_keys: set[str] = set()
    raw_epics = data.get("epics", [])
    if not isinstance(raw_epics, list):
        raise JiraConfigError(
            f'"epics" in {mf} must be a list, got {type(raw_epics).__name__}'
        )
    for i, item in enumerate(raw_epics):
        if not isinstance(item, dict):
            raise JiraConfigError(
                f"epics[{i}] in {mf} must be a JSON object"
            )
        key = item.get("key")
        validate_epic_key(key)  # raises JiraConfigError on bad shape
        if key in seen_keys:
            raise JiraConfigError(
                f"epics[{i}] in {mf}: duplicate epic key {key!r}"
            )
        seen_keys.add(key)
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise JiraConfigError(
                f"epics[{i}] in {mf}: 'name' must be a non-empty string"
            )
        jira_epic_id = item.get("jira_epic_id")
        if jira_epic_id is not None and not isinstance(jira_epic_id, str):
            raise JiraConfigError(
                f"epics[{i}] in {mf}: 'jira_epic_id' must be a string when set"
            )
        description = item.get("description")
        if description is not None and not isinstance(description, str):
            raise JiraConfigError(
                f"epics[{i}] in {mf}: 'description' must be a string when set"
            )
        epics.append(
            Epic(
                key=key,
                name=name.strip(),
                jira_epic_id=jira_epic_id.strip() if jira_epic_id else None,
                description=description.strip() if description else None,
            )
        )

    # Checked once the full list is known — a collision can come from an
    # epic's own jira_epic_id or a sibling's, so no per-item pass in the
    # loop above can see it. Delegates to the same per-epic-vs-the-rest
    # check the CLI uses for one new/edited epic, so the two surfaces
    # can't drift into judging the same collision differently.
    if enforce_key_distinct_from_jira_project:
        for i, e in enumerate(epics):
            others = [x for x in epics if x is not e]
            try:
                validate_new_epic_key_distinct_from_jira_projects(
                    e.key, e.jira_epic_id, others
                )
            except JiraConfigError as exc:
                raise JiraConfigError(
                    f"epics[{i}] in {mf}: {exc} Run `plan-tool jira config` "
                    "to repair this config."
                ) from exc

    raw_assignments = data.get("plan_assignments", {})
    if not isinstance(raw_assignments, dict):
        raise JiraConfigError(
            f'"plan_assignments" in {mf} must be a JSON object, '
            f"got {type(raw_assignments).__name__}"
        )
    assignments: dict[str, str] = {}
    for plan_path, epic_key in raw_assignments.items():
        if not isinstance(plan_path, str) or not plan_path.strip():
            raise JiraConfigError(
                f"plan_assignments key {plan_path!r} in {mf}: must be a "
                "non-empty string (repo-relative plan path)"
            )
        if not isinstance(epic_key, str):
            raise JiraConfigError(
                f"plan_assignments[{plan_path!r}] in {mf}: value must be a string"
            )
        upper = epic_key.upper()
        if upper not in seen_keys:
            raise JiraConfigError(
                f"plan_assignments[{plan_path!r}] in {mf}: references "
                f"unknown epic key {epic_key!r} (defined keys: "
                f"{sorted(seen_keys) or 'none'})"
            )
        assignments[plan_path.strip()] = upper

    raw_tags = data.get("plan_tags", {})
    if not isinstance(raw_tags, dict):
        raise JiraConfigError(
            f'"plan_tags" in {mf} must be a JSON object, '
            f"got {type(raw_tags).__name__}"
        )
    tags: dict[str, str] = {}
    for plan_path, tag in raw_tags.items():
        if not isinstance(plan_path, str) or not plan_path.strip():
            raise JiraConfigError(
                f"plan_tags key {plan_path!r} in {mf}: must be a "
                "non-empty string (repo-relative plan path)"
            )
        validate_plan_tag(tag)  # raises JiraConfigError on bad shape
        tags[plan_path.strip()] = tag

    return JiraConfig(epics=epics, plan_assignments=assignments, plan_tags=tags)


def write_jira_config(config: JiraConfig, path: Path) -> None:
    """Serialize ``config`` to ``path`` with stable formatting.

    Always emits an object with ``epics``, ``plan_assignments``, and
    ``plan_tags`` keys (even when empty) so diffs against a fresh init
    don't churn on appearing-keys. Assignments/tags are sorted by plan
    path for stable serialization; epic order is preserved as authored.
    """
    payload = {
        "epics": [e.to_dict() for e in config.epics],
        "plan_assignments": {
            k: config.plan_assignments[k]
            for k in sorted(config.plan_assignments)
        },
        "plan_tags": {
            k: config.plan_tags[k] for k in sorted(config.plan_tags)
        },
    }
    atomic_write_text(path, json.dumps(payload, indent=2) + "\n")


def plan_rel_path(plan_path: Path, repo_root: Path) -> Optional[str]:
    """Return ``plan_path`` expressed relative to ``repo_root`` as a posix string.

    Returns ``None`` when ``plan_path`` doesn't live under ``repo_root``
    — the caller treats that as "unassignable" (no config entry can
    refer to it). Posix forward slashes ensure the same assignment
    works regardless of which OS authored the config.
    """
    try:
        rel = plan_path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return None
    return rel.as_posix()
