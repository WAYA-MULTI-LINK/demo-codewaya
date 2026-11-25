import os
import re
import unittest
from html.parser import HTMLParser

INDEX = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "index.html"
)


class _PageParser(HTMLParser):
    """Collect element ids, script contents and key attributes from index.html."""

    def __init__(self):
        """Initialise empty collections for the parsed page."""
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.in_script = False
        self.in_style = False
        self.script = []
        self.text = []
        self.scripts_without_src = 0

    def handle_starttag(self, tag, attrs):
        """Record ids and track whether we are inside script/style blocks."""
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.add(attributes["id"])
        if tag == "script" and "src" not in attributes:
            self.in_script = True
            self.scripts_without_src += 1
        elif tag == "style":
            self.in_style = True

    def handle_endtag(self, tag):
        """Leave script/style blocks."""
        if tag == "script":
            self.in_script = False
        elif tag == "style":
            self.in_style = False

    def handle_data(self, data):
        """Capture inline script code and human-visible text."""
        if self.in_script:
            self.script.append(data)
        elif not self.in_style:
            self.text.append(data)


def parse_page():
    """Parse ``index.html`` and return the populated parser.

    Returns:
        _PageParser: ids, inline script source and visible text of the page.

    Raises:
        FileNotFoundError: if ``index.html`` is missing from the project root.
    """
    with open(INDEX, "r", encoding="utf-8") as handle:
        source = handle.read()
    parser = _PageParser()
    parser.feed(source)
    return parser


class TestIndexPage(unittest.TestCase):
    """Check the static task page exposes US-02 style status/id/title/description."""

    def setUp(self):
        """Parse the page once per test."""
        self.page = parse_page()
        self.source = "".join(self.page.script)

    def test_required_elements_exist(self):
        """The list, toggle, summary, empty and error regions are present."""
        for element_id in (
            "task-list",
            "show-completed",
            "summary",
            "empty-state",
            "error-state",
        ):
            self.assertIn(element_id, self.page.ids)

    def test_empty_state_message_matches_cli(self):
        """An empty task list shows the same friendly message as the CLI."""
        self.assertIn("No tasks found.", "".join(self.page.text))

    def test_page_lists_status_id_title_and_description(self):
        """Rendered rows carry `[x]`/`[ ]`, the id, title and description."""
        self.assertIn('"[x]"', self.source)
        self.assertIn('"[ ]"', self.source)
        for field in ("id", "title", "description", "completed"):
            self.assertIn(f"task.{field}", self.source)

    def test_hides_completed_when_toggle_is_off(self):
        """Unchecking "show completed" filters completed tasks out."""
        self.assertIn("task.completed", self.source)
        self.assertIn("toggle.checked", self.source)

    def test_loads_tasks_json_and_handles_missing_file(self):
        """The page fetches tasks.json and reports a readable error otherwise."""
        self.assertIn('"tasks.json"', self.source)
        self.assertIn("response.ok", self.source)
        self.assertIn("error-state", self.source)

    def test_titles_are_inserted_as_text_not_html(self):
        """Task data is written with textContent so titles cannot inject markup."""
        self.assertNotRegex(self.source, r"\.innerHTML\s*=")
        self.assertIn("textContent", self.source)

    def test_no_debug_leftovers(self):
        """The page contains no alert/confirm/console debug calls."""
        self.assertIsNone(re.search(r"\b(alert|confirm|prompt)\s*\(", self.source))
        self.assertNotIn("console.log", self.source)

    def test_no_hard_coded_credentials(self):
        """No tokens, passwords or API keys are baked into the page."""
        self.assertIsNone(
            re.search(r"(api[_-]?key|password|secret|token)\s*[:=]", self.source, re.I)
        )


if __name__ == "__main__":
    unittest.main()
