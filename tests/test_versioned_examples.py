"""Captured examples of each version of a persisted format must still load.

``tests/fixtures/versioned/`` holds files written by the code of the release or
commit in each name, captured once and never edited. A record built from today's
output only checks the shape its author expects; these check what an older
release really wrote. A failing example means the reader regressed: fix the
reader, not the example. See ``tests/fixtures/versioned/README.md``.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

import pytest
import yaml

from plan_tool.checkpoint import CHECKPOINT_SCHEMA_VERSION, Checkpoint, load_if_valid
from plan_tool.cli.data_contract_cmd import _filter_candidates, _load_payloads
from plan_tool.concept_tree import (
    CONCEPTS_SCHEMA_VERSION,
    StaleConceptTreeError,
    concepts_path,
    load_concepts,
)
from plan_tool.detail import parse_acceptance_bullets
from plan_tool.detail_artifacts import SUPPORTED_DETAIL_FORMAT_VERSIONS
from plan_tool.grounding import (
    GROUNDING_SCHEMA_VERSION,
    Grounding,
    grounding_path,
    read_grounding,
)
from plan_tool.parser import parse_plan, split_plan_document
from plan_tool.project_profile import (
    PROJECT_PROFILE_SCHEMA_VERSION,
    ProjectProfile,
    project_profile_path,
    read_project_profile,
)
from plan_tool.purity_cache import PURITY_CACHE_SCHEMA_VERSION, load_purity_cache
from plan_tool.renderer import _load_detail
from plan_tool.review_persistence import (
    _SUPPORTED_SCHEMA_VERSIONS,
    AuditInputSnapshot,
    load_review,
)
from plan_tool.schema import SUPPORTED_PLAN_FORMAT_VERSIONS

FIXTURES = Path(__file__).parent / "fixtures" / "versioned"
EXAMPLES = sorted((FIXTURES / "saved-review").glob("*.json"))
# Explicit versions of the plan and its detail, respectively.
AUTHORED_VERSIONS = {
    "v0.2.0": (1, 1),
    "5d9ce9aca": (None, None),
}
CAPTURED_DETAIL = "plan-details/orch/01-wire-up-renderer.md"
CAPTURED_DATA_CONTRACT_REPORT = (
    FIXTURES / "data-contract" / "v1.8.0" / "20260526-120000-completeness.json"
)
CHECKPOINT_EXAMPLES = {
    "checkpoint/v1.8.0/cp.json": Checkpoint(
        input_hash="match",
        payload="hello",
        created_at="2026-11-20T04:10:32+00:00",
        schema_version=1,
    ),
}
GROUNDING_EXAMPLES = {
    "grounding/v1.8.0/2-foo.md": Grounding(
        plan_slug="foo",
        grounded_at="2026-11-20T13:27:04Z",
        plan_fingerprint="b",
        code_fingerprint={"x": "y"},
        step_authoring_fingerprints={"1": "fp1", "2": "fp2"},
        schema_version=1,
    ),
}
CONCEPT_EXAMPLES = {
    "concepts/v1.8.0/full-tree/1-sample.md": (1, "full-tree"),
    "concepts/v1.8.0/decision-record/1-sample.md": (1, "decision-record"),
}
PURITY_CACHE_EXAMPLES = {
    "purity-cache/v1.8.0/checked-pure/x.json": 1,
    "purity-cache/v1.8.0/pruned-steps/x.json": 1,
}
PROJECT_PROFILE_EXAMPLES = {
    "project-profile/v1.8.0": ProjectProfile(
        schema_version=1,
        intent="Keep delivery planning grounded in the current product.",
        non_goals=("Do not infer unstated priorities.", "Do not change create yet."),
        decisions=("Do not execute a plan without a demonstrated problem.",),
    ),
}
NAME_RE = re.compile(
    r"^(?P<shape>[a-z-]+)\.sidecar-v(?P<sidecar>\d+)"
    r"(?:\.revision-v(?P<revision>\d+))?\.(?P<source>.+)\.json$"
)
SHAPE_KIND = {
    "completeness-final": "completeness",
    "completeness-checkpoint": "completeness",
    "completeness-legacy": "completeness",
    "completeness-advisory": "completeness",
    "completeness-checkpoint-no-revision": "completeness",
    "review": "review",
    "run-reconcile": "run-reconcile",
    "detail-reconcile": "detail-reconcile",
}


def _parts(path: Path) -> re.Match[str]:
    match = NAME_RE.match(path.name)
    assert match, f"{path.name} does not follow <shape>.sidecar-vN[.revision-vM].<source>.json"
    assert match["shape"] in SHAPE_KIND, path.name
    return match


PARTS = {path: _parts(path) for path in EXAMPLES}


def _raw_revision(raw: dict, shape: str) -> dict | None:
    if shape == "completeness-final":
        return raw["qualified_result"]["audit_revision"]
    if shape == "completeness-checkpoint":
        return raw["checkpoint_audit_revision"]
    return None


def _current_revision_version(tmp_path: Path) -> int:
    plan = tmp_path / "plan.md"
    plan.write_text(
        "---\ntitle: Demo\nstatus: planning\npriority: medium\nsteps:\n"
        "  - id: 1\n    title: First\n---\n\n# Plan\n",
        encoding="utf-8",
    )
    return AuditInputSnapshot.capture(plan, tmp_path).revision["version"]


def test_examples_exist() -> None:
    assert EXAMPLES, "tests/fixtures/versioned/saved-review/ holds no examples"


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_a_captured_example_loads_through_the_current_reader(path: Path, tmp_path: Path) -> None:
    """The file's own claims (sidecar and revision version, kind, shape) hold, and the reader
    keeps its meaning: kind, checkpoint flag, recommendations, and the revision upgraded to
    today's version with the digests an older record lacked read as ``None``."""
    parts = PARTS[path]
    raw = json.loads(path.read_text(encoding="utf-8"))
    saved = load_review(path)

    assert raw["version"] == int(parts["sidecar"])
    assert saved.kind == SHAPE_KIND[parts["shape"]]
    assert [(r.id, r.severity, r.impact, r.step_id) for r in saved.recommendations] == [
        (r["id"], r["severity"], r.get("impact"), r.get("step_id")) for r in raw["recommendations"]
    ]
    assert saved.plan_fingerprint == raw["plan_fingerprint"]
    assert saved.is_pre_apply_checkpoint is bool(raw.get("is_pre_apply_checkpoint"))
    if parts["shape"] == "completeness-advisory":
        assert saved.audit_shape_advisory is not None
        assert saved.audit_shape_advisory.shape_id == raw["audit_shape_advisory"]["shape_id"]

    raw_revision = _raw_revision(raw, parts["shape"])
    if parts["revision"] is None:
        assert raw_revision is None
        assert saved.audit_revision is None and saved.qualified_result is None
        return

    assert raw_revision is not None and raw_revision["version"] == int(parts["revision"])
    current = _current_revision_version(tmp_path)
    loaded = saved.audit_revision
    assert loaded is not None, "the reader dropped a revision an older release wrote"
    # The expected record is written out here, not computed by the reader: a current-version
    # revision loads unchanged, and an older one gains only its version and the digests it
    # lacked, read as None (a report of a plan without siblings stays current after upgrade).
    expected = dict(raw_revision)
    if int(parts["revision"]) < 4:  # v4 introduced sibling_paths_digest
        assert "sibling_paths_digest" not in raw_revision
        expected.update(version=current, sibling_paths_digest=None)
    assert loaded == expected
    if parts["shape"] == "completeness-checkpoint":
        assert saved.is_pre_apply_checkpoint is True
        assert saved.qualified_result is None
    else:
        assert saved.is_pre_apply_checkpoint is False
        assert saved.qualified_result["audit_revision"] == loaded
        assert saved.qualified_result["coverage"] == "confirmed"


def test_every_supported_sidecar_version_has_a_captured_example() -> None:
    """A version bump must add an example of the new version in the same change. The bound is
    the reader's own supported set, so a new sidecar version cannot be added without one."""
    sidecars = {int(parts["sidecar"]) for parts in PARTS.values()}
    supported = set(_SUPPORTED_SCHEMA_VERSIONS)
    assert not supported - sidecars, (
        f"no example of sidecar version(s) {sorted(supported - sidecars)}"
    )
    assert sidecars <= supported, "an example claims a version the reader no longer supports"


def test_the_current_and_an_older_audit_revision_version_have_captured_examples(
    tmp_path: Path,
) -> None:
    """The current revision version, and at least one older one, so the upgrade branch of the
    normalizer stays covered when the current version moves."""
    revisions = {int(parts["revision"]) for parts in PARTS.values() if parts["revision"]}
    current = _current_revision_version(tmp_path)
    assert current in revisions, "no example of the current audit-revision version"
    assert any(version < current for version in revisions), "no example of an older revision"


@pytest.mark.parametrize("source", AUTHORED_VERSIONS)
def test_a_captured_plan_and_its_detail_load_through_current_readers(source: str) -> None:
    plan_version, detail_version = AUTHORED_VERSIONS[source]
    root = FIXTURES / "authored" / source
    plan_path = root / "2-orch.md"
    document = split_plan_document(plan_path.read_text(encoding="utf-8"))
    frontmatter = yaml.safe_load(document.frontmatter_yaml)
    if plan_version is None:
        assert "format_version" not in frontmatter
    else:
        assert frontmatter["format_version"] == plan_version

    plan = parse_plan(plan_path)
    assert plan.format_version == (1 if plan_version is None else plan_version)
    assert plan.title == "Orchestrator Plan"
    step = plan.step_by_id(1)
    assert step.detail == CAPTURED_DETAIL
    assert plan.step_by_id(2).depends_on == [1]

    detail = _load_detail(step, repo_root=root, plan=plan, plan_path=plan_path)
    assert detail == (root / CAPTURED_DETAIL).read_text(encoding="utf-8")
    marker_slot = next(line for line in detail.splitlines()[1:] if line.strip())
    if detail_version is None:
        assert "plan-tool:detail-format-version" not in detail
    else:
        assert marker_slot == f"<!-- plan-tool:detail-format-version: {detail_version} -->"
    assert parse_acceptance_bullets(detail) == ["function returns 42"]


def test_every_supported_plan_and_detail_version_has_a_captured_example() -> None:
    plans = {plan for plan, _ in AUTHORED_VERSIONS.values() if plan is not None}
    details = {detail for _, detail in AUTHORED_VERSIONS.values() if detail is not None}
    missing_plans = SUPPORTED_PLAN_FORMAT_VERSIONS - plans
    missing_details = SUPPORTED_DETAIL_FORMAT_VERSIONS - details
    assert not missing_plans, f"no example of plan format version(s) {sorted(missing_plans)}"
    assert not missing_details, (
        f"no example of detail format version(s) {sorted(missing_details)}"
    )


def test_a_captured_data_contract_finding_loads_with_its_apply_payload() -> None:
    path = CAPTURED_DATA_CONTRACT_REPORT
    saved = load_review(path)
    assert saved.schema_version == 1
    assert saved.kind == "completeness"
    assert saved.report_md == path.with_suffix(".md").read_text(encoding="utf-8")

    candidates, non_applyable = _filter_candidates(
        saved.recommendations, _load_payloads(path)
    )
    assert non_applyable == []
    (candidate,) = candidates
    assert (candidate.rec.id, candidate.rec.source, candidate.rec.severity) == (
        "dc", "data-contract", "medium"
    )
    assert candidate.payload == {
        "target_section": "SavedReview",
        "operation": "add",
        "candidate_fields": {"field": "new_field"},
        "freshness": {
            "contract_fingerprint": "contract",
            "registry_fingerprint": "registry",
        },
    }


@pytest.mark.parametrize(("path", "expected"), CHECKPOINT_EXAMPLES.items())
def test_a_captured_checkpoint_loads_only_for_the_matching_input(
    path: str, expected: Checkpoint
) -> None:
    fixture = FIXTURES / path
    raw = json.loads(fixture.read_text(encoding="utf-8"))
    assert raw["schema_version"] == expected.schema_version

    # Frozen captures outlive the normal resume window.
    assert load_if_valid(
        fixture, expected_input_hash=expected.input_hash, max_age_seconds=None
    ) == expected
    assert load_if_valid(
        fixture, expected_input_hash="different-input", max_age_seconds=None
    ) is None


def test_the_current_checkpoint_schema_has_a_captured_example() -> None:
    versions = {example.schema_version for example in CHECKPOINT_EXAMPLES.values()}
    assert CHECKPOINT_SCHEMA_VERSION in versions, (
        f"no example of checkpoint schema version {CHECKPOINT_SCHEMA_VERSION}"
    )


@pytest.mark.parametrize(("plan", "expected"), GROUNDING_EXAMPLES.items())
def test_a_captured_grounding_record_preserves_all_fingerprints(
    plan: str, expected: Grounding
) -> None:
    plan_path = FIXTURES / plan
    raw = json.loads(grounding_path(plan_path).read_text(encoding="utf-8"))
    assert raw["schema_version"] == expected.schema_version
    assert read_grounding(plan_path) == expected


def test_the_current_grounding_schema_has_a_captured_example() -> None:
    versions = {example.schema_version for example in GROUNDING_EXAMPLES.values()}
    assert GROUNDING_SCHEMA_VERSION in versions, (
        f"no example of grounding schema version {GROUNDING_SCHEMA_VERSION}"
    )


@pytest.mark.parametrize(("plan", "expected"), CONCEPT_EXAMPLES.items())
def test_a_captured_concept_record_retains_its_fingerprint_policy(
    plan: str, expected: tuple[int, str]
) -> None:
    _, record_kind = expected
    plan_path = FIXTURES / plan
    raw = json.loads(concepts_path(plan_path).read_text(encoding="utf-8"))
    assert (raw["schema_version"], raw["record_kind"]) == expected

    loaded = load_concepts(plan_path, "fingerprint")
    assert loaded is not None
    assert asdict(loaded) == raw

    if record_kind == "full-tree":
        with pytest.raises(StaleConceptTreeError):
            load_concepts(plan_path, "changed-fingerprint")
    else:
        assert load_concepts(plan_path, "changed-fingerprint") == loaded


def test_the_current_concept_schema_has_a_captured_example() -> None:
    versions = {version for version, _ in CONCEPT_EXAMPLES.values()}
    assert CONCEPTS_SCHEMA_VERSION in versions, (
        f"no example of concept schema version {CONCEPTS_SCHEMA_VERSION}"
    )


@pytest.mark.parametrize(("path", "version"), PURITY_CACHE_EXAMPLES.items())
def test_a_captured_purity_cache_preserves_verdicts_and_prunes_removed_steps(
    path: str, version: int
) -> None:
    fixture = FIXTURES / path
    raw = json.loads(fixture.read_text(encoding="utf-8"))
    cache = load_purity_cache(fixture)
    assert raw["version"] == version
    assert cache.plan_slug == "x"
    assert {str(step_id): asdict(entry) for step_id, entry in cache.entries.items()} == {
        step_id: {**entry, "step_id": int(step_id)}
        for step_id, entry in raw["entries"].items()
    }

    # Step 3 is in the plan but has no saved verdict. Step 9 is no longer in the plan.
    pruned = load_purity_cache(fixture, valid_step_ids={2, 3})
    assert pruned.entries == {2: cache.entries[2]}


def test_the_current_purity_cache_schema_has_a_captured_example() -> None:
    assert PURITY_CACHE_SCHEMA_VERSION in PURITY_CACHE_EXAMPLES.values(), (
        f"no example of purity cache schema version {PURITY_CACHE_SCHEMA_VERSION}"
    )


@pytest.mark.parametrize(("directory", "expected"), PROJECT_PROFILE_EXAMPLES.items())
def test_a_captured_project_profile_preserves_confirmed_settings(
    directory: str, expected: ProjectProfile
) -> None:
    root = FIXTURES / directory
    raw = json.loads(project_profile_path(root).read_text(encoding="utf-8"))
    assert raw["schema_version"] == expected.schema_version
    assert read_project_profile(root) == expected


def test_the_current_project_profile_schema_has_a_captured_example() -> None:
    versions = {profile.schema_version for profile in PROJECT_PROFILE_EXAMPLES.values()}
    assert PROJECT_PROFILE_SCHEMA_VERSION in versions, (
        f"no example of project profile schema version {PROJECT_PROFILE_SCHEMA_VERSION}"
    )


def test_the_readme_table_lists_exactly_the_examples() -> None:
    """One row per example, matched on the file name; a row for a deleted or renamed file fails."""
    text = (FIXTURES / "README.md").read_text(encoding="utf-8")
    rows = set(re.findall(r"^\| `([^`]+\.(?:json|md))` \|", text, flags=re.M))
    authored = {
        f"authored/{source}/{path}"
        for source in AUTHORED_VERSIONS
        for path in ("2-orch.md", CAPTURED_DETAIL)
    }
    assert authored == {
        path.relative_to(FIXTURES).as_posix() for path in (FIXTURES / "authored").rglob("*.md")
    }
    data_contract = {
        path.relative_to(FIXTURES).as_posix()
        for path in CAPTURED_DATA_CONTRACT_REPORT.parent.iterdir()
        if path.is_file()
    }
    checkpoints = {
        path.relative_to(FIXTURES).as_posix()
        for path in (FIXTURES / "checkpoint").rglob("*.json")
    }
    assert checkpoints == CHECKPOINT_EXAMPLES.keys()
    grounding = {
        path.relative_to(FIXTURES).as_posix()
        for path in (FIXTURES / "grounding").rglob("*.json")
    }
    assert grounding == {
        grounding_path(FIXTURES / plan).relative_to(FIXTURES).as_posix()
        for plan in GROUNDING_EXAMPLES
    }
    concepts = {
        path.relative_to(FIXTURES).as_posix()
        for path in (FIXTURES / "concepts").rglob("*.json")
    }
    assert concepts == {
        concepts_path(FIXTURES / plan).relative_to(FIXTURES).as_posix()
        for plan in CONCEPT_EXAMPLES
    }
    purity_caches = {
        path.relative_to(FIXTURES).as_posix()
        for path in (FIXTURES / "purity-cache").rglob("*.json")
    }
    assert purity_caches == PURITY_CACHE_EXAMPLES.keys()
    profiles = {
        path.relative_to(FIXTURES).as_posix()
        for path in (FIXTURES / "project-profile").rglob("*.json")
    }
    assert profiles == {
        project_profile_path(FIXTURES / directory).relative_to(FIXTURES).as_posix()
        for directory in PROJECT_PROFILE_EXAMPLES
    }
    assert rows == (
        {path.name for path in EXAMPLES} | authored | data_contract | checkpoints | grounding
        | concepts | purity_caches | profiles
    )
