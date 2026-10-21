"""Deterministic developer-handoff renderer and shared companion provenance.

Turns one companion-mode captured snapshot, threaded through the narrow
:class:`HandoffRenderInput` boundary below rather than imported directly,
into a Markdown developer handoff that follows the committed plan path in
stable dependency order, labels selected-detail material as a non-binding
suggested route, and keeps parked (deferred/wont_do) steps as non-actionable
history.

This module also defines :class:`CompanionProvenance` — the one structured
value both the handoff and the companion-mode story source (markdown or
JSON) carry, plus format-specific writers/readers that recognize a same-plan,
complete generated-source pair before publication considers replacing either
target.

Deliberately pure and a leaf: no filesystem reads, no model calls, no
writes, and no import of ``plan_tool.jira`` (which calls *into* this
module). Callers hand in
already-captured values through the dataclasses below instead of a
``plan_tool.jira`` capture object, so no reverse import is ever created.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Optional

from plan_tool.parser import parse_body_sections
from plan_tool.schema import Plan, StepStatus
from plan_tool.scope_fence import collapse_intent_to_one_line, is_placeholder_intent

# --------------------------------------------------------------------------
# Render-input boundary
# --------------------------------------------------------------------------

DETAIL_STATE_PRESENT = "present"
DETAIL_STATE_MISSING = "missing"

FILE_EXCERPT_STATE_EXCERPT = "excerpt"
FILE_EXCERPT_STATE_MISSING = "missing"
FILE_EXCERPT_STATE_UNREADABLE = "unreadable"

# Plan-body sections rendered as captured developer context, in display
# order. "Audit guardrails" and "Stack" are deliberately absent — the first
# must never appear in a generated handoff, and the second is not carried
# into one (BACKLOG #460 non-goal). Section presence/lookup uses
# ``parser.parse_body_sections``' normalized names (lowercased, trailing
# ``:``/``.`` stripped).
_PLAN_CONTEXT_SECTION_NAMES = (
    "Overview",
    "Problem statement",
    "Architecture",
    "Out of scope",
    "Risks",
    "Acceptance criteria",
    "Scope guardrails",
    "Expected placement",
)

_SCOPE_OR_PLACEMENT_SECTION_NAMES = ("Scope guardrails", "Expected placement")


class HandoffRenderError(ValueError):
    """A captured render input cannot produce a valid handoff.

    Raised only for a committed non-done step missing its required title
    or meaningful intent, or a dependency cycle among committed steps —
    both would otherwise render a handoff that invents or loses a
    binding plan-path fact.
    """


@dataclass(frozen=True)
class DetailRenderInput:
    """One committed step's captured selected-detail render input.

    ``state`` is :data:`DETAIL_STATE_PRESENT` (``path``/``text`` set) or
    :data:`DETAIL_STATE_MISSING` (no selected detail at all — only
    expected on a ``done`` step, where it renders as a historical
    fallback rather than a suggested route).
    """

    state: str
    path: Optional[str] = None
    text: Optional[str] = None


@dataclass(frozen=True)
class FileExcerptRenderInput:
    """One declared file's captured render state for a committed step."""

    path: str
    state: str
    excerpt_text: Optional[str] = None
    excerpt_kind: Optional[str] = None
    fallback_reason: Optional[str] = None
    truncated: bool = False
    error: Optional[str] = None


@dataclass(frozen=True)
class CommittedStepRenderInput:
    """One committed step's captured render input.

    Title, status, intent, and dependency edges are read from the
    snapshot's own ``plan.step_by_id(id)`` rather than duplicated here —
    only the values this module cannot get from ``Plan`` (selected
    detail, file excerpts) live on this record.
    """

    id: int
    detail: DetailRenderInput
    file_excerpts: tuple[FileExcerptRenderInput, ...] = ()


@dataclass(frozen=True)
class ParkedStepRenderInput:
    """A deferred/``wont_do`` step's non-actionable historical record.

    Deliberately narrow: no dependency, outcome, detail, or excerpt data
    is ever selected for a parked step.
    """

    id: int
    title: str
    scope: str
    status_note: Optional[str] = None


@dataclass(frozen=True)
class GeneratedSourcePairIdentity:
    """The normalized (story destination, handoff destination, format) triple."""

    story_path: str
    handoff_path: str
    format: str


@dataclass(frozen=True)
class CompanionRenderSettings:
    """Captured story settings that also define the shared fingerprint."""

    epic_key: str
    epic_name: str
    epic_jira_id: Optional[str]
    epic_description: Optional[str]
    plan_tag: str
    max_hours: int
    start_number: int
    story_prompt_contract_revision: int
    handoff_format_contract_revision: int


@dataclass(frozen=True)
class HandoffRenderInput:
    """One immutable render-input snapshot for the developer handoff.

    Every field is already captured/validated by the caller (step 1) —
    this module never reopens ``plan``, a detail path, or a declared file.
    """

    plan: Plan
    body_text: str
    grade: str
    source_plan_path: str
    committed_steps: tuple[CommittedStepRenderInput, ...]
    parked_step_history: tuple[ParkedStepRenderInput, ...]
    pair_identity: GeneratedSourcePairIdentity
    companion_settings: CompanionRenderSettings


@dataclass(frozen=True)
class CarriedStoryRecordRenderInput:
    """One existing companion story record's fingerprint-relevant projection.

    ``raw_target_proof`` and ``predecessor_provenance_fingerprint`` are
    ownership-validation evidence from a *prior* write, carried here only
    so callers have somewhere to keep them — :func:`compute_input_fingerprint`
    never reads either, so an unchanged rerun (same rendered content,
    fresh target bytes/provenance) keeps the same fingerprint.
    """

    id: str
    steps: tuple[int, ...]
    export_state: str
    jira_issue_key: str
    rendered_content: str
    raw_target_proof: Optional[str] = None
    predecessor_provenance_fingerprint: Optional[str] = None


# --------------------------------------------------------------------------
# Companion provenance
# --------------------------------------------------------------------------

# Bumped when the shape of the provenance block itself changes in a way
# that should make a reader stop recognizing an older block.
PROVENANCE_FORMAT_REVISION = 1

# The only generation mode this module currently produces — named
# explicitly (rather than left implicit) so the provenance block states
# it rather than a reader having to assume it.
GENERATION_MODE_COMPANION = "companion"


@dataclass(frozen=True)
class CompanionProvenance:
    """The shared generated-source marker for the handoff and story outputs.

    One value, computed once, embedded identically (per format) on both
    the handoff and the companion-mode story source so a later publication
    step can prove they came from the same captured snapshot.
    """

    provenance_format_revision: int
    generation_mode: str
    selected_grade: str
    source_plan_path: str
    selected_detail_source_paths: tuple[tuple[int, str], ...]
    pair_identity: GeneratedSourcePairIdentity
    story_prompt_contract_revision: int
    handoff_format_contract_revision: int
    fingerprint: str


def compute_input_fingerprint(
    render_input: HandoffRenderInput,
    existing_story_records: tuple[CarriedStoryRecordRenderInput, ...] = (),
) -> str:
    """Deterministic SHA-256 over every captured value that can change
    either generated source.

    Includes plan-body context, normalized destinations, and each carried
    existing story record's rendered content, covered-step set, lifecycle
    state, and Jira key. Excludes predecessor-output ownership evidence —
    ``raw_target_proof`` / ``predecessor_provenance_fingerprint`` — so a
    rerun over an unchanged render input keeps the same fingerprint and
    never manufactures a false lifecycle change.
    """
    payload = {
        "grade": render_input.grade,
        "source_plan_path": render_input.source_plan_path,
        "pair_identity": {
            "story_path": render_input.pair_identity.story_path,
            "handoff_path": render_input.pair_identity.handoff_path,
            "format": render_input.pair_identity.format,
        },
        "companion_settings": {
            "epic_key": render_input.companion_settings.epic_key,
            "epic_name": render_input.companion_settings.epic_name,
            "epic_jira_id": render_input.companion_settings.epic_jira_id,
            "epic_description": render_input.companion_settings.epic_description,
            "plan_tag": render_input.companion_settings.plan_tag,
            "max_hours": render_input.companion_settings.max_hours,
            "start_number": render_input.companion_settings.start_number,
            "story_prompt_contract_revision": (
                render_input.companion_settings.story_prompt_contract_revision
            ),
            "handoff_format_contract_revision": (
                render_input.companion_settings.handoff_format_contract_revision
            ),
        },
        "plan_title": render_input.plan.title,
        "body_text": render_input.body_text,
        "committed_steps": [
            {
                "id": ci.id,
                "title": render_input.plan.step_by_id(ci.id).title,
                "status": render_input.plan.step_by_id(ci.id).status.value,
                "intent": render_input.plan.step_by_id(ci.id).intent,
                "depends_on": list(render_input.plan.step_by_id(ci.id).depends_on),
                "detail_state": ci.detail.state,
                "detail_path": ci.detail.path,
                "detail_text": ci.detail.text,
                "file_excerpts": [
                    {
                        "path": fc.path,
                        "state": fc.state,
                        "excerpt_text": fc.excerpt_text,
                        "excerpt_kind": fc.excerpt_kind,
                        "fallback_reason": fc.fallback_reason,
                        "truncated": fc.truncated,
                        "error": fc.error,
                    }
                    for fc in ci.file_excerpts
                ],
            }
            for ci in render_input.committed_steps
        ],
        "parked_step_history": [
            {
                "id": p.id,
                "title": p.title,
                "scope": p.scope,
                "status_note": p.status_note,
            }
            for p in render_input.parked_step_history
        ],
        "existing_story_records": [
            {
                "id": r.id,
                "steps": sorted(r.steps),
                "export_state": r.export_state,
                "jira_issue_key": r.jira_issue_key,
                "rendered_content": r.rendered_content,
            }
            for r in sorted(existing_story_records, key=lambda r: r.id)
        ],
    }
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_companion_provenance(
    render_input: HandoffRenderInput,
    *,
    existing_story_records: tuple[CarriedStoryRecordRenderInput, ...] = (),
    generation_mode: str = GENERATION_MODE_COMPANION,
) -> CompanionProvenance:
    """Build the one :class:`CompanionProvenance` shared by both outputs."""
    detail_paths = tuple(
        (ci.id, ci.detail.path)
        for ci in render_input.committed_steps
        if ci.detail.state == DETAIL_STATE_PRESENT and ci.detail.path
    )
    fingerprint = compute_input_fingerprint(render_input, existing_story_records)
    return CompanionProvenance(
        provenance_format_revision=PROVENANCE_FORMAT_REVISION,
        generation_mode=generation_mode,
        selected_grade=render_input.grade,
        source_plan_path=render_input.source_plan_path,
        selected_detail_source_paths=detail_paths,
        pair_identity=render_input.pair_identity,
        story_prompt_contract_revision=(
            render_input.companion_settings.story_prompt_contract_revision
        ),
        handoff_format_contract_revision=(
            render_input.companion_settings.handoff_format_contract_revision
        ),
        fingerprint=fingerprint,
    )


# --------------------------------------------------------------------------
# Provenance writers/readers — Markdown
# --------------------------------------------------------------------------

_MD_PROVENANCE_MARKER = "plan-tool-companion-provenance"
_MD_PROVENANCE_RE = re.compile(
    r"<!--\s*" + re.escape(_MD_PROVENANCE_MARKER) + r"\s*\n(?P<body>.*?)-->",
    re.DOTALL,
)

_REQUIRED_MD_PROVENANCE_KEYS = (
    "provenance_format_revision",
    "generation_mode",
    "selected_grade",
    "source_plan_path",
    "selected_detail_source_paths",
    "pair_identity_story_path",
    "pair_identity_handoff_path",
    "pair_identity_format",
    "story_prompt_contract_revision",
    "handoff_format_contract_revision",
    "fingerprint",
)


def write_markdown_provenance(provenance: CompanionProvenance) -> str:
    """Render ``provenance`` as an embeddable HTML-comment block.

    Used verbatim by both the Markdown handoff and companion-mode
    Markdown story source — an ordinary (non-companion) story export
    never calls this, so its output keeps its current shape.
    """
    detail_paths = json.dumps(
        provenance.selected_detail_source_paths,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    lines = [
        f"<!-- {_MD_PROVENANCE_MARKER}",
        f"provenance_format_revision: {provenance.provenance_format_revision}",
        f"generation_mode: {provenance.generation_mode}",
        f"selected_grade: {provenance.selected_grade}",
        f"source_plan_path: {provenance.source_plan_path}",
        f"selected_detail_source_paths: {detail_paths}",
        f"pair_identity_story_path: {provenance.pair_identity.story_path}",
        f"pair_identity_handoff_path: {provenance.pair_identity.handoff_path}",
        f"pair_identity_format: {provenance.pair_identity.format}",
        f"story_prompt_contract_revision: {provenance.story_prompt_contract_revision}",
        f"handoff_format_contract_revision: {provenance.handoff_format_contract_revision}",
        f"fingerprint: {provenance.fingerprint}",
        "-->",
    ]
    return "\n".join(lines)


def _parse_detail_source_paths(raw: str) -> Optional[tuple[tuple[int, str], ...]]:
    if not raw:
        return ()
    try:
        values = json.loads(raw)
    except json.JSONDecodeError:
        # Read provenance written before paths were encoded as JSON.
        return _parse_legacy_detail_source_paths(raw)
    if not isinstance(values, list):
        return None
    paths: list[tuple[int, str]] = []
    for value in values:
        if (
            not isinstance(value, list)
            or len(value) != 2
            or isinstance(value[0], bool)
            or not isinstance(value[0], int)
            or not isinstance(value[1], str)
            or not value[1]
        ):
            return None
        paths.append((value[0], value[1]))
    return tuple(paths)


def _parse_legacy_detail_source_paths(raw: str) -> Optional[tuple[tuple[int, str], ...]]:
    # Known, accepted ambiguity: a legacy entry's path containing a literal
    # '|' is indistinguishable from an entry separator and misparses (or,
    # more often, safely fails below and is treated as unrecognized
    # provenance rather than corrupting data). Narrow and static -- the
    # writer has emitted JSON-encoded paths since PROVENANCE_FORMAT_REVISION
    # 1 (commit 9c6f7a20), so this fallback only ever reads pre-existing
    # on-disk blocks, never new ones.
    paths: list[tuple[int, str]] = []
    for entry in raw.split("|"):
        step_id_str, sep, path = entry.partition("=")
        step_id = step_id_str.strip()
        if not sep or not _is_ascii_decimal(step_id) or not path:
            return None
        paths.append((int(step_id), path))
    return tuple(paths)


def _is_ascii_decimal(value: str) -> bool:
    """Whether ``value`` is safe for the strict decimal fields we write."""
    return bool(value) and value.isascii() and value.isdecimal()


def _find_trailing_md_provenance_match(text: str) -> "Optional[re.Match[str]]":
    """Locate the real block on a companion story source, never a look-alike.

    :func:`write_markdown_provenance`'s block is always appended as the
    final content of a story file, so a candidate only counts as the real
    block when its closing ``-->`` reaches the end of the text (modulo
    trailing whitespace). Without this, an unanchored search could match
    a provenance-shaped HTML comment that merely appears inside a story's
    own body prose (e.g. one documenting this feature).
    """
    trailing_end = len(text.rstrip())
    match = None
    for candidate in _MD_PROVENANCE_RE.finditer(text):
        match = candidate
    if match is not None and match.end() == trailing_end:
        return match
    return None


_MD_LEADING_TITLE_RE = re.compile(r"\A#[^\n]*\n\n\Z")
_MD_STORY_TITLE_RE = re.compile(r"\A# JIRA stories — [^\n]*\n")


def _find_real_md_provenance_match(text: str) -> "Optional[re.Match[str]]":
    """Locate the writer-placed provenance block, never a look-alike.

    Two document shapes share this reader: a companion story source
    places the block as the file's trailing content (see
    :func:`_find_trailing_md_provenance_match`); a developer handoff
    (:func:`render_handoff`) places it immediately after the title, before
    any of :func:`render_handoff_body`'s content. A candidate counts as
    real only when it matches one of those two exact writer-placed
    positions — a provenance-shaped HTML comment that merely appears
    inside a story's or handoff's own body prose (e.g. documenting this
    feature) matches neither.
    """
    trailing = _find_trailing_md_provenance_match(text)
    if trailing is not None:
        return trailing
    first_match = _MD_PROVENANCE_RE.search(text)
    if first_match is not None and _MD_LEADING_TITLE_RE.match(
        text[: first_match.start()]
    ):
        return first_match
    return None


def read_markdown_story_provenance(text: str) -> Optional[CompanionProvenance]:
    """Read only trailing provenance attached to a generated story source."""
    if (
        not _MD_STORY_TITLE_RE.match(text)
        or _find_trailing_md_provenance_match(text) is None
    ):
        return None
    return read_markdown_provenance(text)


def strip_markdown_provenance(text: str) -> str:
    """Remove companion provenance before parsing Markdown story blocks."""
    match = _find_trailing_md_provenance_match(text)
    if match is None:
        return text.rstrip()
    return text[: match.start()].rstrip()


def read_markdown_provenance(text: str) -> Optional[CompanionProvenance]:
    """Strictly parse a :func:`write_markdown_provenance` block from ``text``.

    Returns ``None`` (never raises) for absent, directly edited, or otherwise
    malformed/incomplete provenance — an unrecognized block never counts
    as generated ownership data.
    """
    match = _find_real_md_provenance_match(text)
    if not match:
        return None
    fields: dict[str, str] = {}
    for line in match.group("body").splitlines():
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        fields[key.strip()] = value.strip()
    if any(key not in fields for key in _REQUIRED_MD_PROVENANCE_KEYS):
        return None
    try:
        provenance_format_revision = int(fields["provenance_format_revision"])
        story_prompt_contract_revision = int(fields["story_prompt_contract_revision"])
        handoff_format_contract_revision = int(
            fields["handoff_format_contract_revision"]
        )
    except ValueError:
        return None
    if provenance_format_revision != PROVENANCE_FORMAT_REVISION:
        return None
    generation_mode = fields["generation_mode"]
    selected_grade = fields["selected_grade"]
    source_plan_path = fields["source_plan_path"]
    fingerprint = fields["fingerprint"]
    story_path = fields["pair_identity_story_path"]
    handoff_path = fields["pair_identity_handoff_path"]
    fmt = fields["pair_identity_format"]
    if not all(
        (generation_mode, selected_grade, source_plan_path, fingerprint, story_path,
         handoff_path, fmt)
    ):
        return None
    detail_paths = _parse_detail_source_paths(fields["selected_detail_source_paths"])
    if detail_paths is None:
        return None
    return CompanionProvenance(
        provenance_format_revision=provenance_format_revision,
        generation_mode=generation_mode,
        selected_grade=selected_grade,
        source_plan_path=source_plan_path,
        selected_detail_source_paths=detail_paths,
        pair_identity=GeneratedSourcePairIdentity(
            story_path=story_path, handoff_path=handoff_path, format=fmt
        ),
        story_prompt_contract_revision=story_prompt_contract_revision,
        handoff_format_contract_revision=handoff_format_contract_revision,
        fingerprint=fingerprint,
    )


# --------------------------------------------------------------------------
# Provenance writers/readers — JSON
# --------------------------------------------------------------------------

_JSON_PROVENANCE_KEY = "plan_tool_companion_provenance"


def write_json_provenance(provenance: CompanionProvenance) -> dict:
    """Build the top-level key a companion-mode JSON story source merges in.

    Merge the returned dict's one key into the story payload — an
    ordinary (non-companion) JSON export never calls this.
    """
    return {
        _JSON_PROVENANCE_KEY: {
            "provenance_format_revision": provenance.provenance_format_revision,
            "generation_mode": provenance.generation_mode,
            "selected_grade": provenance.selected_grade,
            "source_plan_path": provenance.source_plan_path,
            "selected_detail_source_paths": {
                str(step_id): path
                for step_id, path in provenance.selected_detail_source_paths
            },
            "pair_identity": {
                "story_path": provenance.pair_identity.story_path,
                "handoff_path": provenance.pair_identity.handoff_path,
                "format": provenance.pair_identity.format,
            },
            "story_prompt_contract_revision": provenance.story_prompt_contract_revision,
            "handoff_format_contract_revision": (
                provenance.handoff_format_contract_revision
            ),
            "fingerprint": provenance.fingerprint,
        }
    }


def read_json_provenance(payload: "str | dict") -> Optional[CompanionProvenance]:
    """Strictly parse a :func:`write_json_provenance` block.

    ``payload`` may be a JSON document string or an already-parsed dict.
    Returns ``None`` (never raises) for absent or malformed/incomplete
    provenance, including invalid JSON.

    ``selected_detail_source_paths`` round-trips in the dict's own key
    order (which ``write_json_provenance`` writes in the original tuple's
    order) rather than being re-sorted, matching
    :func:`write_markdown_provenance`/:func:`read_markdown_provenance`'s
    write-order-preserving contract for the same field.
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None
    block = payload.get(_JSON_PROVENANCE_KEY)
    if not isinstance(block, dict):
        return None
    # int(...) on a JSON number silently truncates a float (int(1.9) == 1,
    # no error) instead of rejecting it the way the Markdown reader's
    # int(<text>) parse naturally does for a non-integer-looking string --
    # and bool is an int subclass, so int(True) == 1 would separately admit
    # a JSON `true`/`false` as a valid revision. Require each revision field
    # to be an actual int (excluding bool) before parsing, matching the
    # isinstance(..., bool) guard every other int-field validator carries
    # (parse_jira_response's steps check, _parse_detail_source_paths).
    if any(
        not isinstance(block.get(key), int) or isinstance(block.get(key), bool)
        for key in (
            "provenance_format_revision",
            "story_prompt_contract_revision",
            "handoff_format_contract_revision",
        )
    ):
        return None
    try:
        provenance_format_revision = int(block["provenance_format_revision"])
        generation_mode = block["generation_mode"]
        selected_grade = block["selected_grade"]
        source_plan_path = block["source_plan_path"]
        detail_paths_obj = block["selected_detail_source_paths"]
        pair_identity_obj = block["pair_identity"]
        story_prompt_contract_revision = int(block["story_prompt_contract_revision"])
        handoff_format_contract_revision = int(
            block["handoff_format_contract_revision"]
        )
        fingerprint = block["fingerprint"]
    except (KeyError, TypeError, ValueError):
        return None
    if provenance_format_revision != PROVENANCE_FORMAT_REVISION:
        return None
    if not isinstance(detail_paths_obj, dict) or not isinstance(pair_identity_obj, dict):
        return None
    if not all(
        isinstance(v, str) and v
        for v in (generation_mode, selected_grade, source_plan_path, fingerprint)
    ):
        return None
    story_path = pair_identity_obj.get("story_path")
    handoff_path = pair_identity_obj.get("handoff_path")
    fmt = pair_identity_obj.get("format")
    if not all(isinstance(v, str) and v for v in (story_path, handoff_path, fmt)):
        return None
    detail_paths: list[tuple[int, str]] = []
    for key, value in detail_paths_obj.items():
        if (
            not isinstance(key, str)
            or not _is_ascii_decimal(key)
            or not isinstance(value, str)
            or not value
        ):
            return None
        detail_paths.append((int(key), value))
    return CompanionProvenance(
        provenance_format_revision=provenance_format_revision,
        generation_mode=generation_mode,
        selected_grade=selected_grade,
        source_plan_path=source_plan_path,
        selected_detail_source_paths=tuple(detail_paths),
        pair_identity=GeneratedSourcePairIdentity(
            story_path=story_path, handoff_path=handoff_path, format=fmt
        ),
        story_prompt_contract_revision=story_prompt_contract_revision,
        handoff_format_contract_revision=handoff_format_contract_revision,
        fingerprint=fingerprint,
    )


# --------------------------------------------------------------------------
# Handoff rendering
# --------------------------------------------------------------------------


def _stable_committed_order(
    committed_steps: tuple[CommittedStepRenderInput, ...], plan: Plan
) -> list[int]:
    """Topological order over ``committed_steps``, ties broken by ``plan.steps``.

    A dependent listed earlier in ``plan.steps`` than its prerequisite
    still renders after it — only independent steps use plan order.
    """
    order_index = {s.id: i for i, s in enumerate(plan.steps)}
    ids = [ci.id for ci in committed_steps]
    id_set = set(ids)
    deps = {
        step_id: [d for d in plan.step_by_id(step_id).depends_on if d in id_set]
        for step_id in ids
    }
    remaining = set(ids)
    resolved: set[int] = set()
    result: list[int] = []
    while remaining:
        candidates = sorted(
            (i for i in remaining if all(d in resolved for d in deps[i])),
            key=lambda i: order_index[i],
        )
        if not candidates:
            raise HandoffRenderError(
                f"committed steps contain a dependency cycle: {sorted(remaining)}"
            )
        chosen = candidates[0]
        result.append(chosen)
        resolved.add(chosen)
        remaining.discard(chosen)
    return result


def _plan_context_sections(body_text: str) -> dict[str, str]:
    sections = {
        section.name: section.body
        for section in parse_body_sections(body_text, ignore_fenced_code=True)
        if section.body.strip()
    }
    return sections


def _has_scope_or_placement_context(body_text: str) -> bool:
    sections = _plan_context_sections(body_text)
    return any(name.lower() in sections for name in _SCOPE_OR_PLACEMENT_SECTION_NAMES)


def _render_plan_context(body_text: str) -> list[str]:
    sections = _plan_context_sections(body_text)
    lines: list[str] = []
    for name in _PLAN_CONTEXT_SECTION_NAMES:
        body = sections.get(name.lower())
        if body is None:
            continue
        lines.append(f"### {name}")
        lines.append("")
        lines.append(body)
        lines.append("")
    return lines


def _render_file_excerpts(excerpts: tuple[FileExcerptRenderInput, ...]) -> list[str]:
    if not excerpts:
        return ["_(no files declared)_"]
    lines: list[str] = []
    for fc in excerpts:
        if fc.state == FILE_EXCERPT_STATE_MISSING:
            lines.append(f"- `{fc.path}` _(not on disk)_")
        elif fc.state == FILE_EXCERPT_STATE_UNREADABLE:
            lines.append(f"- `{fc.path}` _(unreadable: {fc.error})_")
        else:
            lines.append(f"- `{fc.path}`:")
            lines.append("")
            lines.append(
                f"_excerpt_kind: {fc.excerpt_kind or 'unknown'}; "
                f"fallback_reason: {fc.fallback_reason or 'none'}; "
                f"truncated: {str(fc.truncated).lower()}_"
            )
            lines.append("")
            lines.append(f"```\n{fc.excerpt_text or ''}\n```")
    return lines


_ALTERNATIVE_MECHANISM_NOTE = (
    "_A developer may choose a different compliant mechanism that still "
    "fulfills the plan path above._"
)

_SCOPE_PLACEMENT_PRIORITY_NOTE = (
    "_Scope guardrails and Expected placement in this plan's captured "
    "context win over this suggested route — follow a compliant "
    "alternative when they conflict._"
)


def _render_committed_step(
    step_id: int,
    committed_input: CommittedStepRenderInput,
    plan: Plan,
    *,
    has_scope_or_placement: bool,
) -> list[str]:
    step = plan.step_by_id(step_id)
    title = step.title.strip() or None
    is_done = step.status == StepStatus.DONE
    meaningful_intent = step.intent is not None and not is_placeholder_intent(
        step.intent
    )

    if not is_done and (title is None or not meaningful_intent):
        raise HandoffRenderError(
            f"step {step.id}: committed non-done step requires both a title "
            "and a meaningful intent to render its binding plan path"
        )

    display_title = title or "_(title not recorded)_"
    lines = [f"### Step {step.id} — {display_title}", "", "**Plan path**", ""]
    if is_done:
        lines.append("- Status: done — historical; no implementation action")
    else:
        lines.append(f"- Status: {step.status.value}")
    lines.append(f"- Outcome: {display_title}")
    if meaningful_intent:
        lines.append(f"- Intent: {collapse_intent_to_one_line(step.intent)}")
    else:
        lines.append("- Intent: _(no meaningful intent recorded)_")
    if step.depends_on:
        for dep_id in step.depends_on:
            dep = plan.step_by_id(dep_id)
            lines.append(f"- Depends on: {dep_id} — {dep.title}")
    else:
        lines.append("- Depends on: none")
    lines.append("")

    detail = committed_input.detail
    if is_done:
        if detail.state == DETAIL_STATE_PRESENT:
            lines.append("**Historical implementation context**")
            lines.append("")
            lines.append(
                "_Historical only — this step is already done; nothing here "
                "is a suggested action._"
            )
            lines.append("")
            lines.append(f"_from `{detail.path}`:_")
            lines.append("")
            lines.append(detail.text or "")
        else:
            lines.append(
                "_(no selected detail captured for this historical step)_"
            )
        if committed_input.file_excerpts:
            lines.append("")
            lines.append("**Historical declared files**")
            lines.append("")
            lines.append(
                "_Historical only — these captured excerpts are not a suggested action._"
            )
            lines.append("")
            lines.extend(_render_file_excerpts(committed_input.file_excerpts))
    else:
        lines.append("**Suggested implementation route**")
        lines.append("")
        lines.append(_ALTERNATIVE_MECHANISM_NOTE)
        if has_scope_or_placement:
            lines.append("")
            lines.append(_SCOPE_PLACEMENT_PRIORITY_NOTE)
        lines.append("")
        if detail.state == DETAIL_STATE_PRESENT:
            lines.append(f"_from `{detail.path}`:_")
            lines.append("")
            lines.append(detail.text or "")
        else:
            lines.append("_(no selected detail captured)_")
        lines.append("")
        lines.append("**Declared files**")
        lines.append("")
        lines.extend(_render_file_excerpts(committed_input.file_excerpts))
    return lines


def _render_parked_step(parked: ParkedStepRenderInput) -> str:
    note = parked.status_note or "_(no status note recorded)_"
    return f"- Step {parked.id} — {parked.title} (scope: {parked.scope}) — {note}"


def render_handoff_body(render_input: HandoffRenderInput) -> str:
    """Render the handoff's content — everything except the title and the
    provenance block.

    Never consults an existing story record: a carried or dropped story's
    history can only ever affect :func:`compute_input_fingerprint`, never
    the rendered committed plan path.
    """
    lines: list[str] = []
    context_lines = _render_plan_context(render_input.body_text)
    if context_lines:
        lines.append("## Plan context")
        lines.append("")
        lines.extend(context_lines)

    has_scope_or_placement = _has_scope_or_placement_context(render_input.body_text)

    lines.append("## Plan path")
    lines.append("")
    order = _stable_committed_order(render_input.committed_steps, render_input.plan)
    by_id = {ci.id: ci for ci in render_input.committed_steps}
    for step_id in order:
        lines.extend(
            _render_committed_step(
                step_id,
                by_id[step_id],
                render_input.plan,
                has_scope_or_placement=has_scope_or_placement,
            )
        )
        lines.append("")

    lines.append("## Parked plan history")
    lines.append("")
    if render_input.parked_step_history:
        for parked in render_input.parked_step_history:
            lines.append(_render_parked_step(parked))
    else:
        lines.append("_(none)_")

    return "\n".join(lines).rstrip() + "\n"


def render_handoff(
    render_input: HandoffRenderInput,
    provenance: CompanionProvenance,
    *,
    body: Optional[str] = None,
) -> str:
    """Render the complete Markdown developer handoff.

    A generated-handoff title, a visible provenance block, then
    :func:`render_handoff_body`. Pure: no filesystem reads, model calls,
    or writes.

    ``body`` lets a caller that already computed
    :func:`render_handoff_body` (e.g. to validate it before invoking a
    model) pass it through rather than paying for a second identical
    render — defaults to computing it here when omitted.
    """
    header = [
        f"# Developer handoff — {render_input.plan.title}",
        "",
        write_markdown_provenance(provenance),
        "",
        (
            f"_Generated from `{render_input.source_plan_path}`. This handoff "
            "follows the committed plan path in dependency order. Suggested "
            "implementation routes are non-binding — a developer may choose "
            "any compliant mechanism that still fulfills the plan path._"
        ),
        "",
    ]
    return "\n".join(header) + (
        body if body is not None else render_handoff_body(render_input)
    )
