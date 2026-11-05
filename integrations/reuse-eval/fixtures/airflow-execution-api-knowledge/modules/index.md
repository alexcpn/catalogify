# Modules

* [Execution API security and token scopes](execution-api-security.md) - JWT validation, token types and task-instance identity checks.
* [Execution API versioning (Cadwyn)](execution-api-versioning.md) - Dated version bundles and compatibility rules for the HTTP contract.
* [Task SDK Execution API client](task-sdk-api-client.md) - The httpx client and generated models used for all worker calls to the Execution API.
* [Task SDK comms](task-sdk-comms.md) - The msgpack socket protocol between the task process and its supervisor.
* [Task SDK supervisor](task-sdk-supervisor.md) - The parent process that runs, watches and reports on a task attempt, callback or connection test.
* [Task SDK task runner](task-sdk-task-runner.md) - The child-side runtime that builds the context and executes the operator.
* [Task SDK supervisor schema versioning](task-sdk-schema-versioning.md) - The separately versioned lang-SDK message contract and `schema.json`.
