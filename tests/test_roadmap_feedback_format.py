"""Contract checks for the reviewer-owned roadmap feedback ledger reference."""

from __future__ import annotations

import re
from pathlib import Path

from plan_tool.roadmap_feedback_ledger import (
    LEDGER_SCHEMA_VERSION,
    LedgerState,
    ReviewerItemState,
    parse_ledger,
    render_ledger,
)


_DOC = Path(__file__).resolve().parents[1] / "ROADMAP_FEEDBACK_FORMAT.md"


def _ledger_example() -> str:
    doc = _DOC.read_text(encoding="utf-8")
    match = re.search(
        r"<!-- ledger-example:start -->\n```yaml\n(?P<example>.*?)\n```\n"
        r"<!-- ledger-example:end -->",
        doc,
        re.S,
    )
    assert match, "ledger example markers are missing"
    return match.group("example") + "\n"


def test_ledger_format_examples_parse_and_round_trip() -> None:
    """Keep copied ledger YAML canonical under the landed parser and renderer."""
    example = _ledger_example()
    ledger = parse_ledger(example)
    assert render_ledger(ledger).decode("utf-8") == example


def test_ledger_format_example_uses_landed_lifecycle_vocabulary() -> None:
    """Keep documented lifecycle names and schema version synchronized with code."""
    doc = _DOC.read_text(encoding="utf-8")
    assert f"schema_version: {LEDGER_SCHEMA_VERSION}" in _ledger_example()
    for value in (*LedgerState, *ReviewerItemState):
        assert f"`{value.value}`" in doc or f"{value.value}" in _ledger_example()


def test_ledger_format_preserves_artifact_authority_and_batch_evidence() -> None:
    """Make mutable input and immutable candidate evidence distinct for operators."""
    doc = _DOC.read_text(encoding="utf-8")
    for boundary in (
        "mutable reviewer input",
        "sole selector of canonical artifact content",
        "does not rewrite an accepted artifact",
        "A later unrelated ledger edit does not invalidate recorded evidence",
        "without consuming the reviewer edit",
        "confirmation-required",
        "no prompt or `-y` shortcut",
    ):
        assert boundary in doc


def test_ledger_format_documents_one_ordinary_feedback_intake() -> None:
    """Keep route classification code-owned while the ledger stays mutable input."""
    doc = _DOC.read_text(encoding="utf-8")

    for boundary in (
        "Reviewers never choose a structural feedback type or route",
        "Validated typed operations classify the stored batch as bounded or structural",
        "mutable reviewer input",
    ):
        assert boundary in doc


def test_ledger_format_distinguishes_proposal_decision_and_promotion() -> None:
    """Keep inert proposal storage, exact approval, and publication separate."""
    doc = _DOC.read_text(encoding="utf-8")

    for boundary in (
        "stores an inert candidate",
        "The confirmed approval creates a `structural-approval` review seal",
        "A matching digest creates a `structural-approval` seal, then publishes its top candidate as a second, separately-durable write",
        "The confirmation invokes `promote_review_seal`, which rechecks the accepted root",
        "Edit stores a replacement candidate that requires a fresh decision",
        "rejection releases only the active candidate",
    ):
        assert boundary in doc


def _normalized(text: str) -> str:
    """Collapse hard-wrapped whitespace so a phrase match does not depend on where a line breaks."""
    return " ".join(text.split())


def test_ledger_format_documents_two_invocation_approval_over_the_whole_unpromoted_stack() -> None:
    """Approve is two invocations: the first prints the whole stack and writes nothing, and the digest that
    confirms the second is recomputed, never stored; only approve has a confirm step."""
    doc = _normalized(_DOC.read_text(encoding="utf-8"))

    for boundary in (
        "Approve takes two invocations",
        "`--confirm-stack-digest DIGEST`",
        "prints every unpromoted hop",
        "It writes nothing and exits with status `2`",
        "a differing digest refuses with no write",
        "that invocation is the seal's one construction site",
        "The digest is stateless: it is recomputed at confirm time and never stored",
        "Edit and reject print the stack first and take no confirm; only approve has a confirm step",
        "`-y` is refused beside a candidate decision and is not confirmation",
    ):
        assert boundary in doc


def test_ledger_format_states_a_new_batch_stacks_on_a_structural_active_candidate() -> None:
    """The retired refusal cannot return unstated: the format says a batch stacks under a structural candidate,
    and that a stack is structural by any hop's stored route, derived at use rather than persisted."""
    doc = _normalized(_DOC.read_text(encoding="utf-8"))

    for boundary in (
        "the new batch takes that candidate as its source, structural or not",
        "stacks under an active structural candidate and never refuses because of the active candidate's route",
        "A stack is structural when any candidate above its recorded root stores a STRUCTURAL route",
        "the stack is derived at use from stored candidate records",
        "a candidate with no stored route contributes nothing",
        "refuses a stack that carries a structural hop and names `--decide-candidate`",
    ):
        assert boundary in doc
