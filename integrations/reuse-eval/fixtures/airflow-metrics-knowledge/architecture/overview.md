---
type: Reference
title: Metrics clients architecture
description: How Airflow's StatsD, Datadog and OpenTelemetry metrics clients are layered across shared, airflow-core and task-sdk.
tags: [metrics, observability, architecture]
timestamp: 2026-11-05T00:00:00Z
generated_by: catalogify/0.10.1
open_questions:
  - "Is the airflow-core / task-sdk adapter duplication (identical files except import roots) intentional long-term, or is there a plan to generate one from the other?"
---

# Purpose

Airflow emits operational metrics (counters, gauges, timers) through one facade and one of three backends: StatsD, DogStatsD (Datadog) or OpenTelemetry. The code is split in three layers so that `airflow-core` and `task-sdk` can each read their own configuration yet share the same implementation.

# Layers

| Layer | Location | Role |
| --- | --- | --- |
| Shared implementation | `shared/observability/src/airflow_shared/observability/metrics/` | Backend clients, validators, registry, facade. Symlinked into both consumers as `airflow._shared.observability` and `airflow.sdk._shared.observability`. |
| Core adapters | `airflow-core/src/airflow/observability/metrics/` | Read `[metrics]` config via `airflow.configuration.conf` and build a backend. |
| Task SDK adapters | `task-sdk/src/airflow/sdk/observability/metrics/` | Same code, reading `airflow.sdk.configuration.conf`. |

# Flow

1. A component start-up calls `Stats.initialize(factory=stats_utils.get_stats_factory(), ...)` (called from the scheduler, executors, triggerer, Dag processor, API server and the task runner).
2. The factory picks the backend from config: Datadog, else StatsD, else OpenTelemetry, else `NoStatsLogger`.
3. Callers use the [stats facade](../modules/stats-facade.md), which looks the metric up in the [metrics registry](../modules/metrics-registry.md) and, if a legacy name exists, emits both names.
4. The backend client ([StatsD](../modules/statsd-client.md), [Datadog](../modules/datadog-client.md), [OpenTelemetry](../modules/otel-client.md)) applies [name validation and allow/block lists](../modules/name-validation.md) before emitting.

# Concepts

* [Stats facade](../modules/stats-facade.md)
* [StatsD client](../modules/statsd-client.md)
* [Datadog client](../modules/datadog-client.md)
* [OpenTelemetry client](../modules/otel-client.md)
* [Name validation](../modules/name-validation.md)
* [Metrics registry](../modules/metrics-registry.md)
* [Core adapters](../modules/core-metrics-adapters.md)
* [Task SDK adapters](../modules/task-sdk-metrics-adapters.md)

# Scope note

`airflow/observability/stats.py` and `airflow/sdk/observability/stats.py` sit next to the `metrics/` packages but are outside the requested scope and are not described.
