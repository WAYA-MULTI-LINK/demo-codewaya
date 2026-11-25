"""End-to-end tests for the HTTP JSON API in web.py."""

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from web import make_server


class ApiTestCase(unittest.TestCase):
    """Boot a real server on an ephemeral port backed by a temp storage file."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.storage = os.path.join(cls.tmp.name, "tasks.json")
        cls.server = make_server("127.0.0.1", 0, cls.storage)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def request(self, method, path, body=None):
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.url(path), data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def setUp(self):
        for task in self.request("GET", "/api/tasks")[1]:
            self.request("DELETE", f"/api/tasks/{task['id']}")

    def test_add_and_list(self):
        status, task = self.request("POST", "/api/tasks", {"title": "Buy milk", "priority": "high"})
        self.assertEqual(status, 201)
        self.assertEqual(task["title"], "Buy milk")
        self.assertEqual(task["priority"], "high")
        status, tasks = self.request("GET", "/api/tasks")
        self.assertEqual(status, 200)
        self.assertTrue(any(t["id"] == task["id"] for t in tasks))

    def test_add_requires_title(self):
        status, body = self.request("POST", "/api/tasks", {"title": "  "})
        self.assertEqual(status, 400)
        self.assertIn("error", body)

    def test_complete_and_reopen(self):
        _, task = self.request("POST", "/api/tasks", {"title": "Walk"})
        status, done = self.request("PATCH", f"/api/tasks/{task['id']}/complete")
        self.assertEqual(status, 200)
        self.assertTrue(done["completed"])
        status, reopened = self.request("PATCH", f"/api/tasks/{task['id']}/reopen")
        self.assertEqual(status, 200)
        self.assertFalse(reopened["completed"])

    def test_patch_completed_boolean(self):
        _, task = self.request("POST", "/api/tasks", {"title": "Read"})
        status, done = self.request("PATCH", f"/api/tasks/{task['id']}", {"completed": True})
        self.assertEqual(status, 200)
        self.assertTrue(done["completed"])
        status, body = self.request("PATCH", f"/api/tasks/{task['id']}", {"completed": "yes"})
        self.assertEqual(status, 400)

    def test_edit_fields_and_clear(self):
        _, task = self.request("POST", "/api/tasks", {"title": "Old", "due_date": "2026-01-01"})
        status, edited = self.request(
            "PATCH", f"/api/tasks/{task['id']}", {"title": "New", "due_date": ""}
        )
        self.assertEqual(status, 200)
        self.assertEqual(edited["title"], "New")
        self.assertIsNone(edited["due_date"])

    def test_filters_and_sort(self):
        self.request("POST", "/api/tasks", {"title": "Alpha", "priority": "low"})
        _, beta = self.request("POST", "/api/tasks", {"title": "Beta", "priority": "high"})
        self.request("PATCH", f"/api/tasks/{beta['id']}/complete")
        status, pending = self.request("GET", "/api/tasks?status=pending")
        self.assertEqual(status, 200)
        self.assertTrue(all(not t["completed"] for t in pending))
        status, found = self.request("GET", "/api/tasks?contains=alp")
        self.assertEqual([t["title"] for t in found], ["Alpha"])
        status, sorted_tasks = self.request("GET", "/api/tasks?sort=priority")
        self.assertEqual(sorted_tasks[0]["title"], "Beta")

    def test_stats(self):
        self.request("POST", "/api/tasks", {"title": "A"})
        _, b = self.request("POST", "/api/tasks", {"title": "B"})
        self.request("PATCH", f"/api/tasks/{b['id']}/complete")
        status, stats = self.request("GET", "/api/stats")
        self.assertEqual(status, 200)
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["pending"], 1)

    def test_delete(self):
        _, task = self.request("POST", "/api/tasks", {"title": "Temp"})
        status, body = self.request("DELETE", f"/api/tasks/{task['id']}")
        self.assertEqual(status, 200)
        self.assertTrue(body["deleted"])
        status, _ = self.request("DELETE", f"/api/tasks/{task['id']}")
        self.assertEqual(status, 404)

    def test_unknown_task(self):
        status, _ = self.request("PATCH", "/api/tasks/99999/complete")
        self.assertEqual(status, 404)
        status, _ = self.request("DELETE", "/api/tasks/99999")
        self.assertEqual(status, 404)

    def test_static_index_served(self):
        with urllib.request.urlopen(self.url("/"), timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("Task Checklist", resp.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
