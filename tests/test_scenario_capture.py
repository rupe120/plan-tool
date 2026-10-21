"""Unit tests for the prompt-mode A/B scenario capture.

Mirrors ``plan_tool/scenario_capture.py``. Capture is env-gated and
best-effort; these tests toggle ``PLAN_TOOL_CAPTURE_SCENARIOS`` explicitly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plan_tool.scenario_capture import (
    CATEGORY_FAILURE,
    CATEGORY_FOUNDATIONAL,
    CATEGORY_MIXED_STEP,
    EXPERIMENTS,
    KNOWN_CATEGORIES,
    PROMPT_MODE_EXPERIMENT,
    Experiment,
    arm_from_split,
    capture_enabled,
    capture_scenario,
    categorize_scenario,
    resolve_arm,
    scenarios_dir,
    valid_categories_for,
)


class TestExperiment:
    """The experiment framework that makes the corpus multi-experiment (future
    prompt A/Bs register an ``Experiment`` rather than re-implementing capture)."""

    _exp = Experiment(
        name="demo",
        arms=("a", "b", "c"),
        default_arm="a",
        env_var="DEMO_ARM",
    )

    def test_prompt_mode_registered(self) -> None:
        assert EXPERIMENTS["prompt-mode"] is PROMPT_MODE_EXPERIMENT
        assert PROMPT_MODE_EXPERIMENT.arms == ("combined", "split")
        assert PROMPT_MODE_EXPERIMENT.default_arm == "combined"

    def test_resolve_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DEMO_ARM", raising=False)
        assert self._exp.resolve_arm() == "a"

    def test_resolve_flag(self) -> None:
        assert self._exp.resolve_arm("b") == "b"
        assert self._exp.resolve_arm("  C ") == "c"  # case/space-insensitive

    def test_resolve_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEMO_ARM", "b")
        assert self._exp.resolve_arm() == "b"

    def test_flag_beats_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEMO_ARM", "b")
        assert self._exp.resolve_arm("c") == "c"

    def test_unknown_arm_falls_back_to_default(self) -> None:
        assert self._exp.resolve_arm("bogus") == "a"

    def test_registry_resolver(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PLAN_TOOL_PROMPT_MODE", raising=False)
        assert resolve_arm("prompt-mode", flag="split") == "split"
        assert resolve_arm("prompt-mode") == "combined"
        assert resolve_arm("no-such-experiment") == ""


class TestKnownCategories:
    """``KNOWN_CATEGORIES`` is DERIVED from the registry, not hand-maintained —
    so a future experiment's categories extend it with no second edit."""

    def test_derived_from_registry_plus_failure(self) -> None:
        expected = {CATEGORY_FAILURE}
        for exp in EXPERIMENTS.values():
            expected |= set(exp.categories)
        assert KNOWN_CATEGORIES == expected

    def test_covers_prompt_mode_vocabulary(self) -> None:
        assert {
            CATEGORY_FOUNDATIONAL,
            CATEGORY_MIXED_STEP,
            CATEGORY_FAILURE,
        } <= KNOWN_CATEGORIES


class TestValidCategoriesFor:
    """``Experiment.categories`` is load-bearing: it defines the vocabulary a
    capture site may emit (plus the universal ``failure``)."""

    def test_registered_experiment(self) -> None:
        valid = valid_categories_for("prompt-mode")
        assert valid == PROMPT_MODE_EXPERIMENT.categories | {CATEGORY_FAILURE}
        assert CATEGORY_FAILURE in valid  # universal, not on the Experiment

    def test_unregistered_experiment_is_none(self) -> None:
        # ``None`` signals "don't filter" — the owner defines the vocabulary.
        assert valid_categories_for("no-such-experiment") is None


class TestArmFromSplit:
    """The recorded arm: an explicit resolved arm wins; else invoker-presence."""

    def test_explicit_arm_wins(self) -> None:
        assert arm_from_split("combined", split=True) == "combined"
        assert arm_from_split("split", split=False) == "split"
        # A future arm name passes through verbatim (not just combined/split).
        assert arm_from_split("shallow", split=True) == "shallow"

    def test_falls_back_to_split_flag(self) -> None:
        assert arm_from_split(None, split=True) == "split"
        assert arm_from_split(None, split=False) == "combined"


class TestCategorizeScenario:
    """Open-vocabulary categorizer: records every truthy signal, [] when none."""

    def test_returns_truthy_labels_in_order(self) -> None:
        cats = categorize_scenario(
            {
                CATEGORY_FOUNDATIONAL: True,
                CATEGORY_MIXED_STEP: False,
                CATEGORY_FAILURE: True,
            }
        )
        assert cats == [CATEGORY_FOUNDATIONAL, CATEGORY_FAILURE]

    def test_empty_when_nothing_set(self) -> None:
        assert categorize_scenario(
            {CATEGORY_FOUNDATIONAL: False, CATEGORY_MIXED_STEP: False}
        ) == []

    def test_open_vocabulary_accepts_new_labels(self) -> None:
        # A future A/B axis can introduce a category without touching the module.
        assert categorize_scenario({"new-axis": True, "other-axis": False}) == [
            "new-axis"
        ]


class TestCaptureEnabled:
    def test_off_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PLAN_TOOL_CAPTURE_SCENARIOS", raising=False)
        assert capture_enabled() is False

    @pytest.mark.parametrize("val", ["1", "true", "TRUE", "yes", "on"])
    def test_truthy_values(
        self, monkeypatch: pytest.MonkeyPatch, val: str
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", val)
        assert capture_enabled() is True

    @pytest.mark.parametrize("val", ["0", "false", "no", "", "off"])
    def test_falsy_values(
        self, monkeypatch: pytest.MonkeyPatch, val: str
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", val)
        assert capture_enabled() is False


class TestCaptureScenario:
    def test_noop_when_disabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_CAPTURE_SCENARIOS", raising=False)
        result = capture_scenario(
            "propose_steps",
            experiment="prompt-mode", arm="combined",
            categories=[CATEGORY_MIXED_STEP],
            inputs={"description": "x"},
            repo_root=tmp_path,
        )
        assert result is None
        assert not scenarios_dir(tmp_path).exists()

    def test_noop_when_repo_root_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        assert (
            capture_scenario(
                "detail",
                experiment="prompt-mode", arm="split",
                categories=[CATEGORY_MIXED_STEP],
                inputs={},
                repo_root=None,
            )
            is None
        )

    def test_noop_when_no_categories(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The relevance gate: an uncategorized run is not saved even when
        capture is enabled and ``repo_root`` is set."""
        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        result = capture_scenario(
            "propose_steps",
            experiment="prompt-mode", arm="combined",
            categories=[],
            inputs={"description": "x"},
            repo_root=tmp_path,
        )
        assert result is None
        assert not scenarios_dir(tmp_path).exists()

    def test_writes_jsonl_record(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        path = capture_scenario(
            "propose_steps",
            experiment="prompt-mode", arm="combined",
            categories=[CATEGORY_FOUNDATIONAL, CATEGORY_MIXED_STEP],
            inputs={"description": "build a thing"},
            outcome={"n_steps": 3},
            repo_root=tmp_path,
            run_id="r-123",
        )
        assert path == scenarios_dir(tmp_path) / "propose_steps.jsonl"
        assert path.exists()
        record = json.loads(path.read_text(encoding="utf-8").strip())
        assert record["v"] == 2  # schema version
        assert record["kind"] == "propose_steps"
        assert record["experiment"] == "prompt-mode"
        assert record["arm"] == "combined"
        assert record["categories"] == [CATEGORY_FOUNDATIONAL, CATEGORY_MIXED_STEP]
        assert record["inputs"] == {"description": "build a thing"}
        assert record["outcome"] == {"n_steps": 3}
        assert "captured_at" in record
        # Provenance + telemetry-link fields always present (None when absent).
        assert "repo_sha" in record
        assert record["run_id"] == "r-123"

    def test_drops_categories_outside_experiment_vocabulary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A category the experiment didn't declare (e.g. a typo) is filtered
        out of the record — ``Experiment.categories`` gates the vocabulary."""
        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        path = capture_scenario(
            "propose_steps",
            experiment="prompt-mode", arm="combined",
            categories=[CATEGORY_MIXED_STEP, "mixed-ste"],  # typo of 'mixed-step'
            inputs={"description": "x"},
            repo_root=tmp_path,
        )
        record = json.loads(path.read_text(encoding="utf-8").strip())
        assert record["categories"] == [CATEGORY_MIXED_STEP]  # typo dropped

    def test_noop_when_all_categories_invalid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When nothing survives the vocabulary gate the run is not relevant —
        no record, no file (same as the empty-categories relevance gate)."""
        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        result = capture_scenario(
            "propose_steps",
            experiment="prompt-mode", arm="combined",
            categories=["bogus-only"],
            inputs={"description": "x"},
            repo_root=tmp_path,
        )
        assert result is None
        assert not scenarios_dir(tmp_path).exists()

    def test_unregistered_experiment_categories_not_filtered(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unregistered experiment owns its own vocabulary — capture keeps
        whatever categories it emits rather than dropping them."""
        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        path = capture_scenario(
            "propose_steps",
            experiment="future-axis", arm="x",
            categories=["custom-a", "custom-b"],
            inputs={"description": "x"},
            repo_root=tmp_path,
        )
        record = json.loads(path.read_text(encoding="utf-8").strip())
        assert record["categories"] == ["custom-a", "custom-b"]

    def test_carries_run_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        path = capture_scenario(
            "detail",
            experiment="prompt-mode", arm="split",
            categories=[CATEGORY_FOUNDATIONAL],
            inputs={"plan": "p.md", "step_id": 1},
            repo_root=tmp_path,
            run_id="run-xyz",
        )
        assert json.loads(path.read_text(encoding="utf-8"))["run_id"] == "run-xyz"

    def test_appends_multiple_records(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        for i in range(3):
            capture_scenario(
                "detail",
                experiment="prompt-mode", arm="split",
                categories=[CATEGORY_MIXED_STEP],
                inputs={"plan": "p.md", "step_id": i},
                repo_root=tmp_path,
            )
        lines = (
            (scenarios_dir(tmp_path) / "detail.jsonl")
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()
        )
        assert len(lines) == 3
        assert [json.loads(line)["inputs"]["step_id"] for line in lines] == [
            0,
            1,
            2,
        ]


class TestProposalScenarioSignals:
    """`create._proposal_scenario_signals` detects A/B-relevant behaviors from
    the proposal STRUCTURE only — arm-independent (no split-only sweep), so the
    same input categorizes the same way in either arm."""

    def _sig(self, steps):
        from plan_tool.create import _proposal_scenario_signals

        return _proposal_scenario_signals(steps)

    def test_trivial_proposal_has_no_signals(self) -> None:
        from plan_tool.schema import Step

        sig = self._sig([Step(id=1, title="one")])
        assert categorize_scenario(sig) == []

    def test_mixed_step_signal_from_refactor_feature_split(self) -> None:
        from plan_tool.schema import ChangeType, Step

        steps = [
            Step(id=1, title="refactor", change_type=ChangeType.REFACTOR),
            Step(
                id=2,
                title="feature",
                change_type=ChangeType.FEATURE,
                depends_on=[1],
            ),
        ]
        assert self._sig(steps)[CATEGORY_MIXED_STEP] is True

    def test_foundational_from_multifile_refactor(self) -> None:
        from plan_tool.schema import ChangeType, Step

        steps = [
            Step(
                id=1,
                title="r",
                change_type=ChangeType.REFACTOR,
                files=["a.py", "b.py"],
            )
        ]
        assert self._sig(steps)[CATEGORY_FOUNDATIONAL] is True

    def test_multifile_feature_is_foundational(self) -> None:
        # Broadened proxy (gap D): editing ≥2 files is foundational regardless
        # of change_type — a non-refactor consolidation is caught too.
        from plan_tool.schema import ChangeType, Step

        steps = [
            Step(
                id=1,
                title="f",
                change_type=ChangeType.FEATURE,
                files=["a.py", "b.py"],
            )
        ]
        assert self._sig(steps)[CATEGORY_FOUNDATIONAL] is True

    def test_extract_pattern_is_foundational(self) -> None:
        # Create a new file while editing an existing one (extract shared
        # module + update callers) — foundational even with one of each.
        from plan_tool.schema import Step

        steps = [Step(id=1, title="x", files=["a.py"], creates=["shared.py"])]
        assert self._sig(steps)[CATEGORY_FOUNDATIONAL] is True

    def test_single_file_or_new_only_is_not_foundational(self) -> None:
        from plan_tool.schema import Step

        # One existing file edited, nothing created → not foundational.
        assert self._sig([Step(id=1, title="x", files=["a.py"])])[
            CATEGORY_FOUNDATIONAL
        ] is False
        # Only new files (a fresh feature, no existing logic touched) → not.
        assert self._sig([Step(id=1, title="x", creates=["a.py", "b.py"])])[
            CATEGORY_FOUNDATIONAL
        ] is False


class TestDedupAndProvenance:
    def test_dedup_skips_identical_scenario(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        kw = dict(
            experiment="prompt-mode", arm="combined",
            categories=[CATEGORY_MIXED_STEP],
            inputs={"description": "same"},
            repo_root=tmp_path,
        )
        first = capture_scenario("propose_steps", **kw)
        second = capture_scenario("propose_steps", **kw)  # identical → dropped
        assert first is not None
        assert second is None
        lines = (
            (scenarios_dir(tmp_path) / "propose_steps.jsonl")
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()
        )
        assert len(lines) == 1

    def test_dedup_keeps_different_inputs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        for desc in ("a", "b"):
            capture_scenario(
                "propose_steps",
                experiment="prompt-mode", arm="combined",
                categories=[CATEGORY_MIXED_STEP],
                inputs={"description": desc},
                repo_root=tmp_path,
            )
        lines = (
            (scenarios_dir(tmp_path) / "propose_steps.jsonl")
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()
        )
        assert len(lines) == 2

    def test_dedup_keeps_different_arm(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Same input in the other arm is a distinct scenario — not deduped.
        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        for arm in ("combined", "split"):
            capture_scenario(
                "propose_steps",
                experiment="prompt-mode",
                arm=arm,
                categories=[CATEGORY_MIXED_STEP],
                inputs={"description": "same"},
                repo_root=tmp_path,
            )
        lines = (
            (scenarios_dir(tmp_path) / "propose_steps.jsonl")
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()
        )
        assert len(lines) == 2

    def test_repo_sha_reads_git_head(self, tmp_path: Path) -> None:
        import subprocess

        from plan_tool.scenario_capture import repo_sha

        assert repo_sha(tmp_path) is None  # not a git work tree
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "--allow-empty", "-q",
             "-m", "x", "--author", "T <t@t>"],
            check=True,
            env={
                "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t",
                "PATH": __import__("os").environ["PATH"],
            },
        )
        sha = repo_sha(tmp_path)
        assert sha is not None and len(sha) == 40

    def test_working_tree_dirty_ignores_corpus(self, tmp_path: Path) -> None:
        import subprocess

        from plan_tool.scenario_capture import scenarios_dir, working_tree_dirty

        assert working_tree_dirty(tmp_path) is None  # not a git work tree
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        # A fresh repo with nothing tracked is clean.
        assert working_tree_dirty(tmp_path) is False
        # An untracked corpus file must NOT flip dirty (it's the capture's own
        # output, not a source change the next run depends on).
        sdir = scenarios_dir(tmp_path)
        sdir.mkdir(parents=True)
        (sdir / "propose_steps.jsonl").write_text("{}\n", encoding="utf-8")
        assert working_tree_dirty(tmp_path) is False
        # A real source change DOES flip dirty.
        (tmp_path / "src.py").write_text("x = 1\n", encoding="utf-8")
        assert working_tree_dirty(tmp_path) is True

    def test_content_sha_changes_with_content(self, tmp_path: Path) -> None:
        from plan_tool.scenario_capture import content_sha

        p = tmp_path / "plan.md"
        p.write_text("one", encoding="utf-8")
        a = content_sha(p)
        p.write_text("two", encoding="utf-8")
        assert a is not None and a != content_sha(p)
        assert content_sha(tmp_path / "missing.md") is None

    def test_record_has_dirty_field(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.scenario_capture as sc

        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        monkeypatch.setattr(sc, "working_tree_dirty", lambda r: True)
        path = capture_scenario(
            "propose_steps",
            experiment="prompt-mode", arm="combined",
            categories=[CATEGORY_MIXED_STEP],
            inputs={"description": "x"},
            repo_root=tmp_path,
        )
        assert json.loads(path.read_text(encoding="utf-8"))["dirty"] is True

    def test_failure_then_success_both_kept(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A later success of a previously-failed input is NOT deduped away —
        the failure/success discriminator keeps both (gap C)."""
        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        common = dict(
            experiment="prompt-mode", arm="combined", inputs={"description": "flaky"}, repo_root=tmp_path
        )
        first = capture_scenario(
            "propose_steps", categories=[CATEGORY_FAILURE], **common
        )
        second = capture_scenario(
            "propose_steps", categories=[CATEGORY_MIXED_STEP], **common
        )
        assert first is not None and second is not None
        lines = (
            (scenarios_dir(tmp_path) / "propose_steps.jsonl")
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()
        )
        assert len(lines) == 2
        # ...but two failures of the same input still dedup to one.
        assert (
            capture_scenario(
                "propose_steps", categories=[CATEGORY_FAILURE], **common
            )
            is None
        )


class TestDeterminism:
    """A captured record is a deterministic function of its inputs — only
    ``captured_at`` varies, and the scenario identity excludes it."""

    def test_record_is_canonical_and_reproducible(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.scenario_capture as sc

        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        # Pin the non-input fields so the only freedom is the inputs.
        monkeypatch.setattr(sc, "repo_sha", lambda r: "deadbeef")
        monkeypatch.setattr(sc, "working_tree_dirty", lambda r: False)
        from datetime import datetime, timezone

        monkeypatch.setattr(
            sc, "_utcnow", lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)
        )

        def cap(root: Path):
            root.mkdir(exist_ok=True)
            capture_scenario(
                "propose_steps",
                experiment="prompt-mode", arm="combined",
                categories=[CATEGORY_MIXED_STEP, CATEGORY_FOUNDATIONAL],
                inputs={"description": "x", "z": 1},
                outcome={"n_steps": 2},
                repo_root=root,
                run_id="r",
            )
            return (scenarios_dir(root) / "propose_steps.jsonl").read_text(
                encoding="utf-8"
            )

        line_a = cap(tmp_path / "a")
        line_b = cap(tmp_path / "b")
        # Same inputs → byte-identical record.
        assert line_a == line_b
        # Canonical: JSON keys are sorted.
        keys = list(json.loads(line_a).keys())
        assert keys == sorted(keys)

    def test_identity_independent_of_timestamp(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.scenario_capture as sc
        from datetime import datetime, timezone

        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        monkeypatch.setattr(sc, "repo_sha", lambda r: "abc")
        kw = dict(
            experiment="prompt-mode", arm="combined",
            categories=[CATEGORY_MIXED_STEP],
            inputs={"description": "x"},
            repo_root=tmp_path,
        )
        monkeypatch.setattr(
            sc, "_utcnow", lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        first = capture_scenario("propose_steps", **kw)
        # Later timestamp, same identity → deduped despite the clock moving.
        monkeypatch.setattr(
            sc, "_utcnow", lambda: datetime(2026, 6, 1, tzinfo=timezone.utc)
        )
        second = capture_scenario("propose_steps", **kw)
        assert first is not None and second is None


class TestDetailScenarioSignals:
    """`detail._detail_scenario_signals` — arm-independent (step files + plan
    dependency structure, never the split-only sweep / combined-only purity)."""

    def _plan(self, steps):
        from plan_tool.schema import Plan, PlanStatus, Priority

        return Plan(
            title="t",
            status=PlanStatus.PLANNING,
            priority=Priority.LOW,
            steps=steps,
        )

    def _sig(self, step, plan=None):
        from plan_tool.detail import _detail_scenario_signals

        return _detail_scenario_signals(step, plan or self._plan([step]))

    def test_single_file_lone_step_has_no_signals(self) -> None:
        from plan_tool.schema import Step

        assert categorize_scenario(
            self._sig(Step(id=1, title="one", files=["a.py"]))
        ) == []

    def test_foundational_from_multifile_step(self) -> None:
        from plan_tool.schema import Step

        step = Step(id=1, title="one", files=["a.py", "b.py"])
        assert self._sig(step)[CATEGORY_FOUNDATIONAL] is True

    def test_mixed_step_from_feature_on_refactor(self) -> None:
        """The feature half of a refactor→feature pair is mixed-step relevant."""
        from plan_tool.schema import ChangeType, Step

        refactor = Step(id=1, title="r", change_type=ChangeType.REFACTOR)
        feature = Step(
            id=2, title="f", change_type=ChangeType.FEATURE, depends_on=[1]
        )
        plan = self._plan([refactor, feature])
        assert self._sig(feature, plan)[CATEGORY_MIXED_STEP] is True

    def test_mixed_step_from_refactor_with_feature_dependent(self) -> None:
        """The refactor half is also mixed-step relevant (a feature depends on it)."""
        from plan_tool.schema import ChangeType, Step

        refactor = Step(id=1, title="r", change_type=ChangeType.REFACTOR)
        feature = Step(
            id=2, title="f", change_type=ChangeType.FEATURE, depends_on=[1]
        )
        plan = self._plan([refactor, feature])
        assert self._sig(refactor, plan)[CATEGORY_MIXED_STEP] is True

    def test_lone_step_is_not_mixed(self) -> None:
        from plan_tool.schema import ChangeType, Step

        step = Step(id=1, title="f", change_type=ChangeType.FEATURE)
        assert self._sig(step)[CATEGORY_MIXED_STEP] is False


class TestCaptureWiredIntoCreate:
    """``propose_steps_from_claude`` records a RELEVANT, categorized scenario
    ONLY for an operator run (``capture_scenarios=True``). A trivial
    (uncategorized) proposal and a non-operator run (default) are dropped."""

    def test_failed_proposal_records_failure_scenario(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unparseable proposal is captured as a FAILURE scenario — the
        inputs that broke this arm are re-runnable and discriminating."""
        from plan_tool.create import propose_steps_from_claude

        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        (tmp_path / ".git").mkdir()
        steps = propose_steps_from_claude(
            "build a thing",
            lambda _p: "sorry, no JSON",  # unparseable both attempts
            repo_root=tmp_path,
            capture_scenarios=True,
        )
        assert steps is None
        rec_path = scenarios_dir(tmp_path) / "propose_steps.jsonl"
        record = json.loads(rec_path.read_text(encoding="utf-8").strip())
        assert record["categories"] == [CATEGORY_FAILURE]
        assert record["outcome"]["status"] == "failed"
        assert record["inputs"] == {"description": "build a thing"}

    def test_relevant_combined_run_records_with_categories(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json as _json

        from plan_tool.create import propose_steps_from_claude

        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        (tmp_path / ".git").mkdir()
        # A refactor->feature split makes this proposal A/B-relevant ->
        # categorized "mixed-step".
        proposal = _json.dumps(
            [
                {
                    "title": "refactor",
                    "change_type": "refactor",
                    "files": [],
                    "depends_on": [],
                },
                {
                    "title": "feature",
                    "change_type": "feature",
                    "files": [],
                    "depends_on": [1],
                },
            ]
        )
        steps = propose_steps_from_claude(
            "build a thing",
            lambda _p: proposal,
            repo_root=tmp_path,
            capture_scenarios=True,
        )
        assert steps is not None
        rec_path = scenarios_dir(tmp_path) / "propose_steps.jsonl"
        record = json.loads(rec_path.read_text(encoding="utf-8").strip())
        assert record["experiment"] == "prompt-mode"
        assert record["arm"] == "combined"
        assert record["categories"] == [CATEGORY_MIXED_STEP]
        assert record["inputs"] == {"description": "build a thing"}
        assert record["outcome"]["titles"] == ["refactor", "feature"]

    def test_non_operator_run_records_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Default ``capture_scenarios=False`` (bench / reconcile path) records
        nothing even when relevant + enabled — only operator runs populate the
        corpus."""
        import json as _json

        from plan_tool.create import propose_steps_from_claude

        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        (tmp_path / ".git").mkdir()
        proposal = _json.dumps(
            [
                {"title": "refactor", "change_type": "refactor", "depends_on": []},
                {
                    "title": "feature",
                    "change_type": "feature",
                    "depends_on": [1],
                },
            ]
        )
        propose_steps_from_claude(
            "build a thing", lambda _p: proposal, repo_root=tmp_path
        )
        assert not (scenarios_dir(tmp_path) / "propose_steps.jsonl").exists()

    def test_trivial_run_records_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json as _json

        from plan_tool.create import propose_steps_from_claude

        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        (tmp_path / ".git").mkdir()
        # One plain step, no split / multi-file refactor → uncategorized.
        proposal = _json.dumps(
            [{"title": "one", "files": [], "depends_on": []}]
        )
        propose_steps_from_claude(
            "build a thing",
            lambda _p: proposal,
            repo_root=tmp_path,
            capture_scenarios=True,
        )
        assert not (scenarios_dir(tmp_path) / "propose_steps.jsonl").exists()

    def test_split_run_records_split_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json as _json

        from plan_tool.create import propose_steps_from_claude

        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        (tmp_path / ".git").mkdir()
        # A refactor step spanning 2 files → foundational (arm-independent
        # structural signal, identical in both arms).
        proposal = _json.dumps(
            [
                {
                    "title": "one",
                    "change_type": "refactor",
                    "files": ["a.py", "b.py"],
                    "depends_on": [],
                }
            ]
        )
        # foundational_invoker wired → mode is "split"; sweep finds nothing.
        sweep = _json.dumps(
            {"logic": "x", "shared_locations": [], "consolidation": None}
        )
        propose_steps_from_claude(
            "build a thing",
            lambda _p: proposal,
            repo_root=tmp_path,
            foundational_invoker=lambda _p: sweep,
            capture_scenarios=True,
        )
        rec_path = scenarios_dir(tmp_path) / "propose_steps.jsonl"
        record = json.loads(rec_path.read_text(encoding="utf-8").strip())
        assert record["arm"] == "split"
        assert CATEGORY_FOUNDATIONAL in record["categories"]

    def test_cache_hit_records_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A resumed (checkpoint cache-hit) run issues no call, so it must NOT
        append a scenario — recording it would mislabel the A/B corpus."""
        import json as _json

        from datetime import datetime, timezone

        from plan_tool.checkpoint import (
            Checkpoint,
            checkpoint_path,
            save_checkpoint,
        )
        from plan_tool.create import (
            _INITIAL_STEPS_CHECKPOINT_NAME,
            _initial_steps_input_hash,
            propose_steps_from_claude,
        )

        monkeypatch.setenv("PLAN_TOOL_CAPTURE_SCENARIOS", "1")
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        proposal = _json.dumps(
            [{"title": "one", "files": [], "depends_on": []}]
        )
        save_checkpoint(
            checkpoint_path(tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME),
            Checkpoint(
                input_hash=_initial_steps_input_hash(
                    "demo", "build a thing", out_dir, tmp_path
                ),
                payload=proposal,
                created_at=datetime.now(timezone.utc)
                .replace(microsecond=0)
                .isoformat(),
            ),
        )

        def explode(_p: str) -> str:
            raise AssertionError("invoker must not be called on cache hit")

        steps = propose_steps_from_claude(
            "build a thing",
            explode,
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
            capture_scenarios=True,
        )
        assert steps is not None  # resumed from cache
        assert not (scenarios_dir(tmp_path) / "propose_steps.jsonl").exists()
