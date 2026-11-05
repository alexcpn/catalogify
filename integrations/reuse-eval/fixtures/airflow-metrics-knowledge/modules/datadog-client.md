---
type: Module
title: Datadog client
description: SafeDogStatsdLogger wraps DogStatsd, emitting native tags and honoring the shared validators.
resource: https://github.com/apache/airflow/blob/main/shared/observability/src/airflow_shared/observability/metrics/datadog_logger.py
tags: [metrics, datadog]
timestamp: 2026-07-20T15:52:00+01:00
source_files:
  - shared/observability/src/airflow_shared/observability/metrics/datadog_logger.py
generated_by: catalogify/0.10.1
---

# Responsibilities

Creates a `DogStatsd` client (lazy import) with constant tags from a comma-separated string and wraps it with the same validation and allow/block-list behaviour as the [StatsD client](statsd-client.md). Tags are native: `key:value`, or bare `key` when the value is empty.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `get_dogstatsd_logger` | Factory; sets host, port, namespace and constant tags only when supplied. |
| `SafeDogStatsdLogger` | Backend with `incr`, `decr`, `gauge`, `timing`, `timer`. |

# Dependencies

* Uses [name validation](name-validation.md) and `Timer` ([stats facade](stats-facade.md)).
* Configured by [core](core-metrics-adapters.md) / [Task SDK](task-sdk-metrics-adapters.md) adapters.
* External: `datadog`.

# Gotchas

* Tags are only sent when `metrics_tags` (`statsd_datadog_metrics_tags`) is true; otherwise the tag list is empty.
* `timing` converts `timedelta` to milliseconds; `gauge` ignores `delta` (DogStatsd has no equivalent argument passed here).
* Tags on Dag-run and task-instance metrics gained optional Dag tags in `2a9d508e0b` (#68568).

# Citations

1. `2a9d508e0b` — Optionally emit Dag tags as metric tags (#68568).
