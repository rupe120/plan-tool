"""Characterization tests for the read-only audit verbs' argument gates.

``review`` / ``review-all`` / ``review-walk`` / ``verify`` are all marked
``directly covered`` in ``COVERAGE_BASELINE.md``, and ``_review_walk_
environment_allows`` is pinned as a full truth table in
``tests/test_review.py``. Per the cli-package-split plan's no-duplication
rule those keep their inventory pointers rather than getting copied here:

  - ``_review_walk_environment_allows`` truth table (each opt-out, ``-y``,
    TTY)                          → ``tests/test_review.py``
    ``test_review_walk_environment_allows_predicate``
  - ``review`` reuse / save / walk-gate paths
                                  → ``tests/test_review.py``
  - ``review-all`` ``--fail-on-findings`` / ``--mode reconcile`` end-to-end,
    ``verify`` rollup + ``--deep`` + ``nothing to verify``
                                  → ``tests/test_launcher.py``
  - ``review-walk`` no-saved-review (rc 2) and unknown ``--id`` (rc 2)
                                  → ``tests/test_review_walk.py``

What's pinned *here* is the small set of gates those suites don't cover
without patching a ``plan_tool.cli`` module global — the ones reachable
split-proof because they decide before any claude call. ``review-all``'s
audit-only mode exclusion is a parser contract (``build_parser``); the
no-done-steps and ``--mode reconcile`` routing notice are driven through
``main(argv)`` on the package's temp-repo fixtures (see ``conftest.py``).
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from plan_tool.cli import build_parser, main
from plan_tool.review import Recommendation
from plan_tool.review_persistence import plan_reports_dir, save_review


def _direct_walk_recommendation(rec_id: str) -> Recommendation:
    return Recommendation(
        id=rec_id,
        source="reconcile",
        severity="high",
        step_id=1,
        title=f"Finding {rec_id}",
        body="body",
        suggested_action=None,
    )


def _save_direct_walk_sidecar(
    repo,
    *,
    timestamp: datetime,
    rec_id: str,
    kind: str = "review",
    is_pre_apply_checkpoint: bool = False,
) -> Path:
    save_kwargs = dict(
        plan_slug="demo",
        plan_path=str(repo.plans[0].relative_to(repo.root)),
        repo_root=repo.root,
        report_md="# Saved review",
        recommendations=[_direct_walk_recommendation(rec_id)],
        now=timestamp,
        kind=kind,
        is_pre_apply_checkpoint=is_pre_apply_checkpoint,
    )
    if kind == "completeness" and not is_pre_apply_checkpoint:
        from plan_tool.review_persistence import AuditInputSnapshot

        snapshot = AuditInputSnapshot.capture(repo.plans[0], repo.root)
        save_kwargs["qualified_result"] = {
            "headline": "awaiting-human-action",
            "stage": "detail",
            "coverage": "confirmed",
            "revision_status": "current",
            "audit_revision": snapshot.revision,
        }
    elif kind == "completeness":
        save_kwargs["qualified_result"] = None
    return save_review(**save_kwargs)


def _mark_sidecar_role_unknown(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = 3
    payload.pop("is_pre_apply_checkpoint", None)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_fresh_reconcile_unmatched_fence_opens_no_run_log(registered_plan) -> None:
    plan_path = registered_plan.plans[0]
    plan_path.write_text(
        plan_path.read_text(encoding="utf-8") + "\n```\n",
        encoding="utf-8",
    )

    assert main(registered_plan.argv("reconcile-plan", "demo", "--no-walk")) == 2
    assert not (registered_plan.root / ".plan-tool" / "runs").exists()
    assert not plan_reports_dir(plan_path).exists()


class TestRenderSavedReviewFindings:
    """``_render_saved_review_findings`` is the restricted remote flow's
    preview of every saved finding before that walk begins -- previously
    untested. ``restated_property`` must reach it for the same reason it
    must reach the interactive walk's ``_format_recommendation``."""

    def _saved(self, rec: Recommendation):
        from plan_tool.review_persistence import SavedReview

        return SavedReview(
            plan_slug="x", plan_path="plans/x.md",
            created_at="2026-01-01T00:00:00Z", report_md="report",
            recommendations=[rec],
        )

    def test_restatement_prints_labelled_as_evidence(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.cli.review_cmd import _render_saved_review_findings

        rec = Recommendation(
            id="bare-gap", source="plan-correctness", severity="high",
            step_id=None, title="title", body="body",
            restated_property="the safety net has no route for this case",
        )
        _render_saved_review_findings(self._saved(rec))
        out = capsys.readouterr().out
        assert "the safety net has no route for this case" in out
        assert "evidence" in out.lower()

    def test_no_restatement_line_when_absent(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.cli.review_cmd import _render_saved_review_findings

        rec = Recommendation(
            id="no-restated", source="plan-correctness", severity="high",
            step_id=None, title="title", body="body",
        )
        _render_saved_review_findings(self._saved(rec))
        assert "restatement" not in capsys.readouterr().out.lower()

    def test_no_restatement_line_when_whitespace_only(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.cli.review_cmd import _render_saved_review_findings

        rec = Recommendation(
            id="whitespace-restated", source="plan-correctness", severity="high",
            step_id=None, title="title", body="body", restated_property="  ",
        )
        _render_saved_review_findings(self._saved(rec))
        assert "restatement" not in capsys.readouterr().out.lower()


class TestDirectWalkSavedReviewSelection:
    def test_default_selection_skips_unreadable_and_nonfinal_candidates(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        final_path = _save_direct_walk_sidecar(
            registered_plan,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            rec_id="final",
        )
        _save_direct_walk_sidecar(
            registered_plan,
            timestamp=datetime(2026, 2, 1, tzinfo=timezone.utc),
            rec_id="checkpoint",
            kind="completeness",
            is_pre_apply_checkpoint=True,
        )
        unknown_path = _save_direct_walk_sidecar(
            registered_plan,
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
            rec_id="unknown",
        )
        _mark_sidecar_role_unknown(unknown_path)
        reports_dir = plan_reports_dir(registered_plan.plans[0])
        (reports_dir / "20260401-000000.json").write_text(
            "not valid json", encoding="utf-8"
        )

        captured = {}
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.walk_recommendations",
            lambda saved, **kwargs: captured.setdefault("path", saved.path),
        )

        assert main(registered_plan.argv("reconcile-plan-walk", "demo")) == 0
        assert captured["path"] == final_path

    def test_default_selection_reports_no_eligible_candidate_without_mutation(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        checkpoint = _save_direct_walk_sidecar(
            registered_plan,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            rec_id="checkpoint",
            kind="completeness",
            is_pre_apply_checkpoint=True,
        )
        original_checkpoint = checkpoint.read_text(encoding="utf-8")
        unknown_path = _save_direct_walk_sidecar(
            registered_plan,
            timestamp=datetime(2026, 2, 1, tzinfo=timezone.utc),
            rec_id="unknown",
        )
        _mark_sidecar_role_unknown(unknown_path)
        reports_dir = plan_reports_dir(registered_plan.plans[0])
        (reports_dir / "20260301-000000.json").write_text(
            "not valid json", encoding="utf-8"
        )

        registered_plan.add_plan("2-foreign")
        registered_plan.write_manifest()
        foreign_path = save_review(
            plan_slug="foreign",
            plan_path="plans/2-foreign.md",
            repo_root=registered_plan.root,
            report_md="# Foreign review",
            recommendations=[_direct_walk_recommendation("foreign")],
            now=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        (reports_dir / "20260501-000000.json").symlink_to(foreign_path)

        def fail_before_walk(*args, **kwargs):
            raise AssertionError("ineligible saves must not reach walk setup")

        monkeypatch.setattr(
            "plan_tool.cli.review_cmd._build_review_action_fn", fail_before_walk
        )
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.walk_recommendations", fail_before_walk
        )

        assert main(registered_plan.argv("reconcile-plan-walk", "demo")) == 2
        assert "no eligible saved review" in capsys.readouterr().err.lower()
        assert checkpoint.read_text(encoding="utf-8") == original_checkpoint

    def test_symlinked_reports_root_rejects_foreign_candidates(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Containment must not trust a reports root redirected to another plan."""
        reports_dir = plan_reports_dir(registered_plan.plans[0])
        registered_plan.add_plan("2-foreign")
        registered_plan.write_manifest()
        foreign_path = save_review(
            plan_slug="foreign",
            plan_path="plans/2-foreign.md",
            repo_root=registered_plan.root,
            report_md="# Foreign review",
            recommendations=[_direct_walk_recommendation("foreign")],
            now=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        reports_dir.parent.mkdir(parents=True)
        reports_dir.symlink_to(foreign_path.parent, target_is_directory=True)

        def fail_before_walk(*args, **kwargs):
            raise AssertionError("a redirected reports root must not start a walk")

        monkeypatch.setattr(
            "plan_tool.cli.review_cmd._build_review_action_fn", fail_before_walk
        )
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.walk_recommendations", fail_before_walk
        )

        assert main(registered_plan.argv("reconcile-plan-walk", "demo")) == 2
        assert "no eligible saved review" in capsys.readouterr().err.lower()
        assert (
            main(
                registered_plan.argv(
                    "reconcile-plan-walk", "demo", "--id", foreign_path.stem
                )
            )
            == 2
        )
        assert "outside this plan's reports directory" in capsys.readouterr().err.lower()

    def test_explicit_id_rejects_each_ineligible_state_without_fallback(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        fallback_final = _save_direct_walk_sidecar(
            registered_plan,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            rec_id="fallback",
        )
        original_fallback = fallback_final.read_text(encoding="utf-8")
        reports_dir = plan_reports_dir(registered_plan.plans[0])
        (reports_dir / "ambiguous.json").write_text("{}", encoding="utf-8")
        (reports_dir / "ambiguous.json.json").write_text("{}", encoding="utf-8")
        (reports_dir / "malformed.json").write_text("not valid json", encoding="utf-8")
        checkpoint = _save_direct_walk_sidecar(
            registered_plan,
            timestamp=datetime(2026, 2, 1, tzinfo=timezone.utc),
            rec_id="checkpoint",
            kind="completeness",
            is_pre_apply_checkpoint=True,
        )
        unknown_path = _save_direct_walk_sidecar(
            registered_plan,
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
            rec_id="unknown",
        )
        _mark_sidecar_role_unknown(unknown_path)

        registered_plan.add_plan("2-foreign")
        registered_plan.write_manifest()
        foreign_path = save_review(
            plan_slug="foreign",
            plan_path="plans/2-foreign.md",
            repo_root=registered_plan.root,
            report_md="# Foreign review",
            recommendations=[_direct_walk_recommendation("foreign")],
            now=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        foreign_link = reports_dir / "foreign-link.json"
        foreign_link.symlink_to(foreign_path)

        def fail_before_walk(*args, **kwargs):
            raise AssertionError("an ineligible pin must not fall back to a final save")

        monkeypatch.setattr(
            "plan_tool.cli.review_cmd._build_review_action_fn", fail_before_walk
        )
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.walk_recommendations", fail_before_walk
        )

        expected_refusals = [
            ("missing", "no saved review matched"),
            ("ambiguous.json", "ambiguous --id"),
            ("malformed", "could not be read"),
            (checkpoint.stem, "pre-apply checkpoint"),
            (unknown_path.stem, "unknown checkpoint role"),
            (foreign_link.stem, "outside this plan's reports directory"),
            ("..", "invalid --id"),
            (
                f"../plan-details/foreign/reports/{foreign_path.stem}",
                "invalid --id",
            ),
        ]
        for review_id, refusal in expected_refusals:
            assert (
                main(
                    registered_plan.argv(
                        "reconcile-plan-walk", "demo", "--id", review_id
                    )
                )
                == 2
            )
            assert refusal in capsys.readouterr().err.lower()
        assert fallback_final.read_text(encoding="utf-8") == original_fallback

    def test_final_non_review_kind_is_eligible_for_direct_walk(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        final_path = _save_direct_walk_sidecar(
            registered_plan,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            rec_id="detail-final",
            kind="detail-reconcile",
        )
        captured = {}
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.walk_recommendations",
            lambda saved, **kwargs: captured.update(
                path=saved.path, kind=saved.kind
            ),
        )

        assert main(registered_plan.argv("reconcile-plan-walk", "demo")) == 0
        assert captured == {"path": final_path, "kind": "detail-reconcile"}


class TestVerifyAllAuditOnlyGate:
    """``verify-all`` is audit-only: the mutating ``run`` mode isn't offered."""

    def test_run_mode_is_not_a_valid_choice(self) -> None:
        parser = build_parser()
        # ``--mode`` choices exclude every MUTATING_MODES entry, so ``run``
        # is rejected at parse time (exit 2) rather than reaching the handler.
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["verify-all", "demo", "--mode", "run"])
        assert exc.value.code == 2

    def test_requires_mode_or_rollup(self, registered_plan) -> None:
        # --mode is no longer required at parse time (it's an alternative to
        # --rollup); the handler rejects an invocation that picks neither.
        rc = main(registered_plan.argv("verify-all", "demo"))
        assert rc == 2

    def test_mode_and_rollup_are_mutually_exclusive(self, registered_plan) -> None:
        rc = main(
            registered_plan.argv("verify-all", "demo", "--mode", "check", "--rollup")
        )
        assert rc == 2

    def test_legacy_review_all_alias_still_parses(self) -> None:
        # The deprecated ``review-all`` / ``reconcile-all`` aliases route to
        # the same ``verify-all`` subparser, so the same audit-only gate applies.
        parser = build_parser()
        for alias in ("review-all", "reconcile-all"):
            with pytest.raises(SystemExit) as exc:
                parser.parse_args([alias, "demo", "--mode", "run"])
            assert exc.value.code == 2


class TestVerifyAllRunLog:
    """``verify-all`` spent one claude call per done step with no run log at
    all until this was wired. See BUG_BACKLOG."""

    def _events(self, root) -> list[dict]:
        import json

        out: list[dict] = []
        for log in sorted((root / ".plan-tool" / "runs").rglob("*.jsonl")):
            for line in log.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    out.append(json.loads(line))
        return out

    def test_rollup_opens_a_run_log(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An empty verdict list is the "nothing to verify" path: rc 0 with no
        # claude call, which still has to open and close the log.
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.verify_plan", lambda *a, **k: []
        )
        rc = main(registered_plan.argv("verify-all", "demo", "--rollup"))
        assert rc == 0
        events = self._events(registered_plan.root)
        starts = [e for e in events if e.get("event") == "run_start"]
        ends = [e for e in events if e.get("event") == "run_end"]
        assert [e["command"] for e in starts] == ["verify-all"]
        assert len(ends) == 1 and ends[0]["rc"] == 0

    def test_mode_sweep_opens_a_run_log(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.run_all_done_steps", lambda *a, **k: []
        )
        rc = main(registered_plan.argv("verify-all", "demo", "--mode", "check"))
        assert rc == 0
        starts = [
            e for e in self._events(registered_plan.root)
            if e.get("event") == "run_start"
        ]
        assert [e["command"] for e in starts] == ["verify-all"]

    def test_dry_run_opens_no_run_log(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.run_all_done_steps", lambda *a, **k: []
        )
        rc = main(
            registered_plan.argv(
                "verify-all", "demo", "--mode", "check", "--dry-run"
            )
        )
        assert rc == 0
        assert not (registered_plan.root / ".plan-tool" / "runs").exists()


class TestReviewAllNoDoneSteps:
    """With no done steps there's nothing to audit — exit 0, no claude call."""

    def test_reports_and_exits_zero(
        self, registered_plan, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # ``1-demo`` has a single pending step → zero done steps, so the
        # run-all loop body (and its claude calls) is never entered.
        rc = main(registered_plan.argv("reconcile-all", "demo", "--mode", "check"))
        assert rc == 0
        assert "no done steps in 'demo' to review." in capsys.readouterr().out


# --------------------------------------------------------------------------
# reconcile-plan --reuse / --no-reuse / --reuse-id — parse contract
# --------------------------------------------------------------------------


class TestReconcilePlanReuseFlags:
    def test_reconcile_plan_reuse_default_is_none(self) -> None:
        args = build_parser().parse_args(["reconcile-plan", "demo"])
        assert args.reuse is None
        assert args.reuse_id is None

    def test_reconcile_plan_reuse_flags_parse(self) -> None:
        parser = build_parser()
        assert parser.parse_args(["reconcile-plan", "demo", "--reuse"]).reuse is True
        assert (
            parser.parse_args(["reconcile-plan", "demo", "--no-reuse"]).reuse is False
        )
        pinned = parser.parse_args(
            ["reconcile-plan", "demo", "--reuse-id", "20260612-120000"]
        )
        assert pinned.reuse_id == "20260612-120000"


# --------------------------------------------------------------------------
# _prompt_reuse_saved_review — tri-state consumption (review kind)
# --------------------------------------------------------------------------
#
# The plan-wide ``review`` kind has no ``resolve_reusable_*`` sibling, so
# ``_prompt_reuse_saved_review`` gates the reuse flags inline. These drive it
# directly with a constructed namespace + a seeded fresh ``review`` save.

import argparse
from typing import Optional

from plan_tool.cli import _prompt_reuse_saved_review
from plan_tool.fingerprint import compute_code_fingerprint
from plan_tool.locator import PlanToolContext
from plan_tool.parser import parse_plan
from plan_tool.review_persistence import (
    compute_plan_fingerprint,
    list_saved_reviews,
)


def _review_ctx(repo_root: Path) -> PlanToolContext:
    return PlanToolContext(repo_root=repo_root, plans_dir=None, entries=[])


def _review_args(**overrides) -> argparse.Namespace:
    base = dict(dry_run=False, no_walk=False, no_save=False, step=None, yes=False)
    base.update(overrides)
    return argparse.Namespace(**base)


def _write_review_plan(repo_root: Path) -> Path:
    plan_path = repo_root / "1-fingerprint.md"
    plan_path.write_text(
        "---\n"
        "title: Fingerprint Plan\n"
        "status: in-progress\n"
        "priority: medium\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: Build the widget\n"
        "    files:\n"
        "      - widget.py\n"
        "    status: pending\n"
        "---\n\n# Fingerprint Plan\n",
        encoding="utf-8",
    )
    (repo_root / "widget.py").write_text(
        "def widget():\n    return 1\n", encoding="utf-8"
    )
    return plan_path


def _seed_review(
    repo_root: Path,
    plan_path: Path,
    *,
    now: datetime,
    kind: str = "review",
    is_pre_apply_checkpoint: bool = False,
    plan_fingerprint: Optional[str] = None,
) -> Path:
    """Persist one saved sidecar carrying both fingerprints.

    Defaults to the only reusable shape — an ordinary-final ``kind="review"``
    save, fresh against disk. ``kind`` / ``is_pre_apply_checkpoint`` build the
    ineligible variants; ``plan_fingerprint`` builds the stale one.
    """
    plan = parse_plan(plan_path)
    rec = Recommendation(
        id="step1-review-0",
        source="review",
        severity="medium",
        step_id=1,
        title="t",
        body="b",
    )
    return save_review(
        plan_slug="fingerprint",
        plan_path=plan_path.relative_to(repo_root).as_posix(),
        repo_root=repo_root,
        report_md="prior audit",
        recommendations=[rec],
        kind=kind,
        step_id=1,
        plan_fingerprint=(
            compute_plan_fingerprint(plan_path)
            if plan_fingerprint is None
            else plan_fingerprint
        ),
        code_fingerprint=compute_code_fingerprint(plan, plan_path, repo_root),
        is_pre_apply_checkpoint=is_pre_apply_checkpoint,
        now=now,
    )


def _seed_fresh_review(repo_root: Path, plan_path: Path) -> Path:
    """The eligible ordinary-final ``review`` save the unsafe seeds sit above."""
    return _seed_review(repo_root, plan_path, now=datetime(2999, 1, 1, 0, 0, 0))


def _seed_unsafe_candidates_above(
    repo_root: Path, plan_path: Path
) -> dict[str, Path]:
    """Seed one of every ineligible sidecar, all newer than the eligible save.

    Newest-first by filename: unreadable, checkpoint, unknown-role review,
    ordinary-final completeness. Each loadable one carries fresh fingerprints
    and a plausible name, so only the payload's kind/role can reject it.
    """
    non_review = _seed_review(
        repo_root, plan_path, now=datetime(2999, 1, 2), kind="completeness"
    )
    unknown_role = _seed_review(repo_root, plan_path, now=datetime(2999, 1, 3))
    payload = json.loads(unknown_role.read_text(encoding="utf-8"))
    # The role-aware schema version on a non-completeness kind is a
    # role/version mismatch → the unknown role no reader may trust as final.
    payload["version"] = 3
    unknown_role.write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    checkpoint = _seed_review(
        repo_root,
        plan_path,
        now=datetime(2999, 1, 4),
        kind="completeness",
        is_pre_apply_checkpoint=True,
    )
    unreadable = plan_reports_dir(plan_path) / "29990105-000000.json"
    unreadable.write_text("{ not json", encoding="utf-8")
    return {
        "unreadable": unreadable,
        "checkpoint": checkpoint,
        "unknown-role": unknown_role,
        "non-review": non_review,
    }


def _register_review_plan(repo_root: Path) -> Path:
    """``_write_review_plan`` plus the repo marker + manifest ``main`` needs."""
    plan_path = _write_review_plan(repo_root)
    (repo_root / ".git").mkdir(exist_ok=True)
    (repo_root / "structured_plans.json").write_text(
        json.dumps({"plans": [plan_path.name]}), encoding="utf-8"
    )
    return plan_path


def _review_argv(repo_root: Path, *args: str) -> list[str]:
    return [
        "--repo-root",
        str(repo_root),
        "--manifest",
        str(repo_root / "structured_plans.json"),
        *args,
    ]


class TestPromptReuseSavedReviewFlags:
    def test_review_no_reuse_skips_lookup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = tmp_path.resolve()
        plan_path = _write_review_plan(repo)
        _seed_fresh_review(repo, plan_path)

        import plan_tool.review_persistence as rp

        def _boom(*a, **k):  # pragma: no cover - must not be called
            raise AssertionError("list_saved_reviews must not run under --no-reuse")

        monkeypatch.setattr(rp, "list_saved_reviews", _boom)
        result = _prompt_reuse_saved_review(
            _review_ctx(repo), "fingerprint", _review_args(reuse=False),
            plan_path=plan_path,
        )
        assert result is None

    def test_review_reuse_id_miss_warns_runs_fresh(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = tmp_path.resolve()
        plan_path = _write_review_plan(repo)
        _seed_fresh_review(repo, plan_path)
        result = _prompt_reuse_saved_review(
            _review_ctx(repo), "fingerprint",
            _review_args(reuse_id="nonexistent-stem"),
            plan_path=plan_path,
        )
        assert result is None
        assert "no saved review matched --reuse-id" in capsys.readouterr().err

    def test_review_reuse_true_accepts_eligible_final_without_prompt(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path.resolve()
        plan_path = _write_review_plan(repo)
        saved_path = _seed_fresh_review(repo, plan_path)

        def _no_prompt(_prompt):  # pragma: no cover - must not be called
            raise AssertionError("--reuse over a fresh save must not prompt")

        result = _prompt_reuse_saved_review(
            _review_ctx(repo), "fingerprint", _review_args(reuse=True),
            plan_path=plan_path, input_fn=_no_prompt,
        )
        assert result == saved_path

    def test_review_unpinned_reuse_skips_unsafe_candidates(
        self, tmp_path: Path
    ) -> None:
        """The newest *eligible* save wins, not the newest file on disk."""
        repo = tmp_path.resolve()
        plan_path = _write_review_plan(repo)
        eligible = _seed_fresh_review(repo, plan_path)
        unsafe = _seed_unsafe_candidates_above(repo, plan_path)

        # Guard the fixture: every unsafe seed really does sort above the
        # eligible one, so the scan has to walk past all four to reach it.
        ordered = list_saved_reviews("fingerprint", repo, plan_path=plan_path)
        assert ordered == [
            unsafe["unreadable"],
            unsafe["checkpoint"],
            unsafe["unknown-role"],
            unsafe["non-review"],
            eligible,
        ]

        result = _prompt_reuse_saved_review(
            _review_ctx(repo), "fingerprint", _review_args(reuse=True),
            plan_path=plan_path,
        )
        assert result == eligible

    @pytest.mark.parametrize(
        "candidate, expected_reason",
        [
            ("unreadable", "could not be read"),
            ("checkpoint", "is a pre-apply audit checkpoint"),
            ("unknown-role", "carries an unknown checkpoint role"),
            ("non-review", "is a completeness sidecar"),
        ],
    )
    def test_review_reuse_id_declines_unsafe_or_unreadable_candidate(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        candidate: str,
        expected_reason: str,
    ) -> None:
        """An exact pin is exact: it declines with its own reason and runs
        fresh rather than falling back to the older eligible save."""
        repo = tmp_path.resolve()
        plan_path = _write_review_plan(repo)
        _seed_fresh_review(repo, plan_path)
        pinned = _seed_unsafe_candidates_above(repo, plan_path)[candidate]

        result = _prompt_reuse_saved_review(
            _review_ctx(repo), "fingerprint",
            _review_args(reuse_id=pinned.stem),
            plan_path=plan_path,
        )
        err = capsys.readouterr().err
        assert result is None
        assert expected_reason in err
        assert "running a fresh review" in err
        # Distinct from the stem-matched-nothing message.
        assert "no saved review matched" not in err

    def test_review_reuse_stops_at_newest_eligible_stale_candidate(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Freshness runs once, on the newest eligible save. A stale one
        starts a fresh review instead of widening the scan to older saves."""
        repo = tmp_path.resolve()
        plan_path = _write_review_plan(repo)
        _seed_fresh_review(repo, plan_path)  # older, eligible AND fresh
        _seed_review(
            repo,
            plan_path,
            now=datetime(2999, 1, 2),
            plan_fingerprint="stale-plan-digest",
        )

        result = _prompt_reuse_saved_review(
            _review_ctx(repo), "fingerprint", _review_args(reuse=True),
            plan_path=plan_path,
        )
        assert result is None
        assert "saved review is stale" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "flags, tty, answer, walks",
        [
            ([], True, "y", True),  # interactive acceptance
            (["--reuse"], True, None, True),
            (["--yes"], True, None, True),
            ([], False, None, False),  # non-TTY: selects, reports, no walk
        ],
    )
    def test_review_safe_reuse_dispatch_modes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        flags: list[str],
        tty: bool,
        answer: Optional[str],
        walks: bool,
    ) -> None:
        """Every entry path applies the same eligibility rule; only a TTY
        goes on to the per-finding walk."""
        import sys

        from plan_tool.cli import review_cmd as review_cmd_module
        from plan_tool.review_walk import WalkResult

        # ``--manifest`` is only honored when neither override is set.
        monkeypatch.delenv("PLAN_TOOL_PLANS_DIR", raising=False)
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        repo = tmp_path.resolve()
        plan_path = _register_review_plan(repo)
        eligible = _seed_fresh_review(repo, plan_path)
        _seed_unsafe_candidates_above(repo, plan_path)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: tty)

        def _no_audit(*a, **k):  # pragma: no cover - must not be called
            raise AssertionError("an accepted reuse must not spend a fresh audit")

        monkeypatch.setattr(review_cmd_module, "review_plan_full", _no_audit)

        walked: list[Optional[Path]] = []

        def _fake_walk(saved, **kwargs):
            walked.append(saved.path)
            return WalkResult(answered=0, quit_early=False)

        monkeypatch.setattr(review_cmd_module, "walk_recommendations", _fake_walk)

        def _input(_prompt):
            if answer is None:  # pragma: no cover - must not be called
                raise AssertionError("this dispatch mode must not prompt")
            return answer

        monkeypatch.setattr("builtins.input", _input)

        rc = main(_review_argv(repo, "reconcile-plan", "fingerprint", *flags))
        assert rc == 0
        assert walked == ([eligible] if walks else [])
        if not walks:
            # The findings are still reported, so a CI reader sees them.
            captured = capsys.readouterr()
            assert "(reuse) reusing saved review" in captured.out
            assert "skipping the walk" in captured.err
            assert f"--id {eligible.stem}" in captured.err
            assert "review/medium: t" in captured.out
            assert "confidence: limited" in captured.out

    def test_review_reuse_prompt_starts_and_closes_a_run_lifecycle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A blocking reuse prompt remains visible and exits cleanly on Ctrl-C."""
        import sys

        repo = tmp_path.resolve()
        plan_path = _register_review_plan(repo)
        _seed_fresh_review(repo, plan_path)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

        seen_in_flight: list[Path] = []

        def _interrupt(_prompt: str) -> str:
            snapshots = list(
                (repo / ".plan-tool" / "runs").rglob("in-flight.json")
            )
            assert len(snapshots) == 1
            snapshot = json.loads(snapshots[0].read_text(encoding="utf-8"))
            assert snapshot["command"] == "reconcile-plan"
            seen_in_flight.extend(snapshots)
            raise KeyboardInterrupt

        monkeypatch.setattr("builtins.input", _interrupt)

        with pytest.raises(SystemExit) as exc_info:
            main(_review_argv(repo, "reconcile-plan", "fingerprint"))
        assert exc_info.value.code == 130
        assert seen_in_flight
        assert not list((repo / ".plan-tool" / "runs").rglob("in-flight.json"))

        events = [
            json.loads(line)
            for log in (repo / ".plan-tool" / "runs").rglob("*.jsonl")
            for line in log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        endings = [event for event in events if event.get("event") == "run_end"]
        assert len(endings) == 1
        assert endings[0]["rc"] == 130
        assert endings[0]["error"] == "interrupted"


# --------------------------------------------------------------------------
# reconcile-plan --refresh — parse contract + cmd_review branch
# --------------------------------------------------------------------------
#
# ``--refresh`` short-circuits the audit to the step-3 ``refresh_plan`` entry
# point: a drift-gate (no claude) that reconciles only the changed files. The
# parse-contract cases drive ``build_parser()``; the branch cases drive
# ``main()`` on the ``registered_plan`` fixture while patching the module
# global ``plan_tool.cli.review_cmd.refresh_plan`` so no real reconcile or
# claude seam runs.

import plan_tool.cli.review_cmd as review_cmd
from plan_tool.refresh import RefreshOutcome


class TestReconcilePlanRefreshFlag:
    def test_reconcile_plan_refresh_default_is_false(self) -> None:
        args = build_parser().parse_args(["reconcile-plan", "demo"])
        assert args.refresh is False

    def test_reconcile_plan_refresh_flag_parses(self) -> None:
        args = build_parser().parse_args(["reconcile-plan", "demo", "--refresh"])
        assert args.refresh is True

    def test_reconcile_alias_inherits_refresh(self) -> None:
        parser = build_parser()
        assert parser.parse_args(["reconcile", "demo", "--refresh"]).refresh is True
        assert parser.parse_args(["review", "demo", "--refresh"]).refresh is True


class TestReconcilePlanAllScope:
    """``--all`` names reconcile-plan's existing plan-wide scope."""

    def test_all_flag_parses_for_every_alias(self) -> None:
        parser = build_parser()
        for command in ("reconcile-plan", "reconcile", "review"):
            args = parser.parse_args([command, "demo", "--all"])
            assert args.all is True
            assert args.step is None

    def test_all_and_step_are_mutually_exclusive(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["reconcile-plan", "demo", "--all", "--step", "1"])
        assert exc_info.value.code == 2

    def test_all_keeps_the_plan_wide_review_scope(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``--all`` names an already-default scope (no ``step_id`` narrowing) —
        distinct from checking that ``--all`` merely *parses*, which
        ``test_all_flag_parses_for_every_alias`` already covers. The run-log
        assertion below is what actually proves this call consumed
        ``args.all`` (rather than the flag being silently unwired): without
        it, this test would pass identically whether or not ``--all`` were
        ever read."""
        import json

        from plan_tool.review import ReviewResult

        captured: dict[str, object] = {}

        def _capture(path, **kwargs):
            captured.update(kwargs)
            return ReviewResult(report="ok", recommendations=[], dry_run=False)

        monkeypatch.setattr(review_cmd, "review_plan_full", _capture)
        monkeypatch.setattr(
            review_cmd, "_prompt_reuse_saved_review", lambda *a, **k: None
        )

        rc = main(
            registered_plan.argv(
                "reconcile-plan", "demo", "--all", "--no-save", "--no-walk"
            )
        )
        assert rc == 0
        assert captured["step_id"] is None

        starts = []
        for log in sorted((registered_plan.root / ".plan-tool" / "runs").rglob("*.jsonl")):
            for line in log.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    event = json.loads(line)
                    if event.get("event") == "run_start":
                        starts.append(event)
        assert len(starts) == 1
        assert starts[0]["flags"]["all"] is True

    def test_reconcile_plan_interrupt_exits_130(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            review_cmd,
            "review_plan_full",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
        monkeypatch.setattr(
            review_cmd, "_prompt_reuse_saved_review", lambda *_args, **_kwargs: None
        )

        with pytest.raises(SystemExit) as exc_info:
            main(registered_plan.argv("reconcile-plan", "demo", "--no-save", "--no-walk"))
        assert exc_info.value.code == 130


class TestReconcilePlanLessonsFlag:
    """Lesson capture is opt-in: default off, ``--lessons`` turns it on."""

    def test_reconcile_plan_lessons_default_is_false(self) -> None:
        args = build_parser().parse_args(["reconcile-plan", "demo"])
        assert args.lessons is False

    def test_reconcile_plan_lessons_flags_parse(self) -> None:
        parser = build_parser()
        assert parser.parse_args(["reconcile-plan", "demo", "--lessons"]).lessons is True
        # ``--no-lessons`` stays accepted — scripts pass it habitually.
        assert (
            parser.parse_args(["reconcile-plan", "demo", "--no-lessons"]).lessons
            is False
        )

    def test_reconcile_alias_inherits_lessons(self) -> None:
        parser = build_parser()
        assert parser.parse_args(["reconcile", "demo", "--lessons"]).lessons is True
        assert parser.parse_args(["review", "demo", "--lessons"]).lessons is True

    @pytest.mark.parametrize(
        "extra_argv, expected",
        [([], False), (["--lessons"], True), (["--no-lessons"], False)],
    )
    def test_flag_plumbs_into_review_plan_full(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        extra_argv: list[str],
        expected: bool,
    ) -> None:
        from plan_tool.review import ReviewResult

        captured: dict[str, object] = {}

        def _capture(path, **kwargs):
            captured.update(kwargs)
            return ReviewResult(report="ok", recommendations=[], dry_run=False)

        monkeypatch.setattr(review_cmd, "review_plan_full", _capture)
        monkeypatch.setattr(
            review_cmd, "_prompt_reuse_saved_review", lambda *a, **k: None
        )

        rc = main(
            registered_plan.argv(
                "reconcile-plan", "demo", "--no-save", "--no-walk", *extra_argv
            )
        )
        assert rc == 0
        assert captured.get("extract_lessons") is expected


class TestCmdReviewRefreshBranch:
    """``--refresh`` calls ``refresh_plan`` and renders its outcome, never
    entering the reuse-prompt / ``review_plan_full`` audit path."""

    def test_refresh_no_drift_skips_claude_and_reuse(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            review_cmd,
            "refresh_plan",
            lambda *a, **k: RefreshOutcome(plan_slug="demo"),
        )

        def _boom(*a, **k):  # pragma: no cover - must not be called
            raise AssertionError("--refresh must not enter the audit path")

        monkeypatch.setattr(review_cmd, "review_plan_full", _boom)
        monkeypatch.setattr(review_cmd, "_prompt_reuse_saved_review", _boom)

        rc = main(registered_plan.argv("reconcile-plan", "demo", "--refresh"))
        assert rc == 0

    def test_refresh_no_drift_prints_grounded_message(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(
            review_cmd,
            "refresh_plan",
            lambda *a, **k: RefreshOutcome(plan_slug="demo"),
        )
        rc = main(registered_plan.argv("reconcile-plan", "demo", "--refresh"))
        captured = capsys.readouterr()
        assert rc == 0
        assert "demo" in captured.out
        assert "still grounded" in captured.out
        # No findings → no walk pointer on stderr.
        assert "reconcile-plan-walk" not in captured.err

    def test_refresh_drift_reports_findings_and_walk_pointer(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(
            review_cmd,
            "refresh_plan",
            lambda *a, **k: RefreshOutcome(
                plan_slug="demo",
                drifted=True,
                needs_grounding=False,
                drifted_files=[Path("a.py"), Path("b.py")],
                findings=2,
                reconciled=True,
                grounding_path=None,  # pending findings ⇒ NOT re-stamped (#68)
            ),
        )
        rc = main(registered_plan.argv("reconcile-plan", "demo", "--refresh"))
        captured = capsys.readouterr()
        assert rc == 0
        assert "2 findings" in captured.out
        # Honesty signal: the gate was NOT cleared while findings are pending.
        assert "NOT re-stamped" in captured.out
        assert "plan-tool reconcile-plan-walk demo" in captured.err

    def test_refresh_needs_grounding_reports_baseline(
        self,
        registered_plan,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(
            review_cmd,
            "refresh_plan",
            lambda *a, **k: RefreshOutcome(
                plan_slug="demo",
                needs_grounding=True,
                drifted=True,
                drifted_files=[Path("a.py")],
                findings=0,  # clean reconcile ⇒ first baseline is stamped
                reconciled=True,
                grounding_path=Path(".plan-tool/grounding/demo.json"),
            ),
        )
        rc = main(registered_plan.argv("reconcile-plan", "demo", "--refresh"))
        captured = capsys.readouterr()
        assert rc == 0
        assert "no grounding baseline" in captured.out
        assert "baseline grounding sidecar" in captured.out

    def test_refresh_calls_entry_point_with_repo_root(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple] = []

        def _spy(*args, **kwargs):
            calls.append((args, kwargs))
            return RefreshOutcome(plan_slug="demo")

        monkeypatch.setattr(review_cmd, "refresh_plan", _spy)
        rc = main(registered_plan.argv("reconcile-plan", "demo", "--refresh"))
        assert rc == 0
        assert len(calls) == 1
        (args, kwargs) = calls[0]
        # Shim forwards the resolved plan path + repo root positionally only.
        assert kwargs == {}
        assert len(args) == 2
        plan_path, repo_root = args
        assert plan_path.name == "1-demo.md"
        assert repo_root.resolve() == registered_plan.root.resolve()


class TestReprocessHelpMentionsRefresh:
    """The ``--reprocess`` help disambiguates itself from ``--refresh``."""

    def test_reprocess_help_mentions_refresh(self) -> None:
        parser = build_parser()
        action = next(
            a
            for a in parser._subparsers._group_actions[0].choices["create"]._actions
            if a.dest == "reprocess"
        )
        assert "reconcile-plan --refresh" in action.help
