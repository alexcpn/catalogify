# Execution API and Task SDK runtime knowledge bundle

This directory is generated from the repository with catalogify (OKF v0.1). It covers `airflow-core/src/airflow/api_fastapi/execution_api/`, `task-sdk/src/airflow/sdk/api/` and `task-sdk/src/airflow/sdk/execution_time/`. Start at [architecture/overview.md](architecture/overview.md), or open [index.md](index.md).

- Generator: catalogify 0.11.0. Built from commit `8d4ab8a94d`.
- Concepts: 15 (see [index.md](index.md)).
- Check it: `catalogify validate knowledge` checks structure; `catalogify verify knowledge` checks every cited commit, symbol, path and typed relation against git.

For agents: before changing a file, run `catalogify find <file>` and follow any guardrail and playbook it returns. Do not read the whole bundle up front.

To correct it: unresolved uncertainty is parked in each concept's `open_questions`. `catalogify clarify` walks a human through them, and an answer given there is marked with a sentinel and survives later regeneration. This is the part a machine cannot produce.
