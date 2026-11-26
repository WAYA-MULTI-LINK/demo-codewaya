"""Per-branch task storage for the web UI branch selector.

Each "branch" is just a named task list backed by its own JSON file, so switching
branches in the web UI swaps which set of tasks you view and edit:

    main (default) -> tasks.json
    <branch>       -> tasks-<branch>.json

Branch names are restricted to a safe slug (letters, digits, ``.``, ``-``, ``_``)
so a name can never escape the storage directory. The default branch keeps the
original ``tasks.json`` so existing CLI data is untouched.
"""

import os
import re
import threading

from task_manager import TaskManager

DEFAULT_BRANCH = "main"
_BRANCH_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class BranchError(ValueError):
    """Raised when a branch name is invalid."""


def validate_branch(name: str) -> str:
    """Return ``name`` if it is a safe branch slug, else raise :class:`BranchError`."""
    if not isinstance(name, str) or not _BRANCH_RE.match(name):
        raise BranchError(
            "branch must be 1-64 chars of letters, digits, dot, dash or underscore"
        )
    if name in (".", ".."):
        raise BranchError("branch name may not be '.' or '..'")
    return name


def storage_path_for(name: str, base_dir: str) -> str:
    """Return the JSON storage file for ``name`` under ``base_dir``."""
    branch = validate_branch(name)
    if branch == DEFAULT_BRANCH:
        return os.path.join(base_dir, "tasks.json")
    return os.path.join(base_dir, f"tasks-{branch}.json")


class BranchRegistry:
    """Holds one :class:`TaskManager` per branch, created lazily and thread-safe."""

    def __init__(self, base_dir: str, default_branch: str = DEFAULT_BRANCH):
        self.base_dir = base_dir
        self.default_branch = validate_branch(default_branch)
        self._managers = {}
        self._lock = threading.Lock()

    def get(self, name: str | None) -> TaskManager:
        """Return the manager for ``name`` (default branch when ``None``)."""
        branch = validate_branch(name or self.default_branch)
        with self._lock:
            manager = self._managers.get(branch)
            if manager is None:
                manager = TaskManager(
                    storage_file=storage_path_for(branch, self.base_dir)
                )
                self._managers[branch] = manager
            return manager

    def list_branches(self) -> list[str]:
        """Return the default branch plus any branch whose storage file exists."""
        branches = {self.default_branch}
        prefix, suffix = "tasks-", ".json"
        for entry in os.listdir(self.base_dir):
            if entry.startswith(prefix) and entry.endswith(suffix):
                stem = entry[len(prefix) : -len(suffix)]
                if _BRANCH_RE.match(stem) and stem not in (".", ".."):
                    branches.add(stem)
        # Include any branches already opened in memory.
        with self._lock:
            branches.update(self._managers.keys())
        return sorted(branches)
