---
type: Module
title: Execution API security and token scopes
description: JWT validation, token-type scoping and task-instance identity checks that gate every authenticated Execution API route.
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/security.py
tags: [execution-api, security, jwt, token-scope, multi-team]
timestamp: 2026-08-29T04:02:59Z
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/security.py
  - airflow-core/src/airflow/api_fastapi/execution_api/deps.py
generated_by: catalogify/0.10.1
open_questions:
  - "Should a token of type workload ever be accepted on a route that reads Connections or Variables, or is that path reserved for execution tokens by design?"
  - "What is the intended expiry for a single-use callback token, and who enforces single use: the database or the token validator?"
---

# Responsibilities

Every authenticated Execution API request is checked here in three steps:
`JWTBearer` verifies the signature and claims once per request and caches the
result on the ASGI scope; `require_auth` checks the token type and the
`ti:self` rule (the JWT `sub` must match the `{task_instance_id}` path
parameter); `ExecutionAPIRoute` precomputes the set of allowed token types
per route from `token:*` Security scopes at registration time. Tokens without a
`scope` claim default to `execution`. A `workload` scope is accepted only on
routes that opt in.

Team scoping for multi-team deployments is resolved here too: `get_team_name_dep`
reads the team from the token's task instance or Dag, and the XCom, connection
and variable routes check it.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `JWTBearer` | `HTTPBearer` subclass that validates the token and caches it per request. |
| `require_auth` | Security dependency used on routers; enforces token type and `ti:self`. |
| `ExecutionAPIRoute` | Route class that precomputes `allowed_token_types` from `token:*` scopes. |
| `issue_execution_token` | Writes a refreshed execution token into a response. |
| `get_team_name_dep` | Dependency returning the team name for the current task instance, or `None` outside multi-team mode. |
| `get_team_name_for_ti` | Looks up the team for a task instance ID. |

# Dependencies

- Used by every router in [Execution API server](../services/execution-api.md).
- Reads the typed token claims from [Execution API data models](../data/execution-api-datamodels.md) (`token.py`).
- Team-scope checks are applied in [XComs](../apis/execution-api-xcoms.md), [connections and variables](../apis/execution-api-connections-and-variables.md) and [Dags and Dag runs](../apis/execution-api-dags-and-dag-runs.md).
- `deps.py` builds the container dependency that `security.py` uses for the token, so the two files change together.

# Gotchas

- Validation runs once per request because `JWTBearer` caches the result on the ASGI scope. The restructure in `df4cb30b11` was needed because FastAPI includes Security scopes in the dependency cache key for `HTTPBearer` subclasses, which made the old `JWTBearer` run twice on `ti:self` routes. Adding scopes to a `JWTBearer` subclass can bring that back.
- Outer router dependencies cannot relax a restriction set by an inner route, because Security scopes only accumulate. That is why the allowed token types are computed by `ExecutionAPIRoute` after `include_router` has merged the dependency lists.
- Bearer credentials must not reach logs. `d9e5446aaa` removed that logging. Keep new error paths free of raw token values.
- Team checks changed behaviour in multi-team mode: the XCom API was scoped to teams in `3b9d2a2221`, and `get_team_name_dep` previously created unused sessions when multi-team was off (`1e64f418ad`). Keep the single-tenant path free of database work.
- Claim validation uses a typed schema (`7e85e7bea5`). New claims need a field there, not an untyped dict lookup.
- Connection tests moved to worker-driven execution in `8e1667e004`, which added the `connection-tests` routes and the token-type handling for them.

# Citations

1. `df4cb30b11`: restructure of Execution API security around FastAPI Security scopes.
2. `d9e5446aaa`: avoid logging Execution API bearer credentials.
3. `3b9d2a2221`: scopes the XCom Execution API to teams in multi-team mode.
4. `7e85e7bea5`: validates task identity token claims with a typed schema.
5. `82215cf97c`: adds a single-use callback token for deadline callback context fetch.
6. `8e1667e004`: async connection testing via workers.
