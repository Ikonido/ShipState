import json

import pytest

from shipstate.checks.runner import check_project
from shipstate.cli import main
from conftest import git


def codes(result):
    return {item.code for item in result.findings}


@pytest.mark.parametrize("name, other", [("shipstate", "ship-state"), ("ship-state", "shipstate")])
def test_names_without_separators_are_different_distributions(project_factory, name, other):
    root = project_factory(name=name, readme=f"pip install {other}==0.0.1\n", workflow=f"run: pip install {other}==0.0.1\n")
    assert "readme_version_drift" not in codes(check_project(root))
    assert "workflow_version_drift" not in codes(check_project(root))


@pytest.mark.parametrize("workflow", [
    'run: "pip install requests # meshcontract==0.0.1"\n',
    'name: pip install meshcontract==0.0.1\n',
    'run: echo "pip install meshcontract==0.0.1"\n',
    'run: pip install requests && echo meshcontract==0.0.1\n',
    'jobs:\n  test:\n    name: pip install meshcontract==0.0.1\n    steps:\n      - run: echo ok\n',
])
def test_workflow_metadata_comments_and_echoes_are_not_installs(project_factory, workflow):
    result = check_project(project_factory(workflow=workflow))
    assert "workflow_version_drift" not in codes(result)


def test_full_workflow_yaml_folded_run_is_checked(project_factory):
    result = check_project(project_factory(workflow=(
        'on: [push]\njobs:\n  test:\n    steps:\n      - run: >\n          python -m pip install\n          meshcontract[dev]==0.0.1\n'
    )))
    assert "workflow_version_drift" in codes(result)


@pytest.mark.parametrize("flag", ["-r requirements.txt", "-rrequirements.txt", "--requirement=requirements.txt"])
def test_workflow_checks_local_requirement_pins(project_factory, flag):
    root = project_factory(workflow=f"run: python -m pip install {flag}\n")
    (root / "requirements.txt").write_text('meshcontract[dev]==0.0.1 ; python_version >= "3.11"\n')
    result = check_project(root)
    drift = next(item for item in result.findings if item.code == "workflow_version_drift")
    assert drift.source == "requirements.txt"
    assert drift.actual == "0.0.1"


def test_nested_requirements_resolve_from_including_file(project_factory):
    root = project_factory(workflow="run: pip install -r ci/requirements.txt\n")
    (root / "ci").mkdir()
    (root / "ci/requirements.txt").write_text('-r "more requirements.txt"\n')
    (root / "ci/more requirements.txt").write_text("meshcontract==0.0.1 --hash=sha256:abc\n")
    assert "workflow_version_drift" in codes(check_project(root))


@pytest.mark.parametrize("level", ["step", "job", "workflow"])
def test_requirements_respect_static_working_directory(project_factory, level):
    defaults = "defaults:\n  run:\n    working-directory: sub\n"
    workflow = (defaults if level == "workflow" else "") + "jobs:\n  test:\n"
    if level == "job":
        workflow += "    defaults:\n      run:\n        working-directory: sub\n"
    workflow += "    steps:\n      - run: pip install -r requirements.txt\n"
    if level == "step":
        workflow += "        working-directory: sub\n"
    root = project_factory(workflow=workflow)
    (root / "sub").mkdir()
    (root / "sub/requirements.txt").write_text("meshcontract==0.0.1\n")
    assert "workflow_version_drift" in codes(check_project(root))


@pytest.mark.parametrize("reference", ["missing.txt", "$REQUIREMENTS", "https://example.invalid/requirements.txt", "../outside.txt"])
def test_unresolved_requirements_are_explicit_warnings(project_factory, reference):
    result = check_project(project_factory(workflow=f"run: pip install -r {reference}\n"))
    assert "workflow_requirements_unchecked" in codes(result)
    warning = next(item for item in result.findings if item.code == "workflow_requirements_unchecked")
    assert warning.severity == "warn"


def test_cyclic_requirement_includes_warn_without_recursing_forever(project_factory):
    root = project_factory(workflow="run: pip install -r a.txt\n")
    (root / "a.txt").write_text("-r b.txt\n")
    (root / "b.txt").write_text("-r a.txt\n")
    assert "workflow_requirements_unchecked" in codes(check_project(root))


def test_malformed_workflow_is_a_json_input_error(project_factory, capsys):
    root = project_factory(workflow="jobs: [\n")
    assert main(["check", str(root), "--format", "json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "workflow_invalid_yaml"


@pytest.mark.parametrize("change", ["unstaged", "staged", "untracked"])
def test_uncommitted_changes_warn_even_when_tag_matches_head(project_factory, change):
    root = project_factory()
    path = root / ("new.py" if change == "untracked" else "README.md")
    path.write_text("uncommitted\n")
    if change == "staged":
        git(root, "add", str(path))
    result = check_project(root)
    assert next(item for item in result.findings if item.code == "git_worktree_dirty").severity == "warn"
    assert "version_tag_matches_head" in codes(result)


@pytest.mark.parametrize("backend_path", ["../outside", "/tmp", "missing", "C:/outside"])
def test_invalid_backend_path_fails(project_factory, backend_path):
    root = project_factory()
    pyproject = root / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + f'backend-path = ["{backend_path}"]\n')
    assert "build_system_invalid" in codes(check_project(root))


def test_backend_path_cannot_escape_through_symlink(project_factory, tmp_path):
    root = project_factory()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "backend").symlink_to(outside, target_is_directory=True)
    path = root / "pyproject.toml"
    path.write_text(path.read_text() + 'backend-path = ["backend"]\n')
    assert "build_system_invalid" in codes(check_project(root))


def test_existing_in_project_backend_path_passes(project_factory):
    root = project_factory()
    (root / "backend").mkdir()
    path = root / "pyproject.toml"
    path.write_text(path.read_text() + 'backend-path = ["backend"]\n')
    assert "build_system_present" in codes(check_project(root))
