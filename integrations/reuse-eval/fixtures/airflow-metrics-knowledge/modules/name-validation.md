---
type: Module
title: Name validation and metric filtering
description: Stat-name validation, OpenTelemetry length rules and the allow/block list validators shared by all backends.
resource: https://github.com/apache/airflow/blob/main/shared/observability/src/airflow_shared/observability/metrics/validators.py
tags: [metrics, validation]
timestamp: 2026-07-23T09:47:10+08:00
source_files:
  - shared/observability/src/airflow_shared/observability/metrics/validators.py
generated_by: catalogify/0.10.1
open_questions:
  - "Why does the allow-list regex match anywhere in the name (re.findall) rather than anchored; is substring matching documented user-facing behaviour?"
---

# Responsibilities

Decides whether a metric may be emitted. `validate_stat` wraps backend methods, applies the (configurable) name handler and swallows `InvalidStatsNameException` after logging. `get_validator` returns an allow-list or block-list validator; if both are configured the block list is ignored with a warning.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `validate_stat` | Decorator validating the stat name before the backend call. |
| `get_validator` | Chooses allow/block list validator. |
| `stat_name_otel_handler` | Validates prefix + name against OTel limits (255 chars). |
| `stat_name_default_handler` | Character-set and length check for StatsD/Datadog names. |
| `get_current_handler_stat_name_func` | Resolves the active handler, widening chars for InfluxDB. |
| `ListValidator` | Abstract base for list validators. |
| `PatternAllowListValidator` | Allows names matching any entry. |
| `PatternBlockListValidator` | Blocks names matching any entry. |
| `MetricNameLengthExemptionWarning` | Warning raised for exempted long names. |
| `BACK_COMPAT_METRIC_NAME_PATTERNS` | Legacy long-name patterns exempt from the OTel length limit. |

# Dependencies

* Raises `InvalidStatsNameException` from the package `..exceptions`.
* Used by the [StatsD](statsd-client.md), [Datadog](datadog-client.md) and [OpenTelemetry](otel-client.md) clients.

# Gotchas

* **The exemption list must only shrink.** The source says no new names may be added; exempted names still pass other checks and emit a warning that they will be truncated. A stale entry was removed in `f44634c215` (#69578).
* List entries are lower-cased regexes searched anywhere in the lower-cased name.
* `validate_stat` reads `stat_name_handler` and `statsd_influxdb_enabled` from the backend instance, so every backend must define both attributes.

# Citations

1. `f44634c215` — Detect stale metrics registry entries in the metrics sync prek hook (#69578).
