---
type: Module
title: Execution API versioning (Cadwyn)
description: How the Execution API keeps older workers and newer API servers compatible through dated Cadwyn version bundles and per-version change classes.
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/versions/__init__.py
tags: [execution-api, cadwyn, versioning, compatibility, backward-compatibility]
timestamp: 2026-09-26T21:16:29Z
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/versions/__init__.py
  - airflow-core/src/airflow/api_fastapi/execution_api/versions/v2026_10_30.py
  - airflow-core/src/airflow/api_fastapi/execution_api/services/task_instances.py
generated_by: catalogify/0.10.1
open_questions:
  - "What is the oldest Execution API version that the minimum supported worker release still sends, and when can the older version bundles be removed?"
  - "Is the empty 2025-04-11 bundle entry the compatibility baseline, and does anything rely on it being present?"
---

# Responsibilities

The Execution API is versioned with Cadwyn and CalVer. `versions/__init__.py`
holds one `VersionBundle` with a `HeadVersion` and dated `Version` entries
(newest first, from `2026-10-30` back to `2025-04-11`). Each dated file
contains `VersionChange` classes that describe how the head schema, endpoints
or responses differ from the previous version. Workers and API servers deploy
independently, so a head change must be expressible as a conversion back to the
older shape. Only that bundle is the HTTP contract; the Task SDK supervisor's
body schemas are versioned separately in
[Task SDK schema versioning](../modules/task-sdk-schema-versioning.md).

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `bundle` | The `VersionBundle` that Cadwyn uses to build the versioned app. |
| `AddArgBindingsToTIRunContext` | Version change for argument bindings in the task-run context (`v2026_10_30.py`). |
| `client_supports_arg_bindings` | Reads the `is_applied` flag of a `VersionChangeWithSideEffects` rather than comparing version strings. |
| `get_arg_bindings` | Computes argument bindings for a task instance when the client supports them. |

# Dependencies

- Owns the schema contract for [Execution API data models](../data/execution-api-datamodels.md).
- Applied to every route in [Execution API server](../services/execution-api.md).
- Changes to task-instance responses touch [task instances](../apis/execution-api-task-instances.md) and the generated models in the [Task SDK API client](../modules/task-sdk-api-client.md).

# Gotchas

- Released version files are frozen. The in-progress version is the newest file whose date is still in the future; a change added to an already-released file silently changes an old contract.
- Branch on capability, not version strings. `client_supports_arg_bindings` returns `AddArgBindingsToTIRunContext.is_applied`. Comparing the negotiated version to a date would break when a bundle is re-cut.
- Endpoints added in the newest bundle are mounted through `endpoint(...).didnt_exist`. `8e1667e004` added the connection-test endpoints and their version entries in the same commit as the route, which is the pattern new endpoints should follow.
- Task-instance field additions were also versioned in `05519cd774`, which changed the datamodel, the route, `versions/__init__.py`, the head version file and the generated client models together. Keep those in sync when adding a field.

# Citations

1. `8e1667e004`: added connection-test endpoints with `versions/__init__.py` and `v2026_06_30.py` changes.
2. `05519cd774`: task attempt UUID and try-number alignment, which touched the version bundle, head version and generated models.
