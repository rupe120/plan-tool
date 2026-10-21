"""Read-only ``plan-tool telemetry`` decision-analysis command.

This repository-wide operator surface spends no Claude, writes no run-log
entry, mutates nothing, and always exits 0. The analysis leaf owns all reads,
aggregation, rendering, and JSON shaping; this module only wires it to argparse.
"""

from __future__ import annotations

import argparse
import json

from plan_tool.cli.context import _load_context
from plan_tool.cli.parser import Handler
from plan_tool.telemetry_analysis import (
    analysis_to_dict,
    analyze_telemetry,
    render_analysis,
)


def cmd_telemetry(args: argparse.Namespace) -> int:
    """Print the cross-plan decision outcome analysis in text or JSON form."""
    ctx = _load_context(args)
    analysis = analyze_telemetry(ctx.repo_root)
    if args.json:
        print(json.dumps(analysis_to_dict(analysis), sort_keys=True))
    else:
        print(render_analysis(analysis))
    return 0


def register(subparsers) -> dict[str, Handler]:
    """Add the ``telemetry`` subparser and return its handler map."""
    parser = subparsers.add_parser(
        "telemetry",
        help="analyze recorded heuristic decisions and their outcomes",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the analysis as one machine-readable JSON object",
    )
    return {"telemetry": cmd_telemetry}
