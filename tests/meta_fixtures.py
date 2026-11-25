"""Child bundles and meta roots for the `catalogify meta` tests.

A child bundle here is only files on disk: sync reads it in place and never
needs its repository, so most fixtures are plain directories. The meta root is
a real git repository when a test validates or verifies it, because W6 and V8
resolve against git.
"""
import subprocess
import sys
import textwrap
from pathlib import Path

from okf_fixtures import SCRIPTS, Repo, git_env

META = SCRIPTS / "okf_meta.py"
SHA = "3f2a9c1e4b5d"


def page(fm: dict, body: str) -> str:
    """A concept file: YAML frontmatter from a dict, then the body."""
    import yaml
    return "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + textwrap.dedent(body).lstrip()


def write_bundle(root: Path, pages: dict, commit=SHA, extra=None) -> Path:
    """Write a child bundle: index.md, log.md and the given {rel: text} pages."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.md").write_text('---\nokf_version: "0.1"\n---\n\n# Bundle\n')
    commit_line = f"Commit: `{commit}`\n" if commit else ""
    (root / "log.md").write_text(
        "# Knowledge Bundle Update Log\n\n"
        f"## 2026-02-01\n{commit_line}* **Update**: newer.\n\n"
        "## 2026-01-01\nCommit: `0000000aaaaa`\n* **Initialization**: older.\n")
    for rel, text in {**pages, **(extra or {})}.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return root


def dc_bundle(root: Path, extra=None, **kw) -> Path:
    """Provider repo: three units in two directories, typed relations,
    a Dependencies link, an Interfaces table, a non-unit page and GUIDANCE.md."""
    return write_bundle(root, {
        "services/sessions.md": page({
            "type": "Service", "title": "Session service",
            "description": "Owns subscriber sessions.",
            "source_files": ["svc/sessions/"],
            "relations": [
                {"kind": "calls", "target": "svc/quota/client.go", "evidence": ["a1b2c3d4e5f6"]},
                {"kind": "changes_with", "target": "svc/sessions/api.proto", "evidence": ["a1b2c3d4e5f6"]},
                {"kind": "requires", "target": "lib/auth/token.go"},
                {"kind": "calls", "target": "vendor/unknown.go"},
            ],
        }, """
            # Summary

            Session handling. This sentence is a page body and must never reach the meta repo.

            # Interfaces

            | Symbol | Purpose |
            | --- | --- |
            | `SessionService` | gRPC service. |
            | `(s *Server) OpenSession(ctx, req)` | Opens one. |
            | `Charge` | Too short and not code-shaped. |
            | `PAYMENTS` | Upper case, not code-shaped. |
            | `grpc/sessions-v1` | Has a slash. |

            # Dependencies

            - [Auth](../modules/auth.md)
            - [Missing](../modules/nope.md)
            """),
        "services/quota.md": page({
            "type": "Service", "title": "Quota service",
            "description": "Counts usage | per tenant.",
            "source_files": ["svc/quota/"],
        }, """
            # Interfaces

            | Symbol | Purpose |
            | --- | --- |
            | `QuotaService` | gRPC service. |
            """),
        "modules/auth.md": page({
            "type": "Module", "title": "Auth library",
            "description": "Token checks.",
            "source_files": ["lib/auth/"],
        }, """
            # Interfaces

            | Symbol | Purpose |
            | --- | --- |
            | `AuthClient` | Client. |
            """),
        "overview.md": page({"type": "Reference", "title": "Overview",
                             "description": "Not a unit."}, "# Summary\n\nOverview.\n"),
    }, extra={"GUIDANCE.md": "# Guidance\n\nHuman-owned.\n", **(extra or {})}, **kw)


def edge_bundle(root: Path, **kw) -> Path:
    """Consumer repo: uses dc's SessionService and QuotaService, and its own
    EdgeLocalService (a same-repo match that must not become a contract edge)."""
    return write_bundle(root, {
        "agents/edge-agent.md": page({
            "type": "Service", "title": "Edge agent",
            "description": "Runs on the edge.",
            "source_files": ["agent/"],
        }, """
            # Summary

            Opens sessions with `dc.SessionService` and calls the local `EdgeLocalService`.
            The `SessionServiceClient` wrapper must not match `SessionService` by substring.

            # Interfaces

            | Symbol | Purpose |
            | --- | --- |
            | `EdgeLocalService` | Local API. |

            # Dependencies

            - [Local store](../store/local.md)
            """),
        "store/local.md": page({
            "type": "Module", "title": "Local store",
            "description": "Edge cache.",
            "source_files": ["store/"],
        }, """
            # Behaviour

            Refreshes limits from QuotaService every minute.
            """),
    }, **kw)


REPOS_YAML = """\
version: 1
repos:
  dc:
    title: DC monorepo
    remote: https://git.example.com/org/dc.git
    bundle_path: knowledge
    group_by: directory
  edge:
    title: Edge monorepo
    remote: https://git.example.com/org/edge.git
    bundle_path: docs/kb
    group_by: directory
contracts:
  grpc:
    title: gRPC services
"""


def run_meta(*args, cwd=None):
    p = subprocess.run([sys.executable, str(META), *map(str, args)], cwd=cwd,
                       env=git_env(), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def make_meta(tmp: Path, repos_yaml=REPOS_YAML, git=True) -> Path:
    """A meta root with repos.yaml. Not scaffolded: tests that need the
    scaffold call `meta init` themselves."""
    root = tmp / "meta"
    if git:
        Repo(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "repos.yaml").write_text(repos_yaml)
    return root


def synced(tmp: Path, repos_yaml=REPOS_YAML, git=True):
    """A meta root with dc and edge synced from fixture bundles."""
    root = make_meta(tmp, repos_yaml, git)
    dc = dc_bundle(tmp / "dc" / "knowledge")
    edge = edge_bundle(tmp / "edge" / "docs" / "kb")
    code, out, err = run_meta("sync", "--root", root, f"dc={dc}", f"edge={edge}")
    assert code == 0, err + out
    return root, dc, edge
