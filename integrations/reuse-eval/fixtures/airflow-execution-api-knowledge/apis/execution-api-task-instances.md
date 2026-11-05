---
type: API Resource
title: Execution API task-instance routes
description: The /task-instances endpoints that move a running task through its lifecycle (start, heartbeat, state update, reschedule, rendered fields) and expose read-only scheduling lookups.
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/routes/task_instances.py
tags: [execution-api, task-instances, heartbeat, lifecycle, api-route]
timestamp: 2026-09-30T16:35:13Z
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/task_instances.py
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/task_reschedules.py
  - airflow-core/src/airflow/api_fastapi/execution_api/services/task_instances.py
generated_by: catalogify/0.10.1
open_questions:
  - "After a heartbeat returns 410 Gone for a cleared task instance, is the intended supervisor action to terminate the task process immediately or only to stop heartbeating?"
  - "Is the per-task heartbeat rate a hard contract that the scheduler's stale-heartbeat detection depends on, or only a default?"
---

# Responsibilities

This is the largest route file in the Execution API. Each task attempt calls
`ti_run` (`PATCH /{task_instance_id}/run`) to enter `running`, then
`ti_heartbeat` (`PUT /{task_instance_id}/heartbeat`) while it runs, and
finally `ti_update_state` (`PATCH /{task_instance_id}/state`) with the terminal
or deferred state. Side routes update rendered template fields
(`ti_put_rtif`), rendered map indices (`ti_patch_rendered_map_index`), skip
downstream tasks (`ti_skip_downstream`), and validate inlets and outlets. Read
routes under `/task-instances` answer scheduling questions for the Task SDK:
counts, previous task instances, states, breadcrumbs and the previous
successful Dag run.

# Interfaces

| Symbol | Route | Purpose |
| --- | --- | --- |
| `ti_run` | `PATCH /{task_instance_id}/run` | Transition to `running`; returns the `TIRunContext`. |
| `ti_heartbeat` | `PUT /{task_instance_id}/heartbeat` | Liveness signal; returns 409 on state conflict and 410 when the attempt was cleared. |
| `ti_update_state` | `PATCH /{task_instance_id}/state` | Report success, failure, retry, deferral, reschedule or skip. |
| `ti_skip_downstream` | `PATCH /{task_instance_id}/skip-downstream` | Mark downstream tasks as skipped. |
| `ti_put_rtif` | `PUT /{task_instance_id}/rtif` | Store rendered template fields. |
| `ti_patch_rendered_map_index` | `PATCH /{task_instance_id}/rendered-map-index` | Store the rendered map index label. |
| `get_previous_successful_dagrun` | `GET /{task_instance_id}/previous-successful-dagrun` | Previous successful run for task context. |
| `get_task_instance_count` | `GET /count` | Count matching task instances. |
| `get_previous_task_instance` | `GET /previous/{dag_id}/{task_id}` | Previous task instance for a task. |
| `get_task_instance_states` | `GET /states` | States of task instances in a run. |
| `get_task_instance_breadcrumbs` | `GET /breadcrumbs` | Task-group breadcrumbs for a run. |
| `validate_inlets_and_outlets` | `GET /{task_instance_id}/validate-inlets-and-outlets` | Flags inactive assets referenced by inlets or outlets. |
| `get_start_date` | `GET /task-reschedules/{task_instance_id}/start_date` | First reschedule start date for sensor reschedule mode. |
| `client_supports_arg_bindings`, `get_arg_bindings` | (service) | Argument-binding payload, gated by the API version. |

# Dependencies

- Reads and writes task instances in the metadata DB on behalf of workers; the worker never touches the DB directly.
- State payloads are typed in [Execution API data models](../data/execution-api-datamodels.md) (`TIEnterRunningPayload`, `TISuccessStatePayload`, `TIHeartbeatInfo`, and others).
- Version-dependent fields are declared in [Execution API versioning](../modules/execution-api-versioning.md).
- Client calls come from the [Task SDK API client](../modules/task-sdk-api-client.md) (`TaskInstanceOperations`), and the supervisor reacts to 409 and 410 responses in [Task SDK supervisor](../modules/task-sdk-supervisor.md).
- Callback and retry state goes through [HITL and callbacks](../apis/execution-api-hitl-and-callbacks.md) and the [state stores](../apis/execution-api-state-stores.md) where relevant.

# Gotchas

- A heartbeat that finds the attempt in the history table returns 410 Gone rather than a generic 404. The cleared attempt keeps its old identity, and `ce1270b96f` added the 410 path so the supervisor can tell "cleared" from "unknown".
- Two-token execution: a task waiting in an executor queue can outlive its first token. `2b6e8181e3` added a mechanism so the run call does not fail on an expired token. Changes to `ti_run` need to preserve that path.
- Attempt identity: UUIDs and try numbers must stay aligned across the `TIRunContext` response and later state updates (`05519cd774`).
- Retry reasons are persisted for failures too, not only retries (`f14bed9b85`), so the terminal-state payload carries that field.
- SQLAlchemy errors from these routes are handled by the global exception handler (`7c03dabdcd`); do not wrap them per route.

# Citations

1. `ce1270b96f`: returns 410 Gone for heartbeat when a cleared task instance exists in the history table.
2. `2b6e8181e3`: two-token mechanism for task execution while tasks wait in executor queues.
3. `05519cd774`: keeps task attempt UUIDs and try numbers aligned.
4. `f14bed9b85`: persists `retry_reason` on terminal failure as well as on retry.
5. `7c03dabdcd`: routes SQLAlchemy errors through the global exception handler.
