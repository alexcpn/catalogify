# Modules

* [options](options.md) - Declaration of the core option set (`mitmproxy/options.py`).
* [optmanager](optmanager.md) - Option value engine: typing, transactions, `--set`, config files, CLI parsers (`mitmproxy/optmanager.py`).
* [cli-tools](cli-tools.md) - Command-line parsers and entry points for mitmproxy, mitmdump and mitmweb (`mitmproxy/tools/cmdline.py`, `mitmproxy/tools/main.py`).
* [console-options](console-options.md) - The options editor in the terminal UI (`mitmproxy/tools/console/options.py`).
* [web-ui](web-ui.md) - Web UI master, `/options` API and mitmweb's own options (`mitmproxy/tools/web/`).
* [web-gen](web-gen.md) - Code generators in `web/gen/`, including the TypeScript option types.
* [proxy-core](proxy-core.md) - Sans-I/O proxy event loop: layers, events, commands and the connection handler (`mitmproxy/proxy/`).
* [proxy-modes](proxy-modes.md) - Proxy mode specs and the server instances that listen for each mode.
* [proxy-layers](proxy-layers.md) - Protocol layers for modes, TLS and HTTP.
