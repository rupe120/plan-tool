"""Immutable settlement receipts: record, storage, publication, and proof.

See docs/ARCHITECTURE.md's "Decision-settlement receipts" entry for the
full design; never imports the CLI layer or deletes a published final.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError as PydanticValidationError,
    field_validator,
    model_validator,
)

from plan_tool.checkpoint import compute_input_hash
from plan_tool.roadmap_artifacts import roadmap_dir
from plan_tool.roadmap_decision_settlement import DecisionSettlementCandidate
from plan_tool.roadmap_escalation_run import (
    ReceiptCommitter,
    ReceiptHeadState,
    _receipt_final_path,
    receipt_head_state,
    receipt_path_is_within_worktree,
    receipt_worktree_for_plans_dir,
)
from plan_tool.roadmap_evidence_store import (
    EVIDENCE_CREATED,
    EVIDENCE_EXISTING,
    EVIDENCE_INVALID_INPUT,
    EVIDENCE_WRITE_FAILED,
    EvidenceNamespace,
    EvidencePublishResult,
    publish_evidence,
    read_evidence_final,
)
from plan_tool.roadmap_feedback import is_receipt_safe_id
from plan_tool.roadmap_source_identity import (
    SHA256_DIGEST_RE,
    _reject_duplicate_json_keys,
    load_pending_generation,
    pending_generation_path,
)
from plan_tool.roadmap_versions import (
    RoadmapVersionError,
    load_accepted_head,
    load_accepted_version,
    load_stored_version,
)


DECISION_SETTLEMENT_RECEIPT_SCHEMA_VERSION = 1

DecisionSettlementReceiptOutcome: TypeAlias = Literal[
    "no-worktree",
    "storage-rejected",
    "write-failed",
    "commit-failed",
    "invalid-existing-receipt",
    "collision",
    "created",
    "reused",
    "committed-existing",
]
DECISION_SETTLEMENT_RECEIPT_SUCCESS_OUTCOMES: frozenset[DecisionSettlementReceiptOutcome] = frozenset(
    {"created", "reused", "committed-existing"}
)


class DecisionSettlementReceiptError(ValueError):
    """A settlement receipt is not a valid, redacted versioned value."""


class _DecisionSettlementReceiptStage(Protocol):
    """The narrow stage shape this leaf needs, mirroring step 2's own protocol."""

    artifact_key: str


class _DecisionSettlementSemanticFields(BaseModel):
    """The closed semantic fields that form one settlement receipt's identity."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: int
    artifact_key: str
    decision_id: str
    feedback_id: str
    # "unenrolled" only parses stored legacy receipts; the builder never produces it.
    lineage: Literal["unenrolled", "enrolled"]
    predecessor_digest: str
    predecessor_version_id: str | None
    evidence_digest: str
    resulting_artifact_digest: str
    resulting_version_id: str | None

    @field_validator("schema_version", mode="before")
    @classmethod
    def _requires_supported_schema_version(cls, value: object) -> object:
        if type(value) is not int or value != DECISION_SETTLEMENT_RECEIPT_SCHEMA_VERSION:
            raise ValueError("settlement receipt schema version is unsupported")
        return value

    @field_validator("artifact_key", "decision_id", "feedback_id")
    @classmethod
    def _requires_receipt_safe_id(cls, value: str) -> str:
        if not is_receipt_safe_id(value):
            raise ValueError("settlement receipt identifiers must be receipt-safe")
        return value

    @field_validator("predecessor_digest", "evidence_digest", "resulting_artifact_digest")
    @classmethod
    def _requires_sha256(cls, value: str) -> str:
        if SHA256_DIGEST_RE.fullmatch(value) is None:
            raise ValueError("settlement receipt digest must be lowercase SHA-256")
        return value

    @field_validator("predecessor_version_id", "resulting_version_id")
    @classmethod
    def _requires_optional_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if SHA256_DIGEST_RE.fullmatch(value) is None:
            raise ValueError("settlement receipt version id must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def _requires_lineage_consistent_bindings(self) -> "_DecisionSettlementSemanticFields":
        both_bound = self.predecessor_version_id is not None and self.resulting_version_id is not None
        neither_bound = self.predecessor_version_id is None and self.resulting_version_id is None
        if self.lineage == "enrolled" and not both_bound:
            raise ValueError("an enrolled settlement receipt requires both version bindings")
        if self.lineage == "unenrolled" and not neither_bound:
            raise ValueError("a legacy unenrolled settlement receipt must not carry version bindings")
        return self


class DecisionSettlementReceipt(_DecisionSettlementSemanticFields):
    """One immutable receipt naming the exact result settlement is about to produce."""

    receipt_id: str

    @field_validator("receipt_id")
    @classmethod
    def _requires_sha256_receipt_id(cls, value: str) -> str:
        if SHA256_DIGEST_RE.fullmatch(value) is None:
            raise ValueError("settlement receipt id must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def _requires_matching_receipt_id(self) -> "DecisionSettlementReceipt":
        if self.receipt_id != _semantic_receipt_id(self):
            raise ValueError("settlement receipt id does not match its semantic fields")
        return self

    @property
    def final_name(self) -> str:
        """Return the extension-free immutable storage name."""
        return self.receipt_id


@dataclass(frozen=True)
class DecisionSettlementReceiptPublication:
    """Redacted terminal facts for one settlement receipt publication attempt."""

    outcome: DecisionSettlementReceiptOutcome
    receipt_id: str | None = None


def build_decision_settlement_receipt(
    candidate: DecisionSettlementCandidate,
    *,
    resulting_version_id: str | None,
) -> DecisionSettlementReceipt:
    """Build one immutable receipt naming the exact result settlement is about to produce.

    Pure: no filesystem access. Always produces ``lineage: enrolled`` and
    refuses a candidate without an ``accepted_version_id``, or a missing or
    non-digest ``resulting_version_id``, rather than build a receipt whose
    bindings later fail model validation.
    """
    if not isinstance(candidate, DecisionSettlementCandidate):
        raise DecisionSettlementReceiptError(
            "receipt construction requires a decision settlement candidate"
        )
    if candidate.accepted_version_id is None:
        raise DecisionSettlementReceiptError(
            "a settlement candidate requires an accepted version id"
        )
    if (
        not isinstance(resulting_version_id, str)
        or SHA256_DIGEST_RE.fullmatch(resulting_version_id) is None
    ):
        raise DecisionSettlementReceiptError(
            "a settlement candidate requires a resulting version digest"
        )

    payload: dict[str, object] = {
        "schema_version": DECISION_SETTLEMENT_RECEIPT_SCHEMA_VERSION,
        "artifact_key": candidate.selector.artifact_key,
        "decision_id": candidate.selector.decision_id,
        "feedback_id": candidate.selector.feedback_id,
        "lineage": "enrolled",
        "predecessor_digest": candidate.source_digest,
        "predecessor_version_id": candidate.accepted_version_id,
        "evidence_digest": candidate.evidence_digest,
        "resulting_artifact_digest": candidate.settled_digest,
        "resulting_version_id": resulting_version_id,
    }
    try:
        semantic = _DecisionSettlementSemanticFields.model_validate(payload)
    except PydanticValidationError as exc:
        raise DecisionSettlementReceiptError(
            "receipt construction received invalid settlement facts"
        ) from exc

    receipt_payload = {**_semantic_fields(semantic), "receipt_id": _semantic_receipt_id(semantic)}
    return _validate_receipt_payload(receipt_payload)


def render_decision_settlement_receipt(receipt: DecisionSettlementReceipt) -> bytes:
    """Render one validated receipt as canonical UTF-8 JSON bytes.

    Keeps ``predecessor_version_id`` / ``resulting_version_id`` explicit even
    when ``None`` (a stored legacy ``unenrolled`` receipt) so a reader can tell
    that from "field missing".
    """
    if not isinstance(receipt, DecisionSettlementReceipt):
        raise DecisionSettlementReceiptError(
            "receipt rendering requires a decision settlement receipt"
        )
    payload = receipt.model_dump(mode="json")
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def parse_decision_settlement_receipt(
    data: bytes, *, expected_final_name: object
) -> DecisionSettlementReceipt:
    """Decode, validate, and bind one duplicate-free receipt byte payload."""
    if not isinstance(data, bytes):
        raise DecisionSettlementReceiptError("receipt data must be UTF-8 bytes")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DecisionSettlementReceiptError("receipt data must be strict UTF-8") from exc
    receipt = _validate_receipt_payload(_decode_receipt_object(text))
    if receipt.final_name != expected_final_name:
        raise DecisionSettlementReceiptError(
            "receipt final name does not match its storage record"
        )
    return receipt


def decision_settlement_receipt_path(roadmap_root: Path, final_name: str) -> Path:
    """Return the immutable settlement final path without scanning its namespace."""
    return _receipt_final_path(
        Path(roadmap_root), final_name, namespace=EvidenceNamespace.DECISION_SETTLEMENTS
    )


def publish_decision_settlement_receipt(
    receipt: DecisionSettlementReceipt,
    *,
    plans_dir: Path,
    slug: str,
    receipt_committer: ReceiptCommitter,
) -> DecisionSettlementReceiptPublication:
    """Publish one receipt once, committed to ``HEAD`` before any canonical write.

    Checks the Git worktree before any evidence write, so ``no-worktree``
    leaves no evidence directory. Never overwrites or deletes an existing
    final — the storage layer and the path-limited committer both refuse to.
    """
    if not isinstance(receipt, DecisionSettlementReceipt):
        raise DecisionSettlementReceiptError(
            "receipt publication requires a decision settlement receipt"
        )
    root = roadmap_dir(plans_dir, slug)
    receipt_worktree = receipt_worktree_for_plans_dir(plans_dir)
    if receipt_worktree is None or not receipt_path_is_within_worktree(
        root, receipt_worktree, namespace=EvidenceNamespace.DECISION_SETTLEMENTS
    ):
        return _publication("no-worktree")

    try:
        stored = publish_evidence(
            root,
            EvidenceNamespace.DECISION_SETTLEMENTS,
            receipt.final_name,
            render_decision_settlement_receipt(receipt),
        )
    except OSError:
        stored = EvidencePublishResult(EVIDENCE_WRITE_FAILED)

    return _map_storage_result(
        stored,
        receipt=receipt,
        roadmap_root=root,
        receipt_worktree=receipt_worktree,
        receipt_committer=receipt_committer,
    )


def decision_settlement_receipt_proves_completion(
    receipt: DecisionSettlementReceipt,
    *,
    plans_dir: Path,
    slug: str,
    stages: Sequence[_DecisionSettlementReceiptStage],
) -> bool:
    """Report whether ``receipt`` still proves a completed settlement.

    See docs/ARCHITECTURE.md's "Decision-settlement receipts" entry for the
    per-lineage proof rule. A pending publication always means "not
    proven". Lets ``RoadmapVersionError`` / ``RoadmapSourceIdentityError``
    from a corrupt store propagate unchanged; that is a broken store, not a
    "does not prove" answer.
    """
    if not isinstance(receipt, DecisionSettlementReceipt):
        raise DecisionSettlementReceiptError(
            "read-back requires a decision settlement receipt"
        )
    root = roadmap_dir(plans_dir, slug)
    if load_pending_generation(pending_generation_path(root)) is not None:
        return False
    if receipt.lineage == "enrolled":
        return _enrolled_receipt_proves_completion(receipt, plans_dir=plans_dir, slug=slug)
    return _legacy_receipt_proves_completion(receipt, plans_dir=plans_dir, slug=slug)


def _enrolled_receipt_proves_completion(
    receipt: DecisionSettlementReceipt, *, plans_dir: Path, slug: str
) -> bool:
    head = load_accepted_head(plans_dir=plans_dir, slug=slug)
    if head is None:
        return False
    version_id = head.version_id
    seen: set[str] = set()
    while True:
        if version_id in seen:
            raise RoadmapVersionError(
                f"accepted version predecessor chain for {slug!r} contains a cycle "
                f"at version {version_id!r}"
            )
        seen.add(version_id)
        record = load_stored_version(plans_dir=plans_dir, slug=slug, version_id=version_id)
        if version_id == receipt.resulting_version_id:
            member = next(
                (
                    entry
                    for entry in record.artifact_members
                    if entry.artifact_key == receipt.artifact_key
                ),
                None,
            )
            return (
                member is not None
                and record.predecessor_version_id == receipt.predecessor_version_id
                and member.digest == receipt.resulting_artifact_digest
            )
        if record.predecessor_version_id is None:
            return False
        version_id = record.predecessor_version_id


def _legacy_receipt_proves_completion(
    receipt: DecisionSettlementReceipt, *, plans_dir: Path, slug: str
) -> bool:
    """Prove a stored ``lineage: unenrolled`` receipt against the accepted head only."""
    accepted_version = load_accepted_version(plans_dir=plans_dir, slug=slug)
    if accepted_version is None or receipt.artifact_key not in accepted_version.artifact_keys:
        return False
    member_index = accepted_version.artifact_keys.index(receipt.artifact_key)
    current_digest = hashlib.sha256(accepted_version.artifact_bytes[member_index]).hexdigest()
    return current_digest == receipt.resulting_artifact_digest


def _map_storage_result(
    stored: EvidencePublishResult,
    *,
    receipt: DecisionSettlementReceipt,
    roadmap_root: Path,
    receipt_worktree: Path,
    receipt_committer: ReceiptCommitter,
) -> DecisionSettlementReceiptPublication:
    if stored.outcome == EVIDENCE_CREATED:
        persisted = read_evidence_final(
            roadmap_root, EvidenceNamespace.DECISION_SETTLEMENTS, receipt.final_name
        )
        if persisted.failure is not None or persisted.data is None:
            return _publication("commit-failed")
        head_state = receipt_head_state(
            persisted.data,
            receipt_final_name=receipt.final_name,
            roadmap_root=roadmap_root,
            receipt_worktree=receipt_worktree,
            namespace=EvidenceNamespace.DECISION_SETTLEMENTS,
        )
        return _result_from_receipt_head_state(
            head_state,
            receipt=receipt,
            receipt_data=persisted.data,
            roadmap_root=roadmap_root,
            receipt_worktree=receipt_worktree,
            receipt_committer=receipt_committer,
            success_outcome="created",
        )
    if stored.outcome == EVIDENCE_EXISTING:
        return _classify_existing(
            stored.data,
            receipt=receipt,
            roadmap_root=roadmap_root,
            receipt_worktree=receipt_worktree,
            receipt_committer=receipt_committer,
        )
    if stored.outcome == EVIDENCE_INVALID_INPUT:
        return _publication("storage-rejected")
    return _publication("write-failed")


def _classify_existing(
    data: bytes | None,
    *,
    receipt: DecisionSettlementReceipt,
    roadmap_root: Path,
    receipt_worktree: Path,
    receipt_committer: ReceiptCommitter,
) -> DecisionSettlementReceiptPublication:
    if not isinstance(data, bytes):
        return _publication("invalid-existing-receipt")
    try:
        existing = parse_decision_settlement_receipt(data, expected_final_name=receipt.final_name)
        if _receipt_content_preimage(existing) != _receipt_content_preimage(receipt):
            return _publication("collision")
    except DecisionSettlementReceiptError:
        return _publication("invalid-existing-receipt")
    head_state = receipt_head_state(
        data,
        receipt_final_name=receipt.final_name,
        roadmap_root=roadmap_root,
        receipt_worktree=receipt_worktree,
        namespace=EvidenceNamespace.DECISION_SETTLEMENTS,
    )
    return _result_from_receipt_head_state(
        head_state,
        receipt=receipt,
        receipt_data=data,
        roadmap_root=roadmap_root,
        receipt_worktree=receipt_worktree,
        receipt_committer=receipt_committer,
        success_outcome="committed-existing",
    )


def _result_from_receipt_head_state(
    head_state: ReceiptHeadState,
    *,
    receipt: DecisionSettlementReceipt,
    receipt_data: bytes,
    roadmap_root: Path,
    receipt_worktree: Path,
    receipt_committer: ReceiptCommitter,
    success_outcome: Literal["created", "committed-existing"],
) -> DecisionSettlementReceiptPublication:
    """Map the closed shared-byte predicate to receipt lifecycle outcomes."""
    if head_state == "matching":
        return _publication_result("reused", receipt)
    if head_state == "missing":
        return _commit_receipt(
            receipt=receipt,
            receipt_data=receipt_data,
            roadmap_root=roadmap_root,
            receipt_worktree=receipt_worktree,
            receipt_committer=receipt_committer,
            success_outcome=success_outcome,
        )
    if head_state == "different":
        return _publication("collision")
    return _publication("commit-failed")


def _commit_receipt(
    *,
    receipt: DecisionSettlementReceipt,
    receipt_data: bytes,
    roadmap_root: Path,
    receipt_worktree: Path,
    receipt_committer: ReceiptCommitter,
    success_outcome: Literal["created", "committed-existing"],
) -> DecisionSettlementReceiptPublication:
    """Commit one exact final, retaining its local bytes when Git cannot."""
    receipt_path = decision_settlement_receipt_path(roadmap_root, receipt.final_name)
    try:
        returncode, _stderr_tail = receipt_committer(
            receipt_worktree,
            receipt_path,
            "roadmap: persist decision settlement receipt",
        )
    except (OSError, subprocess.CalledProcessError):
        return _publication("commit-failed")
    if returncode != 0:
        return _publication("commit-failed")
    if (
        receipt_head_state(
            receipt_data,
            receipt_final_name=receipt.final_name,
            roadmap_root=roadmap_root,
            receipt_worktree=receipt_worktree,
            namespace=EvidenceNamespace.DECISION_SETTLEMENTS,
        )
        != "matching"
    ):
        return _publication("commit-failed")
    return _publication_result(success_outcome, receipt)


def _publication(outcome: DecisionSettlementReceiptOutcome) -> DecisionSettlementReceiptPublication:
    return DecisionSettlementReceiptPublication(outcome=outcome, receipt_id=None)


def _publication_result(
    outcome: Literal["created", "reused", "committed-existing"],
    receipt: DecisionSettlementReceipt,
) -> DecisionSettlementReceiptPublication:
    return DecisionSettlementReceiptPublication(outcome=outcome, receipt_id=receipt.receipt_id)


def _semantic_fields(receipt: _DecisionSettlementSemanticFields) -> dict[str, object]:
    """Return exactly ``_DecisionSettlementSemanticFields``'s own declared
    fields, keyed off the base model's own ``model_fields`` (not
    hand-listed) so a future field added there is never silently left out
    of the content-addressed id and collision check that consume this
    dict's full contents. Deliberately keyed off the *base* class, not
    ``type(receipt).model_fields``: ``receipt`` is often the wider
    ``DecisionSettlementReceipt`` subtype, whose own extra ``receipt_id``
    field must stay excluded — it is what this dict's hash computes."""
    if not isinstance(receipt, _DecisionSettlementSemanticFields):
        raise DecisionSettlementReceiptError(
            "semantic identity requires settlement receipt semantic fields"
        )
    return {
        name: getattr(receipt, name)
        for name in _DecisionSettlementSemanticFields.model_fields
    }


def _semantic_receipt_id(receipt: _DecisionSettlementSemanticFields) -> str:
    return compute_input_hash(_semantic_fields(receipt))


def _receipt_content_preimage(receipt: _DecisionSettlementSemanticFields) -> str:
    """Return canonical JSON over one receipt's full semantic identity.

    Kept separate from :func:`_semantic_receipt_id` so a test can force this
    comparison to diverge without breaking the id check every parse relies on.
    """
    return json.dumps(
        _semantic_fields(receipt), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


def _validate_receipt_payload(payload: object) -> DecisionSettlementReceipt:
    try:
        return DecisionSettlementReceipt.model_validate(payload)
    except (PydanticValidationError, ValueError) as exc:
        raise DecisionSettlementReceiptError("invalid decision settlement receipt") from exc


def _decode_receipt_object(text: str) -> dict[str, object]:
    decoder = json.JSONDecoder(
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_nonstandard_constant,
        parse_float=_reject_float,
    )
    start = len(text) - len(text.lstrip(" \t\r\n"))
    try:
        payload, end = decoder.raw_decode(text, start)
    except DecisionSettlementReceiptError:
        raise
    except ValueError as exc:
        raise DecisionSettlementReceiptError(
            "receipt data must be one duplicate-free JSON object"
        ) from exc
    if text[end:].strip(" \t\r\n"):
        raise DecisionSettlementReceiptError("receipt data must not contain trailing JSON")
    if not isinstance(payload, dict):
        raise DecisionSettlementReceiptError("receipt root must be a JSON object")
    return payload


def _reject_nonstandard_constant(value: str) -> None:
    raise DecisionSettlementReceiptError("receipt JSON cannot contain a non-finite constant")


def _reject_float(value: str) -> None:
    raise DecisionSettlementReceiptError("receipt JSON cannot contain a floating-point value")
