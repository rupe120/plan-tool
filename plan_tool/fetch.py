"""Fetch and extract readable text from documentation URLs (stdlib only).

``plan-tool create`` gathers authoritative developer / API reference URLs
via a claude web-research round-trip (see
:func:`plan_tool.create.propose_references_from_claude`). This module turns
those *links* into *content*: it fetches each URL, strips the HTML down to
readable text, and hands back :class:`FetchedDoc` records that the create
flow folds into the body-synthesis prompt so the generated plan body is
grounded in real documentation rather than the seed prose alone.

Why stdlib-only (``urllib`` + ``html.parser``): the project's dependency
contract is ``pydantic`` + ``pyyaml`` and nothing else (see
``pyproject.toml``). A reference-fetch feature is not worth pulling
``requests`` / ``httpx`` / ``beautifulsoup`` into that tree, and the
extraction quality only needs to be "good enough to ground a synthesis
prompt", not pixel-perfect readability.

Failure is never fatal. Every fetch path funnels exceptions into a
:class:`FetchedDoc` carrying an ``error`` string and empty ``text`` — the
create flow drops non-``ok`` docs from the prompt and proceeds. A dead
link, a timeout, or a non-HTML payload must never abort a create.

Bounds (all overridable per call, defaults tuned for a synthesis prompt):

- per-URL socket read cap (:data:`DEFAULT_MAX_BYTES_PER_URL`) so a giant
  page can't exhaust memory,
- per-URL extracted-text cap (:data:`DEFAULT_MAX_CHARS_PER_URL`),
- a total extracted-text budget across all docs
  (:data:`DEFAULT_TOTAL_CHAR_BUDGET`) so the synthesis prompt stays bounded
  regardless of how many references claude returned,
- a per-request timeout (:data:`DEFAULT_TIMEOUT_S`).

Only ``http`` / ``https`` URLs are fetched; any other scheme is rejected
without a network call (defence against an ``file://`` / ``gopher://`` URL
slipping through, even though :class:`~plan_tool.create.Reference` already
validates the scheme upstream).
"""

from __future__ import annotations

import json
import socket
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from typing import Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# --- bounds (see module docstring) ---

DEFAULT_TIMEOUT_S = 10.0
DEFAULT_MAX_BYTES_PER_URL = 2_000_000
DEFAULT_MAX_CHARS_PER_URL = 20_000
DEFAULT_TOTAL_CHAR_BUDGET = 60_000

# Identifies the fetcher to servers that gate on User-Agent. Kept honest
# (no browser spoofing) so an operator inspecting their access logs can
# see exactly what hit them.
_USER_AGENT = "plan-tool reference-fetch (+https://github.com/rupe120/plan-tool)"

# Tags whose text content is noise for a documentation extract — dropped
# wholesale (including nested children). ``head`` is deliberately NOT here:
# its ``<title>`` is the one head element worth keeping.
_SKIP_TAGS = frozenset(
    {"script", "style", "noscript", "template", "svg"}
)

# Tags after which a newline is inserted so the flattened text keeps
# paragraph / list / row structure instead of run-on prose.
_BLOCK_TAGS = frozenset(
    {
        "p", "div", "section", "article", "header", "footer", "main",
        "aside", "nav", "ul", "ol", "li", "table", "tr", "br", "hr",
        "h1", "h2", "h3", "h4", "h5", "h6", "pre", "blockquote", "figure",
        "figcaption", "dd", "dt", "dl",
    }
)


@dataclass(frozen=True)
class FetchedDoc:
    """One fetched documentation URL.

    ``ok`` docs (``error is None`` and non-empty ``text``) are the only
    ones rendered into the synthesis prompt; the rest are kept around so
    the run log / caller can report *why* a reference yielded no content.
    ``title`` is the page ``<title>`` when present (empty otherwise).
    ``truncated`` flags that either the socket read or the extracted text
    hit its cap, so the rendered block can say so.
    """

    url: str
    title: str = ""
    text: str = ""
    error: Optional[str] = None
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.text)


class _TextExtractor(HTMLParser):
    """Collapse an HTML document to readable text + its ``<title>``.

    Skips :data:`_SKIP_TAGS` subtrees entirely (tracked by depth so nested
    ``<script>`` inside skipped content doesn't underflow the counter),
    inserts newlines around :data:`_BLOCK_TAGS`, and captures ``<title>``
    text separately. Whitespace is normalized in :meth:`get_text` rather
    than per-chunk so inline runs ("foo ``<code>`` bar") don't lose their
    separating spaces.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0
        self._in_title = False
        self.title = ""

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_startendtag(self, tag: str, attrs: object) -> None:
        # Self-closing block tags (``<br/>``) still want their newline; a
        # self-closing skip tag opens and closes in one event, so no
        # depth bookkeeping is needed.
        if tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data
            return
        self._chunks.append(data)

    def get_text(self) -> str:
        """Return the extracted body text with whitespace normalized.

        Each newline-delimited segment is internally space-collapsed; empty
        segments are dropped so the result is one non-blank line per block.
        """
        raw = "".join(self._chunks)
        lines = (" ".join(segment.split()) for segment in raw.split("\n"))
        return "\n".join(line for line in lines if line)


def _decode(raw: bytes, charset: Optional[str]) -> str:
    """Decode response bytes, falling back to UTF-8 on a bad/absent charset.

    ``errors="replace"`` keeps a partially-mojibaked page usable rather
    than raising — the extracted text only needs to be good enough to
    ground a synthesis prompt.
    """
    for enc in (charset, "utf-8"):
        if not enc:
            continue
        try:
            return raw.decode(enc, errors="replace")
        except LookupError:
            continue
    return raw.decode("utf-8", errors="replace")


def fetch_url(
    url: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_bytes: int = DEFAULT_MAX_BYTES_PER_URL,
    max_chars: int = DEFAULT_MAX_CHARS_PER_URL,
) -> FetchedDoc:
    """Fetch one URL and return a :class:`FetchedDoc`. Never raises.

    HTML payloads are run through :class:`_TextExtractor`; other ``text/``,
    JSON, and XML payloads are kept verbatim (already human-readable);
    anything else (PDF, images, octet-stream) yields an ``error`` doc.
    The socket read is capped at ``max_bytes + 1`` so over-cap pages are
    detected and flagged ``truncated`` rather than silently clipped.
    """
    if not (url.startswith("http://") or url.startswith("https://")):
        return FetchedDoc(url=url, error="unsupported URL scheme (http/https only)")

    req = Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
        },
    )
    try:
        with urlopen(req, timeout=timeout_s) as resp:
            content_type = resp.headers.get_content_type()
            charset = resp.headers.get_content_charset()
            raw = resp.read(max_bytes + 1)
    except HTTPError as exc:
        return FetchedDoc(url=url, error=f"HTTP {exc.code}")
    except (URLError, socket.timeout, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        return FetchedDoc(url=url, error=f"fetch failed: {reason}")
    except Exception as exc:  # never let a fetch bug abort a create
        return FetchedDoc(url=url, error=f"fetch error: {exc}")

    truncated_bytes = len(raw) > max_bytes
    body = _decode(raw[:max_bytes], charset)

    if "html" in content_type:
        extractor = _TextExtractor()
        try:
            extractor.feed(body)
        except Exception:
            # A malformed document can trip the parser; keep whatever text
            # was accumulated before the break rather than failing the doc.
            pass
        text = extractor.get_text()
        title = " ".join(extractor.title.split())
    elif (
        content_type.startswith("text/")
        or "json" in content_type
        or "xml" in content_type
    ):
        text = body
        title = ""
    else:
        return FetchedDoc(
            url=url, error=f"unsupported content type: {content_type}"
        )

    truncated = truncated_bytes or len(text) > max_chars
    text = text[:max_chars].strip()
    if not text:
        return FetchedDoc(url=url, title=title, error="no extractable text")
    return FetchedDoc(url=url, title=title, text=text, truncated=truncated)


def fetch_reference_docs(
    urls: Sequence[str],
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_bytes_per_url: int = DEFAULT_MAX_BYTES_PER_URL,
    max_chars_per_url: int = DEFAULT_MAX_CHARS_PER_URL,
    total_char_budget: int = DEFAULT_TOTAL_CHAR_BUDGET,
) -> list[FetchedDoc]:
    """Fetch each URL in order, stopping once the total text budget is spent.

    Returns one :class:`FetchedDoc` per attempted URL (including the
    ``error`` docs) in input order, up to the point the running budget is
    exhausted. The per-URL char cap is clamped to whatever budget remains
    so the *last* doc fetched can't blow past the total. URLs reached after
    the budget runs out are simply not fetched (no record emitted) — the
    references they came from still render as plain links in the plan body.
    """
    docs: list[FetchedDoc] = []
    remaining = total_char_budget
    for url in urls:
        if remaining <= 0:
            break
        doc = fetch_url(
            url,
            timeout_s=timeout_s,
            max_bytes=max_bytes_per_url,
            max_chars=min(max_chars_per_url, remaining),
        )
        docs.append(doc)
        if doc.ok:
            remaining -= len(doc.text)
    return docs


def render_reference_docs_block(docs: Sequence[FetchedDoc]) -> str:
    """Render ``ok`` docs as a markdown block for the synthesis prompt.

    Non-``ok`` docs are dropped. Returns the empty string when nothing was
    successfully fetched, which the caller treats as "no doc grounding
    available" (the synthesis prompt then falls back to seed-only).
    """
    sections: list[str] = []
    for doc in docs:
        if not doc.ok:
            continue
        header = doc.title or doc.url
        suffix = " (truncated)" if doc.truncated else ""
        sections.append(
            f"### {header}\nSource: {doc.url}{suffix}\n\n{doc.text}"
        )
    return "\n\n".join(sections)


def docs_to_json(docs: Sequence[FetchedDoc]) -> str:
    """Serialize fetched docs to a JSON string for a checkpoint payload."""
    return json.dumps([asdict(d) for d in docs], ensure_ascii=False)


def docs_from_json(raw: str) -> list[FetchedDoc]:
    """Inverse of :func:`docs_to_json`; tolerant of partial / legacy rows.

    Returns an empty list on any JSON-level failure (the caller then
    behaves as a cache miss). Per-row, missing fields fall back to their
    dataclass defaults so a checkpoint written by an older schema still
    loads.
    """
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []
    out: list[FetchedDoc] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str):
            continue
        out.append(
            FetchedDoc(
                url=url,
                title=item.get("title", "") or "",
                text=item.get("text", "") or "",
                error=item.get("error"),
                truncated=bool(item.get("truncated", False)),
            )
        )
    return out
