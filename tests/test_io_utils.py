import os
import tempfile
import unittest

from task_manager import TaskManager
from io_utils import export_tasks, import_tasks


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


if __name__ == "__main__":
    unittest.main()
