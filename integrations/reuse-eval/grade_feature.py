#!/usr/bin/env python3
"""Behavioural checks for the `[metrics] statsd_socket_path` feature (apache/airflow#70666).

Checks go through the public no-argument wrappers in airflow-core and task-sdk,
with config set by environment variables, so any reasonable internal design
passes. Each check runs in a fresh interpreter. Prints a JSON report.

    grade_feature.py <python with editable airflow-core, task-sdk, statsd and datadog>
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

SOCKET = "/tmp/reuse-eval-statsd.sock"

STATSD_SOCKET = """
from unittest import mock
import statsd
with mock.patch.object(statsd.UnixSocketStatsClient, "__init__", return_value=None) as init:
    from {mod} import statsd_logger
    logger = statsd_logger.get_statsd_logger()
client = getattr(logger, "statsd", None)
assert isinstance(client, statsd.UnixSocketStatsClient), f"client is {{type(client).__name__}}"
call = init.call_args
path = call.kwargs.get("socket_path", call.args[0] if call.args else None)
assert path == {socket!r}, f"socket_path={{path!r}}"
"""

STATSD_UDP_UNCHANGED = """
from unittest import mock
import statsd
with mock.patch.object(statsd.StatsClient, "__init__", return_value=None) as init:
    from {mod} import statsd_logger
    logger = statsd_logger.get_statsd_logger()
client = getattr(logger, "statsd", None)
assert type(client) is statsd.StatsClient, f"client is {{type(client).__name__}}"
assert init.call_args.kwargs.get("host") == "localhost", init.call_args
assert init.call_args.kwargs.get("port") == 8125, init.call_args
"""

DATADOG_SOCKET = """
from unittest import mock
with mock.patch("datadog.DogStatsd") as dog:
    from {mod} import datadog_logger
    datadog_logger.get_dogstatsd_logger()
kwargs = dog.call_args.kwargs
# DogStatsd uses socket_path over host/port when both are given, so host and
# port may still be passed (upstream's own implementation does).
assert kwargs.get("socket_path") == {socket!r}, kwargs
"""

COMPONENTS = {
    "core": "airflow.observability.metrics",
    "sdk": "airflow.sdk.observability.metrics",
}


def check(python: str, code: str, socket: bool) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as home:
        env = {k: v for k, v in os.environ.items() if not k.startswith("AIRFLOW")}
        env.update({"AIRFLOW_HOME": home, "AIRFLOW__METRICS__STATSD_ON": "True"})
        if socket:
            env["AIRFLOW__METRICS__STATSD_SOCKET_PATH"] = SOCKET
        proc = subprocess.run([python, "-c", code], cwd=home, env=env,
                              capture_output=True, text=True, timeout=300)
    if proc.returncode == 0:
        return True, "ok"
    lines = [line for line in (proc.stderr or proc.stdout).strip().splitlines() if line.strip()]
    return False, lines[-1][:240] if lines else f"exit {proc.returncode}"


def main() -> None:
    python = sys.argv[1]
    results = {}
    for name, mod in COMPONENTS.items():
        for label, template, socket in (
            ("statsd_socket", STATSD_SOCKET, True),
            ("statsd_udp_unchanged", STATSD_UDP_UNCHANGED, False),
            ("datadog_socket", DATADOG_SOCKET, True),
        ):
            ok, why = check(python, template.format(mod=mod, socket=SOCKET), socket)
            results[f"{name}_{label}"] = {"pass": ok, "detail": why}
    passed = sum(r["pass"] for r in results.values())
    print(json.dumps({"passed": passed, "total": len(results), "checks": results}, indent=2))


if __name__ == "__main__":
    main()
