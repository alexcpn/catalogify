"""Windows bash lookup, simulated: paths are faked, the OS is not."""
import pytest

from catalogify import runner

STUB = r"C:\Windows\System32\bash.exe"


@pytest.fixture
def fake(monkeypatch, tmp_path):
    """Point shutil.which at chosen paths; no default install locations."""
    found = {}
    monkeypatch.setattr(runner.shutil, "which", lambda name: found.get(name))
    monkeypatch.setattr(runner, "_WINDOWS_BASH_CANDIDATES", ())

    def make(rel):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")
        return str(p)
    return found, make, monkeypatch


@pytest.mark.parametrize("git_rel", ["Git/cmd/git.exe", "Git/bin/git.exe", "Git/mingw64/bin/git.exe"])
def test_git_for_windows_beats_wsl_stub_on_path(fake, git_rel):
    found, make, _ = fake
    bash = make("Git/bin/bash.exe")
    found.update(git=make(git_rel), bash=STUB)
    assert runner._find_windows_bash() == bash


@pytest.mark.parametrize("stub", [STUB, r"C:\Users\me\AppData\Local\Microsoft\WindowsApps\bash.exe"])
def test_wsl_launchers_are_never_used(fake, stub):
    found, _, _ = fake
    found["bash"] = stub
    assert runner._find_windows_bash() is None


def test_default_install_location(fake):
    found, make, monkeypatch = fake
    bash = make("Program Files/Git/bin/bash.exe")
    monkeypatch.setattr(runner, "_WINDOWS_BASH_CANDIDATES", ("", bash))
    found["bash"] = STUB
    assert runner._find_windows_bash() == bash


def test_other_bash_on_path_is_last_resort(fake):
    found, _, _ = fake
    found["bash"] = r"D:\msys64\usr\bin\bash.exe"
    assert runner._find_windows_bash() == found["bash"]
