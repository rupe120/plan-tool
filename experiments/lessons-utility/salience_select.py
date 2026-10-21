#!/usr/bin/env python3
"""C3 prototype — top-K salience selection for the lessons store.

Pure stdlib, read-only. Replaces the production *blind recency* truncation
(plan_tool/lessons.py:_select_lessons_body, which keeps the newest bullets that
fit 48 KB) with a **salience-ranked** selection: score each bullet by citation
count (from project-citations.jsonl) + recency, then pack the top bullets under
a byte budget.

This is an EXPERIMENT prototype, not shipped behavior. If it wins the C1-vs-C3
A/B (see DESIGN.md), it becomes a real plan via `create --from-existing`.

The join to citations is by `rule_hash` = sha256(rule.strip().lower())[:16],
reproducing plan_tool/lessons.py:_rule_hash. Validated at ~98% join coverage.

⚠️  FINDING (2026-06-18): with the CURRENT data this selector degenerates to
recency. `project-citations.jsonl` records ONE record per bullet *at creation*
(append-time audit), not a record each time a lesson is *retrieved/applied* —
so every bullet has exactly 1 citation and the citation term is constant. For
salience to beat recency, the tool must first log a *reuse* event (increment a
counter when a lesson actually surfaces in / influences a run). The scoring
machinery below is correct and ready for that signal; it just has nothing to
chew on yet. See LESSONS.md F2. Until then `--compare` will show C3 ≈ C1.

Usage:
    # rank + select under a budget, print the selected block
    python experiments/lessons-utility/salience_select.py --max-bytes 49152

    # compare C3 salience vs C1 recency truncation at the same budget
    python experiments/lessons-utility/salience_select.py --compare

    # tune the score (citation weight vs recency weight)
    python experiments/lessons-utility/salience_select.py --w-cite 0.7 --w-recency 0.3 --compare

    # emit the selected bullets as a prompt-ready block (for an A/B run)
    python experiments/lessons-utility/salience_select.py --render --max-bytes 24576
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_MAX_INJECT_BYTES = 49152
_TRUNCATION_MARKER = "… _(older entries truncated; see file on disk)_"
_RULE_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_SURFACE_RE = re.compile(r"^-\s+`\[([^\]]+)\]`")


def _rule_hash(rule: str) -> str:
    """Reproduces plan_tool/lessons.py:_rule_hash."""
    return hashlib.sha256(rule.strip().lower().encode("utf-8")).hexdigest()[:16]


def _split_header_and_bullets(body: str) -> tuple[str, list[str]]:
    lines = body.splitlines()
    first = next((i for i, ln in enumerate(lines) if ln.startswith("- ")), len(lines))
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


@dataclass
class Bullet:
    idx: int  # position in file, 0 = oldest (appends land at end)
    text: str
    surface: str | None
    rule_hash: str | None
    n_bytes: int
    citations: int = 0
    score: float = field(default=0.0)


def _extract(bullets: list[str]) -> list[Bullet]:
    out: list[Bullet] = []
    for i, b in enumerate(bullets):
        sm = _SURFACE_RE.match(b)
        rm = _RULE_RE.search(b)
        rh = _rule_hash(rm.group(1)) if rm else None
        out.append(Bullet(idx=i, text=b, surface=sm.group(1) if sm else None,
                          rule_hash=rh, n_bytes=len(b.encode("utf-8")) + 2))
    return out


def _citation_counts(cite_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not cite_path.exists():
        return counts
    for line in cite_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rh = json.loads(line).get("rule_hash")
        except json.JSONDecodeError:
            continue
        if rh:
            counts[rh] = counts.get(rh, 0) + 1
    return counts


def score_bullets(bullets: list[Bullet], w_cite: float, w_recency: float) -> None:
    """Assign each bullet a salience score in-place.

    score = w_cite * norm(log1p(citations)) + w_recency * recency_rank

    - citation term uses log1p so a few noisy high-count sources don't dominate,
      normalized to [0,1] by the max in the corpus.
    - recency_rank is the bullet's file position normalized to [0,1] (newest=1),
      so a never-cited but brand-new lesson still competes (matches the intuition
      behind today's recency truncation, just as one term instead of the only one).
    """
    n = len(bullets)
    max_log = max((math.log1p(b.citations) for b in bullets), default=0.0) or 1.0
    for b in bullets:
        cite_norm = math.log1p(b.citations) / max_log
        recency = b.idx / (n - 1) if n > 1 else 1.0
        b.score = w_cite * cite_norm + w_recency * recency


def select_under_budget(bullets: list[Bullet], max_bytes: int, key) -> list[Bullet]:
    """Greedily pack bullets (ordered by `key`, desc) under max_bytes."""
    chosen: list[Bullet] = []
    used = 0
    for b in sorted(bullets, key=key, reverse=True):
        if chosen and used + b.n_bytes > max_bytes:
            continue  # keep trying smaller bullets — fill the budget, don't stop
        chosen.append(b)
        used += b.n_bytes
    return chosen


def recency_select(bullets: list[Bullet], max_bytes: int) -> list[Bullet]:
    """C1 control: the production newest-first truncation (contiguous suffix)."""
    chosen: list[Bullet] = []
    used = 0
    for b in reversed(bullets):  # newest first
        if chosen and used + b.n_bytes > max_bytes:
            break  # production stops at the first bullet that doesn't fit
        chosen.append(b)
        used += b.n_bytes
    chosen.reverse()
    return chosen


def render_block(header: str, chosen: list[Bullet], truncated: bool) -> str:
    parts: list[str] = []
    if header:
        parts.append(header)
    if truncated:
        parts.append(_TRUNCATION_MARKER)
    # render in file order so any narrative ordering is preserved
    parts.extend(b.text for b in sorted(chosen, key=lambda b: b.idx))
    return ("\n\n".join(parts).rstrip() + "\n") if parts else ""


def _load(md_path: Path, cite_path: Path, w_cite: float, w_recency: float) -> tuple[str, list[Bullet]]:
    body = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    header, raw = _split_header_and_bullets(body)
    bullets = _extract(raw)
    counts = _citation_counts(cite_path)
    for b in bullets:
        b.citations = counts.get(b.rule_hash, 0) if b.rule_hash else 0
    score_bullets(bullets, w_cite, w_recency)
    return header, bullets


def cmd_compare(header, bullets, max_bytes) -> None:
    c1 = recency_select(bullets, max_bytes)
    c3 = select_under_budget(bullets, max_bytes, key=lambda b: b.score)
    c1_ids = {b.idx for b in c1}
    c3_ids = {b.idx for b in c3}
    overlap = c1_ids & c3_ids
    only_c3 = [b for b in c3 if b.idx not in c1_ids]
    only_c1 = [b for b in c1 if b.idx not in c3_ids]
    union = c1_ids | c3_ids

    print(f"# C1 (recency) vs C3 (salience) @ {max_bytes:,} bytes\n")
    print(f"  total bullets        {len(bullets)}")
    print(f"  C1 recency kept      {len(c1)}")
    print(f"  C3 salience kept     {len(c3)}")
    print(f"  overlap              {len(overlap)}  (Jaccard {len(overlap)/len(union):.2f})")
    print()
    # The win: high-cited lessons C1 drops purely because they're old.
    won = sorted(only_c3, key=lambda b: b.citations, reverse=True)
    print(f"  C3 RESCUES {len(only_c3)} bullets C1 drops by recency "
          f"({sum(1 for b in only_c3 if b.citations > 0)} of them cited):")
    for b in won[:8]:
        rule = (_RULE_RE.search(b.text).group(1)[:72] if _RULE_RE.search(b.text) else b.text[:72])
        print(f"    [{b.citations:>3} cites] [{b.surface or '-'}] {rule}…")
    print()
    # The waste C3 avoids: never-cited recent bullets C1 keeps.
    wasted = sum(1 for b in only_c1 if b.citations == 0)
    print(f"  C1 keeps {len(only_c1)} bullets C3 drops; {wasted} of those have ZERO citations")
    print(f"  (i.e. recency truncation spends budget on {wasted} never-referenced lessons)")


def cmd_rank(header, bullets, max_bytes, render: bool, top: int) -> None:
    chosen = select_under_budget(bullets, max_bytes, key=lambda b: b.score)
    truncated = len(chosen) < len(bullets)
    if render:
        sys.stdout.write(render_block(header, chosen, truncated))
        return
    used = sum(b.n_bytes for b in chosen)
    print(f"# C3 salience selection @ {max_bytes:,} bytes\n")
    print(f"  selected {len(chosen)} of {len(bullets)} bullets, ~{used:,} bytes\n")
    print(f"  top {min(top, len(chosen))} by salience score:")
    for b in sorted(chosen, key=lambda b: b.score, reverse=True)[:top]:
        rule = (_RULE_RE.search(b.text).group(1)[:64] if _RULE_RE.search(b.text) else b.text[:64])
        print(f"    {b.score:.3f}  [{b.citations:>3} cites] [{b.surface or '-':<16}] {rule}…")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("md", nargs="?", default=".plan-tool/lessons/project.md")
    ap.add_argument("citations", nargs="?", default=".plan-tool/lessons/project-citations.jsonl")
    ap.add_argument("--max-bytes", type=int, default=_MAX_INJECT_BYTES)
    ap.add_argument("--w-cite", type=float, default=0.5, help="citation-count weight")
    ap.add_argument("--w-recency", type=float, default=0.5, help="recency weight")
    ap.add_argument("--compare", action="store_true", help="C1 recency vs C3 salience diff")
    ap.add_argument("--render", action="store_true", help="emit the selected prompt block to stdout")
    ap.add_argument("--top", type=int, default=12, help="rows to show in rank view")
    args = ap.parse_args(argv)

    md_path, cite_path = Path(args.md), Path(args.citations)
    if not md_path.exists():
        print(f"no lessons file at {md_path}", file=sys.stderr)
        return 2
    header, bullets = _load(md_path, cite_path, args.w_cite, args.w_recency)
    if not bullets:
        print("no bullets found", file=sys.stderr)
        return 2

    max_cites = max((b.citations for b in bullets), default=0)
    if max_cites <= 1 and args.w_cite > 0:
        print(
            f"⚠️  citation signal is degenerate (max {max_cites}/bullet): citations record "
            "CREATION, not reuse, so the citation term is constant and salience == recency. "
            "See LESSONS.md F2; log a reuse event to make --w-cite meaningful.",
            file=sys.stderr,
        )

    if args.compare:
        cmd_compare(header, bullets, args.max_bytes)
    else:
        cmd_rank(header, bullets, args.max_bytes, args.render, args.top)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
