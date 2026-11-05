"""The ontology layer: typed relations, playbooks and guardrails.

One fixture repository where a model, its generated client and a version file
always change together, plus a bundle that states those facts as typed
relations. Each test changes one concept and checks that verify, validate,
cochange or find react to exactly that.
"""
import json
import sys
from pathlib import Path

import pytest

from okf_fixtures import SCRIPTS, Repo, run, validate, verify

pytest.importorskip("yaml")  # relations are nested YAML; the fallback parser cannot read them


def build(root: Path):
    r = Repo(root)
    r.write("src/api/models.py", "class Order:\n    pass\n")
    r.write("gen/client_gen.py", "# generated from src/api/models.py\nORDER = {}\n")
    r.write("versions/v2.py", "CHANGES = []\n")
    c1 = r.commit("Add order model")
    r.write("src/api/models.py", "class Order:\n    total = 0\n")
    r.write("gen/client_gen.py", "# generated from src/api/models.py\nORDER = {'total': 0}\n")
    r.write("versions/v2.py", "CHANGES = ['total']\n")
    c2 = r.commit("Add Order.total")
    r.write("src/api/models.py", "class Order:\n    total = 0\n    note = ''\n")
    r.write("gen/client_gen.py", "# generated from src/api/models.py\nORDER = {'total': 0, 'note': ''}\n")
    r.write("versions/v2.py", "CHANGES = ['total', 'note']\n")
    c3 = r.commit("Add Order.note")
    r.write("src/api/client.py", "from src.api.models import Order\n\n\ndef fetch():\n    return Order()\n")
    r.write("src/api/settings_reader.py", "PATH = 'config/settings.yml'\n")
    r.write("config/settings.yml", "timeout: 3\n")
    r.write("tests/test_no_shell.py", "def test_no_shell():\n    assert True\n")
    c4 = r.commit("Add client, settings and the no-shell test")
    return r, {"c1": c1, "c2": c2, "c3": c3, "c4": c4}


def concept(r, rel, front, body="# Responsibilities\n\nDoes a thing.\n"):
    r.write(f"knowledge/{rel}", f"---\n{front.strip()}\n---\n\n{body}")


def bundle(r, c):
    r.write("knowledge/index.md", '---\nokf_version: "0.1"\n---\n\n# Modules\n')
    concept(r, "modules/api-models.md", f"""
type: Module
title: API models
description: The order model.
source_files: [src/api/models.py]
relations:
  - {{kind: versioned_by, target: versions/v2.py, evidence: [{c['c2']}, {c['c3']}]}}
  - {{kind: changes_with, target: gen/, evidence: [{c['c3']}]}}
""")
    concept(r, "modules/generated-client.md", f"""
type: Module
title: Generated client
description: Client code generated from the models.
source_files: [gen/client_gen.py]
relations:
  - {{kind: generated_from, target: src/api/models.py, evidence: [{c['c2']}]}}
""")
    concept(r, "modules/api-client.md", """
type: Module
title: API client
description: Fetches orders.
source_files: [src/api/client.py]
relations:
  - {kind: calls, target: src/api/models.py}
""")
    concept(r, "modules/settings.md", """
type: Module
title: Settings reader
description: Reads the settings file.
source_files: [src/api/settings_reader.py]
relations:
  - {kind: reads_config, target: config/settings.yml}
""")
    concept(r, "operations/playbooks/add-model-field.md", f"""
type: Playbook
title: Add a field to a model
description: What else moves when a model gains a field.
applies_to: [src/api/models.py]
relations:
  - {{kind: requires, target: versions/, evidence: [{c['c2']}]}}
  - {{kind: requires, target: gen/, evidence: [{c['c3']}]}}
""", "# Steps\n\n1. Edit the model.\n2. Add a version entry in versions/.\n3. Regenerate gen/.\n")
    concept(r, "operations/guardrails/no-shell.md", f"""
type: Guardrail
title: No shell execution in the API
description: The API never shells out.
applies_to: [src/]
rule: Code under src/ never runs a shell; use argument lists.
motivated_by: [{c['c4']}]
enforced_by: [tests/test_no_shell.py]
forbids:
  - {{pattern: "shell=True", in: [src/]}}
""")
    return Path(r.root) / "knowledge"


@pytest.fixture
def repo(tmp_path):
    r, c = build(tmp_path / "repo")
    b = bundle(r, c)
    return r, c, b


def verified(b):
    code, out, err = verify(b, json_out=True)
    assert out, err
    return code, json.loads(out)


def test_valid_bundle_verifies_clean(repo):
    _, _, b = repo
    code, res = verified(b)
    assert res["findings"] == [], res
    assert res["notes"] == [], res
    assert code == 0


def test_unknown_kind_is_v9(repo):
    r, c, b = repo
    concept(r, "modules/api-client.md", """
type: Module
title: API client
description: Fetches orders.
source_files: [src/api/client.py]
relations:
  - {kind: depends_on_somehow, target: src/api/models.py}
""")
    _, res = verified(b)
    assert any(f.startswith("V9 modules/api-client.md") and "depends_on_somehow" in f
               for f in res["findings"]), res


def test_requires_outside_playbook_is_v9(repo):
    r, c, b = repo
    concept(r, "modules/api-client.md", f"""
type: Module
title: API client
description: Fetches orders.
source_files: [src/api/client.py]
relations:
  - {{kind: requires, target: versions/, evidence: [{c['c2']}]}}
""")
    _, res = verified(b)
    assert any(f.startswith("V9 modules/api-client.md") and "Playbook" in f for f in res["findings"])


def test_untracked_target_is_v10(repo):
    r, c, b = repo
    (Path(r.root) / "scratch").mkdir()
    (Path(r.root) / "scratch" / "x.py").write_text("x = 1\n")
    concept(r, "modules/generated-client.md", f"""
type: Module
title: Generated client
description: Client code generated from the models.
source_files: [gen/client_gen.py]
relations:
  - {{kind: generated_from, target: scratch/x.py, evidence: [{c['c2']}]}}
""")
    _, res = verified(b)
    assert any(f.startswith("V10 modules/generated-client.md") for f in res["findings"]), res


def test_evidence_not_touching_target_is_v11(repo):
    r, c, b = repo
    # c4 touched src/api/ and config/, never gen/client_gen.py's partner versions/.
    concept(r, "modules/generated-client.md", f"""
type: Module
title: Generated client
description: Client code generated from the models.
source_files: [gen/client_gen.py]
relations:
  - {{kind: generated_from, target: versions/v2.py, evidence: [{c['c4']}]}}
""")
    _, res = verified(b)
    assert any(f.startswith("V11 modules/generated-client.md") for f in res["findings"]), res


def test_relation_without_evidence_is_v11(repo):
    r, c, b = repo
    concept(r, "modules/api-models.md", """
type: Module
title: API models
description: The order model.
source_files: [src/api/models.py]
relations:
  - {kind: versioned_by, target: versions/v2.py}
""")
    _, res = verified(b)
    assert any(f.startswith("V11 modules/api-models.md") and "cites no evidence" in f
               for f in res["findings"]), res


def test_unknown_evidence_sha_is_v1(repo):
    r, c, b = repo
    concept(r, "modules/api-models.md", """
type: Module
title: API models
description: The order model.
source_files: [src/api/models.py]
relations:
  - {kind: versioned_by, target: versions/v2.py, evidence: [deadbeefdeadbeef]}
""")
    _, res = verified(b)
    assert any(f.startswith("V1 modules/api-models.md") for f in res["findings"]), res


def test_calls_without_import_is_v11(repo):
    r, c, b = repo
    concept(r, "modules/settings.md", """
type: Module
title: Settings reader
description: Reads the settings file.
source_files: [src/api/settings_reader.py]
relations:
  - {kind: calls, target: gen/client_gen.py}
""")
    _, res = verified(b)
    assert any(f.startswith("V11 modules/settings.md") for f in res["findings"]), res


def test_playbook_without_steps_is_v12_note(repo):
    r, c, b = repo
    concept(r, "operations/playbooks/add-model-field.md", f"""
type: Playbook
title: Add a field to a model
description: What else moves when a model gains a field.
applies_to: [src/api/models.py]
relations:
  - {{kind: requires, target: versions/, evidence: [{c['c2']}]}}
""", "Just do it.\n")
    code, res = verified(b)
    assert res["findings"] == []
    assert any(n.startswith("V12 operations/playbooks/add-model-field.md") for n in res["notes"])
    assert code == 0


def test_guardrail_violation_is_v13(repo):
    r, c, b = repo
    r.write("src/api/run.py", "import subprocess\nsubprocess.run('ls', shell=True)\n")
    r.commit("Shell out", "src/api/run.py")
    _, res = verified(b)
    assert any(f.startswith("V13 operations/guardrails/no-shell.md") and "src/api/run.py" in f
               for f in res["findings"]), res


def test_guardrail_pattern_in_tests_is_ignored(repo):
    r, c, b = repo
    r.write("tests/test_shell_detect.py", "BAD = 'shell=True'\n")
    r.commit("Test fixture mentions the pattern", "tests/test_shell_detect.py")
    _, res = verified(b)
    assert res["findings"] == [], res


def test_guardrail_motivation_must_touch_scope_v13(repo):
    r, c, b = repo
    r.write("docs/notes.md", "notes\n")
    off = r.commit("Docs only", "docs/notes.md")
    concept(r, "operations/guardrails/no-shell.md", f"""
type: Guardrail
title: No shell execution in the API
description: The API never shells out.
applies_to: [src/]
rule: Code under src/ never runs a shell.
motivated_by: [{off}]
enforced_by: [tests/test_no_shell.py]
""")
    _, res = verified(b)
    assert any(f.startswith("V13 operations/guardrails/no-shell.md") and "motivated_by" in f
               for f in res["findings"]), res


def test_unenforced_guardrail_is_v14_note(repo):
    r, c, b = repo
    concept(r, "operations/guardrails/no-shell.md", """
type: Guardrail
title: No shell execution in the API
description: The API never shells out.
applies_to: [src/]
rule: Code under src/ never runs a shell.
""")
    code, res = verified(b)
    assert any(n.startswith("V14 operations/guardrails/no-shell.md") for n in res["notes"]), res
    assert code == 0


def test_malformed_relations_are_w12(repo):
    r, c, b = repo
    concept(r, "modules/api-client.md", """
type: Module
title: API client
description: Fetches orders.
source_files: [src/api/client.py]
relations: src/api/models.py
""")
    concept(r, "operations/guardrails/no-shell.md", """
type: Guardrail
title: No shell execution in the API
description: The API never shells out.
""")
    code, out, err = validate(b, json_out=True)
    warnings = json.loads(out)["warnings"]
    assert any(w.startswith("W12 modules/api-client.md") for w in warnings), warnings
    assert any(w.startswith("W12 operations/guardrails/no-shell.md") and "applies_to" in w
               for w in warnings), warnings
    assert any(w.startswith("W12 operations/guardrails/no-shell.md") and "rule" in w
               for w in warnings), warnings


def test_cochange_evidence_lists_shas(repo):
    r, c, b = repo
    code, out, err = run([sys.executable, str(SCRIPTS / "okf-cochange.py"), "src/api/models.py",
                          "--evidence", "5", "--min-support", "2", "--json"], r.root)
    assert code == 0, err
    rows = json.loads(out)["units"][0]["changes_with"]
    gen = next(row for row in rows if row["unit"] == "gen")
    assert gen["support"] == 3
    assert set(gen["commits"]) == {c[k][:10] for k in ("c1", "c2", "c3")}


def test_cochange_without_evidence_has_no_commits_key(repo):
    r, c, b = repo
    code, out, err = run([sys.executable, str(SCRIPTS / "okf-cochange.py"), "src/api/models.py",
                          "--min-support", "2", "--json"], r.root)
    assert all("commits" not in row for row in json.loads(out)["units"][0]["changes_with"])


def find(r, *paths):
    code, out, err = run([sys.executable, str(SCRIPTS / "okf_find.py"), *paths, "--json"], r.root)
    assert code == 0, err
    return json.loads(out)["results"]


def test_find_answers_for_a_model_file(repo):
    r, c, b = repo
    (res,) = find(r, "src/api/models.py")
    assert [g["title"] for g in res["guardrails"]] == ["No shell execution in the API"]
    assert [x["title"] for x in res["concepts"]] == ["API models"]
    kinds = {(x["kind"], x["target"]) for x in res["concepts"][0]["relations"]}
    assert ("versioned_by", "versions/v2.py") in kinds
    incoming = {(i["kind"], i["concept"]) for i in res["incoming"]}
    assert ("generated_from", "modules/generated-client.md") in incoming
    assert ("calls", "modules/api-client.md") in incoming
    (pb,) = res["playbooks"]
    assert pb["requires"] == ["versions", "gen"]
    assert "Regenerate gen/" in pb["steps"]


def test_find_text_lists_guardrails_first(repo):
    r, c, b = repo
    code, out, err = run([sys.executable, str(SCRIPTS / "okf_find.py"), "src/api/models.py"], r.root)
    body = [ln.strip() for ln in out.splitlines()[1:] if ln.strip()]
    assert body[0].startswith("GUARDRAIL"), out


def test_find_unknown_path_is_empty_not_an_error(repo):
    r, c, b = repo
    (res,) = find(r, "nowhere/at/all.py")
    assert not any(res[k] for k in ("guardrails", "concepts", "incoming", "playbooks"))


def test_scripts_import_their_sibling_from_any_cwd(repo, tmp_path):
    """runner.py runs scripts by path; okf_bundle must resolve from the script's own dir."""
    r, c, b = repo
    code, out, err = run([sys.executable, str(SCRIPTS / "okf_find.py"), "--bundle", str(b),
                          "--repo-root", str(r.root), "src/api/models.py"], tmp_path)
    assert code == 0, err
