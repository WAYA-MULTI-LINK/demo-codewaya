# Demo Repo — Python Task Checklist

A simple command-line task checklist manager, built as a demo repo for testing codewaya.

## Requirements
- Python 3.8+

No third-party dependencies.

## Usage

```bash
# Add a task
python cli.py add "Buy groceries" -d "Milk, eggs, bread"

# List tasks (all, including completed)
python cli.py list --all

# List only incomplete tasks
python cli.py list

# Mark a task done
python cli.py done 1

# Delete a task
python cli.py delete 1
```

Tasks are persisted to `tasks.json` in the current directory.

## Web UI

A zero-dependency web frontend is included (Python standard library only):

```bash
python web.py                 # http://127.0.0.1:8000/
python web.py --port 8080 --file my-tasks.json
```

Open the URL in a browser to add, complete, edit, delete and filter tasks. The
UI is styled with [Bootstrap 5.3](https://getbootstrap.com/) (dark theme),
vendored at `web/vendor/bootstrap.min.css` so the app stays dependency-free
and works offline. The UI talks to a small JSON API:

| Method | Path               | Description                            |
| ------ | ------------------ | -------------------------------------- |
| GET    | `/api/tasks`       | List tasks (`?all=0` for active only)  |
| POST   | `/api/tasks`       | Create task: `{"title", "description"}`|
| PATCH  | `/api/tasks/{id}`  | Toggle `{"completed": bool}` or edit `{"title", "description"}` |
| DELETE | `/api/tasks/{id}`  | Delete a task                          |

The CLI and the web UI share the same storage file, so tasks added via one show
up in the other.

## Run tests

```bash
python -m unittest discover -s tests
```
