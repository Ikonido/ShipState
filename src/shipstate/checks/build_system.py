from shipstate.models import Finding, Project


def check_build_system(project: Project) -> list[Finding]:
    if not project.has_build_system:
        return [
            Finding(
                code="build_system_missing",
                severity="warn",
                source="pyproject.toml",
                message="The [build-system] table was not found.",
            )
        ]
    findings = [
        Finding(
            code=code,
            severity="warn",
            source="pyproject.toml",
            message=(
                "The [build-system].requires field was not found."
                if code == "build_system_requires_missing"
                else "The [build-system].build-backend field was not found."
            ),
        )
        for code in project.build_system_warnings
    ]
    if project.build_system_issue is not None:
        findings.append(
            Finding(
                code="build_system_invalid",
                severity="fail",
                source="pyproject.toml",
                message=project.build_system_issue,
            )
        )
    if findings:
        return findings
    return [
        Finding(
            code="build_system_present",
            severity="pass",
            source="pyproject.toml",
            message="The [build-system] table is present.",
        )
    ]
