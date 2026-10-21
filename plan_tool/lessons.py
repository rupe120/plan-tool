"""Accumulated lessons learned, fed back into create / detail / review prompts.

Two files live at deliberately different locations:

- **general.md** lives *per user* at ``~/.plan-tool/lessons/general.md``
  (``$HOME`` resolved at call time so test harnesses that redirect HOME
  keep working). It holds generalizable plan-authoring rules — not
  specific to any one project's domain. Examples: "verify file paths
  against the repo before proposing them", "detail-time grep finds
  partial implementations the heuristic misses". These accumulate across
  every plan-tool invocation by this user, in any repo.
- **project.md** lives *per repo* at
  ``<repo_root>/.plan-tool/lessons/project.md``. It holds domain
  knowledge specific to *this* codebase. Examples: "AppSync
  subscriptions only fire on mutations routed through AppSync
  resolvers; direct DynamoDB writes bypass subscribers." These stay
  with the repo.

Both files are append-only with case-insensitive substring dedupe — a new
entry whose ``rule`` text already appears verbatim (or as a substring) in
the file is silently dropped. Lessons accumulate across runs; pruning uses a
direct edit (these files are checked in and intentionally directly editable).

Before capture, a deterministic scope gate routes a purported general lesson to
the project store when it names a path that resolves inside this repository (or
any absolute path). This keeps one model's bucket choice from leaking domain
facts into every other project's authoring prompt. It gates on *resolution*,
never on how an identifier looks — a bare domain symbol is deliberately not
routed, because no observable separates it from a portable proper noun.

**Reading is always on; writing is opt-in.** Every lesson-consuming
prompt injects these files, but the capture side (``detail`` / the
review lane's ``extract_lessons``) is off by default — it costs a
second claude call per step/review — and is enabled with
``plan-tool detail --lessons`` / ``plan-tool reconcile-plan --lessons``.

The ``append_lessons`` write path also offers two opt-in equivalence
knobs: ``strict_check`` runs ``find_lesson_equivalences`` against the
surviving candidates before writing, refusing entries a claude judge
flags as semantic duplicates or conflicts; ``warn_check`` runs the same
primitive but writes every survivor anyway, recording the findings for
later audit. Both default off, so the warn-and-continue behavior used by
``detail.py`` and ``review.py`` is unchanged on upgrade. Every finding
produced by either ``strict_check`` or ``warn_check`` is also appended to
``<repo>/.plan-tool/lessons-warnings.jsonl`` (gitignored runtime state,
rolling-cap trimmed) so the ``lessons consolidate`` handler can rank
repeat findings ahead of one-offs.

Each appended bullet also writes one record to a sibling JSONL sidecar
(``general-citations.jsonl`` / ``project-citations.jsonl``) carrying
the ``added`` date and ``source`` tag. The bullet stays dense for
prompt-injection at read time; the sidecar carries the audit trail.
Sidecar writes are best-effort — a failed sidecar write does not roll
back the bullet write.

Bullets carry two optional metadata fields — ``surface`` (one of
``LESSON_SURFACES``) and ``trigger`` (free-form "when X" predicate) —
populated by the two ``extract-lessons-*`` prompts. The ``surface``
tag renders inline as a backtick-bracketed prefix (e.g.
``[create-heuristic]``) so a hand-grep already filters by surface.
A future loader refactor will use these tags to slice injection by
the running command.

The module is intentionally narrow: dataclasses, load, render, append,
plus a claude-backed equivalence primitive (``find_lesson_equivalences``)
used by the ``lessons consolidate`` CLI and the opt-in ``strict_check``
path of ``append_lessons``. No CLI surface here — that lives in
``cli.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from string import Template
from typing import Callable, Iterable, Optional

from plan_tool.checkpoint import (
    Checkpoint,
    checkpoint_path,
    compute_input_hash,
    load_if_valid,
    save_checkpoint,
)
from plan_tool.renderer import prompts_dir
from plan_tool.shell import claude_invoke
from plan_tool.style import tool, warn


# General lessons live per-user under ``~/.plan-tool/lessons/`` so the
# portable, plan-authoring rules accumulate across every repo this user
# touches. Project lessons stay per-repo under
# ``<repo>/.plan-tool/lessons/`` because they encode domain knowledge
# that only applies to this codebase.
#
# ``GENERAL_LESSONS_REL`` is anchored at ``Path.home()`` (resolved lazily
# in :func:`general_lessons_dir`); ``PROJECT_LESSONS_REL`` is anchored at
# ``repo_root``.
GENERAL_LESSONS_REL = (".plan-tool", "lessons")
PROJECT_LESSONS_REL = (".plan-tool", "lessons")
GENERAL_FILENAME = "general.md"
PROJECT_FILENAME = "project.md"

# A general lesson may cite *plan-tool's own package* — those rules are about
# driving this tool, which is what the cross-project store is for. Only
# ``plan_tool/`` earns the carve: ``tests/`` and ``docs/`` name directories
# nearly every repository has, so exempting them would wave a consuming repo's
# own project files straight into the global store — the exact leak this gate
# exists to stop. Inside plan-tool a ``tests/``/``docs/`` citation is likewise a
# plan-tool-specific fact and belongs in the project bucket.
_GENERAL_PATH_PREFIXES = ("plan_tool/",)
_BACKTICKED_TOKEN_RE = re.compile(r"`([^`\n]+)`")

# Decided 2026-08-06; do not re-open without new evidence. A CamelCase-symbol
# pass shipped here alongside the path gate and was removed: measured against
# an allowlist of 13 "general vocabulary" tokens, 10 could never match the
# regex that consulted them (``API``/``CLI``/``Plan``/``Claude``/… have no
# second capital), so the effective rule was "any CamelCase token is
# project-scoped" — and it silently demoted ordinary portable prose naming
# ``GitHub``, ``TypeScript``, or ``PlanStatus``. That is CLAUDE.md's
# "measuring vocabulary, not the property"; the governing rule there is that a
# high false-positive rate means kill, not tune. Path resolution stays because
# it is a real observable: the path either resolves in this repo or it does
# not. The known limit is stated in :func:`_entry_has_repo_scoped_identifier`.

# Per-repo append-only audit log of equivalence findings produced by the
# opt-in ``strict_check`` / ``warn_check`` paths of ``append_lessons``.
# Lives next to the other ``.plan-tool/`` runtime-state dirs (``runs``,
# ``checkpoints``, ``reviews``) — same tier, same gitignore coverage — so
# the ``lessons consolidate`` handler can rank repeat findings ahead of
# one-offs. Anchored at ``repo_root`` (not ``Path.home()``): a warning is
# about a specific repo's lessons file, so the log stays with the repo.
WARNINGS_REL = (".plan-tool",)
WARNINGS_FILENAME = "lessons-warnings.jsonl"

# Rolling-record cap for the warning log. ~5000 entries ≈ a few hundred
# KB of JSONL — comfortable for the consolidate reader to load in one
# pass; large enough that a normal week of detail/review iterations
# doesn't trim. Configurable per-call via append_warning(..., max_records=).
DEFAULT_WARNINGS_CAP = 5000

# Subdirectory under the skill's lessons dir that holds *pending* lesson
# files — bullets extracted by ``plan-tool detail`` against a plan whose
# ``files:`` set includes the canonical lessons sink. Quarantining them
# here keeps the distillation pass from corrupting the very file the
# active plan is scrubbing. ``load_lessons`` deliberately does NOT read
# from this directory; pending entries are invisible to the prompt that
# produced them. Promote into the canonical sink through a direct edit (or via a
# future ``plan-tool lessons promote`` command).
PENDING_LESSONS_DIRNAME = "pending"

# Controlled vocabulary for the ``surface`` field on ``LessonEntry``.
#
# A surface tag declares **where a lesson applies during prompt
# injection** — not what the lesson is *about*. The future loader
# (``load_lessons(surfaces=...)``) will use these tags to inject only
# the lessons that match the running command's surface set; today the
# tag renders inline as ``[surface]`` so a hand-grep already filters
# cleanly.
#
# The list is intentionally a **hybrid of command-aligned and content-
# aligned** surfaces, not a 1:1 mirror of plan-tool's subcommand set:
#
#   3 command-aligned surfaces (the only commands that inject lessons
#   today, verified by grep over ``${lessons_block}`` in ``prompts/``):
#     - ``create-heuristic``    → consumed by ``create.py``
#     - ``detail-authoring``    → consumed by ``detail.py`` (covers
#                                 both ``detail.md`` and the
#                                 ``detail-quality.md`` critique pass —
#                                 same artifact, two prompts)
#     - ``review-heuristic``    → consumed by ``review.py``
#
#   2 content-aligned surfaces (cross-cutting clusters observed in the
#   existing corpus that don't fit cleanly under one command):
#     - ``cross-step``    → handoff rules between steps (deferred
#                           bullets, stub-replacement contracts,
#                           frozen-artifact diff invariants). Apply
#                           during both detail (authoring the
#                           consumer step) AND review (checking the
#                           handoff closed). Forcing into one command
#                           would miscategorize.
#     - ``domain-shape``  → step-shape recognition (UI-feature steps,
#                           schema-definition steps, infra-wiring
#                           steps, migration steps, operability
#                           steps). Apply across all three commands
#                           — create uses them to set complexity
#                           floors and propose file skeletons; detail
#                           uses them to mirror conventions; review
#                           uses them to flag shape-vs-content
#                           mismatches.
#
# **Why not enumerate every plan-tool subcommand?** Most subcommands
# (split, reconcile, completeness, jira, run,
# optimize, check, document, lessons-consolidate) don't inject lessons
# into a prompt today — they're either deterministic or consume
# lessons indirectly via the three command-aligned surfaces above.
# Adding surfaces for non-consuming commands inflates the vocabulary
# without changing routing.
#
# **Why not pure command-aligned?** ~30% of bullets in the existing
# corpus are genuinely cross-cutting (a handoff rule about deferred
# bullets, a step-shape rule about UI features) and apply to multiple
# commands. Forcing each into one command's bucket loses the cross-
# cutting signal and produces miscategorizations that the loader
# would then have to undo.
#
# **Why not pure content-aligned?** The future routing rule is "which
# command is running" — a content-only taxonomy would require a
# separate command→content mapping table to bridge the gap, adding
# indirection without buying anything.
#
# **When to add a surface:** (a) a new lesson-consuming prompt lands,
# AND it has accumulated ≥3 lessons that don't fit any existing
# surface; OR (b) a content cluster grows past ~30 bullets and
# doesn't fit ``cross-step`` or ``domain-shape``. Adding a surface
# also requires updating the two ``extract-lessons-*`` prompts so the
# model emits the new value.
#
# **Unknown / empty surface is allowed.** ``_coerce_entries`` quietly
# drops surface values not in this tuple back to ``""`` so a model
# typo doesn't fail the parse. Untagged bullets still land in the
# file; the loader treats them as "inject everywhere" until a future
# pass classifies them.
LESSON_SURFACES = (
    "create-heuristic",
    "detail-authoring",
    "review-heuristic",
    "cross-step",
    "domain-shape",
)

# Maximum bytes from each lessons file injected into a prompt, per file.
#
# A generosity cap, not a context-window constraint: with modern large
# windows the old 6 KB ceiling starved the model of accumulated
# knowledge for no benefit. A cap still earns its keep because lessons
# files grow without bound (pruning is a manual edit) and the block is
# injected on every lesson-consuming call — so an unbounded inject would
# inflate cost and erode prompt-cache stability on a file that only ever
# gets bigger. ``load_lessons(surfaces=...)`` narrows to the relevant
# lessons first; truncation (when it still bites) drops the OLDEST
# entries, so the freshest, most relevant lessons survive.
_MAX_INJECT_BYTES = 49152

DEFAULT_EQUIVALENCE_CONFIDENCE = 0.6
# Threshold below which equivalence findings are dropped before return.
# Picked to match the prompt's "skip pairs below 0.6" guidance — so the
# model self-filters and we double-check on the client. Shared by the
# ``find_lesson_equivalences`` primitive and the opt-in ``strict_check``
# path of ``append_lessons``.

_GENERAL_HEADER = (
    "# General plan-authoring lessons\n\n"
    "_Maintained by `plan-tool reconcile-plan` and `plan-tool detail`. Each "
    "bullet is a generalizable rule distilled from a finding. Lessons "
    "accumulate; prune through a direct edit when an entry no longer applies._\n\n"
)

_PROJECT_HEADER = (
    "# Project-specific lessons\n\n"
    "_Maintained by `plan-tool reconcile-plan` and `plan-tool detail`. Each "
    "bullet is a fact about this codebase that helps future plans be "
    "correct or complete. Lessons accumulate; prune through a direct edit._\n\n"
)


def _pending_header(plan_slug: str) -> str:
    return (
        f"# Pending lessons for plan `{plan_slug}`\n\n"
        "_Captured by `plan-tool detail` and held here because the "
        "canonical lessons file was inside this plan's `files:` set. "
        "Not loaded by `load_lessons`. Promote into the canonical files "
        "through a direct edit or via a future `plan-tool lessons promote` command._\n\n"
    )


_PENDING_GENERAL_SUBSECTION = "## General\n\n"
_PENDING_PROJECT_SUBSECTION = "## Project\n\n"


@dataclass(frozen=True)
class LessonEntry:
    """One bulleted lesson distilled from a review or detail run.

    ``rule`` is the one-line takeaway; ``why``, ``example``, ``surface``,
    and ``trigger`` are optional supporting context the extraction
    prompt produces. The dedupe check matches against the ``rule`` text
    only — ``surface`` / ``trigger`` are forward-compatible metadata for
    the future sectioned-loader (see ``LESSON_SURFACES``).

    Source citations (``added`` date + producer tag) used to be appended
    inline as a ``<sub>...</sub>`` line; they now land in a JSONL sidecar
    next to the lessons file (see ``_append_citation_jsonl``). That
    keeps each bullet dense for prompt-injection at read time while
    preserving the audit trail.
    """

    rule: str
    why: str = ""
    example: str = ""
    surface: str = ""
    trigger: str = ""

    def render(self) -> str:
        """Render as a Markdown bullet for append to the lessons file.

        Layout: ``- [`surface`] **rule** — why _(when: trigger)_ _(e.g.
        example)_``. Each clause collapses when its field is empty.
        Audit metadata (added date, producer tag) is no longer rendered
        inline — it lives in the citations JSONL sidecar.
        """
        rule = self.rule.strip()
        surface = self.surface.strip()
        if surface:
            head = f"- `[{surface}]` **{rule}**"
        else:
            head = f"- **{rule}**"
        parts = [head]
        if self.why.strip():
            parts.append(f" — {self.why.strip()}")
        if self.trigger.strip():
            parts.append(f" _(when: {self.trigger.strip()})_")
        if self.example.strip():
            parts.append(f" _(e.g. {self.example.strip()})_")
        return "".join(parts)


@dataclass(frozen=True)
class LessonsBundle:
    """Both lessons files loaded for prompt injection.

    ``general`` and ``project`` are the raw file bodies (header + bullets)
    or empty strings when the file is absent. ``render_block`` produces
    the concatenated form for prompt placeholders.
    """

    general: str
    project: str

    @property
    def is_empty(self) -> bool:
        return not self.general.strip() and not self.project.strip()


def _entry_text(entry: LessonEntry) -> str:
    """Return every model-authored field that can carry a scoped identifier."""
    return "\n".join(
        value for value in (entry.rule, entry.why, entry.example, entry.trigger) if value
    )


def _is_general_path(text: str) -> bool:
    """Whether one mentioned relative path is plan-tool's own package."""
    normalized = text.lstrip("./")
    return normalized.startswith(_GENERAL_PATH_PREFIXES)


def _entry_has_repo_scoped_identifier(entry: LessonEntry, repo_root: Path) -> bool:
    """Recognize a supposedly-general lesson's *resolvable* local facts.

    The detail extractor owns extension-shaped citations, so import it only at
    call time to preserve this module's existing import direction. The broader
    backticked-token pass also catches extensionless service paths such as
    ``/vendor/credentials``. A path needs to resolve inside this repository to
    count, except absolute paths: those are inherently host/project scoped and
    must never enter a cross-project store.

    Known limits, accepted deliberately rather than patched with a proxy (see
    the note above :data:`_GENERAL_PATH_PREFIXES`):

    - a bare domain **symbol** with no path is not routed. There is no
      observable that separates ``VendorCredentialsSecret`` from ``GitHub``
      without measuring vocabulary.
    - a relative path that escapes ``repo_root`` (``../other-repo/x.yml``)
      resolves outside and is skipped by the ``relative_to`` guard.
    """
    text = _entry_text(entry)
    if not text:
        return False
    from plan_tool.detail import extract_path_mentions

    path_mentions = set(extract_path_mentions(text))
    path_mentions.update(
        token.strip()
        for match in _BACKTICKED_TOKEN_RE.finditer(text)
        if "/" in (token := match.group(1).strip())
    )
    root = repo_root.resolve()
    for mention in path_mentions:
        if Path(mention).is_absolute():
            return True
        if _is_general_path(mention):
            continue
        try:
            candidate = (root / mention).resolve()
            candidate.relative_to(root)
        except (OSError, ValueError):
            continue
        if candidate.exists():
            return True
    return False


def _route_repo_scoped_general_entries(
    general: Iterable[LessonEntry], project: Iterable[LessonEntry], repo_root: Path
) -> tuple[list[LessonEntry], list[LessonEntry]]:
    """Move scope-leaking general candidates into the originating project bucket."""
    routed_general: list[LessonEntry] = []
    routed_project = list(project)
    for entry in general:
        if _entry_has_repo_scoped_identifier(entry, repo_root):
            routed_project.append(entry)
        else:
            routed_general.append(entry)
    return routed_general, routed_project


def general_lessons_dir(repo_root: Path) -> Path:
    """Return the directory holding the general lessons file.

    Resolves to ``~/.plan-tool/lessons/`` (``Path.home()`` evaluated at
    call time so ``$HOME``-overriding test fixtures keep working). The
    ``repo_root`` argument is accepted so callers don't have to know
    which bucket is per-user vs per-repo.
    """
    return Path.home().joinpath(*GENERAL_LESSONS_REL)


def project_lessons_dir(repo_root: Path) -> Path:
    """Return the directory holding the project-specific lessons file.

    Lives at ``<repo_root>/.plan-tool/lessons/`` so domain knowledge
    stays with the codebase.
    """
    return repo_root.joinpath(*PROJECT_LESSONS_REL)


def general_path(repo_root: Path) -> Path:
    return general_lessons_dir(repo_root) / GENERAL_FILENAME


def project_path(repo_root: Path) -> Path:
    return project_lessons_dir(repo_root) / PROJECT_FILENAME


def warnings_log_path(repo_root: Path) -> Path:
    """Return the per-repo warning log path (``<repo>/.plan-tool/lessons-warnings.jsonl``)."""
    return repo_root.joinpath(*WARNINGS_REL, WARNINGS_FILENAME)


def pending_lessons_path(repo_root: Path, plan_slug: str) -> Path:
    """Return the per-plan pending lessons file.

    Lives at ``~/.plan-tool/lessons/pending/<plan_slug>.md`` (alongside
    the canonical general.md sink, since pending entries are
    quarantined GENERAL distillations destined to promote into it).
    Quarantine destination for distilled lesson bullets whose canonical
    sink (``general.md`` / ``project.md``) is in the active plan's
    ``files:`` set.
    """
    return general_lessons_dir(repo_root) / PENDING_LESSONS_DIRNAME / f"{plan_slug}.md"


def general_citations_path(repo_root: Path) -> Path:
    """Sidecar JSONL holding audit metadata for new general.md entries.

    One record per appended bullet: ``{"rule_hash", "rule_preview",
    "added", "source"}``. Append-only; never rewritten in place. The
    bullet is the load-bearing artifact — the sidecar is best-effort
    audit context and is safe to truncate or rotate without affecting
    prompt injection.
    """
    return _citations_path_for(general_path(repo_root))


def project_citations_path(repo_root: Path) -> Path:
    """Sidecar JSONL for project.md entries. Same shape as general."""
    return _citations_path_for(project_path(repo_root))


def _citations_path_for(lessons_path: Path) -> Path:
    return lessons_path.with_name(lessons_path.stem + "-citations.jsonl")


def load_lessons(
    repo_root: Path,
    *,
    surfaces: Optional[frozenset[str]] = None,
    max_bytes: int = _MAX_INJECT_BYTES,
) -> LessonsBundle:
    """Read both lessons files into a bundle.

    ``surfaces`` filters bullets by ``[surface]`` tag (untagged always
    pass; ``None`` keeps all). Each file is recency-truncated to
    ``max_bytes`` — header + newest bullets kept, oldest dropped with a
    marker. Missing files render as empty strings.
    """
    return LessonsBundle(
        general=_select_lessons_body(
            _read_body(general_path(repo_root)),
            surfaces=surfaces,
            max_bytes=max_bytes,
        ),
        project=_select_lessons_body(
            _read_body(project_path(repo_root)),
            surfaces=surfaces,
            max_bytes=max_bytes,
        ),
    )


def _read_body(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


_BULLET_SURFACE_RE = re.compile(r"^-\s+`\[([^\]]+)\]`")
_TRUNCATION_MARKER = "… _(older entries truncated; see file on disk)_"


def _split_header_and_bullets(body: str) -> tuple[str, list[str]]:
    """Split a lessons file into its header prose and the ordered list of
    top-level bullets (oldest first — appends land at the end)."""
    lines = body.splitlines()
    first = next(
        (i for i, ln in enumerate(lines) if ln.startswith("- ")), len(lines)
    )
    header = "\n".join(lines[:first]).rstrip()
    bullets: list[str] = []
    current: list[str] = []
    for ln in lines[first:]:
        if ln.startswith("- "):
            if current:
                bullets.append("\n".join(current).rstrip())
            current = [ln]
        elif current:
            current.append(ln)
    if current:
        bullets.append("\n".join(current).rstrip())
    return header, bullets


def _bullet_surface(bullet: str) -> Optional[str]:
    """Return a bullet's ``[surface]`` tag, or ``None`` when untagged."""
    m = _BULLET_SURFACE_RE.match(bullet)
    return m.group(1) if m else None


def _select_lessons_body(
    body: str,
    *,
    surfaces: Optional[frozenset[str]],
    max_bytes: int,
) -> str:
    """Filter (by surface) and recency-truncate one lessons file body.

    Keeps the header plus the most-recent bullets that fit in
    ``max_bytes``; untagged bullets always pass the surface filter."""
    if not body.strip():
        return ""
    header, bullets = _split_header_and_bullets(body)
    if surfaces is not None:
        bullets = [
            b for b in bullets
            if (s := _bullet_surface(b)) is None or s in surfaces
        ]
    kept: list[str] = []
    used = len(header.encode("utf-8"))
    truncated = False
    for bullet in reversed(bullets):  # newest first
        size = len(bullet.encode("utf-8")) + 2  # +2 for the joining blank line
        if kept and used + size > max_bytes:
            truncated = True
            break
        kept.append(bullet)
        used += size
    kept.reverse()
    parts: list[str] = []
    if header:
        parts.append(header)
    if truncated:
        parts.append(_TRUNCATION_MARKER)
    parts.extend(kept)
    out = ("\n\n".join(parts).rstrip() + "\n") if parts else ""
    # Pathological single oversize bullet: byte-cap as a last resort so
    # one giant entry can't blow the budget.
    if len(out.encode("utf-8")) > max_bytes + len(_TRUNCATION_MARKER) + 16:
        clipped = out.encode("utf-8")[:max_bytes].decode("utf-8", "ignore")
        out = clipped.rstrip() + "\n\n" + _TRUNCATION_MARKER + "\n"
    return out


def render_lessons_block(bundle: LessonsBundle) -> str:
    """Render the bundle as a single prompt-injectable block.

    Empty bundle renders as a one-line placeholder so prompt templates
    never need to handle the absent case. Non-empty bundle concatenates
    general before project with a visible separator and a short framing
    line so claude understands what it's looking at.
    """
    if bundle.is_empty:
        return "_(no lessons captured yet — this is the first run)_"
    parts: list[str] = [
        "These lessons were captured by previous `plan-tool reconcile-plan` and "
        "`plan-tool detail` runs. Treat them as authoritative context. "
        "Apply the rules that fit; ignore those that don't — but do not "
        "regress on a captured rule without good reason."
    ]
    if bundle.general.strip():
        parts.append("")
        parts.append(bundle.general.rstrip())
    if bundle.project.strip():
        parts.append("")
        parts.append(bundle.project.rstrip())
    return "\n".join(parts)


@dataclass(frozen=True)
class AppendLessonsResult:
    """Outcome of one ``append_lessons`` call.

    ``n_general_added`` / ``n_project_added`` count entries written after
    *both* substring dedupe and (when enabled) strict-check filtering.
    ``general_dropped`` / ``project_dropped`` carry the
    ``EquivalenceFinding`` objects that caused entries to be refused in
    strict mode — empty tuples when ``strict_check=False`` or when the
    primitive (which already pre-filters at the confidence threshold)
    returned no findings. ``general_warnings`` / ``project_warnings``
    carry the findings produced under ``warn_check`` (the candidate was
    *kept* despite the finding) — empty tuples unless ``warn_check=True``.
    ``n_general_routed_to_project`` counts candidates the scope gate moved out
    of the general bucket, so the demotion is reported rather than silent.

    Iterates as ``(n_general_added, n_project_added)`` so existing callers
    that destructure ``n_g, n_p = append_lessons(...)`` keep working
    unchanged. The ``*_dropped`` / ``*_warnings`` fields are reached by
    attribute access only.
    """

    n_general_added: int
    n_project_added: int
    general_dropped: tuple["EquivalenceFinding", ...] = ()
    project_dropped: tuple["EquivalenceFinding", ...] = ()
    general_warnings: tuple["EquivalenceFinding", ...] = ()
    project_warnings: tuple["EquivalenceFinding", ...] = ()
    n_general_routed_to_project: int = 0

    def __iter__(self):
        return iter((self.n_general_added, self.n_project_added))


def append_lessons(
    repo_root: Path,
    *,
    general: Iterable[LessonEntry] = (),
    project: Iterable[LessonEntry] = (),
    source: str,
    strict_check: bool = False,
    warn_check: bool = False,
    equivalence_invoker: "Optional[EquivalenceInvoker]" = None,
    min_confidence: float = DEFAULT_EQUIVALENCE_CONFIDENCE,
    now: datetime | None = None,
) -> AppendLessonsResult:
    """Append ``general`` / ``project`` entries to the lessons files.

    Returns an :class:`AppendLessonsResult` (which destructures to
    ``(n_general_added, n_project_added)``) after case-insensitive
    substring dedupe — entries whose ``rule`` text already appears in the
    target file are silently dropped. ``source`` is a short tag like
    ``"review:plan-tool-v0.2"`` or ``"detail:ai-coach-hardening#3"`` that
    gets stamped onto each new bullet so future readers can trace
    lessons back to the run that produced them.

    ``strict_check`` is an opt-in pre-write hook: when True, the
    substring survivors are run through :func:`find_lesson_equivalences`
    against the existing file body, and any candidate flagged as a
    duplicate or conflict at ``confidence >= min_confidence`` is refused
    and surfaced on ``result.general_dropped`` / ``result.project_dropped``.
    The substring filter always runs first (it is local and free), so a
    candidate already deduped never reaches the claude judge. When
    ``strict_check`` is False (the default) no ``equivalence_invoker`` is
    consulted and the function behaves exactly as it did before. When
    ``strict_check`` is True and ``equivalence_invoker`` is None it falls
    back to :func:`shell_equivalence_invoker`.

    ``warn_check`` is the audit-only sibling of ``strict_check``: when
    True (and ``strict_check`` is False), the primitive runs against the
    substring survivors but **no** candidate is dropped — every survivor
    is written and each above-threshold finding is surfaced on
    ``result.general_warnings`` / ``result.project_warnings``.
    ``warn_check`` is ignored when ``strict_check`` is True (strict mode
    already runs the primitive and records the findings, as drops).

    Every finding from either knob is also appended to
    ``<repo>/.plan-tool/lessons-warnings.jsonl`` (best-effort; see
    :func:`append_warning`) so ``lessons consolidate`` can rank repeat
    findings.

    Before dedupe, candidates assigned to ``general`` that cite a path
    resolving inside this repository (or any absolute path) are routed to
    ``project`` and counted on ``n_general_routed_to_project``. Routing
    preserves the lesson; it only narrows the audience that receives it.

    Creates the file (and its parent dir) when absent. Lessons accumulate
    forever — pruning is a manual edit.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    added = now.date().isoformat()
    timestamp = now.replace(microsecond=0).isoformat()
    general_in = list(general)
    general, project = _route_repo_scoped_general_entries(
        general_in, project, repo_root
    )
    n_routed = len(general_in) - len(general)
    n_general, general_dropped, general_warnings = _append_to_file(
        general_path(repo_root),
        header=_GENERAL_HEADER,
        entries=general,
        added=added,
        source=source,
        repo_root=repo_root,
        strict_check=strict_check,
        warn_check=warn_check,
        equivalence_invoker=equivalence_invoker,
        min_confidence=min_confidence,
        timestamp=timestamp,
    )
    n_project, project_dropped, project_warnings = _append_to_file(
        project_path(repo_root),
        header=_PROJECT_HEADER,
        entries=project,
        added=added,
        source=source,
        repo_root=repo_root,
        strict_check=strict_check,
        warn_check=warn_check,
        equivalence_invoker=equivalence_invoker,
        min_confidence=min_confidence,
        timestamp=timestamp,
    )
    return AppendLessonsResult(
        n_general_added=n_general,
        n_project_added=n_project,
        general_dropped=general_dropped,
        project_dropped=project_dropped,
        general_warnings=general_warnings,
        project_warnings=project_warnings,
        n_general_routed_to_project=n_routed,
    )


def parse_lessons_extract_response(
    raw: str,
) -> Optional[tuple[list[LessonEntry], list[LessonEntry]]]:
    """Parse a Claude extract-lessons JSON response.

    Expected shape: ``{"general": [{"rule": str, "why": str, "example":
    str}], "project": [...]}``. Either array may be empty. Tolerates
    leading / trailing chatter the way ``create._parse_steps_json`` does
    by finding the outermost ``{`` / ``}`` and parsing what's between.

    Returns ``(general, project)`` lists on success, ``None`` when:
      - no top-level object can be located,
      - the JSON won't parse,
      - the top-level shape isn't ``{"general": list, "project": list}``.

    Entries with an empty / missing ``rule`` are silently dropped (the
    appender would dedupe them out anyway, but skipping early avoids
    wasted comparisons). Missing ``why`` / ``example`` fields default to
    empty strings.
    """
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    general_raw = obj.get("general", [])
    project_raw = obj.get("project", [])
    if not isinstance(general_raw, list) or not isinstance(project_raw, list):
        return None
    return _coerce_entries(general_raw), _coerce_entries(project_raw)


def _coerce_entries(items: list) -> list[LessonEntry]:
    out: list[LessonEntry] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rule = item.get("rule", "")
        if not isinstance(rule, str) or not rule.strip():
            continue
        why = item.get("why", "")
        example = item.get("example", "")
        surface = item.get("surface", "")
        trigger = item.get("trigger", "")
        if not isinstance(why, str):
            why = ""
        if not isinstance(example, str):
            example = ""
        if not isinstance(surface, str):
            surface = ""
        if not isinstance(trigger, str):
            trigger = ""
        # Quietly drop unknown surface values rather than fail the parse;
        # the future loader treats unknown surfaces as "untagged" anyway.
        surface_clean = surface.strip()
        if surface_clean and surface_clean not in LESSON_SURFACES:
            surface_clean = ""
        out.append(
            LessonEntry(
                rule=rule.strip(),
                why=why.strip(),
                example=example.strip(),
                surface=surface_clean,
                trigger=trigger.strip(),
            )
        )
    return out


def _render_new_bullets(
    existing_body: str,
    entries: Iterable[LessonEntry],
) -> tuple[list[str], list[LessonEntry]]:
    """Dedupe ``entries`` against ``existing_body`` and return rendered bullets.

    Substring match is case-insensitive — mirrors the original
    ``_append_to_file`` loop so callers (canonical sink + pending file)
    share one dedupe rule. Returns ``(rendered_bullets, appended_entries)``
    so the caller can also write citation sidecars keyed off the
    survivors.
    """
    existing_lower = existing_body.lower()
    new_bullets: list[str] = []
    appended_entries: list[LessonEntry] = []
    for entry in entries:
        rule_lower = entry.rule.strip().lower()
        if not rule_lower:
            continue
        if rule_lower in existing_lower:
            continue
        existing_lower += "\n" + rule_lower
        new_bullets.append(entry.render())
        appended_entries.append(entry)
    return new_bullets, appended_entries


def _append_to_file(
    path: Path,
    *,
    header: str,
    entries: Iterable[LessonEntry],
    added: str,
    source: str,
    repo_root: Path,
    strict_check: bool = False,
    warn_check: bool = False,
    equivalence_invoker: "Optional[EquivalenceInvoker]" = None,
    min_confidence: float = DEFAULT_EQUIVALENCE_CONFIDENCE,
    timestamp: str = "",
) -> tuple[int, tuple["EquivalenceFinding", ...], tuple["EquivalenceFinding", ...]]:
    """Append ``entries`` to ``path``, deduped against the existing body.

    Returns ``(n_written, dropped, warnings)`` where ``dropped`` carries
    the ``EquivalenceFinding`` objects the opt-in ``strict_check`` refused
    (always empty when ``strict_check`` is False) and ``warnings`` carries
    the findings ``warn_check`` recorded without dropping (always empty
    unless ``warn_check`` is True and ``strict_check`` is False).

    For each successfully appended bullet, also write one record to the
    sibling ``-citations.jsonl`` sidecar with ``rule_hash``,
    ``rule_preview``, ``added``, and ``source``. Bullet write is the
    durable line — if the citation write fails, the bullet stays
    written and the sidecar is missing one record (audit-trail loss
    only, no functional impact).

    The substring filter (``_render_new_bullets``) always runs first:
    it is local and free, and every entry it dedups would otherwise
    tokenize wastefully into the equivalence prompt. The ``strict_check``
    and ``warn_check`` hooks only fire on the substring survivors.
    ``strict_check`` wins when both are set: it already runs the
    primitive and records the findings (as drops), so ``warn_check`` is a
    redundant second pass.
    """
    entries_list = [e for e in entries if e.rule.strip()]
    if not entries_list:
        return 0, (), ()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if not existing:
        existing = header
    new_bullets, appended_entries = _render_new_bullets(existing, entries_list)
    if not new_bullets:
        return 0, (), ()

    target_file = _repo_rel_posix(path, repo_root)
    dropped: tuple["EquivalenceFinding", ...] = ()
    warnings: tuple["EquivalenceFinding", ...] = ()
    if strict_check:
        new_bullets, appended_entries, dropped = _strict_check_survivors(
            existing=existing,
            new_bullets=new_bullets,
            candidates=appended_entries,
            equivalence_invoker=equivalence_invoker,
            repo_root=repo_root,
            min_confidence=min_confidence,
            source=source,
            target_file=target_file,
            timestamp=timestamp,
        )
        if not new_bullets:
            return 0, dropped, ()
    elif warn_check:
        warnings = _warn_check_survivors(
            existing=existing,
            candidates=appended_entries,
            equivalence_invoker=equivalence_invoker,
            repo_root=repo_root,
            min_confidence=min_confidence,
            source=source,
            target_file=target_file,
            timestamp=timestamp,
        )

    sep = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    path.write_text(existing + sep + "\n".join(new_bullets) + "\n", encoding="utf-8")
    _append_citation_jsonl(
        _citations_path_for(path),
        entries=appended_entries,
        added=added,
        source=source,
    )
    return len(new_bullets), dropped, warnings


def _strict_check_survivors(
    *,
    existing: str,
    new_bullets: list[str],
    candidates: list[LessonEntry],
    equivalence_invoker: "Optional[EquivalenceInvoker]",
    repo_root: Path,
    min_confidence: float,
    source: str,
    target_file: str,
    timestamp: str,
) -> tuple[list[str], list[LessonEntry], tuple["EquivalenceFinding", ...]]:
    """Refuse substring survivors a claude judge flags as duplicates/conflicts.

    Parses the existing file body into prior entries, asks
    :func:`find_lesson_equivalences` to judge each (prior, candidate)
    pair, and drops every candidate named by a returned finding (the
    primitive has already filtered to ``confidence >= min_confidence``).
    ``new_bullets`` and ``candidates`` are positionally parallel, so a
    finding's 1-based ``right_index`` maps to the same slot in both.

    Returns ``(kept_bullets, kept_candidates, dropped_findings)``. For
    each drop, appends a ``mode="drop"`` record to the warning log (the
    durable audit trail) and emits one ``plan-tool: append_lessons
    strict-check dropped ...`` line on stderr (a cheap, interactive
    secondary signal for humans running ``plan-tool detail``).
    """
    invoker = equivalence_invoker or shell_equivalence_invoker
    prior_entries = parse_existing_entries(existing)
    findings = find_lesson_equivalences(
        prior_entries,
        candidates,
        invoker=invoker,
        repo_root=repo_root,
        min_confidence=min_confidence,
    )

    drop_indices: set[int] = set()
    dropped: list[EquivalenceFinding] = []
    for finding in (*findings.duplicates, *findings.conflicts):
        idx = finding.right_index - 1  # 1-based candidate position → 0-based
        if not (0 <= idx < len(candidates)):
            continue
        drop_indices.add(idx)
        dropped.append(finding)
        append_warning(
            repo_root,
            _finding_to_warning(
                finding,
                candidates=candidates,
                prior_entries=prior_entries,
                mode="drop",
                source=source,
                target_file=target_file,
                timestamp=timestamp,
            ),
        )
        rule_snippet = candidates[idx].rule.strip()[:80]
        print(
            f"plan-tool: append_lessons strict-check dropped "
            f"{finding.kind.value} for {rule_snippet} "
            f"(confidence={finding.confidence:.2f}; "
            f"rationale={finding.rationale})",
            file=sys.stderr,
        )

    kept_bullets = [b for i, b in enumerate(new_bullets) if i not in drop_indices]
    kept_candidates = [c for i, c in enumerate(candidates) if i not in drop_indices]
    return kept_bullets, kept_candidates, tuple(dropped)


def _warn_check_survivors(
    *,
    existing: str,
    candidates: list[LessonEntry],
    equivalence_invoker: "Optional[EquivalenceInvoker]",
    repo_root: Path,
    min_confidence: float,
    source: str,
    target_file: str,
    timestamp: str,
) -> tuple["EquivalenceFinding", ...]:
    """Run the equivalence primitive against survivors without dropping any.

    The audit-only sibling of :func:`_strict_check_survivors`: it judges
    each (prior, candidate) pair and appends a ``mode="warn"`` record to
    the warning log for every above-threshold finding, but leaves the
    write set untouched — every candidate that survived substring dedupe
    is still written by the caller. Returns the findings (duplicates then
    conflicts) so ``append_lessons`` can surface them on
    ``result.general_warnings`` / ``result.project_warnings``.
    """
    invoker = equivalence_invoker or shell_equivalence_invoker
    prior_entries = parse_existing_entries(existing)
    findings = find_lesson_equivalences(
        prior_entries,
        candidates,
        invoker=invoker,
        repo_root=repo_root,
        min_confidence=min_confidence,
    )

    warned: list[EquivalenceFinding] = []
    for finding in (*findings.duplicates, *findings.conflicts):
        warned.append(finding)
        append_warning(
            repo_root,
            _finding_to_warning(
                finding,
                candidates=candidates,
                prior_entries=prior_entries,
                mode="warn",
                source=source,
                target_file=target_file,
                timestamp=timestamp,
            ),
        )
    return tuple(warned)


def _finding_to_warning(
    finding: "EquivalenceFinding",
    *,
    candidates: list[LessonEntry],
    prior_entries: list[LessonEntry],
    mode: str,
    source: str,
    target_file: str,
    timestamp: str,
) -> "LessonsWarning":
    """Build a :class:`LessonsWarning` from one equivalence finding.

    ``finding.right_index`` is the 1-based position of the new candidate;
    ``finding.left_index`` is the 1-based position of the prior entry it
    matched. Out-of-range indices coerce to empty text rather than raise
    — the warning log is best-effort audit data, not a contract.
    """
    cand_idx = finding.right_index - 1
    prior_idx = finding.left_index - 1
    candidate_rule = (
        candidates[cand_idx].rule.strip()
        if 0 <= cand_idx < len(candidates)
        else ""
    )
    matched_rules: tuple[str, ...] = ()
    if 0 <= prior_idx < len(prior_entries):
        matched_rules = (prior_entries[prior_idx].rule.strip(),)
    return LessonsWarning(
        timestamp=timestamp,
        target_file=target_file,
        candidate_rule=candidate_rule,
        matched_rules=matched_rules,
        kind=finding.kind.value,
        confidence=finding.confidence,
        rationale=finding.rationale,
        source=source,
        mode=mode,
    )


def _repo_rel_posix(path: Path, repo_root: Path) -> str:
    """Repo-relative POSIX form of ``path``; bare filename when outside the repo.

    Keeps the warning log portable across machines (the recorded
    ``target_file`` is stable regardless of where the repo is checked
    out). Falls back to ``path.name`` when ``path`` can't be made
    relative to ``repo_root`` (a per-plan lessons file pointed outside
    the repo, or an unresolvable symlink)."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except (ValueError, OSError):
        return path.name


def _atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` via a sibling ``.tmp`` + ``os.replace``.

    Mirrors ``checkpoint.save_checkpoint``'s atomic-write contract: a
    crash mid-write cannot leave a half-written ``lessons-warnings.jsonl``.
    The tempfile lives in ``path.parent`` (not ``/tmp``) so the rename
    stays a single-inode operation.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def append_pending_lessons(
    repo_root: Path,
    *,
    plan_slug: str,
    general: Iterable[LessonEntry] = (),
    project: Iterable[LessonEntry] = (),
    source: str,
    now: datetime | None = None,
) -> tuple[int, int]:
    """Append ``general`` / ``project`` entries to the per-plan pending file.

    Quarantine destination for distilled bullets whose canonical sink
    (``general.md`` / ``project.md``) is inside the active plan's
    ``files:`` set. Both buckets land in one file under ``## General`` /
    ``## Project`` subsection headings so a future promoter can split
    mechanically. Returns ``(n_general_added, n_project_added)`` after
    case-insensitive substring dedupe **within the pending file**
    (cross-file dedupe against the canonical sink is deliberately not
    performed — the whole point of quarantine is to keep the bullet
    out of the file the plan is scrubbing).

    Citations sidecar is not written for pending entries; promotion
    into the canonical sink is the point at which the audit-trail
    record should be stamped, not capture. ``now`` / ``source`` are
    accepted for API symmetry with ``append_lessons`` so callers can
    pass the same kwargs through; they don't affect the on-disk
    body today.
    """
    _ = now
    _ = source
    general_list = [e for e in general if e.rule.strip()]
    project_list = [e for e in project if e.rule.strip()]
    if not general_list and not project_list:
        return 0, 0
    path = pending_lessons_path(repo_root, plan_slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if not existing:
        existing = (
            _pending_header(plan_slug)
            + _PENDING_GENERAL_SUBSECTION
            + _PENDING_PROJECT_SUBSECTION
        )
    body = existing
    n_general = 0
    n_project = 0
    if general_list:
        body, n_general = _append_to_pending_subsection(
            body,
            subsection_heading=_PENDING_GENERAL_SUBSECTION,
            entries=general_list,
        )
    if project_list:
        body, n_project = _append_to_pending_subsection(
            body,
            subsection_heading=_PENDING_PROJECT_SUBSECTION,
            entries=project_list,
        )
    if n_general == 0 and n_project == 0:
        return 0, 0
    path.write_text(body, encoding="utf-8")
    return n_general, n_project


# Matches an H2 heading at the start of a line — used to find the
# boundary between subsections inside a pending file. ``re.MULTILINE``
# makes ``^`` anchor to line starts so adjacent subsections (``##
# General\n\n## Project``) split cleanly even when the section body
# is empty.
_PENDING_H2_RE = re.compile(r"^## ", re.MULTILINE)


def _append_to_pending_subsection(
    body: str,
    *,
    subsection_heading: str,
    entries: list[LessonEntry],
) -> tuple[str, int]:
    """Insert ``entries`` (rendered + deduped) under ``subsection_heading``.

    Locates the subsection by exact heading match (callers pass one of
    ``_PENDING_GENERAL_SUBSECTION`` / ``_PENDING_PROJECT_SUBSECTION``),
    inserts the new bullets at the end of that subsection, and
    preserves everything around it byte-for-byte. Falls back to
    appending the subsection if the heading isn't found (defensive —
    the file is always seeded with both subsections, but an
    operator-edited file might have one removed).
    """
    new_bullets, _appended = _render_new_bullets(body, entries)
    if not new_bullets:
        return body, 0

    heading_idx = body.find(subsection_heading)
    if heading_idx == -1:
        sep = "" if body.endswith("\n\n") else ("\n" if body.endswith("\n") else "\n\n")
        return (
            body + sep + subsection_heading + "\n".join(new_bullets) + "\n",
            len(new_bullets),
        )

    section_start = heading_idx + len(subsection_heading)
    m = _PENDING_H2_RE.search(body, section_start)
    if m is None:
        section_body = body[section_start:]
        suffix = ""
    else:
        section_end = m.start()
        section_body = body[section_start:section_end]
        suffix = body[section_end:]

    if section_body.endswith("\n\n"):
        sep_before = ""
    elif section_body.endswith("\n"):
        sep_before = "\n"
    elif section_body:
        sep_before = "\n\n"
    else:
        sep_before = ""
    new_section_body = section_body + sep_before + "\n".join(new_bullets) + "\n"
    if suffix and not new_section_body.endswith("\n\n"):
        new_section_body = new_section_body.rstrip("\n") + "\n\n"
    return body[:section_start] + new_section_body + suffix, len(new_bullets)


def _rule_hash(rule: str) -> str:
    """SHA-256 of the normalized (strip + lowercase) rule, hex-truncated.

    Matches the dedup key used by ``_append_to_file`` so a bullet and
    its citation can be linked by recomputing the hash from the
    Markdown text. 16 hex chars is 64 bits — collision-resistant for
    any plausible lessons-file size.
    """
    normalized = rule.strip().lower().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:16]


def _append_citation_jsonl(
    path: Path,
    *,
    entries: list[LessonEntry],
    added: str,
    source: str,
) -> None:
    """Append one JSONL record per entry. Best-effort; swallows OSError.

    Each record is one JSON object per line:
    ``{"rule_hash", "rule_preview", "added", "source"}``. ``rule_preview``
    is the first 120 chars of the original-cased rule (handy for hand
    grep). The hash links back to the bullet's rule text via
    ``_rule_hash``.
    """
    if not entries:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for entry in entries:
                rule = entry.rule.strip()
                record = {
                    "rule_hash": _rule_hash(rule),
                    "rule_preview": rule[:120],
                    "added": added,
                    "source": source,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        tool(
            f"failed to append citation sidecar {path} ({exc}); "
            "the bullet is still written, only the audit-trail record was lost"
        )


# ----------------------------------------------------------------------
# Equivalence primitive — used by the lessons-consolidate CLI and by the
# opt-in strict_check path of append_lessons. Pure data in, pure data out.
# ----------------------------------------------------------------------

EquivalenceInvoker = Callable[[str], str]  # returns stdout (mirrors create.ClaudeInvoker)

LESSONS_EQUIVALENCE_SLUG = "lessons-equivalence"
# Synthetic checkpoint "slug" used in lieu of a plan slug for this primitive.
# Cached payloads land under .plan-tool/checkpoints/lessons-equivalence/<hash>.json
# via checkpoint_path(repo_root, LESSONS_EQUIVALENCE_SLUG, name=<hash>).


class EquivalenceKind(str, Enum):
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class EquivalenceFinding:
    """One judged pair from the equivalence primitive.

    ``left_index`` / ``right_index`` are 1-based positions into the
    primitive's *inputs* — when the caller passed both ``existing`` and
    ``candidates``, ``left_index`` is the position in ``existing`` and
    ``right_index`` is the position in ``candidates``. When the caller
    passed only ``existing`` (consolidate's intra-set case), both indices
    are positions in ``existing``.
    """

    kind: EquivalenceKind
    left_index: int
    right_index: int
    confidence: float
    rationale: str


@dataclass(frozen=True)
class EquivalenceFindings:
    """Result bundle returned by ``find_lesson_equivalences``.

    Pure data; no I/O. The consolidate command (step 2) renders these as
    a structured summary + diff; ``append_lessons`` strict path (step 3)
    refuses the write when ``duplicates`` or ``conflicts`` is non-empty.
    """

    duplicates: tuple[EquivalenceFinding, ...]
    conflicts: tuple[EquivalenceFinding, ...]

    @property
    def is_empty(self) -> bool:
        return not self.duplicates and not self.conflicts


def find_lesson_equivalences(
    existing: list[LessonEntry],
    candidates: Iterable[LessonEntry] = (),
    *,
    invoker: EquivalenceInvoker,
    repo_root: Optional[Path] = None,
    resume: bool = True,
    min_confidence: float = DEFAULT_EQUIVALENCE_CONFIDENCE,
) -> EquivalenceFindings:
    """Ask claude to judge equivalence/contradiction between lesson rules.

    Single shared primitive consumed by ``cli.cmd_lessons_consolidate``
    (step 2) and the opt-in ``strict_check`` path of ``append_lessons``
    (step 3). Pure data in, pure data out: callers own I/O, diffing,
    write decisions, and confidence-threshold *policy* (this function
    only enforces a floor at ``min_confidence``).

    When ``candidates`` is empty the primitive looks for duplicates and
    conflicts *inside* ``existing`` (consolidate's intra-set case).
    When ``candidates`` is non-empty the primitive judges every
    (existing, candidate) pair (append's pre-write case).

    Results are memoized under
    ``.plan-tool/checkpoints/lessons-equivalence/<hash>.json`` when
    ``repo_root`` is provided. ``resume=False`` skips the load but still
    saves on success. Tests that omit ``repo_root`` get no-checkpoint
    behavior.

    Findings below ``min_confidence`` are dropped silently. The model is
    instructed to self-filter at the same threshold; the client-side
    floor catches drift.
    """
    candidates_list = list(candidates)
    existing_list = list(existing)
    if not existing_list and not candidates_list:
        return EquivalenceFindings(duplicates=(), conflicts=())

    prompt = _render_equivalence_prompt(existing_list, candidates_list)
    input_hash = _equivalence_input_hash(existing_list, candidates_list)

    ckpt_path: Optional[Path] = None
    if repo_root is not None:
        ckpt_path = checkpoint_path(repo_root, LESSONS_EQUIVALENCE_SLUG, input_hash)

    cached: Optional[Checkpoint] = (
        load_if_valid(ckpt_path, expected_input_hash=input_hash)
        if (resume and ckpt_path is not None)
        else None
    )

    if cached is not None:
        raw = cached.payload
    else:
        raw = invoker(prompt)

    findings = parse_equivalence_response(raw)
    if findings is None:
        warn("equivalence response was unparseable; treating as no findings")
        return EquivalenceFindings(duplicates=(), conflicts=())

    duplicates = tuple(f for f in findings.duplicates if f.confidence >= min_confidence)
    conflicts = tuple(f for f in findings.conflicts if f.confidence >= min_confidence)

    # Save AFTER parse passes. An unparseable payload would lock the
    # caller out of a real claude retry next time.
    if ckpt_path is not None and cached is None:
        try:
            save_checkpoint(
                ckpt_path,
                Checkpoint(
                    input_hash=input_hash,
                    payload=raw,
                    created_at=datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat(),
                ),
            )
        except OSError as exc:
            tool(
                f"failed to save equivalence checkpoint "
                f"{ckpt_path} ({exc}); resume on next run will not be "
                "available for this call"
            )

    return EquivalenceFindings(duplicates=duplicates, conflicts=conflicts)


def parse_equivalence_response(raw: str) -> Optional[EquivalenceFindings]:
    """Parse claude's equivalence-judgment JSON. Tolerates preamble/chatter.

    Expected shape: ``{"duplicates": [...], "conflicts": [...]}`` where
    each item is ``{"left_index": int, "right_index": int, "confidence":
    float, "rationale": str}``. Returns ``None`` when:

    - no top-level object can be located,
    - the JSON won't parse,
    - the top-level shape isn't a dict,
    - either ``duplicates`` / ``conflicts`` is present but not a list.

    Items missing required fields, with non-positive indices, or with
    ``confidence`` outside ``[0.0, 1.0]`` are dropped silently. Missing
    ``rationale`` coerces to ``""``.
    """
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    dups = _coerce_findings(obj.get("duplicates", []), EquivalenceKind.DUPLICATE)
    cons = _coerce_findings(obj.get("conflicts", []), EquivalenceKind.CONFLICT)
    if dups is None or cons is None:
        return None
    return EquivalenceFindings(duplicates=tuple(dups), conflicts=tuple(cons))


def _coerce_findings(
    items: object, kind: EquivalenceKind
) -> Optional[list[EquivalenceFinding]]:
    if not isinstance(items, list):
        return None
    out: list[EquivalenceFinding] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        left = item.get("left_index")
        right = item.get("right_index")
        confidence = item.get("confidence")
        # bool is a subclass of int; reject explicitly so True/False
        # don't masquerade as 1-based indices.
        if not isinstance(left, int) or isinstance(left, bool) or left <= 0:
            continue
        if not isinstance(right, int) or isinstance(right, bool) or right <= 0:
            continue
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            continue
        if confidence < 0.0 or confidence > 1.0:
            continue
        rationale = item.get("rationale", "")
        if not isinstance(rationale, str):
            rationale = ""
        out.append(
            EquivalenceFinding(
                kind=kind,
                left_index=int(left),
                right_index=int(right),
                confidence=float(confidence),
                rationale=rationale,
            )
        )
    return out


def _render_entries_block(entries: list[LessonEntry]) -> str:
    """Render a 1-based numbered list of lesson entries for the prompt.

    Each line matches ``{n}. **{rule}** — {why} _(e.g. {example})_`` —
    the optional clauses collapse when fields are empty, mirroring
    ``LessonEntry.render``. Returns the empty string when ``entries`` is
    empty so the caller can substitute its own marker.
    """
    lines: list[str] = []
    for n, entry in enumerate(entries, start=1):
        parts = [f"{n}. **{entry.rule.strip()}**"]
        why = entry.why.strip()
        example = entry.example.strip()
        if why:
            parts.append(f" — {why}")
        if example:
            parts.append(f" _(e.g. {example})_")
        lines.append("".join(parts))
    return "\n".join(lines)


def _render_equivalence_prompt(
    existing: list[LessonEntry],
    candidates: list[LessonEntry],
) -> str:
    template_path = prompts_dir() / "lessons-equivalence.md"
    template = Template(template_path.read_text(encoding="utf-8"))
    return template.safe_substitute(
        existing_block=_render_entries_block(existing) or "_(no existing lessons)_",
        candidates_block=(
            _render_entries_block(candidates)
            if candidates
            else "_(no candidates; analyze existing-vs-existing pairs for duplicates and conflicts)_"
        ),
    )


def _equivalence_input_hash(
    existing: list[LessonEntry],
    candidates: list[LessonEntry],
) -> str:
    """SHA-256 of the canonical-JSON list of (rule, why, example) tuples.

    Hashes rule text exactly as supplied (no case-fold) so a recasing
    legitimately invalidates the cache — the prompt sees different
    wording. Order matters: re-ordering ``existing`` changes the indices
    the prompt and parser use, so the hash must too. Does not include
    ``min_confidence`` — that's a post-return filter, so re-using a
    cached response under a different threshold is correct.
    """
    payload = {
        "existing": [[e.rule, e.why, e.example] for e in existing],
        "candidates": [[c.rule, c.why, c.example] for c in candidates],
    }
    return compute_input_hash(payload)


def shell_equivalence_invoker(prompt: str) -> str:
    """Default ``EquivalenceInvoker`` — wraps ``shell.claude_invoke``.

    Discards the exit code (returns ``""`` on non-zero, same as the
    detail/jira invokers in ``shell.py``). Production CLI wiring in
    step 2 / step 3 passes this; tests pass a fake.
    """
    rc, stdout = claude_invoke(prompt, phase="lessons_equivalence")
    return stdout if rc == 0 else ""


# ----------------------------------------------------------------------
# Consolidate primitives — file discovery, entry parsing, and rewrite.
# Pure data helpers consumed by ``cli.cmd_lessons_consolidate`` (step 2).
# No I/O beyond a single ``Path.is_file`` probe in discovery; no claude.
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class LessonsFile:
    """One discovered lessons file.

    ``kind`` is "general" (skill-shipped), "project" (per-repo), or
    "per-plan" (file at the path declared by a plan's ``lessons:``
    frontmatter field). ``plan_slug`` is populated only for the
    per-plan kind; ``general`` and ``project`` leave it ``None``.
    """

    path: Path
    kind: str  # "general" | "project" | "per-plan"
    plan_slug: Optional[str] = None


def discover_lessons_files(
    repo_root: Path,
    entries: list,  # list[PlanEntry] from plan_tool.locator
) -> list[LessonsFile]:
    """Return every lessons file the consolidate handler should consider.

    Order: ``general.md`` first (skill-shipped at
    ``general_path(repo_root)``), then ``project.md`` (per-repo at
    ``project_path(repo_root)``), then every per-plan ``lessons.md``
    resolved by ``repo_root / entry.plan.lessons`` for each
    ``PlanEntry`` whose ``plan`` is non-None and whose ``plan.lessons``
    is set.

    Files that don't exist on disk are skipped silently (the handler
    treats "missing" and "present but empty" identically).

    De-dupes by resolved ``Path`` — a pathological plan whose
    ``lessons:`` points at ``general.md`` won't be processed twice. The
    order is stable (``general``, ``project``, then per-plan in the
    order ``entries`` came back from ``build_plan_tool_context``) so the
    diff/summary output is reproducible across runs.
    """
    seen: set[Path] = set()
    out: list[LessonsFile] = []

    def _add(path: Path, kind: str, *, plan_slug: Optional[str] = None) -> None:
        if not path.is_file():
            return
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            return
        seen.add(resolved)
        out.append(LessonsFile(path=path, kind=kind, plan_slug=plan_slug))

    _add(general_path(repo_root), "general")
    _add(project_path(repo_root), "project")
    for entry in entries:
        plan = getattr(entry, "plan", None)
        if plan is None:
            continue
        lessons_rel = getattr(plan, "lessons", None)
        if not lessons_rel:
            continue
        _add(repo_root / lessons_rel, "per-plan", plan_slug=entry.slug)
    return out


# Inverse of ``LessonEntry.render`` — recognizes a tool-written bullet of
# the shape ``- `[surface]` **rule** — why _(when: trigger)_ _(e.g. ex)_``
# where every clause except the bold ``**rule**`` span is optional. The
# mandatory bold span is the machine-bullet discriminator; lines without
# it (the file header, blank lines, directly edited prose bullets) don't
# match and are skipped.
_ENTRY_RE = re.compile(
    r"^- (?:`\[(?P<surface>[^\]]+)\]` )?"
    r"\*\*(?P<rule>.+?)\*\*"
    r"(?: — (?P<why>.+?))?"
    r"(?: _\(when: (?P<trigger>.+?)\)_)?"
    r"(?: _\(e\.g\. (?P<example>.+?)\)_)?"
    r"\s*$"
)


def parse_existing_entries(body: str) -> list[LessonEntry]:
    """Parse a lessons-file body into the LessonEntry list it was rendered from.

    Inverse of the current ``LessonEntry.render`` shape, where the
    ``[surface]``, ``— why``, ``_(when: ...)_``, and ``_(e.g. ...)_``
    clauses are each optional and collapse when their field is empty.
    The mandatory ``**rule**`` bold span is the
    machine-bullet discriminator. Lines that don't carry a
    ``- ...**bold rule**...`` head (the file header, blank lines,
    directly edited prose bullets) are silently skipped so the primitive
    only sees tool-written entries — directly written prose isn't a fair
    target for equivalence judgment.
    """
    out: list[LessonEntry] = []
    for line in body.splitlines():
        m = _ENTRY_RE.match(line)
        if m is None:
            continue
        out.append(
            LessonEntry(
                rule=m.group("rule") or "",
                why=m.group("why") or "",
                example=m.group("example") or "",
                surface=m.group("surface") or "",
                trigger=m.group("trigger") or "",
            )
        )
    return out


def render_consolidated_file(
    original_body: str,
    drop_entry_indices: frozenset[int],
) -> str:
    """Return the body with the listed (0-based) entry indices removed.

    Indexing matches ``parse_existing_entries``'s output: index 0 is the
    first ``**bold rule**`` bullet in the file, regardless of any header
    / blank / directly written content before it. Non-matching lines pass
    through verbatim, preserving the file header, blank-line spacing,
    and directly edited bullets. Indices that reference no entry are ignored
    (no ``IndexError``). Trailing newline shape is preserved (the file
    ends with the same newline count as the original).
    """
    kept: list[str] = []
    entry_idx = 0
    for line in original_body.splitlines(keepends=True):
        if _ENTRY_RE.match(line.rstrip("\r\n")):
            drop = entry_idx in drop_entry_indices
            entry_idx += 1
            if drop:
                continue
        kept.append(line)
    return "".join(kept)


# ----------------------------------------------------------------------
# Warning log — append-only JSONL audit trail of equivalence findings
# produced by the opt-in strict_check / warn_check paths of
# append_lessons. Best-effort runtime state: writes never fail the parent
# append, reads tolerate malformed lines. The lessons-consolidate handler
# reads it back to rank repeat findings ahead of one-offs.
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class LessonsWarning:
    """One record in ``.plan-tool/lessons-warnings.jsonl``.

    ``mode`` is ``"warn"`` (the candidate was written despite the
    finding) or ``"drop"`` (the candidate was refused). ``target_file``
    is repo-relative POSIX so the log is portable across machines.
    ``matched_rules`` is a tuple because one candidate can match several
    prior entries (each ``EquivalenceFinding`` carries one, so repeated
    findings for the same candidate become separate records). ``kind``
    mirrors :class:`EquivalenceKind` (``"duplicate"`` / ``"conflict"``).
    """

    timestamp: str          # ISO-8601 UTC, seconds precision
    target_file: str        # repo-relative POSIX path
    candidate_rule: str
    matched_rules: tuple[str, ...]
    kind: str               # EquivalenceKind value: "duplicate" | "conflict"
    confidence: float
    rationale: str
    source: str             # the append_lessons() ``source`` tag
    mode: str               # "warn" | "drop"

    def to_json_line(self) -> str:
        """Serialize as a single JSONL line (trailing ``\\n`` included)."""
        return json.dumps({
            "timestamp": self.timestamp,
            "target_file": self.target_file,
            "candidate_rule": self.candidate_rule,
            "matched_rules": list(self.matched_rules),
            "kind": self.kind,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "source": self.source,
            "mode": self.mode,
        }, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, obj: dict) -> "LessonsWarning":
        return cls(
            timestamp=str(obj.get("timestamp", "")),
            target_file=str(obj.get("target_file", "")),
            candidate_rule=str(obj.get("candidate_rule", "")),
            matched_rules=tuple(obj.get("matched_rules", []) or ()),
            kind=str(obj.get("kind", "")),
            confidence=float(obj.get("confidence", 0.0)),
            rationale=str(obj.get("rationale", "")),
            source=str(obj.get("source", "")),
            mode=str(obj.get("mode", "")),
        )


def append_warning(
    repo_root: Path,
    record: LessonsWarning,
    *,
    max_records: int = DEFAULT_WARNINGS_CAP,
    stderr=sys.stderr,
) -> None:
    """Append ``record`` to ``<repo>/.plan-tool/lessons-warnings.jsonl``.

    Creates the file (and parent dir) on first write. After the append,
    counts the line total and trims to the most recent ``max_records``
    via the atomic ``.tmp`` + ``os.replace`` pattern in
    :func:`_atomic_write_text`, emitting one ``plan-tool:
    lessons-warnings.jsonl trimmed to N records (was M)`` notice on
    ``stderr`` whenever a trim fires so cleanup is observable.

    Never raises — best-effort. A failed append (read-only filesystem,
    full disk) logs a single ``plan-tool: append_warning failed: ...``
    line on ``stderr`` and returns; ``append_lessons`` callers must not
    fail on warning-log I/O.
    """
    path = warnings_log_path(repo_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(record.to_json_line())
        lines = [
            ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()
        ]
        if len(lines) > max_records:
            was = len(lines)
            kept = lines[-max_records:]
            _atomic_write_text(path, "\n".join(kept) + "\n")
            print(
                f"plan-tool: lessons-warnings.jsonl trimmed to "
                f"{max_records} records (was {was})",
                file=stderr,
            )
    except Exception as exc:  # noqa: BLE001 — best-effort; never fail the append.
        print(f"plan-tool: append_warning failed: {exc}", file=stderr)


def load_warnings(repo_root: Path) -> list[LessonsWarning]:
    """Read every record from the warning log, oldest first.

    Returns ``[]`` when the file is absent. Lines that aren't parseable
    JSON or aren't shaped like a ``LessonsWarning`` object are silently
    skipped — the log is best-effort runtime state, not a contract, and
    a single bad line shouldn't poison the consolidate ranking.
    """
    path = warnings_log_path(repo_root)
    if not path.is_file():
        return []
    out: list[LessonsWarning] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        out.append(LessonsWarning.from_json(obj))
    return out


def recurrence_counts(
    records: Iterable[LessonsWarning],
) -> dict[tuple[str, str], int]:
    """Count how often each (candidate, matched-prior) pair has been logged.

    Keys are case-folded so ``"verify file paths"`` and ``"Verify File
    Paths"`` count as the same pair — matches the substring-dedupe
    contract elsewhere in this module. When a record has multiple
    ``matched_rules`` entries, each pair is counted independently
    (a one-to-many warning is N pair-flags, not 1).
    """
    counter: Counter[tuple[str, str]] = Counter()
    for r in records:
        cand = r.candidate_rule.strip().lower()
        if not cand:
            continue
        for matched in r.matched_rules:
            m = matched.strip().lower()
            if not m:
                continue
            counter[(cand, m)] += 1
    return dict(counter)


def recurrence_weight_from_counts(
    counts: dict[tuple[str, str], int],
    *,
    entries_by_index: "Optional[dict[int, LessonEntry]]" = None,
) -> "Callable[[EquivalenceFinding], float]":
    """Build a weight function: ``1.0 + count(left↔right)``, ``1.0`` floor.

    ``entries_by_index`` maps the 1-based indices the primitive returns
    (``EquivalenceFinding.left_index`` / ``right_index``) to their
    ``LessonEntry`` so the canonical ``rule`` text can be keyed against
    ``counts``. When ``None``, the function returns a constant ``1.0``
    (the caller didn't wire entries — degrades to the no-op weight).

    The pair key is summed in both directions because the warning log
    always records the *candidate* as the new entry and the *matched*
    rule as the prior, while ``lessons consolidate`` runs an intra-set
    comparison where either direction is possible. Floor of ``1.0`` keeps
    the sort key positive so first-time findings still order; linear (not
    log) weight because the consolidate output is interactive review, not
    a search ranker, so the simpler scale is more readable.
    """
    def _weight(finding: "EquivalenceFinding") -> float:
        if entries_by_index is None:
            return 1.0
        left = entries_by_index.get(finding.left_index)
        right = entries_by_index.get(finding.right_index)
        if left is None or right is None:
            return 1.0
        key = (right.rule.strip().lower(), left.rule.strip().lower())
        alt = (left.rule.strip().lower(), right.rule.strip().lower())
        return 1.0 + float(counts.get(key, 0) + counts.get(alt, 0))
    return _weight
