# User Stories — Demo Codewaya (Task Checklist)

This document captures user stories for the `demo-codewaya` task checklist app.

Legend:
- **Status**: `Done` (already implemented) / `Planned` (not yet built)
- **Priority**: MoSCoW (`Must`, `Should`, `Could`)
- **ID format**: `US-XX`

## Personas
- **Individual user** — a single person managing a personal to-do list from the command line.
- **Demo/codewaya tester** — a developer exercising the app to validate tooling (codewaya).

---

## Core Task Management

### US-01 — Add a task
**As an** individual user, **I want** to add a task with a title and optional description, **so that** I can capture something I need to do.
- **Status:** Done · **Priority:** Must
- **Acceptance criteria:**
  - `python cli.py add "Title"` creates a task with a unique incrementing id.
  - Optional `-d/--description` stores extra detail.
  - New tasks default to not completed.
  - Task is persisted to storage immediately.
- **Tests:** `test_add_task`, `test_ids_not_reused`

### US-02 — List tasks
**As an** individual user, **I want** to see my tasks with a clear done/not-done indicator, **so that** I know what is left to do.
- **Status:** Done · **Priority:** Must
- **Acceptance criteria:**
  - `python cli.py list` shows only incomplete tasks.
  - `python cli.py list --all` shows all tasks.
  - Each line shows status (`[x]`/`[ ]`), id, title, and description when present.
  - Empty list prints a friendly "No tasks found." message.
- **Tests:** `test_list_incomplete`

### US-03 — Mark a task complete
**As an** individual user, **I want** to mark a task as completed, **so that** I can track progress.
- **Status:** Done · **Priority:** Must
- **Acceptance criteria:**
  - `python cli.py done <id>` marks the task completed and persists it.
  - An unknown id reports "Task <id> not found" and exits with a non-zero code.
- **Tests:** `test_complete_task`

### US-04 — Delete a task
**As an** individual user, **I want** to delete a task, **so that** I can remove items I no longer need.
- **Status:** Done · **Priority:** Must
- **Acceptance criteria:**
  - `python cli.py delete <id>` removes the task and persists the change.
  - An unknown id reports "Task <id> not found" and exits with a non-zero code.
- **Tests:** `test_delete_task`

### US-05 — Persist tasks between runs
**As an** individual user, **I want** my tasks saved to disk, **so that** they survive across program restarts.
- **Status:** Done · **Priority:** Must
- **Acceptance criteria:**
  - Tasks are stored in `tasks.json` (configurable via `--file`).
  - On startup, existing tasks are loaded and the next id continues from the highest existing id.
  - Corrupt/missing storage starts with an empty list rather than crashing.
- **Tests:** `test_persistence`, `test_ids_not_reused`

### US-06 — Choose a storage file
**As a** demo/codewaya tester, **I want** to point the app at a custom storage file, **so that** I can run isolated scenarios without clobbering my main task list.
- **Status:** Done · **Priority:** Should
- **Acceptance criteria:**
  - `--file <path>` overrides the default `tasks.json`.
- **Tests:** Covered indirectly via `TaskManager(storage_file=...)` in all tests.

---

## Extended Features

### US-07 — Reopen a completed task
**As an** individual user, **I want** to mark a completed task as not done again, **so that** I can correct mistakes or repeat a recurring item.
- **Status:** Done · **Priority:** Should
- **Acceptance criteria:**
  - `python cli.py reopen <id>` sets `completed = False` and persists it.
  - An unknown id reports an error and exits with a non-zero code.
- **Tests:** `test_reopen_task`

### US-08 — Edit a task
**As an** individual user, **I want** to update a task's title, description, due date or priority, **so that** I can fix typos or add detail.
- **Status:** Done · **Priority:** Should
- **Acceptance criteria:**
  - `python cli.py edit <id> [--title ...] [--description ...] [--due ...] [--priority ...]` updates fields and persists.
  - Unknown id reports an error with non-zero exit code.
- **Tests:** `test_edit_task`

### US-09 — Search and filter tasks
**As an** individual user, **I want** to filter tasks by text or status, **so that** I can find items in a long list quickly.
- **Status:** Done · **Priority:** Could
- **Acceptance criteria:**
  - `python cli.py list --contains <text>` filters by title/description.
  - `python cli.py list --done` / `--pending` filter by completion status.
- **Tests:** `test_search_contains`, `test_filter_by_status`

### US-10 — Task statistics
**As an** individual user, **I want** a summary of total vs. completed vs. pending vs. overdue tasks, **so that** I can gauge overall progress.
- **Status:** Done · **Priority:** Could
- **Acceptance criteria:**
  - `python cli.py stats` prints counts of total, completed, pending, and overdue tasks.
- **Tests:** `test_stats_and_overdue`

### US-11 — Due dates and priorities
**As an** individual user, **I want** to assign a due date and priority to tasks, **so that** I can order my work.
- **Status:** Done · **Priority:** Could
- **Acceptance criteria:**
  - Tasks may carry `due_date` (YYYY-MM-DD) and `priority` (low/medium/high).
  - `python cli.py list --sort due` and `--sort priority` order the list.
  - Past-due, incomplete tasks are flagged as OVERDUE.
  - Persisted in `tasks.json` and backward-compatible with existing files.
- **Tests:** `test_sort_by_priority`, `test_stats_and_overdue`, `test_backward_compatible_load`

### US-12 — Import/export
**As a** demo/codewaya tester, **I want** to export/import tasks as JSON/CSV, **so that** I can move data between environments and share fixtures.
- **Status:** Done · **Priority:** Could
- **Acceptance criteria:**
  - `python cli.py export --format json|csv --out <path>`.
  - `python cli.py import <path>` adds tasks from a JSON/CSV file.
- **Tests:** `test_json_export_import`, `test_csv_export_import`

---

## Traceability

| Story | Area              | Status  | Tests                                   |
|-------|-------------------|---------|-----------------------------------------|
| US-01 | Add task          | Done    | test_add_task, test_ids_not_reused      |
| US-02 | List tasks        | Done    | test_list_incomplete                    |
| US-03 | Complete task     | Done    | test_complete_task                      |
| US-04 | Delete task       | Done    | test_delete_task                        |
| US-05 | Persistence       | Done    | test_persistence, test_ids_not_reused   |
| US-06 | Custom storage    | Done    | (via TaskManager(storage_file=...))     |
| US-07 | Reopen task       | Done    | test_reopen_task                        |
| US-08 | Edit task         | Done    | test_edit_task                          |
| US-09 | Search/filter     | Done    | test_search_contains, test_filter_by_status |
| US-10 | Statistics        | Done    | test_stats_and_overdue                  |
| US-11 | Due dates/priority| Done    | test_sort_by_priority, test_backward_compatible_load |
| US-12 | Import/export     | Done    | test_json_export_import, test_csv_export_import |
