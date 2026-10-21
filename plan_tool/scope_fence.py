"""Shared plan scope-fence rendering leaf.

One module owns "read a plan file, pick out the fence sections, render
them as a prompt block": the whole-fence renderer (``render_scope_fence``,
intent half then guardrail half), the guardrail half on its own
(``extract_plan_guardrails``), the plan-body H2 splitter it recognizes
sections with (``extract_h2_sections``), the four author-supplied
guardrail headings (``GUARDRAIL_BODY_SECTIONS``), and the ``_(TODO)_``
placeholder check that keeps unfilled sections out.

Deliberately a **leaf**: imports only the stdlib — never ``plan_tool.create``
/ ``detail`` / ``review`` / ``parser`` — so ``renderer`` can import it at
module load without closing the ``detail`` → ``launcher`` → ``renderer``
cycle. ``plan_tool.detail`` and ``plan_tool.create`` re-export the moved
names, so every historical import path keeps returning the same objects and
a monkeypatch on either path patches the one implementation.

Recognition and rendering live together on purpose. This code reads the very
sections ``create`` writes, so a mirrored splitter that drifted by one rule
(dropping the CommonMark closing-sequence strip, say) would silently stop
recognizing a heading a real seed produced, with nothing going red.

Unrelated to ``plan_tool.scope_guard`` (post-apply file-scope diffing) and
``plan_tool.scope_out`` (the carve-and-seed structural remedy) despite the
shared ``scope_`` prefix — they share no code and no concern.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Matches an H1 or H2 heading line; ``extract_h2_sections`` filters to H2.
_H2_HEADING_RE = re.compile(r"^(#{1,2})[ \t]+(.+?)[ \t]*$", re.MULTILINE)
# Up to 3 leading space-or-tab characters, treated as a unit of indentation
# budget rather than a true CommonMark column count (a leading tab there
# expands to the next 4-column stop and would exceed the fence-recognition
# budget, disqualifying it) — a deliberate simplification, not spec parity:
# this scanner exists only to keep a fenced pseudo-heading from leaking
# through ``ignore_fenced_code``, and a tab-indented fence going entirely
# unrecognized would defeat that for the (more common, in practice) case of
# a tab-indented example block, worse than slightly over-recognizing one.
_FENCE_OPEN_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_FENCE_CLOSE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})[ \t]*$")


@dataclass(frozen=True)
class FencedCodeScan:
    """Fenced-code source ranges and the start of an unterminated opener."""

    spans: tuple[tuple[int, int], ...]
    unmatched_opening: int | None = None


# Optional plan-body sections that are author-supplied constraints rather than
# synthesis opportunities. ``create_plan`` captures their original seed bodies
# before distillation can replace the seed and passes them directly to the
# renderer, where they override all model output. Order is contract: the fence
# renders these four first, then ``_DETAIL_FENCE_SECTIONS``.
GUARDRAIL_BODY_SECTIONS: tuple[str, ...] = (
    "Scope guardrails",
    "Audit guardrails",
    "Expected placement",
    "Stack",
)

# Canonical plan-body sections threaded into downstream prompts alongside the
# four author-supplied guardrail headings. ``Out of scope`` is fence content —
# what the plan will not build — so it tells a consumer what to leave out
# without carrying a claim it would otherwise restate independently. See
# PLAN_FORMAT.md ("Plan-level scope fence").
_DETAIL_FENCE_SECTIONS: tuple[str, ...] = ("Out of scope",)

# Headings for the *positive* half of the fence — the plan's and the step's
# stated purpose (``Plan.intent`` / ``Step.intent``). They read as
# instructions because the consuming model sees them with no other framing.
# Pinned by test: ``renderer`` renders the same block into the run prompt, so
# a wording change has to be a visible diff rather than a drift between the
# two surfaces.
PLAN_INTENT_HEADING = (
    "Plan intent (what the whole plan is for — every part of this step "
    "must serve it)"
)
STEP_INTENT_HEADING = (
    "Step intent (what this step is for — do not widen past it)"
)

# Placeholder shapes inside a plan body *section* (``## Out of scope``, …) that
# should be treated as "section empty" when seeding a downstream prompt.
# Deliberately narrower than the intent vocabulary below: a guardrail section
# reading ``TBD`` is a real statement about the section, whereas an *intent* of
# ``TBD`` states no why at all. Do not widen this to TBD — that would silently
# drop guardrail bodies.
_SECTION_PLACEHOLDER_RE = re.compile(
    r"^\s*(?:_\(TODO\)_|TODO|\(TODO\))\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Mirrors review._BODY_PLACEHOLDER_RE for the *intent* contract only. Keep it
# local because this leaf cannot import review.
_INTENT_PLACEHOLDER_RE = re.compile(
    r"^\s*(?:_\((?:TODO|TBD)\)_|(?:TODO|TBD)|\((?:TODO|TBD)\))\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# The six intent non-values, as one exported predicate. Every consumer that
# decides "this intent states no why" must call :func:`is_placeholder_intent`
# — the contract is that whatever ``review.check_intent_presence`` reports
# missing renders nowhere, and that only holds if the whole set agrees. Sites:
# ``_render_intent_section`` here, ``detail._shared_intent``,
# ``review._collapse_usable_audit_intent``,
# ``scope_out._source_plan_intent_framing`` / its step-intent suffix, and
# ``reground``'s plan/step intent framing.


def collapse_intent_to_one_line(text: str) -> str:
    """Collapse whitespace runs in an intent to single spaces, then strip.

    The one definition every intent writer shares — the seed-``## Outcome`` map
    and the step-proposal parser in ``create``, the drafted-value transform in
    ``intent_proposal``, and the fence renderer below. They must agree: the plan
    contract is that the stored frontmatter is *byte-identical* to what the
    fence renders, not merely equivalent, and a real newline in the value could
    put a ``##`` at line start inside a block the prompt labels authoritative.

    Normalization only — nothing is truncated, shortened, or rejected for its
    shape (the plan's fence permanently refuses a length cap).
    """
    return re.sub(r"\s+", " ", text).strip()


def _is_placeholder_section(body: str) -> bool:
    """True when every non-blank line is a ``_(TODO)_``-style placeholder."""
    non_blank = [ln for ln in body.splitlines() if ln.strip()]
    return bool(non_blank) and all(
        _SECTION_PLACEHOLDER_RE.match(ln) for ln in non_blank
    )


def source_references_block(
    source_path: Path, source_references: str | None
) -> list[str]:
    """Render preserved source references or the source-plan fallback."""
    references = (source_references or "").strip()
    if references and not _is_placeholder_section(references):
        return ["## References", "", references, ""]
    return ["## References", "", f"- Source plan: `{source_path}`", ""]


def is_placeholder_intent(intent: str) -> bool:
    """True when an intent is one of review's six missing-value spellings.

    Deliberately wider than :func:`_is_placeholder_section` (which stays
    TODO-only for *body sections*, where a ``TBD`` ``## Out of scope`` is a real
    statement). Every intent consumer shares this one; see the note above
    :data:`_INTENT_PLACEHOLDER_RE` for the site list and why they must agree.
    """
    return _INTENT_PLACEHOLDER_RE.fullmatch(intent.strip()) is not None


def _fence_run_closes(opener_char: str, opener_len: int, candidate_run: str) -> bool:
    """CommonMark's closer rule: same character, run length >= the opener's.

    The single source of truth for this comparison — both
    ``_fenced_code_spans`` (below) and ``detail.py``'s
    ``_strip_bare_fence_lines`` (a hand-rolled two-line hint, not a full
    scan) must apply the identical rule or they can disagree about
    whether a candidate line closes a given opener.
    """
    return candidate_run[0] == opener_char and len(candidate_run) >= opener_len


def _fenced_code_spans(text: str) -> FencedCodeScan:
    """Return fenced-code ranges and whether a supported opener lacks a closer."""
    spans: list[tuple[int, int]] = []
    opener: tuple[str, int, int] | None = None
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        if opener is None:
            match = _FENCE_OPEN_RE.match(stripped)
            if match is not None:
                fence = match.group(1)
                # CommonMark forbids a backtick in a backtick fence's info
                # string specifically to keep this unambiguous: a line that
                # is only ```rm -rf /``` is an inline code span, not an
                # unterminated fence opener that swallows the rest of the
                # document. No such restriction exists for ~~~ fences.
                if fence[0] == "`" and "`" in stripped[match.end():]:
                    offset += len(line)
                    continue
                opener = (fence[0], len(fence), offset)
        else:
            match = _FENCE_CLOSE_RE.match(stripped)
            if match is not None and _fence_run_closes(
                opener[0], opener[1], match.group(1)
            ):
                spans.append((opener[2], offset + len(line)))
                opener = None
        offset += len(line)
    if opener is not None:
        spans.append((opener[2], len(text)))
        return FencedCodeScan(tuple(spans), unmatched_opening=opener[2])
    return FencedCodeScan(tuple(spans))


def _excise_fenced_code(
    text: str, *, fenced_spans: tuple[tuple[int, int], ...] | None = None
) -> str:
    """Return ``text`` with every fenced code block's lines removed entirely.

    Reuses :func:`_fenced_code_spans` rather than a second fence scanner.
    A dropped span always ends at a line boundary, so the surviving lines
    on either side never get welded together.
    """
    spans = _fenced_code_spans(text).spans if fenced_spans is None else fenced_spans
    if not spans:
        return text
    pieces: list[str] = []
    cursor = 0
    for start, end in spans:
        pieces.append(text[cursor:start])
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def extract_h2_section_occurrences(
    text: str,
    *,
    ignore_fenced_code: bool = False,
    strip_fenced_code: bool = False,
    fenced_spans: tuple[tuple[int, int], ...] | None = None,
) -> dict[str, list[str]]:
    """Return every normalized H2 body, retaining duplicate and empty entries.

    The occurrence form serves validators that must distinguish an absent H2
    from an empty or repeated one. Most readers should use
    :func:`extract_h2_sections`, which keeps the first non-empty body.
    """
    if not text:
        return {}
    already_fence_safe = False
    if strip_fenced_code:
        text = _excise_fenced_code(text, fenced_spans=fenced_spans)
        ignore_fenced_code = True
        already_fence_safe = True
    matches = list(_H2_HEADING_RE.finditer(text))
    if ignore_fenced_code and not already_fence_safe:
        spans = (
            _fenced_code_spans(text).spans if fenced_spans is None else fenced_spans
        )
        matches = [
            match
            for match in matches
            if not any(start <= match.start() < end for start, end in spans)
        ]
    occurrences: dict[str, list[str]] = {}
    for i, match in enumerate(matches):
        if match.group(1) != "##":
            continue
        title = _normalized_h2_title(match.group(2))
        if not title:
            continue
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        occurrences.setdefault(title, []).append(text[match.end() : body_end].strip())
    return occurrences


def _normalized_h2_title(raw: str) -> str:
    """Lowercased H2 title with a CommonMark closing ``#`` run removed."""
    title = re.sub(r"[ \t]+#+[ \t]*$", "", raw.strip()).rstrip()
    return title.lower()


def h2_section_spans(text: str, title: str) -> list[tuple[int, int]]:
    """``(start, end)`` offsets of every fence-safe H2 section titled ``title``.

    Uses the heading and fence rules of :func:`extract_h2_section_occurrences`,
    so a caller that rewrites a section removes exactly what a reader of the
    same text sees. A section ends at the next H1 or H2, or at the end of text.
    """
    wanted = title.lower()
    fenced = _fenced_code_spans(text).spans
    matches = [
        match
        for match in _H2_HEADING_RE.finditer(text)
        if not any(start <= match.start() < end for start, end in fenced)
    ]
    spans: list[tuple[int, int]] = []
    for i, match in enumerate(matches):
        if match.group(1) != "##" or _normalized_h2_title(match.group(2)) != wanted:
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        spans.append((match.start(), end))
    return spans


def extract_h2_sections(
    text: str,
    *,
    ignore_fenced_code: bool = False,
    strip_fenced_code: bool = False,
) -> dict[str, str]:
    """Return ``{lowered_h2_title: section_body}`` for every H2 in ``text``.

    Section body is everything after the heading line up to the next H1
    or H2 (or EOF), with surrounding whitespace stripped. Duplicate
    titles keep the first occurrence so a malformed source with two
    ``## Overview`` blocks doesn't silently swap the second in.

    Used by ``create._render_plan_body`` to populate the standard plan
    sections from the original seed file handed to ``create``. Returns
    an empty dict for empty input — caller falls through to
    ``_(TODO)_`` placeholders.

    ``ignore_fenced_code`` only keeps a fenced pseudo-H2 from splitting a
    section early; the fenced text itself still comes back verbatim in
    whichever real section body contains it — correct for a caller that
    renders or preserves the body. ``strip_fenced_code`` additionally
    removes every fenced block from the body text before returning it, for
    a caller that pattern-matches the body against known content (e.g. an
    artifact-reference gate): otherwise a fenced example merely mentioning
    a filename would satisfy the gate the same as a real reference. Passing
    ``strip_fenced_code=True`` implies ``ignore_fenced_code``.
    """
    sections: dict[str, str] = {}
    for key, bodies in extract_h2_section_occurrences(
        text,
        ignore_fenced_code=ignore_fenced_code,
        strip_fenced_code=strip_fenced_code,
    ).items():
        first_nonempty = next((body for body in bodies if body), None)
        if first_nonempty is not None:
            sections[key] = first_nonempty
    return sections


def _strip_frontmatter(text: str) -> str:
    """Return ``text`` with a leading ``---`` YAML frontmatter block removed.

    Hand-rolled because the leaf cannot import ``plan_tool.parser`` (it pulls
    in ``schema`` and pydantic — see the module docstring). Only the leading
    block is removed; an unterminated one leaves the text untouched.

    Load-bearing, not tidying: a ``##``-prefixed YAML **comment** is legal at
    column 0 inside frontmatter, so matching headings against the whole file
    lets ``## Out of scope`` written as a comment parse as a section whose body
    is the rest of the frontmatter — and since duplicate titles keep the first
    occurrence, it *shadows* the plan's real section and the fence silently
    ships YAML instead of the fence.

    Deliberately more lenient than ``parser._split_frontmatter`` on the fence
    line itself (``strip()``, not ``rstrip("\\r\\n")``): most callers here run
    against LLM-authored seed/draft/annotation text that never passes through
    the strict parser at all, and a model's own trailing whitespace on a
    closing ``---`` must not make its real sections invisible. A caller whose
    *same* text is also strictly re-parsed moments later (e.g. ``reprocess``)
    is responsible for keeping the two checks in agreement itself, since only
    that caller knows the two will run back-to-back on the same file.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "".join(lines[i + 1 :])
    return text


def extract_plan_guardrails(plan_path: Path) -> str:
    """Render the plan's scope fence for downstream prompts.

    Carries the four author-supplied guardrail headings plus the canonical
    ``## Out of scope`` section, in that order, each as ``## <Heading>`` over
    its body and joined by a blank line. Empty, placeholder-only, and
    unrecognized sections stay out of the prompt; the plan body remains
    authoritative for every retained heading.

    Strips frontmatter before matching headings. A YAML **comment** is legal
    at column 0, so ``## Out of scope`` written as one would otherwise parse as
    a section — shadowing the plan's real section, since duplicate titles keep
    the first occurrence — and the fence would ship frontmatter instead.
    """
    try:
        text = Path(plan_path).read_text(encoding="utf-8")
    except OSError:
        return ""
    sections = extract_h2_sections(_strip_frontmatter(text), ignore_fenced_code=True)
    rendered: list[str] = []
    for heading in (*GUARDRAIL_BODY_SECTIONS, *_DETAIL_FENCE_SECTIONS):
        body = sections.get(heading.lower(), "").strip()
        if not body or _is_placeholder_section(body):
            continue
        rendered.append(f"## {heading}\n\n{body}")
    return "\n\n".join(rendered)


def _render_intent_section(heading: str, intent: str) -> str:
    """Render one intent section, or ``""`` when the value carries nothing.

    Whitespace collapses to single spaces: a value with a real newline could
    otherwise put a ``##`` at line start and forge a heading inside a block
    the prompt labels authoritative. Length is preserved — nothing truncates
    or tidies the value, so the prompt can't disagree with the plan file.
    """
    collapsed = collapse_intent_to_one_line(intent)
    if not collapsed or is_placeholder_intent(collapsed):
        return ""
    return f"## {heading}\n\n{collapsed}"


def render_scope_fence(
    plan_path: Path,
    *,
    plan_intent: str = "",
    step_intent: str = "",
) -> str:
    """Render the whole scope fence: intent half, then guardrail half.

    The intent half is a *prefix*, so ``render_scope_fence(plan_path)`` with
    neither intent set returns exactly what :func:`extract_plan_guardrails`
    returns — a plan carrying no intent renders the same prompt bytes it
    always has, by construction rather than by coincidence.

    Order is contract, widest fence first: plan intent, step intent, then
    every guardrail section. Empty, whitespace-only, and ``_(TODO)_``-style
    placeholder intents render nothing — an unfilled value inside an
    authoritative block reads as a directive.

    Takes the two intents as plain strings rather than a ``Plan``/``Step``
    so this module stays stdlib-only (see the module docstring); the caller
    unwraps ``None`` with ``plan.intent or ""``.
    """
    rendered = [
        section
        for section in (
            _render_intent_section(PLAN_INTENT_HEADING, plan_intent),
            _render_intent_section(STEP_INTENT_HEADING, step_intent),
        )
        if section
    ]
    guardrails = extract_plan_guardrails(plan_path)
    if guardrails:
        rendered.append(guardrails)
    return "\n\n".join(rendered)
