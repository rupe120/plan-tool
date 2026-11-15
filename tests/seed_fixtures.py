"""Shared `--from-existing` seed fixtures carrying the required guardrail headings."""

from __future__ import annotations

from plan_tool.scope_fence import REQUIRED_GUARDRAIL_HEADINGS

# Every guardrail answered with an explicit `None`: valid, and carries no fence content.
NONE_GUARDRAILS = "".join(
    f"\n\n## {title}\n\nNone\n" for title in REQUIRED_GUARDRAIL_HEADINGS
)


def with_none_guardrails(seed: str) -> str:
    """Append the three required guardrail headings (body `None`) to ``seed``."""
    return seed.rstrip("\n") + "\n" + NONE_GUARDRAILS
