---
type: Module
title: Task SDK task runner (task process)
description: The child-side code that runs user operator code for one task instance, builds the runtime context, reports XComs and state, and maps outcomes to retry, defer or failure.
resource: https://github.com/apache/airflow/blob/main/task-sdk/src/airflow/sdk/execution_time/task_runner.py
tags: [module, task-sdk, task-runner, runtime, context]
timestamp: 2026-09-30T16:10:25+08:00
source_files:
  - task-sdk/src/airflow/sdk/execution_time/task_runner.py
  - task-sdk/src/airflow/sdk/execution_time/context.py
generated_by: catalogify/0.11.0
open_questions:
  - "Retry-policy evaluation (`_evaluate_retry_policy`) runs in the child, but the retry decision is persisted by the server. Which side is authoritative if the two disagree after a supervisor restart?"
  - "Is the 'reporting after finalization' ordering (commit e1f0041325) a guaranteed invariant for operators with `on_failure_callback`, or a best-effort ordering?"
  - "Who owns `RuntimeTaskInstance` API compatibility for third-party operators that subclass it?"
---

# Responsibilities

Runs in the task child process. `main` reads `StartupDetails` from the comms channel, calls `startup` to parse the Dag and task and build `RuntimeTaskInstance` and the `Context`, then `run` executes the operator and maps the result. Outcomes are: success (`_handle_current_task_success`), retry (`_evaluate_retry_policy` then `RetryTask`), deferral (`_defer_task`), await input (`_await_input_task`), or failure (`_handle_current_task_failed` / `_finalize_task_failure`). `finalize` runs callbacks and error e-mails and then sends the final state message to the supervisor.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `main` | Child-process entry point. |
| `get_startup_details` | Reads the first message from the comms channel. |
| `startup` | Parses the Dag and task and returns `(RuntimeTaskInstance, Context, Logger)`. |
| `run` | Executes the operator and returns the outcome. |
| `finalize` | Runs post-task callbacks and sends the final state. |
| `RuntimeTaskInstance` | The task-instance object operators see; reads and writes through comms. |
| `parse` | Builds the runtime task from the Dag bag. |
| `reinit_supervisor_comms` | Re-establishes the comms channel after a fork. |

# Dependencies

- Messages from [comms](sdk-comms.md); the supervisor answers them in [supervisor](sdk-supervisor.md).
- The task process makes no HTTP calls itself; see the [task SDK runtime service](../services/task-sdk-runtime.md) and the [guardrail](../operations/guardrails/task-code-no-direct-metadata-db.md).
- The context object is defined in `context.py` (this concept's second source file).
- Fields in `TIRunContext` come from the [datamodels](../data/execution-api-datamodels.md).

# Gotchas

- Commit `2b8c80568b` touched `context.py` as well as the secrets backend. A `Context` accessor that catches broad exceptions around a secrets lookup could hide an authz denial, so keep denials propagating.
- Commit `f14bed9b85` persisted `retry_reason` on any failure, so the failure path now reports a reason where it previously reported none.

# Citations

- `2b8c80568b` — authz denial in `context.py`.
- `f14bed9b85` — `retry_reason` on failure.
