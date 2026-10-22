"""Read, validate, and round-trip plan markdown files.

A plan file is a markdown document whose first bytes are a YAML frontmatter block
delimited by `---` lines. The rest of the file is prose: structural readers may
inspect its H2 sections, but it is not schema-validated or reserialized.

The round-trip writer preserves the prose body byte-for-byte. Only the frontmatter
block is reserialized, so edits to step status land cleanly without reformatting
the body. The frontmatter itself is reformatted by PyYAML's default style — if you
want to preserve comments or ordering within frontmatter, author the plan with the
format you want and let round-trips overwrite it predictably.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError as PydanticValidationError

from plan_tool.schema import (
    PLAN_FORMAT_VERSION,
    Plan,
    Step,
    SUPPORTED_PLAN_FORMAT_VERSIONS,
)
from plan_tool.scope_fence import _excise_fenced_code, _fenced_code_spans


class ParseError(Exception):
    """Raised when a plan file does not contain a well-formed frontmatter block."""


class ConcurrentModificationError(RuntimeError):
    """Raised when a plan's frontmatter changed on disk since it was parsed.

    :func:`write_plan` is compare-and-swap: it refuses to overwrite a plan
    whose on-disk frontmatter no longer matches what :func:`parse_plan`
    last read for that path in this process, so a concurrent edit (the
    operator's editor, a ``git checkout``, another process) is never
    silently clobbered by a stale in-memory snapshot. The fix is to
    re-read the plan and re-apply the intended change to the fresh copy.
    Deliberately NOT a subclass of :class:`ParseError` / :class:`ValidationError`
    so the ``except (ParseError, ValidationError)`` blocks scattered across
    callers don't swallow it.
    """


# Per-process provenance: resolved-plan-path → sha256 of the frontmatter
# block ``parse_plan`` (or the last ``write_plan``) observed for it. Only
# the frontmatter is hashed — ``write_plan`` already splices the new
# frontmatter onto the *current* on-disk body, so a concurrent body edit
# is preserved and must not trip the guard. Best-effort: a path never
# parsed in-process has no entry and writes through unchecked (it can't
# have a "changed since we read it" problem if we never read it).
_FRONTMATTER_PROVENANCE: dict[str, str] = {}


def _frontmatter_hash(frontmatter_yaml: str) -> str:
    return hashlib.sha256(frontmatter_yaml.encode("utf-8")).hexdigest()


class ValidationError(Exception):
    """Raised when frontmatter YAML fails to validate against the Plan schema.

    Carries the structured pydantic errors in ``.errors`` (possibly empty) so
    callers can render a concise summary via :func:`format_validation_errors`.
    ``str()`` is unchanged — it remains the verbose pydantic dump that most
    call sites surface directly.
    """

    def __init__(
        self, message: str, *, errors: list[dict[str, Any]] | None = None
    ) -> None:
        super().__init__(message)
        self.errors: list[dict[str, Any]] = errors or []


def format_validation_errors(errors: list[dict[str, Any]]) -> list[str]:
    """Render pydantic structured errors as concise, human-readable lines.

    Strips the boilerplate that ``str(PydanticValidationError)`` carries — the
    ``"N validation errors for Plan"`` header, the ``[type=..., input_value=...]``
    annotations, and the ``errors.pydantic.dev`` URL — leaving ``field: message``
    (or just ``message`` for model-level validators that have no field location).

    ``extra_forbidden`` errors get special treatment: pydantic's stock
    "Extra inputs are not permitted" hides *where* the stray field sits and
    *what* would be valid there, so we rewrite it to name the unknown field's
    container and list the allowed fields — and, when the field is real but
    misplaced (e.g. a top-level ``depends_on``, which is a step field), say so.
    """
    lines: list[str] = []
    for err in errors:
        loc_parts = tuple(err.get("loc", ()))
        loc = ".".join(str(p) for p in loc_parts)
        if err.get("type") == "extra_forbidden":
            lines.append(f"{loc}: {_explain_extra_field(loc_parts)}")
            continue
        msg = str(err.get("msg", "invalid")).removeprefix("Value error, ")
        if (
            err.get("type") == "missing"
            and len(loc_parts) == 3
            and loc_parts[0] == "steps"
            and isinstance(loc_parts[1], int)
            and loc_parts[2] == "title"
        ):
            loc = f"steps.{loc_parts[1]}.description"
            msg = "Field required (legacy title is also accepted)"
        lines.append(f"{loc}: {msg}" if loc else msg)
    return lines


def _explain_extra_field(loc_parts: tuple[Any, ...]) -> str:
    """Build an actionable message for a forbidden (unknown) field.

    Determines the field's container from its location — anything under
    ``steps`` is step-level, otherwise plan-level — then lists that
    container's valid fields. If the field is actually defined on the *other*
    container, append a hint pointing the author there.
    """
    field = str(loc_parts[-1]) if loc_parts else ""
    is_step = any(str(p) == "steps" for p in loc_parts[:-1])
    here, here_fields = ("step", Step) if is_step else ("plan-level", Plan)
    allowed_fields = list(here_fields.model_fields)
    if is_step:
        allowed_fields.insert(allowed_fields.index("title"), "description")
    allowed = ", ".join(allowed_fields)
    msg = f"unknown {here} field (allowed: {allowed})"
    other_fields = Plan if is_step else Step
    if field in other_fields.model_fields or (
        other_fields is Step and field == "description"
    ):
        where = "the plan level" if is_step else "a step"
        msg += f"; {field} belongs on {where}"
    return msg


@dataclass
class _Split:
    frontmatter_yaml: str
    body: str


_FENCE = "---"


@dataclass(frozen=True)
class BodySection:
    """One H2 plan-body section in source order."""

    name: str
    heading: str
    body: str
    order: int


@dataclass(frozen=True)
class PlanDocument:
    """The lossless source components surrounding a validated plan."""

    frontmatter_yaml: str
    body: str


def split_plan_document(text: str) -> PlanDocument:
    """Split complete plan Markdown without normalizing either component."""
    split = _split_frontmatter(text)
    return PlanDocument(split.frontmatter_yaml, split.body)


def _split_frontmatter(text: str) -> _Split:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != _FENCE:
        raise ParseError(
            "plan file must begin with a '---' frontmatter fence on line 1"
        )

    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == _FENCE:
            fm = "".join(lines[1:i])
            body = "".join(lines[i + 1 :])
            return _Split(frontmatter_yaml=fm, body=body)

    raise ParseError("plan file opens with '---' but has no closing fence")


def _is_outside_spans(
    offset: int, spans: tuple[tuple[int, int], ...]
) -> bool:
    """Return whether ``offset`` belongs to source outside fenced code."""
    return not any(start <= offset < end for start, end in spans)


def _real_h2_matches(
    body: str,
    *,
    ignore_fenced_code: bool,
    spans: tuple[tuple[int, int], ...] | None = None,
) -> list[re.Match[str]]:
    """Return H2 matches, optionally excluding fenced pseudo-headings.

    Heading whitespace is ``[ \\t]``, not ``\\s`` — ``\\s`` spans newlines, so
    a bare ``##`` line immediately followed by a real ``## Heading`` would
    otherwise merge into one corrupted match spanning both lines.

    ``spans`` lets a caller that already computed ``_fenced_code_spans(body)``
    for its own filtering (e.g. :func:`parse_body_sections`'s ``higher_matches``
    pass) reuse it here instead of re-scanning the same body a second time.
    """
    matches = list(re.finditer(r"^##[ \t]+(.+?)[ \t]*$", body, re.MULTILINE))
    if not ignore_fenced_code:
        return matches
    if spans is None:
        spans = _fenced_code_spans(body).spans
    return [match for match in matches if _is_outside_spans(match.start(), spans)]


def parse_body_sections(
    body: str,
    *,
    ignore_fenced_code: bool = False,
    strip_fenced_code: bool = False,
) -> list[BodySection]:
    """Return H2 sections with normalized names and source ordering.

    ``ignore_fenced_code`` prevents fenced H1/H2-looking lines from defining
    boundaries while retaining their source text in a real section body.
    ``strip_fenced_code`` also removes fenced text and implies boundary safety.
    """
    if not body:
        return []

    if strip_fenced_code:
        body = _excise_fenced_code(body)
        ignore_fenced_code = True

    higher_re = re.compile(r"^(#|##)\s+", re.MULTILINE)
    spans = _fenced_code_spans(body).spans if ignore_fenced_code else ()
    h2_matches = _real_h2_matches(
        body, ignore_fenced_code=ignore_fenced_code, spans=spans
    )
    higher_matches = list(higher_re.finditer(body))
    if ignore_fenced_code:
        higher_matches = [
            match
            for match in higher_matches
            if _is_outside_spans(match.start(), spans)
        ]

    sections: list[BodySection] = []
    for order, match in enumerate(h2_matches):
        heading = match.group(1).strip()
        section_start = match.end()
        next_match = next(
            (candidate for candidate in higher_matches if candidate.start() >= section_start),
            None,
        )
        section_end = next_match.start() if next_match else len(body)
        sections.append(
            BodySection(
                name=heading.rstrip(":.").lower(),
                heading=heading,
                body=body[section_start:section_end].strip("\n"),
                order=order,
            )
        )
    return sections


def split_body_sections(
    body: str,
    *,
    ignore_fenced_code: bool = False,
    strip_fenced_code: bool = False,
) -> dict[str, str]:
    """Map H2 section name -> section body text (heading line excluded).

    Keys are lowercased and stripped of trailing whitespace so callers
    can do case-insensitive lookups. The body for each section runs from
    the line *after* its heading up to (but not including) the next
    H2 / H1, or EOF. Pass ``ignore_fenced_code=True`` to keep fenced H1/H2
    examples from defining those boundaries; pass ``strip_fenced_code=True``
    to omit fenced examples from returned bodies as well.

    A heading like ``## Acceptance criteria`` keys as
    ``"acceptance criteria"`` (full first-line text after the ``## ``
    prefix). Trailing punctuation is trimmed so ``## Risks:`` and
    ``## Risks`` collide on the same key.
    """
    return {
        section.name: section.body
        for section in parse_body_sections(
            body,
            ignore_fenced_code=ignore_fenced_code,
            strip_fenced_code=strip_fenced_code,
        )
    }


def replace_body_sections(
    body: str,
    replacements: dict[str, str],
    *,
    section_order: tuple[str, ...] = ("deferred", "out of scope"),
    ignore_fenced_code: bool = False,
) -> str:
    """Replace selected H2 bodies while preserving every unowned byte.

    Replacement keys use the same normalization as :func:`parse_body_sections`.
    ``ignore_fenced_code`` limits selection and replacement boundaries to real
    H2 headings without changing any unowned source text.
    A missing section is appended in ``section_order`` only when its replacement
    is non-empty; an absent empty section remains absent.
    """
    normalized = {name.rstrip(":.").lower(): value for name, value in replacements.items()}
    matches = _real_h2_matches(body, ignore_fenced_code=ignore_fenced_code)
    pieces: list[str] = []
    cursor = 0
    found: set[str] = set()
    for index, match in enumerate(matches):
        name = match.group(1).strip().rstrip(":.").lower()
        if name not in normalized:
            continue
        section_end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        pieces.append(body[cursor : match.end()])
        replacement = normalized[name]
        pieces.append(f"\n\n{replacement.rstrip()}\n" if replacement else "\n")
        cursor = section_end
        found.add(name)
    pieces.append(body[cursor:])
    updated = "".join(pieces)
    for name in section_order:
        if name in normalized and name not in found and normalized[name]:
            if updated and not updated.endswith("\n"):
                updated += "\n"
            if updated and not updated.endswith("\n\n"):
                updated += "\n"
            heading = "Out of scope" if name == "out of scope" else name.title()
            updated += f"## {heading}\n\n{normalized[name].rstrip()}\n"
    return updated


def _stamp_current_format_version(
    plan: Plan, dumped: dict[str, Any]
) -> dict[str, Any]:
    """Inject the current format declaration, or refuse an ineligible plan.

    A writer emits ``PLAN_FORMAT_VERSION`` only — never a value merely in
    ``SUPPORTED_PLAN_FORMAT_VERSIONS`` — so rewriting a current-minus-one
    plan never silently relabels it as current; it must take its explicit
    raw upgrade first. Returns a new mapping with ``format_version`` first,
    so a human skimming the rendered YAML sees it ahead of every other key.
    """
    if plan.format_version != PLAN_FORMAT_VERSION:
        raise ValidationError(
            f"cannot serialize a plan with effective format_version="
            f"{plan.format_version!r}; this build writes only "
            f"format_version={PLAN_FORMAT_VERSION!r} — the plan needs its "
            f"explicit raw-format upgrade before it can be rewritten"
        )
    return {"format_version": PLAN_FORMAT_VERSION, **dumped}


def _prefer_step_description(dumped: dict[str, Any]) -> None:
    """Translate only authored step text; internal dumps keep their title keys."""
    for step in dumped.get("steps", []):
        step["description"] = step.pop("title")


def render_plan_text(plan: Plan, body: str) -> str:
    """Validate ``plan`` and render complete Markdown around ``body``.

    Always stamps the current ``format_version`` declaration; refuses to
    render a plan whose effective version isn't current.
    """
    dumped = plan.model_dump(exclude_defaults=True, exclude_none=True)
    try:
        Plan.model_validate(dumped)
    except PydanticValidationError as exc:
        raise ValidationError(str(exc), errors=exc.errors()) from exc
    dumped = _stamp_current_format_version(plan, dumped)
    _prefer_step_description(dumped)
    new_fm = yaml.safe_dump(
        _coerce_enums(dumped), default_flow_style=False, sort_keys=False,
        allow_unicode=True,
    )
    return f"{_FENCE}\n{new_fm}{_FENCE}\n{body}"


def refresh_plan_provenance(path: str | Path, text: str) -> None:
    """Record ``text`` as the last frontmatter published for ``path``."""
    key = str(Path(path).resolve())
    try:
        _FRONTMATTER_PROVENANCE[key] = _frontmatter_hash(
            _split_frontmatter(text).frontmatter_yaml
        )
    except Exception:  # noqa: BLE001 - provenance must never mask publication
        _FRONTMATTER_PROVENANCE.pop(key, None)


def _coerce_enums(data: Any) -> Any:
    """Recursively convert enum instances to their string values for yaml.safe_dump.

    This is load-bearing, not cosmetic. Even though our enums inherit from `str`,
    PyYAML's SafeDumper has no representer for Enum subclasses and raises
    `RepresenterError: cannot represent an object` when it encounters one. Do not
    remove without replacing with a custom yaml representer.
    """
    if isinstance(data, Enum):
        return data.value
    if isinstance(data, dict):
        return {k: _coerce_enums(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_coerce_enums(v) for v in data]
    return data


class UnsupportedPlanFormatVersionError(ValidationError):
    """Raised when a plan declares an unsupported ``format_version``."""


# Declaration-free legacy plans remain version 1 after current advances.
_LEGACY_PLAN_FORMAT_VERSION = 1


def _require_supported_plan_format_version(raw: dict[str, Any]) -> int:
    """Return an effective version or refuse an unsupported declaration."""
    declared = raw.get("format_version", _LEGACY_PLAN_FORMAT_VERSION)
    # bool is an int subclass, but never a valid format version.
    if type(declared) is not int or declared not in SUPPORTED_PLAN_FORMAT_VERSIONS:
        raise UnsupportedPlanFormatVersionError(
            f"plan declares format_version={declared!r}, which this build "
            f"does not support (supported: {sorted(SUPPORTED_PLAN_FORMAT_VERSIONS)})"
        )
    return declared


def upgrade_plan_frontmatter_to_current(raw: dict[str, Any]) -> dict[str, Any]:
    """Upgrade raw plan frontmatter; refuse malformed or unsupported states."""
    _require_supported_plan_format_version(raw)
    declared = raw.get("format_version")
    if declared is None:
        return {"format_version": PLAN_FORMAT_VERSION, **raw}
    if declared == PLAN_FORMAT_VERSION:
        return dict(raw)
    raise NotImplementedError(
        f"no upgrade path is declared for plan format_version={declared!r}; "
        "add one before adding it to SUPPORTED_PLAN_FORMAT_VERSIONS"
    )


def parse_plan_text(text: str) -> Plan:
    """Parse a full plan file (frontmatter + body) from a string.

    Validation is deliberately self-contained: concept ownership ids are
    shape-checked by ``Step``, but record membership requires external context.

    Raises ``UnsupportedPlanFormatVersionError`` before schema validation.
    """
    split = _split_frontmatter(text)
    try:
        raw = yaml.safe_load(split.frontmatter_yaml)
    except (yaml.YAMLError, ValueError) as exc:
        raise ParseError(f"invalid YAML in frontmatter: {exc}") from exc
    if not isinstance(raw, dict):
        raise ParseError(
            f"frontmatter must be a YAML mapping, got {type(raw).__name__}"
        )
    raw["format_version"] = _require_supported_plan_format_version(raw)
    try:
        return Plan.model_validate(raw)
    except PydanticValidationError as exc:
        raise ValidationError(str(exc), errors=exc.errors()) from exc


def parse_plan(path: str | Path) -> Plan:
    """Parse a plan file from disk.

    Records the file's frontmatter hash as write-back provenance so a
    later :func:`write_plan` can detect a concurrent on-disk edit (see
    :class:`ConcurrentModificationError`).
    """
    p = Path(path)
    text = p.read_bytes().decode("utf-8")
    plan = parse_plan_text(text)
    try:
        _FRONTMATTER_PROVENANCE[str(p.resolve())] = _frontmatter_hash(
            _split_frontmatter(text).frontmatter_yaml
        )
    except Exception:  # noqa: BLE001 — provenance is best-effort, never block a parse
        pass
    return plan


def write_plan(
    path: str | Path, plan: Plan, *, expect_unchanged: bool = True
) -> None:
    """Write `plan` back to `path`, preserving the prose body byte-for-byte.

    The frontmatter is reserialized from the Plan model using PyYAML's default
    block style. Fields unset in the model (defaults) are elided to keep the
    output small and legible — except ``format_version``, always stamped
    explicitly with the current declaration rather than left to elision.

    The plan is re-validated before writing. Pydantic does not re-run model
    validators when fields are mutated post-construction, so a caller could
    produce an invalid state (e.g. two steps marked `current`) and serialize it
    otherwise. Re-validation ensures the on-disk plan always satisfies the schema
    — raises `ValidationError` if the in-memory mutation violated an invariant.

    Compare-and-swap: when ``expect_unchanged`` (the default) and this path
    was parsed in-process, the on-disk frontmatter must still match what
    :func:`parse_plan` last read — otherwise a concurrent edit happened and
    this write would clobber it, so :class:`ConcurrentModificationError` is
    raised instead. Re-``parse_plan`` the file and re-apply the change to
    pick up the edit. Pass ``expect_unchanged=False`` to force the write
    (e.g. an intentional overwrite that supersedes whatever is on disk).
    Body-only edits never trip this — only the frontmatter is compared,
    and the body below is always taken from the current on-disk file.
    """
    p = Path(path)
    original = p.read_bytes().decode("utf-8")
    split = _split_frontmatter(original)

    key = str(p.resolve())
    if expect_unchanged and key in _FRONTMATTER_PROVENANCE:
        if _frontmatter_hash(split.frontmatter_yaml) != _FRONTMATTER_PROVENANCE[key]:
            raise ConcurrentModificationError(
                f"{p}: frontmatter changed on disk since it was last read "
                f"(concurrent edit); refusing to overwrite and lose that "
                f"change. Re-read the plan and re-apply, or pass "
                f"expect_unchanged=False to force the write."
            )

    dumped = plan.model_dump(exclude_defaults=True, exclude_none=True)
    try:
        Plan.model_validate(dumped)
    except PydanticValidationError as exc:
        raise ValidationError(str(exc), errors=exc.errors()) from exc
    dumped = _stamp_current_format_version(plan, dumped)
    _prefer_step_description(dumped)
    dumped = _coerce_enums(dumped)

    new_fm = yaml.safe_dump(
        dumped,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    new_text = f"{_FENCE}\n{new_fm}{_FENCE}\n{split.body}"
    p.write_bytes(new_text.encode("utf-8"))
    # Refresh provenance to what we just wrote so a subsequent in-process
    # write from the same parse doesn't false-trip on our own change.
    # Hash via _split_frontmatter (not raw new_fm) so it matches exactly
    # what the next parse_plan will read back from new_text.
    try:
        _FRONTMATTER_PROVENANCE[key] = _frontmatter_hash(
            _split_frontmatter(new_text).frontmatter_yaml
        )
    except Exception:  # noqa: BLE001 — provenance is best-effort
        _FRONTMATTER_PROVENANCE.pop(key, None)
