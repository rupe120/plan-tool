"""The jira-ticket lint's Seed:/Plan: lines: the archive clause and the Plan pointer."""

import importlib.util
from pathlib import Path

LINT_PATH = Path(__file__).resolve().parents[1] / ".claude/skills/jira-ticket/lint_ticket.py"
_spec = importlib.util.spec_from_file_location("lint_ticket", LINT_PATH)
lint_ticket = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint_ticket)

CLAUSE = (
    " — authored here; `create` archives it under `plan-seeds/archive/` as "
    "`{name}.replaced[.N].md`"
)
PLAN_ROUTE = (
    "Route: plan — start with `plan-tool create --from-existing plan-seeds/a.md`, "
    "then `plan-tool detail` per step."
)
DIRECT_ROUTE = "Route: direct — implement directly; no plan-tool create/detail/run."


def ticket(route_block: str, example: str = "**Example**\n\nRun X; it prints Y.\n\n") -> str:
    return f"""**Summary**

s

Source: BACKLOG #1

{route_block}

{example}**Change**

* x

**Out of scope:** none

**Stop / defer:** none

**Done when:** y

**Why this tier**

`architect`: z
"""


def run(route_block: str, **kwargs):
    _words, errors, warns = lint_ticket.lint(ticket(route_block, **kwargs), "architect", None)
    return errors, warns


def seed_line(name="a", clause=True):
    return f"Seed: `plan-seeds/{name}.md`" + (CLAUSE.format(name=name) if clause else "")


PLAN_LINE = "Plan: `docs/implementation-plans/2-a.md`"


def test_seed_with_archive_clause_and_plan_line_is_clean():
    errors, warns = run(f"{PLAN_ROUTE}\n{seed_line()}\n{PLAN_LINE}")
    assert (errors, warns) == ([], [])


def test_legacy_seed_without_archive_clause_warns_and_does_not_error():
    # Live tickets written before the clause existed must keep linting as warnings only.
    errors, warns = run(f"{PLAN_ROUTE}\n{seed_line(clause=False)}")
    assert errors == []
    assert any("no archive clause" in w for w in warns)


def test_archive_clause_naming_a_different_seed_is_an_error():
    bad = f"Seed: `plan-seeds/a.md`{CLAUSE.format(name='b')}"
    errors, _ = run(f"{PLAN_ROUTE}\n{bad}")
    assert any("different seed" in e for e in errors)


def test_plan_line_must_follow_the_seed_line_immediately():
    errors, _ = run(f"{PLAN_ROUTE}\n{PLAN_LINE}\n{seed_line()}")
    assert any('"Plan:" must sit immediately after the "Seed:"' in e for e in errors)


def test_two_plan_lines_are_an_error():
    errors, _ = run(f"{PLAN_ROUTE}\n{seed_line()}\n{PLAN_LINE}\n{PLAN_LINE}")
    assert any("at most one" in e for e in errors)


def test_plan_line_outside_docs_implementation_plans_is_an_error():
    errors, _ = run(f"{PLAN_ROUTE}\n{seed_line()}\nPlan: `plan-seeds/a.md`")
    assert any('"Plan:" line is not' in e for e in errors)


def test_direct_route_rejects_seed_and_plan_lines():
    seed_errors, _ = run(f"{DIRECT_ROUTE}\n{seed_line()}")
    plan_errors, _ = run(f"{DIRECT_ROUTE}\n{PLAN_LINE}")
    assert any('"Seed:" line is present' in e for e in seed_errors)
    assert any('"Plan:" line is present' in e for e in plan_errors)


def test_seed_outside_plan_seeds_is_an_error():
    errors, _ = run(f"{PLAN_ROUTE}\nSeed: `docs/a.md`")
    assert any('"Seed:" line is not' in e for e in errors)


def test_ticket_without_example_warns_and_does_not_error():
    # Tickets written before the Example section existed must keep linting as warnings only.
    errors, warns = run(f"{PLAN_ROUTE}\n{seed_line()}", example="")
    assert errors == []
    assert any('no "Example" section' in w for w in warns)


def test_example_after_change_is_an_error():
    body = ticket(f"{PLAN_ROUTE}\n{seed_line()}", example="") + "\n**Example**\n\nlate\n"
    _words, errors, _warns = lint_ticket.lint(body, "architect", None)
    assert any('"Example" must sit between the Summary and Change' in e for e in errors)


def test_empty_example_is_an_error():
    errors, _ = run(f"{PLAN_ROUTE}\n{seed_line()}", example="**Example**\n\n")
    assert any('section "Example" is empty' in e for e in errors)


def test_word_cap_is_300_without_an_example_and_500_with_one():
    filler = "word " * 350
    _w, _e, without = lint_ticket.lint(
        ticket(f"{PLAN_ROUTE}\n{seed_line()}", example="") + filler, "architect", None
    )
    _w, _e, with_example = lint_ticket.lint(
        ticket(f"{PLAN_ROUTE}\n{seed_line()}") + filler, "architect", None
    )
    assert any("over 300" in w for w in without)
    assert not any("words; over" in w for w in with_example)
