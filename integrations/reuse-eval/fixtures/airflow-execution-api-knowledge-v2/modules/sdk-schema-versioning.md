---
type: Module
title: Task SDK supervisor schema versioning and migration
description: The second Cadwyn version bundle, which versions the wire shapes exchanged with non-Python (lang-SDK) runtimes, and the in-process migrator that up- and down-converts message bodies.
resource: https://github.com/apache/airflow/blob/main/task-sdk/src/airflow/sdk/execution_time/schema/__init__.py
tags: [module, task-sdk, schema, cadwyn, versioning, lang-sdk]
timestamp: 2026-06-26T19:52:45+09:00
source_files:
  - task-sdk/src/airflow/sdk/execution_time/schema/__init__.py
  - task-sdk/src/airflow/sdk/execution_time/schema/migrator.py
generated_by: catalogify/0.11.0
open_questions:
  - "The package docstring says two Cadwyn bundles coexist (this one and the Execution API's). Is there a rule for when a change must go into both, and who checks that they stay consistent?"
  - "Is `schema.json` in this directory generated from the bundle, or hand-maintained? The git history shows it changed with the schema versions; no generator is referenced from this module."
  - "Which lang-SDK runtime versions must be supported at once, and when may a schema version be dropped from the bundle?"
---

# Responsibilities

Versions the message bodies exchanged between the Task SDK supervisor and a non-Python runtime started by a coordinator (see [supervisor](sdk-supervisor.md) and the `coordinator.py` module). `schema/__init__.py` builds a Cadwyn `VersionBundle` and a registry of models by name. `SchemaVersionMigrator` walks that bundle in-process, so the supervisor can downgrade outgoing bodies and upgrade incoming ones without an HTTP round-trip. The downgrade path re-validates against the Cadwyn-generated versioned class, so that `didnt_exist` instructions actually remove fields from what is sent.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `registered_models_by_name` | Lookup of versioned body classes by name. |
| `resolve_body_class` | Returns the body class for a message name at a given version. |
| `SchemaVersionMigrator` | Up- and down-converts bodies using the bundle. |
| `get_schema_version_migrator` | Returns the migrator instance for the process. |

# Dependencies

- The bodies themselves live in their semantic homes: [comms](sdk-comms.md) for task execution messages, and the Dag processor for Dag messages.
- The Execution API has its own, separate bundle; see [versioning](execution-api-versioning.md).
- Used by the coordinator path in `coordinator.py` when a non-Python runtime is configured under `[sdk] coordinators`.

# Gotchas

- Two bundles exist. A change to a message that crosses both the Execution API and a lang-SDK runtime must be versioned in both, and neither bundle checks the other.
- The migrator is in-process by design. Do not replace it with an HTTP call to the Cadwyn app; the supervisor cannot afford a network hop per message.
- Schema migration was added to the supervisor-child comm path in commit `0920c770c8` ("Add schema migration to supervisor-child comm"). Changes to message bodies must go through the bundle rather than being bypassed on one side of the pipe.
- Downgrades only drop fields that the versioned class declares as `didnt_exist`; a field added without a version change is sent to older runtimes unchanged.

# Citations

- `0920c770c8` — schema migration added to the supervisor-child comm path.
