---
type: Module
title: Stats facade
description: Process-wide singleton facade (incr/decr/gauge/timing/timer) that lazily builds a backend and dual-emits legacy metric names.
resource: https://github.com/apache/airflow/blob/main/shared/observability/src/airflow_shared/observability/metrics/stats.py
tags: [metrics, facade]
timestamp: 2026-07-20T15:52:00+01:00
source_files:
  - shared/observability/src/airflow_shared/observability/metrics/stats.py
  - shared/observability/src/airflow_shared/observability/metrics/base_stats_logger.py
  - shared/observability/src/airflow_shared/observability/metrics/protocols.py
generated_by: catalogify/0.10.1
open_questions:
  - "Is dual emission (legacy + modern name) meant to be removable once `export_legacy_names` defaults to false, and is there a deprecation timeline?"
---

# Responsibilities

Holds module-level state (`_factory`, `_backend`, `_registry`, `_export_legacy_names`) and exposes functions that forward to the backend. For each call it asks the [registry](metrics-registry.md) for a legacy name; if present it emits the legacy metric (with the leftover tags) and then the regular metric. The backend is created on first use and falls back to `NoStatsLogger` on `socket.gaierror` or `ImportError`.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `initialize` | Stores the backend factory and legacy-name flag; clears any existing backend. |
| `incr` / `decr` | Counter changes; emit legacy name too when registered. |
| `gauge` | Set a gauge value. |
| `timing` | Record a duration. |
| `timer` | Context manager / stopwatch; returns a `_DualTimer` when a legacy name exists. |
| `Stats` | Class shim exposing the same functions as static methods for old call sites. |
| `normalize_name_for_stats` | Replaces characters outside `[a-zA-Z0-9_.-]` with `_`, optionally warning. |
| `build_dag_metric_tags` | Converts Dag tag strings (`env:prod`) into a tag dict. |
| `StatsLogger` | Protocol every backend satisfies (in `base_stats_logger.py`). |
| `NoStatsLogger` | No-op fallback backend. |
| `Timer` | Duration-recording timer wrapping a backend timer (in `protocols.py`). |

# Dependencies

* Uses the [metrics registry](metrics-registry.md) for legacy names.
* Backends: [StatsD](statsd-client.md), [Datadog](datadog-client.md), [OpenTelemetry](otel-client.md); they share `Timer` from `protocols.py`.
* Constructed by the factories in [core adapters](core-metrics-adapters.md) and [Task SDK adapters](task-sdk-metrics-adapters.md).
* External: stdlib only (`os`, `re`, `socket`, `logging`).

# Gotchas

* **Backend must be rebuilt in forked children.** `os.register_at_fork` resets `_backend` so each child calls the factory again; inherited OTel providers have dead exporter threads (see [OpenTelemetry client](otel-client.md)).
* **Legacy names flatten dots in tag values** (`.` becomes `__`) because StatsD treats `.` as hierarchy; a task id like `group.task` would otherwise add a segment. Missing name variables raise `ValueError`.
* **The Stats interfaces were collapsed into this module** and the DualStatsManager removed, so the dual-emit logic lives here (`67bab4a285`, #63932).
* **Dag tags are optional metric tags** built by `build_dag_metric_tags`; built-in keys win on collision (`2a9d508e0b`, #68568).

# Citations

1. `67bab4a285` — Remove the DualStatsManager and the Stats interfaces (#63932).
2. `2a9d508e0b` — Optionally emit Dag tags as metric tags (#68568).
