import argparse
import os
from pathlib import Path

from todo import store
from todo.model import Task


def default_path() -> Path:
    return Path(os.environ.get("TODO_FILE", Path.home() / ".todo.json"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="todo")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="add a task")
    add.add_argument("title")
    sub.add_parser("list", help="list tasks")
    done = sub.add_parser("done", help="mark a task done")
    done.add_argument("id", type=int)
    return parser


def main(argv=None, path: Path | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = path or default_path()
    tasks = store.load(path)
    if args.command == "add":
        task = Task(id=max((t.id for t in tasks), default=0) + 1, title=args.title)
        store.save(path, [*tasks, task])
        print(f"added {task.id}: {task.title}")
    elif args.command == "list":
        for t in tasks:
            print(f"{t.id} [{'x' if t.done else ' '}] {t.title}")
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
