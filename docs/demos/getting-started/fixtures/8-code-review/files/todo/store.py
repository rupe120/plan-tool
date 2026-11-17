import json
from datetime import date
from pathlib import Path

from todo.model import Task


class StoreError(Exception):
    """The task file holds data the CLI cannot read."""


def _from_row(row: dict) -> Task:
    due = row.get("due")
    try:
        parsed = date.fromisoformat(due) if due else None
    except (ValueError, TypeError):
        raise StoreError(f"task {row.get('id')}: invalid due date {due!r} in task file")
    return Task(
        id=row["id"],
        title=row["title"],
        done=row.get("done", False),
        due=parsed,
    )


def _to_row(task: Task) -> dict:
    row = {"id": task.id, "title": task.title, "done": task.done}
    if task.due is not None:
        row["due"] = task.due.isoformat()
    return row


def load(path: Path) -> list[Task]:
    if not path.exists():
        return []
    return [_from_row(row) for row in json.loads(path.read_text())]


def save(path: Path, tasks: list[Task]) -> None:
    path.write_text(json.dumps([_to_row(t) for t in tasks], indent=2))
