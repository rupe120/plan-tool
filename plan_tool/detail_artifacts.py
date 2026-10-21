"""Shared detail-artifact path resolution leaf.

One module owns "where is this step's detail file?": canonical path
derivation (``derive_detail_path`` and its slug helpers) plus the
pointer-vs-canonical resolution (``resolve_detail_artifact``) that
``fingerprint``, ``review``, and ``scope_out`` previously reimplemented
behind call-time lazy imports of ``plan_tool.detail``. Both detail grades derive here —
``derive_jira_detail_path`` sits beside the run-grade derivation so the
collision rules between them are stated in one place. The module also owns
the run-grade detail format-version reader gate and its raw-upgrade entry
point.

Deliberately a **leaf**: imports only the stdlib, ``plan_tool.schema``,
and ``plan_tool.locator`` — never ``plan_tool.detail`` / ``review`` /
``fingerprint`` — so consumers can import it at module load without
closing the ``detail`` → ``review`` cycle. ``plan_tool.detail``
re-exports the moved names unchanged.

The resolver returns **states, not a fallback path**: each consumer keeps
its own — deliberately different — missing-file policy (fingerprint omits
the key, review classifies bare, scope-out treats a set-but-missing
pointer as a lost body with no canonical fallback). A resolver that baked
in one fallback policy would erase the set-but-missing vs never-detailed
distinction those policies depend on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from plan_tool.locator import slug_from_filename
from plan_tool.schema import Plan, Step

# Words that don't carry meaning in a step-title slug. Tighter than
# ``review._TITLE_STOPWORDS`` because slug derivation needs to keep verbs
# like "wire" and "build" that the symbol heuristic intentionally drops.
# Add to this list only when a token shows up in real step titles and
# adds nothing to the slug.
_SLUG_STOPWORDS = frozenset(
    {
        "a", "add", "an", "and", "as", "at", "be", "by",
        "do", "for", "from", "if", "in", "into", "is", "it",
        "now", "of", "onto", "or", "the", "to",
        "via", "with",
    }
)

# Slug fallback when every token is dropped (empty title, all stopwords,
# all single-character tokens). Path components must be non-empty, so
# we always have something to join.
_SLUG_FALLBACK = "step"

# Maximum slug length in bytes. Filesystems cap a path component at
# 255 bytes (NAME_MAX), but the practical concern is readability: long
# restated-paragraph titles produced filenames that humans had to rename
# directly. Cap aggressively and let word-boundary truncation keep the
# leading tokens, which carry the gist of the step.
_MAX_SLUG_LEN = 40


def derive_step_slug(title: str) -> str:
    """Reduce a step title to a kebab-case slug suitable for a filename.

    Pulls ``[A-Za-z0-9]+`` tokens from the title, lowercases them, drops
    single-character tokens and ``_SLUG_STOPWORDS``, and joins with ``-``.
    Returns ``_SLUG_FALLBACK`` (``"step"``) if the result would be empty,
    so the path is always well-formed.

    Caps the result at ``_MAX_SLUG_LEN`` characters, truncating on the
    last ``-`` boundary inside the budget so words aren't split. Steps
    with restated-paragraph titles would otherwise blow past the
    filesystem's per-component byte limit (NAME_MAX = 255 on macOS /
    Linux) and write would fail with ``Errno 63``.
    """
    tokens = re.findall(r"[A-Za-z0-9]+", title)
    out: list[str] = []
    for tok in tokens:
        lo = tok.lower()
        if len(lo) < 2:
            continue
        if lo in _SLUG_STOPWORDS:
            continue
        out.append(lo)
    if not out:
        return _SLUG_FALLBACK
    slug = "-".join(out)
    if len(slug) <= _MAX_SLUG_LEN:
        return slug
    # Truncate on the last ``-`` inside the budget so we don't cut a word
    # in half. Falls back to a hard slice if there's no ``-`` in range
    # (a single token longer than the budget — pathological, but cheap
    # to handle).
    truncated = slug[:_MAX_SLUG_LEN]
    last_dash = truncated.rfind("-")
    if last_dash > 0:
        truncated = truncated[:last_dash]
    return truncated


def _plan_slug(plan_path: Path) -> str:
    """Strip a leading ``<digit>-`` from the plan filename's stem.

    Mirrors ``PlanEntry.slug`` so the conventional path stays consistent
    with how plans are named on disk (and how ``status``/``run`` resolve
    them).
    """
    result = slug_from_filename(plan_path)
    assert result is not None  # default_to_stem=True guarantees non-None
    return result


def derive_detail_path(plan_path: Path, plan: Plan, step: Step) -> Path:
    """Compute the conventional output path for a step's detail file.

    Format:

        <plan_path.parent>/plan-details/<plan_slug>/<NN>-<step_slug>.md

    ``plan_slug`` strips a leading ``<digit>-`` from ``plan_path.stem``
    (mirrors :class:`PlanEntry.slug`). ``NN`` is the zero-padded step id.

    The plan parameter is accepted for API symmetry with future helpers
    that might need plan-level context (e.g. ``plan.lessons``); today the
    function only uses ``plan_path`` and ``step``.
    """
    _ = plan  # accepted for API symmetry; unused today
    plan_dir = plan_path.parent
    plan_slug = _plan_slug(plan_path)
    step_slug = derive_step_slug(step.title)
    filename = f"{step.id:02d}-{step_slug}.md"
    return plan_dir / "plan-details" / plan_slug / filename


# Subdirectory holding the plan's jira-grade detail artifacts. A
# subdirectory rather than a suffixed sibling: ``detail._archive_orphan_details``
# globs ``{NN}-*.md`` non-recursively, so a same-directory jira artifact would
# be archived as an orphan every time the run-grade file for that step is
# re-authored. Nesting puts it outside that glob, outside
# :func:`find_unreferenced_detail_for_step`'s exact-name adoption, and outside
# split migration (which walks ``Step.detail`` pointers).
_JIRA_GRADE_DIRNAME = "jira"


def derive_jira_detail_path(plan_path: Path, plan: Plan, step: Step) -> Path:
    """Compute the conventional output path for a step's **jira-grade**
    detail file.

    Format:

        <plan_path.parent>/plan-details/<plan_slug>/jira/<NN>-<step_slug>.md

    Same id and slug derivation as :func:`derive_detail_path` — only the
    directory differs, so the two grades can never resolve to one path.

    There is no pointer axis: ``Step.detail`` stays run-grade-only and no
    frontmatter field points at a jira artifact, so resolution is this
    derivation plus an ``is_file()`` check. Missing-file policy belongs to
    the consumer, as it does for the run-grade resolver.
    """
    run_grade = derive_detail_path(plan_path, plan, step)
    return run_grade.parent / _JIRA_GRADE_DIRNAME / run_grade.name


def find_unreferenced_detail_for_step(
    plan_path: Path, plan: Plan, step: Step
) -> Optional[Path]:
    """Return ``step``'s **canonical** detail file when it is present on
    disk, so it can be *adopted* (the ``detail:`` pointer reattached)
    instead of re-authored through Claude and clobbered.

    The failure mode this repairs: a step split renumbers steps whose
    ``detail`` pointer was already ``None`` —
    ``detail._migrate_downstream_details_after_split`` only renames/repoints
    steps whose pointer is already *set*, so a split over a never-pointed
    plan strands the on-disk file with no frontmatter reference. The regen
    gate then treats ``step.detail is None`` as "needs authoring" and
    overwrites it.

    Restricted to the canonical name (:func:`derive_detail_path`) on
    purpose. A sibling under the same ``<NN>-`` id prefix but a *different*
    slug is a superseded orphan the authoring path deliberately re-authors
    and archives (``detail._archive_orphan_details``); a stale split prefix
    is indistinguishable from a legitimately-superseded slug there, so only
    an exact-name match is auto-adopted. The prefix-orphan case is left for
    ``validate`` to surface, not silently bound.
    """
    canonical = derive_detail_path(plan_path, plan, step)
    return canonical if canonical.is_file() else None


@dataclass(frozen=True)
class DetailArtifactResolution:
    """Where a step's detail file *would* be, and whether it's there.

    Three facts, from which every consumer's policy is derivable:

    - ``pointer_set`` — ``step.detail`` is set (the pointer is
      authoritative; consumers never fall back to canonical from a
      set-but-missing pointer).
    - ``path`` — the pointer path (``repo_root / step.detail``) when set,
      else the canonical :func:`derive_detail_path`.
    - ``on_disk`` — ``path.is_file()`` at resolution time.
    """

    pointer_set: bool
    path: Path
    on_disk: bool


def resolve_detail_artifact(
    plan_path: Path, plan: Plan, step: Step, repo_root: Path
) -> DetailArtifactResolution:
    """Resolve a step's detail file: pointer first, canonical second.

    Reports state only — no fallback policy, no reading, no writing; one
    ``is_file()`` check. Each consumer maps the states to its own
    missing-file semantics (see the module docstring).
    """
    if step.detail:
        path = repo_root / step.detail
    else:
        path = derive_detail_path(plan_path, plan, step)
    return DetailArtifactResolution(
        pointer_set=bool(step.detail), path=path, on_disk=path.is_file()
    )


# --------------------------------------------------------------------------
# Run-grade detail format-version contract
# --------------------------------------------------------------------------
#
# Fixed in-band carrier for pure-Markdown run-grade details.
# See DETAIL_FORMAT.md's "Format version marker" contract.

DETAIL_FORMAT_VERSION = 1
SUPPORTED_DETAIL_FORMAT_VERSIONS = frozenset({DETAIL_FORMAT_VERSION})

# Declaration-free legacy details remain version 1 after current advances.
_LEGACY_DETAIL_FORMAT_VERSION = 1

# Exactly one leading ``#`` followed by whitespace and content — excludes an
# H2+ heading (whose second character is ``#``, not whitespace) and an
# indented heading (whose first character isn't ``#``).
_H1_RE = re.compile(r"^#[ \t]+\S")

# The fixed marker's grammar. Matching this at all (regardless of the
# captured value's shape) is what makes a slot line an *attempted*
# declaration rather than ordinary prose or an unrelated comment.
_DETAIL_FORMAT_VERSION_MARKER_RE = re.compile(
    r"^<!--\s*plan-tool:detail-format-version:\s*(?P<value>.*?)\s*-->\s*$"
)

# A bare (optionally signed) ASCII decimal integer literal — the only payload
# shape this build accepts. Anything else in a matched marker slot is
# malformed, not absent, and refuses rather than defaulting.
_INTEGER_LITERAL_RE = re.compile(r"^-?[0-9]+$")


class DetailFormatError(Exception):
    """A run-grade detail body declares an unsupported or malformed format
    version at its fixed post-H1 marker slot, or has no valid carrier H1 in
    which to declare one."""

    def __init__(self, message: str, *, path: Optional[Path] = None) -> None:
        super().__init__(message)
        self.path = path


def render_detail_format_version_marker(version: int = DETAIL_FORMAT_VERSION) -> str:
    """The exact carrier line a run-grade detail writer stamps."""
    return f"<!-- plan-tool:detail-format-version: {version} -->"


def locate_detail_format_carrier(text: str) -> Optional[tuple[int, int]]:
    """Return the valid leading H1 and fixed marker-slot line indexes.

    Returns ``None`` without a carrier; see ``DETAIL_FORMAT.md``.
    """
    lines = text.splitlines()
    h1_idx: Optional[int] = None
    for i, line in enumerate(lines):
        if line.strip() == "":
            continue
        if _H1_RE.match(line):
            h1_idx = i
        break
    if h1_idx is None:
        return None
    slot_idx = h1_idx + 1
    while slot_idx < len(lines) and lines[slot_idx].strip() == "":
        slot_idx += 1
    return (h1_idx, slot_idx)


def _location_suffix(path: Optional[Path]) -> str:
    return f" ({path})" if path is not None else ""


def require_supported_detail_format_version(
    text: str, *, path: Optional[Path] = None
) -> None:
    """Refuse an unsupported or malformed fixed-slot declaration.

    See ``DETAIL_FORMAT.md``; callers pass text already read from disk.
    """
    location = _location_suffix(path)
    raw_value: Optional[str] = None
    carrier = locate_detail_format_carrier(text)
    if carrier is not None:
        _h1_idx, slot_idx = carrier
        lines = text.splitlines()
        if slot_idx < len(lines):
            match = _DETAIL_FORMAT_VERSION_MARKER_RE.match(lines[slot_idx])
            if match:
                raw_value = match.group("value")

    if raw_value is None:
        declared = _LEGACY_DETAIL_FORMAT_VERSION
    elif _INTEGER_LITERAL_RE.match(raw_value):
        try:
            declared = int(raw_value)
        except ValueError:
            # Python limits decimal conversion length; preserve the format
            # contract instead of leaking that implementation exception.
            raise DetailFormatError(
                f"detail file{location} declares detail-format-version="
                f"{raw_value!r}, which is not a valid integer (supported: "
                f"{sorted(SUPPORTED_DETAIL_FORMAT_VERSIONS)})",
                path=path,
            ) from None
    else:
        raise DetailFormatError(
            f"detail file{location} declares detail-format-version="
            f"{raw_value!r}, which is not a valid integer (supported: "
            f"{sorted(SUPPORTED_DETAIL_FORMAT_VERSIONS)})",
            path=path,
        )

    if declared not in SUPPORTED_DETAIL_FORMAT_VERSIONS:
        raise DetailFormatError(
            f"detail file{location} declares detail-format-version="
            f"{declared!r}, which this build does not support (supported: "
            f"{sorted(SUPPORTED_DETAIL_FORMAT_VERSIONS)})",
            path=path,
        )


def strip_detail_format_version_marker(text: str) -> str:
    """Remove only a marker occupying the fixed post-H1 slot."""
    carrier = locate_detail_format_carrier(text)
    if carrier is None:
        return text
    _h1_idx, slot_idx = carrier
    lines = text.splitlines(keepends=True)
    if (
        slot_idx < len(lines)
        and _DETAIL_FORMAT_VERSION_MARKER_RE.match(lines[slot_idx])
    ):
        del lines[slot_idx]
        return "".join(lines)
    return text


def _line_terminator(line: str) -> str:
    """Return ``line``'s trailing newline sequence, or ``""`` when it has none."""
    for terminator in (
        "\r\n", "\n", "\r", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85",
        "\u2028", "\u2029",
    ):
        if line.endswith(terminator):
            return terminator
    return ""


def upgrade_detail_body_to_current(text: str) -> str:
    """Upgrade a raw valid-carrier detail body; refuse malformed or unsupported states."""
    require_supported_detail_format_version(text)

    carrier = locate_detail_format_carrier(text)
    if carrier is None:
        raise DetailFormatError(
            "detail body has no valid carrier H1 (a column-0 '#' heading as "
            "the document's first non-blank line), so there is no slot to "
            "declare a format version in; re-author this detail instead of "
            "attempting a raw upgrade"
        )

    h1_idx, slot_idx = carrier
    lines = text.splitlines()
    raw_value: Optional[str] = None
    if slot_idx < len(lines):
        match = _DETAIL_FORMAT_VERSION_MARKER_RE.match(lines[slot_idx])
        if match:
            raw_value = match.group("value")

    if raw_value is None:
        keepends_lines = text.splitlines(keepends=True)
        h1_line = keepends_lines[h1_idx]
        terminator = _line_terminator(h1_line) or "\n"
        if not _line_terminator(h1_line):
            keepends_lines[h1_idx] = h1_line + terminator
        keepends_lines.insert(
            h1_idx + 1, f"{render_detail_format_version_marker()}{terminator}"
        )
        return "".join(keepends_lines)

    declared = int(raw_value)
    if declared == DETAIL_FORMAT_VERSION:
        return text
    raise NotImplementedError(
        f"no upgrade path is declared for detail format_version={declared!r}; "
        "add one before adding it to SUPPORTED_DETAIL_FORMAT_VERSIONS"
    )
