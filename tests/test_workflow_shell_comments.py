"""Comment starts follow POSIX word boundaries, including continued lines."""

import json
import shlex

import pytest
import yaml

from shipstate.checks.workflows import _logical_commands, check_workflows
from shipstate.cli import main


def workflow(root, script):
    directory = root / ".github/workflows"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "ci.yml").write_text(yaml.safe_dump({
        "jobs": {"test": {"runs-on": "ubuntu-latest", "steps": [
            {"run": script, "shell": "bash"},
        ]}},
    }))


@pytest.mark.parametrize("script", [
    "echo ok;\\\n# documentation && pip install shipstate==0.0.1",
    "echo ok;# comment && pip install shipstate==0.0.1",
    "echo ok; # comment && pip install shipstate==0.0.1",
    "echo ok;\\\n\\\n# comment ; pip install shipstate==0.0.1",
    "echo ok;# PIP_REQUIREMENT=req.txt; pip install shipstate==0.0.1",
    "echo ok;# 'FOO=bar' && pip install shipstate==0.0.1",
    "echo ok;# pip ins\\\ntall shipstate==0.0.1",
    "echo ok &&# comment && pip install shipstate==0.0.1\necho done",
    "false ||# comment && pip install shipstate==0.0.1\necho done",
])
def test_comment_examples_do_not_become_install_commands(tmp_path, script):
    workflow(tmp_path, script)
    result = check_workflows(tmp_path, "shipstate", "0.1.0")
    assert [f.code for f in result] == ["workflow_pin_not_found"]


@pytest.mark.parametrize("script", [
    "echo ok && # comment\npip install shipstate==0.0.1",
    "echo ok &&# comment\npip install shipstate==0.0.1",
    "false ||# comment\npip install shipstate==0.0.1",
    "echo ok;# comment\npip install shipstate==0.0.1",
])
def test_comment_ends_at_newline_and_preserves_real_following_install(tmp_path, script):
    workflow(tmp_path, script)
    result = check_workflows(tmp_path, "shipstate", "0.1.0")
    assert [f.code for f in result] == ["workflow_version_drift"]


@pytest.mark.parametrize("script, argument", [
    ("echo foo#bar", "foo#bar"),
    ("echo '# pip install shipstate==0.0.1'", "# pip install shipstate==0.0.1"),
    ('echo "# pip install shipstate==0.0.1"', "# pip install shipstate==0.0.1"),
    ("echo ok\\\n#comment", "ok#comment"),
    ("echo \\#word", "#word"),
    ("echo X\\ #word", "X #word"),
    ("echo X\\;#word", "X;#word"),
    ("echo ''#word", "#word"),
    ('echo ""#word', "#word"),
    ("echo {#literal", "{#literal"),
])
def test_quoted_escaped_and_word_internal_hashes_remain_arguments(script, argument):
    # Expected argv comes from Bash word semantics, including escaped spaces
    # and empty quoted prefixes: all these hashes belong to a word.
    commands = _logical_commands(script)
    assert len(commands) == 1
    assert shlex.split(commands[0]) == ["echo", argument]


@pytest.mark.parametrize("script, expected", [
    ("(# comment && pip install shipstate==0.0.1\necho ok\n)", ["(", "echo ok", ")"]),
    ("{ # comment && pip install shipstate==0.0.1\necho ok;\n}", ["{", "echo ok;", "}"]),
    # Unlike '(', '{' is a reserved word, not a lexical operator. Without a
    # separating space, Bash treats '{#literal' as a command word.
    ("{#literal", ["{#literal"]),
])
def test_group_boundary_comments_without_interpreting_group_execution(script, expected):
    assert _logical_commands(script) == expected


@pytest.mark.parametrize("script, expected_exit", [
    ("echo ok;\\\n# documentation && pip install shipstate==0.0.1", 0),
    ("echo ok && # comment\npip install shipstate==0.0.1", 1),
])
def test_cli_preserves_exit_and_json_status_for_comment_boundary(project_factory, capsys, script, expected_exit):
    root = project_factory(name="shipstate", version="0.1.0", changelog="## 0.1.0\n", readme="pip install shipstate==0.1.0\n", workflow=None)
    workflow(root, script)
    assert main(["check", str(root), "--format", "json"]) == expected_exit
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == ("fail" if expected_exit else "pass")
    assert any(f["code"] == "workflow_version_drift" for f in result["findings"]) == bool(expected_exit)
