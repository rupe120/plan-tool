"""Classify how much of an arbitrary plan/notes file is already implemented.

`classify_plan_implementation` ingests a free-form plan or notes file,
code-grounds it against the current repo, and asks Claude for a
per-section verdict — IMPLEMENTED / PARTIAL / NOT-IMPLEMENTED /
NEEDS-REVIEW — backed by concrete code references. The deliverable is the
:class:`PlanAnnotation`
contract (verbatim source text plus a :class:`SectionAnnotation` list)
that the step-2 renderers consume; this module renders nothing and wires
no CLI.

It reuses the verified `--from-existing` anchors verbatim:
:func:`plan_tool.create.read_existing_description` for ingestion,
:func:`plan_tool.create.extract_file_path_candidates` +
:func:`plan_tool.locator.find_umbrella_root` for grounding, and
:func:`plan_tool.renderer.prompts_dir` + ``string.Template`` for the
prompt. The one new Claude seam is ``prompts/annotate.md`` plus its
overridable :func:`shell_annotate_invoker` default — the autouse gate in
``tests/conftest.py`` raises if a test forgets to override it.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from string import Template
from typing import Callable, Optional

from plan_tool.backend import spawn_cwd_from_repo_root
from plan_tool.create import (
    CreateError,  # noqa: F401 — re-exported for callers/tests; raised by read_existing_description
    extract_file_path_candidates,
    read_existing_description,
)
from plan_tool.detail_artifacts import (
    DetailFormatError,
    require_supported_detail_format_version,
)
from plan_tool.locator import find_umbrella_root
from plan_tool.parser import UnsupportedPlanFormatVersionError, parse_plan_text
from plan_tool.prompt_excerpt import build_prompt_excerpt
from plan_tool.renderer import prompts_dir
from plan_tool.response_contract import JSON_ROOT_ARRAY, JsonResponseContract
from plan_tool.schema import Plan
from plan_tool.shell import claude_invoke


AnnotateInvoker = Callable[[str], str]

# Per-file byte bound for code/spec injected into the annotate prompt.
# This surface owns its cap even though other prompts use the same effective
# default.
_MAX_GROUND_FILE_BYTES = 4096
_GROUNDING_FLOOR_FILE_COUNT = 3
_MAX_GROUNDING_SYMBOL_CANDIDATES = 80
_CODE_REF_RE = re.compile(
    r"^(?P<path>[^:\s]+):(?P<anchor>\d+|[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)$"
)
_ANNOTATE_RESPONSE_CONTRACT = JsonResponseContract(
    root=JSON_ROOT_ARRAY,
    # Show every model-emittable status; NEEDS-REVIEW remains parser-derived.
    example=[{
        "heading": "section heading",
        "status": "IMPLEMENTED",
        "evidence": "one to three sentence justification",
        "code_refs": ["path:symbol"],
        "remaining": "",
        "confidence_low": False,
        "is_step": False,
    }, {
        "heading": "a partially done section",
        "status": "PARTIAL",
        "evidence": "one to three sentence justification",
        "code_refs": ["path:symbol"],
        "remaining": "the not-yet-implemented remainder, 1-2 sentences",
        "confidence_low": False,
        "is_step": False,
    }, {
        "heading": "a section with no matching code",
        "status": "NOT-IMPLEMENTED",
        "evidence": "one to three sentence justification",
        "code_refs": [],
        "remaining": "",
        "confidence_low": False,
        "is_step": False,
    }],
)


class AnnotateError(Exception):
    """Raised when annotate cannot turn a source or response into a result.

    Definitive resolver over a caller-supplied real path, so a bad
    response surfaces rather than being swallowed into an empty result.
    """


class AnnotationStatus(str, Enum):
    """Per-section implementation verdict, with the wire strings the prompt emits.

    Subclasses ``str`` so the value JSON round-trips and renderers can
    compare against the literal without ``.value``.
    """

    IMPLEMENTED = "IMPLEMENTED"
    PARTIAL = "PARTIAL"
    NOT_IMPLEMENTED = "NOT-IMPLEMENTED"
    NEEDS_REVIEW = "NEEDS-REVIEW"


_MODEL_RESPONSE_STATUSES = frozenset(
    {
        AnnotationStatus.IMPLEMENTED,
        AnnotationStatus.PARTIAL,
        AnnotationStatus.NOT_IMPLEMENTED,
    }
)


@dataclass(frozen=True)
class SectionAnnotation:
    """One judged section of the ingested plan/notes file.

    ``code_refs`` are concrete ``path:symbol`` / ``path:line`` anchors —
    expected non-empty for IMPLEMENTED/PARTIAL, empty for NOT-IMPLEMENTED,
    and allowed for NEEDS-REVIEW. An IMPLEMENTED/PARTIAL verdict without
    resolvable refs is demoted to ``low_confidence`` (see
    :func:`_parse_annotation_response`), not rejected. For PARTIAL the refs
    name the already-implemented portion and ``remaining_work`` states the
    not-yet-implemented remainder (the only part step 2's seed renderer
    scopes forward). ``is_step`` is ``True`` when the section is a
    frontmatter ``steps:`` entry, so its ``heading`` is the step's YAML
    ``description:`` or legacy ``title:`` text (no markdown heading line).
    """

    heading: str
    status: AnnotationStatus
    evidence: str
    code_refs: tuple[str, ...] = ()
    remaining_work: str = ""
    low_confidence: bool = False
    is_step: bool = False
    contradiction_review: bool = False
    low_grounding: bool = False


@dataclass(frozen=True)
class PlanAnnotation:
    """The whole classification result step 2's renderers walk.

    ``source_text`` is the ingested file verbatim — load-bearing, because
    step 2's additive-guarantee test diffs the original against the
    rendered report, so the original travels inside the result rather than
    being re-read. ``repo_root`` is the umbrella root the grounding
    actually resolved to (may differ from the caller's when the plan spans
    repos). ``grounded_files`` are the candidate files that resolved on
    disk and were fed to the prompt (empty when none resolved — itself a
    strong NOT-IMPLEMENTED signal). ``grounding_candidate_count`` and
    ``grounding_skipped_count`` summarize candidate-path handling;
    ``grounding_skip_reasons`` names skipped candidates, including binary
    files that were deliberately kept out of the prompt.
    """

    source_path: Path
    source_text: str
    repo_root: Path
    grounded_files: tuple[Path, ...]
    sections: tuple[SectionAnnotation, ...]
    low_grounding: bool = False
    annotated_at: str = ""
    grounding_candidate_count: int = 0
    grounding_skipped_count: int = 0
    grounding_skip_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class GroundedSource:
    """Resolved annotate grounding plus candidate/skip accounting."""

    repo_root: Path
    files: tuple[tuple[Path, str], ...]
    candidate_count: int
    skipped_count: int
    skip_reasons: tuple[str, ...]


def shell_annotate_invoker(prompt: str) -> str:
    """Production invoker: run ``claude -p`` and capture stdout.

    Mirrors :func:`plan_tool.detail.shell_detail_invoker`. The autouse
    gate in ``tests/conftest.py`` raises if a test reaches this without
    overriding ``invoker=``.
    """
    _, stdout = claude_invoke(prompt)
    return stdout


def render_annotate_prompt(
    source_text: str, step_specs_block: str, grounded_files_block: str
) -> str:
    """Render ``prompts/annotate.md`` with the three named placeholders.

    Uses ``safe_substitute`` (not ``substitute``) so a stray ``$`` in the
    ingested prose, loaded spec, or grounded code can't raise — matches
    :func:`plan_tool.detail.render_detail_prompt`. ``step_specs_block`` is
    rendered distinct from ``grounded_files_block`` so the prompt judges
    each step against its real ``detail:`` spec, never mistaking a spec
    file for code evidence.
    """
    template_path = prompts_dir() / "annotate.md"
    return Template(template_path.read_text(encoding="utf-8")).safe_substitute(
        source_body=source_text,
        step_specs_block=step_specs_block,
        grounded_files_block=grounded_files_block,
        response_format_block=_ANNOTATE_RESPONSE_CONTRACT.render_prompt_block(),
    )


def _try_parse_plan(source_text: str) -> Optional[Plan]:
    """Parse ``source_text`` as a plan-tool plan, or ``None`` for non-plan input.

    Unsupported declared versions are structured-plan failures, not notes.
    """
    try:
        return parse_plan_text(source_text)
    except UnsupportedPlanFormatVersionError as exc:
        raise AnnotateError(str(exc)) from exc
    except Exception:
        return None


def _bound_for_block(body: str, max_file_bytes: int) -> str:
    """Cap spec/detail ``body`` at ``max_file_bytes`` chars.

    The label tells the prompt to set ``confidence_low`` rather than
    assume a symbol past the cut is absent. Source grounding uses
    ``build_prompt_excerpt`` instead.
    """
    if len(body) <= max_file_bytes:
        return body
    note = f"[truncated to first {max_file_bytes} bytes — symbols past the cut may exist]"
    return f"{note}\n{body[:max_file_bytes]}"


def _load_step_specs(
    source_text: str,
    *,
    repo_root: Path,
    max_file_bytes: int = _MAX_GROUND_FILE_BYTES,
) -> tuple[tuple[str, str], ...]:
    """Load each frontmatter step's ``detail:`` body as the spec to judge.

    Returns ``(title, spec_body)`` pairs — ``spec_body`` is the ``detail:``
    file's bounded text read from ``repo_root / step.detail``, or ``""``
    when the entry has no ``detail:`` or the file is absent. Returns ``()``
    when the input has no parseable ``steps:`` block (the rough-notes /
    non-plan path), so the prompt sees no spec block.
    """
    plan = _try_parse_plan(source_text)
    if plan is None:
        return ()
    out: list[tuple[str, str]] = []
    for step in plan.steps:
        spec_body = ""
        if step.detail:
            detail_path = repo_root / step.detail
            if detail_path.is_file():
                try:
                    body = detail_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    spec_body = ""
                else:
                    try:
                        require_supported_detail_format_version(
                            body, path=detail_path
                        )
                    except DetailFormatError as exc:
                        raise AnnotateError(str(exc)) from exc
                    spec_body = _bound_for_block(body, max_file_bytes)
        out.append((step.title, spec_body))
    return tuple(out)


def _resolved_detail_paths(
    source_text: str, *, repo_root: Path
) -> frozenset[Path]:
    """Resolved ``detail:`` spec paths for the plan's steps (empty for non-plan).

    Passed to :func:`_ground_source` as ``exclude`` so the plan's own spec
    files are judged as spec (via :func:`_load_step_specs`), never injected
    into the grounded-code block — which would bias every step toward
    IMPLEMENTED because the spec exists on disk.
    """
    plan = _try_parse_plan(source_text)
    if plan is None:
        return frozenset()
    paths: set[Path] = set()
    for step in plan.steps:
        if step.detail:
            paths.add((repo_root / step.detail).resolve())
    return frozenset(paths)


def _format_step_specs_block(specs: tuple[tuple[str, str], ...]) -> str:
    """Render the loaded step specs as a fenced, title-labelled block."""
    if not specs:
        return "_no plan-step specs (the input is not a plan-tool plan)_"
    out: list[str] = []
    for title, body in specs:
        if body:
            out.append(f"### {title}\n\n```\n{body}\n```\n")
        else:
            out.append(f"### {title}\n\n_(no `detail:` spec on disk)_\n")
    return "\n".join(out)


def _read_grounding_text(path: Path) -> str:
    """Read a grounding file as strict UTF-8 text, rejecting binary payloads."""
    raw = path.read_bytes()
    if b"\0" in raw:
        raise ValueError("grounding skipped binary file")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("grounding skipped binary file") from exc


def _derive_grounding_symbols(source_text: str) -> tuple[str, ...]:
    """Return conservative symbol candidates for annotate grounding excerpts."""
    from plan_tool.review import _derive_symbols

    plan = _try_parse_plan(source_text)
    surfaces: list[str] = []
    if plan is not None:
        surfaces.extend(step.title for step in plan.steps)
    surfaces.extend(_grounding_symbol_surfaces_from_notes(source_text))

    out: list[str] = []
    seen: set[str] = set()
    for surface in surfaces:
        for symbol in _derive_symbols(surface):
            key = symbol.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(symbol)
            if len(out) >= _MAX_GROUNDING_SYMBOL_CANDIDATES:
                return tuple(out)
    return tuple(out)


def _grounding_symbol_surfaces_from_notes(source_text: str) -> tuple[str, ...]:
    """Collect compact note surfaces likely to name implementation symbols."""
    lines = source_text.splitlines()
    surfaces: list[str] = []
    path_line_indexes: set[int] = set()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r"#{1,6}\s+\S", stripped):
            surfaces.append(stripped.lstrip("#").strip())
        if extract_file_path_candidates(line):
            path_line_indexes.update(
                i for i in range(index - 1, index + 2) if 0 <= i < len(lines)
            )

    for index in sorted(path_line_indexes):
        stripped = lines[index].strip()
        if stripped:
            surfaces.append(stripped)
    return tuple(surfaces)


def _repo_relative_excerpt_path(path: Path, *, repo_root: Path) -> str:
    """Return a stable path string for prompt excerpt language detection."""
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _ground_source(
    source_text: str,
    *,
    repo_root: Path,
    max_file_bytes: int,
    exclude: frozenset[Path] = frozenset(),
) -> GroundedSource:
    """Resolve cited files against the repo and return grounded text + counts.

    Candidates are resolved against ``repo_root`` — the same search base
    :func:`find_umbrella_root` uses internally — so grounding sees exactly
    the files the umbrella widening saw. An unresolved ref is skipped
    without failing (a NOT-IMPLEMENTED signal, not an error), as is any
    path in ``exclude`` (the plan's own ``detail:`` spec files). Binary
    files are skipped with an explicit reason so raw decode ``ValueError``
    details never reach callers. The returned umbrella is the widened root
    the plan actually spans.
    """
    candidates = extract_file_path_candidates(source_text)
    umbrella = (
        find_umbrella_root(candidates, search_from=repo_root, fallback=repo_root)
        or repo_root
    )
    grounded: list[tuple[Path, str]] = []
    skip_reasons: list[str] = []
    seen: set[Path] = set()
    candidate_symbols = _derive_grounding_symbols(source_text)
    for candidate in candidates:
        base = candidate if candidate.is_absolute() else (repo_root / candidate)
        try:
            resolved = base.resolve()
        except OSError:
            skip_reasons.append(f"{candidate}: grounding skipped unresolved file")
            continue
        if resolved in seen:
            skip_reasons.append(f"{candidate}: grounding skipped duplicate file")
            continue
        if resolved in exclude:
            skip_reasons.append(f"{candidate}: grounding skipped plan detail file")
            continue
        if not resolved.is_file():
            skip_reasons.append(f"{candidate}: grounding skipped unresolved file")
            continue
        seen.add(resolved)
        try:
            body = _read_grounding_text(resolved)
        except OSError:
            skip_reasons.append(f"{candidate}: grounding skipped unreadable file")
            continue
        except ValueError:
            skip_reasons.append(f"{candidate}: grounding skipped binary file")
            continue
        excerpt = build_prompt_excerpt(
            _repo_relative_excerpt_path(resolved, repo_root=umbrella),
            body,
            candidate_symbols,
            max_bytes=max_file_bytes,
        )
        metadata = (
            f"excerpt_kind={excerpt.excerpt_kind}; "
            f"fallback_reason={excerpt.fallback_reason or 'none'}; "
            f"truncated={str(excerpt.truncated).lower()}"
        )
        grounded.append((resolved, f"{metadata}\n{excerpt.text}"))
    return GroundedSource(
        repo_root=umbrella,
        files=tuple(grounded),
        candidate_count=len(candidates),
        skipped_count=len(skip_reasons),
        skip_reasons=tuple(skip_reasons),
    )


def _format_grounded_block(grounded: tuple[tuple[Path, str], ...]) -> str:
    """Render the grounded code as a fenced, path-labelled block."""
    if not grounded:
        return "_no cited files resolved on disk — strong NOT-IMPLEMENTED signal_"
    out: list[str] = []
    for path, body in grounded:
        out.append(f"### `{path}`\n\n```\n{body}\n```\n")
    return "\n".join(out)


def _named_ast_child(nodes: list[ast.stmt], name: str) -> ast.AST | None:
    """Return the named definition or assignment in one AST scope."""
    for node in nodes:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                return node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            if any(
                isinstance(target, ast.Name) and target.id == name
                for target in targets
            ):
                return node
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for imported in node.names:
                imported_name = imported.asname or imported.name.split(".", 1)[0]
                if imported_name == name:
                    return node
    return None


def _code_ref_resolves(repo_root: Path, code_ref: str) -> bool:
    """Check one model-supplied ``path:symbol`` or ``path:line`` reference."""
    match = _CODE_REF_RE.fullmatch(code_ref)
    if match is None:
        return False

    root = repo_root.resolve()
    relative_path = Path(match.group("path"))
    if relative_path.is_absolute():
        return False
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return False

    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    anchor = match.group("anchor")
    if anchor.isdecimal():
        return 1 <= int(anchor) <= len(source.splitlines())
    if path.suffix != ".py":
        return re.search(rf"(?<!\w){re.escape(anchor)}(?!\w)", source) is not None

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    node: ast.AST | None = _named_ast_child(tree.body, anchor.split(".")[0])
    for part in anchor.split(".")[1:]:
        if not isinstance(node, ast.ClassDef):
            return False
        node = _named_ast_child(node.body, part)
    return node is not None


def _unresolved_code_refs(repo_root: Path, code_refs: tuple[str, ...]) -> tuple[str, ...]:
    """Return model citations that do not resolve inside ``repo_root``."""
    return tuple(ref for ref in code_refs if not _code_ref_resolves(repo_root, ref))


def _parse_annotation_response(
    raw: str, *, repo_root: Path
) -> tuple[SectionAnnotation, ...]:
    """Lift the JSON array out of a Claude response into section verdicts.

    Same extraction shape as
    :func:`plan_tool.create._parse_steps_json` (slice between the first
    ``[`` and last ``]``, tolerating prose / fences around it), but raises
    :class:`AnnotateError` on any failure — there is no interactive
    fallback here. Coerces ``status`` via :class:`AnnotationStatus`,
    normalises ``code_refs`` to a tuple. A contradictory
    NOT-IMPLEMENTED-with-``code_refs`` entry degrades to NEEDS-REVIEW
    instead of aborting the whole annotation; an IMPLEMENTED/PARTIAL
    verdict with missing or unresolved refs is demoted to ``low_confidence``
    instead, retaining the model response for manual review.
    """
    items = _ANNOTATE_RESPONSE_CONTRACT.decode(raw)
    if not isinstance(items, list):
        raise AnnotateError("annotate response contained no JSON array")
    if not items:
        raise AnnotateError("annotate response JSON array was empty or not a list")

    sections: list[SectionAnnotation] = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise AnnotateError(f"annotate entry {i} is not a JSON object")
        heading = item.get("heading")
        if not isinstance(heading, str) or not heading.strip():
            raise AnnotateError(f"annotate entry {i} has a missing/blank heading")
        raw_status = item.get("status")
        # Normalize only model-emittable statuses; NEEDS-REVIEW is derived.
        normalized_status = (
            raw_status.strip().upper() if isinstance(raw_status, str) else raw_status
        )
        if (
            not isinstance(normalized_status, str)
            or normalized_status not in _MODEL_RESPONSE_STATUSES
        ):
            raise AnnotateError(
                f"annotate entry {heading.strip()!r} has unknown status {raw_status!r}"
            )
        status = AnnotationStatus(normalized_status)

        raw_refs = item.get("code_refs") or []
        if not isinstance(raw_refs, list):
            raise AnnotateError(
                f"annotate entry {heading.strip()!r} code_refs is not a list"
            )
        code_refs = tuple(str(r).strip() for r in raw_refs if str(r).strip())

        evidence = str(item.get("evidence", "")).strip()
        remaining_work = str(item.get("remaining", "")).strip()
        low_confidence = bool(item.get("confidence_low", False))
        is_step = bool(item.get("is_step", False))

        contradiction_review = False
        if status is AnnotationStatus.NOT_IMPLEMENTED and code_refs:
            status = AnnotationStatus.NEEDS_REVIEW
            low_confidence = True
            contradiction_review = True
            contradiction_note = (
                "NEEDS-REVIEW: model returned NOT-IMPLEMENTED while also "
                "citing code_refs; verify manually before using this section "
                "as planning scope."
            )
            evidence = (
                f"{contradiction_note} {evidence}"
                if evidence
                else contradiction_note
            )
        if (
            status in (AnnotationStatus.IMPLEMENTED, AnnotationStatus.PARTIAL)
            and not code_refs
        ):
            low_confidence = True
        unresolved_refs = _unresolved_code_refs(repo_root, code_refs)
        if unresolved_refs:
            low_confidence = True
            unresolved_note = (
                "LOW-CONFIDENCE: unresolved code_refs at HEAD: "
                + ", ".join(f"`{ref}`" for ref in unresolved_refs)
                + "."
            )
            evidence = (
                f"{unresolved_note} {evidence}" if evidence else unresolved_note
            )

        sections.append(
            SectionAnnotation(
                heading=heading.strip(),
                status=status,
                evidence=evidence,
                code_refs=code_refs,
                remaining_work=remaining_work,
                low_confidence=low_confidence,
                is_step=is_step,
                contradiction_review=contradiction_review,
            )
        )
    return tuple(sections)


def _has_incomplete_grounding(
    grounding: GroundedSource, *, floor_file_count: int = _GROUNDING_FLOOR_FILE_COUNT
) -> bool:
    """True when grounding is too thin to trust confident done verdicts.

    Zero grounded files is always low-grounding, even for prose-heavy notes
    with no path candidates. Otherwise, small plans are exempt only when
    every extracted candidate resolved into grounded text.
    """
    grounded_count = len(grounding.files)
    if grounded_count == 0:
        return True
    if grounded_count >= floor_file_count:
        return False
    if grounding.candidate_count >= floor_file_count:
        return True
    return grounding.skipped_count > 0


def _apply_grounding_floor(
    sections: tuple[SectionAnnotation, ...],
    grounding: GroundedSource,
    *,
    floor_file_count: int = _GROUNDING_FLOOR_FILE_COUNT,
) -> tuple[SectionAnnotation, ...]:
    """Demote or mark optimistic verdicts when grounding is incomplete."""
    if not _has_incomplete_grounding(grounding, floor_file_count=floor_file_count):
        return sections

    out: list[SectionAnnotation] = []
    grounded_count = len(grounding.files)
    reason = (
        f"Low grounding ({grounded_count} grounded file"
        f"{'' if grounded_count == 1 else 's'}; "
        f"{grounding.candidate_count} candidate"
        f"{'' if grounding.candidate_count == 1 else 's'}, "
        f"{grounding.skipped_count} skipped) makes this verdict speculative; "
        "verify manually before trusting it."
    )
    for section in sections:
        if section.status is AnnotationStatus.IMPLEMENTED:
            evidence = f"{reason} {section.evidence}" if section.evidence else reason
            out.append(
                SectionAnnotation(
                    heading=section.heading,
                    status=AnnotationStatus.NEEDS_REVIEW,
                    evidence=evidence,
                    code_refs=section.code_refs,
                    remaining_work=section.remaining_work,
                    low_confidence=True,
                    is_step=section.is_step,
                    contradiction_review=section.contradiction_review,
                    low_grounding=True,
                )
            )
            continue
        if section.status is AnnotationStatus.PARTIAL:
            evidence = f"{reason} {section.evidence}" if section.evidence else reason
            out.append(
                SectionAnnotation(
                    heading=section.heading,
                    status=section.status,
                    evidence=evidence,
                    code_refs=section.code_refs,
                    remaining_work=section.remaining_work,
                    low_confidence=True,
                    is_step=section.is_step,
                    contradiction_review=section.contradiction_review,
                    low_grounding=True,
                )
            )
            continue
        out.append(section)
    return tuple(out)


def _utc_timestamp() -> str:
    """Return a report timestamp string in UTC."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@spawn_cwd_from_repo_root
def classify_plan_implementation(
    source_path: Path,
    *,
    repo_root: Path,
    invoker: AnnotateInvoker = shell_annotate_invoker,
    max_file_bytes: int = _MAX_GROUND_FILE_BYTES,
) -> PlanAnnotation:
    """Classify each section of ``source_path`` against the current repo.

    Ingests the file verbatim, loads each frontmatter step's ``detail:``
    spec, code-grounds the cited files (excluding those spec files so their
    mere presence on disk doesn't bias the verdict), renders the prompt,
    and parses Claude's per-section JSON into a :class:`PlanAnnotation`.

    Raises:
        CreateError: ``source_path`` is not a file (from
            :func:`read_existing_description`).
        AnnotateError: Claude's response is empty / unparseable, or carries
            a malformed section entry.
    """
    source_text = read_existing_description(source_path)
    step_specs = _load_step_specs(
        source_text, repo_root=repo_root, max_file_bytes=max_file_bytes
    )
    exclude = _resolved_detail_paths(source_text, repo_root=repo_root)
    grounding = _ground_source(
        source_text,
        repo_root=repo_root,
        max_file_bytes=max_file_bytes,
        exclude=exclude,
    )
    prompt = render_annotate_prompt(
        source_text,
        _format_step_specs_block(step_specs),
        _format_grounded_block(grounding.files),
    )
    raw = invoker(prompt)
    low_grounding = _has_incomplete_grounding(grounding)
    sections = _apply_grounding_floor(
        _parse_annotation_response(raw, repo_root=grounding.repo_root), grounding
    )
    return PlanAnnotation(
        source_path=source_path,
        source_text=source_text,
        repo_root=grounding.repo_root,
        grounded_files=tuple(p for p, _ in grounding.files),
        sections=sections,
        low_grounding=low_grounding,
        annotated_at=_utc_timestamp(),
        grounding_candidate_count=grounding.candidate_count,
        grounding_skipped_count=grounding.skipped_count,
        grounding_skip_reasons=grounding.skip_reasons,
    )
