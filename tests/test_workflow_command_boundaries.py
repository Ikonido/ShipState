"""Install detection must not prove consistency from unsupported command forms."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from shipstate.checks.workflows import check_workflows


def project(tmp_path, script, *, shell="bash", environment=None):
    root = tmp_path / "project"
    directory = root / ".github/workflows"
    directory.mkdir(parents=True)
    step = {"run": script, "shell": shell}
    if environment is not None:
        step["env"] = environment
    (directory / "ci.yml").write_text(yaml.safe_dump({
        "jobs": {"test": {"runs-on": "ubuntu-latest", "steps": [step]}}
    }))
    return root


def inspect(root):
    return check_workflows(root, "shipstate", "0.1.0")


def only_warning(result, code):
    assert any(f.code == code and f.severity == "warn" for f in result)
    assert not any(f.severity in {"pass", "fail"} for f in result)


@pytest.mark.parametrize("installer", [
    "pip", "pip3", "pip3.12", "python -m pip", "python3 -m pip",
])
@pytest.mark.parametrize("options", [
    "--disable-pip-version-check", "--isolated", "--timeout 15 --retries=2",
    '--log "install log.txt" --quiet',
])
@pytest.mark.parametrize("pin, expected", [
    ("0.0.1", "workflow_version_drift"), ("0.1.0", "workflow_pin_matches"),
])
def test_known_global_option_arity_preserves_exact_pin_checks(tmp_path, installer, options, pin, expected):
    root = project(tmp_path, f"{installer} {options} install shipstate=={pin}")
    result = inspect(root)
    assert any(f.code == expected for f in result)
    assert not any(f.severity == "warn" for f in result)


@pytest.mark.parametrize("script", [
    "pip --unknown value install shipstate==0.0.1",
    "python -m pip --unknown=install install shipstate==0.0.1",
    "pip --help install shipstate==0.0.1",
    "pip --version install shipstate==0.0.1",
    "pip --timeout install shipstate==0.0.1",
])
def test_unknown_or_non_installing_global_options_cannot_establish_a_pin(tmp_path, script):
    only_warning(inspect(project(tmp_path, script)), "workflow_install_ambiguous")


@pytest.mark.parametrize("script", [
    "cd subdir && pip install -r requirements.txt",
    "pushd subdir && pip install -r requirements.txt",
    "command cd subdir && pip install -r requirements.txt",
    "command -p -- cd subdir && pip install -r requirements.txt",
    "builtin cd subdir && pip install -r requirements.txt",
    "(cd subdir && pip install -r requirements.txt)",
    "(cd subdir && pip install -r requirements.txt\n)",
    "(\ncd subdir\npip install -r requirements.txt\n)",
    "{ cd subdir; pip install -c constraints.txt shipstate; }",
])
@pytest.mark.parametrize("root_pin, sub_pin", [("0.0.1", "0.1.0"), ("0.1.0", "0.0.1")])
def test_wrapped_directory_changes_never_read_guessed_requirement_paths(tmp_path, script, root_pin, sub_pin):
    root = project(tmp_path, script)
    (root / "subdir").mkdir()
    for name in ["requirements.txt", "constraints.txt"]:
        (root / name).write_text(f"shipstate=={root_pin}\n")
        (root / "subdir" / name).write_text(f"shipstate=={sub_pin}\n")
    original = Path.read_text

    def read(path, *args, **kwargs):
        assert path.suffix not in {".txt"}, "Ambiguous cwd must not read local requirements"
        return original(path, *args, **kwargs)

    with patch.object(Path, "read_text", read):
        only_warning(inspect(root), "workflow_working_directory_ambiguous")


@pytest.mark.parametrize("shell", ["pwsh", "powershell", "cmd", "cmd.exe", "custom {0}"])
@pytest.mark.parametrize("script", [
    "& 'pip' install shipstate==0.0.1",
    '"pip3" --disable-pip-version-check install shipstate==0.0.1',
    "pip \\\n install shipstate==0.0.1",
])
def test_unsupported_shell_quoted_invocations_warn(tmp_path, shell, script):
    only_warning(inspect(project(tmp_path, script, shell=shell)), "workflow_shell_not_supported")


@pytest.mark.parametrize("script", [
    "${{ env.INSTALL_COMMAND }} shipstate==0.0.1",
    "${INSTALL_COMMAND} shipstate==0.0.1",
    "${{ env.INSTALL_COMMAND }} && pip install -r requirements.txt",
    "custom-installer install shipstate==0.0.1",
])
def test_opaque_install_like_commands_warn_without_declaring_drift(tmp_path, script):
    only_warning(inspect(project(tmp_path, script)), "workflow_install_ambiguous")


@pytest.mark.parametrize("variable", ["PIP_REQUIREMENT", "PIP_CONSTRAINT", "PIP_CONFIG_FILE", "PIP_INDEX_URL"])
@pytest.mark.parametrize("placement", ["inline", "env_prefix", "export", "workflow", "job", "step"])
def test_explicit_pip_environment_settings_warn_without_reading_constraint_only_pins(tmp_path, variable, placement):
    script = "pip install requests"
    if placement == "inline":
        script = f"{variable}=req.txt " + script
    elif placement == "env_prefix":
        script = f"env {variable}=req.txt " + script
    elif placement == "export":
        script = f"export {variable}=req.txt\n" + script
    root = project(tmp_path, script)
    path = root / ".github/workflows/ci.yml"
    document = yaml.safe_load(path.read_text())
    if placement in {"workflow", "job", "step"}:
        target = document if placement == "workflow" else document["jobs"]["test"]
        if placement == "step":
            target = target["steps"][0]
        target["env"] = {variable: "req.txt"}
        path.write_text(yaml.safe_dump(document))
    (root / "req.txt").write_text("shipstate==0.0.1\n")
    original = Path.read_text

    def read(path, *args, **kwargs):
        assert path.name != "req.txt", "Unsupported env configuration must not be partially interpreted"
        return original(path, *args, **kwargs)

    with patch.object(Path, "read_text", read):
        only_warning(inspect(root), "workflow_pip_environment_ambiguous")


@pytest.mark.parametrize("script", [
    "PIP_REQUIREMENT=$REQ pip install requests",
    "PIP_REQUIREMENT=missing.txt pip install requests",
    "PIP_CONSTRAINT=../outside.txt pip install shipstate==0.0.1",
])
def test_unresolved_pip_environment_does_not_establish_an_exact_install(tmp_path, script):
    only_warning(inspect(project(tmp_path, script)), "workflow_pip_environment_ambiguous")


@pytest.mark.parametrize("script", [
    "echo 'pip --unknown install shipstate==0.0.1'",
    "echo '${{ env.INSTALL_COMMAND }} shipstate==0.0.1'",
    "printf '%s\\n' 'PIP_REQUIREMENT=req.txt pip install requests'",
    "# PIP_REQUIREMENT=req.txt pip install shipstate==0.0.1\necho ok",
    'echo "&&" pip --disable-pip-version-check install shipstate==0.0.1',
])
def test_install_fallback_does_not_warn_on_simple_documentation(tmp_path, script):
    result = inspect(project(tmp_path, script))
    assert not any(f.severity in {"warn", "fail"} for f in result)


def test_plain_environment_values_and_pip_option_values_are_not_install_commands(tmp_path):
    root = project(tmp_path, 'env FOO=bar pip --log "pip install shipstate==0.0.1" install shipstate==0.1.0')
    result = inspect(root)
    assert any(f.code == "workflow_pin_matches" for f in result)
    assert not any(f.severity in {"warn", "fail"} for f in result)
