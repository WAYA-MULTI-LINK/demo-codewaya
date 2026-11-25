import os
import subprocess
import sys
import tempfile
import unittest

CLI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cli.py")


class TestCliList(unittest.TestCase):
    """Cover US-02 acceptance criteria through the real CLI entry point."""

    def setUp(self):
        """Create an isolated working directory so tasks.json stays per-test."""
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = self._tmp.name

    def tearDown(self):
        """Remove the temporary working directory."""
        self._tmp.cleanup()

    def run_cli(self, *args):
        """Run ``cli.py`` with ``args`` in the temp dir and return the result.

        Returns:
            subprocess.CompletedProcess: captured stdout/stderr and exit code.
        """
        return subprocess.run(
            [sys.executable, CLI, *args],
            cwd=self.cwd,
            capture_output=True,
            text=True,
            check=False,
        )

    def seed(self):
        """Create one pending and one completed task in the temp store."""
        self.run_cli("add", "Buy milk", "-d", "from store")
        self.run_cli("add", "Write code")
        self.run_cli("done", "1")

    def test_ac1_list_shows_only_incomplete(self):
        """US-02-AC1: plain ``list`` hides completed tasks."""
        self.seed()
        out = self.run_cli("list").stdout
        self.assertIn("Write code", out)
        self.assertNotIn("Buy milk", out)

    def test_ac2_list_all_shows_every_task(self):
        """US-02-AC2: ``list --all`` includes completed tasks too."""
        self.seed()
        out = self.run_cli("list", "--all").stdout
        self.assertIn("Buy milk", out)
        self.assertIn("Write code", out)

    def test_ac3_line_has_status_id_title_and_description(self):
        """US-02-AC3: each line carries status, id, title and description."""
        self.seed()
        lines = self.run_cli("list", "--all").stdout.strip().splitlines()
        self.assertEqual(lines[0], "[x] 1. Buy milk - from store")
        self.assertEqual(lines[1], "[ ] 2. Write code")

    def test_ac4_empty_list_is_friendly(self):
        """US-02-AC4: an empty store prints the friendly message."""
        self.assertEqual(self.run_cli("list").stdout.strip(), "No tasks found.")

    def test_index_alias_lists_tasks(self):
        """``index`` behaves exactly like ``list``."""
        self.seed()
        self.assertEqual(
            self.run_cli("index").stdout, self.run_cli("list").stdout
        )


if __name__ == "__main__":
    unittest.main()
