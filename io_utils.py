import csv
import json
from typing import List

from task_manager import Task


FIELDS = ["id", "title", "description", "completed", "due_date", "priority"]


def export_tasks(tasks: List[Task], path: str, fmt: str = "json") -> None:
    if fmt == "json":
        with open(path, "w", encoding="utf-8") as f:
            json.dump([t.to_dict() for t in tasks], f, indent=2)
    elif fmt == "csv":
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            for t in tasks:
                writer.writerow(t.to_dict())
    else:
        raise ValueError(f"Unsupported export format: {fmt}")


def read_tasks(path: str) -> List[dict]:
    if path.lower().endswith(".csv"):
        with open(path, "r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def import_tasks(manager, path: str) -> int:
    raw = read_tasks(path)
    imported = 0
    for item in raw:
        title = item.get("title")
        if not title:
            continue
        completed = str(item.get("completed", "")).lower() in ("1", "true", "yes")
        priority = item.get("priority") or None
        due_date = item.get("due_date") or None
        task = manager.add_task(title, item.get("description") or "", due_date=due_date, priority=priority)
        if completed:
            manager.complete_task(task.id)
        imported += 1
    return imported
