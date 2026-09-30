"""Shell words and additional uncertainty must not change proven inline pins."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from shipstate.checks.workflows import check_workflows
from shipstate.cli import main


def workflow(root, script, **step_options):
    directory = root / ".github/workflows"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "ci.yml").write_text(yaml.safe_dump({
        "jobs": {"test": {"runs-on": "ubuntu-latest", "steps": [
            {"run": script, "shell": "bash", **step_options},
        ]}},
    }))


@pytest.mark.parametrize("script, expected", [
    ("pip ins\\\ntall shipstate==0.0.1", "workflow_version_drift"),
    ("pip install shipstate==0\\\n.1.0", "workflow_pin_matches"),
    ("python -m p\\\nip install shipstate==0.0.1", "workflow_version_drift"),
    ('pip install "shipstate==0\\\n.1.0"', "workflow_pin_matches"),
    ('pip install "shipstate==0\\\n.0.1"', "workflow_version_drift"),
    ("pip install ship\\\nstate==0.0.1", "workflow_version_drift"),
])
def test_posix_continuation_removes_newline_without_adding_a_separator(tmp_path, script, expected):
    workflow(tmp_path, script)
    result = check_workflows(tmp_path, "shipstate", "0.1.0")
    assert [f.code for f in result] == [expected]


def test_single_quotes_preserve_literal_backslash_and_newline(tmp_path):
    workflow(tmp_path, "pip install 'shipstate==0\\\n.1.0'")
    result = check_workflows(tmp_path, "shipstate", "0.1.0")
    assert any(f.severity == "warn" for f in result)
    assert not any(f.severity in {"pass", "fail"} for f in result)


def test_comment_backslash_does_not_continue_comment_onto_next_command(tmp_path):
    workflow(tmp_path, "# documentation \\\npip install shipstate==0.0.1")
    result = check_workflows(tmp_path, "shipstate", "0.1.0")
    assert [f.code for f in result] == ["workflow_version_drift"]


def test_escaped_backslash_does_not_continue_the_line(tmp_path):
    workflow(tmp_path, "pip install shipstate==0\\\\\n.1.0")
    result = check_workflows(tmp_path, "shipstate", "0.1.0")
    assert any(f.severity == "warn" for f in result)
    assert not any(f.severity in {"pass", "fail"} for f in result)


@pytest.mark.parametrize("shell", ["pwsh", "cmd", "custom {0}"])
def test_unsupported_shell_does_not_claim_posix_continuation_proves_drift(tmp_path, shell):
    workflow(tmp_path, "pip ins\\\ntall shipstate==0.0.1", shell=shell)
    result = check_workflows(tmp_path, "shipstate", "0.1.0")
    assert [f.code for f in result] == ["workflow_shell_not_supported"]


@pytest.mark.parametrize("prefix", [
    "'FOO=bar'", '"FOO=bar"', "'FOO'=bar", "FOO\\=bar", "F'O'O=bar",
    "'PIP_REQUIREMENT=req.txt'",
])
def test_quoted_assignment_name_is_an_opaque_executable_not_an_assignment(tmp_path, prefix):
    workflow(tmp_path, f"{prefix} pip install shipstate==0.0.1")
    result = check_workflows(tmp_path, "shipstate", "0.1.0")
    assert any(f.code == "workflow_install_ambiguous" for f in result)
    assert not any(f.severity in {"pass", "fail"} for f in result)


@pytest.mark.parametrize("prefix", [
    "FOO=bar", "FOO='bar'", 'FOO="bar"', "FOO=one\\ two BAR=baz",
    "FOO='one two'", "env 'FOO=bar'", 'env "FOO=bar"',
    "FOO=bar env 'BAR=baz'",
])
def test_unquoted_assignment_name_and_env_utility_arguments_preserve_inline_pin(tmp_path, prefix):
    workflow(tmp_path, f"{prefix} pip install shipstate==0.0.1")
    result = check_workflows(tmp_path, "shipstate", "0.1.0")
    assert [f.code for f in result] == ["workflow_version_drift"]


@pytest.mark.parametrize("variable", ["PIP_REQUIREMENT", "PIP_CONSTRAINT"])
@pytest.mark.parametrize("placement", ["inline", "env", "export", "step"])
@pytest.mark.parametrize("isolated", [False, True])
def test_pip_environment_warning_cannot_hide_a_proven_stale_inline_pin(tmp_path, variable, placement, isolated):
    script = "pip " + ("--isolated " if isolated else "") + "install shipstate==0.0.1"
    options = {}
    if placement == "inline":
        script = f"{variable}=req.txt " + script
    elif placement == "env":
        script = f"env '{variable}=req.txt' " + script
    elif placement == "export":
        script = f"export {variable}=req.txt\n" + script
    else:
        options["env"] = {variable: "req.txt"}
    workflow(tmp_path, script, **options)
    (tmp_path / "req.txt").write_text("shipstate==0.1.0\n")
    original = Path.read_text

    def read(path, *args, **kwargs):
        assert path.name != "req.txt", "Unknown pip environment must not read guessed files"
        return original(path, *args, **kwargs)

    with patch.object(Path, "read_text", read):
        result = check_workflows(tmp_path, "shipstate", "0.1.0")
    assert any(f.code == "workflow_version_drift" and f.severity == "fail" for f in result)
    assert any(f.code == "workflow_pip_environment_ambiguous" and f.severity == "warn" for f in result)


@pytest.mark.parametrize("variable", ["PIP_REQUIREMENT", "PIP_CONSTRAINT"])
def test_environment_ambiguity_does_not_read_explicit_local_references(tmp_path, variable):
    workflow(tmp_path, f"{variable}=unknown.txt pip install shipstate==0.0.1 -r req.txt")
    (tmp_path / "req.txt").write_text("shipstate==0.1.0\n")
    original = Path.read_text

    def read(path, *args, **kwargs):
        assert path.name != "req.txt"
        return original(path, *args, **kwargs)

    with patch.object(Path, "read_text", read):
        result = check_workflows(tmp_path, "shipstate", "0.1.0")
    assert any(f.code == "workflow_version_drift" for f in result)
    assert any(f.severity == "warn" for f in result)


@pytest.mark.parametrize("script, code, exit_code", [
    ("pip ins\\\ntall shipstate==0.0.1", "workflow_version_drift", 1),
    ("pip install shipstate==0\\\n.1.0", "workflow_pin_matches", 0),
    ("'FOO=bar' pip install shipstate==0.0.1", "workflow_install_ambiguous", 0),
    ("PIP_REQUIREMENT=req.txt pip install shipstate==0.0.1", "workflow_version_drift", 1),
    ("PIP_CONSTRAINT=req.txt pip install shipstate==0.0.1", "workflow_version_drift", 1),
    ("PIP_REQUIREMENT=req.txt pip install requests", "workflow_pip_environment_ambiguous", 0),
    ("PIP_CONSTRAINT=req.txt pip install requests", "workflow_pip_environment_ambiguous", 0),
    ("pip --isolated install shipstate==0.0.1", "workflow_version_drift", 1),
])
def test_cli_aggregates_proven_failure_and_warning_without_changing_output_format(project_factory, capsys, script, code, exit_code):
    root = project_factory(name="shipstate", version="0.1.0", changelog="## 0.1.0\n", readme="pip install shipstate==0.1.0\n", workflow=None)
    workflow(root, script)
    assert main(["check", str(root), "--format", "json"]) == exit_code
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == ("fail" if exit_code else "pass")
    assert any(f["code"] == code for f in result["findings"])
