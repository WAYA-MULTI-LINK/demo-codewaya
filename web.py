"""Minimal web frontend for the task manager: JSON API + static single-page UI."""

import argparse
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from task_manager import TaskManager

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}

TASK_PATH = re.compile(r"^/api/tasks/(\d+)$")


class TaskRequestHandler(BaseHTTPRequestHandler):
    manager: TaskManager  # injected by make_server

    def log_message(self, fmt, *args):  # keep the console quiet-ish but useful
        print(f"{self.command} {self.path} -> {args[1] if len(args) > 1 else ''}")

    # --- helpers -----------------------------------------------------------
    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status, message):
        self._send_json({"error": message}, status=status)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError("Request body must be valid JSON")
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object")
        return data

    def _serve_static(self, path):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        full = os.path.normpath(os.path.join(WEB_DIR, rel))
        if not full.startswith(WEB_DIR + os.sep) and full != WEB_DIR:
            self._send_error_json(403, "Forbidden")
            return
        if not os.path.isfile(full):
            self._send_error_json(404, "Not found")
            return
        ext = os.path.splitext(full)[1]
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # --- HTTP verbs --------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/tasks":
            include_completed = parse_qs(parsed.query).get("all", ["1"])[0] != "0"
            tasks = self.manager.list_tasks(include_completed=include_completed)
            self._send_json([t.to_dict() for t in tasks])
            return
        if parsed.path.startswith("/api/"):
            self._send_error_json(404, "Not found")
            return
        self._serve_static(parsed.path)

    def do_POST(self):
        if urlparse(self.path).path != "/api/tasks":
            self._send_error_json(404, "Not found")
            return
        try:
            data = self._read_json()
        except ValueError as exc:
            self._send_error_json(400, str(exc))
            return
        title = (data.get("title") or "").strip()
        if not title:
            self._send_error_json(400, "Title is required")
            return
        task = self.manager.add_task(title, data.get("description") or "")
        self._send_json(task.to_dict(), status=201)

    def do_PATCH(self):
        match = TASK_PATH.match(urlparse(self.path).path)
        if not match:
            self._send_error_json(404, "Not found")
            return
        try:
            data = self._read_json()
        except ValueError as exc:
            self._send_error_json(400, str(exc))
            return

        task_id = int(match.group(1))
        if "completed" in data:
            if not isinstance(data["completed"], bool):
                self._send_error_json(400, "completed must be a boolean")
                return
            task = self.manager.set_completed(task_id, data["completed"])
        else:
            title = data.get("title")
            if title is not None:
                title = str(title).strip()
                if not title:
                    self._send_error_json(400, "Title cannot be empty")
                    return
            task = self.manager.update_task(
                task_id, title=title, description=data.get("description")
            )

        if task is None:
            self._send_error_json(404, "Task not found")
            return
        self._send_json(task.to_dict())

    def do_DELETE(self):
        match = TASK_PATH.match(urlparse(self.path).path)
        if not match:
            self._send_error_json(404, "Not found")
            return
        if not self.manager.delete_task(int(match.group(1))):
            self._send_error_json(404, "Task not found")
            return
        self._send_json({"deleted": True})


def make_server(host="127.0.0.1", port=8000, storage_file="tasks.json"):
    handler = type(
        "BoundTaskRequestHandler",
        (TaskRequestHandler,),
        {"manager": TaskManager(storage_file=storage_file)},
    )
    return ThreadingHTTPServer((host, port), handler)


def main():
    parser = argparse.ArgumentParser(description="Web UI for the task checklist manager")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--file", default="tasks.json", help="Storage file path")
    args = parser.parse_args()

    server = make_server(args.host, args.port, args.file)
    print(f"Serving task manager at http://{args.host}:{args.port}/ (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
