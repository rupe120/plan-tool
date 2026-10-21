"""Code-owned contracts for structured model responses.

Prompts describe the work; these contracts describe only the reply shape a
parser consumes. Keep the shape beside its parser and render it into prompts.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable, Literal, Optional


JSON_ROOT_OBJECT = "object"
JSON_ROOT_ARRAY = "array"
JsonRoot = Literal["object", "array"]


def coerce_response_id(value: object) -> Optional[int]:
    """Return a bare integer or a strict quoted positive decimal response id."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return None
    raw_id = value.strip()
    if (
        not raw_id.isascii()
        or not raw_id.isdecimal()
        or raw_id.startswith("0")
    ):
        return None
    try:
        return int(raw_id)
    except ValueError:
        return None


@dataclass(frozen=True)
class ResponseSection:
    """One required Markdown H2 section and its parser-facing identity."""

    heading: str
    key: str

    @property
    def normalized_heading(self) -> str:
        return self.heading.casefold()


@dataclass(frozen=True)
class MarkdownSectionsContract:
    """Ordered H2 sections a model reply must emit."""

    sections: tuple[ResponseSection, ...]
    empty_marker: str = "_(none)_"

    def __post_init__(self) -> None:
        headings = [section.normalized_heading for section in self.sections]
        keys = [section.key for section in self.sections]
        if (
            not headings
            or any(not heading.strip() for heading in headings)
            or any(not key.strip() for key in keys)
            or len(headings) != len(set(headings))
            or len(keys) != len(set(keys))
        ):
            raise ValueError("Markdown response headings must be non-empty and unique")

    @property
    def required_headings(self) -> frozenset[str]:
        return frozenset(section.normalized_heading for section in self.sections)

    def heading_pattern(self) -> re.Pattern[str]:
        # ``\b`` rather than an end-of-line anchor: a model that decorates
        # the heading line (``## Findings (none reported)``) must still be
        # recognized — the sections this parses have no retry-on-miss path,
        # so under-matching silently reads as "no block at all" instead of
        # a slightly messy one.
        names = "|".join(re.escape(section.heading) for section in self.sections)
        return re.compile(rf"^##\s+({names})\b", re.MULTILINE | re.IGNORECASE)

    def render_empty_skeleton(self) -> str:
        """Render the valid no-findings form in declared section order."""
        return "\n\n".join(
            f"## {section.heading}\n\n{self.empty_marker}"
            for section in self.sections
        )

    def render_prompt_block(self, *, response_label: str = "response") -> str:
        """Render the format instruction injected into a prompt's stable prefix."""
        count = len(self.sections)
        plural = "section" if count == 1 else "sections"
        return (
            f"Emit exactly these {count} H2 {plural}, in this order. "
            f"Keep an empty section and write `{self.empty_marker}` beneath it:\n\n"
            "```markdown\n"
            f"{self.render_empty_skeleton()}\n"
            "```\n\n"
            f"This is the complete structured portion of your {response_label}."
        )


@dataclass(frozen=True)
class VerdictContract:
    """A required verdict H2 with a closed set of response tokens."""

    heading: str
    tokens: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.heading.strip() or not self.tokens:
            raise ValueError("verdict contracts need a heading and one or more tokens")
        if len(self.tokens) != len(set(self.tokens)):
            raise ValueError("verdict tokens must be unique")

    def heading_pattern(self) -> re.Pattern[str]:
        return re.compile(rf"^##\s*{re.escape(self.heading)}\b", re.MULTILINE)

    def token_pattern(self) -> re.Pattern[str]:
        names = "|".join(
            re.escape(token) for token in sorted(self.tokens, key=len, reverse=True)
        )
        return re.compile(rf"\b({names})\b")

    def render_prompt_block(self) -> str:
        return (
            f"End with this `## {self.heading}` block, choosing exactly one "
            "listed token and placing it on its own line:\n\n"
            "```markdown\n"
            f"## {self.heading}\n\n"
            "<"
            + " | ".join(self.tokens)
            + ">\n```\n\n"
            "Do not put other text on the token line."
        )


@dataclass(frozen=True)
class JsonResponseContract:
    """A JSON envelope shared by a model-response prompt and its parser."""

    root: JsonRoot
    example: object
    required_keys: frozenset[str] = frozenset()
    exact_keys: bool = False
    alternate_examples: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        if self.root not in (JSON_ROOT_OBJECT, JSON_ROOT_ARRAY):
            raise ValueError(f"unknown JSON response root {self.root!r}")
        expected_type = dict if self.root == JSON_ROOT_OBJECT else list
        for example in (self.example, *self.alternate_examples):
            if not isinstance(example, expected_type):
                raise ValueError(
                    "JSON response example does not match its root type"
                )
            if self.root == JSON_ROOT_OBJECT and self.required_keys:
                example_keys = set(example)
                if not self.required_keys <= example_keys:
                    raise ValueError(
                        "JSON response example omits a required key"
                    )

    def render_prompt_block(self) -> str:
        root = "object" if self.root == JSON_ROOT_OBJECT else "array"
        key_rule = (
            "Its top-level keys must exactly match this shape."
            if self.exact_keys
            else (
                "Its top-level keys must include the required keys in this shape."
                if self.root == JSON_ROOT_OBJECT and self.required_keys
                else (
                    "Follow this shape."
                    if self.root == JSON_ROOT_OBJECT
                    else "Each item must follow this shape."
                )
            )
        )
        examples = (self.example, *self.alternate_examples)
        examples_block = "\n\nor\n\n".join(
            "```json\n"
            f"{json.dumps(example, indent=2, ensure_ascii=False)}\n"
            "```"
            for example in examples
        )
        example_rule = (
            key_rule
            if len(examples) == 1
            else f"{key_rule} Each example is valid; use the one that fits."
        )
        return (
            f"Respond with only one JSON {root}, with no fence or surrounding prose. "
            f"{example_rule}\n\n"
            f"{examples_block}"
        )

    def decode(
        self,
        raw: str,
        *,
        allow_surrounding: bool = True,
        object_pairs_hook: Optional[Callable[[list], dict]] = None,
    ) -> object | None:
        """Decode the expected root shape, optionally tolerating model chatter.

        ``object_pairs_hook`` is passed straight to ``json.loads`` for a
        caller that needs stricter-than-default object handling (e.g.
        rejecting duplicate keys); a hook is allowed to raise its own
        ``ValueError``/``TypeError``, which decode treats the same as a
        malformed reply rather than propagating.
        """
        text = raw.strip()
        if allow_surrounding:
            opening, closing = ("{", "}") if self.root == JSON_ROOT_OBJECT else ("[", "]")
            start, end = text.find(opening), text.rfind(closing)
            if start == -1 or end == -1 or end < start:
                return None
            text = text[start : end + 1]
        try:
            value = json.loads(text, object_pairs_hook=object_pairs_hook)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
        expected_type = dict if self.root == JSON_ROOT_OBJECT else list
        if not isinstance(value, expected_type):
            return None
        if isinstance(value, dict):
            keys = set(value)
            if not self.required_keys <= keys:
                return None
            if self.exact_keys and keys != self.required_keys:
                return None
        return value


# The common tail parsed by run modes and review surfaces. Individual prompts
# keep their own finding prose, but none re-declares the machine heading.
FINDINGS_RESPONSE_CONTRACT = MarkdownSectionsContract(
    sections=(ResponseSection("Findings", "findings"),)
)

DEEP_VERDICT_RESPONSE_CONTRACT = VerdictContract(
    heading="Verdict", tokens=("PASS", "FAIL", "UNKNOWN")
)
APPLY_VERDICT_RESPONSE_CONTRACT = VerdictContract(
    heading="Verdict",
    tokens=("BLOCKED-STRUCTURAL", "APPLIED", "NOT-APPLICABLE", "BLOCKED"),
)
APPLY_BASIC_VERDICT_RESPONSE_CONTRACT = VerdictContract(
    heading="Verdict", tokens=("APPLIED", "NOT-APPLICABLE", "BLOCKED")
)
