"""Shared readers for the routers' phase table and DIRECTIVES.md anchors (BACKLOG #518)."""

from __future__ import annotations

import re
from pathlib import Path

from plan_tool.review import fenced_spans

ROOT = Path(__file__).resolve().parent.parent
DIRECTIVES = ROOT / "integrations/shared/DIRECTIVES.md"
SECTION_HEADING = "## Read these `DIRECTIVES.md` sections before acting in a phase"
LINK_RE = re.compile(r"\]\(DIRECTIVES\.md#([^)]+)\)")


def slug(heading: str) -> str:
    """Approximate GitHub's anchor rule: lowercase, drop punctuation (keep word
    characters, hyphens), spaces to hyphens. A literal heading that already looks
    like a ``-1`` suffix is not reserved."""
    text = heading.replace("`", "").lower()
    return re.sub(r"[^\w -]", "", text).replace(" ", "-")


def anchors(text: str) -> set[str]:
    """Anchors of the real headings: a ``#`` line inside a fence is not one, and a
    repeated heading gets the ``-1``, ``-2`` suffix."""
    fenced = fenced_spans(text)
    seen: dict[str, int] = {}
    found: set[str] = set()
    for m in re.finditer(r"^#{1,6} (.+)$", text, re.M):
        if any(start <= m.start() < end for start, end in fenced):
            continue
        base = slug(m.group(1))
        count = seen.get(base, 0)
        found.add(base if count == 0 else f"{base}-{count}")
        seen[base] = count + 1
    return found


def phase_section(router_text: str, label: str) -> str:
    assert router_text.count(SECTION_HEADING) == 1, f"{label} lost its phase table"
    start = router_text.index(SECTION_HEADING)
    end = router_text.find("\n## ", start + len(SECTION_HEADING))
    assert end != -1, f"{label}: no `##` section follows the phase table"
    return router_text[start:end]
