"""`catalogify meta`: scaffold, summarise, derive."""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

from meta_fixtures import (META, REPOS_YAML, SHA, dc_bundle, edge_bundle, make_meta, page,
                           run_meta, synced, write_bundle)
from okf_fixtures import REPO_ROOT, SCRIPTS, Repo, git_env

sys.path.insert(0, str(SCRIPTS))
import okf_meta  # noqa: E402


def fm(path: Path) -> dict:
    text = path.read_text()
    return yaml.safe_load(text.split("---\n")[1])


def derive(root):
    code, out, err = run_meta("derive", "--root", root)
    return code, out, err


def validate(root):
    p = subprocess.run([sys.executable, str(SCRIPTS / "validate_okf.py"), str(root),
                        "--config", str(root / ".okf-config.yml"), "--json"],
                       capture_output=True, text=True, env=git_env())
    return json.loads(p.stdout)


def tree(root: Path) -> dict:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and ".git" not in p.parts}


# --- foundation ---------------------------------------------------------------

@pytest.mark.parametrize("sub", ["init", "sync", "derive"])
def test_help(sub):
    code, out, _ = run_meta(sub, "--help")
    assert code == 0 and "usage" in out.lower()


def test_bare_meta_exits_2():
    code, _, err = run_meta()
    assert code == 2 and "init" in err


def test_cli_dispatch(tmp_path, capfd):
    from catalogify import cli
    assert cli.main(["meta", "init", str(tmp_path / "m")]) == 0
    assert (tmp_path / "m" / "repos.yaml").is_file()
    assert "meta" in cli.USAGE


@pytest.mark.parametrize("text", [None, ""])
def test_missing_or_empty_repos_yaml(tmp_path, text):
    root = tmp_path / "m"
    root.mkdir()
    if text is not None:
        (root / "repos.yaml").write_text(text)
    for sub in ("sync", "derive"):
        code, _, err = run_meta(sub, "--root", root)
        assert code == 2 and "catalogify meta init" in err


@pytest.mark.parametrize("bad, needle", [
    ("version: 2\nrepos: {a: {title: A, remote: r, bundle_path: k}}\n", "version"),
    ("version: 1\nrepos: {A_B: {title: A, remote: r, bundle_path: k}}\n", "A_B"),
    ("version: 1\nrepos: {a: {remote: r, bundle_path: k}}\n", "title"),
    ("version: 1\nrepos: {a: {title: A, remote: r}}\n", "bundle_path"),
    ("version: 1\nrepos: {a: {title: A, remote: r, bundle_path: k, group_by: tree}}\n", "group_by"),
    ("version: 1\nrepos: {external: {title: A, remote: r, bundle_path: k}}\n", "external"),
    ("version: 1\nrepos: {a: {title: A, remote: r, bundle_path: k}}\n"
     "contracts: {grpc: {title: G, provides: {pattern: 'no group'}}}\n", "pattern"),
])
def test_bad_registry_exits_2(tmp_path, bad, needle):
    root = make_meta(tmp_path, bad, git=False)
    code, _, err = run_meta("derive", "--root", root)
    assert code == 2 and needle in err


def test_write_if_changed_ignores_timestamp(tmp_path):
    p = tmp_path / "a.md"
    assert okf_meta.write_if_changed(p, "---\ntimestamp: 1\n---\nbody\n")
    before = p.stat().st_mtime_ns
    time.sleep(0.01)
    assert not okf_meta.write_if_changed(p, "---\ntimestamp: 2\n---\nbody\n")
    assert p.stat().st_mtime_ns == before and "timestamp: 1" in p.read_text()
    assert okf_meta.write_if_changed(p, "---\ntimestamp: 3\n---\nother\n")


def test_merge_questions():
    prev = ["[a:1] Edited text, kept verbatim.", "Hand-added, no ID."]
    notes = "# Notes\n\n<!-- clarified: c:3 -->\nAnswer.\n"
    detected = [("a:1", "Original text."), ("b:2", "New question."), ("c:3", "Answered.")]
    assert okf_meta.merge_questions(prev, detected, notes) == [
        "[a:1] Edited text, kept verbatim.", "Hand-added, no ID.", "[b:2] New question."]


# --- scaffold --------------------------------------------------------------------

SCAFFOLD = ["repos.yaml", "AGENTS.md", ".okf-config.yml", ".gitignore", "README.md", "log.md",
            "index.md", "architecture/index.md", "architecture/spec-splitting.md"]


def test_init_creates_scaffold(tmp_path):
    root = tmp_path / "m"
    code, out, _ = run_meta("init", root)
    assert code == 0
    for f in SCAFFOLD:
        assert (root / f).is_file(), f
        assert f"created {f}" in out
    cfg = yaml.safe_load((root / ".okf-config.yml").read_text())
    assert {"bundles/**", "workspace/**"} <= set(cfg["okf"]["exclude"])
    assert "workspace/" in (root / ".gitignore").read_text()
    assert "catalogify meta sync" in out


def test_init_keeps_existing_files(tmp_path):
    root = tmp_path / "m"
    run_meta("init", root)
    (root / "AGENTS.md").write_text("mine\n")
    before = tree(root)
    code, out, _ = run_meta("init", root)
    assert code == 0 and tree(root) == before
    assert all(f"kept    {f}" in out for f in SCAFFOLD)


@pytest.mark.parametrize("git", [True, False])
def test_scaffold_validates(tmp_path, git):
    root = tmp_path / "m"
    if git:
        Repo(root)
    run_meta("init", root)
    res = validate(root)
    assert res["result"] == "CONFORMANT", res
    assert not [w for w in res["warnings"] if w.split()[0] in ("W2", "W3", "W6", "W10")], res
    log = (root / "log.md").read_text()
    assert "Commit: `none`" in log  # an empty repo has no HEAD


def test_init_records_head(tmp_path):
    r = Repo(tmp_path / "m")
    r.write("x", "x")
    head = r.commit("first")
    run_meta("init", r.root)
    assert re.search(rf"Commit: `{head}[0-9a-f]*`", (r.root / "log.md").read_text())


# --- summarise -------------------------------------------------------------------

def test_sync_writes_only_summaries(tmp_path):
    root, dc, edge = synced(tmp_path)
    files = sorted(p.relative_to(root).as_posix() for p in (root / "bundles").rglob("*") if p.is_file())
    assert files == ["bundles/dc/summary.md", "bundles/edge/summary.md"]
    text = (root / "bundles/dc/summary.md").read_text()
    assert "must never reach the meta repo" not in text
    assert "Human-owned" not in text
    meta = fm(root / "bundles/dc/summary.md")
    assert meta["ref"] == SHA and meta["source"] == "https://git.example.com/org/dc.git"
    assert meta["subpath"] == "knowledge" and meta["units"] == 3
    assert meta["generated_by"].startswith("catalogify-meta/")
    for heading in ("# Units", "# Edges", "# Provides", "# Uses"):
        assert heading in text


def test_sync_from_local(tmp_path):
    yml = REPOS_YAML.replace("bundle_path: knowledge\n", "bundle_path: knowledge\n    local: ../dc\n")
    root = make_meta(tmp_path, yml)
    dc_bundle(tmp_path / "dc" / "knowledge")
    code, out, err = run_meta("sync", "--root", root)
    assert code == 0, err
    assert (root / "bundles/dc/summary.md").is_file() and not (root / "bundles/edge").exists()
    assert "synced 1 repo" in out


def test_sync_registry_record(tmp_path):
    root, _, _ = synced(tmp_path)
    reg = yaml.safe_load((root / "okf-registry.yaml").read_text())
    assert reg["mounts"]["bundles/dc"] == {
        "source": "https://git.example.com/org/dc.git", "subpath": "knowledge",
        "ref": SHA, "synced": reg["mounts"]["bundles/dc"]["synced"]}
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(reg["mounts"]["bundles/dc"]["synced"]))
    assert "Do not edit" in (root / "okf-registry.yaml").read_text()


def test_sync_unknown_ref(tmp_path):
    root = make_meta(tmp_path)
    dc = dc_bundle(tmp_path / "dc", commit=None)
    code, out, _ = run_meta("sync", "--root", root, f"dc={dc}")
    assert code == 0 and "ref unknown" in out
    assert fm(root / "bundles/dc/summary.md")["ref"] == "unknown"


def test_sync_not_a_bundle_keeps_previous(tmp_path):
    root, dc, _ = synced(tmp_path)
    before = (root / "bundles/dc/summary.md").read_bytes()
    empty = tmp_path / "empty"
    empty.mkdir()
    code, _, err = run_meta("sync", "--root", root, f"dc={empty}")
    assert code == 1 and "dc" in err and "not an OKF bundle" in err
    assert (root / "bundles/dc/summary.md").read_bytes() == before


@pytest.mark.parametrize("args, needle", [
    (["zz=/tmp"], "zz"),               
    (["nodelimiter"], "name=dir"),
    ([], "nothing to sync"),
])
def test_sync_usage_errors(tmp_path, args, needle):
    root = make_meta(tmp_path)
    code, _, err = run_meta("sync", "--root", root, *args)
    assert code == 2 and needle in err


def test_partial_sync_keeps_other_entries(tmp_path):
    root, dc, _ = synced(tmp_path)
    run_meta("sync", "--root", root, f"dc={dc}")
    reg = yaml.safe_load((root / "okf-registry.yaml").read_text())
    assert set(reg["mounts"]) == {"bundles/dc", "bundles/edge"}


def test_sync_removes_copied_bundle(tmp_path):
    root, dc, _ = synced(tmp_path)
    shutil.copytree(dc, root / "bundles/dc/full")
    (root / "bundles/dc/index.md").write_text("copied\n")
    code, out, _ = run_meta("sync", "--root", root, f"dc={dc}")
    assert code == 0 and "removed copied bundle files from bundles/dc/" in out
    assert [p.name for p in (root / "bundles/dc").iterdir()] == ["summary.md"]


def test_resync_unchanged_is_byte_identical(tmp_path):
    root, dc, edge = synced(tmp_path)
    before = tree(root)
    run_meta("sync", "--root", root, f"dc={dc}", f"edge={edge}")
    assert tree(root) == before


# --- component pages and within-repo edges ---------------------------------------

def test_directory_grouping(tmp_path):
    root, _, _ = synced(tmp_path)
    code, out, err = derive(root)
    assert code == 0, err
    assert sorted(p.name for p in (root / "components/dc").glob("*.md")) == ["index.md", "modules.md", "services.md"]
    body = (root / "components/dc/services.md").read_text()
    assert "Session service" in body and "Quota service" in body and "Overview" not in body
    assert "Counts usage \\| per tenant." in body


def test_unit_types_case_insensitive(tmp_path):
    yml = REPOS_YAML.replace("    group_by: directory\n  edge:",
                             "    group_by: directory\n    unit_types: [module]\n  edge:")
    root, _, _ = synced(tmp_path, yml)
    derive(root)
    assert not (root / "components/dc/services.md").exists()
    assert (root / "components/dc/modules.md").exists()


def test_catalog_grouping(tmp_path):
    yml = REPOS_YAML.replace("bundle_path: knowledge\n    group_by: directory",
                             "bundle_path: knowledge\n    group_by: catalog:catalog.md\n"
                             "    catalog_skip: [Glossary]")
    root = make_meta(tmp_path, yml)
    dc = dc_bundle(tmp_path / "dc", extra={"catalog.md": page(
        {"type": "Reference", "title": "Catalog", "description": "Domains."}, """
        # Charging

        - [Sessions](services/sessions.md) and [Quota](services/quota.md) on one line
        - [Gone](services/gone.md)

        ## Platform

        - [Auth](modules/auth.md)
        - [Sessions again](services/sessions.md)

        ## Glossary

        - [Overview](overview.md)
        """)})
    edge = edge_bundle(tmp_path / "edge")
    assert run_meta("sync", "--root", root, f"dc={dc}", f"edge={edge}")[0] == 0
    derive(root)
    def units(name):
        return (root / f"components/dc/{name}.md").read_text().split("# Units")[1].split("\n# ")[0]
    charging, platform = units("charging"), units("platform")
    assert "Session service" in charging and "Quota service" not in charging
    assert "Auth library" in platform and "Session service" not in platform
    assert not (root / "components/dc/glossary.md").exists()


def test_frontmatter_grouping(tmp_path):
    yml = REPOS_YAML.replace("bundle_path: knowledge\n    group_by: directory",
                             "bundle_path: knowledge\n    group_by: frontmatter:domain")
    root = make_meta(tmp_path, yml)
    dc = write_bundle(tmp_path / "dc", {
        "a.md": page({"type": "Service", "title": "A", "description": "a", "domain": ["Billing", "X"]}, "# S\n"),
        "b.md": page({"type": "Service", "title": "B", "description": "b"}, "# S\n"),
    })
    assert run_meta("sync", "--root", root, f"dc={dc}")[0] == 0
    derive(root)
    assert "[A]" in (root / "components/dc/billing.md").read_text()
    assert "[B]" in (root / "components/dc/unassigned.md").read_text()


def test_within_repo_edges(tmp_path):
    root, _, _ = synced(tmp_path)
    code, out, err = run_meta("sync", "--root", root, f"dc={tmp_path / 'dc' / 'knowledge'}")
    assert "1 relation target not covered by a unit" in out
    s = okf_meta.read_summary(root / "bundles/dc/summary.md")
    edges = {(e["from"], e["kind"], e["to"]) for e in s["edges"]}
    assert edges == {
        ("services/sessions.md", "calls", "services/quota.md"),
        ("services/sessions.md", "depends_on", "modules/auth.md"),
    }  # self-edge, `requires`, the uncovered target and the missing link are dropped
    calls = next(e for e in s["edges"] if e["kind"] == "calls")
    assert calls["evidence"] == ["a1b2c3d4e5f6"]
    derive(root)
    services = (root / "components/dc/services.md").read_text()
    section = services.split("# Edges within dc")[1].split("\n# ")[0]
    assert "depends_on" in section and "modules.md" in section
    assert "1 edge between units of this domain is not listed" in section
    modules = (root / "components/dc/modules.md").read_text()
    assert "depends_on" in modules.split("# Edges within dc")[1]  # incoming edge listed too
    assert "a1b2c3d4e5f6" not in services  # child shas never on derived pages


def test_within_repo_edge_tie_warns(tmp_path):
    root = make_meta(tmp_path)
    dc = write_bundle(tmp_path / "dc", {
        "a.md": page({"type": "Service", "title": "A", "description": "a", "source_files": ["x/"],
                      "relations": [{"kind": "calls", "target": "shared/f.go"}]}, "# S\n"),
        "b.md": page({"type": "Service", "title": "B", "description": "b", "source_files": ["shared/"]}, "# S\n"),
        "c.md": page({"type": "Service", "title": "C", "description": "c", "source_files": ["shared/"]}, "# S\n"),
    })
    code, out, err = run_meta("sync", "--root", root, f"dc={dc}")
    assert code == 0 and "b.md" in err and "c.md" in err
    assert okf_meta.read_summary(root / "bundles/dc/summary.md")["edges"] == []


def test_permalinks(tmp_path):
    yml = REPOS_YAML.replace("bundle_path: docs/kb\n",
                             "bundle_path: docs/kb\n    url: https://forge.example/edge/-/blob/{ref}/docs/kb/{path}\n")
    root = make_meta(tmp_path, yml)
    dc = dc_bundle(tmp_path / "dc")
    edge = edge_bundle(tmp_path / "edge", commit=None)
    run_meta("sync", "--root", root, f"dc={dc}", f"edge={edge}")
    derive(root)
    dc_page = (root / "components/dc/services.md").read_text()
    assert f"https://git.example.com/org/dc/blob/{SHA}/knowledge/services/sessions.md" in dc_page
    edge_page = (root / "components/edge/agents-domain.md").read_text()
    assert "https://forge.example/edge/-/blob/HEAD/docs/kb/agents/edge-agent.md" in edge_page
    for p in list((root / "components").rglob("*.md")) + list((root / "edges").rglob("*.md")):
        assert not re.search(r"\]\([^)]*bundles/", p.read_text()), p
    sources = fm(root / "components/dc/services.md")["source_files"]
    assert "bundles/dc/summary.md" in sources  # plus the summaries of repos it has edges with
    assert all(re.fullmatch(r"bundles/[a-z0-9-]+/summary\.md", x) for x in sources)


def test_external_stub_written_once(tmp_path):
    yml = REPOS_YAML.replace("contracts:", "  vendor:\n    title: Vendor SaaS\n"
                             "    remote: https://vendor.example\n    bundle_path: null\ncontracts:")
    root, _, _ = synced(tmp_path, yml)
    derive(root)
    stub = root / "components/external/vendor.md"
    meta = fm(stub)
    assert "generated_by" not in meta and meta["open_questions"][0].startswith("[external-scope:vendor]")
    stub.write_text(stub.read_text() + "\nCurated.\n")
    before = stub.read_bytes()
    derive(root)
    assert stub.read_bytes() == before


def test_unsynced_repo_warns(tmp_path):
    root = make_meta(tmp_path)
    run_meta("sync", "--root", root, f"dc={dc_bundle(tmp_path / 'dc')}")
    code, out, err = derive(root)
    assert code == 0 and "edge has no summary" in err
    assert (root / "components/dc/services.md").exists()


def test_stale_summary_warns(tmp_path):
    root, _, _ = synced(tmp_path)
    yml = (root / "repos.yaml").read_text().replace("title: gRPC services", "title: gRPC services\n    min_length: 8")
    (root / "repos.yaml").write_text(yml)
    code, _, err = derive(root)
    assert code == 0 and "dc: summary built with an older repos.yaml; resync" in err


def test_reserved_domain_names_get_a_suffix(tmp_path):
    root, _, _ = synced(tmp_path)
    derive(root)
    assert (root / "components/edge/agents-domain.md").exists()  # not agents.md (AGENTS.md)
    assert not (root / "components/edge/agents.md").exists()
    assert "[Edge monorepo: agents](agents-domain.md)" in (root / "components/edge/index.md").read_text()
    s = okf_meta.read_summary(root / "bundles/dc/summary.md")
    used = {i for u in s["uses"] for i in u["identifiers"]}
    assert not {"auth.md", "nope.md"} & used  # link targets are not identifiers


def test_slug_collision(tmp_path):
    yml = REPOS_YAML.replace("bundle_path: knowledge\n    group_by: directory",
                             "bundle_path: knowledge\n    group_by: frontmatter:domain")
    root = make_meta(tmp_path, yml)
    dc = write_bundle(tmp_path / "dc", {
        "a.md": page({"type": "Service", "title": "A", "description": "a", "domain": "Data Plane"}, "# S\n"),
        "b.md": page({"type": "Service", "title": "B", "description": "b", "domain": "data-plane"}, "# S\n"),
    })
    edge = edge_bundle(tmp_path / "edge")
    run_meta("sync", "--root", root, f"dc={dc}", f"edge={edge}")
    code, _, err = derive(root)
    assert code == 1 and '"Data Plane"' in err and '"data-plane"' in err
    assert not (root / "components/dc").exists()
    assert (root / "components/edge/agents-domain.md").exists()


def test_summary_line_and_indexes(tmp_path):
    root, _, _ = synced(tmp_path)
    run_meta("init", root)
    code, out, _ = derive(root)
    last = [l for l in out.splitlines() if l.startswith("derived")][0]
    assert re.fullmatch(r"derived \d+ component pages?, \d+ contract pages?; \d+ units?, "
                        r"\d+ within-repo edges?, \d+ cross-repo edges?; removed \d+ stale pages?", last)
    idx = (root / "components/index.md").read_text()
    assert idx.startswith("<!-- generated_by: catalogify-meta/")
    assert "[dc/](dc/index.md)" in idx
    root_idx = (root / "index.md").read_text()
    assert root_idx.startswith('---\nokf_version: "0.1"\n---\n\n<!-- generated_by:')
    assert not (root / "bundles/index.md").exists()


# --- cross-repo contracts --------------------------------------------------------

def test_provides_extraction(tmp_path):
    root, _, _ = synced(tmp_path)
    s = okf_meta.read_summary(root / "bundles/dc/summary.md")
    provided = {p["identifier"] for p in s["provides"] if p["unit"] == "services/sessions.md"}
    assert provided == {"SessionService", "OpenSession"}


def test_untokenizable_identifier_warns(tmp_path):
    root = make_meta(tmp_path)
    dc = dc_bundle(tmp_path / "dc")
    dc_page = dc / "services/sessions.md"
    dc_page.write_text(dc_page.read_text().replace("`grpc/sessions-v1`", "`sessions_v1-beta`"))
    code, _, err = run_meta("sync", "--root", root, f"dc={dc}")
    assert code == 0 and "sessions_v1-beta" in err and "provides.pattern" in err


def test_provides_pattern(tmp_path):
    yml = REPOS_YAML.replace("    title: gRPC services\n",
                             "    title: gRPC services\n    provides:\n      pattern: 'service (\\w+Api)'\n")
    root = make_meta(tmp_path, yml)
    dc = write_bundle(tmp_path / "dc", {"a.md": page(
        {"type": "Service", "title": "A", "description": "a"}, "Exposes service BillingApi.\n")})
    run_meta("sync", "--root", root, f"dc={dc}")
    s = okf_meta.read_summary(root / "bundles/dc/summary.md")
    assert [p["identifier"] for p in s["provides"]] == ["BillingApi"]


def test_consumes_sections_narrow(tmp_path):
    yml = REPOS_YAML.replace("    title: gRPC services\n",
                             "    title: gRPC services\n    consumes:\n      sections: [Behaviour]\n")
    root, _, _ = synced(tmp_path, yml)
    s = okf_meta.read_summary(root / "bundles/edge/summary.md")
    used = {u["unit"]: set(u["identifiers"]) for u in s["uses"]}
    assert "QuotaService" in used["store/local.md"]
    assert "agents/edge-agent.md" not in used  # its mentions are in # Summary, not # Behaviour


def test_cross_repo_contract_pages(tmp_path):
    root, _, _ = synced(tmp_path)
    code, out, err = derive(root)
    assert code == 0, err
    pages = sorted(p.name for p in (root / "edges/grpc").glob("*.md"))
    assert pages == ["dc-services.md", "index.md"]
    contract = (root / "edges/grpc/dc-services.md").read_text()
    assert "`SessionService`" in contract and "`QuotaService`" in contract
    assert "Edge agent" in contract and "Local store" in contract
    assert "SessionServiceClient" not in contract.split("# Contract")[1]
    assert "evidence of a caller, not proof" in contract
    meta = fm(root / "edges/grpc/dc-services.md")
    assert meta["type"] == "Interface"
    assert meta["open_questions"][0].startswith("[contract-approval:grpc/dc-services]")
    assert meta["source_files"] == ["bundles/dc/summary.md", "bundles/edge/summary.md"]
    assert not list((root / "edges/grpc").glob("edge-*.md"))  # same-repo EdgeLocalService
    edge_c = (root / "components/edge/agents-domain.md").read_text()
    assert "**Uses dc services**" in edge_c and "../../edges/grpc/dc-services.md" in edge_c
    dc_c = (root / "components/dc/services.md").read_text()
    assert "**Provides gRPC services**" in dc_c


def test_ambiguous_provider(tmp_path):
    yml = REPOS_YAML.replace("contracts:", "  billing:\n    title: Billing\n    remote: https://x/b.git\n"
                             "    bundle_path: kb\ncontracts:")
    root = make_meta(tmp_path, yml)
    dc = dc_bundle(tmp_path / "dc")
    edge = edge_bundle(tmp_path / "edge")
    billing = write_bundle(tmp_path / "billing", {"svc/b.md": page(
        {"type": "Service", "title": "Billing svc", "description": "b"},
        "# Interfaces\n\n| Symbol | Purpose |\n| --- | --- |\n| `SessionService` | Clash. |\n")})
    run_meta("sync", "--root", root, f"dc={dc}", f"edge={edge}", f"billing={billing}")
    derive(root)
    for name in ("dc-services.md", "billing-svc.md"):
        text = (root / "edges/grpc" / name).read_text()
        assert "ambiguous" in text.split("# Contract")[1]
        qs = fm(root / "edges/grpc" / name)["open_questions"]
        assert any(q.startswith("[ambiguous-provider:SessionService]") for q in qs)


def test_no_contracts_no_edges_pages(tmp_path):
    yml = REPOS_YAML.split("contracts:")[0]
    root, _, _ = synced(tmp_path, yml)
    derive(root)
    assert not (root / "edges").exists() or not list((root / "edges").rglob("*-*.md"))
    assert "No cross-repo edges were found" in (root / "components/edge/agents-domain.md").read_text()


# --- rebuild safety --------------------------------------------------------------

def test_rebuild_keeps_human_knowledge(tmp_path):
    root, dc, edge = synced(tmp_path)
    run_meta("init", root)
    derive(root)
    cp = root / "edges/grpc/dc-services.md"
    text = cp.read_text()
    text = re.sub(r"open_questions:\n(  - .*\n)+", 'open_questions:\n  - "Hand-added question."\n', text)
    text += "\n# Notes\n\n<!-- clarified: contract-approval:grpc/dc-services -->\nThe DC team approves.\n"
    cp.write_text(text)
    hand = root / "edges/handwritten.md"
    hand.write_text("---\ntype: Interface\ntitle: Queue\ndescription: A queue contract.\n---\n\n# Summary\n\nQ.\n")
    hand_before = hand.read_bytes()
    derive(root)
    after = cp.read_text()
    assert "The DC team approves." in after
    qs = fm(cp)["open_questions"]
    assert qs == ["Hand-added question."]
    assert hand.read_bytes() == hand_before
    assert "[Queue](handwritten.md)" in (root / "edges/index.md").read_text()


def test_new_question_added_on_rebuild(tmp_path):
    root, dc, edge = synced(tmp_path)
    derive(root)
    cp = root / "edges/grpc/dc-services.md"
    cp.write_text(re.sub(r"open_questions:\n(  - .*\n)+", "", cp.read_text()))
    derive(root)
    assert fm(cp)["open_questions"][0].startswith("[contract-approval:")


def test_stale_page_removed(tmp_path):
    root, dc, edge = synced(tmp_path)
    derive(root)
    hand = root / "edges/grpc/handwritten.md"
    hand.write_text("---\ntype: Interface\ntitle: H\ndescription: h.\n---\n\n# Summary\n\nH.\n")
    for p in (edge / "agents/edge-agent.md", edge / "store/local.md"):
        p.write_text(p.read_text().replace("SessionService", "Nothing").replace("QuotaService", "Nothing"))
    run_meta("sync", "--root", root, f"edge={edge}")
    code, out, _ = derive(root)
    assert not (root / "edges/grpc/dc-services.md").exists()
    assert hand.exists()
    assert "removed 1 stale page" in out


def test_hand_owned_index_kept(tmp_path):
    root, _, _ = synced(tmp_path)
    run_meta("init", root)
    (root / "index.md").write_text('---\nokf_version: "0.1"\n---\n\n# Start here\n\nCurated.\n')
    before = (root / "index.md").read_bytes()
    code, out, _ = derive(root)
    assert (root / "index.md").read_bytes() == before
    assert "kept hand-owned index.md (may be stale)" in out


def test_derive_is_deterministic(tmp_path):
    root, _, _ = synced(tmp_path)
    run_meta("init", root)
    derive(root)
    before = {k: v for k, v in tree(root).items()}
    mtimes = {p: p.stat().st_mtime_ns for p in root.rglob("*.md")}
    time.sleep(0.01)
    derive(root)
    assert tree(root) == before
    assert {p: p.stat().st_mtime_ns for p in root.rglob("*.md")} == mtimes


def test_fresh_meta_validates_after_derive(tmp_path):
    root, _, _ = synced(tmp_path)
    run_meta("init", root)
    derive(root)
    res = validate(root)
    assert res["result"] == "CONFORMANT", res
    bad = [w for w in res["warnings"] if w.split()[0] in ("W2", "W3", "W6", "W10")]
    assert not bad, bad


# --- skill -----------------------------------------------------------------------

def test_skill_routes_to_meta():
    root_skill = (REPO_ROOT / "SKILL.md").read_text()
    asset = REPO_ROOT / "src/catalogify/_skill_assets"
    assert root_skill == (asset / "SKILL.md").read_text()
    desc = " ".join(yaml.safe_load(root_skill.split("---\n")[1])["description"].split())
    for phrase in ("meta repo", "meta bundle", "cross-repo"):
        assert phrase in desc
    assert "`references/meta.md`" in root_skill
    assert "catalogify meta init" in root_skill
    ref = (asset / "references/meta.md").read_text()
    for needle in ("meta init", "repos.yaml", "meta sync", "meta derive", "architecture/overview.md",
                   "clarified:", "validate", "verify", "sparse-checkout"):
        assert needle in ref, needle


def test_speckit_build_has_no_meta_command(tmp_path):
    out = tmp_path / "sk"
    p = subprocess.run([sys.executable, str(REPO_ROOT / "integrations/speckit/build.py"), "--out", str(out)],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert not list((out / "commands").glob("meta*.md"))


# --- performance --------------------------------------------------------------

def test_scale(tmp_path):
    def big(root, prefix, n):
        pages = {}
        for i in range(n):
            pages[f"d{i % 20}/u{i}.md"] = page({
                "type": "Service", "title": f"{prefix} {i}", "description": "x",
                "source_files": [f"src/u{i}/"],
                "relations": [{"kind": "calls", "target": f"src/u{(i + 1) % n}/x.go"}],
            }, f"# Interfaces\n\n| S | P |\n| --- | --- |\n| `{prefix}Svc{i}` | p |\n\n"
               f"# Behaviour\n\nCalls `{'b' if prefix == 'a' else 'a'}Svc{(i * 7) % n}` and "
               + " ".join(f"word{j}Thing" for j in range(30)) + "\n")
        return write_bundle(root, pages)
    yml = REPOS_YAML.replace("dc:", "a:").replace("edge:", "b:")
    root = make_meta(tmp_path, yml, git=False)
    a, b = big(tmp_path / "a", "a", 200), big(tmp_path / "b", "b", 200)
    t = time.time()
    assert run_meta("sync", "--root", root, f"a={a}", f"b={b}")[0] == 0
    assert time.time() - t < 10
    t = time.time()
    assert derive(root)[0] == 0
    assert time.time() - t < 10
