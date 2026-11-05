---
type: Module
title: Task SDK secrets backend that calls the Execution API
description: The secrets backend a worker uses to fetch connections and variables through the Execution API, and the rule that an authorization denial must not fall through to another backend.
resource: https://github.com/apache/airflow/blob/main/task-sdk/src/airflow/sdk/execution_time/secrets/execution_api.py
tags: [module, task-sdk, secrets, security, connections]
timestamp: 2026-08-03T14:34:10+05:30
source_files:
  - task-sdk/src/airflow/sdk/execution_time/secrets/execution_api.py
generated_by: catalogify/0.11.0
open_questions:
  - "Is the rule 'authz denial is not a fallthrough' written down as a guarantee to operators who configure a secrets backend chain, or only in the commit? If it is a guarantee, should it become a Guardrail?"
  - "Which deployments rely on falling through from the Execution API backend to environment variables for tasks that are legitimately not authorized for a connection? Commit 2b8c80568b changed that behaviour."
  - "Who owns the team-boundary check for connections and variables (commits a4f3417bb0 and d32091cd4f) on the server side, and is there a test that runs both sides together?"
---

# Responsibilities

`ExecutionAPISecretsBackend` implements the secrets backend interface on the worker. `get_connection` and `get_variable` call the Execution API through the [API client](sdk-api-client.md) and return the result, or `None` only for a genuine not-found. Authorization denials are not "not found" and must not be reported as `None`, because the secrets backend chain would then try the next backend.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `ExecutionAPISecretsBackend` | The backend class; configured through the `[secrets]` backend chain. |
| `get_connection(conn_id)` | Returns a connection, `None` on not-found, raises on denial. |
| `get_variable(key)` | Returns a variable, `None` on not-found, raises on denial. |

# Dependencies

- Calls the [API client](sdk-api-client.md) (`ConnectionOperations`, `VariableOperations`).
- Server-side checks: `has_connection_access` and `has_variable_access` in [routes](../apis/execution-api-routes.md) and the team checks in [security](execution-api-security.md).
- Used from the [task runner](sdk-task-runner.md) through `context.py`.

# Gotchas

- Commit `2b8c80568b` ("Refuse secrets-backend fallback on Execution-API authz deny") fixed the backend returning `None` for every error response, including 401 and 403. The secrets chain then fell through to the environment-variables backend, which performs no authorization. The fix raises on denial.
- Commit `ae0a330f01` ("Fix Connection or Variable access in Server context") and `da32b682d1` ("Fix connection access in triggerer for deferrable operators") show that this backend is also used in server and triggerer contexts; behaviour changes apply there too.
- Commit `32afc282ea` moved `BaseSecretsBackend` into the shared library, so the interface is imported from a shared distribution.

# Citations

- `2b8c80568b` — refuse fallback on authz denial.
- `ae0a330f01` — server-context access.
- `da32b682d1` — triggerer connection access.
- `32afc282ea` — shared base secrets backend.
