import json
import os
from typing import List, Dict, Optional


class Task:
    def __init__(self, task_id: int, title: str, description: str = "", completed: bool = False):
        self.id = task_id
        self.title = title
        self.description = description
        self.completed = completed

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Task":
        return cls(
            task_id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            completed=data.get("completed", False),
        )


class TaskManager:
    def __init__(self, storage_file: str = "tasks.json"):
        self.storage_file = storage_file
        self.tasks: List[Task] = []
        self._next_id = 1
        self.load()

    def add_task(self, title: str, description: str = "") -> Task:
        task = Task(self._next_id, title, description)
        self.tasks.append(task)
        self._next_id += 1
        self.save()
        return task

    def get_task(self, task_id: int) -> Optional[Task]:
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def list_tasks(self, include_completed: bool = True) -> List[Task]:
        if include_completed:
            return self.tasks
        return [t for t in self.tasks if not t.completed]

    def complete_task(self, task_id: int) -> bool:
        task = self.get_task(task_id)
        if task:
            task.completed = True
            self.save()
            return True
        return False

    def set_completed(self, task_id: int, completed: bool) -> Optional[Task]:
        task = self.get_task(task_id)
        if task:
            task.completed = completed
            self.save()
            return task
        return None

    def update_task(
        self,
        task_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[Task]:
        task = self.get_task(task_id)
        if not task:
            return None
        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        self.save()
        return task

    def delete_task(self, task_id: int) -> bool:
        task = self.get_task(task_id)
        if task:
            self.tasks.remove(task)
            self.save()
            return True
        return False

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
