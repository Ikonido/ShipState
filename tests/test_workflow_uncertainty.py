"""Behavior invariants for supported pins, uncertain installs and path containment."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from shipstate.checks.workflows import check_workflows
from shipstate.cli import main

NAME = "shipstate"
VERSION = "0.1.0"


def workflow(tmp_path, script, *, shell="bash", runner="ubuntu-latest"):
    root = tmp_path / "project"
    directory = root / ".github" / "workflows"
    directory.mkdir(parents=True, exist_ok=True)
    document = {"jobs": {"test": {"runs-on": runner, "steps": [{"run": script}]}}}
    if shell is not None:
        document["jobs"]["test"]["steps"][0]["shell"] = shell
    (directory / "ci.yml").write_text(yaml.safe_dump(document))
    return root


def findings(root):
    return check_workflows(root, NAME, VERSION)


def assert_uncertain(result, code):
    assert any(item.code == code and item.severity == "warn" for item in result)
    assert not any(item.severity in {"fail", "pass"} for item in result)


@pytest.mark.parametrize("expression", [
    "${{ env.VERSION }}", "${{ github.ref_name }}", "${{ env.VERSION || '0.1.0' }}",
    "${{ inputs.version }}", "${{ env.VERSION && inputs.version || '0.0.1' }}",
    "${{ inputs.number > 1 && '0.0.1' || '0.1.0' }}", "$VERSION", "${VERSION}",
])
def test_dynamic_versions_are_opaque_and_warn_without_static_pin(tmp_path, expression):
    root = workflow(tmp_path, f"pip install shipstate=={expression}")
    result = findings(root)
    assert_uncertain(result, "workflow_dynamic_version")
    assert next(item for item in result if item.code == "workflow_dynamic_version").actual == expression


@pytest.mark.parametrize("shell", ["pwsh", "powershell", "cmd", "cmd.exe", "python", "fish", True])
def test_unsupported_shell_does_not_apply_posix_rules(tmp_path, shell):
    root = workflow(tmp_path, "pip install shipstate==0.0.1", shell=shell)
    assert_uncertain(findings(root), "workflow_shell_not_supported")


@pytest.mark.parametrize("level", ["workflow", "job", "step"])
def test_shell_defaults_are_respected(tmp_path, level):
    root = workflow(tmp_path, "pip install shipstate==0.0.1", shell=None)
    path = root / ".github/workflows/ci.yml"
    document = yaml.safe_load(path.read_text())
    job = document["jobs"]["test"]
    if level == "workflow":
        document["defaults"] = {"run": {"shell": "pwsh"}}
    elif level == "job":
        job["defaults"] = {"run": {"shell": "cmd"}}
    else:
        document["defaults"] = {"run": {"shell": "bash"}}
        job["defaults"] = {"run": {"shell": "sh"}}
        job["steps"][0]["shell"] = "pwsh"
    path.write_text(yaml.safe_dump(document))
    assert_uncertain(findings(root), "workflow_shell_not_supported")


def test_supported_step_shell_overrides_unsupported_defaults(tmp_path):
    root = workflow(tmp_path, "pip install shipstate==0.0.1", shell="bash", runner="windows-latest")
    path = root / ".github/workflows/ci.yml"
    document = yaml.safe_load(path.read_text())
    document["defaults"] = {"run": {"shell": "pwsh"}}
    document["jobs"]["test"]["defaults"] = {"run": {"shell": "cmd"}}
    path.write_text(yaml.safe_dump(document))
    assert any(item.code == "workflow_version_drift" for item in findings(root))


@pytest.mark.parametrize("runner", ["windows-latest", "${{ matrix.os }}", ["self-hosted"]])
def test_unknown_or_windows_default_shell_warns(tmp_path, runner):
    root = workflow(tmp_path, "pip install shipstate==0.0.1", shell=None, runner=runner)
    assert_uncertain(findings(root), "workflow_shell_not_supported")


@pytest.mark.parametrize("script", [
    'echo "&&" pip install shipstate==0.0.1',
    "echo 'pip install shipstate==0.0.1'",
    r"echo \&\& pip install shipstate==0.0.1",
    'printf "%s" "pip install shipstate==0.0.1"',
    "pip install requests --index-url https://example.invalid/shipstate==0.0.1",
])
def test_quoted_operators_echoes_and_option_values_do_not_invent_installs(tmp_path, script):
    result = findings(workflow(tmp_path, script))
    assert not any(item.code in {"workflow_version_drift", "workflow_pin_matches"} for item in result)
    assert not any(item.severity == "fail" for item in result)


@pytest.mark.parametrize("script", [
    "cat <<EOF\npip install shipstate==0.0.1\nEOF",
    "cat <<'EOF'\npip install shipstate==0.0.1\nEOF",
    "echo 'documentation\npip install shipstate==0.0.1\n'",
    "if test -f optional; then pip install shipstate==0.0.1; fi",
    "example() { echo documentation; pip install shipstate==0.0.1; }",
    "alias pip=echo; pip install shipstate==0.0.1",
    "source setup.sh && pip install -r requirements.txt",
])
def test_documentation_and_complex_flow_warn_instead_of_false_fail(tmp_path, script):
    assert_uncertain(findings(workflow(tmp_path, script)), "workflow_shell_ambiguous")


@pytest.mark.parametrize("change", ["cd subdir &&", "pushd subdir;", "Set-Location subdir;", "cd subdir\n"])
@pytest.mark.parametrize("root_version, subdir_version", [("0.0.1", VERSION), (VERSION, "0.0.1")])
def test_cwd_changes_never_read_requirements_using_the_old_directory(tmp_path, change, root_version, subdir_version):
    root = workflow(tmp_path, f"{change} pip install -r requirements.txt")
    (root / "subdir").mkdir()
    (root / "requirements.txt").write_text(f"shipstate=={root_version}\n")
    (root / "subdir/requirements.txt").write_text(f"shipstate=={subdir_version}\n")
    original = Path.read_text

    def read(path, *args, **kwargs):
        assert path.name != "requirements.txt", "Ambiguous cwd must not trigger a guessed file read"
        return original(path, *args, **kwargs)

    with patch.object(Path, "read_text", read):
        assert_uncertain(findings(root), "workflow_working_directory_ambiguous")


@pytest.mark.parametrize("reference", ["-c constraints.txt", "--constraint constraints.txt", "--constraint=constraints.txt", "-cconstraints.txt"])
def test_constraint_only_self_pin_is_not_an_install(tmp_path, reference):
    root = workflow(tmp_path, f"pip install requests {reference}")
    (root / "constraints.txt").write_text("shipstate==0.0.1\n")
    assert not any(item.code == "workflow_version_drift" for item in findings(root))


@pytest.mark.parametrize("pin, expected", [(VERSION, "workflow_pin_matches"), ("0.0.1", "workflow_version_drift")])
def test_explicit_bare_self_request_can_use_an_exact_constraint(tmp_path, pin, expected):
    root = workflow(tmp_path, "pip install shipstate -c constraints.txt")
    (root / "constraints.txt").write_text(f"shipstate=={pin}\n")
    assert any(item.code == expected for item in findings(root))


def test_constraints_nested_in_requirements_do_not_request_the_self_package(tmp_path):
    root = workflow(tmp_path, "pip install -r requirements.txt")
    (root / "requirements.txt").write_text("requests\n-c constraints.txt\n")
    (root / "constraints.txt").write_text("shipstate==0.0.1\n")
    assert not any(item.code == "workflow_version_drift" for item in findings(root))


def test_constraint_relevance_is_scoped_to_one_pip_command(tmp_path):
    root = workflow(tmp_path, "pip install requests -c constraints.txt && pip install shipstate")
    (root / "constraints.txt").write_text("shipstate==0.0.1\n")
    assert_uncertain(findings(root), "workflow_version_not_exact")


@pytest.mark.parametrize("script, constraints", [
    ("pip install shipstate==0.1.0 -c constraints.txt", "shipstate==0.0.1\n"),
    ("pip install shipstate -c constraints.txt", "shipstate==0.0.1\nshipstate==0.1.0\n"),
    ("pip install shipstate -c constraints.txt", 'shipstate==0.0.1 ; sys_platform == "win32"\n'),
])
def test_conflicting_or_conditional_constraints_are_not_proof_of_version(tmp_path, script, constraints):
    root = workflow(tmp_path, script)
    (root / "constraints.txt").write_text(constraints)
    assert_uncertain(findings(root), "workflow_version_not_exact")


@pytest.mark.parametrize("entry", [
    "shipstate>=0.1", "shipstate~=0.1", "shipstate<1", "shipstate!=0.1.0",
    "shipstate==0.1.*", "shipstate @ https://example.invalid/package.whl",
])
@pytest.mark.parametrize("in_file", [False, True])
def test_non_exact_self_requirements_warn_in_commands_and_files(tmp_path, entry, in_file):
    root = workflow(tmp_path, "pip install -r requirements.txt" if in_file else f'pip install "{entry}"')
    if in_file:
        (root / "requirements.txt").write_text(entry + "\n")
    assert_uncertain(findings(root), "workflow_version_not_exact")


@pytest.mark.parametrize("entry", [".", "-e .", "-e ./", "--editable=.", "-e."])
@pytest.mark.parametrize("in_file", [False, True])
def test_local_current_project_install_warns_without_version_match(tmp_path, entry, in_file):
    root = workflow(tmp_path, "pip install -r requirements.txt" if in_file else f"pip install {entry}")
    if in_file:
        (root / "requirements.txt").write_text(entry + "\n")
    assert_uncertain(findings(root), "workflow_local_project_install")


def test_dynamic_requirement_in_file_warns(tmp_path):
    root = workflow(tmp_path, "pip install -r requirements.txt")
    (root / "requirements.txt").write_text("shipstate==${{ env.VERSION || '0.1.0' }}\n")
    assert_uncertain(findings(root), "workflow_dynamic_version")


@pytest.mark.parametrize("kind", ["workflow", "requirements", "workflow-directory"])
def test_symlinks_outside_root_are_warned_without_external_reads(tmp_path, kind):
    root = workflow(tmp_path, "pip install -r requirements.txt")
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / ("ci.yml" if kind != "requirements" else "requirements.txt")
    target.write_text("run: pip install shipstate==0.0.1\n" if kind != "requirements" else "shipstate==0.0.1\n")
    if kind == "workflow":
        link = root / ".github/workflows/ci.yml"
        link.unlink()
        link.symlink_to(target)
    elif kind == "requirements":
        (root / "requirements.txt").symlink_to(target)
    else:
        directory = root / ".github/workflows"
        (directory / "ci.yml").unlink()
        directory.rmdir()
        directory.symlink_to(outside, target_is_directory=True)
    original = Path.read_text

    def read(path, *args, **kwargs):
        assert path.resolve().is_relative_to(root), "External contents must never be read"
        return original(path, *args, **kwargs)

    with patch.object(Path, "read_text", read):
        assert_uncertain(findings(root), "workflow_requirements_unchecked" if kind == "requirements" else "workflow_outside_project")


@pytest.mark.parametrize("reference", ["missing.txt", "../outside.txt", "$FILE", "${{ inputs.file }}"])
def test_unresolved_paths_warn_without_pin_not_found_pass(tmp_path, reference):
    root = workflow(tmp_path, f"pip install -r {reference}")
    assert_uncertain(findings(root), "workflow_requirements_unchecked")


def test_absolute_outside_requirement_is_not_read(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("shipstate==0.0.1\n")
    root = workflow(tmp_path, f'pip install -r "{outside}"')
    assert_uncertain(findings(root), "workflow_requirements_unchecked")


@pytest.mark.parametrize("value", [True, False, 123])
def test_non_string_working_directory_is_ambiguous(tmp_path, value):
    root = workflow(tmp_path, "pip install -r requirements.txt")
    path = root / ".github/workflows/ci.yml"
    document = yaml.safe_load(path.read_text())
    document["jobs"]["test"]["steps"][0]["working-directory"] = value
    path.write_text(yaml.safe_dump(document))
    assert_uncertain(findings(root), "workflow_working_directory_ambiguous")


@pytest.mark.parametrize("installer", ["pip", "pip3", "python -m pip", "python3 -m pip", "uv pip", "env FOO=bar pip"])
@pytest.mark.parametrize("pin, code", [(VERSION, "workflow_pin_matches"), ("0.0.1", "workflow_version_drift")])
def test_existing_installers_and_real_command_chains_keep_exact_behavior(tmp_path, installer, pin, code):
    root = workflow(tmp_path, f'echo "&&" && {installer} install shipstate[dev]=={pin} || exit 1')
    assert any(item.code == code for item in findings(root))


@pytest.mark.parametrize("entry, code", [("shipstate>=0.1", "workflow_version_not_exact"), ("shipstate==0.0.1", "workflow_version_drift")])
def test_json_warning_exit_zero_and_fail_exit_one(project_factory, capsys, entry, code):
    root = project_factory(name=NAME, version=VERSION, changelog="## 0.1.0\n", readme="pip install shipstate==0.1.0\n", workflow=f"run: pip install {entry}\n")
    expected_exit = 1 if code == "workflow_version_drift" else 0
    assert main(["check", str(root), "--format", "json"]) == expected_exit
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == ("fail" if expected_exit else "pass")
    finding = next(item for item in payload["findings"] if item["code"] == code)
    assert finding["severity"] == ("fail" if expected_exit else "warn")



def test_working_directory_defaults_keep_step_job_workflow_priority(tmp_path):
    root = workflow(tmp_path, "pip install -r requirements.txt")
    for directory, pin in [("workflow", "0.0.1"), ("job", "0.0.1"), ("step", VERSION)]:
        (root / directory).mkdir()
        (root / directory / "requirements.txt").write_text(f"shipstate=={pin}\n")
    path = root / ".github/workflows/ci.yml"
    document = yaml.safe_load(path.read_text())
    document["defaults"] = {"run": {"working-directory": "workflow"}}
    document["jobs"]["test"]["defaults"] = {"run": {"working-directory": "job"}}
    document["jobs"]["test"]["steps"][0]["working-directory"] = "step"
    path.write_text(yaml.safe_dump(document))
    result = findings(root)
    assert any(item.code == "workflow_pin_matches" and item.source == "step/requirements.txt" for item in result)
    assert not any(item.severity == "fail" for item in result)


def test_nested_constraint_includes_keep_constraint_semantics(tmp_path):
    root = workflow(tmp_path, "pip install requests -c constraints.txt")
    (root / "constraints.txt").write_text("-r other.txt\n")
    (root / "other.txt").write_text("shipstate==0.0.1\n")
    assert not any(item.code == "workflow_version_drift" for item in findings(root))


@pytest.mark.parametrize("word", ["on", "off", "yes", "no"])
def test_yaml_boolean_directory_words_are_warned_without_coercion(tmp_path, word):
    root = workflow(tmp_path, "pip install -r requirements.txt")
    path = root / ".github/workflows/ci.yml"
    path.write_text(f"run: pip install -r requirements.txt\nworking-directory: {word}\n")
    assert_uncertain(findings(root), "workflow_working_directory_ambiguous")


def test_missing_requirement_does_not_hide_a_cycle_warning(tmp_path):
    root = workflow(tmp_path, "pip install -r a.txt")
    (root / "a.txt").write_text("-r b.txt\n")
    (root / "b.txt").write_text("-r a.txt\n")
    assert_uncertain(findings(root), "workflow_requirements_unchecked")
