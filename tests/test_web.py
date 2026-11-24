import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from task_manager import TaskManager
from web import make_server


class TestWebApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.tmp.close()
        os.remove(self.tmp.name)
        self.server = make_server(port=0, storage_file=self.tmp.name)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        if os.path.exists(self.tmp.name):
            os.remove(self.tmp.name)

    def request(self, method, path, payload=None):
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as res:
                return res.status, json.loads(res.read().decode("utf-8") or "null")
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read().decode("utf-8") or "null")

    def test_create_and_list(self):
        status, task = self.request("POST", "/api/tasks", {"title": "Buy milk", "description": "2%"})
        self.assertEqual(status, 201)
        self.assertEqual(task["title"], "Buy milk")
        self.assertFalse(task["completed"])

        status, tasks = self.request("GET", "/api/tasks")
        self.assertEqual(status, 200)
        self.assertEqual([t["title"] for t in tasks], ["Buy milk"])

    def test_create_requires_title(self):
        status, body = self.request("POST", "/api/tasks", {"title": "   "})
        self.assertEqual(status, 400)
        self.assertIn("Title", body["error"])

    def test_toggle_completed_both_directions(self):
        _, task = self.request("POST", "/api/tasks", {"title": "Ship it"})
        status, updated = self.request("PATCH", f"/api/tasks/{task['id']}", {"completed": True})
        self.assertEqual(status, 200)
        self.assertTrue(updated["completed"])

        status, updated = self.request("PATCH", f"/api/tasks/{task['id']}", {"completed": False})
        self.assertEqual(status, 200)
        self.assertFalse(updated["completed"])

    def test_filter_active_only(self):
        _, done = self.request("POST", "/api/tasks", {"title": "Done one"})
        self.request("POST", "/api/tasks", {"title": "Open one"})
        self.request("PATCH", f"/api/tasks/{done['id']}", {"completed": True})

        _, tasks = self.request("GET", "/api/tasks?all=0")
        self.assertEqual([t["title"] for t in tasks], ["Open one"])

    def test_edit_task(self):
        _, task = self.request("POST", "/api/tasks", {"title": "Old"})
        status, updated = self.request(
            "PATCH", f"/api/tasks/{task['id']}", {"title": "New", "description": "why"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["title"], "New")
        self.assertEqual(updated["description"], "why")

    def test_edit_rejects_blank_title(self):
        _, task = self.request("POST", "/api/tasks", {"title": "Keep"})
        status, body = self.request("PATCH", f"/api/tasks/{task['id']}", {"title": ""})
        self.assertEqual(status, 400)
        self.assertIn("Title", body["error"])

    def test_delete_task(self):
        _, task = self.request("POST", "/api/tasks", {"title": "Temp"})
        status, _ = self.request("DELETE", f"/api/tasks/{task['id']}")
        self.assertEqual(status, 200)
        _, tasks = self.request("GET", "/api/tasks")
        self.assertEqual(tasks, [])

    def test_missing_task_returns_404(self):
        status, _ = self.request("DELETE", "/api/tasks/999")
        self.assertEqual(status, 404)
        status, _ = self.request("PATCH", "/api/tasks/999", {"completed": True})
        self.assertEqual(status, 404)

    def test_invalid_json_returns_400(self):
        req = urllib.request.Request(
            self.base + "/api/tasks",
            data=b"not json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

    def test_persists_through_task_manager(self):
        self.request("POST", "/api/tasks", {"title": "Persisted"})
        reloaded = TaskManager(storage_file=self.tmp.name)
        self.assertEqual([t.title for t in reloaded.tasks], ["Persisted"])

    def test_serves_index_and_rejects_traversal(self):
        with urllib.request.urlopen(self.base + "/") as res:
            self.assertEqual(res.status, 200)
            self.assertIn(b"Task Checklist", res.read())

        with urllib.request.urlopen(self.base + "/style.css") as res:
            self.assertIn("text/css", res.headers["Content-Type"])

        with urllib.request.urlopen(self.base + "/app.js") as res:
            self.assertIn("javascript", res.headers["Content-Type"])

        with urllib.request.urlopen(self.base + "/vendor/bootstrap.min.css") as res:
            self.assertIn("text/css", res.headers["Content-Type"])
            self.assertIn(b"Bootstrap", res.read(512))

        req = urllib.request.Request(
            self.base + "/../task_manager.py", method="GET"
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertIn(ctx.exception.code, (403, 404))


if __name__ == "__main__":
    unittest.main()
