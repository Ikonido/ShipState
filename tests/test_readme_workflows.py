import pytest

from shipstate.checks.runner import check_project


def codes(result):
    return {item.code for item in result.findings}


def test_readme_old_self_pin_is_drift(project_factory):
    result = check_project(project_factory(readme="pip install meshcontract==0.2.0\n"))

    drift = next(item for item in result.findings if item.code == "readme_version_drift")
    assert result.status == "fail"
    assert drift.actual == "0.2.0"
    assert drift.expected == "0.2.1"


def test_readme_correct_self_pin_passes(project_factory):
    result = check_project(project_factory(readme="pip install meshcontract==0.2.1\n"))

    assert "readme_pin_matches" in codes(result)
    assert "readme_version_drift" not in codes(result)


def test_readme_extra_self_pin_is_checked(project_factory):
    result = check_project(project_factory(readme="pip install meshcontract[dev]==0.2.0\n"))

    drift = next(item for item in result.findings if item.code == "readme_version_drift")
    assert drift.actual == "0.2.0"


@pytest.mark.parametrize("dependency_name", ["ship-state", "SHIP_STATE", "ship.state", "ship___state", "Ship--State"])
def test_readme_distribution_name_variants_are_checked(project_factory, dependency_name):
    result = check_project(
        project_factory(name="ship-state", readme=f"pip install {dependency_name}==0.2.0\n")
    )

    drift = next(item for item in result.findings if item.code == "readme_version_drift")
    assert result.status == "fail"
    assert drift.actual == "0.2.0"


def test_readme_non_changelog_heading_does_not_hide_a_pin(project_factory):
    result = check_project(
        project_factory(readme="## Notes about the changelog parser\n\npip install meshcontract==0.2.0\n")
    )

    assert result.status == "fail"
    assert "readme_version_drift" in codes(result)


@pytest.mark.parametrize(
    "heading",
    ["## Changelog parser implementation notes", "## Release notes parser implementation notes"],
)
def test_readme_named_sections_do_not_hide_stale_pins(project_factory, heading):
    result = check_project(
        project_factory(readme=f"{heading}\n\npip install meshcontract==0.2.0\n")
    )

    assert result.status == "fail"
    assert "readme_version_drift" in codes(result)


def test_readme_fenced_heading_does_not_hide_a_pin(project_factory):
    result = check_project(
        project_factory(readme="```markdown\n## Changelog excerpt\n```\n\npip install meshcontract==0.2.0\n")
    )

    assert result.status == "fail"
    assert "readme_version_drift" in codes(result)


def test_readme_other_package_pins_do_not_match(project_factory):
    result = check_project(
        project_factory(
            readme=(
                "Install requests==2.32.0 and my-meshcontract==0.1.0.\n"
            )
        )
    )

    assert result.status == "pass"
    assert "readme_version_drift" not in codes(result)


def test_readme_missing_is_warning(project_factory):
    result = check_project(project_factory(readme=None))

    warning = next(item for item in result.findings if item.code == "readme_missing")
    assert warning.severity == "warn"
    assert result.status == "pass"


def test_workflow_old_self_pin_is_drift(project_factory):
    result = check_project(
        project_factory(workflow="run: python -m pip install meshcontract==0.2.0\n")
    )

    drift = next(item for item in result.findings if item.code == "workflow_version_drift")
    assert result.status == "fail"
    assert drift.actual == "0.2.0"
    assert drift.expected == "0.2.1"


def test_workflow_correct_pin_passes(project_factory):
    result = check_project(project_factory(workflow="run: pip install meshcontract==0.2.1\n"))

    assert "workflow_pin_matches" in codes(result)
    assert "workflow_version_drift" not in codes(result)


def test_workflow_comment_is_not_an_install_command(project_factory):
    result = check_project(
        project_factory(workflow="# run: pip install meshcontract==0.1.0\n")
    )

    assert result.status == "pass"
    assert "workflow_version_drift" not in codes(result)


def test_workflow_yaml_extension_and_name_normalization(project_factory):
    root = project_factory(name="my_package", workflow=None)
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "extra.yaml").write_text(
        "run: python -m pip install my-package==0.2.0\n",
        encoding="utf-8",
    )

    result = check_project(root)

    assert "workflow_version_drift" in codes(result)


@pytest.mark.parametrize(
    ("installer", "suffix"),
    [("pip install", ""), ("python -m pip install", ""), ("pip install", "[dev]")],
)
def test_workflow_shell_continuations_detect_stale_self_pins(project_factory, installer, suffix):
    workflow = f"run: |\n  {installer} \\\n    meshcontract{suffix}==0.2.0\n"
    result = check_project(project_factory(workflow=workflow))

    drift = next(item for item in result.findings if item.code == "workflow_version_drift")
    assert drift.actual == "0.2.0"


@pytest.mark.parametrize(
    ("installer", "suffix"),
    [("pip install", ""), ("python -m pip install", ""), ("pip install", "[dev]")],
)
def test_workflow_shell_continuations_allow_current_self_pin(project_factory, installer, suffix):
    workflow = f"run: |\n  {installer} \\\n    meshcontract{suffix}==0.2.1\n"
    result = check_project(project_factory(workflow=workflow))

    assert result.status == "pass"
    assert "workflow_pin_matches" in codes(result)
    assert "workflow_version_drift" not in codes(result)


@pytest.mark.parametrize("dependency_name", ["ship-state", "SHIP_STATE", "ship.state", "ship___state", "Ship--State"])
def test_workflow_distribution_name_variants_are_checked(project_factory, dependency_name):
    root = project_factory(
        name="ship-state",
        workflow=f"run: pip install {dependency_name}==0.2.0\n",
    )

    result = check_project(root)

    drift = next(item for item in result.findings if item.code == "workflow_version_drift")
    assert result.status == "fail"
    assert drift.actual == "0.2.0"


def test_workflow_inline_comment_does_not_create_a_false_pin(project_factory):
    result = check_project(
        project_factory(workflow="run: pip install requests==2.32.0 # meshcontract==0.2.0\n")
    )

    assert result.status == "pass"
    assert "workflow_version_drift" not in codes(result)


def test_workflow_comment_lines_and_inline_comment_pins_are_ignored(project_factory):
    result = check_project(
        project_factory(
            workflow=(
                    "run: |\n"
                    "  # pip install meshcontract==0.2.0\n"
                    "  python -m pip install pytest  # meshcontract==0.2.0\n"
            )
        )
    )

    assert result.status == "pass"
    assert "workflow_version_drift" not in codes(result)


def test_workflow_real_pin_before_inline_comment_is_still_checked(project_factory):
    result = check_project(
        project_factory(workflow="run: pip install meshcontract==0.2.0  # real command\n")
    )

    assert result.status == "fail"
    assert "workflow_version_drift" in codes(result)


@pytest.mark.parametrize("expression", ["$VERSION", "${VERSION}"])
def test_workflow_dynamic_version_is_a_warning_not_a_failure(project_factory, expression):
    result = check_project(
        project_factory(workflow=f"run: python -m pip install meshcontract=={expression}\n")
    )

    dynamic = next(item for item in result.findings if item.code == "workflow_dynamic_version")
    assert result.status == "pass"
    assert dynamic.severity == "warn"
    assert dynamic.actual == expression
    assert dynamic.expected == "0.2.1"
    assert "dynamic version cannot be verified statically" in dynamic.message


def test_workflow_shell_comment_does_not_create_a_false_pin(project_factory):
    result = check_project(
        project_factory(workflow='run: "pip install requests==2.32.0 # ignored" # meshcontract==0.2.0\n')
    )

    assert result.status == "pass"
    assert "workflow_version_drift" not in codes(result)
