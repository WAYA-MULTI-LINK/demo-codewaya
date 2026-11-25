"""Task model and JSON-backed task storage.

``TaskManager`` owns the list of tasks and keeps the storage file in sync after
every mutation, so a freshly added task survives a process restart.
"""

import json
import os
import tempfile
import threading
from datetime import date
from typing import Any

PRIORITIES = ("low", "medium", "high")
MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000


class _Unset:
    """Sentinel distinguishing "field not provided" from "explicitly cleared"."""

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Any = _Unset()


def validate_title(title: str) -> str:
    """Return the stripped title.

    Raises:
        TypeError: If ``title`` is not a string.
        ValueError: If the title is blank or longer than ``MAX_TITLE_LENGTH``.
    """
    if not isinstance(title, str):
        raise TypeError(f"title must be a str, got {type(title).__name__}")
    cleaned = title.strip()
    if not cleaned:
        raise ValueError("title must not be empty")
    if len(cleaned) > MAX_TITLE_LENGTH:
        raise ValueError(f"title must be at most {MAX_TITLE_LENGTH} characters")
    return cleaned


def validate_description(description: str) -> str:
    """Return the description unchanged.

    Raises:
        TypeError: If ``description`` is not a string.
        ValueError: If it is longer than ``MAX_DESCRIPTION_LENGTH``.
    """
    if not isinstance(description, str):
        raise TypeError(f"description must be a str, got {type(description).__name__}")
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise ValueError(
            f"description must be at most {MAX_DESCRIPTION_LENGTH} characters"
        )
    return description


def validate_due_date(due_date: str | None) -> str | None:
    """Return the ISO due date, or ``None`` when it is absent or blank.

    Raises:
        TypeError: If ``due_date`` is neither a string nor ``None``.
        ValueError: If the value is not a valid ``YYYY-MM-DD`` date.
    """
    if due_date is None:
        return None
    if not isinstance(due_date, str):
        raise TypeError(
            f"due_date must be a str or None, got {type(due_date).__name__}"
        )
    cleaned = due_date.strip()
    if not cleaned:
        return None
    try:
        date.fromisoformat(cleaned)
    except ValueError as exc:
        raise ValueError(f"due_date must be YYYY-MM-DD, got {cleaned!r}") from exc
    return cleaned


def validate_priority(priority: str | None) -> str | None:
    """Return the priority, or ``None`` when it is absent or blank.

    Raises:
        TypeError: If ``priority`` is neither a string nor ``None``.
        ValueError: If the value is not one of ``PRIORITIES``.
    """
    if priority is None:
        return None
    if not isinstance(priority, str):
        raise TypeError(
            f"priority must be a str or None, got {type(priority).__name__}"
        )
    cleaned = priority.strip()
    if not cleaned:
        return None
    if cleaned not in PRIORITIES:
        raise ValueError(
            f"priority must be one of {', '.join(PRIORITIES)}, got {cleaned!r}"
        )
    return cleaned


class Task:
    """A single checklist item."""

    def __init__(
        self,
        task_id: int,
        title: str,
        description: str = "",
        completed: bool = False,
        due_date: str | None = None,
        priority: str | None = None,
    ) -> None:
        """Build a task.

        Args:
            task_id: Unique identifier within the owning store.
            title: Short summary of the work.
            description: Optional extra detail.
            completed: Whether the task is already done.
            due_date: Optional ``YYYY-MM-DD`` deadline.
            priority: Optional value from ``PRIORITIES``.
        """
        self.id = task_id
        self.title = title
        self.description = description
        self.completed = completed
        self.due_date = due_date
        self.priority = priority

    def to_dict(self) -> dict[str, Any]:
        """Return the task as a JSON-serialisable mapping."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "completed": self.completed,
            "due_date": self.due_date,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        """Build a task from a stored mapping.

        Raises:
            KeyError: If the required ``id`` or ``title`` keys are missing.
            TypeError: If the keys hold values of the wrong type.
        """
        return cls(
            task_id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            completed=data.get("completed", False),
            due_date=data.get("due_date"),
            priority=data.get("priority"),
        )

    def matches(self, text: str) -> bool:
        """Return whether ``text`` occurs in the title or description, ignoring case.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        if not isinstance(text, str):
            raise TypeError(f"search text must be a str, got {type(text).__name__}")
        needle = text.lower()
        haystack = f"{self.title}\n{self.description or ''}".lower()
        return needle in haystack

    def is_overdue(self) -> bool:
        """Return whether the task is pending and its due date has already passed."""
        if not self.due_date or self.completed:
            return False
        try:
            return date.fromisoformat(self.due_date) < date.today()
        except ValueError:
            return False


def _priority_rank(priority: str | None) -> int:
    """Return the sort rank of ``priority``; unknown values rank lowest."""
    if priority in PRIORITIES:
        return PRIORITIES.index(priority)
    return -1


class TaskManager:
    """Task collection persisted to a JSON file.

    An internal re-entrant lock guards the task list, so several threads may
    share one manager, and every mutation writes the file before returning.
    """

    def __init__(self, storage_file: str = "tasks.json") -> None:
        """Load the store backed by ``storage_file``, starting empty if it is absent."""
        if not isinstance(storage_file, str) or not storage_file.strip():
            raise ValueError("storage_file must be a non-empty string")
        self.storage_file = os.path.realpath(os.path.abspath(storage_file))
        self.tasks: list[Task] = []
        self._next_id = 1
        self._lock = threading.RLock()
        self.load()

    def add_task(
        self,
        title: str,
        description: str = "",
        due_date: str | None = None,
        priority: str | None = None,
    ) -> Task:
        """Create a pending task with the next free id and persist it immediately.

        Returns:
            The newly stored task, whose ``completed`` flag is ``False``.

        Raises:
            TypeError: If an argument has the wrong type.
            ValueError: If the title is blank or too long, or the date or
                priority is invalid.
        """
        clean_title = validate_title(title)
        clean_description = validate_description(description)
        clean_due_date = validate_due_date(due_date)
        clean_priority = validate_priority(priority)
        with self._lock:
            highest = max((task.id for task in self.tasks), default=0)
            self._next_id = max(self._next_id, highest + 1)
            task = Task(
                self._next_id,
                clean_title,
                clean_description,
                due_date=clean_due_date,
                priority=clean_priority,
            )
            self.tasks.append(task)
            self._next_id += 1
            self.save()
            return task

    def get_task(self, task_id: int) -> Task | None:
        """Return the task with ``task_id``, or ``None`` when it does not exist."""
        with self._lock:
            for task in self.tasks:
                if task.id == task_id:
                    return task
            return None

    def list_tasks(
        self,
        include_completed: bool = True,
        contains: str | None = None,
        status: str | None = None,
        sort: str | None = None,
    ) -> list[Task]:
        """Return the tasks matching the given filters.

        Args:
            include_completed: Set to ``False`` to drop completed tasks.
            contains: Keep only tasks whose title or description contains this text.
            status: ``"done"`` or ``"pending"`` to filter on completion state.
            sort: ``"due"`` or ``"priority"`` to order the result.
        """
        with self._lock:
            result = list(self.tasks)

        if status == "done":
            result = [task for task in result if task.completed]
        elif status == "pending" or not include_completed:
            result = [task for task in result if not task.completed]

        if contains:
            result = [task for task in result if task.matches(contains)]

        if sort == "due":
            result.sort(key=lambda task: (task.due_date is None, task.due_date or ""))
        elif sort == "priority":
            result.sort(key=lambda task: _priority_rank(task.priority), reverse=True)

        return result

    def complete_task(self, task_id: int) -> bool:
        """Mark the task done and persist it.

        Returns:
            ``True`` on success, ``False`` when the task does not exist.
        """
        with self._lock:
            task = self.get_task(task_id)
            if task is None:
                return False
            task.completed = True
            self.save()
            return True

    def reopen_task(self, task_id: int) -> bool:
        """Mark the task pending again and persist it.

        Returns:
            ``True`` on success, ``False`` when the task does not exist.
        """
        with self._lock:
            task = self.get_task(task_id)
            if task is None:
                return False
            task.completed = False
            self.save()
            return True

    def edit_task(
        self,
        task_id: int,
        title: str | None = None,
        description: str | None = None,
        due_date: str | None | Any = UNSET,
        priority: str | None | Any = UNSET,
    ) -> bool:
        """Apply the given fields to a task and persist it.

        ``title`` and ``description`` are changed only when not ``None``.
        ``due_date`` and ``priority`` use the ``UNSET`` sentinel so that passing
        ``None`` or ``""`` explicitly clears the field, while omitting the
        argument leaves it unchanged.

        Returns:
            ``True`` when the task was updated, ``False`` when it does not exist.

        Raises:
            TypeError: If an argument has the wrong type.
            ValueError: If the title, date or priority is invalid.
        """
        clean_title = None if title is None else validate_title(title)
        clean_description = (
            None if description is None else validate_description(description)
        )
        with self._lock:
            task = self.get_task(task_id)
            if task is None:
                return False
            if clean_title is not None:
                task.title = clean_title
            if clean_description is not None:
                task.description = clean_description
            if due_date is not UNSET:
                task.due_date = validate_due_date(due_date)
            if priority is not UNSET:
                task.priority = validate_priority(priority)
            self.save()
            return True

    def delete_task(self, task_id: int) -> bool:
        """Remove the task and persist the store.

        Returns:
            ``True`` when deleted, ``False`` when the task does not exist.
        """
        with self._lock:
            task = self.get_task(task_id)
            if task is None:
                return False
            self.tasks.remove(task)
            self.save()
            return True

    def stats(self) -> dict[str, int]:
        """Return counts of total, completed, pending and overdue tasks."""
        with self._lock:
            tasks = list(self.tasks)
        total = len(tasks)
        completed = sum(1 for task in tasks if task.completed)
        return {
            "total": total,
            "completed": completed,
            "pending": total - completed,
            "overdue": sum(1 for task in tasks if task.is_overdue()),
        }

    def save(self) -> None:
        """Write every task to the storage file, replacing it atomically.

        Raises:
            OSError: If the file cannot be written.
        """
        with self._lock:
            data = [task.to_dict() for task in self.tasks]
            directory = os.path.dirname(os.path.abspath(self.storage_file))
            handle_fd, temp_path = tempfile.mkstemp(
                dir=directory, prefix=".tasks-", suffix=".tmp"
            )
            try:
                with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
                    json.dump(data, handle, indent=2)
                os.replace(temp_path, self.storage_file)
            except BaseException:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise

    def load(self) -> None:
        """Replace the in-memory tasks with the stored ones.

        A missing, unreadable or malformed storage file leaves the manager empty
        instead of raising, so a damaged file never blocks adding tasks.
        """
        with self._lock:
            self.tasks = []
            self._next_id = 1
            if not os.path.exists(self.storage_file):
                return
            try:
                with open(self.storage_file, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                return
            if not isinstance(data, list):
                return
            for item in data:
                try:
                    self.tasks.append(Task.from_dict(item))
                except (KeyError, TypeError, AttributeError):
                    continue
            self._next_id = max((task.id for task in self.tasks), default=0) + 1
