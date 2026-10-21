#!/usr/bin/env python3
"""Volume + salience accounting for the lessons store.

Pure stdlib, read-only. Quantifies the "volume" axis of the lessons-utility
experiment: how big the corpus is, how much of it actually reaches the prompt
under the production 48 KB recency-truncation, the per-surface distribution,
and the citation-derived salience signal (which lessons have ever been cited).

Mirrors plan_tool/lessons.py:_select_lessons_body so the kept/dropped counts
match what the orchestrators really inject. Keep the two in sync if the
truncation logic there changes.

Usage:
    python experiments/lessons-utility/measure_lessons.py            # auto-discovers .plan-tool/lessons/
    python experiments/lessons-utility/measure_lessons.py <project.md> [citations.jsonl]
    python experiments/lessons-utility/measure_lessons.py --max-bytes 24576   # sweep a budget
    python experiments/lessons-utility/measure_lessons.py --surfaces cross-step,detail-authoring
    python experiments/lessons-utility/measure_lessons.py --json    # machine-readable
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Keep in sync with plan_tool/lessons.py.
_MAX_INJECT_BYTES = 49152
_TRUNCATION_MARKER = "… _(older entries truncated; see file on disk)_"
_BULLET_SURFACE_RE = re.compile(r"^- `\[([a-z0-9-]*)\]`")
# Rough token estimate: ~4 chars/token for English+code prose. Good enough to
# rank conditions; not a substitute for the backend's real tokenizer.
_CHARS_PER_TOKEN = 4.0


def _split_header_and_bullets(body: str) -> tuple[str, list[str]]:
    """Split a lessons file into header prose + ordered bullets (oldest first)."""
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


def _bullet_surface(bullet: str) -> str | None:
    m = _BULLET_SURFACE_RE.match(bullet)
    return m.group(1) if m else None


def _select(body: str, surfaces: frozenset[str] | None, max_bytes: int) -> tuple[int, int]:
    """Return (kept_bullets, dropped_bullets) after surface filter + recency truncation.

    Mirrors plan_tool/lessons.py:_select_lessons_body's keep/drop accounting."""
    if not body.strip():
        return (0, 0)
    header, bullets = _split_header_and_bullets(body)
    if surfaces is not None:
        bullets = [b for b in bullets if (s := _bullet_surface(b)) is None or s in surfaces]
    total = len(bullets)
    kept = 0
    used = len(header.encode("utf-8"))
    for bullet in reversed(bullets):  # newest first
        size = len(bullet.encode("utf-8")) + 2
        if kept and used + size > max_bytes:
            break
        kept += 1
        used += size
    return (kept, total - kept)


def _tokens(n_bytes: int) -> int:
    return round(n_bytes / _CHARS_PER_TOKEN)


def _load_citations(path: Path) -> tuple[int, Counter, Counter]:
    """Return (total_records, by_source, by_added_month) from a citations jsonl."""
    by_source: Counter = Counter()
    by_month: Counter = Counter()
    total = 0
    if not path.exists():
        return (0, by_source, by_month)
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        by_source[rec.get("source", "?").split("#")[0]] += 1
        added = str(rec.get("added", ""))[:7]  # YYYY-MM
        if added:
            by_month[added] += 1
    return (total, by_source, by_month)


def measure(md_path: Path, cite_path: Path, surfaces: frozenset[str] | None, max_bytes: int) -> dict:
    body = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    disk_bytes = len(body.encode("utf-8"))
    header, bullets = _split_header_and_bullets(body)
    by_surface = Counter(_bullet_surface(b) or "(untagged)" for b in bullets)
    bullet_bytes = [len(b.encode("utf-8")) for b in bullets]
    kept, dropped = _select(body, surfaces, max_bytes)
    eligible = kept + dropped  # bullets passing the surface filter (denominator)
    inject_bytes = min(disk_bytes, max_bytes)
    cite_total, cite_by_source, cite_by_month = _load_citations(cite_path)
    return {
        "file": str(md_path),
        "disk_bytes": disk_bytes,
        "disk_tokens_est": _tokens(disk_bytes),
        "n_bullets": len(bullets),
        "eligible_bullets": eligible,
        "avg_bullet_bytes": round(sum(bullet_bytes) / len(bullets)) if bullets else 0,
        "max_bullet_bytes": max(bullet_bytes) if bullet_bytes else 0,
        "by_surface": dict(by_surface.most_common()),
        "max_bytes_budget": max_bytes,
        "surfaces_filter": sorted(surfaces) if surfaces else None,
        "injected_bullets": kept,
        "dropped_bullets": dropped,
        "pct_corpus_injected": round(100 * kept / eligible, 1) if eligible else 0.0,
        "injected_bytes_est": inject_bytes,
        "injected_tokens_est": _tokens(inject_bytes),
        "citations_total": cite_total,
        "citations_by_source": dict(cite_by_source.most_common()),
        "citations_by_month": dict(sorted(cite_by_month.items())),
    }


def _print_human(m: dict) -> None:
    print(f"# lessons volume report — {m['file']}")
    print()
    print(f"  disk size            {m['disk_bytes']:>10,} bytes  (~{m['disk_tokens_est']:,} tok)")
    print(f"  total bullets        {m['n_bullets']:>10,}")
    print(f"  avg / max bullet     {m['avg_bullet_bytes']:>10,} / {m['max_bullet_bytes']:,} bytes")
    print()
    print(f"  inject budget        {m['max_bytes_budget']:>10,} bytes")
    denom_label = "of corpus"
    if m["surfaces_filter"]:
        print(f"  surfaces filter      {','.join(m['surfaces_filter'])}")
        print(f"  surface-eligible     {m['eligible_bullets']:>10,} of {m['n_bullets']:,} bullets")
        denom_label = "of eligible"
    print(
        f"  injected bullets     {m['injected_bullets']:>10,} of {m['eligible_bullets']:,}"
        f"  ({m['pct_corpus_injected']}% {denom_label})"
    )
    print(f"  DROPPED by truncation{m['dropped_bullets']:>10,}")
    print(f"  injected size (est)  {m['injected_bytes_est']:>10,} bytes  (~{m['injected_tokens_est']:,} tok)")
    print()
    print("  bullets by surface:")
    for surf, n in m["by_surface"].items():
        print(f"    {surf:<22} {n:>5}")
    print()
    print(f"  citations total      {m['citations_total']:>10,}")
    if m["citations_by_source"]:
        print("  citations by source:")
        for src, n in m["citations_by_source"].items():
            print(f"    {src:<40} {n:>5}")
    if m["citations_by_month"]:
        print("  citations by month (accumulation curve):")
        for mo, n in m["citations_by_month"].items():
            print(f"    {mo:<10} {'#' * min(n, 60)} {n}")
    # The headline finding for the experiment write-up.
    if m["dropped_bullets"]:
        scope = "eligible bullets" if m["surfaces_filter"] else "bullets"
        print()
        print(
            f"  >> {m['dropped_bullets']} of {m['eligible_bullets']} {scope} "
            f"({100 - m['pct_corpus_injected']:.1f}%) never reach the prompt "
            f"under the {m['max_bytes_budget'] // 1024} KB cap."
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("md", nargs="?", help="lessons .md file (default: auto-discover .plan-tool/lessons/project.md)")
    ap.add_argument("citations", nargs="?", help="citations .jsonl (default: sibling project-citations.jsonl)")
    ap.add_argument("--max-bytes", type=int, default=_MAX_INJECT_BYTES, help="inject budget to simulate")
    ap.add_argument("--surfaces", default=None, help="comma-separated surface filter (default: inject all)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args(argv)

    if args.md:
        md_path = Path(args.md)
        cite_path = Path(args.citations) if args.citations else md_path.with_name(
            md_path.stem.replace("project", "project-citations").replace("general", "general-citations") + ".jsonl"
        )
    else:
        # Auto-discover from cwd: <repo>/.plan-tool/lessons/project.md
        md_path = Path(".plan-tool/lessons/project.md")
        cite_path = Path(".plan-tool/lessons/project-citations.jsonl")
        if not md_path.exists():
            print("no lessons file found; pass a path explicitly", file=sys.stderr)
            return 2

    surfaces = frozenset(s.strip() for s in args.surfaces.split(",") if s.strip()) if args.surfaces else None
    m = measure(md_path, cite_path, surfaces, args.max_bytes)
    if args.json:
        print(json.dumps(m, indent=2))
    else:
        _print_human(m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
