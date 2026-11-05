---
type: Module
title: Task SDK task runner
description: The child-side runtime that parses the startup message, builds the task context, executes the operator, maps the outcome to a terminal or deferred state and sends it back to the supervisor.
resource: https://github.com/apache/airflow/blob/main/task-sdk/src/airflow/sdk/execution_time/task_runner.py
tags: [task-sdk, task-runner, context, retry, execution, worker]
timestamp: 2026-09-30T08:10:25Z
source_files:
  - task-sdk/src/airflow/sdk/execution_time/task_runner.py
  - task-sdk/src/airflow/sdk/execution_time/execute_workload.py
  - task-sdk/src/airflow/sdk/execution_time/context.py
generated_by: catalogify/0.10.1
open_questions:
  - "Is the retry policy evaluation order relative to on_failure callbacks a documented contract, or an implementation detail that changed in 1e50b89cf8?"
---

# Responsibilities

`main` in `task_runner.py` runs inside the task child process. It reads the
`StartupDetails` message through `get_startup_details`, builds a
`RuntimeTaskInstance` with `parse` and `startup`, and runs the operator in
`run`. Outcomes map to success, retry, deferral, reschedule, await-input, skip
or failure, which `finalize` reports. `execute_workload.py` is the entry
point that the executor or coordinator starts. `context.py` builds the task
context mapping and the accessors that tasks use: `ConnectionAccessor`,
`VariableAccessor`, `TaskStateStoreAccessor`, `AssetStateStoreAccessor`,
`OutletEventAccessors`, `InletEventsAccessors`, `MacrosAccessor`.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `main` | Child-process entry point. |
| `startup`, `parse`, `get_startup_details` | Read the startup message and build the runtime task instance. |
| `RuntimeTaskInstance` | Task instance object seen by operators at run time. |
| `run` | Executes the operator and maps the result to a state. |
| `finalize` | Sends the terminal state and flushes spans. |
| `reinit_supervisor_comms` | Re-establishes comms after a fork. |
| `execute_workload` | Workload entry point (`execute_workload.py`). |
| `set_current_context`, `context_to_airflow_vars` | Build and expose the task context. |
| `ConnectionAccessor`, `VariableAccessor`, `TaskStateStoreAccessor`, `AssetStateStoreAccessor` | Context-time access to Execution API resources. |

# Dependencies

- Sends and receives its messages through [Task SDK comms](../modules/task-sdk-comms.md); its parent is [Task SDK supervisor](../modules/task-sdk-supervisor.md).
- Its accessors call the [Task SDK API client](../modules/task-sdk-api-client.md) indirectly through comms, which the supervisor turns into Execution API calls.
- Startup and state payloads are the [task instance routes](../apis/execution-api-task-instances.md) and their models.
- Asset and state-store access map to [assets](../apis/execution-api-assets.md) and [state stores](../apis/execution-api-state-stores.md).

# Gotchas

- Retry policy is decided outside the post-execute log group (`1e50b89cf8`). Code that reads the retry decision has to run after that block, not inside it.
- Branching over mapped tasks depends on the XCom backend. A branch that did not skip mapped tasks with a custom XCom backend was fixed in `bb5fc37da0`.
- Plugin macros are scoped to their team in multi-team mode (`63b615b252`).
- `retry_reason` is persisted on failure as well as on retry (`f14bed9b85`), so the failure path in `finalize` writes it.

# Citations

1. `1e50b89cf8`: moves the retry policy decision outside the post-execute log group block.
2. `bb5fc37da0`: fixes branch not skipping mapped tasks with a custom XCom backend.
3. `63b615b252`: scopes plugin macros to their team in multi-team mode.
4. `f14bed9b85`: persists `retry_reason` for failures as well as retries.
