"""HTTP JSON API and static front-end for the task checklist manager.

Run ``python web.py`` to serve the existing ``index.html`` viewer plus a small
JSON API that exposes every :class:`TaskManager` operation, so each CLI feature
can be exercised over HTTP:

    GET    /api/branches              list available branches
    GET    /api/tasks                 list tasks (filters: all, status, contains, sort)
    POST   /api/tasks                 add a task
    PATCH  /api/tasks/{id}            update fields, or set completed true/false
    PATCH  /api/tasks/{id}/complete   mark a task done
    PATCH  /api/tasks/{id}/reopen     mark a task pending again
    DELETE /api/tasks/{id}            delete a task
    GET    /api/stats                 totals of completed/pending/overdue tasks

Every task endpoint accepts an optional ``?branch=<name>`` query parameter to pick
which branch's task list is read or written; it defaults to ``main``. Each branch
is backed by its own thread-safe :class:`TaskManager`.
"""

import argparse
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from branches import DEFAULT_BRANCH, BranchError, BranchRegistry

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
TASK_NOT_FOUND = "Task not found"


class TaskRequestHandler(BaseHTTPRequestHandler):
    """Serve the static viewer and the JSON task API."""

    registry: BranchRegistry
    server_version = "TaskChecklist/1.0"

    def log_message(self, fmt: str, *args) -> None:
        """Log one short line per request instead of the default noisy format."""
        print(f"{self.command} {self.path} -> {args[1] if len(args) > 1 else ''}")

    def _branch_and_manager(self) -> tuple[str, object] | None:
        """Resolve ``?branch=`` to ``(name, manager)`` or send a 400 and return None."""
        query = parse_qs(urlparse(self.path).query)
        name = query.get("branch", [None])[0] or DEFAULT_BRANCH
        try:
            return name, self.registry.get(name)
        except BranchError as exc:
            self._send_error_json(400, str(exc))
            return None

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
        """Serve the single ``index.html`` asset for ``/``; 404 for everything else.

        The app ships exactly one static file, so only that file is ever read.
        Any other path (``/web.py``, ``/tasks.json``, ``/.git/...``) is refused,
        which avoids exposing arbitrary files from the application directory.
        """
        if path not in ("/", ""):
            self._send_error_json(404, NOT_FOUND)
            return
        if not os.path.isfile(INDEX_FILE):
            self._send_error_json(404, NOT_FOUND)
            return
        with open(INDEX_FILE, "rb") as handle:
            body = handle.read()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPES[".html"])
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """Handle ``GET`` for branches, the task list, stats, or static files."""
        parsed = urlparse(self.path)
        if parsed.path == "/api/branches":
            self._send_json(self.registry.list_branches())
            return
        if parsed.path == "/api/tasks":
            resolved = self._branch_and_manager()
            if resolved is None:
                return
            self._handle_list(parse_qs(parsed.query), resolved[1])
            return
        if parsed.path == "/api/stats":
            resolved = self._branch_and_manager()
            if resolved is None:
                return
            self._send_json(resolved[1].stats())
            return
        if parsed.path.startswith("/api/"):
            self._send_error_json(404, NOT_FOUND)
            return
        self._serve_static(parsed.path)

    def _handle_list(self, query: dict, manager) -> None:
        """List ``manager`` tasks with the all/status/contains/sort query args."""
        status = query.get("status", [None])[0]
        contains = query.get("contains", [None])[0]
        sort = query.get("sort", [None])[0]
        include_completed = query.get("all", ["1"])[0] != "0"
        tasks = manager.list_tasks(
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
        resolved = self._branch_and_manager()
        if resolved is None:
            return
        manager = resolved[1]
        try:
            data = self._read_json()
        except ValueError as exc:
            self._send_error_json(400, str(exc))
            return
        try:
            task = manager.add_task(
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
        item = TASK_ITEM.match(path)
        if not action and not item:
            self._send_error_json(404, NOT_FOUND)
            return
        resolved = self._branch_and_manager()
        if resolved is None:
            return
        manager = resolved[1]
        if action:
            self._handle_action(manager, int(action.group(1)), action.group(2))
        else:
            self._apply_field_edit(manager, int(item.group(1)))

    def _respond_task(self, manager, task_id: int) -> None:
        """Send the current state of ``task_id``, or 404 if it vanished.

        A concurrent ``DELETE`` can remove the task between a successful
        mutation and this read; re-fetching here and guarding ``None`` prevents a
        500 on the race.
        """
        task = manager.get_task(task_id)
        if task is None:
            self._send_error_json(404, TASK_NOT_FOUND)
            return
        self._send_json(task.to_dict())

    def _handle_action(self, manager, task_id: int, action: str) -> None:
        """Apply ``complete`` or ``reopen`` to ``task_id``."""
        if action == "complete":
            ok = manager.complete_task(task_id)
        else:
            ok = manager.reopen_task(task_id)
        if not ok:
            self._send_error_json(404, TASK_NOT_FOUND)
            return
        self._respond_task(manager, task_id)

    def _toggle_completed(self, manager, task_id: int, completed: bool) -> None:
        """Set ``task_id`` to completed or pending and respond with its state."""
        if not isinstance(completed, bool):
            self._send_error_json(400, "completed must be a boolean")
            return
        ok = (
            manager.complete_task(task_id)
            if completed
            else manager.reopen_task(task_id)
        )
        if not ok:
            self._send_error_json(404, TASK_NOT_FOUND)
            return
        self._respond_task(manager, task_id)

    def _apply_field_edit(self, manager, task_id: int) -> None:
        """Read the request body and apply a partial field update to ``task_id``.

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
            self._toggle_completed(manager, task_id, data["completed"])
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
            ok = manager.edit_task(task_id, **kwargs)
        except (TypeError, ValueError) as exc:
            self._send_error_json(400, str(exc))
            return
        if not ok:
            self._send_error_json(404, TASK_NOT_FOUND)
            return
        self._respond_task(manager, task_id)

    def do_DELETE(self) -> None:
        """Handle ``DELETE /api/tasks/{id}``."""
        match = TASK_ITEM.match(urlparse(self.path).path)
        if not match:
            self._send_error_json(404, NOT_FOUND)
            return
        resolved = self._branch_and_manager()
        if resolved is None:
            return
        manager = resolved[1]
        if not manager.delete_task(int(match.group(1))):
            self._send_error_json(404, TASK_NOT_FOUND)
            return
        self._send_json({"deleted": True})


def make_server(host: str = "127.0.0.1", port: int = 8000, base_dir: str = "."):
    """Return a threaded HTTP server backed by a :class:`BranchRegistry`."""
    handler = type(
        "BoundTaskRequestHandler",
        (TaskRequestHandler,),
        {"registry": BranchRegistry(base_dir)},
    )
    return ThreadingHTTPServer((host, port), handler)


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and serve until interrupted."""
    parser = argparse.ArgumentParser(
        description="Web UI and JSON API for the task checklist"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument(
        "--dir", default=".", help="Directory holding per-branch task files"
    )
    args = parser.parse_args(argv)

    server = make_server(args.host, args.port, args.dir)
    print(f"Serving task checklist at http://{args.host}:{args.port}/ (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
