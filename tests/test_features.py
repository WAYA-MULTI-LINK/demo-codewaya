import os
import tempfile
import unittest
from datetime import date, timedelta

from task_manager import TaskManager


class TestTaskFeatures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.tmp.close()
        os.remove(self.tmp.name)
        self.manager = TaskManager(storage_file=self.tmp.name)

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            os.remove(self.tmp.name)

    def test_reopen_task(self):
        t = self.manager.add_task("A")
        self.manager.complete_task(t.id)
        self.assertTrue(self.manager.reopen_task(t.id))
        self.assertFalse(self.manager.get_task(t.id).completed)
        self.assertFalse(self.manager.reopen_task(999))

    def test_edit_task(self):
        t = self.manager.add_task("A")
        self.assertTrue(self.manager.edit_task(t.id, title="B", priority="high"))
        self.assertEqual(self.manager.get_task(t.id).title, "B")
        self.assertEqual(self.manager.get_task(t.id).priority, "high")
        self.assertFalse(self.manager.edit_task(999, title="X"))

    def test_search_contains(self):
        self.manager.add_task("Buy milk", "from the store")
        self.manager.add_task("Write code")
        results = self.manager.list_tasks(contains="milk")
        self.assertEqual(len(results), 1)
        results = self.manager.list_tasks(contains="STORE")
        self.assertEqual(len(results), 1)

    def test_filter_by_status(self):
        a = self.manager.add_task("A")
        self.manager.add_task("B")
        self.manager.complete_task(a.id)
        self.assertEqual(len(self.manager.list_tasks(status="done")), 1)
        self.assertEqual(len(self.manager.list_tasks(status="pending")), 1)

    def test_sort_by_priority(self):
        self.manager.add_task("Low", priority="low")
        self.manager.add_task("High", priority="high")
        self.manager.add_task("None")
        ordered = self.manager.list_tasks(sort="priority")
        self.assertEqual(ordered[0].title, "High")
        self.assertEqual(ordered[-1].title, "None")

    def test_stats_and_overdue(self):
        past = (date.today() - timedelta(days=1)).isoformat()
        a = self.manager.add_task("Overdue", due_date=past)
        self.manager.add_task("Done", due_date=past)
        self.manager.complete_task(2)
        s = self.manager.stats()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["completed"], 1)
        self.assertEqual(s["pending"], 1)
        self.assertEqual(s["overdue"], 1)
        self.assertTrue(self.manager.get_task(a.id).is_overdue())

    def test_backward_compatible_load(self):
        import json
        with open(self.tmp.name, "w", encoding="utf-8") as f:
            json.dump(
                [{"id": 1, "title": "Old", "description": "", "completed": False}],
                f,
            )
        m = TaskManager(storage_file=self.tmp.name)
        self.assertIsNone(m.tasks[0].due_date)
        self.assertIsNone(m.tasks[0].priority)


if __name__ == "__main__":
    unittest.main()
