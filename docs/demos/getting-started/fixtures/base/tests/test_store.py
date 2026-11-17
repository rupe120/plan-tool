from todo import store
from todo.model import Task


def test_round_trip(tmp_path):
    path = tmp_path / "t.json"
    store.save(path, [Task(1, "a"), Task(2, "b", done=True)])
    assert store.load(path) == [Task(1, "a"), Task(2, "b", done=True)]


def test_missing_file_is_empty(tmp_path):
    assert store.load(tmp_path / "nope.json") == []
