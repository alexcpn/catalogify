---
type: Module
title: OpenTelemetry client
description: SafeOtelLogger maps Airflow counters, gauges and timers onto OpenTelemetry instruments and builds the MeterProvider.
resource: https://github.com/apache/airflow/blob/main/shared/observability/src/airflow_shared/observability/metrics/otel_logger.py
tags: [metrics, opentelemetry]
timestamp: 2026-08-18T21:12:44+02:00
source_files:
  - shared/observability/src/airflow_shared/observability/metrics/otel_logger.py
generated_by: catalogify/0.10.1
open_questions:
  - "SafeOtelLogger.decr calls get_counter without the tags while incr passes them; is the missing attributes argument intentional?"
  - "Is `airflow.dag_processing.processes` still the only entry in UP_DOWN_COUNTERS that needs to be?"
---

# Responsibilities

`get_otel_logger` configures an OTLP-exporting `MeterProvider` (or adopts one built from `OTEL_CONFIG_FILE`) and returns a `SafeOtelLogger`. Names are prefixed (`airflow.` by default). Counters, gauges and histograms are cached in a `MetricsMap` keyed by name plus attributes. Timers and `timing` are stored as exponential-bucket histograms, in milliseconds.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `get_otel_logger` | Builds provider, readers and view; registers an at-exit flush. |
| `SafeOtelLogger` | Backend with `incr`, `decr`, `gauge`, `timing`, `timer`. |
| `MetricsMap` | Cache of counters, gauges and histograms. |
| `InternalGauge` | Sync gauge with current value to support `delta`. |
| `InternalHistogram` | Histogram wrapper. |
| `name_is_otel_safe` | True when prefix + name satisfy OTel naming rules. |
| `full_name` | Joins prefix, `.` and name. |
| `flush_otel_metrics` | Forces the provider to export. |
| `atexit_register_metrics_flush` | Registers the flush at interpreter exit. |

# Dependencies

* Uses [name validation](name-validation.md) (`stat_name_otel_handler`, `get_validator`) and `Timer` ([stats facade](stats-facade.md)).
* Sibling package modules `..common`, `..otel_env_config` and `..exceptions` (outside the metrics package).
* Configured by [core](core-metrics-adapters.md) / [Task SDK](task-sdk-metrics-adapters.md) adapters.
* External: `opentelemetry-api`, `opentelemetry-sdk`.

# Gotchas

* **Every recording method must gate on `_is_recordable`.** The OTel SDK raises on unsafe names and would crash the scheduler or Dag processor. `gauge` and `timer` initially lacked the guard (`764c516b01`, #68284), and non-ASCII Dag names crashed the scheduler (`fe30279b37`, #68023).
* **The SDK's once-guard is reset before `set_meter_provider`.** After a fork the child inherited `_done = True` and kept the parent's dead provider, silently dropping task metrics (`ff77bd2f09`, closes `#64690`).
* **`OTEL_CONFIG_FILE` wins.** When it is set and a `MeterProvider` already exists, that provider is used as-is; previously Airflow replaced it and lost the declared views, readers and exporters (`f558ff1327`, #71529).
* **Only `airflow.dag_processing.processes` is an UpDownCounter**, so collectors don't type regular counters as gauges.
* **`rate < 1` samples randomly**; negative rates or counts raise `ValueError`.

# Citations

1. `764c516b01` — Fix DagProcessor crash: add missing name_is_otel_safe() guard (#68284).
2. `fe30279b37` — Fix scheduler crash with InvalidStatsNameException for non-ASCII Dag names (#68023).
3. `ff77bd2f09` — Fix OTel metrics lost in forked task processes (#64703).
4. `f558ff1327` — Stop discarding a MeterProvider configured via OTEL_CONFIG_FILE (#71529).
