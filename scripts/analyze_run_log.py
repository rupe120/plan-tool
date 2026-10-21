#!/usr/bin/env python3
"""Bucket a plan-tool run log into per-category Claude cost.

Experiment tooling for the minimize-claude-in-create work: parses one or
more ``.plan-tool/runs/<slug>/*.jsonl`` run logs and prints, per phase
category, the wall-clock spent and call count — then breaks out the two
costs the seed targets:

  * iteration re-proposals  (propose_steps / propose_references beyond the
    round-0 call)                                          -> Opportunity 3
  * apply_finding_dispatch fills, split by finding source and (for body
    placeholders) the target section                       -> Opp 1 + 2

Usage:
    python scripts/analyze_run_log.py PATH [PATH ...]
    python scripts/analyze_run_log.py .plan-tool/runs/<slug>/

Pure stdlib; reads, never writes. Safe to run against a live log.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_SECTION_RE = re.compile(r"##\s*([A-Za-z][\w ]*?)\s*(?:body|$|`)")


def _iter_logs(args: list[str]) -> list[Path]:
    out: list[Path] = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            out.extend(sorted(p.glob("*.jsonl")))
        elif p.suffix == ".jsonl":
            out.append(p)
    return out


def _section_of(label: str) -> str:
    m = _SECTION_RE.search(label or "")
    return m.group(1).strip() if m else "?"


def analyze(path: Path) -> None:
    events = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
    # ``claude_call_end`` is the authoritative per-Claude-call record (it
    # carries phase + duration_ms even for iteration re-proposals / applies
    # that the loop does NOT wrap in a phase_end). phase_end is only
    # complete for round-0 phases + the (instrumented) apply dispatch.
    calls = [e for e in events if e.get("event") == "claude_call_end"]
    apply_phases = [
        e for e in events
        if e.get("event") == "phase_end" and e.get("phase") == "apply_finding_dispatch"
    ]

    by_phase_ms: dict[str, int] = defaultdict(int)
    by_phase_n: dict[str, int] = defaultdict(int)
    seen_phase: dict[str, int] = defaultdict(int)
    reproposal_ms = 0

    for e in calls:
        ph = e.get("phase", "?")
        ms = int(e.get("duration_ms") or 0)
        by_phase_ms[ph] += ms
        by_phase_n[ph] += 1
        seen_phase[ph] += 1
        # Opp 3: every propose_* Claude call after the first is a re-proposal.
        if ph in ("propose_steps", "propose_references") and seen_phase[ph] > 1:
            reproposal_ms += ms

    # Opp 1+2: apply identity comes from the instrumented phase_end extras.
    apply_by_source: dict[str, list[int]] = defaultdict(list)
    placeholder_by_section: dict[str, list[int]] = defaultdict(list)
    for e in apply_phases:
        ms = int(e.get("duration_ms") or 0)
        src = e.get("source", "?")
        apply_by_source[src].append(ms)
        label = e.get("finding_label", "")
        if src == "body-completeness" or "placeholder" in label.lower():
            placeholder_by_section[_section_of(label)].append(ms)

    total_ms = sum(by_phase_ms.values())
    print(f"\n=== {path.name} ===")
    print(f"{'claude phase':30} {'n':>3} {'total_s':>9}")
    for ph in sorted(by_phase_ms, key=lambda k: -by_phase_ms[k]):
        print(f"{ph:30} {by_phase_n[ph]:>3} {by_phase_ms[ph] / 1000:>9.1f}")
    print(f"{'TOTAL (claude calls)':30} {len(calls):>3} {total_ms / 1000:>9.1f}")

    def pct(ms: int) -> str:
        return f"{100 * ms / total_ms:.0f}%" if total_ms else "—"

    print("\n  -- targeted costs --")
    print(f"  iteration re-proposals (Opp 3): {reproposal_ms / 1000:.1f}s  ({pct(reproposal_ms)})")
    if apply_by_source:
        print("  apply_finding_dispatch by source (Opp 1+2):")
        for src, mss in sorted(apply_by_source.items(), key=lambda kv: -sum(kv[1])):
            print(f"    {src:24} n={len(mss):>2}  {sum(mss) / 1000:>7.1f}s")
    if placeholder_by_section:
        ph_ms = sum(sum(v) for v in placeholder_by_section.values())
        print(f"  body-placeholder fills: {ph_ms / 1000:.1f}s  ({pct(ph_ms)}) — deterministic-fill candidates:")
        for sec, mss in sorted(placeholder_by_section.items(), key=lambda kv: -sum(kv[1])):
            print(f"    ## {sec:22} n={len(mss):>2}  {sum(mss) / 1000:>7.1f}s")
    if not apply_by_source:
        print("  (no apply_finding_dispatch phases logged — pre-instrumentation run)")


def main(argv: list[str]) -> int:
    logs = _iter_logs(argv[1:])
    if not logs:
        print(__doc__)
        return 2
    for p in logs:
        analyze(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
