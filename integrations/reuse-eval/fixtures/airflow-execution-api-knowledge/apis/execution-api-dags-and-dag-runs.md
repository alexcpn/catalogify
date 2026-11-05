---
type: API Resource
title: Execution API Dag and Dag run routes
description: The /dags and /dag-runs endpoints that let tasks and the Task SDK read Dag metadata, trigger, clear and inspect Dag runs, and count or look up previous runs.
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/routes/dag_runs.py
tags: [execution-api, dag-runs, dags, trigger, clear, api-route]
timestamp: 2026-07-30T13:54:58Z
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/dags.py
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/dag_runs.py
generated_by: catalogify/0.10.1
open_questions:
  - "Which callers are expected to trigger Dag runs through this route rather than the public REST API, and is that split enforced by token type or only by convention?"
---

# Responsibilities

Lets a task inspect and change Dag runs without direct database access, most
notably for `TriggerDagRunOperator` and `ExternalTaskSensor` under the Task
SDK. `trigger_dag_run` creates a run, `clear_dag_run` clears one, and the read
routes return run state, counts and the previous run.

# Interfaces

| Symbol | Route | Purpose |
| --- | --- | --- |
| `get_dag` | `GET /dags/{dag_id}` | Dag metadata used by the Task SDK. |
| `get_dag_run` | `GET /dag-runs/{dag_id}/{run_id}` | Detail for one run. |
| `trigger_dag_run` | `POST /dag-runs/{dag_id}/{run_id}` | Create a run. |
| `clear_dag_run` | `POST /dag-runs/{dag_id}/{run_id}/clear` | Clear a run. |
| `get_dagrun_state` | `GET /dag-runs/{dag_id}/{run_id}/state` | State of one run. |
| `get_dr_count` | `GET /dag-runs/count` | Count matching runs. |
| `get_previous_dagrun` | `GET /dag-runs/previous` | Previous run for a logical date. |
| `get_previous_dagrun_compat` | (helper) | Serves the older `/{dag_id}/previous` shape. |

# Dependencies

- Operates on the models in the metadata DB; the Dag itself comes from serialized Dags, not from user code in the API server.
- Team-scope checks come from [Execution API security](../modules/execution-api-security.md).
- Versioned shape changes (for example `MovePreviousRunEndpoint` and `AddDagEndpoint`) are in [Execution API versioning](../modules/execution-api-versioning.md).
- Payloads are in [Execution API data models](../data/execution-api-datamodels.md) (`dagrun.py`, `dags.py`).

# Gotchas

- The previous-run endpoint changed shape in the 2026-04-06 version (`MovePreviousRunEndpoint`), and `get_previous_dagrun_compat` serves the older form. Clients on both sides must agree on the version they negotiated.
- `rerun_with_latest_version` was applied to `TriggerDagRunOperator` reruns in `d74fbff4e3`, which changed what a trigger call means for an existing run.
- Run-on-latest-version support for backfill and clear landed in `3dc4cd2e01`, which also touched `supervisor.py` and `task_instances.py`.
- The deadline-callback fetch that read Dag run data through this API was reverted in `609656f7d3` and later re-landed with its own token (see the [service](../services/execution-api.md)).

# Citations

1. `d74fbff4e3`: applies `rerun_with_latest_version` to `TriggerDagRunOperator` reruns.
2. `609656f7d3`: reverts the deadline callback fetch through the Execution API.
3. `3dc4cd2e01`: adds `run_on_latest_version` support for backfill and clear operations.
