---
type: Module
title: StatsD client
description: SafeStatsdLogger wraps pystatsd with name validation, allow/block lists and optional InfluxDB-style tags.
resource: https://github.com/apache/airflow/blob/main/shared/observability/src/airflow_shared/observability/metrics/statsd_logger.py
tags: [metrics, statsd]
timestamp: 2026-07-20T15:52:00+01:00
source_files:
  - shared/observability/src/airflow_shared/observability/metrics/statsd_logger.py
generated_by: catalogify/0.10.1
open_questions:
  - "Should `statsd_influxdb_enabled` and `influxdb_tags_enabled` stay two separate parameters? Callers pass the same config value to both."
---

# Responsibilities

Builds a `statsd.StatsClient` and wraps it so every call is name-validated, filtered by the metrics allow/block list, and (when enabled) has tags appended to the stat name in InfluxDB line format. Plain StatsD has no native tags, so with tags disabled they are dropped.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `get_statsd_logger` | Keyword-only factory; builds the client, tag validator and metric validator. |
| `SafeStatsdLogger` | Backend with `incr`, `decr`, `gauge`, `timing`, `timer`. |
| `prepare_stat_with_tags` | Decorator appending `,key=value` tags to the stat name. |

# Dependencies

* Uses [name validation](name-validation.md) (`validate_stat`, `get_validator`, `PatternBlockListValidator`) and `Timer` from the [stats facade](stats-facade.md) module.
* Configured by [core](core-metrics-adapters.md) / [Task SDK](task-sdk-metrics-adapters.md) adapters.
* External: `statsd` (lazy, type-only import here).

# Gotchas

* Tags containing `,` or `=` in key or value are dropped with an error log rather than emitted, since they would corrupt the InfluxDB line (see `prepare_stat_with_tags`).
* `get_statsd_logger` is keyword-only; the arguments were converted from positional and an IPv6 test added (`4c1ce4e3ff`, #69632).
* An empty tag value is rendered as `true`, which is how Dag tags without a value surface (`2a9d508e0b`, #68568).

# Citations

1. `4c1ce4e3ff` — Refactor get_statsd_logger to use keyword arguments (#69632).
2. `2a9d508e0b` — Optionally emit Dag tags as metric tags (#68568).
