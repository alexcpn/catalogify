---
type: Module
title: Proxy modes (mode specs and server instances)
description: mitmproxy/proxy/mode_specs.py parses the strings the mode option accepts; mode_servers.py turns each parsed mode into a listening server instance whose top layer depends on the mode.
tags: [proxy, modes, listeners, options]
timestamp: 2025-04-14T15:46:55Z
resource: https://github.com/mitmproxy/mitmproxy/blob/main/mitmproxy/proxy/mode_specs.py
generated_by: catalogify/0.10.1
source_files:
  - mitmproxy/proxy/mode_specs.py
  - mitmproxy/proxy/mode_servers.py
open_questions:
  - "The mode option help says client playback uses the first mode to pick the upstream server. Is that enforced anywhere in the code, or is it a convention only?"
---

# Responsibilities

A proxy mode spec has the form `mode[:data][@[listen_addr:]listen_port]`, for
example `reverse:https://example.com@127.0.0.1:443`. `ProxyMode.parse` turns a
spec into a typed subclass, and each subclass validates its own data.
`ServerInstance` is the server for one parsed mode. Subclasses register
themselves by `type_name` when they are defined, and `ServerInstance.make`
looks them up. Each instance resolves its listen address and port, falling
back to the global `listen_host` and `listen_port` options, and returns a top
layer from `make_top_layer` for the connection handler to run.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `ProxyMode.parse(spec)` | Parse a spec string into the matching mode class; raises `ValueError` on bad input. |
| `RegularMode`, `TransparentMode`, `UpstreamMode`, `ReverseMode`, `Socks5Mode`, `DnsMode`, `WireGuardMode`, `LocalMode`, `TunMode` | One class per mode name. `OsProxyMode` exists for Windows and is marked no-cover. |
| `ServerInstance.make(mode, manager)` | Build the registered instance for a mode, or a `ValueError` if the class is wrong. |
| `ServerInstance.start()` / `to_json()` | Lifecycle and the JSON state the UI displays. |
| `AsyncioServerInstance` | Base for TCP and UDP listeners. |
| `WireGuardServerInstance`, `LocalRedirectorInstance`, `TunInstance` | Non-asyncio-server modes. |
| `RegularInstance`, `UpstreamInstance`, `TransparentInstance`, `ReverseInstance`, `Socks5Instance`, `DnsInstance` | Thin subclasses that choose the top layer. |

# Dependencies

- The `mode`, `listen_host`, `listen_port` and `confdir` options come from [Options](options.md). `mode_servers.py` reads `listen_host`, `listen_port` and `confdir` at runtime from the option store (`ctx.options`), without importing `options.py`.
- `mitmproxy/addons/proxyserver.py` (outside this bundle's scope) owns the lifecycle. On `mode` or `server` changes it parses each spec, checks for listen-address conflicts, and creates or keeps `ServerInstance` objects.
- Top layers come from [Proxy server](proxy-server.md) and `mitmproxy/proxy/layers/modes.py`: `HttpProxy`, `HttpUpstreamProxy`, `TransparentProxy`, `ReverseProxy`, `Socks5Proxy`, `DNSLayer`.
- [Web code generators](web-gen.md) read `ReverseMode` and the syntax-highlight literal from this module.

# Gotchas

- **Port conflicts ignore modes with no port.** Conflict checking skips modes without a `listen_port` (`68c4e9ff`, `#7177`), so a mode that will pick its own port is not treated as a clash.
- **Random ports are chosen for both transports.** Port selection was changed so the chosen port works for TCP and UDP (`60e3044e`, `#7618`).
- **HTTP/3 reverse proxy is part of the reverse mode.** The separate HTTP/3 reverse mode was merged into `reverse` (`499e8e87`, `#7114`).
- **WireGuard config lives under `confdir`.** `WireGuardServerInstance` uses `Path(confdir).expanduser() / "wireguard.conf"`, so changing `confdir` moves that file.

# Citations

- `68c4e9ff` — proxy server: skip modes without listen_port when calculating conflicts (#7177).
- `60e3044e` — Pick random ports that work with both TCP and UDP (#7618).
- `499e8e87` — Merge https and http3 reverse-proxy modes (#7114).
