# todo

A small task-list CLI that stores tasks in a JSON file (`$TODO_FILE`, default
`~/.todo.json`).

```bash
uv run python -m todo add "write the demo"
uv run python -m todo list
uv run python -m todo done 1
```

Run the tests with `uv run pytest -q`.
