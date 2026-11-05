---
type: Module
title: Task SDK adapters
description: Config-driven factories in task-sdk that pick and build the StatsD, Datadog or OpenTelemetry backend from the [metrics] section.
resource: https://github.com/apache/airflow/blob/main/task-sdk/src/airflow/sdk/observability/metrics/stats_utils.py
tags: [metrics, configuration]
timestamp: 2026-04-30T19:11:00+01:00
source_files:
  - task-sdk/src/airflow/sdk/observability/metrics/stats_utils.py
  - task-sdk/src/airflow/sdk/observability/metrics/statsd_logger.py
  - task-sdk/src/airflow/sdk/observability/metrics/datadog_logger.py
  - task-sdk/src/airflow/sdk/observability/metrics/otel_logger.py
generated_by: catalogify/0.10.1
open_questions:
  - "Why are these adapters copied per distribution instead of parameterised by the config object?"
---

# Responsibilities

Each module reads the `[metrics]` options through `airflow.sdk.configuration` and calls the matching factory in the shared package. `get_stats_factory` returns the factory used by `Stats.initialize`: Datadog if `statsd_datadog_enabled`, else StatsD if `statsd_on`, else OpenTelemetry if `otel_on`, else `NoStatsLogger`. Backend modules are imported lazily so unused client libraries are never loaded.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `get_stats_factory` | Selects the backend factory from config (`stats_utils.py`). |
| `get_statsd_logger` | Builds the [StatsD client](statsd-client.md); honours `statsd_custom_client_path`. |
| `get_dogstatsd_logger` | Builds the [Datadog client](datadog-client.md). |
| `get_otel_logger` | Builds the [OpenTelemetry client](otel-client.md). |

# Dependencies

* Delegates to the shared clients above and uses `NoStatsLogger` from the [stats facade](stats-facade.md) module.
* Mirror of [core-metrics-adapters](core-metrics-adapters.md): the files differ only in import roots (`airflow` vs `airflow.sdk`).
* Package: `airflow.sdk.observability.metrics`.

# Gotchas

* A custom StatsD client must subclass `statsd.StatsClient`, otherwise `AirflowConfigException` is raised at start-up.
* The OTel adapter reads `otel_port` and `otel_interval_milliseconds` only if the option is present, because those settings are deprecated in favour of the standard OTel environment variables (`63ea296047`, #56150).
* The two adapter packages must be kept in step by hand; the Stats interfaces were removed from them in `67bab4a285` (#63932) and legacy-name export became configurable in `b2213ba146` (#53722).

# Citations

1. `63ea296047` — Use the regular OTel environment variables for configuring traces and metrics (#56150).
2. `67bab4a285` — Remove the DualStatsManager and the Stats interfaces (#63932).
3. `b2213ba146` — Option to disable exporting of legacy metric names (#53722).
