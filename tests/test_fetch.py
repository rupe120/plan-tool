"""Unit tests for ``plan_tool.fetch`` — URL content fetching + extraction.

The autouse ``_no_real_network_fetch`` conftest gate patches
``plan_tool.fetch.urlopen`` to raise; every test here that wants a
controlled response monkeypatches the same attribute with a local stub,
which takes precedence (last setattr wins). No test in this module touches
the live network.
"""

from __future__ import annotations

from typing import Optional

import pytest

import plan_tool.fetch as fetch
from plan_tool.fetch import (
    DEFAULT_MAX_CHARS_PER_URL,
    FetchedDoc,
    docs_from_json,
    docs_to_json,
    fetch_reference_docs,
    fetch_url,
    render_reference_docs_block,
)
from urllib.error import HTTPError, URLError


class _FakeHeaders:
    def __init__(self, ctype: str, charset: Optional[str]) -> None:
        self._ctype = ctype
        self._charset = charset

    def get_content_type(self) -> str:
        return self._ctype

    def get_content_charset(self) -> Optional[str]:
        return self._charset


class _FakeResponse:
    """Minimal stand-in for the object ``urlopen`` yields as a context manager."""

    def __init__(
        self,
        body: bytes,
        *,
        content_type: str = "text/html",
        charset: Optional[str] = "utf-8",
    ) -> None:
        self._body = body
        self.headers = _FakeHeaders(content_type, charset)

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            return self._body
        return self._body[:n]

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def _patch_urlopen(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Route ``plan_tool.fetch.urlopen`` to ``handler(req, timeout=...)``."""
    monkeypatch.setattr(fetch, "urlopen", handler)


# --- HTML extraction ---

def test_html_extraction_drops_script_style_and_keeps_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = (
        b"<html><head><title>  My Page </title>"
        b"<style>.a{color:red}</style></head>"
        b"<body><script>var x=1;</script>"
        b"<p>First paragraph.</p><p>Second paragraph.</p>"
        b"<ul><li>one</li><li>two</li></ul></body></html>"
    )
    _patch_urlopen(monkeypatch, lambda req, timeout=None: _FakeResponse(html))

    doc = fetch_url("https://example.com/page")

    assert doc.ok
    assert doc.title == "My Page"
    assert "First paragraph." in doc.text
    assert "Second paragraph." in doc.text
    assert "one" in doc.text and "two" in doc.text
    # Script / style bodies must not leak into the extracted text.
    assert "var x=1" not in doc.text
    assert "color:red" not in doc.text


def test_plain_text_kept_verbatim(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_urlopen(
        monkeypatch,
        lambda req, timeout=None: _FakeResponse(
            b"raw text body", content_type="text/plain"
        ),
    )
    doc = fetch_url("https://example.com/readme.txt")
    assert doc.ok
    assert doc.text == "raw text body"
    assert doc.title == ""


def test_non_text_content_type_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_urlopen(
        monkeypatch,
        lambda req, timeout=None: _FakeResponse(
            b"%PDF-1.7 ...", content_type="application/pdf"
        ),
    )
    doc = fetch_url("https://example.com/manual.pdf")
    assert not doc.ok
    assert doc.error is not None
    assert "content type" in doc.error


# --- scheme rejection (no network call) ---

@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://x/y", "gopher://z"])
def test_non_http_scheme_rejected_without_fetch(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    def explode(req: object, timeout: object = None) -> object:
        raise AssertionError("urlopen must not be called for a bad scheme")

    _patch_urlopen(monkeypatch, explode)
    doc = fetch_url(url)
    assert not doc.ok
    assert "scheme" in (doc.error or "")


# --- failure handling ---

def test_http_error_becomes_error_doc(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_404(req: object, timeout: object = None) -> object:
        raise HTTPError("https://example.com", 404, "Not Found", {}, None)

    _patch_urlopen(monkeypatch, raise_404)
    doc = fetch_url("https://example.com")
    assert not doc.ok
    assert doc.error == "HTTP 404"


def test_url_error_becomes_error_doc(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_conn(req: object, timeout: object = None) -> object:
        raise URLError("connection refused")

    _patch_urlopen(monkeypatch, raise_conn)
    doc = fetch_url("https://example.com")
    assert not doc.ok
    assert doc.error is not None and "fetch failed" in doc.error


def test_unexpected_exception_never_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(req: object, timeout: object = None) -> object:
        raise RuntimeError("kaboom")

    _patch_urlopen(monkeypatch, boom)
    doc = fetch_url("https://example.com")  # must not raise
    assert not doc.ok
    assert doc.error is not None and "kaboom" in doc.error


def test_empty_extracted_text_is_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_urlopen(
        monkeypatch,
        lambda req, timeout=None: _FakeResponse(
            b"<html><head><title>T</title></head><body></body></html>"
        ),
    )
    doc = fetch_url("https://example.com")
    assert not doc.ok
    assert doc.error == "no extractable text"
    # Title is still captured even when the body yields nothing.
    assert doc.title == "T"


# --- bounds ---

def test_text_truncated_to_max_chars(monkeypatch: pytest.MonkeyPatch) -> None:
    body = ("x" * 500).encode("utf-8")
    _patch_urlopen(
        monkeypatch,
        lambda req, timeout=None: _FakeResponse(body, content_type="text/plain"),
    )
    doc = fetch_url("https://example.com", max_chars=100)
    assert doc.ok
    assert len(doc.text) == 100
    assert doc.truncated is True


def test_oversize_body_flags_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = ("y" * 50).encode("utf-8")
    _patch_urlopen(
        monkeypatch,
        lambda req, timeout=None: _FakeResponse(body, content_type="text/plain"),
    )
    # max_bytes smaller than the body => read(max_bytes+1) sees more than
    # max_bytes => truncated flagged even though the kept text fits max_chars.
    doc = fetch_url("https://example.com", max_bytes=10, max_chars=1000)
    assert doc.ok
    assert doc.truncated is True
    assert len(doc.text) <= 10


# --- multi-URL fetch + total budget ---

def test_fetch_reference_docs_stops_at_total_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Each URL serves 40 chars of plain text; a 50-char total budget admits
    # the first doc fully, clamps the second to the 10 chars that remain,
    # and the third URL is never fetched (budget exhausted).
    fetched_urls: list[str] = []

    def handler(req: object, timeout: object = None) -> object:
        fetched_urls.append(req.full_url)
        return _FakeResponse(b"z" * 40, content_type="text/plain")

    _patch_urlopen(monkeypatch, handler)
    docs = fetch_reference_docs(
        ["https://a", "https://b", "https://c"],
        total_char_budget=50,
        max_chars_per_url=40,
    )

    assert [d.url for d in docs] == ["https://a", "https://b"]
    assert len(docs[0].text) == 40
    assert len(docs[1].text) == 10  # clamped to remaining budget
    assert fetched_urls == ["https://a", "https://b"]


def test_fetch_reference_docs_includes_error_docs_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(req: object, timeout: object = None) -> object:
        if req.full_url == "https://bad":
            raise URLError("nope")
        return _FakeResponse(b"<p>ok</p>")

    _patch_urlopen(monkeypatch, handler)
    docs = fetch_reference_docs(["https://good", "https://bad"])
    assert [d.url for d in docs] == ["https://good", "https://bad"]
    assert docs[0].ok
    assert not docs[1].ok


# --- rendering ---

def test_render_block_drops_error_docs_and_marks_truncation() -> None:
    docs = [
        FetchedDoc(url="https://a", title="Alpha", text="body a"),
        FetchedDoc(url="https://b", error="HTTP 500"),
        FetchedDoc(url="https://c", title="", text="body c", truncated=True),
    ]
    block = render_reference_docs_block(docs)
    assert "### Alpha" in block
    assert "body a" in block
    assert "https://b" not in block  # error doc dropped
    assert "### https://c" in block  # falls back to URL when no title
    assert "(truncated)" in block


def test_render_block_empty_when_nothing_ok() -> None:
    docs = [FetchedDoc(url="https://a", error="HTTP 404")]
    assert render_reference_docs_block(docs) == ""


# --- JSON round-trip (checkpoint payload) ---

def test_docs_json_round_trip() -> None:
    docs = [
        FetchedDoc(url="https://a", title="T", text="body", truncated=True),
        FetchedDoc(url="https://b", error="HTTP 404"),
    ]
    restored = docs_from_json(docs_to_json(docs))
    assert restored == docs


def test_docs_from_json_tolerates_garbage() -> None:
    assert docs_from_json("not json") == []
    assert docs_from_json("{}") == []  # not a list
    # Rows without a url string are skipped; valid rows survive.
    assert docs_from_json('[{"no":"url"}, {"url":"https://x"}]') == [
        FetchedDoc(url="https://x")
    ]


def test_default_char_cap_is_a_sane_bound() -> None:
    # Guards against an accidental edit that removes the per-URL cap.
    assert 0 < DEFAULT_MAX_CHARS_PER_URL <= 100_000
