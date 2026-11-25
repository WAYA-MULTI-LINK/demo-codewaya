"""HTTP JSON API and static front-end for the task checklist manager.

Run ``python web.py`` to serve the existing ``index.html`` viewer plus a small
JSON API that exposes every :class:`TaskManager` operation, so each CLI feature
can be exercised over HTTP:

    GET    /api/tasks                 list tasks (filters: all, status, contains, sort)
    POST   /api/tasks                 add a task
    PATCH  /api/tasks/{id}            update fields, or set completed true/false
    PATCH  /api/tasks/{id}/complete   mark a task done
    PATCH  /api/tasks/{id}/reopen     mark a task pending again
    DELETE /api/tasks/{id}            delete a task
    GET    /api/stats                 totals of completed/pending/overdue tasks

The shared ``TaskManager`` is thread-safe (it owns an ``RLock``), so one instance
can safely back the threaded server.
"""

import argparse
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from task_manager import TaskManager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(BASE_DIR, "index.html")

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}

TASK_ITEM = re.compile(r"^/api/tasks/(\d+)$")
TASK_ACTION = re.compile(r"^/api/tasks/(\d+)/(complete|reopen)$")

NOT_FOUND = "Not found"


class TaskRequestHandler(BaseHTTPRequestHandler):
    """Serve the static viewer and the JSON task API."""

    manager: TaskManager
    server_version = "TaskChecklist/1.0"

    def log_message(self, fmt: str, *args) -> None:
        """Log one short line per request instead of the default noisy format."""
        print(f"{self.command} {self.path} -> {args[1] if len(args) > 1 else ''}")

    def _send_json(self, payload, status: int = 200) -> None:
        """Write ``payload`` as a JSON response with ``status``."""
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, message: str) -> None:
        """Write a JSON error body with ``status``."""
        self._send_json({"error": message}, status=status)

    def _read_json(self) -> dict:
        """Parse and return the request body as a JSON object.

        Raises:
            ValueError: If the body is not a JSON object.
        """
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("Request body must be valid JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object")
        return data

    def _serve_static(self, path: str) -> None:
        """Serve ``index.html`` for ``/`` and 404 for anything else."""
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        full = os.path.normpath(os.path.join(BASE_DIR, rel))
        if not full.startswith(BASE_DIR + os.sep) and full != BASE_DIR:
            self._send_error_json(403, "Forbidden")
            return
        if not os.path.isfile(full):
            self._send_error_json(404, NOT_FOUND)
            return
        ext = os.path.splitext(full)[1]
        with open(full, "rb") as handle:
            body = handle.read()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """Handle ``GET`` for the task list, stats, or static files."""
        parsed = urlparse(self.path)
        if parsed.path == "/api/tasks":
            self._handle_list(parse_qs(parsed.query))
            return
        if parsed.path == "/api/stats":
            self._send_json(self.manager.stats())
            return
        if parsed.path.startswith("/api/"):
            self._send_error_json(404, NOT_FOUND)
            return
        self._serve_static(parsed.path)

    def _handle_list(self, query: dict) -> None:
        """List tasks applying the ``all``/``status``/``contains``/``sort`` query args."""
        status = query.get("status", [None])[0]
        contains = query.get("contains", [None])[0]
        sort = query.get("sort", [None])[0]
        include_completed = query.get("all", ["1"])[0] != "0"
        tasks = self.manager.list_tasks(
            include_completed=include_completed,
            contains=contains,
            status=status,
            sort=sort,
        )
        self._send_json([task.to_dict() for task in tasks])

    def do_POST(self) -> None:
        """Handle ``POST /api/tasks`` to add a task."""
        if urlparse(self.path).path != "/api/tasks":
            self._send_error_json(404, NOT_FOUND)
            return
        try:
            data = self._read_json()
        except ValueError as exc:
            self._send_error_json(400, str(exc))
            return
        try:
            task = self.manager.add_task(
                data.get("title") or "",
                data.get("description") or "",
                due_date=data.get("due_date"),
                priority=data.get("priority"),
            )
        except (TypeError, ValueError) as exc:
            self._send_error_json(400, str(exc))
            return
        self._send_json(task.to_dict(), status=201)

    def do_PATCH(self) -> None:
        """Handle ``PATCH`` for completing, reopening, or editing a task."""
        path = urlparse(self.path).path
        action = TASK_ACTION.match(path)
        if action:
            self._handle_action(int(action.group(1)), action.group(2))
            return
        item = TASK_ITEM.match(path)
        if item:
            self._handle_edit(int(item.group(1)))
            return
        self._send_error_json(404, NOT_FOUND)

    def _handle_action(self, task_id: int, action: str) -> None:
        """Apply ``complete`` or ``reopen`` to ``task_id``."""
        if action == "complete":
            ok = self.manager.complete_task(task_id)
        else:
            ok = self.manager.reopen_task(task_id)
        if not ok:
            self._send_error_json(404, "Task not found")
            return
        self._send_json(self.manager.get_task(task_id).to_dict())

    def _handle_edit(self, task_id: int) -> None:
        """Apply a partial update to ``task_id``.

        A boolean ``completed`` toggles completion; other keys edit fields. Omitted
        keys are left unchanged, while ``due_date``/``priority`` may be cleared by
        sending ``null`` or an empty string.
        """
        try:
            data = self._read_json()
        except ValueError as exc:
            self._send_error_json(400, str(exc))
            return

        if "completed" in data:
            if not isinstance(data["completed"], bool):
                self._send_error_json(400, "completed must be a boolean")
                return
            ok = (
                self.manager.complete_task(task_id)
                if data["completed"]
                else self.manager.reopen_task(task_id)
            )
            if not ok:
                self._send_error_json(404, "Task not found")
                return
            self._send_json(self.manager.get_task(task_id).to_dict())
            return

        kwargs = {}
        if "title" in data:
            kwargs["title"] = data["title"]
        if "description" in data:
            kwargs["description"] = data["description"]
        if "due_date" in data:
            kwargs["due_date"] = data["due_date"] if data["due_date"] else None
        if "priority" in data:
            kwargs["priority"] = data["priority"] if data["priority"] else None

        try:
            ok = self.manager.edit_task(task_id, **kwargs)
        except (TypeError, ValueError) as exc:
            self._send_error_json(400, str(exc))
            return
        if not ok:
            self._send_error_json(404, "Task not found")
            return
        self._send_json(self.manager.get_task(task_id).to_dict())

    def do_DELETE(self) -> None:
        """Handle ``DELETE /api/tasks/{id}``."""
        match = TASK_ITEM.match(urlparse(self.path).path)
        if not match:
            self._send_error_json(404, NOT_FOUND)
            return
        if not self.manager.delete_task(int(match.group(1))):
            self._send_error_json(404, "Task not found")
            return
        self._send_json({"deleted": True})


def make_server(host: str = "127.0.0.1", port: int = 8000, storage_file: str = "tasks.json"):
    """Return a threaded HTTP server bound to a fresh ``TaskManager``."""
    handler = type(
        "BoundTaskRequestHandler",
        (TaskRequestHandler,),
        {"manager": TaskManager(storage_file=storage_file)},
    )
    return ThreadingHTTPServer((host, port), handler)


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and serve until interrupted."""
    parser = argparse.ArgumentParser(description="Web UI and JSON API for the task checklist")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--file", default="tasks.json", help="Storage file path")
    args = parser.parse_args(argv)

    server = make_server(args.host, args.port, args.file)
    print(f"Serving task checklist at http://{args.host}:{args.port}/ (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
