import json

import pytest
from conftest import git

from shipstate import __version__
from shipstate.checks.runner import check_project
from shipstate.cli import main


def test_missing_license_and_build_system_are_warnings(project_factory):
    root = project_factory(license_file=False, build_system=False)

    result = check_project(root)

    severities = {item.code: item.severity for item in result.findings}
    assert severities["license_missing"] == "warn"
    assert severities["build_system_missing"] == "warn"
    assert result.status == "pass"


def test_empty_license_is_treated_as_missing(project_factory):
    root = project_factory()
    (root / "LICENSE").write_text("", encoding="utf-8")

    result = check_project(root)

    assert next(item for item in result.findings if item.code == "license_missing").severity == "warn"


@pytest.mark.parametrize(
    ("build_system", "expected_codes"),
    [
        ('build-backend = "setuptools.build_meta"\n', {"build_system_requires_missing"}),
        ('requires = ["setuptools"]\n', {"build_backend_missing"}),
        ("", {"build_system_requires_missing", "build_backend_missing"}),
    ],
)
def test_missing_build_system_fields_are_warnings_with_exit_zero(
    project_factory, capsys, build_system, expected_codes
):
    root = project_factory()
    pyproject = root / "pyproject.toml"
    original = pyproject.read_text(encoding="utf-8")
    project_table = original.split("\n[build-system]\n", 1)[0]
    pyproject.write_text(project_table + "\n\n[build-system]\n" + build_system, encoding="utf-8")
    git(root, "add", "pyproject.toml")
    git(root, "commit", "--amend", "--no-edit")
    git(root, "tag", "-f", "v0.2.1")

    result = check_project(root)
    build_findings = [item for item in result.findings if item.code.startswith("build_")]

    assert result.status == "pass"
    assert {item.code for item in build_findings} == expected_codes
    assert all(item.severity == "warn" for item in build_findings)
    assert main(["check", str(root), "--format", "json"]) == 0
    cli_result = json.loads(capsys.readouterr().out)
    assert cli_result["status"] == "pass"


def test_dynamic_workflow_warning_only_has_pass_status_and_exit_zero(project_factory, capsys):
    root = project_factory(workflow="run: pip install meshcontract==$VERSION\n")

    exit_code = main(["check", str(root), "--format", "json"])
    result = json.loads(capsys.readouterr().out)
    warning = next(item for item in result["findings"] if item["code"] == "workflow_dynamic_version")

    assert exit_code == 0
    assert result["status"] == "pass"
    assert warning["severity"] == "warn"
    assert warning["actual"] == "$VERSION"
    assert warning["expected"] == "0.2.1"


def test_text_output_and_success_exit_code(project_factory, capsys):
    root = project_factory()

    exit_code = main(["check", str(root)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert f"ShipState {__version__}" in output
    assert "Project: meshcontract" in output
    assert "PASS git tag: v0.2.1" in output
    assert "Release consistency: PASS" in output


def test_failure_has_exit_code_one(project_factory, capsys):
    root = project_factory(readme="pip install meshcontract==0.2.0\n")

    exit_code = main(["check", str(root)])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "FAIL README pin: meshcontract==0.2.0" in output
    assert "Release consistency: FAIL" in output


def test_json_output_has_stable_result_shape(project_factory, capsys):
    root = project_factory(readme="pip install meshcontract==0.2.0\n")

    exit_code = main(["check", str(root), "--format", "json"])
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert result["shipstate_version"] == __version__
    assert result["status"] == "fail"
    assert result["project"] == {"name": "meshcontract", "version": "0.2.1"}
    drift = next(item for item in result["findings"] if item["code"] == "readme_version_drift")
    assert drift == {
        "code": "readme_version_drift",
        "severity": "fail",
        "source": "README.md",
        "message": "README.md pins meshcontract to 0.2.0; expected 0.2.1.",
        "actual": "0.2.0",
        "expected": "0.2.1",
    }


def test_json_input_error_has_exit_code_two(tmp_path, capsys):
    exit_code = main(["check", str(tmp_path), "--format", "json"])
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert result["status"] == "error"
    assert result["error"]["code"] == "pyproject_missing"


def test_non_git_directory_has_exit_code_two(tmp_path, capsys):
    root = tmp_path / "project"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )

    exit_code = main(["check", str(root), "--format", "json"])
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert result["error"]["code"] == "not_git_repository"


def test_version_and_help_options(capsys):
    with pytest.raises(SystemExit) as version_exit:
        main(["--version"])
    assert version_exit.value.code == 0
    assert capsys.readouterr().out.strip() == f"ShipState {__version__}"

    with pytest.raises(SystemExit) as help_exit:
        main(["--help"])
    assert help_exit.value.code == 0
    assert "check" in capsys.readouterr().out


def test_warnings_are_allowed_with_exit_code_zero(project_factory, capsys):
    root = project_factory(license_file=False, build_system=False)

    exit_code = main(["check", str(root)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "WARN license: LICENSE not found" in output
    assert "WARN build system:" in output
    assert "Release consistency: PASS" in output
