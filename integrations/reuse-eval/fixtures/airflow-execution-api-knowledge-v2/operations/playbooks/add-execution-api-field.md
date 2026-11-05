---
type: Playbook
title: Add a field or endpoint to the Execution API
description: Ordered steps for a change that touches the Execution API datamodels, routes, version bundle and the Task SDK generated client, which co-change in every recent instance.
applies_to:
  - airflow-core/src/airflow/api_fastapi/execution_api/datamodels/
  - airflow-core/src/airflow/api_fastapi/execution_api/routes/
relations:
  - {kind: requires, target: airflow-core/src/airflow/api_fastapi/execution_api/versions/__init__.py, evidence: [05519cd774, f14bed9b85, 63b615b252]}
  - {kind: requires, target: task-sdk/src/airflow/sdk/api/datamodels/_generated.py, evidence: [05519cd774, f14bed9b85, 63b615b252]}
generated_by: catalogify/0.11.0
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/versions/__init__.py
  - task-sdk/src/airflow/sdk/api/datamodels/_generated.py
open_questions:
  - "Step 5 requires the message type to be added to the Dag processor and triggerer exclusion lists. Is that list still maintained by hand, or is there a test that fails when it drifts?"
---

# Steps

Applies when a datamodel under `execution_api/datamodels/` or a route under `execution_api/routes/` changes shape. Sources for each step are named in brackets.

1. **Datamodel.** Add or change the request or response model in `airflow-core/src/airflow/api_fastapi/execution_api/datamodels/`. [`execution_api/AGENTS.md`, "Adding a New Feature End-to-End", step 1]
2. **Route.** Add or change the endpoint in `airflow-core/src/airflow/api_fastapi/execution_api/routes/`. Use `Security(require_auth, scopes=[...])` for the token types that may call it. [`execution_api/AGENTS.md` step 2; `security.py` docstring]
3. **Version migration.** If the change is unreleased and the newest dated file in `versions/` is in the future, add the `VersionChange` to that file. Otherwise create `vYYYY_MM_DD.py`, and add it to `bundle` in `versions/__init__.py`. Use `schema(Model).field("name").didnt_exist` for a new field and `endpoint("/path", ["GET"]).didnt_exist` for a new endpoint, with positional arguments. Add response converters for nested objects. [`execution_api/AGENTS.md` "When Making Changes" and "Common Patterns"]
4. **Task SDK message types (only if a new worker message is needed).** Add the request and response classes in `task-sdk/src/airflow/sdk/execution_time/comms.py`, the client method in `task-sdk/src/airflow/sdk/api/client.py`, and the handler in `task-sdk/src/airflow/sdk/execution_time/supervisor.py`. [`execution_api/AGENTS.md` steps 4–6]
5. **Dag processor and triggerer.** If a new message type was added, add it to the handler or exclusion lists in `airflow-core/src/airflow/dag_processing/processor.py` and `airflow-core/src/airflow/jobs/triggerer_job_runner.py`. [`execution_api/AGENTS.md` step 7]
6. **Regenerate the Task SDK models.** Run `uv run --active --group codegen --project apache-airflow-task-sdk --directory task-sdk -s dev/generate_task_sdk_models.py`. This writes `task-sdk/src/airflow/sdk/api/datamodels/_generated.py` from the in-process OpenAPI document of the newest version. Do not edit `_generated.py` by hand. [`execution_api/AGENTS.md` step 8; `.pre-commit-config.yaml` entry for the same command; `task-sdk/dev/generate_task_sdk_models.py`]
7. **Tests.** Add endpoint tests in `airflow-core/tests/unit/api_fastapi/execution_api/`, both for the new version and for the previous one. Add client tests in `task-sdk/tests/task_sdk/api/test_client.py`. If there is a new message type, add a `RequestTestCase` entry in `task-sdk/tests/task_sdk/execution_time/test_supervisor.py` and runner coverage in `test_task_runner.py`. [`execution_api/AGENTS.md` step 9 and "When Making Changes" step 4]
8. **Check the version header.** Run the versioned OpenAPI test (`airflow-core/tests/unit/api_fastapi/execution_api/test_app.py`) so that older `Airflow-API-Version` values still produce the schema they expect.

# Evidence

Three recent commits changed the datamodels, the version bundle and `_generated.py` together: `05519cd774` (attempt UUIDs), `f14bed9b85` (`retry_reason`) and `63b615b252` (team-scoped macros). The commit history shows about thirty commits in this shape, so the sequence is established. Steps 4 and 5 apply only to new message types, not to field changes.

# Pitfalls

- Never add a change to a version file that has already shipped (see [versioning](../../modules/execution-api-versioning.md)).
- Never branch business logic on the negotiated version string; use `VersionChangeWithSideEffects` and `is_applied`.
- A field added to a model without a version change is seen by older workers, which will reject it if their models are strict.
