---
type: Service
title: Execution API service
description: The private FastAPI/Cadwyn application that workers and the Dag processor use to read and update task instance state, XComs, connections and variables.
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/app.py
tags: [service, execution-api, api-server, fastapi, cadwyn]
timestamp: 2026-08-28T21:02:59-07:00
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/app.py
  - airflow-core/src/airflow/api_fastapi/execution_api/deps.py
generated_by: catalogify/0.11.0
open_questions:
  - "Do workers rely on the server answering within the client's configured request timeout (added in commit 051160409f), or is that timeout only a client-side bound? Nothing on the server side sets a deadline."
  - "Which team owns the Execution API on-call path, and what is the escalation when task heartbeats fail across the whole fleet?"
  - "Does the `/execution` mount prefix have to be stable for external workers, or may it change in a future major release?"
---

# Responsibilities

Serves the private task execution HTTP API under `/execution` on the API server. `create_task_execution_api_app` builds a Cadwyn-versioned FastAPI app, adds the correlation-ID and JWT-reissue middlewares, generates versioned routers from the [routes](../apis/execution-api-routes.md), and wraps unhandled exceptions as a JSON 500. The same app can be run in-process through `InProcessExecutionAPI`, which the Dag processor and triggerer use instead of a network hop.

Control flow is request/response: every endpoint is a stateless handler that opens a session, applies a state transition or read, and returns. The supervisor's heartbeat is the only periodic traffic.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `create_task_execution_api_app(lifespan=...)` | Builds the versioned app; the single factory the API server mounts. |
| `InProcessExecutionAPI` | Wraps the app for in-process callers (Dag processor, triggerer). |
| `get_extra_schemas()` | Adds schemas that are not reachable from route signatures to OpenAPI. |
| `CadwynWithOpenAPICustomization` | Cadwyn app subclass that customises OpenAPI output per version. |
| `JWTReissueMiddleware` | Issues a fresh token on responses when the presented one is close to expiry. |
| `CorrelationIdMiddleware` | Propagates the `correlation-id` header into logs and error bodies. |

# Dependencies

- Routes: [Execution API routes](../apis/execution-api-routes.md), which the app generates versioned routers from.
- Auth: [Execution API security](../modules/execution-api-security.md) (`JWTBearer`, `require_auth`, `ExecutionAPIRoute`).
- Versioning: [Execution API versioning](../modules/execution-api-versioning.md) (`versions.bundle`).
- Models: [Execution API datamodels](../data/execution-api-datamodels.md).
- Client side: the [Task SDK API client](../modules/sdk-api-client.md) and the [task SDK runtime](task-sdk-runtime.md) call this service over HTTP.
- External packages: FastAPI, Cadwyn, svcs (dependency container), structlog.

# Gotchas

- The JWT reissue middleware changes response headers on the way out. Any new middleware that rewrites responses must preserve that header. Commit `4418c72e9a` ("Issue refreshed Execution API JWT to tasks if their current token is expiring") introduced the reissue path in `app.py`, `deps.py` and `routes/__init__.py`.
- Unhandled exceptions return a generic `Internal server error` body and log the traceback. The handler exists because mounted sub-apps otherwise log nothing for unhandled errors (see the comment in `create_task_execution_api_app`).
- Some handlers are reachable from the Dag processor and triggerer through `InProcessExecutionAPI`, so a change that works over HTTP can still behave differently in-process. Verify both paths.

# Citations

- `4418c72e9a` — JWT reissue for expiring tokens (`app.py`, `deps.py`, `routes/__init__.py`).
- `82215cf97c` — single-use callback token; also touches `app.py`.
