---
type: Module
title: Execution API versioning (Cadwyn version bundle)
description: How the Execution API's CalVer versions and VersionChange migrations are declared, and the rules for adding to unreleased versus released version files.
resource: https://github.com/apache/airflow/blob/main/airflow-core/src/airflow/api_fastapi/execution_api/versions/__init__.py
tags: [module, execution-api, versioning, cadwyn, compatibility]
timestamp: 2026-09-26T22:16:29+01:00
source_files:
  - airflow-core/src/airflow/api_fastapi/execution_api/versions/__init__.py
  - airflow-core/src/airflow/api_fastapi/execution_api/versions/v2026_10_30.py
generated_by: catalogify/0.11.0
open_questions:
  - "Which release is the `2026-10-30` version targeted at, and is its date still tentative? Commit c921eaaacb collapsed earlier unreleased versions on the assumption that unreleased dates can move."
  - "Is there a policy for how many released Execution API versions are kept? Only the bundle list is visible in code."
  - "Do workers pinned to an older Task SDK ever send a version header that is no longer in the bundle, and what does the server answer?"
---

# Responsibilities

Declares the ordered list of Execution API versions (`VersionBundle`) that Cadwyn uses to generate per-version routers and OpenAPI documents. Workers and the API server deploy independently, so each version file describes how a newer server response or request is rewritten for an older client. `HeadVersion()` marks the unreleased head. At this commit the newest dated `Version` is `2026-10-30`, and the Task SDK generated models target that same value (`API_VERSION` in `_generated.py`).

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `bundle` | The `VersionBundle` consumed by `create_task_execution_api_app`. |
| `Version("YYYY-MM-DD", *VersionChange)` | One released or unreleased API version and its migrations. |
| `HeadVersion()` | The unversioned head; new unreleased changes land in the newest dated file. |
| `VersionChange` subclasses in `vYYYY_MM_DD.py` | Field and endpoint migrations (`schema(...).field(...).didnt_exist`, `endpoint(...).didnt_exist`). |
| `VersionChangeWithSideEffects` | Used when a branch must check `is_applied` instead of comparing version strings. |

# Dependencies

- Consumed by [service app](../services/execution-api.md) and the [routes](../apis/execution-api-routes.md) it generates.
- Field migrations target [datamodels](../data/execution-api-datamodels.md).
- The Task SDK side regenerates `_generated.py` against the newest version ([API client](sdk-api-client.md)).
- The [add-field playbook](../operations/playbooks/add-execution-api-field.md) walks the full change.
- The SDK-side supervisor schema bundle is a separate Cadwyn bundle; see [schema versioning](sdk-schema-versioning.md).

# Gotchas

- Do not add a change to a version file that has shipped. Add it to the newest dated file if that date is in the future, otherwise create a new `vYYYY_MM_DD.py` and add it to `bundle` (see `AGENTS.md` under `execution_api/`).
- Unreleased versions are collapsed before release. Commit `c921eaaacb` ("Collapse unreleased Execution API versions under 2026-06-30") merged two unreleased versions into one, which means a version name in a test can disappear between commits.
- Response converters must be added for new fields in nested objects, not only at the top level. The directory's agent doc lists this as a pitfall.
- Version-gated behaviour must not compare the negotiated version string. Use a `VersionChangeWithSideEffects` subclass and its `is_applied` flag.
- Commit `82215cf97c` changed `versions/__init__.py` and `v2026_10_30.py` together with `security.py`: a new auth-relevant endpoint can require both a version change and a scope change.

# Citations

- `c921eaaacb` — collapse of unreleased versions into `2026-06-30`.
- `82215cf97c` — callback token change; touched the `2026-10-30` version file.
- `05519cd774` — task attempt alignment touched `versions/__init__.py` and `v2026_10_30.py`.
