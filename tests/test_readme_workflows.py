from shipcheck.checks.runner import check_project


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


def test_readme_other_package_pins_do_not_match(project_factory):
    result = check_project(
        project_factory(
            readme=(
                "Install requests==2.32.0 and my-meshcontract==0.1.0.\n"
                "## Changelog excerpt\n\nHistorical install: meshcontract==0.1.0\n"
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
