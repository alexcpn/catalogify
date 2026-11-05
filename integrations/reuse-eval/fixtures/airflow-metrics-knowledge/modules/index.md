# Modules

* [Stats facade](stats-facade.md) - Singleton facade that lazily builds a backend and dual-emits legacy metric names.
* [StatsD client](statsd-client.md) - SafeStatsdLogger wrapping pystatsd.
* [Datadog client](datadog-client.md) - SafeDogStatsdLogger wrapping DogStatsd.
* [OpenTelemetry client](otel-client.md) - SafeOtelLogger and MeterProvider setup.
* [Name validation and metric filtering](name-validation.md) - Name checks and allow/block lists.
* [Metrics registry](metrics-registry.md) - YAML metric catalogue and docs generator.
* [Core adapters](core-metrics-adapters.md) - airflow-core config-driven factories.
* [Task SDK adapters](task-sdk-metrics-adapters.md) - task-sdk config-driven factories.
