---
type: API Resource
title: Execution API connection, connection-test and variable routes
description: The /connections, /connection-tests and /variables endpoints through which workers read secrets-backed connections and variables and run connection tests without the API server holding their secrets.
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/routes/connections.py
tags: [execution-api, connections, variables, secrets, connection-test, multi-team, api-route]
timestamp: 2026-09-24T22:52:13Z
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/connections.py
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/connection_tests.py
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/variables.py
generated_by: catalogify/0.10.1
open_questions:
  - "Does the connection-test flow ever store the tested secret on the API server side beyond the lifetime of one request, and where is the expiry of a connection-test record enforced?"
  - "Who owns the decision that connection tests run only on workers, and is there a documented fallback when no worker can pick the test up?"
---

# Responsibilities

Serves connections and variables to tasks and to the Task SDK. Connection
reads go through `get_connection` after `has_connection_access`; variable
reads, writes, deletes and key listings go through `get_variable`,
`put_variable`, `delete_variable` and `get_variable_keys` after
`has_variable_access`. Connection tests are a two-step exchange: the API server
records a test, a worker executes it, and the worker reports the result back
through `get_connection_test_connection` and `patch_connection_test`.

# Interfaces

| Symbol | Route | Purpose |
| --- | --- | --- |
| `get_connection` | `GET /connections/{connection_id}` | Read a connection for a task. |
| `get_connection_test_connection` | `GET /connection-tests/{connection_test_id}/connection` | Worker fetches the connection to test. |
| `patch_connection_test` | `PATCH /connection-tests/{connection_test_id}` | Worker reports the test state and result. |
| `get_variable` | `GET /variables/{variable_key}` | Read a variable. |
| `put_variable` | `PUT /variables/{variable_key}` | Write a variable. |
| `delete_variable` | `DELETE /variables/{variable_key}` | Delete a variable. |
| `get_variable_keys` | `GET /variables/keys` | List variable keys, optionally by prefix. |
| `has_connection_access`, `has_variable_access` | (dependencies) | Team and token checks. |

# Dependencies

- Team checks come from [Execution API security](../modules/execution-api-security.md).
- Connection-test request and response bodies are in [Execution API data models](../data/execution-api-datamodels.md) (`connection.py`, `connection_test.py`, `variable.py`).
- The worker side that answers connection tests is [Task SDK supervisor](../modules/task-sdk-supervisor.md) (`connection_test_supervisor.py`); the client calls are `ConnectionOperations`, `VariableOperations` and `ConnectionTestOperations` in the [Task SDK API client](../modules/task-sdk-api-client.md).
- Connection and variable values reach task code through the Task SDK context accessors described in [Task SDK task runner](../modules/task-sdk-task-runner.md).

# Gotchas

- Connection tests were moved off the API server to workers in `8e1667e004` so the server does not run user-supplied connection code. Anything that adds a synchronous test call on this route reintroduces that exposure.
- Team boundaries for connections and variables were added separately in `a4f3417bb0` and `d32091cd4f`. A new read path on either resource must go through the same team check.
- The deadline-callback change `609656f7d3` touched `connections.py` and `variables.py` and was reverted. Any future use of these routes by non-task callers should check the callback token scope first.

# Citations

1. `8e1667e004`: async connection testing via workers for security isolation.
2. `a4f3417bb0`: checks team boundaries in connections.
3. `d32091cd4f`: checks team boundaries in variables.
4. `e94cc4dd96`: adds `Variable.keys()` support and the keys route.
