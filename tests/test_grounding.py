"""Unit coverage for ``plan_tool.grounding`` (no Claude shell-out)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from plan_tool.grounding import (
    GROUNDING_FILENAME,
    GROUNDING_SCHEMA_VERSION,
    Grounding,
    check_grounding_drift,
    compute_step_authoring_fingerprint,
    extract_scope_bearing_sections,
    grounding_path,
    read_grounding,
    stale_detail_steps,
    write_grounding,
)
from plan_tool.review_persistence import compute_plan_fingerprint
from plan_tool.schema import ChangeType, Plan, PlanStatus, Priority, Step


def _plan(tmp_path: Path, name: str = "2-foo.md") -> Path:
    plan = tmp_path / name
    plan.write_text("# plan\n", encoding="utf-8")
    return plan


def test_grounding_path_is_sidecar_under_plan_details(tmp_path: Path) -> None:
    plan = _plan(tmp_path, "2-foo.md")
    expected = tmp_path / "plan-details" / "foo" / GROUNDING_FILENAME
    assert grounding_path(plan) == expected
    assert grounding_path(plan).name == "grounding.json"


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    code_fp = {"plan_tool/foo.py": "abc123", "plan_tool/bar.py": "def456"}
    now = datetime(2026, 6, 16, 12, 34, 56, tzinfo=timezone.utc)
    write_grounding(
        plan, plan_fingerprint="planhash", code_fingerprint=code_fp, now=now
    )
    g = read_grounding(plan)
    assert g is not None
    assert g.code_fingerprint == code_fp
    assert g.plan_fingerprint == "planhash"
    assert g.grounded_at == "2026-06-16T12:34:56Z"
    assert g.plan_slug == "foo"
    assert g.schema_version == GROUNDING_SCHEMA_VERSION


def test_write_returns_sidecar_path(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    path = write_grounding(plan, plan_fingerprint="", code_fingerprint={})
    assert path == grounding_path(plan)
    assert path.is_file()


def test_second_write_overwrites_in_place(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    write_grounding(plan, plan_fingerprint="first", code_fingerprint={"a": "1"})
    write_grounding(plan, plan_fingerprint="second", code_fingerprint={"a": "2"})
    sidecar_dir = grounding_path(plan).parent
    json_files = list(sidecar_dir.glob("*.json"))
    assert json_files == [grounding_path(plan)]
    g = read_grounding(plan)
    assert g is not None
    assert g.plan_fingerprint == "second"
    assert g.code_fingerprint == {"a": "2"}


def test_write_creates_missing_parent_dirs(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    assert not grounding_path(plan).parent.exists()
    write_grounding(plan, plan_fingerprint="", code_fingerprint={})
    assert grounding_path(plan).is_file()


def test_grounded_at_is_iso_utc_z(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    now = datetime(2026, 1, 2, 3, 4, 5, 999999, tzinfo=timezone.utc)
    write_grounding(plan, plan_fingerprint="", code_fingerprint={}, now=now)
    g = read_grounding(plan)
    assert g is not None
    assert g.grounded_at == "2026-01-02T03:04:05Z"


def test_read_absent_returns_none(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    assert read_grounding(plan) is None


def test_read_malformed_json_returns_none(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    path = grounding_path(plan)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert read_grounding(plan) is None


def test_read_wrong_schema_version_returns_none(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    path = grounding_path(plan)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "plan_slug": "foo",
                "grounded_at": "2026-06-16T12:34:56Z",
                "plan_fingerprint": "",
                "code_fingerprint": {},
                "schema_version": 999,
            }
        ),
        encoding="utf-8",
    )
    assert read_grounding(plan) is None


def test_read_missing_required_field_returns_none(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    path = grounding_path(plan)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "grounded_at": "2026-06-16T12:34:56Z",
                "schema_version": GROUNDING_SCHEMA_VERSION,
            }
        ),
        encoding="utf-8",
    )
    assert read_grounding(plan) is None


def test_check_drift_unchanged_matches(tmp_path: Path) -> None:
    g = Grounding(
        plan_slug="foo",
        grounded_at="2026-06-16T12:34:56Z",
        code_fingerprint={"a.py": "1", "b.py": "2"},
    )
    diff = check_grounding_drift(
        g, {"a.py": "1", "b.py": "2"}, tmp_path
    )
    assert diff.match is True
    assert diff.content_drifted == []


def test_check_drift_changed_file_reports_absolute_path(tmp_path: Path) -> None:
    g = Grounding(
        plan_slug="foo",
        grounded_at="2026-06-16T12:34:56Z",
        code_fingerprint={"a.py": "1"},
    )
    diff = check_grounding_drift(g, {"a.py": "2"}, tmp_path)
    assert diff.match is False
    assert diff.content_drifted == [(tmp_path / "a.py").resolve()]


def test_check_drift_deletion_is_footprint_membership(tmp_path: Path) -> None:
    g = Grounding(
        plan_slug="foo",
        grounded_at="2026-06-16T12:34:56Z",
        code_fingerprint={"a.py": "1", "gone.py": "9"},
    )
    diff = check_grounding_drift(g, {"a.py": "1"}, tmp_path)
    assert diff.match is False
    assert diff.content_drifted == []
    assert diff.footprint_removed == [(tmp_path / "gone.py").resolve()]


def test_check_drift_new_file_is_footprint_membership(tmp_path: Path) -> None:
    g = Grounding(
        plan_slug="foo",
        grounded_at="2026-06-16T12:34:56Z",
        code_fingerprint={"a.py": "1"},
    )
    diff = check_grounding_drift(
        g, {"a.py": "1", "new.py": "5"}, tmp_path
    )
    assert diff.match is False
    assert diff.content_drifted == []
    assert diff.footprint_added == [(tmp_path / "new.py").resolve()]


def test_check_drift_paths_sorted_and_absolute(tmp_path: Path) -> None:
    g = Grounding(
        plan_slug="foo",
        grounded_at="2026-06-16T12:34:56Z",
        code_fingerprint={"changed.py": "1", "deleted.py": "2"},
    )
    diff = check_grounding_drift(
        g, {"changed.py": "9", "new.py": "3"}, tmp_path
    )
    assert diff.match is False
    assert diff.content_drifted == [(tmp_path / "changed.py").resolve()]
    assert diff.any_path_change == sorted(diff.any_path_change)
    for path in diff.any_path_change:
        assert path.is_absolute()
        assert path.is_relative_to(tmp_path.resolve())


def test_grounding_json_excluded_from_plan_fingerprint(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    bundle = grounding_path(plan).parent
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "1-step.md").write_text("# step\n", encoding="utf-8")
    before = compute_plan_fingerprint(plan)
    write_grounding(
        plan, plan_fingerprint=before, code_fingerprint={"a.py": "1"}
    )
    after = compute_plan_fingerprint(plan)
    assert before == after


# --- BACKLOG #165: per-step authoring fingerprint / stale-detail gate -----


def _real_plan(
    tmp_path: Path,
    *,
    out_of_scope: str = "Nothing excluded.",
    deferred: str = "Nothing deferred.",
    files: str = "  files:\n    - a.py\n",
) -> Path:
    """A plan file with real body sections, for the extraction/fingerprint
    functions that read scope-bearing text off disk (not just a dataclass)."""
    plan = tmp_path / "2-demo.md"
    plan.write_text(
        "---\n"
        "title: Demo\n"
        "status: planning\n"
        "priority: medium\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: Step one\n"
        f"{files}"
        "---\n"
        "# Demo\n\n"
        f"## Out of scope\n\n{out_of_scope}\n\n"
        f"## Deferred\n\n{deferred}\n",
        encoding="utf-8",
    )
    return plan


def _step(**overrides: object) -> Step:
    defaults = dict(id=1, title="Step one", files=["a.py"])
    defaults.update(overrides)
    return Step(**defaults)


class TestExtractScopeBearingSections:
    def test_reads_out_of_scope_and_deferred_verbatim(
        self, tmp_path: Path
    ) -> None:
        plan = _real_plan(
            tmp_path, out_of_scope="Skip auth.", deferred="Skip retries."
        )
        out_of_scope, deferred = extract_scope_bearing_sections(plan)
        assert out_of_scope.strip() == "Skip auth."
        assert deferred.strip() == "Skip retries."

    def test_empty_when_sections_absent(self, tmp_path: Path) -> None:
        plan = tmp_path / "2-bare.md"
        plan.write_text(
            "---\ntitle: Bare\nstatus: planning\npriority: medium\n"
            "steps:\n  - id: 1\n    title: One\n---\n# Bare\n",
            encoding="utf-8",
        )
        assert extract_scope_bearing_sections(plan) == ("", "")

    def test_empty_when_plan_missing(self, tmp_path: Path) -> None:
        assert extract_scope_bearing_sections(tmp_path / "gone.md") == (
            "",
            "",
        )


class TestComputeStepAuthoringFingerprint:
    def test_stable_for_identical_inputs(self) -> None:
        step = _step()
        a = compute_step_authoring_fingerprint(
            step, out_of_scope="x", deferred="y"
        )
        b = compute_step_authoring_fingerprint(
            step, out_of_scope="x", deferred="y"
        )
        assert a == b

    def test_changes_when_files_change(self) -> None:
        base = compute_step_authoring_fingerprint(
            _step(files=["a.py"]), out_of_scope="x", deferred="y"
        )
        changed = compute_step_authoring_fingerprint(
            _step(files=["a.py", "b.py"]), out_of_scope="x", deferred="y"
        )
        assert base != changed

    def test_changes_when_change_type_changes(self) -> None:
        base = compute_step_authoring_fingerprint(
            _step(change_type=ChangeType.FEATURE), out_of_scope="x", deferred="y"
        )
        changed = compute_step_authoring_fingerprint(
            _step(change_type=ChangeType.REFACTOR), out_of_scope="x", deferred="y"
        )
        assert base != changed

    def test_changes_when_out_of_scope_changes(self) -> None:
        step = _step()
        base = compute_step_authoring_fingerprint(
            step, out_of_scope="Skip auth.", deferred="y"
        )
        narrowed = compute_step_authoring_fingerprint(
            step, out_of_scope="Skip auth and retries.", deferred="y"
        )
        assert base != narrowed

    def test_changes_when_deferred_changes(self) -> None:
        step = _step()
        base = compute_step_authoring_fingerprint(
            step, out_of_scope="x", deferred="Deferred: caching."
        )
        changed = compute_step_authoring_fingerprint(
            step, out_of_scope="x", deferred="Deferred: caching, retries."
        )
        assert base != changed

    def test_unaffected_by_complexity_or_id(self) -> None:
        """Deliberately narrow (BACKLOG #165's own field list) — fields
        outside title/files/creates/change_type/depends_on/scope-sections
        must not flip the digest, or an unrelated authoring tweak (e.g.
        setting complexity after the fact) would falsely read as stale."""
        from plan_tool.schema import Complexity

        base = compute_step_authoring_fingerprint(
            _step(complexity=None), out_of_scope="x", deferred="y"
        )
        recomplexified = compute_step_authoring_fingerprint(
            _step(complexity=Complexity.HIGH), out_of_scope="x", deferred="y"
        )
        assert base == recomplexified


class TestStaleDetailSteps:
    def _plan_obj(self, **step_overrides: object) -> Plan:
        return Plan(
            title="Demo",
            status=PlanStatus.PLANNING,
            priority=Priority.MEDIUM,
            steps=[_step(**step_overrides)],
        )

    def test_empty_when_no_baseline_recorded(self, tmp_path: Path) -> None:
        plan_path = _real_plan(tmp_path)
        grounding = Grounding(plan_slug="demo", grounded_at="2026-01-01T00:00:00Z")
        assert stale_detail_steps(grounding, self._plan_obj(), plan_path) == []

    def test_empty_when_nothing_changed(self, tmp_path: Path) -> None:
        plan_path = _real_plan(tmp_path, out_of_scope="Skip auth.")
        plan = self._plan_obj()
        out_of_scope, deferred = extract_scope_bearing_sections(plan_path)
        fp = compute_step_authoring_fingerprint(
            plan.steps[0], out_of_scope=out_of_scope, deferred=deferred
        )
        grounding = Grounding(
            plan_slug="demo",
            grounded_at="2026-01-01T00:00:00Z",
            step_authoring_fingerprints={"1": fp},
        )
        assert stale_detail_steps(grounding, plan, plan_path) == []

    def test_reports_the_step_whose_out_of_scope_narrowed(
        self, tmp_path: Path
    ) -> None:
        plan_path = _real_plan(tmp_path, out_of_scope="Skip auth.")
        plan = self._plan_obj()
        out_of_scope, deferred = extract_scope_bearing_sections(plan_path)
        fp = compute_step_authoring_fingerprint(
            plan.steps[0], out_of_scope=out_of_scope, deferred=deferred
        )
        grounding = Grounding(
            plan_slug="demo",
            grounded_at="2026-01-01T00:00:00Z",
            step_authoring_fingerprints={"1": fp},
        )
        # The plan narrows after the fingerprint was stamped.
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8").replace(
                "Skip auth.", "Skip auth and retries."
            ),
            encoding="utf-8",
        )
        assert stale_detail_steps(grounding, plan, plan_path) == [1]

    def test_a_step_with_no_stored_fingerprint_is_skipped_not_reported(
        self, tmp_path: Path
    ) -> None:
        """Never detailed (or detailed before BACKLOG #165 existed) means no
        baseline to compare against — silently skip, don't guess stale."""
        plan_path = _real_plan(tmp_path)
        plan = Plan(
            title="Demo",
            status=PlanStatus.PLANNING,
            priority=Priority.MEDIUM,
            steps=[_step(id=1), _step(id=2, title="Step two", files=["b.py"])],
        )
        out_of_scope, deferred = extract_scope_bearing_sections(plan_path)
        fp = compute_step_authoring_fingerprint(
            plan.steps[0], out_of_scope=out_of_scope, deferred=deferred
        )
        grounding = Grounding(
            plan_slug="demo",
            grounded_at="2026-01-01T00:00:00Z",
            step_authoring_fingerprints={"1": fp},  # step 2 never detailed
        )
        assert stale_detail_steps(grounding, plan, plan_path) == []


class TestWriteGroundingPreservesStepFingerprints:
    def test_omitted_kwarg_preserves_existing_step_map(
        self, tmp_path: Path
    ) -> None:
        plan = _plan(tmp_path)
        write_grounding(
            plan,
            plan_fingerprint="a",
            code_fingerprint={},
            step_authoring_fingerprints={"1": "fp1", "2": "fp2"},
        )
        # A caller that knows nothing about #165 (refresh.py, the pre-#165
        # call shape) must not wipe the map just by re-stamping.
        write_grounding(plan, plan_fingerprint="b", code_fingerprint={"x": "y"})
        g = read_grounding(plan)
        assert g is not None
        assert g.step_authoring_fingerprints == {"1": "fp1", "2": "fp2"}
        assert g.plan_fingerprint == "b"

    def test_explicit_empty_dict_clears_it(self, tmp_path: Path) -> None:
        plan = _plan(tmp_path)
        write_grounding(
            plan,
            plan_fingerprint="a",
            code_fingerprint={},
            step_authoring_fingerprints={"1": "fp1"},
        )
        write_grounding(
            plan,
            plan_fingerprint="b",
            code_fingerprint={},
            step_authoring_fingerprints={},
        )
        g = read_grounding(plan)
        assert g is not None
        assert g.step_authoring_fingerprints == {}


def test_extract_scope_bearing_sections_uses_real_headings_and_preserves_fenced_text(
    tmp_path: Path,
) -> None:
    plan = _real_plan(
        tmp_path,
        out_of_scope=(
            "Keep the fenced example.\n\n```markdown\n"
            "## Deferred\nExample-only deferred text.\n```"
        ),
        deferred="Real deferred scope.",
    )

    out_of_scope, deferred = extract_scope_bearing_sections(plan)

    assert "## Deferred" in out_of_scope
    assert "Example-only deferred text." in out_of_scope
    assert deferred.strip() == "Real deferred scope."

    def test_pre_165_sidecar_defaults_to_empty_map(self, tmp_path: Path) -> None:
        """No schema-version bump for this additive field — a sidecar
        written before #165 simply lacks the key."""
        plan = _plan(tmp_path)
        path = grounding_path(plan)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "plan_slug": "foo",
                    "grounded_at": "2026-06-16T12:34:56Z",
                    "plan_fingerprint": "",
                    "code_fingerprint": {},
                    "schema_version": GROUNDING_SCHEMA_VERSION,
                }
            ),
            encoding="utf-8",
        )
        g = read_grounding(plan)
        assert g is not None
        assert g.step_authoring_fingerprints == {}
