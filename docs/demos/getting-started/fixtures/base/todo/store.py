import json
from pathlib import Path

from todo.model import Task


def load(path: Path) -> list[Task]:
    if not path.exists():
        return []
    return [Task(**row) for row in json.loads(path.read_text())]


def save(path: Path, tasks: list[Task]) -> None:
    path.write_text(json.dumps([vars(t) for t in tasks], indent=2))
