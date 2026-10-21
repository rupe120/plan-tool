"""Result types for the confirmed settlement of one Roadmap-derived pending decision.

``plan_tool.roadmap_decision_settlement_enrolled`` is the only runner; it builds
its results through :func:`_result`. See docs/ARCHITECTURE.md's
"Decision-settlement receipts" entry for the full design.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from plan_tool.roadmap_decision_settlement import DecisionSettlementRefusalVerdict
from plan_tool.roadmap_decision_settlement_receipt import DecisionSettlementReceiptOutcome

DecisionSettlementRunOutcome: TypeAlias = Literal[
    "settled", "preflight-rejected", "receipt-rejected", "write-failed", "interrupted"
]
DecisionSettlementRunRefusal: TypeAlias = (
    DecisionSettlementRefusalVerdict
    | Literal[
        "confirmation-required",
        "mode-rejected",
        "journal-unrecoverable",
        "no-published-version",
        "unpromoted-candidate-lineage",
        "settled-content-fails-gates",
    ]
    | DecisionSettlementReceiptOutcome
)

_STATUS_BY_OUTCOME: dict[DecisionSettlementRunOutcome, Literal[0, 1, 2, 130]] = {
    "settled": 0,
    "preflight-rejected": 2,
    "receipt-rejected": 1,
    "write-failed": 1,
    "interrupted": 130,
}


@dataclass(frozen=True)
class DecisionSettlementRunResult:
    """Redacted terminal facts for the confirmed decision-settlement command."""

    outcome: DecisionSettlementRunOutcome
    status: Literal[0, 1, 2, 130]
    refusal: DecisionSettlementRunRefusal | None = None
    receipt_id: str | None = None


def _result(
    outcome: DecisionSettlementRunOutcome,
    refusal: DecisionSettlementRunRefusal | None = None,
    *,
    receipt_id: str | None = None,
) -> DecisionSettlementRunResult:
    return DecisionSettlementRunResult(
        outcome=outcome,
        status=_STATUS_BY_OUTCOME[outcome],
        refusal=refusal,
        receipt_id=receipt_id,
    )
