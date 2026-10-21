"""Reviewer-owned mutable feedback ledgers for immutable roadmap versions."""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from plan_tool.roadmap_artifacts import (
    FeedbackTargetKind,
    RoadmapArtifactError,
    design_row_collections,
    parse_components_artifact,
    parse_constraints_artifact,
    parse_domain_artifact,
    parse_plans_artifact,
    roadmap_dir,
)
from plan_tool.roadmap_versions import (
    ResolvedRoadmapVersion,
    VERSION_ARTIFACT_INVENTORY,
)


LEDGER_SCHEMA_VERSION = 1
LEDGER_FILENAME = "feedback-ledger.yaml"
_DIGEST_RE = re.compile(r"[0-9a-f]{64}", re.ASCII)
_ITEM_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", re.ASCII)
# Marks a legacy row that carried no request text; never derived from the row.
LEGACY_BLANK_REQUEST_MARKER = "(legacy feedback row had no request text)"


class RoadmapFeedbackLedgerError(ValueError):
    """A mutable feedback ledger is not a trusted ledger snapshot."""


def is_valid_item_id(value: str) -> bool:
    return _ITEM_ID_RE.fullmatch(value) is not None


class _FrozenLedgerRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class LedgerState(str, enum.Enum):
    LEDGER_NATIVE = "ledger-native"


# The removed pre-ledger migration state. It is recognized only so a ledger file
# that still names it fails with a remedy; no code path models or migrates it.
_REMOVED_MIGRATION_PENDING_STATE = "migration-pending"


class ReviewerItemState(str, enum.Enum):
    OPEN = "open"
    AWAITING_REVIEW = "awaiting-review"
    DEFERRED = "deferred"
    CLOSED = "closed"


class LedgerTarget(_FrozenLedgerRecord):
    """One artifact or exact row selected from a fixed artifact inventory."""

    artifact_key: str
    kind: FeedbackTargetKind
    row_id: str | None = None

    @field_validator("kind", mode="before")
    @classmethod
    def _parses_target_kind(cls, value: object) -> FeedbackTargetKind:
        try:
            return FeedbackTargetKind(value)
        except ValueError as exc:
            raise ValueError("ledger target kind is unsupported") from exc

    @field_validator("artifact_key")
    @classmethod
    def _requires_inventory_key(cls, value: str) -> str:
        if value not in {entry.artifact_key for entry in VERSION_ARTIFACT_INVENTORY}:
            raise ValueError("ledger target artifact key is not configured")
        return value

    @model_validator(mode="after")
    def _requires_matching_target_payload(self) -> "LedgerTarget":
        if self.kind is FeedbackTargetKind.ARTIFACT and self.row_id is not None:
            raise ValueError("artifact target must not name a row")
        if self.kind is FeedbackTargetKind.ROW and (not self.row_id or not self.row_id.strip()):
            raise ValueError("row target requires a nonempty row id")
        return self


class ProposalFields(_FrozenLedgerRecord):
    """Live model-facing proposal fields, deliberately not process history.

    ``candidate_version_id`` names the stored candidate that produced the
    response; it is ``None`` for a proposal migrated from a legacy embedded row,
    which no stored candidate produced.
    """

    response: str
    candidate_version_id: str | None = None

    @field_validator("response")
    @classmethod
    def _requires_response(cls, value: str) -> str:
        if not value:
            raise ValueError("proposal response must be nonempty")
        return value

    @field_validator("candidate_version_id")
    @classmethod
    def _requires_candidate_digest(cls, value: str | None) -> str | None:
        if value is not None and _DIGEST_RE.fullmatch(value) is None:
            raise ValueError("proposal candidate version must be lowercase SHA-256")
        return value


class LegacyFeedbackSource(_FrozenLedgerRecord):
    """The embedded legacy row a migrated item was imported from; native items carry ``None``."""

    artifact_key: str
    feedback_id: str

    @field_validator("artifact_key")
    @classmethod
    def _requires_inventory_key(cls, value: str) -> str:
        if value not in {entry.artifact_key for entry in VERSION_ARTIFACT_INVENTORY}:
            raise ValueError("legacy source artifact key is not configured")
        return value


class ReviewerFeedbackItem(_FrozenLedgerRecord):
    item_id: str
    target: LedgerTarget
    request: str
    state: ReviewerItemState
    submitted_against_version_id: str
    target_fingerprint: str
    proposal: ProposalFields | None = None
    legacy_source: LegacyFeedbackSource | None = None

    @field_validator("state", mode="before")
    @classmethod
    def _parses_item_state(cls, value: object) -> ReviewerItemState:
        try:
            return ReviewerItemState(value)
        except ValueError as exc:
            raise ValueError("reviewer item state is unsupported") from exc

    @field_validator("item_id")
    @classmethod
    def _requires_item_id(cls, value: str) -> str:
        if not is_valid_item_id(value):
            raise ValueError("reviewer item id is unsafe")
        return value

    @field_validator("request")
    @classmethod
    def _requires_request(cls, value: str) -> str:
        if not value:
            raise ValueError("reviewer request must be nonempty")
        return value

    @field_validator("submitted_against_version_id", "target_fingerprint")
    @classmethod
    def _requires_digest(cls, value: str) -> str:
        if _DIGEST_RE.fullmatch(value) is None:
            raise ValueError("ledger source binding must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def _closed_items_clear_proposals(self) -> "ReviewerFeedbackItem":
        if self.state is ReviewerItemState.CLOSED and self.proposal is not None:
            raise ValueError("closed reviewer item must clear its live proposal")
        return self


class ReviewerFeedbackGroup(_FrozenLedgerRecord):
    """Items submitted against one direct predecessor, in reviewer-defined order."""

    predecessor_version_id: str
    items: tuple[ReviewerFeedbackItem, ...]

    @field_validator("items", mode="before")
    @classmethod
    def _retains_item_order(cls, value: object) -> tuple[object, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("feedback group items must be an ordered sequence")
        return tuple(value)

    @field_validator("predecessor_version_id")
    @classmethod
    def _requires_predecessor(cls, value: str) -> str:
        if _DIGEST_RE.fullmatch(value) is None:
            raise ValueError("feedback group predecessor must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def _requires_items_for_its_predecessor(self) -> "ReviewerFeedbackGroup":
        if any(item.submitted_against_version_id != self.predecessor_version_id for item in self.items):
            raise ValueError("feedback item must belong to its predecessor group")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError("feedback group has duplicate item ids")
        return self


class DerivedFeedbackContext(_FrozenLedgerRecord):
    """Revision-bound roadmap context, never reviewer-created feedback."""

    source_version_id: str
    context_id: str
    content: str

    @field_validator("source_version_id")
    @classmethod
    def _requires_source(cls, value: str) -> str:
        if _DIGEST_RE.fullmatch(value) is None:
            raise ValueError("derived context source must be lowercase SHA-256")
        return value

    @field_validator("context_id", "content")
    @classmethod
    def _requires_nonempty_text(cls, value: str) -> str:
        if not value:
            raise ValueError("derived context fields must be nonempty")
        return value


class RoadmapFeedbackLedger(_FrozenLedgerRecord):
    schema_version: int
    roadmap_slug: str
    ledger_state: LedgerState
    reviewer_feedback_groups: tuple[ReviewerFeedbackGroup, ...]
    derived_context: tuple[DerivedFeedbackContext, ...]

    @field_validator("ledger_state", mode="before")
    @classmethod
    def _parses_ledger_state(cls, value: object) -> LedgerState:
        try:
            return LedgerState(value)
        except ValueError as exc:
            raise ValueError("ledger state is unsupported") from exc

    @field_validator("reviewer_feedback_groups", "derived_context", mode="before")
    @classmethod
    def _retains_collection_order(cls, value: object) -> tuple[object, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("ledger collections must be ordered sequences")
        return tuple(value)

    @field_validator("schema_version")
    @classmethod
    def _requires_schema(cls, value: int) -> int:
        if value != LEDGER_SCHEMA_VERSION:
            raise ValueError("feedback ledger schema version is unsupported")
        return value

    @field_validator("roadmap_slug")
    @classmethod
    def _requires_safe_slug(cls, value: str) -> str:
        try:
            roadmap_dir(Path("."), value)
        except ValueError as exc:
            raise ValueError("ledger roadmap slug is unsafe") from exc
        return value

    @model_validator(mode="after")
    def _requires_global_item_identity(self) -> "RoadmapFeedbackLedger":
        item_ids = [item.item_id for group in self.reviewer_feedback_groups for item in group.items]
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("feedback ledger has duplicate item ids")
        predecessors = [group.predecessor_version_id for group in self.reviewer_feedback_groups]
        if len(set(predecessors)) != len(predecessors):
            raise ValueError("feedback ledger has duplicate predecessor groups")
        return self


class ReviewerItemSnapshot(_FrozenLedgerRecord):
    """Immutable item evidence for one later candidate batch."""

    item_id: str
    request: str
    state: ReviewerItemState
    target: LedgerTarget
    submitted_against_version_id: str
    target_fingerprint: str
    proposal: ProposalFields | None = None


def roadmap_feedback_ledger_path(plans_dir: Path, slug: str) -> Path:
    """Return the mutable ledger path below the configured roadmap root."""
    return roadmap_dir(Path(plans_dir), slug) / LEDGER_FILENAME


def initial_ledger(
    slug: str, ledger_state: LedgerState = LedgerState.LEDGER_NATIVE
) -> RoadmapFeedbackLedger:
    """The empty ledger a root version publishes beside its head; the one construction site."""
    return RoadmapFeedbackLedger(
        schema_version=LEDGER_SCHEMA_VERSION,
        roadmap_slug=slug,
        ledger_state=ledger_state,
        reviewer_feedback_groups=(),
        derived_context=(),
    )


def render_ledger(ledger: RoadmapFeedbackLedger) -> bytes:
    """Render the single reviewer-editable form with stable UTF-8 bytes."""
    _require_ledger(ledger)
    try:
        text = yaml.safe_dump(
            ledger.model_dump(mode="json"),
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=88,
        )
    except yaml.YAMLError as exc:
        raise RoadmapFeedbackLedgerError("cannot render feedback ledger") from exc
    return text.encode("utf-8")


def parse_ledger(text: str) -> RoadmapFeedbackLedger:
    """Load only the exact canonical text form; never silently normalize it."""
    if not isinstance(text, str):
        raise RoadmapFeedbackLedgerError("feedback ledger text must be a string")
    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RoadmapFeedbackLedgerError("feedback ledger is not valid YAML") from exc
    if not isinstance(value, dict):
        raise RoadmapFeedbackLedgerError("feedback ledger root must be a mapping")
    if value.get("ledger_state") == _REMOVED_MIGRATION_PENDING_STATE:
        raise RoadmapFeedbackLedgerError(
            f"feedback ledger state {_REMOVED_MIGRATION_PENDING_STATE!r} is no longer "
            "supported; create the roadmap again under a new successor slug"
        )
    try:
        ledger = RoadmapFeedbackLedger.model_validate(value)
    except ValidationError as exc:
        raise RoadmapFeedbackLedgerError("feedback ledger fields are malformed") from exc
    if render_ledger(ledger).decode("utf-8") != text:
        raise RoadmapFeedbackLedgerError("feedback ledger is not in canonical form")
    return ledger


def load_ledger(path: Path) -> RoadmapFeedbackLedger:
    """Read a path-bearing ledger loader while retaining the text parser split."""
    try:
        data = Path(path).read_bytes()
        text = data.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RoadmapFeedbackLedgerError(f"cannot read feedback ledger at {path}") from exc
    return parse_ledger(text)


def ledger_digest(ledger: RoadmapFeedbackLedger) -> str:
    return hashlib.sha256(render_ledger(ledger)).hexdigest()


def item_snapshot(item: ReviewerFeedbackItem) -> ReviewerItemSnapshot:
    return ReviewerItemSnapshot(**item.model_dump(exclude={"legacy_source"}))


def close_reviewer_item(item: ReviewerFeedbackItem) -> ReviewerFeedbackItem:
    return _updated_item(item, state=ReviewerItemState.CLOSED, proposal=None)


def reopen_reviewer_item(item: ReviewerFeedbackItem) -> ReviewerFeedbackItem:
    _require_request_text_to_open(item, item.request)
    return _updated_item(item, state=ReviewerItemState.OPEN, proposal=None)


def defer_reviewer_item(item: ReviewerFeedbackItem) -> ReviewerFeedbackItem:
    return _updated_item(item, state=ReviewerItemState.DEFERRED)


def edit_reviewer_item(
    item: ReviewerFeedbackItem, *, request: str | None = None, target: LedgerTarget | None = None,
) -> ReviewerFeedbackItem:
    """Apply an explicit reviewer request/target change without minting a new id."""
    _require_request_text_to_open(item, item.request if request is None else request)
    updates: dict[str, Any] = {"state": ReviewerItemState.OPEN, "proposal": None}
    if request is not None:
        updates["request"] = request
    if target is not None:
        updates["target"] = target
    return _updated_item(item, **updates)


def _require_request_text_to_open(item: ReviewerFeedbackItem, request: str) -> None:
    """Keep the migration marker, or blank text, from becoming the request a model sees.

    "No request text" is the predicate migration uses (``not request.strip()``).

    Enforced at the transitions that open an item, not in the schema, so a loaded ledger
    always parses; a migrated item has a ``legacy_source``, a reviewer-written one does not.
    """
    if item.legacy_source is not None and (request == LEGACY_BLANK_REQUEST_MARKER or not request.strip()):
        raise RoadmapFeedbackLedgerError(
            f"item {item.item_id!r} would have no request text; "
            "a migrated item needs non-blank request text before it can be open"
        )


def target_fingerprint(
    source: ResolvedRoadmapVersion, target: LedgerTarget, *, parsed: dict[str, Any] | None = None,
) -> str:
    """Hash the selected immutable source version and exact addressed content.

    ``parsed`` holds this source's artifacts by key, so a caller fingerprinting many
    targets against one source passes one dict and parses each artifact at most once.
    """
    parsed = {} if parsed is None else parsed
    if not isinstance(source, ResolvedRoadmapVersion):
        raise RoadmapFeedbackLedgerError("target fingerprint requires a resolved roadmap version")
    artifact_bytes = _source_artifact_bytes(source, target.artifact_key)
    selected: Any = artifact_bytes.decode("utf-8")
    if target.kind is FeedbackTargetKind.ROW:
        selected = _find_exact_row(artifact_bytes, target, parsed)
    return _fingerprint(source, target, selected)


def unresolved_target_fingerprint(source: ResolvedRoadmapVersion, target: LedgerTarget) -> str:
    """Fingerprint a row target that selects no live design row.

    ``selected`` is ``None``, which no live row or artifact fingerprint carries, so
    the result never equals one and the item stays ineligible until retargeted.
    """
    if not isinstance(source, ResolvedRoadmapVersion):
        raise RoadmapFeedbackLedgerError("target fingerprint requires a resolved roadmap version")
    return _fingerprint(source, target, None)


def _fingerprint(source: ResolvedRoadmapVersion, target: LedgerTarget, selected: Any) -> str:
    payload = {
        "source_version_id": source.record.version_id,
        "artifact_key": target.artifact_key,
        "kind": target.kind.value,
        "row_id": target.row_id,
        "selected": selected,
    }
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def eligible_reviewer_items(
    ledger: RoadmapFeedbackLedger, source: ResolvedRoadmapVersion
) -> tuple[ReviewerFeedbackItem, ...]:
    """Return only open items bound to this source and its unchanged target."""
    _require_ledger(ledger)
    if not isinstance(source, ResolvedRoadmapVersion):
        return ()
    result: list[ReviewerFeedbackItem] = []
    parsed: dict[str, Any] = {}
    for group in ledger.reviewer_feedback_groups:
        for item in group.items:
            if item.state is not ReviewerItemState.OPEN:
                continue
            if item.submitted_against_version_id != source.record.version_id:
                continue
            try:
                fingerprint = target_fingerprint(source, item.target, parsed=parsed)
            except RoadmapFeedbackLedgerError:
                continue
            if fingerprint == item.target_fingerprint:
                result.append(item)
    return tuple(result)


def _source_artifact_bytes(source: ResolvedRoadmapVersion, artifact_key: str) -> bytes:
    try:
        index = source.artifact_keys.index(artifact_key)
    except ValueError as exc:
        raise RoadmapFeedbackLedgerError("target artifact is not configured") from exc
    return source.artifact_bytes[index]


def _find_exact_row(artifact_bytes: bytes, target: LedgerTarget, parsed: dict[str, Any]) -> Any:
    artifact = parsed.get(target.artifact_key)
    if artifact is None:
        try:
            parser = {
                "domain": parse_domain_artifact,
                "constraints": parse_constraints_artifact,
                "components": parse_components_artifact,
                "plans": parse_plans_artifact,
            }[target.artifact_key]
            artifact = parser(artifact_bytes.decode("utf-8"))
        except (KeyError, UnicodeDecodeError, RoadmapArtifactError) as exc:
            raise RoadmapFeedbackLedgerError("target artifact cannot supply a row fingerprint") from exc
        parsed[target.artifact_key] = artifact
    # Only design rows are addressable, the same universe the impact-closure
    # resolver treats as live; embedded feedback, removals, stores and hosting
    # are not, so a target naming one is ineligible rather than fingerprinted.
    matches = [
        row
        for rows in design_row_collections(artifact).values()
        for row in rows
        if row.id == target.row_id
    ]
    if len(matches) != 1:
        raise RoadmapFeedbackLedgerError("row target must identify exactly one artifact row")
    return _json_value(matches[0])


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _require_ledger(ledger: RoadmapFeedbackLedger) -> None:
    if not isinstance(ledger, RoadmapFeedbackLedger):
        raise RoadmapFeedbackLedgerError("expected a validated feedback ledger")


def _updated_item(item: ReviewerFeedbackItem, **updates: Any) -> ReviewerFeedbackItem:
    values = item.model_dump()
    values.update(updates)
    return ReviewerFeedbackItem(**values)


def _json_value(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {field.name: _json_value(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value
