"""Tests for complete read-only roadmap comparison snapshots and Git evidence."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from plan_tool import roadmap_candidate, roadmap_compare_run
from plan_tool.roadmap_candidate_run import CandidateProposalError
from plan_tool.roadmap_artifacts import (
    ComponentsArtifact,
    ConstraintsArtifact,
    DomainArtifact,
    EntityRow,
    PlansArtifact,
    render_components_artifact,
    render_constraints_artifact,
    render_domain_artifact,
    render_plans_artifact,
    roadmap_dir,
)
from plan_tool.roadmap_seed_manifest import NoPublishedRoadmapVersionError
from plan_tool.roadmap_versions import (
    ROADMAP_VERSION_SCHEMA_VERSION,
    AcceptedRoadmapHead,
    PreparedRoadmapVersion,
    RoadmapVersionContent,
    VERSION_ARTIFACT_INVENTORY,
    accepted_head_path,
    create_root_version,
    render_accepted_head,
    stored_version_members,
    version_directory_path,
)


SLUG = "comparison"


def _artifact_bytes(*, domain_body: str = "# Domain\n") -> tuple[bytes, ...]:
    rendered = {
        "domain": render_domain_artifact(DomainArtifact((), (), (), (), domain_body)),
        "constraints": render_constraints_artifact(ConstraintsArtifact((), (), (), "# Constraints\n")),
        "components": render_components_artifact(ComponentsArtifact((), (), (), (), "# Components\n")),
        "plans": render_plans_artifact(PlansArtifact((), (), (), (), "# Plans\n")),
    }
    return tuple(rendered[item.artifact_key].encode("utf-8") for item in VERSION_ARTIFACT_INVENTORY)


def _prepared(artifact_bytes: tuple[bytes, ...]) -> PreparedRoadmapVersion:
    content = RoadmapVersionContent(brief_bytes=b"brief\n", artifact_bytes=artifact_bytes)
    return PreparedRoadmapVersion(
        record=create_root_version(
            roadmap_slug=SLUG,
            brief_digest=hashlib.sha256(content.brief_bytes).hexdigest(),
            artifact_digests=tuple(hashlib.sha256(value).hexdigest() for value in artifact_bytes),
        ),
        content=content,
    )


def _write_version(tmp_path: Path, prepared: PreparedRoadmapVersion, *, accepted: bool = False) -> None:
    version_dir = version_directory_path(tmp_path / "plans", SLUG, prepared.record.version_id)
    for member in stored_version_members(prepared):
        path = version_dir / member.member_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(member.data)
    if accepted:
        path = accepted_head_path(tmp_path / "plans", SLUG)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(render_accepted_head(AcceptedRoadmapHead(
            schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
            roadmap_slug=SLUG,
            version_id=prepared.record.version_id,
        )))


def _write_stale_top_level_files(tmp_path: Path, artifacts: tuple[bytes, ...]) -> None:
    """Legacy top-level 0N-*.md files; comparison must never read them."""
    root = roadmap_dir(tmp_path / "plans", SLUG)
    root.mkdir(parents=True, exist_ok=True)
    for entry, data in zip(VERSION_ARTIFACT_INVENTORY, artifacts, strict=True):
        (root / entry.member_name).write_bytes(data)


def _stored_pair(tmp_path: Path, *, target_domain: str = "# Stored target\n"):
    base = _prepared(_artifact_bytes())
    target = _prepared(_artifact_bytes(domain_body=target_domain))
    _write_version(tmp_path, base, accepted=True)
    _write_version(tmp_path, target)
    return base, target


def _activate(monkeypatch: pytest.MonkeyPatch, version_id: str | None) -> None:
    monkeypatch.setattr(
        roadmap_compare_run, "load_candidate_admission",
        lambda **_kwargs: SimpleNamespace(active_candidate_version_id=version_id),
    )


def _prose_addition(row_id: str, fragment: str) -> roadmap_candidate.CandidateAddRow:
    return roadmap_candidate.CandidateAddRow(
        feedback_id="feedback", artifact_key="domain", row_type="entities",
        row=EntityRow(id=row_id, name=row_id, fields=()),
        prose_amendment=roadmap_candidate.CandidateAddRowProseAmendment(
            row_id=row_id, fragment=fragment
        ),
    )


def _stub_candidate(monkeypatch: pytest.MonkeyPatch, *, predecessor: str | None, operations=()):
    monkeypatch.setattr(
        roadmap_compare_run, "load_stored_candidate_proposal",
        lambda **_kwargs: SimpleNamespace(
            record=SimpleNamespace(predecessor_version_id=predecessor),
            evidence=SimpleNamespace(normalized_operations=operations),
        ),
    )


def _evidence(tmp_path: Path, *, base_kind="root", base_id="root", target_kind="candidate", target_id="tip"):
    return roadmap_compare_run._bound_prose_amendment_evidence(
        plans_dir=tmp_path, slug=SLUG,
        base=SimpleNamespace(kind=base_kind, version_id=base_id),
        target=SimpleNamespace(kind=target_kind, version_id=target_id),
    )


def test_direct_predecessor_binds_the_candidates_prose_amendments_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_candidate(
        monkeypatch, predecessor="root",
        operations=(_prose_addition("first", "One."), _prose_addition("second", "Two.")),
    )

    evidence = _evidence(tmp_path)

    assert evidence.outcome == "bound"
    assert [(item.artifact_key, item.row_id, item.fragment) for item in evidence.amendments] == [
        ("domain", "first", "One."), ("domain", "second", "Two."),
    ]


@pytest.mark.parametrize(
    "predecessor, base_id",
    [("middle", "root"), (None, "root"), ("root", "tip")],
    ids=["non-adjacent", "no-predecessor", "base-is-the-candidate-itself"],
)
def test_non_adjacent_rootless_or_identical_pair_is_not_directly_bound_without_inference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, predecessor: str | None, base_id: str
) -> None:
    # A prose-bearing candidate two hops above the base must not have its
    # fragments attributed to the base: binding is never inferred from bytes.
    _stub_candidate(
        monkeypatch, predecessor=predecessor, operations=(_prose_addition("row", "Text."),)
    )

    evidence = _evidence(tmp_path, base_id=base_id)

    assert (evidence.outcome, evidence.amendments) == ("not-directly-bound", ())


def test_legacy_candidate_without_operation_evidence_is_unknown_not_bound_and_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Selector-era and pre-route batch candidates store normalized_operations=None:
    # "unknown" must not render as the empty `bound` collection meaning "admitted none".
    _stub_candidate(monkeypatch, predecessor="root", operations=None)

    evidence = _evidence(tmp_path)

    assert (evidence.outcome, evidence.amendments) == ("no-operation-evidence", ())


def test_row_only_candidate_is_bound_with_an_empty_collection_not_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_candidate(monkeypatch, predecessor="root")

    evidence = _evidence(tmp_path)

    assert (evidence.outcome, evidence.amendments) == ("bound", ())


@pytest.mark.parametrize(
    "target_kind, target_id, base_id",
    [("root", "root", "other"), ("candidate", "tip", None)],
)
def test_non_candidate_pairs_are_not_applicable_and_load_no_candidate_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target_kind, target_id, base_id
) -> None:
    def _forbidden(**_kwargs):
        raise AssertionError("candidate evidence must not be loaded")

    monkeypatch.setattr(roadmap_compare_run, "load_stored_candidate_proposal", _forbidden)

    evidence = _evidence(tmp_path, target_kind=target_kind, target_id=target_id, base_id=base_id)

    assert (evidence.outcome, evidence.amendments) == ("not-applicable", ())


def test_malformed_candidate_evidence_refuses_the_comparison_before_rendering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _refuse(**_kwargs):
        raise CandidateProposalError("candidate evidence does not bind its stored version")

    monkeypatch.setattr(roadmap_compare_run, "load_stored_candidate_proposal", _refuse)
    monkeypatch.setattr(roadmap_compare_run, "_resolve_base_snapshot", lambda **_k: SimpleNamespace(
        kind="root", version_id="root"))
    monkeypatch.setattr(roadmap_compare_run, "_resolve_target_snapshot", lambda **_k: SimpleNamespace(
        kind="candidate", version_id="tip"))

    with pytest.raises(roadmap_compare_run.RoadmapComparisonRunError, match="does not bind"):
        roadmap_compare_run.run_roadmap_comparison(plans_dir=tmp_path, slug=SLUG)


def test_default_base_uses_complete_accepted_version_and_captures_every_artifact(tmp_path: Path) -> None:
    base_bytes = _artifact_bytes()
    prepared, target = _stored_pair(tmp_path, target_domain="# Changed domain\n")

    result = roadmap_compare_run.run_roadmap_comparison(
        plans_dir=tmp_path / "plans", slug=SLUG, target_version_id=target.record.version_id
    )

    assert result.base.record == prepared.record
    assert result.base.brief_bytes == b"brief\n"
    assert result.base.artifact_bytes == base_bytes
    assert [patch.artifact_key for patch in result.patches] == [
        item.artifact_key for item in VERSION_ARTIFACT_INVENTORY
    ]
    assert [patch.status for patch in result.patches] == [1, 0, 0, 0]
    assert result.patches[0].patch.startswith(
        "diff --git a/before/01-domain.md b/after/01-domain.md"
    )


def test_explicit_stored_base_and_target_read_only_the_version_store(tmp_path: Path) -> None:
    base, target = _stored_pair(tmp_path)
    _write_stale_top_level_files(tmp_path, _artifact_bytes(domain_body="# Stale\n"))

    result = roadmap_compare_run.run_roadmap_comparison(
        plans_dir=tmp_path / "plans",
        slug=SLUG,
        base_version_id=base.record.version_id,
        target_version_id=target.record.version_id,
    )

    assert result.base.version_id == base.record.version_id
    assert result.target.version_id == target.record.version_id


def test_no_accepted_head_raises_the_no_published_version_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The base resolves before the target, so a headless folder reports the
    # missing head even though no candidate is active either.
    _write_stale_top_level_files(tmp_path, _artifact_bytes())
    _activate(monkeypatch, None)

    with pytest.raises(NoPublishedRoadmapVersionError, match="no published version"):
        roadmap_compare_run.run_roadmap_comparison(plans_dir=tmp_path / "plans", slug=SLUG)


def test_default_target_is_the_active_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base, target = _stored_pair(tmp_path)
    _activate(monkeypatch, target.record.version_id)

    result = roadmap_compare_run.run_roadmap_comparison(plans_dir=tmp_path / "plans", slug=SLUG)

    assert result.base.version_id == base.record.version_id
    assert result.target.version_id == target.record.version_id


def test_default_target_binds_prose_amendment_evidence_like_an_explicit_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base, target = _stored_pair(tmp_path)
    _activate(monkeypatch, target.record.version_id)
    monkeypatch.setattr(roadmap_compare_run, "_snapshot_from_resolved", lambda resolved: SimpleNamespace(
        kind="candidate", version_id=resolved.record.version_id,
        artifact_bytes=(), parsed_artifacts={}))
    seen: list[str] = []
    def stop_after_recording(**kwargs):
        seen.append(kwargs["target"].version_id)
        raise roadmap_compare_run.RoadmapComparisonRunError("stop")

    monkeypatch.setattr(roadmap_compare_run, "_bound_prose_amendment_evidence", stop_after_recording)

    with pytest.raises(roadmap_compare_run.RoadmapComparisonRunError, match="stop"):
        roadmap_compare_run.run_roadmap_comparison(plans_dir=tmp_path / "plans", slug=SLUG)

    assert seen == [target.record.version_id]


def _forbid_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(roadmap_compare_run.subprocess, "run", lambda *args, **kwargs: pytest.fail("Git ran"))


def test_no_active_candidate_refuses_naming_comparison_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stored_pair(tmp_path)
    _activate(monkeypatch, None)

    with pytest.raises(roadmap_compare_run.RoadmapComparisonRunError, match="--comparison-target"):
        roadmap_compare_run.run_roadmap_comparison(plans_dir=tmp_path / "plans", slug=SLUG)


def test_missing_admission_record_refuses_naming_comparison_target(tmp_path: Path) -> None:
    # The real admission loader runs and finds no admission file.
    _stored_pair(tmp_path)

    with pytest.raises(roadmap_compare_run.RoadmapComparisonRunError, match="--comparison-target"):
        roadmap_compare_run.run_roadmap_comparison(plans_dir=tmp_path / "plans", slug=SLUG)


def test_refusal_without_active_candidate_spawns_no_git_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stored_pair(tmp_path)
    _activate(monkeypatch, None)
    _forbid_git(monkeypatch)

    with pytest.raises(roadmap_compare_run.RoadmapComparisonRunError):
        roadmap_compare_run.run_roadmap_comparison(plans_dir=tmp_path / "plans", slug=SLUG)


def test_top_level_artifact_files_are_never_read(tmp_path: Path) -> None:
    base, target = _stored_pair(tmp_path)
    ids = dict(base_version_id=base.record.version_id, target_version_id=target.record.version_id)
    clean = roadmap_compare_run.run_roadmap_comparison(plans_dir=tmp_path / "plans", slug=SLUG, **ids)

    broken = list(_artifact_bytes(domain_body="# Stale top-level\n"))
    broken[1] = b"not valid roadmap text\n"
    _write_stale_top_level_files(tmp_path, tuple(broken))
    after = roadmap_compare_run.run_roadmap_comparison(plans_dir=tmp_path / "plans", slug=SLUG, **ids)

    assert after.comparison == clean.comparison
    assert [p.patch for p in after.patches] == [p.patch for p in clean.patches]


def test_bare_type_error_from_comparison_building_is_not_leaked_uncaught(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """build_roadmap_comparison can raise a bare TypeError on an internal
    invariant violation; run_roadmap_comparison's documented contract is
    RoadmapComparisonRunError for every caller, not just the CLI (which
    happens to catch TypeError separately)."""
    _, target = _stored_pair(tmp_path)
    monkeypatch.setattr(
        roadmap_compare_run,
        "build_roadmap_comparison",
        lambda **_kwargs: (_ for _ in ()).throw(TypeError("comparison value is not JSON-safe")),
    )

    with pytest.raises(roadmap_compare_run.RoadmapComparisonRunError, match="not JSON-safe"):
        roadmap_compare_run.run_roadmap_comparison(
            plans_dir=tmp_path / "plans", slug=SLUG, target_version_id=target.record.version_id
        )


def test_git_abnormal_status_refuses_without_returning_partial_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, target = _stored_pair(tmp_path)

    class Result:
        returncode = 2
        stdout = b"partial patch"
        stderr = b"fatal: something git-specific went wrong"

    monkeypatch.setattr(roadmap_compare_run.subprocess, "run", lambda *args, **kwargs: Result())
    with pytest.raises(
        roadmap_compare_run.RoadmapComparisonRunError,
        match="failed.*exit 2.*fatal: something git-specific went wrong",
    ):
        roadmap_compare_run.run_roadmap_comparison(
            plans_dir=tmp_path / "plans", slug=SLUG, target_version_id=target.record.version_id
        )


def test_git_patch_capture_pins_its_evidence_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Git configuration cannot alter the stable no-index evidence stream."""
    captured: list[str] = []

    class Result:
        returncode = 0
        stdout = b""

    def run(command: list[str], **_kwargs: object) -> Result:
        captured.extend(command)
        return Result()

    monkeypatch.setattr(roadmap_compare_run.subprocess, "run", run)
    result = roadmap_compare_run._capture_patch(
        "domain", "01-domain.md", tmp_path / "before", tmp_path / "after", cwd=tmp_path
    )

    assert result.status == 0
    assert captured == [
        "git", "-c", "diff.algorithm=myers", "-c", "diff.indentHeuristic=false",
        "-c", "core.autocrlf=false", "-c", "core.safecrlf=false",
        "diff", "--no-index", "--no-ext-diff", "--no-textconv", "--no-color", "--text",
        "--unified=3", "--src-prefix=a/", "--dst-prefix=b/",
        "--", "before/01-domain.md", "after/01-domain.md",
    ]


def test_ambient_autocrlf_config_does_not_hide_a_real_byte_difference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A user's ambient core.autocrlf=true (common on Windows/mixed setups)
    makes plain `git diff --no-index` report two byte-different files
    (CRLF vs LF line endings) as identical at exit 0 — confirmed by direct
    reproduction. The pinned -c core.autocrlf=false override in the command
    must survive regardless of what the caller's environment sets."""
    global_gitconfig = tmp_path / "gitconfig"
    global_gitconfig.write_text("[core]\n\tautocrlf = true\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_gitconfig))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")

    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    before_dir.mkdir()
    after_dir.mkdir()
    (before_dir / "01-domain.md").write_bytes(b"line one\r\nline two\r\n")
    (after_dir / "01-domain.md").write_bytes(b"line one\nline two\n")

    result = roadmap_compare_run._capture_patch(
        "domain", "01-domain.md", before_dir, after_dir, cwd=tmp_path
    )

    assert result.status == 1
    assert result.patch != ""


def test_embedded_nul_byte_still_produces_a_real_diff_not_a_binary_placeholder(
    tmp_path: Path,
) -> None:
    """Without --text, git's own binary-file heuristic (triggered by a NUL
    byte, which is otherwise valid UTF-8 and passes every other validator)
    replaces the patch with a useless "Binary files ... differ" placeholder
    at exit code 1 — indistinguishable from an ordinary text change."""
    prepared = _prepared(_artifact_bytes(domain_body="line one\nline two\x00more\n"))
    target = _prepared(_artifact_bytes(domain_body="line one\nline TWO\x00more\n"))
    _write_version(tmp_path, prepared, accepted=True)
    _write_version(tmp_path, target)

    result = roadmap_compare_run.run_roadmap_comparison(
        plans_dir=tmp_path / "plans", slug=SLUG, target_version_id=target.record.version_id
    )

    domain_patch = next(patch for patch in result.patches if patch.artifact_key == "domain")
    assert domain_patch.status == 1
    assert "Binary files" not in domain_patch.patch
    assert "-line two" in domain_patch.patch
    assert "+line TWO" in domain_patch.patch


def test_comparison_does_not_write_roadmap_or_git_state(tmp_path: Path) -> None:
    _, target = _stored_pair(tmp_path, target_domain="# Stored target\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "plans"], cwd=tmp_path, check=True)
    index = tmp_path / ".git" / "index"
    before_index = index.read_bytes()
    before_roadmap = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in (tmp_path / "plans" / "roadmaps" / SLUG).rglob("*")
        if path.is_file()
    }

    roadmap_compare_run.run_roadmap_comparison(
        plans_dir=tmp_path / "plans", slug=SLUG, target_version_id=target.record.version_id
    )

    after_roadmap = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in (tmp_path / "plans" / "roadmaps" / SLUG).rglob("*")
        if path.is_file()
    }
    assert after_roadmap == before_roadmap
    assert index.read_bytes() == before_index
