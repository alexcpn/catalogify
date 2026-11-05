---
type: API Resource
title: Execution API XCom routes
description: The /xcoms endpoints a task uses to push, pull, count, slice and delete XCom values, including the mapped-index and slice forms used by dynamic task mapping.
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/routes/xcoms.py
tags: [execution-api, xcom, task-mapping, multi-team, api-route]
timestamp: 2026-09-30T16:35:13Z
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/xcoms.py
generated_by: catalogify/0.10.1
open_questions:
  - "Is the XCom slice endpoint's upper bound exclusive in every caller, or only in the Task SDK client that builds it?"
---

# Responsibilities

Stores and retrieves task outputs keyed by `dag_id`, `run_id`, `task_id`, and
`key`. Mapped tasks have an extra index or slice path. Access is checked by
`has_xcom_access`, which applies team scoping in multi-team mode before any
read or write.

# Interfaces

| Symbol | Route | Purpose |
| --- | --- | --- |
| `head_xcom` | `HEAD /{dag_id}/{run_id}/{task_id}/{key}` | Existence and count check without the value. |
| `get_xcom` | `GET /{dag_id}/{run_id}/{task_id}/{key}` | Read one XCom value. |
| `set_xcom` | `POST /{dag_id}/{run_id}/{task_id}/{key}` | Write one XCom value. |
| `delete_xcom` | `DELETE /{dag_id}/{run_id}/{task_id}/{key}` | Remove one XCom value. |
| `get_mapped_xcom_by_index` | `GET .../{key}/item/{offset}` | Read one element of a mapped XCom sequence. |
| `get_mapped_xcom_by_slice` | `GET .../{key}/slice` | Read a range of a mapped XCom sequence. |
| `has_xcom_access` | (dependency) | Team and token check for all XCom routes. |

# Dependencies

- Authorisation comes from [Execution API security](../modules/execution-api-security.md) (`get_team_name_dep`).
- Request and response models are in [Execution API data models](../data/execution-api-datamodels.md) (`datamodels/xcom.py`).
- The Task SDK reads and writes XComs through `XComOperations` in the [Task SDK API client](../modules/task-sdk-api-client.md), and the supervisor serves in-task XCom requests from [Task SDK comms](../modules/task-sdk-comms.md).

# Gotchas

- XCom keys can contain slashes. Keys are path parameters with a `{key:path}` converter; a key with `/` was mishandled before `6e3e51201e` fixed it. Do not change the converter without rechecking that case.
- Pushing `None` is a real value, not a delete (`b4cf3afe2a`).
- In multi-team mode, XCom reads are scoped to the team of the requesting task (`3b9d2a2221`). A cross-team read is not an error path; it is denied by the scope check.
- Slice bounds were fixed for crossed ranges in `4dd620f48d`. The route now handles `low > high` instead of returning a 500.

# Citations

1. `3b9d2a2221`: scopes the XCom Execution API to teams in multi-team mode.
2. `6e3e51201e`: fixes XCom key handling for keys containing slashes.
3. `b4cf3afe2a`: fixes pushing `None` as an XCom value.
4. `4dd620f48d`: fixes the XCom slice endpoint for crossed bounds.
