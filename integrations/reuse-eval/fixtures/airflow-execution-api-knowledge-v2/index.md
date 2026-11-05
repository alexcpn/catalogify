---
okf_version: "0.1"
---

# Execution API and Task SDK runtime

# Architecture

* [Overview](architecture/overview.md) - How a task instance is run by the Task SDK supervisor and task process, and how both talk to the Execution API served by the API server.

# Services

* [Execution API service](services/execution-api.md) - The private FastAPI/Cadwyn application that workers and the Dag processor use to read and update task instance state, XComs, connections and variables.
* [Task SDK runtime (supervisor and task process)](services/task-sdk-runtime.md) - The worker-side pair of processes that run one task instance.

# Modules

* [Execution API security (JWT and token scopes)](modules/execution-api-security.md) - JWT validation, token-type scopes (execution, workload) and the ti:self check that binds a request to one task instance.
* [Execution API versioning (Cadwyn version bundle)](modules/execution-api-versioning.md) - How the Execution API's CalVer versions and VersionChange migrations are declared, and the rules for adding to unreleased versus released version files.
* [Task SDK Execution API client and generated models](modules/sdk-api-client.md) - The httpx-based client the supervisor uses to call the Execution API, and the datamodels generated from the server's OpenAPI schema.
* [Task SDK comms protocol (task process ↔ supervisor)](modules/sdk-comms.md) - The length-prefixed msgpack request/response protocol between the task process and its supervisor.
* [Task SDK supervisor](modules/sdk-supervisor.md) - The worker-side parent process that forks or execs the task process, owns the Execution API connection and heartbeats, forwards logs and signals, and reports the final state.
* [Task SDK task runner (task process)](modules/sdk-task-runner.md) - The child-side code that runs user operator code for one task instance and reports XComs and state.
* [Task SDK secrets backend that calls the Execution API](modules/sdk-secrets-execution-api.md) - The secrets backend a worker uses to fetch connections and variables, and the rule that an authorization denial must not fall through.
* [Task SDK supervisor schema versioning and migration](modules/sdk-schema-versioning.md) - The second Cadwyn version bundle, for wire shapes exchanged with non-Python runtimes.

# APIs

* [Execution API routes](apis/execution-api-routes.md) - The routers mounted under /execution and the auth each one requires.

# Data

* [Execution API datamodels](data/execution-api-datamodels.md) - Request and response models: TI state payloads, run context, and JWT claim models.

# Operations

* [playbooks/](operations/playbooks/) - Ordered change procedures mined from co-change.
* [guardrails/](operations/guardrails/) - Rules that must not be broken.
