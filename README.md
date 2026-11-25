# Demo Repo — Python Task Checklist

A simple command-line task checklist manager, built as a demo repo for testing codewaya.

## Requirements
- Python 3.8+

No third-party dependencies.

## Usage

```bash
# Add a task (optionally with description, due date, priority)
python cli.py add "Buy groceries" -d "Milk, eggs, bread" --due 2026-01-15 --priority high

# List tasks
python cli.py list                 # pending only
python cli.py index                # alias for list
python cli.py list --all           # include completed
python cli.py list --done          # only completed
python cli.py list --pending       # only pending
python cli.py list --contains milk # search title/description
python cli.py list --sort priority # or --sort due

# Mark / reopen / edit
python cli.py done 1
python cli.py reopen 1
python cli.py edit 1 --title "New title" --priority low

# Delete
python cli.py delete 1

# Statistics
python cli.py stats

# Import / export
python cli.py export --format json --out backup.json
python cli.py export --format csv --out backup.csv
python cli.py import backup.json
```

Tasks are persisted to `tasks.json` in the current directory (override with `--file`).

## Web view

`index.html` is a static, dependency-free page that renders `tasks.json` with the same
`[x]` / `[ ]` status, id, title and description as `python cli.py list`, plus a search
box and a "show completed" toggle. Browsers block `fetch` on `file://`, so serve the
folder over HTTP:

```bash
python -m http.server 8000     # read-only: serve this folder, open http://localhost:8000/
```

Unchecking "Show completed" hides completed tasks; an empty store shows
"No tasks found."

## Web UI + JSON API

`web.py` serves the same `index.html` plus a JSON API that exposes **every** task
operation, so each function can be exercised over HTTP:

```bash
python web.py --port 8000 --file tasks.json   # open http://localhost:8000/
```

| Method | Path                       | Purpose                                              |
|--------|----------------------------|------------------------------------------------------|
| GET    | `/api/tasks`               | list tasks; query `all=0`, `status=done\|pending`, `contains=<text>`, `sort=due\|priority` |
| POST   | `/api/tasks`               | add a task: `{"title", "description?", "due_date?", "priority?"}` |
| PATCH  | `/api/tasks/{id}`          | edit fields, or `{"completed": true/false}` to toggle |
| PATCH  | `/api/tasks/{id}/complete` | mark done                                            |
| PATCH  | `/api/tasks/{id}/reopen`   | mark pending again                                   |
| DELETE | `/api/tasks/{id}`          | delete a task                                        |
| GET    | `/api/stats`               | total / completed / pending / overdue counts         |

The shared `TaskManager` is thread-safe (it owns an `RLock`), so the threaded server
is safe under concurrency.

## Project layout

- `task_manager.py` — `Task` and `TaskManager` (core logic, persistence, filtering, stats)
- `formatter.py` — human-readable formatting of tasks and stats
- `io_utils.py` — JSON/CSV import and export
- `cli.py` — command-line interface
- `index.html` — static browser viewer for `tasks.json`
- `web.py` — HTTP JSON API that serves `index.html`

## Run tests

```bash
python -m unittest discover -s tests -t .
```

The US-01 acceptance criteria (unique incrementing ids, `-d/--description`,
pending by default, immediate persistence) are covered end to end by
`tests/test_cli_add.py`, which drives the real CLI in a temporary folder.
