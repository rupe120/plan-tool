import argparse
import os
from datetime import date
from pathlib import Path

from todo import store
from todo.model import Task


def default_path() -> Path:
    return Path(os.environ.get("TODO_FILE", Path.home() / ".todo.json"))


def parse_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date {text!r}; use YYYY-MM-DD")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="todo")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="add a task")
    add.add_argument("title")
    add.add_argument("--due", type=parse_date, help="due date, YYYY-MM-DD")
    lst = sub.add_parser("list", help="list tasks")
    lst.add_argument("--overdue", action="store_true", help="only open tasks past due")
    done = sub.add_parser("done", help="mark a task done")
    done.add_argument("id", type=int)
    return parser


def main(argv=None, path: Path | None = None, today: date | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = path or default_path()
    today = today or date.today()
    tasks = store.load(path)
    if args.command == "add":
        task = Task(
            id=max((t.id for t in tasks), default=0) + 1,
            title=args.title,
            due=args.due,
        )
        store.save(path, [*tasks, task])
        print(f"added {task.id}: {task.title}")
    elif args.command == "list":
        for t in tasks:
            if args.overdue and not (not t.done and t.due is not None and t.due < today):
                continue
            due = f" (due {t.due.isoformat()})" if t.due else ""
            print(f"{t.id} [{'x' if t.done else ' '}] {t.title}{due}")
    elif args.command == "done":
        for t in tasks:
            if t.id == args.id:
                t.done = True
                store.save(path, tasks)
                print(f"done {t.id}")
                return 0
        print(f"no task {args.id}")
        return 1
    return 0
