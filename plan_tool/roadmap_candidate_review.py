"""Immutable question, answer, replacement, and seal records for one candidate."""

from __future__ import annotations

import contextlib
import hashlib
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from string import Template
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from plan_tool import roadmap_candidate, roadmap_candidate_narrative, roadmap_candidate_run, shell
from plan_tool.renderer import prompts_dir
from plan_tool.roadmap import STAGES, refresh_roadmap_index
from plan_tool.roadmap_artifacts import RoadmapArtifactError
from plan_tool.roadmap_candidate_context import (
    CandidateContextCapsule,
    CandidateContextFeedback,
    CandidateContextReceipt,
    is_supported_candidate_context_ceiling,
)
from plan_tool.roadmap_diff import RoadmapDiff, build_roadmap_diff
from plan_tool.roadmap_feedback_ledger import (
    RoadmapFeedbackLedgerError,
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
    VERSION_ARTIFACT_KEYS,
    PreparedRoadmapVersion,
    ResolvedRoadmapVersion,
    RoadmapVersionContent,
    RoadmapVersionError,
    StoredRoadmapVersion,
    create_candidate_version,
    load_accepted_version,
    load_stored_version,
    sha256_digests,
    stored_artifact_path,
    stored_brief_path,
    stored_version_members,
    version_directory_path,
    version_namespace_path,
)
from plan_tool.run_log import RunLogWriter, hash_prompt


_SCHEMA_VERSION: Final[int] = 1
_DIGEST_LENGTH: Final[int] = 64
_QUESTION_PHASE: Final[str] = "roadmap-candidate-question"
_REPLACEMENT_PHASE: Final[str] = "roadmap-candidate-replacement"
_STRUCTURAL_EDIT_PHASE: Final[str] = "roadmap-candidate-structural-edit"
_QUESTION_INVENTORY_FILENAME: Final[str] = "candidate-review-question-inventory.json"
_ANSWER_FILENAME: Final[str] = "candidate-review-answer.json"
_REPLACEMENT_STATE_FILENAME: Final[str] = "candidate-review-replacement-state.json"
_REPLACEMENT_BINDING_FILENAME: Final[str] = "candidate-review-replacement-binding.json"
_REPLACEMENT_EVIDENCE_FILENAME: Final[str] = "candidate-review-replacement.json"
_SEALS_DIRECTORY: Final[str] = "review-seals"
_APPROVAL_DIGEST_REQUIRED: Final[str] = "structural approval requires the stack digest that confirms it"
_APPROVAL_DIGEST_MISMATCH: Final[str] = "confirming stack digest differs from the candidate's stack digest"

CandidateReviewInvoker = Callable[[str], tuple[int, str]]
CandidateReviewOutcome = Literal["stored", "response-rejected", "failed", "refused", "interrupted"]


class CandidateReviewError(ValueError):
    """Stored review evidence is missing, malformed, or substituted."""


class CandidateQuestionResponseError(ValueError):
    """A question response falls outside the closed question contract."""


class _FrozenReviewRecord(BaseModel):
    """Base type for exact, immutable review evidence."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, arbitrary_types_allowed=True)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            _wire_value(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CandidateReviewError("candidate review record cannot be canonical JSON") from exc


def _canonical_json_text(value: object) -> str:
    return _canonical_json_bytes(value).decode("utf-8")


def _identity(value: object) -> str:
    return _digest(_canonical_json_bytes(value))


def _require_digest(value: str, *, name: str) -> str:
    return roadmap_candidate_run._require_digest(value, name=name)


class CandidateQuestionAnchor(_FrozenReviewRecord):
    """One stored immutable fact that gives a question a deterministic target."""

    kind: Literal["feedback", "diff-row", "full-member", "inventory", "reviewer-item", "response", "derived-context"]
    artifact_key: str
    row_type: str | None = None
    row_id: str | None = None
    feedback_id: str | None = None

    @model_validator(mode="after")
    def _requires_kind_shape(self) -> "CandidateQuestionAnchor":
        if not self.artifact_key:
            raise ValueError("question anchor artifact key must be nonempty")
        if self.kind == "feedback":
            if self.feedback_id is None or self.row_type is not None or self.row_id is not None:
                raise ValueError("feedback anchor has the wrong fields")
        elif self.feedback_id is not None or not self.row_type or not self.row_id:
            raise ValueError("row anchor has the wrong fields")
        return self


class CandidateQuestion(_FrozenReviewRecord):
    """One opaque model question with a code-derived identity."""

    question_id: str
    anchor: CandidateQuestionAnchor
    question_text: str

    @model_validator(mode="after")
    def _requires_expected_identity(self) -> "CandidateQuestion":
        expected = _identity(
            {
                "schema_version": _SCHEMA_VERSION,
                "anchor": self.anchor,
                "question_text": self.question_text,
            }
        )
        if self.question_id != expected:
            raise ValueError("question id does not bind its anchor and opaque text")
        return self


class CandidateQuestionInventory(_FrozenReviewRecord):
    """The single question inventory admitted for one initial candidate."""

    schema_version: int
    inventory_id: str
    initial_candidate_version_id: str
    initial_content_identity: str
    predecessor_version_id: str
    feedback: CandidateContextFeedback | None = None
    predecessor_diff: roadmap_candidate.CandidatePredecessorDiff
    capsule_identity: str
    question: CandidateQuestion
    review_requirement: roadmap_candidate.CandidateReviewRequirement | None = None
    # Batch candidates retain these independently from their direct source.
    # Optional fields keep historical selector-bound inventories readable.
    root_version_id: str | None = None
    source_version_id: str | None = None
    batch_receipt_identity: str | None = None

    @field_validator(
        "inventory_id",
        "initial_candidate_version_id",
        "initial_content_identity",
        "predecessor_version_id",
        "capsule_identity",
        "root_version_id",
        "source_version_id",
        "batch_receipt_identity",
    )
    @classmethod
    def _requires_digest(cls, value: str | None, info: object) -> str | None:
        return None if value is None else _require_digest(value, name=getattr(info, "field_name", "review identity"))

    @model_validator(mode="after")
    def _requires_exact_identity(self) -> "CandidateQuestionInventory":
        if self.schema_version != _SCHEMA_VERSION:
            raise ValueError("question inventory schema version is unsupported")
        batch_fields = (self.root_version_id, self.source_version_id, self.batch_receipt_identity)
        if any(value is not None for value in batch_fields) and any(value is None for value in batch_fields):
            raise ValueError("question inventory batch binding is incomplete")
        if self.root_version_id is not None and (self.feedback is not None or self.review_requirement is not None):
            raise ValueError("batch question inventory cannot substitute selector feedback")
        expected = _identity(_inventory_preimage(self))
        if self.inventory_id != expected:
            raise ValueError("question inventory id does not bind its immutable facts")
        return self


class CandidateReviewAnswer(_FrozenReviewRecord):
    """One exact reviewer answer, separate from the candidate and question."""

    schema_version: int
    answer_id: str
    inventory_id: str
    question_id: str
    answer_text: str

    @field_validator("answer_id", "inventory_id", "question_id")
    @classmethod
    def _requires_digest(cls, value: str, info: object) -> str:
        return _require_digest(value, name=getattr(info, "field_name", "answer identity"))

    @model_validator(mode="after")
    def _requires_exact_identity(self) -> "CandidateReviewAnswer":
        if self.schema_version != _SCHEMA_VERSION:
            raise ValueError("review answer schema version is unsupported")
        expected = _identity(
            {
                "schema_version": _SCHEMA_VERSION,
                "inventory_id": self.inventory_id,
                "question_id": self.question_id,
                "answer_text": self.answer_text,
            }
        )
        if self.answer_id != expected:
            raise ValueError("answer id does not bind its supplied text")
        return self


class CandidateAnswerIncorporation(_FrozenReviewRecord):
    """Mechanical proof that one exact stored pair drove a replacement request."""

    incorporation_id: str
    inventory_id: str
    question_id: str
    answer_id: str

    @field_validator("incorporation_id", "inventory_id", "question_id", "answer_id")
    @classmethod
    def _requires_digest(cls, value: str, info: object) -> str:
        return _require_digest(value, name=getattr(info, "field_name", "incorporation identity"))

    @model_validator(mode="after")
    def _requires_exact_identity(self) -> "CandidateAnswerIncorporation":
        expected = _identity(
            {
                "schema_version": _SCHEMA_VERSION,
                "inventory_id": self.inventory_id,
                "question_id": self.question_id,
                "answer_id": self.answer_id,
            }
        )
        if self.incorporation_id != expected:
            raise ValueError("incorporation id does not bind its review pair")
        return self


class CandidateReviewReplacementState(_FrozenReviewRecord):
    """The persisted final capsule after this lineage spends its one expansion."""

    schema_version: int
    initial_candidate_version_id: str
    initial_content_identity: str
    predecessor_version_id: str
    feedback: CandidateContextFeedback
    capsule: CandidateContextCapsule
    receipt: CandidateContextReceipt

    @field_validator(
        "initial_candidate_version_id", "initial_content_identity", "predecessor_version_id"
    )
    @classmethod
    def _requires_digest(cls, value: str, info: object) -> str:
        return _require_digest(value, name=getattr(info, "field_name", "replacement state identity"))

    @model_validator(mode="after")
    def _requires_final_capsule(self) -> "CandidateReviewReplacementState":
        if (
            self.schema_version != _SCHEMA_VERSION
            or self.capsule.expansion is None
            or self.capsule.receipt != self.receipt
            or self.capsule.feedback != self.feedback
            or self.capsule.predecessor.version_id != self.predecessor_version_id
            or not is_supported_candidate_context_ceiling(self.capsule.ceiling_bytes)
            or self.receipt.ceiling_bytes != self.capsule.ceiling_bytes
            or not roadmap_candidate_run._capsule_and_receipt_are_exact(self.capsule, self.receipt)
        ):
            raise ValueError("replacement state does not bind one final capsule")
        return self


class CandidateReviewReplacementBinding(_FrozenReviewRecord):
    """The initial candidate's fixed pointer to its one answer-bound replacement."""

    schema_version: int
    initial_candidate_version_id: str
    inventory_id: str
    question_id: str
    answer_id: str
    candidate_version_id: str

    @field_validator(
        "initial_candidate_version_id",
        "inventory_id",
        "question_id",
        "answer_id",
        "candidate_version_id",
    )
    @classmethod
    def _requires_digest(cls, value: str, info: object) -> str:
        return _require_digest(value, name=getattr(info, "field_name", "replacement binding identity"))

    @model_validator(mode="after")
    def _requires_supported_schema_version(self) -> "CandidateReviewReplacementBinding":
        if self.schema_version != _SCHEMA_VERSION:
            raise ValueError("replacement binding schema version is unsupported")
        return self


class CandidateReviewReplacement(_FrozenReviewRecord):
    """Evidence retained beside one answer-bound replacement candidate.

    A selector-era replacement carries its selected ``feedback`` and issued
    ``capsule``/``receipt``. A ledger-batch replacement instead carries the
    reviewed candidate's ``root``/``source``/``batch_receipt_identity`` and the
    replacement's own ``response_patch`` and ``derived_feedback``, which its content
    identity binds; its capsule and receipt are the reviewed candidate's, kept in
    the replacement's own ``candidate-evidence.json``.
    """

    schema_version: int
    roadmap_slug: str
    initial_candidate_version_id: str
    candidate_version_id: str
    predecessor_version_id: str
    review_lineage_identity: str
    feedback: CandidateContextFeedback | None = None
    raw_brief_digest: str
    artifact_digests: tuple[str, ...]
    content_identity: str
    predecessor_diff: roadmap_candidate.CandidatePredecessorDiff
    replacement_impact_atoms: tuple[roadmap_candidate.CandidateImpactAtom, ...] | None = None
    replacement_impact_identity: str | None = None
    replacement_review_requirement: roadmap_candidate.CandidateReviewRequirement | None = None
    gate_evidence: tuple[roadmap_candidate_run.CandidateGateEvidence, ...]
    capsule: CandidateContextCapsule | None = None
    receipt: CandidateContextReceipt | None = None
    question_inventory_id: str
    answer_incorporation: CandidateAnswerIncorporation
    root_version_id: str | None = None
    source_version_id: str | None = None
    batch_receipt_identity: str | None = None
    response_patch: roadmap_candidate.CandidateResponsePatch | None = None
    derived_feedback: tuple[roadmap_candidate.CandidateDerivedFeedback, ...] | None = None

    @field_validator(
        "initial_candidate_version_id",
        "candidate_version_id",
        "predecessor_version_id",
        "review_lineage_identity",
        "raw_brief_digest",
        "content_identity",
        "question_inventory_id",
    )
    @classmethod
    def _requires_digest(cls, value: str, info: object) -> str:
        return _require_digest(value, name=getattr(info, "field_name", "replacement identity"))

    @field_validator("root_version_id", "source_version_id", "batch_receipt_identity")
    @classmethod
    def _requires_optional_batch_digest(cls, value: str | None, info: object) -> str | None:
        return (
            None
            if value is None
            else _require_digest(value, name=getattr(info, "field_name", "replacement batch identity"))
        )

    @field_validator("replacement_impact_identity")
    @classmethod
    def _requires_optional_impact_identity(cls, value: str | None) -> str | None:
        return (
            None
            if value is None
            else _require_digest(value, name="replacement impact identity")
        )

    @field_validator("artifact_digests")
    @classmethod
    def _requires_artifact_digests(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(STAGES):
            raise ValueError("replacement must bind every artifact digest")
        return tuple(_require_digest(item, name="replacement artifact digest") for item in value)

    @model_validator(mode="after")
    def _requires_exact_bindings(self) -> "CandidateReviewReplacement":
        if (
            self.schema_version != _SCHEMA_VERSION
            or not self.roadmap_slug
            or tuple(item.artifact_key for item in self.gate_evidence)
            != tuple(stage.artifact_key for stage in STAGES)
            or any(item.violations for item in self.gate_evidence)
            or self.question_inventory_id != self.answer_incorporation.inventory_id
        ):
            raise ValueError("replacement evidence has inconsistent immutable bindings")
        expected_lineage = _review_lineage_identity(
            self.question_inventory_id, self.answer_incorporation.answer_id
        )
        if self.review_lineage_identity != expected_lineage:
            raise ValueError("replacement has the wrong answer-bound lineage identity")
        batch_fields = (
            self.root_version_id,
            self.source_version_id,
            self.batch_receipt_identity,
            self.response_patch,
            self.derived_feedback,
        )
        if any(value is not None for value in batch_fields):
            return self._require_batch_bindings(batch_fields)
        return self._require_selector_bindings()

    def _require_batch_bindings(self, batch_fields: tuple[object, ...]) -> "CandidateReviewReplacement":
        if any(value is None for value in batch_fields):
            raise ValueError("replacement batch binding is incomplete")
        if (
            self.feedback is not None
            or self.capsule is not None
            or self.receipt is not None
            or self.replacement_impact_atoms is not None
            or self.replacement_impact_identity is not None
            or self.replacement_review_requirement is not None
        ):
            raise ValueError("batch replacement cannot substitute selector evidence")
        if self.predecessor_version_id != self.source_version_id:
            raise ValueError("batch replacement predecessor must be its reviewed source")
        return self

    def _require_selector_bindings(self) -> "CandidateReviewReplacement":
        if self.feedback is None or self.capsule is None or self.receipt is None:
            raise ValueError("replacement evidence has inconsistent immutable bindings")
        if (
            self.capsule.receipt != self.receipt
            or self.capsule.feedback != self.feedback
            or self.capsule.predecessor.version_id != self.predecessor_version_id
            or not is_supported_candidate_context_ceiling(self.capsule.ceiling_bytes)
            or self.receipt.ceiling_bytes != self.capsule.ceiling_bytes
            or not roadmap_candidate_run._capsule_and_receipt_are_exact(self.capsule, self.receipt)
        ):
            raise ValueError("replacement evidence has inconsistent immutable bindings")
        if (self.replacement_impact_atoms is None) != (
            self.replacement_impact_identity is None
        ):
            raise ValueError("replacement impact evidence is incomplete")
        has_persisted_impact = self.replacement_impact_atoms is not None
        if has_persisted_impact and self.replacement_impact_identity != (
            roadmap_candidate.candidate_impact_identity(self.replacement_impact_atoms)
        ):
            raise ValueError("replacement impact identity does not bind its derived atoms")
        if not has_persisted_impact and self.replacement_review_requirement is not None:
            raise ValueError("replacement review requirement has no derived impact")
        requires_review = roadmap_candidate._candidate_diff_requires_review_requirement(
            self.predecessor_diff
        )
        if has_persisted_impact and (
            self.replacement_review_requirement is not None
        ) != requires_review:
            raise ValueError("replacement review requirement does not match its candidate impact")
        if not has_persisted_impact and requires_review:
            raise ValueError("replacement review requirement lacks derived impact")
        if self.replacement_review_requirement is not None and (
            self.replacement_review_requirement.predecessor_version_id
            != self.predecessor_version_id
            or self.replacement_review_requirement.selected_feedback != self.feedback
            or self.replacement_review_requirement.capsule_receipt != self.receipt
            or self.replacement_review_requirement.predecessor_diff != self.predecessor_diff
            or self.replacement_review_requirement.impact_atoms != self.replacement_impact_atoms
        ):
            raise ValueError("replacement review requirement does not bind its derived impact")
        return self


class CandidateReviewSeal(_FrozenReviewRecord):
    """A completed immutable review binding, not a promotion instruction."""

    schema_version: int
    seal_id: str
    roadmap_slug: str
    initial_candidate_version_id: str
    question_inventory_id: str | None = None
    answer_ids: tuple[str, ...] = ()
    replacement_candidate_version_id: str | None = None
    replacement_content_identity: str | None = None
    answer_incorporation_id: str | None = None
    final_capsule_identity: str
    # A direct structural approval seals the displayed active candidate itself.
    # Defaults keep historical answered-replacement seal bytes and identities intact.
    decision: Literal["answered-replacement", "structural-approval"] = "answered-replacement"
    approved_candidate_version_id: str | None = None
    approved_content_identity: str | None = None
    # A batch seal also binds the reviewed candidate's root, source and batch;
    # optional so selector-era seals keep their exact bytes and identity.
    root_version_id: str | None = None
    source_version_id: str | None = None
    batch_receipt_identity: str | None = None

    @field_validator(
        "seal_id",
        "initial_candidate_version_id",
        "question_inventory_id", "replacement_candidate_version_id",
        "replacement_content_identity", "answer_incorporation_id",
        "final_capsule_identity",
        "approved_candidate_version_id", "approved_content_identity",
    )
    @classmethod
    def _requires_digest(cls, value: str | None, info: object) -> str | None:
        return None if value is None else _require_digest(value, name=getattr(info, "field_name", "review seal identity"))

    @field_validator("root_version_id", "source_version_id", "batch_receipt_identity")
    @classmethod
    def _requires_optional_batch_digest(cls, value: str | None, info: object) -> str | None:
        return (
            None
            if value is None
            else _require_digest(value, name=getattr(info, "field_name", "review seal batch identity"))
        )

    @field_validator("answer_ids")
    @classmethod
    def _requires_answers(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) not in (0, 1):
            raise ValueError("review seal has an invalid answer count")
        return tuple(_require_digest(item, name="review seal answer id") for item in value)

    @model_validator(mode="after")
    def _requires_exact_identity(self) -> "CandidateReviewSeal":
        if self.schema_version != _SCHEMA_VERSION or not self.roadmap_slug:
            raise ValueError("review seal has unsupported bindings")
        batch_fields = (self.root_version_id, self.source_version_id, self.batch_receipt_identity)
        if any(value is not None for value in batch_fields) and any(value is None for value in batch_fields):
            raise ValueError("review seal batch binding is incomplete")
        legacy = (
            self.question_inventory_id, self.replacement_candidate_version_id,
            self.replacement_content_identity, self.answer_incorporation_id,
        )
        if self.decision == "structural-approval":
            if any(value is not None for value in legacy) or self.answer_ids or (
                self.approved_candidate_version_id is None or self.approved_content_identity is None
            ):
                raise ValueError("structural approval seal has answered-review bindings")
        elif (
            any(value is None for value in legacy) or len(self.answer_ids) != 1
            or self.approved_candidate_version_id is not None or self.approved_content_identity is not None
        ):
            raise ValueError("answered review seal has incomplete bindings")
        expected = _identity(_seal_preimage(self))
        if self.seal_id != expected:
            raise ValueError("review seal id does not bind its complete review")
        return self


@dataclass(frozen=True)
class StoredCandidateReviewReplacement:
    """One replacement version and its exact answer-incorporation evidence."""

    record: StoredRoadmapVersion
    content: RoadmapVersionContent
    evidence: CandidateReviewReplacement

    @property
    def version_id(self) -> str:
        """Return the immutable replacement candidate identity."""
        return self.record.version_id


@dataclass(frozen=True)
class CandidateReviewResult:
    """A closed terminal result for question or answer-driven review work."""

    outcome: CandidateReviewOutcome
    initial_candidate: roadmap_candidate_run.StoredCandidateProposal | None = None
    question_inventory: CandidateQuestionInventory | None = None
    answer: CandidateReviewAnswer | None = None
    replacement: StoredCandidateReviewReplacement | None = None
    active_candidate: roadmap_candidate_run.StoredCandidateProposal | None = None
    seal: CandidateReviewSeal | None = None
    detail: str | None = None
    call_count: int = 0

    def __post_init__(self) -> None:
        if self.outcome == "stored" and self.initial_candidate is None:
            raise ValueError("stored candidate review results require an initial candidate")
        if self.outcome != "stored" and any(
            value is not None
            for value in (
                self.question_inventory,
                self.answer,
                self.replacement,
                self.active_candidate,
                self.seal,
            )
        ):
            raise ValueError("non-stored candidate review results cannot expose review records")


def shell_candidate_review_invoker(
    prompt: str, *, phase: str = _QUESTION_PHASE
) -> tuple[int, str]:
    """Make one physical candidate-review request without retry waiting."""
    return shell.claude_invoke(
        prompt,
        phase=phase,
        attempt=1,
        wait_on_rate_limit=False,
        max_transient_retries=1,
    )


def question_inventory_path(plans_dir: Path, slug: str, initial_candidate_version_id: str) -> Path:
    """Return the sole question inventory path for one admitted initial candidate."""
    return version_directory_path(plans_dir, slug, initial_candidate_version_id) / _QUESTION_INVENTORY_FILENAME


def reviewer_answer_path(plans_dir: Path, slug: str, initial_candidate_version_id: str) -> Path:
    """Return the one reviewer answer path for the one-question inventory."""
    return version_directory_path(plans_dir, slug, initial_candidate_version_id) / _ANSWER_FILENAME


def replacement_state_path(plans_dir: Path, slug: str, initial_candidate_version_id: str) -> Path:
    """Return the continuation state for a spent answer-driven expansion."""
    return version_directory_path(plans_dir, slug, initial_candidate_version_id) / _REPLACEMENT_STATE_FILENAME


def replacement_binding_path(plans_dir: Path, slug: str, initial_candidate_version_id: str) -> Path:
    """Return the initial candidate's deterministic pointer to its replacement."""
    return version_directory_path(plans_dir, slug, initial_candidate_version_id) / _REPLACEMENT_BINDING_FILENAME


def replacement_evidence_path(plans_dir: Path, slug: str, candidate_version_id: str) -> Path:
    """Return the exact review evidence retained beside a replacement version."""
    return version_directory_path(plans_dir, slug, candidate_version_id) / _REPLACEMENT_EVIDENCE_FILENAME


def review_seal_path(plans_dir: Path, slug: str, seal_id: str) -> Path:
    """Return the deterministic shared-version path for one review seal."""
    _require_digest(seal_id, name="review seal id")
    return version_namespace_path(plans_dir, slug) / _SEALS_DIRECTORY / f"{seal_id}.json"


def render_question_inventory(inventory: CandidateQuestionInventory) -> bytes:
    """Render a question inventory as exact canonical JSON bytes."""
    return _render_record(
        inventory,
        description="candidate question inventory",
        exclude_none_fields=True,
    )


def parse_question_inventory(data: bytes) -> CandidateQuestionInventory:
    """Parse one exact canonical question inventory."""
    _decode_strict_json(data, description="candidate question inventory")
    try:
        inventory = CandidateQuestionInventory.model_validate_json(data)
    except ValidationError as exc:
        raise CandidateReviewError("candidate question inventory is malformed") from exc
    if render_question_inventory(inventory) != data:
        raise CandidateReviewError("candidate question inventory must use exact canonical JSON")
    return inventory


def render_reviewer_answer(answer: CandidateReviewAnswer) -> bytes:
    """Render a reviewer answer as exact canonical JSON bytes."""
    return _render_record(answer, description="candidate reviewer answer")


def parse_reviewer_answer(data: bytes) -> CandidateReviewAnswer:
    """Parse one exact canonical reviewer answer."""
    return cast(
        CandidateReviewAnswer,
        _parse_record(data, CandidateReviewAnswer, description="candidate reviewer answer"),
    )


def render_replacement_state(state: CandidateReviewReplacementState) -> bytes:
    """Render the one immutable final-capsule continuation state."""
    return _render_record(state, description="candidate replacement state")


def parse_replacement_state(data: bytes) -> CandidateReviewReplacementState:
    """Parse one exact canonical replacement continuation state."""
    return cast(
        CandidateReviewReplacementState,
        _parse_record(data, CandidateReviewReplacementState, description="candidate replacement state"),
    )


def render_replacement_binding(binding: CandidateReviewReplacementBinding) -> bytes:
    """Render the one fixed replacement pointer for an answered inventory."""
    return _render_record(binding, description="candidate replacement binding")


def parse_replacement_binding(data: bytes) -> CandidateReviewReplacementBinding:
    """Parse the initial candidate's exact replacement pointer."""
    return cast(
        CandidateReviewReplacementBinding,
        _parse_record(data, CandidateReviewReplacementBinding, description="candidate replacement binding"),
    )


def render_replacement_evidence(replacement: CandidateReviewReplacement) -> bytes:
    """Render one answer-bound replacement record."""
    return _render_record(
        replacement,
        description="candidate review replacement",
        exclude_unset_fields=True,
    )


def parse_replacement_evidence(data: bytes) -> CandidateReviewReplacement:
    """Parse one exact canonical answer-bound replacement record."""
    return cast(
        CandidateReviewReplacement,
        _parse_record(
            data,
            CandidateReviewReplacement,
            description="candidate review replacement",
            exclude_unset_fields=True,
        ),
    )


def render_review_seal(seal: CandidateReviewSeal) -> bytes:
    """Render one immutable review seal."""
    return _render_record(seal, description="candidate review seal", exclude_unset_fields=True)


def parse_review_seal(data: bytes) -> CandidateReviewSeal:
    """Parse one exact canonical review seal."""
    return cast(
        CandidateReviewSeal,
        _parse_record(
            data, CandidateReviewSeal, description="candidate review seal", exclude_unset_fields=True
        ),
    )


def render_candidate_question_prompt(
    *,
    candidate: roadmap_candidate_run.StoredCandidateProposal,
) -> str:
    """Render the closed question prompt from persisted candidate facts only."""
    evidence = candidate.evidence
    receipt = evidence.receipt
    if evidence.batch_receipt is not None:
        batch = evidence.batch_receipt
        template = Template((prompts_dir() / "roadmap-candidate-questions.md").read_text(encoding="utf-8"))
        try:
            return template.substitute(
                initial_candidate_version_id=candidate.version_id,
                initial_content_identity=evidence.content_identity,
                predecessor_version_id=evidence.predecessor_version_id,
                root_version_id=evidence.root_version_id,
                source_version_id=evidence.source_version_id,
                batch_receipt_identity=batch.capsule_identity,
                feedback="null",
                predecessor_diff=_canonical_json_text(evidence.predecessor_diff),
                closure_members=_canonical_json_text(batch.full_members),
                declared_relations=_canonical_json_text(batch.relation_evidence),
                inventory=_canonical_json_text(batch.inventory),
                capsule_receipt=_canonical_json_text(batch),
                review_requirement="null",
                reviewer_items=_canonical_json_text(batch.reviewer_items),
                derived_context=_canonical_json_text(batch.derived_context),
            )
        except (KeyError, ValueError) as exc:
            raise CandidateReviewError("candidate question prompt has unresolved variables") from exc
    if (
        evidence.capsule.receipt != receipt
        or evidence.capsule.feedback != evidence.feedback
        or evidence.capsule.predecessor.version_id != evidence.predecessor_version_id
        or receipt.predecessor.version_id != evidence.predecessor_version_id
    ):
        raise CandidateReviewError("candidate question prompt has inconsistent stored authority")
    template = Template(
        (prompts_dir() / "roadmap-candidate-questions.md").read_text(encoding="utf-8")
    )
    closure_members = tuple(
        {
            "identity": member.identity,
            "row_digest": member.row_digest,
            "inclusion_reasons": member.inclusion_reasons,
            "source_spans": member.source_spans,
        }
        for member in receipt.full_members
    )
    try:
        return template.substitute(
            initial_candidate_version_id=candidate.version_id,
            initial_content_identity=evidence.content_identity,
            predecessor_version_id=evidence.predecessor_version_id,
            feedback=_canonical_json_text(evidence.feedback),
            predecessor_diff=_canonical_json_text(evidence.predecessor_diff),
            closure_members=_canonical_json_text(closure_members),
            declared_relations=_canonical_json_text(receipt.relation_evidence),
            inventory=_canonical_json_text(receipt.inventory),
            capsule_receipt=_canonical_json_text(receipt),
            review_requirement=_canonical_json_text(evidence.review_requirement),
            root_version_id="null",
            source_version_id="null",
            batch_receipt_identity="null",
            reviewer_items="[]",
            derived_context="[]",
        )
    except (KeyError, ValueError) as exc:
        raise CandidateReviewError("candidate question prompt has unresolved variables") from exc


def parse_candidate_question_response(
    response_text: str,
    *,
    candidate: roadmap_candidate_run.StoredCandidateProposal,
) -> CandidateQuestion:
    """Parse one question whose anchor resolves entirely inside stored facts."""
    payload = _decode_single_json_object(response_text, description="candidate question response")
    if set(payload) != {"anchor", "question"}:
        raise CandidateQuestionResponseError("candidate question response has unknown or missing fields")
    question_text = payload["question"]
    anchor_value = payload["anchor"]
    if not isinstance(question_text, str) or not isinstance(anchor_value, dict):
        raise CandidateQuestionResponseError("candidate question response has malformed fields")
    anchor = _parse_question_anchor(anchor_value, candidate=candidate)
    return CandidateQuestion(
        question_id=_identity(
            {
                "schema_version": _SCHEMA_VERSION,
                "anchor": anchor,
                "question_text": question_text,
            }
        ),
        anchor=anchor,
        question_text=question_text,
    )


def generate_candidate_question(
    slug: str,
    initial_candidate_version_id: str,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: CandidateReviewInvoker | None = None,
    run_logger: RunLogWriter | None = None,
) -> CandidateReviewResult:
    """Create or return the one question inventory for the admitted initial candidate."""
    logger = run_logger or RunLogWriter.start(
        repo_root=repo_root,
        slug=slug,
        command="roadmap",
        argv=["plan-tool", "roadmap", slug, "--review-candidate", initial_candidate_version_id],
        flags={"mode": "candidate-question"},
    )
    invoke = invoker or shell_candidate_review_invoker
    result: CandidateReviewResult | None = None
    call_count = 0
    last_response: roadmap_candidate_run.CandidateModelInvocation | None = None
    response_accepted = False
    started_at = time.monotonic()
    logger.phase_start(_QUESTION_PHASE)
    try:
        with roadmap_writer_guard(plans_dir, slug) as writer_token:
            initial = _load_admitted_initial_candidate(
                plans_dir=plans_dir,
                slug=slug,
                initial_candidate_version_id=initial_candidate_version_id,
            )
            _require_answered_review_route(initial, plans_dir=plans_dir, slug=slug)
            inventory = _load_question_inventory_if_present(
                plans_dir=plans_dir, slug=slug, initial=initial
            )
            if inventory is not None:
                result = _stored_result(initial=initial, inventory=inventory, call_count=call_count)
                return result
            prompt = render_candidate_question_prompt(candidate=initial)
            call_count = 1
            invocation = _invoke_once(
                invoke=invoke,
                logger=logger,
                phase=_QUESTION_PHASE,
                prompt=prompt,
                attempt=1,
            )
            last_response = invocation
            if invocation.rc != 0:
                result = _result("failed", "candidate question backend request failed", call_count)
                return result
            response = invocation.response
            try:
                question = parse_candidate_question_response(response, candidate=initial)
            except CandidateQuestionResponseError as exc:
                result = _result("response-rejected", str(exc), call_count)
                return result
            # The response is accepted from here on — a later storage failure
            # must not mislabel it as a rejected response.
            response_accepted = True
            inventory = _new_question_inventory(initial=initial, question=question)
            try:
                _publish_new_record(
                    plans_dir=plans_dir,
                    slug=slug,
                    writer_token=writer_token,
                    path=question_inventory_path(plans_dir, slug, initial.version_id),
                    data=render_question_inventory(inventory),
                    description="candidate question inventory",
                )
            except OSError as exc:
                result = _result("failed", str(exc), call_count)
                return result
            result = _stored_result(initial=initial, inventory=inventory, call_count=call_count)
            return result
    except KeyboardInterrupt:
        result = _interrupted_result(
            logger, phase=_QUESTION_PHASE, call_count=call_count, detail="candidate question interrupted"
        )
        return result
    except CandidateReviewError as exc:
        result = _result("refused", str(exc), call_count)
        return result
    except (RoadmapWriterGuardError, RoadmapVersionError) as exc:
        result = _result("failed", str(exc), call_count)
        return result
    except OSError as exc:
        result = _result("failed", str(exc), call_count)
        return result
    finally:
        terminal = result or _result("failed", "candidate question did not finish", call_count)
        _finish_log(
            logger,
            _QUESTION_PHASE,
            started_at,
            terminal,
            expansion_used=False,
            last_response=last_response,
            response_accepted=response_accepted,
        )


def record_reviewer_answer(
    slug: str,
    question_id: str,
    answer_text: str,
    *,
    plans_dir: Path,
    question_inventory_id: str | None = None,
) -> CandidateReviewResult:
    """Store one supplied answer exactly, or return its exact immutable replay."""
    try:
        with roadmap_writer_guard(plans_dir, slug) as writer_token:
            initial = _load_admitted_initial_candidate_from_admission(plans_dir=plans_dir, slug=slug)
            inventory = _require_question_inventory(plans_dir=plans_dir, slug=slug, initial=initial)
            initial_requirement = initial.evidence.review_requirement
            if inventory.review_requirement != initial_requirement:
                raise CandidateReviewError("question inventory does not bind the stored review requirement")
            if initial_requirement is not None:
                _replacement_capsule(plans_dir=plans_dir, slug=slug, initial=initial)
            if (
                question_id != inventory.question.question_id
                or question_inventory_id is not None and question_inventory_id != inventory.inventory_id
            ):
                return _result("refused", "reviewer answer does not bind the stored question inventory", 0)
            if not isinstance(answer_text, str):
                return _result("refused", "reviewer answer must be supplied as a string", 0)
            answer = _new_answer(inventory=inventory, answer_text=answer_text)
            path = reviewer_answer_path(plans_dir, slug, initial.version_id)
            if path.exists() or path.is_symlink():
                stored = _load_reviewer_answer(path)
                _validate_answer(stored, inventory=inventory)
                if stored != answer:
                    return _result("refused", "reviewer answer already has different exact bytes", 0)
                return _stored_result(initial=initial, inventory=inventory, answer=stored)
            _publish_new_record(
                plans_dir=plans_dir,
                slug=slug,
                writer_token=writer_token,
                path=path,
                data=render_reviewer_answer(answer),
                description="candidate reviewer answer",
                before_replace=(
                    lambda: _require_review_required_predecessor_is_current(
                        plans_dir=plans_dir, slug=slug, initial=initial
                    )
                    if initial_requirement is not None
                    else None
                ),
            )
            return _stored_result(initial=initial, inventory=inventory, answer=answer)
    except (CandidateReviewError, RoadmapVersionError, RoadmapWriterGuardError, OSError) as exc:
        return _result("refused" if isinstance(exc, CandidateReviewError) else "failed", str(exc), 0)


def request_replacement(
    slug: str,
    question_id: str,
    answer_text: str,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: CandidateReviewInvoker | None = None,
    run_logger: RunLogWriter | None = None,
    question_inventory_id: str | None = None,
) -> CandidateReviewResult:
    """Materialize or return the one replacement bound to the exact stored answer."""
    logger = run_logger or RunLogWriter.start(
        repo_root=repo_root,
        slug=slug,
        command="roadmap",
        argv=["plan-tool", "roadmap", slug, "--answer-question", question_id],
        flags={"mode": "candidate-replacement"},
    )
    invoke = invoker or (lambda prompt: shell_candidate_review_invoker(prompt, phase=_REPLACEMENT_PHASE))
    result: CandidateReviewResult | None = None
    call_count = 0
    expansion_used = False
    last_response: roadmap_candidate_run.CandidateModelInvocation | None = None
    response_accepted = False
    started_at = time.monotonic()
    logger.phase_start(_REPLACEMENT_PHASE)
    try:
        with roadmap_writer_guard(plans_dir, slug) as writer_token:
            initial = _load_admitted_initial_candidate_from_admission(plans_dir=plans_dir, slug=slug)
            inventory = _require_question_inventory(plans_dir=plans_dir, slug=slug, initial=initial)
            initial_requirement = initial.evidence.review_requirement
            if inventory.review_requirement != initial_requirement:
                raise CandidateReviewError("question inventory does not bind the stored review requirement")
            if (
                question_id != inventory.question.question_id
                or question_inventory_id is not None and question_inventory_id != inventory.inventory_id
            ):
                result = _result("refused", "replacement does not bind the stored question inventory", call_count)
                return result
            answer = _require_stored_answer(
                plans_dir=plans_dir,
                slug=slug,
                initial=initial,
                inventory=inventory,
                answer_text=answer_text,
            )
            _require_review_required_predecessor_is_current(
                plans_dir=plans_dir,
                slug=slug,
                initial=initial,
            )
            existing = _load_replacement_if_present(
                plans_dir=plans_dir,
                slug=slug,
                initial=initial,
                inventory=inventory,
                answer=answer,
            )
            if existing is not None:
                result = _stored_result(
                    initial=initial,
                    inventory=inventory,
                    answer=answer,
                    replacement=existing,
                    call_count=call_count,
                )
                return result
            predecessor = roadmap_candidate_run._load_resolved_version(
                plans_dir=plans_dir,
                slug=slug,
                version_id=initial.evidence.predecessor_version_id,
            )
            capsule, receipt = _replacement_capsule(
                plans_dir=plans_dir,
                slug=slug,
                initial=initial,
            )
            review_pair = roadmap_candidate_run.CandidateReviewPair(
                question_id=inventory.question.question_id,
                anchor=_canonical_json_text(inventory.question.anchor),
                question_text=inventory.question.question_text,
                answer_id=answer.answer_id,
                answer_text=answer.answer_text,
            )
            call_count = 1
            invocation = _invoke_replacement(
                invoke=invoke,
                logger=logger,
                capsule=capsule,
                receipt=receipt,
                review_pair=review_pair,
                attempt=1,
                source=predecessor,
            )
            last_response = invocation
            if invocation.rc != 0:
                result = _result("failed", "candidate replacement backend request failed", call_count)
                return result
            response = invocation.response
            try:
                disposition = roadmap_candidate_run.parse_candidate_proposal_response(
                    response,
                    capsule=capsule,
                    allow_expansion=(
                        initial_requirement is None
                        and capsule.expansion is None
                        and initial.evidence.batch_receipt is None
                    ),
                )
            except roadmap_candidate_run.CandidateProposalResponseError as exc:
                result = _result("response-rejected", str(exc), call_count)
                return result
            if isinstance(disposition, roadmap_candidate_run.CandidateExpansionRequest):
                if initial_requirement is not None:
                    result = _result(
                        "response-rejected",
                        "review-required candidate replacements cannot expand their capsule",
                        call_count,
                    )
                    return result
                expanded = roadmap_candidate_run.expand_candidate_context(
                    predecessor,
                    roadmap_candidate_run._hydrate_capsule(capsule),
                    disposition.entry,
                )
                if expanded.capsule is None:
                    result = _result(
                        "response-rejected",
                        expanded.refusal.detail if expanded.refusal is not None else "candidate expansion refused",
                        call_count,
                    )
                    return result
                # The expansion request itself is a valid, accepted response from here on —
                # a later storage failure must not mislabel it as a rejected response.
                response_accepted = True
                capsule = expanded.capsule
                receipt = capsule.receipt
                state = CandidateReviewReplacementState(
                    schema_version=_SCHEMA_VERSION,
                    initial_candidate_version_id=initial.version_id,
                    initial_content_identity=initial.evidence.content_identity,
                    predecessor_version_id=initial.evidence.predecessor_version_id,
                    feedback=initial.evidence.feedback,
                    capsule=capsule,
                    receipt=receipt,
                )
                try:
                    _publish_new_record(
                        plans_dir=plans_dir,
                        slug=slug,
                        writer_token=writer_token,
                        path=replacement_state_path(plans_dir, slug, initial.version_id),
                        data=render_replacement_state(state),
                        description="candidate replacement state",
                    )
                except OSError as exc:
                    result = _result("failed", str(exc), call_count)
                    return result
                expansion_used = True
                call_count = 2
                invocation = _invoke_replacement(
                    invoke=invoke,
                    logger=logger,
                    capsule=capsule,
                    receipt=receipt,
                    review_pair=review_pair,
                    attempt=2,
                    source=predecessor,
                )
                last_response = invocation
                response_accepted = False
                if invocation.rc != 0:
                    result = _result("failed", "candidate replacement backend request failed", call_count)
                    return result
                response = invocation.response
                try:
                    disposition = roadmap_candidate_run.parse_candidate_proposal_response(
                        response, capsule=capsule, allow_expansion=False
                    )
                except roadmap_candidate_run.CandidateProposalResponseError as exc:
                    result = _result("response-rejected", str(exc), call_count)
                    return result
            if isinstance(disposition, roadmap_candidate_run.CandidateExpansionRequest):
                result = _result("response-rejected", "candidate replacement response has no delta", call_count)
                return result
            materialized = roadmap_candidate.materialize_candidate(
                disposition,
                predecessor=predecessor,
                capsule=roadmap_candidate_run._hydrate_capsule(capsule),
                receipt=receipt,
            )
            if initial.evidence.batch_receipt is not None:
                if materialized.batch_candidate is None:
                    result = _result(
                        "response-rejected",
                        materialized.refusal.detail
                        if materialized.refusal is not None
                        else "candidate replacement materialization refused",
                        call_count,
                    )
                    return result
                if (
                    materialized.batch_candidate.operation_classification
                    is roadmap_candidate.CandidateOperationClassification.STRUCTURAL
                ):
                    result = _result(
                        "response-rejected",
                        "structural replacement cannot use the answered review route; "
                        "propose it with --propose-candidate and decide it with --decide-candidate",
                        call_count,
                    )
                    return result
                # Materialization succeeded: the response is accepted, so a later storage
                # failure must not mislabel it as a rejected response.
                response_accepted = True
                replacement = _store_batch_replacement(
                    plans_dir=plans_dir,
                    slug=slug,
                    writer_token=writer_token,
                    initial=initial,
                    inventory=inventory,
                    answer=answer,
                    predecessor=predecessor,
                    materialized=materialized.batch_candidate,
                    capsule=capsule,
                )
                result = _stored_result(
                    initial=initial,
                    inventory=inventory,
                    answer=answer,
                    replacement=replacement,
                    call_count=call_count,
                )
                return result
            replacement_candidate = materialized.candidate or materialized.review_required
            if replacement_candidate is None:
                result = _result(
                    "response-rejected",
                    materialized.refusal.detail
                    if materialized.refusal is not None
                    else "candidate replacement materialization refused",
                    call_count,
                )
                return result
            replacement_impact_atoms = _materialized_impact_atoms(replacement_candidate)
            if initial_requirement is not None and (
                materialized.review_required is not None
                and materialized.review_required.review_requirement.reason != initial_requirement.reason
                or not roadmap_candidate.review_requirement_contains_impact(
                    initial_requirement, replacement_impact_atoms
                )
            ):
                result = _result(
                    "response-rejected",
                    "candidate replacement impact exceeds the initial review disclosure",
                    call_count,
                )
                return result
            # Materialization succeeded: the response is accepted, so a later storage
            # failure must not mislabel it as a rejected response.
            response_accepted = True
            replacement = _store_replacement(
                plans_dir=plans_dir,
                slug=slug,
                writer_token=writer_token,
                initial=initial,
                inventory=inventory,
                answer=answer,
                predecessor=predecessor,
                materialized=replacement_candidate,
                capsule=capsule,
                receipt=receipt,
            )
            result = _stored_result(
                initial=initial,
                inventory=inventory,
                answer=answer,
                replacement=replacement,
                call_count=call_count,
            )
            return result
    except KeyboardInterrupt:
        result = _interrupted_result(
            logger, phase=_REPLACEMENT_PHASE, call_count=call_count, detail="candidate replacement interrupted"
        )
        return result
    except CandidateReviewError as exc:
        result = _result("refused", str(exc), call_count)
        return result
    except (RoadmapWriterGuardError, RoadmapVersionError) as exc:
        result = _result("failed", str(exc), call_count)
        return result
    except (OSError, roadmap_candidate_run.CandidateProposalError) as exc:
        result = _result("failed", str(exc), call_count)
        return result
    finally:
        terminal = result or _result("failed", "candidate replacement did not finish", call_count)
        _finish_log(
            logger,
            _REPLACEMENT_PHASE,
            started_at,
            terminal,
            expansion_used=expansion_used,
            last_response=last_response,
            response_accepted=response_accepted,
        )


def seal_review(
    slug: str,
    replacement_candidate_version_id: str,
    *,
    plans_dir: Path,
) -> CandidateReviewResult:
    """Create or return a seal for only the exact completed replacement lineage."""
    try:
        with roadmap_writer_guard(plans_dir, slug) as writer_token:
            initial = _load_admitted_initial_candidate_from_admission(plans_dir=plans_dir, slug=slug)
            inventory = _require_question_inventory(plans_dir=plans_dir, slug=slug, initial=initial)
            answer = _require_stored_answer(
                plans_dir=plans_dir,
                slug=slug,
                initial=initial,
                inventory=inventory,
                answer_text=None,
            )
            replacement = _load_replacement_if_present(
                plans_dir=plans_dir,
                slug=slug,
                initial=initial,
                inventory=inventory,
                answer=answer,
            )
            if replacement is None or replacement.version_id != replacement_candidate_version_id:
                return _result("refused", "review seal requires the exact stored replacement binding", 0)
            _require_review_required_predecessor_is_current(
                plans_dir=plans_dir,
                slug=slug,
                initial=initial,
            )
            seal = _new_seal(initial=initial, inventory=inventory, answer=answer, replacement=replacement)
            path = review_seal_path(plans_dir, slug, seal.seal_id)
            if path.exists() or path.is_symlink():
                stored = load_review_seal(plans_dir=plans_dir, slug=slug, seal_id=seal.seal_id)
                if stored != seal:
                    return _result("refused", "review seal identity collides with conflicting evidence", 0)
                return _stored_result(
                    initial=initial,
                    inventory=inventory,
                    answer=answer,
                    replacement=replacement,
                    seal=stored,
                )
            _require_no_blocking_narrative_defects(
                plans_dir=plans_dir, slug=slug, initial=initial, candidate_content=replacement.content
            )
            if initial.evidence.batch_receipt is not None:
                _publish_batch_seal(
                    plans_dir=plans_dir, slug=slug, writer_token=writer_token,
                    initial=initial, replacement=replacement, seal=seal,
                )
                return _stored_result(
                    initial=initial, inventory=inventory, answer=answer,
                    replacement=replacement, seal=seal,
                )
            _publish_new_record(
                plans_dir=plans_dir,
                slug=slug,
                writer_token=writer_token,
                path=path,
                data=render_review_seal(seal),
                description="candidate review seal",
                before_replace=(
                    lambda: _require_review_required_predecessor_is_current(
                        plans_dir=plans_dir, slug=slug, initial=initial
                    )
                    if initial.evidence.review_requirement is not None
                    else None
                ),
            )
            return _stored_result(
                initial=initial,
                inventory=inventory,
                answer=answer,
                replacement=replacement,
                seal=seal,
            )
    except (CandidateReviewError, RoadmapVersionError, RoadmapWriterGuardError, OSError) as exc:
        return _result("refused" if isinstance(exc, CandidateReviewError) else "failed", str(exc), 0)


def decide_structural_candidate(
    slug: str,
    candidate_version_id: str,
    decision: Literal["approve", "edit", "reject"],
    *,
    plans_dir: Path,
    repo_root: Path | None = None,
    correction: str | None = None,
    invoker: CandidateReviewInvoker | None = None,
    confirm_digest: str | None = None,
) -> CandidateReviewResult:
    """Apply one closed decision to the exact active structural candidate.

    Approval seals only when ``confirm_digest`` equals the stack digest recomputed under the writer
    guard; the digest confirms an approval and nothing else.
    See docs/implementation-plans/2-roadmap-stack-aware-approval.md § "Architecture" (Digest).
    """
    if decision not in {"approve", "edit", "reject"}:
        return _result("refused", "structural decision is unknown", 0)
    if decision == "approve" and confirm_digest is None:
        return _result("refused", _APPROVAL_DIGEST_REQUIRED, 0)
    if decision != "approve" and confirm_digest is not None:
        return _result("refused", "a stack digest confirms a structural approval only", 0)
    if decision == "reject":
        try:
            _require_structural_candidate(
                _load_admitted_initial_candidate(
                    plans_dir=plans_dir, slug=slug, initial_candidate_version_id=candidate_version_id
                ),
                plans_dir=plans_dir, slug=slug,
            )
        except (CandidateReviewError, RoadmapVersionError) as exc:
            return _result("refused", str(exc), 0)
        return reject_candidate_review(slug, candidate_version_id, plans_dir=plans_dir)
    if decision == "approve":
        try:
            with roadmap_writer_guard(plans_dir, slug) as writer_token:
                candidate = _load_admitted_initial_candidate(
                    plans_dir=plans_dir, slug=slug, initial_candidate_version_id=candidate_version_id
                )
                _require_structural_candidate(candidate, plans_dir=plans_dir, slug=slug)
                view = build_candidate_stack_view(plans_dir=plans_dir, slug=slug, candidate=candidate)
                if view.digest != confirm_digest:
                    raise CandidateReviewError(_APPROVAL_DIGEST_MISMATCH)
                seal = _new_structural_approval_seal(candidate)
                path = review_seal_path(plans_dir, slug, seal.seal_id)
                if path.exists() or path.is_symlink():
                    stored = load_review_seal(plans_dir=plans_dir, slug=slug, seal_id=seal.seal_id)
                    if stored != seal:
                        raise CandidateReviewError("review seal identity collides with conflicting evidence")
                    return _stored_result(initial=candidate, seal=stored)
                _require_no_blocking_narrative_defects(
                    plans_dir=plans_dir, slug=slug, initial=candidate, candidate_content=candidate.content
                )
                admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=slug)
                _publish_new_record(
                    plans_dir=plans_dir, slug=slug, writer_token=writer_token, path=path,
                    data=render_review_seal(seal), description="structural approval seal",
                    before_replace=lambda: _require_active_structural_candidate(
                        plans_dir=plans_dir, slug=slug, candidate=candidate, admission=admission
                    ),
                )
                return _stored_result(initial=candidate, seal=seal)
        except (CandidateReviewError, RoadmapVersionError, RoadmapWriterGuardError, OSError) as exc:
            return _result("refused" if isinstance(exc, CandidateReviewError) else "failed", str(exc), 0)
    if not correction:
        return _result("refused", "structural edit requires one nonempty correction", 0)
    if repo_root is None:
        return _result("refused", "structural edit requires a repository root", 0)
    return _edit_structural_candidate(
        slug, candidate_version_id, correction, repo_root=repo_root, plans_dir=plans_dir, invoker=invoker
    )


@dataclass(frozen=True)
class CandidateStackView:
    """One candidate's whole unpromoted stack, described from stored records alone.

    ``hops`` runs oldest first and ends at the candidate; the recorded root is not a hop. The digest
    covers structured facts, never printed text.
    See docs/implementation-plans/2-roadmap-stack-aware-approval.md § "Architecture" (Stack view, Digest).
    """

    root_version_id: str
    hops: tuple[roadmap_candidate_run.StoredCandidateProposal, ...]
    cumulative_diff: RoadmapDiff

    @property
    def promoted_version_ids(self) -> tuple[str, ...]:
        """Every hop is promoted together with the top candidate."""
        return tuple(hop.version_id for hop in self.hops)

    @property
    def structural_version_ids(self) -> tuple[str, ...]:
        """The hops whose stored route is STRUCTURAL, which make enrolled seed state invalidate."""
        return tuple(
            hop.version_id
            for hop in self.hops
            if hop.evidence.operation_classification
            is roadmap_candidate.CandidateOperationClassification.STRUCTURAL
        )

    @property
    def digest(self) -> str:
        """Hex sha256 of the view's facts; it moves when any covered fact, the hop set, or the hop order moves."""
        return _identity(_stack_view_identity_input(self))


def _correction_identity_input(evidence: Any) -> dict[str, object]:
    corrections = roadmap_candidate.candidate_prose_correction_diffs(
        evidence.normalized_operations, getattr(evidence, "capsule", None)
    )
    return {"corrections": corrections} if corrections else {}


def _stack_view_identity_input(view: CandidateStackView) -> dict[str, object]:
    """The facts the digest covers. A hop with no stored route keeps an explicit ``None`` route.

    A hop with correct-prose operations also covers each correction's stored before and after text
    under ``corrections``; a hop without any omits the key, so stacks without corrections keep
    their prior digest.
    """
    return {
        "kind": "structural-stack-view",
        "root_version_id": view.root_version_id,
        "hops": [
            {
                "version_id": hop.version_id,
                "route": hop.evidence.operation_classification,
                "batch_receipt_identity": (
                    None if hop.evidence.batch_receipt is None else hop.evidence.batch_receipt.capsule_identity
                ),
                "selected_feedback": (
                    () if hop.evidence.batch_receipt is None else hop.evidence.batch_receipt.reviewer_items
                ),
                "typed_operations": hop.evidence.normalized_operations,
                "own_diff": hop.evidence.predecessor_diff,
                **_correction_identity_input(hop.evidence),
            }
            for hop in view.hops
        ],
        "cumulative_diff": view.cumulative_diff,
    }


def build_candidate_stack_view(
    *, plans_dir: Path, slug: str, candidate: roadmap_candidate_run.StoredCandidateProposal
) -> CandidateStackView:
    """Describe the candidate's whole unpromoted stack, refusing when any part cannot be derived.

    Reads only the candidate's id and recorded root: every hop and both diff endpoints are reloaded
    from stored records, so an in-memory edit of ``candidate`` cannot change the view or its digest.
    Read-only, and it does not judge whether the stack is structural.
    """
    root_version_id = candidate.evidence.root_version_id
    if root_version_id is None:
        raise CandidateReviewError("candidate records no accepted root, so its stack cannot be viewed")
    try:
        stack = roadmap_candidate_run.candidate_stack_route(
            plans_dir=plans_dir, slug=slug,
            tip_version_id=candidate.version_id, root_version_id=root_version_id,
        )
        root = roadmap_candidate_run._load_resolved_version(
            plans_dir=plans_dir, slug=slug, version_id=root_version_id
        )
    except roadmap_candidate_run.CandidateProposalError as exc:
        raise CandidateReviewError(f"candidate stack is underivable: {exc}") from exc
    if not stack.hops:
        raise CandidateReviewError("candidate stack is underivable: no candidate sits above the recorded root")
    tip = stack.hops[-1]
    tip_version = ResolvedRoadmapVersion(
        record=tip.record, brief_bytes=tip.content.brief_bytes, artifact_bytes=tip.content.artifact_bytes
    )
    endpoints = []
    for endpoint in (root, tip_version):
        parsed = roadmap_candidate._parse_predecessor_artifacts(endpoint, STAGES)
        if isinstance(parsed, roadmap_candidate.CandidateRefusal):
            raise CandidateReviewError(f"candidate stack cumulative diff is underivable: {parsed.detail}")
        endpoints.append(parsed)
    (root_artifacts, root_bytes), (tip_artifacts, tip_bytes) = endpoints
    return CandidateStackView(
        root_version_id=root_version_id,
        hops=stack.hops,
        cumulative_diff=build_roadmap_diff(
            predecessor_artifacts=root_artifacts,
            candidate_artifacts=tip_artifacts,
            predecessor_bytes=root_bytes,
            candidate_artifacts_bytes=tip_bytes,
            stages=STAGES,
        ),
    )


def _stack_is_structural(
    *, plans_dir: Path, slug: str, tip_version_id: str, root_version_id: str | None
) -> bool:
    """Whether the unpromoted stack ending at the tip stores a STRUCTURAL route.

    An underivable stack refuses here, so no guard reads "cannot tell" as "not structural".
    """
    try:
        return roadmap_candidate_run.candidate_stack_route(
            plans_dir=plans_dir, slug=slug,
            tip_version_id=tip_version_id, root_version_id=root_version_id,
        ).is_structural
    except roadmap_candidate_run.CandidateProposalError as exc:
        raise CandidateReviewError(f"candidate stack route is underivable: {exc}") from exc


def _require_structural_candidate(
    candidate: roadmap_candidate_run.StoredCandidateProposal, *, plans_dir: Path, slug: str
) -> None:
    evidence = candidate.evidence
    if (
        evidence.batch_receipt is None
        or evidence.normalized_operations is None
        or not _stack_is_structural(
            plans_dir=plans_dir, slug=slug,
            tip_version_id=candidate.version_id, root_version_id=evidence.root_version_id,
        )
    ):
        raise CandidateReviewError("candidate is not a stored structural proposal")


def _require_answered_review_route(
    candidate: roadmap_candidate_run.StoredCandidateProposal, *, plans_dir: Path, slug: str
) -> None:
    if _stack_is_structural(
        plans_dir=plans_dir, slug=slug,
        tip_version_id=candidate.version_id, root_version_id=candidate.evidence.root_version_id,
    ):
        raise CandidateReviewError("structural candidate requires --decide-candidate")


def _require_active_structural_candidate(
    *, plans_dir: Path, slug: str, candidate: roadmap_candidate_run.StoredCandidateProposal,
    admission: roadmap_candidate_run.CandidateProposalAdmission | None,
) -> None:
    _require_active_candidate_unchanged(
        plans_dir=plans_dir, slug=slug, candidate=candidate, admission=admission
    )
    _require_structural_candidate(candidate, plans_dir=plans_dir, slug=slug)


def _require_active_candidate_unchanged(
    *, plans_dir: Path, slug: str, candidate: roadmap_candidate_run.StoredCandidateProposal,
    admission: roadmap_candidate_run.CandidateProposalAdmission | None,
) -> None:
    current = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=slug)
    if current != admission:
        raise CandidateReviewError("active candidate pointer changed before structural decision")
    if current is None:
        raise CandidateReviewError("roadmap has no active candidate pointer")
    try:
        reloaded = roadmap_candidate_run.load_stored_candidate_proposal(
            plans_dir=plans_dir, slug=slug, candidate_version_id=candidate.version_id
        )
    except roadmap_candidate_run.CandidateProposalError as exc:
        raise CandidateReviewError("active candidate changed before structural decision") from exc
    if reloaded != candidate:
        raise CandidateReviewError("active candidate changed before structural decision")
    _validate_initial_candidate(candidate, admission=current, slug=slug)


def _edit_structural_candidate(
    slug: str, candidate_version_id: str, correction: str, *, repo_root: Path,
    plans_dir: Path, invoker: CandidateReviewInvoker | None,
) -> CandidateReviewResult:
    """Materialize and activate an unsealed structural replacement in one generation."""
    logger = RunLogWriter.start(
        repo_root=repo_root,
        slug=slug,
        command="roadmap",
        argv=["plan-tool", "roadmap", slug, "--decide-candidate", candidate_version_id, "--candidate-decision", "edit"],
        flags={"mode": "candidate-structural-edit"},
    )
    invoke = invoker or (lambda prompt: shell_candidate_review_invoker(prompt, phase=_STRUCTURAL_EDIT_PHASE))
    result: CandidateReviewResult | None = None
    call_count = 0
    last_response: roadmap_candidate_run.CandidateModelInvocation | None = None
    response_accepted = False
    started_at = time.monotonic()
    logger.phase_start(_STRUCTURAL_EDIT_PHASE)
    try:
        with roadmap_writer_guard(plans_dir, slug) as writer_token:
            initial = _load_admitted_initial_candidate(
                plans_dir=plans_dir, slug=slug, initial_candidate_version_id=candidate_version_id
            )
            _require_structural_candidate(initial, plans_dir=plans_dir, slug=slug)
            admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=slug)
            _require_active_structural_candidate(
                plans_dir=plans_dir, slug=slug, candidate=initial, admission=admission
            )
            evidence = initial.evidence
            capsule = cast(CandidateContextCapsule, evidence.capsule)
            receipt = evidence.batch_receipt
            if receipt is None or evidence.root_version_id is None or evidence.source_version_id is None:
                raise CandidateReviewError("structural edit has incomplete batch bindings")
            pair = roadmap_candidate_run.CandidateReviewPair(
                question_id=_identity({"candidate": initial.version_id, "kind": "structural-edit"}),
                anchor=initial.version_id,
                question_text="Apply this structural review correction.",
                answer_id=_identity({"candidate": initial.version_id, "correction": correction}),
                answer_text=correction,
            )
            predecessor = roadmap_candidate_run._load_resolved_version(
                plans_dir=plans_dir, slug=slug, version_id=evidence.source_version_id
            )
            call_count = 1
            prompt = roadmap_candidate_run.render_candidate_delta_prompt(
                capsule=capsule, receipt=receipt, review_pair=pair, source=predecessor
            )
            invocation = _invoke_once(
                invoke=invoke, logger=logger, phase=_STRUCTURAL_EDIT_PHASE, prompt=prompt, attempt=1
            )
            last_response = invocation
            if invocation.rc != 0:
                result = _result("failed", "structural edit backend request failed", call_count)
                return result
            try:
                delta = roadmap_candidate_run.parse_candidate_proposal_response(
                    invocation.response, capsule=capsule, allow_expansion=False
                )
            except roadmap_candidate_run.CandidateProposalResponseError as exc:
                result = _result("response-rejected", str(exc), call_count)
                return result
            if isinstance(delta, roadmap_candidate_run.CandidateExpansionRequest):
                result = _result("response-rejected", "structural edit response has no delta", call_count)
                return result
            materialized = roadmap_candidate.materialize_candidate(
                delta, predecessor=predecessor, capsule=roadmap_candidate_run._hydrate_capsule(capsule), receipt=receipt
            ).batch_candidate
            if materialized is None:
                result = _result("response-rejected", "structural edit candidate materialization refused", call_count)
                return result
            # The replacement is not stored yet, so its stack is its own route plus its source's stack.
            if (
                materialized.operation_classification
                is not roadmap_candidate.CandidateOperationClassification.STRUCTURAL
                and not _stack_is_structural(
                    plans_dir=plans_dir, slug=slug,
                    tip_version_id=evidence.source_version_id, root_version_id=evidence.root_version_id,
                )
            ):
                result = _result("response-rejected", "structural edit replacement is not structural", call_count)
                return result
            # The response is accepted from here on: a later storage failure must not
            # mislabel it as a rejected response.
            response_accepted = True
            replacement = _store_active_structural_replacement(
                plans_dir=plans_dir, slug=slug, writer_token=writer_token, initial=initial,
                admission=cast(roadmap_candidate_run.CandidateProposalAdmission, admission),
                predecessor=predecessor, materialized=materialized, capsule=capsule,
            )
            result = _stored_result(initial=initial, active_candidate=replacement, call_count=call_count)
            return result
    except KeyboardInterrupt:
        result = _interrupted_result(
            logger, phase=_STRUCTURAL_EDIT_PHASE, call_count=call_count, detail="structural edit interrupted"
        )
        return result
    except (CandidateReviewError, roadmap_candidate_run.CandidateProposalError, RoadmapVersionError,
            RoadmapWriterGuardError, OSError) as exc:
        refused = isinstance(exc, (CandidateReviewError, roadmap_candidate_run.CandidateProposalError))
        result = _result("refused" if refused else "failed", str(exc), call_count)
        return result
    finally:
        terminal = result or _result("failed", "structural edit did not finish", call_count)
        _finish_log(
            logger,
            _STRUCTURAL_EDIT_PHASE,
            started_at,
            terminal,
            expansion_used=False,
            last_response=last_response,
            response_accepted=response_accepted,
        )


def _store_active_structural_replacement(
    *, plans_dir: Path, slug: str, writer_token: object,
    initial: roadmap_candidate_run.StoredCandidateProposal,
    admission: roadmap_candidate_run.CandidateProposalAdmission,
    predecessor: roadmap_candidate_run.ResolvedRoadmapVersion,
    materialized: roadmap_candidate.BatchGateCleanCandidate,
    capsule: CandidateContextCapsule,
) -> roadmap_candidate_run.StoredCandidateProposal:
    """Publish replacement bytes, pointer, supersession, and selected ledger effects together."""
    evidence = initial.evidence
    receipt = evidence.batch_receipt
    if receipt is None or evidence.root_version_id is None or evidence.source_version_id is None:
        raise CandidateReviewError("structural edit has incomplete batch bindings")
    content = RoadmapVersionContent(predecessor.brief_bytes, tuple(item.data for item in materialized.artifacts))
    record = create_candidate_version(
        roadmap_slug=slug, predecessor_version_id=predecessor.record.version_id,
        content_identity=materialized.content_identity,
        review_lineage_identity=INITIAL_EMPTY_REVIEW_LINEAGE_ID,
        brief_digest=_digest(content.brief_bytes), artifact_digests=sha256_digests(content.artifact_bytes),
    )
    candidate_evidence = roadmap_candidate_run.CandidateProposalEvidence(
        schema_version=roadmap_candidate_run._SCHEMA_VERSION, roadmap_slug=slug,
        candidate_version_id=record.version_id, predecessor_version_id=predecessor.record.version_id,
        review_lineage_identity=INITIAL_EMPTY_REVIEW_LINEAGE_ID,
        raw_brief_digest=_digest(content.brief_bytes), artifact_digests=sha256_digests(content.artifact_bytes),
        content_identity=materialized.content_identity, predecessor_diff=materialized.predecessor_diff,
        gate_evidence=tuple(roadmap_candidate_run.CandidateGateEvidence(artifact_key=x.stage.artifact_key, violations=()) for x in materialized.gate_outcomes),
        capsule=capsule, receipt=receipt, expansion_available=False,
        root_version_id=evidence.root_version_id, source_version_id=evidence.source_version_id,
        batch_receipt=receipt, normalized_operations=materialized.normalized_operations,
        operation_classification=materialized.operation_classification,
    )
    candidate = roadmap_candidate_run.StoredCandidateProposal(record, content, candidate_evidence)
    roadmap_candidate_run._validate_candidate_evidence(candidate, plans_dir=plans_dir, slug=slug)
    ledger_path = roadmap_feedback_ledger_path(plans_dir, slug)
    ledger_bytes = ledger_path.read_bytes()
    ledger = load_ledger(ledger_path)
    updated_ledger = roadmap_candidate_run.apply_replacement_ledger_patch(
        ledger, reviewed_candidate_version_id=initial.version_id, replacement_version_id=record.version_id,
        response_patch=materialized.response_patch, derived_feedback=materialized.derived_feedback,
    )
    root = version_namespace_path(plans_dir, slug).parent
    candidate_dir = version_directory_path(plans_dir, slug, record.version_id)
    members = [
        GenerationMember((candidate_dir / member.member_name).relative_to(root).as_posix(), None, member.data)
        for member in stored_version_members(PreparedRoadmapVersion(record, content))
    ]
    evidence_path = roadmap_candidate_run.candidate_evidence_path(plans_dir, slug, record.version_id)
    if evidence_path.exists() or evidence_path.is_symlink() or candidate_dir.exists():
        raise CandidateReviewError("structural replacement identity collides with existing storage")
    members.extend((
        GenerationMember(evidence_path.relative_to(root).as_posix(), None, roadmap_candidate_run.render_candidate_evidence(candidate_evidence)),
        roadmap_candidate_run.build_supersession_member(plans_dir=plans_dir, slug=slug, admission=admission, successor_version_id=record.version_id),
        roadmap_candidate_run.build_active_candidate_pointer_member(plans_dir=plans_dir, slug=slug, previous=admission, root_version_id=evidence.root_version_id, candidate_version_id=record.version_id),
        GenerationMember(ledger_path.relative_to(root).as_posix(), ledger_bytes, render_ledger(updated_ledger)),
    ))
    def final_recheck() -> None:
        _require_active_structural_candidate(
            plans_dir=plans_dir, slug=slug, candidate=initial, admission=admission
        )
        roadmap_candidate_run.require_batch_state_unchanged(
            plans_dir=plans_dir, slug=slug, admission=admission, ledger_bytes=ledger_bytes
        )

    publish_roadmap_generation(
        PendingGeneration(kind="structural-candidate-edit", members=tuple(members)), plans_dir=plans_dir,
        slug=slug, writer_token=cast(Any, writer_token),
        before_replace=final_recheck,
    )
    refresh_roadmap_index(plans_dir, slug)
    return candidate


def answer_candidate_question(
    slug: str,
    question_id: str,
    answer_text: str,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: CandidateReviewInvoker | None = None,
    run_logger: RunLogWriter | None = None,
    question_inventory_id: str | None = None,
) -> CandidateReviewResult:
    """Record an answer, materialize its replacement, then seal that exact pair."""
    recorded = record_reviewer_answer(
        slug,
        question_id,
        answer_text,
        plans_dir=plans_dir,
        question_inventory_id=question_inventory_id,
    )
    if recorded.outcome != "stored":
        return recorded
    requested = request_replacement(
        slug,
        question_id,
        answer_text,
        repo_root=repo_root,
        plans_dir=plans_dir,
        invoker=invoker,
        run_logger=run_logger,
        question_inventory_id=question_inventory_id,
    )
    if requested.outcome != "stored" or requested.replacement is None:
        return requested
    sealed = seal_review(slug, requested.replacement.version_id, plans_dir=plans_dir)
    if sealed.outcome != "stored":
        return sealed
    return CandidateReviewResult(
        outcome="stored",
        initial_candidate=requested.initial_candidate,
        question_inventory=requested.question_inventory,
        answer=requested.answer,
        replacement=requested.replacement,
        seal=sealed.seal,
        call_count=requested.call_count,
    )


def reject_candidate_review(
    slug: str, candidate_version_id: str, *, plans_dir: Path
) -> CandidateReviewResult:
    """Record a rejection and release precisely the currently active candidate."""
    return _release_active_candidate(slug, candidate_version_id, plans_dir=plans_dir, reason="rejected")


def discard_candidate_review(
    slug: str, candidate_version_id: str, *, plans_dir: Path
) -> CandidateReviewResult:
    """Record an explicit discard and release precisely the active candidate."""
    return _release_active_candidate(slug, candidate_version_id, plans_dir=plans_dir, reason="discarded")


def _release_active_candidate(
    slug: str, candidate_version_id: str, *, plans_dir: Path,
    reason: Literal["rejected", "discarded"],
) -> CandidateReviewResult:
    try:
        with roadmap_writer_guard(plans_dir, slug) as writer_token:
            candidate = _load_admitted_initial_candidate(
                plans_dir=plans_dir, slug=slug, initial_candidate_version_id=candidate_version_id
            )
            evidence = candidate.evidence
            if evidence.batch_receipt is None or evidence.root_version_id is None or evidence.source_version_id is None:
                raise CandidateReviewError("terminal review resolution requires an active batch candidate")
            admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=slug)
            if admission is None:
                raise CandidateReviewError("roadmap has no active candidate pointer")
            resolution = roadmap_candidate_run.new_terminal_resolution(candidate, reason=reason)
            generation = roadmap_candidate_run.build_terminal_resolution_generation(
                plans_dir=plans_dir, slug=slug, admission=admission, resolution=resolution
            )
            def _still_active() -> None:
                _require_active_candidate_unchanged(
                    plans_dir=plans_dir, slug=slug, candidate=candidate, admission=admission
                )
            publish_roadmap_generation(
                generation,
                plans_dir=plans_dir, slug=slug, writer_token=cast(Any, writer_token), before_replace=_still_active,
            )
            refresh_roadmap_index(plans_dir, slug)
            return _stored_result(initial=candidate)
    except (
        CandidateReviewError, roadmap_candidate_run.CandidateProposalError,
        RoadmapVersionError, RoadmapWriterGuardError, OSError,
    ) as exc:
        refused = isinstance(exc, (CandidateReviewError, roadmap_candidate_run.CandidateProposalError))
        return _result("refused" if refused else "failed", str(exc), 0)


def load_review_seal(*, plans_dir: Path, slug: str, seal_id: str) -> CandidateReviewSeal:
    """Load one exact seal without selecting a candidate or accepted head."""
    path = review_seal_path(plans_dir, slug, seal_id)
    try:
        seal = parse_review_seal(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise CandidateReviewError("candidate review seal is unreadable") from exc
    if seal.roadmap_slug != slug or seal.seal_id != seal_id:
        raise CandidateReviewError("candidate review seal does not match its requested identity")
    return seal


def load_stored_candidate_review_replacement(
    *, plans_dir: Path, slug: str, candidate_version_id: str
) -> StoredCandidateReviewReplacement:
    """Load one answer-bound replacement and exact bytes without any live reconstruction."""
    try:
        record = load_stored_version(
            plans_dir=plans_dir, slug=slug, version_id=candidate_version_id
        )
    except RoadmapVersionError as exc:
        raise CandidateReviewError("replacement candidate version is unreadable") from exc
    if record.version_kind != "candidate" or record.review_lineage_identity == INITIAL_EMPTY_REVIEW_LINEAGE_ID:
        raise CandidateReviewError("replacement binding does not name an answer-bound candidate")
    content = RoadmapVersionContent(
        brief_bytes=_read_member(
            stored_brief_path(plans_dir, slug, candidate_version_id),
            expected_digest=record.brief_digest,
            description="replacement recorded brief",
        ),
        artifact_bytes=tuple(
            _read_member(
                stored_artifact_path(plans_dir, slug, candidate_version_id, member.artifact_key),
                expected_digest=member.digest,
                description=f"replacement artifact {member.artifact_key}",
            )
            for member in record.artifact_members
        ),
    )
    path = replacement_evidence_path(plans_dir, slug, candidate_version_id)
    try:
        evidence = parse_replacement_evidence(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise CandidateReviewError("candidate review replacement is unreadable") from exc
    if (
        evidence.roadmap_slug != slug
        or evidence.candidate_version_id != candidate_version_id
        or evidence.predecessor_version_id != record.predecessor_version_id
        or evidence.review_lineage_identity != record.review_lineage_identity
        or evidence.content_identity != record.content_identity
        or evidence.raw_brief_digest != record.brief_digest
        or evidence.artifact_digests != tuple(member.digest for member in record.artifact_members)
    ):
        raise CandidateReviewError("candidate review replacement does not bind its stored version")
    return StoredCandidateReviewReplacement(record=record, content=content, evidence=evidence)


def _load_admitted_initial_candidate(
    *, plans_dir: Path, slug: str, initial_candidate_version_id: str
) -> roadmap_candidate_run.StoredCandidateProposal:
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=slug)
    if admission is None or admission.candidate_version_id is None:
        raise CandidateReviewError("roadmap has no stored admitted initial candidate")
    if admission.candidate_version_id != initial_candidate_version_id:
        raise CandidateReviewError("candidate review accepts only the admitted initial candidate")
    initial = roadmap_candidate_run.load_stored_candidate_proposal(
        plans_dir=plans_dir, slug=slug, candidate_version_id=initial_candidate_version_id
    )
    _validate_initial_candidate(initial, admission=admission, slug=slug)
    return initial


def _load_admitted_initial_candidate_from_admission(
    *, plans_dir: Path, slug: str
) -> roadmap_candidate_run.StoredCandidateProposal:
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=slug)
    if admission is None or admission.candidate_version_id is None:
        raise CandidateReviewError("roadmap has no stored admitted initial candidate")
    initial = _load_admitted_initial_candidate(
        plans_dir=plans_dir, slug=slug, initial_candidate_version_id=admission.candidate_version_id
    )
    _require_answered_review_route(initial, plans_dir=plans_dir, slug=slug)
    return initial


def _validate_initial_candidate(
    initial: roadmap_candidate_run.StoredCandidateProposal,
    *,
    admission: roadmap_candidate_run.CandidateProposalAdmission,
    slug: str,
) -> None:
    evidence = initial.evidence
    if evidence.batch_receipt is not None:
        receipt = evidence.batch_receipt
        if (
            evidence.roadmap_slug != slug
            or evidence.candidate_version_id != initial.version_id
            or admission.root_version_id != evidence.root_version_id
            or admission.predecessor_version_id != evidence.root_version_id
            or admission.active_candidate_version_id != initial.version_id
            or admission.candidate_version_id != initial.version_id
            or evidence.source_version_id != evidence.predecessor_version_id
            or receipt.root.version_id != evidence.root_version_id
            or receipt.source.version_id != evidence.source_version_id
            or evidence.content_identity != initial.record.content_identity
        ):
            raise CandidateReviewError("active candidate does not bind its stored root, source, and batch")
        return
    if (
        initial.record.review_lineage_identity != INITIAL_EMPTY_REVIEW_LINEAGE_ID
        or evidence.review_lineage_identity != INITIAL_EMPTY_REVIEW_LINEAGE_ID
        or evidence.roadmap_slug != slug
        or evidence.candidate_version_id != initial.version_id
        or admission.candidate_version_id != initial.version_id
        or evidence.predecessor_version_id != admission.predecessor_version_id
        or evidence.feedback != admission.feedback
        or evidence.capsule != admission.capsule
        or evidence.receipt != admission.receipt
        or evidence.expansion_available != admission.expansion_available
        or evidence.content_identity != initial.record.content_identity
    ):
        raise CandidateReviewError("admitted initial candidate facts are inconsistent")


def _load_question_inventory_if_present(
    *, plans_dir: Path, slug: str, initial: roadmap_candidate_run.StoredCandidateProposal
) -> CandidateQuestionInventory | None:
    path = question_inventory_path(plans_dir, slug, initial.version_id)
    if not path.exists():
        if path.is_symlink():
            raise CandidateReviewError("candidate question inventory is a dangling symlink")
        return None
    inventory = _load_question_inventory(path)
    _validate_inventory(inventory, initial=initial)
    return inventory


def _require_question_inventory(
    *, plans_dir: Path, slug: str, initial: roadmap_candidate_run.StoredCandidateProposal
) -> CandidateQuestionInventory:
    inventory = _load_question_inventory_if_present(plans_dir=plans_dir, slug=slug, initial=initial)
    if inventory is None:
        raise CandidateReviewError("candidate question inventory has not been generated")
    return inventory


def _load_question_inventory(path: Path) -> CandidateQuestionInventory:
    try:
        return parse_question_inventory(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise CandidateReviewError("candidate question inventory is unreadable") from exc


def _validate_inventory(
    inventory: CandidateQuestionInventory,
    *,
    initial: roadmap_candidate_run.StoredCandidateProposal,
) -> None:
    evidence = initial.evidence
    if evidence.batch_receipt is not None:
        receipt = evidence.batch_receipt
        if (
            inventory.initial_candidate_version_id != initial.version_id
            or inventory.initial_content_identity != evidence.content_identity
            or inventory.predecessor_version_id != evidence.predecessor_version_id
            or inventory.root_version_id != evidence.root_version_id
            or inventory.source_version_id != evidence.source_version_id
            or inventory.batch_receipt_identity != receipt.capsule_identity
            or inventory.capsule_identity != evidence.capsule.capsule_identity
            or inventory.predecessor_diff != evidence.predecessor_diff
            or inventory.feedback is not None
            or inventory.review_requirement is not None
            or not _anchor_resolves(inventory.question.anchor, candidate=initial)
        ):
            raise CandidateReviewError("question inventory does not bind stored active candidate batch")
        return
    if (
        inventory.initial_candidate_version_id != initial.version_id
        or inventory.initial_content_identity != evidence.content_identity
        or inventory.predecessor_version_id != evidence.predecessor_version_id
        or inventory.feedback != evidence.feedback
        or inventory.predecessor_diff != evidence.predecessor_diff
        or inventory.capsule_identity != evidence.capsule.capsule_identity
        or inventory.review_requirement != evidence.review_requirement
        or not _anchor_resolves(inventory.question.anchor, candidate=initial)
    ):
        raise CandidateReviewError("candidate question inventory does not bind stored initial facts")


def _new_question_inventory(
    *, initial: roadmap_candidate_run.StoredCandidateProposal, question: CandidateQuestion
) -> CandidateQuestionInventory:
    evidence = initial.evidence
    if evidence.batch_receipt is not None:
        # A batch has no selected feedback row; retain that absence explicitly.
        feedback = None
        batch_identity = evidence.batch_receipt.capsule_identity
        inventory_id = _identity(_question_inventory_preimage(
            initial_candidate_version_id=initial.version_id,
            initial_content_identity=evidence.content_identity,
            predecessor_version_id=evidence.predecessor_version_id,
            feedback=feedback,
            predecessor_diff=evidence.predecessor_diff,
            capsule_identity=evidence.capsule.capsule_identity,
            question=question,
            review_requirement=None,
            root_version_id=evidence.root_version_id,
            source_version_id=evidence.source_version_id,
            batch_receipt_identity=batch_identity,
        ))
        return CandidateQuestionInventory(
            schema_version=_SCHEMA_VERSION, inventory_id=inventory_id,
            initial_candidate_version_id=initial.version_id,
            initial_content_identity=evidence.content_identity,
            predecessor_version_id=evidence.predecessor_version_id, feedback=feedback,
            predecessor_diff=evidence.predecessor_diff,
            capsule_identity=evidence.capsule.capsule_identity, question=question,
            root_version_id=evidence.root_version_id, source_version_id=evidence.source_version_id,
            batch_receipt_identity=batch_identity,
        )
    inventory_id = _identity(
        _question_inventory_preimage(
            initial_candidate_version_id=initial.version_id,
            initial_content_identity=evidence.content_identity,
            predecessor_version_id=evidence.predecessor_version_id,
            feedback=evidence.feedback,
            predecessor_diff=evidence.predecessor_diff,
            capsule_identity=evidence.capsule.capsule_identity,
            question=question,
            review_requirement=evidence.review_requirement,
        )
    )
    return CandidateQuestionInventory(
        schema_version=_SCHEMA_VERSION,
        inventory_id=inventory_id,
        initial_candidate_version_id=initial.version_id,
        initial_content_identity=evidence.content_identity,
        predecessor_version_id=evidence.predecessor_version_id,
        feedback=evidence.feedback,
        predecessor_diff=evidence.predecessor_diff,
        capsule_identity=evidence.capsule.capsule_identity,
        question=question,
        review_requirement=evidence.review_requirement,
    )


def _inventory_preimage(inventory: CandidateQuestionInventory) -> dict[str, object]:
    return _question_inventory_preimage(
        initial_candidate_version_id=inventory.initial_candidate_version_id,
        initial_content_identity=inventory.initial_content_identity,
        predecessor_version_id=inventory.predecessor_version_id,
        feedback=inventory.feedback,
        predecessor_diff=inventory.predecessor_diff,
        capsule_identity=inventory.capsule_identity,
        question=inventory.question,
        review_requirement=inventory.review_requirement,
        root_version_id=inventory.root_version_id,
        source_version_id=inventory.source_version_id,
        batch_receipt_identity=inventory.batch_receipt_identity,
    )


def _question_inventory_preimage(
    *,
    initial_candidate_version_id: str,
    initial_content_identity: str,
    predecessor_version_id: str,
    feedback: CandidateContextFeedback | None,
    predecessor_diff: roadmap_candidate.CandidatePredecessorDiff,
    capsule_identity: str,
    question: CandidateQuestion,
    review_requirement: roadmap_candidate.CandidateReviewRequirement | None,
    root_version_id: str | None = None,
    source_version_id: str | None = None,
    batch_receipt_identity: str | None = None,
) -> dict[str, object]:
    """Return the exact facts admitted to one question inventory identity."""
    preimage: dict[str, object] = {
        "schema_version": _SCHEMA_VERSION,
        "initial_candidate_version_id": initial_candidate_version_id,
        "initial_content_identity": initial_content_identity,
        "predecessor_version_id": predecessor_version_id,
        "feedback": feedback,
        "predecessor_diff": predecessor_diff,
        "capsule_identity": capsule_identity,
        "question": question,
    }
    if review_requirement is not None:
        preimage["review_requirement"] = review_requirement
    if root_version_id is not None:
        preimage["root_version_id"] = root_version_id
        preimage["source_version_id"] = source_version_id
        preimage["batch_receipt_identity"] = batch_receipt_identity
    return preimage


def _new_answer(*, inventory: CandidateQuestionInventory, answer_text: str) -> CandidateReviewAnswer:
    return CandidateReviewAnswer(
        schema_version=_SCHEMA_VERSION,
        answer_id=_identity(
            {
                "schema_version": _SCHEMA_VERSION,
                "inventory_id": inventory.inventory_id,
                "question_id": inventory.question.question_id,
                "answer_text": answer_text,
            }
        ),
        inventory_id=inventory.inventory_id,
        question_id=inventory.question.question_id,
        answer_text=answer_text,
    )


def _load_reviewer_answer(path: Path) -> CandidateReviewAnswer:
    try:
        return parse_reviewer_answer(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise CandidateReviewError("candidate reviewer answer is unreadable") from exc


def _validate_answer(answer: CandidateReviewAnswer, *, inventory: CandidateQuestionInventory) -> None:
    if (
        answer.inventory_id != inventory.inventory_id
        or answer.question_id != inventory.question.question_id
    ):
        raise CandidateReviewError("candidate reviewer answer does not bind its question inventory")


def _require_stored_answer(
    *,
    plans_dir: Path,
    slug: str,
    initial: roadmap_candidate_run.StoredCandidateProposal,
    inventory: CandidateQuestionInventory,
    answer_text: str | None,
) -> CandidateReviewAnswer:
    path = reviewer_answer_path(plans_dir, slug, initial.version_id)
    if not path.exists() and not path.is_symlink():
        raise CandidateReviewError("candidate reviewer answer has not been recorded")
    answer = _load_reviewer_answer(path)
    _validate_answer(answer, inventory=inventory)
    if answer_text is not None and answer.answer_text != answer_text:
        raise CandidateReviewError("replacement answer does not match the immutable stored answer")
    return answer


def _require_no_blocking_narrative_defects(
    *,
    plans_dir: Path,
    slug: str,
    initial: roadmap_candidate_run.StoredCandidateProposal,
    candidate_content: RoadmapVersionContent,
) -> None:
    """Refuse approval while live prose names a removed row; evidence is recomputed, never stored.

    See ROADMAP_FORMAT.md § "Narrative review evidence".
    """
    try:
        predecessor = roadmap_candidate_run._load_resolved_version(
            plans_dir=plans_dir, slug=slug, version_id=initial.evidence.predecessor_version_id
        )
        evidence = roadmap_candidate_narrative.candidate_narrative_evidence_from_bytes(
            dict(zip(VERSION_ARTIFACT_KEYS, candidate_content.artifact_bytes, strict=True)),
            predecessor,
            feedback_free=initial.evidence.batch_receipt is not None,
        )
    except (ValueError, RoadmapArtifactError) as exc:
        # A load, member-count, decode or parse failure surfaces as the approval path's failed result,
        # not a traceback; nothing is written.
        raise RoadmapVersionError(f"narrative evidence could not be computed: {exc}") from exc
    if not evidence.has_blocking_findings:
        return
    defects = "; ".join(
        f"{finding.artifact} names removed id '{finding.row_id}' ({finding.kind})"
        for finding in evidence.blocking_findings
    )
    exits = "; or ".join(
        dict.fromkeys(path for finding in evidence.blocking_findings for path in finding.correction_path)
    )
    raise CandidateReviewError(
        f"approval refused: live prose names removed rows: {defects}. To clear: {exits}"
    )


def _require_review_required_predecessor_is_current(
    *, plans_dir: Path, slug: str, initial: roadmap_candidate_run.StoredCandidateProposal
) -> None:
    """Keep answer-bound review-required writes attached to the current accepted head."""
    if initial.evidence.review_requirement is None:
        return
    accepted = load_accepted_version(plans_dir=plans_dir, slug=slug)
    if (
        accepted is None
        or accepted.record.version_id != initial.evidence.predecessor_version_id
    ):
        raise CandidateReviewError(
            "review-required replacement predecessor is not the current accepted roadmap head"
        )


def _replacement_capsule(
    *, plans_dir: Path, slug: str, initial: roadmap_candidate_run.StoredCandidateProposal
) -> tuple[CandidateContextCapsule, CandidateContextReceipt]:
    path = replacement_state_path(plans_dir, slug, initial.version_id)
    if initial.evidence.review_requirement is not None:
        if path.exists() or path.is_symlink():
            raise CandidateReviewError(
                "review-required candidate replacements cannot use replacement expansion state"
            )
        return initial.evidence.capsule, initial.evidence.receipt
    if not path.exists() and not path.is_symlink():
        return initial.evidence.capsule, initial.evidence.receipt
    try:
        state = parse_replacement_state(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise CandidateReviewError("candidate replacement state is unreadable") from exc
    if (
        state.initial_candidate_version_id != initial.version_id
        or state.initial_content_identity != initial.evidence.content_identity
        or state.predecessor_version_id != initial.evidence.predecessor_version_id
        or state.feedback != initial.evidence.feedback
        or state.capsule.expansion is None
        or state.capsule.expansion.parent_capsule_identity
        != initial.evidence.capsule.capsule_identity
        or state.capsule.expansion.inventory_entry not in initial.evidence.capsule.inventory
    ):
        raise CandidateReviewError("candidate replacement state does not bind its initial candidate")
    return state.capsule, state.receipt


def _load_replacement_if_present(
    *,
    plans_dir: Path,
    slug: str,
    initial: roadmap_candidate_run.StoredCandidateProposal,
    inventory: CandidateQuestionInventory,
    answer: CandidateReviewAnswer,
) -> StoredCandidateReviewReplacement | None:
    path = replacement_binding_path(plans_dir, slug, initial.version_id)
    if not path.exists() and not path.is_symlink():
        return None
    try:
        binding = parse_replacement_binding(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise CandidateReviewError("candidate replacement binding is unreadable") from exc
    if (
        binding.initial_candidate_version_id != initial.version_id
        or binding.inventory_id != inventory.inventory_id
        or binding.question_id != inventory.question.question_id
        or binding.answer_id != answer.answer_id
    ):
        raise CandidateReviewError("candidate replacement binding does not bind the stored review pair")
    replacement = load_stored_candidate_review_replacement(
        plans_dir=plans_dir, slug=slug, candidate_version_id=binding.candidate_version_id
    )
    _validate_replacement(
        replacement,
        plans_dir=plans_dir,
        slug=slug,
        initial=initial,
        inventory=inventory,
        answer=answer,
    )
    return replacement


def _materialized_impact_atoms(
    materialized: roadmap_candidate.GateCleanCandidate | roadmap_candidate.ReviewRequiredCandidate,
) -> tuple[roadmap_candidate.CandidateImpactAtom, ...]:
    """Read the materializer-derived impact stream from either terminal candidate arm."""
    if isinstance(materialized, roadmap_candidate.ReviewRequiredCandidate):
        return materialized.review_requirement.impact_atoms
    return materialized.impact_atoms


def _store_replacement(
    *,
    plans_dir: Path,
    slug: str,
    writer_token: object,
    initial: roadmap_candidate_run.StoredCandidateProposal,
    inventory: CandidateQuestionInventory,
    answer: CandidateReviewAnswer,
    predecessor: object,
    materialized: roadmap_candidate.GateCleanCandidate | roadmap_candidate.ReviewRequiredCandidate,
    capsule: CandidateContextCapsule,
    receipt: CandidateContextReceipt,
) -> StoredCandidateReviewReplacement:
    if (
        materialized.predecessor_version_id != initial.evidence.predecessor_version_id
        or materialized.selected_feedback != initial.evidence.feedback
        or materialized.capsule_receipt != receipt
        or len(materialized.gate_outcomes) != len(STAGES)
        or any(outcome.stage is not stage for outcome, stage in zip(materialized.gate_outcomes, STAGES, strict=True))
        or any(outcome.violations for outcome in materialized.gate_outcomes)
    ):
        raise CandidateReviewError("replacement materialization does not match stored lineage authority")
    if not isinstance(predecessor, roadmap_candidate_run.ResolvedRoadmapVersion):
        raise CandidateReviewError("replacement predecessor has the wrong stored type")
    initial_requirement = initial.evidence.review_requirement
    if inventory.review_requirement != initial_requirement:
        raise CandidateReviewError("question inventory does not bind the stored review requirement")
    _require_review_required_predecessor_is_current(
        plans_dir=plans_dir,
        slug=slug,
        initial=initial,
    )
    impact_atoms = _materialized_impact_atoms(materialized)
    replacement_requirement = (
        materialized.review_requirement
        if isinstance(materialized, roadmap_candidate.ReviewRequiredCandidate)
        else None
    )
    if initial_requirement is not None and (
        replacement_requirement is not None
        and replacement_requirement.reason != initial_requirement.reason
        or not roadmap_candidate.review_requirement_contains_impact(
            initial_requirement, impact_atoms
        )
    ):
        raise CandidateReviewError("replacement impact exceeds the initial review disclosure")
    incorporation = CandidateAnswerIncorporation(
        incorporation_id=_identity(
            {
                "schema_version": _SCHEMA_VERSION,
                "inventory_id": inventory.inventory_id,
                "question_id": inventory.question.question_id,
                "answer_id": answer.answer_id,
            }
        ),
        inventory_id=inventory.inventory_id,
        question_id=inventory.question.question_id,
        answer_id=answer.answer_id,
    )
    lineage_id = _review_lineage_identity(inventory.inventory_id, answer.answer_id)
    content = RoadmapVersionContent(
        brief_bytes=predecessor.brief_bytes,
        artifact_bytes=tuple(member.data for member in materialized.artifacts),
    )
    record = create_candidate_version(
        roadmap_slug=slug,
        predecessor_version_id=predecessor.record.version_id,
        content_identity=materialized.content_identity,
        review_lineage_identity=lineage_id,
        brief_digest=_digest(content.brief_bytes),
        artifact_digests=sha256_digests(content.artifact_bytes),
    )
    prepared = PreparedRoadmapVersion(record=record, content=content)
    evidence = CandidateReviewReplacement(
        schema_version=_SCHEMA_VERSION,
        roadmap_slug=slug,
        initial_candidate_version_id=initial.version_id,
        candidate_version_id=record.version_id,
        predecessor_version_id=predecessor.record.version_id,
        review_lineage_identity=lineage_id,
        feedback=initial.evidence.feedback,
        raw_brief_digest=_digest(content.brief_bytes),
        artifact_digests=sha256_digests(content.artifact_bytes),
        content_identity=materialized.content_identity,
        predecessor_diff=materialized.predecessor_diff,
        replacement_impact_atoms=impact_atoms,
        replacement_impact_identity=roadmap_candidate.candidate_impact_identity(impact_atoms),
        replacement_review_requirement=replacement_requirement,
        gate_evidence=tuple(
            roadmap_candidate_run.CandidateGateEvidence(
                artifact_key=outcome.stage.artifact_key,
                violations=tuple(violation.message for violation in outcome.violations),
            )
            for outcome in materialized.gate_outcomes
        ),
        capsule=capsule,
        receipt=receipt,
        question_inventory_id=inventory.inventory_id,
        answer_incorporation=incorporation,
    )
    candidate_dir = version_directory_path(plans_dir, slug, record.version_id)
    root = version_namespace_path(plans_dir, slug).parent
    members: list[GenerationMember] = []
    for member in stored_version_members(prepared):
        path = candidate_dir / member.member_name
        if path.exists() or path.is_symlink():
            raise CandidateReviewError("replacement candidate version identity collides with existing storage")
        members.append(GenerationMember(path.relative_to(root).as_posix(), None, member.data))
    evidence_path = replacement_evidence_path(plans_dir, slug, record.version_id)
    if evidence_path.exists() or evidence_path.is_symlink():
        raise CandidateReviewError("replacement evidence identity collides with existing storage")
    members.append(
        GenerationMember(
            evidence_path.relative_to(root).as_posix(), None, render_replacement_evidence(evidence)
        )
    )
    binding_path = replacement_binding_path(plans_dir, slug, initial.version_id)
    if binding_path.exists() or binding_path.is_symlink():
        raise CandidateReviewError("replacement binding already exists")
    binding = CandidateReviewReplacementBinding(
        schema_version=_SCHEMA_VERSION,
        initial_candidate_version_id=initial.version_id,
        inventory_id=inventory.inventory_id,
        question_id=inventory.question.question_id,
        answer_id=answer.answer_id,
        candidate_version_id=record.version_id,
    )
    members.append(
        GenerationMember(
            binding_path.relative_to(root).as_posix(), None, render_replacement_binding(binding)
        )
    )
    publish_roadmap_generation(
        PendingGeneration(kind="candidate-review-replacement", members=tuple(members)),
        plans_dir=plans_dir,
        slug=slug,
        writer_token=cast(Any, writer_token),
        before_replace=(
            lambda: _require_review_required_predecessor_is_current(
                plans_dir=plans_dir, slug=slug, initial=initial
            )
            if initial_requirement is not None
            else None
        ),
    )
    refresh_roadmap_index(plans_dir, slug)
    return load_stored_candidate_review_replacement(
        plans_dir=plans_dir, slug=slug, candidate_version_id=record.version_id
    )


def _store_batch_replacement(
    *,
    plans_dir: Path,
    slug: str,
    writer_token: object,
    initial: roadmap_candidate_run.StoredCandidateProposal,
    inventory: CandidateQuestionInventory,
    answer: CandidateReviewAnswer,
    predecessor: object,
    materialized: roadmap_candidate.BatchGateCleanCandidate,
    capsule: CandidateContextCapsule,
) -> StoredCandidateReviewReplacement:
    """Store one batch replacement immutably; the active pointer stays on the reviewed candidate.

    The replacement applies its delta to the reviewed candidate's own source and
    records that source as its predecessor. The pointer swap, supersession record and
    ledger patch happen when the review is sealed, so sealing still loads the
    reviewed candidate as the active one.
    """
    evidence = initial.evidence
    receipt = evidence.batch_receipt
    if (
        receipt is None
        or evidence.root_version_id is None
        or evidence.source_version_id is None
        or materialized.capsule_receipt != receipt
        or materialized.root_version_id != evidence.root_version_id
        or materialized.predecessor_version_id != evidence.source_version_id
        or len(materialized.gate_outcomes) != len(STAGES)
        or any(
            outcome.stage is not stage or outcome.violations
            for outcome, stage in zip(materialized.gate_outcomes, STAGES, strict=True)
        )
    ):
        raise CandidateReviewError("replacement materialization does not match stored lineage authority")
    if not isinstance(predecessor, roadmap_candidate_run.ResolvedRoadmapVersion):
        raise CandidateReviewError("replacement predecessor has the wrong stored type")
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=slug)
    if admission is None or admission.active_candidate_version_id != initial.version_id:
        raise CandidateReviewError("active candidate pointer changed before replacement storage")
    incorporation = CandidateAnswerIncorporation(
        incorporation_id=_identity(
            {
                "schema_version": _SCHEMA_VERSION,
                "inventory_id": inventory.inventory_id,
                "question_id": inventory.question.question_id,
                "answer_id": answer.answer_id,
            }
        ),
        inventory_id=inventory.inventory_id,
        question_id=inventory.question.question_id,
        answer_id=answer.answer_id,
    )
    lineage_id = _review_lineage_identity(inventory.inventory_id, answer.answer_id)
    content = RoadmapVersionContent(
        brief_bytes=predecessor.brief_bytes,
        artifact_bytes=tuple(member.data for member in materialized.artifacts),
    )
    record = create_candidate_version(
        roadmap_slug=slug,
        predecessor_version_id=predecessor.record.version_id,
        content_identity=materialized.content_identity,
        review_lineage_identity=lineage_id,
        brief_digest=_digest(content.brief_bytes),
        artifact_digests=sha256_digests(content.artifact_bytes),
    )
    prepared = PreparedRoadmapVersion(record=record, content=content)
    gate_evidence = tuple(
        roadmap_candidate_run.CandidateGateEvidence(artifact_key=outcome.stage.artifact_key, violations=())
        for outcome in materialized.gate_outcomes
    )
    replacement_evidence = CandidateReviewReplacement(
        schema_version=_SCHEMA_VERSION,
        roadmap_slug=slug,
        initial_candidate_version_id=initial.version_id,
        candidate_version_id=record.version_id,
        predecessor_version_id=predecessor.record.version_id,
        review_lineage_identity=lineage_id,
        raw_brief_digest=_digest(content.brief_bytes),
        artifact_digests=sha256_digests(content.artifact_bytes),
        content_identity=materialized.content_identity,
        predecessor_diff=materialized.predecessor_diff,
        gate_evidence=gate_evidence,
        question_inventory_id=inventory.inventory_id,
        answer_incorporation=incorporation,
        root_version_id=evidence.root_version_id,
        source_version_id=evidence.source_version_id,
        batch_receipt_identity=receipt.capsule_identity,
        response_patch=materialized.response_patch,
        derived_feedback=materialized.derived_feedback,
    )
    candidate_evidence = roadmap_candidate_run.CandidateProposalEvidence(
        schema_version=roadmap_candidate_run._SCHEMA_VERSION,
        roadmap_slug=slug,
        candidate_version_id=record.version_id,
        predecessor_version_id=predecessor.record.version_id,
        review_lineage_identity=lineage_id,
        raw_brief_digest=_digest(content.brief_bytes),
        artifact_digests=sha256_digests(content.artifact_bytes),
        content_identity=materialized.content_identity,
        predecessor_diff=materialized.predecessor_diff,
        gate_evidence=gate_evidence,
        capsule=capsule,
        receipt=receipt,
        expansion_available=False,
        root_version_id=evidence.root_version_id,
        source_version_id=evidence.source_version_id,
        batch_receipt=receipt,
    )
    roadmap_candidate_run._validate_candidate_evidence(
        roadmap_candidate_run.StoredCandidateProposal(record, content, candidate_evidence),
        plans_dir=plans_dir,
        slug=slug,
    )
    candidate_dir = version_directory_path(plans_dir, slug, record.version_id)
    root = version_namespace_path(plans_dir, slug).parent
    members: list[GenerationMember] = []
    for member in stored_version_members(prepared):
        path = candidate_dir / member.member_name
        if path.exists() or path.is_symlink():
            raise CandidateReviewError("replacement candidate version identity collides with existing storage")
        members.append(GenerationMember(path.relative_to(root).as_posix(), None, member.data))
    evidence_path = replacement_evidence_path(plans_dir, slug, record.version_id)
    candidate_evidence_path = roadmap_candidate_run.candidate_evidence_path(plans_dir, slug, record.version_id)
    binding_path = replacement_binding_path(plans_dir, slug, initial.version_id)
    for path, description in (
        (evidence_path, "replacement evidence"),
        (candidate_evidence_path, "replacement candidate evidence"),
        (binding_path, "replacement binding"),
    ):
        if path.exists() or path.is_symlink():
            raise CandidateReviewError(f"{description} identity collides with existing storage")
    binding = CandidateReviewReplacementBinding(
        schema_version=_SCHEMA_VERSION,
        initial_candidate_version_id=initial.version_id,
        inventory_id=inventory.inventory_id,
        question_id=inventory.question.question_id,
        answer_id=answer.answer_id,
        candidate_version_id=record.version_id,
    )
    for path, data in (
        (evidence_path, render_replacement_evidence(replacement_evidence)),
        (candidate_evidence_path, roadmap_candidate_run.render_candidate_evidence(candidate_evidence)),
        (binding_path, render_replacement_binding(binding)),
    ):
        members.append(GenerationMember(path.relative_to(root).as_posix(), None, data))

    def _pointer_still_names_the_reviewed_candidate() -> None:
        if roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=slug) != admission:
            raise CandidateReviewError("active candidate pointer changed before replacement storage")

    publish_roadmap_generation(
        PendingGeneration(kind="candidate-review-replacement", members=tuple(members)),
        plans_dir=plans_dir,
        slug=slug,
        writer_token=cast(Any, writer_token),
        before_replace=_pointer_still_names_the_reviewed_candidate,
    )
    refresh_roadmap_index(plans_dir, slug)
    return load_stored_candidate_review_replacement(
        plans_dir=plans_dir, slug=slug, candidate_version_id=record.version_id
    )


def _publish_batch_seal(
    *,
    plans_dir: Path,
    slug: str,
    writer_token: object,
    initial: roadmap_candidate_run.StoredCandidateProposal,
    replacement: StoredCandidateReviewReplacement,
    seal: CandidateReviewSeal,
) -> None:
    """Seal a batch replacement and make it the active candidate in one generation.

    The seal, the supersession record for the reviewed candidate, the pointer swap and
    the ledger patch become visible together, so a crash can never leave a seal whose
    replacement is not active, or an active replacement without its seal.
    """
    evidence = replacement.evidence
    if evidence.response_patch is None or evidence.derived_feedback is None or evidence.root_version_id is None:
        raise CandidateReviewError("batch replacement evidence is incomplete")
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=slug)
    if admission is None or admission.active_candidate_version_id != initial.version_id:
        raise CandidateReviewError("review seal requires the reviewed candidate to be the active candidate")
    ledger_path = roadmap_feedback_ledger_path(plans_dir, slug)
    try:
        ledger_bytes = ledger_path.read_bytes()
        ledger = load_ledger(ledger_path)
    except (OSError, RoadmapFeedbackLedgerError) as exc:
        raise CandidateReviewError("feedback ledger is unreadable") from exc
    updated = roadmap_candidate_run.apply_replacement_ledger_patch(
        ledger,
        reviewed_candidate_version_id=initial.version_id,
        replacement_version_id=replacement.version_id,
        response_patch=evidence.response_patch,
        derived_feedback=evidence.derived_feedback,
    )
    root = version_namespace_path(plans_dir, slug).parent
    seal_path = review_seal_path(plans_dir, slug, seal.seal_id)
    if seal_path.exists() or seal_path.is_symlink():
        raise CandidateReviewError("candidate review seal already exists")
    try:
        supersession = roadmap_candidate_run.build_supersession_member(
            plans_dir=plans_dir, slug=slug, admission=admission, successor_version_id=replacement.version_id
        )
        publish_roadmap_generation(
            PendingGeneration(
                kind="candidate-review-seal",
                members=(
                    GenerationMember(seal_path.relative_to(root).as_posix(), None, render_review_seal(seal)),
                    supersession,
                    roadmap_candidate_run.build_active_candidate_pointer_member(
                        plans_dir=plans_dir, slug=slug, previous=admission,
                        root_version_id=evidence.root_version_id,
                        candidate_version_id=replacement.version_id,
                    ),
                    GenerationMember(
                        ledger_path.relative_to(root).as_posix(), ledger_bytes, render_ledger(updated)
                    ),
                ),
            ),
            plans_dir=plans_dir,
            slug=slug,
            writer_token=cast(Any, writer_token),
            before_replace=lambda: roadmap_candidate_run.require_batch_state_unchanged(
                plans_dir=plans_dir, slug=slug, admission=admission, ledger_bytes=ledger_bytes
            ),
        )
        refresh_roadmap_index(plans_dir, slug)
    except roadmap_candidate_run.CandidateStorageRefusal as exc:
        raise CandidateReviewError(str(exc)) from exc


def _review_lineage_identity(inventory_id: str, answer_id: str) -> str:
    return _identity(
        {
            "review_lineage_version": _SCHEMA_VERSION,
            "questions": [inventory_id],
            "answers": [answer_id],
        }
    )


def _validate_replacement(
    replacement: StoredCandidateReviewReplacement,
    *,
    plans_dir: Path,
    slug: str,
    initial: roadmap_candidate_run.StoredCandidateProposal,
    inventory: CandidateQuestionInventory,
    answer: CandidateReviewAnswer,
) -> None:
    evidence = replacement.evidence
    expected_lineage = _review_lineage_identity(inventory.inventory_id, answer.answer_id)
    if initial.evidence.batch_receipt is not None:
        _validate_batch_replacement(
            replacement, plans_dir=plans_dir, slug=slug, initial=initial,
            inventory=inventory, answer=answer, expected_lineage=expected_lineage,
        )
        return
    capsule, receipt = _replacement_capsule(plans_dir=plans_dir, slug=slug, initial=initial)
    if (
        replacement.record.review_lineage_identity != expected_lineage
        or evidence.initial_candidate_version_id != initial.version_id
        or evidence.predecessor_version_id != initial.evidence.predecessor_version_id
        or evidence.feedback != initial.evidence.feedback
        or evidence.question_inventory_id != inventory.inventory_id
        or evidence.answer_incorporation.inventory_id != inventory.inventory_id
        or evidence.answer_incorporation.question_id != inventory.question.question_id
        or evidence.answer_incorporation.answer_id != answer.answer_id
        or evidence.review_lineage_identity != expected_lineage
        or evidence.candidate_version_id != replacement.version_id
        or evidence.content_identity != replacement.record.content_identity
        or evidence.capsule != capsule
        or evidence.receipt != receipt
    ):
        raise CandidateReviewError("replacement does not bind the exact stored review pair")
    if inventory.review_requirement != initial.evidence.review_requirement:
        raise CandidateReviewError("question inventory does not bind the stored review requirement")
    if (evidence.replacement_impact_atoms is None) != (
        evidence.replacement_impact_identity is None
    ):
        raise CandidateReviewError("replacement impact evidence is incomplete")
    if evidence.replacement_impact_atoms is None:
        if (
            initial.evidence.review_requirement is not None
            or evidence.replacement_review_requirement is not None
        ):
            raise CandidateReviewError("replacement lacks required computed impact evidence")
        return
    impact_atoms = _recompute_replacement_impact_atoms(
        replacement=replacement,
        initial=initial,
        capsule=capsule,
        receipt=receipt,
        plans_dir=plans_dir,
        slug=slug,
    )
    if (
        roadmap_candidate._wire_value(evidence.replacement_impact_atoms)
        != roadmap_candidate._wire_value(impact_atoms)
        or evidence.replacement_impact_identity
        != roadmap_candidate.candidate_impact_identity(impact_atoms)
    ):
        raise CandidateReviewError("replacement impact atoms cannot be reproduced from stored candidate")
    initial_requirement = initial.evidence.review_requirement
    if initial_requirement is not None and (
        evidence.capsule != initial.evidence.capsule
        or evidence.receipt != initial.evidence.receipt
        or evidence.replacement_review_requirement is not None
        and evidence.replacement_review_requirement.reason != initial_requirement.reason
        or not roadmap_candidate.review_requirement_contains_impact(
            initial_requirement, impact_atoms
        )
    ):
        raise CandidateReviewError("replacement impact exceeds the initial review disclosure")
    _validate_replacement_review_requirement(
        replacement=replacement,
        initial=initial,
        capsule=capsule,
        receipt=receipt,
        plans_dir=plans_dir,
        slug=slug,
    )


def _validate_batch_replacement(
    replacement: StoredCandidateReviewReplacement,
    *,
    plans_dir: Path,
    slug: str,
    initial: roadmap_candidate_run.StoredCandidateProposal,
    inventory: CandidateQuestionInventory,
    answer: CandidateReviewAnswer,
    expected_lineage: str,
) -> None:
    """Bind a batch replacement to the reviewed candidate's stored batch and its own evidence."""
    evidence = replacement.evidence
    receipt = initial.evidence.batch_receipt
    capsule = initial.evidence.capsule
    if (
        receipt is None
        or replacement.record.review_lineage_identity != expected_lineage
        or evidence.initial_candidate_version_id != initial.version_id
        or evidence.predecessor_version_id != initial.evidence.predecessor_version_id
        or evidence.root_version_id != initial.evidence.root_version_id
        or evidence.source_version_id != initial.evidence.source_version_id
        or evidence.batch_receipt_identity != receipt.capsule_identity
        or evidence.question_inventory_id != inventory.inventory_id
        or evidence.answer_incorporation.inventory_id != inventory.inventory_id
        or evidence.answer_incorporation.question_id != inventory.question.question_id
        or evidence.answer_incorporation.answer_id != answer.answer_id
        or evidence.review_lineage_identity != expected_lineage
        or evidence.candidate_version_id != replacement.version_id
        or evidence.content_identity != replacement.record.content_identity
        or evidence.response_patch is None
        or tuple(entry.item for entry in evidence.response_patch.entries)
        != getattr(capsule, "reviewer_items", None)
    ):
        raise CandidateReviewError("replacement does not bind the exact stored review pair")
    # The replacement's own candidate evidence must agree with the review evidence
    # that overlaps it, so an active replacement is never reloaded on other facts.
    try:
        stored = roadmap_candidate_run.load_stored_candidate_proposal(
            plans_dir=plans_dir, slug=slug, candidate_version_id=replacement.version_id
        )
    except roadmap_candidate_run.CandidateProposalError as exc:
        raise CandidateReviewError("replacement candidate evidence is unreadable") from exc
    own = stored.evidence
    if (
        own.capsule != capsule
        or own.batch_receipt != receipt
        or own.predecessor_diff != evidence.predecessor_diff
        or own.gate_evidence != evidence.gate_evidence
        or own.review_lineage_identity != expected_lineage
        or own.content_identity != evidence.content_identity
    ):
        raise CandidateReviewError("replacement candidate evidence does not bind its review evidence")


def _recompute_replacement_impact_atoms(
    *,
    replacement: StoredCandidateReviewReplacement,
    initial: roadmap_candidate_run.StoredCandidateProposal,
    capsule: CandidateContextCapsule,
    receipt: CandidateContextReceipt,
    plans_dir: Path,
    slug: str,
) -> tuple[roadmap_candidate.CandidateImpactAtom, ...]:
    """Derive replacement atoms from the stored candidate rather than its evidence."""
    predecessor = roadmap_candidate_run._load_resolved_version(
        plans_dir=plans_dir,
        slug=slug,
        version_id=initial.evidence.predecessor_version_id,
    )
    verified = roadmap_candidate._verify_bindings(
        predecessor=predecessor,
        capsule=roadmap_candidate_run._hydrate_capsule(capsule),
        receipt=receipt,
        stages=STAGES,
    )
    if isinstance(verified, roadmap_candidate.CandidateRefusal):
        raise CandidateReviewError("replacement capsule cannot be reproduced from its predecessor")
    predecessor_artifacts, predecessor_bytes = verified
    try:
        candidate_members = tuple(
            roadmap_candidate.CandidateArtifact(
                artifact_key=stage.artifact_key,
                data=data,
                text=data.decode("utf-8"),
                artifact=stage.parse(data.decode("utf-8")),
                digest=_digest(data),
            )
            for stage, data in zip(STAGES, replacement.content.artifact_bytes, strict=True)
        )
    except (AttributeError, TypeError, UnicodeDecodeError, ValueError) as exc:
        raise CandidateReviewError("replacement candidate artifacts are unreadable") from exc
    candidate_artifacts = {
        member.artifact_key: member.artifact for member in candidate_members
    }
    expected_diff = roadmap_candidate._build_predecessor_diff(
        predecessor_artifacts=predecessor_artifacts,
        candidate_artifacts=candidate_artifacts,
        predecessor_bytes=predecessor_bytes,
        candidate_artifacts_bytes=tuple(member.data for member in candidate_members),
        stages=STAGES,
    )
    expected_content_identity = roadmap_candidate._content_identity(
        predecessor_version_id=predecessor.record.version_id,
        selected_feedback=replacement.evidence.feedback,
        receipt=receipt,
        artifacts=candidate_members,
        predecessor_diff=expected_diff,
    )
    if (
        roadmap_candidate._wire_value(replacement.evidence.predecessor_diff)
        != roadmap_candidate._wire_value(expected_diff)
        or replacement.evidence.content_identity != expected_content_identity
        or replacement.record.content_identity != expected_content_identity
    ):
        raise CandidateReviewError("replacement candidate facts cannot be reproduced from stored bytes")
    return roadmap_candidate.candidate_impact_atoms_for_diff(
        expected_diff,
        before_relations=roadmap_candidate.extract_declared_relations(**predecessor_artifacts),
        after_relations=roadmap_candidate.extract_declared_relations(**candidate_artifacts),
    )


def _validate_replacement_review_requirement(
    *,
    replacement: StoredCandidateReviewReplacement,
    initial: roadmap_candidate_run.StoredCandidateProposal,
    capsule: CandidateContextCapsule,
    receipt: CandidateContextReceipt,
    plans_dir: Path,
    slug: str,
) -> None:
    """Replay a remaining review requirement so its facts cannot be hand-written."""
    requirement = replacement.evidence.replacement_review_requirement
    if requirement is None:
        return
    predecessor = roadmap_candidate_run._load_resolved_version(
        plans_dir=plans_dir,
        slug=slug,
        version_id=initial.evidence.predecessor_version_id,
    )
    try:
        delta = roadmap_candidate.parse_candidate_delta(
            roadmap_candidate_run._canonical_json_text(
                {"operations": roadmap_candidate._operations_wire_for_reparse(requirement.normalized_operations)}
            )
        )
    except (roadmap_candidate.CandidateDeltaError, roadmap_candidate_run.CandidateProposalError) as exc:
        raise CandidateReviewError("replacement review requirement is malformed") from exc
    replayed = roadmap_candidate.materialize_candidate(
        delta,
        predecessor=predecessor,
        capsule=roadmap_candidate_run._hydrate_capsule(capsule),
        receipt=receipt,
    )
    if (
        replayed.review_required is None
        or replayed.refusal is not None
        or tuple(member.data for member in replayed.review_required.artifacts)
        != replacement.content.artifact_bytes
        or roadmap_candidate._wire_value(replayed.review_required.review_requirement)
        != roadmap_candidate._wire_value(requirement)
    ):
        raise CandidateReviewError("replacement review requirement cannot be reproduced")


def _new_seal(
    *,
    initial: roadmap_candidate_run.StoredCandidateProposal,
    inventory: CandidateQuestionInventory,
    answer: CandidateReviewAnswer,
    replacement: StoredCandidateReviewReplacement,
) -> CandidateReviewSeal:
    evidence = replacement.evidence
    seal_values: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "roadmap_slug": initial.record.roadmap_slug,
        "initial_candidate_version_id": initial.version_id,
        "question_inventory_id": inventory.inventory_id,
        "answer_ids": (answer.answer_id,),
        "replacement_candidate_version_id": replacement.version_id,
        "replacement_content_identity": evidence.content_identity,
        "answer_incorporation_id": evidence.answer_incorporation.incorporation_id,
    }
    if evidence.batch_receipt_identity is not None:
        # The batch replacement's capsule is the reviewed candidate's, kept in
        # the reviewed candidate's own evidence.
        seal_values["final_capsule_identity"] = initial.evidence.capsule.capsule_identity
        seal_values["root_version_id"] = evidence.root_version_id
        seal_values["source_version_id"] = evidence.source_version_id
        seal_values["batch_receipt_identity"] = evidence.batch_receipt_identity
    else:
        seal_values["final_capsule_identity"] = cast(CandidateContextCapsule, evidence.capsule).capsule_identity
    return CandidateReviewSeal(
        seal_id=_identity(seal_values),
        **seal_values,
    )


def _seal_preimage(seal: CandidateReviewSeal) -> dict[str, object]:
    if seal.decision == "structural-approval":
        preimage: dict[str, object] = {
            "schema_version": _SCHEMA_VERSION,
            "roadmap_slug": seal.roadmap_slug,
            "decision": seal.decision,
            "initial_candidate_version_id": seal.initial_candidate_version_id,
            "approved_candidate_version_id": seal.approved_candidate_version_id,
            "approved_content_identity": seal.approved_content_identity,
            "final_capsule_identity": seal.final_capsule_identity,
        }
        if seal.root_version_id is not None:
            preimage["root_version_id"] = seal.root_version_id
            preimage["source_version_id"] = seal.source_version_id
            preimage["batch_receipt_identity"] = seal.batch_receipt_identity
        return preimage
    preimage: dict[str, object] = {
        "schema_version": _SCHEMA_VERSION,
        "roadmap_slug": seal.roadmap_slug,
        "initial_candidate_version_id": seal.initial_candidate_version_id,
        "question_inventory_id": seal.question_inventory_id,
        "answer_ids": seal.answer_ids,
        "replacement_candidate_version_id": seal.replacement_candidate_version_id,
        "replacement_content_identity": seal.replacement_content_identity,
        "answer_incorporation_id": seal.answer_incorporation_id,
        "final_capsule_identity": seal.final_capsule_identity,
    }
    # Only a batch seal names them, so a selector-era seal id is unchanged.
    if seal.root_version_id is not None:
        preimage["root_version_id"] = seal.root_version_id
        preimage["source_version_id"] = seal.source_version_id
        preimage["batch_receipt_identity"] = seal.batch_receipt_identity
    return preimage


def _new_structural_approval_seal(
    candidate: roadmap_candidate_run.StoredCandidateProposal,
) -> CandidateReviewSeal:
    """Bind a direct approval to the active candidate's persisted bytes."""
    evidence = candidate.evidence
    values: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "roadmap_slug": candidate.record.roadmap_slug,
        "initial_candidate_version_id": candidate.version_id,
        "decision": "structural-approval",
        "approved_candidate_version_id": candidate.version_id,
        "approved_content_identity": evidence.content_identity,
        "final_capsule_identity": evidence.capsule.capsule_identity,
    }
    if evidence.batch_receipt is not None:
        values.update(
            root_version_id=evidence.root_version_id,
            source_version_id=evidence.source_version_id,
            batch_receipt_identity=evidence.batch_receipt.capsule_identity,
        )
    return CandidateReviewSeal(seal_id=_identity(values), **values)


def _parse_question_anchor(
    value: dict[str, object],
    *,
    candidate: roadmap_candidate_run.StoredCandidateProposal,
) -> CandidateQuestionAnchor:
    kind = value.get("kind")
    expected_keys: set[str]
    if kind == "feedback":
        expected_keys = {"kind", "artifact_key", "feedback_id"}
    elif kind in {"diff-row", "full-member", "inventory", "reviewer-item", "response", "derived-context"}:
        expected_keys = {"kind", "artifact_key", "row_type", "row_id"}
    else:
        raise CandidateQuestionResponseError("candidate question anchor has an invalid kind")
    if set(value) != expected_keys:
        raise CandidateQuestionResponseError("candidate question anchor has mixed or unknown fields")
    try:
        anchor = CandidateQuestionAnchor.model_validate(value)
    except ValidationError as exc:
        raise CandidateQuestionResponseError("candidate question anchor is malformed") from exc
    if anchor.kind == "response" and candidate.evidence.batch_receipt is not None:
        raise CandidateQuestionResponseError(
            "a batch candidate question cannot anchor on a response: its evidence retains no response text"
        )
    if not _anchor_resolves(anchor, candidate=candidate):
        raise CandidateQuestionResponseError("candidate question anchor does not resolve in stored facts")
    return anchor


def _anchor_resolves(
    anchor: CandidateQuestionAnchor,
    *,
    candidate: roadmap_candidate_run.StoredCandidateProposal,
) -> bool:
    evidence = candidate.evidence
    if evidence.batch_receipt is not None:
        receipt = evidence.batch_receipt
        identity = (anchor.artifact_key, anchor.row_type, anchor.row_id)
        if anchor.kind == "reviewer-item":
            return any(identity == ("ledger", "reviewer-item", item.item_id) for item in receipt.reviewer_items)
        if anchor.kind == "response":
            # Not offered: the receipt's snapshots carry no proposal and the evidence keeps no response text.
            return False
        if anchor.kind == "derived-context":
            return any(identity == ("derived-context", "row", item.context_id) for item in receipt.derived_context)
        if anchor.kind == "full-member":
            return any(identity == (member.identity.artifact_key, member.identity.row_type, member.identity.row_id) for member in receipt.full_members)
        if anchor.kind == "inventory":
            return any(identity == (entry.artifact_key, entry.row_type, entry.row_id) for entry in receipt.inventory)
        if anchor.kind == "diff-row":
            return any(identity == (row.artifact_key, row.row_type, row.row_id) for row in evidence.predecessor_diff.changed_rows)
        return False
    if anchor.kind == "feedback":
        return (
            anchor.artifact_key == evidence.feedback.artifact_key
            and anchor.feedback_id == evidence.feedback.feedback_id
        )
    identity = (anchor.artifact_key, anchor.row_type, anchor.row_id)
    if anchor.kind == "diff-row":
        return any(
            identity == (row.artifact_key, row.row_type, row.row_id)
            for row in evidence.predecessor_diff.changed_rows
        )
    if anchor.kind == "full-member":
        return any(
            identity == (member.identity.artifact_key, member.identity.row_type, member.identity.row_id)
            for member in evidence.receipt.full_members
        )
    # reviewer-item, response and derived-context anchors exist only for a batch receipt.
    if anchor.kind != "inventory":
        return False
    return any(
        identity == (entry.artifact_key, entry.row_type, entry.row_id)
        for entry in evidence.receipt.inventory
    )


def _invoke_replacement(
    *,
    invoke: CandidateReviewInvoker,
    logger: RunLogWriter,
    capsule: CandidateContextCapsule,
    receipt: CandidateContextReceipt,
    review_pair: roadmap_candidate_run.CandidateReviewPair,
    attempt: int,
    source: ResolvedRoadmapVersion,
) -> roadmap_candidate_run.CandidateModelInvocation:
    prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=capsule, receipt=receipt, review_pair=review_pair, source=source
    )
    return _invoke_once(
        invoke=invoke,
        logger=logger,
        phase=_REPLACEMENT_PHASE,
        prompt=prompt,
        attempt=attempt,
    )


def _invoke_once(
    *,
    invoke: CandidateReviewInvoker,
    logger: RunLogWriter,
    phase: str,
    prompt: str,
    attempt: int,
) -> roadmap_candidate_run.CandidateModelInvocation:
    logger.claude_call_start(
        phase,
        attempt,
        len(prompt.encode("utf-8")),
        prompt_sha256=hash_prompt(prompt),
    )
    with logger.bind_shell_sink(phase=phase, attempt=attempt):
        rc, response = invoke(prompt)
    if rc != 0:
        logger.attempt_failed(phase=phase, attempt=attempt, failure_kind="transport")
    return roadmap_candidate_run.CandidateModelInvocation(attempt=attempt, rc=rc, response=response)


def _finish_log(
    logger: RunLogWriter,
    phase: str,
    started_at: float,
    result: CandidateReviewResult,
    *,
    expansion_used: bool,
    last_response: roadmap_candidate_run.CandidateModelInvocation | None,
    response_accepted: bool = False,
) -> None:
    failure_extras: dict[str, object] = {}
    if result.outcome != "stored":
        with contextlib.suppress(KeyboardInterrupt):
            failure_extras = roadmap_candidate_run.candidate_failure_diagnostic_extras(
                attempt=last_response.attempt if last_response is not None else None,
                call_count=result.call_count,
                failure_detail=result.detail or "candidate review failed without a detail",
                response_text=(
                    last_response.response
                    if last_response is not None and not response_accepted
                    else None
                ),
            )
    # A second KeyboardInterrupt landing anywhere in this call — including
    # its own setup, before either of its internal guards is reached — must
    # not stop the terminal-record calls below from being attempted.
    with contextlib.suppress(KeyboardInterrupt):
        failure_extras = (
            roadmap_candidate_run.record_candidate_failure_diagnostics(
                logger=logger,
                phase=phase,
                attempt=last_response.attempt if last_response is not None else None,
                outcome=result.outcome,
                call_count=result.call_count,
                failure_detail=result.detail or "candidate review failed without a detail",
                response_text=(
                    last_response.response
                    if last_response is not None and not response_accepted
                    else None
                ),
            )
            if result.outcome != "stored"
            else {}
        )
    with contextlib.suppress(KeyboardInterrupt):
        logger.phase_end(
            phase,
            int((time.monotonic() - started_at) * 1000),
            result.outcome,
            call_count=result.call_count,
            expansion_used=expansion_used,
            **failure_extras,
        )
    with contextlib.suppress(KeyboardInterrupt):
        logger.run_end(
            outcome=result.outcome,
            rc=_result_return_code(result.outcome),
            termination_reason="operator_interrupt" if result.outcome == "interrupted" else None,
        )


def _result_return_code(outcome: CandidateReviewOutcome) -> int:
    """Map one closed review outcome to its command exit code."""
    return {
        "stored": 0,
        "response-rejected": 1,
        "failed": 1,
        "refused": 2,
        "interrupted": 130,
    }[outcome]


def _stored_result(
    *,
    initial: roadmap_candidate_run.StoredCandidateProposal,
    inventory: CandidateQuestionInventory | None = None,
    answer: CandidateReviewAnswer | None = None,
    replacement: StoredCandidateReviewReplacement | None = None,
    active_candidate: roadmap_candidate_run.StoredCandidateProposal | None = None,
    seal: CandidateReviewSeal | None = None,
    call_count: int = 0,
) -> CandidateReviewResult:
    return CandidateReviewResult(
        outcome="stored",
        initial_candidate=initial,
        question_inventory=inventory,
        answer=answer,
        replacement=replacement,
        active_candidate=active_candidate,
        seal=seal,
        call_count=call_count,
    )


def _result(outcome: CandidateReviewOutcome, detail: str, call_count: int) -> CandidateReviewResult:
    return CandidateReviewResult(outcome=outcome, detail=detail, call_count=call_count)


def _interrupted_result(
    logger: RunLogWriter, *, phase: str, call_count: int, detail: str
) -> CandidateReviewResult:
    """Report a first KeyboardInterrupt, then return the "interrupted" result.

    A second KeyboardInterrupt landing mid-report must not stop this from
    still returning "interrupted" rather than leaving `result` unset.
    """
    with contextlib.suppress(KeyboardInterrupt):
        logger.run_interrupted(phase=phase, attempt=max(call_count, 1), source="candidate-review")
    return _result("interrupted", detail, call_count)


def _publish_new_record(
    *,
    plans_dir: Path,
    slug: str,
    writer_token: object,
    path: Path,
    data: bytes,
    description: str,
    before_replace: Callable[[], None] | None = None,
) -> None:
    """Publish one immutable review member through the shared generation boundary."""
    if path.exists() or path.is_symlink():
        raise CandidateReviewError(f"{description} already exists")
    root = version_namespace_path(plans_dir, slug).parent
    publish_roadmap_generation(
        PendingGeneration(
            kind="candidate-review-record",
            members=(GenerationMember(path.relative_to(root).as_posix(), None, data),),
        ),
        plans_dir=plans_dir,
        slug=slug,
        writer_token=cast(Any, writer_token),
        before_replace=before_replace,
    )
    refresh_roadmap_index(plans_dir, slug)


def _read_member(path: Path, *, expected_digest: str, description: str) -> bytes:
    try:
        data = path.read_bytes()
        data.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CandidateReviewError(f"{description} is unreadable") from exc
    if _digest(data) != expected_digest:
        raise CandidateReviewError(f"{description} does not match its recorded digest")
    return data


def _render_record(
    record: BaseModel,
    *,
    description: str,
    exclude_none_fields: bool = False,
    exclude_unset_fields: bool = False,
) -> bytes:
    try:
        encoded = _canonical_json_bytes(
            record.model_dump(
                mode="json",
                exclude_none=exclude_none_fields,
                exclude_unset=exclude_unset_fields,
            )
        )
        validated = record.__class__.model_validate_json(encoded)
        return _canonical_json_bytes(
            validated.model_dump(
                mode="json",
                exclude_none=exclude_none_fields,
                exclude_unset=exclude_unset_fields,
            )
        )
    except (ValidationError, TypeError, ValueError) as exc:
        raise CandidateReviewError(f"{description} is invalid") from exc


def _parse_record(
    data: bytes,
    record_type: type[BaseModel],
    *,
    description: str,
    exclude_unset_fields: bool = False,
) -> BaseModel:
    _decode_strict_json(data, description=description)
    try:
        record = record_type.model_validate_json(data)
    except ValidationError as exc:
        raise CandidateReviewError(f"{description} is malformed") from exc
    if (
        _render_record(
            record,
            description=description,
            exclude_unset_fields=exclude_unset_fields,
        )
        != data
    ):
        raise CandidateReviewError(f"{description} must use exact canonical JSON")
    return record


def _decode_single_json_object(response_text: str, *, description: str) -> dict[str, object]:
    if not isinstance(response_text, str):
        raise CandidateQuestionResponseError(f"{description} must be JSON text")
    decoder = json.JSONDecoder(object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant)
    start = len(response_text) - len(response_text.lstrip(" \t\r\n"))
    try:
        payload, end = decoder.raw_decode(response_text, start)
    except (CandidateQuestionResponseError, json.JSONDecodeError) as exc:
        raise CandidateQuestionResponseError(f"{description} must be one unfenced JSON object") from exc
    if response_text[end:].strip(" \t\r\n"):
        raise CandidateQuestionResponseError(f"{description} must not contain trailing text")
    if not isinstance(payload, dict):
        raise CandidateQuestionResponseError(f"{description} root must be an object")
    return cast(dict[str, object], payload)


def _decode_strict_json(data: bytes, *, description: str) -> object:
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, CandidateQuestionResponseError) as exc:
        raise CandidateReviewError(f"{description} is not strict JSON") from exc


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise CandidateQuestionResponseError("candidate review JSON has duplicate keys")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise CandidateQuestionResponseError(f"candidate review JSON cannot use constant {value!r}")


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
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value
