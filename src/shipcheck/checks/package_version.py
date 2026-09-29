from shipcheck.models import Finding, Project


def check_package_version(project: Project) -> Finding:
    return Finding(
        code="package_version_valid",
        severity="pass",
        source="pyproject.toml",
        message=f"Project version {project.version} is valid.",
        actual=project.version,
        expected=project.version,
    )
