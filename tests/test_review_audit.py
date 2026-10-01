"""Regression checks for repository-review findings and error contracts."""

import json
import subprocess
from pathlib import Path

import pytest

from shipstate.checks.workflows import check_workflows
from shipstate.cli import main


def test_workflow_order_is_deterministic_for_case_collisions(tmp_path, monkeypatch):
    directory = tmp_path / ".github" / "workflows"
    directory.mkdir(parents=True)
    for name in ("A.yml", "a.yml"):
        (directory / name).write_text("run: pip install .\n", encoding="utf-8")
    original = Path.iterdir

    def results(reverse):
        def ordered(path):
            entries = list(original(path))
            return iter(sorted(entries, key=lambda entry: entry.name, reverse=reverse))
        monkeypatch.setattr(Path, "iterdir", ordered)
        return [item.to_dict() for item in check_workflows(tmp_path, "shipstate", "0.1.0")]

    assert results(False) == results(True)


@pytest.mark.parametrize(("contents", "code"), [
    ('[project\n', "invalid_pyproject"),
    ('[project]\nname = "example"\ndynamic = ["version"]\n', "dynamic_version_not_supported"),
])
def test_configuration_errors_preserve_json_contract(tmp_path, capsys, contents, code):
    (tmp_path / "pyproject.toml").write_text(contents, encoding="utf-8")
    assert main(["check", str(tmp_path), "--format", "json"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error"
    assert result["error"]["code"] == code
    assert set(result) == {"shipstate_version", "status", "error"}


def test_unsafe_yaml_constructor_is_rejected_without_execution(project_factory, capsys):
    root = project_factory(workflow=None)
    directory = root / ".github" / "workflows"
    directory.mkdir(parents=True)
    marker = root / "executed"
    (directory / "unsafe.yml").write_text(
        f'!!python/object/apply:builtins.open ["{marker}", "w"]\n', encoding="utf-8"
    )
    assert main(["check", str(root), "--format", "json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "workflow_invalid_yaml"
    assert not marker.exists()


def test_git_timeout_preserves_json_error(project_factory, monkeypatch, capsys):
    root = project_factory()

    def timeout(args, **kwargs):
        assert isinstance(args, list)
        assert kwargs["timeout"] == 10
        assert not kwargs.get("shell", False)
        raise subprocess.TimeoutExpired(args, kwargs["timeout"])

    monkeypatch.setattr("shipstate.git.subprocess.run", timeout)
    assert main(["check", str(root), "--format", "json"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error"
    assert result["error"]["code"] == "git_timeout"
