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

## View tasks in the browser

`index.html` is a dependency-free page that reads `tasks.json` and shows the same
tasks, including a search box and a "show completed" toggle.

```bash
python cli.py add "Buy groceries" -d "Milk, eggs, bread" --due 2026-01-15 --priority high
python -m http.server 8000     # serve this folder, then open http://localhost:8000/
```

The page must be served over HTTP — opening the file directly cannot fetch `tasks.json`
due to browser same-origin rules.

## Project layout

- `task_manager.py` — `Task` and `TaskManager` (core logic, persistence, filtering, stats)
- `formatter.py` — human-readable formatting of tasks and stats
- `io_utils.py` — JSON/CSV import and export
- `cli.py` — command-line interface
- `index.html` — static browser viewer for `tasks.json`

## Run tests

```bash
python -m unittest discover -s tests -t .
```

The US-01 acceptance criteria (unique incrementing ids, `-d/--description`,
pending by default, immediate persistence) are covered end to end by
`tests/test_cli_add.py`, which drives the real CLI in a temporary folder.
