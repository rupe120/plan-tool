from __future__ import annotations

import ast
import re
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from plan_tool.roadmap_artifacts import (
    DomainArtifact,
    EntityRow,
    FieldRow,
    FieldType,
    RemovalRecord,
    RoadmapArtifactError,
    render_domain_artifact,
)
from plan_tool.roadmap_candidate_narrative import (
    CORRECTION_NONE_REQUIRED,
    CandidateNarrativeEvidence,
    candidate_narrative_evidence_from_bytes,
    compute_candidate_narrative_evidence,
    in_memory_member_bytes,
)
from plan_tool.roadmap_gates import (
    HISTORY_MARKER_END,
    HISTORY_MARKER_START,
    NARRATIVE_REMOVED_ID_AMBIGUOUS_REFERENCE,
    NARRATIVE_REMOVED_ID_IN_LIVE_PROSE,
)
from plan_tool.roadmap_versions import ResolvedRoadmapVersion, RoadmapVersionError

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "plan_tool" / "roadmap_candidate_narrative.py"
)
_INTEGRATION_PARAGRAPH = Path(__file__).parent / "fixtures" / "roadmap" / "integration-decisions-paragraph.md"
_REMOVED = "decision-gone"
_ENTITY = EntityRow(id="entity-1", name="Order", fields=(FieldRow(name="note", type=FieldType.TEXT),))


def _removal(row_id: str = _REMOVED) -> RemovalRecord:
    return RemovalRecord(removed_id=row_id, rationale="Dropped.", feedback_ids=())


def _domain(body: str, *, removals=()) -> DomainArtifact:
    return DomainArtifact(
        entities=(_ENTITY,),
        business_rules=(),
        workflows=(),
        decisions=(),
        body=body,
        feedback=(),
        removals=tuple(removals),
    )


@dataclass(frozen=True)
class _DomainOnlyVersion(ResolvedRoadmapVersion):
    """A stored-version stand-in holding only the domain member, so a test needs no
    other stage's artifact."""

    @property
    def artifact_keys(self) -> tuple[str, ...]:
        return ("domain",)


def _stored_predecessor(artifact: DomainArtifact) -> ResolvedRoadmapVersion:
    data = render_domain_artifact(artifact).encode("utf-8")
    return _DomainOnlyVersion(record=None, brief_bytes=b"", artifact_bytes=(data,))  # type: ignore[arg-type]


def _evidence(body: str, *, removals=(), predecessor_body: str = "entity-1 is described here.\n"):
    return compute_candidate_narrative_evidence(
        {"domain": _domain(body, removals=removals)},
        {"domain": _domain(predecessor_body)},
    )


def test_no_removed_ids_gives_empty_evidence() -> None:
    evidence = _evidence(f"entity-1 and {_REMOVED} here.\n")
    assert evidence == CandidateNarrativeEvidence((), ())
    assert not evidence.has_blocking_findings


def test_removed_id_in_live_prose_is_a_blocking_finding() -> None:
    evidence = _evidence(f"First.\nSecond names {_REMOVED} here.\n", removals=[_removal()])
    (finding,) = evidence.blocking_findings
    assert evidence.has_blocking_findings
    assert evidence.evidence_items == ()
    assert (finding.kind, finding.artifact, finding.row_id, finding.line) == (
        NARRATIVE_REMOVED_ID_IN_LIVE_PROSE,
        "01-domain.md",
        _REMOVED,
        2,
    )
    assert len(finding.correction_path) == 2
    assert "`correct-prose`" in finding.correction_path[0]
    assert "IPPT" not in finding.message  # operators see this text; a ticket key means nothing to them
    assert HISTORY_MARKER_START in finding.correction_path[1]
    assert HISTORY_MARKER_END in finding.correction_path[1]


def test_correction_exit_says_it_applies_only_to_a_block_that_also_names_a_live_row() -> None:
    """A block naming only removed rows is not issued as a span, so the exit must not promise one."""
    (finding,) = _evidence(f"Names {_REMOVED}.\n", removals=[_removal()]).blocking_findings

    assert "only when the block also names a live row" in finding.correction_path[0]


def test_unclosed_fence_hiding_a_removed_id_is_evidence_and_never_blocks() -> None:
    evidence = _evidence(f"```\n{_REMOVED}\n", removals=[_removal()])

    assert not evidence.has_blocking_findings
    (item,) = evidence.evidence_items
    assert item.kind == "unclosed-fence-unread"
    assert "close the code fence" in item.correction_path[0]
    assert _REMOVED in item.message


def test_finding_message_is_self_contained_and_carries_no_line_number() -> None:
    (finding,) = _evidence(f"One.\nTwo {_REMOVED}.\n", removals=[_removal()]).blocking_findings
    assert "01-domain.md" in finding.message
    assert _REMOVED in finding.message
    assert not re.search(r"\bline\b|\d+:\d+", finding.message)


def test_ambiguous_reference_is_evidence_not_blocking() -> None:
    """The carve-out: a removed id that is also a present row never blocks."""
    evidence = _evidence("entity-1 is described here.\n", removals=[_removal("entity-1")])
    (item,) = evidence.evidence_items
    assert item.kind == NARRATIVE_REMOVED_ID_AMBIGUOUS_REFERENCE
    assert item.correction_path == (CORRECTION_NONE_REQUIRED,)
    assert evidence.blocking_findings == ()
    assert not evidence.has_blocking_findings


def test_historical_marker_prose_produces_no_finding() -> None:
    body = f"entity-1.\n{HISTORY_MARKER_START}\n{_REMOVED} was rejected.\n{HISTORY_MARKER_END}\n"
    assert _evidence(body, removals=[_removal()]) == CandidateNarrativeEvidence((), ())


def test_finding_order_is_deterministic() -> None:
    body = f"b {_REMOVED}-two b {_REMOVED}\n\n{_REMOVED}\n"
    removals = [_removal(), _removal(f"{_REMOVED}-two")]
    first = _evidence(body, removals=removals)
    second = _evidence(body, removals=list(reversed(removals)))
    assert [(f.start, f.row_id) for f in first.blocking_findings] == sorted(
        (f.start, f.row_id) for f in first.blocking_findings
    )
    assert {(f.start, f.row_id) for f in first.blocking_findings} == {
        (f.start, f.row_id) for f in second.blocking_findings
    }
    assert first == _evidence(body, removals=removals)


def test_function_never_raises_on_defective_candidate() -> None:
    """A defect is reported as data, not raised."""
    evidence = _evidence(f"{_REMOVED}\n", removals=[_removal()])
    assert isinstance(evidence, CandidateNarrativeEvidence)
    assert evidence.has_blocking_findings


def test_missing_predecessor_member_raises_instead_of_reading_clean() -> None:
    with pytest.raises(RoadmapVersionError):
        compute_candidate_narrative_evidence({"domain": _domain("x\n")}, {})


def test_feedback_free_candidate_is_checked_against_predecessor_removals() -> None:
    """A batch candidate renders with its removals cleared; the predecessor's apply."""
    predecessor = _domain("entity-1.\n", removals=[_removal()])
    evidence = compute_candidate_narrative_evidence(
        {"domain": _domain(f"Names {_REMOVED}.\n")}, {"domain": predecessor}, feedback_free=True
    )
    assert evidence.has_blocking_findings


@pytest.mark.parametrize(
    ("body", "removals", "feedback_free"),
    [
        pytest.param("entity-1.\n", (), False, id="clean"),
        pytest.param(f"entity-1 {_REMOVED}.\n", (_removal(),), False, id="blocking"),
        pytest.param("entity-1.\n", (_removal("entity-1"),), False, id="ambiguous"),
        pytest.param(f"entity-1 {_REMOVED}.\n", (), True, id="feedback-free"),
    ],
)
def test_stored_and_in_memory_candidate_yield_identical_evidence(
    body: str, removals: tuple, feedback_free: bool
) -> None:
    """Both candidate forms funnel through one adapter, so display and refusal agree."""
    predecessor_artifact = _domain("entity-1.\n", removals=(_removal(),) if feedback_free else ())
    predecessor = _stored_predecessor(predecessor_artifact)
    data = render_domain_artifact(_domain(body, removals=removals)).encode("utf-8")
    in_memory = in_memory_member_bytes([_Member("domain", data)])
    stored = dict(zip(("domain",), (data,)))
    assert candidate_narrative_evidence_from_bytes(
        in_memory, predecessor, feedback_free=feedback_free
    ) == candidate_narrative_evidence_from_bytes(stored, predecessor, feedback_free=feedback_free)
    if removals or feedback_free:
        assert candidate_narrative_evidence_from_bytes(
            stored, predecessor, feedback_free=feedback_free
        ) != CandidateNarrativeEvidence((), ())


@dataclass(frozen=True)
class _Member:
    artifact_key: str
    data: bytes


def test_legacy_candidate_without_prior_evidence_gets_same_evidence() -> None:
    """Nothing is read from storage, so a candidate older than this contract is judged
    by the same computation as a new one."""
    predecessor = _stored_predecessor(_domain("entity-1.\n"))
    data = render_domain_artifact(_domain(f"entity-1 {_REMOVED}.\n", removals=[_removal()])).encode()
    first = candidate_narrative_evidence_from_bytes({"domain": data}, predecessor)
    assert first == candidate_narrative_evidence_from_bytes({"domain": data}, predecessor)
    assert first.has_blocking_findings


def test_adapter_surfaces_parser_error_instead_of_clean_result() -> None:
    predecessor = _stored_predecessor(_domain("entity-1.\n"))
    with pytest.raises(RoadmapArtifactError):
        candidate_narrative_evidence_from_bytes({"domain": b"not an artifact"}, predecessor)


def test_adapter_surfaces_unreadable_predecessor_instead_of_clean_result() -> None:
    bad = replace(_stored_predecessor(_domain("x\n")), artifact_bytes=(b"not an artifact",))
    data = render_domain_artifact(_domain("entity-1.\n")).encode()
    with pytest.raises(RoadmapArtifactError):
        candidate_narrative_evidence_from_bytes({"domain": data}, bad)


def test_integration_decisions_paragraph_fixture_yields_expected_finding() -> None:
    paragraph = _INTEGRATION_PARAGRAPH.read_bytes().decode("utf-8")
    removed = "decision-exclude-repo-browsing"
    evidence = _evidence(paragraph, removals=[_removal(removed)])
    (finding,) = evidence.blocking_findings
    assert finding.row_id == removed
    assert paragraph[finding.start : finding.end] == removed


def test_module_imports_no_backend_or_cli() -> None:
    """Covers lazy imports inside functions too: every Import node in the tree."""
    forbidden = (
        "plan_tool.roadmap",
        "plan_tool.roadmap_candidate_review",
        "plan_tool.cli",
        "plan_tool.backend",
        "plan_tool.shell",
        "plan_tool.launcher",
    )
    imported: list[str] = []
    for node in ast.walk(ast.parse(MODULE_PATH.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not [name for name in imported if name in forbidden or name.startswith("plan_tool.cli")]


def test_module_has_no_write_or_cache_path() -> None:
    """Evidence is recomputed on every call: no file write, no cache, no invoker seam."""
    source = MODULE_PATH.read_text(encoding="utf-8")
    for token in (
        "write_text",
        "write_bytes",
        "open(",
        "lru_cache",
        "functools",
        "invoker",
        "datetime",
        "time.time",
    ):
        assert token not in source, token
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, (ast.Dict, ast.List, ast.Set)):
            pytest.fail("module-level mutable container could cache results")
