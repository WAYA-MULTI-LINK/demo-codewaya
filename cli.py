import argparse
import sys

from task_manager import TaskManager, PRIORITIES
from formatter import format_tasks, format_stats
from io_utils import export_tasks, import_tasks


def main():
    """Parse command-line arguments and dispatch to the matching task command.

    Commands write their result to stdout and exit non-zero when a referenced
    task id does not exist. Accepts no arguments directly; reads ``sys.argv``.
    """
    parser = argparse.ArgumentParser(description="Simple task checklist manager")
    parser.add_argument("--file", default="tasks.json", help="Storage file path")

    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="Add a new task")
    add_p.add_argument("title", help="Task title")
    add_p.add_argument("-d", "--description", default="", help="Task description")
    add_p.add_argument("--due", help="Due date (YYYY-MM-DD)")
    add_p.add_argument("--priority", choices=PRIORITIES, help="Task priority")

    list_p = sub.add_parser(
        "list", aliases=["index"], help="List tasks (alias: index)"
    )
    list_p.add_argument("-a", "--all", action="store_true", help="Include completed tasks")
    list_p.add_argument("--contains", help="Filter by text in title/description")
    list_p.add_argument("--done", action="store_true", help="Only completed tasks")
    list_p.add_argument("--pending", action="store_true", help="Only pending tasks")
    list_p.add_argument("--sort", choices=("due", "priority"), help="Sort order")

    done_p = sub.add_parser("done", help="Mark a task as completed")
    done_p.add_argument("id", type=int, help="Task id")

    reopen_p = sub.add_parser("reopen", help="Mark a completed task as pending")
    reopen_p.add_argument("id", type=int, help="Task id")

    edit_p = sub.add_parser("edit", help="Edit a task")
    edit_p.add_argument("id", type=int, help="Task id")
    edit_p.add_argument("--title", help="New title")
    edit_p.add_argument("--description", help="New description")
    edit_p.add_argument("--due", help="New due date (YYYY-MM-DD)")
    edit_p.add_argument("--priority", choices=PRIORITIES, help="New priority")

    del_p = sub.add_parser("delete", help="Delete a task")
    del_p.add_argument("id", type=int, help="Task id")

    sub.add_parser("stats", help="Show task statistics")

    export_p = sub.add_parser("export", help="Export tasks")
    export_p.add_argument("--format", choices=("json", "csv"), default="json")
    export_p.add_argument("--out", required=True, help="Output path")

    import_p = sub.add_parser("import", help="Import tasks from a file")
    import_p.add_argument("path", help="Input path (.json or .csv)")

    args = parser.parse_args()
    manager = TaskManager(storage_file=args.file)

    if args.command == "add":
        task = manager.add_task(
            args.title, args.description, due_date=args.due, priority=args.priority
        )
        print(f"Added task {task.id}: {task.title}")
    elif args.command in ("list", "index"):
        status = "done" if args.done else "pending" if args.pending else None
        tasks = manager.list_tasks(
            include_completed=args.all,
            contains=args.contains,
            status=status,
            sort=args.sort,
        )
        print(format_tasks(tasks))
    elif args.command == "done":
        if manager.complete_task(args.id):
            print(f"Completed task {args.id}")
        else:
            print(f"Task {args.id} not found")
            sys.exit(1)
    elif args.command == "reopen":
        if manager.reopen_task(args.id):
            print(f"Reopened task {args.id}")
        else:
            print(f"Task {args.id} not found")
            sys.exit(1)
    elif args.command == "edit":
        if manager.edit_task(
            args.id,
            title=args.title,
            description=args.description,
            due_date=args.due,
            priority=args.priority,
        ):
            print(f"Updated task {args.id}")
        else:
            print(f"Task {args.id} not found")
            sys.exit(1)
    elif args.command == "delete":
        if manager.delete_task(args.id):
            print(f"Deleted task {args.id}")
        else:
            print(f"Task {args.id} not found")
            sys.exit(1)
    elif args.command == "stats":
        print(format_stats(manager.stats()))
    elif args.command == "export":
        export_tasks(manager.tasks, args.out, fmt=args.format)
        print(f"Exported {len(manager.tasks)} task(s) to {args.out}")
    elif args.command == "import":
        count = import_tasks(manager, args.path)
        print(f"Imported {count} task(s) from {args.path}")


if __name__ == "__main__":
    main()
