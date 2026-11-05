---
type: Module
title: Metrics registry
description: YAML catalogue of every Airflow metric with its legacy name and name variables, plus the RST docs generator.
resource: https://github.com/apache/airflow/blob/main/shared/observability/src/airflow_shared/observability/metrics/metrics_template.yaml
tags: [metrics, registry, docs]
timestamp: 2026-08-22T15:00:10-07:00
source_files:
  - shared/observability/src/airflow_shared/observability/metrics/metrics_registry.py
  - shared/observability/src/airflow_shared/observability/metrics/metrics_template.yaml
generated_by: catalogify/0.10.1
open_questions:
  - "Which prek hook or CI step regenerates metric_tables.rst, and is it run automatically on registry change?"
---

# Responsibilities

`metrics_template.yaml` lists each metric (`name`, `description`, `type`, `legacy_name`, `name_variables`). `MetricsRegistry` loads it for name lookup by the [stats facade](stats-facade.md); `generate_metrics_rst_from_registry` renders counters, gauges and timers into the documentation table file.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `MetricsRegistry` | Loads the YAML; `get(name)` returns the entry or None. |
| `read_metrics_yaml` | Parses a registry file, raising `FileNotFoundError` if missing. |
| `convert_to_rst_tables` | Builds RST tables grouped by metric type. |
| `write_metric_tables_file` | Writes the tables with licence header and do-not-edit warning. |
| `generate_metrics_rst_from_registry` | End-to-end docs generation. |

# Dependencies

* Consumed by the [stats facade](stats-facade.md) (lazy-initialised to avoid import-time file I/O).
* External: `pyyaml`, `tabulate` (imported lazily).

# Gotchas

* **Entries without a legacy name use `legacy_name: "-"`**, which suppresses dual emission.
* **Every metric emitted in code must have a registry entry**; a prek check keeps them in sync and now also detects stale entries (`f44634c215`, #69578).
* Dynamic metric names are matched on all static parts, not just the prefix before the first variable, so names built from a caller-supplied prefix can be validated (`bcf1dbf41a`, #71815).

# Citations

1. `f44634c215` — Detect stale metrics registry entries in the metrics sync prek hook (#69578).
2. `bcf1dbf41a` — Report Dag cache metrics under each component's own namespace (#71815).
