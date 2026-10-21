"""Read-only ``gate-status`` command wiring."""

import argparse
import json

from plan_tool.cli.context import _load_context
from plan_tool.cli.convergence_cmd import _current_audit_stage
from plan_tool.cli.parser import Handler
from plan_tool.gate_status import build_gate_status
from plan_tool.jira_grade import GRADE_DEFAULT, JIRA_GRADE_VALUES
from plan_tool.locator import resolve_plan_for_context


def cmd_gate_status(args: argparse.Namespace) -> int:
    """Print saved gate verdicts without running an audit or writing state."""
    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)
    document = build_gate_status(
        path,
        ctx.repo_root,
        detail_grade=args.grade,
        current_stage=_current_audit_stage(ctx, path, detail_grade=args.grade),
    )
    print(json.dumps(document, indent=2))
    return 0


def register(subparsers) -> dict[str, Handler]:
    """Register the saved-verdict command."""
    p = subparsers.add_parser(
        "gate-status", help="report saved audit gate verdicts as versioned JSON"
    )
    p.add_argument("name", help="plan slug, filename stem, or filename.md")
    p.add_argument("--json", action="store_true", help="accepted for explicit JSON requests; output is always JSON")
    p.add_argument(
        "--grade", choices=JIRA_GRADE_VALUES, default=GRADE_DEFAULT,
        help=f"select saved results and current stage for this detail grade (default: {GRADE_DEFAULT})",
    )
    return {"gate-status": cmd_gate_status}
