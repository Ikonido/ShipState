"""External input symlinks must not let the checker read unrelated files."""

import json
from pathlib import Path

import pytest

from shipstate.cli import main

FILES = ("pyproject.toml", "README.md", "CHANGELOG.md", "LICENSE", "LICENSE.md", "LICENSE.txt")


@pytest.mark.parametrize("name", FILES)
@pytest.mark.parametrize("missing", [False, True])
def test_external_input_symlink_is_json_error_without_reading(
    project_factory, tmp_path, monkeypatch, capsys, name, missing
):
    root = project_factory(license_file=not name.startswith("LICENSE"))
    target = tmp_path / "outside.txt"
    if not missing:
        target.write_text("This file must not be read.\n", encoding="utf-8")
    path = root / name
    path.unlink(missing_ok=True)
    path.symlink_to(target)
    original = Path.read_text

    def guarded_read(path, *args, **kwargs):
        assert path.resolve() != target, "External file contents were read"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read)
    assert main(["check", str(root), "--format", "json"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert set(result) == {"shipstate_version", "status", "error"}
    assert result["status"] == "error"
    assert result["error"]["code"] == "project_file_outside_project"
    assert name in result["error"]["message"]


@pytest.mark.parametrize("name", FILES)
def test_internal_input_symlink_remains_supported(project_factory, capsys, name):
    root = project_factory(license_file=not name.startswith("LICENSE"))
    path = root / name
    contents = path.read_text() if path.exists() else "MIT License\n"
    target = root / "inputs" / name
    target.parent.mkdir()
    target.write_text(contents, encoding="utf-8")
    path.unlink(missing_ok=True)
    path.symlink_to(target)
    assert main(["check", str(root), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "pass"


def test_symlinked_project_root_remains_supported(project_factory, tmp_path, capsys):
    root = project_factory()
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    assert main(["check", str(alias), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "pass"


@pytest.mark.parametrize("name", FILES)
def test_cyclic_file_symlink_is_json_error(project_factory, capsys, name):
    root = project_factory(license_file=not name.startswith("LICENSE"))
    path = root / name
    path.unlink(missing_ok=True)
    path.symlink_to(name)
    assert main(["check", str(root), "--format", "json"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error"
    assert result["error"]["code"] == "project_file_unresolvable"
