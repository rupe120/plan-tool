"""Jira-grade detail contract: the single authority for the compact schema.

One module owns the jira-grade side of the detail-grade axis — the five
required H2 sections (``Intent``, ``Change``, ``Constraints``,
``Done when``, ``Out of scope``), the deterministic read-time validator
that accepts a conforming body and loudly rejects a run-grade body parked
at a jira-grade path, and the deterministic plain-English gate over the
prose between the code anchors. Every consumer (``detail`` authoring,
``jira`` export, the ``run`` renderer, the completeness audit) imports the
tokens from here rather than re-declaring them, so the copies cannot drift.

Two things this module deliberately does **not** do:

- **Import ``plan_tool.detail``.** The run-grade tokens stay where they
  are; the first-token matching *convention* is mirrored, not shared.
  Consolidating the repo's H2 matchers is a cross-module refactor routed
  to reconcile. This module is a **stdlib-only leaf** so any consumer can
  import it at module load.
- **Judge with Claude.** Both gates are pure functions of the text — no
  ``invoker=`` seam. The model-reviewed clarity half of the plain-English
  rubric stays out.

The two gates split by **audience**: read-time consumers validate the
structural H2 contract only (:func:`validate_jira_grade_body`), while the
prose gate's blocking findings drive the authoring retry loop. Nothing at
read time rejects an artifact over prose taste.

Artifact paths live in :mod:`plan_tool.detail_artifacts`
(``derive_jira_detail_path``), beside the run-grade derivation they must
never collide with.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

# --------------------------------------------------------------------------
# The grade axis
# --------------------------------------------------------------------------

# The detail-grade tokens themselves. Minted here because this module is the
# only common ancestor of the four commands that grow a grade selector
# (``jira --grade``, ``run --detail-grade``, ``completeness-audit --grade``,
# ``detail --grade``): each reads the spelling from here, never from a
# sibling consumer.
GRADE_RUN = "run"
GRADE_JIRA = "jira"

# Ordered for argparse ``choices=``.
JIRA_GRADE_VALUES = (GRADE_RUN, GRADE_JIRA)

# The default grade on every surface. A named constant rather than "the first
# value of JIRA_GRADE_VALUES": four commands grow a grade selector, and this
# module exists so they read one fact instead of each re-deciding it.
GRADE_DEFAULT = GRADE_RUN


def is_known_grade(value: str) -> bool:
    """Whether ``value`` names a grade this module defines."""
    return value in JIRA_GRADE_VALUES


def unknown_grade_message(value: str) -> str:
    """The rejection message for an unrecognized grade.

    Single-sourced so the grade-taking surfaces read one wording instead of
    each spelling their own; they keep their own exception types, which
    differ by layer (``ValueError`` / ``DetailGradeError`` / ``JiraError``).
    """
    return (
        f"unknown detail grade '{value}' "
        f"(expected one of {', '.join(JIRA_GRADE_VALUES)})"
    )


# --------------------------------------------------------------------------
# The section contract
# --------------------------------------------------------------------------

# The required H2 sections, in display order. The durable authority — every
# jira-grade consumer imports these and never re-declares them.
JIRA_GRADE_REQUIRED_H2S = (
    "Intent",
    "Change",
    "Constraints",
    "Done when",
    "Out of scope",
)

# First-token matcher set derived from the display names, mirroring
# ``detail.py:_REQUIRED_H2_TOKENS``' convention — first word, lowercased,
# trailing words allowed — so ``## done when`` and ``## Done when
# (acceptance)`` both satisfy ``done``.
JIRA_GRADE_REQUIRED_H2_TOKENS = tuple(
    name.split()[0].lower() for name in JIRA_GRADE_REQUIRED_H2S
)

_DISPLAY_BY_TOKEN = dict(
    zip(JIRA_GRADE_REQUIRED_H2_TOKENS, JIRA_GRADE_REQUIRED_H2S)
)

# Run-grade's required H2 tokens, copied rather than imported (``detail``
# sits above this leaf) for one purpose: recognizing a run-grade body at a
# jira-grade path so the validator can name the mistake in a single line
# instead of five missing-section lines. Keep in sync with
# ``detail.py:_REQUIRED_H2_TOKENS`` if that contract ever changes.
# Ordered (not a plain set) so a consumer needing contract order --
# jira.py's companion capture, which reports missing sections in that
# order -- can import this instead of hand-maintaining a third copy.
_RUN_GRADE_H2_TOKENS = (
    "summary",
    "table",
    "why",
    "files",
    "implementation",
    "tests",
    "acceptance",
)

# How many run-grade headings make "this is the other schema" the honest
# diagnosis. Three of run-grade's seven is well past coincidence, and a
# jira body with one or two strays still gets the precise per-heading
# findings instead.
_WRONG_SCHEMA_MIN_RUN_H2S = 3

# Match an H2 heading line and capture its full text: ``## Done when
# (acceptance)`` → ``Done when (acceptance)``. ``### Foo`` does not match
# (``\s+`` fails on the third ``#``), so H3s inside a section are free.
_H2_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")

# The heading's first significant token, checked against the required set.
_H2_TOKEN_RE = re.compile(r"^([A-Za-z]+)")

# A fenced-code delimiter line. Fences are tracked so a ``## `` line inside
# a code sample is never read as a section heading.
_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")

# Same delimiter shape as ``_FENCE_RE`` but with no indentation limit --
# :func:`fenced_spans` parses a model's own free-form citation protocol
# rather than rendered markdown, so treating a fence nested deeper than
# CommonMark's 3-space rule as literal (a false negative) is the unsafe
# direction here, not a false positive.
_FENCE_MARKER_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def fenced_spans(text: str) -> list[tuple[int, int]]:
    """Char spans of fenced ```/~~~ code blocks in ``text``, one pass.

    A closing run must share the opening's fence character and be at
    least as long (CommonMark's own rule for this), so a citation nesting
    a same-character run no longer than the opener's can't close it
    early -- callers that need this protected should tell an author to
    open with a longer run than anything nested inside. An unclosed fence
    spans to end-of-text rather than pairing with an unrelated later
    fence, matching this module's existing "an unclosed fence makes
    everything below it invisible" posture (see
    :func:`_unterminated_fence`). CRLF-safe via ``str.splitlines``.
    """
    spans: list[tuple[int, int]] = []
    fence_char: Optional[str] = None
    fence_len = 0
    span_start = 0
    pos = 0
    for line in text.splitlines(keepends=True):
        match = _FENCE_MARKER_RE.match(line)
        if match:
            run = match.group(1)
            char, length = run[0], len(run)
            if fence_char is None:
                fence_char, fence_len, span_start = char, length, pos
            elif char == fence_char and length >= fence_len:
                spans.append((span_start, pos + len(line)))
                fence_char = None
        pos += len(line)
    if fence_char is not None:
        spans.append((span_start, len(text)))
    return spans


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------

# Finding kinds, exposed so consumers key on a constant rather than a
# literal. Structural kinds come from :func:`validate_jira_grade_body`;
# prose kinds from :func:`check_plain_english`.
FINDING_MISSING_SECTION = "missing-section"
FINDING_EMPTY_SECTION = "empty-section"
FINDING_UNKNOWN_SECTION = "unknown-section"
FINDING_DUPLICATE_SECTION = "duplicate-section"
FINDING_WRONG_SCHEMA = "wrong-schema"
FINDING_UNTERMINATED_FENCE = "unterminated-fence"
FINDING_FILLER_PHRASE = "filler-phrase"
FINDING_LONG_SENTENCE = "long-sentence"
FINDING_DENSE_CLAUSES = "dense-clauses"
FINDING_LONG_SECTION = "long-section"


@dataclass(frozen=True)
class JiraGradeFinding:
    """One thing wrong with a jira-grade body.

    ``blocking`` is the whole decision surface: a blocking finding means
    the body does not meet the contract (reject it), advisory means the
    caller may surface it and move on. Findings report — nothing here
    rewrites or truncates text.
    """

    kind: str
    blocking: bool
    message: str


class JiraGradeContractError(Exception):
    """A jira-grade artifact is unreadable or fails the section contract.

    Carries the ``path`` it came from and the ``findings`` that blocked it,
    so a consumer can render the detail instead of re-validating.
    """

    def __init__(
        self,
        message: str,
        *,
        path: Optional[Path] = None,
        findings: Iterable[JiraGradeFinding] = (),
    ) -> None:
        super().__init__(message)
        self.path = path
        self.findings = tuple(findings)


@dataclass(frozen=True)
class JiraGradeSection:
    """One ``##`` section: its matcher ``token``, the heading as written,
    and the stripped body beneath it."""

    token: str
    heading: str
    body: str


# --------------------------------------------------------------------------
# Section parsing
# --------------------------------------------------------------------------


def _scan_sections(text: str) -> list[JiraGradeSection]:
    """Split ``text`` into its H2 sections, in document order.

    Fence-aware, so a ``## `` line inside a code sample stays content.
    Anything before the first H2 (a title, a preamble) is not a section and
    is not returned — the closed schema constrains H2s only.
    """
    sections: list[JiraGradeSection] = []
    heading: Optional[str] = None
    body: list[str] = []
    # (marker character, run length) — a closer must match the opener's
    # character AND be at least as long (CommonMark's own rule), or a
    # shorter same-character run nested inside a longer fence (e.g. a
    # ``` example line inside a ```` block) would close it early.
    fence: Optional[tuple[str, int]] = None

    def flush() -> None:
        if heading is None:
            return
        token_match = _H2_TOKEN_RE.match(heading)
        sections.append(
            JiraGradeSection(
                token=token_match.group(1).lower() if token_match else "",
                heading=heading,
                body="\n".join(body).strip(),
            )
        )

    for line in text.splitlines():
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            run = fence_match.group(1)
            marker = run[0]
            if fence is None:
                fence = (marker, len(run))
            elif marker == fence[0] and len(run) >= fence[1]:
                fence = None
        elif fence is None:
            heading_match = _H2_HEADING_RE.match(line)
            if heading_match:
                flush()
                heading = heading_match.group(1)
                body = []
                continue
        if heading is not None:
            body.append(line)
    flush()
    return sections


def _unterminated_fence(text: str) -> Optional[str]:
    """The delimiter of a code fence that is never closed, else ``None``.

    An unclosed fence makes both gates lie rather than fail: section scanning
    swallows every heading below it, and :func:`_strip_fenced_blocks` drops
    the rest of the document so the prose gate measures nothing at all.
    Both gates therefore report it and stop, instead of reporting the
    downstream symptoms.
    """
    fence: Optional[tuple[str, int]] = None
    for line in text.splitlines():
        match = _FENCE_RE.match(line)
        if not match:
            continue
        run = match.group(1)
        marker = run[0]
        if fence is None:
            fence = (marker, len(run))
        elif marker == fence[0] and len(run) >= fence[1]:
            fence = None
    return fence[0] if fence is not None else None


def _unterminated_fence_finding(text: str) -> Optional[JiraGradeFinding]:
    """The blocking finding for an unclosed fence, or ``None`` when closed."""
    marker = _unterminated_fence(text)
    if marker is None:
        return None
    return JiraGradeFinding(
        kind=FINDING_UNTERMINATED_FENCE,
        blocking=True,
        message=(
            f"unterminated code fence (opened with {marker * 3}) — every "
            "heading and sentence below it is invisible to both gates; "
            "close the fence and re-check"
        ),
    )


def parse_jira_grade_sections(text: str) -> dict[str, str]:
    """Map each H2's matcher token to its body, for consumers that render
    from a jira-grade artifact.

    A duplicate heading collapses to its last occurrence — call
    :func:`validate_jira_grade_body` first if that matters (it flags
    duplicates as blocking).
    """
    return {section.token: section.body for section in _scan_sections(text)}


# --------------------------------------------------------------------------
# The read-time validator
# --------------------------------------------------------------------------


def validate_jira_grade_body(text: str) -> list[JiraGradeFinding]:
    """Check ``text`` against the jira-grade section contract.

    Every finding is blocking — the contract is closed, so a body either
    conforms or does not. Four defects, in report order: missing required
    sections, then per-section duplicates, empty bodies, and unknown H2s.

    Rejecting unknown H2s is deliberate rather than a default: the compact
    schema is the *smallest shared* schema, and a closed set is what makes a
    hybrid or wrong-schema body fail structurally instead of passing on a
    five-heading subset. H3s inside a section are unconstrained.

    A body carrying run-grade headings instead short-circuits to a single
    :data:`FINDING_WRONG_SCHEMA` finding — naming the actual mistake beats
    five missing-section lines.
    """
    fence_finding = _unterminated_fence_finding(text)
    if fence_finding is not None:
        return [fence_finding]

    sections = _scan_sections(text)
    present = [section.token for section in sections]
    missing = [
        token for token in JIRA_GRADE_REQUIRED_H2_TOKENS if token not in present
    ]

    run_grade_headings = [
        section.heading
        for section in sections
        if section.token in _RUN_GRADE_H2_TOKENS
    ]
    if missing and len(run_grade_headings) >= _WRONG_SCHEMA_MIN_RUN_H2S:
        return [
            JiraGradeFinding(
                kind=FINDING_WRONG_SCHEMA,
                blocking=True,
                message=(
                    "run-grade body at a jira-grade path: found run-grade "
                    f"sections ({', '.join(run_grade_headings)}); the "
                    "jira-grade contract is "
                    f"{', '.join(JIRA_GRADE_REQUIRED_H2S)}"
                ),
            )
        ]

    findings = [
        JiraGradeFinding(
            kind=FINDING_MISSING_SECTION,
            blocking=True,
            message=f"missing required section: ## {_DISPLAY_BY_TOKEN[token]}",
        )
        for token in missing
    ]

    seen: set[str] = set()
    for section in sections:
        if section.token not in JIRA_GRADE_REQUIRED_H2_TOKENS:
            findings.append(
                JiraGradeFinding(
                    kind=FINDING_UNKNOWN_SECTION,
                    blocking=True,
                    message=(
                        f"unknown section: ## {section.heading} — the "
                        "jira-grade schema is closed to "
                        f"{', '.join(JIRA_GRADE_REQUIRED_H2S)}"
                    ),
                )
            )
            continue
        display = _DISPLAY_BY_TOKEN[section.token]
        if section.token in seen:
            findings.append(
                JiraGradeFinding(
                    kind=FINDING_DUPLICATE_SECTION,
                    blocking=True,
                    message=f"duplicate section: ## {display}",
                )
            )
            continue
        seen.add(section.token)
        if not section.body:
            findings.append(
                JiraGradeFinding(
                    kind=FINDING_EMPTY_SECTION,
                    blocking=True,
                    message=f"empty section body: ## {display}",
                )
            )
    return findings


def load_jira_grade_detail(path: Path) -> str:
    """Read ``path`` and return its text, raising on any blocking finding.

    The loud-failure form consumers want: a jira-grade artifact that is
    missing, unreadable, or off-contract raises
    :class:`JiraGradeContractError` rather than degrading into a
    placeholder. Prose findings are not consulted — read-time consumption
    validates structure only.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise JiraGradeContractError(
            f"jira-grade detail could not be read: {path} ({exc})", path=path
        ) from exc
    blocking = [f for f in validate_jira_grade_body(text) if f.blocking]
    if blocking:
        detail = "\n".join(f"  - {f.message}" for f in blocking)
        raise JiraGradeContractError(
            f"jira-grade detail does not meet the contract: {path}\n{detail}",
            path=path,
            findings=blocking,
        )
    return text


# --------------------------------------------------------------------------
# The plain-English gate
# --------------------------------------------------------------------------

# Word cap for one sentence, measured *after* code anchors are stripped.
# Past this a reader has to re-read; the remedy is always a period.
_MAX_SENTENCE_WORDS = 35

# Advisory-only shape signals: a section that has stopped being compact,
# and a sentence stacking clauses behind commas.
_MAX_SECTION_WORDS = 250
_MAX_SENTENCE_COMMAS = 4

# Phrases that always carry more syllables than meaning. High precision is
# the entry bar — a blocking finding on a false positive costs an authoring
# retry, so only add a phrase whose direct rewrite is obvious.
_FILLER_PHRASES = (
    "as a matter of fact",
    "at the end of the day",
    "at this point in time",
    "due to the fact that",
    "for all intents and purposes",
    "in order to",
    "in terms of",
    "it is important to note",
    "it is worth noting",
    "it should be noted",
    "needless to say",
    "the fact that",
    "this means that",
)

_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_AUTOLINK_RE = re.compile(r"<[^>\s]+>")
_HEADING_LINE_RE = re.compile(r"^\s{0,3}#{1,6}\s")
_LIST_MARKER_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_BLOCKQUOTE_RE = re.compile(r"^\s*>\s?")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_TRIM_CHARS = ".,;:!?()[]{}\"'"


def _strip_fenced_blocks(text: str) -> str:
    """Drop fenced code blocks, delimiters included."""
    kept: list[str] = []
    fence: Optional[str] = None
    for line in text.splitlines():
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)[0]
            if fence is None:
                fence = marker
                continue
            if marker == fence:
                fence = None
                continue
        if fence is None:
            kept.append(line)
    return "\n".join(kept)


def _strip_inline_anchors(text: str) -> str:
    """Remove inline code spans and link/autolink targets.

    Link *text* survives (it is prose); the URL does not. A backticked
    symbol is an immutable fact the gate must never measure, so the whole
    span goes.
    """
    text = _LINK_RE.sub(r"\1", text)
    text = _INLINE_CODE_RE.sub(" ", text)
    return _AUTOLINK_RE.sub(" ", text)


def _looks_like_code(token: str) -> bool:
    """True when ``token`` is an identifier / path / acronym, not prose.

    Same shape as ``create.py:_looks_like_code``: path or identifier
    punctuation, any digit, or an uppercase letter past the first character.
    A plainly Title-cased word is prose.
    """
    if any(ch in token for ch in "/._`@$"):
        return True
    if any(ch.isdigit() for ch in token):
        return True
    return any(ch.isupper() for ch in token[1:])


def _prose_words(sentence: str) -> list[str]:
    """Words that count toward a sentence's length — code anchors excluded."""
    words: list[str] = []
    for raw in sentence.split():
        word = raw.strip(_WORD_TRIM_CHARS)
        if word and not _looks_like_code(word):
            words.append(word)
    return words


def _prose_sentences(text: str) -> list[str]:
    """Extract prose sentences, skipping code and structure.

    Fenced blocks and heading lines drop out entirely. Each list item is its
    own unit (so two short bullets never merge into one long "sentence"),
    continuation lines fold into the item they continue, and a blank line
    ends a block.
    """
    blocks: list[list[str]] = []
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if current:
            blocks.append(current)
            current = []

    for line in _strip_fenced_blocks(text).splitlines():
        if not line.strip() or _HEADING_LINE_RE.match(line):
            flush()
            continue
        line = _BLOCKQUOTE_RE.sub("", line)
        if _LIST_MARKER_RE.match(line):
            flush()
            line = _LIST_MARKER_RE.sub("", line)
        current.append(line.strip())
    flush()

    sentences: list[str] = []
    for block in blocks:
        joined = " ".join(block)
        sentences.extend(
            part.strip() for part in _SENTENCE_SPLIT_RE.split(joined) if part.strip()
        )
    return sentences


def check_plain_english(text: str) -> list[JiraGradeFinding]:
    """Flag padding and buried outcomes in ``text``'s prose.

    Deterministic and mechanical by design. Code anchors — fenced blocks,
    backtick spans, links, path- and identifier-shaped tokens — are
    immutable facts and are stripped before anything is measured, so a long
    symbol can never trip a length check.

    Blocking findings are the high-precision signals (a denylisted filler
    phrase, a sentence past :data:`_MAX_SENTENCE_WORDS`) and drive the
    authoring retry loop. Shape heuristics stay advisory. Nothing here
    rewrites the text.
    """
    fence_finding = _unterminated_fence_finding(text)
    if fence_finding is not None:
        return [fence_finding]

    findings: list[JiraGradeFinding] = []

    # Collapse whitespace before matching: prose is routinely hard-wrapped,
    # and a phrase straddling a line break must not escape the denylist. The
    # sentence checks below already fold lines (``_prose_sentences`` joins a
    # block with spaces), so this keeps the two halves of the gate agreeing
    # that a newline is a space.
    scan = " ".join(
        _strip_inline_anchors(_strip_fenced_blocks(text)).lower().split()
    )
    for phrase in sorted(_FILLER_PHRASES, key=len, reverse=True):
        if phrase in scan:
            # Blank the match so a phrase contained in a longer one
            # ("the fact that" inside "due to the fact that") reports once.
            scan = scan.replace(phrase, " ")
            findings.append(
                JiraGradeFinding(
                    kind=FINDING_FILLER_PHRASE,
                    blocking=True,
                    message=f'filler phrase "{phrase}" — say it directly',
                )
            )

    for sentence in _prose_sentences(text):
        clean = _strip_inline_anchors(sentence)
        words = _prose_words(clean)
        if len(words) > _MAX_SENTENCE_WORDS:
            findings.append(
                JiraGradeFinding(
                    kind=FINDING_LONG_SENTENCE,
                    blocking=True,
                    message=(
                        f"sentence runs {len(words)} words past code anchors "
                        f"(cap {_MAX_SENTENCE_WORDS}) — split it: "
                        f"{_excerpt(sentence)}"
                    ),
                )
            )
        elif clean.count(",") >= _MAX_SENTENCE_COMMAS:
            findings.append(
                JiraGradeFinding(
                    kind=FINDING_DENSE_CLAUSES,
                    blocking=False,
                    message=(
                        f"{clean.count(',')} clauses stacked in one sentence: "
                        f"{_excerpt(sentence)}"
                    ),
                )
            )

    for section in _scan_sections(text):
        words = sum(
            len(_prose_words(_strip_inline_anchors(sentence)))
            for sentence in _prose_sentences(section.body)
        )
        if words > _MAX_SECTION_WORDS:
            findings.append(
                JiraGradeFinding(
                    kind=FINDING_LONG_SECTION,
                    blocking=False,
                    message=(
                        f"## {section.heading} runs {words} words "
                        f"(compact is under {_MAX_SECTION_WORDS})"
                    ),
                )
            )
    return findings


def _excerpt(sentence: str, limit: int = 60) -> str:
    """First ``limit`` characters of ``sentence``, for locating a finding."""
    collapsed = " ".join(sentence.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rstrip() + "…"
