---
type: Data Model
title: Execution API datamodels (task instance, run context, tokens)
description: The request and response models of the Execution API — TI state payloads, the run context returned at startup, and the JWT claim models.
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/datamodels/taskinstance.py
tags: [data-model, execution-api, pydantic, schema]
timestamp: 2026-09-26T22:16:29+01:00
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/datamodels/taskinstance.py
  - airflow-core/src/airflow/api_fastapi/execution_api/datamodels/token.py
generated_by: catalogify/0.11.0
relations:
  - {kind: versioned_by, target: airflow-core/src/airflow/api_fastapi/execution_api/versions/, evidence: [05519cd774, f14bed9b85, 63b615b252]}
open_questions:
  - "The state payload models use StrictBaseModel. Is strictness (extra fields rejected) intended for requests only, or also for responses that older workers parse?"
---

# Schema

Key models in `taskinstance.py`:

| Model | Role |
| --- | --- |
| `TIEnterRunningPayload` | Body of `PATCH /task-instances/{id}/run`. |
| `TISuccessStatePayload`, `TIRetryStatePayload`, `TIDeferredStatePayload`, `TIRescheduleStatePayload`, `TIAwaitingInputStatePayload`, `TISkippedDownstreamTasksStatePayload` | Bodies of `PATCH .../state` and skip-downstream, one per terminal or intermediate state. |
| `TITerminalStatePayload`, `TerminalStateNonSuccess` | Terminal failure states and their enum. |
| `TIHeartbeatInfo` | Body of the heartbeat. |
| `TIRunContext` | What a worker receives at startup (identity, dag run, bindings, team). |
| `TaskInstance`, `DagRun` | Read-side representations. |
| `TaskStatesResponse`, `TaskBreadcrumbsResponse`, `PreviousTIResponse`, `PrevSuccessfulDagRunResponse` | Read responses. |

Token models in `token.py`: `TokenScope` (a `Literal` of `"execution"`, `"workload"`, `"callback"`), `TIClaims`, `TIToken`.

# Interfaces

The models are used as request bodies and response types by [routes](../apis/execution-api-routes.md). The Task SDK does not import them directly; it consumes the generated copies in `task-sdk/src/airflow/sdk/api/datamodels/_generated.py` (see [API client](../modules/sdk-api-client.md)).

# Dependencies

- Imported by the routes and by [security](../modules/execution-api-security.md) (token models).
- Changes here are migrated through [versioning](../modules/execution-api-versioning.md) with `VersionChange` classes.
- Regeneration of the SDK copies follows the [add-field playbook](../operations/playbooks/add-execution-api-field.md).

# Gotchas

- Commit `05519cd774` added attempt fields that must be set together with the try number; the model alone does not enforce the pairing.
- `TITerminalStatePayload.retry_reason` (added by `f14bed9b85`, "Persist `retry_reason` not just for retries but even when a task fails") is a field that older workers do not send. A new field of this kind needs a version migration in `versions/` so that older clients keep working, and must not be added to an already-released version file.
- `TokenScope` includes `callback`, which the security module docstring does not list (see [security](../modules/execution-api-security.md)).

# Citations

- `05519cd774` — attempt UUID and try number pairing.
- `f14bed9b85` — `retry_reason` on terminal failure.
- `63b615b252` — scope plugin macros to their team in multi-team mode.
