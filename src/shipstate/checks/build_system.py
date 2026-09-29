from shipstate.models import Finding, Project


def check_build_system(project: Project) -> Finding:
    if not project.has_build_system:
        return Finding(
            code="build_system_missing",
            severity="warn",
            source="pyproject.toml",
            message="The [build-system] table was not found.",
        )
    if project.build_system_issue is not None:
        return Finding(
            code="build_system_invalid",
            severity="fail",
            source="pyproject.toml",
            message=project.build_system_issue,
        )
    return Finding(
        code="build_system_present",
        severity="pass",
        source="pyproject.toml",
        message="The [build-system] table is present.",
    )
