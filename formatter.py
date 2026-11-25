from typing import List

from task_manager import Task


def format_task(task: Task) -> str:
    status = "[x]" if task.completed else "[ ]"
    parts = [f"{status} {task.id}. {task.title}"]
    if task.description:
        parts.append(f"- {task.description}")
    if task.priority:
        parts.append(f"(priority: {task.priority})")
    if task.due_date:
        due = f"(due: {task.due_date}"
        if task.is_overdue():
            due += ", OVERDUE"
        due += ")"
        parts.append(due)
    return " ".join(parts)


def format_tasks(tasks: List[Task]) -> str:
    if not tasks:
        return "No tasks found."
    return "\n".join(format_task(t) for t in tasks)


def format_stats(stats: dict) -> str:
    return (
        f"Total: {stats['total']} | "
        f"Completed: {stats['completed']} | "
        f"Pending: {stats['pending']} | "
        f"Overdue: {stats['overdue']}"
    )
