import json
import os
import tempfile
import threading
import unittest

from task_manager import TaskManager


class TestTaskManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.tmp.close()
        os.remove(self.tmp.name)
        self.manager = TaskManager(storage_file=self.tmp.name)

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            os.remove(self.tmp.name)

    def test_add_task(self):
        task = self.manager.add_task("Buy milk")
        self.assertEqual(task.id, 1)
        self.assertEqual(task.title, "Buy milk")
        self.assertFalse(task.completed)
        self.assertEqual(len(self.manager.tasks), 1)

    def test_complete_task(self):
        task = self.manager.add_task("Write tests")
        self.assertTrue(self.manager.complete_task(task.id))
        self.assertTrue(self.manager.get_task(task.id).completed)
        self.assertFalse(self.manager.complete_task(999))

    def test_delete_task(self):
        task = self.manager.add_task("Temp task")
        self.assertTrue(self.manager.delete_task(task.id))
        self.assertIsNone(self.manager.get_task(task.id))
        self.assertFalse(self.manager.delete_task(999))

    def test_persistence(self):
        self.manager.add_task("Persisted")
        self.manager.complete_task(1)
        reloaded = TaskManager(storage_file=self.tmp.name)
        self.assertEqual(len(reloaded.tasks), 1)
        self.assertTrue(reloaded.tasks[0].completed)

    def test_list_incomplete(self):
        self.manager.add_task("A")
        self.manager.add_task("B")
        self.manager.complete_task(1)
        incomplete = self.manager.list_tasks(include_completed=False)
        self.assertEqual(len(incomplete), 1)
        self.assertEqual(incomplete[0].title, "B")

    def test_ids_not_reused(self):
        self.manager.add_task("A")
        self.manager.add_task("B")
        self.manager.delete_task(2)
        task = self.manager.add_task("C")
        self.assertEqual(task.id, 3)

    def test_add_persists_immediately_and_defaults_to_pending(self):
        """US-01-AC3/AC4: the file is written at once and the task starts pending."""
        task = self.manager.add_task("Immediate", "detail")
        self.assertFalse(task.completed)
        with open(self.tmp.name, encoding="utf-8") as handle:
            stored = json.load(handle)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["title"], "Immediate")
        self.assertEqual(stored[0]["description"], "detail")
        self.assertFalse(stored[0]["completed"])

    def test_add_rejects_blank_title_and_bad_input(self):
        """Adding validates its input and leaves the store untouched on error."""
        with self.assertRaises(ValueError):
            self.manager.add_task("   ")
        with self.assertRaises(ValueError):
            self.manager.add_task("Title", due_date="not-a-date")
        with self.assertRaises(ValueError):
            self.manager.add_task("Title", priority="urgent")
        with self.assertRaises(TypeError):
            self.manager.add_task(123)
        self.assertEqual(self.manager.tasks, [])

    def test_concurrent_adds_keep_ids_unique(self):
        """Ids stay unique when several threads add tasks at the same time."""

        def worker(index):
            self.manager.add_task(f"Task {index}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        ids = [task.id for task in TaskManager(storage_file=self.tmp.name).tasks]
        self.assertEqual(sorted(ids), list(range(1, 21)))


if __name__ == "__main__":
    unittest.main()
