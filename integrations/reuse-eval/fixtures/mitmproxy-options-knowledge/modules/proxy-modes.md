---
type: Module
title: proxy-modes (mode specs and server instances)
description: Parses mode specs such as regular, reverse:URL and socks5@port, and creates the server instance that listens for each mode. The Proxyserver addon keeps one instance per mode in step with options.mode.
resource: https://github.com/mitmproxy/mitmproxy/blob/main/mitmproxy/proxy/mode_specs.py
tags: [proxy, modes, listeners, options, python]
source_files:
  - mitmproxy/proxy/mode_specs.py
  - mitmproxy/proxy/mode_servers.py
timestamp: 2025-04-14T15:46:55Z
generated_by: catalogify/0.11.0
relations:
  - {kind: changes_with, target: mitmproxy/proxy/mode_servers.py, evidence: [1706a9b9, 2b10e3f3, 2d495c09]}
open_questions:
  - "Is the rule that the first mode in options.mode determines the upstream for client playback documented as a promise, or is it an implementation detail of how the first listener is chosen?"
  - "Which modes are supported on which platforms (tun, os proxy, local redirect)? The code guards them with platform checks; no document in scope states the matrix."
---

# Responsibilities

`mode_specs.py` turns a string into a `ProxyMode`. The syntax is
`mode[:configuration][@[listen_addr:]listen_port]`, for example
`reverse:https://example.com@127.0.0.1:443`. Subclasses cover `regular`,
`transparent`, `upstream`, `reverse`, `socks5`, `dns`, `wireguard`, `local`,
`tun` and `osproxy`. Each reports its default port and transport (TCP, UDP or
both), and resolves listen host and port, falling back to the option values.

`mode_servers.py` creates what listens. `ServerInstance.make(mode, manager)`
picks the right subclass (`RegularInstance`, `TransparentInstance`,
`ReverseInstance`, `Socks5Instance`, `DnsInstance`, `WireGuardServerInstance`,
`LocalRedirectorInstance`, `TunInstance`). `AsyncioServerInstance` handles TCP
and UDP servers with `asyncio`; `start`, `stop` and `listen_addrs` manage its
lifecycle. `ProxyConnectionHandler` makes each accepted connection use the
core in [proxy-core](proxy-core.md).

The option-driven part is in `mitmproxy/addons/proxyserver.py`, outside this
concept's files. `Proxyserver.configure` parses each entry of `options.mode`
and fills in `listen_host` and `listen_port`. `Servers.update` then starts
new instances, keeps existing ones and stops the rest. When `options.server`
is false, no instances are created.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `ProxyMode` | Base class for mode specs; `parse` builds one from a string. |
| `ProxyMode.parse` | Parses a mode spec string; raises `ValueError` on malformed input. |
| `ProxyMode.listen_host` | Resolves the listen host from the spec or a default. |
| `ProxyMode.listen_port` | Resolves the listen port from the spec, the default port or a default. |
| `RegularMode`, `TransparentMode`, `UpstreamMode`, `ReverseMode`, `Socks5Mode`, `DnsMode`, `WireGuardMode`, `LocalMode`, `TunMode`, `OsProxyMode` | Concrete mode specs. |
| `ServerInstance` | Base for a running listener; `make`, `start`, `stop`, `listen_addrs`, `to_json`. |
| `AsyncioServerInstance` | TCP and UDP listener built on `asyncio`. |
| `ProxyConnectionHandler` | Connection handler for accepted connections. |

# Dependencies

- Internal: [proxy-core](proxy-core.md) (`ConnectionHandler` base) and
  [proxy-layers](proxy-layers.md) (the top layer each mode creates).
- Internal: [options](options.md) through `options.mode`, `options.listen_host`,
  `options.listen_port` and `options.server`, read by `mitmproxy/addons/proxyserver.py`.
- External: `mitmproxy_rs` for UDP and WireGuard transports, `mitmproxy.net.server_spec`.

# Key files

- `mitmproxy/proxy/mode_specs.py` - the grammar and the subclasses.
- `mitmproxy/proxy/mode_servers.py` - the instance classes.

# Gotchas

- Commit `1706a9b9` (`#5556`) unified the proxy modes and added UDP protocol
  detection. It changed `mitmproxy/proxy/mode_specs.py` and `mode_servers.py`
  together, so a change to one usually needs a change to the other.
- Several modes can run at once (`options.mode` is a list). Commit `83e543c3`
  added this multi-mode support. Each mode gets its own listener, keyed by the
  parsed `ProxyMode`.

# Citations

- `1706a9b9` - Unify proxy modes, introduce UDP protocol detection (#5556).
- `83e543c3` - add multi proxy mode.
