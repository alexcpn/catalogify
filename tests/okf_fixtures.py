"""Tiny, deterministic git repositories for the CLI tests, and a runner that
captures every command's output in a form that can be compared across versions.

Commits use fixed author, committer and dates, so their SHAs are the same on
every machine. That is what lets `golden/` hold real 0.9.2 output.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "src" / "catalogify" / "_scripts"

# Keys added to the inventory in 0.10.0. T1 compares everything else.
NEW_INVENTORY_KEYS = ("agent_docs", "guidance", "bundle")
NEW_SUMMARY_PREFIXES = ("  agent docs:", "  guidance:")


def git_env():
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("GIT_") or k.startswith("OKF_"):
            del env[k]
    env.update({
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.com",
        "GIT_COMMITTER_NAME": "Fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.com",
    })
    return env


class Repo:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._n = 0
        self.git("init", "-q", "-b", "main")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, env=self._env(),
                              check=True, capture_output=True, text=True).stdout.strip()

    def _env(self):
        env = git_env()
        date = f"2026-01-{1 + self._n:02d}T12:00:00+00:00"
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
        return env

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def commit(self, msg, *paths):
        self.git("add", *(paths or ["-A"]))
        self.git("commit", "-q", "-m", msg)
        self._n += 1
        return self.git("rev-parse", "--short=12", "HEAD")


def build_sample(root: Path, bundle_dir="knowledge", config=None) -> Repo:
    """A small service with a conformant, verifiable bundle."""
    r = Repo(root)
    if config is not None:
        r.write(".okf-config.yml", config)
    r.write("README.md", "# Sample\n\nA tiny service.\n")
    r.write("Dockerfile", "FROM python:3.12-slim\n")
    r.write("app/__init__.py", "")
    r.write("app/main.py", "def serve(port):\n    return port\n\n\nclass Server:\n    pass\n")
    r.write("app/models.py", "class Order:\n    pass\n")
    r.commit("Add service skeleton")
    r.write("app/main.py",
            "import threading\n\n_lock = threading.Lock()\n\n\n"
            "def serve(port):\n    with _lock:\n        return port\n\n\nclass Server:\n    pass\n")
    fix = r.commit("Fix race in serve when two listeners start")

    b = bundle_dir
    r.write(f"{b}/index.md", '---\nokf_version: "0.1"\n---\n\n# Modules\n\n'
            "* [App](modules/app.md) - The HTTP entry point.\n")
    r.write(f"{b}/README.md", "# Knowledge\n\nGenerated. Start at [index](index.md).\n")
    r.write(f"{b}/modules/index.md", "# Modules\n\n* [App](app.md) - The HTTP entry point.\n")
    r.write(f"{b}/modules/app.md", f"""---
type: Module
title: App
description: The HTTP entry point.
source_files:
  - app/main.py
generated_by: catalogify/0.9.2
---

# Responsibilities

Starts the server.

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `serve(port)` | Starts listening. |
| `Server` | Server object. |

# Gotchas

Listener start is serialised by a lock (`{fix}`).
""")
    r.write(f"{b}/log.md", f"# Knowledge Bundle Update Log\n\n## 2026-01-03\nCommit: `{fix}`\n"
            "* **Initialization**: Generated bundle.\n")
    r.commit("Add knowledge bundle")
    return r


def run(cmd, cwd, env=None):
    p = subprocess.run(cmd, cwd=cwd, env=env or git_env(), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def inventory(repo_root: Path, out: Path, scripts=SCRIPTS, config=None):
    cmd = ["bash", str(scripts / "okf-inventory.sh"), str(out)]
    if config:
        cmd += ["--config", str(config)]
    code, stdout, stderr = run(cmd, repo_root)
    assert code == 0, stderr
    return json.loads(out.read_text()), stdout


def validate(bundle: Path, scripts=SCRIPTS, json_out=False, config=None):
    cmd = [sys.executable, str(scripts / "validate_okf.py"), str(bundle)]
    if config:
        cmd += ["--config", str(config)]
    if json_out:
        cmd.append("--json")
    return run(cmd, bundle)


def verify(bundle: Path, scripts=SCRIPTS, json_out=False):
    cmd = [sys.executable, str(scripts / "verify_okf.py"), str(bundle)]
    if json_out:
        cmd.append("--json")
    return run(cmd, bundle)


def snapshot(repo_root: Path, bundle: Path, out: Path, scripts=SCRIPTS, config=None) -> dict:
    """Every command's output, with paths that vary per run normalised and the
    0.10.0 additions removed, so 0.9.2 and later output can be compared."""
    def norm(s):
        return s.replace(str(out), "<OUT>").replace(str(repo_root), "<REPO>")

    inv, inv_text = inventory(repo_root, out, scripts, config)
    inv.pop("root")
    for k in NEW_INVENTORY_KEYS:
        inv.pop(k, None)
    inv_text = "\n".join(l for l in norm(inv_text).splitlines()
                         if not l.startswith(NEW_SUMMARY_PREFIXES))
    snap = {"inventory_json": inv, "inventory_text": inv_text}
    for name, fn, kw in (("validate", validate, {"config": config}), ("verify", verify, {})):
        for j in (False, True):
            code, stdout, stderr = fn(bundle, scripts, json_out=j, **kw)
            snap[f"{name}{'_json' if j else ''}"] = {
                "code": code, "stdout": norm(stdout), "stderr": norm(stderr)}
    return snap


SAMPLE_CONFIG = """okf:
  bundle_dir: "docs/kb"   # non-default location
  exclude:
    - "app/models.py"
"""

FIXTURES = {
    # name -> (bundle_dir, config text or None)
    "default": ("knowledge", None),
    "configured": ("docs/kb", SAMPLE_CONFIG),
}


def snapshot_fixture(name: str, tmp: Path, scripts=SCRIPTS) -> dict:
    bundle_dir, config = FIXTURES[name]
    root = tmp / name
    build_sample(root, bundle_dir, config)
    cfg = root / ".okf-config.yml" if config else None
    return snapshot(root, root / bundle_dir, tmp / f"{name}-inventory.json", scripts, cfg)
