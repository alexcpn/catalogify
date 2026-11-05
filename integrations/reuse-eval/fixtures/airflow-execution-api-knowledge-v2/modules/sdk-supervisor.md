---
type: Module
title: Task SDK supervisor
description: The worker-side parent process that forks or execs the task process, owns the Execution API connection and heartbeats, forwards logs and signals, and reports the final state.
resource: https://github.com/apache/airflow/blob/main/task-sdk/src/airflow/sdk/execution_time/supervisor.py
tags: [module, task-sdk, supervisor, worker, heartbeat]
timestamp: 2026-09-29T14:41:25+05:30
source_files:
  - task-sdk/src/airflow/sdk/execution_time/supervisor.py
  - task-sdk/src/airflow/sdk/execution_time/callback_supervisor.py
generated_by: catalogify/0.11.0
relations:
  - {kind: changes_with, target: task-sdk/src/airflow/sdk/execution_time/comms.py, evidence: [f14bed9b85, f72e6c9bef, 40311ffe4d]}
open_questions:
  - "What is the escalation path when the supervisor's selector loop is blocked by a slow log sink? The heartbeat-retry commit notes that client backoff blocked the loop, but no timeout is documented for the log path."
  - "Is `block_orm_access()` (supervisor.py, called in the fork path) the only guard against task-side metadata DB access, or are there deployments that rely on network-level blocking as the commit that added it suggests?"
  - "Which team owns Dag processor orphan-kill handling that shares `WatchedSubprocess` (commit 6d9cc2ed37), and is it covered by the same tests?"
---

# Responsibilities

Runs one task instance from the worker side. `supervise_task` starts the child (fork, or `posix_spawn` / exec when configured), installs signal handlers, and runs a selector loop that: dispatches framed requests from the child to `request_handlers`, forwards task logs from the log socket, heartbeats the task instance through the [API client](sdk-api-client.md), and waits for the child to exit. `callback_supervisor` runs the same pattern for deadline callbacks. `block_orm_access` is applied in the child before user code runs.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `supervise_task`, `supervise` | Entry points; `supervise` takes keyword arguments from the worker. |
| `WatchedSubprocess` | Generic child-process watcher with selector, log forwarding and kill escalation. |
| `ActivitySubprocess` | Task-instance specialisation; owns heartbeats and final state. |
| `InProcessTestSupervisor`, `run_task_in_process` | In-process variant. |
| `block_orm_access`, `BlockedDBSession` | Child-side guard that replaces the ORM session with one that raises. |
| `ProcessTracker`, `PsutilTracker` | Tracks spawned descendants so they can be killed with the task. |
| `supervise_callback`, `CallbackSubprocess` (in `callback_supervisor.py`) | Deadline-callback equivalent. |

# Dependencies

- Child protocol: [comms](sdk-comms.md) (`CommsDecoder`, messages).
- HTTP: [API client](sdk-api-client.md) — heartbeats, state updates, XComs.
- Request dispatch: `request_handlers.py` (shared with callbacks and the triggerer).
- Child-side logic: [task runner](sdk-task-runner.md).
- Server side of every call: [routes](../apis/execution-api-routes.md).

# Gotchas

- A heartbeat 409 means the server has moved the task out of `running` (scheduler reset or operator PATCH). The supervisor kills the child and must also kill descendants. Commit `6145746438` ("Fix orphaned subprocesses and supervisor crash on heartbeat 409") fixed children reparented to PID 1 and a supervisor crash on this path.
- SIGTERM and SIGINT are forwarded to the child so that the operator's `on_kill()` runs before exit. Commit `4f76227dbd` ("Forward termination signals from supervisor to task subprocess") added this; before it, a Kubernetes pod shutdown orphaned the child.
- Retry reporting is delayed until task finalization completes (commit `e1f0041325`, "Delay retry reporting until task finalization completes"). Keep the final-state report after the finalization step when adding an outcome path.
- Task logs are uploaded even when the final state update fails (commit `033aeb1a7c`, "Upload task logs even when final state update fails"). Log upload must not depend on the state update succeeding.
- `WatchedSubprocess` cleanup must unregister sockets from the shared selector before the process exits; commit `6d9cc2ed37` fixed a crash where a closed log handle was written to after SIGKILL.
- Child startup moved to `os.posix_spawn` in `ddfc357e83`. The fork path (`_fork_main`) still exists, and fork+exec is selected through `execute_tasks_new_python_interpreter` (commit `4e52a36e81`). Test both when changing startup code.
- Heartbeat retries are limited by `[workers] max_failed_heartbeats` (default raised to 30 in `cb9765fa4e`).

# Citations

- `6145746438` — heartbeat 409 and orphaned children.
- `4f76227dbd` — signal forwarding.
- `6d9cc2ed37` — orphan-kill socket cleanup.
- `e1f0041325` — retry reporting after finalization.
- `033aeb1a7c` — log upload independent of state update.
- `ddfc357e83` — `posix_spawn` instead of fork+exec.
- `cb9765fa4e` — heartbeat retry policy.
