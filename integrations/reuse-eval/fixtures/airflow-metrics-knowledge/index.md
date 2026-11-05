---
okf_version: "0.1"
---

# Architecture

* [Metrics clients architecture](architecture/overview.md) - How Airflow's StatsD, Datadog and OpenTelemetry metrics clients are layered across shared, airflow-core and task-sdk.

# Modules

* [Stats facade](modules/stats-facade.md) - Process-wide singleton facade (incr/decr/gauge/timing/timer) that lazily builds a backend and dual-emits legacy metric names.
* [StatsD client](modules/statsd-client.md) - SafeStatsdLogger wraps pystatsd with name validation, allow/block lists and optional InfluxDB-style tags.
* [Datadog client](modules/datadog-client.md) - SafeDogStatsdLogger wraps DogStatsd, emitting native tags and honoring the shared validators.
* [OpenTelemetry client](modules/otel-client.md) - SafeOtelLogger maps Airflow counters, gauges and timers onto OpenTelemetry instruments and builds the MeterProvider.
* [Name validation and metric filtering](modules/name-validation.md) - Stat-name validation, OpenTelemetry length rules and the allow/block list validators shared by all backends.
* [Metrics registry](modules/metrics-registry.md) - YAML catalogue of every Airflow metric with its legacy name and name variables, plus the RST docs generator.
* [Core adapters](modules/core-metrics-adapters.md) - Config-driven factories in airflow-core that pick and build the backend from the [metrics] section.
* [Task SDK adapters](modules/task-sdk-metrics-adapters.md) - Config-driven factories in task-sdk that pick and build the backend from the [metrics] section.
