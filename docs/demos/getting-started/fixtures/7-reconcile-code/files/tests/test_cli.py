from datetime import date

import pytest

from todo import store
from todo.cli import main
from todo.model import Task

TODAY = date(2026, 2, 1)


def test_add_list_done(tmp_path, capsys):
    path = tmp_path / "t.json"
    assert main(["add", "write"], path=path) == 0
    assert main(["done", "1"], path=path) == 0
    assert main(["list"], path=path) == 0
    assert "1 [x] write" in capsys.readouterr().out


def test_done_unknown_id_fails(tmp_path):
    assert main(["done", "9"], path=tmp_path / "t.json") == 1


def test_add_with_due_stores_the_date(tmp_path):
    path = tmp_path / "t.json"
    assert main(["add", "x", "--due", "2026-01-31"], path=path) == 0
    assert store.load(path)[0].due == date(2026, 1, 31)


def test_add_with_malformed_due_is_refused_and_writes_nothing(tmp_path):
    path = tmp_path / "t.json"
    with pytest.raises(SystemExit) as exc:
        main(["add", "x", "--due", "31/01/2026"], path=path)
    assert exc.value.code == 2
    assert not path.exists()


def test_overdue_lists_only_open_tasks_strictly_past_due(tmp_path, capsys):
    path = tmp_path / "t.json"
    store.save(path, [
        Task(1, "late", due=date(2026, 1, 31)),
        Task(2, "late but done", done=True, due=date(2026, 1, 31)),
        Task(3, "no date"),
        Task(4, "due today", due=TODAY),
        Task(5, "due later", due=date(2026, 3, 1)),
    ])
    assert main(["list", "--overdue"], path=path, today=TODAY) == 0
    out = capsys.readouterr().out
    assert "late" in out and "late but done" not in out
    assert "no date" not in out and "due today" not in out and "due later" not in out


def test_list_shows_due_date_only_when_set(tmp_path, capsys):
    path = tmp_path / "t.json"
    store.save(path, [Task(1, "dated", due=date(2026, 1, 31)), Task(2, "plain")])
    main(["list"], path=path, today=TODAY)
    lines = capsys.readouterr().out.splitlines()
    assert lines == ["1 [ ] dated (due 2026-01-31)", "2 [ ] plain"]
