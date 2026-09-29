import subprocess
from pathlib import Path

import pytest

from shipstate.checks.runner import check_project
from shipstate.models import InputError
from shipstate.project import load_project

from conftest import git


def finding(result, code: str):
    return next(item for item in result.findings if item.code == code)


def test_complete_project_passes(project_factory):
    root = project_factory()

    result = check_project(root)

    assert result.status == "pass"
    assert {item.code for item in result.findings} == {
        "package_version_valid",
        "version_tag_matches_head",
        "changelog_version_found",
        "readme_pin_matches",
        "workflow_pin_matches",
        "license_present",
        "build_system_present",
    }


def test_missing_tag_fails(project_factory):
    result = check_project(project_factory(tag=False))

    assert result.status == "fail"
    assert finding(result, "missing_version_tag").expected == "v0.2.1"


def test_tag_on_previous_commit_fails(project_factory):
    root = project_factory()
    tagged_commit = git(root, "rev-parse", "HEAD")
    (root / "after-tag.txt").write_text("new commit\n", encoding="utf-8")
    git(root, "add", "after-tag.txt")
    git(root, "commit", "-m", "move HEAD after tag")

    result = check_project(root)

    assert result.status == "fail"
    mismatch = finding(result, "tag_commit_mismatch")
    assert mismatch.actual == tagged_commit
    assert mismatch.expected == git(root, "rev-parse", "HEAD")


def test_annotated_tag_on_head_passes(project_factory):
    root = project_factory(tag=False)
    git(root, "tag", "-a", "v0.2.1", "-m", "release")

    assert check_project(root).status == "pass"


def test_missing_changelog_fails(project_factory):
    result = check_project(project_factory(changelog=None))

    assert finding(result, "changelog_missing").severity == "fail"


def test_changelog_without_current_version_fails(project_factory):
    result = check_project(project_factory(changelog="## 0.2.0\n\nOld release.\n"))

    assert finding(result, "changelog_version_missing").expected == "0.2.1"


@pytest.mark.parametrize(
    "heading",
    ["## 0.2.1", "## [0.2.1]", "# 0.2.1", "# [0.2.1]"],
)
def test_supported_changelog_headings_pass(project_factory, heading):
    result = check_project(project_factory(changelog=f"{heading}\n\nNotes.\n"))

    assert finding(result, "changelog_version_found").actual == "0.2.1"


@pytest.mark.parametrize(
    "heading",
    ["## [0.2.1] - 2026-09-29", "### v0.2.1", "## [v0.2.1](https://example.invalid/releases/0.2.1)"],
)
def test_changelog_supports_dated_prefixed_and_linked_headings(project_factory, heading):
    result = check_project(project_factory(changelog=f"{heading}\n\nNotes.\n"))

    assert finding(result, "changelog_version_found").severity == "pass"


@pytest.mark.parametrize("fence", ["```text\n## 0.2.1\n```", "~~~markdown\n# [0.2.1]\n~~~"])
def test_changelog_heading_inside_fenced_code_is_ignored(project_factory, fence):
    result = check_project(project_factory(changelog=f"Example:\n\n{fence}\n"))

    assert finding(result, "changelog_version_missing").severity == "fail"


def test_changelog_heading_must_be_exact(project_factory):
    result = check_project(project_factory(changelog="## 0.2.10\n"))

    assert finding(result, "changelog_version_missing").severity == "fail"


def test_missing_version_tag_to_non_commit_object_is_mismatch(project_factory):
    root = project_factory(tag=False)
    blob = git(root, "hash-object", "-w", "--stdin")
    git(root, "update-ref", "refs/tags/v0.2.1", blob)

    result = check_project(root)

    assert finding(result, "tag_commit_mismatch").severity == "fail"


def test_non_git_directory_is_input_error(project_factory):
    root = project_factory(initialize_git=False)

    with pytest.raises(InputError) as exc_info:
        check_project(root)

    assert exc_info.value.code == "not_git_repository"


def test_git_os_error_is_reported_as_input_error(monkeypatch, tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )

    def fail_to_start(*args, **kwargs):
        raise PermissionError("access denied")

    monkeypatch.setattr("shipstate.git.subprocess.run", fail_to_start)

    with pytest.raises(InputError) as exc_info:
        check_project(root)

    assert exc_info.value.code == "git_execution_failed"


def test_dynamic_version_is_rejected(project_factory):
    root = project_factory(dynamic="version")

    with pytest.raises(InputError) as exc_info:
        load_project(root)

    assert exc_info.value.code == "dynamic_version_not_supported"


def test_missing_project_version_is_input_error(tmp_path: Path):
    root = tmp_path / "invalid"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "example"\n', encoding="utf-8")

    with pytest.raises(InputError) as exc_info:
        load_project(root)

    assert exc_info.value.code == "project_version_missing"


def test_missing_project_name_is_input_error(tmp_path: Path):
    root = tmp_path / "missing-name"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n', encoding="utf-8")

    with pytest.raises(InputError) as exc_info:
        load_project(root)

    assert exc_info.value.code == "project_name_missing"


@pytest.mark.parametrize("contents", ["not toml [", "[build-system]\n"])
def test_invalid_or_missing_project_table_is_input_error(tmp_path: Path, contents: str):
    root = tmp_path / "invalid"
    root.mkdir(exist_ok=True)
    (root / "pyproject.toml").write_text(contents, encoding="utf-8")

    with pytest.raises(InputError) as exc_info:
        load_project(root)

    assert exc_info.value.code in {"invalid_pyproject", "project_metadata_missing"}


def test_invalid_project_version_is_input_error(tmp_path: Path):
    root = tmp_path / "invalid-version"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "not-a-version"\n',
        encoding="utf-8",
    )

    with pytest.raises(InputError) as exc_info:
        load_project(root)

    assert exc_info.value.code == "invalid_project_version"


def test_project_name_with_surrounding_whitespace_is_rejected(project_factory):
    root = project_factory(name=" meshcontract ")

    with pytest.raises(InputError) as exc_info:
        load_project(root)

    assert exc_info.value.code == "project_name_invalid"


def test_invalid_dynamic_metadata_is_input_error(project_factory):
    root = project_factory()
    pyproject = root / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "meshcontract"\nversion = "0.2.1"\ndynamic = "description"\n',
        encoding="utf-8",
    )

    with pytest.raises(InputError) as exc_info:
        load_project(root)

    assert exc_info.value.code == "invalid_project_dynamic"


@pytest.mark.parametrize(
    "build_system",
    [
        '[build-system]\nrequires = "setuptools"\nbuild-backend = "setuptools.build_meta"\n',
        '[build-system]\nrequires = ["setuptools"]\nbuild-backend = "bad backend"\n',
    ],
)
def test_malformed_build_system_fails(project_factory, build_system):
    root = project_factory()
    pyproject = root / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "meshcontract"\nversion = "0.2.1"\n\n' + build_system,
        encoding="utf-8",
    )

    result = check_project(root)

    assert finding(result, "build_system_invalid").severity == "fail"
