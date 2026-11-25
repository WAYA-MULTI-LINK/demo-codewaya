"""Human-readable formatting of tasks and statistics."""

from task_manager import Task


def format_task(task: Task) -> str:
    """Return a single-line rendering of ``task`` with status, id and details."""
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


def format_tasks(tasks: list[Task]) -> str:
    """Return the tasks one per line, or a friendly message when there are none."""
    if not tasks:
        return "No tasks found."
    return "\n".join(format_task(task) for task in tasks)


def format_stats(stats: dict[str, int]) -> str:
    """Return a one-line summary of total, completed, pending and overdue counts."""
    return (
        f"Total: {stats['total']} | "
        f"Completed: {stats['completed']} | "
        f"Pending: {stats['pending']} | "
        f"Overdue: {stats['overdue']}"
    )
