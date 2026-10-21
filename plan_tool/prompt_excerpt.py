"""Symbol-aware prompt excerpts for source previews.

This module is intentionally leaf-only: callers provide already-read text,
repo-relative paths, and candidate symbols. Filesystem errors and plan
semantics stay with the caller.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal, Sequence


TRUNCATION_MARKER = "… _(truncated)_"
FALLBACK_PREVIEW_PREFIX = "fallback preview"

_CODE_LIKE_SUFFIXES = frozenset(
    {
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".rb",
        ".swift",
        ".md",
        ".toml",
        ".json",
    }
)


@dataclass(frozen=True)
class ExcerptResult:
    """Rendered excerpt plus stable metadata for prompt callers."""

    path: str
    text: str
    excerpt_kind: Literal["symbol", "fallback"]
    fallback_reason: Literal[
        "parse-error", "no-symbol-match", "unsupported-file-type"
    ] | None
    truncated: bool


@dataclass(frozen=True)
class _SymbolRange:
    name: str
    start_line: int
    end_line: int


def build_prompt_excerpt(
    path: str,
    text: str,
    candidate_symbols: Sequence[str],
    *,
    max_bytes: int,
) -> ExcerptResult:
    """Return a bounded excerpt that favors candidate symbol matches."""

    suffix = PurePosixPath(path).suffix.lower()
    candidates = _normalized_candidates(candidate_symbols)
    if suffix == ".py":
        return _build_python_excerpt(path, text, candidates, max_bytes=max_bytes)
    if suffix == ".md":
        markdown = _build_markdown_excerpt(
            path, text, candidates, max_bytes=max_bytes
        )
        if markdown.excerpt_kind == "symbol":
            return markdown
        if candidates:
            line_match = _build_line_match_excerpt(
                path, text, candidates, max_bytes=max_bytes
            )
            if line_match is not None:
                return line_match
        return markdown
    if suffix in _CODE_LIKE_SUFFIXES:
        line_match = _build_line_match_excerpt(
            path, text, candidates, max_bytes=max_bytes
        )
        if line_match is not None:
            return line_match
        return _build_fallback_excerpt(
            path,
            text,
            max_bytes=max_bytes,
            reason="no-symbol-match",
        )
    return _build_fallback_excerpt(
        path,
        text,
        max_bytes=max_bytes,
        reason="unsupported-file-type",
    )


def _build_python_excerpt(
    path: str,
    text: str,
    candidates: Sequence[str],
    *,
    max_bytes: int,
) -> ExcerptResult:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _build_fallback_excerpt(
            path,
            text,
            max_bytes=max_bytes,
            reason="parse-error",
        )

    lines = text.splitlines()
    symbol_range = _find_python_symbol_range(tree, candidates, lines)
    if symbol_range is None:
        return _build_fallback_excerpt(
            path,
            text,
            max_bytes=max_bytes,
            reason="no-symbol-match",
        )

    import_block = _top_import_block(tree)
    parts: list[str] = []
    start = symbol_range.start_line
    end = symbol_range.end_line
    symbol_text = _slice_lines(lines, start, end)
    omitted_before = start > 1
    omitted_after = end < len(lines)

    if import_block is not None and import_block[1] < start:
        import_text = _slice_lines(lines, import_block[0], import_block[1])
        gap_before_symbol = import_block[1] + 1 < start
        combined = f"{import_text}\n\n{TRUNCATION_MARKER}\n\n{symbol_text}"
        if _byte_len(combined) <= max_bytes:
            parts.append(import_text)
            # The byte-budget check above already sized `combined` as
            # import_text + marker + symbol_text; omitting the marker here
            # when there's an actual gap would render the two as
            # contiguous even though truncated=True is reported below.
            if gap_before_symbol:
                parts.append(TRUNCATION_MARKER)
            omitted_before = import_block[0] > 1 or gap_before_symbol
        else:
            parts.append(TRUNCATION_MARKER)
    elif omitted_before:
        parts.append(TRUNCATION_MARKER)

    parts.append(symbol_text)
    if omitted_after:
        parts.append(TRUNCATION_MARKER)

    rendered = "\n\n".join(part for part in parts if part)
    truncated = omitted_before or omitted_after or _byte_len(rendered) > max_bytes
    rendered, clipped = clip_text_to_byte_budget(rendered, max_bytes=max_bytes)
    return ExcerptResult(
        path=path,
        text=rendered,
        excerpt_kind="symbol",
        fallback_reason=None,
        truncated=truncated or clipped,
    )


def _find_python_symbol_range(
    tree: ast.AST, candidates: Sequence[str], lines: Sequence[str]
) -> _SymbolRange | None:
    nodes: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nodes.append(node)
    if isinstance(tree, ast.Module):
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                nodes.append(node)
    nodes.sort(key=lambda node: getattr(node, "lineno", 0))

    by_name: dict[str, _SymbolRange] = {}
    for node in nodes:
        for name in _python_node_names(node):
            key = name.lower()
            if key in by_name:
                continue
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start)
            start = _include_python_leading_context(lines, start)
            by_name[key] = _SymbolRange(name=name, start_line=start, end_line=end)

    for candidate in candidates:
        match = by_name.get(candidate.lower())
        if match is not None:
            return match
    return None


def _python_node_names(node: ast.AST) -> list[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    if isinstance(node, ast.Assign):
        return _assignment_target_names(node.targets)
    if isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        return _assignment_target_names([node.target])
    return []


def _assignment_target_names(targets: Sequence[ast.expr]) -> list[str]:
    names: list[str] = []
    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            names.extend(_assignment_target_names(target.elts))
    return names


def _include_python_leading_context(lines: Sequence[str], start_line: int) -> int:
    start = start_line
    minimum_start = max(1, start_line - 4)
    while start > minimum_start:
        previous = lines[start - 2].strip()
        if previous.startswith("@") or previous.startswith("#") or previous == "":
            start -= 1
            continue
        break
    return start


def _top_import_block(tree: ast.Module) -> tuple[int, int] | None:
    body = list(tree.body)
    index = 0
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        index = 1

    start: int | None = None
    end: int | None = None
    while index < len(body):
        node = body[index]
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            break
        if start is None:
            start = node.lineno
        end = getattr(node, "end_lineno", node.lineno)
        index += 1
    if start is None or end is None:
        return None
    return start, end


def _build_markdown_excerpt(
    path: str,
    text: str,
    candidates: Sequence[str],
    *,
    max_bytes: int,
) -> ExcerptResult:
    lines = text.splitlines()
    heading_index: int | None = None
    for candidate in candidates:
        candidate_key = candidate.lower()
        for index, line in enumerate(lines):
            match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
            if match is None:
                continue
            heading_text = match.group(2).strip().lower()
            if candidate_key in heading_text:
                heading_index = index
                break
        if heading_index is not None:
            break

    if heading_index is None:
        return _build_fallback_excerpt(
            path,
            text,
            max_bytes=max_bytes,
            reason="no-symbol-match",
        )

    heading_match = re.match(r"^(#{1,6})", lines[heading_index])
    assert heading_match is not None
    heading_level = len(heading_match.group(1))
    end_index = len(lines)
    for index in range(heading_index + 1, len(lines)):
        match = re.match(r"^(#{1,6})\s+", lines[index])
        if match is not None and len(match.group(1)) <= heading_level:
            end_index = index
            break

    section = "\n".join(lines[heading_index:end_index])
    omitted_before = heading_index > 0
    omitted_after = end_index < len(lines)
    rendered = section
    if omitted_before:
        rendered = f"{TRUNCATION_MARKER}\n\n{rendered}"
    if omitted_after:
        rendered = f"{rendered}\n\n{TRUNCATION_MARKER}"
    truncated = omitted_before or omitted_after or _byte_len(rendered) > max_bytes
    rendered, clipped = clip_text_to_byte_budget(rendered, max_bytes=max_bytes)
    return ExcerptResult(
        path=path,
        text=rendered,
        excerpt_kind="symbol",
        fallback_reason=None,
        truncated=truncated or clipped,
    )


def _build_line_match_excerpt(
    path: str,
    text: str,
    candidates: Sequence[str],
    *,
    max_bytes: int,
) -> ExcerptResult | None:
    if not candidates:
        return None
    lines = text.splitlines()
    match_index: int | None = None
    for candidate in candidates:
        for index, line in enumerate(lines):
            if _line_matches_candidate(line, candidate):
                match_index = index
                break
        if match_index is not None:
            break
    if match_index is None:
        return None

    start_index = max(0, match_index - 3)
    end_index = min(len(lines), match_index + 4)
    rendered = "\n".join(lines[start_index:end_index])
    omitted_before = start_index > 0
    omitted_after = end_index < len(lines)
    if omitted_before:
        rendered = f"{TRUNCATION_MARKER}\n\n{rendered}"
    if omitted_after:
        rendered = f"{rendered}\n\n{TRUNCATION_MARKER}"
    truncated = omitted_before or omitted_after or _byte_len(rendered) > max_bytes
    rendered, clipped = clip_text_to_byte_budget(rendered, max_bytes=max_bytes)
    return ExcerptResult(
        path=path,
        text=rendered,
        excerpt_kind="symbol",
        fallback_reason=None,
        truncated=truncated or clipped,
    )


def _line_matches_candidate(line: str, candidate: str) -> bool:
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_]){re.escape(candidate)}(?![A-Za-z0-9_])",
        re.IGNORECASE,
    )
    return pattern.search(line) is not None


def _build_fallback_excerpt(
    path: str,
    text: str,
    *,
    max_bytes: int,
    reason: Literal["parse-error", "no-symbol-match", "unsupported-file-type"],
) -> ExcerptResult:
    cue = f"{FALLBACK_PREVIEW_PREFIX}: {reason}\n"
    truncated = _byte_len(cue + text) > max_bytes
    rendered, clipped = clip_text_to_byte_budget(
        cue + text,
        max_bytes=max_bytes,
    )
    return ExcerptResult(
        path=path,
        text=rendered,
        excerpt_kind="fallback",
        fallback_reason=reason,
        truncated=truncated or clipped,
    )


def _normalized_candidates(candidate_symbols: Sequence[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for candidate in candidate_symbols:
        stripped = candidate.strip()
        if not stripped:
            continue
        key = stripped.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(stripped)
    return out


def _slice_lines(lines: Sequence[str], start_line: int, end_line: int) -> str:
    return "\n".join(lines[start_line - 1 : end_line])


def clip_text_to_byte_budget(text: str, *, max_bytes: int) -> tuple[str, bool]:
    if max_bytes <= 0:
        return "", bool(text)
    if _byte_len(text) <= max_bytes:
        return text, False

    marker = "\n" + TRUNCATION_MARKER
    marker_bytes = _byte_len(marker)
    if max_bytes <= marker_bytes:
        raw = TRUNCATION_MARKER.encode("utf-8")[:max_bytes]
        return raw.decode("utf-8", errors="ignore"), True

    budget = max_bytes - marker_bytes
    raw = text.encode("utf-8")[:budget]
    clipped = raw.decode("utf-8", errors="ignore").rstrip()
    return f"{clipped}{marker}", True


def _byte_len(text: str) -> int:
    return len(text.encode("utf-8"))
