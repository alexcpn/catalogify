---
type: Reference
title: Execution API and Task SDK runtime — overview
description: How a task instance is run by the Task SDK supervisor and task process, and how both talk to the Execution API served by the API server.
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/app.py
tags: [architecture, execution-api, task-sdk, start-here]
timestamp: 2026-09-29T14:41:25+05:30
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/app.py
  - task-sdk/src/airflow/sdk/execution_time/supervisor.py
  - task-sdk/src/airflow/sdk/api/client.py
generated_by: catalogify/0.11.0
open_questions:
  - "Is the Execution API intended to stay private to Airflow components (the app description says 'private'), or is an external client a supported use case?"
---

# Execution API and Task SDK runtime — overview

This bundle covers three scoped subsystems. Start here, then follow links.

| Layer | Where it runs | Concept |
| --- | --- | --- |
| Execution API (FastAPI + Cadwyn, mounted under `/execution`) | API server | [Execution API service](../services/execution-api.md) |
| Routes, security, versions, datamodels | API server | [Routes](../apis/execution-api-routes.md), [Security](../modules/execution-api-security.md), [Versioning](../modules/execution-api-versioning.md), [Datamodels](../data/execution-api-datamodels.md) |
| Supervisor (parent process on the worker) | Worker | [Task SDK runtime service](../services/task-sdk-runtime.md), [Supervisor](../modules/sdk-supervisor.md) |
| Task process (user code, `RuntimeTaskInstance`) | Worker, child process | [Task runner](../modules/sdk-task-runner.md), [Comms](../modules/sdk-comms.md) |
| HTTP client and generated models | Worker | [API client](../modules/sdk-api-client.md) |
| Secrets backend that calls the API | Worker | [ExecutionAPISecretsBackend](../modules/sdk-secrets-execution-api.md) |
| Supervisor schema migration | Worker | [Schema versioning](../modules/sdk-schema-versioning.md) |

## How the pieces fit

1. The scheduler queues a task instance; a worker starts the supervisor (`supervise_task` in `supervisor.py`).
2. The supervisor forks or execs a task process. The task process never speaks HTTP. It sends msgpack request frames over its stdin socket, and the supervisor answers them ([comms](../modules/sdk-comms.md)).
3. The supervisor turns those requests into HTTP calls to the Execution API through the Task SDK `Client` ([API client](../modules/sdk-api-client.md)). It also heartbeats the task instance. Heartbeat failures are handled by the supervisor, not by the client's retry loop.
4. The API server authenticates each request with a short-lived JWT scoped to one task instance ([security](../modules/execution-api-security.md)). Routes live in [`routes/`](../apis/execution-api-routes.md) and use datamodels from [`datamodels/`](../data/execution-api-datamodels.md).
5. The Task SDK's generated models are produced from the Execution API's OpenAPI schema, so a server-side datamodel change is a client change too ([playbook](../operations/playbooks/add-execution-api-field.md)).

## Boundaries

The task process must not touch the metadata database. See the [guardrail](../operations/guardrails/task-code-no-direct-metadata-db.md).

## Where to look first

- Changing a wire field: follow the [add-field playbook](../operations/playbooks/add-execution-api-field.md).
- Changing an endpoint or its auth: [`catalogify find`](../apis/execution-api-routes.md) on the file first.
- Reading the "why": the gotchas in each module concept cite the commits that established the behaviour.
