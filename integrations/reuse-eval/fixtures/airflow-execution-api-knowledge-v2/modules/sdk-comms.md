---
type: Module
title: Task SDK comms protocol (task process ↔ supervisor)
description: The length-prefixed msgpack request/response protocol that lets a task process ask its supervisor for XComs, variables, connections and state without holding an HTTP connection.
resource: https://github.com/apache/airflow/blob/main/task-sdk/src/airflow/sdk/execution_time/comms.py
tags: [module, task-sdk, ipc, msgpack, protocol]
timestamp: 2026-09-25T12:29:14+01:00
source_files:
  - task-sdk/src/airflow/sdk/execution_time/comms.py
generated_by: catalogify/0.11.0
relations:
  - {kind: changes_with, target: task-sdk/src/airflow/sdk/execution_time/supervisor.py, evidence: [f14bed9b85, f72e6c9bef, 40311ffe4d]}
open_questions:
  - "Is the 4-byte big-endian length prefix a frozen part of the protocol, or may it change with a new protocol version? Nothing in the module records a protocol version field."
  - "The protocol is also specified in the Go SDK coordinator ADR (go-sdk/adr/0003-coordinator-protocol-msgpack-ipc.md, outside this bundle). Which document is authoritative when they disagree?"
  - "Who owns the decision that task processes must not open their own HTTP connection, and is it recorded anywhere besides the module docstring?"
---

# Responsibilities

Defines the wire messages between the task process and its supervisor. Requests are written by the child to its stdin socket as a msgspec `_RequestFrame` (4-byte big-endian length, then msgpack); responses come back as `_ResponseFrame`. Log lines travel on a separate JSON line channel. The protocol is deliberately request/response only: the task process sends nothing unless it is waiting for an answer, because it may be running user code that must not be interrupted. `CommsDecoder` is the child-side reader and writer.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `CommsDecoder` | Generic frame reader/writer used by the task process. |
| `DeadlockImminentError` | A `BaseException` subclass, so a user `except Exception` does not swallow it. |
| `StartupDetails` | First message: identity and run context for the task. |
| Request messages `GetXCom`, `SetXCom`, `GetConnection`, `GetVariable`, `PutVariable`, `GetDagRun`, … | One class per request kind. |
| Result types `XComResult`, `ConnectionResult`, `VariableResult`, `DagRunResult`, … | Responses the child deserialises. |
| Terminal messages `SucceedTask`, `RetryTask`, `DeferTask`, `RescheduleTask`, `SkipDownstreamTasks` | Final state the supervisor forwards to the API. |

# Dependencies

- The supervisor's handlers in [supervisor](sdk-supervisor.md) read these messages. Shared handler functions live in `request_handlers.py`, described under the [task SDK runtime service](../services/task-sdk-runtime.md).
- The child-side loop in [task runner](sdk-task-runner.md) sends them.
- Message types that correspond to Execution API calls must match the server's datamodels; see [datamodels](../data/execution-api-datamodels.md).
- The [add-field playbook](../operations/playbooks/add-execution-api-field.md) lists this file as a required touch point for new message types.

# Gotchas

- Frame reads must accumulate short reads on the header as well as the payload. Commit `f72e6c9bef` ("Fix short-read handling in task-sdk IPC framing") fixed a 4-byte header read that returned fewer bytes, which deadlocked the supervisor selector. Regression tests use a socket that returns 2 bytes at a time.
- Trace context is carried through the IPC channel so that API calls made for a task are parented to the task's span. Commit `f481758f04` ("Propagate task OTel trace context through IPC and into execution API requests") added this and changed the same files as the client.
- Commit `f14bed9b85` (retry reason persisted on any failure) touched comms and supervisor together: a new terminal field needs both the message class and the supervisor handler.
- Commit `40311ffe4d` (partition-key filters on asset events) is another commit that changed both `comms.py` and `supervisor.py`.

# Citations

- `f72e6c9bef` — short-read IPC framing fix.
- `f481758f04` — OTel trace context through IPC.
- `f14bed9b85` — `retry_reason` persisted on failure.
- `40311ffe4d` — asset-event partition-key filters.
