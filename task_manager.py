import json
import os
from datetime import date
from typing import List, Dict, Optional

PRIORITIES = ("low", "medium", "high")


class Task:
    def __init__(
        self,
        task_id: int,
        title: str,
        description: str = "",
        completed: bool = False,
        due_date: Optional[str] = None,
        priority: Optional[str] = None,
    ):
        self.id = task_id
        self.title = title
        self.description = description
        self.completed = completed
        self.due_date = due_date
        self.priority = priority

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "completed": self.completed,
            "due_date": self.due_date,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Task":
        return cls(
            task_id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            completed=data.get("completed", False),
            due_date=data.get("due_date"),
            priority=data.get("priority"),
        )

    def matches(self, text: str) -> bool:
        needle = text.lower()
        return needle in self.title.lower() or needle in (self.description or "").lower()

    def is_overdue(self) -> bool:
        if not self.due_date or self.completed:
            return False
        try:
            return date.fromisoformat(self.due_date) < date.today()
        except ValueError:
            return False


def _priority_rank(priority: Optional[str]) -> int:
    if priority in PRIORITIES:
        return PRIORITIES.index(priority)
    return -1


class TaskManager:
    def __init__(self, storage_file: str = "tasks.json"):
        self.storage_file = storage_file
        self.tasks: List[Task] = []
        self._next_id = 1
        self.load()

    def add_task(
        self,
        title: str,
        description: str = "",
        due_date: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> Task:
        task = Task(self._next_id, title, description, due_date=due_date, priority=priority)
        self.tasks.append(task)
        self._next_id += 1
        self.save()
        return task

    def get_task(self, task_id: int) -> Optional[Task]:
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def list_tasks(
        self,
        include_completed: bool = True,
        contains: Optional[str] = None,
        status: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> List[Task]:
        result = list(self.tasks)

        if status == "done":
            result = [t for t in result if t.completed]
        elif status == "pending":
            result = [t for t in result if not t.completed]
        elif not include_completed:
            result = [t for t in result if not t.completed]

        if contains:
            result = [t for t in result if t.matches(contains)]

        if sort == "due":
            result.sort(key=lambda t: (t.due_date is None, t.due_date or ""))
        elif sort == "priority":
            result.sort(key=lambda t: _priority_rank(t.priority), reverse=True)

        return result

    def complete_task(self, task_id: int) -> bool:
        task = self.get_task(task_id)
        if task:
            task.completed = True
            self.save()
            return True
        return False

    def reopen_task(self, task_id: int) -> bool:
        task = self.get_task(task_id)
        if task:
            task.completed = False
            self.save()
            return True
        return False

    def edit_task(
        self,
        task_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        due_date: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if due_date is not None:
            task.due_date = due_date
        if priority is not None:
            task.priority = priority
        self.save()
        return True

    def delete_task(self, task_id: int) -> bool:
        task = self.get_task(task_id)
        if task:
            self.tasks.remove(task)
            self.save()
            return True
        return False

    def stats(self) -> Dict[str, int]:
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks if t.completed)
        return {
            "total": total,
            "completed": completed,
            "pending": total - completed,
            "overdue": sum(1 for t in self.tasks if t.is_overdue()),
        }

    def save(self) -> None:
        data = [t.to_dict() for t in self.tasks]
        with open(self.storage_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        if not os.path.exists(self.storage_file):
            self.tasks = []
            return
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.tasks = [Task.from_dict(d) for d in data]
                if self.tasks:
                    self._next_id = max(t.id for t in self.tasks) + 1
        except (json.JSONDecodeError, KeyError):
            self.tasks = []
