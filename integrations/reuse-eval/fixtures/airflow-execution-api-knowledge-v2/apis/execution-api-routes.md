---
type: API Resource
title: Execution API routes
description: The routers mounted under /execution — task instances, XComs, Dag runs, connections, variables, assets and state stores — and the auth each one requires.
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/routes/__init__.py
tags: [api, execution-api, routes, rest]
timestamp: 2026-09-30T18:35:13+02:00
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/__init__.py
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/task_instances.py
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/xcoms.py
generated_by: catalogify/0.11.0
open_questions:
  - "Should the `/store/ti` and `/store/asset` state-store routes be treated as stable for external workers, given that the names changed in 74a52cf5d3 (task_store to task_state_store)?"
  - "Which routes must answer 410 for stale IDs (commit a327dd4a73 added this for the set-RTIF route)? No single rule is written down for when a stale ID returns 410 versus 404."
---

# Responsibilities

Exposes the state the task runtime reads and writes. All authenticated routers are grouped in `routes/__init__.py` under `Security(require_auth)`, with one prefix per resource. The health router is included outside the authenticated router, so `/health` and `/health/ping` do not pass through `require_auth`. Task instance routes handle the lifecycle: run (`PATCH .../run`), state transition (`PATCH .../state`), skip downstream, heartbeat (`PUT .../heartbeat`), rendered fields and map index, and validation of inlets and outlets. Most handlers are synchronous; the exceptions are noted under Gotchas.

# Interfaces

Prefixes mounted in `routes/__init__.py`, with the handler module:

| Prefix | Module | Notes |
| --- | --- | --- |
| `/task-instances` | `task_instances.py` | `ti_run`, `ti_update_state`, `ti_heartbeat`, `get_task_instance_count`, `get_task_instance_states`; `ti:self` on `/{task_instance_id}/...` |
| `/xcoms` | `xcoms.py` | GET, HEAD, POST, DELETE on `/{dag_id}/{run_id}/{task_id}/{key}`, plus `/slice` and `/item/{offset}` |
| `/dag-runs` | `dag_runs.py` | get, create, clear, state, previous, count |
| `/connections` | `connections.py` | GET `/{connection_id:path}` |
| `/variables` | `variables.py` | `/keys`, GET/PUT/DELETE `/{variable_key}` |
| `/connection-tests` | `connection_tests.py` | GET connection for a test, PATCH result |
| `/callbacks` | `callbacks.py` | PATCH `/{callback_id}/run` |
| `/hitlDetails` | `hitl.py` | GET, POST, PATCH `/{task_instance_id}` |
| `/store/ti`, `/store/asset` | `task_state_store.py`, `asset_state_store.py` | Key/value state stores |
| `/assets`, `/asset-events`, `/dags`, `/task-reschedules` | respective modules | Read paths used by sensors and asset-triggered runs |

# Dependencies

- Auth from [Execution API security](../modules/execution-api-security.md) — every route here except health passes through `require_auth`.
- Request and response models in [datamodels](../data/execution-api-datamodels.md).
- Version migrations from [versioning](../modules/execution-api-versioning.md).
- Business logic for task instance transitions is in `services/task_instances.py` (not a separate concept).
- Callers: the [API client](../modules/sdk-api-client.md) (`calls` relation below) and the [supervisor](../modules/sdk-supervisor.md) through it.

# Gotchas

- Commit `05519cd774` ("Keep task attempt UUIDs and try numbers aligned") changed `task_instances.py` so that a retry or clear allocates `(uuid, try_number)` together. A route that reads only one of the two will show a mismatched attempt.
- XComs are team-scoped in multi-team mode (`3b9d2a2221`, `xcoms.py`). A route change here must keep the read/write split.
- `ti_heartbeat` and `xcom_query` are `async def`, as are the connection and variable access checks. A blocking call added to any of them stalls the event loop for every request the server is handling.

# Citations

- `05519cd774` — attempt UUID and try number allocation.
- `3b9d2a2221` — XCom team scoping.
- `a327dd4a73` — 410 for stale ID on set-RTIF.
- `74a52cf5d3` — rename to task_state_store and asset_state_store.
