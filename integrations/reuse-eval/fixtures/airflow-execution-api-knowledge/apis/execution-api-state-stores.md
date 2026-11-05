---
type: API Resource
title: Execution API task and asset state-store routes
description: The /store/ti and /store/asset endpoints that let a task or an asset-scoped component keep small keyed state between runs, with optional expiry.
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/routes/task_state_store.py
tags: [execution-api, state-store, task-state, asset-state, api-route]
timestamp: 2026-08-03T05:44:19Z
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/task_state_store.py
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/asset_state_store.py
generated_by: catalogify/0.10.1
open_questions:
  - "Is the expiry on a state-store value enforced at read time, at a sweep, or both, and what is the retention for expired rows?"
  - "Can a value written by one task attempt be read by a later attempt of the same task instance, and is that intended for retries?"
---

# Responsibilities

Gives tasks (`/store/ti/{task_instance_id}/{key}`) and assets
(`/store/asset/by-name/value`, `/store/asset/by-uri/value`) a small
key-value store that outlives a single process. Task-scoped routes are keyed by
the task instance and key; asset-scoped routes resolve the asset by name or URI
first. Clear routes remove every key in a scope.

# Interfaces

| Symbol | Route | Purpose |
| --- | --- | --- |
| `get_task_state_store` | `GET /store/ti/{task_instance_id}/{key}` | Read a task-scoped value. |
| `set_task_state_store` | `PUT /store/ti/{task_instance_id}/{key}` | Write a task-scoped value. |
| `delete_task_state_store` | `DELETE /store/ti/{task_instance_id}/{key}` | Delete one key. |
| `clear_task_state_store` | `DELETE /store/ti/{task_instance_id}` | Clear all keys for the task instance. |
| `get_asset_state_store_by_name` | `GET /store/asset/by-name/value` | Read an asset-scoped value by asset name. |
| `set_asset_state_store_by_name` | `PUT /store/asset/by-name/value` | Write it. |
| `delete_asset_state_store_by_name` | `DELETE /store/asset/by-name/value` | Delete one key. |
| `clear_asset_state_store_by_name` | `DELETE /store/asset/by-name/clear` | Clear the asset scope. |
| `get_asset_state_store_by_uri`, `set_asset_state_store_by_uri`, `delete_asset_state_store_by_uri`, `clear_asset_state_store_by_uri` | `/store/asset/by-uri/...` | The same operations addressed by URI. |

# Dependencies

- Task-scoped access uses the `ti:self` rule from [Execution API security](../modules/execution-api-security.md).
- Request and response bodies are `TaskStateStorePutBody`, `TaskStateStoreResponse`, `AssetStateStorePutBody` and `AssetStateStoreResponse` in [Execution API data models](../data/execution-api-datamodels.md).
- The Task SDK side is `TaskStateStoreOperations` and `AssetStateStoreOperations` in the [Task SDK API client](../modules/task-sdk-api-client.md), accessed from task code through `TaskStateStoreAccessor` and `AssetStateStoreAccessor` in [Task SDK task runner](../modules/task-sdk-task-runner.md).

# Gotchas

- Keys can contain slashes. The task-scoped routes use a `{key:path}` converter, and `4899e90418` fixed the case where the API rejected such keys. Keep that converter when adding routes.
- The asset-scoped routes are reachable from the triggerer as well as from tasks (`feea09d610`), so their token checks must accept the triggerer's token type.

# Citations

1. `4899e90418`: fixes the task state store Execution API rejecting keys that contain slashes.
2. `feea09d610`: allows the asset state store accessors to run on the triggerer.
