"""Public CLI contract for reading saved gate verdicts."""

import json

import pytest

from plan_tool.cli import main


@pytest.mark.integration
class TestGateStatusReadOnlyJson:
    def test_gate_status_emits_run_grade_versioned_json_without_creating_state(self, registered_plan, capsys):
        repo = registered_plan
        before = {p.relative_to(repo.root): p.read_bytes() for p in repo.root.rglob('*') if p.is_file()}
        assert main(repo.argv('gate-status', 'demo', '--json')) == 0
        document = json.loads(capsys.readouterr().out)
        assert document == {
            'version': 1, 'plan': 'demo', 'plan_path': 'plans/1-demo.md',
            'current_stage': 'bare',
            'stages': {'bare': None, 'detail': None},
        }
        after = {p.relative_to(repo.root): p.read_bytes() for p in repo.root.rglob('*') if p.is_file()}
        assert after == before

@pytest.mark.integration
def test_unparseable_plan_has_unknown_current_stage(registered_plan, capsys):
    plan = registered_plan.plans_dir / "1-demo.md"
    plan.write_text("---\ninvalid: [\n")
    assert main(registered_plan.argv("gate-status", "demo")) == 0
    assert json.loads(capsys.readouterr().out)["current_stage"] is None


@pytest.mark.integration
def test_unresolvable_plan_is_a_command_error(registered_plan, capsys):
    assert main(registered_plan.argv("gate-status", "missing-plan")) != 0
    assert capsys.readouterr().out == ""


@pytest.mark.integration
def test_external_plans_directory_preserves_absolute_plan_path(registered_plan, capsys):
    repo = registered_plan
    source = repo.plans_dir / "1-demo.md"
    directory = repo.root.parent / f"{repo.root.name}-external"
    directory.mkdir()
    external = directory / "1-outside.md"
    external.write_bytes(source.read_bytes())
    assert main(repo.argv(
        "--plans-dir", str(directory), "gate-status", "outside", "--json"
    )) == 0
    assert json.loads(capsys.readouterr().out)["plan_path"] == str(external)


@pytest.mark.integration
class TestRunGradeGateStatusWiring:
    def test_gate_status_rejects_removed_grade_selector(self, registered_plan, capsys):
        with pytest.raises(SystemExit) as caught:
            main(registered_plan.argv("gate-status", "demo", "--grade", "jira"))
        assert caught.value.code == 2
        assert "unrecognized arguments: --grade jira" in capsys.readouterr().err
