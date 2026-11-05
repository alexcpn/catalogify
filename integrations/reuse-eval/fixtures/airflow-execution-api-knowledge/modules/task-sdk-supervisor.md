---
type: Module
title: Task SDK supervisor
description: The parent process that forks or execs a task, watches its sockets and heartbeat, forwards its requests to the Execution API, and reports the final state; also used for callbacks and connection tests.
resource: https://github.com/apache/airflow/blob/main/task-sdk/src/airflow/sdk/execution_time/supervisor.py
tags: [task-sdk, supervisor, heartbeat, subprocess, signals, execution-api]
timestamp: 2026-09-29T09:11:25Z
source_files:
  - task-sdk/src/airflow/sdk/execution_time/supervisor.py
  - task-sdk/src/airflow/sdk/execution_time/callback_supervisor.py
  - task-sdk/src/airflow/sdk/execution_time/connection_test_supervisor.py
generated_by: catalogify/0.10.1
open_questions:
  - "When a heartbeat returns 409 because the attempt was forcibly moved out of running, is the intended outcome to kill the task process immediately, or to stop heartbeating and let the task finish?"
  - "Which team owns the stale-heartbeat threshold on the supervisor side, and is it documented as a hard SLA for the scheduler's zombie detection?"
---

# Responsibilities

`WatchedSubprocess` (with `ActivitySubprocess` for task attempts) starts the
task process, owns its pipes, and runs the event loop that services its
requests. The supervisor sends a heartbeat to the Execution API on a timer,
forwards each `ToSupervisor` message to the [client](../modules/task-sdk-api-client.md),
and sends the result back over [comms](../modules/task-sdk-comms.md). After the
task exits it reports the final state. The same machinery runs callbacks
(`CallbackSubprocess`, `supervise_callback`) and connection tests
(`supervise_connection_test`). `InProcessTestSupervisor` and
`run_task_in_process` run a task without a child process for `dag.test`.

The forked child calls `block_orm_access`, which makes direct database access
from task code fail. Task code must reach metadata only through the Execution
API.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `WatchedSubprocess` | Base class: process lifecycle, sockets, signal and exit handling. |
| `ActivitySubprocess` | Supervisor for a task attempt: heartbeat, state reporting, request forwarding. |
| `InProcessTestSupervisor`, `run_task_in_process` | In-process execution path used by `dag.test`. |
| `ProcessTracker`, `PsutilTracker` | Track child processes so orphans can be found and killed. |
| `block_orm_access` | Blocks direct ORM access in the child process. |
| `CallbackSubprocess`, `supervise_callback`, `execute_callback` | Callback execution under supervision. |
| `supervise_connection_test` | Connection test execution under supervision. |

# Dependencies

- Talks to the task process through [Task SDK comms](../modules/task-sdk-comms.md) and to the server through the [Task SDK API client](../modules/task-sdk-api-client.md).
- Reports state to the routes in [task instances](../apis/execution-api-task-instances.md); connection tests use [connections and variables](../apis/execution-api-connections-and-variables.md).
- Launches the child that runs [Task SDK task runner](../modules/task-sdk-task-runner.md) code (`task_runner.py`, `execute_workload.py`).
- Forwards trace context to the server (`f481758f04`).

# Gotchas

- A forcibly-failed attempt must not leave orphan children. `6145746438` fixed orphaned subprocesses and a supervisor crash on heartbeat 409; `ce1270b96f` added the 410 Gone response that the supervisor now distinguishes from a plain conflict.
- Termination signals are forwarded from the supervisor to the task process (`4f76227dbd`). The supervisor has to remain PID 1-safe in containers, which is why the forwarding exists.
- `DagProcessorJob` could crash on an orphan processor kill because a closed log handle stayed on the selector (`6d9cc2ed37`). Cleanup of sockets must unregister them before the next select.
- Retry reporting is delayed until finalization completes (`e1f0041325`), so a retry decision is not visible to the scheduler mid-finalize.
- Heartbeats are not retried by the general worker retry policy (`cb9765fa4e`).
- A remote-logging connection cache keyed by the API client retained clients indefinitely (`416c73e864`). Cache keys must not hold the client.

# Citations

1. `6145746438`: fixes orphaned subprocesses and supervisor crash on heartbeat 409.
2. `ce1270b96f`: returns 410 Gone for heartbeat when the cleared TI exists in the history table.
3. `4f76227dbd`: forwards termination signals from the supervisor to the task subprocess.
4. `6d9cc2ed37`: fixes the DagProcessorJob crash on orphan processor kill.
5. `e1f0041325`: delays retry reporting until task finalization completes.
6. `cb9765fa4e`: task heartbeats are not retried under `[workers] execution_api_retries`.
7. `416c73e864`: fixes a memory leak in the remote logging connection cache.
