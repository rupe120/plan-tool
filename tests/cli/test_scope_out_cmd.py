"""CLI-integration tests for ``plan-tool scope-out --through`` — driving
``main([...])`` through the real parse → dispatch → command path.

The ``--through M`` flag carves the inclusive ``N..M`` region (from ``--step
N``) in one atomic carve, writing a single forward-seed; ``--step`` alone is
the unchanged single-step path. These tests need a **multi-step** plan, which
``CliRepo.add_plan`` does not build, so the repo + manifest are assembled by
hand (mirroring ``tests/test_scope_out.py``'s ``_register_plan`` helper)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
import yaml

from plan_tool.parser import _coerce_enums, parse_plan
from plan_tool.concept_tree import (
    ConceptNode,
    ConceptTree,
    concept_id,
    concepts_path,
    load_concepts,
    save_concepts,
)
from plan_tool.review_persistence import compute_plan_fingerprint
from plan_tool.schema import Plan, PlanStatus, Priority, Step, StepStatus


def _mk_step(step_id: int, title: str | None = None, **kwargs) -> Step:
    return Step(id=step_id, title=title or f"Step {step_id}", **kwargs)


def _five_step_plan() -> Plan:
    # Carving any contiguous slice of 2..4 is safe: only survivor 5 depends on
    # the DONE survivor 1, nothing depends on a carved step, all-pending.
    return Plan(
        title="Spinning Plan",
        status=PlanStatus.PLANNING,
        priority=Priority.MEDIUM,
        steps=[
            _mk_step(1, "First"),
            _mk_step(2, "Second"),
            _mk_step(3, "Third"),
            _mk_step(4, "Fourth"),
            _mk_step(5, "Fifth", depends_on=[1]),
        ],
    )


def _write_plan_file(tmp_path: Path, plan: Plan, name: str = "2-spin.md") -> Path:
    dumped = _coerce_enums(plan.model_dump(exclude_defaults=True, exclude_none=True))
    fm = yaml.safe_dump(
        dumped, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    path = tmp_path / name
    path.write_text(
        f"---\n{fm}---\n\nPlan prose body that survives narrowing.\n",
        encoding="utf-8",
    )
    return path


def _register_plan(tmp_path: Path, plan: Plan, name: str = "2-spin.md"):
    path = _write_plan_file(tmp_path, plan, name=name)
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"plans": [name]}), encoding="utf-8")
    return path, manifest


def _scope_out_argv(tmp_path: Path, manifest: Path, *rest: str) -> list[str]:
    return [
        "--repo-root",
        str(tmp_path),
        "--manifest",
        str(manifest),
        "scope-out",
        *rest,
    ]


def _seed_files(tmp_path: Path) -> list[Path]:
    d = tmp_path / "plan-seeds"
    return sorted(d.glob("*.md")) if d.is_dir() else []


def _save_concepts(plan_path: Path, *titles: str) -> dict[str, str]:
    ids = {title: concept_id(title, []) for title in titles}
    save_concepts(
        plan_path,
        ConceptTree(
            plan_slug="spin",
            plan_fingerprint=compute_plan_fingerprint(plan_path),
            concepts=[
                ConceptNode(
                    id=ids[title],
                    title=title,
                    order=order,
                    decision="include",
                    review_state="approved",
                )
                for order, title in enumerate(titles)
            ],
        ),
    )
    return ids


@pytest.mark.integration
class TestScopeOutThroughCLI:
    def test_apply_yes_defers_last_owned_concept(self, tmp_path):
        from plan_tool.cli.app import main

        owned = concept_id("Owned", [])
        plan = _five_step_plan()
        plan.steps[1].concept_ids = [owned]
        path, manifest = _register_plan(tmp_path, plan)
        _save_concepts(path, "Owned")

        rc = main(
            _scope_out_argv(
                tmp_path, manifest, "2-spin", "--step", "2", "--apply", "-y"
            )
        )

        assert rc == 0
        tree = load_concepts(path, compute_plan_fingerprint(path))
        assert tree.concepts[0].decision == "defer"

    def test_apply_yes_keeps_shared_concept_included(self, tmp_path):
        from plan_tool.cli.app import main

        shared = concept_id("Shared", [])
        plan = _five_step_plan()
        plan.steps[0].concept_ids = [shared]
        plan.steps[1].concept_ids = [shared]
        path, manifest = _register_plan(tmp_path, plan)
        _save_concepts(path, "Shared")

        rc = main(
            _scope_out_argv(
                tmp_path, manifest, "2-spin", "--step", "2", "--apply", "-y"
            )
        )

        assert rc == 0
        tree = load_concepts(path, compute_plan_fingerprint(path))
        assert tree.concepts[0].decision == "include"

    def test_through_defers_only_concepts_with_no_owner_outside_region(
        self, tmp_path
    ):
        from plan_tool.cli.app import main

        ownerless = concept_id("Ownerless", [])
        shared = concept_id("Shared", [])
        plan = _five_step_plan()
        plan.steps[0].concept_ids = [shared]
        plan.steps[1].concept_ids = [ownerless, shared]
        plan.steps[2].concept_ids = [ownerless]
        path, manifest = _register_plan(tmp_path, plan)
        _save_concepts(path, "Ownerless", "Shared")

        rc = main(
            _scope_out_argv(
                tmp_path,
                manifest,
                "2-spin",
                "--step",
                "2",
                "--through",
                "3",
                "--apply",
                "-y",
            )
        )

        assert rc == 0
        tree = load_concepts(path, compute_plan_fingerprint(path))
        decisions = {node.title: node.decision for node in tree.concepts}
        assert decisions == {"Ownerless": "defer", "Shared": "include"}

    def test_recommend_only_leaves_concept_record_unchanged(self, tmp_path):
        from plan_tool.cli.app import main

        owned = concept_id("Owned", [])
        plan = _five_step_plan()
        plan.steps[1].concept_ids = [owned]
        path, manifest = _register_plan(tmp_path, plan)
        _save_concepts(path, "Owned")
        before = concepts_path(path).read_text(encoding="utf-8")

        rc = main(
            _scope_out_argv(tmp_path, manifest, "2-spin", "--step", "2")
        )

        assert rc == 0
        assert concepts_path(path).read_text(encoding="utf-8") == before
        assert not _seed_files(tmp_path)

    def test_through_carves_region_and_narrows_plan(self, tmp_path):
        from plan_tool.cli.app import main

        path, manifest = _register_plan(tmp_path, _five_step_plan())

        rc = main(
            _scope_out_argv(
                tmp_path, manifest, "2-spin",
                "--step", "2", "--through", "4", "--apply", "-y",
            )
        )
        assert rc == 0

        # Exactly one region seed, and steps 2..4 gone from the plan.
        assert len(_seed_files(tmp_path)) == 1
        narrowed = parse_plan(path)
        assert [s.id for s in narrowed.steps] == [1, 2]
        assert [s.title for s in narrowed.steps] == ["First", "Fifth"]
        by_id = {s.id: s for s in narrowed.steps}
        assert by_id[2].depends_on == [1]  # old 5 dep on survivor 1 unchanged

    def test_through_out_of_order_is_rejected(self, tmp_path, capsys):
        from plan_tool.cli.app import main

        path, manifest = _register_plan(tmp_path, _five_step_plan())
        before = path.read_text(encoding="utf-8")

        rc = main(
            _scope_out_argv(
                tmp_path, manifest, "2-spin",
                "--step", "4", "--through", "2", "--apply", "-y",
            )
        )
        assert rc != 0  # usage error
        assert not _seed_files(tmp_path)
        assert path.read_text(encoding="utf-8") == before
        assert "ordered" in capsys.readouterr().err

    def test_through_equal_to_step_is_single_step(self, tmp_path):
        from plan_tool.cli.app import main

        path, manifest = _register_plan(tmp_path, _five_step_plan())

        rc = main(
            _scope_out_argv(
                tmp_path, manifest, "2-spin",
                "--step", "2", "--through", "2", "--apply", "-y",
            )
        )
        assert rc == 0
        seeds = _seed_files(tmp_path)
        assert len(seeds) == 1
        # A single-id range takes the single-step seed path, not a range name.
        assert seeds[0].name == "spin-carved-second.md"
        narrowed = parse_plan(path)
        assert [s.title for s in narrowed.steps] == [
            "First", "Third", "Fourth", "Fifth",
        ]

    def test_step_only_unchanged(self, tmp_path):
        from plan_tool.cli.app import main

        path, manifest = _register_plan(tmp_path, _five_step_plan())

        rc = main(
            _scope_out_argv(
                tmp_path, manifest, "2-spin", "--step", "2", "--apply", "-y"
            )
        )
        assert rc == 0
        seeds = _seed_files(tmp_path)
        assert len(seeds) == 1
        assert seeds[0].name == "spin-carved-second.md"
        narrowed = parse_plan(path)
        assert [s.id for s in narrowed.steps] == [1, 2, 3, 4]
        assert "Second" not in [s.title for s in narrowed.steps]

    def test_through_recommend_only_by_default(self, tmp_path, capsys):
        from plan_tool.cli.app import main

        path, manifest = _register_plan(tmp_path, _five_step_plan())
        before = path.read_text(encoding="utf-8")

        rc = main(
            _scope_out_argv(
                tmp_path, manifest, "2-spin", "--step", "2", "--through", "3"
            )
        )
        assert rc == 0
        assert not _seed_files(tmp_path)
        assert path.read_text(encoding="utf-8") == before
        captured = capsys.readouterr()
        text = captured.out + captured.err
        # The recommend hint carries the range form the operator asked for.
        assert "--through 3" in text
        assert "steps 2..3" in text

    def test_through_past_last_step_is_step_missing(self, tmp_path, capsys):
        from plan_tool.cli.app import main

        path, manifest = _register_plan(tmp_path, _five_step_plan())
        before = path.read_text(encoding="utf-8")

        rc = main(
            _scope_out_argv(
                tmp_path, manifest, "2-spin",
                "--step", "3", "--through", "9", "--apply", "-y",
            )
        )
        assert rc == 0  # a refusal is not a failure-to-complete
        assert not _seed_files(tmp_path)
        assert path.read_text(encoding="utf-8") == before
        captured = capsys.readouterr()
        assert "no step with that id" in captured.out + captured.err

    def test_region_seed_round_trips_through_create_from_existing(self, tmp_path):
        from plan_tool.cli.app import main
        from plan_tool.create import create_plan, read_existing_description

        path, manifest = _register_plan(tmp_path, _five_step_plan())

        rc = main(
            _scope_out_argv(
                tmp_path, manifest, "2-spin",
                "--step", "2", "--through", "3", "--apply", "-y",
            )
        )
        assert rc == 0
        seed_path = _seed_files(tmp_path)[0]

        canned = json.dumps(
            [{"title": "re-plan the carved region", "complexity": "low",
              "files": [], "depends_on": []}]
        )

        def prepared_seed_invoker(prompt: str) -> str:
            if "Distill a free-form seed into a canonical plan body" not in prompt:
                return canned
            evidence_line = next(
                int(number)
                for raw_line in prompt.splitlines()
                if (number := raw_line.partition("\t")[0]).isdigit()
                and (source_line := raw_line.partition("\t")[2]).strip()
                and not source_line.lstrip().startswith(("#", "---"))
            )
            return json.dumps(
                {
                    "outcome": "single",
                    "sections": {
                        "Overview": "Prepared overview.",
                        "Problem statement": "Prepared problem.",
                        "Architecture": "Prepared architecture.",
                        "Out of scope": "candidate",
                        "Risks": "candidate",
                        "Testing": "candidate",
                        "Acceptance criteria": "candidate",
                        "Deferred": "candidate",
                    },
                    "evidence_spans": {
                        key: [{"start_line": evidence_line, "end_line": evidence_line}]
                        for key in (
                            "Out of scope",
                            "Risks",
                            "Testing",
                            "Acceptance criteria",
                            "Deferred",
                        )
                    },
                }
            )

        out_dir = tmp_path / "replanned"
        out_dir.mkdir()
        seed_text = read_existing_description(seed_path)
        result = create_plan(
            "recarve",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=tmp_path / "recarve-m.json",
            from_description=seed_text,
            from_existing_path=seed_path,
            seed_body=seed_text,
            claude_invoker=prepared_seed_invoker,
            yes=True,
            synthesize_body=False,
            fetch_docs=False,
            distill=False,
            resume=False,
            allow_placeholder_body=True,
        )
        assert result.plan_path.is_file()
        replanned = parse_plan(result.plan_path)
        assert [s.title for s in replanned.steps] == ["re-plan the carved region"]

    def test_scope_out_help_lists_through(self):
        from plan_tool.cli.app import build_parser

        parser = build_parser()
        sub = None
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                sub = action.choices["scope-out"]
        assert sub is not None
        flags = {opt for a in sub._actions for opt in a.option_strings}
        assert "--through" in flags
