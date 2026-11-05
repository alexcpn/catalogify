---
type: Module
title: proxy-core (sans-I/O event loop, commands and connection handler)
description: The proxy core runs protocol layers as a stack driven by events, and executes the commands they yield (open connection, send data, run hook, log) in the asyncio connection handler.
resource: https://github.com/mitmproxy/mitmproxy/blob/main/mitmproxy/proxy/server.py
tags: [proxy, event-loop, asyncio, layers, python]
source_files:
  - mitmproxy/proxy/server.py
  - mitmproxy/proxy/layer.py
  - mitmproxy/proxy/events.py
  - mitmproxy/proxy/commands.py
  - mitmproxy/proxy/context.py
timestamp: 2025-08-19T20:15:46+02:00
generated_by: catalogify/0.11.0
open_questions:
  - "Are TCP_TIMEOUT (600 seconds) and UDP_TIMEOUT (20 seconds) hard limits that clients rely on, or defaults chosen for resource use? Nothing in the code or history states which."
  - "Which teams own the proxy core, and who is the escalation path for a deadlock or lost connection in production?"
---

# Responsibilities

The core is sans-I/O. A `Layer` (`layer.py`) receives `events` (`DataReceived`,
`ConnectionClosed`, `CommandCompleted`, `HookCompleted`, `Wakeup`,
`MessageInjected`) and yields `commands` (`OpenConnection`, `SendData`,
`CloseConnection`, `CloseTcpConnection`, `StartHook`, `RequestWakeup`, `Log`).
Layers do not touch sockets. Each layer is pushed on a stack in `Context.layers`,
and a `NextLayer` decides which protocol layer to push next by asking the
`NextLayerHook`.

`ConnectionHandler` in `server.py` is the executor. It runs the top layer for
each event, performs the commands it is given, and feeds the results back.
`handle_client` starts a connection, `open_connection` makes outbound
connections, `handle_connection` pumps reads, `drain_writers` flushes before
close, `on_timeout` closes idle connections through `TimeoutWatchdog`, and
`handle_hook` runs the addon hooks. `LiveConnectionHandler` is the version used
by real servers, and `SimpleConnectionHandler` is a stand-in for tests and
simple uses.

`Context` carries the client and server connections, the option object for
layers (`options`, documented as not for addon use; addons use `ctx.options`),
and the layer stack.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `Layer` | Base protocol layer; implements `handle_event` as a generator of commands. |
| `NextLayer` | Layer that chooses the next protocol from the first bytes; uses `NextLayerHook`. |
| `Event`, `DataReceived`, `ConnectionClosed`, `CommandCompleted`, `HookCompleted`, `Wakeup`, `MessageInjected` | Inputs to layers. |
| `Command`, `OpenConnection`, `SendData`, `CloseConnection`, `CloseTcpConnection`, `StartHook`, `RequestWakeup`, `Log` | Outputs from layers. |
| `Context` | Per-connection state: client, server, options, layer stack. |
| `ConnectionHandler` | Abstract executor for commands; `handle_client`, `open_connection`, `handle_connection`. |
| `LiveConnectionHandler` | Executor used with real sockets. |
| `SimpleConnectionHandler` | Test-oriented executor built from reader and writer. |
| `TimeoutWatchdog` | Closes a connection after a period with no activity. |

# Dependencies

- Internal: [proxy-modes](proxy-modes.md) builds the server instances that
  create `ConnectionHandler` objects. [proxy-layers](proxy-layers.md) provides
  the concrete `Layer` subclasses.
- Internal: options reach the core through `Context.options`; see [options](options.md).
- External: `asyncio`, `mitmproxy_rs` for transport, and the `mitmproxy.hooks`
  base class for `StartHook`.

# Key files

- `mitmproxy/proxy/layer.py` - `Layer.handle_event` and the generator protocol.
- `mitmproxy/proxy/server.py` - `ConnectionHandler`, the command executor.
- `mitmproxy/proxy/commands.py` and `mitmproxy/proxy/events.py` - the vocabulary between layers and the executor.

# Gotchas

- Reentrancy in `server_event` was a real bug: commit `74424df8` guarded it (`#7027`).
  Anything that adds work to a connection's event path needs to be checked
  against this guard.
- Writers must be drained before closing. Commits `b9dc95cb` (race in
  `drain_writers`, `#5749`) and `000e2667` (cancellation errors while draining,
  `#5034`) changed this code. Keep the drain step before close.
- A `server_connected` hook must be awaited before the connection is used.
  Commit `437e55c2` made this change (`#5110`, fixes `#5108`).
- Layers log through the `Log` command. A switch to stdlib logging inside the
  layers was reverted in `0afc48b7`, so the `Log` command is still the path.

# Citations

- `74424df8` - Guard server_event against reentrancy, fix #7027 (#7031).
- `b9dc95cb` - fix a race condition in `ConnectionHandler.drain_writers` (#5749).
- `000e2667` - catch cancellation errors when draining writers, fix #5034 (#5040).
- `437e55c2` - await server_connected hook before doing something with the connection (#5110).
- `0afc48b7` - Revert "use stdlib logging instead of Log command".
