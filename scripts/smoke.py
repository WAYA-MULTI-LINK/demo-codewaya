"""End-to-end smoke test: drive the CLI and the HTTP API to prove every function works.

Run from the repository root:

    python scripts/smoke.py

It uses a throwaway storage file and a server on an ephemeral port, then prints a
PASS/FAIL line for each feature and exits non-zero if anything fails.
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from web import make_server  # noqa: E402

CLI = os.path.join(REPO_ROOT, "cli.py")
RESULTS = []


def record(name, ok, detail=""):
    """Record and print one check result."""
    RESULTS.append(ok)
    status = "PASS" if ok else "FAIL"
    line = f"[{status}] {name}"
    if detail:
        line += f" - {detail}"
    print(line)


def run_cli(*args):
    """Run cli.py with the given args; return (returncode, stdout).

    Uses a timeout so a hung CLI invocation cannot stall the smoke run; on
    timeout the returncode is reported as -1 with the error text.
    """
    try:
        # Args are fixed literals from this script plus the test storage path;
        # no untrusted input reaches the command (S603 is a false positive here).
        proc = subprocess.run(  # noqa: S603
            [sys.executable, CLI, *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return -1, "CLI timed out"
    return proc.returncode, proc.stdout + proc.stderr


class Api:
    """Tiny JSON client for the running test server."""

    def __init__(self, port):
        self.base = f"http://127.0.0.1:{port}"

    def call(self, method, path, body=None):
        """Return ``(status, parsed_json)``; network errors become ``(0, {...})``.

        Never raises: a connection error or a non-JSON body is reported as a
        failed status so one bad request fails a single check instead of aborting
        the whole run with a traceback.
        """
        url = self.base + path
        if not url.startswith(("http://127.0.0.1:", "http://localhost:")):
            return 0, {"error": f"refusing non-loopback url {url!r}"}
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(  # noqa: S310 - loopback url validated above
            url, data=data, method=method, headers=headers
        )
        try:
            # url is validated to be http://127.0.0.1 or http://localhost above.
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
                raw = resp.read().decode()
                return resp.status, json.loads(raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode()
            try:
                return exc.code, json.loads(raw)
            except json.JSONDecodeError:
                return exc.code, {"raw": raw}
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            return 0, {"error": str(exc)}


def smoke_cli(storage):
    """Exercise every CLI command against ``storage``."""
    code, out = run_cli(
        "--file", storage, "add", "Buy milk", "-d", "2%", "--priority", "high"
    )
    record("CLI: add", code == 0 and "Added task 1" in out, out.strip())

    code, out = run_cli("--file", storage, "add", "Write docs")
    record("CLI: add second", code == 0, out.strip())

    code, out = run_cli("--file", storage, "list", "--all")
    record(
        "CLI: list shows both", code == 0 and "Buy milk" in out and "Write docs" in out
    )

    code, out = run_cli("--file", storage, "done", "1")
    record("CLI: done", code == 0 and "Completed task 1" in out)

    code, out = run_cli("--file", storage, "reopen", "1")
    record("CLI: reopen", code == 0 and "Reopened task 1" in out)

    code, out = run_cli("--file", storage, "edit", "2", "--title", "Write docs well")
    record("CLI: edit", code == 0 and "Updated task 2" in out)

    code, out = run_cli("--file", storage, "stats")
    record("CLI: stats", code == 0 and "Total: 2" in out, out.strip())

    code, out = run_cli("--file", storage, "done", "1")
    code, out = run_cli("--file", storage, "list", "--done", "--contains", "milk")
    record(
        "CLI: filter done+contains",
        code == 0 and "Buy milk" in out and "Write docs" not in out,
    )

    export_path = storage + ".export.json"
    code, out = run_cli(
        "--file", storage, "export", "--format", "json", "--out", export_path
    )
    ok = code == 0 and os.path.exists(export_path)
    record("CLI: export", ok)

    if ok:
        imported_storage = storage + ".imported.json"
        code, out = run_cli("--file", imported_storage, "import", export_path)
        record("CLI: import", code == 0 and "Imported 2" in out, out.strip())

    code, out = run_cli("--file", storage, "delete", "2")
    record("CLI: delete", code == 0 and "Deleted task 2" in out)


def smoke_api(api):
    """Exercise every HTTP API endpoint."""
    status, task = api.call(
        "POST", "/api/tasks", {"title": "API task", "priority": "low"}
    )
    record("API: POST add", status == 201 and task.get("title") == "API task")
    task_id = task.get("id") if isinstance(task, dict) else None

    status, tasks = api.call("GET", "/api/tasks")
    record(
        "API: GET list", status == 200 and any(t["title"] == "API task" for t in tasks)
    )

    status, done = api.call("PATCH", f"/api/tasks/{task_id}/complete")
    record("API: complete", status == 200 and done["completed"] is True)

    status, reopened = api.call("PATCH", f"/api/tasks/{task_id}/reopen")
    record("API: reopen", status == 200 and reopened["completed"] is False)

    status, edited = api.call("PATCH", f"/api/tasks/{task_id}", {"title": "Renamed"})
    record("API: edit", status == 200 and edited["title"] == "Renamed")

    status, stats = api.call("GET", "/api/stats")
    record("API: stats", status == 200 and "total" in stats)

    status, body = api.call("POST", "/api/tasks", {"title": "  "})
    record("API: rejects blank title", status == 400)

    status, body = api.call("DELETE", f"/api/tasks/{task_id}")
    record("API: delete", status == 200 and body.get("deleted") is True)

    status, _ = api.call("DELETE", f"/api/tasks/{task_id}")
    record("API: delete missing -> 404", status == 404)

    status, branches = api.call("GET", "/api/branches")
    record("API: branches listed", status == 200 and "main" in branches)

    api.call("POST", "/api/tasks?branch=smoke-a", {"title": "Branch A task"})
    api.call("POST", "/api/tasks?branch=smoke-b", {"title": "Branch B task"})
    _, only_a = api.call("GET", "/api/tasks?branch=smoke-a")
    _, only_b = api.call("GET", "/api/tasks?branch=smoke-b")
    record(
        "API: branch isolation",
        [t["title"] for t in only_a] == ["Branch A task"]
        and [t["title"] for t in only_b] == ["Branch B task"],
    )

    status, _ = api.call("GET", "/api/tasks?branch=../etc")
    record("API: invalid branch -> 400", status == 400)


def smoke_static(api):
    """Confirm the viewer page is served and arbitrary files are not."""
    try:
        with urllib.request.urlopen(  # noqa: S310 - loopback URL built from port
            api.base + "/", timeout=10
        ) as resp:
            html = resp.read().decode()
            served_ok = resp.status == 200 and "Task Checklist" in html
    except (urllib.error.URLError, OSError) as exc:
        served_ok = False
        print(f"  (index fetch error: {exc})")
    record("Web: index.html served", served_ok)

    try:
        with urllib.request.urlopen(  # noqa: S310 - loopback URL built from port
            api.base + "/web.py", timeout=10
        ):
            exposed = True
    except urllib.error.HTTPError as exc:
        exposed = exc.code != 404
    except (urllib.error.URLError, OSError):
        exposed = False
    record("Web: does not expose source", not exposed)


def main():
    """Run CLI, API and static checks, then summarise."""
    tmp = tempfile.mkdtemp()
    storage = os.path.join(tmp, "tasks.json")
    print(f"Smoke test (storage: {storage})\n")

    print("== CLI ==")
    try:
        smoke_cli(storage)
    except Exception as exc:  # noqa: BLE001 - report, never crash the run
        record("CLI section completed", False, repr(exc))

    print("\n== HTTP API ==")
    server = make_server("127.0.0.1", 0, tmp)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    api = Api(port)
    try:
        try:
            smoke_api(api)
            print("\n== Web ==")
            smoke_static(api)
        except Exception as exc:  # noqa: BLE001 - report, never crash the run
            record("API/Web section completed", False, repr(exc))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    passed = sum(RESULTS)
    total = len(RESULTS)
    print(f"\n{passed}/{total} checks passed")
    if passed != total:
        print("SMOKE TEST FAILED")
        sys.exit(1)
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
