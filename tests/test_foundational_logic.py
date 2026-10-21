"""Unit tests for the shared foundational-logic sweep.

Mirrors ``plan_tool/foundational_logic.py``. The sweep is the divergent
repo-wide duplication search lifted out of the ``create`` step-proposal and
``detail`` authoring prompts. All tests stub the invoker — no backend spawns.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plan_tool.foundational_logic import (
    ConsolidationSuggestion,
    SharedLocation,
    SweepResult,
    format_foundational_logic_block,
    merge_sweep_into_steps,
    parse_sweep_response,
    render_foundational_logic_prompt,
    run_foundational_logic_sweep,
)
from plan_tool.schema import ChangeType, Step


def _sweep_json(**overrides) -> str:
    body = {
        "logic": "path resolution",
        "shared_locations": [
            {
                "path": "plan_tool/locator.py",
                "anchor": "resolve_root",
                "relation": "duplicate",
                "recommendation": "update-in-place",
                "note": "second copy of the root walk",
                "step_id": 1,
            }
        ],
        "consolidation": None,
    }
    body.update(overrides)
    return json.dumps(body)


class TestParseSweepResponse:
    def test_parses_full_object(self) -> None:
        result = parse_sweep_response(_sweep_json())
        assert result is not None
        assert result.logic == "path resolution"
        assert len(result.shared_locations) == 1
        loc = result.shared_locations[0]
        assert loc.path == "plan_tool/locator.py"
        assert loc.relation == "duplicate"
        assert loc.recommendation == "update-in-place"
        assert loc.step_id == 1

    def test_tolerates_trailing_prose(self) -> None:
        raw = _sweep_json() + "\n\nThat's the sweep result."
        assert parse_sweep_response(raw) is not None

    def test_garbage_returns_none(self) -> None:
        assert parse_sweep_response("sorry, no JSON here") is None

    def test_empty_result_returns_none(self) -> None:
        raw = json.dumps(
            {"logic": "", "shared_locations": [], "consolidation": None}
        )
        assert parse_sweep_response(raw) is None

    def test_unknown_relation_coerced_blank(self) -> None:
        raw = _sweep_json(
            shared_locations=[
                {"path": "a/b.py", "relation": "bogus", "recommendation": "x"}
            ]
        )
        result = parse_sweep_response(raw)
        assert result is not None
        assert result.shared_locations[0].relation == ""
        assert result.shared_locations[0].recommendation == ""

    def test_location_without_path_dropped(self) -> None:
        raw = _sweep_json(
            shared_locations=[{"anchor": "x"}, {"path": "real/file.py"}]
        )
        result = parse_sweep_response(raw)
        assert result is not None
        assert [loc.path for loc in result.shared_locations] == ["real/file.py"]

    def test_consolidation_parsed(self) -> None:
        raw = _sweep_json(
            shared_locations=[],
            consolidation={
                "title": "Consolidate root walk into locator",
                "files": ["plan_tool/locator.py"],
                "creates": [],
                "rationale": "one source of truth",
                "after_step_id": 1,
            },
        )
        result = parse_sweep_response(raw)
        assert result is not None
        assert result.consolidation is not None
        assert result.consolidation.after_step_id == 1
        assert result.consolidation.files == ["plan_tool/locator.py"]

    def test_quoted_numeral_resolves_to_the_same_id_as_its_bare_int_form(self) -> None:
        raw = _sweep_json(
            shared_locations=[{"path": "a.py", "step_id": "1"}],
            consolidation={"title": "Consolidate", "after_step_id": "1"},
        )
        result = parse_sweep_response(raw)
        assert result is not None
        assert result.shared_locations[0].step_id == 1
        assert result.consolidation is not None
        assert result.consolidation.after_step_id == 1

    @pytest.mark.parametrize(
        "raw_id",
        [
            "--5",
            "²",
            "5.0",
            "2_0",
            "٢",
            "02",
            "0",
            pytest.param("1" + "0" * 4999, id="oversized"),
        ],
    )
    def test_malformed_numeral_ids_are_dropped_without_raising(
        self, raw_id: str
    ) -> None:
        raw = _sweep_json(
            shared_locations=[{"path": "a.py", "step_id": raw_id}],
            consolidation={"title": "Consolidate", "after_step_id": raw_id},
        )
        result = parse_sweep_response(raw)
        assert result is not None
        assert result.shared_locations[0].step_id is None
        assert result.consolidation is not None
        assert result.consolidation.after_step_id is None

    def test_consolidation_without_title_dropped(self) -> None:
        raw = _sweep_json(
            shared_locations=[],
            consolidation={"files": ["x.py"]},
        )
        # A title-less consolidation is dropped; ``logic`` still keeps the
        # result alive (it is not empty), but no consolidation step is minted.
        result = parse_sweep_response(raw)
        assert result is not None
        assert result.consolidation is None

    def test_consolidation_intent_key_parsed(self) -> None:
        """The parser round-trips the JSON "intent" key on `consolidation` —
        proves the sweep prompt's field actually reaches
        `ConsolidationSuggestion`, not only that a hand-built dataclass
        instance behaves correctly."""
        raw = _sweep_json(
            shared_locations=[],
            consolidation={
                "title": "Consolidate shared rule",
                "files": [],
                "creates": [],
                "rationale": "single source beats patching",
                "intent": "removes the duplicated rule for good",
                "after_step_id": 1,
            },
        )
        result = parse_sweep_response(raw)
        assert result is not None
        assert result.consolidation is not None
        assert (
            result.consolidation.intent == "removes the duplicated rule for good"
        )

    def test_blank_everything_returns_none(self) -> None:
        raw = json.dumps(
            {
                "logic": "",
                "shared_locations": [],
                "consolidation": {"files": ["x.py"]},
            }
        )
        assert parse_sweep_response(raw) is None


class TestSweepResponseContract:
    def test_prompt_examples_cover_closed_values_and_nullable_ids(self) -> None:
        prompt = render_foundational_logic_prompt("a scoped change")
        for value in (
            '"duplicate"',
            '"parallel-call-site"',
            '"sibling-implementation"',
            '"update-in-place"',
            '"consolidate"',
            '"defer"',
            '"step_id": null',
            '"step_id": 2',
            '"after_step_id": null',
            '"after_step_id": 2',
        ):
            assert value in prompt
        assert "either a bare step id such\n  as `2` or `null`" in prompt

    def test_split_sweep_prompt_classifies_semantic_reach_not_file_count(self) -> None:
        prompt = render_foundational_logic_prompt(
            "Focused plan description:\nAdd the focused property.\n\n"
            "Proposed steps for this plan:\n- step 1: Add the focused path"
        )
        assert "focused description and each proposed\n   step's declared boundary" in prompt
        assert "current common owner unchanged" in prompt
        assert "smallest local\n     adapter or bounded additive extension" in prompt
        assert "required shared semantic change to `defer`" in prompt
        assert "A shared path, duplicate, parallel caller" in prompt
        assert "number of consumers is inspection evidence only" in prompt
        assert "Do not emit that owner in" in prompt
        assert "observable execution handoff" in prompt
        assert "Otherwise omit `consolidation`" in prompt
        assert "may accompany an\n   unrelated `defer` finding" in prompt


class TestRunSweep:
    def test_success_first_attempt(self) -> None:
        calls = {"n": 0}

        def invoker(prompt: str) -> str:
            calls["n"] += 1
            return _sweep_json()

        result = run_foundational_logic_sweep("scope", invoker)
        assert calls["n"] == 1
        assert result is not None

    def test_repair_retry_on_bad_first(self) -> None:
        calls = {"n": 0}

        def invoker(prompt: str) -> str:
            calls["n"] += 1
            return "nonsense" if calls["n"] == 1 else _sweep_json()

        result = run_foundational_logic_sweep("scope", invoker)
        assert calls["n"] == 2
        assert result is not None

    def test_returns_none_when_both_attempts_fail(self) -> None:
        result = run_foundational_logic_sweep("scope", lambda _p: "garbage")
        assert result is None


class _FakeRunLogger:
    """Records the run-log telemetry a split sub-call would emit."""

    run_id = "run-1"

    def __init__(self) -> None:
        self.starts: list[tuple] = []
        self.binds: list[tuple] = []

    def claude_call_start(
        self, *, phase, attempt, prompt_bytes, prompt_sha256, **extra
    ):
        assert len(prompt_sha256) == 64  # hash of the prompt, never its text
        self.starts.append((phase, attempt, extra))

    def bind_shell_sink(self, *, phase, attempt):
        import contextlib

        self.binds.append((phase, attempt))
        return contextlib.nullcontext()


class TestSweepInstrumentation:
    """A wired ``run_logger`` makes each split sub-call visible in the run-log
    (gap B): one ``claude_call_start`` per attempt + a bound shell sink."""

    def test_single_attempt_emits_one_call_start(self) -> None:
        rl = _FakeRunLogger()
        run_foundational_logic_sweep(
            "scope", lambda _p: _sweep_json(), run_logger=rl, step_id=7
        )
        assert rl.starts == [("foundational_sweep", 1, {"step_id": 7})]
        assert rl.binds == [("foundational_sweep", 1)]

    def test_retry_emits_two_call_starts(self) -> None:
        rl = _FakeRunLogger()
        calls = {"n": 0}

        def invoker(_p):
            calls["n"] += 1
            return "garbage" if calls["n"] == 1 else _sweep_json()

        run_foundational_logic_sweep("scope", invoker, run_logger=rl)
        assert [s[1] for s in rl.starts] == [1, 2]  # attempts 1 and 2
        assert all(s[0] == "foundational_sweep" for s in rl.starts)

    def test_no_run_logger_is_silent(self) -> None:
        # Without a run_logger, the call still works (no instrumentation).
        assert (
            run_foundational_logic_sweep("scope", lambda _p: _sweep_json())
            is not None
        )

    def test_split_proposal_call_instrumented(self) -> None:
        """``_propose_step_split``'s claude call was spent unrecorded: the
        caller brackets it with phase_start/phase_end but nothing bound a
        sink, so ``_emit_call_end`` no-opped. See BACKLOG #176-#178.

        Instrumentation fires before the response is parsed, so a garbage
        reply still pins it without coupling to the steps-JSON schema.
        """
        from plan_tool.create import _propose_step_split

        rl = _FakeRunLogger()
        _propose_step_split(
            Step(id=3, title="mixed step"), lambda _p: "garbage", run_logger=rl
        )
        # Phase matches the caller's phase_start("propose_step_split") so the
        # cost lands inside the phase that brackets it.
        assert rl.starts == [("propose_step_split", 1, {"step_id": 3})]
        assert rl.binds == [("propose_step_split", 1)]

    def test_split_proposal_without_run_logger_still_works(self) -> None:
        from plan_tool.create import _propose_step_split

        assert _propose_step_split(
            Step(id=1, title="x"), lambda _p: "garbage"
        ) is None


class TestMergeSweepIntoSteps:
    def _steps(self) -> list[Step]:
        return [
            Step(id=1, title="one", files=["plan_tool/a.py"]),
            Step(id=2, title="two"),
        ]

    def test_none_result_unchanged(self) -> None:
        steps = self._steps()
        assert merge_sweep_into_steps(steps, None) is steps

    def test_split_create_defer_does_not_expand_steps_or_files(
        self, tmp_path: Path
    ) -> None:
        steps = self._steps()
        result = SweepResult(
            logic="shared lifecycle",
            shared_locations=[
                SharedLocation(
                    path="plan_tool/shared.py",
                    relation="parallel-call-site",
                    recommendation="defer",
                    note="would change shared lifecycle semantics",
                    step_id=1,
                )
            ],
        )

        merged = merge_sweep_into_steps(steps, result, repo_root=tmp_path)

        assert merged == steps
        assert len(merged) == len(steps)
        assert merged[0].files == ["plan_tool/a.py"]
        assert merged[0].creates == []

    def test_deferred_consolidation_path_suppresses_a_consolidation_suggestion(
        self, tmp_path: Path
    ) -> None:
        result = SweepResult(
            logic="shared lifecycle",
            shared_locations=[
                SharedLocation(
                    path="plan_tool/shared.py",
                    recommendation="defer",
                    step_id=1,
                )
            ],
            consolidation=ConsolidationSuggestion(
                title="Consolidate shared lifecycle",
                files=["plan_tool/shared.py"],
                after_step_id=1,
            ),
        )

        merged = merge_sweep_into_steps(self._steps(), result, repo_root=tmp_path)

        assert merged == self._steps()

    def test_unrelated_defer_does_not_suppress_a_consolidation_suggestion(
        self, tmp_path: Path
    ) -> None:
        result = SweepResult(
            logic="shared lifecycle",
            shared_locations=[
                SharedLocation(
                    path="plan_tool/unrelated.py",
                    recommendation="defer",
                    step_id=1,
                )
            ],
            consolidation=ConsolidationSuggestion(
                title="Consolidate shared lifecycle",
                files=["plan_tool/shared.py"],
                after_step_id=1,
            ),
        )

        merged = merge_sweep_into_steps(self._steps(), result, repo_root=tmp_path)

        assert [step.title for step in merged] == [
            "one", "two", "Consolidate shared lifecycle"
        ]

    def test_update_in_place_appends_to_files_when_on_disk(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "plan_tool").mkdir()
        (tmp_path / "plan_tool" / "locator.py").write_text("x", encoding="utf-8")
        result = SweepResult(
            logic="root walk",
            shared_locations=[
                SharedLocation(
                    path="plan_tool/locator.py",
                    recommendation="update-in-place",
                    step_id=1,
                )
            ],
        )
        merged = merge_sweep_into_steps(
            self._steps(), result, repo_root=tmp_path
        )
        assert merged[0].files == ["plan_tool/a.py", "plan_tool/locator.py"]
        assert merged[0].creates == []

    def test_update_in_place_appends_to_creates_when_absent(
        self, tmp_path: Path
    ) -> None:
        result = SweepResult(
            logic="root walk",
            shared_locations=[
                SharedLocation(
                    path="plan_tool/new.py",
                    recommendation="update-in-place",
                    step_id=2,
                )
            ],
        )
        merged = merge_sweep_into_steps(
            self._steps(), result, repo_root=tmp_path
        )
        assert merged[1].creates == ["plan_tool/new.py"]

    def test_unknown_step_id_ignored(self, tmp_path: Path) -> None:
        result = SweepResult(
            logic="x",
            shared_locations=[
                SharedLocation(
                    path="z.py", recommendation="update-in-place", step_id=99
                )
            ],
        )
        merged = merge_sweep_into_steps(
            self._steps(), result, repo_root=tmp_path
        )
        assert merged == self._steps()

    def test_consolidation_appends_refactor_step(self, tmp_path: Path) -> None:
        result = SweepResult(
            logic="root walk",
            consolidation=ConsolidationSuggestion(
                title="Consolidate root walk",
                files=["plan_tool/locator.py"],
                after_step_id=1,
            ),
        )
        merged = merge_sweep_into_steps(
            self._steps(), result, repo_root=tmp_path
        )
        assert len(merged) == 3
        new = merged[-1]
        assert new.id == 3
        assert new.change_type == ChangeType.REFACTOR
        assert new.depends_on == [1]
        assert new.title == "Consolidate root walk"

    def test_consolidation_collapses_multiline_rationale(
        self, tmp_path: Path
    ) -> None:
        """A rationale spanning multiple lines (the model ignoring the
        prompt's "one line" ask) must collapse to a single line before it
        becomes ``intent`` — a raw newline in ``intent`` risks a ``##`` at
        line start inside frontmatter the plan format treats as
        authoritative (``scope_fence.collapse_intent_to_one_line``'s
        contract)."""
        result = SweepResult(
            logic="root walk",
            consolidation=ConsolidationSuggestion(
                title="Consolidate root walk",
                files=["plan_tool/locator.py"],
                after_step_id=1,
                rationale="dedup the walk\nacross both call sites",
            ),
        )
        merged = merge_sweep_into_steps(
            self._steps(), result, repo_root=tmp_path
        )
        assert merged[-1].intent == "dedup the walk across both call sites"

    def test_consolidation_collapses_multiline_intent(
        self, tmp_path: Path
    ) -> None:
        """The same multi-line-collapse contract applies when ``intent`` is
        the field actually taken — not just when the fallback lands on
        ``rationale``; the collapse happens after fallback selection, and a
        test only covering the fallback branch can't prove the direct
        branch collapses too."""
        result = SweepResult(
            logic="root walk",
            consolidation=ConsolidationSuggestion(
                title="Consolidate root walk",
                files=["plan_tool/locator.py"],
                after_step_id=1,
                rationale="a single source beats patching both call sites",
                intent="removes the duplicated rule\nfor good",
            ),
        )
        merged = merge_sweep_into_steps(
            self._steps(), result, repo_root=tmp_path
        )
        assert merged[-1].intent == "removes the duplicated rule for good"

    def test_consolidation_whitespace_only_intent_falls_back_to_rationale(
        self, tmp_path: Path
    ) -> None:
        """A whitespace-only ``intent`` (blank but non-empty, so bare ``or``
        truthiness would pick it) must not out-truthy a real ``rationale`` —
        it strips to nothing either way, so the fallback still fires."""
        result = SweepResult(
            logic="root walk",
            consolidation=ConsolidationSuggestion(
                title="Consolidate root walk",
                files=["plan_tool/locator.py"],
                after_step_id=1,
                rationale="a single source beats patching both call sites",
                intent="   ",
            ),
        )
        merged = merge_sweep_into_steps(
            self._steps(), result, repo_root=tmp_path
        )
        assert (
            merged[-1].intent == "a single source beats patching both call sites"
        )

    def test_consolidation_placeholder_intent_falls_back_to_rationale(
        self, tmp_path: Path
    ) -> None:
        """A placeholder ``intent`` ("TBD") is non-blank, so a bare
        blankness check would let it win over a genuinely usable
        ``rationale`` — the same three non-values (absent, blank, TBD/TODO)
        every other intent consumer treats as absent must apply here too
        (``review.is_usable_intent``'s shared contract)."""
        result = SweepResult(
            logic="root walk",
            consolidation=ConsolidationSuggestion(
                title="Consolidate root walk",
                files=["plan_tool/locator.py"],
                after_step_id=1,
                rationale="a single source beats patching both call sites",
                intent="TBD",
            ),
        )
        merged = merge_sweep_into_steps(
            self._steps(), result, repo_root=tmp_path
        )
        assert (
            merged[-1].intent == "a single source beats patching both call sites"
        )

    def test_consolidation_both_fields_placeholder_yields_none(
        self, tmp_path: Path
    ) -> None:
        """When neither field clears the usability bar, intent is None —
        not a placeholder string stored verbatim."""
        result = SweepResult(
            logic="root walk",
            consolidation=ConsolidationSuggestion(
                title="Consolidate root walk",
                files=["plan_tool/locator.py"],
                after_step_id=1,
                rationale="TODO",
                intent="TBD",
            ),
        )
        merged = merge_sweep_into_steps(
            self._steps(), result, repo_root=tmp_path
        )
        assert merged[-1].intent is None

    def test_consolidation_prefers_intent_over_rationale(
        self, tmp_path: Path
    ) -> None:
        """`ConsolidationSuggestion.intent` and `.rationale` answer different
        questions (why this step exists vs. why consolidation beats in-place
        patches); when the model supplies both, the consolidation step's
        `Step.intent` takes the field that actually matches its meaning."""
        result = SweepResult(
            logic="root walk",
            consolidation=ConsolidationSuggestion(
                title="Consolidate root walk",
                files=["plan_tool/locator.py"],
                after_step_id=1,
                rationale="a single source beats patching both call sites",
                intent="removes the duplicated validation rule for good",
            ),
        )
        merged = merge_sweep_into_steps(
            self._steps(), result, repo_root=tmp_path
        )
        assert (
            merged[-1].intent == "removes the duplicated validation rule for good"
        )

    def test_dedup_skips_already_declared_path(self, tmp_path: Path) -> None:
        (tmp_path / "plan_tool").mkdir()
        (tmp_path / "plan_tool" / "a.py").write_text("x", encoding="utf-8")
        result = SweepResult(
            logic="x",
            shared_locations=[
                SharedLocation(
                    path="plan_tool/a.py",
                    recommendation="update-in-place",
                    step_id=1,
                )
            ],
        )
        merged = merge_sweep_into_steps(
            self._steps(), result, repo_root=tmp_path
        )
        # Already in files → no duplicate, step returned unchanged.
        assert merged[0].files == ["plan_tool/a.py"]


class TestFormatBlock:
    def test_empty_placeholder(self) -> None:
        assert "no shared foundational logic" in format_foundational_logic_block(
            None
        )

    def test_renders_locations_and_consolidation(self) -> None:
        result = SweepResult(
            logic="path resolution",
            shared_locations=[
                SharedLocation(
                    path="plan_tool/locator.py",
                    anchor="resolve_root",
                    relation="duplicate",
                    recommendation="consolidate",
                    note="second copy",
                )
            ],
            consolidation=ConsolidationSuggestion(
                title="Consolidate root walk", rationale="one source"
            ),
        )
        block = format_foundational_logic_block(result)
        assert "path resolution" in block
        assert "plan_tool/locator.py" in block
        assert "resolve_root" in block
        assert "Consolidate root walk" in block
