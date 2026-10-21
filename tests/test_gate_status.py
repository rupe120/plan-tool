"""Saved gate selection and qualification invariants."""

from datetime import datetime, timezone
import json

import pytest

from plan_tool.gate_status import build_gate_status
from plan_tool.review_persistence import AuditInputSnapshot, plan_reports_dir, save_review


@pytest.fixture
def plan_path(tmp_path):
    path = tmp_path / '1-demo.md'
    path.write_text('---\ntitle: Demo\nstatus: planning\npriority: medium\nsteps:\n  - id: 1\n    title: First\n---\n# Plan\n')
    return path


def _save(path, *, day=1, grade='run', stage='bare', headline='clean',
          coverage='confirmed', revision_status='current', **kwargs):
    return save_review(
        plan_slug='demo', plan_path=path.name, repo_root=path.parent,
        report_md='report', recommendations=[], kind='completeness',
        now=datetime(2026, 10, day, tzinfo=timezone.utc),
        qualified_result={
            'headline': headline, 'stage': stage, 'coverage': coverage,
            'revision_status': revision_status,
            'audit_revision': AuditInputSnapshot.capture(path, path.parent, detail_grade=grade).revision,
        }, **kwargs,
    )


def _document(path, grade='run'):
    return build_gate_status(path, path.parent, detail_grade=grade, current_stage='bare')


@pytest.mark.parametrize('headline,coverage,revision_status,expected', [
    ('clean', 'confirmed', 'current', True),
    ('advisory-only', 'confirmed', 'current', True),
    ('awaiting-human-action', 'confirmed', 'current', False),
    ('clean', 'unconfirmed', 'current', False),
    ('clean', 'confirmed', 'stale', False),
    ('no-qualified-current-evidence', 'confirmed', 'current', False),
])
def test_converged_requires_current_confirmed_clean_or_advisory_result(
    plan_path, headline, coverage, revision_status, expected,
):
    report = _save(plan_path, headline=headline, coverage=coverage, revision_status=revision_status)
    result = _document(plan_path)['stages']['bare']
    saved = json.loads(report.read_text())['qualified_result']
    assert result['headline'] == saved['headline']
    assert result['coverage'] == saved['coverage']
    assert result['converged'] is expected
    assert result['confirmation_kind'] is None


def test_plan_edit_invalidates_a_saved_clean_result_without_mutating_it(plan_path):
    report = _save(plan_path)
    before = report.read_bytes()
    plan_path.write_text(plan_path.read_text() + '\nChanged intent\n')
    result = _document(plan_path)['stages']['bare']
    assert result['view_revision_status'] == 'stale'
    assert result['revision_status'] == 'current'
    assert result['converged'] is False
    assert report.read_bytes() == before


def test_reader_never_substitutes_a_foreign_grade_sidecar(plan_path):
    run = _save(plan_path)
    jira = _save(plan_path, day=2, grade='jira', headline='awaiting-human-action')
    assert _document(plan_path)['stages']['bare']['report'] == run.stem
    assert _document(plan_path, 'jira')['stages']['bare']['report'] == jira.stem
    assert _document(plan_path, 'jira')['stages']['bare']['converged'] is False


def test_newest_per_stage_wins_even_when_older_report_matches_current_files(plan_path):
    original = plan_path.read_text()
    _save(plan_path)
    plan_path.write_text(original + '\nTemporary change\n')
    newest = _save(plan_path, day=2)
    plan_path.write_text(original)
    result = _document(plan_path)['stages']['bare']
    assert result['report'] == newest.stem
    assert result['converged'] is False


def test_each_stage_retains_its_own_latest_result(plan_path):
    bare = _save(plan_path)
    detail = _save(plan_path, day=2, stage='detail')
    stages = _document(plan_path)['stages']
    assert stages['bare']['report'] == bare.stem
    assert stages['detail']['report'] == detail.stem


def test_checkpoint_legacy_and_malformed_reports_supply_no_stage_verdict(plan_path):
    final = _save(plan_path)
    raw = json.loads(final.read_text())
    raw['is_pre_apply_checkpoint'] = True
    raw['qualified_result'] = None
    final.write_text(json.dumps(raw))
    save_review(plan_slug='demo', plan_path=plan_path.name, repo_root=plan_path.parent,
                report_md='legacy', recommendations=[], kind='completeness',
                now=datetime(2026, 10, 2, tzinfo=timezone.utc))
    (plan_reports_dir(plan_path) / '9999-malformed.json').write_text('{')
    assert _document(plan_path)['stages'] == {'bare': None, 'detail': None}


def test_detail_edit_invalidates_detail_grade_result(plan_path):
    plan_path.write_text(plan_path.read_text().replace('    title: First', '    title: First\n    detail: detail.md'))
    detail = plan_path.parent / 'detail.md'
    detail.write_text('# Original\n')
    _save(plan_path, stage='detail')
    assert _document(plan_path)['stages']['detail']['converged'] is True
    detail.write_text('# Changed\n')
    result = _document(plan_path)['stages']['detail']
    assert result['view_revision_status'] == 'stale'
    assert result['converged'] is False


def test_confirmation_kind_is_delivered_from_coverage_without_inference(plan_path):
    _save(plan_path, audit_coverage={
        'budget_limited': False, 'passes_used': 2, 'cap': 3,
        'recommendation_kind': None, 'recommended_passes': None,
        'recommendation_advice': None, 'confirmation_kind': 'confirmed-low-yield',
        'conforming_pass_count': 2, 'failed_or_malformed_pass_count': 0,
    })
    assert _document(plan_path)['stages']['bare']['confirmation_kind'] == 'confirmed-low-yield'


def test_corrupt_and_nonfinal_newer_reports_do_not_hide_final_evidence(plan_path):
    final = _save(plan_path)
    newer = _save(plan_path, day=2)
    raw = json.loads(newer.read_text())
    raw['is_pre_apply_checkpoint'] = True
    raw['qualified_result'] = None
    newer.write_text(json.dumps(raw))
    (plan_reports_dir(plan_path) / '9999-corrupt.json').write_text('{')
    assert _document(plan_path)['stages']['bare']['report'] == final.stem


@pytest.mark.parametrize("unavailable", ["unknown-role", "not-sampled"])
def test_unknown_role_and_not_sampled_reports_cannot_replace_a_final_result(
    plan_path, unavailable,
):
    final = _save(plan_path)
    newer = _save(plan_path, day=2)
    payload = json.loads(newer.read_text())
    if unavailable == "unknown-role":
        payload["is_pre_apply_checkpoint"] = "false"
    else:
        payload["qualified_result"] = {
            "headline": "no-qualified-current-evidence",
            "stage": "not-sampled", "coverage": "not-sampled",
            "revision_status": "not-sampled", "audit_revision": None,
        }
    newer.write_text(json.dumps(payload))
    assert _document(plan_path)["stages"]["bare"]["report"] == final.stem


def test_markdown_only_audit_does_not_replace_the_last_saved_final_result(plan_path):
    from plan_tool.completeness_report import write_completeness_report

    final = _save(plan_path)
    markdown = write_completeness_report(
        plan_path, "# Audit without final sidecar\n", repo_root=plan_path.parent,
        recommendations=None, now=datetime(2026, 10, 2, tzinfo=timezone.utc),
    )
    assert not markdown.with_suffix(".json").exists()
    assert _document(plan_path)["stages"]["bare"]["report"] == final.stem
