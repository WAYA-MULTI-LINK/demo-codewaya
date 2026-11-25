"""JSON/CSV import and export helpers for task lists."""

import csv
import json
import os

from task_manager import (
    validate_due_date,
    validate_priority,
    validate_title,
    Task,
    TaskManager,
)

FIELDS = ["id", "title", "description", "completed", "due_date", "priority"]
SUPPORTED_FORMATS = ("json", "csv")
MAX_IMPORT_BYTES = 5 * 1024 * 1024
_TRUE_VALUES = ("1", "true", "yes")


def export_tasks(tasks: list[Task], path: str, fmt: str = "json") -> None:
    """Write ``tasks`` to ``path`` as JSON or CSV.

    Args:
        tasks: Tasks to serialise.
        path: Destination file path.
        fmt: Either ``"json"`` or ``"csv"``.

    Raises:
        ValueError: If ``fmt`` is not a supported format.
        OSError: If the destination cannot be written.
    """
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported export format: {fmt}. "
            f"Use one of {', '.join(SUPPORTED_FORMATS)}"
        )
    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        raise ValueError(f"Export directory does not exist: {directory}")

    if fmt == "json":
        with open(path, "w", encoding="utf-8") as handle:
            json.dump([task.to_dict() for task in tasks], handle, indent=2)
        return

    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for task in tasks:
            writer.writerow(task.to_dict())


def read_tasks(path: str) -> list[dict]:
    """Read task records from a JSON or CSV file.

    Args:
        path: Source file, detected as CSV by its ``.csv`` suffix.

    Returns:
        The raw records, one mapping per task.

    Raises:
        ValueError: If the file is too large or does not contain a list of records.
        OSError: If the file cannot be read.
    """
    size = os.path.getsize(path)
    if size > MAX_IMPORT_BYTES:
        raise ValueError(
            f"{path} is {size} bytes, larger than the {MAX_IMPORT_BYTES} byte limit"
        )

    if path.lower().endswith(".csv"):
        with open(path, "r", encoding="utf-8", newline="") as handle:
            records = list(csv.DictReader(handle))
    else:
        with open(path, "r", encoding="utf-8") as handle:
            records = json.load(handle)

    if not isinstance(records, list) or not all(
        isinstance(record, dict) for record in records
    ):
        raise ValueError(f"{path} must contain a list of task objects")
    return records


def _is_completed(value: object) -> bool:
    """Return whether a stored completion flag counts as done."""
    return str(value).strip().lower() in _TRUE_VALUES


def import_tasks(manager: TaskManager, path: str) -> int:
    """Add every valid record from ``path`` to ``manager``.

    Records without a usable title, due date or priority are skipped rather than
    aborting the whole import.

    Args:
        manager: Store the tasks are added to.
        path: JSON or CSV source file.

    Returns:
        The number of tasks imported.

    Raises:
        ValueError: If the file is unreadable as task records.
        OSError: If the file cannot be read.
    """
    raw = read_tasks(path)
    imported = 0
    for item in raw:
        try:
            title = validate_title(item.get("title") or "")
            due_date = validate_due_date(item.get("due_date") or None)
            priority = validate_priority(item.get("priority") or None)
        except (TypeError, ValueError):
            continue
        description = item.get("description") or ""
        if not isinstance(description, str):
            description = str(description)
        task = manager.add_task(
            title, description, due_date=due_date, priority=priority
        )
        if _is_completed(item.get("completed", "")):
            manager.complete_task(task.id)
        imported += 1
    return imported
