---
type: API Resource
title: Execution API asset and asset-event routes
description: The /assets and /asset-events endpoints that resolve assets by name, URI or alias and list asset events for inlet and outlet access in a task.
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/routes/assets.py
tags: [execution-api, assets, asset-events, lineage, api-route]
timestamp: 2026-09-30T16:35:13Z
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/assets.py
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/asset_events.py
generated_by: catalogify/0.10.1
open_questions:
  - "Is the asset-event listing limit a hard cap that callers depend on, or a default that the Task SDK can override?"
---

# Responsibilities

Resolves an asset reference a task used in code (name, URI, or alias) to the
asset record, and lists the asset events that feed inlet access and
`triggering_asset_events`. Asset state is a separate concern, covered by the
[state stores](../apis/execution-api-state-stores.md).

# Interfaces

| Symbol | Route | Purpose |
| --- | --- | --- |
| `get_asset_by_name` | `GET /assets/by-name` | Resolve an asset by name. |
| `get_asset_by_uri` | `GET /assets/by-uri` | Resolve an asset by URI. |
| `get_assets_by_alias` | `GET /assets/by-alias` | Assets reachable through an alias. |
| `get_asset_event_by_asset_name_uri` | `GET /asset-events/by-asset` | Events for an asset identified by name or URI. |
| `get_asset_event_by_asset_alias` | `GET /asset-events/by-asset-alias` | Events for an asset alias. |

# Dependencies

- Asset rows are defined in the core models; the response models are in [Execution API data models](../data/execution-api-datamodels.md) (`asset.py`, `asset_event.py`).
- Versioned additions such as `AddAssetsByAliasEndpoint` and the partition fields are in [Execution API versioning](../modules/execution-api-versioning.md).
- Task SDK clients are `AssetOperations` and `AssetEventOperations` in the [Task SDK API client](../modules/task-sdk-api-client.md); the context accessors that consume them are in [Task SDK task runner](../modules/task-sdk-task-runner.md).

# Notes

- Alias resolution and event listing are separate routes. A change that alters how aliases map to assets needs to be checked in both `assets.py` and `asset_events.py`.
- Events carry partition keys from the 2026 versions onward (`AddPartitionKeyField`, `AddConsumedAssetEventPartitionKeyField`). Older clients do not see them.
- `_raise_if_not_found` centralises the 404 for asset lookups.

No commit in this concept's history was flagged by the history helper, so no historical gotchas are recorded here.
