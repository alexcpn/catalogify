---
type: Module
title: Task SDK supervisor-to-task message channel (comms)
description: The msgpack-framed socket protocol between a task process and its supervisor, including the request and response message types and the guard against deadlocked synchronous calls.
resource: https://github.com/apache/airflow/blob/main/task-sdk/src/airflow/sdk/execution_time/comms.py
tags: [task-sdk, ipc, msgpack, socket, supervisor, task-runner]
timestamp: 2026-09-25T11:29:14Z
source_files:
  - task-sdk/src/airflow/sdk/execution_time/comms.py
  - task-sdk/src/airflow/sdk/execution_time/request_handlers.py
generated_by: catalogify/0.10.1
open_questions:
  - "Is DeadlockImminentError meant to be caught by user code at all, given it derives from BaseException rather than Exception?"
  - "Which lang-SDK coordinator path is expected to send messages over this channel, and does it reuse CommsDecoder or a separate framing?"
---

# Responsibilities

Carries every request a task makes to the supervisor (XCom, variable,
connection, state store, asset and Dag run lookups) and the replies, over a
Unix socket. `CommsDecoder` is the task-side end: it writes msgpack request
frames with an incrementing ID, reads response frames, and decodes the body
against the `ToTask` union. `ToSupervisor` is the message union the supervisor
decodes. `request_handlers.py` holds the supervisor-side handlers that turn a
`ToSupervisor` message into a Task SDK `Client` call and return the result.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `CommsDecoder` | Task-side framed send and receive; holds the socket and the decoders. |
| `ToTask` | Discriminated union of messages the supervisor sends to the task (startup details, results). |
| `ToSupervisor` | Discriminated union of messages the task sends to the supervisor. |
| `StartupDetails` | First message a task receives; carries the run context. |
| `DeadlockImminentError` | Raised when a synchronous comms call would block on a paused event-loop thread. |
| `handle_get_connection` | Supervisor-side handler for a connection request. |
| `handle_get_variable`, `handle_put_variable`, `handle_delete_variable` | Supervisor-side variable handlers. |
| `handle_set_xcom`, `handle_get_xcom` | Supervisor-side XCom handlers. |

# Dependencies

- The supervisor side is [Task SDK supervisor](../modules/task-sdk-supervisor.md). The handlers call the [Task SDK API client](../modules/task-sdk-api-client.md).
- The task-side consumers are the [Task SDK task runner](../modules/task-sdk-task-runner.md) and the context accessors it builds.
- Its message shapes are the ones versioned for lang-SDK coordinators in [Task SDK schema versioning](../modules/task-sdk-schema-versioning.md).
- Adding a message type touches this file, `request_handlers.py`, the client and the supervisor together; the Execution API `AGENTS.md` lists the full set.

# Gotchas

- Synchronous comms calls from a thread that owns a paused event loop deadlock. `6a73afb1c1` added detection in `CommsDecoder`, and `0cf78267ad` made it raise `DeadlockImminentError` instead of blocking. Code that calls comms from async code must go through the async path.
- Short reads on the socket were mishandled before `f72e6c9bef`. Framing code must loop until a full frame is read.
- `DeadlockImminentError` derives from `BaseException`, so a bare `except Exception` in task code will not catch it. That is deliberate in the current code, but its intended handling is not documented in the module (see open questions).
- Trace context travels with requests that the supervisor forwards to the server (`f481758f04`).

# Citations

1. `0cf78267ad`: raises `DeadlockImminentError` for synchronous comms calls from a paused event-loop thread.
2. `6a73afb1c1`: adds deadlock detection in `CommsDecoder`.
3. `f72e6c9bef`: fixes short-read handling in the task SDK IPC framing.
4. `f481758f04`: propagates task OTel trace context through IPC.
