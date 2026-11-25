import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from task_manager import TaskManager

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli.py"


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    """Run cli.py with the given arguments inside ``cwd`` and capture its output."""
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


class TestAddTaskCli(unittest.TestCase):
    """Acceptance criteria for US-01: ``python cli.py add``."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.workdir = Path(self.tmp_dir.name)
        self.storage = self.workdir / "tasks.json"

    def stored_tasks(self) -> list[dict]:
        """Return the raw task records persisted to the storage file."""
        with open(self.storage, encoding="utf-8") as handle:
            return json.load(handle)

    def test_add_task_assigns_incrementing_unique_ids(self):
        """US-01-AC1: each add call creates an id that increments and never repeats."""
        for title in ("First", "Second", "Third"):
            result = run_cli("add", title, cwd=self.workdir)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(title, result.stdout)

        ids = [task["id"] for task in self.stored_tasks()]
        self.assertEqual(ids, [1, 2, 3])
        self.assertEqual(len(ids), len(set(ids)))

    def test_description_flag_stores_extra_detail(self):
        """US-01-AC2: ``-d`` and ``--description`` both persist the description."""
        short = run_cli(
            "add", "With short flag", "-d", "short detail", cwd=self.workdir
        )
        self.assertEqual(short.returncode, 0, short.stderr)
        long = run_cli(
            "add", "With long flag", "--description", "long detail", cwd=self.workdir
        )
        self.assertEqual(long.returncode, 0, long.stderr)
        without = run_cli("add", "No description", cwd=self.workdir)
        self.assertEqual(without.returncode, 0, without.stderr)

        descriptions = {
            task["title"]: task["description"] for task in self.stored_tasks()
        }
        self.assertEqual(descriptions["With short flag"], "short detail")
        self.assertEqual(descriptions["With long flag"], "long detail")
        self.assertEqual(descriptions["No description"], "")

    def test_new_tasks_default_to_not_completed(self):
        """US-01-AC3: a freshly added task is stored as not completed."""
        result = run_cli("add", "Not done yet", cwd=self.workdir)
        self.assertEqual(result.returncode, 0, result.stderr)

        (task,) = self.stored_tasks()
        self.assertFalse(task["completed"])
        self.assertFalse(TaskManager(storage_file=str(self.storage)).tasks[0].completed)

    def test_task_is_persisted_immediately(self):
        """US-01-AC4: the storage file exists and reloads right after the add call."""
        self.assertFalse(self.storage.exists())

        result = run_cli("add", "Persisted at once", cwd=self.workdir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.storage.exists())

        reloaded = TaskManager(storage_file=str(self.storage))
        self.assertEqual([task.title for task in reloaded.tasks], ["Persisted at once"])

    def test_custom_file_option_is_honoured(self):
        """US-01-AC4: ``--file`` redirects persistence away from the default path."""
        custom = self.workdir / "nested-tasks.json"
        result = run_cli("--file", str(custom), "add", "Custom store", cwd=self.workdir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(custom.exists())
        self.assertFalse(self.storage.exists())

    def test_invalid_input_exits_with_error_and_persists_nothing(self):
        """Blank titles and malformed values are rejected with a clear message."""
        blank = run_cli("add", "   ", cwd=self.workdir)
        self.assertEqual(blank.returncode, 2)
        self.assertIn("Error:", blank.stderr)

        bad_due = run_cli("add", "Task", "--due", "2026-13-45", cwd=self.workdir)
        self.assertEqual(bad_due.returncode, 2)

        escape = run_cli("--file", "../outside.json", "add", "Task", cwd=self.workdir)
        self.assertEqual(escape.returncode, 2)
        self.assertFalse(self.storage.exists())


class TestIndexPage(unittest.TestCase):
    """Structural checks for the static index.html task viewer."""

    @classmethod
    def setUpClass(cls):
        cls.html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")

    def test_page_reads_tasks_storage(self):
        """The page fetches the same storage file the CLI writes."""
        self.assertIn('"tasks.json"', self.html)
        self.assertIn("fetch(", self.html)

    def test_page_renders_task_list_and_filters(self):
        """The page exposes a task list, a search box and a completed filter."""
        element_ids = ("task-list", "search", "show-completed", "summary", "message")
        for element_id in element_ids:
            self.assertIn(f'id="{element_id}"', self.html)

    def test_page_has_no_debug_leftovers(self):
        """Debug helpers such as alert, confirm, console.log must not ship."""
        for banned in ("alert(", "confirm(", "console.log"):
            self.assertNotIn(banned, self.html)


if __name__ == "__main__":
    unittest.main()
