"""Narrative review evidence for a roadmap candidate, computed and never stored.

One pure function turns a candidate's artifacts and its predecessor's artifacts
(both supplied by the caller) into the removed-id evidence of
``roadmap_gates.check_removed_ids_in_live_prose``; one adapter turns member
bytes into those artifacts, so a stored candidate and its in-memory form yield
equal evidence. See ROADMAP_FORMAT.md § "Narrative review evidence".
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Callable

from plan_tool.roadmap_artifacts import (
    parse_components_artifact,
    parse_constraints_artifact,
    parse_domain_artifact,
    parse_plans_artifact,
)
from plan_tool.roadmap_gates import (
    HISTORY_MARKER_END,
    HISTORY_MARKER_START,
    NARRATIVE_REMOVED_ID_IN_LIVE_PROSE,
    NARRATIVE_UNCLOSED_FENCE_UNREAD,
    ArtifactEnvelope,
    NarrativeReference,
    StageArtifact,
    check_removed_ids_in_live_prose,
)
from plan_tool.roadmap_versions import (
    VERSION_ARTIFACT_KEYS,
    ResolvedRoadmapVersion,
    RoadmapVersionError,
)

CORRECTION_NONE_REQUIRED = "none required; the reviewer reads this evidence item"

_PARSERS: Mapping[str, Callable[[str], StageArtifact]] = {
    "domain": parse_domain_artifact,
    "constraints": parse_constraints_artifact,
    "components": parse_components_artifact,
    "plans": parse_plans_artifact,
}


@dataclass(frozen=True)
class NarrativeFinding:
    """One narrative defect or evidence item, self-contained for quoting.

    ``start``/``end`` are body offsets and ``line`` is body-relative, for a
    display that wants to point at the span; ``message`` never carries them.
    ``correction_path`` lists every exit, so no caller composes its own.
    """

    kind: str
    artifact: str
    row_id: str
    start: int
    end: int
    line: int
    excerpt: str
    correction_path: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class CandidateNarrativeEvidence:
    """Blocking findings and non-blocking evidence items for one candidate."""

    blocking_findings: tuple[NarrativeFinding, ...]
    evidence_items: tuple[NarrativeFinding, ...]

    @property
    def has_blocking_findings(self) -> bool:
        return bool(self.blocking_findings)


def _finding_from(reference: NarrativeReference) -> NarrativeFinding:
    if reference.kind == NARRATIVE_REMOVED_ID_IN_LIVE_PROSE:
        correction_path = (
            "rewrite the span with a `correct-prose` operation (only when the block also names a live row)",
            f"set the span off with the historical marker lines {HISTORY_MARKER_START} "
            f"and {HISTORY_MARKER_END}",
        )
        message = (
            f"{reference.artifact} names the removed id '{reference.row_id}' in live prose "
            f"({reference.kind}); {'; or '.join(correction_path)}"
        )
    elif reference.kind == NARRATIVE_UNCLOSED_FENCE_UNREAD:
        correction_path = ("close the code fence so the check can read the text after it",)
        message = (
            f"{reference.artifact} has an unclosed code fence that hides text naming the removed "
            f"id '{reference.row_id}' ({reference.kind}); {'; or '.join(correction_path)}"
        )
    else:
        correction_path = (CORRECTION_NONE_REQUIRED,)
        message = (
            f"{reference.artifact} names '{reference.row_id}', which a removal record drops "
            f"and a present row also uses ({reference.kind}), so the token may name the "
            f"live row; {CORRECTION_NONE_REQUIRED}"
        )
    return NarrativeFinding(
        kind=reference.kind,
        artifact=reference.artifact,
        row_id=reference.row_id,
        start=reference.start,
        end=reference.end,
        line=reference.line,
        excerpt=reference.excerpt,
        correction_path=correction_path,
        message=message,
    )


def _member_envelope(
    key: str,
    candidate: Mapping[str, StageArtifact],
    predecessor: Mapping[str, StageArtifact],
) -> ArtifactEnvelope:
    # Only the slot under check is read; domain is the envelope's required slot.
    domain = candidate.get("domain", predecessor.get("domain"))
    if domain is None:
        raise RoadmapVersionError("narrative evidence needs a domain artifact")
    if key == "domain":
        return ArtifactEnvelope(domain=domain, predecessor=predecessor[key])  # type: ignore[arg-type]
    return ArtifactEnvelope(
        domain=domain,  # type: ignore[arg-type]
        predecessor=predecessor[key],
        **{key: candidate[key]},
    )


def compute_candidate_narrative_evidence(
    candidate: Mapping[str, StageArtifact],
    predecessor: Mapping[str, StageArtifact],
    *,
    feedback_free: bool = False,
) -> CandidateNarrativeEvidence:
    """Evidence for every candidate member, each against its own predecessor.

    Pure: no model call, storage, or loading. A candidate member with no
    predecessor member raises ``RoadmapVersionError`` rather than reading as
    clean. ``feedback_free`` marks a batch candidate, rendered with its
    ``removals`` cleared.
    """
    blocking: list[NarrativeFinding] = []
    evidence: list[NarrativeFinding] = []
    for key in VERSION_ARTIFACT_KEYS:
        if key not in candidate:
            continue
        if key not in predecessor:
            raise RoadmapVersionError(f"predecessor version has no {key} artifact to compare")
        envelope = _member_envelope(key, candidate, predecessor)
        for reference in check_removed_ids_in_live_prose(envelope, feedback_free=feedback_free):
            finding = _finding_from(reference)
            target = blocking if finding.kind == NARRATIVE_REMOVED_ID_IN_LIVE_PROSE else evidence
            target.append(finding)
    return CandidateNarrativeEvidence(tuple(blocking), tuple(evidence))


def parse_member_bytes(members: Mapping[str, bytes]) -> dict[str, StageArtifact]:
    """Parse member bytes through the roadmap parsers; a parse or decode error surfaces."""
    return {key: _PARSERS[key](data.decode("utf-8")) for key, data in members.items()}


def stored_member_bytes(resolved: ResolvedRoadmapVersion) -> dict[str, bytes]:
    """The member bytes of a stored version, keyed by artifact key."""
    return dict(zip(resolved.artifact_keys, resolved.artifact_bytes, strict=True))


def in_memory_member_bytes(artifacts: Iterable[object]) -> dict[str, bytes]:
    """The member bytes of an in-memory candidate's ``CandidateArtifact`` members."""
    return {member.artifact_key: member.data for member in artifacts}  # type: ignore[attr-defined]


def candidate_narrative_evidence_from_bytes(
    candidate_members: Mapping[str, bytes],
    predecessor: ResolvedRoadmapVersion,
    *,
    feedback_free: bool = False,
) -> CandidateNarrativeEvidence:
    """The one adapter: member bytes of a stored or in-memory candidate to evidence.

    ``predecessor`` is already loaded by the caller, so an unreadable one has
    raised before this runs. Both candidate forms funnel through here, which is
    what keeps their evidence equal.
    """
    return compute_candidate_narrative_evidence(
        parse_member_bytes(candidate_members),
        parse_member_bytes(stored_member_bytes(predecessor)),
        feedback_free=feedback_free,
    )
