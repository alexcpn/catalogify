"""Write the T1 golden files from a given copy of the scripts.

Run once against the 0.9.2 scripts, never against the working tree:

    git show v0.9.2-ref:src/catalogify/_scripts/<f> > /some/dir/<f>   # each script
    python3 tests/golden/make_golden.py /some/dir

Regenerating from the current scripts would make T1 compare the code with itself.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from okf_fixtures import FIXTURES, snapshot_fixture  # noqa: E402


def main():
    scripts = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        for name in FIXTURES:
            snap = snapshot_fixture(name, Path(tmp), scripts)
            (HERE / f"{name}.json").write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n")
            print(f"wrote {name}.json")


if __name__ == "__main__":
    main()
