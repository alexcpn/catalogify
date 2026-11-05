---
type: Module
title: Task SDK Execution API client
description: The httpx-based client in the Task SDK that every worker-side call to the Execution API goes through, plus the generated Pydantic models it validates against.
resource: https://github.com/apache/airflow/blob/main/task-sdk/src/airflow/sdk/api/client.py
tags: [task-sdk, execution-api, client, httpx, generated-models]
timestamp: 2026-09-27T17:47:48Z
source_files:
  - task-sdk/src/airflow/sdk/api/client.py
  - task-sdk/src/airflow/sdk/api/datamodels/_generated.py
generated_by: catalogify/0.10.1
open_questions:
  - "Is the heartbeat retry policy configured separately from [workers] execution_api_retries by design, and which setting should operators tune for flaky networks?"
---

# Responsibilities

`Client` is an `httpx.Client` subclass that builds every Execution API request
the worker makes. It holds the base URL and the execution token, refreshes the
token when the server reissues it, propagates trace context, and exposes one
`*Operations` object per resource (`TaskInstanceOperations`, `XComOperations`,
`VariableOperations`, and so on). Runtime code calls those operations, not raw
HTTP. `_generated.py` contains the models those operations validate against; it
is produced from the Execution API schema, not written by hand.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `Client` | The HTTP client; owns the base URL, token refresh and retries. |
| `TaskInstanceOperations` | Start, finish, retry, defer, reschedule, heartbeat, RTIF, and previous-TI lookups. |
| `XComOperations` | Head, get, set, delete, and mapped-sequence item and slice access. |
| `VariableOperations`, `ConnectionOperations` | Variable get, set, delete, keys; connection get. |
| `TaskStateStoreOperations`, `AssetStateStoreOperations` | State-store get, set, delete and clear. |
| `AssetOperations`, `AssetEventOperations` | Asset lookup by name or URI, and asset event listing. |
| `DagRunOperations`, `DagsOperations` | Trigger, clear, state, count and previous-run lookups; Dag fetch. |
| `HITLOperations` | Add and update HITL responses, read detail. |
| `ConnectionTestOperations`, `CallbackOperations` | Worker side of connection tests; callback run. |

# Dependencies

- Calls the routes in [task instances](../apis/execution-api-task-instances.md), [XComs](../apis/execution-api-xcoms.md), [connections and variables](../apis/execution-api-connections-and-variables.md), [state stores](../apis/execution-api-state-stores.md), [assets](../apis/execution-api-assets.md), [Dags and Dag runs](../apis/execution-api-dags-and-dag-runs.md), and [HITL and callbacks](../apis/execution-api-hitl-and-callbacks.md).
- Its models mirror [Execution API data models](../data/execution-api-datamodels.md). The generator command is in the Execution API `AGENTS.md`; edit the server model first, then regenerate.
- Used by the supervisor, which forwards messages from the task process in [Task SDK comms](../modules/task-sdk-comms.md) to these operations in [Task SDK supervisor](../modules/task-sdk-supervisor.md).
- Co-changes with the Execution API routes and with `task-sdk/tests` (lift around 43 for the directory in `catalogify cochange`). The coupling is by design: a route change needs the client change in the same commit.

# Gotchas

- Heartbeat failures are not retried by the general `[workers] execution_api_retries` policy (`cb9765fa4e`). A heartbeat that keeps failing must reach the supervisor's own handling, not a silent retry loop.
- The client carries the trace context from the task into HTTP headers (`f481758f04`), so spans from the worker and the server line up.
- Token refresh is handled in the client (`4418c72e9a`); a token refreshed in one response must be used for the next request, not cached elsewhere.
- Task-instance fields added in `05519cd774` landed in `client.py` and `_generated.py` together with the server change. A server-only field does not reach workers until the models are regenerated.

# Citations

1. `f481758f04`: propagates task OTel trace context through IPC and into Execution API requests.
2. `cb9765fa4e`: task heartbeats are no longer retried under `[workers] execution_api_retries`.
3. `4418c72e9a`: issues a refreshed Execution API JWT when the current one is expiring.
4. `05519cd774`: keeps task attempt UUIDs and try numbers aligned across client and server models.
