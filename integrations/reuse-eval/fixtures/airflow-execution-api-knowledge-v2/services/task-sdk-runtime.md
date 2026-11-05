---
type: Service
title: Task SDK runtime (supervisor and task process)
description: The worker-side pair of processes that run one task instance — a supervisor that owns HTTP and heartbeats, and a task process that runs user code and speaks only over the comms socket.
resource: https://github.com/apache/airflow/blob/main/task-sdk/src/airflow/sdk/execution_time/supervisor.py
tags: [service, task-sdk, worker, supervisor, execution-time]
timestamp: 2026-09-30T16:10:25+08:00
source_files:
  - task-sdk/src/airflow/sdk/execution_time/supervisor.py
  - task-sdk/src/airflow/sdk/execution_time/task_runner.py
  - task-sdk/src/airflow/sdk/execution_time/comms.py
generated_by: catalogify/0.11.0
open_questions:
  - "What is the intended behaviour when the supervisor is killed while the task process is in a user-level subprocess (virtualenv, Docker exec)? Commit 6145746438 handles the 409 path; the SIGKILL path is not described in code comments."
  - "Is `[workers] max_failed_heartbeats` default 30 chosen to match the scheduler's zombie-detection window? The commit message says roughly equivalent but does not show the derivation."
  - "Who owns worker-side failure escalation when the supervisor itself crashes after the task has finished, and where is that documented for operators?"
---

# Responsibilities

Runs exactly one task instance per worker process pair. The supervisor (`ActivitySubprocess` / `WatchedSubprocess`) owns the HTTP connection to the Execution API, heartbeats the task instance, forwards logs and watches the child. The task process (`task_runner.main`) runs operator code, serialises XComs and state updates, and reports the final state back through the supervisor. Control flow is a selector loop in the supervisor that dispatches framed requests from the child and reads task logs from a separate socket.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `supervise_task` / `supervise` | Entry points the worker calls to run one task instance. |
| `WatchedSubprocess`, `ActivitySubprocess` | Supervisor process object and its task specialisation. |
| `InProcessTestSupervisor`, `run_task_in_process` | In-process supervisor used for running a task without a worker subprocess. |
| `task_runner.main`, `task_runner.run`, `task_runner.finalize` | Task-process entry, execution, and final state reporting. |
| `CommsDecoder` (in `comms.py`) | Reads and writes the framed request/response protocol on the child's stdin. |

# Dependencies

- [Supervisor](../modules/sdk-supervisor.md), [task runner](../modules/sdk-task-runner.md) and [comms](../modules/sdk-comms.md) are the three module concepts.
- Calls the Execution API via the [Task SDK API client](../modules/sdk-api-client.md); the client runs in the supervisor, never in the task process.
- Calls the server described in the [Execution API service](execution-api.md).
- Enforces the [task-code-no-metadata-DB guardrail](../operations/guardrails/task-code-no-direct-metadata-db.md) by replacing the ORM session with `BlockedDBSession` in the child.

# Gotchas

- A 409 on heartbeat means the server has moved the task out of `running`. The supervisor must kill the task and also its spawned children; commit `6145746438` ("Fix orphaned subprocesses and supervisor crash on heartbeat 409") fixed orphaned children reparented to PID 1.
- Signals arriving at the supervisor (for example SIGTERM from a Kubernetes pod) must be forwarded to the child so that `on_kill()` runs. Commit `4f76227dbd` ("Forward termination signals from supervisor to task subprocess") added this forwarding.
- Frame reads on the comms socket must accumulate short reads. Commit `f72e6c9bef` ("Fix short-read handling in task-sdk IPC framing") fixed a case where a 4-byte length prefix read returned fewer bytes and the supervisor's selector never dispatched the frame.
- Heartbeat retries are governed only by `[workers] max_failed_heartbeats`, not by the client retry setting. Commit `cb9765fa4e` made this change because client backoff blocked the supervisor loop from forwarding logs.

# Citations

- `6145746438` — heartbeat 409 handling and orphaned subprocesses.
- `4f76227dbd` — SIGTERM/SIGINT forwarding to the task subprocess.
- `f72e6c9bef` — short-read fix in IPC framing.
- `cb9765fa4e` — heartbeat retry policy.
