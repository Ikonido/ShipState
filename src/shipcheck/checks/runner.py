from pathlib import Path

from shipcheck.checks.build_system import check_build_system
from shipcheck.checks.changelog import check_changelog
from shipcheck.checks.license import check_license
from shipcheck.checks.package_version import check_package_version
from shipcheck.checks.readme import check_readme
from shipcheck.checks.tag import check_tag
from shipcheck.checks.workflows import check_workflows
from shipcheck.git import get_git_context
from shipcheck.models import CheckResult
from shipcheck.project import load_project


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
        check_build_system(project),
    ]
    return CheckResult(project=project, findings=tuple(findings))
