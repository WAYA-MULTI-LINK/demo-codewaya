import os
import tempfile
import unittest

from io_utils import export_tasks, import_tasks, safe_path
from task_manager import TaskManager


class TestIOUtils(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_json_export_import(self):
        m1 = TaskManager(storage_file=os.path.join(self.tmp_dir.name, "m1.json"))
        m1.add_task("T1", "D1", priority="high")
        t2 = m1.add_task("T2")
        m1.complete_task(t2.id)

        out_json = os.path.join(self.tmp_dir.name, "export.json")
        export_tasks(m1.tasks, out_json, fmt="json")

        m2 = TaskManager(storage_file=os.path.join(self.tmp_dir.name, "m2.json"))
        count = import_tasks(m2, out_json)
        self.assertEqual(count, 2)
        self.assertEqual(m2.tasks[0].title, "T1")
        self.assertEqual(m2.tasks[0].priority, "high")

    def test_csv_export_import(self):
        m1 = TaskManager(storage_file=os.path.join(self.tmp_dir.name, "m1.json"))
        m1.add_task("T1", "D1")

        out_csv = os.path.join(self.tmp_dir.name, "export.csv")
        export_tasks(m1.tasks, out_csv, fmt="csv")

        m2 = TaskManager(storage_file=os.path.join(self.tmp_dir.name, "m2.json"))
        count = import_tasks(m2, out_csv)
        self.assertEqual(count, 1)
        self.assertEqual(m2.tasks[0].title, "T1")


class TestSafePath(unittest.TestCase):
    def test_returns_absolute_normalised_path(self):
        resolved = safe_path("sub/../tasks.json")
        self.assertTrue(os.path.isabs(resolved))
        self.assertNotIn("..", resolved)

    def test_rejects_empty_and_non_string(self):
        with self.assertRaises(ValueError):
            safe_path("   ")
        with self.assertRaises(TypeError):
            safe_path(None)  # type: ignore[arg-type]

    def test_rejects_nul_bytes(self):
        with self.assertRaises(ValueError):
            safe_path("tasks\x00.json")


if __name__ == "__main__":
    unittest.main()
