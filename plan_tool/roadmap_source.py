"""Concept-brief readers shared by roadmap consumers.

The roadmap orchestrator owns when a brief is selected. This module only reads
a brief and its carried decisions, so snapshot code can bind the same inputs
without importing orchestration.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


class RoadmapSourceError(ValueError):
    """A concept brief cannot be read or interpreted."""


@dataclass(frozen=True)
class ConfirmedAnswer:
    """One approved answer that a carried decision may cite."""

    id: str
    answer: str


@dataclass(frozen=True)
class RejectedAlternative:
    """One upstream-stated option and the reason it was not selected."""

    option: str
    reason: str


@dataclass(frozen=True)
class CarriedDecision:
    """One closed, upstream-approved decision for a Roadmap artifact."""

    id: str
    owner: Literal["domain", "constraints", "components", "plans"]
    anchor: str
    chosen_option: str
    source: str
    rationale: str | None = None
    rejected_alternatives: tuple[RejectedAlternative, ...] = ()


@dataclass(frozen=True)
class CarriedDecisions:
    """The optional approved-decision input admitted from one brief."""

    confirmed_answers: tuple[ConfirmedAnswer, ...] = ()
    decisions: tuple[CarriedDecision, ...] = ()


_CARRIED_DECISIONS_HEADING = re.compile(r"^## Carried decisions[ \t]*$", re.MULTILINE)
_CARRIED_DECISIONS_HEADING_PREFIX = re.compile(r"^## Carried decisions", re.MULTILINE)
_SECTION_HEADING = re.compile(r"^#{1,2}[ \t]+", re.MULTILINE)
_JSON_FENCE = re.compile(r"^```json[ \t]*\n(?P<body>.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
_CARRIED_OWNERS = frozenset(("domain", "constraints", "components", "plans"))


def _brief_error(brief_path: Path, message: str) -> RoadmapSourceError:
    return RoadmapSourceError(f"carried decisions in brief {brief_path}: {message}")


def _required_string(payload: object, field: str, *, brief_path: Path, context: str) -> str:
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get(field), str)
        or not payload[field].strip()
    ):
        raise _brief_error(brief_path, f"{context} must contain a non-blank '{field}'")
    return payload[field]


def _closed_object(
    payload: object, allowed: frozenset[str], *, brief_path: Path, context: str
) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise _brief_error(brief_path, f"{context} must be an object")
    unknown = set(payload) - allowed
    if unknown:
        raise _brief_error(
            brief_path, f"{context} contains unsupported field(s): {', '.join(sorted(unknown))}"
        )
    return payload


def parse_carried_decisions(brief: str, *, brief_path: Path) -> CarriedDecisions:
    """Parse the optional closed carried-decisions section from a brief."""
    exact_headings = tuple(_CARRIED_DECISIONS_HEADING.finditer(brief))
    heading_prefixes = tuple(_CARRIED_DECISIONS_HEADING_PREFIX.finditer(brief))
    if not exact_headings:
        if heading_prefixes:
            raise _brief_error(brief_path, "has a malformed '## Carried decisions' heading")
        return CarriedDecisions()
    if len(exact_headings) != 1 or len(heading_prefixes) != 1:
        raise _brief_error(brief_path, "must contain exactly one '## Carried decisions' heading")

    section_start = exact_headings[0].end()
    next_heading = _SECTION_HEADING.search(brief, section_start)
    section = brief[section_start : next_heading.start() if next_heading else len(brief)]
    fences = tuple(_JSON_FENCE.finditer(section))
    if (
        len(fences) != 1
        or section[: fences[0].start()].strip()
        or section[fences[0].end() :].strip()
    ):
        raise _brief_error(brief_path, "must contain exactly one fenced json object")
    try:
        payload = json.loads(fences[0].group("body"))
    except json.JSONDecodeError as exc:
        raise _brief_error(brief_path, f"contains invalid JSON ({exc})") from exc
    root = _closed_object(
        payload,
        frozenset(("confirmed_answers", "decisions")),
        brief_path=brief_path,
        context="carried-decision block",
    )
    answers_payload = root.get("confirmed_answers")
    decisions_payload = root.get("decisions")
    if not isinstance(answers_payload, list) or not isinstance(decisions_payload, list):
        raise _brief_error(brief_path, "must contain 'confirmed_answers' and 'decisions' arrays")

    answers: list[ConfirmedAnswer] = []
    answer_ids: set[str] = set()
    for index, answer_payload in enumerate(answers_payload, start=1):
        answer = _closed_object(
            answer_payload,
            frozenset(("id", "answer", "status")),
            brief_path=brief_path,
            context=f"confirmed answer {index}",
        )
        answer_id = _required_string(
            answer, "id", brief_path=brief_path, context=f"confirmed answer {index}"
        )
        answer_text = _required_string(
            answer, "answer", brief_path=brief_path, context=f"confirmed answer {index}"
        )
        if answer.get("status") != "confirmed":
            raise _brief_error(
                brief_path, f"confirmed answer '{answer_id}' must have status 'confirmed'"
            )
        if answer_id in answer_ids:
            raise _brief_error(brief_path, f"has duplicate confirmed answer id '{answer_id}'")
        answer_ids.add(answer_id)
        answers.append(ConfirmedAnswer(id=answer_id, answer=answer_text))
    answers_by_id = {answer.id: answer for answer in answers}

    decisions: list[CarriedDecision] = []
    decision_ids: set[str] = set()
    for index, decision_payload in enumerate(decisions_payload, start=1):
        decision = _closed_object(
            decision_payload,
            frozenset(
                (
                    "id",
                    "owner",
                    "anchor",
                    "chosen_option",
                    "source",
                    "rationale",
                    "rejected_alternatives",
                )
            ),
            brief_path=brief_path,
            context=f"carried decision {index}",
        )
        decision_id = _required_string(
            decision, "id", brief_path=brief_path, context=f"carried decision {index}"
        )
        owner = _required_string(
            decision, "owner", brief_path=brief_path, context=f"carried decision {index}"
        )
        anchor = _required_string(
            decision, "anchor", brief_path=brief_path, context=f"carried decision {index}"
        )
        chosen_option = _required_string(
            decision, "chosen_option", brief_path=brief_path, context=f"carried decision {index}"
        )
        source = _required_string(
            decision, "source", brief_path=brief_path, context=f"carried decision {index}"
        )
        if owner not in _CARRIED_OWNERS:
            raise _brief_error(
                brief_path, f"carried decision '{decision_id}' has unsupported owner '{owner}'"
            )
        if decision_id in decision_ids:
            raise _brief_error(brief_path, f"has duplicate carried decision id '{decision_id}'")
        cited_answer = answers_by_id.get(source)
        if cited_answer is None:
            raise _brief_error(
                brief_path,
                f"carried decision '{decision_id}' cites unknown confirmed answer '{source}'",
            )
        if chosen_option != cited_answer.answer:
            raise _brief_error(
                brief_path,
                f"carried decision '{decision_id}' chosen_option does not match '{source}'",
            )
        rationale = decision.get("rationale")
        if rationale is not None and (not isinstance(rationale, str) or not rationale.strip()):
            raise _brief_error(
                brief_path,
                f"carried decision '{decision_id}' rationale must be non-blank when present",
            )
        alternatives_payload = decision.get("rejected_alternatives", [])
        if not isinstance(alternatives_payload, list):
            raise _brief_error(
                brief_path,
                f"carried decision '{decision_id}' rejected_alternatives must be an array",
            )
        alternatives: list[RejectedAlternative] = []
        for alternative_index, alternative_payload in enumerate(alternatives_payload, start=1):
            alternative = _closed_object(
                alternative_payload,
                frozenset(("option", "reason")),
                brief_path=brief_path,
                context=f"rejected alternative {alternative_index} of carried decision '{decision_id}'",
            )
            alternatives.append(
                RejectedAlternative(
                    option=_required_string(
                        alternative, "option", brief_path=brief_path, context="rejected alternative"
                    ),
                    reason=_required_string(
                        alternative, "reason", brief_path=brief_path, context="rejected alternative"
                    ),
                )
            )
        decision_ids.add(decision_id)
        decisions.append(
            CarriedDecision(
                id=decision_id,
                owner=owner,
                anchor=anchor,
                chosen_option=chosen_option,
                source=source,
                rationale=rationale,
                rejected_alternatives=tuple(alternatives),
            )
        )
    return CarriedDecisions(confirmed_answers=tuple(answers), decisions=tuple(decisions))


def digest_decoded_text(text: str) -> str:
    """Return the SHA-256 of UTF-8 bytes re-encoded from decoded text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_brief_text(brief_path: Path) -> str:
    """Read a concept brief through the roadmap's UTF-8 text contract."""
    return Path(brief_path).read_text(encoding="utf-8")
