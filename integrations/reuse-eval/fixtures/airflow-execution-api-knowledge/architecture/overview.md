---
type: Reference
title: Execution API and Task SDK runtime overview
description: "Start here: how the Execution API server and the Task SDK runtime (client, supervisor, task runner, comms and schema) cooperate so that a task runs without touching the metadata database."
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/app.py
tags: [architecture, execution-api, task-sdk, overview, start-here]
timestamp: 2026-09-30T08:10:25Z
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/app.py
  - task-sdk/src/airflow/sdk/execution_time/supervisor.py
  - task-sdk/src/airflow/sdk/execution_time/task_runner.py
  - task-sdk/src/airflow/sdk/api/client.py
generated_by: catalogify/0.10.1
open_questions:
  - "Is the Task SDK runtime expected to remain usable against an Execution API server one version older or newer, and which direction is tested in CI?"
---

# Responsibilities

A running task is split across three processes and one HTTP boundary. The
**Execution API server** runs inside the API server and is the only component
that reads or writes metadata for a task. The **supervisor** runs in the
worker, forks the task process, watches its pipes and heartbeat, and makes the
HTTP calls on its behalf. The **task runner** runs in the child process, builds
the task context, and executes the operator. Messages between supervisor and
task go over a msgpack socket protocol (comms). The contract on each side is
versioned separately: the HTTP contract with Cadwyn, and the lang-SDK message
shapes with a second Cadwyn bundle.

The data flow for one attempt is: the supervisor calls `ti_run`, the task
runs, its requests arrive at the supervisor over comms and are forwarded through
the client, the heartbeat keeps the attempt alive, and `ti_update_state` records
the outcome.

# Interfaces

| Component | Entry point | Concept |
| --- | --- | --- |
| Execution API app | `create_task_execution_api_app` | [Execution API server](../services/execution-api.md) |
| Token checks | `JWTBearer`, `require_auth`, `ExecutionAPIRoute` | [security](../modules/execution-api-security.md) |
| HTTP versions | `bundle` (Cadwyn `VersionBundle`) | [versioning](../modules/execution-api-versioning.md) |
| Worker HTTP client | `Client` | [API client](../modules/task-sdk-api-client.md) |
| Supervisor | `ActivitySubprocess`, `WatchedSubprocess` | [supervisor](../modules/task-sdk-supervisor.md) |
| Task process | `main`, `run`, `finalize` | [task runner](../modules/task-sdk-task-runner.md) |
| Child/parent channel | `CommsDecoder`, `ToTask`, `ToSupervisor` | [comms](../modules/task-sdk-comms.md) |
| Lang-SDK schema | `SchemaVersionMigrator` | [schema versioning](../modules/task-sdk-schema-versioning.md) |

Route groups, each with its own concept: [task instances](../apis/execution-api-task-instances.md),
[XComs](../apis/execution-api-xcoms.md), [Dags and Dag runs](../apis/execution-api-dags-and-dag-runs.md),
[assets](../apis/execution-api-assets.md), [connections and variables](../apis/execution-api-connections-and-variables.md),
[state stores](../apis/execution-api-state-stores.md), [HITL and callbacks](../apis/execution-api-hitl-and-callbacks.md).
Request and response models: [data models](../data/execution-api-datamodels.md).

# Dependencies

- The Execution API is the only path to metadata for workers; the scheduler and the Dag processor do not appear in this scope except as callers noted in the service concept.
- In-process use (`dag.test`, the Dag processor and the triggerer) goes through `InProcessExecutionAPI` and the in-process supervisor in [supervisor](../modules/task-sdk-supervisor.md).
- Co-change in the repo-wide history links this scope to `ts-sdk/src` (about 19% of Execution API commits; see the [service](../services/execution-api.md)), to `airflow-ctl/src` (about 40% of client-side commits), and to the tests of both sides. These are observed couplings; their mechanism is not documented here.

# Gotchas

- Both sides of every route change must move together. The Execution API `AGENTS.md` lists the steps; the tests live under `airflow-core/tests/unit/api_fastapi/execution_api/` and `task-sdk/tests/`.
- Heartbeat handling is the main source of supervisor changes. A 409 on heartbeat, a 410 for a cleared attempt, and the orphan-subprocess cleanup all depend on each other (`6145746438`, `ce1270b96f`).
- The HTTP contract and the lang-SDK contract are independent. A change to one does not bump the other (see the [schema versioning](../modules/task-sdk-schema-versioning.md) concept).

# Citations

1. `6145746438`, `ce1270b96f`: supervisor heartbeat behaviour for 409 and 410 responses.
2. `2b6e8181e3`: two-token mechanism for tasks waiting in executor queues.
3. `8095abb571`, `609656f7d3`, `82215cf97c`: deadline-callback fetch through the Execution API, reverted and re-landed.

# Notes

Files in scope that do not have their own concept in this bundle: `task-sdk/.../execution_time/coordinator.py`, `bundles.py`, `context.py` (covered by the task runner concept but not in its detail), `secrets/execution_api.py`, `cache.py`, `secrets_masker.py`, `hitl.py`, `macros.py`, `task_mapping.py`, `lazy_sequence.py`, `timeout.py`, `tracing.py`, `sentry/`, and `email_backend.py`. They were skipped for this medium-granularity pass.
