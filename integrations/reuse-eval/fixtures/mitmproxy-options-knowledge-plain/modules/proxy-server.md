---
type: Module
title: Proxy server (connection handling core)
description: mitmproxy/proxy/server.py drives each accepted connection through the layer stack, using the shared Options object through Context; layer.py defines the command protocol the layers speak.
tags: [proxy, connections, layers, concurrency]
timestamp: 2025-08-19T20:15:46+02:00
resource: https://github.com/mitmproxy/mitmproxy/blob/main/mitmproxy/proxy/server.py
generated_by: catalogify/0.10.1
source_files:
  - mitmproxy/proxy/server.py
  - mitmproxy/proxy/context.py
  - mitmproxy/proxy/layer.py
open_questions:
  - "Context.fork shares the same Options object rather than a snapshot. Should a change made from the UI or CLI mid-connection apply to in-flight connections, or only to new ones? Which layers are expected to re-read options per event?"
  - "TimeoutWatchdog decides when an idle connection is closed. Is the timeout a hard guarantee to users, or an internal default that can change?"
---

# Responsibilities

`ConnectionHandler` owns one accepted client connection. It runs the top layer
from a mode (see [Proxy modes](proxy-modes.md)), executes the commands each
layer yields (open a connection, wake up, call a hook, log), dispatches
server-side events back into the layer stack, and closes connections. Layers
do not do I/O directly. They yield commands, and the handler performs them.
`Context` carries the client, the server, the `Options` object and the stack of
layers. `Layer` is the base class of every protocol layer, and `NextLayer`
chooses the next layer by asking a hook, which is how addons pick protocols.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `ConnectionHandler.handle_client()` | Main loop for one client connection. |
| `ConnectionHandler.open_connection(command)` | Perform an `OpenConnection` command. |
| `ConnectionHandler.handle_connection(connection)` | Pump reads and writes on one connection. |
| `ConnectionHandler.handle_hook(hook)` / `server_event(event)` | Run a hook; deliver an event into the layer stack. |
| `ConnectionHandler.drain_writers()` / `close_connection()` | Flush and close writers. |
| `LiveConnectionHandler(reader, writer, options, mode, hook_handlers)` | Handler for real sockets; takes the `Options` object. |
| `TimeoutWatchdog(timeout, callback)` | Calls `callback` after the connection has been idle for `timeout` seconds. |
| `Context(client, options)` / `Context.fork()` | Per-connection state; `fork` copies the layer list and shares `options`. |
| `Layer.handle_event(event)` | Generator-based protocol step; yields commands. |
| `NextLayer` / `NextLayerHook` | Ask which layer comes next, through a hook. |

# Dependencies

- Reads options from `Context.options`: `connection_strategy`, `keep_host_header`, `store_streamed_bodies` in `layers/http`, `http2_ping_keepalive` and the header validation flags in `layers/http/_http2.py`, `http3` in `layers/quic/_stream_layers.py`, `http_connect_send_host_header` in `layers/http/_upstream_proxy.py`. See [Options](options.md) for the core declarations; several of these are declared by addons.
- Created by [Proxy modes](proxy-modes.md) `ServerInstance` subclasses, which pick the top layer.
- [OptManager](optmanager.md) supplies the `Options` object and its `changed` signal; this module does not subscribe to it itself.

# Gotchas

- **Writes to closing streams were a contested change.** `a1ddbcad` stopped writing to streams that were closing (`#5363`, `#5589`). It was reverted (`ec5a74cd`) and then the revert was reverted (`db9b3c21`), so the behaviour went back and forth. Changes in this area need the closing-connection tests to pass.
- **Draining writers races.** A race in `ConnectionHandler.drain_writers` was fixed in `b9dc95cb`, and cancellation errors raised while draining are caught (`000e2667`, `#5034`).
- **Server events are reentrancy-guarded.** `server_event` has a reentrancy guard (`74424df8`, `#7027`). The commit title is the only evidence recorded here for why.
- **Async `client_connected` handlers.** A crash caused by async `client_connected` handlers was fixed in `d4200a7c` (`#6749`).
- **Per-connection state.** Commit `5ec4bbf4` ("don't persist connection state", fixes `#5524`) changed what survives between connections; the body of that commit was not read.

# Citations

- `a1ddbcad` — Don't write to closing streams, fix #5363 (#5589); reverted by `ec5a74cd`, re-applied by `db9b3c21`.
- `b9dc95cb` — fix a race condition in `ConnectionHandler.drain_writers` (#5749).
- `000e2667` — catch cancellation errors when draining writers, fix #5034 (#5040).
- `74424df8` — Guard server_event against reentrancy, fix #7027 (#7031).
- `d4200a7c` — Fix async `client_connected` handlers crashing mitmproxy (#6749).
- `5ec4bbf4` — don't persist connection state, fix #5524.
