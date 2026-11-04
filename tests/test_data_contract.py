"""Drift guard for ``DATA_CONTRACT.md`` (BACKLOG #63)."""

from __future__ import annotations

import dataclasses as dc
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, get_args, get_origin, get_type_hints

import pytest

from plan_tool import data_contract as contract
from plan_tool import concept_tree
from plan_tool import detail_artifacts
from plan_tool import grounding
from plan_tool import review as rv
from plan_tool import review_persistence as rp
from plan_tool import run_log as run_log_module
from plan_tool import schema
from plan_tool import telemetry as tm
from plan_tool.schema import Step

_DOC = Path(__file__).resolve().parents[1] / "DATA_CONTRACT.md"
_HEADING_RE = re.compile(r"^(#{2,6})\s+(.+?)\s*$", re.MULTILINE)
_FIELD_ROW_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)
_ROADMAP_EVIDENCE_LIFECYCLE_CONTRACTS = (
    "RoadmapStructuralRevisionPreflight",
    "RoadmapStructuralRevisionAttempt",
    "RoadmapEscalationPreflight",
    "RoadmapEscalationResult",
    "RoadmapImpactPreflight",
    "RoadmapImpactResult",
)


def _doc_text() -> str:
    return _DOC.read_text(encoding="utf-8")


def _section(text: str, title: str) -> str:
    headings = list(_HEADING_RE.finditer(text))
    for i, match in enumerate(headings):
        if title in match.group(2):
            level = len(match.group(1))
            end = len(text)
            for later in headings[i + 1 :]:
                if len(later.group(1)) <= level:
                    end = later.start()
                    break
            return text[match.start() : end]
    raise AssertionError(f"DATA_CONTRACT.md:{title} section is missing")


def _documented_field_names(section_text: str) -> set[str]:
    current = _HEADING_RE.search(section_text)
    search_from = current.end() if current else 0
    nested = _HEADING_RE.search(section_text, search_from)
    own_text = section_text[: nested.start()] if nested else section_text
    return set(_FIELD_ROW_RE.findall(own_text))


def _dataclass_contract(owner: str) -> contract.PersistedDataclassContract:
    for item in contract.persisted_dataclass_contracts():
        if item.owner == owner:
            return item
    raise AssertionError(f"registry missing {owner}")


def _stale_fields(
    item: contract.PersistedDataclassContract, section_text: str
) -> set[str]:
    documented = _documented_field_names(section_text)
    return documented - item.accepted_documented_fields


def _obsolete_dataclass_sections(text: str) -> set[str]:
    registered = {item.owner for item in contract.persisted_dataclass_contracts()}
    obsolete: set[str] = set()
    for match in _HEADING_RE.finditer(text):
        title = match.group(2)
        owner_match = re.match(r"`([^`]+)` \(`[^`]+\.py`", title)
        if owner_match and owner_match.group(1) not in registered:
            obsolete.add(owner_match.group(1))
    return obsolete


def _literal_values(annotation: object) -> set[object]:
    """Return closed literal values through optional and union wrappers."""
    if get_origin(annotation) is Literal:
        return set(get_args(annotation))
    return {
        value
        for argument in get_args(annotation)
        for value in _literal_values(argument)
    }


def test_data_contract_doc_exists() -> None:
    assert _DOC.is_file(), f"{_DOC} is missing"


def test_concept_ownership_contract_documented() -> None:
    section = _section(_doc_text(), "Authored plan concept ownership")
    assert "`steps[].concept_ids`" in section
    assert "defaults to `[]`" in section
    assert "frontmatter" in section
    assert "does not" in section and "concept exists" in section


def test_concept_ownership_contract_matches_step_schema() -> None:
    assert "concept_ids" in Step.model_fields
    field = Step.model_fields["concept_ids"]
    assert field.default_factory is list
    assert "`steps[].concept_ids`" in _section(
        _doc_text(), "Authored plan concept ownership"
    )


def test_contract_registry_names_persisted_dataclasses() -> None:
    owners = {item.owner for item in contract.persisted_dataclass_contracts()}
    assert {
        "SavedReview",
        "Annotation",
        "Recommendation",
        "Redirect",
        "DecisionEvent",
        "ProjectProfile",
    } <= owners


def test_contract_registry_names_concept_records() -> None:
    owners = {item.owner for item in contract.persisted_dataclass_contracts()}
    assert {"ConceptTree", "ConceptNode"} <= owners


def test_concept_contract_discovers_runtime_fields() -> None:
    tree = _dataclass_contract("ConceptTree")
    node = _dataclass_contract("ConceptNode")
    assert tree.field_names == tuple(f.name for f in dc.fields(concept_tree.ConceptTree))
    assert node.field_names == tuple(f.name for f in dc.fields(concept_tree.ConceptNode))


def test_concept_contract_is_documented() -> None:
    text = _doc_text()
    tree = _section(text, "ConceptTree")
    node = _section(text, "ConceptNode")
    assert "concepts.json" in tree
    assert "CONCEPTS_SCHEMA_VERSION" in tree
    assert "plan_fingerprint" in tree and "stale" in tree
    assert "`record_kind`" in tree
    assert "`bucket`" in node
    for name in _dataclass_contract("ConceptTree").field_names:
        assert f"`{name}`" in tree
    for name in _dataclass_contract("ConceptNode").field_names:
        assert f"`{name}`" in node
    assert "Identity excludes" in node
    for state in ("unreviewed", "approved", "rejected"):
        assert state in node


def test_contract_registry_discovers_dataclass_fields() -> None:
    saved = _dataclass_contract("SavedReview")
    rec = _dataclass_contract("Recommendation")
    assert saved.field_names == tuple(f.name for f in dc.fields(rp.SavedReview))
    assert rec.field_names == tuple(f.name for f in dc.fields(rv.Recommendation))
    assert "detail_bundle_fingerprint_present" in saved.field_names
    assert "anchor" in rec.field_names


def test_recommendation_confidence_contract_documented() -> None:
    section = _section(_doc_text(), "Recommendation")

    assert "`confidence`" in section
    assert "`supported`" in section and "`limited`" in section
    assert "unknown" in section.lower()
    assert "ReviewLoadError" in section


def test_purity_cache_confidence_contract_documented() -> None:
    section = _section(_doc_text(), "PurityCacheEntry")

    assert "`confidence`" in section
    assert "empty miss" in section


def test_saved_review_schema_version_alias_is_registered() -> None:
    saved = _dataclass_contract("SavedReview")
    assert saved.json_key_aliases["schema_version"] == "version"
    assert "version" in saved.persisted_json_keys


def test_saved_review_advisory_is_conditionally_persisted() -> None:
    saved = _dataclass_contract("SavedReview")
    assert "audit_shape_advisory" in saved.persisted_json_keys
    assert "audit_shape_advisory" not in saved.required_persisted_json_keys


def test_saved_review_coverage_is_conditionally_persisted() -> None:
    saved = _dataclass_contract("SavedReview")
    section = _section(_doc_text(), saved.section_title)

    assert "audit_coverage" in saved.persisted_json_keys
    assert "audit_coverage" not in saved.required_persisted_json_keys
    assert "completeness sidecars only" in section
    assert "unknown" in section.lower()


def test_data_contract_documents_conformance_coverage_keys() -> None:
    text = _doc_text()
    assert "`conforming_pass_count`" in text
    assert "`failed_or_malformed_pass_count`" in text
    assert "`conceptual_bar_blocking_ids`" in text


def test_data_contract_documents_plan_quota_coverage_stop() -> None:
    text = _doc_text()

    assert "`early_stop_reason`" in text
    assert "terminal plan quota" in text
    assert "ordinary final findings sidecar" in text


def test_normalize_audit_coverage_accepts_extended_key_set() -> None:
    from plan_tool.review_persistence import normalize_audit_coverage

    coverage = {
        "budget_limited": False,
        "passes_used": 1,
        "cap": 1,
        "recommendation_kind": None,
        "recommended_passes": None,
        "recommendation_advice": None,
        "confirmation_kind": "confirmed-dry",
        "conforming_pass_count": 1,
        "failed_or_malformed_pass_count": 0,
    }
    assert normalize_audit_coverage(coverage) is not None


@pytest.mark.parametrize(
    "field, bad_value",
    [
        ("conforming_pass_count", True),
        ("conforming_pass_count", -1),
        ("failed_or_malformed_pass_count", True),
        ("failed_or_malformed_pass_count", -1),
    ],
)
def test_normalize_audit_coverage_rejects_malformed_pass_counts(
    field: str, bad_value: object,
) -> None:
    """The bool-typed / non-int / negative guards on the two conformance
    counters are new; confirm each rejection branch actually fires rather
    than trusting the accept-path test above to imply it."""
    from plan_tool.review_persistence import normalize_audit_coverage

    coverage = {
        "budget_limited": False,
        "passes_used": 1,
        "cap": 1,
        "recommendation_kind": None,
        "recommended_passes": None,
        "recommendation_advice": None,
        "confirmation_kind": "confirmed-dry",
        "conforming_pass_count": 1,
        "failed_or_malformed_pass_count": 0,
    }
    coverage[field] = bad_value
    assert normalize_audit_coverage(coverage) is None


def test_saved_review_checkpoint_marker_is_conditionally_persisted() -> None:
    saved = _dataclass_contract("SavedReview")

    assert "is_pre_apply_checkpoint" in saved.field_names
    assert "is_pre_apply_checkpoint" in saved.persisted_json_keys
    assert "is_pre_apply_checkpoint" not in saved.required_persisted_json_keys


def test_saved_review_sampler_state_is_conditionally_registered() -> None:
    saved = _dataclass_contract("SavedReview")

    assert "sampler_state" in saved.field_names
    assert "sampler_state" in saved.persisted_json_keys
    assert "sampler_state" not in saved.required_persisted_json_keys
    assert "sampler_state" in saved.conditionally_persisted


def test_saved_review_sampler_state_and_role_are_documented() -> None:
    section = _section(_doc_text(), _dataclass_contract("SavedReview").section_title)

    assert "`sampler_state`" in section
    assert "`in-progress-sampler-checkpoint.json`" in section
    assert '`"in-progress"' in section
    assert '`"terminal-residue"' in section


def test_saved_review_audit_stage_is_conditionally_persisted() -> None:
    saved = _dataclass_contract("SavedReview")
    assert "audit_stage" in saved.persisted_json_keys
    assert "audit_stage" not in saved.required_persisted_json_keys
    assert "audit_stage" in saved.conditionally_persisted


def test_saved_review_checkpoint_marker_documented() -> None:
    text = _doc_text()
    section = _section(text, _dataclass_contract("SavedReview").section_title)

    assert "`is_pre_apply_checkpoint`" in section
    # The version fence, and the three normalized role states.
    assert "**`4`**" in _section(text, "Saved review sidecar")
    # Hyphen or space: the doc writes "version-3". Pin the fence, not the
    # spelling — a bare substring here breaks on any legitimate rewording.
    assert re.search(r"version[-\s]4", section)
    assert "Confirmed checkpoint" in section
    assert "Ordinary final" in section
    assert "Unknown" in section
    # The two states an unmarked or malformed sidecar must not be read as.
    assert "unmarked version-1/2 sidecar" in section
    assert "non-boolean marker" in section


def test_saved_review_qualified_result_contract_documented() -> None:
    text = _doc_text()
    assert "`qualified_result`" in text
    assert "`audit_revision`" in text
    assert "JSON `null`" in text
    assert "Versions `1`–`3`" in text


def test_saved_review_path_is_registered_as_in_memory_only() -> None:
    saved = _dataclass_contract("SavedReview")
    assert "path" in saved.field_names
    assert "path" in saved.in_memory_only
    assert "path" not in saved.persisted_field_names
    assert "`path`" in _section(_doc_text(), saved.section_title)


def test_saved_review_alias_and_in_memory_field_contract_documented() -> None:
    saved = _dataclass_contract("SavedReview")
    section = _section(_doc_text(), saved.section_title)
    assert "`schema_version`" in section
    assert "`version`" in section
    assert "`path`" in section
    assert "in-memory" in section.lower()


def test_intentional_exclusion_requires_reason() -> None:
    for item in contract.intentional_exclusions():
        assert item.owner
        assert item.field_or_key
        assert item.reason
        assert item.rationale
    assert "Intentional exclusions" in _doc_text()


def test_update_annotation_preserves_saved_review_contract_keys(tmp_path: Path) -> None:
    saved = _dataclass_contract("SavedReview")
    path = rp.save_review(
        plan_slug="x",
        plan_path="plans/1-x.md",
        repo_root=tmp_path,
        report_md="report",
        recommendations=[
            rv.Recommendation(
                id="rec-1",
                source="file-check",
                severity="high",
                step_id=1,
                title="title",
                body="body",
            )
        ],
        now=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        plan_fingerprint="plan",
        code_fingerprint={},
        detail_bundle_fingerprint={"plans/plan-details/x/1.md": "abc"},
    )
    before = json.loads(path.read_text(encoding="utf-8"))
    rp.update_annotation(path, "rec-1", rp.Annotation("applied", "done"))
    after = json.loads(path.read_text(encoding="utf-8"))
    assert set(saved.required_persisted_json_keys) <= set(after)
    for key in saved.required_persisted_json_keys:
        if key != "annotations":
            assert after[key] == before[key], key


@pytest.mark.parametrize(
    "item",
    contract.persisted_dataclass_contracts(),
    ids=lambda item: item.owner,
)
def test_every_persisted_field_is_documented_in_own_section(
    item: contract.PersistedDataclassContract,
) -> None:
    section = _section(_doc_text(), item.section_title)
    excluded = {entry.field_or_key for entry in item.intentional_exclusions}
    missing = [
        name
        for name in item.field_names
        if name not in excluded and f"`{name}`" not in section
    ]
    assert not missing, (
        f"{item.source_symbol} field(s) absent from "
        f"DATA_CONTRACT.md:{item.section_title} section: {missing}"
    )


@pytest.mark.parametrize(
    "item",
    contract.persisted_dataclass_contracts(),
    ids=lambda item: item.owner,
)
def test_conditionally_persisted_and_in_memory_only_name_real_fields(
    item: contract.PersistedDataclassContract,
) -> None:
    """A typo'd entry here would silently never match, not fail loudly."""
    fields = set(item.field_names)
    assert set(item.conditionally_persisted) <= fields
    assert set(item.in_memory_only) <= fields


def test_run_log_event_omit_when_none_matches_conditionally_persisted() -> None:
    """Keeps ``_emit``'s runtime omission and the registered contract in sync.

    The two can't be derived from each other (data_contract.py already
    imports run_log.py, so the reverse import would cycle), so this test is
    the tie between them instead.
    """
    for item in contract.persisted_dataclass_contracts():
        omit_when_none = getattr(item.cls, "omit_when_none", None)
        if omit_when_none is None:
            continue
        assert set(omit_when_none) == set(item.conditionally_persisted), item.owner


def test_decision_event_new_fields_documented() -> None:
    section = _section(_doc_text(), "DecisionEvent")
    for name in ("decision_id", "run_id", "plan_fingerprint", "code_fingerprint", "anchor"):
        assert f"`{name}`" in section, f"{name!r} absent from DecisionEvent section"
    assert "**`3` = `TELEMETRY_SCHEMA_VERSION`**" in section
    assert "plan-tool-code-fingerprint-v1" in section
    assert "computed empty map" in section
    assert "schema-v2 `{}`" in section


def test_schema_constants_are_documented_from_registry() -> None:
    text = _doc_text()
    for item in contract.persisted_dataclass_contracts():
        section = _section(text, item.section_title)
        for constant in item.schema_constants:
            assert constant in section, (
                f"{constant} absent from DATA_CONTRACT.md:{item.section_title} section"
            )


def test_plan_manifest_contract_is_documented_from_registry() -> None:
    item = next(c for c in contract.json_object_contracts() if c.owner == "Plan manifest")
    section = _section(_doc_text(), item.section_title)
    for value in item.path_labels + item.keys + item.required_phrases:
        assert value in section, f"{value!r} absent from DATA_CONTRACT.md:Plan manifest"


def test_grounding_contract_is_documented_from_registry() -> None:
    item = _dataclass_contract("Grounding")
    section = _section(_doc_text(), item.section_title)
    assert "grounding.json" in section
    for name in item.field_names:
        assert f"`{name}`" in section, f"{name!r} absent from Grounding section"
    assert "freshness" in section


def test_artifact_format_version_contracts_registered() -> None:
    owners = {item.owner for item in contract.artifact_format_version_contracts()}
    assert owners == {"Plan format version", "Detail format version"}


def _format_version_contract(owner: str) -> contract.ArtifactFormatVersionContract:
    for item in contract.artifact_format_version_contracts():
        if item.owner == owner:
            return item
    raise AssertionError(f"registry missing {owner}")


def test_plan_format_version_binds_live_constant() -> None:
    """Pins that the registry reads the live constant rather than a copied
    literal — a stale hand-typed value here would not move when the module's
    constant changes."""
    item = _format_version_contract("Plan format version")
    assert item.current_version == schema.PLAN_FORMAT_VERSION
    assert item.supported_versions == frozenset(schema.SUPPORTED_PLAN_FORMAT_VERSIONS)


def test_detail_format_version_binds_live_constant() -> None:
    """Same live-binding guarantee as the plan entry, for the detail class."""
    item = _format_version_contract("Detail format version")
    assert item.current_version == detail_artifacts.DETAIL_FORMAT_VERSION
    assert item.supported_versions == frozenset(
        detail_artifacts.SUPPORTED_DETAIL_FORMAT_VERSIONS
    )


def test_artifact_format_version_contract_is_version_only() -> None:
    """Pins the deliberate carve-out: this record never grows a ``cls``,
    ``field_names``, ``json_key_aliases``, or other schema-shape field — it
    names constants and policy, nothing about an artifact's content shape."""
    field_names = {f.name for f in dc.fields(contract.ArtifactFormatVersionContract)}
    assert field_names == {
        "owner",
        "section_title",
        "source_symbol",
        "version_constant",
        "supported_versions_constant",
        "current_version",
        "supported_versions",
    }


def test_plan_format_version_documented_with_live_value() -> None:
    item = _format_version_contract("Plan format version")
    section = _section(_doc_text(), "Plan format version")
    assert f"`{item.version_constant}`" in section
    assert f"`{item.supported_versions_constant}`" in section
    assert f"`{item.current_version}`" in section


def test_detail_format_version_documented_with_live_value() -> None:
    item = _format_version_contract("Detail format version")
    section = _section(_doc_text(), "Detail format version")
    assert f"`{item.version_constant}`" in section
    assert f"`{item.supported_versions_constant}`" in section
    assert f"`{item.current_version}`" in section


def test_plan_format_version_class_rules_documented() -> None:
    section = _section(_doc_text(), "Plan format version")
    assert 'extra="forbid"' in section
    assert "must bump" in section
    assert "except for the named" in section
    assert "Version-1 step alias exception" in section
    assert "owner-confirmed 2026-10-22 (#517)" in section
    assert "retaining format version 1 without an explicit upgrade" in section
    assert "Existing\n  plans remain readable and writable" in section
    assert "Older installations that do not recognize" in section
    assert "reject newly emitted keys through strict validation" in section
    assert "permits no arbitrary unknown fields" in section
    assert "effective-older plan" in section
    assert "current-minus-one" in section
    assert "dated, user-approved record" in section
    assert "operator-invocable upgrade route" in section
    assert "compatibility preflight" in section
    assert "state change" in section


def test_detail_format_version_class_rules_documented() -> None:
    section = _section(_doc_text(), "Detail format version")
    assert "additive and does not bump" in section
    assert "carrier move" in section
    assert "current-minus-one" in section
    assert "forced re-authoring" in section
    assert "dated, user-approved record" in section
    assert "operator-invocable upgrade route" in section
    assert "compatibility preflight" in section
    assert "historical snapshot" in section
    assert "no live reader obligation" in section
    assert "no upgrade obligation" in section


def test_data_contract_scope_names_authored_artifact_versions() -> None:
    text = _doc_text()
    scope = text[: text.index("\n## ")]
    assert "format-version" in scope
    assert "PLAN_FORMAT.md" in scope
    assert "DETAIL_FORMAT.md" in scope
    assert "JIRA_FORMAT.md" in scope


def test_artifact_format_version_owners_do_not_collide_with_existing_registries() -> None:
    dataclass_owners = {c.owner for c in contract.persisted_dataclass_contracts()}
    json_owners = {c.owner for c in contract.json_object_contracts()}
    version_owners = {c.owner for c in contract.artifact_format_version_contracts()}
    assert version_owners.isdisjoint(dataclass_owners)
    assert version_owners.isdisjoint(json_owners)


def test_purity_cache_entry_is_registered() -> None:
    owners = {c.owner for c in contract.persisted_dataclass_contracts()}
    assert "PurityCacheEntry" in owners


def test_backend_observability_events_are_registered() -> None:
    owners = {c.owner for c in contract.persisted_dataclass_contracts()}
    assert {
        "BackendSpawn",
        "BackendTermination",
        "RunInterrupted",
        "BackendRecoveryWait",
    } <= owners


def test_structural_revision_event_contracts_are_registered_and_documented() -> None:
    owners = {item.owner for item in contract.persisted_dataclass_contracts()}
    expected = {
        "RoadmapStructuralRevisionPreflight",
        "RoadmapStructuralRevisionAttempt",
    }
    assert expected <= owners
    text = _doc_text()
    for owner in expected:
        item = _dataclass_contract(owner)
        section = _section(text, item.section_title)
        for field in item.field_names:
            assert f"`{field}`" in section, (
                f"{field!r} absent from DATA_CONTRACT.md:{item.section_title}"
            )
    assert "evaluator-rejected" in _section(text, "RoadmapStructuralRevisionPreflight")
    assert "changed-brief" in _section(text, "RoadmapStructuralRevisionPreflight")
    assert "legacy-brief" in _section(text, "RoadmapStructuralRevisionPreflight")
    assert "final-snapshot-stale" in _section(
        text, "RoadmapStructuralRevisionAttempt"
    )
    assert "changed-brief" in _section(text, "RoadmapStructuralRevisionAttempt")
    assert "legacy-brief" in _section(text, "RoadmapStructuralRevisionAttempt")


def test_roadmap_evidence_lifecycle_contracts_are_registered_and_documented() -> None:
    """Keep every registered evidence event field and closed result documented."""
    owners = {item.owner for item in contract.persisted_dataclass_contracts()}
    assert set(_ROADMAP_EVIDENCE_LIFECYCLE_CONTRACTS) <= owners
    text = _doc_text()
    for owner in _ROADMAP_EVIDENCE_LIFECYCLE_CONTRACTS:
        item = _dataclass_contract(owner)
        section = _section(text, item.section_title)
        assert set(item.field_names) <= _documented_field_names(section)
        for field in ("verdict", "outcome"):
            annotation = get_type_hints(item.cls).get(field)
            if annotation is None:
                continue
            for value in _literal_values(annotation):
                assert f'"{value}"' in section, (
                    f"{value!r} absent from DATA_CONTRACT.md:{item.section_title}.{field}"
                )


def test_roadmap_evidence_lifecycle_reference_remains_redacted() -> None:
    """Document durable evidence events without admitting sensitive payload fields."""
    text = _doc_text()
    section = _section(text, "Roadmap evidence lifecycle records")
    for boundary in (
        "source prose",
        "baseline contents",
        "reviewer requests",
        "prompts",
        "replies",
        "backend text",
    ):
        assert boundary in section

    documented_fields = set().union(
        *(
            _documented_field_names(_section(text, owner))
            for owner in _ROADMAP_EVIDENCE_LIFECYCLE_CONTRACTS
        )
    )
    assert documented_fields.isdisjoint(
        {
            "source_prose",
            "baseline_contents",
            "reviewer_request",
            "prompt",
            "reply",
            "backend_text",
        }
    )


def test_purity_cache_entry_documented() -> None:
    item = _dataclass_contract("PurityCacheEntry")
    section = _section(_doc_text(), item.section_title)
    for name in item.field_names:
        assert f"`{name}`" in section, f"{name!r} absent from PurityCacheEntry section"
    for constant in item.schema_constants:
        assert constant in section, f"{constant} absent from PurityCacheEntry section"


def test_purity_cache_file_contract_documented() -> None:
    item = next(
        c for c in contract.json_object_contracts() if c.owner == "Purity findings cache"
    )
    section = _section(_doc_text(), item.section_title)
    for value in item.path_labels + item.keys:
        assert value in section, (
            f"{value!r} absent from DATA_CONTRACT.md:Purity findings cache"
        )


def test_project_config_contract_is_documented_from_registry() -> None:
    item = next(
        c for c in contract.json_object_contracts() if c.owner == "Project configuration"
    )
    section = _section(_doc_text(), item.section_title)
    for value in item.path_labels + item.keys:
        assert value in section, (
            f"{value!r} absent from DATA_CONTRACT.md:Project configuration"
        )


def test_project_config_contract_registers_stage_feedback_limits() -> None:
    item = next(
        c for c in contract.json_object_contracts() if c.owner == "Project configuration"
    )
    assert {
        "roadmap_feedback",
        "stage_limits",
        "max_active_feedback_items",
        "max_response_bytes",
        "max_prose_amendment_bytes",
    } <= set(item.keys)


def test_project_config_reference_keeps_stage_feedback_limits_project_only() -> None:
    """Keep the strict registry leaves tied to their documented ownership."""
    section = _section(_doc_text(), "Project configuration")
    for boundary in (
        "roadmap_feedback.stage_limits",
        "can lower but never raise",
        "no user-level fallback",
        "fails command preflight before a backend call",
    ):
        assert boundary in section


@pytest.mark.parametrize(
    "item",
    contract.persisted_dataclass_contracts(),
    ids=lambda item: item.owner,
)
def test_documented_fields_are_registered_or_aliases(
    item: contract.PersistedDataclassContract,
) -> None:
    stale = _stale_fields(item, _section(_doc_text(), item.section_title))
    assert not stale, (
        f"DATA_CONTRACT.md:{item.section_title} section documents stale fields: "
        f"{sorted(stale)}"
    )


def test_stale_documented_field_fails_contract_check() -> None:
    item = _dataclass_contract("Annotation")
    section = """
### `Annotation` (`review_persistence.py`)

| Field | Meaning |
|---|---|
| `status` | current status |
| `ghost` | stale field |
"""
    assert _stale_fields(item, section) == {"ghost"}


def test_obsolete_contract_section_fails_contract_check() -> None:
    text = """
## Saved review sidecar

### `RetiredRecord` (`review_persistence.py`)

| Field | Meaning |
|---|---|
| `id` | old |
"""
    assert _obsolete_dataclass_sections(text) == {"RetiredRecord"}
    assert _obsolete_dataclass_sections(_doc_text()) == set()


def test_drift_record_contains_apply_payload() -> None:
    record = contract.make_drift_record(
        source_type="dataclass",
        owner="SavedReview",
        field_or_key="detail_bundle_fingerprint",
        target_section="SavedReview",
        operation="add",
        contract_text=_doc_text(),
        candidate={"type": "dict[str, str]", "json_key": "detail_bundle_fingerprint"},
    )
    assert record.operation == "add"
    assert record.registry_fingerprint
    assert record.contract_fingerprint
    assert record.candidate["target_section"] == "SavedReview"
    assert record.candidate["json_key"] == "detail_bundle_fingerprint"


def test_report_kinds_documented() -> None:
    text = _doc_text()
    for kind in ("detail-reconcile", "run-reconcile", "completeness"):
        assert kind in text, f"report kind {kind!r} not documented"


def test_data_contract_apply_workflow_documented() -> None:
    text = _doc_text()
    assert 'source="data-contract"' in text
    assert "plan-tool data-contract-apply" in text
    assert "saved-review schema" in text


def test_completeness_persists_mixed_step_split_documented() -> None:
    section = _section(_doc_text(), "Saved review sidecar")
    assert "granularity-split" in section
    assert "mixed" in section.lower()
    assert "recommendations" in section


def test_create_granularity_decisions_documented() -> None:
    text = _doc_text()
    for decision in ("create-review", "create-step-outcome"):
        assert decision in text, f"create telemetry decision {decision!r} not documented"


def test_create_granularity_context_keys_documented() -> None:
    text = _doc_text()
    for key in (
        "stage",
        "assessment_id",
        "steps",
        "candidate_fingerprint",
        "file_footprint",
        "split",
        "split_steps",
        "merge",
        "split_step_ids",
        "predicate_counts",
        "can_split",
        "mode",
        "step_id",
        "had_split_hint",
        "proposed_change_type",
        "resolved_change_type",
        "action",
        "before_steps",
        "after_steps",
        "error_class",
    ):
        assert f"`{key}`" in text, f"create telemetry context key {key!r} not documented"


def test_create_assessment_join_semantics_documented() -> None:
    section = _section(_doc_text(), "Create granularity decisions")
    normalized = " ".join(section.split())
    assert "fresh per-pass association" in normalized
    assert "successfully appended" in normalized
    assert "suppresses every child" in normalized
    assert "review event alone" in normalized
    assert "`plan_slug` plus `ts` can collide" in normalized
    assert "Legacy create rows remain readable" in normalized
    assert "cannot be linked unambiguously" in normalized


def test_create_granularity_dedupe_semantics_documented() -> None:
    text = _doc_text()
    assert 'mode="checkpoint"' in text
    assert '"fresh signal fired"' in text
    assert "`plan_slug` plus `candidate_fingerprint`" in text


def test_create_granularity_action_semantics_documented() -> None:
    text = _doc_text()
    for action in (
        "accept",
        "override",
        "unclassified-accepted",
        "unclassified-classified",
        "split-requested",
        "split-applied",
        "split-unusable",
        "split-invalid",
        "split-error",
    ):
        assert action in text, f"create telemetry action {action!r} not documented"
    assert "resolved change type equals the proposed change type" in text


def test_plan_criteria_decision_documented() -> None:
    assert "plan-criteria-breakdown" in _doc_text()


def test_plan_criteria_context_keys_documented() -> None:
    # code_fingerprint is NOT a plan-criteria context key (it is base-homed only);
    # plan_fingerprint stays dual-homed so split_criteria.py's context reader works.
    text = _doc_text()
    for key in (
        "plan_fingerprint",
        "criteria",
        "criteria_count",
        "fired_count",
    ):
        assert f"`{key}`" in text, f"plan-criteria context key {key!r} not documented"


def test_prompt_budget_decision_documented() -> None:
    assert "prompt-budget" in _doc_text()


def test_prompt_budget_context_keys_documented() -> None:
    text = _doc_text()
    for key in (
        "phase",
        "total_bytes",
        "advisory",
        "estimated_tokens",
        "context_window",
        "headroom_ratio",
        "blocks",
    ):
        assert f"`{key}`" in text, f"prompt-budget context key {key!r} not documented"


def test_drift_gate_decision_documented() -> None:
    assert "drift-gate" in _doc_text()


def test_drift_gate_context_keys_documented() -> None:
    text = _doc_text()
    for key in ("verdict", "drifted_files", "findings"):
        assert f"`{key}`" in text, f"drift-gate context key {key!r} not documented"


def test_apply_verdict_decision_documented() -> None:
    assert "apply-verdict" in _doc_text()


def test_apply_verdict_context_keys_documented() -> None:
    text = _section(_doc_text(), "Apply verdict")
    for key in ("verdict", "step_id"):
        assert f"`{key}`" in text, f"apply-verdict context key {key!r} not documented"
    assert "`INVOCATION-FAILED`" in text
    assert "`UNKNOWN`" in text
    assert "zero-exit response" in text


def test_apply_verdict_preserves_tokens_without_retired_replay_writer() -> None:
    text = _section(_doc_text(), "Apply verdict")
    for token in ("APPLIED", "NOT-APPLICABLE", "BLOCKED", "BLOCKED-STRUCTURAL",
                  "UNKNOWN", "INVOCATION-FAILED"):
        assert f'`"{token}"`' in text
    assert "replay_results" not in text


def test_escalate_split_decision_documented() -> None:
    assert "escalate-split" in _doc_text()


def test_escalate_split_context_keys_documented() -> None:
    text = _doc_text()
    for key in ("outcome", "allow_split", "step_id", "blocking"):
        assert f"`{key}`" in text, f"escalate-split context key {key!r} not documented"


def test_registry_uses_runtime_constants() -> None:
    saved = _dataclass_contract("SavedReview")
    decision = _dataclass_contract("DecisionEvent")
    ground = _dataclass_contract("Grounding")
    assert saved.cls is rp.SavedReview
    assert decision.cls is tm.DecisionEvent
    assert ground.cls is grounding.Grounding


def _input_doc(body: str) -> str:
    return f"# Plan\n\n## Input\n\n{body}\n\n## Implementation\n\nDo it.\n"


def test_input_contract_reference_accepts_registered_dataclass_field_with_anchor() -> None:
    issues = contract.check_input_contract_references(
        _input_doc(
            "Reads `SavedReview.recommendations` from "
            "`plan_tool/review_persistence.py:SavedReview`."
        ),
        _DOC.parents[0],
        location="plan.md:## Input",
    )
    assert issues == []


def test_input_contract_reference_accepts_serialized_alias_with_anchor() -> None:
    issues = contract.check_input_contract_references(
        _input_doc(
            "Reads `SavedReview.version` from "
            "`plan_tool/review_persistence.py:SavedReview`."
        ),
        _DOC.parents[0],
        location="detail.md:## Input",
    )
    assert issues == []


def test_input_contract_reference_flags_unknown_field() -> None:
    issues = contract.check_input_contract_references(
        _input_doc(
            "Reads `SavedReview.not_a_field` from "
            "`plan_tool/review_persistence.py:SavedReview`."
        ),
        _DOC.parents[0],
        location="detail.md:## Input",
    )
    assert len(issues) == 1
    assert issues[0].owner == "SavedReview"
    assert issues[0].field_or_key == "not_a_field"


def test_input_contract_reference_requires_code_location_anchor() -> None:
    issues = contract.check_input_contract_references(
        _input_doc("Reads `SavedReview.recommendations`."),
        _DOC.parents[0],
        location="detail.md:## Input",
    )
    assert len(issues) == 1
    assert "lacks a matching HEAD code-location anchor" in issues[0].reason


def test_input_contract_reference_accepts_valid_code_location_anchor() -> None:
    issues = contract.check_input_contract_references(
        _input_doc(
            "Uses `plan_tool/review_persistence.py:SavedReview` and "
            "`plan_tool/review.py:Recommendation.source`."
        ),
        _DOC.parents[0],
        location="plan.md:## Input",
    )
    assert issues == []


def test_input_contract_reference_flags_stale_code_location_anchor() -> None:
    issues = contract.check_input_contract_references(
        _input_doc("Uses `plan_tool/review_persistence.py:MissingSymbol`."),
        _DOC.parents[0],
        location="plan.md:## Input",
    )
    assert len(issues) == 1
    assert issues[0].code_anchor == "plan_tool/review_persistence.py:MissingSymbol"


def test_input_contract_reference_flags_absent_path_without_planned_paths() -> None:
    issues = contract.check_input_contract_references(
        _input_doc("Uses `plan_tool/not_yet_written.py:Thing`."),
        _DOC.parents[0],
        location="detail.md:## Input",
    )
    assert len(issues) == 1
    assert "does not exist" in issues[0].reason


def test_input_contract_reference_accepts_path_the_plan_creates() -> None:
    issues = contract.check_input_contract_references(
        _input_doc("Uses `plan_tool/not_yet_written.py:Thing`."),
        _DOC.parents[0],
        location="detail.md:## Input",
        planned_paths={"plan_tool/not_yet_written.py"},
    )
    assert issues == []


def test_input_contract_reference_normalizes_planned_path_forms() -> None:
    issues = contract.check_input_contract_references(
        _input_doc("Uses `plan_tool/not_yet_written.py:Thing`."),
        _DOC.parents[0],
        location="detail.md:## Input",
        planned_paths=["./plan_tool/not_yet_written.py"],
    )
    assert issues == []


def test_normalize_planned_paths_keeps_dotted_directory() -> None:
    # ``lstrip("./")`` would eat the leading dot and yield ``plan-tool/x.py``.
    assert contract._normalize_planned_paths([".plan-tool/x.py"]) == frozenset(
        {".plan-tool/x.py"}
    )


def test_planned_path_does_not_excuse_a_stale_symbol_on_a_real_file() -> None:
    # The file exists, so the anchor is checked normally even though the plan
    # also lists it under ``creates:``.
    issues = contract.check_input_contract_references(
        _input_doc("Uses `plan_tool/review_persistence.py:MissingSymbol`."),
        _DOC.parents[0],
        location="detail.md:## Input",
        planned_paths={"plan_tool/review_persistence.py"},
    )
    assert len(issues) == 1
    assert issues[0].code_anchor == "plan_tool/review_persistence.py:MissingSymbol"
    assert "does not resolve in HEAD" in issues[0].reason


@pytest.mark.parametrize("planned_paths", [(), ("plan_tool/review_persistence.py",)])
def test_existing_valid_symbol_remains_valid_when_path_is_planned(planned_paths) -> None:
    assert contract.check_input_contract_references(
        _input_doc("Uses `plan_tool/review_persistence.py:SavedReview`."),
        _DOC.parents[0],
        location="detail.md:## Input",
        planned_paths=planned_paths,
    ) == []


def test_code_anchor_resolves_via_monorepo_subdirectory_root(tmp_path: Path) -> None:
    # Written relative to a subdirectory project root (e.g. a monorepo's
    # ``backend-py/``), not the git repo root — still a real file. See
    # BUG_BACKLOG.
    nested = tmp_path / "backend-py" / "app" / "db" / "queries"
    nested.mkdir(parents=True)
    (nested / "oauth_credentials.py").write_text("value = 1\n", encoding="utf-8")
    issues = contract.check_input_contract_references(
        _input_doc("Reads via `app/db/queries/oauth_credentials.py`."),
        tmp_path,
        location="detail.md:## Input",
    )
    assert issues == []


def test_code_anchor_bare_filename_is_never_fallback_resolved(
    tmp_path: Path,
) -> None:
    # Deliberately NOT resolved via tail-match, even uniquely: a bare name
    # is a global, non-distinctive search (unlike a multi-segment suffix),
    # so it risks silently validating an unrelated file with the same
    # generic name (e.g. `config.py`) elsewhere in the repo. See
    # BUG_BACKLOG.
    nested = tmp_path / "tests" / "integration"
    nested.mkdir(parents=True)
    (nested / "test_qbo_realm_release.py").write_text("", encoding="utf-8")
    issues = contract.check_input_contract_references(
        _input_doc("See `test_qbo_realm_release.py`."),
        tmp_path,
        location="detail.md:## Input",
    )
    assert len(issues) == 1
    assert "does not exist" in issues[0].reason


def test_code_anchor_ambiguous_tail_match_still_reports_missing(
    tmp_path: Path,
) -> None:
    # Two real files could satisfy the multi-segment suffix — an ambiguous
    # tail match must not silently pick a side.
    (tmp_path / "one" / "queries").mkdir(parents=True)
    (tmp_path / "two" / "queries").mkdir(parents=True)
    (tmp_path / "one" / "queries" / "shared_name.py").write_text(
        "", encoding="utf-8"
    )
    (tmp_path / "two" / "queries" / "shared_name.py").write_text(
        "", encoding="utf-8"
    )
    issues = contract.check_input_contract_references(
        _input_doc("Uses `queries/shared_name.py`."),
        tmp_path,
        location="detail.md:## Input",
    )
    assert len(issues) == 1
    assert "does not exist" in issues[0].reason


def test_code_anchor_walk_is_shared_across_anchors_in_one_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Several unresolved anchors in the same ## Input section must trigger
    # one fallback walk, not one per anchor. See BUG_BACKLOG.
    calls: list[Path] = []
    original = contract._walk_anchor_search_tree

    def counting_walk(repo_root: Path) -> tuple[str, ...]:
        calls.append(repo_root)
        return original(repo_root)

    monkeypatch.setattr(contract, "_walk_anchor_search_tree", counting_walk)
    issues = contract.check_input_contract_references(
        _input_doc(
            "Uses `tests/integration/missing_one.py` and "
            "`tests/integration/missing_two.py`."
        ),
        tmp_path,
        location="detail.md:## Input",
    )
    assert len(issues) == 2
    assert len(calls) == 1


def test_input_contract_reference_accepts_registered_context_key() -> None:
    issues = contract.check_input_contract_references(
        _input_doc(
            "Reads `DecisionEvent.context.stage` from "
            "`plan_tool/telemetry.py:DecisionEvent`."
        ),
        _DOC.parents[0],
        location="plan.md:## Input",
    )
    assert issues == []


@pytest.mark.parametrize(
    "key",
    (
        "early_stop_reason",
        "backend",
        "classified_as",
        "markers",
        "excerpt",
        "phase",
    ),
)
def test_input_contract_reference_accepts_plan_quota_context_keys(key: str) -> None:
    issues = contract.check_input_contract_references(
        _input_doc(
            f"Reads `DecisionEvent.context.{key}` from "
            "`plan_tool/telemetry.py:DecisionEvent`."
        ),
        _DOC.parents[0],
        location="plan.md:## Input",
    )
    assert issues == []


def test_input_contract_reference_accepts_registered_references_with_anchors() -> None:
    issues = contract.check_input_contract_references(
        _input_doc(
            "Reads persisted field `SavedReview.recommendations`, serialized "
            "alias `SavedReview.version`, and context key "
            "`DecisionEvent.context.stage` from "
            "`plan_tool/review_persistence.py:SavedReview` and "
            "`plan_tool/telemetry.py:DecisionEvent`."
        ),
        _DOC.parents[0],
        location="plan.md:## Input",
    )
    assert issues == []


def test_input_contract_reference_ignores_non_contract_backticks() -> None:
    issues = contract.check_input_contract_references(
        _input_doc(
            "Run `pytest tests/test_data_contract.py`; prose mentions "
            "`UnknownOwner.field` and `README.md`."
        ),
        _DOC.parents[0],
        location="plan.md:## Input",
    )
    assert issues == []


def test_missing_input_section_has_no_issue() -> None:
    issues = contract.check_input_contract_references(
        "# Plan\n\n## Implementation\n\nUses `SavedReview.missing`.\n",
        _DOC.parents[0],
        location="plan.md",
    )
    assert issues == []


def test_data_contract_documents_impact_brief_refusal_vocabulary() -> None:
    preflight = _section(_doc_text(), "RoadmapImpactPreflight")
    result = _section(_doc_text(), "RoadmapImpactResult")

    for outcome in ("changed-brief", "legacy-brief"):
        assert f'`"{outcome}"`' in preflight
        assert f'`"{outcome}"`' in result
    assert "leave every snapshot and closure fact `null`" in " ".join(preflight.split())
    assert "leaves all four analysis facts `null`" in result


def test_removed_run_log_events_are_absent_from_the_registry_and_the_doc() -> None:
    """The source.json and legacy-revision events are deleted; neither the registry nor the doc names them."""
    owners = {item.owner for item in contract.persisted_dataclass_contracts()}
    text = _doc_text()
    for removed in (
        "RoadmapSourceResolved",
        "RoadmapSourceRecorded",
        "RoadmapSourceAdmission",
        "RoadmapLocalRevisionPreflight",
        "RoadmapLocalRevisionAttempt",
        "RevisionFeedbackDelivered",
    ):
        assert removed not in owners
        assert not hasattr(run_log_module, removed)
        assert removed not in text


def test_saved_review_qualified_result_contract_documents_run_grade_only_evidence():
    contract = (Path(__file__).resolve().parents[1] / "DATA_CONTRACT.md").read_text()
    assert "Revision versions 1, 2, and 3 remain supported" in contract
    assert "Explicit retired Jira-grade evidence and malformed revisions are unavailable" in contract
    assert "reads never rewrite archived sidecars" in contract
    gate = _section(contract, "Saved gate verdict")
    grade_value = re.search(r'^\| `detail_grade` \| (.*?) \|$', gate, re.MULTILINE)
    assert grade_value is not None
    assert grade_value.group(1) == 'literal `"run"`'
    audit_fields = _documented_field_names(_section(contract, "`completeness-audit --json`"))
    assert {"detail_grade", "detail_bundle_fingerprint"}.isdisjoint(audit_fields)
