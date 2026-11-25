"""Command-line interface for the task checklist manager."""

import argparse
import os
import sys

from formatter import format_stats, format_tasks
from io_utils import export_tasks, import_tasks
from task_manager import PRIORITIES, UNSET, TaskManager


def _is_within(candidate: str, root: str) -> bool:
    """Return whether ``candidate`` is ``root`` itself or lives beneath it.

    Uses :func:`os.path.commonpath`, which compares path components rather than
    string prefixes, so sibling paths that merely share a prefix (``/data`` vs
    ``/data-other``) are not treated as contained. Root is handled correctly:
    every absolute path is inside ``/`` on POSIX.
    """
    try:
        return os.path.commonpath([os.path.realpath(candidate), root]) == root
    except ValueError:
        return False


def resolve_storage_path(path: str, base_dir: str | None = None) -> str:
    """Resolve the user-supplied storage path.

    Absolute paths are honoured as an explicit user choice; relative paths are
    resolved against ``base_dir`` and must stay inside it, so a relative value
    such as ``../secrets.json`` cannot escape. In both cases the parent directory
    must already exist.

    Args:
        path: Storage file path given on the command line.
        base_dir: Folder relative paths resolve against; defaults to the
            current directory.

    Returns:
        The absolute, symlink-free path to the storage file.

    Raises:
        TypeError: If ``path`` is not a string.
        ValueError: If the path is empty, a relative path escapes ``base_dir``,
            or the parent directory does not exist.
    """
    if not isinstance(path, str):
        raise TypeError(f"storage file path must be a str, got {type(path).__name__}")
    if not path.strip():
        raise ValueError("storage file path must not be empty")
    root = os.path.realpath(base_dir or os.getcwd())
    if os.path.isabs(path):
        resolved = os.path.realpath(path)
    else:
        resolved = os.path.realpath(os.path.join(root, path))
        if not _is_within(resolved, root):
            raise ValueError(f"storage file must stay inside {root}, got {path!r}")
    parent = os.path.dirname(resolved)
    if not os.path.isdir(parent):
        raise ValueError(f"storage directory does not exist: {parent}")
    return resolved


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the ``cli.py`` command line."""
    parser = argparse.ArgumentParser(description="Simple task checklist manager")
    parser.add_argument("--file", default="tasks.json", help="Storage file path")

    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="Add a new task")
    add_p.add_argument("title", help="Task title")
    add_p.add_argument("-d", "--description", default="", help="Task description")
    add_p.add_argument("--due", help="Due date (YYYY-MM-DD)")
    add_p.add_argument("--priority", choices=PRIORITIES, help="Task priority")

    list_p = sub.add_parser("list", aliases=["index"], help="List tasks (alias: index)")
    list_p.add_argument(
        "-a", "--all", action="store_true", help="Include completed tasks"
    )
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

    return parser


def run_command(args: argparse.Namespace, manager: TaskManager) -> int:
    """Execute the parsed subcommand against ``manager``.

    Args:
        args: Parsed command-line arguments.
        manager: Store the command operates on.

    Returns:
        ``0`` on success, ``1`` when the given task id does not exist.
    """
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
        if not manager.complete_task(args.id):
            print(f"Task {args.id} not found")
            return 1
        print(f"Completed task {args.id}")
    elif args.command == "reopen":
        if not manager.reopen_task(args.id):
            print(f"Task {args.id} not found")
            return 1
        print(f"Reopened task {args.id}")
    elif args.command == "edit":
        updated = manager.edit_task(
            args.id,
            title=args.title,
            description=args.description,
            due_date=args.due if args.due is not None else UNSET,
            priority=args.priority if args.priority is not None else UNSET,
        )
        if not updated:
            print(f"Task {args.id} not found")
            return 1
        print(f"Updated task {args.id}")
    elif args.command == "delete":
        if not manager.delete_task(args.id):
            print(f"Task {args.id} not found")
            return 1
        print(f"Deleted task {args.id}")
    elif args.command == "stats":
        print(format_stats(manager.stats()))
    elif args.command == "export":
        export_tasks(manager.tasks, args.out, fmt=args.format)
        print(f"Exported {len(manager.tasks)} task(s) to {args.out}")
    elif args.command == "import":
        count = import_tasks(manager, args.path)
        print(f"Imported {count} task(s) from {args.path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return the process exit code.

    Args:
        argv: Arguments to parse; defaults to ``sys.argv[1:]``.

    Returns:
        ``0`` on success, ``1`` for an unknown task id, ``2`` for invalid input.
    """
    args = build_parser().parse_args(argv)
    try:
        storage_file = resolve_storage_path(args.file)
        manager = TaskManager(storage_file=storage_file)
        return run_command(args, manager)
    except (ValueError, TypeError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
