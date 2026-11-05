---
type: Reference
title: mitmproxy options and proxy core - overview
description: Start here. How mitmproxy declares and manages options, exposes them on the command line and in the web UI, and feeds them to the proxy server.
tags: [architecture, options, proxy, overview]
timestamp: 2025-08-19T23:04:34+02:00
generated_by: catalogify/0.11.0
---

# Purpose

mitmproxy is configured through one option registry. Options are declared
once and then reached from four directions:

1. **Declaration** - `Options` in `mitmproxy/options.py` declares the core
   options. Addons declare more at load time through `Loader.add_option`
   (`mitmproxy/addonmanager.py`), which forwards to the same registry.
2. **Management** - `OptManager` in `mitmproxy/optmanager.py` holds values,
   validates types, applies updates transactionally, parses `--set` and config
   files, and notifies subscribers.
3. **Exposure** - the CLI (`mitmproxy/tools/cmdline.py`, `mitmproxy/tools/main.py`),
   the console options editor (`mitmproxy/tools/console/options.py`) and the web
   UI (`mitmproxy/tools/web/`, which serves `/options` and pushes `options/update`).
4. **Consumption** - the proxy core (`mitmproxy/proxy/`) and the addons that
   start proxy servers (`mitmproxy/addons/proxyserver.py`) read the options
   and turn `mode` specs into running servers.

# Layout

| Area | Concept |
| --- | --- |
| Option declarations | [options](../modules/options.md) |
| Value engine, `--set`, config files | [optmanager](../modules/optmanager.md) |
| CLI parsers and entry points | [cli-tools](../modules/cli-tools.md) |
| Console options editor | [console-options](../modules/console-options.md) |
| Web UI API and mitmweb options | [web-ui](../modules/web-ui.md) |
| Generated TypeScript option types | [web-gen](../modules/web-gen.md) |
| Proxy event loop and commands | [proxy-core](../modules/proxy-core.md) |
| Proxy mode specs and listeners | [proxy-modes](../modules/proxy-modes.md) |
| Protocol layers (HTTP, TLS, modes) | [proxy-layers](../modules/proxy-layers.md) |

# How the pieces connect

- Every option is an `_Option` with a type, default, help text and optional
  choices. Reads return deep copies; writes go through `OptManager.update`,
  which rolls back and re-raises on `OptionsError`.
- `make_parser` turns each option into an argparse flag. Booleans get a
  `--x` / `--no-x` pair; `Sequence[str]` options are repeatable.
- The web UI and the console both subscribe to `options.changed`, so a change
  made in one front end is visible in the other.
- The proxy server does not read the option registry directly for listener
  setup; `Proxyserver.configure` parses `options.mode` into `ProxyMode`
  objects and `Servers.update` starts, keeps or stops one `ServerInstance` per mode.
- Protocol layers receive the options through their `Context`. Their decisions
  (for example HTTP/2 CONNECT, inbound header validation) are driven by option values.

# Operations

- [Add a new option](../operations/playbooks/add-option.md) - the checklist
  for declaring an option and keeping the web UI types in sync.
- [HTTP smuggling guardrail](../operations/guardrails/http-smuggling-hard-fail.md) -
  inbound header validation must stay on by default.

# Start points for reading code

- `mitmproxy/optmanager.py` - `OptManager.update`, `set`, `make_parser`, `load_paths`.
- `mitmproxy/tools/main.py` - `run()` shows the order: master first (addons
  declare options), then parser, then `--set`, config files, and CLI values.
- `mitmproxy/proxy/server.py` - `ConnectionHandler`, the executor for proxy commands.
- `mitmproxy/proxy/layer.py` - `Layer.handle_event`, the sans-I/O layer protocol.
