"""Run-log coverage of Claude call sites and the ``prompt_sha256`` field.

Both checks read source with ``ast``: a call site that stops binding a sink, or
a ``claude_call_start`` that drops the hash, fails here instead of silently
shrinking the token ledger. Invokers stay neutralized — nothing is spawned.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

import pytest

from plan_tool.run_log import RunLogWriter, hash_prompt

PKG = Path(__file__).resolve().parent.parent / "plan_tool"

# Sites that write a start/end pair (or bind the sink that writes the end).
# \b keeps ``uninstall_call_end_sink`` from satisfying ``install_call_end_sink``.
SINK_RE = re.compile(r"\b(bind_shell_sink|install_call_end_sink|_emit_claude_call_end)\b")
LOGGED_SITES = [
    ("launcher.py", "apply_finding"),
    ("create.py", "assess_direct_source_split_from_claude"),
    ("create.py", "_propose_risk_profile_from_seed"),
    ("create.py", "propose_steps_from_claude"),
    ("create.py", "propose_references_from_claude"),
    ("create.py", "propose_body_sections"),
    ("detail.py", "_author_step_detail"),
    ("detail.py", "collect_detail_quality_findings"),
    ("review.py", "audit_plan_until_stable"),
    ("gates.py", "suggest_gates"),
]

# Sites that stay unlogged: no RunLogWriter is reachable from the function or
# its callers' signatures, so wiring one means widening public signatures and
# every CLI caller. Filed in BUG_BACKLOG.md. Each entry must not mention a
# sink call; wiring one moves it to LOGGED_SITES.
DEFERRED_SITES = {
    ("create.py", "suggest_slug"): "no run_logger parameter",
    ("review.py", "check_criteria_fulfillment"): "no run_logger parameter",
    ("review.py", "review_plan_full"): "no run_logger parameter",
    ("review.py", "extract_and_append_review_lessons"): "no run_logger parameter",
    ("jira.py", "render_jira_export"): "no run_logger parameter",
    ("annotate.py", "classify_plan_implementation"): "no run_logger parameter",
    ("lessons.py", "find_lesson_equivalences"): "no run_logger parameter",
    ("concept_tree.py", "emit_concept_tree"): "no run_logger parameter",
    ("launcher.py", "_run_deep_for_step"): "no run_logger parameter",
    ("launcher.py", "run_all_done_steps"): "no run_logger parameter",
}


def _function_source(filename: str, name: str) -> str:
    text = (PKG / filename).read_text()
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"{filename}:{name} not found — update the site list")


@pytest.mark.parametrize(("filename", "name"), LOGGED_SITES)
def test_logged_call_site_binds_a_call_end_sink(filename: str, name: str) -> None:
    source = _function_source(filename, name)
    assert SINK_RE.search(source), (
        f"{filename}:{name} no longer writes a claude_call_end; "
        "its tokens vanish from the run log"
    )


@pytest.mark.parametrize(("filename", "name"), sorted(DEFERRED_SITES))
def test_deferred_site_is_still_unlogged_so_the_list_stays_honest(
    filename: str, name: str
) -> None:
    source = _function_source(filename, name)
    assert not SINK_RE.search(source), (
        f"{filename}:{name} now logs; move it from DEFERRED_SITES to LOGGED_SITES"
    )


def _claude_call_start_calls(path: Path) -> list[ast.Call]:
    tree = ast.parse(path.read_text())
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "claude_call_start"
    ]


@pytest.mark.parametrize(
    "path",
    sorted(
        p
        for p in PKG.rglob("*.py")
        if p.name != "run_log.py" and _claude_call_start_calls(p)
    ),
    ids=lambda p: str(p.relative_to(PKG)),
)
def test_every_claude_call_start_carries_the_prompt_hash(path: Path) -> None:
    missing = [
        call.lineno
        for call in _claude_call_start_calls(path)
        if "prompt_sha256" not in {kw.arg for kw in call.keywords}
    ]
    assert not missing, f"{path.name} claude_call_start without prompt_sha256 at lines {missing}"


def test_call_start_records_hash_of_prompt_never_its_text(tmp_path: Path) -> None:
    prompt = "secret prompt body"
    writer = RunLogWriter.start(
        repo_root=tmp_path, slug="demo", command="run", argv=["plan-tool", "run"]
    )
    log = writer.log_path
    writer.claude_call_start("p", 1, len(prompt), prompt_sha256=hash_prompt(prompt))
    writer.claude_call_start("p", 2, len(prompt))
    starts = [
        e
        for e in (json.loads(line) for line in log.read_text().splitlines())
        if e["event"] == "claude_call_start"
    ]
    first, second = starts
    assert first["prompt_sha256"] == hashlib.sha256(prompt.encode()).hexdigest()
    assert second["prompt_sha256"] is None  # caller supplied none: explicit null
    assert prompt not in log.read_text()


def test_every_create_call_end_sink_has_a_matching_call_start() -> None:
    """A bound end sink without a same-(phase, attempt) start leaves an orphan end in the ledger (repair attempts did this)."""
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "plan_tool" / "create.py"

    def key(call: ast.Call, default_attempt: int | None):
        kw = {k.arg: k.value for k in call.keywords}
        if not isinstance(kw.get("phase"), (ast.Constant, ast.Name)):
            return None
        phase = ast.unparse(kw["phase"])
        attempt = kw["attempt"].value if isinstance(kw.get("attempt"), ast.Constant) else default_attempt
        return (phase, attempt)

    orphans = []
    for fn in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        sinks, starts = [], set()
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "install_call_end_sink":
                    k = key(node, 1)
                    if k:
                        sinks.append((k, node.lineno))
                elif node.func.attr in {"claude_call_start", "start_step"}:
                    k = key(node, 1)
                    if k:
                        starts.add(k)
        orphans += [f"{fn.name}:{line} {k}" for k, line in sinks if k not in starts]
    assert orphans == []


def test_audit_pass_end_records_ids_not_text_and_old_events_stay_valid(
    tmp_path: Path,
) -> None:
    writer = RunLogWriter.start(
        repo_root=tmp_path, slug="demo", command="run", argv=["plan-tool", "run"]
    )
    writer.audit_pass_end(
        pass_number=2, cap=3, outcome="conforming",
        new_ids=["a1"], material_new_ids=[], unique_so_far=4,
    )
    ev = [
        e
        for e in (json.loads(line) for line in writer.log_path.read_text().splitlines())
        if e["event"] == "audit_pass_end"
    ]
    assert ev == [
        {
            **ev[0],
            "pass_number": 2, "cap": 3, "outcome": "conforming",
            "new_ids": ["a1"], "material_new_ids": [], "unique_so_far": 4,
        }
    ]


def test_audit_pass_end_caps_id_lists_but_keeps_exact_counts(tmp_path: Path) -> None:
    """A huge pass must not overflow the 4 KB line cap and abort the audit."""
    writer = RunLogWriter.start(
        repo_root=tmp_path, slug="demo", command="run", argv=["plan-tool", "run"]
    )
    ids = [f"step1-plan-completeness-{i:08x}" for i in range(500)]
    writer.audit_pass_end(
        pass_number=1, cap=3, outcome="conforming",
        new_ids=ids, material_new_ids=ids[:200], unique_so_far=500,
    )
    ev = next(
        e
        for e in (json.loads(line) for line in writer.log_path.read_text().splitlines())
        if e["event"] == "audit_pass_end"
    )
    assert (ev["new_count"], ev["material_new_count"]) == (500, 200)
    assert len(ev["new_ids"]) == len(ev["material_new_ids"]) == 40
