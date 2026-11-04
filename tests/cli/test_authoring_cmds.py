"""Characterization tests for the authoring command seams in ``plan_tool.cli``.

Pins the pure authoring helpers behind ``create`` / ``detail`` — the seed
reader, the split-proposal renderer/emitter — plus the *argument-routing*
branches that the legacy suites don't exercise directly: ``create
--reprocess`` with no slug, and ``detail``'s two dispatch-guard rejections
(``--reconcile --dry-run`` and ``--all`` without ``--reconcile``). The
"split cli.py into an intent-grouped package" refactor can then relocate
these between modules without changing what they read, render, or reject.

Per ``tests/cli/COVERAGE_BASELINE.md`` the full ``create`` / ``detail``
happy paths are already directly covered (``test_create.py``,
``test_detail.py``, ``test_reprocess.py``); this module adds tests *only*
for the ``indirectly covered`` helpers and the routing branches those
suites leave untouched. No claude is ever invoked — the routing tests halt
at a guard before any ``create_plan`` / ``generate_detail`` boundary call,
and the helper tests call the helpers on plain inputs.

Split-proof conventions (see ``test_package_surface.py``): every symbol is
imported from ``plan_tool.cli`` and either called directly or driven via
``main(argv)`` on a temp repo. Stdin/TTY are scripted by patching
``builtins`` / ``sys.stdin`` (process-level seams, not cli-module globals);
no ``plan_tool.cli`` global is ``monkeypatch.setattr``\\ed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from plan_tool.cli import (
    _confirm_repo_root,
    _emit_split_proposal,
    _read_seed_body,
    _render_split_proposal_markdown,
    _stamp_grounding,
    main,
)
from plan_tool.cli.authoring import _SPLIT_PROPOSAL_ROADMAP_GUIDANCE
from plan_tool.cli.gitcommit import branch_exists
from plan_tool.create import (
    CreateResult,
    FileBackedSourceRoute,
    SplitProposal,
    SplitProposalEntry,
)
from plan_tool.roadmap_artifacts import (
    COMPONENTS_FILENAME,
    CONSTRAINTS_FILENAME,
    DOMAIN_FILENAME,
    PlanDisposition,
    PlanRow,
    PLANS_FILENAME,
    PlansArtifact,
    render_plans_artifact,
    roadmap_dir,
)
from plan_tool.roadmap_seed_state import (
    TrackedSeedLocation,
    digest_text,
    empty_seed_state,
    locate_tracked_seed,
    seed_state_path,
    write_seed_state,
)


def _canonical_with_source(source: str) -> str:
    """A canonical-shaped text whose frontmatter carries a ``source`` pointer."""
    return f"---\nsource: {source}\n---\n# Canonical body\n"


class TestReadSeedBody:
    def test_no_provenance_returns_none(self, tmp_path: Path) -> None:
        # Plain prose, no frontmatter → no provenance → nothing to read.
        canonical = tmp_path / "canon.md"
        assert _read_seed_body(canonical, "# Just a body\n") is None

    def test_source_pointing_at_self_returns_none(self, tmp_path: Path) -> None:
        canonical = tmp_path / "canon.md"
        text = _canonical_with_source("canon.md")
        assert _read_seed_body(canonical, text) is None

    def test_missing_seed_warns_and_returns_none(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        canonical = tmp_path / "canon.md"
        text = _canonical_with_source("seed.md")  # seed.md never created
        assert _read_seed_body(canonical, text) is None
        assert "not on disk" in capsys.readouterr().err

    def test_existing_seed_body_returned(self, tmp_path: Path) -> None:
        (tmp_path / "seed.md").write_text("SEED CONTENT\n", encoding="utf-8")
        canonical = tmp_path / "canon.md"
        text = _canonical_with_source("seed.md")
        assert _read_seed_body(canonical, text) == "SEED CONTENT\n"


class TestRenderSplitProposalMarkdown:
    def test_entry_with_range_emits_carve_command(self) -> None:
        entries = [
            SplitProposalEntry(
                title="Auth rework",
                suggested_slug="auth-rework",
                rationale="own deploy cadence",
                start_line=1,
                end_line=20,
            ),
        ]
        md = _render_split_proposal_markdown("seed", entries, "seed.md")
        assert "# Split proposal for `seed`" in md
        assert "describes 1 independent plans" in md
        assert "## 1. Auth rework" in md
        assert "**Suggested slug:** `auth-rework`" in md
        assert "**Why its own plan:** own deploy cadence" in md
        assert "**Seed lines:** 1–20" in md
        assert "sed -n '1,20p' seed.md > auth-rework.md" in md

    def test_entry_without_range_omits_carve_command(self) -> None:
        entries = [
            SplitProposalEntry(
                title="No range",
                suggested_slug="no-range",
                rationale="",
                start_line=None,
                end_line=None,
            ),
        ]
        md = _render_split_proposal_markdown("seed", entries, "seed.md")
        assert "## 1. No range" in md
        assert "Seed lines:" not in md
        assert "Carve:" not in md
        # Empty rationale is dropped rather than rendered as a blank bullet.
        assert "Why its own plan:" not in md

    def test_render_split_proposal_markdown_includes_roadmap_guidance(self) -> None:
        md = _render_split_proposal_markdown("seed", _proposal().entries, "seed.md")
        assert _SPLIT_PROPOSAL_ROADMAP_GUIDANCE in md

    def test_render_split_proposal_markdown_does_not_include_runnable_roadmap_command(
        self,
    ) -> None:
        md = _render_split_proposal_markdown("seed", _proposal().entries, "seed.md")
        assert not re.search(r"plan-tool roadmap.*--from-existing", md)


def _proposal(slug_a: str = "alpha", slug_b: str = "beta") -> SplitProposal:
    return SplitProposal(
        entries=[
            SplitProposalEntry(
                title="Alpha effort",
                suggested_slug=slug_a,
                rationale="independent",
                start_line=1,
                end_line=10,
            ),
            SplitProposalEntry(
                title="Beta effort",
                suggested_slug=slug_b,
                rationale="separate owner",
                start_line=11,
                end_line=22,
            ),
        ]
    )


class TestEmitSplitProposal:
    def test_yes_autosaves_worksheet_and_prints_summary(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _emit_split_proposal(
            _proposal(),
            slug="seed",
            source_path=tmp_path / "seed.md",
            output_dir_override=tmp_path,
            repo_root=tmp_path,
            yes=True,
        )
        out = capsys.readouterr().out
        assert "no plan created — the seed describes 2 independent plans:" in out
        assert "1. Alpha effort  [slug: alpha]" in out
        assert "saved split proposal to" in out
        saved = tmp_path / "seed-split-proposal.md"
        assert saved.is_file()
        assert "# Split proposal for `seed`" in saved.read_text(encoding="utf-8")

    def test_split_proposal_has_no_audit_follow_up(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _emit_split_proposal(
            _proposal(),
            slug="seed",
            source_path=None,
            output_dir_override=tmp_path,
            repo_root=tmp_path,
            yes=True,
        )
        output = capsys.readouterr().out
        assert "completeness-audit" not in output

    def test_non_tty_autosaves_without_prompting(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        _emit_split_proposal(
            _proposal(),
            slug="seed",
            source_path=None,
            output_dir_override=tmp_path,
            repo_root=tmp_path,
            yes=False,
        )
        assert (tmp_path / "seed-split-proposal.md").is_file()
        assert "saved split proposal to" in capsys.readouterr().out

    def test_tty_decline_skips_save_but_prints_next_steps(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda _prompt: "n")
        _emit_split_proposal(
            _proposal(),
            slug="seed",
            source_path=tmp_path / "seed.md",
            output_dir_override=tmp_path,
            repo_root=tmp_path,
            yes=False,
        )
        out = capsys.readouterr().out
        assert not (tmp_path / "seed-split-proposal.md").exists()
        assert "saved split proposal" not in out
        assert "No plan or manifest entry was written." in out
        assert _SPLIT_PROPOSAL_ROADMAP_GUIDANCE in out

    def test_emit_split_proposal_prints_roadmap_guidance(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _emit_split_proposal(
            _proposal(),
            slug="seed",
            source_path=tmp_path / "seed.md",
            output_dir_override=tmp_path,
            repo_root=tmp_path,
            yes=True,
        )
        assert "plan-tool roadmap" in capsys.readouterr().out

    def test_emit_split_proposal_does_not_print_runnable_roadmap_command(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _emit_split_proposal(
            _proposal(),
            slug="seed",
            source_path=tmp_path / "seed.md",
            output_dir_override=tmp_path,
            repo_root=tmp_path,
            yes=True,
        )
        assert not re.search(
            r"plan-tool roadmap.*--from-existing", capsys.readouterr().out
        )


class TestCmdCreateFileBackedRoutes:
    @pytest.mark.parametrize(
        ("route", "expected_rc"),
        [
            (FileBackedSourceRoute.DIRECT, 0),
            (FileBackedSourceRoute.NORMALIZED, 0),
            (FileBackedSourceRoute.SPLIT, 0),
            (FileBackedSourceRoute.REFUSED, 2),
        ],
    )
    def test_cmd_create_route_output_and_run_log_agree(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        route: FileBackedSourceRoute,
        expected_rc: int,
    ) -> None:
        import plan_tool.cli.authoring as authoring

        source = tmp_repo.root / "seed.md"
        source.write_text(
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        plan_path = tmp_repo.add_plan("1-demo")

        def create(_slug: str, **kwargs: object) -> CreateResult:
            logger = kwargs["run_logger"]
            extra: dict[str, str] = {"route": route.value}
            if route is FileBackedSourceRoute.REFUSED:
                extra["refusal_reason"] = "unsupported source evidence"
            logger.phase_end("file_backed_route", 0, "selected", **extra)
            if route is FileBackedSourceRoute.SPLIT:
                return CreateResult(
                    plan_path=None,
                    manifest_path=tmp_repo.manifest_path,
                    manifest_updated=False,
                    split_proposal=_proposal(),
                    file_backed_route=route,
                )
            if route is FileBackedSourceRoute.REFUSED:
                return CreateResult(
                    plan_path=None,
                    manifest_path=tmp_repo.manifest_path,
                    manifest_updated=False,
                    file_backed_route=route,
                    refusal_reason=extra["refusal_reason"],
                )
            return CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                file_backed_route=route,
            )

        monkeypatch.setattr(authoring, "create_plan", create)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source),
                "--no-iterate", "--yes",
            )
        )

        captured = capsys.readouterr()
        assert rc == expected_rc
        if route is FileBackedSourceRoute.REFUSED:
            assert "route: refused — file-backed source: unsupported source evidence" in captured.err
            assert "created " not in captured.out
            assert "Next steps:" not in captured.out
        else:
            assert f"route: {route.value}" in captured.out

        records = [
            json.loads(line)
            for log_path in (tmp_repo.root / ".plan-tool" / "runs" / "demo").glob("*.jsonl")
            for line in log_path.read_text(encoding="utf-8").splitlines()
        ]
        route_records = [
            record for record in records
            if record["event"] == "phase_end"
            and record["phase"] == "file_backed_route"
        ]
        assert len(route_records) == 1
        assert route_records[0]["route"] == route.value
        if route is FileBackedSourceRoute.REFUSED:
            assert route_records[0]["refusal_reason"] == "unsupported source evidence"
        else:
            assert "refusal_reason" not in route_records[0]

    @pytest.mark.parametrize(
        ("yes", "is_tty"), [(False, True), (True, True), (False, False)],
    )
    def test_cmd_create_refused_exits_two_without_success_tail(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        yes: bool,
        is_tty: bool,
    ) -> None:
        import plan_tool.cli.authoring as authoring

        source = tmp_repo.root / "seed.md"
        source.write_text(
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        result = CreateResult(
            plan_path=None,
            manifest_path=tmp_repo.manifest_path,
            manifest_updated=False,
            file_backed_route=FileBackedSourceRoute.REFUSED,
            refusal_reason="source lacks retained support",
        )
        monkeypatch.setattr(authoring, "create_plan", lambda *_a, **_k: result)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: is_tty)
        flags = [
            "create",
            "demo",
            "--from-existing",
            str(source),
            "--no-iterate",
        ]
        if yes:
            flags.append("--yes")

        assert main(tmp_repo.argv(*flags)) == 2
        captured = capsys.readouterr()
        assert "route: refused — file-backed source: source lacks retained support" in captured.err
        assert "created " not in captured.out
        assert "Next steps:" not in captured.out

    @pytest.mark.parametrize(
        ("route", "expected_rc"),
        [
            (FileBackedSourceRoute.SPLIT, 0),
            (FileBackedSourceRoute.REFUSED, 2),
        ],
    )
    def test_cmd_create_no_plan_route_rolls_back_collision_binding(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        route: FileBackedSourceRoute,
        expected_rc: int,
    ) -> None:
        """No-plan routes restore the disambiguation binding before their output."""
        import shutil

        import plan_tool.cli.authoring as authoring
        from plan_tool.branch_binding import all_bindings

        shutil.rmtree(tmp_repo.root / ".git")
        source = tmp_repo.root / "seed.md"
        source.write_text(
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        default = _branch_aware_repo(tmp_repo.root)
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", default)
        _make_branch(tmp_repo.root, "plan/demo")
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda *_args, **_kwargs: CreateResult(
                plan_path=None,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                split_proposal=_proposal()
                if route is FileBackedSourceRoute.SPLIT
                else None,
                file_backed_route=route,
                refusal_reason="source lacks retained support"
                if route is FileBackedSourceRoute.REFUSED
                else None,
            ),
        )

        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source), "--no-iterate", "--yes"
            )
        )

        assert rc == expected_rc
        assert source.is_file()
        assert _checked_out_branch(tmp_repo.root) == default
        assert "demo" not in all_bindings(tmp_repo.root)
        assert branch_exists(tmp_repo.root, "plan/demo-2")
        worksheet = (
            tmp_repo.root
            / "docs"
            / "implementation-plans"
            / "demo-split-proposal.md"
        )
        assert worksheet.exists() is (route is FileBackedSourceRoute.SPLIT)


class TestCmdCreateRouteArtifacts:
    def test_cmd_create_reports_replaced_archives_through_shared_helper(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Create and annotate use one flat archive-result reporter."""
        import plan_tool.cli.authoring as authoring
        import plan_tool.cli.annotate_cmd as annotate_cmd

        assert authoring._report_archive_result is annotate_cmd._report_archive_result

        plan_path = tmp_repo.add_plan("1-demo")
        original = tmp_repo.root / "old-plan.md"
        target = tmp_repo.root / "archive" / "old-plan.replaced.md"
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda _slug, **_kwargs: CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                replaced_archives=[(original, target)],
                replaced_skipped=["replacement skipped"],
            ),
        )
        reported = []
        monkeypatch.setattr(
            authoring,
            "_report_archive_result",
            lambda archive, **_kwargs: reported.append(archive),
        )

        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from", "idea", "--no-iterate", "--yes"
            )
        )

        assert rc == 0
        assert len(reported) == 1
        assert reported[0].archived == [(original, target)]
        assert reported[0].skipped == ["replacement skipped"]

    def test_cmd_create_direct_archives_raw_source_only_after_clean_completion(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.cli.authoring as authoring

        source = tmp_repo.root / "seed.md"
        source.write_text(
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        plan_path = tmp_repo.add_plan("1-demo")
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda _slug, **_kwargs: CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                # Payload presence must not make a direct route write a sibling.
                distilled_seed="normalized text that direct must not archive",
                file_backed_route=FileBackedSourceRoute.DIRECT,
            ),
        )

        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source), "--no-iterate", "--yes"
            )
        )

        archive = tmp_repo.root / "archive"
        assert rc == 0
        assert not source.exists()
        assert (archive / "seed.replaced.md").is_file()
        assert not (archive / "seed.distilled.replaced.md").exists()
        assert not (tmp_repo.root / "seed.distilled.md").exists()

    def test_cmd_create_normalized_archives_source_and_normalized_artifact(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.cli.authoring as authoring

        source = tmp_repo.root / "seed.md"
        source.write_text(
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        plan_path = tmp_repo.add_plan("1-demo")
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda _slug, **_kwargs: CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                distilled_seed="## Overview\n\nNormalized artifact.\n",
                file_backed_route=FileBackedSourceRoute.NORMALIZED,
            ),
        )

        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source), "--no-iterate", "--yes"
            )
        )

        archive = tmp_repo.root / "archive"
        assert rc == 0
        assert (archive / "seed.replaced.md").is_file()
        normalized = archive / "seed.distilled.replaced.md"
        assert normalized.is_file()
        assert "Normalized artifact." in normalized.read_text(encoding="utf-8")

    def test_cmd_create_normalized_archive_rotates_stale_artifact(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Archive both a stale sibling and this run's normalized result."""
        import plan_tool.cli.authoring as authoring

        source = tmp_repo.root / "seed.md"
        source.write_text(
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        stale = tmp_repo.root / "seed.distilled.md"
        stale.write_text("stale normalized artifact\n", encoding="utf-8")
        plan_path = tmp_repo.add_plan("1-demo")
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda _slug, **_kwargs: CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                distilled_seed="fresh normalized artifact\n",
                file_backed_route=FileBackedSourceRoute.NORMALIZED,
            ),
        )

        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source), "--no-iterate", "--yes"
            )
        )

        archive = tmp_repo.root / "archive"
        assert rc == 0
        assert not stale.exists()
        assert "stale normalized artifact" in (
            archive / "seed.distilled.replaced.md"
        ).read_text(encoding="utf-8")
        assert "fresh normalized artifact" in (
            archive / "seed.distilled.replaced.1.md"
        ).read_text(encoding="utf-8")

    def test_cmd_create_normalized_archive_replaces_dangling_artifact_link(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A dangling sibling is cleared so the fresh artifact reaches archive."""
        import plan_tool.cli.authoring as authoring

        source = tmp_repo.root / "seed.md"
        source.write_text(
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        dangling = tmp_repo.root / "seed.distilled.md"
        dangling.symlink_to(tmp_repo.root / "missing-normalized-artifact.md")
        plan_path = tmp_repo.add_plan("1-demo")
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda _slug, **_kwargs: CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                distilled_seed="fresh normalized artifact\n",
                file_backed_route=FileBackedSourceRoute.NORMALIZED,
            ),
        )

        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source), "--no-iterate", "--yes"
            )
        )

        archive = tmp_repo.root / "archive"
        assert rc == 0
        assert not dangling.is_symlink()
        assert "fresh normalized artifact" in (
            archive / "seed.distilled.replaced.md"
        ).read_text(encoding="utf-8")

    @pytest.mark.parametrize("contention_kind", ["file", "dangling-link"])
    def test_cmd_create_normalized_archive_retains_source_on_reappearing_collision(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        contention_kind: str,
    ) -> None:
        """A collision after recovery preserves the occupant and raw source."""
        import plan_tool.cli.authoring as authoring

        source = tmp_repo.root / "seed.md"
        source.write_text(
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        stale = tmp_repo.root / "seed.distilled.md"
        stale.write_text("first stale artifact\n", encoding="utf-8")
        plan_path = tmp_repo.add_plan("1-demo")
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda _slug, **_kwargs: CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                distilled_seed="fresh normalized artifact\n",
                file_backed_route=FileBackedSourceRoute.NORMALIZED,
            ),
        )
        durable_create = authoring.durable_create_text
        attempts = 0

        def reappear_after_recovery(path: Path, payload: str, **kwargs) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 2:
                if contention_kind == "file":
                    path.write_text("competing artifact\n", encoding="utf-8")
                else:
                    path.symlink_to(path.parent / "competing-missing-artifact.md")
            durable_create(path, payload, **kwargs)

        monkeypatch.setattr(
            authoring, "durable_create_text", reappear_after_recovery
        )

        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source), "--no-iterate", "--yes"
            )
        )

        archive = tmp_repo.root / "archive"
        assert rc == 0
        assert attempts == 2
        assert source.is_file()
        assert "first stale artifact" in (
            archive / "seed.distilled.replaced.md"
        ).read_text(encoding="utf-8")
        normalized = tmp_repo.root / "seed.distilled.md"
        assert not (archive / "seed.distilled.replaced.1.md").exists()
        if contention_kind == "file":
            assert normalized.read_text(encoding="utf-8") == "competing artifact\n"
        else:
            assert normalized.is_symlink()
        captured = capsys.readouterr()
        assert "normalized artifact collision persisted at seed.distilled.md" in captured.err
        assert "competing-missing-artifact.md" not in captured.err

    def test_cmd_create_normalized_archive_failure_keeps_source_without_partial_artifact(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Keep the raw source when the normalized artifact cannot be published."""
        import plan_tool.cli.authoring as authoring
        from plan_tool.create import ArchiveResult

        source = tmp_repo.root / "seed.md"
        source.write_text(
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        plan_path = tmp_repo.add_plan("1-demo")
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda _slug, **_kwargs: CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                distilled_seed="## Overview\n\nNormalized artifact.\n",
                file_backed_route=FileBackedSourceRoute.NORMALIZED,
            ),
        )

        def fail_normalized_archive(path: Path, *_args, **_kwargs) -> ArchiveResult:
            assert path.name == "seed.distilled.md"
            return ArchiveResult(skipped=["archive directory unavailable"])

        monkeypatch.setattr(authoring, "archive_existing_source", fail_normalized_archive)

        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source), "--no-iterate", "--yes"
            )
        )

        assert rc == 0
        assert source.is_file()
        normalized = tmp_repo.root / "seed.distilled.md"
        assert normalized.read_text(encoding="utf-8") == "## Overview\n\nNormalized artifact.\n"
        assert not (tmp_repo.root / "archive").exists()

    def test_cmd_create_normalized_artifact_create_failure_keeps_source(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Leave the source recoverable when artifact creation fails after publication."""
        import plan_tool.cli.authoring as authoring

        source = tmp_repo.root / "seed.md"
        source.write_text(
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        plan_path = tmp_repo.add_plan("1-demo")
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda _slug, **_kwargs: CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                distilled_seed="Normalized artifact.\n",
                file_backed_route=FileBackedSourceRoute.NORMALIZED,
            ),
        )
        monkeypatch.setattr(
            authoring,
            "durable_create_text",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
        )

        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source), "--no-iterate", "--yes"
            )
        )

        assert rc == 0
        assert source.is_file()
        assert not (tmp_repo.root / "seed.distilled.md").exists()
        assert not (tmp_repo.root / "archive").exists()

    def test_cmd_create_normalized_artifact_retry_failure_keeps_source(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A recovery retry keeps the source when its write fails."""
        import plan_tool.cli.authoring as authoring

        source = tmp_repo.root / "seed.md"
        source.write_text(
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        stale = tmp_repo.root / "seed.distilled.md"
        stale.write_text("stale normalized artifact\n", encoding="utf-8")
        plan_path = tmp_repo.add_plan("1-demo")
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda _slug, **_kwargs: CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                distilled_seed="fresh normalized artifact\n",
                file_backed_route=FileBackedSourceRoute.NORMALIZED,
            ),
        )
        durable_create = authoring.durable_create_text
        attempts = 0

        def fail_retry(path: Path, payload: str, **kwargs) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 2:
                raise OSError("retry disk full")
            durable_create(path, payload, **kwargs)

        monkeypatch.setattr(authoring, "durable_create_text", fail_retry)

        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source), "--no-iterate", "--yes"
            )
        )

        assert rc == 0
        assert attempts == 2
        assert source.is_file()
        assert not (tmp_repo.root / "seed.distilled.md").exists()
        assert "stale normalized artifact" in (
            tmp_repo.root / "archive" / "seed.distilled.replaced.md"
        ).read_text(encoding="utf-8")

    def test_cmd_create_keeps_provenance_seed_after_source_archive_skip(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Archive provenance only after the canonical source itself moved."""
        import plan_tool.cli.authoring as authoring
        from plan_tool.canonical import CanonicalProvenance
        from plan_tool.create import ArchiveResult

        source = tmp_repo.root / "canonical.md"
        seed = tmp_repo.root / "seed.md"
        source.write_text("## References\n\n- [API](https://example.test/api)\n", encoding="utf-8")
        seed.write_text("original seed\n", encoding="utf-8")
        plan_path = tmp_repo.add_plan("1-demo")
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda _slug, **_kwargs: CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                provenance=CanonicalProvenance(source="seed.md"),
                file_backed_route=FileBackedSourceRoute.DIRECT,
            ),
        )
        archive_calls: list[Path] = []

        def fail_source_archive(path: Path, *_args, **_kwargs) -> ArchiveResult:
            archive_calls.append(path)
            return ArchiveResult(skipped=["archive directory unavailable"])

        monkeypatch.setattr(authoring, "archive_existing_source", fail_source_archive)

        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source), "--no-iterate", "--yes"
            )
        )

        assert rc == 0
        assert archive_calls == [source]
        assert source.is_file()
        assert seed.is_file()

    @pytest.mark.parametrize(
        ("route", "expected_rc"),
        [
            (FileBackedSourceRoute.SPLIT, 0),
            (FileBackedSourceRoute.REFUSED, 2),
        ],
    )
    def test_cmd_create_split_and_refused_leave_no_normalized_artifact(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        route: FileBackedSourceRoute,
        expected_rc: int,
    ) -> None:
        """Do not let a producer payload override either no-plan route."""
        import plan_tool.cli.authoring as authoring

        source = tmp_repo.root / "seed.md"
        source.write_text(
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda _slug, **_kwargs: CreateResult(
                plan_path=None,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                split_proposal=_proposal()
                if route is FileBackedSourceRoute.SPLIT
                else None,
                distilled_seed="producer payload must not create an artifact",
                file_backed_route=route,
                refusal_reason="unsupported source" if route is FileBackedSourceRoute.REFUSED else None,
            ),
        )

        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source), "--no-iterate", "--yes"
            )
        )

        assert rc == expected_rc
        assert source.is_file()
        assert not (tmp_repo.root / "seed.distilled.md").exists()
        assert not (tmp_repo.root / "archive").exists()

    def test_cmd_create_without_selected_route_keeps_file_backed_source(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Require a selected route before a public file-backed source is archived."""
        import plan_tool.cli.authoring as authoring

        source = tmp_repo.root / "seed.md"
        source.write_text(
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        plan_path = tmp_repo.add_plan("1-demo")
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda _slug, **_kwargs: CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                distilled_seed="must not become an artifact without a route",
            ),
        )

        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source), "--no-iterate", "--yes"
            )
        )

        assert rc == 0
        assert source.is_file()
        assert not (tmp_repo.root / "archive").exists()
        assert not (tmp_repo.root / "seed.distilled.md").exists()


class TestConfirmRepoRoot:
    @staticmethod
    def _cwd_and_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        cwd = tmp_path / "cwd"
        root = tmp_path / "elsewhere"
        cwd.mkdir()
        root.mkdir()
        monkeypatch.chdir(cwd)
        return cwd.resolve(), root

    def test_root_equals_cwd_returns_root_without_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.chdir(tmp_path)
        # Should not even prompt — pass an input_fn that would fail if called.
        def _boom(_prompt: str) -> str:  # pragma: no cover - must not run
            raise AssertionError("should not prompt when root == cwd")

        assert _confirm_repo_root(tmp_path, yes=False, input_fn=_boom) == tmp_path.resolve()
        assert capsys.readouterr().err == ""

    def test_differing_root_keeps_root_on_yes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _cwd, root = self._cwd_and_root(tmp_path, monkeypatch)
        # ``yes=True`` keeps the discovered root without prompting, but warns.
        assert _confirm_repo_root(root, yes=True) == root.resolve()
        assert "is not the current directory" in capsys.readouterr().err

    def test_differing_root_non_tty_keeps_root_with_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _cwd, root = self._cwd_and_root(tmp_path, monkeypatch)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        assert _confirm_repo_root(root, yes=False) == root.resolve()
        assert "is not the current directory" in capsys.readouterr().err

    def test_differing_root_tty_abort_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _cwd, root = self._cwd_and_root(tmp_path, monkeypatch)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        # Empty input takes the default — abort.
        assert _confirm_repo_root(root, yes=False, input_fn=lambda _p: "") is None
        assert _confirm_repo_root(root, yes=False, input_fn=lambda _p: "a") is None

    def test_differing_root_tty_keep_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _cwd, root = self._cwd_and_root(tmp_path, monkeypatch)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        assert _confirm_repo_root(root, yes=False, input_fn=lambda _p: "r") == root.resolve()
        # ``y`` stays an alias for keeping the discovered root.
        assert _confirm_repo_root(root, yes=False, input_fn=lambda _p: "y") == root.resolve()

    def test_differing_root_tty_choose_current_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        cwd, root = self._cwd_and_root(tmp_path, monkeypatch)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        assert _confirm_repo_root(root, yes=False, input_fn=lambda _p: "c") == cwd


class TestCreateReprocessRouting:
    def test_reprocess_without_slug_is_usage_error(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # ``create --reprocess`` routes into ``_cmd_create_reprocess``,
        # which rejects the missing slug (no description to suggest one
        # from) with exit 2 — before any archive lookup or claude call.
        rc = main(tmp_repo.argv("create", "--reprocess"))
        assert rc == 2
        assert "slug" in capsys.readouterr().err

    def test_cli_frontmatter_only_references_stops_before_create_plan(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import argparse

        import plan_tool.cli.authoring as authoring

        source = tmp_path / "seed.md"
        source.write_text(
            "---\n## References\n---\n# Draft\n\n## Overview\n\nBody.\n",
            encoding="utf-8",
        )
        calls = 0

        def create_plan_must_not_run(*_args: object, **_kwargs: object) -> None:
            nonlocal calls
            calls += 1
            raise AssertionError("create_plan must not run after seed preflight refusal")

        def run_log_must_not_open(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("run log must not open after seed preflight refusal")

        monkeypatch.setattr(authoring, "create_plan", create_plan_must_not_run)
        monkeypatch.setattr(authoring.RunLogWriter, "start", run_log_must_not_open)
        args = argparse.Namespace(
            repo_root=tmp_path,
            reprocess=False,
            from_description=None,
            from_existing=source,
        )

        assert authoring.cmd_create(args) == 2
        assert calls == 0
        assert "## References" in capsys.readouterr().err
        assert not (tmp_path / ".plan-tool").exists()

    def test_create_preflights_canonical_source_after_valid_provenance_seed(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import argparse

        import plan_tool.cli.authoring as authoring

        source = tmp_path / "canonical.md"
        source.write_text(
            "---\nsource: raw.md\n---\n# Draft\n\n## Overview\n\n```\n",
            encoding="utf-8",
        )
        (tmp_path / "raw.md").write_text(
            "## References\n\n- [Real](https://example.test/reference)\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(authoring, "locate_tracked_seed", lambda *_a, **_k: None)
        monkeypatch.setattr(
            authoring, "_confirm_invalidated_roadmap_seed", lambda *_a, **_k: True
        )
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda *_a, **_k: pytest.fail("create_plan must not run after fence refusal"),
        )
        monkeypatch.setattr(
            authoring.RunLogWriter,
            "start",
            lambda **_k: pytest.fail("run log must not open after fence refusal"),
        )
        args = argparse.Namespace(
            repo_root=tmp_path,
            reprocess=False,
            from_description=None,
            from_existing=source,
            yes=True,
        )

        assert authoring.cmd_create(args) == 2
        assert "unmatched opening code fence" in capsys.readouterr().err
        assert not (tmp_path / ".plan-tool").exists()


class TestCreateResultSinkAbsent:
    """A ``create`` run that sets no ``_create_result_sink`` is unchanged.

    ``cmd_create`` deposits its ``CreateResult`` into ``args._create_result_sink``
    only when an in-process caller set it. Ordinary CLI dispatch builds the
    ``Namespace`` from argparse and never sets the attribute, so the deposit is
    skipped and the run behaves exactly as before. Split-proof: the fake backend
    is installed on ``plan_tool.shell`` (a process seam), not a ``plan_tool.cli``
    global, and ``-y`` routes create's prompts through its silent stand-in.
    """

    def test_cmd_create_without_sink_unchanged(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json

        from plan_tool import backend_runner
        from plan_tool import shell as shell_module

        steps_json = json.dumps(
            [{"title": "first", "complexity": "low", "files": [], "depends_on": []}]
        )
        refs_json = json.dumps(
            [{"title": "Docs", "url": "https://example.com", "description": "x"}]
        )
        # Every required body section populated so the non-iterating TODO gate
        # (active without --iterate) doesn't reject the plan.
        body_json = json.dumps({
            "Overview": "o", "Problem statement": "p", "Architecture": "a",
            "Out of scope": "s", "Risks": "r", "Testing": "t",
            "Acceptance criteria": "c", "Deferred": "d",
        })

        def _route(prompt: str) -> str:
            if "Propose an initial plan step-list" in prompt:
                return steps_json
            if "developer and API reference documentation" in prompt:
                return refs_json
            if "Synthesize plan body sections" in prompt:
                return body_json
            return steps_json

        monkeypatch.setattr(
            shell_module.shutil, "which", lambda _name: "/usr/bin/claude"
        )

        class _FakePipe:
            def __init__(self, lines: list) -> None:
                self._lines = list(lines)

            def __iter__(self):
                return iter(self._lines)

        class _FakeProc:
            def __init__(self, stdout_lines: list) -> None:
                self.stdout = _FakePipe(stdout_lines)
                self.stderr = _FakePipe([])
                self.returncode = 0
                self.stdin = None

            def wait(self) -> int:
                return self.returncode

        real_popen = backend_runner.subprocess.Popen

        def fake_popen(argv, **kwargs):
            if argv and argv[0] == "git":
                return real_popen(argv, **kwargs)
            prompt = argv[-1]
            envelope = json.dumps({
                "type": "result",
                "result": _route(prompt),
                "usage": {
                    "input_tokens": 1, "output_tokens": 1,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                },
            })
            return _FakeProc((envelope + "\n").splitlines(keepends=True))

        monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

        rc = main(tmp_repo.argv(
            "create", "demo",
            "--from", "build a thing",
            "--output-dir", str(tmp_repo.plans_dir),
            "-y", "--no-iterate", "--no-distill",
        ))
        assert rc == 0
        assert (tmp_repo.plans_dir / "2-demo.md").is_file()


class TestDetailDispatchGuards:
    def test_reconcile_with_dry_run_rejected(
        self, registered_plan, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # ``--reconcile`` is a read-only audit path; ``--dry-run`` only
        # applies to the authoring write path, so the combination is
        # rejected before any run log opens.
        rc = main(registered_plan.argv("detail", "demo", "--reconcile", "--dry-run"))
        assert rc == 2
        assert "--dry-run" in capsys.readouterr().err

    def test_all_without_reconcile_rejected(
        self, registered_plan, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Bare ``--all`` (no ``--reconcile``) is a misremembered sweep —
        # the authoring path already covers every step lacking detail.
        rc = main(registered_plan.argv("detail", "demo", "--all"))
        assert rc == 2
        assert "--all requires --reconcile" in capsys.readouterr().err


# --------------------------------------------------------------------------
# --reuse / --no-reuse / --reuse-id parse contract (detail --reconcile)
# --------------------------------------------------------------------------
#
# The detail subparser carries the same tri-state reuse family as the
# reconcile-family commands (parity with completeness-audit's
# --reuse-audit). ``--reuse`` is BooleanOptionalAction(default=None);
# ``--reuse-id STEM`` pins one save. Pure parse-contract gates.


class TestDetailReuseFlags:
    def test_detail_reuse_default_is_none(self) -> None:
        from plan_tool.cli import build_parser

        args = build_parser().parse_args(
            ["detail", "demo", "--reconcile", "--step", "1"]
        )
        assert args.reuse is None
        assert args.reuse_id is None

    def test_detail_reuse_flags_parse(self) -> None:
        from plan_tool.cli import build_parser

        parser = build_parser()
        assert (
            parser.parse_args(
                ["detail", "demo", "--reconcile", "--step", "1", "--reuse"]
            ).reuse
            is True
        )
        assert (
            parser.parse_args(
                ["detail", "demo", "--reconcile", "--step", "1", "--no-reuse"]
            ).reuse
            is False
        )
        pinned = parser.parse_args(
            [
                "detail", "demo", "--reconcile", "--step", "1",
                "--reuse-id", "20260612-120000-detail-reconcile",
            ]
        )
        assert pinned.reuse_id == "20260612-120000-detail-reconcile"


# --------------------------------------------------------------------------
# `plan-tool detail --jobs N` — concurrent-authoring flag wiring
# --------------------------------------------------------------------------
#
# Step 3 only exposes the value: the flag parses (rejecting < 1), threads
# into `generate_detail`'s `jobs` kwarg, and is recorded in the run-log
# flags. The concurrency machinery and the jobs>1 + --iterate guard are
# owned by generate_detail (tested in tests/test_detail.py); here we patch
# `authoring.generate_detail` so no claude is invoked.


class TestDetailJobsFlag:
    @staticmethod
    def _patch_capture(monkeypatch: pytest.MonkeyPatch) -> dict:
        """Patch ``authoring.generate_detail`` with a kwargs-capturing fake."""
        import plan_tool.cli.authoring as authoring

        calls: dict = {}

        def fake_generate_detail(plan_path, **kwargs):
            calls["called"] = True
            calls["jobs"] = kwargs.get("jobs")
            calls["yes"] = kwargs.get("yes")
            calls["prompt_fn"] = kwargs.get("prompt_fn")
            return []

        monkeypatch.setattr(authoring, "generate_detail", fake_generate_detail)
        return calls

    def test_jobs_defaults_to_one(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = self._patch_capture(monkeypatch)
        rc = main(registered_plan.argv("detail", "demo", "--no-iterate"))
        assert rc == 0
        assert calls["jobs"] == 1

    def test_jobs_threads_into_generate_detail(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = self._patch_capture(monkeypatch)
        rc = main(
            registered_plan.argv(
                "detail", "demo", "--jobs", "4", "--no-iterate", "--no-split"
            )
        )
        assert rc == 0
        assert calls["jobs"] == 4

    def test_cmd_detail_forwards_yes_and_prompt_fn(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = self._patch_capture(monkeypatch)
        rc = main(
            registered_plan.argv("detail", "demo", "--yes", "--no-iterate")
        )
        assert rc == 0
        assert calls["yes"] is True
        assert callable(calls["prompt_fn"])

    def test_jobs_zero_rejected(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The custom ``type=`` rejects < 1 at parse time, before any
        # ``generate_detail`` boundary call.
        calls = self._patch_capture(monkeypatch)
        for bad in ("0", "-1"):
            with pytest.raises(SystemExit) as exc:
                main(registered_plan.argv("detail", "demo", "--jobs", bad, "--no-iterate"))
            assert exc.value.code == 2
        assert "called" not in calls

    def test_jobs_recorded_in_run_log_flags(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json

        self._patch_capture(monkeypatch)
        rc = main(
            registered_plan.argv(
                "detail", "demo", "--jobs", "2", "--no-iterate", "--no-split"
            )
        )
        assert rc == 0
        # The run log lands under <root>/.plan-tool/runs/<slug>/<run_id>.jsonl;
        # ``detail`` slugs it as ``demo`` (leading ``1-`` stripped).
        run_dir = registered_plan.root / ".plan-tool" / "runs" / "demo"
        run_start = next(
            evt
            for path in run_dir.glob("*.jsonl")
            for line in path.read_text(encoding="utf-8").splitlines()
            if (evt := json.loads(line)).get("event") == "run_start"
        )
        assert run_start["flags"]["jobs"] == 2

    def test_jobs_with_default_iterate_conflicts(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # With iterate at its ON default, generate_detail's guard raises
        # DetailError; cmd_detail's ``except DetailError`` arm returns rc=2.
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailError

        def fake_generate_detail(plan_path, **kwargs):
            raise DetailError(
                "jobs > 1 (concurrent detail authoring) is mutually exclusive "
                "with --iterate"
            )

        monkeypatch.setattr(authoring, "generate_detail", fake_generate_detail)
        rc = main(registered_plan.argv("detail", "demo", "--jobs", "4"))
        assert rc == 2


# --------------------------------------------------------------------------
# `plan-tool detail --jobs N` — CLI-level refuse/degrade guard
# --------------------------------------------------------------------------
#
# The operator-facing front door in front of generate_detail's deep guard:
# `--jobs > 1` is refused under a plan-structure-mutating mode (--iterate /
# --split, both default ON) with a usage error naming the conflict, and
# degraded to serial (with a warning) when combined with a single-step run
# (--step N). The only runnable parallel invocation is
# `--jobs N --no-iterate --no-split`, and a completed parallel run prints a
# terminal un-converged-first-pass warning. Refuse tests halt at the guard
# (no generate_detail call); degrade/all-clear tests patch
# `authoring.generate_detail` with a kwargs-capturing fake.


class TestAuthoringFormatRefusalRunLog:
    @pytest.mark.parametrize(
        ("command", "target", "argv"),
        [
            ("detail", "generate_detail", ["detail", "demo"]),
            (
                "split",
                "split_step",
                ["split", "demo", "--step", "1", "--into", "A", "--into", "B"],
            ),
            (
                "merge",
                "merge_steps",
                ["merge", "demo", "--steps", "3", "--steps", "4"],
            ),
        ],
    )
    def test_format_refusal_keeps_the_run_log_diagnostic(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        command: str,
        target: str,
        argv: list[str],
    ) -> None:
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail_artifacts import DetailFormatError

        message = f"{command} detail declares an unsupported version"
        monkeypatch.setattr(
            authoring,
            target,
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                DetailFormatError(message)
            ),
        )

        assert main(registered_plan.argv(*argv)) == 1

        log_path = next(
            (registered_plan.root / ".plan-tool" / "runs" / "demo").glob("*.jsonl")
        )
        events = [
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
        ]
        run_end = next(event for event in events if event["event"] == "run_end")
        assert run_end["rc"] == 1
        assert run_end["error"] == message


class TestDetailJobsConflictGuard:
    @staticmethod
    def _patch_capture(monkeypatch: pytest.MonkeyPatch) -> dict:
        """Patch ``authoring.generate_detail`` to record the ``jobs`` kwarg."""
        import plan_tool.cli.authoring as authoring

        calls: dict = {}

        def fake_generate_detail(plan_path, **kwargs):
            calls["called"] = True
            calls["jobs"] = kwargs.get("jobs")
            return []

        monkeypatch.setattr(authoring, "generate_detail", fake_generate_detail)
        return calls

    def test_jobs_gt_one_with_iterate_rejected(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Iterate explicitly on (default is now OFF): the CLI guard fires
        # before any generate_detail boundary call and names ``--iterate``.
        calls = self._patch_capture(monkeypatch)
        rc = main(
            registered_plan.argv("detail", "demo", "--jobs", "4", "--iterate")
        )
        assert rc == 2
        assert "--iterate" in capsys.readouterr().err
        assert "called" not in calls

    def test_jobs_gt_one_with_split_rejected(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Iterate off but split at its ON default: still refused, naming
        # ``--split``.
        calls = self._patch_capture(monkeypatch)
        rc = main(
            registered_plan.argv("detail", "demo", "--jobs", "4", "--no-iterate")
        )
        assert rc == 2
        assert "--split" in capsys.readouterr().err
        assert "called" not in calls

    def test_jobs_gt_one_with_lessons_rejected(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        calls = self._patch_capture(monkeypatch)
        rc = main(
            registered_plan.argv(
                "detail", "demo", "--jobs", "4",
                "--no-iterate", "--no-split", "--lessons",
            )
        )
        assert rc == 2
        err = capsys.readouterr().err
        assert "--lessons" in err
        assert "called" not in calls

    def test_jobs_gt_one_no_iterate_no_split_allowed(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The only runnable parallel invocation reaches generate_detail with
        # the requested jobs value.
        calls = self._patch_capture(monkeypatch)
        rc = main(
            registered_plan.argv(
                "detail", "demo", "--jobs", "4", "--no-iterate", "--no-split"
            )
        )
        assert rc == 0
        assert calls["jobs"] == 4

    def test_jobs_gt_one_with_step_degrades_to_serial(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # A single-step parallel request is pointless, not incompatible:
        # warn and normalize the effective jobs to 1 rather than erroring.
        calls = self._patch_capture(monkeypatch)
        rc = main(
            registered_plan.argv(
                "detail", "demo", "--jobs", "4",
                "--no-iterate", "--no-split", "--step", "2",
            )
        )
        assert rc != 2
        assert calls["jobs"] == 1
        assert "serial" in capsys.readouterr().err

    def test_jobs_one_is_unaffected(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Default ``--jobs 1``: both guards are no-ops, no warning.
        calls = self._patch_capture(monkeypatch)
        rc = main(registered_plan.argv("detail", "demo", "--no-iterate"))
        assert rc == 0
        assert calls["jobs"] == 1
        err = capsys.readouterr().err
        assert "serial" not in err
        assert "un-converged" not in err

    def test_jobs_gt_one_step_with_iterate_still_rejected(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # The refuse guard outranks the single-step degrade: ``--jobs 4
        # --step 2 --iterate`` errors rather than degrading.
        calls = self._patch_capture(monkeypatch)
        rc = main(
            registered_plan.argv(
                "detail", "demo", "--jobs", "4", "--step", "2", "--iterate"
            )
        )
        assert rc == 2
        assert "--iterate" in capsys.readouterr().err
        assert "called" not in calls

    def test_jobs_gt_one_emits_unconverged_warning(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # A completed parallel run flags the bodies as an un-converged first
        # pass and prints the ``--iterate`` follow-up; rc is unaffected.
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult

        tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        ddir = tmp_repo.plans_dir / "plan-details" / "demo"

        def fake_gen(plan_path, *, repo_root, **kw):
            ddir.mkdir(parents=True, exist_ok=True)
            f = ddir / "01-only-step.md"
            f.write_text("# detail\n", encoding="utf-8")
            return [DetailResult(step_id=1, output_path=f, written=True)]

        monkeypatch.setattr(authoring, "generate_detail", fake_gen)
        monkeypatch.setattr(app, "cmd_completeness", lambda _a: 0)

        rc = main(
            tmp_repo.argv(
                "detail", "demo", "--jobs", "4", "--no-iterate", "--no-split"
            )
        )
        assert rc == 0
        err = capsys.readouterr().err
        assert "un-converged" in err
        assert "plan-tool detail demo --iterate" in err

    def test_degraded_single_step_no_unconverged_warning(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # A degraded single-step run actually ran serial (effective jobs 1),
        # so it must NOT print the un-converged warning.
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult

        tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        ddir = tmp_repo.plans_dir / "plan-details" / "demo"

        def fake_gen(plan_path, *, repo_root, **kw):
            ddir.mkdir(parents=True, exist_ok=True)
            f = ddir / "01-only-step.md"
            f.write_text("# detail\n", encoding="utf-8")
            return [DetailResult(step_id=1, output_path=f, written=True)]

        monkeypatch.setattr(authoring, "generate_detail", fake_gen)
        monkeypatch.setattr(app, "cmd_completeness", lambda _a: 0)

        rc = main(
            tmp_repo.argv(
                "detail", "demo", "--jobs", "4",
                "--no-iterate", "--no-split", "--step", "1",
            )
        )
        assert rc == 0
        assert "un-converged" not in capsys.readouterr().err


# --------------------------------------------------------------------------
# `plan-tool split` — on-demand step split + author + completeness tail
# --------------------------------------------------------------------------
#
# The deterministic counterpart to `detail --split`. These pin the parse
# contract and the routing branches (the two-title guard, and that a clean
# split runs the conceptual completeness tail). The structural split itself
# is covered end-to-end in test_detail.py::TestSplitStepOnDemand; here we
# patch the `split_step` / `cmd_completeness` boundaries — the documented
# interception seams (see plan_tool.cli.authoring's module docstring) — so
# no claude is invoked.


class TestSplitParseContract:
    def test_step_is_required(self) -> None:
        from plan_tool.cli import build_parser

        with pytest.raises(SystemExit):
            build_parser().parse_args(["split", "demo"])

    def test_into_appends_and_defaults_on(self) -> None:
        from plan_tool.cli import build_parser

        args = build_parser().parse_args(
            ["split", "demo", "--step", "2", "--into", "A", "--into", "B"]
        )
        assert args.into == ["A", "B"]
        assert args.step == 2
        assert args.iterate is True
        assert args.author_details is True
        assert args.auto_completeness is True

    def test_no_detail_and_no_completeness_flags(self) -> None:
        from plan_tool.cli import build_parser

        args = build_parser().parse_args(
            ["split", "demo", "--step", "1", "--no-detail", "--no-completeness"]
        )
        assert args.author_details is False
        assert args.auto_completeness is False


class TestSplitCmd:
    def test_fewer_than_two_titles_rejected(
        self, registered_plan, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The two-title guard fires before any split — exit 2, no claude.
        rc = main(registered_plan.argv("split", "demo", "--step", "1", "--into", "solo"))
        assert rc == 2
        assert "at least two" in capsys.readouterr().err

    def test_keyboard_interrupt_exits_130_after_recording_run_end(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json

        import plan_tool.cli.authoring as authoring

        monkeypatch.setattr(
            authoring,
            "split_step",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )

        with pytest.raises(SystemExit) as exc:
            main(registered_plan.argv(
                "split", "demo", "--step", "1", "--into", "A", "--into", "B"
            ))
        assert exc.value.code == 130

        log_path = next(
            (registered_plan.root / ".plan-tool" / "runs" / "demo").glob("*.jsonl")
        )
        events = [
            json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
        ]
        assert events[-1]["event"] == "run_end"
        assert events[-1]["rc"] == 130
        assert events[-1]["error"] == "interrupted"

    def test_clean_split_authors_and_runs_completeness_tail(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult, SplitResult

        calls: dict[str, object] = {}

        def fake_split_step(plan_path, *, target_id, new_titles, repo_root, **kw):
            calls["target_id"] = target_id
            calls["new_titles"] = list(new_titles)
            calls["author_details"] = kw.get("author_details")
            return SplitResult(
                target_id=target_id,
                original_title="Only step",
                new_ids=[1, 2],
                new_titles=list(new_titles),
                detail_results=[
                    DetailResult(
                        step_id=1,
                        output_path=repo_root / "plan-details/demo/01-a.md",
                        written=True,
                    ),
                    DetailResult(
                        step_id=2,
                        output_path=repo_root / "plan-details/demo/02-b.md",
                        written=True,
                    ),
                ],
            )

        monkeypatch.setattr(authoring, "split_step", fake_split_step)
        monkeypatch.setattr(
            app, "cmd_completeness", lambda _a: calls.__setitem__("tail", True) or 0
        )

        rc = main(
            registered_plan.argv(
                "split", "demo", "--step", "1",
                "--into", "Extract validator", "--into", "Wire it in",
            )
        )
        assert rc == 0
        assert calls["target_id"] == 1
        assert calls["new_titles"] == ["Extract validator", "Wire it in"]
        assert calls["author_details"] is True
        # The clean split ran the conceptual completeness tail.
        assert calls.get("tail") is True

    def test_no_completeness_skips_tail(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult, SplitResult

        ran = {"tail": False}

        def fake_split_step(plan_path, *, target_id, new_titles, repo_root, **kw):
            return SplitResult(
                target_id=target_id,
                original_title="Only step",
                new_ids=[1, 2],
                new_titles=list(new_titles),
                detail_results=[
                    DetailResult(
                        step_id=1,
                        output_path=repo_root / "01-a.md",
                        written=True,
                    ),
                ],
            )

        monkeypatch.setattr(authoring, "split_step", fake_split_step)
        monkeypatch.setattr(
            app, "cmd_completeness", lambda _a: ran.__setitem__("tail", True) or 0
        )

        rc = main(
            registered_plan.argv(
                "split", "demo", "--step", "1", "--no-completeness",
                "--into", "A", "--into", "B",
            )
        )
        assert rc == 0
        assert ran["tail"] is False
        err = capsys.readouterr().err
        assert "no current qualified audit result exists" in err
        assert "plan-tool completeness-audit demo" in err

    def test_no_detail_points_at_detail_next(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # `--no-detail` leaves the new halves un-authored, so the next step
        # is `plan-tool detail`, not reconcile-plan/run, and the completeness
        # tail (which needs authored bodies) is skipped.
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import SplitResult

        ran = {"tail": False}

        def fake_split_step(plan_path, *, target_id, new_titles, repo_root, **kw):
            assert kw.get("author_details") is False
            return SplitResult(
                target_id=target_id,
                original_title="Only step",
                new_ids=[1, 2],
                new_titles=list(new_titles),
                detail_results=[],
            )

        monkeypatch.setattr(authoring, "split_step", fake_split_step)
        monkeypatch.setattr(
            app, "cmd_completeness", lambda _a: ran.__setitem__("tail", True) or 0
        )

        rc = main(
            registered_plan.argv(
                "split", "demo", "--step", "1", "--no-detail",
                "--into", "A", "--into", "B",
            )
        )
        assert rc == 0
        err = capsys.readouterr().err
        assert "plan-tool detail demo" in err
        assert "plan-tool completeness-audit demo" in err
        assert "reconcile-plan" not in err
        assert ran["tail"] is False

    def test_dry_run_previews_without_writing(
        self, tmp_repo, capsys: pytest.CaptureFixture[str],
    ) -> None:
        # --dry-run runs the real split_step (no claude — dry-run returns
        # before authoring) and must leave the plan file byte-identical.
        plan_path = tmp_repo.plans_dir / "1-demo.md"
        plan_path.write_text(
            "---\ntitle: Demo\nstatus: in-progress\npriority: low\n"
            "steps:\n"
            "  - id: 1\n    title: Only step\n"
            "  - id: 2\n    title: Next\n    depends_on: [1]\n"
            "---\n# Body\n",
            encoding="utf-8",
        )
        tmp_repo.plans = [plan_path]
        tmp_repo.write_manifest()
        before = plan_path.read_text(encoding="utf-8")

        rc = main(
            tmp_repo.argv(
                "split", "demo", "--step", "1", "--dry-run",
                "--into", "A", "--into", "B",
            )
        )
        assert rc == 0
        assert plan_path.read_text(encoding="utf-8") == before
        out = capsys.readouterr()
        combined = out.out + out.err
        assert "dry-run" in combined
        assert "step 2 → 3" in combined

    def test_detail_error_returns_2(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailError

        def boom(*a, **k):
            raise DetailError("step 9 not found in 1-demo.md")

        monkeypatch.setattr(authoring, "split_step", boom)
        rc = main(
            registered_plan.argv(
                "split", "demo", "--step", "9", "--into", "A", "--into", "B"
            )
        )
        assert rc == 2
        assert "step 9 not found" in capsys.readouterr().err


def _write_multi_step_plan(repo, *, n: int = 4) -> Path:
    """Write + register an ``n``-step planning plan as ``1-demo`` under ``repo``.

    Used by the merge gate tests that need real steps 3/4 to exist so the TTY
    confirm gate can collect member ``Step`` objects.
    """
    steps = ["  - id: 1\n    title: Step one\n"]
    for i in range(2, n + 1):
        steps.append(f"  - id: {i}\n    title: Step {i}\n    depends_on: [{i - 1}]\n")
    plan_path = repo.plans_dir / "1-demo.md"
    plan_path.write_text(
        "---\ntitle: Demo\nstatus: planning\npriority: low\nsteps:\n"
        + "".join(steps)
        + "---\n# Body\n",
        encoding="utf-8",
    )
    repo.plans = [plan_path]
    repo.write_manifest()
    return plan_path


class TestMergeParseContract:
    def test_steps_appends_and_defaults_on(self) -> None:
        from plan_tool.cli import build_parser

        args = build_parser().parse_args(
            ["merge", "demo", "--steps", "3", "--steps", "4"]
        )
        assert args.steps == [3, 4]
        assert args.iterate is True
        assert args.author_details is True
        assert args.auto_completeness is True

    def test_steps_is_required(self) -> None:
        from plan_tool.cli import build_parser

        with pytest.raises(SystemExit):
            build_parser().parse_args(["merge", "demo"])

    def test_title_optional_defaults_none(self) -> None:
        from plan_tool.cli import build_parser

        args = build_parser().parse_args(
            ["merge", "demo", "--steps", "1", "--steps", "2"]
        )
        assert args.title is None
        args2 = build_parser().parse_args(
            ["merge", "demo", "--steps", "1", "--steps", "2", "--title", "X"]
        )
        assert args2.title == "X"

    def test_no_detail_and_no_completeness_flags(self) -> None:
        from plan_tool.cli import build_parser

        args = build_parser().parse_args(
            [
                "merge", "demo", "--steps", "1", "--steps", "2",
                "--no-detail", "--no-completeness",
            ]
        )
        assert args.author_details is False
        assert args.auto_completeness is False


class TestMergeCmd:
    def test_fewer_than_two_ids_rejected(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # The id guard fires before any merge — exit 2, no orchestrator call.
        import plan_tool.cli.authoring as authoring

        called = {"merge": False}
        monkeypatch.setattr(
            authoring, "merge_steps",
            lambda *a, **k: called.__setitem__("merge", True),
        )
        rc = main(registered_plan.argv("merge", "demo", "--steps", "1"))
        assert rc == 2
        assert "at least two" in capsys.readouterr().err
        assert called["merge"] is False

    def test_duplicate_ids_rejected(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # ``len(set(...)) < 2`` rejects a duplicated id too.
        import plan_tool.cli.authoring as authoring

        called = {"merge": False}
        monkeypatch.setattr(
            authoring, "merge_steps",
            lambda *a, **k: called.__setitem__("merge", True),
        )
        rc = main(
            registered_plan.argv("merge", "demo", "--steps", "3", "--steps", "3")
        )
        assert rc == 2
        assert called["merge"] is False

    def test_keyboard_interrupt_exits_130_after_recording_run_end(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json

        import plan_tool.cli.authoring as authoring

        monkeypatch.setattr(
            authoring,
            "merge_steps",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )

        with pytest.raises(SystemExit) as exc:
            main(registered_plan.argv(
                "merge", "demo", "--steps", "3", "--steps", "4"
            ))
        assert exc.value.code == 130

        log_path = next(
            (registered_plan.root / ".plan-tool" / "runs" / "demo").glob("*.jsonl")
        )
        events = [
            json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
        ]
        assert events[-1]["event"] == "run_end"
        assert events[-1]["rc"] == 130
        assert events[-1]["error"] == "interrupted"

    def test_interactive_decline_aborts_before_merge_steps(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # On a TTY without --yes, a declined confirm returns rc 2 before any
        # orchestrator call or disk mutation.
        import plan_tool.cli.authoring as authoring

        _write_multi_step_plan(tmp_repo)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr(
            authoring, "_confirm_merge", lambda *a, **k: False
        )
        called = {"merge": False}
        monkeypatch.setattr(
            authoring, "merge_steps",
            lambda *a, **k: called.__setitem__("merge", True),
        )
        rc = main(tmp_repo.argv("merge", "demo", "--steps", "3", "--steps", "4"))
        assert rc == 2
        assert "aborted" in capsys.readouterr().err
        assert called["merge"] is False

    def test_yes_bypasses_gate_and_proceeds(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # --yes bypasses the TTY gate (even on a TTY) and the merge proceeds.
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult, MergeResult

        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        confirmed = {"asked": False}
        monkeypatch.setattr(
            authoring, "_confirm_merge",
            lambda *a, **k: confirmed.__setitem__("asked", True) or True,
        )

        def fake_merge_steps(plan_path, *, merge_ids, title, repo_root, **kw):
            return MergeResult(
                merged_id=3,
                merged_title="Merged",
                folded_ids=list(merge_ids),
                folded_titles=["A", "B"],
                detail_results=[
                    DetailResult(
                        step_id=3,
                        output_path=repo_root / "03-merged.md",
                        written=True,
                    ),
                ],
            )

        monkeypatch.setattr(authoring, "merge_steps", fake_merge_steps)
        monkeypatch.setattr(app, "cmd_completeness", lambda _a: 0)

        rc = main(
            registered_plan.argv(
                "merge", "demo", "--steps", "3", "--steps", "4", "--yes"
            )
        )
        assert rc == 0
        assert confirmed["asked"] is False

    def test_confirm_invoked_before_merge_steps(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The confirm gate receives the member steps + preview title and fires
        # before merge_steps; --dry-run skips the prompt entirely.
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import MergeResult

        _write_multi_step_plan(tmp_repo)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        order: list[str] = []
        seen: dict[str, object] = {}

        def fake_confirm(prompt_fn, *, steps_to_merge, merged_title):
            order.append("confirm")
            seen["ids"] = [s.id for s in steps_to_merge]
            seen["title"] = merged_title
            return True

        def fake_merge_steps(plan_path, *, merge_ids, title, repo_root, **kw):
            order.append("merge")
            return MergeResult(
                merged_id=3,
                merged_title="Step 3",
                folded_ids=list(merge_ids),
                folded_titles=["Step 3", "Step 4"],
                detail_results=[],
            )

        monkeypatch.setattr(authoring, "_confirm_merge", fake_confirm)
        monkeypatch.setattr(authoring, "merge_steps", fake_merge_steps)
        monkeypatch.setattr(app, "cmd_completeness", lambda _a: 0)

        rc = main(tmp_repo.argv("merge", "demo", "--steps", "3", "--steps", "4"))
        assert rc == 0
        assert order == ["confirm", "merge"]
        assert seen["ids"] == [3, 4]
        # Preview title defaults to the lowest-id member's title.
        assert seen["title"] == "Step 3"

        # --dry-run skips the gate.
        order.clear()

        def fake_dry(plan_path, *, merge_ids, title, repo_root, **kw):
            order.append("merge")
            return MergeResult(
                merged_id=3,
                merged_title="Step 3",
                folded_ids=list(merge_ids),
                folded_titles=["Step 3", "Step 4"],
                detail_results=[],
                dry_run=True,
                renumber=[(4, 3)],
                new_plan=[(3, "Step 3", [])],
            )

        monkeypatch.setattr(authoring, "merge_steps", fake_dry)
        rc2 = main(
            tmp_repo.argv(
                "merge", "demo", "--steps", "3", "--steps", "4", "--dry-run"
            )
        )
        assert rc2 == 0
        assert order == ["merge"]

    def test_clean_merge_authors_and_runs_completeness_tail(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult, MergeResult

        calls: dict[str, object] = {}

        def fake_merge_steps(plan_path, *, merge_ids, title, repo_root, **kw):
            calls["merge_ids"] = list(merge_ids)
            calls["title"] = title
            calls["author_details"] = kw.get("author_details")
            return MergeResult(
                merged_id=3,
                merged_title="Merged",
                folded_ids=list(merge_ids),
                folded_titles=["A", "B"],
                detail_results=[
                    DetailResult(
                        step_id=3,
                        output_path=repo_root / "plan-details/demo/03-merged.md",
                        written=True,
                    ),
                ],
            )

        monkeypatch.setattr(authoring, "merge_steps", fake_merge_steps)
        monkeypatch.setattr(
            app, "cmd_completeness", lambda _a: calls.__setitem__("tail", True) or 0
        )

        rc = main(
            registered_plan.argv("merge", "demo", "--steps", "3", "--steps", "4")
        )
        assert rc == 0
        assert calls["merge_ids"] == [3, 4]
        assert calls["title"] is None
        assert calls["author_details"] is True
        assert calls.get("tail") is True

    def test_no_completeness_skips_tail(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult, MergeResult

        ran = {"tail": False}

        def fake_merge_steps(plan_path, *, merge_ids, title, repo_root, **kw):
            return MergeResult(
                merged_id=3,
                merged_title="Merged",
                folded_ids=list(merge_ids),
                folded_titles=["A", "B"],
                detail_results=[
                    DetailResult(
                        step_id=3, output_path=repo_root / "03-m.md", written=True
                    ),
                ],
            )

        monkeypatch.setattr(authoring, "merge_steps", fake_merge_steps)
        monkeypatch.setattr(
            app, "cmd_completeness", lambda _a: ran.__setitem__("tail", True) or 0
        )

        rc = main(
            registered_plan.argv(
                "merge", "demo", "--steps", "3", "--steps", "4", "--no-completeness"
            )
        )
        assert rc == 0
        assert ran["tail"] is False
        err = capsys.readouterr().err
        assert "no current qualified audit result exists" in err
        assert "plan-tool completeness-audit demo" in err

    def test_no_detail_points_at_detail_next(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # --no-detail leaves the merged step un-authored, so the next step is
        # `plan-tool detail`, not reconcile-plan/run, and the tail is skipped.
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import MergeResult

        ran = {"tail": False}

        def fake_merge_steps(plan_path, *, merge_ids, title, repo_root, **kw):
            assert kw.get("author_details") is False
            return MergeResult(
                merged_id=3,
                merged_title="Merged",
                folded_ids=list(merge_ids),
                folded_titles=["A", "B"],
                detail_results=[],
            )

        monkeypatch.setattr(authoring, "merge_steps", fake_merge_steps)
        monkeypatch.setattr(
            app, "cmd_completeness", lambda _a: ran.__setitem__("tail", True) or 0
        )

        rc = main(
            registered_plan.argv(
                "merge", "demo", "--steps", "3", "--steps", "4", "--no-detail"
            )
        )
        assert rc == 0
        err = capsys.readouterr().err
        assert "plan-tool detail demo" in err
        assert "plan-tool completeness-audit demo" in err
        assert "reconcile-plan" not in err
        assert ran["tail"] is False

    def test_dry_run_previews_without_writing(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Driving the real merge_steps dry-run requires steps 1-2 landed; this
        # routing test patches the orchestrator to return a dry-run result.
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import MergeResult

        def fake_merge_steps(plan_path, *, merge_ids, title, repo_root, **kw):
            assert kw.get("dry_run") is True
            return MergeResult(
                merged_id=3,
                merged_title="Merged",
                folded_ids=list(merge_ids),
                folded_titles=["A", "B"],
                detail_results=[],
                dry_run=True,
                renumber=[(1, 1), (2, 2), (3, 3), (4, 3), (5, 4)],
                new_plan=[(3, "Merged", [2])],
            )

        monkeypatch.setattr(authoring, "merge_steps", fake_merge_steps)
        rc = main(
            registered_plan.argv(
                "merge", "demo", "--steps", "3", "--steps", "4", "--dry-run"
            )
        )
        assert rc == 0
        out = capsys.readouterr()
        combined = out.out + out.err
        assert "dry-run" in combined
        assert "step 4 → 3" in combined
        assert "resulting plan" in combined

    def test_detail_error_returns_2(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailError

        def boom(*a, **k):
            raise DetailError("step 9 not found in 1-demo.md")

        monkeypatch.setattr(authoring, "merge_steps", boom)
        rc = main(
            registered_plan.argv("merge", "demo", "--steps", "3", "--steps", "9")
        )
        assert rc == 2
        assert "step 9 not found" in capsys.readouterr().err

    def test_title_forwarded_to_orchestrator(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult, MergeResult

        seen: dict[str, object] = {}

        def fake_merge_steps(plan_path, *, merge_ids, title, repo_root, **kw):
            seen["title"] = title
            return MergeResult(
                merged_id=3,
                merged_title=title or "Merged",
                folded_ids=list(merge_ids),
                folded_titles=["A", "B"],
                detail_results=[
                    DetailResult(
                        step_id=3, output_path=repo_root / "03-m.md", written=True
                    ),
                ],
            )

        monkeypatch.setattr(authoring, "merge_steps", fake_merge_steps)
        monkeypatch.setattr(app, "cmd_completeness", lambda _a: 0)
        rc = main(
            registered_plan.argv(
                "merge", "demo", "--steps", "3", "--steps", "4",
                "--title", "Combined",
            )
        )
        assert rc == 0
        assert seen["title"] == "Combined"


class TestDetailRecoverRefusedFlag:
    """``--recover-refused`` is a narrow, explicit opt-in: only the exact
    ``--step N --force --no-completeness --recover-refused`` shape passes
    ``recovery_only=True`` to ``generate_detail``; every other flag
    combination — including ordinary ``--force`` alone, which many other
    callers (merge, forced review regeneration) also pass — fails before
    mutation or leaves ``recovery_only`` unset."""

    @staticmethod
    def _patch_capture(monkeypatch: pytest.MonkeyPatch) -> dict:
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult

        calls: dict = {}

        def fake_generate_detail(plan_path, **kwargs):
            calls["called"] = True
            calls["recovery_only"] = kwargs.get("recovery_only")
            written = plan_path.parent / "detail.md"
            written.write_text("# detail\n", encoding="utf-8")
            return [DetailResult(step_id=1, output_path=written, written=True)]

        monkeypatch.setattr(authoring, "generate_detail", fake_generate_detail)
        return calls

    def test_exact_companion_shape_passes_recovery_only(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls = self._patch_capture(monkeypatch)
        rc = main(
            registered_plan.argv(
                "detail", "demo", "--step", "1", "--force",
                "--no-completeness", "--recover-refused",
            )
        )
        assert rc == 0
        assert calls["recovery_only"] is True

    def test_missing_step_is_rejected_before_mutation(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        calls = self._patch_capture(monkeypatch)
        rc = main(
            registered_plan.argv(
                "detail", "demo", "--force",
                "--no-completeness", "--recover-refused",
            )
        )
        assert rc == 2
        assert "--recover-refused" in capsys.readouterr().err
        assert "called" not in calls

    def test_missing_force_is_rejected_before_mutation(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        calls = self._patch_capture(monkeypatch)
        rc = main(
            registered_plan.argv(
                "detail", "demo", "--step", "1",
                "--no-completeness", "--recover-refused",
            )
        )
        assert rc == 2
        assert "--recover-refused" in capsys.readouterr().err
        assert "called" not in calls

    def test_missing_no_completeness_is_rejected_before_mutation(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        calls = self._patch_capture(monkeypatch)
        rc = main(
            registered_plan.argv(
                "detail", "demo", "--step", "1", "--force", "--recover-refused",
            )
        )
        assert rc == 2
        assert "--recover-refused" in capsys.readouterr().err
        assert "called" not in calls

    def test_ordinary_force_without_recover_refused_keeps_normal_context(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ordinary forced re-authoring — the shape merge and forced review
        regeneration also use — must not accidentally set recovery_only."""
        calls = self._patch_capture(monkeypatch)
        rc = main(
            registered_plan.argv("detail", "demo", "--step", "1", "--force")
        )
        assert rc == 0
        assert calls["recovery_only"] is False

    def test_docs_cli_reference_documents_the_flag(self) -> None:
        text = (
            Path(__file__).resolve().parents[2] / "docs" / "cli" / "detail.md"
        ).read_text(encoding="utf-8")
        assert "--recover-refused" in text


class TestDetailSkippedOnlyHint:
    def test_all_skipped_prints_split_or_force_hint(
        self, tmp_repo, capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # A plan whose only step already has its detail file on disk: a bare
        # `detail` run (non-TTY → auto-declines replace) skips everything and
        # invokes no claude. The tail must explain the no-op + point at
        # --force / `plan-tool split`, instead of printing nothing.
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        plan_path = tmp_repo.plans_dir / "1-demo.md"
        plan_path.write_text(
            "---\ntitle: Demo\nstatus: in-progress\npriority: low\n"
            "steps:\n"
            "  - id: 1\n    title: Only step\n"
            "    detail: plan-details/demo/01-only-step.md\n"
            "---\n# Body\n",
            encoding="utf-8",
        )
        ddir = tmp_repo.plans_dir / "plan-details" / "demo"
        ddir.mkdir(parents=True)
        (ddir / "01-only-step.md").write_text("# Only step\n", encoding="utf-8")
        tmp_repo.plans = [plan_path]
        tmp_repo.write_manifest()

        rc = main(tmp_repo.argv("detail", "demo"))
        assert rc == 0
        err = capsys.readouterr().err
        assert "Nothing to author" in err
        assert "plan-tool split demo --step" in err
        assert "--force" in err
        assert "no current qualified audit result exists" in err
        assert "plan-tool completeness-audit demo" in err


class TestDetailTailAuditFollowUp:
    @staticmethod
    def _current_result(plan_path: Path, repo_root: Path):
        from plan_tool.cli.completeness_cmd import QualifiedAuditResult
        from plan_tool.review_persistence import AuditInputSnapshot

        snapshot = AuditInputSnapshot.capture(plan_path, repo_root)
        return QualifiedAuditResult(
            "clean", "detail", "confirmed", "current", snapshot.revision
        )

    def test_qualified_run_tail_keeps_disposition_commands(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult

        plan_path = registered_plan.plans_dir / "1-demo.md"

        def fake_generate_detail(path, **kwargs):
            written = path.parent / "detail.md"
            written.write_text("# detail\n", encoding="utf-8")
            return [DetailResult(step_id=1, output_path=written, written=True)]

        def fake_tail(*_args, **_kwargs):
            return authoring._CompletenessTailOutcome(
                [
                    (
                        "plan-tool completeness-apply demo",
                        "walk the current audit findings",
                    )
                ],
                self._current_result(plan_path, registered_plan.root),
            )

        monkeypatch.setattr(authoring, "generate_detail", fake_generate_detail)
        monkeypatch.setattr(authoring, "_run_completeness_tail", fake_tail)
        rc = main(registered_plan.argv("detail", "demo"))
        assert rc == 0
        err = capsys.readouterr().err
        assert err.count("Next steps:") == 1
        assert "plan-tool completeness-apply demo" in err
        assert "plan-tool completeness-audit demo" not in err
        assert err.index("plan-tool completeness-apply demo") < err.index(
            "plan-tool reconcile-plan demo"
        )

    def test_auto_completeness_tail_reraises_detail_format_error(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A refused sibling surfacing during the automatic post-authoring
        audit must escape ``_run_completeness_tail`` — the shared helper
        every one of ``detail``/``split``/``merge`` calls — rather than
        being folded into the ordinary warning-only failure path, so a
        successful authoring write can never conceal it. ``main()`` itself
        reaches ``cli/app.py``'s typed handler and reports exit 1, not a
        successful-authoring outcome."""
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult
        from plan_tool.detail_artifacts import DetailFormatError

        def fake_generate_detail(path, **kwargs):
            written = path.parent / "detail.md"
            written.write_text("# detail\n", encoding="utf-8")
            return [DetailResult(step_id=1, output_path=written, written=True)]

        def boom(_args):
            raise DetailFormatError("detail declares an unsupported version")

        monkeypatch.setattr(authoring, "generate_detail", fake_generate_detail)
        monkeypatch.setattr(app, "cmd_completeness", boom)

        rc = main(registered_plan.argv("detail", "demo"))
        assert rc == 1
        err = capsys.readouterr().err
        assert "detail declares an unsupported version" in err
        assert "warning: auto-completeness pass failed" not in err

    def test_auto_completeness_tail_reraises_unsupported_plan_version(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult
        from plan_tool.parser import UnsupportedPlanFormatVersionError

        def fake_generate_detail(path, **kwargs):
            written = path.parent / "detail.md"
            written.write_text("# detail\n", encoding="utf-8")
            return [DetailResult(step_id=1, output_path=written, written=True)]

        def boom(_args):
            raise UnsupportedPlanFormatVersionError("unsupported format_version")

        monkeypatch.setattr(authoring, "generate_detail", fake_generate_detail)
        monkeypatch.setattr(app, "cmd_completeness", boom)

        assert main(registered_plan.argv("detail", "demo")) == 1
        err = capsys.readouterr().err
        assert "unsupported format_version" in err
        assert "warning: auto-completeness pass failed" not in err

    def test_direct_recovery_skips_the_auto_completeness_tail(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``--no-completeness`` is the flag every recovery route relies on
        to skip the whole-bundle tail entirely — including the direct
        ``--force --recover-refused`` incantation a later step adds, which
        is documented to skip this same tail while it replaces one refused
        target at a time. Proves the new exception handling is reachable
        only when the tail actually runs."""
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult

        ran = {"tail": False}

        def fake_generate_detail(path, **kwargs):
            written = path.parent / "detail.md"
            written.write_text("# detail\n", encoding="utf-8")
            return [DetailResult(step_id=1, output_path=written, written=True)]

        monkeypatch.setattr(authoring, "generate_detail", fake_generate_detail)
        monkeypatch.setattr(
            app, "cmd_completeness", lambda _a: ran.__setitem__("tail", True) or 0
        )

        rc = main(
            registered_plan.argv(
                "detail", "demo", "--step", "1", "--force", "--no-completeness",
            )
        )
        assert rc == 0
        assert ran["tail"] is False

    def test_auto_completeness_tail_keeps_ordinary_failure_as_warning(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult

        def fake_generate_detail(path, **kwargs):
            written = path.parent / "detail.md"
            written.write_text("# detail\n", encoding="utf-8")
            return [DetailResult(step_id=1, output_path=written, written=True)]

        def boom(_args):
            raise RuntimeError("transient audit failure")

        monkeypatch.setattr(authoring, "generate_detail", fake_generate_detail)
        monkeypatch.setattr(app, "cmd_completeness", boom)

        rc = main(registered_plan.argv("detail", "demo"))
        assert rc == 0
        err = capsys.readouterr().err
        assert "warning: auto-completeness pass failed" in err
        assert "transient audit failure" in err

    @pytest.mark.parametrize(
        "result",
        [
            None,
            {
                "headline": "no-qualified-current-evidence",
                "stage": "not-sampled",
                "coverage": "not-sampled",
                "revision_status": "not-sampled",
                "audit_revision": None,
            },
            {
                "headline": "clean",
                "stage": "detail",
                "coverage": "unconfirmed",
                "revision_status": "current",
                "audit_revision": "CURRENT",
            },
            {
                "headline": "clean",
                "stage": "detail",
                "coverage": "confirmed",
                "revision_status": "stale",
                "audit_revision": "CURRENT",
            },
            {
                "headline": "clean",
                "stage": "detail",
                "coverage": "confirmed",
                "revision_status": "unknown-legacy",
                "audit_revision": "CURRENT",
            },
        ],
    )
    def test_unqualified_or_missing_run_tail_routes_to_fresh_audit(
        self, registered_plan, result
    ) -> None:
        import plan_tool.cli.authoring as authoring
        from plan_tool.review_persistence import AuditInputSnapshot

        plan_path = registered_plan.plans_dir / "1-demo.md"
        snapshot = AuditInputSnapshot.capture(plan_path, registered_plan.root)
        if isinstance(result, dict) and result["audit_revision"] == "CURRENT":
            result = {**result, "audit_revision": snapshot.revision}
        follow_up = authoring._authoring_audit_follow_up(
            "demo",
            path=plan_path,
            repo_root=registered_plan.root,
            tail_outcome=authoring._CompletenessTailOutcome(
                [("unsafe command", "must not survive")], result
            ),
        )
        assert follow_up == [
            (
                "plan-tool completeness-audit demo --iterate",
                "no current qualified audit result exists; run a fresh audit",
            )
        ]

    def test_nonmatching_tail_revision_routes_to_fresh_audit(
        self, registered_plan
    ) -> None:
        import plan_tool.cli.authoring as authoring

        plan_path = registered_plan.plans_dir / "1-demo.md"
        result = self._current_result(plan_path, registered_plan.root).as_dict()
        result["audit_revision"] = {
            **result["audit_revision"],
            "plan_digest": "other-plan-revision",
        }
        follow_up = authoring._authoring_audit_follow_up(
            "demo",
            path=plan_path,
            repo_root=registered_plan.root,
            tail_outcome=authoring._CompletenessTailOutcome([], result),
        )
        assert follow_up[0][0] == "plan-tool completeness-audit demo --iterate"


# --------------------------------------------------------------------------
# `plan-tool detail --commit` — opt-in post-authoring git commit
# --------------------------------------------------------------------------


def _init_git_repo(root: Path) -> None:
    import subprocess

    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(cmd, cwd=root, check=True, capture_output=True)


def _git_commit_all(root: Path, message: str) -> None:
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", message],
        cwd=root, check=True, capture_output=True,
    )


class TestDetailCommitHelpers:
    def test_step_subject_format(self) -> None:
        from plan_tool.cli.authoring import _detail_step_commit_subject

        assert _detail_step_commit_subject("demo", 1, "Add the widget") == (
            "plan(demo): detail step 1 — Add the widget"
        )
        # A long / whitespace-noisy title is collapsed + truncated so the
        # subject stays a sane one-liner.
        subj = _detail_step_commit_subject("demo", 2, "x " * 80)
        assert subj.startswith("plan(demo): detail step 2 — ")
        assert len(subj) < 100

    def test_residual_subject_format(self) -> None:
        from plan_tool.cli.authoring import _detail_residual_commit_subject

        assert _detail_residual_commit_subject("demo") == (
            "plan(demo): detail — residual authoring edits"
        )

    def test_working_tree_dirty_detects_change_and_non_repo(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.cli.authoring import _working_tree_dirty

        # Not a git work tree → treated as dirty (can't safely commit).
        assert _working_tree_dirty(tmp_path) is True
        _init_git_repo(tmp_path)
        (tmp_path / "f.txt").write_text("x\n", encoding="utf-8")
        _git_commit_all(tmp_path, "init")
        assert _working_tree_dirty(tmp_path) is False
        (tmp_path / "f.txt").write_text("y\n", encoding="utf-8")
        assert _working_tree_dirty(tmp_path) is True

    def test_commit_detail_step_commits_when_dirty_noop_when_clean(
        self, tmp_path: Path
    ) -> None:
        import subprocess

        from plan_tool.cli.authoring import _commit_detail_step

        def _count(root: Path) -> int:
            return int(subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=root, capture_output=True, text=True,
            ).stdout.strip())

        _init_git_repo(tmp_path)
        (tmp_path / "seed.txt").write_text("x\n", encoding="utf-8")
        _git_commit_all(tmp_path, "init")

        # Clean tree → None (nothing to commit; never counted as a commit).
        base = _count(tmp_path)
        assert _commit_detail_step(
            tmp_path, slug="demo", step_id=1, title="Nothing"
        ) is None
        assert _count(tmp_path) == base

        # Dirty tree → one commit with the per-step subject.
        (tmp_path / "new.md").write_text("# new\n", encoding="utf-8")
        res = _commit_detail_step(
            tmp_path, slug="demo", step_id=3, title="Add thing"
        )
        assert res is not None
        rc, tail = res
        assert rc == 0, tail
        assert _count(tmp_path) == base + 1
        log = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=tmp_path, capture_output=True, text=True,
        ).stdout
        assert "plan(demo): detail step 3 — Add thing" in log

    @pytest.mark.parametrize(
        "exc",
        [
            OSError("git: command not found"),
            # subprocess.run(text=True) raises UnicodeDecodeError (a ValueError)
            # decoding non-UTF-8 git/hook output.
            UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
        ],
    )
    def test_commit_if_dirty_degrades_on_git_subprocess_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exc: Exception,
    ) -> None:
        """The shared commit primitive (used by BOTH the per-step commit and the
        end-of-run sweep) degrades a git subprocess failure — OSError, or a
        UnicodeDecodeError/ValueError from decoding non-UTF-8 output — to a
        reported failure, never raising, so neither path can crash the run."""
        from plan_tool.cli import authoring

        _init_git_repo(tmp_path)
        (tmp_path / "seed.txt").write_text("x\n", encoding="utf-8")
        _git_commit_all(tmp_path, "init")
        (tmp_path / "new.md").write_text("# new\n", encoding="utf-8")  # dirty

        def boom(*_a, **_k):
            raise exc

        monkeypatch.setattr(authoring, "_commit_all", boom)
        res = authoring._commit_if_dirty(tmp_path, "plan(demo): subj")
        assert res is not None
        rc, tail = res
        assert rc == 1
        assert "git subprocess error" in tail


class TestDetailCommitCmd:
    def test_commit_requires_clean_tree(
        self, tmp_repo, capsys: pytest.CaptureFixture[str],
    ) -> None:
        import shutil

        shutil.rmtree(tmp_repo.root / ".git")
        _init_git_repo(tmp_repo.root)
        tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")
        # Dirty the tree so the precheck rejects.
        (tmp_repo.root / "stray.txt").write_text("x\n", encoding="utf-8")

        rc = main(tmp_repo.argv("detail", "demo", "--commit"))
        assert rc == 2
        assert "clean working tree" in capsys.readouterr().err

    def _setup_git_plan(self, tmp_repo) -> Path:
        import shutil

        shutil.rmtree(tmp_repo.root / ".git")
        _init_git_repo(tmp_repo.root)
        tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")
        return tmp_repo.plans_dir / "plan-details" / "demo"

    def test_commit_is_per_step(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """#122: --commit commits each converged step separately (not one at
        the end), so the history is per-step and completed steps are durable."""
        import subprocess

        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult

        ddir = self._setup_git_plan(tmp_repo)

        def fake_gen(plan_path, *, repo_root, commit_step=None, **kw):
            # Simulate generate_detail authoring two steps, each firing the
            # per-step commit callback as it converges.
            ddir.mkdir(parents=True, exist_ok=True)
            results = []
            for sid, title in [(1, "First step"), (2, "Second step")]:
                f = ddir / f"{sid:02d}-step.md"
                f.write_text(f"# detail {sid}\n", encoding="utf-8")
                if commit_step is not None:
                    commit_step(sid, title)
                results.append(
                    DetailResult(step_id=sid, output_path=f, written=True)
                )
            return results

        monkeypatch.setattr(authoring, "generate_detail", fake_gen)
        monkeypatch.setattr(app, "cmd_completeness", lambda _a: 0)

        rc = main(tmp_repo.argv("detail", "demo", "--commit"))
        assert rc == 0
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=tmp_repo.root, capture_output=True, text=True,
        ).stdout
        # Two distinct per-step commits, not one "authored N steps" commit.
        assert "detail step 1 — First step" in log
        assert "detail step 2 — Second step" in log
        # Both files are committed (gone from the working-tree status).
        porcelain = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=tmp_repo.root, capture_output=True, text=True,
        ).stdout
        assert "01-step.md" not in porcelain
        assert "02-step.md" not in porcelain

    def test_commit_interruption_keeps_completed_steps(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """#122's core win: a batch that crashes mid-run keeps the steps that
        already converged + committed — no manual commit-and-resume needed."""
        import subprocess

        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring

        ddir = self._setup_git_plan(tmp_repo)

        def fake_gen(plan_path, *, repo_root, commit_step=None, **kw):
            ddir.mkdir(parents=True, exist_ok=True)
            (ddir / "01-step.md").write_text("# detail 1\n", encoding="utf-8")
            if commit_step is not None:
                commit_step(1, "First step")
            # Crash before step 2 — the pre-#122 behavior would have committed
            # nothing at all.
            raise RuntimeError("boom — simulated crash mid-batch")

        monkeypatch.setattr(authoring, "generate_detail", fake_gen)
        monkeypatch.setattr(app, "cmd_completeness", lambda _a: 0)

        rc = main(tmp_repo.argv("detail", "demo", "--commit"))
        assert rc != 0  # the crash surfaced as a non-zero rc
        # ...but step 1's commit is durably present despite the crash.
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=tmp_repo.root, capture_output=True, text=True,
        ).stdout
        assert "detail step 1 — First step" in log

    def test_commit_concurrent_path_is_one_batch(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The concurrent (--jobs>1) path authors in parallel and cannot commit
        per step (all files land before the serial tail), so generate_detail
        never fires commit_step there — --commit falls back to one batch commit
        at end-of-run, not a misattributed per-step history."""
        import subprocess

        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult

        ddir = self._setup_git_plan(tmp_repo)

        def fake_gen(plan_path, *, repo_root, commit_step=None, **kw):
            # Simulate the concurrent path: files written, commit_step NOT fired.
            ddir.mkdir(parents=True, exist_ok=True)
            results = []
            for sid in (1, 2):
                f = ddir / f"{sid:02d}-step.md"
                f.write_text(f"# detail {sid}\n", encoding="utf-8")
                results.append(
                    DetailResult(step_id=sid, output_path=f, written=True)
                )
            return results

        monkeypatch.setattr(authoring, "generate_detail", fake_gen)
        monkeypatch.setattr(app, "cmd_completeness", lambda _a: 0)

        # --jobs>1 needs a frozen step set (--no-iterate --no-split).
        rc = main(tmp_repo.argv(
            "detail", "demo", "--commit", "--jobs", "2",
            "--no-iterate", "--no-split",
        ))
        assert rc == 0
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=tmp_repo.root, capture_output=True, text=True,
        ).stdout
        assert "detail — authored 2 steps" in log  # one batch commit
        assert "detail step 1" not in log  # not per-step

    def test_commit_skipped_only_run_makes_no_commit(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A --commit run that authors nothing (every step already detailed)
        must not create a commit, even if tracked run-log churn dirtied the
        tree — the residual sweep is gated on a productive run."""
        import subprocess

        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult

        self._setup_git_plan(tmp_repo)

        def fake_gen(plan_path, *, repo_root, commit_step=None, **kw):
            # Author nothing; dirty a tracked file to stand in for run-log noise.
            (tmp_repo.root / "noise.txt").write_text("x\n", encoding="utf-8")
            return [
                DetailResult(
                    step_id=1,
                    output_path=tmp_repo.root / "x",
                    written=False,
                    skipped_reason="already exists",
                )
            ]

        monkeypatch.setattr(authoring, "generate_detail", fake_gen)
        monkeypatch.setattr(app, "cmd_completeness", lambda _a: 0)

        def _count() -> str:
            return subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=tmp_repo.root, capture_output=True, text=True,
            ).stdout.strip()

        before = _count()
        rc = main(tmp_repo.argv("detail", "demo", "--commit"))
        assert rc == 0
        assert _count() == before  # nothing authored → no commit

    def test_commit_stops_after_a_per_step_failure(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A failed per-step commit (e.g. a hook rejection) stops further
        per-step commits, so a later step's `git add -A` cannot fold the failed
        step's staged files into the wrong commit (review finding #1)."""
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult

        ddir = self._setup_git_plan(tmp_repo)

        calls: list[str] = []
        real_commit_all = authoring._commit_all

        def flaky_commit_all(repo_root, subject):
            calls.append(subject)
            if "detail step 1" in subject:  # reject step 1's commit
                return (1, "pre-commit hook rejected")
            return real_commit_all(repo_root, subject)

        monkeypatch.setattr(authoring, "_commit_all", flaky_commit_all)

        def fake_gen(plan_path, *, repo_root, commit_step=None, **kw):
            ddir.mkdir(parents=True, exist_ok=True)
            results = []
            for sid, title in [(1, "First step"), (2, "Second step")]:
                f = ddir / f"{sid:02d}-step.md"
                f.write_text(f"# detail {sid}\n", encoding="utf-8")
                if commit_step is not None:
                    commit_step(sid, title)
                results.append(
                    DetailResult(step_id=sid, output_path=f, written=True)
                )
            return results

        monkeypatch.setattr(authoring, "generate_detail", fake_gen)
        monkeypatch.setattr(app, "cmd_completeness", lambda _a: 0)

        rc = main(tmp_repo.argv("detail", "demo", "--commit"))
        assert rc != 0  # the failure surfaced
        # Step 1's commit was attempted (and failed); step 2's was NOT attempted
        # — no misattributing step 1's staged files under a step-2 subject.
        assert any("detail step 1" in s for s in calls)
        assert not any("detail step 2" in s for s in calls)

    def test_detail_merges_completeness_next_steps_into_one_block(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch, capsys,
    ) -> None:
        """The completeness tail's disposition action leads a single
        ``Next steps:`` block, ahead of the standing pipeline commands —
        not buried in a separate, second next-steps block above it."""
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult

        tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        ddir = tmp_repo.plans_dir / "plan-details" / "demo"

        def fake_gen(plan_path, *, repo_root, **kw):
            ddir.mkdir(parents=True, exist_ok=True)
            f = ddir / "01-only-step.md"
            f.write_text("# detail\n", encoding="utf-8")
            return [DetailResult(step_id=1, output_path=f, written=True)]

        monkeypatch.setattr(authoring, "generate_detail", fake_gen)

        # Stand in for the completeness finalize: populate the sink the tail
        # hands it, including its final evidence, as the real
        # `_persist_and_present_report` does.
        def fake_completeness(a):
            from plan_tool.cli.completeness_cmd import QualifiedAuditResult
            from plan_tool.review_persistence import AuditInputSnapshot

            a._next_steps_sink.append((
                "plan-tool completeness-apply demo",
                "walk 4 conceptual gap(s) — advisory, your call",
            ))
            snapshot = AuditInputSnapshot.capture(
                tmp_repo.plans_dir / "1-demo.md", tmp_repo.root
            )
            a._final_qualified_result_sink.append(QualifiedAuditResult(
                "awaiting-human-action",
                "detail",
                "confirmed",
                "current",
                snapshot.revision,
            ))
            return 0

        monkeypatch.setattr(app, "cmd_completeness", fake_completeness)

        rc = main(tmp_repo.argv("detail", "demo"))
        assert rc == 0
        err = capsys.readouterr().err
        # Exactly one "Next steps:" header.
        assert err.count("Next steps:") == 1
        # The disposition action comes before the pipeline `reconcile-plan` line.
        assert (
            err.index("plan-tool completeness-apply demo")
            < err.index("plan-tool reconcile-plan demo")
        )

    def test_no_commit_flag_leaves_changes_uncommitted(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import shutil
        import subprocess

        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult

        shutil.rmtree(tmp_repo.root / ".git")
        _init_git_repo(tmp_repo.root)
        tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")

        ddir = tmp_repo.plans_dir / "plan-details" / "demo"

        def fake_gen(plan_path, *, repo_root, **kw):
            ddir.mkdir(parents=True, exist_ok=True)
            f = ddir / "01-only-step.md"
            f.write_text("# detail\n", encoding="utf-8")
            return [DetailResult(step_id=1, output_path=f, written=True)]

        monkeypatch.setattr(authoring, "generate_detail", fake_gen)
        monkeypatch.setattr(app, "cmd_completeness", lambda _a: 0)

        rc = main(tmp_repo.argv("detail", "demo"))
        assert rc == 0
        # Without --commit the authored file is left uncommitted.
        assert subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=tmp_repo.root, capture_output=True, text=True,
        ).stdout.strip() != ""


# --------------------------------------------------------------------------
# `create` namespace-collision gate — `_create_branch_collision_gate`
# --------------------------------------------------------------------------


def _enable_branch_awareness_config(root: Path) -> None:
    import json

    cfg = root / ".plan-tool" / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        json.dumps({"branch_awareness": {"enabled": True}}), encoding="utf-8"
    )


def _branch_aware_repo(root: Path) -> str:
    """Init a real git repo with branch-awareness on + one clean commit.

    Commits the config (and a README) so the tree is clean — the
    disambiguation path needs a clean tree. Returns the default branch name.
    """
    import subprocess

    _init_git_repo(root)
    _enable_branch_awareness_config(root)
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _git_commit_all(root, "init")
    return subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"],
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _make_branch(root: Path, name: str) -> None:
    import subprocess

    subprocess.run(
        ["git", "branch", name], cwd=root, check=True, capture_output=True
    )


def _branch_head(root: Path, ref: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", "rev-parse", ref],
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _checked_out_branch(root: Path) -> "str | None":
    import subprocess

    proc = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"],
        cwd=root, capture_output=True, text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


class TestCreateBranchCollisionGate:
    """Helper-level unit cases against a real ``tmp_path`` git repo."""

    @staticmethod
    def _args(**over):
        import argparse

        ns = argparse.Namespace(yes=False)
        for k, v in over.items():
            setattr(ns, k, v)
        return ns

    @staticmethod
    def _gate(**kw):
        from plan_tool.cli.authoring import _create_branch_collision_gate

        return _create_branch_collision_gate(**kw)

    def test_off_config_is_noop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No config → branch awareness off → returns None before any git read.
        import plan_tool.cli.authoring as authoring

        _init_git_repo(tmp_path)
        def _boom(*_a, **_k):  # pragma: no cover - must not run
            raise AssertionError("gate must not read git when awareness is off")

        monkeypatch.setattr(authoring, "current_branch", _boom)
        assert (
            self._gate(
                args=self._args(), repo_root=tmp_path, slug="demo",
                registered_slugs=set(),
            )
            is None
        )

    def test_non_git_or_detached_is_noop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Detached HEAD with an existing plan/demo branch → short-circuits at
        # the current_branch-is-None check, never reaching ownership work.
        import subprocess

        import plan_tool.cli.authoring as authoring

        _branch_aware_repo(tmp_path)
        _make_branch(tmp_path, "plan/demo")
        subprocess.run(
            ["git", "checkout", "-q", "--detach", "HEAD"],
            cwd=tmp_path, check=True, capture_output=True,
        )

        def _boom(*_a, **_k):  # pragma: no cover - must not run
            raise AssertionError("must not reach ownership check on detached HEAD")

        monkeypatch.setattr(authoring, "branch_owner", _boom)
        assert (
            self._gate(
                args=self._args(), repo_root=tmp_path, slug="demo",
                registered_slugs=set(),
            )
            is None
        )

    def test_no_existing_branch_proceeds(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _branch_aware_repo(tmp_path)
        assert (
            self._gate(
                args=self._args(), repo_root=tmp_path, slug="demo",
                registered_slugs=set(),
            )
            is None
        )
        assert "already exists" not in capsys.readouterr().err

    def test_existing_owned_branch_proceeds(self, tmp_path: Path) -> None:
        # plan/demo exists AND demo is registered → convention owner → not a
        # foreign collision.
        _branch_aware_repo(tmp_path)
        _make_branch(tmp_path, "plan/demo")
        assert (
            self._gate(
                args=self._args(), repo_root=tmp_path, slug="demo",
                registered_slugs={"demo"},
            )
            is None
        )

    def test_unowned_collision_declined_returns_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _branch_aware_repo(tmp_path)
        _make_branch(tmp_path, "plan/demo")
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        rc = self._gate(
            args=self._args(), repo_root=tmp_path, slug="demo",
            registered_slugs=set(), input_fn=lambda _p: "a",
        )
        assert rc == 2
        assert not branch_exists(tmp_path, "plan/demo-2")

    def test_unowned_collision_continue_creates_first_free(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = _branch_aware_repo(tmp_path)
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", base)
        _make_branch(tmp_path, "plan/demo")
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        rc = self._gate(
            args=self._args(), repo_root=tmp_path, slug="demo",
            registered_slugs=set(), input_fn=lambda _p: "c",
        )
        assert rc is None
        assert branch_exists(tmp_path, "plan/demo")  # foreign branch intact
        assert branch_exists(tmp_path, "plan/demo-2")
        assert _checked_out_branch(tmp_path) == "plan/demo-2"

    def test_disambiguated_branch_is_bound(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.branch_ownership import expected_branch
        from plan_tool.project_config import branch_prefixes

        base = _branch_aware_repo(tmp_path)
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", base)
        _make_branch(tmp_path, "plan/demo")
        rc = self._gate(
            args=self._args(yes=True), repo_root=tmp_path, slug="demo",
            registered_slugs=set(),
        )
        assert rc is None
        prefixes = branch_prefixes(tmp_path)
        assert expected_branch(tmp_path, "demo", prefixes) == "plan/demo-2"

    def test_disambiguation_skips_taken_suffixes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = _branch_aware_repo(tmp_path)
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", base)
        _make_branch(tmp_path, "plan/demo")
        _make_branch(tmp_path, "plan/demo-2")
        rc = self._gate(
            args=self._args(yes=True), repo_root=tmp_path, slug="demo",
            registered_slugs=set(),
        )
        assert rc is None
        assert branch_exists(tmp_path, "plan/demo-3")
        assert _checked_out_branch(tmp_path) == "plan/demo-3"

    def test_yes_auto_continues(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = _branch_aware_repo(tmp_path)
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", base)
        _make_branch(tmp_path, "plan/demo")
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

        def _boom(_p):  # pragma: no cover - must not prompt under --yes
            raise AssertionError("must not prompt when yes=True")

        rc = self._gate(
            args=self._args(yes=True), repo_root=tmp_path, slug="demo",
            registered_slugs=set(), input_fn=_boom,
        )
        assert rc is None
        assert branch_exists(tmp_path, "plan/demo-2")

    def test_dirty_tree_refuses(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = _branch_aware_repo(tmp_path)
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", base)
        _make_branch(tmp_path, "plan/demo")
        (tmp_path / "stray.txt").write_text("x\n", encoding="utf-8")
        rc = self._gate(
            args=self._args(yes=True), repo_root=tmp_path, slug="demo",
            registered_slugs=set(),
        )
        assert rc == 2
        assert not branch_exists(tmp_path, "plan/demo-2")
        assert _checked_out_branch(tmp_path) == base

    def test_no_default_branch_skips_disambiguation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _branch_aware_repo(tmp_path)
        monkeypatch.delenv("PLAN_TOOL_DEFAULT_BRANCH", raising=False)
        _make_branch(tmp_path, "plan/demo")
        rc = self._gate(
            args=self._args(yes=True), repo_root=tmp_path, slug="demo",
            registered_slugs=set(),
        )
        assert rc is None
        assert not branch_exists(tmp_path, "plan/demo-2")
        from plan_tool.branch_binding import all_bindings

        assert "demo" not in all_bindings(tmp_path)
        # A strong warning (stderr), naming the skipped protection.
        assert "protection skipped" in capsys.readouterr().err

    def test_creates_from_default_not_current_head(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import subprocess

        base = _branch_aware_repo(tmp_path)
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", base)
        # Move to an unrelated branch with a distinct HEAD.
        subprocess.run(
            ["git", "switch", "-q", "-c", "feature"],
            cwd=tmp_path, check=True, capture_output=True,
        )
        (tmp_path / "feature.txt").write_text("f\n", encoding="utf-8")
        _git_commit_all(tmp_path, "feature work")
        _make_branch(tmp_path, "plan/demo")  # unowned collision
        rc = self._gate(
            args=self._args(yes=True), repo_root=tmp_path, slug="demo",
            registered_slugs=set(),
        )
        assert rc is None
        assert _branch_head(tmp_path, "plan/demo-2") == _branch_head(tmp_path, base)
        assert _branch_head(tmp_path, "plan/demo-2") != _branch_head(
            tmp_path, "feature"
        )


class TestCreateBranchRemoteCollisionGate:
    """Helper-level unit cases for the no-local-branch remote advisory tier.

    ``authoring.list_branches`` is stubbed so the remote ref is simulated and
    the test asserts the gate reads the offline, network-free enumerator (a
    raise-on-call stub proves the read never happens on the other paths).
    """

    @staticmethod
    def _args(**over):
        import argparse

        ns = argparse.Namespace(yes=False)
        for k, v in over.items():
            setattr(ns, k, v)
        return ns

    @staticmethod
    def _gate(**kw):
        from plan_tool.cli.authoring import _create_branch_collision_gate

        return _create_branch_collision_gate(**kw)

    def test_remote_only_collision_warns_and_proceeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import plan_tool.cli.authoring as authoring

        _branch_aware_repo(tmp_path)  # no local plan/demo
        monkeypatch.setattr(
            authoring, "list_branches",
            lambda _r: ["origin/plan/demo", "main"],
        )
        assert (
            self._gate(
                args=self._args(), repo_root=tmp_path, slug="demo",
                registered_slugs=set(),
            )
            is None
        )
        err = capsys.readouterr().err
        assert "origin/plan/demo" in err
        assert "no network performed" in err
        assert not branch_exists(tmp_path, "plan/demo-2")  # no disambiguation

    def test_remote_no_collision_is_silent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import plan_tool.cli.authoring as authoring

        _branch_aware_repo(tmp_path)  # no local plan/demo
        monkeypatch.setattr(
            authoring, "list_branches", lambda _r: ["main", "origin/main"],
        )
        assert (
            self._gate(
                args=self._args(), repo_root=tmp_path, slug="demo",
                registered_slugs=set(),
            )
            is None
        )
        assert "already exists on the remote" not in capsys.readouterr().err

    def test_local_collision_does_not_read_remote(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import plan_tool.cli.authoring as authoring

        base = _branch_aware_repo(tmp_path)
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", base)
        _make_branch(tmp_path, "plan/demo")  # local unowned collision

        def _boom(_r):  # pragma: no cover - must not run
            raise AssertionError("disambiguation must not read remote refs")

        monkeypatch.setattr(authoring, "list_branches", _boom)
        rc = self._gate(
            args=self._args(yes=True), repo_root=tmp_path, slug="demo",
            registered_slugs=set(),
        )
        assert rc is None
        assert branch_exists(tmp_path, "plan/demo-2")  # local path still ran
        assert "already exists on the remote" not in capsys.readouterr().err

    def test_owned_local_branch_skips_remote_read(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import plan_tool.cli.authoring as authoring

        _branch_aware_repo(tmp_path)
        _make_branch(tmp_path, "plan/demo")  # owned (demo registered)

        def _boom(_r):  # pragma: no cover - must not run
            raise AssertionError("owned-defer path must not read remote refs")

        monkeypatch.setattr(authoring, "list_branches", _boom)
        assert (
            self._gate(
                args=self._args(), repo_root=tmp_path, slug="demo",
                registered_slugs={"demo"},
            )
            is None
        )

    def test_flag_off_reads_no_branches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import plan_tool.cli.authoring as authoring

        _init_git_repo(tmp_path)  # no branch-awareness config

        def _boom(_r):  # pragma: no cover - must not run
            raise AssertionError("flag-off gate must not enumerate branches")

        monkeypatch.setattr(authoring, "list_branches", _boom)
        assert (
            self._gate(
                args=self._args(), repo_root=tmp_path, slug="demo",
                registered_slugs=set(),
            )
            is None
        )


class TestCreateBranchCollisionMain:
    """Component cases driving ``main(['create', …])`` (no claude)."""

    def test_main_create_off_config_unchanged(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import shutil

        import plan_tool.cli.authoring as authoring
        from plan_tool.create import CreateResult

        shutil.rmtree(tmp_repo.root / ".git")
        _init_git_repo(tmp_repo.root)
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")
        _make_branch(tmp_repo.root, "plan/demo")
        before = _checked_out_branch(tmp_repo.root)

        def fake_create_plan(slug, *, repo_root, manifest_path, **kw):
            plan_path = _write_created_plan(tmp_repo, slug=slug)
            return CreateResult(
                plan_path=plan_path, manifest_path=manifest_path,
                manifest_updated=True,
            )

        monkeypatch.setattr(authoring, "create_plan", fake_create_plan)
        rc = main(tmp_repo.argv("create", "demo", "--from", "an idea", "--yes"))
        assert rc == 0
        # Gate was inert: no disambiguation, no branch switch.
        assert not branch_exists(tmp_repo.root, "plan/demo-2")
        assert _checked_out_branch(tmp_repo.root) == before

    def test_main_create_declined_collision_returns_2_no_plan(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import shutil

        import plan_tool.cli.authoring as authoring

        shutil.rmtree(tmp_repo.root / ".git")
        _init_git_repo(tmp_repo.root)
        _enable_branch_awareness_config(tmp_repo.root)
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")
        _make_branch(tmp_repo.root, "plan/demo")

        def _boom(*_a, **_k):  # pragma: no cover - must not be reached
            raise AssertionError("create_plan must not run on a declined collision")

        monkeypatch.setattr(authoring, "create_plan", _boom)
        # An interactive stdin that answers "a" (abort): isatty True forces the
        # prompt, and the bare builtin ``input`` reads our scripted line.
        import io

        class _Tty(io.StringIO):
            def isatty(self) -> bool:
                return True

        monkeypatch.setattr(sys, "stdin", _Tty("a\n"))
        rc = main(tmp_repo.argv("create", "demo", "--from", "an idea"))
        assert rc == 2
        assert not (tmp_repo.plans_dir / "1-demo.md").exists()
        assert not branch_exists(tmp_repo.root, "plan/demo-2")

    def test_main_create_roadmap_refusal_rolls_back_binding(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import shutil

        import plan_tool.cli.authoring as authoring
        from plan_tool.branch_binding import all_bindings, reverse_binding
        from plan_tool.create import CreateError

        shutil.rmtree(tmp_repo.root / ".git")
        _init_git_repo(tmp_repo.root)
        _enable_branch_awareness_config(tmp_repo.root)
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")
        invocation = _checked_out_branch(tmp_repo.root)
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", invocation)
        _make_branch(tmp_repo.root, "plan/demo")
        source = _write_tracked_draft(tmp_repo.root)
        _git_commit_all(tmp_repo.root, "add tracked create source")

        def _fail(slug, **kw):
            raise CreateError(
                "selected roadmap product 'Demo' at test origin has no source "
                "evidence or recorded description; add a description or repair "
                "source evidence before retrying"
            )

        monkeypatch.setattr(authoring, "create_plan", _fail)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source), "--yes"
            )
        )
        assert rc == 1
        # Binding cleared, invocation branch restored, candidate and source remain.
        assert "demo" not in all_bindings(tmp_repo.root)
        assert reverse_binding(tmp_repo.root, "plan/demo-2") is None
        assert _checked_out_branch(tmp_repo.root) == invocation
        assert branch_exists(tmp_repo.root, "plan/demo-2")
        assert source.is_file()
        assert not (source.parent / "archive").exists()

    def test_main_create_nonexistent_from_existing_path_returns_2(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Same failure class as the tracked-seed-state case below (an
        # unusable/invalid seed reference, not a hard crash) -- both are
        # "usage" per cmd_create's own documented 1=hard-error /
        # 2=usage-or-collision exit contract.
        import plan_tool.cli.authoring as authoring

        def _boom_create(*_a, **_k):  # pragma: no cover - must not be reached
            raise AssertionError("create_plan must not run past a missing --from-existing path")

        monkeypatch.setattr(authoring, "create_plan", _boom_create)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(tmp_repo.root / "missing.md"), "--yes"
            )
        )
        assert rc == 2

    def test_main_create_malformed_tracked_seed_state_returns_2(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # locate_tracked_seed's failure class matches
        # _confirm_invalidated_roadmap_seed's own handler for the same
        # exception types a few lines below (still exit 2) — both describe
        # an unusable/invalid tracked-seed reference, not a hard crash.
        import plan_tool.cli.authoring as authoring
        from plan_tool.roadmap_seed_state import RoadmapSeedStateError

        source = tmp_repo.root / "seed.md"
        source.write_text("# Demo seed\n", encoding="utf-8")

        def _boom(*_a, **_k):
            raise RoadmapSeedStateError("corrupt seed-state.json")

        def _boom_create(*_a, **_k):  # pragma: no cover - must not be reached
            raise AssertionError("create_plan must not run past a malformed seed state")

        monkeypatch.setattr(authoring, "locate_tracked_seed", _boom)
        monkeypatch.setattr(authoring, "create_plan", _boom_create)
        rc = main(
            tmp_repo.argv("create", "demo", "--from-existing", str(source), "--yes")
        )
        assert rc == 2

    def test_main_create_retained_artifact_keeps_branch_binding(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import shutil

        import plan_tool.cli.authoring as authoring
        from plan_tool.branch_binding import all_bindings
        from plan_tool.create import CreateError, _CreatedArtifact

        shutil.rmtree(tmp_repo.root / ".git")
        _init_git_repo(tmp_repo.root)
        _enable_branch_awareness_config(tmp_repo.root)
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")
        invocation = _checked_out_branch(tmp_repo.root)
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", invocation)
        _make_branch(tmp_repo.root, "plan/demo")
        retained = tmp_repo.plans_dir / "1-demo.md"

        def _fail_after_write(slug, **kw):
            raise CreateError(
                "target write failed",
                artifact=_CreatedArtifact(retained, registered=False, parse_valid=False),
            )

        monkeypatch.setattr(authoring, "create_plan", _fail_after_write)
        rc = main(tmp_repo.argv("create", "demo", "--from", "an idea", "--yes"))
        assert rc == 1
        assert all_bindings(tmp_repo.root)["demo"] == "plan/demo-2"
        assert _checked_out_branch(tmp_repo.root) == "plan/demo-2"

    def test_main_create_postwrite_interrupt_keeps_branch_binding(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import shutil

        import plan_tool.cli.authoring as authoring
        from plan_tool.branch_binding import all_bindings
        from plan_tool.create import _CreatedArtifact, _CreateInterrupted

        shutil.rmtree(tmp_repo.root / ".git")
        _init_git_repo(tmp_repo.root)
        _enable_branch_awareness_config(tmp_repo.root)
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")
        invocation = _checked_out_branch(tmp_repo.root)
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", invocation)
        _make_branch(tmp_repo.root, "plan/demo")
        retained = tmp_repo.plans_dir / "1-demo.md"

        def _interrupt_after_write(slug, **kw):
            raise _CreateInterrupted(
                _CreatedArtifact(retained, registered=False, parse_valid=True)
            )

        monkeypatch.setattr(authoring, "create_plan", _interrupt_after_write)
        with pytest.raises(SystemExit) as exc_info:
            main(tmp_repo.argv("create", "demo", "--from", "an idea", "--yes"))
        assert exc_info.value.code == 130
        assert all_bindings(tmp_repo.root)["demo"] == "plan/demo-2"
        assert _checked_out_branch(tmp_repo.root) == "plan/demo-2"

def _write_created_plan(
    repo,
    *,
    slug: str = "demo",
    priority: str = "low",
    risk_profile: str | None = "standard",
) -> Path:
    declaration = ""
    if risk_profile is not None:
        declaration = (
            f"risk_profile: {risk_profile}\n"
            "risk_profile_rationale: explicitly declared for this test\n"
        )
    plan_path = repo.plans_dir / f"1-{slug}.md"
    plan_path.write_text(
        "---\n"
        "title: Demo Plan\n"
        "status: planning\n"
        f"priority: {priority}\n"
        f"{declaration}"
        "steps:\n"
        "  - id: 1\n"
        "    title: Only step\n"
        "---\n"
        "# Body\n",
        encoding="utf-8",
    )
    return plan_path


class TestCreateRiskProfileSummary:
    @pytest.mark.parametrize("risk_profile", ["low", "standard", "high"])
    def test_create_completion_summary_reports_persisted_risk_tier(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        risk_profile: str,
    ) -> None:
        import plan_tool.cli.authoring as authoring

        def fake_create_plan(slug, **kwargs):
            plan_path = _write_created_plan(
                tmp_repo, slug=slug, risk_profile=risk_profile
            )
            return CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
            )

        monkeypatch.setattr(authoring, "create_plan", fake_create_plan)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from", "an idea", "--no-iterate", "--yes"
            )
        )
        assert rc == 0
        assert f"saved risk tier: {risk_profile}" in capsys.readouterr().out

    def test_create_completion_summary_uses_saved_tier_not_plan_priority(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import plan_tool.cli.authoring as authoring

        def fake_create_plan(slug, **kwargs):
            plan_path = _write_created_plan(
                tmp_repo, slug=slug, priority="low", risk_profile="standard"
            )
            return CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
            )

        monkeypatch.setattr(authoring, "create_plan", fake_create_plan)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from", "an idea", "--no-iterate", "--yes"
            )
        )
        assert rc == 0
        output = capsys.readouterr().out
        assert "saved risk tier: standard" in output
        assert "saved risk tier: low" not in output

    def test_create_completion_summary_read_failure_warns_without_rollback(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import shutil

        import plan_tool.cli.authoring as authoring
        from plan_tool.branch_binding import all_bindings

        shutil.rmtree(tmp_repo.root / ".git")
        _init_git_repo(tmp_repo.root)
        _enable_branch_awareness_config(tmp_repo.root)
        seed_path = tmp_repo.root / "seed.md"
        seed_path.write_text(
            "an idea\n\n## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        _git_commit_all(tmp_repo.root, "init")
        invocation = _checked_out_branch(tmp_repo.root)
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", invocation)
        _make_branch(tmp_repo.root, "plan/demo")

        def fake_create_plan(slug, **kwargs):
            plan_path = _write_created_plan(tmp_repo, slug=slug)
            return CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                file_backed_route=FileBackedSourceRoute.DIRECT,
            )

        def unreadable_plan(_path):
            raise OSError("simulated persisted-plan read failure")

        monkeypatch.setattr(authoring, "create_plan", fake_create_plan)
        monkeypatch.setattr(authoring, "parse_plan", unreadable_plan)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(seed_path),
                "--no-iterate", "--yes"
            )
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "could not confirm saved risk tier" in captured.err
        assert "plan-tool detail demo" in captured.err
        assert (tmp_repo.root / "archive" / "seed.replaced.md").is_file()
        assert all_bindings(tmp_repo.root)["demo"] == "plan/demo-2"
        assert _checked_out_branch(tmp_repo.root) == "plan/demo-2"

    def test_create_completion_summary_missing_declaration_warns_without_fallback(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import plan_tool.cli.authoring as authoring

        def fake_create_plan(slug, **kwargs):
            plan_path = _write_created_plan(
                tmp_repo, slug=slug, risk_profile=None
            )
            return CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
            )

        monkeypatch.setattr(authoring, "create_plan", fake_create_plan)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from", "an idea", "--no-iterate", "--yes"
            )
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "could not confirm saved risk tier" in captured.err
        assert "saved risk tier:" not in captured.out
        assert "plan-tool detail demo" in captured.err


class TestCreateRecoveryCommandBoundaries:
    @pytest.mark.parametrize(
        ("parse_valid", "expected_recovery"),
        [
            (True, "parse-valid but unregistered"),
            (False, "invalid and unregistered"),
        ],
    )
    def test_created_artifact_failure_reports_its_recovery_state_and_skips_success_tail(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        parse_valid: bool,
        expected_recovery: str,
    ) -> None:
        """Name valid adoption and invalid repair as different operator choices."""
        import plan_tool.cli.authoring as authoring
        from plan_tool.create import _CreatedArtifact, _created_artifact_error

        retained = tmp_repo.plans_dir / "1-demo.md"
        retained.write_text("retained\n", encoding="utf-8")

        def fail_after_target_write(_slug: str, **_kwargs: object) -> CreateResult:
            raise _created_artifact_error(
                "target write stopped",
                _CreatedArtifact(retained, registered=False, parse_valid=parse_valid),
            )

        monkeypatch.setattr(authoring, "create_plan", fail_after_target_write)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from", "an idea", "--no-iterate", "--yes"
            )
        )

        captured = capsys.readouterr()
        assert rc == 1
        assert str(retained) in captured.err
        assert expected_recovery in captured.err
        assert "created plans/1-demo.md" not in captured.out

    def test_valid_retained_plan_can_be_registered_explicitly(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Adopt an unchanged parse-valid retained plan only through register."""
        retained = _write_created_plan(tmp_repo, slug="retained")
        retained_bytes = retained.read_bytes()

        rc = main(tmp_repo.argv("register", str(retained)))

        assert rc == 0
        assert retained.read_bytes() == retained_bytes
        assert json.loads(tmp_repo.manifest_path.read_text(encoding="utf-8")) == {
            "plans": ["plans/1-retained.md"]
        }
        assert "registered plans/1-retained.md" in capsys.readouterr().out

    def test_invalid_retained_plan_is_rejected_by_explicit_registration(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Require repair or removal before an interrupted stub can be adopted."""
        retained = tmp_repo.plans_dir / "1-retained.md"
        retained.write_text(
            "---\ncreate_in_progress: true\n---\n# Incomplete\n",
            encoding="utf-8",
        )

        rc = main(tmp_repo.argv("register", str(retained)))

        assert rc == 1
        assert retained.is_file()
        assert json.loads(tmp_repo.manifest_path.read_text(encoding="utf-8")) == {
            "plans": []
        }
        assert "is not a valid structured plan" in capsys.readouterr().err

    def test_registered_finalization_error_skips_success_summary_and_source_archive(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Keep source archival behind a completed create, not manifest registration."""
        import plan_tool.cli.authoring as authoring
        from plan_tool.create import _CreatedArtifact, _created_artifact_error

        source = tmp_repo.root / "seed.md"
        source.write_text(
            "recoverable source\n\n## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        retained = _write_created_plan(tmp_repo, slug="demo")

        def fail_after_registration(_slug: str, **_kwargs: object) -> CreateResult:
            raise _created_artifact_error(
                "finalization stopped",
                _CreatedArtifact(retained, registered=True, parse_valid=True),
            )

        monkeypatch.setattr(authoring, "create_plan", fail_after_registration)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source), "--no-iterate", "--yes"
            )
        )

        captured = capsys.readouterr()
        assert rc == 1
        assert source.is_file()
        assert not (tmp_repo.root / "archive").exists()
        assert "registered but finalization is incomplete" in captured.err
        assert "created plans/1-demo.md" not in captured.out

    def test_iteration_incomplete_still_runs_completed_create_tail(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Treat an iteration-stage failure as a completed registered create."""
        import plan_tool.cli.authoring as authoring

        source = tmp_repo.root / "seed.md"
        source.write_text(
            "recoverable source\n\n## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )

        def completed_with_iteration_failure(slug: str, **_kwargs: object) -> CreateResult:
            plan_path = _write_created_plan(tmp_repo, slug=slug)
            return CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=True,
                distilled_seed="## Overview\n\nNormalized recovery payload.\n",
                iteration_stage_failure=(
                    "reference research failed in iteration 1 "
                    "(terminal unparseable response)"
                ),
                file_backed_route=FileBackedSourceRoute.NORMALIZED,
            )

        monkeypatch.setattr(authoring, "create_plan", completed_with_iteration_failure)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source), "--no-iterate", "--yes"
            )
        )

        assert rc == 0
        assert source.is_file()
        assert not (tmp_repo.root / "archive").exists()
        captured = capsys.readouterr()
        assert "created plans/1-demo.md (route: normalized)" in captured.out
        assert "plan-tool completeness-audit demo --iterate" in captured.err

    def test_main_create_retained_artifact_keeps_branch_binding(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import shutil

        import plan_tool.cli.authoring as authoring
        from plan_tool.branch_binding import all_bindings
        from plan_tool.create import CreateError, _CreatedArtifact

        shutil.rmtree(tmp_repo.root / ".git")
        _init_git_repo(tmp_repo.root)
        _enable_branch_awareness_config(tmp_repo.root)
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")
        invocation = _checked_out_branch(tmp_repo.root)
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", invocation)
        _make_branch(tmp_repo.root, "plan/demo")
        retained = tmp_repo.plans_dir / "1-demo.md"

        def _fail_after_write(slug, **kw):
            raise CreateError(
                "target write failed",
                artifact=_CreatedArtifact(retained, registered=False, parse_valid=False),
            )

        monkeypatch.setattr(authoring, "create_plan", _fail_after_write)
        rc = main(tmp_repo.argv("create", "demo", "--from", "an idea", "--yes"))
        assert rc == 1
        assert all_bindings(tmp_repo.root)["demo"] == "plan/demo-2"
        assert _checked_out_branch(tmp_repo.root) == "plan/demo-2"

    def test_main_create_postwrite_interrupt_keeps_branch_binding(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import shutil

        import plan_tool.cli.authoring as authoring
        from plan_tool.branch_binding import all_bindings
        from plan_tool.create import _CreatedArtifact, _CreateInterrupted

        shutil.rmtree(tmp_repo.root / ".git")
        _init_git_repo(tmp_repo.root)
        _enable_branch_awareness_config(tmp_repo.root)
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")
        invocation = _checked_out_branch(tmp_repo.root)
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", invocation)
        _make_branch(tmp_repo.root, "plan/demo")
        retained = tmp_repo.plans_dir / "1-demo.md"

        def _interrupt_after_write(slug, **kw):
            raise _CreateInterrupted(
                _CreatedArtifact(retained, registered=False, parse_valid=True)
            )

        monkeypatch.setattr(authoring, "create_plan", _interrupt_after_write)
        with pytest.raises(SystemExit) as exc_info:
            main(tmp_repo.argv("create", "demo", "--from", "an idea", "--yes"))
        assert exc_info.value.code == 130
        assert all_bindings(tmp_repo.root)["demo"] == "plan/demo-2"
        assert _checked_out_branch(tmp_repo.root) == "plan/demo-2"

def _write_created_plan(
    repo,
    *,
    slug: str = "demo",
    priority: str = "low",
    risk_profile: str | None = "standard",
) -> Path:
    declaration = ""
    if risk_profile is not None:
        declaration = (
            f"risk_profile: {risk_profile}\n"
            "risk_profile_rationale: explicitly declared for this test\n"
        )
    plan_path = repo.plans_dir / f"1-{slug}.md"
    plan_path.write_text(
        "---\n"
        "title: Demo Plan\n"
        "status: planning\n"
        f"priority: {priority}\n"
        f"{declaration}"
        "steps:\n"
        "  - id: 1\n"
        "    title: Only step\n"
        "---\n"
        "# Body\n",
        encoding="utf-8",
    )
    return plan_path


class TestCreateRiskProfileSummary:
    @pytest.mark.parametrize("risk_profile", ["low", "standard", "high"])
    def test_create_completion_summary_reports_persisted_risk_tier(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        risk_profile: str,
    ) -> None:
        import plan_tool.cli.authoring as authoring

        def fake_create_plan(slug, **kwargs):
            plan_path = _write_created_plan(
                tmp_repo, slug=slug, risk_profile=risk_profile
            )
            return CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
            )

        monkeypatch.setattr(authoring, "create_plan", fake_create_plan)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from", "an idea", "--no-iterate", "--yes"
            )
        )
        assert rc == 0
        assert f"saved risk tier: {risk_profile}" in capsys.readouterr().out

    def test_create_completion_summary_uses_saved_tier_not_plan_priority(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import plan_tool.cli.authoring as authoring

        def fake_create_plan(slug, **kwargs):
            plan_path = _write_created_plan(
                tmp_repo, slug=slug, priority="low", risk_profile="standard"
            )
            return CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
            )

        monkeypatch.setattr(authoring, "create_plan", fake_create_plan)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from", "an idea", "--no-iterate", "--yes"
            )
        )
        assert rc == 0
        output = capsys.readouterr().out
        assert "saved risk tier: standard" in output
        assert "saved risk tier: low" not in output

    def test_create_completion_summary_read_failure_warns_without_rollback(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import shutil

        import plan_tool.cli.authoring as authoring
        from plan_tool.branch_binding import all_bindings

        shutil.rmtree(tmp_repo.root / ".git")
        _init_git_repo(tmp_repo.root)
        _enable_branch_awareness_config(tmp_repo.root)
        seed_path = tmp_repo.root / "seed.md"
        seed_path.write_text(
            "an idea\n\n## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        _git_commit_all(tmp_repo.root, "init")
        invocation = _checked_out_branch(tmp_repo.root)
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", invocation)
        _make_branch(tmp_repo.root, "plan/demo")

        def fake_create_plan(slug, **kwargs):
            plan_path = _write_created_plan(tmp_repo, slug=slug)
            return CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                file_backed_route=FileBackedSourceRoute.DIRECT,
            )

        def unreadable_plan(_path):
            raise OSError("simulated persisted-plan read failure")

        monkeypatch.setattr(authoring, "create_plan", fake_create_plan)
        monkeypatch.setattr(authoring, "parse_plan", unreadable_plan)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(seed_path),
                "--no-iterate", "--yes"
            )
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "could not confirm saved risk tier" in captured.err
        assert "plan-tool detail demo" in captured.err
        assert (tmp_repo.root / "archive" / "seed.replaced.md").is_file()
        assert all_bindings(tmp_repo.root)["demo"] == "plan/demo-2"
        assert _checked_out_branch(tmp_repo.root) == "plan/demo-2"

    def test_create_completion_summary_missing_declaration_warns_without_fallback(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import plan_tool.cli.authoring as authoring

        def fake_create_plan(slug, **kwargs):
            plan_path = _write_created_plan(
                tmp_repo, slug=slug, risk_profile=None
            )
            return CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
            )

        monkeypatch.setattr(authoring, "create_plan", fake_create_plan)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from", "an idea", "--no-iterate", "--yes"
            )
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "could not confirm saved risk tier" in captured.err
        assert "saved risk tier:" not in captured.out
        assert "plan-tool detail demo" in captured.err


class TestCreateRecoveryCommandBoundaries:
    @pytest.mark.parametrize(
        ("parse_valid", "expected_recovery"),
        [
            (True, "parse-valid but unregistered"),
            (False, "invalid and unregistered"),
        ],
    )
    def test_created_artifact_failure_reports_its_recovery_state_and_skips_success_tail(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        parse_valid: bool,
        expected_recovery: str,
    ) -> None:
        """Name valid adoption and invalid repair as different operator choices."""
        import plan_tool.cli.authoring as authoring
        from plan_tool.create import _CreatedArtifact, _created_artifact_error

        retained = tmp_repo.plans_dir / "1-demo.md"
        retained.write_text("retained\n", encoding="utf-8")

        def fail_after_target_write(_slug: str, **_kwargs: object) -> CreateResult:
            raise _created_artifact_error(
                "target write stopped",
                _CreatedArtifact(retained, registered=False, parse_valid=parse_valid),
            )

        monkeypatch.setattr(authoring, "create_plan", fail_after_target_write)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from", "an idea", "--no-iterate", "--yes"
            )
        )

        captured = capsys.readouterr()
        assert rc == 1
        assert str(retained) in captured.err
        assert expected_recovery in captured.err
        assert "created plans/1-demo.md" not in captured.out

    def test_valid_retained_plan_can_be_registered_explicitly(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Adopt an unchanged parse-valid retained plan only through register."""
        retained = _write_created_plan(tmp_repo, slug="retained")
        retained_bytes = retained.read_bytes()

        rc = main(tmp_repo.argv("register", str(retained)))

        assert rc == 0
        assert retained.read_bytes() == retained_bytes
        assert json.loads(tmp_repo.manifest_path.read_text(encoding="utf-8")) == {
            "plans": ["plans/1-retained.md"]
        }
        assert "registered plans/1-retained.md" in capsys.readouterr().out

    def test_invalid_retained_plan_is_rejected_by_explicit_registration(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Require repair or removal before an interrupted stub can be adopted."""
        retained = tmp_repo.plans_dir / "1-retained.md"
        retained.write_text(
            "---\ncreate_in_progress: true\n---\n# Incomplete\n",
            encoding="utf-8",
        )

        rc = main(tmp_repo.argv("register", str(retained)))

        assert rc == 1
        assert retained.is_file()
        assert json.loads(tmp_repo.manifest_path.read_text(encoding="utf-8")) == {
            "plans": []
        }
        assert "is not a valid structured plan" in capsys.readouterr().err

    def test_registered_finalization_error_skips_success_summary_and_source_archive(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Keep source archival behind a completed create, not manifest registration."""
        import plan_tool.cli.authoring as authoring
        from plan_tool.create import _CreatedArtifact, _created_artifact_error

        source = tmp_repo.root / "seed.md"
        source.write_text(
            "recoverable source\n\n## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        retained = _write_created_plan(tmp_repo, slug="demo")

        def fail_after_registration(_slug: str, **_kwargs: object) -> CreateResult:
            raise _created_artifact_error(
                "finalization stopped",
                _CreatedArtifact(retained, registered=True, parse_valid=True),
            )

        monkeypatch.setattr(authoring, "create_plan", fail_after_registration)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source), "--no-iterate", "--yes"
            )
        )

        captured = capsys.readouterr()
        assert rc == 1
        assert source.is_file()
        assert not (tmp_repo.root / "archive").exists()
        assert "registered but finalization is incomplete" in captured.err
        assert "created plans/1-demo.md" not in captured.out

    def test_iteration_incomplete_still_runs_completed_create_tail(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Treat an iteration-stage failure as a completed registered create."""
        import plan_tool.cli.authoring as authoring

        source = tmp_repo.root / "seed.md"
        source.write_text(
            "recoverable source\n\n## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )

        def completed_with_iteration_failure(slug: str, **_kwargs: object) -> CreateResult:
            plan_path = _write_created_plan(tmp_repo, slug=slug)
            return CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=True,
                distilled_seed="## Overview\n\nNormalized recovery payload.\n",
                iteration_stage_failure=(
                    "reference research failed in iteration 1 "
                    "(terminal unparseable response)"
                ),
                file_backed_route=FileBackedSourceRoute.NORMALIZED,
            )

        monkeypatch.setattr(authoring, "create_plan", completed_with_iteration_failure)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from-existing", str(source), "--no-iterate", "--yes"
            )
        )

        assert rc == 0
        assert source.is_file()
        assert not (tmp_repo.root / "archive").exists()
        captured = capsys.readouterr()
        assert "created plans/1-demo.md (route: normalized)" in captured.out
        assert "plan-tool completeness-audit demo --iterate" in captured.err


def _write_grounded_plan(repo) -> Path:
    """Write a minimal ``1-demo`` plan whose one step touches a real file.

    The referenced ``src.py`` exists, so ``compute_code_fingerprint``
    yields a non-empty map — the round-trip assertions then exercise a
    real digest rather than an empty one.
    """
    (repo.root / "src.py").write_text("print('hi')\n", encoding="utf-8")
    plan_path = repo.plans_dir / "1-demo.md"
    plan_path.write_text(
        "---\n"
        "title: Demo Plan\n"
        "status: planning\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: Only step\n"
        "    files:\n"
        "      - src.py\n"
        "---\n"
        "# Body\n",
        encoding="utf-8",
    )
    return plan_path


class TestStampGrounding:
    """``_stamp_grounding`` helper + the ``create`` / ``detail`` call sites.

    No claude is invoked — the ``create_plan`` / ``generate_detail``
    orchestrators are stubbed to write a plan/return a result on disk, and
    ``_stamp_grounding`` then runs for real against that plan with
    ``write_grounding`` / ``compute_*`` unstubbed.
    """

    # --- helper-level -----------------------------------------------------

    def test_stamp_grounding_writes_sidecar(self, tmp_repo) -> None:
        from plan_tool.grounding import grounding_path

        plan_path = _write_grounded_plan(tmp_repo)
        result = _stamp_grounding(plan_path, tmp_repo.root)
        assert result == grounding_path(plan_path)
        assert grounding_path(plan_path).is_file()

    def test_stamp_grounding_records_current_code_fingerprint(
        self, tmp_repo
    ) -> None:
        from plan_tool.fingerprint import compute_code_fingerprint
        from plan_tool.grounding import read_grounding
        from plan_tool.parser import parse_plan

        plan_path = _write_grounded_plan(tmp_repo)
        _stamp_grounding(plan_path, tmp_repo.root)
        expected = compute_code_fingerprint(
            parse_plan(plan_path), plan_path, tmp_repo.root
        )
        grounding = read_grounding(plan_path)
        assert grounding is not None
        assert grounding.code_fingerprint == expected
        assert expected  # the referenced src.py made the map non-empty

    def test_stamp_grounding_records_plan_digest(self, tmp_repo) -> None:
        from plan_tool.grounding import read_grounding
        from plan_tool.review_persistence import compute_plan_fingerprint

        plan_path = _write_grounded_plan(tmp_repo)
        _stamp_grounding(plan_path, tmp_repo.root)
        grounding = read_grounding(plan_path)
        assert grounding is not None
        assert grounding.plan_fingerprint == compute_plan_fingerprint(plan_path)

    def test_stamp_grounding_fail_soft_on_parse_error(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.grounding import grounding_path

        plan_path = _write_grounded_plan(tmp_repo)

        def boom(_path):
            raise ValueError("unparseable")

        monkeypatch.setattr("plan_tool.cli.authoring.parse_plan", boom)
        # Returns None, writes no sidecar, never raises, warns on stderr.
        assert _stamp_grounding(plan_path, tmp_repo.root) is None
        assert not grounding_path(plan_path).exists()
        assert "could not stamp grounding" in capsys.readouterr().err

    # --- per-step authoring fingerprint (BACKLOG #165) --------------------

    def _write_two_step_plan(self, repo, *, out_of_scope: str) -> Path:
        """Two steps, both already detailed on disk."""
        plan_path = repo.plans_dir / "1-demo.md"
        details_dir = repo.plans_dir / "plan-details" / "demo"
        details_dir.mkdir(parents=True, exist_ok=True)
        (details_dir / "01-step-one.md").write_text("# detail one\n", encoding="utf-8")
        (details_dir / "02-step-two.md").write_text("# detail two\n", encoding="utf-8")
        plan_path.write_text(
            "---\n"
            "title: Demo Plan\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Step one\n"
            "    detail: plans/plan-details/demo/01-step-one.md\n"
            "  - id: 2\n"
            "    title: Step two\n"
            "    detail: plans/plan-details/demo/02-step-two.md\n"
            "---\n"
            f"# Body\n\n## Out of scope\n\n{out_of_scope}\n",
            encoding="utf-8",
        )
        return plan_path

    def test_touched_step_ids_none_stamps_every_detailed_step(
        self, tmp_repo
    ) -> None:
        """The ``create`` call shape — no prior baseline to disturb, so a
        blanket first-bootstrap stamp is correct."""
        from plan_tool.grounding import read_grounding

        plan_path = self._write_two_step_plan(tmp_repo, out_of_scope="none")
        _stamp_grounding(plan_path, tmp_repo.root, touched_step_ids=None)
        g = read_grounding(plan_path)
        assert g is not None
        assert set(g.step_authoring_fingerprints) == {"1", "2"}

    def test_touched_step_ids_preserves_untouched_siblings(
        self, tmp_repo
    ) -> None:
        """The load-bearing case a naive blanket-restamp would break: after
        a plan narrowing, re-running ``detail`` for step 2 only must not
        silently re-baseline step 1 against the *new* scope — that would
        erase exactly the staleness signal BACKLOG #165 exists to record."""
        from plan_tool.grounding import read_grounding, stale_detail_steps
        from plan_tool.parser import parse_plan

        plan_path = self._write_two_step_plan(
            tmp_repo, out_of_scope="Skip auth."
        )
        # Both steps detailed against the original (wide) scope.
        _stamp_grounding(plan_path, tmp_repo.root, touched_step_ids=None)
        baseline = read_grounding(plan_path)
        assert baseline is not None
        step_1_fp_before = baseline.step_authoring_fingerprints["1"]

        # The plan narrows — step 1's detail is now stale relative to it.
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8").replace(
                "Skip auth.", "Skip auth and retries."
            ),
            encoding="utf-8",
        )

        # Only step 2 gets re-authored/re-stamped (mirrors the CLI's
        # ``touched_step_ids={step_id for step_id, _ in wrote}``).
        _stamp_grounding(plan_path, tmp_repo.root, touched_step_ids={2})

        after = read_grounding(plan_path)
        assert after is not None
        # Step 1's fingerprint is untouched by the restamp...
        assert after.step_authoring_fingerprints["1"] == step_1_fp_before
        # ...so it still compares stale against the narrowed plan.
        assert stale_detail_steps(after, parse_plan(plan_path), plan_path) == [1]
        # Step 2 (the one actually touched) is freshly baselined and clean.
        assert 2 not in stale_detail_steps(
            after, parse_plan(plan_path), plan_path
        )

    def test_touched_step_ids_drops_a_step_whose_detail_vanished(
        self, tmp_repo
    ) -> None:
        from plan_tool.grounding import read_grounding

        plan_path = self._write_two_step_plan(tmp_repo, out_of_scope="none")
        _stamp_grounding(plan_path, tmp_repo.root, touched_step_ids=None)
        (tmp_repo.plans_dir / "plan-details" / "demo" / "02-step-two.md").unlink()

        _stamp_grounding(plan_path, tmp_repo.root, touched_step_ids={2})

        g = read_grounding(plan_path)
        assert g is not None
        assert "2" not in g.step_authoring_fingerprints
        assert "1" in g.step_authoring_fingerprints  # untouched, preserved

    # --- create call site -------------------------------------------------

    def test_main_create_stamps_grounding(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.grounding import grounding_path

        plan_path = tmp_repo.plans_dir / "1-demo.md"

        def fake_create_plan(slug, **kwargs):
            _write_grounded_plan(tmp_repo)
            return CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
            )

        monkeypatch.setattr(
            "plan_tool.cli.authoring.create_plan", fake_create_plan
        )
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from", "an idea", "--no-iterate", "--yes"
            )
        )
        assert rc == 0
        assert grounding_path(plan_path).is_file()

    def test_created_plan_routes_to_fresh_bare_audit(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import plan_tool.cli.authoring as authoring

        plan_path = tmp_repo.plans_dir / "1-demo.md"

        def fake_create_plan(slug, **kwargs):
            _write_grounded_plan(tmp_repo)
            return CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
            )

        monkeypatch.setattr(authoring, "create_plan", fake_create_plan)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from", "an idea", "--no-iterate", "--yes"
            )
        )
        assert rc == 0
        err = capsys.readouterr().err
        assert "no current qualified audit result exists" in err
        assert "plan-tool completeness-audit demo" in err
        assert err.index("plan-tool completeness-audit demo") < err.index(
            "plan-tool detail demo"
        )

    def test_main_create_split_proposal_does_not_stamp(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.grounding import grounding_path

        plan_path = tmp_repo.plans_dir / "1-demo.md"

        def fake_create_plan(slug, **kwargs):
            return CreateResult(
                plan_path=None,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                split_proposal=_proposal(),
                file_backed_route=FileBackedSourceRoute.SPLIT,
            )

        monkeypatch.setattr(
            "plan_tool.cli.authoring.create_plan", fake_create_plan
        )
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from", "an idea", "--no-iterate", "--yes"
            )
        )
        assert rc == 0
        # No plan was written, so no grounding sidecar exists anywhere.
        assert not grounding_path(plan_path).exists()
        assert "saved risk tier:" not in capsys.readouterr().out

    def test_main_create_failure_does_not_stamp(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.create import CreateError
        from plan_tool.grounding import grounding_path

        plan_path = tmp_repo.plans_dir / "1-demo.md"

        def boom(slug, **kwargs):
            raise CreateError("nope")

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", boom)
        rc = main(
            tmp_repo.argv(
                "create", "demo", "--from", "an idea", "--no-iterate", "--yes"
            )
        )
        assert rc == 1
        assert not grounding_path(plan_path).exists()

    # --- detail call site -------------------------------------------------

    def _detail_argv(self, repo, *extra: str) -> list[str]:
        return repo.argv(
            "detail", "demo", "--no-iterate", "--no-completeness", *extra
        )

    def test_main_detail_stamps_grounding(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.detail import DetailResult
        from plan_tool.grounding import grounding_path

        plan_path = registered_plan.plans_dir / "1-demo.md"

        def fake_generate_detail(path, **kwargs):
            return [
                DetailResult(
                    step_id=1,
                    output_path=path.parent / "detail-1.md",
                    written=True,
                )
            ]

        monkeypatch.setattr(
            "plan_tool.cli.authoring.generate_detail", fake_generate_detail
        )
        rc = main(self._detail_argv(registered_plan))
        assert rc == 0
        assert grounding_path(plan_path).is_file()

    def test_main_detail_skipped_only_does_not_stamp(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.detail import DetailResult
        from plan_tool.grounding import grounding_path

        plan_path = registered_plan.plans_dir / "1-demo.md"

        def fake_generate_detail(path, **kwargs):
            return [
                DetailResult(
                    step_id=1,
                    output_path=path.parent / "detail-1.md",
                    written=False,
                    skipped_reason="already exists",
                )
            ]

        monkeypatch.setattr(
            "plan_tool.cli.authoring.generate_detail", fake_generate_detail
        )
        rc = main(self._detail_argv(registered_plan))
        assert rc == 0
        assert not grounding_path(plan_path).exists()

    def test_main_detail_dry_run_does_not_stamp(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.detail import DetailResult
        from plan_tool.grounding import grounding_path

        plan_path = registered_plan.plans_dir / "1-demo.md"

        def fake_generate_detail(path, **kwargs):
            return [
                DetailResult(
                    step_id=1,
                    output_path=path.parent / "detail-1.md",
                    written=False,
                    prompt="rendered prompt",
                )
            ]

        monkeypatch.setattr(
            "plan_tool.cli.authoring.generate_detail", fake_generate_detail
        )
        rc = main(self._detail_argv(registered_plan, "--dry-run"))
        assert rc == 0
        assert not grounding_path(plan_path).exists()


# --------------------------------------------------------------------------
# Detail authoring selector removal
# --------------------------------------------------------------------------
#
# Argparse rejects retired selectors before authoring starts.


@pytest.mark.integration
class TestDetailSelectorRemoval:
    @staticmethod
    def _patch_capture(monkeypatch: pytest.MonkeyPatch) -> dict:
        """Record the selector-free generator contract."""
        import plan_tool.cli.authoring as authoring

        calls: dict = {}

        def fake_generate_detail(plan_path, **kwargs):
            calls["called"] = True
            calls["kwargs"] = kwargs
            return []

        monkeypatch.setattr(authoring, "generate_detail", fake_generate_detail)
        return calls

    def test_default_grade_is_run(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls = self._patch_capture(monkeypatch)
        rc = main(registered_plan.argv("detail", "demo"))
        assert rc == 0
        assert "grade" not in calls["kwargs"]

    @pytest.mark.parametrize(
        "extra_args",
        [
            (),
            ("--force", "--dry-run", "--step", "1", "--no-resume"),
            ("--detail-only",),
            ("--detail-only", "--no-completeness"),
            ("--all",),
            ("--reconcile", "--all"),
            ("--reconcile", "--dry-run"),
            ("--jobs", "4", "--iterate"),
            ("--jobs", "4", "--no-iterate"),
            ("--lessons", "--no-iterate"),
            ("--commit",),
        ],
    )
    def test_detail_rejects_removed_grade_selector(
        self,
        extra_args: tuple[str, ...],
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import plan_tool.cli.authoring as authoring

        calls = self._patch_capture(monkeypatch)
        monkeypatch.setattr(
            authoring,
            "_load_context",
            lambda _args: pytest.fail("Jira-grade refusal must precede context loading"),
        )
        with pytest.raises(SystemExit) as exc:
            main(registered_plan.argv(
                "detail", "missing-plan", "--grade", "jira", *extra_args
            ))
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "unrecognized arguments: --grade jira" in err
        assert "called" not in calls
        assert not (registered_plan.root / ".plan-tool" / "runs").exists()

    def test_detail_without_grade_keeps_run_grade_generator_contract(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult

        tail_calls: list[int] = []

        def fake_generate_detail(plan_path, **kwargs):
            assert "grade" not in kwargs
            written = Path(plan_path).parent / "detail.md"
            written.write_text("x\n", encoding="utf-8")
            return [
                DetailResult(step_id=1, output_path=written, written=True)
            ]

        def fake_tail(*_args, **_kwargs):
            tail_calls.append(1)
            return []

        monkeypatch.setattr(authoring, "generate_detail", fake_generate_detail)
        monkeypatch.setattr(authoring, "_run_completeness_tail", fake_tail)
        rc = main(registered_plan.argv("detail", "demo"))
        assert rc == 0
        assert tail_calls == [1]


def _write_tracked_draft(
    tmp_path: Path,
    *,
    status: str = "current",
    recorded_text: str | None = None,
    publish: bool = True,
    head_has_plan_row: bool = True,
) -> Path:
    """Write a tracked draft seed whose roadmap is published as an accepted root."""
    from tests.roadmap_accepted_fixtures import publish_accepted_root, with_minimal_upstream

    plans_dir = tmp_path / "custom-plans"
    slug = "demo"
    plan = PlanRow(
        id="slice",
        title="Slice",
        disposition=PlanDisposition.KEEP,
        component_ids=("component-a",),
        draft_seed_path="plan-seed-drafts/slice.md",
        sizing_rationale="Keeps one bounded concern together.",
    )
    artifact = PlansArtifact(
        plans=(plan,) if head_has_plan_row else (),
        ordering=(),
        assumptions=(),
        decisions=(),
        body="# Roadmap\n",
    )
    root = roadmap_dir(plans_dir, slug)
    root.mkdir(parents=True)
    if publish:
        publish_accepted_root(
            plans_dir, slug, with_minimal_upstream(render_plans_artifact(artifact))
        )
    text = (
        "---\nroadmap_components:\n  - component-a\n---\n# Seed\n\n"
        "## Risks\n\n- A risk the accepted roadmap already states.\n\n"
        "## References\n\n"
        f"- `{DOMAIN_FILENAME}`\n"
        f"- `{CONSTRAINTS_FILENAME}`\n"
        f"- `{COMPONENTS_FILENAME}`\n"
        f"- `{PLANS_FILENAME}`\n"
    )
    source = root / plan.draft_seed_path
    source.parent.mkdir()
    source.write_text(text, encoding="utf-8")
    state = empty_seed_state()
    state["seeds"][plan.id] = {
        "draft_seed_path": plan.draft_seed_path,
        "status": status,
        "digest": digest_text(recorded_text if recorded_text is not None else text),
        "published": False,
    }
    write_seed_state(seed_state_path(root), state)
    return source


class TestRoadmapSeedConfirmation:
    def test_current_classification_needs_no_confirmation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli.authoring import _confirm_invalidated_roadmap_seed

        source = _write_tracked_draft(tmp_path)
        monkeypatch.setattr("plan_tool.cli.authoring.sys.stdin.isatty", lambda: True)
        prompts: list[str] = []

        location = locate_tracked_seed(source, repo_root=tmp_path)
        assert location is not None
        assert _confirm_invalidated_roadmap_seed(
            location,
            yes=False,
            input_fn=lambda prompt: prompts.append(prompt) or "n",
        )
        assert prompts == []

    def test_stale_classification_uses_roadmap_revision_wording(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli.authoring import _confirm_invalidated_roadmap_seed

        source = _write_tracked_draft(tmp_path, status="invalidated")
        monkeypatch.setattr("plan_tool.cli.authoring.sys.stdin.isatty", lambda: True)
        prompts: list[str] = []

        location = locate_tracked_seed(source, repo_root=tmp_path)
        assert location is not None
        assert not _confirm_invalidated_roadmap_seed(
            location,
            yes=False,
            input_fn=lambda prompt: prompts.append(prompt) or "n",
        )
        assert "is invalidated by a roadmap revision" in prompts[0]

    def test_digest_mismatch_prompts_with_its_classification(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli.authoring import _confirm_invalidated_roadmap_seed

        source = _write_tracked_draft(tmp_path, recorded_text="# generated\n")
        monkeypatch.setattr("plan_tool.cli.authoring.sys.stdin.isatty", lambda: True)
        prompts: list[str] = []

        location = locate_tracked_seed(source, repo_root=tmp_path)
        assert location is not None
        assert not _confirm_invalidated_roadmap_seed(
            location,
            yes=False,
            input_fn=lambda prompt: prompts.append(prompt) or "n",
        )
        assert "classifies as 'digest-mismatched'" in prompts[0]

    def test_yes_bypasses_a_non_current_classification(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli.authoring import _confirm_invalidated_roadmap_seed

        source = _write_tracked_draft(tmp_path, recorded_text="# generated\n")
        monkeypatch.setattr("plan_tool.cli.authoring.sys.stdin.isatty", lambda: False)

        location = locate_tracked_seed(source, repo_root=tmp_path)
        assert location is not None
        assert _confirm_invalidated_roadmap_seed(
            location, yes=True, input_fn=lambda _prompt: "n"
        )

    def test_non_tty_refuses_a_non_current_classification(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli.authoring import _confirm_invalidated_roadmap_seed

        source = _write_tracked_draft(tmp_path, recorded_text="# generated\n")
        monkeypatch.setattr("plan_tool.cli.authoring.sys.stdin.isatty", lambda: False)

        location = locate_tracked_seed(source, repo_root=tmp_path)
        assert location is not None
        assert not _confirm_invalidated_roadmap_seed(
            location, yes=False, input_fn=lambda _prompt: "yes"
        )
        assert "digest-mismatched" in capsys.readouterr().err

    def test_plan_row_missing_from_accepted_head_refuses(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.cli.authoring import _confirm_invalidated_roadmap_seed

        source = _write_tracked_draft(tmp_path, head_has_plan_row=False)

        location = locate_tracked_seed(source, repo_root=tmp_path)
        assert location is not None
        assert not _confirm_invalidated_roadmap_seed(location, yes=True)
        assert "is no longer present in its roadmap" in capsys.readouterr().err

    def test_plan_row_present_only_in_stale_top_level_file_is_still_absent(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A leftover top-level 04-roadmap.md must not be consulted for the plan row."""
        from plan_tool.cli.authoring import _confirm_invalidated_roadmap_seed

        source = _write_tracked_draft(tmp_path, head_has_plan_row=False)
        stale_top_level = (
            roadmap_dir(tmp_path / "custom-plans", "demo") / PLANS_FILENAME
        )
        stale_top_level.write_text(
            render_plans_artifact(
                PlansArtifact(
                    plans=(
                        PlanRow(
                            id="slice",
                            title="Slice",
                            disposition=PlanDisposition.KEEP,
                            component_ids=("component-a",),
                            draft_seed_path="plan-seed-drafts/slice.md",
                            sizing_rationale="Keeps one bounded concern together.",
                        ),
                    ),
                    ordering=(),
                    assumptions=(),
                    decisions=(),
                    body="# Roadmap\n",
                )
            ),
            encoding="utf-8",
        )

        location = locate_tracked_seed(source, repo_root=tmp_path)
        assert location is not None
        assert not _confirm_invalidated_roadmap_seed(location, yes=True)
        assert "is no longer present in its roadmap" in capsys.readouterr().err

    def test_no_accepted_head_refuses_with_the_named_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.cli.authoring import _confirm_invalidated_roadmap_seed

        source = _write_tracked_draft(tmp_path, publish=False)

        location = locate_tracked_seed(source, repo_root=tmp_path)
        assert location is not None
        assert not _confirm_invalidated_roadmap_seed(location, yes=True)
        assert "has no published version" in capsys.readouterr().err

    def test_promoted_copy_validated_against_sidecar_while_row_read_from_head(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.cli.authoring import _confirm_invalidated_roadmap_seed

        source = _write_tracked_draft(tmp_path)
        plans_dir = tmp_path / "custom-plans"
        location = TrackedSeedLocation(
            plan_id="slice",
            roadmap_slug="demo",
            state_path=seed_state_path(roadmap_dir(plans_dir, "demo")),
            via_marker=True,
        )
        source.unlink()  # the draft is archived once its promotion lands

        assert _confirm_invalidated_roadmap_seed(location, yes=False)


@pytest.mark.integration
def test_cmd_create_from_existing_refuses_when_roadmap_has_no_accepted_head(
    tmp_repo, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import plan_tool.cli.authoring as authoring

    source = _write_tracked_draft(tmp_repo.root, publish=False)
    calls: list[object] = []
    monkeypatch.setattr(
        authoring, "create_plan", lambda *a, **kw: calls.append((a, kw))
    )

    rc = main(tmp_repo.argv("create", "demo", "--from-existing", str(source), "--yes"))

    assert rc == 2
    assert "has no published version" in capsys.readouterr().err
    assert calls == []


def test_tracked_seed_location_is_resolved_once_before_confirmation_and_create(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep confirmation and create pinned to the initially selected source."""
    import argparse

    from plan_tool.cli import authoring
    from plan_tool.roadmap_seed_state import TrackedSeedLocation

    source = tmp_path / "promoted-seed.md"
    source.write_text(
        "# Seed\n\n## References\n\n- [API](https://example.test/api)\n",
        encoding="utf-8",
    )
    location = TrackedSeedLocation(
        plan_id="original",
        roadmap_slug="original-roadmap",
        state_path=tmp_path / "plans" / "roadmaps" / "original-roadmap" / ".seed-state.json",
        via_marker=True,
    )
    locate_calls: list[Path] = []
    confirmed: list[TrackedSeedLocation | None] = []
    created: list[TrackedSeedLocation | None] = []

    def locate(path: Path, *, repo_root: Path) -> TrackedSeedLocation:
        assert repo_root == tmp_path
        locate_calls.append(path)
        return location

    def confirm(selected: TrackedSeedLocation | None, **_kwargs: object) -> bool:
        confirmed.append(selected)
        return True

    def create(_slug: str, **kwargs: object) -> CreateResult:
        created.append(kwargs["tracked_seed_location"])
        return CreateResult(
            plan_path=None,
            manifest_path=tmp_path / "manifest.json",
            manifest_updated=False,
            split_proposal=SplitProposal(entries=[]),
            file_backed_route=FileBackedSourceRoute.SPLIT,
        )

    class Logger:
        def run_end(self, **_kwargs: object) -> None:
            pass

    monkeypatch.setattr(authoring, "_resolve_cmd_repo_root", lambda _args: tmp_path)
    monkeypatch.setattr(authoring, "locate_tracked_seed", locate)
    monkeypatch.setattr(authoring, "_confirm_invalidated_roadmap_seed", confirm)
    monkeypatch.setattr(authoring, "_confirm_repo_root", lambda _root, **_kwargs: tmp_path)
    monkeypatch.setattr(authoring, "_create_branch_collision_gate", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(authoring, "create_plan", create)
    monkeypatch.setattr(authoring, "_emit_split_proposal", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(authoring.RunLogWriter, "start", lambda **_kwargs: Logger())

    args = argparse.Namespace(
        repo_root=tmp_path,
        reprocess=False,
        from_description=None,
        from_existing=source,
        yes=True,
        slug="selected",
        output_dir=tmp_path / "plans",
        manifest=None,
        no_resume=False,
        iterate=False,
        max_iterations=3,
        iteration_budget=60,
        max_stall_rounds=1,
        prompt_mode=None,
        experiment_arm=[],
        allow_drift=False,
        auto_reconcile_on_drift=True,
        collision_sidecar=True,
        triage=True,
        include_info=False,
        no_synthesize_body=False,
        no_fetch_docs=False,
        no_distill=True,
        no_skip_prose_reproposal=False,
    )

    assert authoring.cmd_create(args) == 0
    assert locate_calls == [source.resolve()]
    assert confirmed == [location]
    assert created == [location]


class TestWarnNormalizedArtifactWriteFailure:
    """Pins the commit-87539cfa fix: this warning must name a dangling
    symlink's own lexical link path, not the (missing) target
    ``_short_path``'s resolving helper would follow it to — regression
    coverage the fix itself shipped without."""

    def test_names_the_link_not_its_missing_resolved_target(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.cli import authoring

        link = tmp_path / "note.distilled.md"
        link.symlink_to(tmp_path / "missing.md")

        authoring._warn_normalized_artifact_write_failure(
            link, tmp_path, OSError("disk full")
        )

        err = capsys.readouterr().err
        assert "note.distilled.md" in err
        assert "missing.md" not in err


class TestAuthoringGuidanceNotCurrentVerdict:
    """A not-current tail result still lends its gap count and re-audit reason."""

    @staticmethod
    def _follow_up(verdict, *, moved=False):
        import plan_tool.cli.authoring as authoring

        return authoring._fresh_completeness_audit_follow_up(
            "demo", verdict=verdict,
            artifacts_moved=moved,
        )

    def test_authoring_guidance_not_current_names_verdict_reason_and_count(self) -> None:
        from plan_tool.completeness_report import (
            UNTRUSTED_PERSISTENT,
            blocking_verdict_from_gate,
        )

        _command, why = self._follow_up(
            blocking_verdict_from_gate(["a", "b"], untrusted_cause=UNTRUSTED_PERSISTENT)
        )
        assert "2 blocking gap(s) open" in why
        assert "re-auditing unchanged text reproduces this result" in why

    def test_set_verdict_whose_artifacts_moved_reads_as_stale_revision(self) -> None:
        from plan_tool.completeness_report import blocking_verdict_from_gate

        command, why = self._follow_up(
            blocking_verdict_from_gate(["a"]), moved=True
        )
        assert command == "plan-tool completeness-audit demo --iterate"
        assert "no current audit evidence" in why
        # The saved ids describe changed text: advisory, never counted as open.
        assert "blocking gap(s) open" not in why

    def test_set_verdict_not_proven_current_keeps_its_gaps_and_is_not_called_stale(
        self,
    ) -> None:
        """Deliberate: a tail that could not prove its result current (a
        missing or mismatched result) is not evidence the files moved. The
        gate completed on text that did not change, so its gaps stay named and
        no "changed text" claim is made."""
        from plan_tool.completeness_report import blocking_verdict_from_gate

        _command, why = self._follow_up(blocking_verdict_from_gate(["a"]))
        assert "1 blocking gap(s) open" in why
        assert "no current audit evidence" not in why

    def test_an_empty_set_not_proven_current_reads_as_the_fixed_fresh_row(
        self,
    ) -> None:
        from plan_tool.completeness_report import blocking_verdict_from_gate

        assert self._follow_up(blocking_verdict_from_gate([])) == (
            "plan-tool completeness-audit demo --iterate",
            "no current qualified audit result exists; run a fresh audit",
        )

    @pytest.mark.parametrize("cause", ["transient", "persistent"])
    def test_a_moved_tail_reads_stale_whatever_the_original_cause(
        self, cause
    ) -> None:
        """Deliberate: "re-auditing unchanged text reproduces this" and "the
        audit stopped early" are false once the files changed."""
        from plan_tool.completeness_report import blocking_verdict_from_gate

        _command, why = self._follow_up(
            blocking_verdict_from_gate(["a"], untrusted_cause=cause), moved=True
        )
        assert "no current audit evidence" in why
        assert "reproduces" not in why
        assert "stopped early" not in why

    @pytest.mark.parametrize(
        ("cause", "phrase"),
        [
            ("transient", "the audit stopped early"),
            ("persistent", "re-auditing unchanged text reproduces this result"),
        ],
    )
    def test_an_unmoved_tail_keeps_its_own_cause(self, cause, phrase) -> None:
        from plan_tool.completeness_report import blocking_verdict_from_gate

        _command, why = self._follow_up(
            blocking_verdict_from_gate(["a"], untrusted_cause=cause)
        )
        assert phrase in why

    def test_stale_revision_follow_up_counts_only_deterministic_blockers(
        self,
    ) -> None:
        """A stale-revision verdict reached from a finalize result keeps its
        deterministic blockers (they are recomputed each audit); a tail whose
        files then moved drops them (see the moved-tail test)."""
        from types import SimpleNamespace

        from plan_tool.completeness_report import blocking_verdict_from_gate

        blocker = SimpleNamespace(
            id="purity-1", source="purity-coverage", severity="high",
            title="Uncovered purity row", body="",
        )
        # Unmoved with its own stale cause: the blocker still counts.
        _command, why = self._follow_up(
            blocking_verdict_from_gate(
                ["a"], [blocker], untrusted_cause="stale-revision"
            )
        )
        assert "1 blocking gap(s) open" in why
        # Files moved after the tail: the blocker was computed on changed text.
        _command, moved_why = self._follow_up(
            blocking_verdict_from_gate(["a"], [blocker]), moved=True
        )
        assert "blocking gap(s) open" not in moved_why

    def test_bare_plan_label_survives_a_non_absent_verdict(self) -> None:
        """Keys not words: the bare-plan gate is named for every verdict state."""
        import plan_tool.cli.authoring as authoring
        from plan_tool.completeness_report import (
            UNTRUSTED_PERSISTENT,
            blocking_verdict_from_gate,
        )

        _command, why = authoring._fresh_completeness_audit_follow_up(
            "demo",
            bare_plan=True,
            verdict=blocking_verdict_from_gate(
                ["a"], untrusted_cause=UNTRUSTED_PERSISTENT
            ),
        )
        assert "(bare-plan audit)" in why

    def test_authoring_guidance_absent_verdict_keeps_fresh_audit_row(self) -> None:
        from plan_tool.completeness_report import ABSENT_BLOCKING_VERDICT

        assert self._follow_up(ABSENT_BLOCKING_VERDICT) == (
            "plan-tool completeness-audit demo --iterate",
            "no current qualified audit result exists; run a fresh audit",
        )


def _run_end_records(repo_root: Path, slug: str) -> list[dict]:
    return [
        record
        for log_path in (repo_root / ".plan-tool" / "runs" / slug).glob("*.jsonl")
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if (record := json.loads(line))["event"] == "run_end"
    ]


class TestAuthoringRunEndResult:
    """`create` / `detail` record what they wrote in `run_end.result`.

    A driver reads the plan path and archives from the run log instead of
    diffing `plans.json`; a run that writes nothing records explicit empties so
    "nothing written" is distinguishable from "field missing".
    """

    def test_create_result_names_plan_manifest_and_archives(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.cli.authoring as authoring

        plan_path = tmp_repo.add_plan("1-demo")
        archived = tmp_repo.root / "docs" / "implementation-plans" / "archive" / "old.md"
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda *_a, **_k: CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=True,
                replaced_archives=[(tmp_repo.root / "old.md", archived)],
            ),
        )

        assert main(tmp_repo.argv("create", "demo", "--from", "x", "--no-iterate", "--yes")) == 0

        (end,) = _run_end_records(tmp_repo.root, "demo")
        result = end["result"]
        assert (tmp_repo.root / result["plan_path"]).resolve() == plan_path.resolve()
        assert result["manifest_updated"] is True
        assert [Path(p).name for p in result["archived_paths"]] == ["old.md"]

    @pytest.mark.parametrize(
        "route", [FileBackedSourceRoute.SPLIT, FileBackedSourceRoute.REFUSED]
    )
    def test_create_without_a_plan_records_explicit_empties(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch, route: FileBackedSourceRoute
    ) -> None:
        """Keys, not absence: no-plan routes carry null/empty fields, not missing ones."""
        import plan_tool.cli.authoring as authoring

        source = tmp_repo.root / "seed.md"
        source.write_text("## References\n\n- [API](https://example.test/api)\n", encoding="utf-8")
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda *_a, **_k: CreateResult(
                plan_path=None,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                split_proposal=_proposal() if route is FileBackedSourceRoute.SPLIT else None,
                file_backed_route=route,
                refusal_reason="unsupported" if route is FileBackedSourceRoute.REFUSED else None,
            ),
        )

        main(tmp_repo.argv("create", "demo", "--from-existing", str(source), "--no-iterate", "--yes"))

        (end,) = _run_end_records(tmp_repo.root, "demo")
        assert end["result"] == {
            "plan_path": None,
            "manifest_updated": None,
            "archived_paths": [],
            "archived_paths_truncated": False,
        }

    @pytest.mark.parametrize(
        ("route", "expected"),
        [
            (FileBackedSourceRoute.DIRECT, {"seed.replaced.md"}),
            (
                FileBackedSourceRoute.NORMALIZED,
                {"seed.replaced.md", "seed.distilled.replaced.md"},
            ),
        ],
    )
    def test_create_result_records_source_and_normalized_archives(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        route: FileBackedSourceRoute,
        expected: set[str],
    ) -> None:
        """Every archive move lands in `archived_paths`: the raw source (direct)
        and both the normalized artifact and the source (normalized)."""
        import plan_tool.cli.authoring as authoring

        plan_path = tmp_repo.add_plan("1-demo")
        source = tmp_repo.root / "seed.md"
        source.write_text("## References\n\n- [API](https://example.test/api)\n", encoding="utf-8")
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda _slug, **_k: CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=False,
                distilled_seed="normalized text",
                file_backed_route=route,
            ),
        )

        assert main(
            tmp_repo.argv("create", "demo", "--from-existing", str(source), "--no-iterate", "--yes")
        ) == 0

        (end,) = _run_end_records(tmp_repo.root, "demo")
        paths = end["result"]["archived_paths"]
        assert {Path(p).name for p in paths} == expected
        # Repo-relative POSIX, as DATA_CONTRACT.md states.
        assert all(not Path(p).is_absolute() and "\\" not in p for p in paths)

    def test_retained_artifact_is_reported_not_lost_when_create_fails(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A plan left on disk and registered by a failed create is a written artifact."""
        import plan_tool.cli.authoring as authoring
        from plan_tool.create import CreateError, _CreatedArtifact

        plan_path = tmp_repo.add_plan("1-demo")

        def boom(*_a, **_k):
            raise CreateError(
                "finalization failed",
                artifact=_CreatedArtifact(path=plan_path, registered=True, parse_valid=True),
            )

        monkeypatch.setattr(authoring, "create_plan", boom)

        assert main(tmp_repo.argv("create", "demo", "--from", "x", "--no-iterate", "--yes")) == 1

        (end,) = _run_end_records(tmp_repo.root, "demo")
        assert end["outcome"] == "error"
        assert end["result"]["plan_path"].endswith("1-demo.md")
        assert end["result"]["manifest_updated"] is True

    def test_interrupt_during_post_create_reporting_still_names_the_written_plan(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The plan is recorded as soon as create_plan returns, before reporting runs."""
        import plan_tool.cli.authoring as authoring

        plan_path = tmp_repo.add_plan("1-demo")
        monkeypatch.setattr(
            authoring,
            "create_plan",
            lambda *_a, **_k: CreateResult(
                plan_path=plan_path,
                manifest_path=tmp_repo.manifest_path,
                manifest_updated=True,
            ),
        )

        def interrupted(*_a, **_k):
            raise KeyboardInterrupt

        monkeypatch.setattr(authoring, "_report_archive_result", interrupted)

        with pytest.raises(SystemExit) as exc:
            main(tmp_repo.argv("create", "demo", "--from", "x", "--no-iterate", "--yes"))
        assert exc.value.code == 130

        (end,) = _run_end_records(tmp_repo.root, "demo")
        assert end["outcome"] == "interrupted"
        assert end["result"]["plan_path"].endswith("1-demo.md")
        assert end["result"]["manifest_updated"] is True

    def test_quote_heavy_paths_are_costed_by_serialized_size(self) -> None:
        """Escaping counts toward the line cap: the shared run_log helper costs serialized bytes."""
        import plan_tool.cli.authoring as authoring

        paths = ['d/"' * 30 + f"{i}.md" for i in range(80)]
        kept, truncated = authoring._bounded_paths(paths)

        assert truncated is True
        assert len(json.dumps(kept, ensure_ascii=False).encode("utf-8")) <= 2048 + 4 * len(kept)

    def test_detail_that_raises_reports_files_as_unknown_not_empty(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`[]` means "nothing written"; a call that raised may have written files
        before failing, so the result says "unknown" (null), never an empty list."""
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailError

        def boom(*_a, **_k):
            raise DetailError("step 4 failed")

        monkeypatch.setattr(authoring, "generate_detail", boom)

        assert main(registered_plan.argv("detail", "demo", "--no-iterate")) == 2

        (end,) = _run_end_records(registered_plan.root, "demo")
        assert end["result"] == {
            "detail_files_written": None,
            "detail_files_written_count": None,
            "detail_files_truncated": None,
        }

    def test_detail_result_lists_written_files(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.cli.authoring as authoring
        from plan_tool.detail import DetailResult

        out = registered_plan.root / "docs" / "implementation-plans" / "plan-details" / "demo" / "step-1.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("x", encoding="utf-8")
        monkeypatch.setattr(
            authoring,
            "generate_detail",
            lambda *_a, **_k: [DetailResult(step_id=1, output_path=out, written=True)],
        )
        monkeypatch.setattr(authoring, "_run_completeness_tail", lambda *_a, **_k: [])
        monkeypatch.setattr(authoring, "_stamp_grounding", lambda *_a, **_k: None)

        assert main(registered_plan.argv("detail", "demo", "--no-iterate")) == 0

        (end,) = _run_end_records(registered_plan.root, "demo")
        assert [Path(p).name for p in end["result"]["detail_files_written"]] == ["step-1.md"]
        assert end["result"]["detail_files_written_count"] == 1
        assert end["result"]["detail_files_truncated"] is False

    def test_detail_with_nothing_written_records_explicit_empty_list(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.cli.authoring as authoring

        monkeypatch.setattr(authoring, "generate_detail", lambda *_a, **_k: [])

        assert main(registered_plan.argv("detail", "demo", "--no-iterate")) == 0

        (end,) = _run_end_records(registered_plan.root, "demo")
        assert end["result"] == {
            "detail_files_written": [],
            "detail_files_written_count": 0,
            "detail_files_truncated": False,
        }

    def test_detail_result_is_bounded_so_one_event_stays_under_the_line_cap(self) -> None:
        """A large plan truncates the list but keeps the true count and says so."""
        import plan_tool.cli.authoring as authoring

        paths = [f"docs/implementation-plans/plan-details/demo/step-{i}.md" for i in range(200)]
        result = authoring._detail_end_result(paths)

        assert result["detail_files_written_count"] == 200
        assert result["detail_files_truncated"] is True
        assert len(json.dumps(result)) < 2500

    def test_end_result_bound_counts_utf8_bytes_not_characters(self) -> None:
        """The run log caps serialized bytes; multibyte paths must not slip past a character count."""
        import plan_tool.cli.authoring as authoring

        paths = [f"docs/\u6587\u66f8/\u30b9\u30c6\u30c3\u30d7-{i}-" + "\u3042" * 40 + ".md" for i in range(60)]
        kept, truncated = authoring._bounded_paths(paths)

        assert truncated is True
        assert sum(len(p.encode("utf-8")) for p in kept) <= 2000
