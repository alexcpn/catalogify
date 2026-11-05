---
type: Service
title: Execution API server
description: The FastAPI/Cadwyn HTTP service inside the API server through which workers, the Dag processor and the triggerer read and write runtime state; it never gives them direct database access.
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/app.py
tags: [execution-api, fastapi, cadwyn, api-server, task-sdk]
timestamp: 2026-08-29T04:02:59Z
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/app.py
  - airflow-core/src/airflow/api_fastapi/execution_api/security.py
  - airflow-core/src/airflow/api_fastapi/execution_api/deps.py
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/__init__.py
generated_by: catalogify/0.10.1
open_questions:
  - "Is the Execution API expected to serve the Dag processor and triggerer only through InProcessExecutionAPI, or is a networked client path for them also supported by design?"
  - "Which team owns the Execution API response-time budget, and what is the escalation path when task heartbeats or state updates slow down under load?"
---

# Responsibilities

The Execution API is the only channel through which a running task, the Dag
processor, and the triggerer read or write metadata. It is mounted under the
API server and assembled by `create_task_execution_api_app`. The app wraps a
set of authenticated routers (`/task-instances`, `/xcoms`, `/connections`, and
so on) in a Cadwyn `VersionedAPIRouter`, so older and newer clients can talk to
the same server. Requests pass through correlation-ID and JWT-reissue
middleware, and task-identity tokens are checked on every authenticated route
(see [Execution API security](../modules/execution-api-security.md)).

The same app can be run in-process. `InProcessExecutionAPI` wraps it for
`dag.test`, the Dag processor and the triggerer, which keep the request/response
shape but skip the network.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `create_task_execution_api_app` | Builds the FastAPI app: lifespan, middlewares, exception handlers, and the versioned router. |
| `InProcessExecutionAPI` | Runs the same app inside the current process for Dag test and internal components. |
| `CadwynWithOpenAPICustomization` | Cadwyn subclass that adds the OpenAPI customization used for versioned schemas. |
| `CorrelationIdMiddleware` | Assigns and propagates a correlation ID per request. |
| `JWTReissueMiddleware` | Issues a refreshed execution token when the presented one is close to expiry. |
| `get_extra_schemas` | Supplies extra JSON schemas to the OpenAPI document. |

Route prefixes are registered in `routes/__init__.py`: `/task-instances`,
`/xcoms`, `/dag-runs`, `/dags`, `/assets`, `/asset-events`, `/connections`,
`/connection-tests`, `/callbacks`, `/variables`, `/task-reschedules`,
`/hitlDetails`, `/store/ti`, `/store/asset`, plus the unauthenticated
`/health` router. Endpoint details live in the `apis/` concepts.

# Dependencies

- Uses the versioned contract in [Execution API versioning](../modules/execution-api-versioning.md).
- Authenticates every authenticated route through [Execution API security](../modules/execution-api-security.md) (`JWTBearer`, `require_auth`, `ExecutionAPIRoute`).
- Serves the route groups in [task instances](../apis/execution-api-task-instances.md), [XComs](../apis/execution-api-xcoms.md), [Dags and Dag runs](../apis/execution-api-dags-and-dag-runs.md), [assets](../apis/execution-api-assets.md), [connections and variables](../apis/execution-api-connections-and-variables.md), [state stores](../apis/execution-api-state-stores.md), and [HITL and callbacks](../apis/execution-api-hitl-and-callbacks.md).
- Request and response bodies are defined in [Execution API data models](../data/execution-api-datamodels.md).
- Clients are the [Task SDK API client](../modules/task-sdk-api-client.md) and the in-process supervisor comms in [Task SDK supervisor](../modules/task-sdk-supervisor.md).
- Co-changes with `ts-sdk/src` in about 19% of its commits (lift around 10 in the repo-wide `catalogify cochange` output for this directory). No import explains this, so it is recorded here as an observed coupling. See the open question on the Dag and triggerer path.
- External: FastAPI, Cadwyn (`VersionedAPIRouter`), and `svcs` for the request-scoped container.

# Gotchas

- Reverting a server-side endpoint is not a clean undo. Deadline-callback context fetch through this API was merged (`8095abb571`) and reverted the same week (`609656f7d3`, which touched `app.py`). It came back later with a single-use callback token (`82215cf97c`). Treat new endpoints that serve non-task callers as needing their own token scope from the start.
- `InProcessExecutionAPI` owns a background event-loop thread. A thread leak in it was fixed in `a52be75711`, which moved thread management into the class. Changes to its lifecycle need to preserve that cleanup.
- Missing `api_auth.jwt_secret` is tolerated only for the in-process case (`e886dfd05e`). Do not assume the network server can start without it.
- SQLAlchemy errors now go through the global exception handler (`7c03dabdcd`) rather than per-route handling. Route code should not add its own wrapping for these.
- Trace headers from the client are propagated onto server-side spans (`88ec07321f`); new middleware that changes request scope needs to keep them intact.

# Citations

1. `8095abb571`, `609656f7d3`, `82215cf97c`: deadline callback context fetch through the Execution API, reverted and re-landed with a single-use callback token.
2. `a52be75711`: fix for the thread leak in `InProcessExecutionAPI`.
3. `e886dfd05e`: allows a missing `jwt_secret` for the in-process API.
4. `7c03dabdcd`: routes SQLAlchemy errors through the global exception handler.
5. `88ec07321f`: propagates OpenTelemetry trace headers into server-side spans.
