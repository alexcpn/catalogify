#!/usr/bin/env python3
"""Custom grader for the catalogify SkillEvaluator cases (grading mode default_plus_custom).

Runs inside the task container after the agent finishes. It reads the case id
from the Harbor entry JSON and writes custom metrics (each 0.0-1.0) to the
Harbor reward files. Standard SkillEvaluator grading runs alongside it.

Cases:
  airflow-metrics-bundle-*   the agent was asked for a knowledge bundle; checked
                             with catalogify's own validate and verify commands
  airflow-uds-feature-*      the agent implemented Airflow PR #70517; checked
                             against the upstream tests from the merge commit,
                             fetched only now so the agent never saw them
  airflow-negative-*         the agent should answer without writing anything

Paths and tools can be overridden for a local dry run:
  CATALOGIFY_EVAL_REPO     Airflow checkout          (default /workspace/airflow)
  CATALOGIFY_EVAL_PYTHON   Python with test deps     (default /opt/afvenv/bin/python)
  CATALOGIFY_EVAL_CLI      catalogify command        (default "uvx catalogify@0.10.1")
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ENTRY = Path(os.environ.get("HARBOR_ENTRY_JSON", "/tests/entry.json"))
REWARD_JSON = Path(os.environ.get("HARBOR_REWARD_JSON", "/logs/verifier/reward.json"))
REWARD_TXT = Path(os.environ.get("HARBOR_REWARD_TXT", "/logs/verifier/reward.txt"))
REPO = Path(os.environ.get("CATALOGIFY_EVAL_REPO", "/workspace/airflow"))
PYTHON = os.environ.get("CATALOGIFY_EVAL_PYTHON", "/opt/afvenv/bin/python")
CLI = shlex.split(os.environ.get("CATALOGIFY_EVAL_CLI", "uvx catalogify@0.10.1"))

BASE_SHA = "f44bb16d825edcb533b5819c152c4d6a23a0ffd9"  # parent of the feature, what the agent starts from
UPSTREAM_SHA = "b03e48a875d991ad42b9d81efb7e75e001879404"  # apache/airflow#70517 merged

BUNDLE = "knowledge"
METRICS_COPIES = [
    "airflow-core/src/airflow/observability/metrics/statsd_logger.py",
    "shared/observability/src/airflow_shared/observability/metrics/statsd_logger.py",
    "task-sdk/src/airflow/sdk/observability/metrics/statsd_logger.py",
]

# Upstream tests from the merge commit, run against the agent's code. "fixed" are
# the tests that fail on BASE_SHA and pass on UPSTREAM_SHA; every other test in
# these files passes on both, so a failure there is a regression.
UPSTREAM_TESTS = {
    "shared/observability": "tests/observability/metrics/test_stats.py",
    "airflow-core": "tests/unit/observability/metrics/test_stats.py",
}
FIXED = {
    "shared/observability": {
        "TestGetStatsdLogger::test_passes_ipv6_as_keyword",
        "TestGetStatsdLogger::test_socket_path_constructs_stats_class_with_socket_path",
        "TestGetStatsdLogger::test_no_stats_class_with_socket_path_uses_unix_client",
        "TestGetStatsdLogger::test_no_stats_class_without_socket_path_uses_stats_client",
        "TestStats::test_enabled_by_config",
        "TestStats::test_load_custom_statsd_client",
        "TestStats::test_load_allow_list_validator",
        "TestStats::test_load_block_list_validator",
        "TestStats::test_load_allow_and_block_list_validator_loads_only_allow_list_validator",
        "TestPatternValidatorConfigOption::test_pattern_picker[pattern_allow_by_default]",
        "TestPatternValidatorConfigOption::test_pattern_picker[pattern_allow_list_provided]",
        "TestPatternValidatorConfigOption::test_pattern_picker[pattern_block_list_provided]",
        "TestPatternValidatorConfigOption::test_pattern_picker[pattern_both_lists_provided]",
        "TestPatternValidatorConfigOption::test_setting_allow_and_block_logs_warning",
        "TestCustomStatsName::test_does_not_send_stats_using_statsd_when_the_name_is_not_valid",
        "TestCustomStatsName::test_dogstatsd_socket_path_passed_and_host_port_omitted",
        "TestCustomStatsName::test_does_send_stats_using_statsd_when_the_name_is_valid",
    },
    "airflow-core": {
        "TestStats::test_load_invalid_custom_stats_client[socket]",
    },
}


def run(cmd: list[str], cwd: Path, timeout: int = 900, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, **(env or {})})


def git(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return run(["git", *args], REPO, timeout=600, env=env)


def changed_paths() -> list[str]:
    """Files the agent changed or added relative to the starting commit."""
    out = git("status", "--porcelain", "--untracked-files=all").stdout
    return [line[3:].split(" -> ")[-1] for line in out.splitlines() if line.strip()]


# ---------------------------------------------------------------- bundle cases

def catalogify_json(*args: str) -> dict | None:
    proc = run([*CLI, *args, "--json"], REPO, timeout=900)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def grade_bundle() -> tuple[dict, dict]:
    metrics: dict[str, float] = {}
    details: dict[str, dict] = {}
    index = REPO / BUNDLE / "index.md"
    present = index.is_file() and "okf_version" in index.read_text(errors="replace")
    metrics["bundle_present"] = 1.0 if present else 0.0
    details["bundle_present"] = {"score": metrics["bundle_present"], "reason": f"{BUNDLE}/index.md with okf_version"}
    if not present:
        for name in ("bundle_validates", "bundle_verifies", "bundle_covers_metrics_copies"):
            metrics[name] = 0.0
            details[name] = {"score": 0.0, "reason": "no bundle"}
        return metrics, details

    val = catalogify_json("validate", BUNDLE)
    ok = val is not None and not val.get("errors")
    metrics["bundle_validates"] = 1.0 if ok else 0.0
    details["bundle_validates"] = {"score": metrics["bundle_validates"],
                                   "reason": "no validate errors" if ok else f"errors: {(val or {}).get('errors', 'no JSON')!s:.400}"}

    ver = catalogify_json("verify", BUNDLE)
    if ver is None or not ver.get("concepts"):
        score, reason = 0.0, "verify produced no result or no concepts"
    else:
        n, bad = ver["concepts"], len(ver.get("findings", []))
        score, reason = max(0.0, 1.0 - bad / n), f"{bad} findings across {n} concepts"
    metrics["bundle_verifies"] = score
    details["bundle_verifies"] = {"score": score, "reason": reason}

    # The metrics client exists in three places that must change together.
    # A bundle that lists only one of them misses the coupling a reader needs.
    text = "\n".join(p.read_text(errors="replace") for p in (REPO / BUNDLE).rglob("*.md"))
    hits = [c for c in METRICS_COPIES if c in text]
    metrics["bundle_covers_metrics_copies"] = len(hits) / len(METRICS_COPIES)
    details["bundle_covers_metrics_copies"] = {"score": metrics["bundle_covers_metrics_copies"],
                                               "reason": f"cites {len(hits)}/3 statsd_logger.py copies"}
    return metrics, details


# --------------------------------------------------------------- feature case

def run_upstream_tests(dist: str, test: str) -> dict[str, str]:
    """Run one upstream test file in place; return {test id: outcome}."""
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / "junit.xml"
        run([PYTHON, "-m", "pytest", "-q", "-p", "no:cacheprovider", test, f"--junitxml={xml}"],
            REPO / dist, timeout=900, env={"AIRFLOW_HOME": tmp})
        if not xml.is_file():
            return {}
        results = {}
        for case in ET.parse(xml).getroot().iter("testcase"):
            name = f"{case.get('classname', '').split('.')[-1]}::{case.get('name')}"
            failed = any(child.tag in ("failure", "error") for child in case)
            skipped = any(child.tag == "skipped" for child in case)
            results[name] = "failed" if failed else "skipped" if skipped else "passed"
        return results


def grade_feature() -> tuple[dict, dict]:
    metrics: dict[str, float] = {}
    details: dict[str, dict] = {}

    # The merge commit must not be in the repository before we fetch it: if it
    # is, the agent fetched upstream and may have copied the real change. The
    # checkout is a partial clone, so without GIT_NO_LAZY_FETCH this very check
    # would download the commit from the promisor remote and always see it.
    seen = git("cat-file", "-e", f"{UPSTREAM_SHA}^{{commit}}",
               env={"GIT_NO_LAZY_FETCH": "1"}).returncode == 0
    metrics["upstream_fix_not_fetched"] = 0.0 if seen else 1.0
    details["upstream_fix_not_fetched"] = {"score": metrics["upstream_fix_not_fetched"],
                                           "reason": "agent fetched the upstream fix" if seen else "clean"}

    sdk = [
        "task-sdk/src/airflow/sdk/observability/metrics/statsd_logger.py",
        "task-sdk/src/airflow/sdk/observability/metrics/datadog_logger.py",
    ]
    reads = [p for p in sdk if "statsd_socket_path" in (REPO / p).read_text(errors="replace")]
    metrics["task_sdk_reads_socket_path"] = len(reads) / len(sdk)
    details["task_sdk_reads_socket_path"] = {"score": metrics["task_sdk_reads_socket_path"],
                                             "reason": f"{len(reads)}/2 task-sdk metrics clients read the new option"}

    cfg = (REPO / "airflow-core/src/airflow/config_templates/config.yml").read_text(errors="replace")
    declared = re.search(r"^\s{4}statsd_socket_path:\s*$", cfg, re.M) is not None
    metrics["config_option_declared"] = 1.0 if declared else 0.0
    details["config_option_declared"] = {"score": metrics["config_option_declared"],
                                         "reason": "[metrics] statsd_socket_path in config.yml" if declared else "missing"}

    fetch = git("fetch", "-q", "--filter=blob:none", "origin", UPSTREAM_SHA)
    if fetch.returncode != 0:
        for name in ("upstream_tests_fixed", "upstream_tests_no_regressions"):
            metrics[name] = 0.0
            details[name] = {"score": 0.0, "reason": f"could not fetch upstream tests: {fetch.stderr[-300:]}"}
        return metrics, details

    fixed_pass = fixed_total = other_pass = other_total = 0
    notes = []
    for dist, test in UPSTREAM_TESTS.items():
        path = REPO / dist / test
        path.write_text(git("show", f"{UPSTREAM_SHA}:{dist}/{test}").stdout)
        outcomes = run_upstream_tests(dist, test)
        if not outcomes:
            notes.append(f"{dist}: test run produced no results")
        for name in FIXED[dist]:
            fixed_total += 1
            fixed_pass += outcomes.get(name) == "passed"
        for name, outcome in outcomes.items():
            if name in FIXED[dist] or outcome == "skipped":
                continue
            other_total += 1
            other_pass += outcome == "passed"
        git("checkout", "-q", "--", f"{dist}/{test}")  # leave the agent's tree as it was

    metrics["upstream_tests_fixed"] = fixed_pass / fixed_total
    details["upstream_tests_fixed"] = {"score": metrics["upstream_tests_fixed"],
                                       "reason": f"{fixed_pass}/{fixed_total} upstream tests for the feature pass {'; '.join(notes)}"}
    metrics["upstream_tests_no_regressions"] = other_pass / other_total if other_total else 0.0
    details["upstream_tests_no_regressions"] = {"score": metrics["upstream_tests_no_regressions"],
                                                "reason": f"{other_pass}/{other_total} existing tests still pass"}
    return metrics, details


# -------------------------------------------------------------- negative case

def grade_negative() -> tuple[dict, dict]:
    changed = changed_paths()
    bundle = any(p.startswith(f"{BUNDLE}/") for p in changed)
    metrics = {"no_bundle_written": 0.0 if bundle else 1.0,
               "no_files_changed": 0.0 if changed else 1.0}
    details = {"no_bundle_written": {"score": metrics["no_bundle_written"], "reason": "wrote a bundle" if bundle else "clean"},
               "no_files_changed": {"score": metrics["no_files_changed"], "reason": f"changed: {changed[:10]}" if changed else "clean"}}
    return metrics, details


def main() -> None:
    entry = json.loads(ENTRY.read_text()) if ENTRY.is_file() else {}
    case = str(entry.get("id", ""))
    try:
        if case.startswith("airflow-metrics-bundle"):
            metrics, details = grade_bundle()
        elif case.startswith("airflow-uds-feature"):
            metrics, details = grade_feature()
        elif case.startswith("airflow-negative"):
            metrics, details = grade_negative()
        else:
            metrics, details = {}, {}
    except Exception as exc:  # a grader crash must still leave a well-formed reward
        metrics, details = {"grader_completed": 0.0}, {"grader_completed": {"score": 0.0, "reason": repr(exc)[:400]}}
    overall = sum(metrics.values()) / len(metrics) if metrics else 0.0
    REWARD_JSON.parent.mkdir(parents=True, exist_ok=True)
    REWARD_JSON.write_text(json.dumps({"overall": round(overall, 4), "custom_metrics": metrics,
                                       "details": details}, indent=2) + "\n")
    REWARD_TXT.write_text(f"{overall:.4f}\n")
    print(json.dumps({"case": case, "overall": round(overall, 4), "custom_metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
