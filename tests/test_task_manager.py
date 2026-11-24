import os
import tempfile
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

    def test_set_completed(self):
        task = self.manager.add_task("Toggle me")
        self.assertTrue(self.manager.set_completed(task.id, True).completed)
        self.assertFalse(self.manager.set_completed(task.id, False).completed)
        self.assertIsNone(self.manager.set_completed(999, True))

    def test_update_task(self):
        task = self.manager.add_task("Old", "old desc")
        updated = self.manager.update_task(task.id, title="New", description="new desc")
        self.assertEqual(updated.title, "New")
        self.assertEqual(updated.description, "new desc")
        self.assertIsNone(self.manager.update_task(999, title="x"))

    def test_ids_not_reused(self):
        self.manager.add_task("A")
        self.manager.add_task("B")
        self.manager.delete_task(2)
        task = self.manager.add_task("C")
        self.assertEqual(task.id, 3)


if __name__ == "__main__":
    unittest.main()
