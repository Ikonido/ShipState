from pathlib import Path

from shipstate.checks.build_system import check_build_system
from shipstate.checks.changelog import check_changelog
from shipstate.checks.license import check_license
from shipstate.checks.package_version import check_package_version
from shipstate.checks.readme import check_readme
from shipstate.checks.tag import check_tag
from shipstate.checks.workflows import check_workflows
from shipstate.git import get_git_context
from shipstate.models import CheckResult
from shipstate.project import load_project


def check_project(path: Path) -> CheckResult:
    project = load_project(path)
    git = get_git_context(path)
    findings = [
        check_package_version(project),
        check_tag(path, project.version, git),
        check_changelog(path, project.version),
        *check_readme(path, project.name, project.version),
        *check_workflows(path, project.name, project.version),
        check_license(path),
        *check_build_system(project),
    ]
    return CheckResult(project=project, findings=tuple(findings))
