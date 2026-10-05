"""0.10.0: agent docs as context, and BUNDLE_DIR/GUIDANCE.md as steering.

T1-T6 from the steering spec. Every fixture is a tiny git repository built in
tmp_path; see okf_fixtures.py.
"""
import hashlib
import json
from pathlib import Path

import pytest

from okf_fixtures import (FIXTURES, build_sample, inventory, snapshot_fixture,
                          validate, verify)

GOLDEN = Path(__file__).resolve().parent / "golden"


def inv(repo, tmp_path, config=None):
    data, _ = inventory(repo.root, tmp_path / "inv.json", config=config)
    return data


def validate_json(bundle):
    code, out, err = validate(bundle, json_out=True)
    assert code in (0, 1), err
    return json.loads(out)


# --- T1: no agent docs, no guidance -> identical to 0.9.2 ---------------------

@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_t1_output_matches_092(name, tmp_path):
    golden = json.loads((GOLDEN / f"{name}.json").read_text())
    snap = json.loads(json.dumps(snapshot_fixture(name, tmp_path)))
    assert snap == golden


def test_t1_new_keys_are_empty(tmp_path):
    r = build_sample(tmp_path / "repo")
    data, text = inventory(r.root, tmp_path / "inv.json")
    assert data["agent_docs"] == {"items": [], "truncated": False}
    assert data["guidance"]["exists"] is False
    assert data["bundle"]["concept_files"] == 1
    assert "  agent docs: 0" in text.splitlines()
    assert "  guidance: none" in text.splitlines()


# --- T2: agent docs discovery -------------------------------------------------

def test_t2_agent_docs(tmp_path):
    r = build_sample(tmp_path / "repo", config='okf:\n  exclude:\n    - "skipme/**"\n')
    r.write("AGENTS.md", "root context\n")
    r.write("services/billing/CLAUDE.md", "billing\n")
    r.write("services/billing/api/GEMINI.md", "api\n")
    r.write(".github/copilot-instructions.md", "copilot\n")
    r.write("skipme/AGENTS.md", "excluded\n")
    r.write("knowledge/AGENTS.md", "for bundle readers\n")
    r.commit("Add agent docs")
    r.write("untracked/AGENTS.md", "not in git\n")

    data = inv(r, tmp_path, config=r.root / ".okf-config.yml")
    items = {d["path"]: d for d in data["agent_docs"]["items"]}
    assert set(items) == {"AGENTS.md", "services/billing/CLAUDE.md",
                          "services/billing/api/GEMINI.md", ".github/copilot-instructions.md"}
    assert items["AGENTS.md"]["scope"] == "."
    assert items["services/billing/CLAUDE.md"]["scope"] == "services/billing"
    assert items["services/billing/api/GEMINI.md"]["scope"] == "services/billing/api"
    assert items[".github/copilot-instructions.md"]["scope"] == "."
    assert items["AGENTS.md"]["bytes"] == len("root context\n")
    assert data["agent_docs"]["truncated"] is False


def test_t2_agent_docs_cap(tmp_path):
    r = build_sample(tmp_path / "repo")
    for i in range(3):
        r.write(f"m{i}/AGENTS.md", "x\n")
    r.commit("Add agent docs")
    import okf_fixtures
    env = okf_fixtures.git_env()
    env["OKF_INVENTORY_CAP"] = "2"
    out = tmp_path / "inv.json"
    code, _, err = okf_fixtures.run(
        ["bash", str(okf_fixtures.SCRIPTS / "okf-inventory.sh"), str(out)], r.root, env)
    assert code == 0, err
    data = json.loads(out.read_text())
    assert len(data["agent_docs"]["items"]) == 2
    assert data["agent_docs"]["truncated"] is True


# --- T3: guidance -------------------------------------------------------------

def test_t3_guidance(tmp_path):
    r = build_sample(tmp_path / "repo")
    assert inv(r, tmp_path)["guidance"] == {
        "path": "knowledge/GUIDANCE.md", "exists": False,
        "tracked": None, "sha256": None, "bytes": None}

    text = "# Guidance\n\nCall them tenants, not customers.\n"
    r.write("knowledge/GUIDANCE.md", text)
    g = inv(r, tmp_path)["guidance"]
    assert g["exists"] is True and g["tracked"] is False
    assert g["sha256"] == hashlib.sha256(text.encode()).hexdigest()
    assert g["bytes"] == len(text.encode())

    r.commit("Add guidance")
    assert inv(r, tmp_path)["guidance"]["tracked"] is True

    r.write("knowledge/GUIDANCE.md", text + "Skip the demo/ tree.\n")
    assert inv(r, tmp_path)["guidance"]["sha256"] != g["sha256"]


def test_t3_bundle_dir_from_config(tmp_path):
    r = build_sample(tmp_path / "repo", bundle_dir="docs/kb",
                     config="okf:\n  bundle_dir: './docs/kb/'   # moved\n")
    r.write("docs/kb/GUIDANCE.md", "g\n")
    r.write("docs/kb/CLAUDE.md", "for readers\n")
    r.write("knowledge/AGENTS.md", "not the bundle here\n")
    r.commit("guidance")
    data = inv(r, tmp_path, config=r.root / ".okf-config.yml")
    assert data["guidance"]["path"] == "docs/kb/GUIDANCE.md"
    assert data["guidance"]["exists"] is True
    assert data["bundle"]["dir"] == "docs/kb"
    paths = [d["path"] for d in data["agent_docs"]["items"]]
    assert paths == ["knowledge/AGENTS.md"]


# --- T4: bundle.concept_files -------------------------------------------------

def test_t4_concept_files(tmp_path):
    r = build_sample(tmp_path / "repo")
    r.git("rm", "-rq", "knowledge")
    r.commit("Remove bundle")
    data = inv(r, tmp_path)
    assert data["bundle"] == {"dir": "knowledge", "exists": False,
                              "concept_files": 0, "non_concept_files": []}

    r.write("knowledge/GUIDANCE.md", "g\n")
    r.write("knowledge/README.md", "r\n")
    b = inv(r, tmp_path)["bundle"]
    assert b["exists"] is True and b["concept_files"] == 0
    assert b["non_concept_files"] == ["GUIDANCE.md", "README.md"]

    r.write("knowledge/index.md", "# Index\n")
    r.write("knowledge/log.md", "# Log\n")
    r.write("knowledge/modules/AGENTS.md", "a\n")
    assert inv(r, tmp_path)["bundle"]["concept_files"] == 0

    r.write("knowledge/modules/app.md", "---\ntype: Module\n---\nx\n")
    b = inv(r, tmp_path)["bundle"]
    assert b["concept_files"] == 1
    assert b["non_concept_files"] == ["GUIDANCE.md", "README.md", "modules/AGENTS.md"]


# --- T5: validator ignores steering files -------------------------------------

def test_t5_validator_ignored_files(tmp_path):
    r = build_sample(tmp_path / "repo")
    b = r.root / "knowledge"
    (b / "GUIDANCE.md").write_text("# Guidance\n\nNo frontmatter here.\n")
    (b / "AGENTS.md").write_text("# For agents\n")
    (b / "modules" / "CLAUDE.md").write_text("# For Claude\n")
    (b / "modules" / "GEMINI.md").write_text("# For Gemini\n")
    res = validate_json(b)
    assert res["result"] == "CONFORMANT", res
    assert res["concepts"] == 1
    assert res["warnings"] == []

    (b / "modules" / "GUIDANCE.md").write_text("# Misplaced\n")
    res = validate_json(b)
    assert res["result"] == "CONFORMANT", res
    assert any(w.startswith("W10 modules/GUIDANCE.md") for w in res["warnings"])
    assert not any("GUIDANCE" in e for e in res["errors"])

    (b / "modules" / "notes.md").write_text("# No frontmatter\n")
    res = validate_json(b)
    assert res["result"] == "NON-CONFORMANT"
    assert any(e.startswith("E1 modules/notes.md") for e in res["errors"])


def test_t5_verify_ignores_guidance(tmp_path):
    r = build_sample(tmp_path / "repo")
    b = r.root / "knowledge"
    (b / "GUIDANCE.md").write_text("Index the marker `deadbeef12`.\n")
    (b / "AGENTS.md").write_text("Agents: see `cafebabe00`.\n")
    code, out, err = verify(b, json_out=True)
    res = json.loads(out)
    assert code == 0, (out, err)
    assert res["concepts"] == 1 and res["findings"] == []


# --- T6: Guidance: line in log.md ---------------------------------------------

def _log(tmp_path, block):
    r = build_sample(tmp_path / "repo")
    b = r.root / "knowledge"
    sha = r.git("rev-parse", "--short=12", "HEAD")
    (b / "log.md").write_text("# Log\n\n## 2026-10-05\n" + block.format(sha=sha) + "* **Update**: x\n")
    return validate_json(b)


def _e4(res):
    return [e for e in res["errors"] if e.startswith("E4")]


def test_t6_guidance_after_commit_ok(tmp_path):
    res = _log(tmp_path, "Commit: `{sha}`\nGuidance: `9f86d081884c`\n")
    assert res["result"] == "CONFORMANT", res


def test_t6_guidance_before_commit(tmp_path):
    assert _e4(_log(tmp_path, "Guidance: `9f86d081884c`\nCommit: `{sha}`\n"))


def test_t6_guidance_without_commit(tmp_path):
    errs = _e4(_log(tmp_path, "Guidance: `9f86d081884c`\n"))
    assert any("missing required 'Commit:" in e for e in errs)


def test_t6_two_guidance_lines(tmp_path):
    errs = _e4(_log(tmp_path, "Commit: `{sha}`\nGuidance: `9f86d081884c`\nGuidance: `9f86d081884c`\n"))
    assert any("at most one" in e for e in errs)


def test_t6_malformed_guidance(tmp_path):
    errs = _e4(_log(tmp_path, "Commit: `{sha}`\nGuidance: `9f86`\n"))
    assert any("malformed" in e for e in errs)


def _plain_log(tmp_path, block):
    b = tmp_path / "plain" / "knowledge"
    b.mkdir(parents=True)
    (b / "index.md").write_text('---\nokf_version: "0.1"\n---\n# Index\n')
    (b / "log.md").write_text("# Log\n\n## 2026-10-05\n" + block)
    return validate_json(b)


def test_t6_guidance_outside_git_ok(tmp_path):
    res = _plain_log(tmp_path, "Commit: `none`\nGuidance: `9f86d081884c`\n")
    assert res["result"] == "CONFORMANT", res


@pytest.mark.parametrize("block,why", [
    ("Commit: `none`\nGuidance: `9f86`\n", "malformed"),
    ("Guidance: `9f86d081884c`\nCommit: `none`\n", "not directly after"),
    ("Commit: `none`\nGuidance: `9f86d081884c`\nGuidance: `9f86d081884c`\n", "at most one"),
])
def test_t6_guidance_checked_outside_git(tmp_path, block, why):
    errs = _e4(_plain_log(tmp_path, block))
    assert any(why in e for e in errs), errs


def test_t6_no_commit_line_still_optional_outside_git(tmp_path):
    assert _plain_log(tmp_path, "* **Initialization**: x\n")["result"] == "CONFORMANT"


# --- Filename case ------------------------------------------------------------

def test_inventory_guidance_name_is_case_exact(tmp_path):
    r = build_sample(tmp_path / "repo")
    r.write("knowledge/guidance.md", "lower-case\n")
    data, text = inventory(r.root, tmp_path / "inv.json")
    assert data["guidance"]["exists"] is False
    assert data["bundle"]["concept_files"] == 1          # not counted as a concept
    assert "guidance.md" in data["bundle"]["non_concept_files"]
    assert "rename it to GUIDANCE.md" in text


def test_validator_warns_on_case_variant(tmp_path):
    r = build_sample(tmp_path / "repo")
    b = r.root / "knowledge"
    (b / "guidance.md").write_text("# lower-case guidance, no frontmatter\n")
    (b / "modules" / "Agents.md").write_text("# for agents\n")
    res = validate_json(b)
    assert res["result"] == "CONFORMANT", res
    assert res["concepts"] == 1
    assert any(w.startswith("W11 guidance.md: rename guidance.md to GUIDANCE.md") for w in res["warnings"])
    assert any(w.startswith("W11 modules/Agents.md: rename Agents.md to AGENTS.md") for w in res["warnings"])


def test_verify_skips_case_variant(tmp_path):
    r = build_sample(tmp_path / "repo")
    b = r.root / "knowledge"
    (b / "guidance.md").write_text("Index the marker `deadbeef12`.\n")
    code, out, _ = verify(b, json_out=True)
    res = json.loads(out)
    assert code == 0 and res["concepts"] == 1 and res["findings"] == []
