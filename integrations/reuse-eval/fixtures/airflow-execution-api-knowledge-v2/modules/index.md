# Modules

* [Execution API security (JWT and token scopes)](execution-api-security.md) - JWT validation, token-type scopes and the ti:self check.
* [Execution API versioning (Cadwyn version bundle)](execution-api-versioning.md) - CalVer versions and VersionChange migrations.
* [Task SDK Execution API client and generated models](sdk-api-client.md) - The httpx client and the datamodels generated from the server's OpenAPI schema.
* [Task SDK comms protocol](sdk-comms.md) - Length-prefixed msgpack protocol between the task process and its supervisor.
* [Task SDK supervisor](sdk-supervisor.md) - Parent process that owns the API connection, heartbeats, logs and signals.
* [Task SDK task runner](sdk-task-runner.md) - Child-side code that runs operator code and reports outcomes.
* [Task SDK secrets backend](sdk-secrets-execution-api.md) - Secrets backend that fetches connections and variables via the Execution API.
* [Task SDK schema versioning](sdk-schema-versioning.md) - Second Cadwyn bundle for lang-SDK runtime wire shapes.
