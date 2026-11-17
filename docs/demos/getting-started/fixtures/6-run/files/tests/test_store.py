import json
from datetime import date

from todo import store
from todo.model import Task


def test_round_trip(tmp_path):
    path = tmp_path / "t.json"
    store.save(path, [Task(1, "a"), Task(2, "b", done=True)])
    assert store.load(path) == [Task(1, "a"), Task(2, "b", done=True)]


def test_missing_file_is_empty(tmp_path):
    assert store.load(tmp_path / "nope.json") == []


def test_due_date_round_trips(tmp_path):
    path = tmp_path / "t.json"
    store.save(path, [Task(1, "a", due=date(2026, 1, 31))])
    assert store.load(path)[0].due == date(2026, 1, 31)


def test_task_without_due_writes_no_due_key(tmp_path):
    path = tmp_path / "t.json"
    store.save(path, [Task(1, "a")])
    assert "due" not in json.loads(path.read_text())[0]


def test_legacy_file_without_due_loads_as_none(tmp_path):
    path = tmp_path / "t.json"
    path.write_text(json.dumps([{"id": 1, "title": "old", "done": False}]))
    assert store.load(path) == [Task(1, "old", done=False, due=None)]
