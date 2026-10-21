"""Characterization tests for the no-claude inspection commands.

Pins the stdout / stderr / exit-code behavior of ``list`` / ``status`` /
``validate`` — the three read-only "discovery & inspection" verbs that
never call claude — so the "split cli.py into an intent-grouped package"
refactor can relocate ``cmd_list`` / ``cmd_status`` / ``cmd_validate``
into an inspection submodule without changing what an operator sees.

Per ``tests/cli/COVERAGE_BASELINE.md`` the headline gap is ``cmd_status``
(genuinely ``uncovered`` — no legacy test drives ``main(["status", …])``).
``cmd_list`` / ``cmd_validate`` are directly covered elsewhere
(``test_locator.py`` / ``test_cli.py``); the thin pass here pins the whole
group at one seam without re-deriving their legacy edge cases.

Split-proof conventions (see ``test_package_surface.py``): every command
is driven through ``main(argv)`` against a temp repo + manifest built by
the ``tmp_repo`` / ``registered_plan`` fixtures from ``conftest.py``; no
``plan_tool.cli`` module global is ``monkeypatch.setattr``\\ed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plan_tool.cli import main

# Parseable frontmatter with a schema violation (priority literal). The
# MALFORMED-row / INVALID-verdict machinery fires for this *and* for
# frontmatter-less files: both are now carried by the locator's index as
# malformed entries (see the *_unparseable_* tests for the parse-error case).
_SCHEMA_INVALID_PLAN = """\
---
title: Broken
status: planning
priority: urgent
steps:
- id: 1
  title: placeholder
---
# Broken
"""

_RISK_PROFILE_INVALID_PLAN = """\
---
title: Broken risk profile
status: planning
priority: low
risk_profile: urgent
risk_profile_rationale: Bounded work.
steps:
- id: 1
  title: placeholder
---
# Broken
"""

# A well-formed, otherwise-valid plan declaring a format_version this
# build does not support. Distinct from _SCHEMA_INVALID_PLAN: this one is
# refused for the version, not for a field-level schema violation, and
# `validate` exits 1 for it unconditionally (the one named carve-out from
# --fail-on-findings' otherwise flag-controlled exit code).
_FORMAT_VERSION_INVALID_PLAN = """\
---
title: Newer plan
status: planning
priority: low
format_version: 999
steps:
- id: 1
  title: placeholder
---
# Broken
"""


def _cached_annotated_report(
    *,
    source: Path,
    annotated_at: str = "2026-07-05T12:34:56Z",
    grounded_files: int = 3,
    implemented: int = 0,
    partial: int = 0,
    not_implemented: int = 0,
    needs_review: int = 0,
) -> str:
    return (
        "<!-- plan-tool annotate report\n"
        f"source: {source}\n"
        "repo_root: /repo\n"
        f"annotated_at: {annotated_at}\n"
        f"grounded_files: {grounded_files}\n"
        "candidate_text_files: 4\n"
        "skipped_or_unreadable_files: 1\n"
        "-->\n"
        f"> **Coverage:** {implemented} IMPLEMENTED · {partial} PARTIAL · "
        f"{not_implemented} NOT-IMPLEMENTED · {needs_review} NEEDS-REVIEW\n"
        "\n# Body\n"
    )


def _smell_rec(title: str, *, source: str):
    """Build a stub info-severity advisory smell ``Recommendation``."""
    from plan_tool.review import Recommendation

    return Recommendation(
        id=f"smell-{source}",
        source=source,
        severity="info",
        step_id=1,
        title=title,
        body=f"{title} detail",
    )


def _audit_shape_table(rows: list[str] | None = None) -> str:
    """Build the one exact CLAUDE.md table owned by the drift checker."""
    from plan_tool.audit_shapes import AUDIT_SHAPES

    if rows is None:
        rows = [
            f"| `{shape.id}` | {shape.tell} | `{shape.classification}` |"
            for shape in AUDIT_SHAPES
        ]
    return "\n".join(
        [
            "<!-- plan-tool:audit-shapes -->",
            "| id | tell | classification |",
            "| --- | --- | --- |",
            *rows,
            "",
        ]
    )


class TestCmdList:
    def test_empty_manifest_reports_nothing_registered(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(tmp_repo.argv("list"))
        out = capsys.readouterr().out
        assert rc == 0
        assert "no plan-tool plans registered" in out
        # Manifest mode points the operator at the "plans" array to populate.
        assert 'add repo-relative paths to the "plans" array' in out

    def test_registered_plan_renders_a_table_row(
        self, registered_plan, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(registered_plan.argv("list"))
        out = capsys.readouterr().out
        assert rc == 0
        assert "registered in manifest:" in out
        # Header + a row carrying the slug, status, priority, progress, file.
        assert "SLUG" in out and "STATUS" in out and "FILE" in out
        assert "demo" in out
        assert "planning" in out
        assert "low" in out
        assert "0/1" in out
        assert "1-demo.md" in out

    def test_malformed_plan_marks_row_and_points_at_validate(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Schema-invalid but PARSEABLE frontmatter renders a MALFORMED row.
        # (A file with no frontmatter at all is carried the same way —
        # pinned separately by test_unparseable_plan_renders_malformed_row.)
        bad = tmp_repo.plans_dir / "2-broken.md"
        bad.write_text(_SCHEMA_INVALID_PLAN, encoding="utf-8")
        tmp_repo.plans.append(bad)
        tmp_repo.write_manifest()

        rc = main(tmp_repo.argv("list"))
        out = capsys.readouterr().out
        assert rc == 0
        assert "MALFORMED" in out
        # Footer steers the operator to the per-plan diagnostic.
        assert "failed to validate" in out
        assert "plan-tool validate" in out

    def test_unsupported_format_version_plan_renders_malformed_row(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An unsupported declared format_version renders exactly like any
        other schema-invalid plan on `list` — a MALFORMED row plus the
        "failed to validate" footer; the distinct exit-1 carve-out lives
        only on `validate`, not on `list`."""
        bad = tmp_repo.plans_dir / "2-broken.md"
        bad.write_text(_FORMAT_VERSION_INVALID_PLAN, encoding="utf-8")
        tmp_repo.plans.append(bad)
        tmp_repo.write_manifest()

        rc = main(tmp_repo.argv("list"))
        out = capsys.readouterr().out
        assert rc == 0
        assert "MALFORMED" in out
        assert "failed to validate" in out
        assert "plan-tool validate" in out

    def test_unparseable_plan_renders_malformed_row(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A registered plan whose frontmatter cannot be parsed at all is
        carried by the locator's index as a MALFORMED row: ``list`` shows
        the slug, the MALFORMED marker, and the "failed to validate"
        footer — exactly as a schema-invalid plan renders.
        """
        bad = tmp_repo.plans_dir / "2-broken.md"
        bad.write_text("this is not valid frontmatter\n", encoding="utf-8")
        tmp_repo.plans.append(bad)
        tmp_repo.write_manifest()

        rc = main(tmp_repo.argv("list"))
        out = capsys.readouterr().out
        assert rc == 0
        assert "broken" in out
        assert "MALFORMED" in out
        assert "failed to validate" in out

    def test_missing_manifest_entry_warns_on_stderr(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ghost = tmp_repo.plans_dir / "9-ghost.md"  # never written to disk
        tmp_repo.plans.append(ghost)
        tmp_repo.write_manifest()

        rc = main(tmp_repo.argv("list"))
        captured = capsys.readouterr()
        assert rc == 0
        assert "not found on disk" in captured.err
        assert "if no longer needed, remove" in captured.err

    def test_status_rollup_md_reads_conventional_reports_and_flags_unannotated(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        first = tmp_repo.add_plan("1-demo", title="Demo Plan")
        second = tmp_repo.add_plan("2-other", title="Other Plan")
        tmp_repo.write_manifest()
        reports_dir = tmp_repo.plans_dir / "plan-details" / "demo" / "reports"
        reports_dir.mkdir(parents=True)
        (reports_dir / "20260705-demo.annotated.md").write_text(
            _cached_annotated_report(
                source=first.resolve(),
                implemented=2,
                partial=1,
                not_implemented=3,
                needs_review=4,
                grounded_files=5,
            ),
            encoding="utf-8",
        )

        rc = main(tmp_repo.argv("list", "--status", "--format", "md"))
        out = capsys.readouterr().out

        assert rc == 0
        assert (
            "| Plan | Annotated | IMPLEMENTED | PARTIAL | NOT-IMPLEMENTED | "
            "NEEDS-REVIEW | grounded_files | last_annotated | File |"
        ) in out
        assert (
            "| demo | yes | 2 | 1 | 3 | 4 | 5 | 2026-07-05T12:34:56Z | "
            "plans/1-demo.md |"
        ) in out
        second_rel = second.relative_to(tmp_repo.root).as_posix()
        assert (
            f"| other | no | - | - | - | - | - | - | {second_rel} |"
        ) in out
        assert "registered in manifest:" not in out

    def test_status_rollup_reads_explicit_report_dir_by_source_metadata(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan = tmp_repo.add_plan("1-demo", title="Demo Plan")
        tmp_repo.write_manifest()
        reports_dir = tmp_repo.root / "external-reports"
        reports_dir.mkdir()
        (reports_dir / "copied.annotated.md").write_text(
            _cached_annotated_report(
                source=Path("plans/1-demo.md"),
                annotated_at="2026-07-05T13:00:00Z",
                implemented=1,
                needs_review=2,
                grounded_files=7,
            ),
            encoding="utf-8",
        )

        rc = main(
            tmp_repo.argv("list", "--status", "--report-dir", str(reports_dir))
        )
        out = capsys.readouterr().out

        assert rc == 0
        assert "SLUG" in out and "REVIEW" in out and "GROUNDED" in out
        assert "demo" in out
        assert "yes" in out
        assert "1" in out
        assert "2" in out
        assert "7" in out
        assert "2026-07-05T13:00:00Z" in out
        assert plan.name in out


class TestCmdListManifestFallbackHonorsRepoRoot:
    """`list` with `--manifest` omitted must name the `--repo-root`-derived
    manifest in its hints, never one under the ambient cwd (regression for the
    bare `default_manifest_path()` calls in `cmd_list`).
    """

    @staticmethod
    def _two_git_roots(tmp_path: Path):
        repo_root = tmp_path / "repo"
        (repo_root / ".git").mkdir(parents=True)
        cwd = tmp_path / "elsewhere"
        (cwd / ".git").mkdir(parents=True)
        return repo_root, cwd

    @staticmethod
    def _write_manifest(repo_root: Path, plans: list[str]) -> Path:
        manifest = repo_root / ".plan-tool" / "plans.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"plans": plans}), encoding="utf-8")
        return manifest

    def _chdir_elsewhere(self, monkeypatch: pytest.MonkeyPatch, cwd: Path) -> None:
        monkeypatch.delenv("PLAN_TOOL_PLANS_DIR", raising=False)
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(cwd)

    def test_missing_entry_warning_names_repo_root_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        repo_root, cwd = self._two_git_roots(tmp_path)
        manifest = self._write_manifest(repo_root, ["plans/9-ghost.md"])
        self._chdir_elsewhere(monkeypatch, cwd)

        rc = main(["--repo-root", str(repo_root), "list"])

        err = capsys.readouterr().err
        assert rc == 0
        assert "not found on disk" in err
        assert str(manifest) in err
        assert str(cwd / ".plan-tool" / "plans.json") not in err

    def test_empty_manifest_hint_names_repo_root_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        repo_root, cwd = self._two_git_roots(tmp_path)
        manifest = self._write_manifest(repo_root, [])
        self._chdir_elsewhere(monkeypatch, cwd)

        rc = main(["--repo-root", str(repo_root), "list"])

        out = capsys.readouterr().out
        assert rc == 0
        assert "no plan-tool plans registered" in out
        assert str(manifest) in out
        assert str(cwd / ".plan-tool" / "plans.json") not in out


class TestCmdStatus:
    def test_registered_plan_prints_header_and_steps(
        self, registered_plan, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(registered_plan.argv("status", "demo"))
        out = capsys.readouterr().out
        assert rc == 0
        assert "Demo Plan  (1-demo.md)" in out
        assert "status=planning" in out
        assert "priority=low" in out
        assert "progress=0/1" in out
        # A pending step renders the empty-box marker and its id + title.
        assert "[ ] 1. Only step" in out

    def test_unknown_name_exits_2_with_error(
        self, registered_plan, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(registered_plan.argv("status", "does-not-exist"))
        err = capsys.readouterr().err
        assert rc == 2  # main() maps name-resolution FileNotFoundError → 2
        assert "no plan matching 'does-not-exist'" in err

    def test_no_grounding_sidecar_prints_no_stale_warning(
        self, registered_plan, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(registered_plan.argv("status", "demo"))
        out = capsys.readouterr().out
        assert rc == 0
        assert "stale detail" not in out

    def test_stale_detail_step_warns(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.grounding import (
            compute_step_authoring_fingerprint,
            write_grounding,
        )
        from plan_tool.parser import parse_plan

        plan_path = tmp_repo.plans_dir / "1-demo.md"
        plan_path.write_text(
            "---\ntitle: Demo Plan\nstatus: planning\npriority: low\n"
            "steps:\n  - id: 1\n    title: Only step\n"
            "    detail: plans/plan-details/demo/01-step.md\n"
            "---\n# Body\n\n## Out of scope\n\nSkip auth.\n",
            encoding="utf-8",
        )
        tmp_repo.plans.append(plan_path)
        tmp_repo.write_manifest()
        plan = parse_plan(plan_path)
        # Fingerprint stamped against the *original* out-of-scope text.
        fp = compute_step_authoring_fingerprint(
            plan.steps[0], out_of_scope="Skip auth.", deferred=""
        )
        write_grounding(
            plan_path,
            plan_fingerprint="",
            code_fingerprint={},
            step_authoring_fingerprints={"1": fp},
        )
        # The plan narrows after that stamp.
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8").replace(
                "Skip auth.", "Skip auth and retries."
            ),
            encoding="utf-8",
        )

        rc = main(tmp_repo.argv("status", "demo"))

        out = capsys.readouterr().out
        assert rc == 0
        assert "stale detail: step(s) 1" in out
        assert "plan-tool detail --force" in out

    def test_matching_fingerprint_prints_no_stale_warning(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.grounding import (
            compute_step_authoring_fingerprint,
            write_grounding,
        )
        from plan_tool.parser import parse_plan

        plan_path = tmp_repo.plans_dir / "1-demo.md"
        plan_path.write_text(
            "---\ntitle: Demo Plan\nstatus: planning\npriority: low\n"
            "steps:\n  - id: 1\n    title: Only step\n"
            "    detail: plans/plan-details/demo/01-step.md\n"
            "---\n# Body\n\n## Out of scope\n\nSkip auth.\n",
            encoding="utf-8",
        )
        tmp_repo.plans.append(plan_path)
        tmp_repo.write_manifest()
        plan = parse_plan(plan_path)
        fp = compute_step_authoring_fingerprint(
            plan.steps[0], out_of_scope="Skip auth.", deferred=""
        )
        write_grounding(
            plan_path,
            plan_fingerprint="",
            code_fingerprint={},
            step_authoring_fingerprints={"1": fp},
        )

        rc = main(tmp_repo.argv("status", "demo"))

        out = capsys.readouterr().out
        assert rc == 0
        assert "stale detail" not in out


class TestCmdRoot:
    def test_pinned_repo_root_reports_flag_source(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # ``argv`` pins ``--repo-root``; ``root`` should name that source,
        # print the resolved root, and the manifest path beneath it.
        rc = main(tmp_repo.argv("root"))
        out = capsys.readouterr().out
        assert rc == 0
        assert str(tmp_repo.root.resolve()) in out
        assert "source:" in out and "--repo-root flag" in out
        assert ".plan-tool/plans.json" in out

    def test_env_var_reports_env_source(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_REPO_ROOT", str(tmp_repo.root))
        rc = main(["root"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "PLAN_TOOL_REPO_ROOT env" in out

    def test_walks_from_cwd_when_unpinned_and_no_differ_note(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Invoked from the repo root with nothing pinned: the source is the
        # marker walk-up, and root == cwd so the differs note is suppressed.
        monkeypatch.chdir(tmp_repo.root)
        rc = main(["root"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "walked up from cwd to .git or .plan-tool/plans.json" in out
        assert "differs" not in out

    def test_plan_tool_manifest_alone_is_a_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # A directory with a ``.plan-tool/plans.json`` manifest but no
        # ``.git`` still resolves as the root — the manifest marker is enough.
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.delenv("PLAN_TOOL_PLANS_DIR", raising=False)
        (tmp_path / ".plan-tool").mkdir()
        (tmp_path / ".plan-tool" / "plans.json").write_text("{}")
        monkeypatch.chdir(tmp_path)
        rc = main(["root"])
        out = capsys.readouterr().out
        assert rc == 0
        assert str(tmp_path.resolve()) in out
        assert "walked up from cwd to .git or .plan-tool/plans.json" in out

    def test_bare_plan_tool_dir_falls_back_to_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # A ``.plan-tool`` directory with no ``plans.json`` is global/work
        # state (cf. ``~/.plan-tool``), not a plan root — the walk must not
        # treat it as a marker. With no other marker up the tree it falls
        # back to the cwd rather than reporting a spurious manifest root.
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.delenv("PLAN_TOOL_PLANS_DIR", raising=False)
        (tmp_path / ".plan-tool").mkdir()  # no plans.json
        monkeypatch.chdir(tmp_path)
        rc = main(["root"])
        out = capsys.readouterr().out
        assert rc == 0
        assert str(tmp_path.resolve()) in out
        assert "current directory (no .git or .plan-tool/plans.json found)" in out

    def test_subdirectory_reports_differs_note(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        subdir = tmp_repo.root / "pkg" / "nested"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)
        rc = main(["root"])
        out = capsys.readouterr().out
        assert rc == 0
        # Root resolves to the .git ancestor; cwd is the subdir — flagged.
        assert str(tmp_repo.root.resolve()) in out
        assert "differs" in out
        assert str(subdir.resolve()) in out

    def test_no_marker_falls_back_to_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # No ``.git`` / ``.plan-tool/plans.json`` anywhere up the tree:
        # rather than erroring, the root defaults to the current directory.
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.delenv("PLAN_TOOL_PLANS_DIR", raising=False)
        bare = tmp_path / "no-markers"
        bare.mkdir()
        monkeypatch.chdir(bare)
        rc = main(["root"])
        out = capsys.readouterr().out
        assert rc == 0
        assert str(bare.resolve()) in out
        assert "current directory (no .git or .plan-tool/plans.json found)" in out


class TestCmdValidate:
    def test_valid_plan_prints_ok_and_exits_0(
        self, registered_plan, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(registered_plan.argv("validate", "demo"))
        out = capsys.readouterr().out
        assert rc == 0
        assert out.startswith("OK:")
        assert "1-demo.md" in out

    def test_validate_accepts_matching_ordered_audit_shape_records(
        self, registered_plan, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (registered_plan.root / "CLAUDE.md").write_text(
            _audit_shape_table(), encoding="utf-8"
        )

        rc = main(registered_plan.argv("validate", "demo"))
        out = capsys.readouterr().out

        assert rc == 0
        assert out.startswith("OK:")
        assert "audit-shape documentation" not in out

    @pytest.mark.parametrize(
        ("drift_kind", "edit_rows", "expected_output"),
        [
            ("missing", lambda rows: rows[:-1], "missing registered record"),
            ("duplicate", lambda rows: rows + [rows[0]], "duplicate documented record"),
            (
                "unknown",
                lambda rows: [row.replace("check-saturation", "unknown-shape") for row in rows],
                "unknown documented record",
            ),
            (
                "malformed",
                lambda rows: ["| arm-clustering | malformed | checked |", *rows[1:]],
                "malformed documented record",
            ),
            (
                "reordered",
                lambda rows: [rows[1], rows[0], *rows[2:]],
                "record order differs",
            ),
            (
                "tell drift",
                lambda rows: [row.replace("strict-majority", "simple-majority") for row in rows],
                "tell drift",
            ),
            (
                "classification drift",
                lambda rows: [row.replace("`checked`", "`judgment_only`") for row in rows],
                "classification drift",
            ),
        ],
        ids=lambda case: case if isinstance(case, str) else None,
    )
    def test_validate_reports_audit_shape_documentation_drift_as_advisory(
        self,
        registered_plan,
        capsys: pytest.CaptureFixture[str],
        drift_kind: str,
        edit_rows,
        expected_output: str,
    ) -> None:
        del drift_kind
        rows = _audit_shape_table().splitlines()[3:]
        (registered_plan.root / "CLAUDE.md").write_text(
            _audit_shape_table(edit_rows(rows)), encoding="utf-8"
        )

        rc = main(registered_plan.argv("validate", "demo"))
        out = capsys.readouterr().out

        assert rc == 0
        assert out.startswith("OK:")
        assert "audit-shape documentation (advisory, repo-wide):" in out
        assert expected_output in out

    def test_validate_audit_shape_documentation_check_is_inert_without_an_owned_marker(
        self, registered_plan, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(registered_plan.argv("validate", "demo"))
        assert rc == 0
        assert "audit-shape documentation" not in capsys.readouterr().out

        (registered_plan.root / "CLAUDE.md").write_text(
            _audit_shape_table().replace("<!-- plan-tool:audit-shapes -->\n", ""),
            encoding="utf-8",
        )
        rc = main(registered_plan.argv("validate", "demo"))
        assert rc == 0
        assert "audit-shape documentation" not in capsys.readouterr().out

    def test_validate_audit_shape_documentation_drift_never_changes_exit_code(
        self, registered_plan, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (registered_plan.root / "CLAUDE.md").write_text(
            "<!-- plan-tool:audit-shapes -->\nnot a table\n", encoding="utf-8"
        )

        assert main(registered_plan.argv("validate", "demo")) == 0
        assert "audit-shape documentation" in capsys.readouterr().out
        assert main(registered_plan.argv("validate", "demo", "--fail-on-findings")) == 0
        assert "audit-shape documentation" in capsys.readouterr().out

    def test_validate_documented_arm_advice_preserves_operator_override_without_a_software_gate(
        self,
    ) -> None:
        from plan_tool.audit_shapes import AUDIT_SHAPES

        document = (Path(__file__).parents[2] / "CLAUDE.md").read_text(
            encoding="utf-8"
        )

        assert "<!-- plan-tool:audit-shapes -->" in document
        for shape in AUDIT_SHAPES:
            assert (
                f"| `{shape.id}` | {shape.tell} | `{shape.classification}` |"
                in document
            )
        assert "count will not taper" not in document
        assert "not a software\ngate" in document
        assert "surface the scope decision to the user" in document
        assert "no\ncaller class, convergence gate, continuation rule, or dispatch path" in document

    def test_invalid_plan_does_not_render_audit_shape_documentation_advisory(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bad = tmp_repo.plans_dir / "2-broken.md"
        bad.write_text(_SCHEMA_INVALID_PLAN, encoding="utf-8")
        tmp_repo.plans.append(bad)
        tmp_repo.write_manifest()
        (tmp_repo.root / "CLAUDE.md").write_text(
            "<!-- plan-tool:audit-shapes -->\nnot a table\n", encoding="utf-8"
        )

        rc = main(tmp_repo.argv("validate", "broken"))
        out = capsys.readouterr().out

        assert rc == 0
        assert out.startswith("INVALID:")
        assert "audit-shape documentation" not in out

    def test_invalid_plan_prints_invalid_but_exits_0_by_default(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Schema-invalid but parseable. Frontmatter-less files reach the
        # same INVALID: verdict (see test_unparseable_plan_validate_prints_invalid).
        bad = tmp_repo.plans_dir / "2-broken.md"
        bad.write_text(_SCHEMA_INVALID_PLAN, encoding="utf-8")
        tmp_repo.plans.append(bad)
        tmp_repo.write_manifest()

        rc = main(tmp_repo.argv("validate", "broken"))
        out = capsys.readouterr().out
        # The INVALID: line is the verdict; the exit code stays 0 unless gated.
        assert rc == 0
        assert out.startswith("INVALID:")

    def test_invalid_plan_with_fail_on_findings_exits_1(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bad = tmp_repo.plans_dir / "2-broken.md"
        bad.write_text(_SCHEMA_INVALID_PLAN, encoding="utf-8")
        tmp_repo.plans.append(bad)
        tmp_repo.write_manifest()

        rc = main(tmp_repo.argv("validate", "broken", "--fail-on-findings"))
        out = capsys.readouterr().out
        assert rc == 1
        assert out.startswith("INVALID:")

    def test_validate_reports_invalid_risk_profile(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bad = tmp_repo.plans_dir / "2-broken.md"
        bad.write_text(_RISK_PROFILE_INVALID_PLAN, encoding="utf-8")
        tmp_repo.plans.append(bad)
        tmp_repo.write_manifest()

        rc = main(tmp_repo.argv("validate", "broken"))
        out = capsys.readouterr().out

        assert rc == 0
        assert out.startswith("INVALID:")
        assert "risk_profile" in out

        rc = main(tmp_repo.argv("validate", "broken", "--fail-on-findings"))
        out = capsys.readouterr().out

        assert rc == 1
        assert out.startswith("INVALID:")
        assert "risk_profile" in out

    def test_validate_reports_unsupported_format_version(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An unsupported declared format_version always exits 1 on
        `validate`, with or without --fail-on-findings — unlike ordinary
        schema-invalid input (test_validate_reports_invalid_risk_profile,
        the control), which stays flag-controlled."""
        bad = tmp_repo.plans_dir / "2-broken.md"
        bad.write_text(_FORMAT_VERSION_INVALID_PLAN, encoding="utf-8")
        tmp_repo.plans.append(bad)
        tmp_repo.write_manifest()

        rc = main(tmp_repo.argv("validate", "broken"))
        out = capsys.readouterr().out

        assert rc == 1
        assert out.startswith("INVALID:")
        assert "999" in out

        rc = main(tmp_repo.argv("validate", "broken", "--fail-on-findings"))
        out = capsys.readouterr().out

        assert rc == 1
        assert out.startswith("INVALID:")
        assert "999" in out

    def test_unparseable_plan_validate_prints_invalid(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """validate resolves a frontmatter-less plan by slug and prints
        the INVALID verdict carrying the parse error — the locator now
        carries it in the index, so resolution succeeds (exit 0 by
        default, identical to a schema-invalid plan).
        """
        bad = tmp_repo.plans_dir / "2-broken.md"
        bad.write_text("not a structured plan\n", encoding="utf-8")
        tmp_repo.plans.append(bad)
        tmp_repo.write_manifest()

        rc = main(tmp_repo.argv("validate", "broken"))
        out = capsys.readouterr().out
        assert rc == 0
        assert out.startswith("INVALID:")

    def test_unparseable_plan_fail_on_findings_exits_1(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Frontmatter-less plan under ``--fail-on-findings`` exits 1 with
        the INVALID verdict — the identical contract schema-invalid plans
        already satisfy."""
        bad = tmp_repo.plans_dir / "2-broken.md"
        bad.write_text("not a structured plan\n", encoding="utf-8")
        tmp_repo.plans.append(bad)
        tmp_repo.write_manifest()

        rc = main(tmp_repo.argv("validate", "broken", "--fail-on-findings"))
        out = capsys.readouterr().out
        assert rc == 1
        assert out.startswith("INVALID:")

    def test_valid_plan_with_smells_prints_advisory_block_and_exits_0(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Patch the body-local import target (`plan_tool.review`), never a
        # `plan_tool.cli.inspect` global — the split-proof cli convention.
        rec = _smell_rec("brittle feature ref", source="feature-ref")
        monkeypatch.setattr(
            "plan_tool.review.collect_smell_findings", lambda *a, **k: [rec]
        )
        rc = main(registered_plan.argv("validate", "demo"))
        out = capsys.readouterr().out
        assert rc == 0
        assert out.startswith("OK:")
        assert "smells (advisory):" in out
        assert "brittle feature ref" in out
        assert "[feature-ref]" in out
        assert "[confidence: limited]" in out

    def test_valid_plan_without_smells_prints_only_ok(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(
            "plan_tool.review.collect_smell_findings", lambda *a, **k: []
        )
        rc = main(registered_plan.argv("validate", "demo"))
        out = capsys.readouterr().out
        assert rc == 0
        assert out.startswith("OK:")
        assert "smells (advisory):" not in out

    def test_smell_only_plan_with_fail_on_findings_still_exits_0(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # A smell on the valid path never flips rc — only an INVALID: verdict does.
        rec = _smell_rec("suppression-shaped step", source="suppression-shape")
        monkeypatch.setattr(
            "plan_tool.review.collect_smell_findings", lambda *a, **k: [rec]
        )
        rc = main(registered_plan.argv("validate", "demo", "--fail-on-findings"))
        out = capsys.readouterr().out
        assert rc == 0
        assert out.startswith("OK:")
        # ``suppression-shape`` is in ``SELF_CONSISTENCY_SOURCES``, so it blocks
        # completeness convergence and must not be printed as advisory here —
        # ``validate`` still gates on nothing, which is what rc == 0 pins.
        assert "blocks completeness convergence" in out
        assert "smells (advisory):" not in out

    def test_non_blocking_smell_still_prints_under_advisory(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A source outside ``SELF_CONSISTENCY_SOURCES`` keeps the old header.

        The split is by *routing*, not severity: telling an operator a finding
        is advisory when the next command halts on it is the mismatch this
        header split exists to remove.
        """
        rec = _smell_rec("fragmented steps", source="granularity-merge")
        monkeypatch.setattr(
            "plan_tool.review.collect_smell_findings", lambda *a, **k: [rec]
        )
        rc = main(registered_plan.argv("validate", "demo"))
        out = capsys.readouterr().out
        assert rc == 0
        assert "smells (advisory):" in out
        assert "blocks completeness convergence" not in out

    def test_invalid_plan_does_not_call_smell_collector(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # The except arm never reaches the valid-path collector call.
        bad = tmp_repo.plans_dir / "2-broken.md"
        bad.write_text(_SCHEMA_INVALID_PLAN, encoding="utf-8")
        tmp_repo.plans.append(bad)
        tmp_repo.write_manifest()

        def _boom(*a, **k):  # pragma: no cover - must never be called
            raise AssertionError("collect_smell_findings ran on an INVALID plan")

        monkeypatch.setattr("plan_tool.review.collect_smell_findings", _boom)
        rc = main(tmp_repo.argv("validate", "broken"))
        out = capsys.readouterr().out
        assert rc == 0
        assert out.startswith("INVALID:")

    def test_capability_findings_surface_repo_wide(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # The repo-wide capability honesty check is surfaced from validate.
        # Patch the body-local import target (split-proof convention).
        from plan_tool.capability_catalog import CapabilityFinding

        monkeypatch.setattr(
            "plan_tool.review.collect_smell_findings", lambda *a, **k: []
        )
        monkeypatch.setattr(
            "plan_tool.capability_catalog.check_capabilities",
            lambda *a, **k: [
                CapabilityFinding("orphan-subcommand", "subcommand 'foo' has no owning capability")
            ],
        )
        rc = main(registered_plan.argv("validate", "demo"))
        out = capsys.readouterr().out
        assert rc == 0
        assert "capability catalog (advisory, repo-wide):" in out
        assert "[orphan-subcommand]" in out
        assert "subcommand 'foo'" in out

    def test_capability_findings_never_flip_exit_code(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.capability_catalog import CapabilityFinding

        monkeypatch.setattr(
            "plan_tool.review.collect_smell_findings", lambda *a, **k: []
        )
        monkeypatch.setattr(
            "plan_tool.capability_catalog.check_capabilities",
            lambda *a, **k: [CapabilityFinding("unserved-principle", "principle 'x' is served by no capability")],
        )
        # A capability advisory must not gate CI even under --fail-on-findings.
        rc = main(registered_plan.argv("validate", "demo", "--fail-on-findings"))
        assert rc == 0
        assert "capability catalog (advisory, repo-wide):" in capsys.readouterr().out

    def test_validate_refuses_an_unsupported_pointer_backed_detail_before_printing_ok(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.detail_artifacts import render_detail_format_version_marker

        plan_path = tmp_repo.plans_dir / "1-demo.md"
        plan_path.write_text(
            "---\ntitle: Demo Plan\nstatus: planning\npriority: low\n"
            "steps:\n  - id: 1\n    title: Only step\n"
            "    detail: plans/plan-details/demo/01-step.md\n"
            "---\n# Body\n",
            encoding="utf-8",
        )
        tmp_repo.plans.append(plan_path)
        tmp_repo.write_manifest()
        detail_path = tmp_repo.root / "plans" / "plan-details" / "demo" / "01-step.md"
        detail_path.parent.mkdir(parents=True)
        detail_path.write_text(
            f"# Only step\n{render_detail_format_version_marker(999)}\n\nfine.\n",
            encoding="utf-8",
        )

        rc = main(tmp_repo.argv("validate", "demo"))
        out = capsys.readouterr().out

        assert rc == 1
        assert out.count("INVALID:") == 1
        assert "OK:" not in out
        assert "999" in out


class TestCmdStatusPendingDecisions:
    """The non-blocking pending concept-decision block on ``status`` (step 5)."""

    @staticmethod
    def _write_plan_with_sections(repo, sections) -> Path:
        body = "# Demo\n\nIntro prose.\n"
        for name, prose in sections.items():
            body += f"\n## {name}\n\n{prose}\n"
        path = repo.plans_dir / "1-demo.md"
        path.write_text(
            "---\ntitle: Demo Plan\nstatus: planning\npriority: low\nsteps:\n"
            "  - id: 1\n    title: Only step\n---\n" + body,
            encoding="utf-8",
        )
        repo.plans.append(path)
        repo.write_manifest()
        return path

    @staticmethod
    def _write_decision_record(plan_path: Path, nodes) -> None:
        from plan_tool.concept_tree import (
            RECORD_KIND_DECISION,
            ConceptTree,
            save_concepts,
        )
        from plan_tool.review_persistence import compute_plan_fingerprint

        save_concepts(
            plan_path,
            ConceptTree(
                plan_slug="demo",
                plan_fingerprint=compute_plan_fingerprint(plan_path),
                concepts=nodes,
                record_kind=RECORD_KIND_DECISION,
            ),
        )

    def test_status_lists_unsigned_pending_deferral(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.concept_tree import ConceptNode, concept_id

        plan_path = self._write_plan_with_sections(tmp_repo, {"Caching": "Cache prose."})
        self._write_decision_record(
            plan_path,
            [ConceptNode(
                id=concept_id("Deferred cache", []),
                title="Deferred cache",
                decision="defer",
                review_state="unreviewed",
                bucket="caching",
            )],
        )
        rc = main(tmp_repo.argv("status", "demo"))
        out = capsys.readouterr().out
        assert rc == 0
        assert "Pending concept decisions (1)" in out
        assert "plan-tool scope-review demo" in out

    def test_status_lists_missing_bucket_rereview(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.concept_tree import ConceptNode, concept_id

        plan_path = self._write_plan_with_sections(tmp_repo, {"Caching": "Cache prose."})
        self._write_decision_record(
            plan_path,
            [ConceptNode(
                id=concept_id("Orphan", []),
                title="Orphan",
                decision="defer",
                review_state="unreviewed",
                bucket="gone-section",
            )],
        )
        rc = main(tmp_repo.argv("status", "demo"))
        out = capsys.readouterr().out
        assert rc == 0
        assert "Pending concept decisions" in out
        assert "section no longer exists" in out

    def test_status_no_pending_prints_nothing(
        self, registered_plan, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A plain plan with no concept record surfaces no pending block.
        rc = main(registered_plan.argv("status", "demo"))
        out = capsys.readouterr().out
        assert rc == 0
        assert "Pending concept decisions" not in out

    def test_status_shows_bucket_section_context(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.concept_tree import ConceptNode, concept_id

        plan_path = self._write_plan_with_sections(
            tmp_repo,
            {"Caching": "Distinctive cache invalidation context.", "Other": "x"},
        )
        self._write_decision_record(
            plan_path,
            [
                ConceptNode(
                    id=concept_id("Cache node", []),
                    title="Cache node",
                    decision="defer",
                    review_state="unreviewed",
                    bucket="caching",
                ),
                ConceptNode(
                    id=concept_id("Gone node", []),
                    title="Gone node",
                    decision="defer",
                    review_state="unreviewed",
                    bucket="vanished",
                ),
            ],
        )
        rc = main(tmp_repo.argv("status", "demo"))
        out = capsys.readouterr().out
        assert rc == 0
        # The bucket's section body is excerpted as lazy context.
        assert "Distinctive cache invalidation context." in out
        # The vanished-bucket node shows the note instead of raising.
        assert "section no longer exists" in out

    def test_status_no_crash_on_stale_legacy_record(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.concept_tree import (
            RECORD_KIND_FULL_TREE,
            ConceptNode,
            ConceptTree,
            concept_id,
            save_concepts,
        )

        plan_path = self._write_plan_with_sections(tmp_repo, {"Caching": "Cache prose."})
        # A full-tree record whose stored fingerprint drifted from current plan.
        save_concepts(
            plan_path,
            ConceptTree(
                plan_slug="demo",
                plan_fingerprint="stale-does-not-match-current-plan",
                concepts=[ConceptNode(
                    id=concept_id("Legacy", []),
                    title="Legacy",
                    decision="defer",
                    review_state="unreviewed",
                )],
                record_kind=RECORD_KIND_FULL_TREE,
            ),
        )
        rc = main(tmp_repo.argv("status", "demo"))
        out = capsys.readouterr().out
        assert rc == 0  # no StaleConceptTreeError bubbles up
        assert "Pending concept decisions" in out
        assert "re-sync" in out

    def test_status_legacy_pending_groups_separately(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.concept_tree import (
            RECORD_KIND_FULL_TREE,
            ConceptNode,
            ConceptTree,
            concept_id,
            save_concepts,
        )
        from plan_tool.review_persistence import compute_plan_fingerprint

        plan_path = self._write_plan_with_sections(tmp_repo, {"Caching": "Cache prose."})
        # A fingerprint-current full-tree record with an unreviewed defer node
        # carrying no bucket — a valid legacy deferral, not a missing section.
        save_concepts(
            plan_path,
            ConceptTree(
                plan_slug="demo",
                plan_fingerprint=compute_plan_fingerprint(plan_path),
                concepts=[ConceptNode(
                    id=concept_id("Legacy pending", []),
                    title="Legacy pending",
                    decision="defer",
                    review_state="unreviewed",
                )],
                record_kind=RECORD_KIND_FULL_TREE,
            ),
        )
        rc = main(tmp_repo.argv("status", "demo"))
        out = capsys.readouterr().out
        assert rc == 0
        assert "legacy record" in out
        assert "section no longer exists" not in out


def test_status_pending_context_uses_real_section_after_fenced_pseudo_heading(
    tmp_repo, capsys: pytest.CaptureFixture[str]
) -> None:
    from plan_tool.concept_tree import ConceptNode, concept_id

    plan_path = TestCmdStatusPendingDecisions._write_plan_with_sections(
        tmp_repo,
        {
            "Caching": (
                "Before the example.\n\n```markdown\n"
                "## Example context\nExample-only text.\n```\n\n"
                "After the example."
            )
        },
    )
    TestCmdStatusPendingDecisions._write_decision_record(
        plan_path,
        [
            ConceptNode(
                id=concept_id("Deferred cache", []),
                title="Deferred cache",
                decision="defer",
                review_state="unreviewed",
                bucket="caching",
            )
        ],
    )

    rc = main(tmp_repo.argv("status", "demo"))
    out = capsys.readouterr().out

    assert rc == 0
    assert "## Example context" in out


def test_validate_format_refusal_docs_distinguish_the_exit_one_carve_out() -> None:
    """The cmd_validate docstring, the generated CLI reference, and
    RUNBOOK.md must all name the unsupported-format-version exit-1
    carve-out distinctly from ordinary INVALID: exit-0 behavior — a
    regression guard for the plan's one deliberate operator-visible
    widening beyond ordinary schema-invalid handling."""
    from plan_tool.cli.inspect import cmd_validate

    docstring = cmd_validate.__doc__ or ""
    assert "UnsupportedPlanFormatVersionError" in docstring
    assert "exits 1" in docstring

    repo_root = Path(__file__).resolve().parents[2]
    reference = (repo_root / "docs" / "cli" / "validate.md").read_text(
        encoding="utf-8"
    )
    assert "format_version" in reference
    assert "exits 1 regardless of this flag" in reference

    runbook = (repo_root / "RUNBOOK.md").read_text(encoding="utf-8")
    assert "format_version" in runbook
    assert "exits 1 unconditionally" in runbook
