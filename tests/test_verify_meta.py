"""`catalogify verify` on a meta root: V15, V16."""
import json
import re
import subprocess
import sys

import pytest

from meta_fixtures import SHA, edge_bundle, run_meta, synced
from okf_fixtures import SCRIPTS, git_env


def verify(root, *extra):
    p = subprocess.run([sys.executable, str(SCRIPTS / "verify_okf.py"), str(root), *extra],
                       capture_output=True, text=True, env=git_env())
    return p.returncode, p.stdout, p.stderr


@pytest.fixture
def meta(tmp_path):
    root, dc, edge = synced(tmp_path)
    run_meta("init", root)
    assert run_meta("derive", "--root", root)[0] == 0
    subprocess.run(["git", "add", "-A"], cwd=root, env=git_env(), check=True)
    subprocess.run(["git", "commit", "-qm", "meta"], cwd=root, env=git_env(), check=True)
    return root, dc, edge


def findings(out, code):
    # verify reports paths with the OS separator; compare them in posix form.
    return [l.split("FINDING ", 1)[1].replace("\\", "/") for l in out.splitlines() if "FINDING " in l]


def test_clean_meta_verifies(meta):
    root, _, _ = meta
    code, out, err = verify(root)
    assert code == 0, out + err
    assert "(meta bundle: 2 repo summaries)" in out
    assert "VERIFIED" in out


def test_json_meta_key(meta):
    root, _, _ = meta
    code, out, _ = verify(root, "--json")
    data = json.loads(out)
    assert data["meta"] == {"summaries": 2}
    # The walk skips bundles/: only meta-repo concepts are counted.
    walked = [p for p in root.rglob("*.md")
              if p.name not in ("index.md", "log.md", "README.md", "AGENTS.md")
              and "bundles" not in p.parts and ".git" not in p.parts]
    assert data["concepts"] == len(walked)


def test_not_meta_without_registry(meta):
    root, _, _ = meta
    (root / "okf-registry.yaml").unlink()
    code, out, _ = verify(root)
    assert "meta bundle" not in out


def test_v15_source_files(meta):
    root, _, _ = meta
    p = root / "components/dc/services.md"
    p.write_text(p.read_text().replace('"bundles/dc/summary.md"', '"bundles/dc/old.md"'))
    code, out, _ = verify(root)
    assert code == 1
    assert any(f.startswith("V15 components/dc/services.md") and "bundles/dc/old.md" in f
               for f in findings(out, code))


def test_v15_link_to_unlisted_unit(meta):
    root, _, _ = meta
    p = root / "components/dc/services.md"
    p.write_text(p.read_text().replace("knowledge/services/quota.md", "knowledge/services/gone.md"))
    code, out, _ = verify(root)
    assert code == 1
    assert any("V15" in f and "services/gone.md" in f and "does not list" in f for f in findings(out, code))


def test_v15_link_at_other_ref(meta):
    root, _, _ = meta
    p = root / "components/dc/services.md"
    p.write_text(p.read_text().replace(f"/blob/{SHA}/knowledge/services/quota.md",
                                       "/blob/0123456789ab/knowledge/services/quota.md"))
    code, out, _ = verify(root)
    assert code == 1
    assert any("V15" in f and "0123456789ab" in f for f in findings(out, code))


def test_v16_ref_mismatch(meta):
    root, _, _ = meta
    reg = root / "okf-registry.yaml"
    reg.write_text(reg.read_text().replace(f'"{SHA}"', '"8be01d4aaaaa"', 1))
    code, out, _ = verify(root)
    assert code == 1
    assert any(f.startswith("V16 bundles/") and "8be01d4aaaaa" in f for f in findings(out, code))


def test_v16_short_ref_agrees(meta):
    root, _, _ = meta
    reg = root / "okf-registry.yaml"
    reg.write_text(reg.read_text().replace(f'"{SHA}"', f'"{SHA[:7]}"'))
    code, out, _ = verify(root)
    assert code == 0, out


def test_v16_unknown_ref(tmp_path):
    root, dc, edge = synced(tmp_path)
    edge_bundle(edge, commit=None)
    run_meta("sync", "--root", root, f"edge={edge}")
    run_meta("derive", "--root", root)
    subprocess.run(["git", "add", "-A"], cwd=root, env=git_env(), check=True)
    subprocess.run(["git", "commit", "-qm", "m"], cwd=root, env=git_env(), check=True)
    code, out, _ = verify(root)
    assert code == 1
    assert any(f.startswith("V16 bundles/edge") and "unknown" in f for f in findings(out, code))


def test_v16_missing_summary(meta):
    root, _, _ = meta
    (root / "bundles/edge/summary.md").unlink()
    code, out, _ = verify(root)
    assert any(f.startswith("V16 bundles/edge") and "missing" in f for f in findings(out, code))


def test_v16_copied_bundle_files(meta):
    root, dc, _ = meta
    (root / "bundles/dc/index.md").write_text((dc / "index.md").read_text())
    code, out, _ = verify(root)
    assert code == 1
    assert any(f.startswith("V16 bundles/dc") and "other than summary.md" in f for f in findings(out, code))
    assert not any("bundles/dc/index.md" in f and f.startswith(("V1 ", "V8 ")) for f in findings(out, code))
