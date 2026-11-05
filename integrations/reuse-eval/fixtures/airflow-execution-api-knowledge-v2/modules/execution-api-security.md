---
type: Module
title: Execution API security (JWT and token scopes)
description: JWT validation, token-type scopes (execution, workload) and the ti:self check that binds a request to one task instance.
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/security.py
tags: [module, execution-api, security, jwt, auth]
timestamp: 2026-08-28T21:02:59-07:00
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/security.py
generated_by: catalogify/0.11.0
open_questions:
  - "The module docstring lists two token types (execution, workload), but TokenScope in datamodels/token.py also includes callback. Is callback documented in the JWT authentication docs, and which routes accept it?"
  - "Is a 401 on a `ti:self` mismatch treated as a security event that must be audited, or only logged? Commit d9e5446aaa removed bearer details from logs."
  - "Who owns rotation of the JWT signing key, and is there a documented upper bound on how long a reissued execution token can live?"
---

# Responsibilities

Validates the bearer JWT once per request and enforces three things: the token type allowed for the route, the `ti:self` binding between the token's `sub` and the `{task_instance_id}` path parameter, and the team scope in multi-team mode. Routers declare access with `Security(require_auth, scopes=[...])`. `ExecutionAPIRoute` precomputes the allowed token types at registration time, because FastAPI scopes accumulate only additively and an inner `token:workload` scope could not relax an outer default.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `require_auth` | FastAPI Security dependency; enforces token type and `ti:self`. |
| `JWTBearer` | `HTTPBearer` subclass that validates the token once and caches it on the ASGI scope. |
| `ExecutionAPIRoute` | Route class that precomputes `allowed_token_types` from `token:*` scopes. |
| `issue_execution_token` | Writes a refreshed token onto the response. |
| `get_team_name_dep`, `get_team_name_for_ti` | Resolves the team for a task instance in multi-team mode. |
| `VALID_TOKEN_TYPES` | Frozen set of accepted token scope names. |

# Dependencies

- Used by every authenticated router in [routes](../apis/execution-api-routes.md) through `routes/__init__.py`.
- Token claim models: [datamodels](../data/execution-api-datamodels.md) (`TIClaims`, `TIToken`, `TokenScope`).
- Token signing and validation: `airflow.api_fastapi.auth.tokens` (`JWTGenerator`, `JWTValidator`), outside this bundle's scope.
- Reissue is driven by the middleware in [service app](../services/execution-api.md).
- Worker side: the client sends the bearer via `BearerAuth` in the [API client](sdk-api-client.md).

# Gotchas

- A `token:workload` token is long-lived and must be accepted only on routes that opt in. Commit `82215cf97c` ("Add single-use callback token for deadline callback context fetch") was written because an earlier opt-in let a long-lived token read arbitrary DagRun, connection, variable and XCom data.
- Team checks apply to XComs in multi-team mode: reads are allowed for the task's own team or global Dags, writes and deletes only for its own team. Commit `3b9d2a2221` ("Scope XCom Execution API to teams in multi-team mode") added this in `routes/xcoms.py` and `security.py`.
- Bearer credentials must not reach logs. Commit `d9e5446aaa` ("Avoid logging Execution API bearer credentials") removed them; keep new log lines free of token contents and validation details.
- Token scope names are a closed set. Add a new scope to `TokenScope` and to every route that accepts it, or the route will reject the token with the default execution-only policy.

# Citations

- `82215cf97c` — single-use callback token; scope tightening for `token:workload`.
- `3b9d2a2221` — XCom team scoping.
- `d9e5446aaa` — bearer credential logging.
- `df4cb30b11` — restructured security scopes and `ExecutionAPIRoute` rationale.
