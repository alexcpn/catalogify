---
type: API Resource
title: Execution API HITL detail and callback routes
description: The /hitlDetails and /callbacks endpoints used for human-in-the-loop review of task instances and for running a single-use callback from a token.
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/routes/hitl.py
tags: [execution-api, hitl, human-in-the-loop, callbacks, api-route]
timestamp: 2026-09-30T16:35:13Z
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/hitl.py
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/callbacks.py
generated_by: catalogify/0.10.1
open_questions:
  - "Which token type is expected to call POST /callbacks/{callback_id}/run, and does a callback run count as a task heartbeat for stale-detection purposes?"
---

# Responsibilities

`hitlDetails` stores a human-in-the-loop request on a task instance, lets a
reviewer or the worker read it, and records the response. `callbacks` runs one
callback by ID, used for deadline callbacks that fetch their context at run
time.

# Interfaces

| Symbol | Route | Purpose |
| --- | --- | --- |
| `upsert_hitl_detail` | `POST /hitlDetails/{task_instance_id}` | Create or replace the HITL request for a task instance. |
| `update_hitl_detail` | `PATCH /hitlDetails/{task_instance_id}` | Record a response. |
| `get_hitl_detail` | `GET /hitlDetails/{task_instance_id}` | Read the request and its response. |
| `run_callback` | `PATCH /callbacks/{callback_id}/run` | Run a callback identified by ID; loads the row with `with_for_update`. |
| `_check_hitl_detail_exists` | (helper) | Raises when the HITL detail is missing for the task instance. |

# Dependencies

- Task-instance identity checks come from [Execution API security](../modules/execution-api-security.md) (`JWTBearerTIPathDep`).
- Models are `CreateHITLDetailPayload`, `UpdateHITLDetailPayload` and `HITLDetailResponse` in [Execution API data models](../data/execution-api-datamodels.md) (`hitl.py`).
- The worker sends and reads HITL requests through `HITLOperations` in the [Task SDK API client](../modules/task-sdk-api-client.md), and the task runner waits in the awaiting-input state described in [Task SDK task runner](../modules/task-sdk-task-runner.md).

# Gotchas

- A HITL detail belongs to one attempt. Clearing a task instance while a review is open was mishandled; `5619bf196e` added the clearing case to both get and update.
- Task-instance validation was added to HITL routes in `0f64abcee3`, and an import of the path-validation dependency was broken and fixed in `3a40a9420f`. Keep the dependency imported from the same module as the other routes.
- Callback tokens are single-use (`82215cf97c`), so a retried callback run needs a fresh token rather than replaying the first.

# Citations

1. `5619bf196e`: handles task instance clearing cases when getting and updating a HITL detail.
2. `0f64abcee3`: adds task instance validation for HITL.
3. `3a40a9420f`: fixes the `JWTBearerTIPathDep` import error in HITL routes.
4. `82215cf97c`: adds a single-use callback token for deadline callback context fetch.
