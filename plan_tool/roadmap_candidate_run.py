"""Bounded storage of one immutable roadmap candidate proposal."""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, is_dataclass, fields
from pathlib import Path
from string import Template
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_serializer, model_validator

from plan_tool import roadmap_candidate, shell
from plan_tool.fileio import durable_write_bytes
from plan_tool.renderer import prompts_dir
from plan_tool.roadmap import STAGES, read_roadmap_text, refresh_roadmap_index
from plan_tool.roadmap_candidate import (
    CandidateDelta,
    CandidateDeltaError,
    CandidatePredecessorDiff,
    GateCleanCandidate,
    ReviewRequiredCandidate,
    materialize_candidate,
    parse_candidate_delta,
)
from plan_tool.roadmap_candidate_context import (
    CandidateContextBatchCapsule,
    CandidateContextBatchReceipt,
    CandidateContextCapsule,
    CandidateContextFeedback,
    CandidateContextFullMember,
    CandidateContextInventoryEntry,
    CandidateContextReceipt,
    build_candidate_context,
    candidate_collection_hints,
    _capsule_is_intact,
    expand_candidate_context,
    is_supported_candidate_context_ceiling,
)
from plan_tool.roadmap_feedback_ledger import (
    DerivedFeedbackContext,
    ProposalFields,
    ReviewerFeedbackGroup,
    ReviewerFeedbackItem,
    ReviewerItemState,
    RoadmapFeedbackLedger,
    RoadmapFeedbackLedgerError,
    item_snapshot,
    load_ledger,
    render_ledger,
    roadmap_feedback_ledger_path,
)
from plan_tool.roadmap_json import unwrap_enum_value
from plan_tool.roadmap_revision_publish import (
    RoadmapWriterGuardError,
    publish_roadmap_generation,
    roadmap_writer_guard,
)
from plan_tool.roadmap_source_identity import GenerationMember, PendingGeneration
from plan_tool.roadmap_versions import (
    INITIAL_EMPTY_REVIEW_LINEAGE_ID,
    PreparedRoadmapVersion,
    ResolvedRoadmapVersion,
    RoadmapVersionContent,
    RoadmapVersionError,
    StoredRoadmapVersion,
    create_candidate_version,
    load_stored_version,
    load_accepted_version,
    sha256_digests,
    stored_artifact_path,
    stored_brief_path,
    stored_version_members,
    version_directory_path,
    version_namespace_path,
)
from plan_tool.run_log import RunLogWriter, hash_prompt


CANDIDATE_PROPOSAL_PHASE: Final[str] = "roadmap-candidate-proposal"
_ADMISSION_FILENAME: Final[str] = "candidate-admission.json"
_EVIDENCE_FILENAME: Final[str] = "candidate-evidence.json"
_SCHEMA_VERSION: Final[int] = 1
_SHA256_DIGEST_RE: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{64}", re.ASCII)

CandidateProposalInvoker = Callable[[str], tuple[int, str]]
CandidateProposalOutcome = Literal["stored", "response-rejected", "failed", "refused", "interrupted"]


class CandidateProposalError(ValueError):
    """A persisted proposal lineage is malformed or cannot be safely used."""


class CandidateStorageRefusal(CandidateProposalError):
    """Mutable state changed after a batch was built; storage refused and wrote nothing."""


class CandidateProposalResponseError(ValueError):
    """A model reply is outside the closed proposal response contract."""


class _FrozenProposalRecord(BaseModel):
    """Closed, immutable records retained beside immutable candidate versions."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, arbitrary_types_allowed=True)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_digest(value: str, *, name: str) -> str:
    if not isinstance(value, str) or _SHA256_DIGEST_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a SHA-256 digest")
    return value


class CandidateGateEvidence(_FrozenProposalRecord):
    """The persisted green outcome for one fixed roadmap stage."""

    artifact_key: str
    violations: tuple[str, ...]


class CandidateReviewPair(_FrozenProposalRecord):
    """The one immutable question-and-answer pair a later replacement may carry."""

    question_id: str
    anchor: str
    question_text: str
    answer_id: str
    answer_text: str

    @field_validator("question_id", "anchor", "answer_id")
    @classmethod
    def _requires_nonempty_text(cls, value: str) -> str:
        if not value:
            raise ValueError("candidate review pair fields must be nonempty")
        return value


class CandidateProposalAdmission(_FrozenProposalRecord):
    """The one fixed feedback lineage permitted for an enrolled roadmap."""

    schema_version: int
    roadmap_slug: str
    predecessor_version_id: str
    feedback: CandidateContextFeedback | None = None
    capsule: CandidateContextCapsule | CandidateContextBatchCapsule | None = None
    receipt: CandidateContextReceipt | CandidateContextBatchReceipt | None = None
    expansion_available: bool
    candidate_version_id: str | None = None
    # Batch admissions retain the accepted root independently of the source
    # used for the next candidate.  The older fields remain readable for the
    # selector-only proposal format.
    root_version_id: str | None = None
    active_candidate_version_id: str | None = None

    @model_serializer(mode="wrap")
    def _omit_pointer_keys_from_selector_era_record(self, handler: Any) -> dict[str, Any]:
        # Selector-era admissions were written without the batch pointer keys; a
        # batch admission keeps both, with an explicit null for a released pointer.
        data = handler(self)
        if self.root_version_id is None and self.active_candidate_version_id is None:
            data.pop("root_version_id", None)
            data.pop("active_candidate_version_id", None)
        return data

    @field_validator("schema_version", mode="before")
    @classmethod
    def _requires_schema_version(cls, value: object) -> int:
        if type(value) is not int or value != _SCHEMA_VERSION:
            raise ValueError("candidate proposal admission schema version is unsupported")
        return value

    @field_validator("roadmap_slug")
    @classmethod
    def _requires_slug(cls, value: str) -> str:
        if (
            not value
            or value in {".", ".."}
            or "/" in value
            or "\\" in value
            or Path(value).parts != (value,)
        ):
            raise ValueError("candidate proposal admission slug is invalid")
        return value

    @field_validator("predecessor_version_id", "candidate_version_id", "root_version_id", "active_candidate_version_id")
    @classmethod
    def _requires_identities(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return value
        field_name = getattr(info, "field_name", "candidate proposal identity")
        return _require_digest(value, name=field_name)

    @model_validator(mode="after")
    def _requires_bound_capsule(self) -> "CandidateProposalAdmission":
        # A batch admission is deliberately only a root/active pointer.  Its
        # model authority lives beside each immutable candidate, never here.
        if self.root_version_id is not None:
            if self.root_version_id != self.predecessor_version_id or any(
                value is not None for value in (self.feedback, self.capsule, self.receipt)
            ) or self.expansion_available:
                raise ValueError("candidate batch admission has inconsistent root bindings")
            if self.candidate_version_id != self.active_candidate_version_id:
                raise ValueError("candidate batch admission has inconsistent active pointer")
            return self
        if self.capsule is None or self.receipt is None or self.feedback is None:
            raise ValueError("candidate proposal admission lacks immutable bindings")
        if (
            self.capsule.receipt != self.receipt
            or self.capsule.feedback != self.feedback
            or self.capsule.predecessor.version_id != self.predecessor_version_id
            or self.receipt.predecessor.version_id != self.predecessor_version_id
            or self.receipt.feedback != self.feedback
            or self.expansion_available != (self.capsule.expansion is None)
        ):
            raise ValueError("candidate proposal admission has inconsistent immutable bindings")
        if (
            not is_supported_candidate_context_ceiling(self.capsule.ceiling_bytes)
            or self.receipt.ceiling_bytes != self.capsule.ceiling_bytes
            or self.receipt.payload_bytes != len(self.capsule.payload)
            or _digest(self.capsule.payload) != self.capsule.capsule_identity
            or self.capsule.capsule_identity != self.receipt.payload_digest
            or self.capsule.capsule_identity != self.receipt.capsule_identity
            or not _capsule_and_receipt_are_exact(self.capsule, self.receipt)
        ):
            raise ValueError("candidate proposal capsule does not bind its exact payload")
        return self


class CandidateProposalEvidence(_FrozenProposalRecord):
    """Complete inert evidence retained with one stored candidate version."""

    schema_version: int
    roadmap_slug: str
    candidate_version_id: str
    predecessor_version_id: str
    review_lineage_identity: str
    feedback: CandidateContextFeedback | None = None
    raw_brief_digest: str
    artifact_digests: tuple[str, ...]
    content_identity: str
    predecessor_diff: CandidatePredecessorDiff
    gate_evidence: tuple[CandidateGateEvidence, ...]
    capsule: CandidateContextCapsule | CandidateContextBatchCapsule
    receipt: CandidateContextReceipt | CandidateContextBatchReceipt
    expansion_available: bool
    review_requirement: roadmap_candidate.CandidateReviewRequirement | None = None
    root_version_id: str | None = None
    source_version_id: str | None = None
    batch_receipt: CandidateContextBatchReceipt | None = None
    normalized_operations: tuple[roadmap_candidate.CandidateDeltaOperation, ...] | None = None
    operation_classification: roadmap_candidate.CandidateOperationClassification | None = None

    @field_validator("schema_version", mode="before")
    @classmethod
    def _requires_schema_version(cls, value: object) -> int:
        if type(value) is not int or value != _SCHEMA_VERSION:
            raise ValueError("candidate proposal evidence schema version is unsupported")
        return value

    @field_validator(
        "candidate_version_id",
        "predecessor_version_id",
        "review_lineage_identity",
        "raw_brief_digest",
        "content_identity",
    )
    @classmethod
    def _requires_digest_fields(cls, value: str, info: object) -> str:
        return _require_digest(value, name=getattr(info, "field_name", "candidate evidence"))

    @field_validator("artifact_digests")
    @classmethod
    def _requires_artifact_digests(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(STAGES):
            raise ValueError("candidate evidence must bind every artifact digest")
        return tuple(_require_digest(item, name="candidate artifact digest") for item in value)

    @field_validator("normalized_operations", mode="before")
    @classmethod
    def _requires_normalized_operations(
        cls, value: object
    ) -> tuple[roadmap_candidate.CandidateDeltaOperation, ...] | None:
        if value is None:
            return None
        try:
            return parse_candidate_delta(
                _canonical_json_text({"operations": roadmap_candidate._operations_wire_for_reparse(value)})
            ).operations
        except CandidateDeltaError as exc:
            raise ValueError("candidate batch operations are malformed") from exc

    @model_validator(mode="after")
    def _requires_exact_bindings(self) -> "CandidateProposalEvidence":
        if self.batch_receipt is not None:
            if (
                not isinstance(self.capsule, CandidateContextBatchCapsule)
                or not isinstance(self.receipt, CandidateContextBatchReceipt)
                or self.receipt != self.batch_receipt
                or self.capsule.receipt != self.receipt
                or self.root_version_id != self.receipt.root.version_id
                or self.source_version_id != self.receipt.source.version_id
                or self.predecessor_version_id != self.source_version_id
                or self.feedback is not None
                or (self.normalized_operations is None) != (self.operation_classification is None)
            ):
                raise ValueError("candidate batch evidence has inconsistent immutable bindings")
            return self
        if self.normalized_operations is not None or self.operation_classification is not None:
            raise ValueError("selector-era candidate evidence cannot claim batch route facts")
        if (
            self.review_lineage_identity != INITIAL_EMPTY_REVIEW_LINEAGE_ID
            or not is_supported_candidate_context_ceiling(self.capsule.ceiling_bytes)
            or self.receipt.ceiling_bytes != self.capsule.ceiling_bytes
            or self.capsule.receipt != self.receipt
            or self.capsule.feedback != self.feedback
            or self.capsule.predecessor.version_id != self.predecessor_version_id
            or self.receipt.predecessor.version_id != self.predecessor_version_id
            or self.expansion_available != (self.capsule.expansion is None)
            or tuple(item.artifact_key for item in self.gate_evidence)
            != tuple(stage.artifact_key for stage in STAGES)
            or any(item.violations for item in self.gate_evidence)
            or self.receipt.payload_bytes != len(self.capsule.payload)
            or _digest(self.capsule.payload) != self.capsule.capsule_identity
            or self.capsule.capsule_identity != self.receipt.payload_digest
            or self.capsule.capsule_identity != self.receipt.capsule_identity
            or not _capsule_and_receipt_are_exact(self.capsule, self.receipt)
        ):
            raise ValueError("candidate evidence has inconsistent immutable bindings")
        if self.review_requirement is not None and (
            self.review_requirement.predecessor_version_id != self.predecessor_version_id
            or self.review_requirement.selected_feedback != self.feedback
            or self.review_requirement.capsule_receipt != self.receipt
            or roadmap_candidate._wire_value(self.review_requirement.predecessor_diff)
            != roadmap_candidate._wire_value(self.predecessor_diff)
        ):
            raise ValueError("candidate review requirement does not bind its candidate evidence")
        return self


class CandidateTerminalResolution(_FrozenProposalRecord):
    """Immutable history entry for a released non-promoted candidate."""

    schema_version: int
    root_version_id: str
    source_version_id: str
    candidate_version_id: str
    batch_receipt: CandidateContextBatchReceipt
    reason: Literal["rejected", "discarded", "settled"]

    @field_validator("schema_version", mode="before")
    @classmethod
    def _requires_schema_version(cls, value: object) -> int:
        if value != _SCHEMA_VERSION:
            raise ValueError("candidate terminal resolution schema version is unsupported")
        return cast(int, value)

    @field_validator("root_version_id", "source_version_id", "candidate_version_id")
    @classmethod
    def _requires_version_digests(cls, value: str, info: Any) -> str:
        return _require_digest(value, name=getattr(info, "field_name", "candidate terminal resolution"))

    @model_validator(mode="after")
    def _requires_receipt_bindings(self) -> "CandidateTerminalResolution":
        if (
            self.root_version_id != self.batch_receipt.root.version_id
            or self.source_version_id != self.batch_receipt.source.version_id
        ):
            raise ValueError("candidate terminal resolution does not bind its batch receipt")
        return self


class CandidateSupersession(_FrozenProposalRecord):
    """Immutable relation marking a former active candidate as superseded.

    History only: the root/active pointer stays the sole processing selector.
    """

    schema_version: int
    root_version_id: str
    superseded_candidate_version_id: str
    successor_candidate_version_id: str

    @field_validator("schema_version", mode="before")
    @classmethod
    def _requires_schema_version(cls, value: object) -> int:
        if value != _SCHEMA_VERSION:
            raise ValueError("candidate supersession schema version is unsupported")
        return cast(int, value)

    @field_validator(
        "root_version_id", "superseded_candidate_version_id", "successor_candidate_version_id"
    )
    @classmethod
    def _requires_version_digests(cls, value: str, info: Any) -> str:
        return _require_digest(value, name=getattr(info, "field_name", "candidate supersession"))


@dataclass(frozen=True)
class StoredCandidateProposal:
    """One completely validated candidate version and its adjacent evidence."""

    record: StoredRoadmapVersion
    content: RoadmapVersionContent
    evidence: CandidateProposalEvidence

    @property
    def version_id(self) -> str:
        """Return the immutable candidate-version identity."""
        return self.record.version_id


@dataclass(frozen=True)
class CandidateProposalResult:
    """The closed terminal result of one bounded initial-proposal attempt."""

    outcome: CandidateProposalOutcome
    candidate: StoredCandidateProposal | None = None
    detail: str | None = None
    call_count: int = 0

    def __post_init__(self) -> None:
        if (self.outcome == "stored") != (self.candidate is not None):
            raise ValueError("only a stored candidate proposal result may expose a candidate")


@dataclass(frozen=True)
class CandidateModelInvocation:
    """One candidate-model reply retained until the terminal result is recorded."""

    attempt: int
    rc: int
    response: str


@dataclass
class _ProposalAttempt:
    """Diagnostic state the run's terminal record reads, filled by a route that owns its own steps."""

    call_count: int = 0
    last_response: CandidateModelInvocation | None = None
    response_accepted: bool = False
    terminal_response_recorded: bool = False


@dataclass(frozen=True)
class CandidateExpansionRequest:
    """The compact-inventory item named by the first closed response."""

    entry: CandidateContextInventoryEntry


def shell_candidate_proposal_invoker(prompt: str) -> tuple[int, str]:
    """Make one physical candidate-proposal request without rate-limit waiting."""
    return shell.claude_invoke(
        prompt,
        phase=CANDIDATE_PROPOSAL_PHASE,
        attempt=1,
        wait_on_rate_limit=False,
        max_transient_retries=1,
    )


def candidate_admission_path(plans_dir: Path, slug: str) -> Path:
    """Return the roadmap-fixed lineage admission path."""
    return version_namespace_path(plans_dir, slug) / _ADMISSION_FILENAME


def candidate_evidence_path(plans_dir: Path, slug: str, candidate_version_id: str) -> Path:
    """Return the adjacent immutable evidence path for one candidate version."""
    return version_directory_path(plans_dir, slug, candidate_version_id) / _EVIDENCE_FILENAME


def render_candidate_admission(admission: CandidateProposalAdmission) -> bytes:
    """Render one validated admission using exact canonical JSON bytes."""
    return _render_record(admission, description="candidate proposal admission")


def parse_candidate_admission(data: bytes) -> CandidateProposalAdmission:
    """Parse one exact canonical persisted proposal admission."""
    return _parse_record(data, CandidateProposalAdmission, description="candidate proposal admission")


def render_candidate_evidence(evidence: CandidateProposalEvidence) -> bytes:
    """Render one validated inert candidate-evidence record."""
    return _render_record(
        evidence,
        description="candidate proposal evidence",
        exclude_none=True,
    )


def render_candidate_terminal_resolution(resolution: CandidateTerminalResolution) -> bytes:
    """Render one closed terminal-history record."""
    return _render_record(resolution, description="candidate terminal resolution")


def render_candidate_supersession(supersession: CandidateSupersession) -> bytes:
    """Render one closed supersession-history record."""
    return _render_record(supersession, description="candidate supersession")


_SUPERSESSIONS_DIRECTORY: Final[str] = "candidate-supersessions"


def supersession_path(plans_dir: Path, slug: str, superseded_candidate_version_id: str) -> Path:
    """Return the immutable supersession record path for one replaced candidate."""
    _require_digest(superseded_candidate_version_id, name="candidate version id")
    return (
        version_namespace_path(plans_dir, slug)
        / _SUPERSESSIONS_DIRECTORY
        / f"{superseded_candidate_version_id}.json"
    )


def build_supersession_member(
    *, plans_dir: Path, slug: str, admission: CandidateProposalAdmission, successor_version_id: str
) -> GenerationMember:
    """Build the new-file member recording ``admission``'s active candidate as superseded.

    Written in the same generation as the pointer replacement, so a crash cannot
    leave a replaced candidate without its supersession record.
    """
    if admission.root_version_id is None or admission.active_candidate_version_id is None:
        raise CandidateProposalError("supersession requires an active candidate")
    path = supersession_path(plans_dir, slug, admission.active_candidate_version_id)
    if path.exists() or path.is_symlink():
        raise CandidateStorageRefusal("candidate supersession already exists")
    record = CandidateSupersession(
        schema_version=_SCHEMA_VERSION,
        root_version_id=admission.root_version_id,
        superseded_candidate_version_id=admission.active_candidate_version_id,
        successor_candidate_version_id=successor_version_id,
    )
    root = version_namespace_path(plans_dir, slug).parent
    return GenerationMember(
        path.relative_to(root).as_posix(), None, render_candidate_supersession(record)
    )


def parse_candidate_supersession(data: bytes) -> CandidateSupersession:
    """Parse one exact canonical persisted supersession record."""
    return _parse_record(data, CandidateSupersession, description="candidate supersession")


def load_candidate_supersession(
    *, plans_dir: Path, slug: str, superseded_candidate_version_id: str
) -> CandidateSupersession:
    """Load the immutable record naming the successor of one superseded candidate."""
    path = supersession_path(plans_dir, slug, superseded_candidate_version_id)
    try:
        record = parse_candidate_supersession(path.read_bytes())
    except OSError as exc:
        raise CandidateProposalError("candidate supersession is unreadable") from exc
    if record.superseded_candidate_version_id != superseded_candidate_version_id:
        raise CandidateProposalError("candidate supersession does not match its requested identity")
    return record


_TERMINAL_RESOLUTIONS_DIRECTORY: Final[str] = "candidate-terminal-resolutions"


def terminal_resolution_path(plans_dir: Path, slug: str, candidate_version_id: str) -> Path:
    """Return the immutable terminal record path for one released candidate."""
    _require_digest(candidate_version_id, name="candidate version id")
    return version_namespace_path(plans_dir, slug) / _TERMINAL_RESOLUTIONS_DIRECTORY / f"{candidate_version_id}.json"


def new_terminal_resolution(
    candidate: "StoredCandidateProposal", *, reason: Literal["rejected", "discarded", "settled"]
) -> CandidateTerminalResolution:
    """Bind one released batch candidate's own root/source/batch evidence to a reason."""
    evidence = candidate.evidence
    if evidence.batch_receipt is None or evidence.root_version_id is None or evidence.source_version_id is None:
        raise CandidateProposalError("terminal resolution requires an active batch candidate")
    return CandidateTerminalResolution(
        schema_version=_SCHEMA_VERSION,
        root_version_id=evidence.root_version_id,
        source_version_id=evidence.source_version_id,
        candidate_version_id=candidate.version_id,
        batch_receipt=evidence.batch_receipt,
        reason=reason,
    )


def build_terminal_resolution_generation(
    *,
    plans_dir: Path,
    slug: str,
    admission: CandidateProposalAdmission,
    resolution: CandidateTerminalResolution,
) -> PendingGeneration:
    """Pair the bare pointer release with its immutable terminal-history record."""
    if (
        resolution.candidate_version_id != admission.active_candidate_version_id
        or resolution.root_version_id != admission.root_version_id
    ):
        raise CandidateProposalError("terminal resolution does not name the candidate being released")
    path = terminal_resolution_path(plans_dir, slug, resolution.candidate_version_id)
    if path.exists() or path.is_symlink():
        raise CandidateProposalError("candidate terminal resolution already exists")
    release = build_active_candidate_pointer_release_generation(
        plans_dir=plans_dir, slug=slug, admission=admission
    )
    root = version_namespace_path(plans_dir, slug).parent
    member = GenerationMember(
        path.relative_to(root).as_posix(), None, render_candidate_terminal_resolution(resolution)
    )
    return PendingGeneration(kind="candidate-terminal-resolution", members=release.members + (member,))


def build_active_candidate_pointer_release_generation(
    *, plans_dir: Path, slug: str, admission: CandidateProposalAdmission
) -> PendingGeneration:
    """Build the bare active-pointer release used by promotion and terminal flows."""
    if admission.root_version_id is None or admission.active_candidate_version_id is None:
        raise CandidateProposalError("active candidate pointer is not present")
    path = candidate_admission_path(plans_dir, slug)
    root = version_namespace_path(plans_dir, slug).parent
    released = admission.model_copy(update={"candidate_version_id": None, "active_candidate_version_id": None})
    return PendingGeneration(
        kind="candidate-pointer-release",
        members=(GenerationMember(path.relative_to(root).as_posix(), render_candidate_admission(admission), render_candidate_admission(released)),),
    )


def parse_candidate_evidence(data: bytes) -> CandidateProposalEvidence:
    """Parse one exact canonical persisted candidate-evidence record."""
    return _parse_record(
        data,
        CandidateProposalEvidence,
        description="candidate proposal evidence",
        exclude_none=True,
    )


def load_candidate_admission(*, plans_dir: Path, slug: str) -> CandidateProposalAdmission | None:
    """Load the one fixed proposal lineage without compiling any fresh context."""
    path = candidate_admission_path(plans_dir, slug)
    if not path.exists():
        if path.is_symlink():
            raise CandidateProposalError("candidate proposal admission is a dangling symlink")
        return None
    try:
        admission = parse_candidate_admission(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise CandidateProposalError("candidate proposal admission is unreadable") from exc
    if admission.roadmap_slug != slug:
        raise CandidateProposalError("candidate proposal admission does not match its roadmap")
    return admission


def load_stored_candidate_proposal(
    *, plans_dir: Path, slug: str, candidate_version_id: str
) -> StoredCandidateProposal:
    """Load and reproduce exact candidate bytes and evidence without selecting a head."""
    try:
        record = load_stored_version(
            plans_dir=plans_dir, slug=slug, version_id=candidate_version_id
        )
    except RoadmapVersionError as exc:
        raise CandidateProposalError("candidate version record is unreadable") from exc
    if record.version_kind != "candidate":
        raise CandidateProposalError("candidate proposal binding does not name a candidate version")
    brief_bytes = _read_member(
        stored_brief_path(plans_dir, slug, candidate_version_id),
        expected_digest=record.brief_digest,
        description="candidate recorded brief",
    )
    artifact_bytes = tuple(
        _read_member(
            stored_artifact_path(plans_dir, slug, candidate_version_id, member.artifact_key),
            expected_digest=member.digest,
            description=f"candidate artifact {member.artifact_key}",
        )
        for member in record.artifact_members
    )
    evidence_path = candidate_evidence_path(plans_dir, slug, candidate_version_id)
    try:
        evidence = parse_candidate_evidence(evidence_path.read_bytes())
    except (OSError, ValueError) as exc:
        raise CandidateProposalError("candidate evidence is unreadable") from exc
    if (
        evidence.roadmap_slug != slug
        or evidence.candidate_version_id != candidate_version_id
        or evidence.predecessor_version_id != record.predecessor_version_id
        or evidence.content_identity != record.content_identity
        or evidence.review_lineage_identity != record.review_lineage_identity
        or evidence.raw_brief_digest != record.brief_digest
        or evidence.artifact_digests != tuple(member.digest for member in record.artifact_members)
    ):
        raise CandidateProposalError("candidate evidence does not bind its stored version")
    candidate = StoredCandidateProposal(
        record=record,
        content=RoadmapVersionContent(brief_bytes=brief_bytes, artifact_bytes=artifact_bytes),
        evidence=evidence,
    )
    _validate_candidate_evidence(candidate, plans_dir=plans_dir, slug=slug)
    return candidate


def source_ancestry_to_root(
    *, plans_dir: Path, slug: str, source_version_id: str, root_version_id: str
) -> tuple[str, ...]:
    """Walk stored predecessor records from a candidate source up to the root.

    Returns the predecessor ids from the source's immediate predecessor through
    the root, inclusive; ``()`` when the source is the root. Every intermediate
    version must be a stored candidate, so an unrelated, broken, or cyclic chain
    refuses rather than being trusted.
    """
    if source_version_id == root_version_id:
        return ()
    chain: list[str] = []
    seen = {source_version_id}
    current = source_version_id
    while True:
        try:
            record = load_stored_version(plans_dir=plans_dir, slug=slug, version_id=current)
        except RoadmapVersionError as exc:
            raise CandidateProposalError("candidate source ancestry is unreadable") from exc
        if record.version_kind != "candidate" or record.predecessor_version_id in seen:
            raise CandidateProposalError("candidate batch source does not trace to its declared root")
        current = record.predecessor_version_id
        seen.add(current)
        chain.append(current)
        if current == root_version_id:
            return tuple(chain)


@dataclass(frozen=True)
class CandidateStackRoute:
    """The unpromoted candidates above a recorded root, oldest first, ending at the tip."""

    hops: tuple[StoredCandidateProposal, ...]

    @property
    def is_structural(self) -> bool:
        """Whether any hop stores a STRUCTURAL route; a hop with no stored route contributes nothing."""
        return any(
            hop.evidence.operation_classification
            is roadmap_candidate.CandidateOperationClassification.STRUCTURAL
            for hop in self.hops
        )


def candidate_stack_route(
    *, plans_dir: Path, slug: str, tip_version_id: str, root_version_id: str | None
) -> CandidateStackRoute:
    """Derive the unpromoted stack from ``tip_version_id`` down to, excluding, ``root_version_id``.

    An unreadable hop raises ``CandidateProposalError``; it is never read as "not structural".
    See docs/implementation-plans/archive/2-roadmap-stack-aware-approval.md § "Architecture" (Stack route).
    """
    if root_version_id is None or tip_version_id == root_version_id:
        return CandidateStackRoute(hops=())
    ancestry = source_ancestry_to_root(
        plans_dir=plans_dir, slug=slug, source_version_id=tip_version_id, root_version_id=root_version_id
    )
    unpromoted_ids = (*reversed(ancestry[:-1]), tip_version_id)
    return CandidateStackRoute(
        hops=tuple(
            load_stored_candidate_proposal(plans_dir=plans_dir, slug=slug, candidate_version_id=version_id)
            for version_id in unpromoted_ids
        )
    )


def _validate_candidate_evidence(
    candidate: StoredCandidateProposal, *, plans_dir: Path, slug: str
) -> None:
    """Reproduce candidate facts before publication or later review use."""
    evidence = candidate.evidence
    if evidence.batch_receipt is not None:
        if not _capsule_is_intact(evidence.capsule):
            raise CandidateProposalError("candidate batch capsule does not match its stored evidence")
        root = _load_resolved_version(
            plans_dir=plans_dir, slug=slug, version_id=evidence.root_version_id or ""
        )
        source = _load_resolved_version(
            plans_dir=plans_dir, slug=slug, version_id=evidence.source_version_id or ""
        )
        if (
            root.record.version_id != evidence.batch_receipt.root.version_id
            or source.record.version_id != evidence.batch_receipt.source.version_id
            or source.record.version_id != candidate.record.predecessor_version_id
        ):
            raise CandidateProposalError("candidate batch source does not trace to its declared root")
        source_ancestry_to_root(
            plans_dir=plans_dir, slug=slug,
            source_version_id=source.record.version_id, root_version_id=root.record.version_id,
        )
        # Not recomputed for batch evidence: gate_evidence, review_requirement, content_identity and
        # capsule reproduction; identity is bound via the stored record and `_capsule_is_intact`.
        _require_reproducible_batch_diff(candidate, source)
        _require_reproducible_batch_operations(candidate, source)
        return
    predecessor = _load_resolved_version(
        plans_dir=plans_dir, slug=slug, version_id=evidence.predecessor_version_id
    )
    if candidate.content.brief_bytes != predecessor.brief_bytes:
        raise CandidateProposalError("candidate recorded brief does not match its predecessor")
    capsule = _hydrate_capsule(evidence.capsule)
    verified = roadmap_candidate._verify_bindings(
        predecessor=predecessor,
        capsule=capsule,
        receipt=evidence.receipt,
        stages=STAGES,
    )
    if isinstance(verified, roadmap_candidate.CandidateRefusal):
        raise CandidateProposalError("candidate capsule cannot be reproduced from its predecessor")
    predecessor_artifacts, predecessor_bytes = verified
    if len(candidate.content.artifact_bytes) != len(STAGES):
        raise CandidateProposalError("candidate does not retain every roadmap stage artifact")
    try:
        candidate_members = tuple(
            roadmap_candidate.CandidateArtifact(
                artifact_key=stage.artifact_key,
                data=data,
                text=data.decode("utf-8"),
                artifact=stage.parse(data.decode("utf-8")),
                digest=_digest(data),
            )
            for stage, data in zip(STAGES, candidate.content.artifact_bytes, strict=True)
        )
    except (AttributeError, TypeError, UnicodeDecodeError, ValueError) as exc:
        raise CandidateProposalError("candidate stored artifacts are unreadable") from exc
    expected_diff = roadmap_candidate._build_predecessor_diff(
        predecessor_artifacts=predecessor_artifacts,
        candidate_artifacts={member.artifact_key: member.artifact for member in candidate_members},
        predecessor_bytes=predecessor_bytes,
        candidate_artifacts_bytes=tuple(member.data for member in candidate_members),
        stages=STAGES,
    )
    expected_content_identity = roadmap_candidate._content_identity(
        predecessor_version_id=predecessor.record.version_id,
        selected_feedback=evidence.feedback,
        receipt=evidence.receipt,
        artifacts=candidate_members,
        predecessor_diff=expected_diff,
    )
    if (
        roadmap_candidate._wire_value(evidence.predecessor_diff)
        != roadmap_candidate._wire_value(expected_diff)
        or evidence.content_identity != expected_content_identity
        or candidate.record.content_identity != expected_content_identity
    ):
        raise CandidateProposalError("candidate evidence cannot be reproduced from stored bytes")
    gate_evidence = roadmap_candidate.CompleteRoadmapGateEvidence(
        artifact_keys=tuple(stage.artifact_key for stage in STAGES),
        artifact_texts=tuple(member.text for member in candidate_members),
        artifacts=tuple(member.artifact for member in candidate_members),
        artifact_digests=tuple(member.digest for member in candidate_members),
        brief_bytes=candidate.content.brief_bytes,
    )
    try:
        outcomes = roadmap_candidate.check_complete_roadmap_gates(gate_evidence, stages=STAGES)
    except roadmap_candidate.RoadmapImpactSnapshotError as exc:
        raise CandidateProposalError("candidate stored gate evidence is invalid") from exc
    if (
        len(outcomes) != len(STAGES)
        or any(outcome.stage is not stage for outcome, stage in zip(outcomes, STAGES, strict=True))
        or any(outcome.violations for outcome in outcomes)
    ):
        raise CandidateProposalError("candidate does not pass the complete stored roadmap gate walk")
    expected_gate_evidence = tuple(
        CandidateGateEvidence(
            artifact_key=outcome.stage.artifact_key,
            violations=tuple(violation.message for violation in outcome.violations),
        )
        for outcome in outcomes
    )
    if evidence.gate_evidence != expected_gate_evidence:
        raise CandidateProposalError("candidate stored gate evidence cannot be reproduced")
    review_required = roadmap_candidate._candidate_diff_requires_review_requirement(expected_diff)
    if (evidence.review_requirement is not None) != review_required:
        raise CandidateProposalError("candidate review requirement does not match materialization")
    if evidence.review_requirement is not None:
        try:
            replay_delta = parse_candidate_delta(
                _canonical_json_text(
                    {"operations": roadmap_candidate._operations_wire_for_reparse(
                        evidence.review_requirement.normalized_operations
                    )}
                )
            )
        except (CandidateDeltaError, CandidateProposalError) as exc:
            raise CandidateProposalError("candidate review requirement is malformed") from exc
        replayed = materialize_candidate(
            replay_delta, predecessor=predecessor, capsule=capsule, receipt=evidence.receipt
        )
        if replayed.review_required is None or replayed.refusal is not None:
            raise CandidateProposalError("candidate review requirement cannot be reproduced")
        if (
            tuple(item.data for item in replayed.review_required.artifacts)
            != candidate.content.artifact_bytes
            or roadmap_candidate._wire_value(replayed.review_required.review_requirement)
            != roadmap_candidate._wire_value(evidence.review_requirement)
        ):
            raise CandidateProposalError("candidate review requirement cannot be reproduced")


def _require_reproducible_batch_diff(
    candidate: StoredCandidateProposal, source: ResolvedRoadmapVersion
) -> None:
    """Refuse batch evidence whose `predecessor_diff` differs from its stored bytes.

    The diff is the one stored field the batch flow reads (the question prompt and
    `diff-row` anchors), and it is recomputable from the source and the stored artifacts.
    """
    parsed = roadmap_candidate._parse_predecessor_artifacts(source, STAGES)
    if isinstance(parsed, roadmap_candidate.CandidateRefusal):
        raise CandidateProposalError("candidate batch source cannot be reproduced from its stored bytes")
    source_artifacts, source_bytes = parsed
    try:
        candidate_artifacts = {
            stage.artifact_key: stage.parse(data.decode("utf-8"))
            for stage, data in zip(STAGES, candidate.content.artifact_bytes, strict=True)
        }
    except (AttributeError, TypeError, UnicodeDecodeError, ValueError) as exc:
        raise CandidateProposalError("candidate stored artifacts are unreadable") from exc
    expected = roadmap_candidate._build_predecessor_diff(
        predecessor_artifacts=source_artifacts,
        candidate_artifacts=candidate_artifacts,
        predecessor_bytes=source_bytes,
        candidate_artifacts_bytes=candidate.content.artifact_bytes,
        stages=STAGES,
    )
    if roadmap_candidate._wire_value(candidate.evidence.predecessor_diff) != roadmap_candidate._wire_value(expected):
        raise CandidateProposalError("candidate batch predecessor diff cannot be reproduced from stored bytes")


def _require_reproducible_batch_operations(
    candidate: StoredCandidateProposal, source: ResolvedRoadmapVersion
) -> None:
    """Replay stored batch operations against immutable source and capsule evidence."""
    evidence = candidate.evidence
    operations = evidence.normalized_operations
    route = evidence.operation_classification
    if operations is None and route is None:
        return  # Existing batch candidates and replacements predate route evidence.
    if operations is None or route is None or not isinstance(evidence.capsule, CandidateContextBatchCapsule):
        raise CandidateProposalError("candidate batch operation evidence is incomplete")
    parsed = roadmap_candidate._parse_predecessor_artifacts(source, STAGES)
    if isinstance(parsed, roadmap_candidate.CandidateRefusal):
        raise CandidateProposalError("candidate batch operations cannot be reproduced")
    predecessor_artifacts, predecessor_bytes = parsed
    # Corrections have no row target; _prepare_operations keeps its row-only contract.
    row_operations = tuple(
        operation
        for operation in operations
        if not isinstance(operation, roadmap_candidate.CandidateCorrectProse)
    )
    prepared = roadmap_candidate._prepare_operations(
        row_operations, predecessor_artifacts=predecessor_artifacts, stages=STAGES
    )
    if isinstance(prepared, roadmap_candidate.CandidateRefusal):
        raise CandidateProposalError("candidate batch operations cannot be reproduced")
    feedback_ids = tuple(item.item_id for item in evidence.capsule.reviewer_items)
    corrections = roadmap_candidate._resolve_corrections(
        tuple(
            operation
            for operation in operations
            if isinstance(operation, roadmap_candidate.CandidateCorrectProse)
        ),
        row_operations=prepared,
        predecessor_artifacts=predecessor_artifacts,
        capsule=evidence.capsule,
        feedback_ids=feedback_ids,
        stages=STAGES,
    )
    if isinstance(corrections, roadmap_candidate.CandidateRefusal):
        raise CandidateProposalError("candidate batch operations exceed stored reviewer authority")
    normalized = (*prepared, *(resolved.operation for resolved in corrections))
    if roadmap_candidate._wire_value(normalized) != roadmap_candidate._wire_value(operations):
        raise CandidateProposalError("candidate batch operations are not normalized")
    raw_authority = roadmap_candidate._full_member_authority(evidence.capsule)
    authority: dict[tuple[str, str, str], object] = {}
    for operation in prepared:
        if isinstance(operation, roadmap_candidate.CandidateAddRow):
            continue
        existing = roadmap_candidate._find_existing_row(
            predecessor_artifacts[operation.artifact_key], operation.row_type, operation.row_id
        )
        if isinstance(existing, roadmap_candidate.CandidateRefusal):
            raise CandidateProposalError("candidate batch operations exceed stored reviewer authority")
        key = (operation.artifact_key, type(existing).__name__, operation.row_id)
        raw = raw_authority.get(key)
        if raw is not None and roadmap_candidate._wire_value(raw) == roadmap_candidate._wire_value(existing):
            authority[key] = existing
    authority_failure = roadmap_candidate._validate_operation_authority(
        prepared,
        predecessor_artifacts=predecessor_artifacts,
        authority=authority,
        feedback_ids=feedback_ids,
    )
    if authority_failure is not None:
        raise CandidateProposalError("candidate batch operations exceed stored reviewer authority")
    try:
        replayed_artifacts = roadmap_candidate._apply_operations_in_contract_order(
            predecessor_artifacts, prepared, corrections
        )
        assembled = roadmap_candidate._assemble_candidate_artifacts(
            predecessor_artifacts=predecessor_artifacts,
            candidate_artifacts=replayed_artifacts,
            predecessor_bytes=predecessor_bytes,
            stages=STAGES,
            feedback_free=True,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise CandidateProposalError("candidate batch operations cannot be reproduced") from exc
    if (
        isinstance(assembled, roadmap_candidate.CandidateRefusal)
        or tuple(item.data for item in assembled) != candidate.content.artifact_bytes
        or roadmap_candidate._classify_validated_operations(
            normalized, predecessor_artifacts=predecessor_artifacts
        ) != route
    ):
        raise CandidateProposalError("candidate batch route does not match its stored operations")


def _render_batch_operation_shapes() -> str:
    """Render valid closed operation examples from the parser's key contracts."""
    contracts = (
        ("add-row", roadmap_candidate.ADD_ROW_REQUIRED_KEYS, roadmap_candidate.ADD_ROW_OPTIONAL_KEYS),
        ("replace-row", roadmap_candidate.REPLACE_ROW_REQUIRED_KEYS, roadmap_candidate.REPLACE_ROW_OPTIONAL_KEYS),
        ("remove-row", roadmap_candidate.REMOVE_ROW_REQUIRED_KEYS, roadmap_candidate.REMOVE_ROW_OPTIONAL_KEYS),
    )
    examples: list[str] = []
    for operation, required_keys, optional_keys in contracts:
        values: dict[str, object] = {
            "op": operation,
            "feedback_id": "issued-reviewer-item-id",
            "artifact_key": "domain",
            "row_type": "entities",
            "row_id": "entity-existing",
            "row": {
                "id": "entity-new" if operation == "add-row" else "entity-existing",
                "name": "Example entity",
                "fields": [],
            },
            "prose_amendment": {
                "row_id": "entity-new",
                "fragment": "Describe entity-new.",
            },
            "ordering": None,
        }
        keys = required_keys | optional_keys
        example = {key: values[key] for key in sorted(keys)}
        examples.append(f"### `{operation}`\n\n```json\n{_canonical_json_text(example)}\n```")
    return "\n\n".join(examples)


def _build_non_addable_collections_notice() -> str:
    """Shared verbatim between the batch and selector templates — one
    definition, not two copies to drift; too small to need its own file."""
    names = ", ".join(f"`{name}`" for name in roadmap_candidate.NON_ADDABLE_ROW_TYPES)
    return (
        f"`add-row` is prohibited for {names}. These collections\n"
        "cannot declare the required reached anchor for an addition. If feedback needs\n"
        "one changed, replace an authorized existing row, or omit the operation and\n"
        "explain the limitation in that reviewer's response. Do not invent an anchor."
    )


_NON_ADDABLE_COLLECTIONS_NOTICE: Final[str] = _build_non_addable_collections_notice()


def render_candidate_delta_prompt(
    *,
    capsule: CandidateContextCapsule,
    receipt: CandidateContextReceipt,
    review_pair: CandidateReviewPair | Mapping[str, object] | None = None,
    source: ResolvedRoadmapVersion | None = None,
    correction_reason: str | None = None,
) -> str:
    """Render the closed prompt using only issued immutable authority."""
    if not isinstance(capsule, CandidateContextCapsule) or receipt != capsule.receipt:
        raise CandidateProposalError("candidate prompt requires an issued capsule and its receipt")
    if review_pair is not None and not isinstance(review_pair, CandidateReviewPair):
        try:
            review_pair = CandidateReviewPair.model_validate(review_pair)
        except ValidationError as exc:
            raise CandidateProposalError("candidate review pair is malformed") from exc
    try:
        capsule_payload = capsule.payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CandidateProposalError("candidate capsule payload is not UTF-8") from exc
    is_batch = isinstance(capsule, CandidateContextBatchCapsule)
    # Each template asks for the response shape its own parser branch accepts.
    template_path = prompts_dir() / (
        "roadmap-candidate-delta.md" if is_batch else "roadmap-candidate-delta-selector.md"
    )

    def unreadable_template(exc: OSError | UnicodeDecodeError) -> CandidateProposalError:
        return CandidateProposalError(f"no candidate prompt template at {template_path} ({exc})")

    template = Template(read_roadmap_text(template_path, error_for_read_failure=unreadable_template))
    collection_hints = "null"
    operation_shapes = ""
    if is_batch:
        if source is None:
            raise CandidateProposalError("candidate batch prompt requires its immutable source")
        try:
            collection_hints = _canonical_json_text(candidate_collection_hints(capsule, source))
        except ValueError as exc:
            raise CandidateProposalError(str(exc)) from exc
        operation_shapes = _render_batch_operation_shapes()
    if correction_reason is not None and not is_batch:
        raise CandidateProposalError("candidate correction requires a ledger batch")
    try:
        prompt = template.substitute(
            capsule_payload=capsule_payload,
            capsule_receipt=_canonical_json_text(_wire_value(receipt)),
            collection_hints=collection_hints,
            operation_shapes=operation_shapes,
            non_addable_collections_notice=_NON_ADDABLE_COLLECTIONS_NOTICE,
            feedback_id=(capsule.feedback.feedback_id if capsule.feedback is not None else "reviewer-batch"),
            review_pair=(
                "null" if review_pair is None else _canonical_json_text(_wire_value(review_pair))
            ),
        )
    except (KeyError, ValueError) as exc:
        raise CandidateProposalError("candidate delta prompt has unresolved variables") from exc
    if correction_reason is not None:
        prompt += (
            "\nCorrection for the preceding rejected reply: "
            + _canonical_json_text(correction_reason)
            + "\nReturn one complete replacement JSON object under the same issued batch and receipt, "
            "including the required row-owned prose amendment for every eligible add-row.\n"
        )
    return prompt


def parse_candidate_proposal_response(
    response_text: str,
    *,
    capsule: CandidateContextCapsule,
    allow_expansion: bool,
) -> CandidateDelta | CandidateExpansionRequest:
    """Parse one strict delta or, only initially, one exact inventory expansion request."""
    if isinstance(capsule, CandidateContextBatchCapsule):
        # The batch prompt defines one unwrapped delta shape and no expansion, for
        # the initial proposal and the review replacement alike.
        try:
            return parse_candidate_delta(response_text)
        except CandidateDeltaError as exc:
            raise CandidateProposalResponseError(f"candidate response delta is invalid: {exc}") from exc
    payload = _decode_single_json_object(response_text)
    if set(payload) == {"delta"}:
        delta_value = payload["delta"]
        if not isinstance(delta_value, dict):
            raise CandidateProposalResponseError("candidate response delta must be an object")
        try:
            return parse_candidate_delta(_canonical_json_text(delta_value))
        except CandidateDeltaError as exc:
            raise CandidateProposalResponseError(f"candidate response delta is invalid: {exc}") from exc
    if set(payload) != {"expand"}:
        raise CandidateProposalResponseError("candidate response requires exactly one disposition")
    if not allow_expansion:
        raise CandidateProposalResponseError("candidate response cannot request a second expansion")
    entry_value = payload["expand"]
    if not isinstance(entry_value, dict) or set(entry_value) != {
        "artifact_key",
        "row_type",
        "row_id",
        "label",
        "digest",
    }:
        raise CandidateProposalResponseError("candidate expansion must name one exact inventory entry")
    try:
        entry = CandidateContextInventoryEntry.model_validate(entry_value)
    except ValidationError as exc:
        raise CandidateProposalResponseError("candidate expansion entry is malformed") from exc
    if entry not in capsule.inventory:
        raise CandidateProposalResponseError("candidate expansion entry is not in the issued inventory")
    return CandidateExpansionRequest(entry=entry)


def run_initial_candidate_proposal(
    slug: str,
    feedback_selector: str | None,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: CandidateProposalInvoker | None = None,
    run_logger: RunLogWriter | None = None,
) -> CandidateProposalResult:
    """Store one valid inert candidate from one delta or one expansion then delta."""
    logger = run_logger or RunLogWriter.start(
        repo_root=repo_root,
        slug=slug,
        command="roadmap",
        argv=["plan-tool", "roadmap", slug, "--propose-candidate", *([] if feedback_selector is None else [feedback_selector])],
        flags={"mode": "candidate-proposal"},
    )
    invoke = invoker or shell_candidate_proposal_invoker
    result: CandidateProposalResult | None = None
    call_count = 0
    expansion_used = False
    last_response: CandidateModelInvocation | None = None
    response_accepted = False
    terminal_response_recorded = False
    started_at = time.monotonic()
    logger.phase_start(CANDIDATE_PROPOSAL_PHASE)

    try:
        # Enrolled roadmaps have a reviewer ledger.  Its batch contract is
        # distinct from the legacy selector path retained below for old data.
        if roadmap_feedback_ledger_path(plans_dir, slug).exists():
            batch_attempt = _ProposalAttempt()
            try:
                with roadmap_writer_guard(plans_dir, slug) as writer_token:
                    result = _run_batch_candidate_proposal(
                        slug=slug,
                        plans_dir=plans_dir,
                        writer_token=writer_token,
                        invoke=invoke,
                        logger=logger,
                        diagnostics=batch_attempt,
                    )
                    return result
            finally:
                # Also runs when the model call raises, so the failure keeps its call count.
                call_count = batch_attempt.call_count
                last_response = batch_attempt.last_response
                response_accepted = batch_attempt.response_accepted
                terminal_response_recorded = batch_attempt.terminal_response_recorded
        with roadmap_writer_guard(plans_dir, slug) as writer_token:
            admission = load_candidate_admission(plans_dir=plans_dir, slug=slug)
            if admission is None:
                predecessor = load_accepted_version(plans_dir=plans_dir, slug=slug)
                if predecessor is None:
                    result = _result("refused", "roadmap has no accepted immutable predecessor", call_count)
                    return result
                context = build_candidate_context(predecessor, feedback_selector)
                if context.capsule is None:
                    result = _result(
                        "refused",
                        context.refusal.detail if context.refusal is not None else "candidate context refused",
                        call_count,
                    )
                    return result
                admission = CandidateProposalAdmission(
                    schema_version=_SCHEMA_VERSION,
                    roadmap_slug=slug,
                    predecessor_version_id=predecessor.record.version_id,
                    feedback=context.capsule.feedback,
                    capsule=context.capsule,
                    receipt=context.capsule.receipt,
                    expansion_available=True,
                )
                try:
                    _create_admission(plans_dir=plans_dir, slug=slug, admission=admission)
                except (OSError, CandidateProposalError) as exc:
                    result = _result("failed", str(exc), call_count)
                    return result
            else:
                if feedback_selector != _feedback_selector(admission.feedback):
                    result = _result("refused", "roadmap admission already binds different feedback", call_count)
                    return result

            if admission.candidate_version_id is not None:
                try:
                    candidate = load_stored_candidate_proposal(
                        plans_dir=plans_dir,
                        slug=slug,
                        candidate_version_id=admission.candidate_version_id,
                    )
                except CandidateProposalError as exc:
                    result = _result("failed", str(exc), call_count)
                    return result
                result = CandidateProposalResult("stored", candidate=candidate, call_count=call_count)
                return result

            try:
                predecessor = _load_resolved_version(
                    plans_dir=plans_dir, slug=slug, version_id=admission.predecessor_version_id
                )
                capsule = _hydrate_capsule(admission.capsule)
            except CandidateProposalError as exc:
                result = _result("refused", str(exc), call_count)
                return result

            if admission.expansion_available:
                call_count += 1
                invocation = _invoke_once(
                    invoke=invoke,
                    logger=logger,
                    capsule=capsule,
                    receipt=admission.receipt,
                    attempt=1,
                    review_pair=None,
                )
                last_response = invocation
                if invocation.rc != 0:
                    result = _result("failed", "candidate proposal backend request failed", call_count)
                    return result
                response = invocation.response
                try:
                    disposition = parse_candidate_proposal_response(
                        response, capsule=capsule, allow_expansion=True
                    )
                except CandidateProposalResponseError as exc:
                    result = _result("response-rejected", str(exc), call_count)
                    return result
                if isinstance(disposition, CandidateExpansionRequest):
                    expanded = expand_candidate_context(predecessor, capsule, disposition.entry)
                    if expanded.capsule is None:
                        result = _result(
                            "response-rejected",
                            expanded.refusal.detail
                            if expanded.refusal is not None
                            else "candidate expansion refused",
                            call_count,
                        )
                        return result
                    # The expansion request itself is a valid, accepted response from here on —
                    # a later storage failure must not mislabel it as a rejected response.
                    response_accepted = True
                    capsule = expanded.capsule
                    admission = admission.model_copy(
                        update={
                            "capsule": capsule,
                            "receipt": capsule.receipt,
                            "expansion_available": False,
                        }
                    )
                    try:
                        _replace_admission(plans_dir=plans_dir, slug=slug, admission=admission)
                    except OSError as exc:
                        result = _result("failed", str(exc), call_count)
                        return result
                    expansion_used = True
                    call_count += 1
                    invocation = _invoke_once(
                        invoke=invoke,
                        logger=logger,
                        capsule=capsule,
                        receipt=admission.receipt,
                        attempt=2,
                        review_pair=None,
                    )
                    last_response = invocation
                    response_accepted = False
                    if invocation.rc != 0:
                        result = _result("failed", "candidate proposal backend request failed", call_count)
                        return result
                    response = invocation.response
                    try:
                        disposition = parse_candidate_proposal_response(
                            response, capsule=capsule, allow_expansion=False
                        )
                    except CandidateProposalResponseError as exc:
                        result = _result("response-rejected", str(exc), call_count)
                        return result
                if isinstance(disposition, CandidateExpansionRequest):
                    result = _result("response-rejected", "candidate response has no delta", call_count)
                    return result
                delta = disposition
            else:
                call_count += 1
                invocation = _invoke_once(
                    invoke=invoke,
                    logger=logger,
                    capsule=capsule,
                    receipt=admission.receipt,
                    attempt=1,
                    review_pair=None,
                )
                last_response = invocation
                if invocation.rc != 0:
                    result = _result("failed", "candidate proposal backend request failed", call_count)
                    return result
                response = invocation.response
                try:
                    delta_response = parse_candidate_proposal_response(
                        response, capsule=capsule, allow_expansion=False
                    )
                except CandidateProposalResponseError as exc:
                    result = _result("response-rejected", str(exc), call_count)
                    return result
                if isinstance(delta_response, CandidateExpansionRequest):
                    result = _result("response-rejected", "candidate response has no delta", call_count)
                    return result
                delta = delta_response

            materialized = materialize_candidate(
                delta,
                predecessor=predecessor,
                capsule=capsule,
                receipt=admission.receipt,
            )
            if materialized.candidate is not None:
                stored_materialization: GateCleanCandidate | ReviewRequiredCandidate = (
                    materialized.candidate
                )
            elif materialized.review_required is not None:
                stored_materialization = materialized.review_required
            else:
                result = _result(
                    "response-rejected",
                    materialized.refusal.detail
                    if materialized.refusal is not None
                    else "candidate materialization refused",
                    call_count,
                )
                return result
            # Materialization succeeded: the response is accepted, so a later storage
            # failure must not mislabel it as a rejected response.
            response_accepted = True
            try:
                candidate = _store_candidate(
                    plans_dir=plans_dir,
                    slug=slug,
                    writer_token=writer_token,
                    admission=admission,
                    predecessor=predecessor,
                    materialized=stored_materialization,
                )
            except (OSError, ValueError, CandidateProposalError, RoadmapVersionError) as exc:
                result = _result("failed", str(exc), call_count)
                return result
            result = CandidateProposalResult("stored", candidate=candidate, call_count=call_count)
            return result
    except KeyboardInterrupt:
        # A second KeyboardInterrupt landing mid-call must not stop `result`
        # from being set to "interrupted" below.
        with contextlib.suppress(KeyboardInterrupt):
            logger.run_interrupted(
                phase=CANDIDATE_PROPOSAL_PHASE,
                attempt=max(call_count, 1),
                source="candidate-proposal",
            )
        result = _result("interrupted", "candidate proposal interrupted", call_count)
        return result
    except (OSError, RoadmapVersionError, RoadmapWriterGuardError, CandidateProposalError) as exc:
        result = _result("failed", str(exc), call_count)
        return result
    finally:
        terminal = result or _result("failed", "candidate proposal did not finish", call_count)
        failure_extras: dict[str, object] = {}
        if terminal.outcome != "stored":
            with contextlib.suppress(KeyboardInterrupt):
                failure_extras = candidate_failure_diagnostic_extras(
                    attempt=last_response.attempt if last_response is not None else None,
                    call_count=terminal.call_count,
                    failure_detail=terminal.detail or "candidate proposal failed without a detail",
                    response_text=(
                        last_response.response
                        if last_response is not None and not response_accepted and not terminal_response_recorded
                        else None
                    ),
                )
        # A second KeyboardInterrupt landing anywhere in this call — including
        # its own setup, before either of its internal guards is reached —
        # must not stop the terminal-record calls below from being attempted.
        with contextlib.suppress(KeyboardInterrupt):
            failure_extras = (
                record_candidate_failure_diagnostics(
                    logger=logger,
                    phase=CANDIDATE_PROPOSAL_PHASE,
                    attempt=last_response.attempt if last_response is not None else None,
                    outcome=terminal.outcome,
                    call_count=terminal.call_count,
                    failure_detail=terminal.detail or "candidate proposal failed without a detail",
                    response_text=(
                        last_response.response
                        if last_response is not None and not response_accepted and not terminal_response_recorded
                        else None
                    ),
                )
                if terminal.outcome != "stored"
                else {}
            )
        with contextlib.suppress(KeyboardInterrupt):
            logger.phase_end(
                CANDIDATE_PROPOSAL_PHASE,
                int((time.monotonic() - started_at) * 1000),
                terminal.outcome,
                call_count=call_count,
                expansion_used=expansion_used,
                **failure_extras,
            )
        with contextlib.suppress(KeyboardInterrupt):
            logger.run_end(
                outcome=terminal.outcome,
                rc=_result_return_code(terminal.outcome),
                termination_reason=("operator_interrupt" if terminal.outcome == "interrupted" else None),
            )


def _invoke_once(
    *,
    invoke: CandidateProposalInvoker,
    logger: RunLogWriter,
    capsule: CandidateContextCapsule,
    receipt: CandidateContextReceipt,
    attempt: int,
    review_pair: CandidateReviewPair | Mapping[str, object] | None,
    source: ResolvedRoadmapVersion | None = None,
    correction_reason: str | None = None,
) -> CandidateModelInvocation:
    prompt = render_candidate_delta_prompt(
        capsule=capsule, receipt=receipt, review_pair=review_pair, source=source,
        correction_reason=correction_reason,
    )
    logger.claude_call_start(
        CANDIDATE_PROPOSAL_PHASE,
        attempt,
        len(prompt.encode("utf-8")),
        prompt_sha256=hash_prompt(prompt),
    )
    with logger.bind_shell_sink(phase=CANDIDATE_PROPOSAL_PHASE, attempt=attempt):
        rc, response = invoke(prompt)
    if rc != 0:
        logger.attempt_failed(
            phase=CANDIDATE_PROPOSAL_PHASE,
            attempt=attempt,
            failure_kind="transport",
        )
    return CandidateModelInvocation(attempt=attempt, rc=rc, response=response)


def _run_batch_candidate_proposal(
    *, slug: str, plans_dir: Path, writer_token: object, invoke: CandidateProposalInvoker,
    logger: RunLogWriter, diagnostics: _ProposalAttempt,
) -> CandidateProposalResult:
    """Run one fresh ledger batch; only its exact receipt qualifies for reentry."""
    ledger_path = roadmap_feedback_ledger_path(plans_dir, slug)
    try:
        ledger = load_ledger(ledger_path)
    except RoadmapFeedbackLedgerError as exc:
        return _result("refused", str(exc), 0)
    admission = load_candidate_admission(plans_dir=plans_dir, slug=slug)
    root = load_accepted_version(plans_dir=plans_dir, slug=slug)
    if root is None:
        return _result("refused", "roadmap has no accepted immutable predecessor", 0)
    # A batch pointer would replace a selector-era candidate still awaiting promotion,
    # orphaning its review lineage. Once promoted the head has moved past it.
    if (
        admission is not None
        and admission.root_version_id is None
        and admission.candidate_version_id is not None
        and admission.predecessor_version_id == root.record.version_id
    ):
        return _result("refused", "unpromoted-candidate-lineage", 0)
    active: StoredCandidateProposal | None = None
    source_ancestry: tuple[str, ...] | None = None
    # A released pointer names no candidate, so its root may predate a promotion.
    if admission is not None and admission.active_candidate_version_id is not None:
        if admission.root_version_id != root.record.version_id:
            return _result("refused", "candidate processing pair changed", 0)
        try:
            active = load_stored_candidate_proposal(
                plans_dir=plans_dir, slug=slug,
                candidate_version_id=admission.active_candidate_version_id,
            )
            if active.evidence.root_version_id != root.record.version_id:
                return _result("refused", "candidate processing pair changed", 0)
            source_ancestry = source_ancestry_to_root(
                plans_dir=plans_dir, slug=slug,
                source_version_id=active.version_id, root_version_id=root.record.version_id,
            )
        except CandidateProposalError as exc:
            return _result("failed", str(exc), 0)
    source = _load_resolved_version(
        plans_dir=plans_dir, slug=slug,
        version_id=active.version_id if active is not None else root.record.version_id,
    )
    context = build_candidate_context(
        root, source if active is not None else None, ledger, source_ancestry=source_ancestry
    )
    if context.no_work is not None:
        return _result("refused", "candidate batch has no eligible work", 0)
    if context.refusal is not None or not isinstance(context.capsule, CandidateContextBatchCapsule):
        return _result("refused", context.refusal.detail if context.refusal else "candidate batch refused", 0)
    capsule = context.capsule
    if active is not None and active.evidence.batch_receipt == capsule.receipt:
        return CandidateProposalResult("stored", candidate=active, call_count=0)
    correction_reason: str | None = None
    for attempt in (1, 2):
        diagnostics.call_count = attempt
        invocation = _invoke_once(
            invoke=invoke, logger=logger, capsule=capsule, receipt=capsule.receipt,
            attempt=attempt, review_pair=None, source=source, correction_reason=correction_reason,
        )
        diagnostics.last_response = invocation
        diagnostics.terminal_response_recorded = False
        if invocation.rc != 0:
            return _result("failed", "candidate proposal backend request failed", attempt)
        try:
            delta = parse_candidate_delta(invocation.response)
        except CandidateDeltaError as exc:
            rejection = str(exc)
        else:
            materialized = materialize_candidate(
                delta, predecessor=source, capsule=capsule, receipt=capsule.receipt
            )
            if materialized.batch_candidate is not None:
                break
            rejection = materialized.refusal.detail if materialized.refusal else "candidate materialization refused"
        record_candidate_failure_diagnostics(
            logger=logger, phase=CANDIDATE_PROPOSAL_PHASE, attempt=attempt,
            outcome="response-rejected", call_count=attempt,
            failure_detail=rejection, response_text=invocation.response,
        )
        diagnostics.terminal_response_recorded = True
        if attempt == 2:
            return _result("response-rejected", rejection, attempt)
        correction_reason = rejection
    # A storage failure past this point must not be recorded as a rejected response.
    diagnostics.response_accepted = True
    try:
        candidate = _store_batch_candidate(
            plans_dir=plans_dir, slug=slug, writer_token=writer_token, root=root,
            source=source, ledger=ledger, admission=admission, capsule=capsule,
            materialized=materialized.batch_candidate,
        )
    except CandidateStorageRefusal as exc:
        return _result("refused", str(exc), diagnostics.call_count)
    except (CandidateProposalError, OSError, RoadmapVersionError, RoadmapFeedbackLedgerError) as exc:
        return _result("failed", str(exc), diagnostics.call_count)
    return CandidateProposalResult("stored", candidate=candidate, call_count=diagnostics.call_count)


def _store_batch_candidate(
    *, plans_dir: Path, slug: str, writer_token: object, root: ResolvedRoadmapVersion,
    source: ResolvedRoadmapVersion, ledger: RoadmapFeedbackLedger,
    admission: CandidateProposalAdmission | None, capsule: CandidateContextBatchCapsule,
    materialized: roadmap_candidate.BatchGateCleanCandidate,
) -> StoredCandidateProposal:
    """Publish immutable bytes, pointer and mutable batch effects as one generation."""
    # Re-read only mutable state that can invalidate this exact batch.
    current_ledger = load_ledger(roadmap_feedback_ledger_path(plans_dir, slug))
    current = load_candidate_admission(plans_dir=plans_dir, slug=slug)
    if current != admission:
        raise CandidateStorageRefusal("candidate processing pair changed before storage")
    content = RoadmapVersionContent(source.brief_bytes, tuple(item.data for item in materialized.artifacts))
    record = create_candidate_version(
        roadmap_slug=slug, predecessor_version_id=source.record.version_id,
        content_identity=materialized.content_identity, review_lineage_identity=INITIAL_EMPTY_REVIEW_LINEAGE_ID,
        brief_digest=_digest(content.brief_bytes), artifact_digests=sha256_digests(content.artifact_bytes),
    )
    updated_ledger = _apply_batch_ledger_patch(
        current_ledger, materialized, capsule, candidate_version_id=record.version_id
    )
    evidence = CandidateProposalEvidence(
        schema_version=_SCHEMA_VERSION, roadmap_slug=slug, candidate_version_id=record.version_id,
        predecessor_version_id=source.record.version_id, review_lineage_identity=INITIAL_EMPTY_REVIEW_LINEAGE_ID,
        feedback=None, raw_brief_digest=_digest(content.brief_bytes), artifact_digests=sha256_digests(content.artifact_bytes),
        content_identity=materialized.content_identity, predecessor_diff=materialized.predecessor_diff,
        gate_evidence=tuple(CandidateGateEvidence(artifact_key=x.stage.artifact_key, violations=()) for x in materialized.gate_outcomes),
        capsule=capsule, receipt=capsule.receipt, expansion_available=False,
        root_version_id=root.record.version_id, source_version_id=source.record.version_id,
        batch_receipt=capsule.receipt,
        normalized_operations=materialized.normalized_operations,
        operation_classification=materialized.operation_classification,
    )
    candidate = StoredCandidateProposal(record, content, evidence)
    _validate_candidate_evidence(candidate, plans_dir=plans_dir, slug=slug)
    namespace_root = version_namespace_path(plans_dir, slug).parent
    candidate_dir = version_directory_path(plans_dir, slug, record.version_id)
    members: list[GenerationMember] = []
    for member in stored_version_members(PreparedRoadmapVersion(record, content)):
        path = candidate_dir / member.member_name
        if path.exists() or path.is_symlink():
            raise CandidateStorageRefusal("candidate version identity collides with existing storage")
        members.append(GenerationMember(path.relative_to(namespace_root).as_posix(), None, member.data))
    evidence_path = candidate_evidence_path(plans_dir, slug, record.version_id)
    if evidence_path.exists() or evidence_path.is_symlink():
        raise CandidateStorageRefusal("candidate evidence identity collides with existing storage")
    members.append(GenerationMember(evidence_path.relative_to(namespace_root).as_posix(), None, render_candidate_evidence(evidence)))
    if admission is not None and admission.active_candidate_version_id is not None:
        members.append(
            build_supersession_member(
                plans_dir=plans_dir, slug=slug, admission=admission,
                successor_version_id=record.version_id,
            )
        )
    members.append(build_active_candidate_pointer_member(
        plans_dir=plans_dir, slug=slug, previous=admission,
        root_version_id=root.record.version_id, candidate_version_id=record.version_id,
    ))
    ledger_path = roadmap_feedback_ledger_path(plans_dir, slug)
    ledger_bytes = render_ledger(current_ledger)
    members.append(GenerationMember(ledger_path.relative_to(namespace_root).as_posix(), ledger_bytes, render_ledger(updated_ledger)))
    publish_roadmap_generation(
        PendingGeneration(kind="candidate-proposal", members=tuple(members)),
        plans_dir=plans_dir, slug=slug, writer_token=cast(Any, writer_token),
        before_replace=lambda: require_batch_state_unchanged(
            plans_dir=plans_dir, slug=slug, admission=admission, ledger_bytes=ledger_bytes
        ),
    )
    refresh_roadmap_index(plans_dir, slug)
    return candidate


def build_active_candidate_pointer_member(
    *,
    plans_dir: Path,
    slug: str,
    previous: CandidateProposalAdmission | None,
    root_version_id: str,
    candidate_version_id: str,
) -> GenerationMember:
    """Point the root's one active-candidate pointer at ``candidate_version_id``."""
    visible = CandidateProposalAdmission(
        schema_version=_SCHEMA_VERSION, roadmap_slug=slug, predecessor_version_id=root_version_id,
        expansion_available=False, root_version_id=root_version_id,
        candidate_version_id=candidate_version_id, active_candidate_version_id=candidate_version_id,
    )
    path = candidate_admission_path(plans_dir, slug)
    namespace_root = version_namespace_path(plans_dir, slug).parent
    return GenerationMember(
        path.relative_to(namespace_root).as_posix(),
        None if previous is None else render_candidate_admission(previous),
        render_candidate_admission(visible),
    )


def require_batch_state_unchanged(
    *, plans_dir: Path, slug: str, admission: CandidateProposalAdmission | None, ledger_bytes: bytes
) -> None:
    """Refuse, inside the publication window, if the pointer or ledger moved since they were read.

    ``publish_roadmap_generation`` overwrites members without comparing their recorded
    old bytes, so this is what keeps a generation from replacing a newer reviewer edit.
    """
    if load_candidate_admission(plans_dir=plans_dir, slug=slug) != admission:
        raise CandidateStorageRefusal("candidate processing pair changed before storage")
    try:
        current = roadmap_feedback_ledger_path(plans_dir, slug).read_bytes()
    except OSError as exc:
        raise CandidateStorageRefusal("feedback ledger is unreadable before storage") from exc
    if current != ledger_bytes:
        raise CandidateStorageRefusal("feedback ledger changed before storage")


def apply_replacement_ledger_patch(
    ledger: RoadmapFeedbackLedger,
    *,
    reviewed_candidate_version_id: str,
    replacement_version_id: str,
    response_patch: roadmap_candidate.CandidateResponsePatch,
    derived_feedback: tuple[roadmap_candidate.CandidateDerivedFeedback, ...],
) -> RoadmapFeedbackLedger:
    """Carry a sealed replacement's responses and derived set into the ledger.

    Only an item still ``awaiting-review`` on the reviewed candidate's proposal, whose
    reviewer-owned fields are unchanged since admission, takes the replacement's
    response and binding. An item the reviewer has since reopened, edited, closed or
    deferred is left exactly as they left it.
    """
    entries = {entry.item.item_id: entry for entry in response_patch.entries}
    groups: list[ReviewerFeedbackGroup] = []
    for group in ledger.reviewer_feedback_groups:
        items: list[ReviewerFeedbackItem] = []
        for item in group.items:
            entry = entries.get(item.item_id)
            if (
                entry is not None
                and item.state is ReviewerItemState.AWAITING_REVIEW
                and item.proposal is not None
                and item.proposal.candidate_version_id == reviewed_candidate_version_id
                and (item.request, item.target, item.submitted_against_version_id, item.target_fingerprint)
                == (entry.item.request, entry.item.target, entry.item.submitted_against_version_id, entry.item.target_fingerprint)
            ):
                item = item.model_copy(update={"proposal": ProposalFields(
                    response=entry.response, candidate_version_id=replacement_version_id
                )})
            items.append(item)
        groups.append(group.model_copy(update={"items": tuple(items)}))
    derived = (
        *ledger.derived_context,
        *(
            DerivedFeedbackContext(
                source_version_id=replacement_version_id, context_id=entry.context_id, content=entry.content
            )
            for entry in derived_feedback
        ),
    )
    return ledger.model_copy(update={"reviewer_feedback_groups": tuple(groups), "derived_context": derived})


def _apply_batch_ledger_patch(
    ledger: RoadmapFeedbackLedger, materialized: roadmap_candidate.BatchGateCleanCandidate,
    capsule: CandidateContextBatchCapsule, *, candidate_version_id: str,
) -> RoadmapFeedbackLedger:
    """Apply only exact admitted snapshots, leaving unrelated reviewer edits intact."""
    responses = {entry.item.item_id: entry for entry in materialized.response_patch.entries}
    found: set[str] = set()
    groups: list[ReviewerFeedbackGroup] = []
    for group in ledger.reviewer_feedback_groups:
        items: list[ReviewerFeedbackItem] = []
        for item in group.items:
            entry = responses.get(item.item_id)
            if entry is not None:
                if item_snapshot(item) != entry.item:
                    raise CandidateStorageRefusal("admitted reviewer item changed before storage")
                found.add(item.item_id)
                items.append(item.model_copy(update={"state": ReviewerItemState.AWAITING_REVIEW, "proposal": ProposalFields(response=entry.response, candidate_version_id=candidate_version_id)}))
            else:
                items.append(item)
        groups.append(group.model_copy(update={"items": tuple(items)}))
    if found != set(responses) or tuple(entry.item for entry in materialized.response_patch.entries) != capsule.reviewer_items:
        raise CandidateStorageRefusal("admitted reviewer item changed before storage")
    derived = (*ledger.derived_context, *(DerivedFeedbackContext(source_version_id=candidate_version_id, context_id=x.context_id, content=x.content) for x in materialized.derived_feedback))
    return ledger.model_copy(update={"reviewer_feedback_groups": tuple(groups), "derived_context": derived})


def _result_return_code(outcome: CandidateProposalOutcome) -> int:
    """Map one closed proposal outcome to its command exit code."""
    return {
        "stored": 0,
        "response-rejected": 1,
        "failed": 1,
        "refused": 2,
        "interrupted": 130,
    }[outcome]


def _create_admission(
    *, plans_dir: Path, slug: str, admission: CandidateProposalAdmission
) -> None:
    path = candidate_admission_path(plans_dir, slug)
    if path.exists() or path.is_symlink():
        raise CandidateProposalError("candidate proposal admission already exists")
    durable_write_bytes(path, render_candidate_admission(admission))


def _replace_admission(
    *, plans_dir: Path, slug: str, admission: CandidateProposalAdmission
) -> None:
    durable_write_bytes(candidate_admission_path(plans_dir, slug), render_candidate_admission(admission))


def _store_candidate(
    *,
    plans_dir: Path,
    slug: str,
    writer_token: object,
    admission: CandidateProposalAdmission,
    predecessor: ResolvedRoadmapVersion,
    materialized: GateCleanCandidate | ReviewRequiredCandidate,
) -> StoredCandidateProposal:
    if isinstance(materialized, GateCleanCandidate):
        review_requirement = None
    elif isinstance(materialized, ReviewRequiredCandidate):
        review_requirement = materialized.review_requirement
    else:
        raise CandidateProposalError("candidate storage requires a materialized candidate")
    if (
        materialized.predecessor_version_id != admission.predecessor_version_id
        or materialized.selected_feedback != admission.feedback
        or materialized.capsule_receipt != admission.receipt
        or len(materialized.gate_outcomes) != len(STAGES)
        or any(
            outcome.stage is not stage
            for outcome, stage in zip(materialized.gate_outcomes, STAGES, strict=True)
        )
        or any(outcome.violations for outcome in materialized.gate_outcomes)
    ):
        raise CandidateProposalError("candidate materialization does not match the fixed admission")
    content = RoadmapVersionContent(
        brief_bytes=predecessor.brief_bytes,
        artifact_bytes=tuple(member.data for member in materialized.artifacts),
    )
    record = create_candidate_version(
        roadmap_slug=slug,
        predecessor_version_id=predecessor.record.version_id,
        content_identity=materialized.content_identity,
        review_lineage_identity=INITIAL_EMPTY_REVIEW_LINEAGE_ID,
        brief_digest=_digest(content.brief_bytes),
        artifact_digests=sha256_digests(content.artifact_bytes),
    )
    prepared = PreparedRoadmapVersion(record=record, content=content)
    evidence = CandidateProposalEvidence(
        schema_version=_SCHEMA_VERSION,
        roadmap_slug=slug,
        candidate_version_id=record.version_id,
        predecessor_version_id=predecessor.record.version_id,
        review_lineage_identity=INITIAL_EMPTY_REVIEW_LINEAGE_ID,
        feedback=admission.feedback,
        raw_brief_digest=_digest(content.brief_bytes),
        artifact_digests=sha256_digests(content.artifact_bytes),
        content_identity=materialized.content_identity,
        predecessor_diff=materialized.predecessor_diff,
        gate_evidence=tuple(
            CandidateGateEvidence(
                artifact_key=outcome.stage.artifact_key,
                violations=tuple(violation.message for violation in outcome.violations),
            )
            for outcome in materialized.gate_outcomes
        ),
        capsule=admission.capsule,
        receipt=admission.receipt,
        expansion_available=admission.expansion_available,
        review_requirement=review_requirement,
    )
    candidate = StoredCandidateProposal(record=record, content=content, evidence=evidence)
    _validate_candidate_evidence(candidate, plans_dir=plans_dir, slug=slug)
    candidate_dir = version_directory_path(plans_dir, slug, record.version_id)
    root = version_namespace_path(plans_dir, slug).parent
    admission_path = candidate_admission_path(plans_dir, slug)
    admission_old = admission_path.read_bytes()
    if admission_old != render_candidate_admission(admission):
        raise CandidateProposalError("candidate proposal admission changed before storage")
    members: list[GenerationMember] = []
    for member in stored_version_members(prepared):
        path = candidate_dir / member.member_name
        if path.exists() or path.is_symlink():
            raise CandidateProposalError("candidate version identity collides with existing storage")
        members.append(GenerationMember(path.relative_to(root).as_posix(), None, member.data))
    evidence_path = candidate_evidence_path(plans_dir, slug, record.version_id)
    if evidence_path.exists() or evidence_path.is_symlink():
        raise CandidateProposalError("candidate evidence identity collides with existing storage")
    members.append(
        GenerationMember(
            evidence_path.relative_to(root).as_posix(),
            None,
            render_candidate_evidence(evidence),
        )
    )
    visible_admission = admission.model_copy(update={"candidate_version_id": record.version_id})
    members.append(
        GenerationMember(
            admission_path.relative_to(root).as_posix(),
            admission_old,
            render_candidate_admission(visible_admission),
        )
    )
    publish_roadmap_generation(
        PendingGeneration(kind="candidate-proposal", members=tuple(members)),
        plans_dir=plans_dir,
        slug=slug,
        writer_token=cast(Any, writer_token),
    )
    refresh_roadmap_index(plans_dir, slug)
    return StoredCandidateProposal(
        record=record,
        content=content,
        evidence=parse_candidate_evidence(render_candidate_evidence(evidence)),
    )


def _load_resolved_version(*, plans_dir: Path, slug: str, version_id: str) -> ResolvedRoadmapVersion:
    try:
        record = load_stored_version(plans_dir=plans_dir, slug=slug, version_id=version_id)
    except RoadmapVersionError as exc:
        raise CandidateProposalError("admitted predecessor version is unreadable") from exc
    brief_bytes = _read_member(
        stored_brief_path(plans_dir, slug, version_id),
        expected_digest=record.brief_digest,
        description="admitted predecessor brief",
    )
    artifacts = tuple(
        _read_member(
            stored_artifact_path(plans_dir, slug, version_id, member.artifact_key),
            expected_digest=member.digest,
            description=f"admitted predecessor artifact {member.artifact_key}",
        )
        for member in record.artifact_members
    )
    return ResolvedRoadmapVersion(record=record, brief_bytes=brief_bytes, artifact_bytes=artifacts)


def _read_member(path: Path, *, expected_digest: str, description: str) -> bytes:
    try:
        data = path.read_bytes()
        data.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CandidateProposalError(f"{description} is unreadable") from exc
    if _digest(data) != expected_digest:
        raise CandidateProposalError(f"{description} does not match its recorded digest")
    return data


def _capsule_and_receipt_are_exact(
    capsule: CandidateContextCapsule, receipt: CandidateContextReceipt
) -> bool:
    """Verify stored model authority without reading a live roadmap or recompiling context."""
    payload = _canonical_json_bytes(
        {
            "schema_version": 1,
            "predecessor": _wire_value(capsule.predecessor),
            "brief": capsule.brief,
            "feedback": _wire_value(capsule.feedback),
            "full_members": [
                {
                    "identity": _wire_value(member.identity),
                    "row": _wire_value(member.row),
                    "row_digest": member.row_digest,
                    "source_spans": _wire_value(member.source_spans),
                    "inclusion_reasons": list(member.inclusion_reasons),
                }
                for member in capsule.full_members
            ],
            "relation_evidence": _wire_value(capsule.relation_evidence),
            "inventory": _wire_value(capsule.inventory),
            "ceiling_bytes": capsule.ceiling_bytes,
            "expansion": _wire_value(capsule.expansion),
        }
    )
    expected_receipt = {
        "schema_version": 1,
        "predecessor": _wire_value(capsule.predecessor),
        "feedback": _wire_value(capsule.feedback),
        "full_members": [
            {
                "identity": _wire_value(member.identity),
                "row_digest": member.row_digest,
                "inclusion_reasons": list(member.inclusion_reasons),
                "source_spans": [
                    {
                        "row_id": span.row_id,
                        "span_id": span.span_id,
                        "digest": span.digest,
                        # Absent on single-owner and legacy spans, as in the issued receipt.
                        **(
                            {"owning_row_ids": list(span.owning_row_ids)}
                            if span.owning_row_ids is not None
                            else {}
                        ),
                    }
                    for span in member.source_spans
                ],
            }
            for member in capsule.full_members
        ],
        "relation_evidence": _wire_value(capsule.relation_evidence),
        "inventory": _wire_value(capsule.inventory),
        "ceiling_bytes": capsule.ceiling_bytes,
        "payload_bytes": len(capsule.payload),
        "payload_digest": _digest(capsule.payload),
        "capsule_identity": _digest(capsule.payload),
        "expansion": _wire_value(capsule.expansion),
    }
    return payload == capsule.payload and _wire_value(receipt) == expected_receipt


def _hydrate_capsule(capsule: CandidateContextCapsule) -> CandidateContextCapsule:
    """Restore typed rows after JSON admission loading without compiling new context."""
    members: list[CandidateContextFullMember] = []
    for member in capsule.full_members:
        if not isinstance(member.row, dict):
            members.append(member)
            continue
        row_type = _DELTA_ROW_TYPES.get(member.identity.row_type)
        if row_type is None:
            raise CandidateProposalError("stored capsule has an unsupported row type")
        where = f"{member.identity.artifact_key} {member.identity.row_id}"
        try:
            row = roadmap_candidate._restore_stored_stage_row(row_type, member.row)
        except CandidateDeltaError as exc:
            raise CandidateProposalError(f"stored capsule row {where} cannot be restored: {exc}") from exc
        if row.id != member.identity.row_id:
            raise CandidateProposalError(f"stored capsule row {where} does not match its identity")
        members.append(member.model_copy(update={"row": row}))
    return capsule.model_copy(update={"full_members": tuple(members)})


_DELTA_ROW_TYPES: Final[dict[str, str]] = {
    "EntityRow": "entities",
    "BusinessRuleRow": "business_rules",
    "WorkflowRow": "workflows",
    "DecisionRow": "decisions",
    "AttributeDispositionRow": "dispositions",
    "ConstraintRow": "constraints",
    "HostingRow": "hosting",
    "PatternRow": "system_patterns",
    "StoreRow": "stores",
    "StackRow": "stack",
    "ComponentRow": "components",
    "PlanRow": "plans",
    "AssumptionRow": "assumptions",
}


def _feedback_selector(feedback: CandidateContextFeedback) -> str:
    return f"{feedback.artifact_key}:{feedback.feedback_id}"


def _result(outcome: CandidateProposalOutcome, detail: str, call_count: int) -> CandidateProposalResult:
    return CandidateProposalResult(outcome=outcome, detail=detail, call_count=call_count)


def candidate_failure_diagnostic_extras(
    *,
    attempt: int | None,
    call_count: int,
    failure_detail: str,
    response_text: str | None,
) -> dict[str, object]:
    return {
        "failure_detail": failure_detail,
        "failure_attempt": attempt,
        "failure_call_count": call_count,
        "response_capture": "not-applicable" if response_text is None else "unavailable",
    }


def record_candidate_failure_diagnostics(
    *,
    logger: RunLogWriter,
    phase: str,
    attempt: int | None,
    outcome: str,
    call_count: int,
    failure_detail: str,
    response_text: str | None,
) -> dict[str, object]:
    """Persist failure facts and, when present, the exact rejected response.

    Candidate paths reuse the established parse-failure receipt rather than
    extending the shared run-log schema. The receipt is best-effort; its
    digest and capture result are still recorded if writing it fails.
    """
    extras = candidate_failure_diagnostic_extras(
        attempt=attempt,
        call_count=call_count,
        failure_detail=failure_detail,
        response_text=response_text,
    )
    if response_text is None:
        return extras

    raw = response_text.encode("utf-8")
    digest = _digest(raw)
    receipt_dir = logger.repo_root / ".plan-tool" / "parse-failures" / logger.slug
    safe_phase = re.sub(r"[^A-Za-z0-9._-]+", "-", phase).strip(".-") or "candidate"
    receipt_path = receipt_dir / f"{logger.run_id}-{safe_phase}-attempt{attempt or 1}-{digest[:16]}.txt"
    try:
        durable_write_bytes(receipt_path, raw)
        failure_path = receipt_path.relative_to(logger.repo_root).as_posix()
        response_capture = "stored"
    except BaseException:
        # Best-effort by contract: a write failure — including a second
        # KeyboardInterrupt landing here — must not stop the caller's
        # finally block from recording the command's real terminal outcome.
        failure_path = ""
        response_capture = "unavailable"

    # A second KeyboardInterrupt landing mid-write here must not stop the
    # caller's finally block from reaching its own phase_end/run_end call —
    # the same goal as backend_runner.py's `_finalize_interrupted_call`,
    # which guards its own best-effort observer calls the same way (though
    # via a hand-rolled try/except, not this suppress helper).
    with contextlib.suppress(KeyboardInterrupt):
        logger.parse_failure(
            phase=phase,
            attempt=attempt or 1,
            failure_path=failure_path,
            reason=failure_detail,
            outcome=outcome,
            call_count=call_count,
            raw_bytes=len(raw),
            response_digest=digest,
            response_capture=response_capture,
        )
    extras.update(
        failure_path=failure_path or None,
        failure_response_bytes=len(raw),
        failure_response_digest=digest,
        response_capture=response_capture,
    )
    return extras


def _decode_single_json_object(response_text: str) -> dict[str, object]:
    if not isinstance(response_text, str):
        raise CandidateProposalResponseError("candidate response must be JSON text")
    decoder = json.JSONDecoder(
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_constant,
    )
    start = len(response_text) - len(response_text.lstrip(" \t\r\n"))
    try:
        payload, end = decoder.raw_decode(response_text, start)
    except (CandidateProposalResponseError, json.JSONDecodeError) as exc:
        raise CandidateProposalResponseError("candidate response must be one unfenced JSON object") from exc
    if response_text[end:].strip(" \t\r\n"):
        raise CandidateProposalResponseError("candidate response must not contain trailing text")
    if not isinstance(payload, dict):
        raise CandidateProposalResponseError("candidate response root must be an object")
    return cast(dict[str, object], payload)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise CandidateProposalResponseError("candidate response has duplicate JSON keys")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise CandidateProposalResponseError(f"candidate response cannot use JSON constant {value!r}")


def _render_record(record: BaseModel, *, description: str, exclude_none: bool = False) -> bytes:
    try:
        encoded = _canonical_json_bytes(record.model_dump(mode="json", exclude_none=exclude_none))
        validated = record.__class__.model_validate_json(encoded)
        return _canonical_json_bytes(validated.model_dump(mode="json", exclude_none=exclude_none))
    except (ValidationError, TypeError, ValueError) as exc:
        raise CandidateProposalError(f"{description} is invalid") from exc


def _parse_record(
    data: bytes,
    record_type: type[BaseModel],
    *,
    description: str,
    exclude_none: bool = False,
) -> Any:
    _decode_strict_json(data, description=description)
    try:
        record = record_type.model_validate_json(data)
    except ValidationError as exc:
        raise CandidateProposalError(f"{description} is malformed") from exc
    if _render_record(record, description=description, exclude_none=exclude_none) != data:
        raise CandidateProposalError(f"{description} must use exact canonical JSON")
    return record


def _decode_strict_json(data: bytes, *, description: str) -> object:
    try:
        text = data.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, CandidateProposalResponseError) as exc:
        raise CandidateProposalError(f"{description} is not strict JSON") from exc


def _wire_value(value: object) -> object:
    value = unwrap_enum_value(value)
    if isinstance(value, BaseModel):
        return {
            name: _wire_value(getattr(value, name))
            for name in value.__class__.model_fields
            # Mirrors roadmap_candidate_context._wire_value: single-owner and legacy spans omit it.
            if not (name == "owning_row_ids" and getattr(value, name) is None)
        }
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _wire_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple | list):
        return [_wire_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _wire_value(item) for key, item in value.items()}
    if value is None or type(value) in {str, int, float, bool}:
        return value
    raise CandidateProposalError(f"candidate proposal cannot render {type(value).__name__}")


def _canonical_json_text(value: object) -> str:
    return _canonical_json_bytes(value).decode("utf-8")


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CandidateProposalError("candidate proposal JSON must be canonical") from exc
