---
type: Guardrail
title: Task code never reads or writes the metadata database directly
description: Operator and task code, and the Task SDK modules that run it, reach task state only through the Execution API, never through SQLAlchemy models or sessions.
applies_to:
  - task-sdk/src/airflow/sdk/execution_time/
  - task-sdk/src/airflow/sdk/api/
rule: Code that runs inside a task (the task process and the Task SDK modules it imports) must not import Airflow ORM models or open database sessions. State access goes through the Execution API client, with a short-lived JWT scoped to one task instance.
forbids:
  - {pattern: "from airflow.models", in: [task-sdk/src/airflow/sdk/execution_time/task_runner.py, task-sdk/src/airflow/sdk/api/]}
generated_by: catalogify/0.11.0
open_questions:
  - "Please confirm this rule is a hard security boundary for this subsystem and not only a design preference. The repository's root agent doc (AGENTS.md) states it as an architecture boundary; the security model document is the authoritative reference and was not read for this bundle."
  - "The supervisor (supervisor.py) imports `airflow.models.dagbag` in the fork path. Should the forbids list include supervisor.py, or is the supervisor a deliberate exception that runs outside the task process?"
  - "The only literal guard found is `block_orm_access()` in the child process. Is any test checking that this guard is applied, given that no task-sdk test was found referencing it? Should `enforced_by` point at one?"
---

# Rule

Task code must not touch the metadata database directly. Every read or write of task state goes through the Execution API. Two layers enforce this in software, and neither is a security boundary against deliberate bypass:

1. The task process replaces the ORM session with `BlockedDBSession` (via `block_orm_access()`) before user code runs.
2. The `forbids` entry below is a static check on the task runner and the Task SDK API package: no literal `from airflow.models` import appears there.

Each task receives a JWT scoped to its task instance, so the Execution API can reject cross-task access even if a bypass occurs. Network-level blocking of the database is a deployment hardening measure, not something this bundle can verify.

# Why

The Execution API exists so that workers can run tasks without database credentials. The [task SDK runtime](../../services/task-sdk-runtime.md) and the [Execution API service](../../services/execution-api.md) are the two halves of this design, and the [supervisor](../../modules/sdk-supervisor.md) is where `block_orm_access()` is applied.

# How to apply

- Do not add `from airflow.models ...` imports to `task_runner.py`, `context.py`, or the Task SDK `api/` package. The `forbids` entry above fails `catalogify verify` if one appears.
- Add new task-side state access as an Execution API call through the [client](../../modules/sdk-api-client.md), then a route, as described in the [add-field playbook](../playbooks/add-execution-api-field.md).
- Do not treat a passing local test as proof of isolation. The guard is in-process only.

# Known limits

- `block_orm_access()` makes direct access fail with an error, but it does not stop code that opens a raw database connection.
- The root agent doc documents database access for the Dag processor and the triggerer as a known limitation. This guardrail covers only the task process and the Task SDK modules it runs.
