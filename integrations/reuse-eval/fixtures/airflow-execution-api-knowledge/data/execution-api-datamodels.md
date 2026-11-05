---
type: Data Model
title: Execution API request and response models
description: The Pydantic models that define the task-instance state payloads, the task-instance run context and the identity-token claims exchanged over the Execution API.
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/datamodels/taskinstance.py
tags: [execution-api, pydantic, datamodels, task-instance, token-claims]
timestamp: 2026-09-26T21:16:29Z
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/datamodels/taskinstance.py
  - airflow-core/src/airflow/api_fastapi/execution_api/datamodels/token.py
generated_by: catalogify/0.10.1
open_questions:
  - "Are the StrictBaseModel payloads (state updates) meant to reject unknown fields from newer clients, or should they ignore them as forward-compatible extras?"
---

# Schema

The models split into two groups. Request and state payloads
(`StrictBaseModel`) reject unknown fields. Response models (`BaseModel`) are
the shapes the server returns.

| Model | Role |
| --- | --- |
| `TIEnterRunningPayload` | Body for `ti_run`: the PID and start time reported by the supervisor. |
| `TISuccessStatePayload`, `TITerminalStatePayload`, `TIDeferredStatePayload`, `TIRescheduleStatePayload`, `TIRetryStatePayload`, `TIAwaitingInputStatePayload`, `TISkippedDownstreamTasksStatePayload` | Terminal, deferred, rescheduled, retrying, awaiting-input and skipped state updates. |
| `TIHeartbeatInfo` | Body for `ti_heartbeat`. |
| `TIRunContext` | Response from `ti_run`: everything the task runner needs to start. |
| `TaskInstance`, `DagRun`, `PrevSuccessfulDagRunResponse`, `PreviousTIResponse`, `TaskStatesResponse`, `TaskBreadcrumbsResponse`, `InactiveAssetsResponse` | Read shapes for the scheduling lookups. |
| `TIClaims`, `TIToken` (`token.py`) | Typed claims of the identity token; validated by the security layer. |

# Dependencies

- Used by [task instance routes](../apis/execution-api-task-instances.md), the [Dag run routes](../apis/execution-api-dags-and-dag-runs.md), and [security](../modules/execution-api-security.md).
- Versioned by [Execution API versioning](../modules/execution-api-versioning.md); the head shape and the older shapes are generated from these classes.
- Mirrored as generated models in the [Task SDK API client](../modules/task-sdk-api-client.md) (`_generated.py`). Edit this file first and regenerate.

# Gotchas

- Task-instance fields that worker code depends on were versioned together in `872427c253` (`taskinstance.py`, the version bundle, and the generated Task SDK models). Adding a field means touching all four.
- Token claims moved from an untyped dict to a typed schema in `7e85e7bea5` (`token.py`), and `82215cf97c` added a single-use callback token claim to the same file.
- `TIRunContext` changes are versioned; `05519cd774` aligned attempt UUIDs and try numbers across this model and the route that returns it.

# Citations

1. `872427c253`: versions the worker-bound TaskInstance fields in the Execution API schema.
2. `05519cd774`: keeps task attempt UUIDs and try numbers aligned.
3. `7e85e7bea5`: validates task identity token claims with a typed schema.
4. `82215cf97c`: adds a single-use callback token.
